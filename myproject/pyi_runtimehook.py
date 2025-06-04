import os
import sys

# print("--- pyi_runtimehook.py: INICIO ---")
# Variable de entorno que settings.py usará para encontrar el .env
ENV_VAR_FOR_EXECUTABLE_DIR = 'SMGP_APP_EXECUTABLE_DIR'

if getattr(sys, 'frozen', False):  # Estamos en un entorno empaquetado
    # Tanto para --onefile como para --onedir, sys.executable es la ruta al ejecutable.
    # El archivo .env debe estar en el mismo directorio que el .exe.
    executable_dir = os.path.dirname(sys.executable)
    application_path_for_env = os.path.abspath(executable_dir)

    # Cambiar el directorio de trabajo actual a donde está el .exe
    # Esto ayuda a que las rutas relativas para archivos de datos (como .env, media) funcionen como se espera.
    os.chdir(application_path_for_env)
    # print(f"--- pyi_runtimehook.py (FROZEN): CWD y {ENV_VAR_FOR_EXECUTABLE_DIR} seteados a: {application_path_for_env} ---")
else:  # Corriendo como script normal (desarrollo)
    # En desarrollo, el .env suele estar en la raíz del proyecto (donde está manage.py)
    # settings.py puede manejar esto por defecto.
    application_path_for_env = os.path.abspath(
        os.getcwd())  # O SPECPATH si lo prefieres
    # print(f"--- pyi_runtimehook.py (SCRIPT): {ENV_VAR_FOR_EXECUTABLE_DIR} seteado a: {application_path_for_env} ---")

os.environ[ENV_VAR_FOR_EXECUTABLE_DIR] = application_path_for_env

# Establecer DJANGO_SETTINGS_MODULE si no está ya establecido.
# Es mejor si tu script start.py principal lo hace ANTES de importar Django.
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'myproject.settings'

# print(f"--- pyi_runtimehook.py: DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')} ---")
# print(f"--- pyi_runtimehook.py: {ENV_VAR_FOR_EXECUTABLE_DIR}: {os.environ.get(ENV_VAR_FOR_EXECUTABLE_DIR)} ---")
# print(f"--- pyi_runtimehook.py: CWD actual: {os.getcwd()} ---")
# print("--- pyi_runtimehook.py: FIN ---")
