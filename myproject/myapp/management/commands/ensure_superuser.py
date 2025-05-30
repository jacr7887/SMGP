# myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Robustly ensures a superuser exists or is created/updated with credentials from environment variables.'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')

        # Variables de tu modelo Usuario que necesitamos asegurar
        # Asume un valor por defecto o léelo del env
        tipo_usuario_admin = os.environ.get(
            'DJANGO_SUPERUSER_TIPO_USUARIO', 'ADMIN')
        nivel_acceso_admin = int(os.environ.get(
            'DJANGO_SUPERUSER_NIVEL_ACCESO', 5))  # Asume 5 o léelo

        if not email:
            self.stderr.write(self.style.ERROR(
                'CRITICAL: DJANGO_SUPERUSER_EMAIL environment variable not set.'))
            return 1  # Salir con código de error
        if not password:
            self.stderr.write(self.style.ERROR(
                'CRITICAL: DJANGO_SUPERUSER_PASSWORD environment variable not set.'))
            return 1  # Salir con código de error

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser.py: Comando INICIADO para email: '{email}' ---"))

        try:
            with transaction.atomic():
                # Usamos el email como el campo para buscar o crear, ya que es tu USERNAME_FIELD
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        # Estos son los campos que se usarán SOLO SI el usuario es NUEVO
                        # Tu UsuarioManager se encargará de generar el 'username' si no se provee aquí
                        'primer_nombre': first_name,
                        'primer_apellido': last_name,
                        'tipo_usuario': tipo_usuario_admin,  # Asegúrate que tu modelo/manager lo espere
                        'nivel_acceso': nivel_acceso_admin,  # Se establecerá aquí y luego save() lo usa
                        'activo': True,  # Asegurar que esté activo
                        # 'username': email, # Opcional: si quieres que el username inicial sea el email
                        # tu manager lo generará si no lo pasas
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Superusuario '{email}' CREADO (PK: {user.pk}). Estableciendo contraseña y flags finales... ---"))
                    # Para usuarios recién creados, create_superuser (si es llamado por get_or_create debido al manager)
                    # ya debería haber establecido la contraseña y los flags de superuser/staff
                    # Pero para estar seguros y cubrir el caso de create_user + flags:
                    # Establecer/Re-establecer la contraseña
                    user.set_password(password)
                    user.is_staff = True
                    user.is_superuser = True
                    user.activo = True  # Tu campo personalizado
                    user.is_active = True  # El campo de Django
                    user.nivel_acceso = 5  # Forzar nivel de superusuario
                    # Asegurar campos de nombre si create_superuser no los tomó de defaults
                    user.primer_nombre = first_name
                    user.primer_apellido = last_name
                    user.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Contraseña y flags finales establecidos para NUEVO superusuario '{email}'. ---"))
                else:
                    self.stdout.write(self.style.NOTICE(
                        f"--- ensure_superuser.py: Usuario '{email}' ENCONTRADO (PK: {user.pk}). Forzando actualización de contraseña y flags... ---"))
                    # ¡SIEMPRE actualiza la contraseña!
                    user.set_password(password)
                    user.is_staff = True
                    user.is_superuser = True
                    user.activo = True  # Tu campo personalizado
                    user.is_active = True  # El campo de Django
                    user.nivel_acceso = 5  # Forzar nivel de superusuario

                    # Actualiza otros campos si quieres que se sobrescriban siempre
                    user.primer_nombre = first_name
                    user.primer_apellido = last_name
                    user.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"--- ensure_superuser.py: Detalles y contraseña del superusuario '{email}' actualizados. ---"))

        except IntegrityError as ie:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: IntegrityError para '{email}': {ie} ---"))
            self.stderr.write(self.style.ERROR(
                "--- ensure_superuser.py: Podría ser un username duplicado si no es el email, o un email que ya existe pero no es el que se busca. ---"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser.py: ERROR INESPERADO para '{email}': {type(e).__name__} - {e} ---"))
            import traceback
            traceback.print_exc(file=self.stderr)

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser.py: Comando FINALIZADO ---"))
