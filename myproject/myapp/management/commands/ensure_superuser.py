# En myapp/management/commands/ensure_superuser.py

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import os  # Asegúrate de importar os

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists with credentials from environment variables, creating or updating as necessary.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando iniciado ---"))
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        # Default a vacío si no está
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', '')
        # Default a vacío si no está
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', '')
        # Añade aquí cualquier otro campo que tu modelo Usuario requiera y que quieras setear desde el env
        # Por ejemplo, si tu modelo tiene un campo username y quieres que sea igual al email:
        username_val = email  # O como quieras generarlo

        if not email or not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: DJANGO_SUPERUSER_EMAIL y DJANGO_SUPERUSER_PASSWORD deben estar definidos en el entorno. ---'))
            return

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser.py: Buscando/Creando superusuario con email: '{email}' ---"))
        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: Usuario '{email}' encontrado. Actualizando contraseña y detalles... ---"))

            # Actualizar campos
            user.set_password(password)  # Siempre actualiza la contraseña
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            if first_name:  # Solo actualiza si se proveyó
                user.primer_nombre = first_name
            if last_name:  # Solo actualiza si se proveyó
                user.primer_apellido = last_name
            # Si tu USERNAME_FIELD no es email, también actualiza el username si es necesario:
            # if hasattr(user, 'username') and User.USERNAME_FIELD != 'email':
            #     user.username = username_val # O la lógica que tengas para el username

            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"--- ensure_superuser.py: Detalles y contraseña del superusuario '{email}' actualizados correctamente. ---"))

        except User.DoesNotExist:
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: Superusuario con email='{email}' NO existe. Creando... ---"))
            # Asegúrate de que tu CustomUserManager.create_superuser maneje los campos que pasas
            # o usa User.objects.create_user y luego actualiza los flags de superuser.
            # La forma más segura es usar create_superuser si está bien definido:
            try:
                User.objects.create_superuser(
                    email=email,
                    password=password,
                    primer_nombre=first_name,
                    primer_apellido=last_name
                    # username=username_val, # Si tu USERNAME_FIELD es 'username'
                )
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser.py: Superusuario '{email}' creado exitosamente. ---"))
            except Exception as e_create:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser.py: Error al CREAR superusuario '{email}': {e_create} ---"))

        except Exception as e_general:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: Error inesperado procesando superusuario '{email}': {e_general} ---"))

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando finalizado ---"))
