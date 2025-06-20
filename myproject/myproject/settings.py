# myproject/settings.py
import os
import sys
from pathlib import Path
import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

# --- LÓGICA DE RUTAS UNIFICADA Y ROBUSTA ---
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    # MODO CONGELADO (.exe)
    # BASE_DIR apunta a la carpeta _internal, donde están los recursos de solo lectura (templates, static).
    BASE_DIR = Path(sys._MEIPASS)
    # WRITABLE_DIR apunta a una carpeta junto al .exe para datos de usuario (media, logs, cache, db).
    WRITABLE_DIR = Path(sys.executable).parent / "app_data_smgp"
else:
    # MODO DESARROLLO (python manage.py runserver)
    # BASE_DIR es la raíz del proyecto.
    BASE_DIR = Path(__file__).resolve().parent.parent
    # WRITABLE_DIR es una carpeta local para datos de desarrollo.
    WRITABLE_DIR = BASE_DIR / "local_app_data_smgp"

# Aseguramos que el directorio de datos escribibles exista.
WRITABLE_DIR.mkdir(parents=True, exist_ok=True)


# --- CARGA DE VARIABLES DE ENTORNO ---
# El hook o start.py ya se encargan de crear el .env si no existe.
# Aquí solo lo leemos.
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['127.0.0.1', 'localhost']),
    DATABASE_URL=(str, f'sqlite:///{WRITABLE_DIR / "dev_db.sqlite3"}'),
    SESSION_COOKIE_AGE=(int, 86400),
    DATA_UPLOAD_MAX_NUMBER_FIELDS=(int, 5000),
    SECRET_KEY=(str, ''),
    SMGP_LICENSE_VERIFY_KEY_B64=(
        str, '48FUC+B/1sYVGhvmnRQuXKWwKqcIsg1cE49xF5VRxIY='),
    DJANGO_SUPERUSER_USERNAME=(str, 'admin'),
    DJANGO_SUPERUSER_EMAIL=(str, 'admin@example.com'),
    DJANGO_SUPERUSER_PASSWORD=(str, None),
    DJANGO_SUPERUSER_PRIMER_NOMBRE=(str, 'Admin'),
    DJANGO_SUPERUSER_PRIMER_APELLIDO=(str, 'User'),
    SECURE_SSL_REDIRECT=(bool, False),
    SECURE_HSTS_SECONDS=(int, 0),
    SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, False),
    SECURE_HSTS_PRELOAD=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
    DB_CONN_MAX_AGE=(int, 600),
    DB_CONNECT_TIMEOUT=(int, None),
    CACHE_DEFAULT_TIMEOUT=(int, 300),
    CACHE_DEFAULT_MAX_ENTRIES=(int, 500),
)

# El .env se lee desde junto al .exe (congelado) o desde la raíz del proyecto (desarrollo).
env_file_path = Path(sys.executable).parent / \
    '.env' if IS_FROZEN else BASE_DIR / '.env'
if env_file_path.is_file():
    environ.Env.read_env(env_file=str(env_file_path))


# --- VARIABLES DE CONFIGURACIÓN CRÍTICAS ---
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

if not SECRET_KEY and not DEBUG:
    raise ImproperlyConfigured(
        "CRITICAL ERROR! SECRET_KEY no definida y DEBUG es False.")
elif not SECRET_KEY and DEBUG:
    SECRET_KEY = 'django_insecure_debug_only_fallback_key_for_smgp_project_12345!@#$%'


# --- APLICACIONES Y MIDDLEWARE ---
INSTALLED_APPS = [
    # 1. Apps nativas de Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # 2. Apps de terceros
    'django_filters',
    'django_select2',
    'rangefilter',
    'sequences',
    'pgtrigger',
    'widget_tweaks',
    'background_task',

    # 3. Mi aplicación siempre al final
    'myapp.apps.MyappConfig'
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'myapp.middleware.AuditoriaMiddleware',
    'myapp.middleware.CustomSessionMiddleware',
    'myapp.middleware.LicenseCheckMiddleware',
]

ROOT_URLCONF = 'myproject.urls'
WSGI_APPLICATION = 'myproject.wsgi.application'


# --- PLANTILLAS ---
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': [
                  'django.template.context_processors.debug',
                  'django.template.context_processors.request',
                  'django.template.context_processors.request',

                  'django.contrib.auth.context_processors.auth',
                  'django.contrib.messages.context_processors.messages',
                  'myapp.context_processors.system_notifications',
              ], 'builtins': [
                  'myapp.templatetags.querystring_tags',
                  'myapp.templatetags.comision_tags',
              ]}}]


