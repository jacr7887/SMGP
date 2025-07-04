# myapp/urls.py

from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'myapp'

urlpatterns = [
    # Vistas de autenticación
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),

    # Vistas principales y de reportes
    path('', views.DynamicHomeView.as_view(), name='home'),
    path('reportes/', views.ReporteGeneralView.as_view(), name='reporte_general'),
    path('mi-dashboard/', views.IntermediarioDashboardView.as_view(),
         name='intermediario_dashboard'),

    # Vistas de Auditoría de Sistema
    path('auditoria/', views.AuditoriaSistemaListView.as_view(),
         name='auditoria_sistema_list'),
    path('auditoria/<int:pk>/', views.AuditoriaSistemaDetailView.as_view(),
         name='auditoria_sistema_detail'),

    # Vistas de Afiliado Individual
    path('afiliados/individuales/', views.AfiliadoIndividualListView.as_view(),
         name='afiliado_individual_list'),
    path('afiliados/individuales/<int:pk>/',
         views.AfiliadoIndividualDetailView.as_view(), name='afiliado_individual_detail'),
    path('afiliados/individuales/crear/',
         views.AfiliadoIndividualCreateView.as_view(), name='afiliado_individual_create'),
    path('afiliados/individuales/editar/<int:pk>/',
         views.AfiliadoIndividualUpdateView.as_view(), name='afiliado_individual_update'),
    path('afiliados/individuales/eliminar/<int:pk>/',
         views.AfiliadoIndividualDeleteView.as_view(), name='afiliado_individual_delete'),

    # Vistas de Afiliado Colectivo
    path('afiliados/colectivos/', views.AfiliadoColectivoListView.as_view(),
         name='afiliado_colectivo_list'),
    path('afiliados/colectivos/<int:pk>/',
         views.AfiliadoColectivoDetailView.as_view(), name='afiliado_colectivo_detail'),
    path('afiliados/colectivos/crear/', views.AfiliadoColectivoCreateView.as_view(),
         name='afiliado_colectivo_create'),
    path('afiliados/colectivos/editar/<int:pk>/',
         views.AfiliadoColectivoUpdateView.as_view(), name='afiliado_colectivo_update'),
    path('afiliados/colectivos/eliminar/<int:pk>/',
         views.AfiliadoColectivoDeleteView.as_view(), name='afiliado_colectivo_delete'),

    # Vistas de Contrato Individual
    path('contratos/individuales/', views.ContratoIndividualListView.as_view(),
         name='contrato_individual_list'),
    path('contratos/individuales/<int:pk>/',
         views.ContratoIndividualDetailView.as_view(), name='contrato_individual_detail'),
    path('contratos/individuales/crear/',
         views.ContratoIndividualCreateView.as_view(), name='contrato_individual_create'),
    path('contratos/individuales/editar/<int:pk>/',
         views.ContratoIndividualUpdateView.as_view(), name='contrato_individual_update'),
    path('contratos/individuales/eliminar/<int:pk>/',
         views.ContratoIndividualDeleteView.as_view(), name='contrato_individual_delete'),

    # Vistas de Contrato Colectivo
    path('contratos/colectivos/', views.ContratoColectivoListView.as_view(),
         name='contrato_colectivo_list'),
    path('contratos/colectivos/<int:pk>/',
         views.ContratoColectivoDetailView.as_view(), name='contrato_colectivo_detail'),
    path('contratos/colectivos/crear/', views.ContratoColectivoCreateView.as_view(),
         name='contrato_colectivo_create'),
    path('contratos/colectivos/editar/<int:pk>/',
         views.ContratoColectivoUpdateView.as_view(), name='contrato_colectivo_update'),
    path('contratos/colectivos/eliminar/<int:pk>/',
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

    # Vistas de Pago
    path('pagos/', views.PagoListView.as_view(), name='pago_list'),
    path('pagos/<int:pk>/', views.PagoDetailView.as_view(), name='pago_detail'),
    path('pagos/crear/', views.PagoCreateView.as_view(), name='pago_create'),
    path('pagos/editar/<int:pk>/',
         views.PagoUpdateView.as_view(), name='pago_update'),
    path('pagos/eliminar/<int:pk>/',
         views.PagoDeleteView.as_view(), name='pago_delete'),
    path('pagos/<int:pk>/pdf/', views.PagoPdfView.as_view(), name='pago_pdf'),

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
    path('facturas/<int:pk>/pdf/',
         views.FacturaPdfView.as_view(), name='factura_pdf'),

    # Vistas de Comisiones
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
    path('comisiones/historial/', views.HistorialLiquidacionesListView.as_view(),
         name='historial_liquidaciones_list'),

    # Vistas de Búsqueda y Licencia
    path('busqueda_avanzada/', views.BusquedaAvanzadaView.as_view(),
         name='busqueda_avanzada'),
    path('licencia/', views.ActivateLicenseView.as_view(), name='activate_license'),
    path('licencia-invalida/',
         TemplateView.as_view(template_name='license_invalid.html'), name='license_invalid'),

    # --- APIs ---
    path('api/reclamacion/<int:pk>/status/',
         views.ReclamacionStatusAPIView.as_view(), name='api_reclamacion_status'),
    path('api/obtener_grafica/<str:graph_id>/',
         views.obtener_grafica, name='obtener_grafica'),

    # Notificaciones
    path('notificaciones/marcar-leida/',
         views.MarkNotificationReadView.as_view(), name='mark_notification_read'),
]
