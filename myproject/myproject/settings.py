# MPC/myproject/myproject/settings.py
import environ
import os
import sys
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ImproperlyConfigured
import logging

# --- Configuración Inicial de Logging (muy básico, antes de que se cargue la config completa de Django) ---
# Esto ayuda a ver los prints y logs iniciales del settings.py
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - SETTINGS - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Logger específico para settings

logger.info("Iniciando la carga de settings.py...")

# --- Determinación de Rutas Base ---
SOURCE_CODE_BASE_DIR = Path(__file__).resolve().parent.parent
logger.info(
    f"SOURCE_CODE_BASE_DIR (raíz del código fuente): {SOURCE_CODE_BASE_DIR}")

IS_FROZEN = getattr(sys, 'frozen', False)
BUNDLE_DIR = None  # Directorio raíz del bundle de PyInstaller (ej: _MEIPASS)
# Directorio donde reside el .exe (útil para onedir o datos externos)
APP_EXECUTABLE_DIR = None

if IS_FROZEN:
    logger.info("La aplicación está CONGELADA (ejecutable PyInstaller).")
    if hasattr(sys, '_MEIPASS'):
        BUNDLE_DIR = Path(sys._MEIPASS)
        logger.info(
            f"  BUNDLE_DIR (sys._MEIPASS, para archivos internos del bundle): {BUNDLE_DIR}")
    else:
        # Esto es menos común para PyInstaller onefile, pero puede ocurrir.
        # Para onedir, sys.executable.parent es el directorio de la app.
        BUNDLE_DIR = Path(sys.executable).parent
        logger.info(
            f"  BUNDLE_DIR (sys.executable.parent, podría ser onedir o fallback): {BUNDLE_DIR}")

    APP_EXECUTABLE_DIR = Path(sys.executable).parent
    logger.info(
        f"  APP_EXECUTABLE_DIR (directorio del .exe): {APP_EXECUTABLE_DIR}")
else:
    logger.info(
        "La aplicación NO está congelada (ejecutando desde código fuente).")
    # En desarrollo, BUNDLE_DIR no es relevante de la misma manera.
    # APP_EXECUTABLE_DIR podría ser el directorio del script python, pero menos usado.

# --- Directorio para Datos de Aplicación Persistentes (logs, cache, media, db si es sqlite) ---
# Debe ser escribible y persistente.
APP_DATA_DIR_BASE = None
SMGP_APP_EXECUTABLE_DIR_ENV = os.environ.get('SMGP_APP_EXECUTABLE_DIR')

if SMGP_APP_EXECUTABLE_DIR_ENV:
    logger.info(
        f"Usando SMGP_APP_EXECUTABLE_DIR_ENV para APP_DATA_DIR_BASE: {SMGP_APP_EXECUTABLE_DIR_ENV}")
    candidate_path = Path(SMGP_APP_EXECUTABLE_DIR_ENV)
    try:
        # Intentar crear/asegurar
        candidate_path.mkdir(parents=True, exist_ok=True)
        APP_DATA_DIR_BASE = candidate_path
        logger.info(
            f"  APP_DATA_DIR_BASE establecido a (desde var env): {APP_DATA_DIR_BASE}")
    except Exception as e:
        logger.error(
            f"  No se pudo usar/crear SMGP_APP_EXECUTABLE_DIR ({candidate_path}): {e}. Se usará fallback.")
        APP_DATA_DIR_BASE = None  # Forzar fallback si hay error

