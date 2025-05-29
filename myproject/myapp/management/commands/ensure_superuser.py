# myapp/management/commands/ensure_superuser.py

import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import DEFAULT_DB_ALIAS
# from myapp.commons import CommonChoices # Descomenta si realmente necesitas CommonChoices aquí

User = get_user_model()  # Esto será myapp.Usuario


class Command(BaseCommand):
    help = (
        "Crea un superusuario si no existe, o actualiza su contraseña y "
        "campos básicos si ya existe, utilizando variables de entorno. "
        "Se espera que USERNAME_FIELD sea 'email'."
    )

    def handle(self, *args, **options):
        db = options.get('database', DEFAULT_DB_ALIAS)

        # Nombres de las variables de entorno
        env_email = 'DJANGO_SUPERUSER_EMAIL'
        env_password = 'DJANGO_SUPERUSER_PASSWORD'
        env_primer_nombre = 'DJANGO_SUPERUSER_PRIMER_NOMBRE'
        env_primer_apellido = 'DJANGO_SUPERUSER_PRIMER_APELLIDO'
        # Opcional: si tu modelo Usuario tiene un campo 'username' separado y quieres controlarlo
        # env_username_explicit = 'DJANGO_SUPERUSER_USERNAME_EXPLICIT'

        # Leer valores del entorno
        email = os.getenv(env_email)
        password = os.getenv(env_password)
        primer_nombre = os.getenv(env_primer_nombre)
        primer_apellido = os.getenv(env_primer_apellido)
        # username_explicit = os.getenv(env_username_explicit) # Descomenta si usas un campo username separado

        # Validar variables esenciales
        if not all([email, password, primer_nombre, primer_apellido]):
            missing = [var for var, val in [
                (env_email, email), (env_password, password),
                (env_primer_nombre, primer_nombre), (env_primer_apellido, primer_apellido)
            ] if not val]
            raise CommandError(
                f"Faltan variables de entorno para superusuario: {', '.join(missing)}. "
                "No se puede crear/actualizar."
            )

        # Argumentos para buscar el usuario (USERNAME_FIELD debe ser 'email' para tu modelo)
        if User.USERNAME_FIELD != 'email':
            raise CommandError(
                f"Este script espera que USERNAME_FIELD de tu modelo User ('{User.USERNAME_FIELD}') sea 'email'."
            )

        # Usamos 'email' directamente ya que es tu USERNAME_FIELD
        user_lookup_kwargs = {'email': email}

        try:
            user, created = User.objects.using(db).get_or_create(
                email=email,  # Usar el campo USERNAME_FIELD para la búsqueda/creación única
                defaults={
                    'primer_nombre': primer_nombre,
                    'primer_apellido': primer_apellido,
                    # Otros campos que tu modelo podría requerir en la creación y que no establece el manager
                    # Por ejemplo, si 'username' es un campo separado y requerido:
                    # 'username': username_explicit or User.objects.normalize_email(email).split('@')[0] # Un default para username
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"Superusuario con email='{email}' creado exitosamente."
                ))
                # El manager create_superuser debería manejar is_staff, is_superuser, activo, etc.
                # Solo necesitamos establecer la contraseña aquí si get_or_create no la establece
                # o si el manager no es llamado por get_or_create para los defaults.
                # Usualmente, create_superuser es un método de manager, get_or_create usa el manager .create()
                # Así que es mejor llamar a create_superuser directamente si no existe.
                # Vamos a rehacer esta parte para llamar explícitamente a create_superuser si no existe.

            else:  # El usuario ya existía
                self.stdout.write(self.style.SUCCESS(
                    f"Superusuario con email='{email}' ya existe. Actualizando..."
                ))

            # Actualizar/Asegurar campos para el usuario existente o recién creado (si get_or_create no lo hizo completamente)
            user.set_password(password)
            user.primer_nombre = primer_nombre
            user.primer_apellido = primer_apellido

            # Asegurar flags de superusuario y campos relacionados
            # Estos son usualmente manejados por create_superuser, pero es bueno asegurarlos
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True  # Asumiendo que tu modelo tiene is_active, Django lo usa

            if hasattr(user, 'activo'):  # Si tienes tu propio campo 'activo'
                user.activo = True

            if hasattr(user, 'nivel_acceso'):
                user.nivel_acceso = 5  # Asumiendo que 5 es el nivel de superadmin

            if hasattr(user, 'tipo_usuario'):
                # Asume que 'ADMIN' es el valor correcto para un superusuario
                user.tipo_usuario = "ADMIN"
                # Si usas CommonChoices:
                # from myapp.commons import CommonChoices
                # user.tipo_usuario = next((c[0] for c in CommonChoices.TIPO_USUARIO if c[0] == 'ADMIN'), None)

            # Si tienes un campo 'username' separado del email y quieres sincronizarlo o establecerlo
            # if username_explicit:
            #     user.username = username_explicit
            # elif not user.username: # Si no hay username explícito y el campo username está vacío
            #     user.username = User.objects.normalize_email(email).split('@')[0] # Generar uno básico

            user.save(using=db)

            if created:  # Si fue creado, el mensaje ya se dio.
                pass
            else:  # Si se actualizó
                self.stdout.write(self.style.SUCCESS(
                    f"Detalles y contraseña del superusuario '{email}' actualizados correctamente."
                ))

        except CommandError:  # Re-lanzar CommandError para que el script de despliegue falle
            raise
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Ocurrió un error inesperado al asegurar el superusuario: {e}"))
            import traceback
            traceback.print_exc()
            raise CommandError(f"Error inesperado: {e}")
