import environ
import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Inicializar django-environ
env = environ.Env(
    DEBUG=(bool, False),  # El default es False si no se encuentra en .env
    ALLOWED_HOSTS=(list, ['127.0.0.1', 'localhost']
                   ),  # Default para ALLOWED_HOSTS
    DB_PORT=(int, 5432),  # Default para DB_PORT
    SESSION_COOKIE_AGE=(int, 86400),
    DATA_UPLOAD_MAX_NUMBER_FIELDS=(int, 5000),
)

# Leer archivo .env
# Asume .env en la raíz del proyecto (junto a manage.py)
ENV_FILE_PATH = BASE_DIR / '.env'  # <--- CORRECCIÓN AQUÍ

if ENV_FILE_PATH.exists():
    environ.Env.read_env(str(ENV_FILE_PATH))  # read_env espera un string
    print(f".env file loaded from: {ENV_FILE_PATH}")
else:
    print(
        f"WARNING: .env file not found at {ENV_FILE_PATH}. Using system environment variables or defaults.")


# --- Seguridad ---
SECRET_KEY = env('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "CRITICAL ERROR! SECRET_KEY environment variable is not set.")

# Se toma el default (False) si no está en .env o es inválido
DEBUG = env('DEBUG')

# Usa el default definido en Env() si no está en .env
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# --- Aplicaciones ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 'import_export',
    'django.contrib.humanize',
    'django_filters',
    'django_select2',
    'rangefilter',
    'sequences',
    'pgtrigger',
    'widget_tweaks',
    'myapp.apps.MyappConfig',
]

# --- Middleware ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Generalmente después de Security y antes de Session
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'myapp.middleware.AuditoriaMiddleware',
    'myapp.middleware.CustomSessionMiddleware',
    'myapp.middleware.LicenseCheckMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'myapp.context_processors.system_notifications',

            ],
            'builtins': [
                'myapp.templatetags.querystring_tags',
                'myapp.templatetags.comision_tags',
            ],
        },
    },
]

LICENSE_EXEMPT_URL_NAMES = [
    'myapp:login',
    'myapp:logout',
    'myapp:license_invalid',
    'myapp:activate_license',
    'admin:index',  # Para que el admin base sea accesible
    'admin:login',
    'admin:logout',
    'admin:password_change',
    'admin:password_change_done',
    'admin:myapp_licenseinfo_changelist',
    'admin:myapp_licenseinfo_add',  # Aunque no deberías añadir, solo cambiar
    'admin:myapp_licenseinfo_change',
]

LOGIN_REDIRECT_URL = '/home/'

SMGP_LICENSE_VERIFY_KEY_B64 = '48FUC+B/1sYVGhvmnRQuXKWwKqcIsg1cE49xF5VRxIY='
if not SMGP_LICENSE_VERIFY_KEY_B64:

    print("WARNING: SMGP_LICENSE_VERIFY_KEY_B64 no está definida en el entorno. La verificación de licencias podría fallar.")

WSGI_APPLICATION = 'myproject.wsgi.application'

# --- Base de Datos ---
# django-environ puede construir la URL de la base de datos o usar campos individuales
DATABASES = {
    'default': env.db_url_config(env('DATABASE_URL', default=f"postgres://{env('DB_USER', default='user')}:{env('DB_PASSWORD', default='pass')}@{env('DB_HOST', default='localhost')}:{env('DB_PORT')}/{env('DB_NAME', default='dbname')}"))
}
# Si DATABASE_URL no está en .env, usará las variables individuales DB_USER, DB_PASSWORD, etc.
# Asegúrate que DB_NAME, DB_USER, DB_PASSWORD estén definidas en .env si no usas DATABASE_URL
if not DATABASES['default']['NAME'] or DATABASES['default']['NAME'] == 'dbname':  # Chequeo básico
    if not (env('DB_NAME', default=None) and env('DB_USER', default=None) and env('DB_PASSWORD', default=None)):
        print("WARNING: DB_NAME, DB_USER, or DB_PASSWORD not fully configured and DATABASE_URL not found. Django might fail to connect.")

DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=600)
DATABASES['default']['OPTIONS'] = {
    'connect_timeout': env.int('DB_CONNECT_TIMEOUT', default=5)}


# --- Autenticación ---
AUTH_USER_MODEL = 'myapp.Usuario'
AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
LOGIN_URL = 'myapp:login'
LOGOUT_REDIRECT_URL = 'myapp:login'

