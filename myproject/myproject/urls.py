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

# # --- 3. AÑADIR ESTE BLOQUE AL FINAL DEL ARCHIVO ---
# if settings.DEBUG:
#     # Esto le dice a Django que sirva los archivos de MEDIA_ROOT
#     # cuando DEBUG es True.
#     urlpatterns += static(settings.MEDIA_URL,
#                           document_root=settings.MEDIA_ROOT)
