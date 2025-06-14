# start.py (Versión Final y a Prueba de Balas)

import os
import sys
from pathlib import Path
import logging

# --- PASO 1: Configurar el entorno ANTES DE CUALQUIER IMPORT DE DJANGO ---
# Añadir la ruta del proyecto al path de Python.
# Esto es crucial para que el .exe encuentre 'myproject.settings'.
# sys._MEIPASS es una variable especial que PyInstaller crea en el .exe
# y que apunta a la carpeta temporal donde se extraen los archivos.
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    project_path = sys._MEIPASS
    # Si tus apps están en un subdirectorio, ajústalo aquí.
    # Por ejemplo, si la estructura es src/myproject, src/myapp:
    # sys.path.insert(0, os.path.join(project_path, 'src'))
else:
    project_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, project_path)

# Establecer la variable de entorno que Django necesita.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# --- PASO 2: Crear el archivo .env si no existe ---
# (Tu lógica original, sin cambios)
DEFAULT_ENV_CONTENT = """# .env - Creado automáticamente.
SECRET_KEY='django-insecure-DEFAULT-KEY-CHANGE-ME-12345!@#$%'
DEBUG=False
ALLOWED_HOSTS=*
DATABASE_URL=sqlite:///db.sqlite3
SMGP_LICENSE_VERIFY_KEY_B64='48FUC+B/1sYVGhvmnRQuXKWwKqcIsg1cE49xF5VRxIY='
DJANGO_SUPERUSER_USERNAME='admin'
DJANGO_SUPERUSER_EMAIL='admin@example.com'
DJANGO_SUPERUSER_PASSWORD='password'
DJANGO_SUPERUSER_PRIMER_NOMBRE='Admin'
DJANGO_SUPERUSER_PRIMER_APELLIDO='User'
"""
try:
    # Usamos la misma lógica para la ruta base
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent
    env_path = base_path / '.env'
    if not env_path.exists():
        print(f"Archivo .env no encontrado. Creando uno nuevo en: {env_path}")
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_ENV_CONTENT)
except Exception as e:
    print(f"ERROR: No se pudo crear el archivo .env: {e}")
    input("Presiona Enter para salir.")
    sys.exit(1)


# --- PASO 3: Función de Inicialización (con imports locales) ---
def initialize_database():
    """
    Verifica si la base de datos necesita ser creada/poblada.
    IMPORTANTE: Todas las importaciones de Django se hacen DENTRO de la función.
    """
    # Importar Django y configurarlo aquí dentro
    import django
    from django.conf import settings
    from django.core.management import call_command

    print("Llamando a django.setup() desde initialize_database...")
    django.setup()
    print("Configuración de Django completada.")

    # Ahora importar modelos
    from myapp.models import Usuario, Tarifa

    try:
        db_path = settings.DATABASES['default']['NAME']
        db_needs_init = not os.path.exists(db_path)
        if not db_needs_init:
            if not Usuario.objects.filter(is_superuser=True).exists() or not Tarifa.objects.exists():
                print("Base de datos encontrada, pero vacía. Se procederá a poblarla.")
                db_needs_init = True

        if db_needs_init:
            print("\n[INICIALIZACIÓN DE BD REQUERIDA]")
            print("Aplicando migraciones...")
            call_command('migrate', interactive=False)
            print("Poblando base de datos...")
            call_command('seed_db', '--clean')
            print("¡Inicialización completada!")
        else:
            print("La base de datos ya existe y está poblada.")
    except Exception as e:
        logging.exception(
            f"ERROR CRÍTICO durante la inicialización de la BD: {e}")
        input("La aplicación no pudo iniciarse correctamente. Presiona Enter para salir.")
        sys.exit(1)

# --- PASO 4: Función Principal (con imports locales) ---


def main():
    """
    Función principal que verifica la BD y luego inicia el servidor.
    """
    print("\n--- SMGP App ---", flush=True)

    # Primero, inicializamos la base de datos
    initialize_database()

    # Importar waitress y la aplicación WSGI justo antes de usarlos
    from waitress import serve
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
    host = '127.0.0.1'
    port = 8000

    print(f"\nIniciando servidor Waitress en http://{host}:{port}", flush=True)
    print("Presiona Ctrl+C para detener el servidor.", flush=True)

    serve(application, host=host, port=port, threads=8)


# --- Punto de Entrada ---
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("\n" + "="*70)
        print("!!! LA APLICACIÓN HA FALLADO DURANTE EL ARRANQUE !!!")
        logging.exception(f"ERROR: {e}")
        print("="*70)
        input("La aplicación ha fallado. Presiona Enter para cerrar esta ventana.")
