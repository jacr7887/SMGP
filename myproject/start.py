# MPC/myproject/start.py
from waitress import serve
from django.db import connection, ProgrammingError, OperationalError
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command
from django.conf import settings
import os
import sys
import django  # Importar django primero
from pathlib import Path  # No es estrictamente necesario aquí pero es buena práctica

# --- Configuración Inicial y Django Setup ---
# 1. Establecer DJANGO_SETTINGS_MODULE (crucial ANTES de django.setup())
#    El runtime hook (pyi_runtimehook.py) también intenta establecerlo, pero es bueno tenerlo aquí.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# 2. Llamar a django.setup() para cargar settings y configurar Django.
#    Esto debe hacerse antes de importar modelos o llamar management commands.
try:
    print("--- start.py: Iniciando django.setup() ---")
    django.setup()
    print("--- start.py: django.setup() completado ---")
except ImportError as exc:
    print(
        f"ErrorCRITICO_ImportDjango: No se pudo importar o configurar Django: {exc}")
    print("Por favor, asegúrate de que Django está correctamente instalado y empaquetado.")
    # En un entorno empaquetado, input() podría no funcionar si no hay consola.
    # Considera loguear a un archivo si esto es un problema.
    if getattr(sys, 'frozen', False):
        # Podrías escribir este error a un archivo conocido si no hay consola
        with open("critical_error_start.txt", "w") as f_error:
            f_error.write(f"ErrorCRITICO_ImportDjango: {exc}\n")
            import traceback
            traceback.print_exc(file=f_error)
    else:
        input("Presiona Enter para salir...")
    sys.exit(1)
except Exception as e:
    print(
        f"ErrorCRITICO_DjangoSetup: Error durante django.setup(): {type(e).__name__} - {e}")
    import traceback
    traceback.print_exc()
    if getattr(sys, 'frozen', False):
        with open("critical_error_django_setup.txt", "w") as f_error:
            f_error.write(
                f"ErrorCRITICO_DjangoSetup: {type(e).__name__} - {e}\n")
            traceback.print_exc(file=f_error)
    else:
        input("Presiona Enter para salir...")
    sys.exit(1)

# --- Imports después de django.setup() ---
# Solo ahora podemos importar cosas que dependen de Django configurado

# --- Función para configurar la base de datos al inicio ---


def setup_database():
    """
    Aplica migraciones, asegura el superusuario y opcionalmente siembra la base de datos.
    """
    print("--- start.py: Iniciando configuración de base de datos ---")

    # 1. Aplicar Migraciones
    try:
        print("--- start.py: Aplicando migraciones... ---")
        call_command('migrate', interactive=False, verbosity=1)
        print("--- start.py: Migraciones aplicadas (o ya estaban al día). ---")
    except (OperationalError, ProgrammingError) as db_error:  # Errores comunes si la BD no está lista
        print(
            f"--- start.py: ERROR CRÍTICO de BD aplicando migraciones: {type(db_error).__name__} - {db_error} ---")
        print("--- start.py: Verifica la conexión a la base de datos y que el servidor de BD esté corriendo. ---")
        # Podrías decidir salir si las migraciones son críticas para el arranque.
        # input("Presiona Enter para intentar continuar o cierra la aplicación...")
        return False  # Indicar fallo
    except Exception as e:
        print(
            f"--- start.py: ADVERTENCIA - Error inesperado aplicando migraciones: {type(e).__name__} - {e} ---")
        # Continuar podría ser posible, pero con riesgo.

    # 2. Asegurar Superusuario
    print("--- start.py: Asegurando superusuario... ---")
    try:
        # El comando 'ensure_superuser' debe ser robusto y manejar variables de entorno faltantes.
        # DJANGO_SUPERUSER_* env vars deben estar disponibles desde el .env o sistema.
        call_command('ensure_superuser')
        print("--- start.py: Intento de asegurar superusuario completado. ---")
    except Exception as e:
        print(
            f"--- start.py: ADVERTENCIA - Error asegurando superusuario: {type(e).__name__} - {e} ---")

    # 3. Sembrar Base de Datos (Opcional, basado en conteo de datos existentes)
    print("--- start.py: Verificando si se necesita sembrar datos... ---")
    try:
        # Importar modelos aquí, después de migraciones y setup.
        from myapp.models import ContratoIndividual, ContratoColectivo  # Ajusta a tus modelos

        num_contratos = 0
        # Intentar contar. Si las tablas no existen (a pesar de migrate), ProgrammingError ocurrirá.
        try:
            num_contratos_ind = ContratoIndividual.objects.count()
            num_contratos_col = ContratoColectivo.objects.count()
            num_contratos = num_contratos_ind + num_contratos_col
            print(
                f"--- start.py: Contratos Individuales: {num_contratos_ind}, Colectivos: {num_contratos_col}. Total: {num_contratos} ---")
        except ProgrammingError:  # Si las tablas aún no existen
            print("--- start.py: Tablas de contratos no encontradas. Asumiendo 0 para seed. (Migraciones podrían haber fallado o es la primera vez y no se crearon). ---")
            # Si las migraciones fallaron críticamente arriba, esto podría no ser necesario.

        umbral_contratos_para_seed = getattr(
            settings, 'UMBRAL_CONTRATOS_PARA_SEED', 5)  # Configurable en settings.py
        if num_contratos < umbral_contratos_para_seed:
            print(
                f"--- start.py: Sembrando base de datos (contratos: {num_contratos} < {umbral_contratos_para_seed})... ---")
            # Ajusta los argumentos de seed_db según necesites
            # Es buena idea hacer estos parámetros configurables también, quizás vía settings o .env
            call_command('seed_db', users=30, intermediarios=15, afiliados_ind=30, afiliados_col=15,
                         tarifas=30, contratos_ind=24, contratos_col=12, facturas=60,
                         reclamaciones=30, pagos=45, igtf_chance=50, pago_parcial_chance=60)  # Ejemplo
            print("--- start.py: Sembrado de base de datos completado. ---")
        else:
            print(
                f"--- start.py: Base de datos parece ya sembrada (contratos: {num_contratos}). Saltando seed. ---")

    except ProgrammingError as pe:
        print(
            f"--- start.py: ProgrammingError durante el conteo/sembrado de datos (Tablas podrían no existir aún): {pe} ---")
    except Exception as e:
        print(
            f"--- start.py: ERROR durante el sembrado de datos: {type(e).__name__} - {e} ---")

    print("--- start.py: Configuración inicial de base de datos finalizada. ---")
    return True


