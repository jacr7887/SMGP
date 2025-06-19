# start.py (Versión Final con Celery y Multiprocesamiento)

import os
import sys
import multiprocessing
import subprocess  # [NUEVO] Necesario para llamar a Celery
from pathlib import Path
import logging

# --- PASO 1: Configurar el entorno ANTES DE CUALQUIER IMPORT DE DJANGO ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    project_path = sys._MEIPASS
else:
    project_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, project_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# --- PASO 2: Crear el archivo .env si no existe ---
DEFAULT_ENV_CONTENT = """# .env - Creado automáticamente.
SECRET_KEY='Xgfei34531#$&/$234fGHYtfhuY&6%$33rf#FfHUu7854fd"S3F%6HrR2dfdgG%6(5##3rfDfv-t4342345F$26fd6/%$#)'
DEBUG=False
ALLOWED_HOSTS=*
DATABASE_URL=postgres://postgres:7319@localhost:5432/smgp
SMGP_LICENSE_VERIFY_KEY_B64='48FUC+B/1sYVGhvmnRQuXKWwKqcIsg1cE49xF5VRxIY='
DJANGO_SUPERUSER_USERNAME='jacr7887@gmail.com'
DJANGO_SUPERUSER_EMAIL='jacr7887@gmail.com'
DJANGO_SUPERUSER_PASSWORD='123456789/*-+'
DJANGO_SUPERUSER_PRIMER_NOMBRE='Jesus'
DJANGO_SUPERUSER_PRIMER_APELLIDO='Chacon'
"""
try:
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

# --- PASO 3: Función de Inicialización de la BD (sin cambios) ---


def initialize_database():
    import django
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection
    from django.db.utils import OperationalError

    print("Llamando a django.setup() desde initialize_database...")
    django.setup()
    print("Configuración de Django completada.")

    from myapp.models import Usuario, Tarifa

    try:
        # La mejor forma de saber si la BD está vacía es intentar una conexión
        # y luego verificar si las tablas existen o están pobladas.
        connection.ensure_connection()

        # Verificar si las migraciones ya se aplicaron y si hay datos
        if not Usuario.objects.filter(is_superuser=True).exists() or not Tarifa.objects.exists():
            print("\n[INICIALIZACIÓN DE BD REQUERIDA]")
            print("Aplicando migraciones...")
            call_command('migrate', interactive=False)
            print("Poblando base de datos...")
            call_command('seed_db', '--clean')
            print("¡Inicialización completada!")
        else:
            print("La base de datos ya existe y está poblada.")

    except OperationalError as oe:
        print(f"ERROR DE CONEXIÓN A LA BASE DE DATOS: {oe}")
        print("Por favor, asegúrese de que el servidor PostgreSQL esté corriendo y sea accesible.")
        input("La aplicación no pudo conectarse a la base de datos. Presiona Enter para salir.")
        sys.exit(1)
    except Exception as e:
        logging.exception(
            f"ERROR CRÍTICO durante la inicialización de la BD: {e}")
        input("La aplicación no pudo iniciarse correctamente. Presiona Enter para salir.")
        sys.exit(1)


# --- [NUEVO] Funciones para lanzar cada proceso hijo ---

def run_django_waitress():
    """Inicia el servidor web Django."""
    # Importaciones locales para que el proceso hijo las tenga
    from waitress import serve
    from myproject.wsgi import application  # Asegúrate que la ruta sea correcta

    print(
        ">>> [Proceso 1/3] Iniciando servidor Django con Waitress en el puerto 8000...")
    try:
        serve(application, host='0.0.0.0', port='8000', threads=8)
    except Exception as e:
        print(f"!!! Error al iniciar el servidor Django: {e}")


def run_celery_worker():
    """Inicia el Worker de Celery."""
    print(">>> [Proceso 2/3] Iniciando Celery Worker...")
    try:
        # --pool=solo es crucial para la compatibilidad con PyInstaller en Windows
        command = [sys.executable, '-m', 'celery', '-A',
                   'myproject.celery', 'worker', '--loglevel=info', '--pool=solo']
        subprocess.run(command)
    except Exception as e:
        print(f"!!! Error al iniciar Celery Worker: {e}")


def run_celery_beat():
    """Inicia el programador (Beat) de Celery."""
    print(">>> [Proceso 3/3] Iniciando Celery Beat...")
    try:
        pid_file = 'celerybeat.pid'
        if os.path.exists(pid_file):
            os.remove(pid_file)

        command = [sys.executable, '-m', 'celery', '-A', 'myproject.celery', 'beat',
                   '--loglevel=info', '--scheduler', 'django_celery_beat.schedulers:DatabaseScheduler']
        subprocess.run(command)
    except Exception as e:
        print(f"!!! Error al iniciar Celery Beat: {e}")


# --- [NUEVO] Punto de Entrada Principal con Multiprocesamiento ---
if __name__ == '__main__':
    # Necesario para PyInstaller en Windows
    multiprocessing.freeze_support()

    print("\n" + "="*50)
    print("--- SMGP App - INICIANDO SISTEMA ---")
    print("="*50, flush=True)

    try:
        # PASO A: Ejecutar la inicialización de la base de datos UNA SOLA VEZ en el proceso principal.
        initialize_database()

        print("\n" + "-"*50)
        print("Iniciando procesos en paralelo...")
        print("1. Servidor Web (Django/Waitress)")
        print("2. Procesador de Tareas (Celery Worker)")
        print("3. Programador de Tareas (Celery Beat)")
        print("La aplicación estará lista en http://localhost:8000")
        print("Presiona Ctrl+C en esta ventana para detener todos los servicios.")
        print("-"*50, flush=True)

        # PASO B: Crear los procesos para cada servicio.
        process_django = multiprocessing.Process(
            target=run_django_waitress, name="Django-Waitress")
        process_worker = multiprocessing.Process(
            target=run_celery_worker, name="Celery-Worker")
        process_beat = multiprocessing.Process(
            target=run_celery_beat, name="Celery-Beat")

        # PASO C: Iniciar todos los procesos.
        process_django.start()
        process_worker.start()
        process_beat.start()

        # PASO D: Esperar a que los procesos terminen.
        # Esto mantiene el script principal vivo. Si el usuario cierra esta ventana,
        # los procesos hijos también se terminarán.
        process_django.join()
        process_worker.join()
        process_beat.join()

        print(">>> Todos los procesos han finalizado. Cerrando aplicación.")

    except Exception as e:
        print("\n" + "="*70)
        print("!!! LA APLICACIÓN HA FALLADO DURANTE EL ARRANQUE !!!")
        logging.exception(f"ERROR: {e}")
        print("="*70)
        input("La aplicación ha fallado. Presiona Enter para cerrar esta ventana.")
