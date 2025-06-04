# myproject/wsgi.py
import os
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise         # <--- Importar WhiteNoise
from django.conf import settings        # <--- Importar settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

_original_application = get_wsgi_application()

print("--- wsgi.py: Envolviendo aplicación WSGI con WhiteNoise explícitamente ---")
# WhiteNoise usará settings.STATIC_ROOT y settings.STATIC_URL
application = WhiteNoise(_original_application)

if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
    static_root_path_str = str(settings.STATIC_ROOT)
    prefix = settings.STATIC_URL
    if not prefix.endswith('/'):
        prefix += '/'
    print(
        f"--- wsgi.py: WhiteNoise debería servir desde (settings.STATIC_ROOT): {static_root_path_str} con prefijo {prefix} ---")
    # Nota: La inicialización WhiteNoise(_original_application) ya debería hacer esto.
    # La línea application.add_files(...) es generalmente para casos más complejos o sin middleware.
    # Si después de esta prueba sigue sin funcionar, podríamos probar a DESCOMENTAR:
    # print(f"--- wsgi.py: Intentando application.add_files('{static_root_path_str}', prefix='{prefix}') ---")
    # application.add_files(static_root_path_str, prefix=prefix)
else:
    print("--- wsgi.py: ADVERTENCIA - settings.STATIC_ROOT no está definido o está vacío en settings.")

print("--- wsgi.py: Aplicación envuelta y configurada con WhiteNoise. ---")
