from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    help = 'Crea un superusuario por defecto si no existe y realiza otras configuraciones iniciales.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin_cmd')
        password = os.environ.get(
            'DJANGO_SUPERUSER_PASSWORD', 'P@$$wOrdCmdS3cur3!')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL',
                               'admin_cmd@example.com')

        if not User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(
                f"Creando superusuario: {username}"))
            User.objects.create_superuser(
                username=username, email=email, password=password)
        else:
            self.stdout.write(self.style.WARNING(
                f"Superusuario {username} ya existe."))

        # Aquí puedes añadir otra lógica de configuración inicial si es necesario
        self.stdout.write(self.style.SUCCESS(
            "Configuración inicial completada."))
