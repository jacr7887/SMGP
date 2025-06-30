# myproject/settings.py
import os
import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

# ==============================================================================
# --- FUNCIÓN AUXILIAR PARA REEMPLAZAR A DECOUPLE ---
# ==============================================================================


_sentinel = object()  # Objeto único para usar como centinela


def get_env_variable(var_name, default=_sentinel, cast=None):
    """
    Lee una variable de entorno. Si no existe, usa el valor por defecto.
    Si no hay valor por defecto, lanza un error.
    Permite convertir el tipo de dato (cast).
    """
    value = os.environ.get(var_name)

    if value is None:
        # La variable no está en el entorno. Verificamos si hay un default.
        if default is _sentinel:
            # No se proporcionó un default, es un error crítico.
            raise ImproperlyConfigured(
                f"La variable de entorno requerida '{var_name}' no está definida."
            )
        # Se proporcionó un default, lo usamos.
        value = default

    # Si el valor final es None (porque el default era None), lo devolvemos sin castear.
    if value is None:
        return None

    # Si se especifica una función de 'cast', se aplica.
    if cast:
        return cast(value)

    return value


# ==============================================================================
# --- 1. LÓGICA DE RUTAS (Tu lógica original, está perfecta) ---
# ==============================================================================
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    BASE_DIR = Path(sys._MEIPASS)
    WRITABLE_DIR = Path(sys.executable).parent / "app_data_smgp"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    WRITABLE_DIR = BASE_DIR / "local_app_data_smgp"

WRITABLE_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# --- 2. CONFIGURACIÓN DE SEGURIDAD Y CIFRADO ---
# ==============================================================================
SECRET_KEY = get_env_variable('SECRET_KEY')
DEBUG = get_env_variable('DEBUG', default='False',
                         cast=lambda v: v.lower() in ('true', '1', 't'))
ALLOWED_HOSTS = get_env_variable('ALLOWED_HOSTS', cast=lambda v: [
                                 s.strip() for s in v.split(',')])

# --- Configuración de Cifrado ---
MASTER_ENCRYPTION_KEY = get_env_variable('FERNET_KEY')
FERNET_KEYS = [MASTER_ENCRYPTION_KEY]
FIELD_ENCRYPTION_KEY = MASTER_ENCRYPTION_KEY
logger.critical(
    f"CLAVE DE CIFRADO MAESTRA CARGADA: ...{MASTER_ENCRYPTION_KEY[-6:]}")

# ==============================================================================
# --- 3. APLICACIONES Y MIDDLEWARE (Sin cambios) ---
# ==============================================================================
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_filters',
    'django_select2',
    'rangefilter',
    'sequences',
    'pgtrigger',
    'widget_tweaks',
    'background_task',
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

# ==============================================================================
# --- 4. PLANTILLAS, BASE DE DATOS Y AUTENTICACIÓN ---
# ==============================================================================
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': [
                  'django.template.context_processors.debug',
                  'django.template.context_processors.request',
                  'django.contrib.auth.context_processors.auth',
                  'django.contrib.messages.context_processors.messages',
                  'myapp.context_processors.system_notifications',
              ], 'builtins': [
                  'myapp.templatetags.querystring_tags',
                  'myapp.templatetags.comision_tags',
              ]}}]

# --- BASE DE DATOS ---
db_url_str = get_env_variable('DATABASE_URL')
db_url = urlparse(db_url_str)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_url.path[1:],
        'USER': db_url.username,
        'PASSWORD': db_url.password,
        'HOST': db_url.hostname,
        'PORT': db_url.port,
        'CONN_MAX_AGE': get_env_variable('DB_CONN_MAX_AGE', default=600, cast=int),
    }
}
db_connect_timeout = get_env_variable('DB_CONNECT_TIMEOUT', default=None)
if db_connect_timeout is not None:
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['connect_timeout'] = int(
        db_connect_timeout)

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

# settings.py