# --- BASE DE DATOS ---
DATABASES = {'default': env.db_url_config(env('DATABASE_URL'))}
DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE')
if env.int('DB_CONNECT_TIMEOUT', default=None) is not None:
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['connect_timeout'] = env.int(
        'DB_CONNECT_TIMEOUT')


# --- AUTENTICACIÓN ---
AUTH_USER_MODEL = 'myapp.Usuario'
LOGIN_URL = 'myapp:login'
LOGIN_REDIRECT_URL = 'myapp:home'
LOGOUT_REDIRECT_URL = 'myapp:login'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- INTERNACIONALIZACIÓN ---
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Caracas'
USE_I18N = True
USE_TZ = True
LANGUAGES = [('es', _('Español')), ('en', _('Inglés'))]
LOCALE_PATHS = [BASE_DIR / 'locale']


# --- ARCHIVOS ESTÁTICOS Y DE MEDIOS ---
STATIC_URL = '/static/'
# En modo congelado, los estáticos están DENTRO del bundle. En desarrollo, collectstatic los junta aquí.
STATIC_ROOT = BASE_DIR / 'static' if IS_FROZEN else BASE_DIR / \
    'staticfiles_collected_for_pyinstaller'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
# Los archivos de medios siempre van a la carpeta escribible.
MEDIA_ROOT = WRITABLE_DIR / 'media_user_uploads'
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


# --- LOGS Y CACHÉ ---
LOG_DIR = WRITABLE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = WRITABLE_DIR / 'django_cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': str(CACHE_DIR / 'default_cache'),
                'TIMEOUT': env.int('CACHE_DEFAULT_TIMEOUT'),
                'OPTIONS': {'MAX_ENTRIES': env.int('CACHE_DEFAULT_MAX_ENTRIES')}},
    'graphs': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
               'LOCATION': str(CACHE_DIR / 'graphs_cache'), 'TIMEOUT': 3600,
               'OPTIONS': {'MAX_ENTRIES': 100}},
    'license': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': str(CACHE_DIR / 'license_cache_smgp_v2'), 'TIMEOUT': None,
                'OPTIONS': {'MAX_ENTRIES': 10}}
}

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '%(levelname)s %(asctime)s [%(name)s] %(message)s'}},
    'handlers': {
        'console': {'level': 'DEBUG', 'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'file_info': {'level': 'INFO', 'class': 'logging.handlers.RotatingFileHandler',
                      'filename': LOG_DIR / 'app_info.log',
                      'maxBytes': 1024 * 1024 * 5, 'backupCount': 3, 'formatter': 'simple'},
    },
    'loggers': {
        'django': {'handlers': ['console', 'file_info'], 'level': 'INFO', 'propagate': False},
        'myapp': {'handlers': ['console', 'file_info'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False},
    },
    'root': {'handlers': ['console', 'file_info'], 'level': 'WARNING'},
}


# --- OTRAS CONFIGURACIONES ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE')
DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int('DATA_UPLOAD_MAX_NUMBER_FIELDS')

# --- SEGURIDAD ---
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT')
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS')
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS')
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD')
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE')
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE')
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# --- CONFIGURACIÓN ESPECÍFICA DE LA APLICACIÓN ---
DJANGO_SUPERUSER_USERNAME = env('DJANGO_SUPERUSER_USERNAME')
DJANGO_SUPERUSER_EMAIL = env('DJANGO_SUPERUSER_EMAIL')
DJANGO_SUPERUSER_PASSWORD = env('DJANGO_SUPERUSER_PASSWORD')
DJANGO_SUPERUSER_PRIMER_NOMBRE = env('DJANGO_SUPERUSER_PRIMER_NOMBRE')
DJANGO_SUPERUSER_PRIMER_APELLIDO = env('DJANGO_SUPERUSER_PRIMER_APELLIDO')

LICENSE_EXEMPT_URL_NAMES = [
    'myapp:login', 'myapp:logout', 'myapp:license_invalid', 'myapp:activate_license',
    'admin:index', 'admin:login', 'admin:logout', 'admin:password_change', 'admin:password_change_done',
    'admin:myapp_licenseinfo_changelist', 'admin:myapp_licenseinfo_add',
    'admin:myapp_licenseinfo_change', 'admin:myapp_licenseinfo_delete',
    'admin:myapp_licenseinfo_history', 'admin:myapp_licenseinfo_view',
]
SMGP_LICENSE_VERIFY_KEY_B64 = env('SMGP_LICENSE_VERIFY_KEY_B64')
