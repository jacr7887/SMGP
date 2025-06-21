from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from myapp import views
from .views import CalcularMontoContratoAPI, ReclamacionStatusAPIView, IntermediarioDashboardView
from django.views.generic import TemplateView  # Importa TemplateView

app_name = 'myapp'

urlpatterns = [
    # Vistas de autenticación
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    # Vistas de gráficos
    path('graficas/', views.mi_vista_con_todos_los_graficos, name='graficas'),


    # Vistas de búsqueda
    path('busqueda/', views.BusquedaAvanzadaView.as_view(), name='busqueda'),

    # Vistas de Home
    path('', views.DynamicHomeView.as_view(), name='home'),
    path('home/', views.DynamicHomeView.as_view(), name='home'),

    # Vistas de Auditoría de Sistema
    path('auditoria_sistema/', views.AuditoriaSistemaListView.as_view(),
         name='auditoria_sistema_list'),
    path('auditoria_sistema/<int:pk>/',
         views.AuditoriaSistemaDetailView.as_view(), name='auditoria_sistema_detail'),
    path('auditoria_sistema/crear/', views.AuditoriaSistemaCreateView.as_view(),
         name='auditoria_sistema_create'),
    path('auditoria_sistema/editar/<int:pk>/',
         views.AuditoriaSistemaUpdateView.as_view(), name='auditoria_sistema_update'),
    path('auditoria_sistema/eliminar/<int:pk>/',
         views.AuditoriaSistemaDeleteView.as_view(), name='auditoria_sistema_delete'),

    # Vistas de Afiliado Individual
    path('afiliados_individuales/', views.AfiliadoIndividualListView.as_view(),
         name='afiliado_individual_list'),
    path('afiliados_individuales/<int:pk>/',
         views.AfiliadoIndividualDetailView.as_view(), name='afiliado_individual_detail'),
    path('afiliados_individuales/crear/',
         views.AfiliadoIndividualCreateView.as_view(), name='afiliado_individual_create'),
    path('afiliados_individuales/editar/<int:pk>/',
         views.AfiliadoIndividualUpdateView.as_view(), name='afiliado_individual_update'),
    path('afiliados_individuales/eliminar/<int:pk>/',
         views.AfiliadoIndividualDeleteView.as_view(), name='afiliado_individual_delete'),

    # Vistas de Afiliado Colectivo
    path('afiliados_colectivos/', views.AfiliadoColectivoListView.as_view(),
         name='afiliado_colectivo_list'),
    path('afiliados_colectivos/<int:pk>/',
         views.AfiliadoColectivoDetailView.as_view(), name='afiliado_colectivo_detail'),
    path('afiliados_colectivos/crear/', views.AfiliadoColectivoCreateView.as_view(),
         name='afiliado_colectivo_create'),
    path('afiliados_colectivos/editar/<int:pk>/',
         views.AfiliadoColectivoUpdateView.as_view(), name='afiliado_colectivo_update'),
    path('afiliados_colectivos/eliminar/<int:pk>/',
         views.AfiliadoColectivoDeleteView.as_view(), name='afiliado_colectivo_delete'),

    # Vistas de Contrato Individual
    path('contratos_individuales/', views.ContratoIndividualListView.as_view(),
         name='contrato_individual_list'),
    path('contratos_individuales/<int:pk>/',
         views.ContratoIndividualDetailView.as_view(), name='contrato_individual_detail'),
    path('contratos_individuales/crear/',
         views.ContratoIndividualCreateView.as_view(), name='contrato_individual_create'),
    path('contratos_individuales/editar/<int:pk>/',
         views.ContratoIndividualUpdateView.as_view(), name='contrato_individual_update'),
    path('contratos_individuales/eliminar/<int:pk>/',
         views.ContratoIndividualDeleteView.as_view(), name='contrato_individual_delete'),

    # Vistas de Contrato Colectivo
    path('contratos_colectivos/', views.ContratoColectivoListView.as_view(),
         name='contrato_colectivo_list'),
    path('contratos_colectivos/<int:pk>/',
         views.ContratoColectivoDetailView.as_view(), name='contrato_colectivo_detail'),
    path('contratos_colectivos/crear/', views.ContratoColectivoCreateView.as_view(),
         name='contrato_colectivo_create'),
    path('contratos_colectivos/editar/<int:pk>/',
         views.ContratoColectivoUpdateView.as_view(), name='contrato_colectivo_update'),
    path('contratos_colectivos/eliminar/<int:pk>/',
         views.ContratoColectivoDeleteView.as_view(), name='contrato_colectivo_delete'),

    # Vistas de Intermediario
    path('intermediarios/', views.IntermediarioListView.as_view(),
         name='intermediario_list'),
    path('intermediarios/<int:pk>/',
         views.IntermediarioDetailView.as_view(), name='intermediario_detail'),
    path('intermediarios/crear/', views.IntermediarioCreateView.as_view(),
         name='intermediario_create'),
    path('intermediarios/editar/<int:pk>/',
         views.IntermediarioUpdateView.as_view(), name='intermediario_update'),
    path('intermediarios/eliminar/<int:pk>/',
         views.IntermediarioDeleteView.as_view(), name='intermediario_delete'),
    path('intermediario/dashboard/', IntermediarioDashboardView.as_view(),
         name='intermediario_dashboard'),

    # Vistas de Reclamación
    path('reclamaciones/', views.ReclamacionListView.as_view(),
         name='reclamacion_list'),
    path('reclamaciones/<int:pk>/', views.ReclamacionDetailView.as_view(),
         name='reclamacion_detail'),
    path('reclamaciones/crear/', views.ReclamacionCreateView.as_view(),
         name='reclamacion_create'),
    path('reclamaciones/editar/<int:pk>/',
         views.ReclamacionUpdateView.as_view(), name='reclamacion_update'),
    path('reclamaciones/eliminar/<int:pk>/',
         views.ReclamacionDeleteView.as_view(), name='reclamacion_delete'),
    path('api/reclamacion/<int:pk>/status/',
         ReclamacionStatusAPIView.as_view(), name='api_reclamacion_status'),

    # Vistas de Pago
    path('pagos/', views.PagoListView.as_view(), name='pago_list'),
    path('pagos/<int:pk>/', views.PagoDetailView.as_view(), name='pago_detail'),
    path('pagos/crear/', views.PagoCreateView.as_view(), name='pago_create'),
    path('pagos/editar/<int:pk>/',
         views.PagoUpdateView.as_view(), name='pago_update'),
    path('pagos/eliminar/<int:pk>/',
         views.PagoDeleteView.as_view(), name='pago_delete'),

    # Vistas de Tarifa
    path('tarifas/', views.TarifaListView.as_view(), name='tarifa_list'),
    path('tarifas/<int:pk>/', views.TarifaDetailView.as_view(), name='tarifa_detail'),
    path('tarifas/crear/', views.TarifaCreateView.as_view(), name='tarifa_create'),
    path('tarifas/editar/<int:pk>/',
         views.TarifaUpdateView.as_view(), name='tarifa_update'),
    path('tarifas/eliminar/<int:pk>/',
         views.TarifaDeleteView.as_view(), name='tarifa_delete'),

    # Vistas de Usuario
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/<int:pk>/', views.UsuarioDetailView.as_view(),
         name='usuario_detail'),
    path('usuarios/crear/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/editar/<int:pk>/',
         views.UsuarioUpdateView.as_view(), name='usuario_update'),
    path('usuarios/eliminar/<int:pk>/',
         views.UsuarioDeleteView.as_view(), name='usuario_delete'),

    # Vistas de Factura
    path('facturas/', views.FacturaListView.as_view(), name='factura_list'),
    path('facturas/<int:pk>/', views.FacturaDetailView.as_view(),
         name='factura_detail'),
    path('facturas/crear/', views.FacturaCreateView.as_view(), name='factura_create'),
    path('facturas/editar/<int:pk>/',
         views.FacturaUpdateView.as_view(), name='factura_update'),
    path('facturas/eliminar/<int:pk>/',
         views.FacturaDeleteView.as_view(), name='factura_delete'),

    path('facturas/crear/<str:tipo_contrato>/<int:contrato_id>/',
         views.FacturaCreateView.as_view(), name='factura_create_from_contrato'),
    path('ajax/get-contrato-monto-cuota/', views.get_contrato_monto_cuota_api_view,
         name='get_contrato_monto_cuota_api'),

    path('comisiones/', views.RegistroComisionListView.as_view(),
         name='registro_comision_list'),
    path('comisiones/<int:pk>/', views.RegistroComisionDetailView.as_view(),
         name='registro_comision_detail'),

    path('mis-comisiones/', views.MisComisionesListView.as_view(),
         name='mis_comisiones_list'),
    path('comisiones/liquidacion/', views.liquidacion_comisiones_view,
         name='liquidacion_comisiones'),

    path('comisiones/marcar-pagadas/', views.marcar_comisiones_pagadas_view,
         name='marcar_comisiones_pagadas'),

    path('comisiones/marcar-pagada-individual/<int:pk>/',
         views.marcar_comision_individual_pagada_view, name='marcar_comision_pagada_individual'),
    path('comisiones/marcar-pagada-ajax/',
         views.marcar_comision_pagada_ajax_view, name='marcar_comision_pagada_ajax'),
    path('reportes/', views.ReporteGeneralView.as_view(), name='reporte_general'),

    path('comisiones/historial/', views.HistorialLiquidacionesListView.as_view(),
         name='historial_liquidaciones_list'),


    path('busqueda_avanzada/', views.BusquedaAvanzadaView.as_view(),
         name='busqueda_avanzada'),

    path('buscar/get-campos/', views.get_campos_por_modelo,
         name='get_campos_por_modelo'),

    path('busqueda/', views.BusquedaAvanzadaView.as_view(), name='busqueda'),

    path('graficas_cached/', views.get_cached_graph, name='graficas_cached'),

    path('limpiar_cache_graficas/', views.clear_graph_cache,
         name='limpiar_cache_graficas'),

    path('grafica/<int:graph_id>/', views.get_cached_graph, name='grafica'),

    path('obtener_grafica/<str:graph_id>/',
         views.obtener_grafica, name='obtener_grafica'),

    path('facturas/<int:pk>/pdf/',
         views.FacturaPdfView.as_view(), name='factura_pdf'),

    path('pagos/<int:pk>/pdf/', views.PagoPdfView.as_view(), name='pago_pdf'),

    path('notificaciones/marcar-leida/',
         views.MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('licencia/', views.ActivateLicenseView.as_view(), name='activate_license'),
    path('licencia-invalida/',
         TemplateView.as_view(template_name='license_invalid.html'), name='license_invalid'),
    path('api/calcular-monto-contrato/', CalcularMontoContratoAPI.as_view(),
         name='api_calcular_monto_contrato'),


    path('error/', views.error_page, name='error_page'),



]
handler500 = 'myapp.views.handler500'
# Configuración de archivos estáticos en modo de desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
