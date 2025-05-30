# En myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'FOR DEBUGGING: Tries to create or forcefully update superuser.'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL',
                               '').strip()  # Añade .strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')
        username_val = email  # Asumimos esto

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser (DEBUG): INICIO. Email: '{email}', Pass: '{password is not None}' ---"))

        if not email or not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser (DEBUG): FALTAN EMAIL O PASSWORD ENV VARS ---'))
            return

        user = None
        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser (DEBUG): Usuario '{email}' ENCONTRADO (PK: {user.pk}). Forzando actualización. ---"))
        except User.DoesNotExist:
            self.stdout.write(self.style.NOTICE(
                f"--- ensure_superuser (DEBUG): Usuario '{email}' NO encontrado. Intentando crear... ---"))
            try:
                # Asegúrate que tu create_superuser maneja estos campos, o usa create_user y luego actualiza
                user = User.objects.create_superuser(
                    email=email,
                    password=password,
                    primer_nombre=first_name,
                    primer_apellido=last_name
                    # username=username_val, # Si es necesario
                    # Agrega cualquier otro campo obligatorio de tu modelo Usuario
                )
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser (DEBUG): Superusuario '{email}' CREADO (PK: {user.pk}). ---"))
            except Exception as e_create:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser (DEBUG): !!! ERROR AL CREAR superusuario '{email}': {e_create} !!! ---"))
                import traceback
                traceback.print_exc()
                return  # Salir si la creación falla

        except Exception as e_get:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser (DEBUG): !!! ERROR AL BUSCAR usuario '{email}': {e_get} !!! ---"))
            import traceback
            traceback.print_exc()
            return  # Salir si la búsqueda falla catastróficamente

        # Si llegamos aquí, 'user' debería ser un objeto (ya sea encontrado o recién creado)
        if user:
            try:
                self.stdout.write(self.style.NOTICE(
                    f"--- ensure_superuser (DEBUG): Estableciendo contraseña y flags para '{email}' (PK: {user.pk}) ---"))
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                # Puedes añadir otros campos a actualizar si es necesario
                user.primer_nombre = first_name
                user.primer_apellido = last_name
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser (DEBUG): Usuario '{email}' (PK: {user.pk}) guardado/actualizado. ---"))
            except Exception as e_save:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser (DEBUG): !!! ERROR AL GUARDAR/ACTUALIZAR usuario '{email}' (PK: {user.pk}): {e_save} !!! ---"))
                import traceback
                traceback.print_exc()
        else:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser (DEBUG): CRÍTICO - El objeto 'user' es None después de intentar get/create para '{email}'. Algo falló antes. ---"))

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser (DEBUG): Comando FINALIZADO ---"))
