# myapp/context_processors.py

import logging
from django.conf import settings
from datetime import timedelta, datetime
from django.db.models import Sum
from django.utils import timezone
from django.core.cache import cache
from django.urls import reverse, NoReverseMatch

# Importar modelos directamente para evitar problemas de carga de apps
from .models import (
    ContratoIndividual, AfiliadoIndividual, ContratoColectivo, AfiliadoColectivo,
    # Asegúrate que todos estos se usen
    Reclamacion, Pago, AuditoriaSistema, Usuario, Notificacion
)

logger = logging.getLogger(__name__)


def get_now():
    return timezone.now() if settings.USE_TZ else datetime.now()


def safe_reverse(viewname, args=None, kwargs=None, current_app=None):
    try:
        return reverse(viewname, args=args, kwargs=kwargs, current_app=current_app)
    except NoReverseMatch:
        logger.warning(
            f"NoReverseMatch for viewname '{viewname}' with args={args}, kwargs={kwargs}")
        return '#'


def global_data(request):
    now = get_now()
    current_year = now.year
    site_name = getattr(settings, 'SITE_NAME', 'Sistema de Gestión')
    support_email = getattr(settings, 'SUPPORT_EMAIL', 'soporte@example.com')

    data = {
        'site_name': site_name,
        'support_email': support_email,
        'current_year': current_year,
        'total_contratos_individuales': 'N/A',
        'total_afiliados_individuales': 'N/A',
        'total_contratos_colectivos': 'N/A',
        'reclamaciones_abiertas': 'N/A',
        'ingresos_mensuales': 'N/A',
        'auditorias_recientes': [],
    }

    try:
        data['total_contratos_individuales'] = ContratoIndividual.objects.count()
    except Exception as e:
        logger.error(f"Error contando ContratoIndividual en global_data: {e}")

    try:
        data['total_afiliados_individuales'] = AfiliadoIndividual.objects.count()
    except Exception as e:
        logger.error(f"Error contando AfiliadoIndividual en global_data: {e}")

    try:
        data['total_contratos_colectivos'] = ContratoColectivo.objects.count()
    except Exception as e:
        logger.error(f"Error contando ContratoColectivo en global_data: {e}")

    try:
        data['reclamaciones_abiertas'] = Reclamacion.objects.filter(
            estado='ABIERTA').count()
    except Exception as e:
        logger.error(
            f"Error contando Reclamaciones abiertas en global_data: {e}")

    try:
        mes_actual = now.month
        data['ingresos_mensuales'] = Pago.objects.filter(
            fecha_pago__month=mes_actual, fecha_pago__year=now.year
        ).aggregate(total=Sum('monto_pago'))['total'] or 0
    except Exception as e:
        logger.error(
            f"Error calculando ingresos mensuales en global_data: {e}")

    # try: # Comentado si AuditoriaSistema ya no se usa o causa problemas aquí
    #     data['auditorias_recientes'] = AuditoriaSistema.objects.order_by(
    #         '-tiempo_inicio')[:5]
    # except Exception as e:
    #     logger.error(
    #         f"Error obteniendo auditorías recientes en global_data: {e}")

    return data


def user_permissions(request):
    user_perms = {}
    # ELIMINADO 'view_exportacion': 'can_export' de aquí
    permissions_to_check = {
        'view_contratoindividual': 'can_view_contratos', 'add_contratoindividual': 'can_add_contratos',
        'change_contratoindividual': 'can_change_contratos', 'delete_contratoindividual': 'can_delete_contratos',
        'view_reclamacion': 'can_view_reclamaciones', 'add_reclamacion': 'can_add_reclamaciones',
        'change_reclamacion': 'can_change_reclamaciones', 'delete_reclamacion': 'can_delete_reclamaciones',
        'view_contratocolectivo': 'can_view_contratos_colectivos', 'add_contratocolectivo': 'can_add_contratos_colectivos',
        'change_contratocolectivo': 'can_change_contratos_colectivos', 'delete_contratocolectivo': 'can_delete_contratos_colectivos',
        'view_auditoriasistema': 'can_view_auditoria',
        'view_afiliadoindividual': 'can_view_afiliados_ind', 'add_afiliadoindividual': 'can_add_afiliados_ind',
        'view_afiliadocolectivo': 'can_view_afiliados_col', 'add_afiliadocolectivo': 'can_add_afiliados_col',
        'view_intermediario': 'can_view_intermediarios', 'add_intermediario': 'can_add_intermediarios',
        'view_factura': 'can_view_facturas', 'add_factura': 'can_add_facturas',
        'view_pago': 'can_view_pagos', 'add_pago': 'can_add_pagos',
        'view_tarifa': 'can_view_tarifas', 'add_tarifa': 'can_add_tarifas',
        'view_usuario': 'can_view_usuarios', 'add_usuario': 'can_add_usuarios',
        'change_usuario': 'can_change_usuarios', 'delete_usuario': 'can_delete_usuarios',
        # Añadido permiso para la licencia
        'change_licenseinfo': 'can_change_license'
    }

    if request.user.is_authenticated:
        user_perm_set = request.user.get_user_permissions(
        ) | request.user.get_group_permissions()
        for perm_code, context_key in permissions_to_check.items():
            full_perm_code = f'myapp.{perm_code}' if '.' not in perm_code else perm_code
            user_perms[context_key] = full_perm_code in user_perm_set
        user_perms['is_admin'] = request.user.is_superuser or request.user.is_staff
    else:
        for context_key in permissions_to_check.values():
            user_perms[context_key] = False
        user_perms['is_admin'] = False

    return {'user_perms': user_perms}


