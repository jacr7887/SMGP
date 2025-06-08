# MPC/myproject/start.py
from django.utils import timezone
from django.conf import settings
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.db import connection, ProgrammingError, OperationalError
from waitress import serve
import os
import sys
import django  # Importar django primero
from pathlib import Path  # Buena práctica, aunque no se use directamente aquí
from datetime import timedelta  # Para la licencia de prueba

# --- Configuración Inicial y Django Setup ---
# 1. Establecer DJANGO_SETTINGS_MODULE (crucial ANTES de django.setup())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# 2. Llamar a django.setup() para cargar settings y configurar Django.
try:
    print("--- start.py: Iniciando django.setup() ---")
    django.setup()
    print("--- start.py: django.setup() completado ---")
except ImportError as exc:
    print(
        f"ErrorCRITICO_ImportDjango: No se pudo importar o configurar Django: {exc}")
    # ... (manejo de error como lo tenías, escribiendo a archivo si es frozen) ...
    if getattr(sys, 'frozen', False):
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
# Asegúrate que la ruta de importación sea correcta para tu modelo LicenseInfo
# y otros modelos que puedas necesitar aquí.
try:
    from myapp.models import LicenseInfo, ContratoIndividual, ContratoColectivo
except ImportError:
    print("ErrorCRITICO_ModelImport: No se pudieron importar modelos de 'myapp'. Verifica INSTALLED_APPS y la estructura del proyecto.")
    # ... (manejo de error similar al anterior) ...
    sys.exit(1)


# --- Función para asegurar licencia de prueba ---
def ensure_trial_license():
    """
    Asegura que exista un registro de licencia de prueba en la base de datos.
    Lo crea si no existe, o lo actualiza/renueva si es una de prueba.
    """
    print("--- start.py: Asegurando licencia de prueba... ---")
    try:
        singleton_id = getattr(LicenseInfo, 'SINGLETON_ID', 1)
        default_key = 'TRIAL-LICENSE-KEY-FOR-EXE'  # Clave específica
        default_expiry_days = getattr(
            settings, 'TRIAL_LICENSE_DAYS', 30)  # Ej: 30 días de prueba

        license_obj, created = LicenseInfo.objects.get_or_create(
            pk=singleton_id,
            defaults={
                'license_key': default_key,
                'expiry_date': timezone.now().date() + timedelta(days=default_expiry_days)
            }
        )
        if created:
            print(
                f"--- start.py: Licencia de prueba CREADA (ID: {license_obj.pk}). Expira: {license_obj.expiry_date} ---")
        else:
            is_trial_key = default_key in license_obj.license_key.upper()  # Más flexible
            is_expired = license_obj.expiry_date < timezone.now().date()

            if is_trial_key and is_expired:
                new_expiry = timezone.now().date() + timedelta(days=default_expiry_days)
                license_obj.expiry_date = new_expiry
                license_obj.license_key = default_key  # Asegurar que sea la clave de prueba
                license_obj.save()
                print(
                    f"--- start.py: Licencia de prueba (ID: {license_obj.pk}) RENOVADA. Expira: {license_obj.expiry_date} ---")
            elif is_trial_key:
                print(
                    f"--- start.py: Licencia de prueba (ID: {license_obj.pk}) existente encontrada y válida. Expira: {license_obj.expiry_date} ---")
            else:
                print(
                    f"--- start.py: Licencia de producción (ID: {license_obj.pk}) existente encontrada. Expira: {license_obj.expiry_date} ---")

    except ProgrammingError as pe_license:
        print(
            f"--- start.py: ProgrammingError asegurando licencia (Tabla 'LicenseInfo' podría no existir aún, verifica migraciones): {pe_license} ---")
    except Exception as e_license:
        print(
            f"--- start.py: ERROR asegurando licencia de prueba: {type(e_license).__name__} - {e_license} ---")
        import traceback
        traceback.print_exc()


