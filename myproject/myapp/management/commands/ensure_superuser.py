# En MPC/myproject/myapp/management/commands/ensure_superuser.py

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.exceptions import ImproperlyConfigured
import os

User = get_user_model()


class Command(BaseCommand):
    help = ('Ensures a superuser exists with credentials from environment variables, '
            'creating or updating as necessary.')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando iniciado ---"))

        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', '')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', '')

        # Determinar el valor para el USERNAME_FIELD.
        # Si USERNAME_FIELD es 'email', no necesitamos un 'username' separado.
        # Si es 'username', podemos usar el email como username o generar uno.
        username_val = email
        if User.USERNAME_FIELD != 'email':
            # Aquí podrías tener una lógica más compleja si quieres un username diferente al email
            # Por ahora, usaremos el email como username si USERNAME_FIELD no es 'email'.
            pass

        if not email:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: DJANGO_SUPERUSER_EMAIL debe estar definido en el entorno. ---'))
            raise ImproperlyConfigured(
                "DJANGO_SUPERUSER_EMAIL no está configurado.")

        if not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: DJANGO_SUPERUSER_PASSWORD debe estar definido en el entorno. ---'))
            raise ImproperlyConfigured(
                "DJANGO_SUPERUSER_PASSWORD no está configurado.")

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser.py: Asegurando superusuario con email: '{email}' ---"))

        user_data = {
            'primer_nombre': first_name,
            'primer_apellido': last_name,
            # Añade aquí otros campos que tu modelo Usuario tenga y quieras establecer/actualizar
            # Por ejemplo, si tu modelo tiene 'tipo_usuario' y 'nivel_acceso' y quieres
            # que el superuser siempre los tenga de una forma específica:
            # 'tipo_usuario': 'ADMIN', # O el valor que uses para admin
            # 'nivel_acceso': 5,       # O el valor máximo
        }
        if User.USERNAME_FIELD != 'email':
            user_data[User.USERNAME_FIELD] = username_val

        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: Usuario '{email}' encontrado. Actualizando... ---"))

            # Actualizar campos y contraseña
            changed = False
            for field, value in user_data.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True

            # Siempre actualiza la contraseña y los flags de superuser/staff/active
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True  # Muy importante

            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"--- ensure_superuser.py: Superusuario '{email}' actualizado correctamente. ---"))

        except User.DoesNotExist:
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: Superusuario con email='{email}' NO existe. Creando... ---"))
            try:
                # Asegúrate de que tu CustomUserManager.create_superuser (si tienes uno)
                # o el User.objects.create_superuser por defecto, maneje estos campos.
                # Si USERNAME_FIELD es 'email', no necesitas pasar 'username' a create_superuser
                # a menos que tu manager lo requiera explícitamente.

                create_kwargs = {
                    User.USERNAME_FIELD: email if User.USERNAME_FIELD == 'email' else username_val,
                    'password': password,
                    'primer_nombre': first_name,
                    'primer_apellido': last_name,
                    # Añade aquí otros campos obligatorios para tu modelo Usuario
                    # Por ejemplo:
                    # 'tipo_usuario': 'ADMIN',
                    # 'nivel_acceso': 5,
                }
                # Si USERNAME_FIELD es 'email', el create_superuser de Django espera 'email'
                if User.USERNAME_FIELD == 'email' and 'username' in create_kwargs:
                    # Evitar pasar username si el campo es email
                    del create_kwargs['username']
                if User.USERNAME_FIELD != 'email' and 'email' not in create_kwargs:
                    # Asegurar que el email se pase si USERNAME_FIELD no es email
                    create_kwargs['email'] = email

                User.objects.create_superuser(**create_kwargs)
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser.py: Superusuario '{email}' CREADO exitosamente. ---"))
            except Exception as e_create:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser.py: ERROR al CREAR superusuario '{email}': {e_create} ---"))
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser.py: Datos con los que se intentó crear: {create_kwargs} ---"))

        except Exception as e_general:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: Error inesperado procesando '{email}': {e_general} ---"))

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando finalizado ---"))