# Prioridad 2: Lógica para modo congelado si APP_DATA_DIR_BASE aún no está definido
if not APP_DATA_DIR_BASE and IS_FROZEN:
    logger.info(
        "SMGP_APP_EXECUTABLE_DIR_ENV no definido o inválido. Determinando APP_DATA_DIR_BASE para modo CONGELADO.")
    if APP_EXECUTABLE_DIR and BUNDLE_DIR == APP_EXECUTABLE_DIR:  # Probablemente un build --onedir
        APP_DATA_DIR_BASE = APP_EXECUTABLE_DIR / "app_data_smgp"
        logger.info(
            f"  Modo congelado (--onedir probable), usando APP_DATA_DIR_BASE: {APP_DATA_DIR_BASE}")
    else:  # Probablemente --onefile, usar appdirs o fallback
        logger.info(
            "  Modo congelado (--onefile probable). Intentando usar appdirs...")
        try:
            from appdirs import user_data_dir
            APP_DATA_DIR_BASE = Path(user_data_dir(
                appname="SMGP_App", appauthor="TuEmpresa"))
            logger.info(f"    appdirs user_data_dir: {APP_DATA_DIR_BASE}")
        except ImportError:
            logger.warning(
                "    Módulo 'appdirs' no encontrado. Usando fallback simple para APP_DATA_DIR_BASE.")
            if sys.platform == "win32":
                APP_DATA_DIR_BASE = Path(
                    os.getenv('APPDATA', Path.home() / 'AppData/Roaming')) / "SMGP_App"
            elif sys.platform == "darwin":
                APP_DATA_DIR_BASE = Path.home() / "Library/Application Support/SMGP_App"
            else:  # Linux y otros
                APP_DATA_DIR_BASE = Path.home() / ".local/share/SMGP_App"
            logger.info(f"    Fallback APP_DATA_DIR_BASE: {APP_DATA_DIR_BASE}")

# Prioridad 3: Lógica para modo desarrollo si APP_DATA_DIR_BASE aún no está definido
if not APP_DATA_DIR_BASE and not IS_FROZEN:
    logger.info("Determinando APP_DATA_DIR_BASE para modo DESARROLLO.")
    APP_DATA_DIR_BASE = SOURCE_CODE_BASE_DIR / "local_app_data_smgp"
    logger.info(
        f"  Modo desarrollo, usando APP_DATA_DIR_BASE: {APP_DATA_DIR_BASE}")

# Asegurar que APP_DATA_DIR_BASE tenga un valor final y crear el directorio
if not APP_DATA_DIR_BASE:
    # Esto no debería ocurrir si la lógica anterior es completa, pero como salvaguarda:
    logger.error(
        "CRÍTICO: APP_DATA_DIR_BASE no pudo ser determinado. Usando un directorio temporal inseguro.")
    import tempfile
    APP_DATA_DIR_BASE = Path(tempfile.gettempdir()) / "SMGP_App_Fallback_Error"

try:
    APP_DATA_DIR_BASE.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Directorio base final para datos de aplicación asegurado/creado: {APP_DATA_DIR_BASE}")
except Exception as e:
    logger.error(
        f"CRÍTICO: No se pudo crear APP_DATA_DIR_BASE en {APP_DATA_DIR_BASE}: {e}")
    # Considera lanzar una excepción aquí si este directorio es absolutamente esencial para el arranque.
    # raise ImproperlyConfigured(f"No se pudo crear el directorio de datos de la aplicación: {APP_DATA_DIR_BASE}")

# --- Configuración de `environ` ---
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['127.0.0.1', 'localhost',]),
    # Default a SQLite en APP_DATA_DIR_BASE para dev si no hay .env
    DATABASE_URL=(str, f'sqlite:///{APP_DATA_DIR_BASE / "dev_db.sqlite3"}'),
    SESSION_COOKIE_AGE=(int, 86400),  # 24 horas
    DATA_UPLOAD_MAX_NUMBER_FIELDS=(int, 5000),
    SECRET_KEY=(str, ''),  # Debe estar en .env para producción
    SMGP_LICENSE_VERIFY_KEY_B64=(
        str, '48FUC+B/1sYVGhvmnRQuXKWwKqcIsg1cE49xF5VRxIY='),  # Default, mejor en .env
    DJANGO_SUPERUSER_USERNAME=(str, 'admin'),
    DJANGO_SUPERUSER_EMAIL=(str, 'admin@example.com'),
    DJANGO_SUPERUSER_PASSWORD=(str, None),  # Mejor generar o pedir si es None
    DJANGO_SUPERUSER_PRIMER_NOMBRE=(str, 'Admin'),
    DJANGO_SUPERUSER_PRIMER_APELLIDO=(str, 'User'),
    # MEDIA_ROOT se definirá más abajo usando APP_DATA_DIR_BASE
    # LOG_DIR_RELATIVE_TO_APP_ROOT y CACHE_DIR_RELATIVE_TO_APP_ROOT ya no son necesarios con la nueva lógica de APP_DATA_DIR_BASE
    SECURE_SSL_REDIRECT=(bool, False),
    SECURE_HSTS_SECONDS=(int, 0),
    SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, False),
    SECURE_HSTS_PRELOAD=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
    DB_CONN_MAX_AGE=(int, 600),
    # Default a None, para que solo se use si está en .env
    DB_CONNECT_TIMEOUT=(int, None),
    CACHE_DEFAULT_TIMEOUT=(int, 300),  # 5 minutos
    CACHE_DEFAULT_MAX_ENTRIES=(int, 500),
)

