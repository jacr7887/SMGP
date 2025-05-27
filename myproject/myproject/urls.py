from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from myapp import views  # Importación faltante

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('myapp.urls')),
    path('error/', views.error_page, name='error_page'),  # Ahora funciona
    path('select2/', include('django_select2.urls')),  # Añade esta línea


] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Personalización del admin
admin.site.site_header = 'SMGP - Administración'
admin.site.site_title = 'Panel de Control SMGP'
admin.site.index_title = 'Sistema Mágico de Gestión de Pólizas'

if settings.DEBUG:
    # Servir archivos de medios (subidos por usuarios) durante el desarrollo
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    # Opcional: Servir archivos estáticos (si no usas WhiteNoise o similar en DEBUG)
    # urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Definir handler500 (si no estaba ya)
handler500 = views.handler500