# --- Validación de Contraseñas ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Internacionalización ---
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Caracas'  # Asegúrate que esto sea lo que quieres
USE_I18N = True
LANGUAGES = [('es', _('Español')), ('en', _('Inglés'))]
LOCALE_PATHS = [BASE_DIR / 'locale']
USE_L10N = True  # Para formatos localizados
USE_TZ = True   # Habilitar soporte de zonas horarias

# --- Formatos de Fecha/Hora ---
DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y P'  # P es para 'a.m.'/'p.m.' en formato localizado
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'
TIME_FORMAT = 'P'
DATE_INPUT_FORMATS = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']

# --- Archivos Estáticos/Media ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'myapp/static']
# Para producción con WhiteNoise (descomentar si lo usas así):
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'mediafiles'))
Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)


# --- Cache ---
CACHE_DIR = BASE_DIR / 'django_cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(CACHE_DIR / 'default_cache'),
        'TIMEOUT': env.int('CACHE_DEFAULT_TIMEOUT', default=300),
        'OPTIONS': {'MAX_ENTRIES': env.int('CACHE_DEFAULT_MAX_ENTRIES', default=500)}
    },
    'graphs': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(CACHE_DIR / 'graphs_cache'),
        'TIMEOUT': 3600, 'OPTIONS': {'MAX_ENTRIES': 100}
    },
    'license': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(CACHE_DIR / 'license_cache_smgp_v2'),
        'TIMEOUT': None, 'OPTIONS': {'MAX_ENTRIES': 10}
    }
}

# --- Logging ---
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'},
        'simple': {'format': '%(levelname)s %(asctime)s [%(name)s] %(message)s'},
    },
    'handlers': {
        'console': {'level': 'DEBUG' if DEBUG else 'INFO', 'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'file': {'level': 'DEBUG', 'class': 'logging.FileHandler', 'filename': LOG_DIR / 'django_debug.log', 'formatter': 'verbose'},
    },
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'django.db.backends': {'handlers': ['console', 'file'], 'level': 'WARNING', 'propagate': False},
        'myapp': {'handlers': ['console', 'file'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False},
        'myapp.licensing': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'sequences': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
    },
    'root': {'handlers': ['console', 'file'], 'level': 'WARNING'},
}

# --- Configuraciones Adicionales ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE')  # Ya definido en Env()
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # O True si prefieres
# IMPORT_EXPORT_USE_TRANSACTIONS = True
# IMPORT_EXPORT_SKIP_ADMIN_LOG = False
SITE_NAME = "Sistema SMGP"  # Actualizado
SUPPORT_EMAIL = "soporte@smgp.com"  # Actualizado
DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int(
    'DATA_UPLOAD_MAX_NUMBER_FIELDS')  # Ya definido

# --- Seguridad Producción (Configuración por defecto para local/despliegue simple) ---
# Para un despliegue en producción real, querrías habilitar más de estas
# y configurarlas adecuadamente con un proxy inverso (Nginx/Apache).
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# --- Variables para el superusuario (leídas desde .env) ---
# Estas se pueden usar en migraciones de datos o comandos de gestión.
# El comando `createsuperuser --noinput` las leerá directamente del entorno del sistema operativo.
DJANGO_SUPERUSER_USERNAME = env('DJANGO_SUPERUSER_USERNAME', default='admin')
DJANGO_SUPERUSER_EMAIL = env(
    'DJANGO_SUPERUSER_EMAIL', default='admin@example.com')
# No hay un password por defecto seguro
DJANGO_SUPERUSER_PASSWORD = env('DJANGO_SUPERUSER_PASSWORD', default=None)
DJANGO_SUPERUSER_PRIMER_NOMBRE = env(
    'DJANGO_SUPERUSER_PRIMER_NOMBRE', default='')
DJANGO_SUPERUSER_PRIMER_APELLIDO = env(
    'DJANGO_SUPERUSER_PRIMER_APELLIDO', default='')

# Verificar que el password del superusuario esté en .env si se piensa usar para creación automática
if not DJANGO_SUPERUSER_PASSWORD and not DEBUG:  # En producción, es crucial
    print("WARNING: DJANGO_SUPERUSER_PASSWORD no está definido en .env. La creación automática de superusuario podría fallar o usar un default inseguro.")
elif not DJANGO_SUPERUSER_PASSWORD and DEBUG:
    print("INFO: DJANGO_SUPERUSER_PASSWORD no está definido en .env. Si usas 'createsuperuser --noinput', se te pedirá.")