# --- Carga de archivo .env ---
# Buscar .env junto al ejecutable (si está congelado y es onedir) o en la raíz del código fuente (desarrollo)
env_file_paths_to_check = []
if IS_FROZEN and APP_EXECUTABLE_DIR:
    env_file_paths_to_check.append(APP_EXECUTABLE_DIR / '.env')
if APP_DATA_DIR_BASE:
    env_file_paths_to_check.append(APP_DATA_DIR_BASE / '.env')
env_file_paths_to_check.append(
    SOURCE_CODE_BASE_DIR / '.env')  # Para desarrollo

ENV_FILE_PATH_LOADED = None
for p in env_file_paths_to_check:
    if p.is_file():
        logger.info(f"Cargando variables de entorno desde: {p}")
        environ.Env.read_env(env_file=str(p))
        ENV_FILE_PATH_LOADED = p
        break
if not ENV_FILE_PATH_LOADED:
    logger.warning(
        f"Archivo .env NO encontrado en las ubicaciones buscadas: {env_file_paths_to_check}. Se usarán valores por defecto o variables de entorno del sistema.")

# --- Variables Críticas y de Configuración ---
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

if not SECRET_KEY and not DEBUG:
    raise ImproperlyConfigured(
        "CRITICAL ERROR! SECRET_KEY no definida y DEBUG es False.")
elif not SECRET_KEY and DEBUG:
    logger.warning(
        "ADVERTENCIA: SECRET_KEY no definida en modo DEBUG. Usando clave insegura solo para desarrollo.")
    SECRET_KEY = 'django_insecure_debug_only_fallback_key_for_smgp_project_12345!@#$%'

# Inicialización explícita para el analizador estático del IDE (opcional)
# Lee del .env o usa el default de environ.Env()
_allowed_hosts_from_env = env.list('ALLOWED_HOSTS')

# ----- NUEVO LOGGING AQUÍ -----
logger.info(
    f"SETTINGS: ALLOWED_HOSTS (después de env.list): {_allowed_hosts_from_env} (Tipo: {type(_allowed_hosts_from_env)})")
# -----------------------------

# Asignar a la variable final que Django usará
ALLOWED_HOSTS = _allowed_hosts_from_env

if DEBUG and not ALLOWED_HOSTS:
    # Esta condición sigue siendo probablemente redundante
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
    logger.info(
        f"SETTINGS: DEBUG=True y ALLOWED_HOSTS estaba vacío, re-estableciendo a: {ALLOWED_HOSTS}")

# ----- OTRO LOGGING AQUÍ (VALOR FINAL) -----
logger.info(f"SETTINGS: Valor FINAL de ALLOWED_HOSTS: {ALLOWED_HOSTS}")
# ------------------------------------------


# --- Aplicaciones Instaladas ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',  # Requerido para la gestión de estáticos
    'django.contrib.humanize',

    # Terceros
    'django_filters',
    'django_select2',
    'rangefilter',
    'sequences',
    'pgtrigger',
    'widget_tweaks',
    # Para que WhiteNoise sirva estáticos con el servidor de desarrollo si DEBUG=True
    'whitenoise.runserver_nostatic',

    # Tu aplicación
    'myapp.apps.MyappConfig',
]

# --- Middleware ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # Para traducciones
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # X-Frame-Options

    # Middlewares personalizados (asegúrate que el orden sea correcto)
    'myapp.middleware.AuditoriaMiddleware',
    # Revisa si esto es necesario o si compite con el de Django
    'myapp.middleware.CustomSessionMiddleware',
    'myapp.middleware.LicenseCheckMiddleware',
    # 'myapp.middleware.DatabaseConnectionMiddleware', # Comentado en tu .spec, ¿lo necesitas?
    # 'myapp.middleware.ErrorLoggingMiddleware', # Comentado en tu .spec, ¿lo necesitas?
]

ROOT_URLCONF = 'myproject.urls'

