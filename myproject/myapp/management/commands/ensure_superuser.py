# myapp/management/commands/ensure_superuser.py
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists with credentials from environment variables, creating or updating as needed.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando iniciado ---"))

        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        # Default si no se provee
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        # Default si no se provee
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')

        if not email:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: ERROR: DJANGO_SUPERUSER_EMAIL no está definida en el entorno.'))
            raise ImproperlyConfigured(
                "DJANGO_SUPERUSER_EMAIL no está definida.")

        if not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: ERROR: DJANGO_SUPERUSER_PASSWORD no está definida en el entorno.'))
            raise ImproperlyConfigured(
                "DJANGO_SUPERUSER_PASSWORD no está definida.")

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser.py: Intentando encontrar/crear superusuario con email: {email} ---"))

        try:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'primer_nombre': first_name,
                    'primer_apellido': last_name,
                    # Añade aquí otros campos que tu modelo Usuario requiera al crear con valores por defecto
                    # Por ejemplo, si tienes 'tipo_usuario' como campo obligatorio:
                    # 'tipo_usuario': 'ADMIN', # O el valor que corresponda
                    # 'nivel_acceso': 5, # Si es aplicable
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser.py: Superusuario '{email}' CREADO NUEVO. Estableciendo contraseña y flags... ---"))
                user.set_password(password)
                # Asegurar que sea superusuario y activo
                user.is_superuser = True
                user.is_staff = True  # Superusuarios deben ser staff
                user.is_active = True
                # Si create_superuser de tu manager no asigna estos, o si get_or_create los omite:
                if not user.primer_nombre and first_name:
                    user.primer_nombre = first_name
                if not user.primer_apellido and last_name:
                    user.primer_apellido = last_name
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser.py: Superusuario '{email}' creado y configurado exitosamente. ---"))
            else:
                self.stdout.write(self.style.NOTICE(
                    f"--- ensure_superuser.py: Superusuario '{email}' ya existe. Actualizando detalles y contraseña... ---"))
                # Actualizar campos si es necesario y la contraseña
                changed = False
                if user.primer_nombre != first_name and first_name:
                    user.primer_nombre = first_name
                    changed = True
                if user.primer_apellido != last_name and last_name:
                    user.primer_apellido = last_name
                    changed = True

                user.set_password(password)  # Siempre actualiza la contraseña
                user.is_superuser = True    # Asegurar flags
                user.is_staff = True
                user.is_active = True
                user.save()  # Guarda la nueva contraseña y cualquier cambio en los campos
                if changed:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Detalles y contraseña del superusuario '{email}' actualizados correctamente. ---"))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Contraseña del superusuario '{email}' actualizada correctamente (otros detalles sin cambios). ---"))

        except ImproperlyConfigured as e:
            # Re-lanzar para que falle el script si las variables de entorno no están
            raise e
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: Error inesperado: {type(e).__name__} - {e} ---"))
            # Considera lanzar la excepción para detener el entrypoint si esto es crítico
            # raise e

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando finalizado ---"))
