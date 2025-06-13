# start.py
from django.core.wsgi import get_wsgi_application
import waitress
import os
import sys
from pathlib import Path

DEFAULT_ENV_CONTENT = """# .env - Creado automáticamente.
SECRET_KEY='django-insecure-DEFAULT-KEY-CHANGE-ME-12345!@#$%'
DEBUG=False
ALLOWED_HOSTS=*
DATABASE_URL=postgres://postgres:7319@localhost:5432/smgp
SMGP_LICENSE_VERIFY_KEY_B64='48FUC+B/1sYVGhvmnRQuXKWwKqcIsg1cE49xF5VRxIY='
DJANGO_SUPERUSER_USERNAME='admin'
DJANGO_SUPERUSER_EMAIL='admin@example.com'
DJANGO_SUPERUSER_PASSWORD='password'
DJANGO_SUPERUSER_PRIMER_NOMBRE='Admin'
DJANGO_SUPERUSER_PRIMER_APELLIDO='User'
"""
env_path = Path(sys.executable).parent / '.env'
if not env_path.exists():
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(DEFAULT_ENV_CONTENT)


try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    application = get_wsgi_application()
    print("\n--- SMGP App ---", flush=True)
    print(f"Iniciando servidor Waitress en http://127.0.0.1:8000", flush=True)
    print("Presiona Ctrl+C para detener el servidor.", flush=True)

    waitress.serve(application, host='127.0.0.1', port=8000)
except Exception as e:
    print("\n" + "="*70)
    print("!!! LA APLICACIÓN HA FALLADO DURANTE EL ARRANQUE DE DJANGO !!!")
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    print("="*70)
    input("La aplicación ha fallado. Presiona Enter para cerrar esta ventana.")
