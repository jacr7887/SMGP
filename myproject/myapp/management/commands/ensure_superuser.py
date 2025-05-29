from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists with credentials from environment variables, creating or updating as necessary.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando iniciado ---"))
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', '')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', '')
        username_val = email  # Asumiendo que quieres que el username sea el email

        if not email or not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: DJANGO_SUPERUSER_EMAIL y DJANGO_SUPERUSER_PASSWORD deben estar definidos. ---'))
            return

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser.py: Buscando/Asegurando superusuario con email: '{email}' ---"))
        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: Usuario '{email}' encontrado. Forzando actualización de contraseña y detalles... ---"))

            user.set_password(password)  # ¡SIEMPRE actualiza la contraseña!
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            if first_name:
                user.primer_nombre = first_name
            if last_name:
                user.primer_apellido = last_name
            # Si USERNAME_FIELD es 'username' y quieres que sea igual al email:
            if hasattr(user, 'username') and User.USERNAME_FIELD == 'username':
                user.username = username_val

            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"--- ensure_superuser.py: Detalles y contraseña del superusuario '{email}' actualizados. ---"))

        except User.DoesNotExist:
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: Superusuario '{email}' NO existe. Creando... ---"))
            try:
                User.objects.create_superuser(
                    email=email,
                    password=password,
                    primer_nombre=first_name,
                    primer_apellido=last_name,
                    # Asegúrate de que tu create_superuser acepte 'username' si es necesario
                    username=username_val
                    # o que tu modelo lo maneje si USERNAME_FIELD es email.
                )
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser.py: Superusuario '{email}' CREADO. ---"))
            except Exception as e_create:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser.py: ERROR al CREAR superusuario '{email}': {e_create} ---"))

        except Exception as e_general:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: Error inesperado procesando '{email}': {e_general} ---"))

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando finalizado ---"))
