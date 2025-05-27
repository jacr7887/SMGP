# myapp/management/commands/create_initial_admin.py

import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
import logging

# Obtener el modelo de Usuario personalizado
Usuario = get_user_model()
logger = logging.getLogger(__name__)  # Usar logger para mejor seguimiento


class Command(BaseCommand):
    help = ('Crea un superusuario inicial utilizando variables de entorno '
            '(DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD, '
            'DJANGO_SUPERUSER_PRIMER_NOMBRE, DJANGO_SUPERUSER_PRIMER_APELLIDO). '
            'No hará nada si el usuario ya existe.')

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO')

        # Validar que todas las variables necesarias estén presentes
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

        # Verificar si el usuario ya existe (basado en el email que es unique)
        if Usuario.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(
                f"El superusuario con email '{email}' ya existe. No se realizaron cambios."))
            logger.warning(f"Intento de crear superusuario duplicado: {email}")
            return  # Salir sin hacer nada si ya existe

        # Intentar crear el superusuario
        try:
            self.stdout.write(f"Intentando crear superusuario: {email}...")
            # Usar el manager personalizado y su método create_superuser
            # Asegúrate que tu Usuario.objects.create_superuser acepte estos kwargs
            user = Usuario.objects.create_superuser(
                email=email,
                password=password,
                primer_nombre=first_name,
                primer_apellido=last_name
                # Pasar cualquier otro valor por defecto necesario si create_superuser los espera
                # ej: tipo_usuario='ADMINISTRADOR', nivel_acceso=5 (aunque create_superuser ya lo hace)
            )
            self.stdout.write(self.style.SUCCESS(
                f"Superusuario '{user.email}' creado exitosamente con ID: {user.pk}."))
            logger.info(f"Superusuario '{user.email}' creado exitosamente.")

        except IntegrityError as e:
            # Esto podría pasar si, a pesar del chequeo previo, hay una condición de carrera
            # o si otro campo único (como username generado) colisiona.
            logger.error(
                f"Error de integridad al crear superusuario '{email}': {e}", exc_info=True)
            raise CommandError(
                f"Error de integridad al crear superusuario '{email}' (¿ya existe o hubo colisión?): {e}")
        except Exception as e:
            # Capturar otros errores inesperados
            logger.error(
                f"Error inesperado al crear superusuario '{email}': {e}", exc_info=True)
            raise CommandError(
                f"Error inesperado al crear superusuario '{email}': {e}")
