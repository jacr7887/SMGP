# myapp/management/commands/ensure_superuser.py

import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import DEFAULT_DB_ALIAS

User = get_user_model() # Esto será myapp.Usuario

class Command(BaseCommand):
    help = (
        "Crea un superusuario si no existe, o actualiza sus detalles/contraseña "
        "si ya existe, utilizando variables de entorno. "
        "Se espera que USERNAME_FIELD sea 'email'."
    )

    def handle(self, *args, **options):
        db = options.get('database', DEFAULT_DB_ALIAS)

        # Nombres de las variables de entorno que se esperan
        env_email_login = 'DJANGO_SUPERUSER_EMAIL'  # Para el USERNAME_FIELD y el campo email
        env_password = 'DJANGO_SUPERUSER_PASSWORD'
        env_primer_nombre = 'DJANGO_SUPERUSER_PRIMER_NOMBRE'
        env_primer_apellido = 'DJANGO_SUPERUSER_PRIMER_APELLIDO'
        env_username_explicit = 'DJANGO_SUPERUSER_USERNAME_EXPLICIT' # Opcional, para el campo 'username'

        # Leer los valores de las variables de entorno
        email_login = os.getenv(env_email_login)
        password = os.getenv(env_password)
        primer_nombre = os.getenv(env_primer_nombre)
        primer_apellido = os.getenv(env_primer_apellido)
        username_explicit = os.getenv(env_username_explicit) # Puede ser None

        # Validar que las variables de entorno esenciales estén configuradas
        required_env_vars = {
            env_email_login: email_login,
            env_password: password,
            env_primer_nombre: primer_nombre,
            env_primer_apellido: primer_apellido,
        }

        missing_vars = [var_name for var_name, value in required_env_vars.items() if not value]
        if missing_vars:
            self.stdout.write(self.style.ERROR(
                f"Las siguientes variables de entorno para el superusuario no están configuradas o están vacías: {', '.join(missing_vars)}. "
                "No se puede crear/actualizar el superusuario."
            ))
            # Considera lanzar CommandError para que el script de despliegue falle si es crítico
            # raise CommandError(f"Missing superuser environment variables: {', '.join(missing_vars)}")
            return

        # Argumentos para buscar/obtener el usuario (basado en USERNAME_FIELD)
        user_lookup_kwargs = {User.USERNAME_FIELD: email_login}

        try:
            if User.objects.using(db).filter(**user_lookup_kwargs).exists():
                self.stdout.write(self.style.SUCCESS(
                    f"Superusuario con {User.USERNAME_FIELD}='{email_login}' ya existe. Actualizando..."
                ))
                user = User.objects.using(db).get(**user_lookup_kwargs)
                
                # Actualizar contraseña
                user.set_password(password)
                
                # Actualizar campos definidos en .env
                user.email = email_login # Asegurar que el email (USERNAME_FIELD) es el del .env
                user.primer_nombre = primer_nombre
                user.primer_apellido = primer_apellido

                # Actualizar username explícito si se proporcionó y es diferente
                if username_explicit and user.username != username_explicit:
                    # Verificar si el nuevo username explícito ya está en uso por OTRO usuario
                    if User.objects.using(db).filter(username=username_explicit).exclude(pk=user.pk).exists():
                        self.stdout.write(self.style.WARNING(
                            f"El username explícito '{username_explicit}' ya está en uso por otro usuario. No se actualizará el username."
                        ))
                    else:
                        user.username = username_explicit
                
                # Asegurar que los flags y campos de superusuario estén correctos
                # según tu UsuarioManager.create_superuser
                user.nivel_acceso = 5
                if hasattr(User, 'tipo_usuario'): # Verificar si el campo existe
                    # Tu manager usa CommonChoices, aquí replicamos la lógica para 'ADMIN'
                    # Deberías importar CommonChoices si quieres usarlo directamente
                    # from myapp.commons import CommonChoices
                    # tipo_admin = next((c[0] for c in CommonChoices.TIPO_USUARIO if c[0] == 'ADMIN'), "ADMIN_FALLBACK")
                    # user.tipo_usuario = tipo_admin
                    user.tipo_usuario = "ADMIN" # O el valor de string exacto esperado

                user.is_staff = True
                user.is_superuser = True
                user.activo = True # Usando tu campo 'activo' para consistencia

                user.save(using=db) # El método save() de tu modelo maneja is_active y grupos
                self.stdout.write(self.style.SUCCESS(
                    f"Detalles y contraseña del superusuario '{email_login}' actualizados correctamente."
                ))

            else:
                self.stdout.write(
                    f"Creando superusuario con {User.USERNAME_FIELD}='{email_login}'..."
                )
                
                # Campos adicionales para pasar a create_superuser
                # Tu UsuarioManager.create_superuser espera: email, password, **extra_fields
                # Los **extra_fields relevantes aquí son primer_nombre, primer_apellido
                # y opcionalmente 'username' si quieres un valor explícito.
                # Otros campos como nivel_acceso, tipo_usuario, is_staff, is_superuser, activo
                # son establecidos DENTRO de tu UsuarioManager.create_superuser.
                
                creation_kwargs = {
                    'primer_nombre': primer_nombre,
                    'primer_apellido': primer_apellido,
                }
                
                if username_explicit:
                    # Verificar si el username explícito ya está en uso
                    if User.objects.using(db).filter(username=username_explicit).exists():
                        self.stdout.write(self.style.ERROR(
                            f"El username explícito '{username_explicit}' de la variable de entorno ya está en uso. "
                            "No se puede crear el superusuario con este username. "
                            "Omita la variable '{env_username_explicit}' para permitir la autogeneración."
                        ))
                        raise CommandError(f"Username explícito '{username_explicit}' ya existe.")
                    creation_kwargs['username'] = username_explicit
                
                # No necesitamos pasar 'nivel_acceso', 'tipo_usuario', 'is_staff', 
                # 'is_superuser', 'activo' aquí porque tu UsuarioManager.create_superuser
                # los establece internamente.

                User.objects.db_manager(db).create_superuser(
                    email=email_login, # El valor del USERNAME_FIELD
                    password=password,
                    **creation_kwargs
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Superusuario con {User.USERNAME_FIELD}='{email_login}' creado exitosamente."
                ))

        except CommandError: # Re-lanzar CommandError para que el script de despliegue falle
            raise
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Ocurrió un error inesperado: {e}"
            ))
            import traceback
            traceback.print_exc()
            # Considera lanzar CommandError aquí también si este fallo es crítico
            # raise CommandError(f"Error inesperado: {e}")