# run.py (Versión a prueba de errores)
import logging
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from waitress import serve
import os
import sys
import subprocess
import threading
import webbrowser

# --- INICIO DEL CÓDIGO CLAVE DE CORRECCIÓN ---
# Esto asegura que la aplicación pueda encontrar sus propios módulos (myapp, myproject)
# tanto en desarrollo como cuando está empaquetada por PyInstaller.
if getattr(sys, 'frozen', False):
    # Si la aplicación está congelada (es un .exe), la raíz es el directorio
    # que contiene el ejecutable.
    project_root = os.path.dirname(sys.executable)
else:
    # En desarrollo, la raíz es el directorio que contiene este script (run.py).
    project_root = os.path.dirname(os.path.abspath(__file__))

# Añadimos la raíz del proyecto al path de Python.
# Ahora importaciones como 'from myapp.models import ...' funcionarán siempre.
sys.path.insert(0, project_root)
# --- FIN DEL CÓDIGO CLAVE DE CORRECCIÓN ---


# Configura un logger básico para este script
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - [Launcher] - %(message)s')


def run_migrations():
    """Ejecuta las migraciones de Django."""
    logging.info("Verificando y aplicando migraciones de base de datos...")
    try:
        command = [sys.executable, 'manage.py', 'migrate', '--noinput']
        # El CWD (Current Working Directory) debe ser la raíz del proyecto para que manage.py funcione.
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, cwd=project_root)
        logging.info("Migraciones aplicadas correctamente.")
        logging.debug(f"Salida de migrate: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logging.error("¡ERROR al aplicar migraciones!")
        logging.error(f"STDOUT: {e.stdout}")
        logging.error(f"STDERR: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        logging.error(
            "Error: 'manage.py' no encontrado. Asegúrate de que el script se ejecuta desde la raíz del proyecto.")
        sys.exit(1)


def ensure_superuser():
    """Asegura que exista un superusuario."""
    if settings.DJANGO_SUPERUSER_USERNAME and settings.DJANGO_SUPERUSER_PASSWORD:
        logging.info("Verificando la existencia del superusuario...")
        from myapp.models import Usuario
        if not Usuario.objects.filter(username=settings.DJANGO_SUPERUSER_USERNAME).exists():
            logging.info(
                f"Creando superusuario '{settings.DJANGO_SUPERUSER_USERNAME}'...")
            Usuario.objects.create_superuser(
                username=settings.DJANGO_SUPERUSER_USERNAME,
                email=settings.DJANGO_SUPERUSER_EMAIL,
                password=settings.DJANGO_SUPERUSER_PASSWORD,
                primer_nombre=settings.DJANGO_SUPERUSER_PRIMER_NOMBRE,
                primer_apellido=settings.DJANGO_SUPERUSER_PRIMER_APELLIDO
            )
            logging.info("Superusuario creado exitosamente.")
        else:
            logging.info("El superusuario ya existe.")


def start_server():
    """Inicia el servidor Waitress."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

    import django
    django.setup()

    run_migrations()
    ensure_superuser()

    application = get_wsgi_application()
    host = '127.0.0.1'
    port = 8000
    url = f"http://{host}:{port}"
    logging.info(f"Iniciando servidor en {url}")

    threading.Timer(1.25, lambda: webbrowser.open(url)).start()
    serve(application, host=host, port=port, threads=8)


if __name__ == '__main__':
    start_server()