# --- Función para configurar la base de datos al inicio ---
def setup_database():
    """
    Aplica migraciones, asegura licencia, superusuario y opcionalmente siembra la base de datos.
    """
    print("--- start.py: Iniciando configuración de base de datos ---")

    # 1. Aplicar Migraciones
    try:
        print("--- start.py: Aplicando migraciones... ---")
        call_command('migrate', interactive=False, verbosity=1)
        print("--- start.py: Migraciones aplicadas (o ya estaban al día). ---")
    except (OperationalError, ProgrammingError) as db_error:
        print(
            f"--- start.py: ERROR CRÍTICO de BD aplicando migraciones: {type(db_error).__name__} - {db_error} ---")
        print("--- start.py: Verifica la conexión a la base de datos y que el servidor de BD esté corriendo. ---")
        return False
    except Exception as e:
        print(
            f"--- start.py: ADVERTENCIA - Error inesperado aplicando migraciones: {type(e).__name__} - {e} ---")
        # Considerar si continuar es seguro

    # 2. Asegurar Licencia de Prueba (DESPUÉS de migraciones)
    ensure_trial_license()

    # 3. Asegurar Superusuario
    print("--- start.py: Asegurando superusuario... ---")
    try:
        # Asume que este comando existe y es robusto
        call_command('ensure_superuser')
        print("--- start.py: Intento de asegurar superusuario completado. ---")
    except Exception as e:
        print(
            f"--- start.py: ADVERTENCIA - Error asegurando superusuario: {type(e).__name__} - {e} ---")

    # 4. Sembrar Base de Datos (Opcional)
    print("--- start.py: Verificando si se necesita sembrar datos... ---")
    try:
        num_contratos = 0
        try:
            # Asegurarse que las tablas existen antes de contar
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('myapp_contratoindividual');")
                table_exists_ci = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT to_regclass('myapp_contratocolectivo');")
                table_exists_cc = cursor.fetchone()[0]

            if table_exists_ci:
                num_contratos_ind = ContratoIndividual.objects.count()
            else:
                num_contratos_ind = 0
                print(
                    "--- start.py: Tabla ContratoIndividual no encontrada para conteo. ---")

            if table_exists_cc:
                num_contratos_col = ContratoColectivo.objects.count()
            else:
                num_contratos_col = 0
                print(
                    "--- start.py: Tabla ContratoColectivo no encontrada para conteo. ---")

            num_contratos = num_contratos_ind + num_contratos_col
            print(
                f"--- start.py: Contratos Individuales: {num_contratos_ind}, Colectivos: {num_contratos_col}. Total: {num_contratos} ---")

        # Si las tablas aún no existen a pesar de la verificación anterior (raro)
        except ProgrammingError:
            print("--- start.py: Tablas de contratos no encontradas (ProgrammingError). Asumiendo 0 para seed. ---")

        umbral_contratos_para_seed = getattr(
            settings, 'UMBRAL_CONTRATOS_PARA_SEED', 5)
        # Nueva opción para forzar
        force_seed = getattr(settings, 'FORCE_SEED_ON_START', False)

        if force_seed or num_contratos < umbral_contratos_para_seed:
            if force_seed:
                print(
                    "--- start.py: FORZANDO sembrado de base de datos (FORCE_SEED_ON_START=True)... ---")
            else:
                print(
                    f"--- start.py: Sembrando base de datos (contratos: {num_contratos} < {umbral_contratos_para_seed})... ---")

            # AUMENTAR NÚMEROS PARA DATOS MÁS "IMPRESIONANTES"
            call_command('seed_db',
                         users=50,              # Más usuarios
                         intermediarios=25,     # Más intermediarios
                         afiliados_ind=200,     # Muchos más afiliados individuales
                         afiliados_col=50,      # Más empresas
                         tarifas=100,           # Más variedad de tarifas
                         contratos_ind=150,     # Muchos más contratos individuales
                         contratos_col=70,      # Más contratos colectivos
                         # Muchas facturas (varias por contrato)
                         facturas=1000,
                         reclamaciones=300,     # Un buen número de reclamaciones
                         # Muchos pagos (varios por factura/reclamación)
                         pagos=1200,
                         igtf_chance=30,        # Chance de IGTF
                         pago_parcial_chance=40  # Chance de pago parcial
                         )
            print("--- start.py: Sembrado de base de datos completado. ---")
        else:
            print(
                f"--- start.py: Base de datos parece ya sembrada (contratos: {num_contratos}). Saltando seed. ---")

    except ProgrammingError as pe:
        print(
            f"--- start.py: ProgrammingError durante el conteo/sembrado (Tablas podrían no existir): {pe} ---")
    except Exception as e:
        print(
            f"--- start.py: ERROR durante el sembrado de datos: {type(e).__name__} - {e} ---")
        import traceback
        traceback.print_exc()

    print("--- start.py: Configuración inicial de base de datos finalizada. ---")
    return True


# --- Punto de Entrada Principal ---
if __name__ == '__main__':
    print(f"--- start.py: __main__ - CWD actual: {os.getcwd()} ---")
    print(
        f"--- start.py: __main__ - DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')} ---")
    print(
        f"--- start.py: __main__ - SMGP_APP_EXECUTABLE_DIR: {os.environ.get('SMGP_APP_EXECUTABLE_DIR')} ---")

    print("--- start.py: Llamando a setup_database()... ---")
    if not setup_database():
        print("--- start.py: Falló la configuración crítica de la base de datos. La aplicación podría no funcionar correctamente. ---")
        if getattr(sys, 'frozen', False):
            with open("critical_error_db_setup.txt", "w") as f_error:
                f_error.write("Falló setup_database()\n")
        else:
            input("Presiona Enter para salir...")
        sys.exit(1)

    print("--- start.py: Obteniendo aplicación WSGI... ---")
    try:
        application = get_wsgi_application()
        print("--- start.py: Aplicación WSGI obtenida. ---")
    except Exception as e_wsgi:
        print(
            f"ErrorCRITICO_WSGI: No se pudo obtener la aplicación WSGI: {type(e_wsgi).__name__} - {e_wsgi}")
        sys.exit(1)

    host = getattr(settings, 'SERVER_HOST', '0.0.0.0')
    port = int(getattr(settings, 'SERVER_PORT', 8000))  # Asegurar que sea int
    # Asegurar que sea int
    num_threads = int(getattr(settings, 'WAITRESS_THREADS', 8))

    django_debug_mode = settings.DEBUG
    print(
        f"--- start.py: DEBUG mode (desde settings.py): {django_debug_mode} ---")
    print(
        f"--- start.py: Iniciando servidor Waitress en http://{host}:{port} con {num_threads} hilos ---")
    print("--- start.py: Waitress no usa autoreload por defecto.")
    print("--- start.py: Para detener el servidor, cierra esta ventana o presiona Ctrl+C.")

    try:
        serve(application, host=host, port=port, threads=num_threads)
    except OSError as e_os:
        print(
            f"ErrorCRITICO_Waitress_OSError: No se pudo iniciar el servidor Waitress (¿Puerto {port} en uso?): {e_os}")
        sys.exit(1)
    except Exception as e_serve:
        print(
            f"ErrorCRITICO_Waitress: No se pudo iniciar el servidor Waitress: {type(e_serve).__name__} - {e_serve}")
        sys.exit(1)
