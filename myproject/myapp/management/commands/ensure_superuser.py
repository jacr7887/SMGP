# myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction  # Para asegurar atomicidad
import os
import sys  # Para escribir en stderr

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists with credentials from env, creating or updating as necessary.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- CMD ensure_superuser: Comando INICIADO ---"))

        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_NOMBRE', '')  # Default a vacío
        last_name = os.environ.get(
            'DJANGO_SUPERUSER_PRIMER_APELLIDO', '')  # Default a vacío

        # Determinar el valor para el USERNAME_FIELD
        # Si USERNAME_FIELD es 'email', username_val será el email.
        # Si USERNAME_FIELD es 'username', y DJANGO_SUPERUSER_USERNAME está definido, se usa ese.
        # Si no, se usa el email como fallback para 'username'.
        username_val = email
        if User.USERNAME_FIELD == 'username':  # Si el campo de usuario es 'username'
            env_username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
            if env_username:
                username_val = env_username
            self.stdout.write(self.style.NOTICE(
                f"--- CMD ensure_superuser: USERNAME_FIELD es 'username'. Usando '{username_val}' como username. ---"))

        if not email:
            self.stderr.write(self.style.ERROR(
                '--- CMD ensure_superuser: ERROR CRÍTICO: DJANGO_SUPERUSER_EMAIL no está definido. ---'))
            sys.exit(1)  # Salir con error
        if not password:
            self.stderr.write(self.style.ERROR(
                '--- CMD ensure_superuser: ERROR CRÍTICO: DJANGO_SUPERUSER_PASSWORD no está definido. ---'))
            sys.exit(1)  # Salir con error

        self.stdout.write(self.style.NOTICE(
            f"--- CMD ensure_superuser: Asegurando superusuario con email: '{email}' (username a usar: '{username_val}') ---"))

        try:
            with transaction.atomic():
                # Intentar obtener por email primero, ya que es único
                user = None
                try:
                    user = User.objects.get(email=email)
                    self.stdout.write(self.style.NOTICE(
                        f"--- CMD ensure_superuser: Usuario con email '{email}' encontrado (PK: {user.pk}). Forzando actualización de contraseña y flags... ---"))
                    created = False
                except User.DoesNotExist:
                    self.stdout.write(self.style.NOTICE(
                        f"--- CMD ensure_superuser: Usuario con email='{email}' NO encontrado. Intentando crear... ---"))

                    # Preparar los campos para la creación
                    create_kwargs = {
                        User.USERNAME_FIELD: username_val,  # Usar el USERNAME_FIELD
                        'email': email,  # Asegurar que el email también se pase
                        'primer_nombre': first_name,
                        'primer_apellido': last_name,
                        # Agrega aquí otros campos obligatorios de tu modelo Usuario si los tienes
                    }
                    user = User.objects.create_superuser(**create_kwargs)
                    # create_superuser ya debería manejar set_password y los flags is_staff, is_superuser, is_active
                    self.stdout.write(self.style.SUCCESS(
                        f"--- CMD ensure_superuser: Superusuario '{email}' CREADO (PK: {user.pk}). Estableciendo contraseña explícitamente... ---"))
                    created = True

                # Siempre establecer/restablecer la contraseña y asegurar flags
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True  # Muy importante para el login

                # Actualizar otros campos si no fue una creación reciente y se proveyeron
                if not created:
                    if first_name:
                        user.primer_nombre = first_name
                    if last_name:
                        user.primer_apellido = last_name

                user.save()
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- CMD ensure_superuser: Contraseña y flags establecidos para nuevo superusuario '{email}' (PK: {user.pk}). ---"))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- CMD ensure_superuser: Detalles y contraseña del superusuario '{email}' (PK: {user.pk}) actualizados. ---"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- CMD ensure_superuser: !!! ERROR INESPERADO procesando superusuario '{email}': {type(e).__name__} - {e} !!! ---"))
            import traceback
            self.stderr.write(
                "--- Traceback del error en ensure_superuser: ---")
            traceback.print_exc(file=sys.stderr)  # Imprimir traceback a stderr
            # Salir con error para detener el entrypoint.sh si algo grave pasa aquí
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            "--- CMD ensure_superuser: Comando FINALIZADO ---"))
