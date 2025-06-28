# myapp/management/commands/check_user.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Verifica si un usuario y contraseña son válidos.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str,
                            help='El email del usuario a verificar')
        parser.add_argument('password', type=str,
                            help='La contraseña a verificar')

    def handle(self, *args, **options):
        User = get_user_model()
        email = options['email']
        password = options['password']

        self.stdout.write(f"--- Verificando al usuario con email: {email} ---")

        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.SUCCESS(
                f"Usuario '{email}' encontrado en la base de datos."))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"ERROR: No se encontró ningún usuario con el email '{email}'."))
            return

        self.stdout.write(f"Verificando contraseña: '{password}'...")

        if user.check_password(password):
            self.stdout.write(self.style.SUCCESS(
                "¡ÉXITO! La contraseña es correcta."))
        else:
            self.stdout.write(self.style.ERROR(
                "FALLO: La contraseña es incorrecta."))
