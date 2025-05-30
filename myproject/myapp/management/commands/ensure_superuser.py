# myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError  # Importar IntegrityError
import os
import sys
import traceback

User = get_user_model()


class Command(BaseCommand):
    help = 'DEBUG: Attempts to CREATE superuser. Will fail if already exists. V7'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V7: Comando INICIADO ---"))

        email_env = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password_env = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name_env = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_NOMBRE', 'DefNombre')
        last_name_env = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_APELLIDO', 'DefApellido')

        username_to_use = email_env

        if not email_env or not password_env or not first_name_env or not last_name_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V7: Faltan variables de entorno requeridas (EMAIL, PASSWORD, PRIMER_NOMBRE, PRIMER_APELLIDO). Saliendo. ---'))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser V7: Intentando CREAR superusuario con email: '{email_env}' ---"))

        try:
            # Intentar crear directamente. Si ya existe por email (unique=True), fallará.
            user = User.objects.create_superuser(
                email=email_env,
                password=password_env,
                primer_nombre=first_name_env,
                primer_apellido=last_name_env
                # Añade username=username_to_use si USERNAME_FIELD es 'username' y es diferente al email
            )
            self.stdout.write(self.style.SUCCESS(
                f"--- ensure_superuser V7: Superusuario '{email_env}' CREADO (PK: {user.pk}). ---"))

        except IntegrityError as ie:
            self.stdout.write(self.style.WARNING(
                f"--- ensure_superuser V7: IntegrityError al crear '{email_env}': {ie}. Probablemente YA EXISTE. ---"))
            # NO intentamos actualizar aquí, solo queremos ver si la creación falla como esperamos.
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser V7: !!! ERROR INESPERADO al crear '{email_env}': {type(e).__name__} - {e} !!! ---"))
            self.stderr.write(
                "--- Traceback del error en ensure_superuser V7: ---")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V7: Comando FINALIZADO ---"))
