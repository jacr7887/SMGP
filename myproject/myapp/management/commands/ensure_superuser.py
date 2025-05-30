# En MPC/myproject/myapp/management/commands/ensure_superuser.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import os
import sys

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures a superuser exists or is updated with credentials from env.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V3: Comando INICIADO ---"))

        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')

        if not email:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V3: ERROR CRÍTICO: DJANGO_SUPERUSER_EMAIL no definido. ---'))
            sys.exit(1)
        if not password:
            self.stderr.write(self.style.ERROR(
                '--- ensure_superuser V3: ERROR CRÍTICO: DJANGO_SUPERUSER_PASSWORD no definido. ---'))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            f"--- ensure_superuser V3: Asegurando superusuario con email: '{email}' ---"))

        # Campos que deben estar presentes en el usuario
        defaults = {
            'primer_nombre': first_name,
            'primer_apellido': last_name,
            'is_staff': True,
            'is_superuser': True,
            'is_active': True
        }
        # Si tu USERNAME_FIELD es 'username' y quieres que sea igual al email, añádelo a defaults:
        # if User.USERNAME_FIELD == 'username':
        #     defaults[User.USERNAME_FIELD] = email

        try:
            user, created = User.objects.update_or_create(
                email=email,  # Campo para buscar el usuario
                # Campos a establecer si se crea o se actualiza (excepto la contraseña)
                defaults=defaults
            )

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser V3: Superusuario '{email}' CREADO (PK: {user.pk}). Estableciendo contraseña... ---"))
            else:
                self.stdout.write(self.style.NOTICE(
                    f"--- ensure_superuser V3: Usuario '{email}' ENCONTRADO (PK: {user.pk}). Actualizando contraseña y re-asegurando flags... ---"))

            # Siempre establecer/actualizar la contraseña
            user.set_password(password)
            user.save()  # Guardar la contraseña y cualquier cambio de 'defaults' si era una actualización

            self.stdout.write(self.style.SUCCESS(
                f"--- ensure_superuser V3: Contraseña para '{email}' (PK: {user.pk}) establecida/actualizada. Flags asegurados. ---"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"--- ensure_superuser V3: !!! ERROR procesando superusuario '{email}': {type(e).__name__} - {e} !!! ---"))
            import traceback
            self.stderr.write(
                "--- Traceback del error en ensure_superuser V3: ---")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

        self.stdout.write(self.style.NOTICE(
            "--- ensure_superuser V3: Comando FINALIZADO ---"))