JAZZMIN_SETTINGS = {
    "site_title": "SMGP Admin",
    "site_header": "SMGP",
    "site_brand": "SMGP",
    "site_logo": "favicon-96x96.png",  # Ruta a tu logo en la carpeta static
    "login_logo": "favicon-96x96.png",
    "welcome_sign": "Bienvenido al Admin de SMGP",
    "copyright": "Sistema Mágico de Gestión de Pólizas",

    # Cambiar a True para habilitar el selector de temas en la UI
    "show_themes": False,

    # Por defecto, Jazzmin usa un tema claro. Lo forzaremos a un modo oscuro personalizado.
    # Usamos 'darkly' como base, pero lo sobreescribiremos todo.
    "theme": "darkly",

    # Para el modo oscuro, podemos usar un tema base y sobreescribirlo.
    "dark_mode_theme": None,  # Lo controlaremos con nuestro CSS personalizado.

    ###############
    # UI Tweaks   #
    ###############
    # Clases de Bootstrap para la fuente del sitio
    "site_brand_classes": "text-light",
    "site_header_classes": "text-light",
    "topmenu_classes": "navbar-dark",
    "sidebar_classes": "sidebar-dark-primary",
    "custom_css": "jazzmin_custom.css",
    "custom_js": "jazzmin_custom.js",

    # Mostrar el panel de modelos en la página de índice del admin
    "show_ui_builder": False,

    # Renderizar el sidebar a la izquierda
    "navigation_expanded": True,

    # Ocultar los modelos de apps no especificadas en "order"
    "hide_apps": [],

    # Ocultar modelos específicos
    "hide_models": [],

    # Orden de las apps en el menú
    # Reemplaza con tus apps
    "order_with_respect_to": ["auth", "SMGP"],

    # Iconos para apps y modelos (Font Awesome)
    # https://fontawesome.com/v5/search
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        # Añade aquí los iconos para tus modelos
        "tu_app.AfiliadoIndividual": "fas fa-user-tie",
        "tu_app.OtroModelo": "fas fa-cogs",
    },

    # Clases de texto para los botones
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },

    # Clases para los alerts
    "alert_classes": {
        "primary": "alert-primary",
        "secondary": "alert-secondary",
        "info": "alert-info",
        "warning": "alert-warning",
        "danger": "alert-danger",
        "success": "alert-success",
    },
}

JAZZMIN_UI_TWEAKS = {
    # === TRADUCCIÓN DE TU PALETA DE COLORES ===
    # Estos valores sobreescribirán los del tema "darkly"
    "theme": "darkly",
    "dark_mode_theme": None,  # Desactivamos el switcher, controlaremos todo nosotros
    "navbar": "navbar-dark",
    "sidebar": "sidebar-dark-primary",

    # Colores principales
    "brand_colour": "#0f1224",  # --bg-dark (para el fondo de la marca)
    "accent": "#5c77ff",       # --primary (rgb(92, 119, 255))

    # Colores del layout
    "main_bg": "#0f1224",      # --bg-dark
    "sidebar_bg": "rgba(16, 21, 36, 0.65)",  # --glass-bg
    "body_bg": "#0f1224",
    "footer_bg": "rgba(15, 18, 36, 0.8)",  # --bg-dark con un toque de glass

    # Colores de texto
    "text_colour": "#ffffff",  # --text-light
    "link_colour": "#87CEEB",  # --link-blue

    # Colores de los componentes
    "button_primary": "#5c77ff",  # --primary
    "button_success": "#28a745",  # --success
    "button_danger": "#dc3545",  # --danger
    "button_warning": "#ffc107",  # --warning
    "button_info": "#3498DB",    # --info

    # Clases y estilos
    "navbar_classes": "border-bottom",
    "no_navbar_border": False,
    "sidebar_classes": "sidebar-dark-primary",
    "sidebar_fixed": True,
    "footer_fixed": False,
    "actions_sticky_top": True,
    "actions_fixed": True,

    # Radios y bordes (tu CSS lo manejará mejor, pero podemos dar una base)
    "border_radius": "30px",  # --glass-border-radius
    "card_border_radius": "30",
    "button_border_radius": "25",
    "input_border_radius": "25",

    # Fuentes (se aplicará mejor con CSS personalizado)
    "font_family_sans_serif": '"Segoe UI", system-ui, sans-serif',
    "font_family_monospace": 'monospace',
    "font_size": "1.05rem",

    # Ocultar breadcrumbs si no los quieres
    "show_breadcrumbs": True,
}

