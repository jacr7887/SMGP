# myapp/management/commands/create_initial_admin.py

import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
import logging

# Obtener el modelo de Usuario personalizado
Usuario = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ('Crea un superusuario inicial utilizando variables de entorno. '
            'No hará nada si un usuario con ese email ya existe.')

    def handle(self, *args, **options):
        # 1. Leer las variables de entorno
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO')

        # 2. Validar que todas las variables necesarias estén presentes
        required_vars = {
            'DJANGO_SUPERUSER_EMAIL': email,
            'DJANGO_SUPERUSER_PASSWORD': password,
            'DJANGO_SUPERUSER_PRIMER_NOMBRE': first_name,
            'DJANGO_SUPERUSER_PRIMER_APELLIDO': last_name
        }
        missing_vars = [name for name,
                        value in required_vars.items() if not value]
        if missing_vars:
            raise CommandError(
                f"Faltan las siguientes variables de entorno requeridas: {', '.join(missing_vars)}")

        # 3. Verificar si el usuario ya existe para evitar errores
        if Usuario.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(
                f"El superusuario con email '{email}' ya existe. No se realizaron cambios."))
            logger.warning(f"Intento de crear superusuario duplicado: {email}")
            return

        # 4. Intentar crear el superusuario usando el manager corregido
        try:
            self.stdout.write(f"Intentando crear superusuario: {email}...")

            # --- LÓGICA CORREGIDA ---
            # Llamamos a create_superuser solo con los datos personales.
            # El manager se encargará de establecer tipo_usuario='ADMIN', is_staff=True, etc.
            user = Usuario.objects.create_superuser(
                email=email,
                password=password,
                primer_nombre=first_name,
                primer_apellido=last_name
            )

            self.stdout.write(self.style.SUCCESS(
                f"Superusuario '{user.email}' creado exitosamente con ID: {user.pk} y rol '{user.tipo_usuario}'."))
            logger.info(f"Superusuario '{user.email}' creado exitosamente.")

        except IntegrityError as e:
            logger.error(
                f"Error de integridad al crear superusuario '{email}': {e}", exc_info=True)
            raise CommandError(
                f"Error de integridad al crear superusuario '{email}' (¿colisión de username?): {e}")
        except Exception as e:
            logger.error(
                f"Error inesperado al crear superusuario '{email}': {e}", exc_info=True)
            raise CommandError(
                f"Error inesperado al crear superusuario '{email}': {e}")
