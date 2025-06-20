# start.py (Versión Final, a prueba de todo, con lector de .env integrado)

import os
import sys
import multiprocessing
import subprocess
from pathlib import Path
import logging

# --- PASO 1: Configurar el entorno ANTES DE CUALQUIER IMPORT DE DJANGO ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Modo Congelado (.exe)
    # _MEIPASS es la carpeta temporal donde PyInstaller extrae los archivos
    project_path = sys._MEIPASS
else:
    # Modo Desarrollo (python manage.py ...)
    # La ruta del script start.py
    project_path = os.path.dirname(os.path.abspath(__file__))

# Añadimos la ruta del proyecto al path de Python para que encuentre los módulos
sys.path.insert(0, project_path)
# Establecemos la variable de entorno que Django usará para encontrar la configuración
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')


# --- [SOLUCIÓN DEFINITIVA] Función para leer .env y cargar variables al entorno ---
def load_env_from_file():
    """
    Busca el archivo .env, lo crea si no existe, y carga sus variables
    directamente en el entorno de ejecución de Python (os.environ).
    """
    print("Buscando y cargando archivo .env...")
    try:
        # Determinar la ruta base donde debe estar el .env
        if getattr(sys, 'frozen', False):
            # Si es un .exe, el .env debe estar junto al ejecutable
            base_path = Path(sys.executable).parent
        else:
            # En desarrollo, el .env está en la carpeta raíz del proyecto (un nivel arriba de donde está start.py)
            base_path = Path(__file__).parent.parent

        env_path = base_path / '.env'

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
        if not env_path.exists():
            print(
                f"Archivo .env no encontrado. Creando uno nuevo en: {env_path}")
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_ENV_CONTENT)

        # Leemos el archivo línea por línea y cargamos las variables
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Quitar comillas si las hay
                    if (value.startswith("'") and value.endswith("'")) or \
                       (value.startswith('"') and value.endswith('"')):
                        value = value[1:-1]
                    # Establecer la variable de entorno si no existe ya
                    os.environ.setdefault(key, value)
        print("Variables de entorno cargadas con éxito desde .env")

    except Exception as e:
        print(f"ERROR CRÍTICO: No se pudo procesar el archivo .env: {e}")
        input("Presiona Enter para salir.")
        sys.exit(1)


def initialize_database():
    """
    Verifica la conexión a la BD y ejecuta migraciones/poblado si es necesario.
    """
    import django
    from django.core.management import call_command
    from django.db import connection
    from django.db.utils import OperationalError

    # Llamar a django.setup() es crucial para que Django se configure
    print("Llamando a django.setup() desde initialize_database...")
    django.setup()
    print("Configuración de Django completada.")

    from myapp.models import Usuario, Tarifa

    try:
        connection.ensure_connection()
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


def run_django_waitress():
    """Inicia el servidor web Django con Waitress."""
    from waitress import serve
    from myproject.wsgi import application
    print(
        ">>> [Proceso 1/2] Iniciando servidor Django con Waitress en el puerto 8000...")
    try:
        serve(application, host='0.0.0.0', port='8000', threads=8)
    except Exception as e:
        print(f"!!! Error al iniciar el servidor Django: {e}")


def run_task_processor():
    """Inicia el procesador de tareas de django-background-tasks."""
    print(
        ">>> [Proceso 2/2] Iniciando Procesador de Tareas (django-background-tasks)...")
    try:
        # Usamos call_command, que es la forma limpia de ejecutar comandos de gestión
        from django.core.management import call_command
        call_command('process_tasks')
    except Exception as e:
        print(f"!!! Error al iniciar el procesador de tareas: {e}")


# --- Punto de Entrada Principal con Multiprocesamiento ---
if __name__ == '__main__':
    # Necesario para que el multiprocesamiento funcione correctamente con PyInstaller
    multiprocessing.freeze_support()

    # [CAMBIO CLAVE] Cargamos el .env ANTES de que Django o cualquier otra cosa se inicie
    load_env_from_file()

    print("\n" + "="*50)
    print("--- SMGP App - PROCESO PRINCIPAL INICIANDO ---")
    print("="*50, flush=True)

    try:
        # Se ejecuta la inicialización una sola vez en el proceso principal.
        initialize_database()

        print("\n" + "-"*50)
        print("Iniciando procesos en paralelo...")
        print("1. Servidor Web (Waitress)")
        print("2. Procesador de Tareas (Background Tasks)")
        print("La aplicación estará lista en http://localhost:8000")
        print("Presiona Ctrl+C en esta ventana para detener todos los servicios.")
        print("-"*50, flush=True)

        # Se crean y lanzan los dos procesos necesarios.
        process_django = multiprocessing.Process(
            target=run_django_waitress, name="Django-Waitress")
        process_tasks = multiprocessing.Process(
            target=run_task_processor, name="Task-Processor")

        process_django.start()
        process_tasks.start()

        process_django.join()
        process_tasks.join()

        print(">>> Todos los procesos han finalizado. Cerrando aplicación.")

    except Exception as e:
        print("\n" + "="*70)
        print("!!! LA APLICACIÓN HA FALLADO DURANTE EL ARRANQUE !!!")
        logging.exception(f"ERROR: {e}")
        print("="*70)
        input("La aplicación ha fallado. Presiona Enter para cerrar esta ventana.")