# ==============================================================================
# --- 5. INTERNACIONALIZACIÓN, ARCHIVOS, LOGS Y CACHÉ ---
# ==============================================================================
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Caracas'
USE_I18N = True
USE_TZ = True
LANGUAGES = [('es', _('Español')), ('en', _('Inglés'))]
LOCALE_PATHS = [BASE_DIR / 'locale']

STATIC_URL = '/static/'
if IS_FROZEN:
    STATIC_ROOT = BASE_DIR / 'static'
    STATICFILES_DIRS = []
else:
    STATIC_ROOT = BASE_DIR / 'staticfiles_collected_for_pyinstaller'
    STATICFILES_DIRS = [BASE_DIR / 'myapp' / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
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
                'TIMEOUT': get_env_variable('CACHE_DEFAULT_TIMEOUT', default=300, cast=int),
                'OPTIONS': {'MAX_ENTRIES': get_env_variable('CACHE_DEFAULT_MAX_ENTRIES', default=500, cast=int)}},
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

# ==============================================================================
# --- 6. OTRAS CONFIGURACIONES DE DJANGO Y DE LA APLICACIÓN ---
# ==============================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_AGE = get_env_variable(
    'SESSION_COOKIE_AGE', default=86400, cast=int)
DATA_UPLOAD_MAX_NUMBER_FIELDS = get_env_variable(
    'DATA_UPLOAD_MAX_NUMBER_FIELDS', default=5000, cast=int)

# --- SEGURIDAD ---
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = get_env_variable(
    'SECURE_SSL_REDIRECT', default='False', cast=lambda v: v.lower() in ('true', '1', 't'))
SECURE_HSTS_SECONDS = get_env_variable(
    'SECURE_HSTS_SECONDS', default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_variable(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', default='False', cast=lambda v: v.lower() in ('true', '1', 't'))
SECURE_HSTS_PRELOAD = get_env_variable(
    'SECURE_HSTS_PRELOAD', default='False', cast=lambda v: v.lower() in ('true', '1', 't'))
SESSION_COOKIE_SECURE = get_env_variable(
    'SESSION_COOKIE_SECURE', default='False', cast=lambda v: v.lower() in ('true', '1', 't'))
CSRF_COOKIE_SECURE = get_env_variable(
    'CSRF_COOKIE_SECURE', default='False', cast=lambda v: v.lower() in ('true', '1', 't'))
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# --- CONFIGURACIÓN ESPECÍFICA DE LA APLICACIÓN ---
DJANGO_SUPERUSER_USERNAME = get_env_variable('DJANGO_SUPERUSER_USERNAME')
DJANGO_SUPERUSER_EMAIL = get_env_variable('DJANGO_SUPERUSER_EMAIL')
DJANGO_SUPERUSER_PASSWORD = get_env_variable('DJANGO_SUPERUSER_PASSWORD')
DJANGO_SUPERUSER_PRIMER_NOMBRE = get_env_variable(
    'DJANGO_SUPERUSER_PRIMER_NOMBRE')
DJANGO_SUPERUSER_PRIMER_APELLIDO = get_env_variable(
    'DJANGO_SUPERUSER_PRIMER_APELLIDO')

LICENSE_EXEMPT_URL_NAMES = [
    'myapp:login', 'myapp:logout', 'myapp:license_invalid', 'myapp:activate_license',
    'admin:index', 'admin:login', 'admin:logout', 'admin:password_change', 'admin:password_change_done',
    'admin:myapp_licenseinfo_changelist', 'admin:myapp_licenseinfo_add',
    'admin:myapp_licenseinfo_change', 'admin:myapp_licenseinfo_delete',
    'admin:myapp_licenseinfo_history', 'admin:myapp_licenseinfo_view',
]
SMGP_LICENSE_VERIFY_KEY_B64 = get_env_variable('SMGP_LICENSE_VERIFY_KEY_B64')
