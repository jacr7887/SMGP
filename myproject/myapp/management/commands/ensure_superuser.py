# MPC/myproject/myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
import os
import sys

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists or is updated with credentials from env. V5'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V5: Comando INICIADO ---"))

        email_env = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password_env = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        # Para REQUIRED_FIELDS, es crucial que tengan un valor.
        # Si no están en el .env, el comando fallará si el manager los exige.
        first_name_env = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE')
        last_name_env = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO')

        if not email_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V5: ERROR: DJANGO_SUPERUSER_EMAIL no definido. ---'))
            sys.exit(1)
        if not password_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V5: ERROR: DJANGO_SUPERUSER_PASSWORD no definido. ---'))
            sys.exit(1)
        if not first_name_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V5: ERROR: DJANGO_SUPERUSER_PRIMER_NOMBRE no definido (requerido). ---'))
            sys.exit(1)
        if not last_name_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V5: ERROR: DJANGO_SUPERUSER_PRIMER_APELLIDO no definido (requerido). ---'))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser V5: Asegurando superusuario con email: '{email_env}' ---"))

        try:
            with transaction.atomic():
                user = None
                created = False
                try:
                    user = User.objects.get(email=email_env)
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser V5: Usuario '{email_env}' ENCONTRADO (PK: {user.pk}). Actualizando... ---"))
                except User.DoesNotExist:
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser V5: Usuario '{email_env}' NO encontrado. CREANDO... ---"))
                    # Llamamos a create_superuser del manager, que ya maneja is_staff, is_superuser, nivel_acceso, etc.
                    user = User.objects.create_superuser(
                        email=email_env,
                        password=password_env,  # create_superuser se encarga del hashing
                        primer_nombre=first_name_env,
                        primer_apellido=last_name_env
                        # Añade aquí otros campos que tu create_superuser específico podría necesitar
                        # o que quieras pasar explícitamente, aunque tu manager ya pone defaults.
                    )
                    created = True
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser V5: Superusuario '{email_env}' CREADO (PK: {user.pk}). ---"))

                # Si el usuario fue encontrado (no recién creado), o para asegurar los campos
                # incluso si fue creado (aunque create_superuser debería manejarlos).
                if not created:  # Solo si fue encontrado, porque create_superuser ya establece estos.
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser V5: Re-asegurando contraseña y campos para usuario existente '{email_env}' (PK: {user.pk}). ---"))

                # Asegurar que la contraseña sea la del .env
                user.set_password(password_env)
                user.primer_nombre = first_name_env  # Actualizar por si cambia en .env
                user.primer_apellido = last_name_env  # Actualizar por si cambia en .env
                user.is_staff = True       # Asegurar flags
                user.is_superuser = True
                user.is_active = True      # Asegurar que esté activo
                user.nivel_acceso = 5      # Asegurar nivel de superusuario
                user.tipo_usuario = 'ADMIN'  # O el valor correcto de CommonChoices

                user.save()  # Guardar todos los cambios (contraseña, flags, nombres)

                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser V5: Contraseña y flags establecidos para nuevo superusuario '{email_env}'. ---"))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser V5: Superusuario '{email_env}' (PK: {user.pk}) actualizado. ---"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser V5: !!! ERROR procesando superusuario '{email_env}': {type(e).__name__} - {e} !!! ---"))
            self.stderr.write(
                "--- Traceback del error en ensure_superuser V5: ---")
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V5: Comando FINALIZADO ---"))