# --- Punto de Entrada Principal ---
if __name__ == '__main__':
    # El CWD ya debería ser la carpeta del .exe (o _MEIPASS para onefile) gracias al runtime hook.
    print(
        f"--- start.py: __main__ - CWD actual (debería ser la carpeta del exe o _MEIPASS): {os.getcwd()} ---")
    print(
        f"--- start.py: __main__ - DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')} ---")
    print(
        f"--- start.py: __main__ - SMGP_APP_EXECUTABLE_DIR: {os.environ.get('SMGP_APP_EXECUTABLE_DIR')} ---")

    # Ejecutar configuración de la base de datos
    print("--- start.py: Llamando a setup_database()... ---")
    if not setup_database():
        print("--- start.py: Falló la configuración crítica de la base de datos. La aplicación podría no funcionar correctamente. ---")
        # Podrías decidir salir aquí si es un fallo crítico.
        # input("Presiona Enter para salir...")
        # sys.exit(1)

    # 3. Obtener la aplicación WSGI (después de setup y db_setup)
    print("--- start.py: Obteniendo aplicación WSGI... ---")
    try:
        application = get_wsgi_application()
        print("--- start.py: Aplicación WSGI obtenida. ---")
    except Exception as e_wsgi:
        print(
            f"ErrorCRITICO_WSGI: No se pudo obtener la aplicación WSGI: {type(e_wsgi).__name__} - {e_wsgi}")
        import traceback
        traceback.print_exc()
        if getattr(sys, 'frozen', False):
            with open("critical_error_wsgi.txt", "w") as f_error:
                f_error.write(
                    f"ErrorCRITICO_WSGI: {type(e_wsgi).__name__} - {e_wsgi}\n")
                traceback.print_exc(file=f_error)
        else:
            input("Presiona Enter para salir...")
        sys.exit(1)

    # Configuración del servidor Waitress
    # Leer host y puerto desde settings.py o .env para mayor flexibilidad
    # Por ejemplo, en settings.py: SERVER_HOST = env('SERVER_HOST', default='0.0.0.0')
    #                               SERVER_PORT = env.int('SERVER_PORT', default=8000)
    host = getattr(settings, 'SERVER_HOST', '0.0.0.0')
    port = getattr(settings, 'SERVER_PORT', 8000)
    num_threads = getattr(settings, 'WAITRESS_THREADS', 8)  # Configurable

    django_debug_mode = settings.DEBUG  # settings ya está cargado
    print(
        f"--- start.py: DEBUG mode (desde settings.py): {django_debug_mode} ---")

    print(
        f"--- start.py: Iniciando servidor Waitress en http://{host}:{port} con {num_threads} hilos ---")
    print("--- start.py: Waitress no usa autoreload por defecto (comportamiento similar a manage.py runserver --noreload). ---")
    print("--- start.py: Para detener el servidor, cierra esta ventana o presiona Ctrl+C si la consola lo permite. ---")

    try:
        serve(application, host=host, port=port, threads=num_threads)
    except OSError as e_os:  # Común si el puerto ya está en uso
        print(
            f"ErrorCRITICO_Waitress_OSError: No se pudo iniciar el servidor Waitress (¿Puerto {port} en uso?): {e_os}")
        if getattr(sys, 'frozen', False):
            with open("critical_error_waitress.txt", "w") as f_error:
                f_error.write(f"ErrorCRITICO_Waitress_OSError: {e_os}\n")
        else:
            input("Presiona Enter para salir...")
        sys.exit(1)
    except Exception as e_serve:
        print(
            f"ErrorCRITICO_Waitress: No se pudo iniciar el servidor Waitress: {type(e_serve).__name__} - {e_serve}")
        import traceback
        traceback.print_exc()
        if getattr(sys, 'frozen', False):
            with open("critical_error_waitress.txt", "w") as f_error:
                f_error.write(
                    f"ErrorCRITICO_Waitress: {type(e_serve).__name__} - {e_serve}\n")
                traceback.print_exc(file=f_error)
        else:
            input("Presiona Enter para salir...")
        sys.exit(1)