# --- Plantillas ---
TEMPLATES_DIR_MAIN = SOURCE_CODE_BASE_DIR / 'templates'
TEMPLATES_DIRS_LIST = [TEMPLATES_DIR_MAIN] if TEMPLATES_DIR_MAIN.is_dir() else [
]
if not TEMPLATES_DIRS_LIST:
    logger.warning(
        f"Directorio de plantillas globales NO encontrado en {TEMPLATES_DIR_MAIN}")

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': TEMPLATES_DIRS_LIST,
    'APP_DIRS': True,  # Busca plantillas dentro de las apps
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'myapp.context_processors.system_notifications',  # Tu context processor
        ],
        'builtins': [
            'myapp.templatetags.querystring_tags',
            'myapp.templatetags.comision_tags',
        ],
    },
}]

WSGI_APPLICATION = 'myproject.wsgi.application'  # O ASGI si usas Channels/ASGI

# --- Base de Datos ---
DATABASES = {'default': env.db_url_config(env('DATABASE_URL'))}
DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE')
DATABASES['default'].setdefault('OPTIONS', {})  # Asegurar que OPTIONS exista

db_engine_name = DATABASES['default'].get('ENGINE', '')
if 'sqlite' in db_engine_name:
    db_path = Path(DATABASES['default']['NAME'])
    if not db_path.parent.exists():
        logger.info(
            f"El directorio para la base de datos SQLite ({db_path.parent}) no existe. Creándolo...")
        db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Usando base de datos SQLite en: {db_path}")

db_connect_timeout_val = env.int('DB_CONNECT_TIMEOUT', default=None)
if db_connect_timeout_val is not None:
    if 'postgres' in db_engine_name or 'postgis' in db_engine_name:
        DATABASES['default']['OPTIONS']['connect_timeout'] = db_connect_timeout_val
        logger.info(
            f"Configurando connect_timeout para PostgreSQL: {db_connect_timeout_val}s")
    else:
        logger.warning(
            f"DB_CONNECT_TIMEOUT ({db_connect_timeout_val}s) definido, pero el motor '{db_engine_name}' podría no soportarlo. Omitiendo.")

logger.info(
    f"Configuración final de BD: Motor='{db_engine_name}', Nombre='{DATABASES['default'].get('NAME')}', Opciones='{DATABASES['default'].get('OPTIONS')}'")

# --- Autenticación y Autorización ---
AUTH_USER_MODEL = 'myapp.Usuario'
AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
# Asegúrate que 'myapp' sea el namespace de tu app y 'login' el name de la URL
LOGIN_URL = 'myapp:login'
# O la URL a la que quieres redirigir tras login exitoso
LOGIN_REDIRECT_URL = 'myapp:home'
LOGOUT_REDIRECT_URL = 'myapp:login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Internacionalización y Localización ---
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Caracas'
USE_I18N = True
USE_L10N = True  # Para formatos localizados de números y fechas
USE_TZ = True
LANGUAGES = [('es', _('Español')), ('en', _('Inglés'))]

LOCALE_PATHS_DIR = SOURCE_CODE_BASE_DIR / 'locale'
LOCALE_PATHS = [LOCALE_PATHS_DIR] if LOCALE_PATHS_DIR.is_dir() else []
if not LOCALE_PATHS:
    logger.warning(
        f"Directorio LOCALE_PATHS no encontrado en {LOCALE_PATHS_DIR}")

# --- Archivos Estáticos (CSS, JavaScript, Imágenes de la UI) ---
STATIC_URL = '/static/'

if IS_FROZEN and BUNDLE_DIR:
    STATIC_ROOT = BUNDLE_DIR / 'static'
    STATICFILES_DIRS = []  # Correcto para modo congelado
    logger.info(
        f"MODO CONGELADO: STATIC_ROOT (para WhiteNoise) = {STATIC_ROOT}")