def dashboard_metrics(request):
    cache_key = 'dashboard_metrics_cache'
    metrics = cache.get(cache_key)

    if metrics is None:
        metrics = {'total_contratos_activos': 'N/A', 'total_contratos_colectivos_activos': 'N/A',
                   'total_reclamaciones_abiertas': 'N/A', 'total_pagos_mes_actual': 'N/A', 'total_ingresos_mes_actual': 'N/A'}
        now = get_now()
        current_month = now.month
        current_year = now.year
        try:
            metrics['total_contratos_activos'] = ContratoIndividual.objects.filter(
                estatus='VIGENTE').count()
        except Exception as e:
            logger.error(f"Error métrica cont_ind_activos: {e}")
        try:
            metrics['total_contratos_colectivos_activos'] = ContratoColectivo.objects.filter(
                estatus='VIGENTE').count()
        except Exception as e:
            logger.error(f"Error métrica cont_col_activos: {e}")
        try:
            metrics['total_reclamaciones_abiertas'] = Reclamacion.objects.filter(
                estado='ABIERTA').count()
        except Exception as e:
            logger.error(f"Error métrica recl_abiertas: {e}")
        try:
            pagos_mes = Pago.objects.filter(
                fecha_pago__year=current_year, fecha_pago__month=current_month)
            metrics['total_pagos_mes_actual'] = pagos_mes.count()
            metrics['total_ingresos_mes_actual'] = pagos_mes.aggregate(
                total=Sum('monto_pago'))['total'] or 0
        except Exception as e:
            logger.error(f"Error métrica pagos/ingresos mes: {e}")
        cache.set(cache_key, metrics, 300)

    return {'dashboard_metrics': metrics}


# Esta función parece específica de user_dashboard_data
def obtener_notificaciones_usuario(user):
    notifications = []
    if not user or not user.is_authenticated:  # Añadida verificación
        return notifications
    try:
        dias_limite = 10
        fecha_limite = get_now().date() - timedelta(days=dias_limite)
        reclamaciones_asignadas = Reclamacion.objects.filter(
            usuario_asignado=user, estado='ABIERTA', fecha_reclamo__lte=fecha_limite).count()
        if reclamaciones_asignadas > 0:
            url = safe_reverse('myapp:reclamacion_list') + \
                f'?usuario_asignado={user.pk}&estado=ABIERTA'  # Cuidado con exponer Pk así
            notifications.append({'message': f"Tienes {reclamaciones_asignadas} reclamaciones asignadas abiertas por más de {dias_limite} días.",
                                 'type': 'danger', 'icon': 'fas fa-user-clock', 'url': url})
    except Exception as e:
        logger.error(
            f"Error obteniendo notificaciones de reclamaciones para usuario {user.pk}: {e}")
    return notifications


# Este context processor podría fusionarse con el siguiente o el de notificaciones
def user_dashboard_data(request):
    context = {}
    if request.user.is_authenticated:
        # Renombrado para evitar colisión con el 'usuario' de Notificacion
        context['usuario_actual'] = request.user
        context['notificaciones_dashboard_usuario'] = obtener_notificaciones_usuario(
            request.user)
    else:
        context['usuario_actual'] = None
        context['notificaciones_dashboard_usuario'] = []
    return context


# Esta es la función que se usa en tu base.html para el menú de notificaciones
def system_notifications(request):
    logger.info(
        f"--- EJECUTANDO system_notifications PARA USUARIO: {request.user.username if request.user.is_authenticated else 'Anónimo'} ---")
    notifications_list = []
    notifications_count_val = 0
    if request.user.is_authenticated:
        try:
            unread_qs = Notificacion.objects.filter(
                usuario=request.user, leida=False)
            notifications_count_val = unread_qs.count()
            # Convertir a lista para logging
            notifications_list = list(
                unread_qs.order_by('-fecha_creacion')[:10])
            logger.info(
                f"    Usuario: {request.user.email}, Count: {notifications_count_val}, Lista IDs (últimos 10): {[n.id for n in notifications_list]}")
        except Exception as e:
            logger.error(
                f"Error obteniendo notificaciones para {request.user.pk}: {e}", exc_info=True)
    return {'notifications': notifications_list, 'notifications_count': notifications_count_val}


logger_cp = logging.getLogger(__name__ + ".context_processor")


# Renombrar función para claridad
def unread_notifications_for_topbar(request):
    logger_cp.info(
        f"--- CONTEXT PROCESSOR: unread_notifications_for_topbar ---")
    if request.user.is_authenticated:
        logger_cp.info(
            f"    Usuario autenticado para notificaciones topbar: {request.user.email}")
        try:
            # Obtener todas las no leídas para el conteo
            unread_qs = Notificacion.objects.filter(
                usuario=request.user, leida=False)
            count_val = unread_qs.count()

            # Obtener las últimas N (ej. 5 o 10) para el dropdown
            list_val = list(unread_qs.order_by(
                '-fecha_creacion')[:5])  # O :10 si prefieres

            logger_cp.info(
                f"    Notificaciones no leídas (topbar) encontradas para {request.user.email}: {count_val}")
            # for n_idx, n_obj in enumerate(list_val):
            #    logger_cp.debug(f"        Notif (topbar) {n_idx+1}: '{n_obj.mensaje[:30]}...' (PK: {n_obj.pk})")

            return {
                'notifications_count': count_val,       # <--- Nombre esperado por base.html
                'notifications': list_val             # <--- Nombre esperado por base.html
            }
        except Exception as e:
            logger_cp.error(
                f"    Error DENTRO del context processor (topbar) para {request.user.email}: {e}", exc_info=True)
            return {'notifications_count': 0, 'notifications': []}
    else:
        logger_cp.info(
            f"    Usuario NO autenticado para notificaciones topbar.")
        return {'notifications_count': 0, 'notifications': []}
