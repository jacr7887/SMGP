# myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError
import os
import sys

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates a superuser if one does not exist with the given email, or updates password if it does.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando INICIADO ---"))

        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')

        # Determinar el username_val
        username_val = email  # Por defecto, o si USERNAME_FIELD es email
        if User.USERNAME_FIELD == 'username':
            env_username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
            if env_username:
                username_val = env_username
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: USERNAME_FIELD es 'username'. Usando '{username_val}' como username_val. ---"))
        else:
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: USERNAME_FIELD es '{User.USERNAME_FIELD}'. Usando email '{email}' como username_val. ---"))

        if not email:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: ERROR: DJANGO_SUPERUSER_EMAIL no definido. ---'))
            sys.exit(1)
        if not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: ERROR: DJANGO_SUPERUSER_PASSWORD no definido. ---'))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser.py: Intentando asegurar superusuario con email: '{email}' y username_val: '{username_val}' ---"))

        try:
            # Intenta crear el superusuario directamente
            # El manager create_superuser debería manejar la unicidad del USERNAME_FIELD
            # y establecer is_staff, is_superuser, is_active a True.
            create_kwargs = {
                User.USERNAME_FIELD: username_val,
                'email': email,  # Asegurar que el email también se pase y sea único
                'password': password,
                'primer_nombre': first_name,
                'primer_apellido': last_name,
                # Añade aquí CUALQUIER OTRO CAMPO OBLIGATORIO de tu modelo Usuario
                # que no tenga un valor por defecto y no sea nullable=True.
            }
            # Eliminar 'username' de kwargs si USERNAME_FIELD es 'email' para evitar pasarlo dos veces si el manager no lo espera
            if User.USERNAME_FIELD == 'email' and 'username' in create_kwargs:
                del create_kwargs['username']

            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser.py: Intentando User.objects.create_superuser(**{create_kwargs}) ---"))
            user = User.objects.create_superuser(**create_kwargs)
            self.stdout.write(self.style.SUCCESS(
                f"--- ensure_superuser.py: Superusuario '{email}' CREADO con PK: {user.pk}. ---"))

        except IntegrityError as e:
            self.stdout.write(self.style.WARNING(
                f"--- ensure_superuser.py: No se pudo crear usuario (Probablemente ya existe basado en email o username '{username_val}'): {e}. Intentando actualizar... ---"))
            try:
                # Intenta obtenerlo por email, ya que debería ser único.
                user = User.objects.get(email=email)
                self.stdout.write(self.style.NOTICE(
                    f"--- ensure_superuser.py: Usuario con email '{email}' encontrado (PK: {user.pk}). Actualizando contraseña y flags. ---"))
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                if first_name:
                    user.primer_nombre = first_name
                if last_name:
                    user.primer_apellido = last_name
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser.py: Contraseña y flags del superusuario '{email}' actualizados. ---"))
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser.py: ERROR CRÍTICO: Usuario con email '{email}' no existe DESPUÉS de un IntegrityError al crear. Esto es inesperado. ---"))
                sys.exit(1)
            except Exception as e_update:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser.py: ERROR al actualizar usuario existente '{email}': {e_update} ---"))
                import traceback
                traceback.print_exc(file=sys.stderr)
                sys.exit(1)
        except Exception as e_general:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: !!! ERROR INESPERADO durante create_superuser para '{email}': {type(e_general).__name__} - {e_general} !!! ---"))
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando FINALIZADO ---"))