else:
    # MODO DESARROLLO
    # Para cuando ejecutes collectstatic
    STATIC_ROOT = SOURCE_CODE_BASE_DIR / 'staticfiles_collected_for_pyinstaller'

    # MODIFICADO: Deja que AppDirectoriesFinder maneje los estáticos de 'myapp'
    # Si tienes OTRAS carpetas de estáticos a nivel de proyecto (fuera de cualquier app),
    # añádelas aquí. Si no, puede ser una lista vacía.
    STATICFILES_DIRS = [
        # Ejemplo: SOURCE_CODE_BASE_DIR / 'global_project_statics',
    ]
    if not STATICFILES_DIRS:
        logger.info(
            "MODO DESARROLLO: STATICFILES_DIRS está vacío. Se usarán los directorios 'static/' de las apps.")
    else:
        logger.info(f"MODO DESARROLLO: STATICFILES_DIRS = {STATICFILES_DIRS}")

    logger.info(
        f"MODO DESARROLLO: STATIC_ROOT (para collectstatic) = {STATIC_ROOT}")

# WhiteNoise Storage (recomendado para compresión y cacheo eficiente)
# Si DEBUG=False, WhiteNoise servirá desde STATIC_ROOT después de collectstatic.
# Si DEBUG=True y 'whitenoise.runserver_nostatic' en INSTALLED_APPS,
# WhiteNoise intentará servir estáticos de forma similar a como lo hace Django en desarrollo
# (usando STATICFILES_DIRS y los directorios 'static/' de las apps).
STATICFILES_STORAGE = 'whitenoise.storage.MissingFileErrorStorage'
# --- Archivos de Medios (Subidos por el usuario) ---
MEDIA_URL = '/media/'
# MEDIA_ROOT debe ser una ruta absoluta a una carpeta escribible y persistente.
MEDIA_ROOT = APP_DATA_DIR_BASE / 'media_user_uploads'
try:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info(f"MEDIA_ROOT (archivos subidos por usuario) = {MEDIA_ROOT}")
except Exception as e:
    logger.error(f"No se pudo crear MEDIA_ROOT en {MEDIA_ROOT}: {e}")


# --- Caché ---
CACHE_DIR_BASE_PATH = APP_DATA_DIR_BASE / 'django_cache'
try:
    CACHE_DIR_BASE_PATH.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Directorio base para caché de archivos = {CACHE_DIR_BASE_PATH}")
except Exception as e:
    logger.error(
        f"No se pudo crear CACHE_DIR_BASE_PATH en {CACHE_DIR_BASE_PATH}: {e}")

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(CACHE_DIR_BASE_PATH / 'default_cache'),
        'TIMEOUT': env.int('CACHE_DEFAULT_TIMEOUT'),
        'OPTIONS': {'MAX_ENTRIES': env.int('CACHE_DEFAULT_MAX_ENTRIES')}
    },
    'graphs': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(CACHE_DIR_BASE_PATH / 'graphs_cache'),
        'TIMEOUT': 3600,  # 1 hora
        'OPTIONS': {'MAX_ENTRIES': 100}
    },
    'license': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(CACHE_DIR_BASE_PATH / 'license_cache_smgp_v2'),
        'TIMEOUT': None,  # Cachear indefinidamente hasta que se invalide
        'OPTIONS': {'MAX_ENTRIES': 10}
    }
}

# --- Logging de Django ---
LOG_DIR_BASE_PATH = APP_DATA_DIR_BASE / 'logs'
try:
    LOG_DIR_BASE_PATH.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio base para archivos de log = {LOG_DIR_BASE_PATH}")
