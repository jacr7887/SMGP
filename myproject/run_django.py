# run_django.py
from django.core.management import execute_from_command_line
import os
import sys
import django

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

# Ejecutar la aplicación Django

if __name__ == '__main__':
    execute_from_command_line(sys.argv)
