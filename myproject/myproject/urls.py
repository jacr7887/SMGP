# myproject/urls.py (PARA EL CONTEXTO DEL .EXE CON DEBUG=False)
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from myapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('myapp.urls')),
    path('error/', views.error_page, name='error_page'),
    path('select2/', include('django_select2.urls')),
]

admin.site.site_header = 'SMGP - Administración'
admin.site.site_title = 'Panel de Control SMGP'
admin.site.index_title = 'Sistema Mágico de Gestión de Pólizas'

# Servir archivos de MEDIOS SIEMPRE (para el contexto del .exe)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# WhiteNoise debería manejar los estáticos desde STATIC_ROOT en el .exe,
# por lo que la siguiente línea para STATIC_URL usualmente no es necesaria.
# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
