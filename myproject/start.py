# start.py - VERSIÓN FINAL Y ROBUSTA

import os
import sys
import multiprocessing
import logging
from pathlib import Path
from textwrap import dedent
from dotenv import load_dotenv

# --- PASO 1: Definir y ejecutar la carga del entorno INMEDIATAMENTE ---


def setup_environment():
    """
    Busca y carga el archivo .env. Esta es la primera acción del script.
    """
    print("Buscando y cargando archivo .env con python-dotenv...")
    try:
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).resolve().parent

        env_path = base_path / '.env'

        # La lógica para crear el .env por defecto se mantiene
        DEFAULT_ENV_CONTENT = dedent("""\
            # .env - Creado automáticamente.
            SECRET_KEY=Xgfei34531$&/$234fGHYtfhuY&6%$33rfFfHUu7854fdS3F%6HrR2dfdgG%653rfDfv-t43423sF$26fd6/%$
            DEBUG=False
            ALLOWED_HOSTS=*
            DATABASE_URL=postgres://postgres:7319@localhost:5432/smgp
            FERNET_KEY=X4ERAbaFKwrBXTwFk-v45F6a9mVfiT60jZKG-VqO7iA=
            SMGP_LICENSE_VERIFY_KEY_B64=48FUC+B/1sYVGhvmnRQuXKWwKqcIsg1cE49xF5VRxIY=
            DJANGO_SUPERUSER_USERNAME=jacr7887@gmail.com
            DJANGO_SUPERUSER_EMAIL=jacr7887@gmail.com
            DJANGO_SUPERUSER_PASSWORD=123456789/*-+
            DJANGO_SUPERUSER_PRIMER_NOMBRE=Jesus
            DJANGO_SUPERUSER_PRIMER_APELLIDO=Chacon
        """)
        if not env_path.exists():
            print(
                f"Archivo .env no encontrado. Creando uno nuevo en: {env_path}")
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_ENV_CONTENT)

        # 2. Usar la nueva librería para cargar el archivo en os.environ
        # El argumento override=True asegura que los valores del archivo .env
        # tengan prioridad, lo cual es importante.
        if load_dotenv(dotenv_path=env_path, override=True):
            print("Variables de entorno cargadas con éxito desde .env")
        else:
            print("ADVERTENCIA: No se pudo cargar el archivo .env.")

    except Exception as e:
        print(f"ERROR CRÍTICO: No se pudo procesar el archivo .env: {e}")
        input("Presiona Enter para salir.")
        sys.exit(1)


# Se llama a la función aquí, al principio de todo.
setup_environment()

# --- PASO 2: Configurar el entorno de Django ---
# Esto se ejecuta DESPUÉS de que el .env ha sido cargado.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # En modo congelado, PyInstaller maneja las rutas internas.
    project_path = sys._MEIPASS
else:
    # En desarrollo, nos aseguramos de que la ruta del proyecto esté en el sys.path.
    project_path = os.path.dirname(os.path.abspath(__file__))
    if project_path not in sys.path:
        sys.path.insert(0, project_path)


# --- PASO 3: Funciones para los procesos hijos (se mantienen igual) ---
def run_django_waitress():
    """Inicia el servidor web Waitress para servir la aplicación Django."""
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
    """Inicia el procesador de tareas en segundo plano."""
    import django
    django.setup()
    from django.core.management import call_command
    print(
        ">>> [Proceso 2/2] Iniciando Procesador de Tareas (django-background-tasks)...")
    try:
        call_command('process_tasks')
    except Exception as e:
        print(f"!!! Error al iniciar el procesador de tareas: {e}")


# --- PUNTO DE ENTRADA PRINCIPAL DE LA APLICACIÓN ---
if __name__ == '__main__':
    multiprocessing.freeze_support()

    # La llamada a load_env_from_file() ya se hizo arriba, por lo que se elimina de aquí.

    print("\n" + "="*50)
    print("--- SMGP App - FASE 1: INICIALIZACIÓN DE BASE DE DATOS ---")
    print("="*50, flush=True)

    try:
        # Importamos Django aquí para asegurar que el entorno ya está configurado
        import django
        from django.core.management import call_command
        from django.db import connection
        from django.db.utils import OperationalError

        # Configuramos Django UNA SOLA VEZ en el proceso principal
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

        # 3. Verificamos si hay que poblar la base de datos
        print("Verificando si la base de datos necesita ser poblada...")
        if not Usuario.objects.filter(is_superuser=True).exists() or not Tarifa.objects.exists():
            print("\n[POBLADO DE BD REQUERIDO]")
            print("Poblando base de datos con datos iniciales...")
            call_command('seed_db', '--clean')
            print("¡Poblado completado!")

            # --- [NUEVA LÍNEA DE DIAGNÓSTICO] ---
            # Justo después de crear el usuario, verificamos si la contraseña es correcta.
            print("\n--- EJECUTANDO PRUEBA DE VERIFICACIÓN DE CONTRASEÑA ---")
            from django.conf import settings
            superuser_email = settings.DJANGO_SUPERUSER_EMAIL
            superuser_password = settings.DJANGO_SUPERUSER_PASSWORD
            call_command('check_user', superuser_email, superuser_password)
            print("--- FIN DE LA PRUEBA DE VERIFICACIÓN ---\n")
            # -----------------------------------------

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

    # --- FASE 2: LANZAR PROCESOS HIJOS ---
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
