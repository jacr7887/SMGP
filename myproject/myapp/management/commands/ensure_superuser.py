# En myapp/management/commands/ensure_superuser.py

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import os  # Asegúrate de importar os

User = get_user_model()


class Command(BaseCommand):
    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        first_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_NOMBRE', 'Admin')
        last_name = os.environ.get('DJANGO_SUPERUSER_PRIMER_APELLIDO', 'User')
        self.stdout.write(
            f"--- ensure_superuser: Intentando crear '{email}' con password '{password}' ---")
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(
                f"--- ensure_superuser: Usuario '{email}' YA EXISTE. No se modifica. ---"))
        else:
            try:
                User.objects.create_superuser(
                    email=email, password=password, primer_nombre=first_name, primer_apellido=last_name)
                self.stdout.write(self.style.SUCCESS(
                    f"--- ensure_superuser: Superusuario '{email}' CREADO. ---"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"--- ensure_superuser: ERROR al crear superusuario '{email}': {e} ---"))
