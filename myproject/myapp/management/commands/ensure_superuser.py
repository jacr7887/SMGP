# MPC/myproject/myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
import os
import sys
import traceback

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists or is updated. V6 - Detailed Debugging'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V6: Comando INICIADO ---"))

        email_env = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password_env = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name_env = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        last_name_env = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')

        username_to_use = email_env  # Asumimos USERNAME_FIELD = 'email'

        if not email_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V6: ERROR: DJANGO_SUPERUSER_EMAIL no definido. Saliendo. ---'))
            sys.exit(1)
        if not password_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V6: ERROR: DJANGO_SUPERUSER_PASSWORD no definido. Saliendo. ---'))
            sys.exit(1)
        if not first_name_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V6: ERROR: DJANGO_SUPERUSER_PRIMER_NOMBRE no definido. Saliendo. ---'))
            sys.exit(1)
        if not last_name_env:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V6: ERROR: DJANGO_SUPERUSER_PRIMER_APELLIDO no definido. Saliendo. ---'))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser V6: Intentando asegurar superusuario: email='{email_env}', primer_nombre='{first_name_env}', primer_apellido='{last_name_env}' ---"))

        try:
            with transaction.atomic():
                user = None
                try:
                    # Intenta obtener el usuario por el campo que es único y usado para login (email)
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser V6: Buscando usuario por email exacto: '{email_env}' ---"))
                    # Búsqueda insensible a mayúsculas para email
                    user = User.objects.get(email__iexact=email_env)
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser V6: Usuario ENCONTRADO (PK: {user.pk}, Email en BD: '{user.email}'). Actualizando... ---"))

                    # Forzar actualización de campos
                    user.set_password(password_env)
                    user.primer_nombre = first_name_env
                    user.primer_apellido = last_name_env
                    user.is_staff = True
                    user.is_superuser = True
                    user.is_active = True
                    user.nivel_acceso = 5  # Asegurar nivel superusuario
                    user.tipo_usuario = 'ADMIN'  # O el valor correcto de tus CommonChoices

                    # Si tu USERNAME_FIELD es 'username' y quieres que sea diferente o asegurar que sea el email
                    if User.USERNAME_FIELD == 'username' and hasattr(user, 'username'):
                        user.username = email_env  # O una lógica para generar el username
                        self.stdout.write(self.style.NOTICE(
                            f"--- ensure_superuser V6: Estableciendo username a '{user.username}' ---"))

                    user.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser V6: Usuario '{email_env}' (PK: {user.pk}) ACTUALIZADO y contraseña establecida. ---"))

                except User.DoesNotExist:
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser V6: Usuario con email '{email_env}' NO encontrado. CREANDO... ---"))

                    create_kwargs = {
                        'email': email_env,  # Email es el USERNAME_FIELD
                        'primer_nombre': first_name_env,
                        'primer_apellido': last_name_env,
                        # Añade aquí otros campos que TU manager create_superuser espera OBLIGATORIAMENTE
                        # y que no toma de los **extra_fields pasados a create_superuser en el manager
                        # (por ejemplo, si tu manager no usa los defaults que pusiste)
                        # 'tipo_usuario': 'ADMIN', # Si create_superuser no lo pone por defecto
                        # 'nivel_acceso': 5,     # Si create_superuser no lo pone por defecto
                    }
                    # Si tu USERNAME_FIELD es 'username', asegúrate de que create_superuser lo maneje
                    # o pásalo explícitamente si es diferente al email.
                    if User.USERNAME_FIELD == 'username':
                        # O la lógica para username
                        create_kwargs[User.USERNAME_FIELD] = email_env

                    user = User.objects.create_superuser(
                        password=password_env, **create_kwargs)
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser V6: Superusuario '{email_env}' CREADO (PK: {user.pk}). ---"))
                    # create_superuser ya debería haber establecido la contraseña y los flags is_active, is_staff, is_superuser

        except IntegrityError as ie:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser V6: !!! IntegrityError al procesar '{email_env}': {ie} !!! ---"))
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser V6: Esto puede pasar si el email o username ya existen pero con diferentes mayúsculas/minúsculas y la BD es sensible. ---"))
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser V6: !!! ERROR INESPERADO procesando '{email_env}': {type(e).__name__} - {e} !!! ---"))
            self.stderr.write(
                "--- Traceback del error en ensure_superuser V6: ---")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V6: Comando FINALIZADO ---"))