except Exception as e:
    logger.error(
        f"No se pudo crear LOG_DIR_BASE_PATH en {LOG_DIR_BASE_PATH}: {e}")

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'},
        'simple': {'format': '%(levelname)s %(asctime)s [%(name)s] %(message)s'},
        'settings_formatter': {'format': '%(asctime)s - SETTINGS - %(levelname)s - %(message)s'},
    },
    'handlers': {
        'console': {'level': 'DEBUG' if DEBUG else 'INFO', 'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'file_debug': {'level': 'DEBUG', 'class': 'logging.handlers.RotatingFileHandler',
                       'filename': LOG_DIR_BASE_PATH / 'app_debug.log',
                       'maxBytes': 1024 * 1024 * 5, 'backupCount': 3, 'formatter': 'verbose'},  # 5MB
        'file_info': {'level': 'INFO', 'class': 'logging.handlers.RotatingFileHandler',
                      'filename': LOG_DIR_BASE_PATH / 'app_info.log',
                      'maxBytes': 1024 * 1024 * 5, 'backupCount': 3, 'formatter': 'simple'},
        'settings_log_file': {'level': 'INFO', 'class': 'logging.handlers.RotatingFileHandler',
                              'filename': LOG_DIR_BASE_PATH / 'settings_config.log',
                              'maxBytes': 1024 * 1024 * 1, 'backupCount': 1, 'formatter': 'settings_formatter'},
    },
    'loggers': {
        'django': {'handlers': ['console', 'file_info'], 'level': 'INFO', 'propagate': False},
        'django.db.backends': {'handlers': ['console', 'file_debug'] if DEBUG else ['file_info'],
                               'level': 'DEBUG' if DEBUG else 'WARNING', 'propagate': False},
        'myapp': {'handlers': ['console', 'file_debug', 'file_info'],
                  'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False},
        'myapp.licensing': {'handlers': ['console', 'file_info'], 'level': 'INFO', 'propagate': False},
        'sequences': {'handlers': ['console', 'file_info'], 'level': 'INFO', 'propagate': False},
        'waitress': {'handlers': ['console', 'file_info'], 'level': 'INFO', 'propagate': False},
        # Para logs de django-environ
        'environ': {'handlers': ['console', 'settings_log_file'], 'level': 'INFO', 'propagate': False},
        # Para logs de este archivo settings.py
        __name__: {'handlers': ['console', 'settings_log_file'], 'level': 'INFO', 'propagate': False},
    },
    # Captura todo lo demás
    'root': {'handlers': ['console', 'file_info'], 'level': 'WARNING'},
}


# --- Otros Ajustes ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# O 'backends.cache' si prefieres
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE')
# Considera si esto es necesario, puede tener impacto en rendimiento
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SITE_NAME = "Sistema SMGP"
SUPPORT_EMAIL = "soporte@smgp.com"  # Cambia esto
DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int('DATA_UPLOAD_MAX_NUMBER_FIELDS')

# --- Seguridad ---
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'  # Buena práctica
SECURE_CONTENT_TYPE_NOSNIFF = True  # Buena práctica

# Estas configuraciones dependen de si usas HTTPS
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT')
# Ej: 31536000 (1 año) si siempre usas HTTPS
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS')
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS')
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD')
SESSION_COOKIE_SECURE = env.bool(
    'SESSION_COOKIE_SECURE')  # True si siempre HTTPS
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE')     # True si siempre HTTPS
# 'Strict' es más seguro pero puede romper algunos flujos
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# --- Configuración Específica de la Aplicación ---
DJANGO_SUPERUSER_USERNAME = env('DJANGO_SUPERUSER_USERNAME')
DJANGO_SUPERUSER_EMAIL = env('DJANGO_SUPERUSER_EMAIL')
DJANGO_SUPERUSER_PASSWORD = env('DJANGO_SUPERUSER_PASSWORD')  # Puede ser None
DJANGO_SUPERUSER_PRIMER_NOMBRE = env('DJANGO_SUPERUSER_PRIMER_NOMBRE')
DJANGO_SUPERUSER_PRIMER_APELLIDO = env('DJANGO_SUPERUSER_PRIMER_APELLIDO')

if not DJANGO_SUPERUSER_PASSWORD:
    if DEBUG:
        logger.info(
            "DJANGO_SUPERUSER_PASSWORD no definido en .env. El comando 'ensure_superuser' podría usar un default o generarla.")
    else:
        logger.warning("PRODUCCIÓN: DJANGO_SUPERUSER_PASSWORD no definido en .env. El comando 'ensure_superuser' podría no crear/actualizar el superusuario si la contraseña es requerida y no se provee.")

LICENSE_EXEMPT_URL_NAMES = [
    'myapp:login', 'myapp:logout', 'myapp:license_invalid', 'myapp:activate_license',
    'admin:index', 'admin:login', 'admin:logout', 'admin:password_change', 'admin:password_change_done',
    # ... (asegúrate que estas URLs existan y sean correctas)
    'admin:myapp_licenseinfo_changelist', 'admin:myapp_licenseinfo_add',
    'admin:myapp_licenseinfo_change', 'admin:myapp_licenseinfo_delete',
    'admin:myapp_licenseinfo_history', 'admin:myapp_licenseinfo_view',
]
SMGP_LICENSE_VERIFY_KEY_B64 = env('SMGP_LICENSE_VERIFY_KEY_B64')


logger.info("settings.py cargado completamente.")
