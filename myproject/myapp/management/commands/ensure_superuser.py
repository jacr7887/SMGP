# MPC/myproject/myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
import os
import sys
import traceback

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists or is updated. V6.1 - Focused Update'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V6.1: Comando INICIADO ---"))

        email_env = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password_env = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name_env = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        last_name_env = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')
        username_val = email_env

        if not all([email_env, password_env, first_name_env, last_name_env]):
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V6.1: Faltan variables de entorno requeridas. Saliendo. ---'))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser V6.1: Asegurando superusuario con email: '{email_env}' ---"))

        user = None
        try:
            with transaction.atomic():
                try:
                    # Búsqueda insensible
                    user = User.objects.get(email__iexact=email_env)
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser V6.1: Usuario '{email_env}' ENCONTRADO (PK: {user.pk}). Procediendo a actualizar. ---"))
                except User.DoesNotExist:
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser V6.1: Usuario '{email_env}' NO encontrado. Procediendo a CREAR... ---"))
                    create_kwargs = {
                        'email': email_env, 'primer_nombre': first_name_env, 'primer_apellido': last_name_env}
                    if User.USERNAME_FIELD == 'username':
                        create_kwargs[User.USERNAME_FIELD] = username_val
                    user = User.objects.create_superuser(
                        password=password_env, **create_kwargs)
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser V6.1: Superusuario '{email_env}' CREADO (PK: {user.pk}). ---"))

                # En este punto, 'user' debe ser un objeto válido (encontrado o creado)
                self.stdout.write(self.style.NOTICE(
                    f"--- ensure_superuser V6.1: Estableciendo/Actualizando contraseña y flags para '{email_env}' (PK: {user.pk}). ---"))
                user.set_password(password_env)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                user.primer_nombre = first_name_env  # Asegurar que estos también se actualicen
                user.primer_apellido = last_name_env
                # Actualizar username si es diferente a email
                if User.USERNAME_FIELD == 'username' and hasattr(user, 'username'):
                    user.username = username_val
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser V6.1: Usuario '{email_env}' (PK: {user.pk}) guardado/actualizado. ---"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser V6.1: !!! ERROR INESPERADO procesando '{email_env}': {type(e).__name__} - {e} !!! ---"))
            self.stderr.write(
                "--- Traceback del error en ensure_superuser V6.1: ---")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V6.1: Comando FINALIZADO ---"))
