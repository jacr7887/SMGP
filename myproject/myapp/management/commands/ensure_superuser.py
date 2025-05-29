# En myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction  # Para asegurar atomicidad
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists with credentials from env, creating or updating.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando INICIADO ---"))
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')  # Default si no está
        last_name = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')   # Default si no está

        # Asume que USERNAME_FIELD es 'email' o que quieres que username sea el email.
        # Si USERNAME_FIELD es 'username' y es diferente al email, debes manejarlo.
        username_val = email

        if not email:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: ERROR CRÍTICO: DJANGO_SUPERUSER_EMAIL no está definido. ---'))
            return
        if not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser.py: ERROR CRÍTICO: DJANGO_SUPERUSER_PASSWORD no está definido. ---'))
            return

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser.py: Buscando usuario con email: '{email}' ---"))

        try:
            with transaction.atomic():  # Asegura que todas las operaciones de BD sean atómicas
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        # Campos para pasar a create_user/create_superuser si no existe
                        # Asegúrate que estos campos sean aceptados por tu manager
                        User.USERNAME_FIELD: username_val,  # Si USERNAME_FIELD es 'username'
                        'primer_nombre': first_name,
                        'primer_apellido': last_name,
                        # Añade aquí cualquier otro campo que tu modelo necesite al crear
                        # y que no tenga un valor por defecto o sea nullable=False
                        'is_staff': True,     # create_superuser los pone, pero por si acaso
                        'is_superuser': True,
                        'is_active': True,    # Importante para poder iniciar sesión
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Superusuario '{email}' CREADO. Estableciendo contraseña... ---"))
                    user.set_password(password)
                    # Si create_superuser no estableció estos, asegúralo:
                    user.is_staff = True
                    user.is_superuser = True
                    user.is_active = True
                    user.save()  # Guardar después de set_password y flags
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Contraseña y flags establecidos para el nuevo superusuario '{email}'. ---"))
                else:
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser.py: Usuario '{email}' encontrado. Forzando actualización de contraseña y flags... ---"))
                    user.set_password(password)
                    user.is_staff = True
                    user.is_superuser = True
                    user.is_active = True
                    # Actualiza otros campos si quieres que se sobrescriban siempre
                    if first_name:
                        user.primer_nombre = first_name
                    if last_name:
                        user.primer_apellido = last_name
                    user.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Detalles y contraseña del superusuario '{email}' actualizados. ---"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: !!! ERROR INESPERADO procesando superusuario '{email}': {e} !!! ---"))
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: Traceback del error: ---"))
            import traceback
            traceback.print_exc()  # Imprime el traceback completo del error

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando FINALIZADO ---"))
