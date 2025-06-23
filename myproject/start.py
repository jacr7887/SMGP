# start.py - VERSIÓN FINAL A PRUEBA DE RACE CONDITIONS
import os
import sys
import multiprocessing
import logging
from pathlib import Path

# --- PASO 1: Configurar el entorno ANTES DE CUALQUIER IMPORT DE DJANGO ---
# (Esta parte está bien, no la cambiamos)
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    project_path = sys._MEIPASS
else:
    project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# --- PASO 2: Función para cargar .env (Esta parte está bien) ---


def load_env_from_file():
    print("Buscando y cargando archivo .env...")
    try:
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
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
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if (value.startswith("'") and value.endswith("'")) or \
                       (value.startswith('"') and value.endswith('"')):
                        value = value[1:-1]
                    os.environ.setdefault(key, value)
        print("Variables de entorno cargadas con éxito desde .env")
    except Exception as e:
        print(f"ERROR CRÍTICO: No se pudo procesar el archivo .env: {e}")
        input("Presiona Enter para salir.")
        sys.exit(1)

# --- PASO 3: Funciones para los procesos hijos (Las mantenemos igual) ---


def run_django_waitress():
    import django
    django.setup()
    from waitress import serve
    from myproject.wsgi import application
    print(
        ">>> [Proceso 1/2] Iniciando servidor Django con Waitress en el puerto 8000...")
    try:
        serve(application, host='0.0.0.0', port='8000', threads=8)
    except Exception as e:
        print(f"!!! Error al iniciar el servidor Django: {e}")


def run_task_processor():
    import django
    django.setup()
    from django.core.management import call_command
    print(
        ">>> [Proceso 2/2] Iniciando Procesador de Tareas (django-background-tasks)...")
    try:
        call_command('process_tasks')
    except Exception as e:
        print(f"!!! Error al iniciar el procesador de tareas: {e}")


# --- PUNTO DE ENTRADA PRINCIPAL (LA VERSIÓN A PRUEBA DE TODO) ---
if __name__ == '__main__':
    multiprocessing.freeze_support()
    load_env_from_file()

    print("\n" + "="*50)
    print("--- SMGP App - FASE 1: INICIALIZACIÓN DE BASE DE DATOS ---")
    print("="*50, flush=True)

    try:
        # Importamos Django y sus componentes aquí, en el proceso principal
        import django
        from django.core.management import call_command
        from django.db import connection
        from django.db.utils import OperationalError

        # Configuramos Django UNA SOLA VEZ
        django.setup()

        # Importamos los modelos DESPUÉS de django.setup()
        from myapp.models import Usuario, Tarifa

        # 1. Verificamos conexión
        print("Verificando conexión a la base de datos...")
        connection.ensure_connection()
        print("Conexión exitosa.")

        # 2. Aplicamos migraciones
        print("Aplicando migraciones (esto crea las tablas si no existen)...")
        call_command('migrate', interactive=False)
        print("Migraciones completadas.")

        # 3. Verificamos si hay que poblar
        print("Verificando si la base de datos necesita ser poblada...")
        if not Usuario.objects.filter(is_superuser=True).exists() or not Tarifa.objects.exists():
            print("\n[POBLADO DE BD REQUERIDO]")
            print("Poblando base de datos con datos iniciales...")
            call_command('seed_db', '--clean')
            print("¡Poblado completado!")
        else:
            print("La base de datos ya contiene datos. No se requiere poblado.")

    except OperationalError as oe:
        print(f"ERROR DE CONEXIÓN A LA BASE DE DATOS: {oe}")
        input("Presiona Enter para salir.")
        sys.exit(1)
    except Exception as e:
        logging.exception(f"ERROR CRÍTICO durante la inicialización: {e}")
        input("Presiona Enter para salir.")
        sys.exit(1)

    # --- FASE 2: LANZAR PROCESOS ---
    # Solo si la inicialización fue exitosa, lanzamos los procesos hijos.
    print("\n" + "="*50)
    print("--- SMGP App - FASE 2: INICIANDO SERVICIOS ---")
    print("="*50, flush=True)

    try:
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
        logging.exception(
            f"ERROR CRÍTICO durante la ejecución de servicios: {e}")
        input("Presiona Enter para salir.")
