
# views.py
from myapp.commons import CommonChoices  # Ajusta la ruta de importación
from .signals import calcular_y_registrar_comisiones
from myapp.models import ContratoIndividual, ContratoColectivo, Reclamacion, Intermediario, Pago, Factura
import collections  # Para defaultdict si se usa en ReporteGeneralView
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from datetime import date as py_date
from dateutil.relativedelta import relativedelta
from django.db.models import Count, Case, When, Q, IntegerField, Sum, Avg, Subquery, OuterRef, F, ExpressionWrapper, Value, DecimalField, Func
from django.db.models.functions import ExtractYear, TruncMonth  # TruncMonth añadido
from plotly.offline import plot
import plotly.express as px
from django.utils.http import url_has_allowed_host_and_scheme
import plotly.graph_objects as go
import pandas as pd
import hashlib
from datetime import date as py_date, datetime as py_datetime
from .commons import CommonChoices
from .models import Pago, Factura, Reclamacion, AuditoriaSistema
from xhtml2pdf import pisa
from django.db.models import Q
from django.http import HttpResponse, FileResponse
from django.shortcuts import get_object_or_404
from django.db.models.functions import Coalesce
from urllib.parse import urlencode
# <--- IMPORTANTE PARA DATETIMES AWARE
from django.utils import timezone as django_timezone
from django.db.models import Sum, Value, F, Case, When, ExpressionWrapper, DurationField, DecimalField, Count
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from .licensing import activate_or_update_license, get_license_info
from django.contrib.admin.views.decorators import staff_member_required
from .forms import LicenseActivationForm, LoginForm
from .models import Factura, AuditoriaSistema, Pago, Notificacion  # Añadido Notificacion
from django.views.decorators.csrf import csrf_protect  # Decorador csrf
from django.utils.decorators import method_decorator  # Para csrf_protect en clases
import chardet  # Recuerda: pip install chardet
from .models import AuditoriaSistema
from django.contrib import messages
# <--- IMPORTAR PAGINATOR
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse, NoReverseMatch  # Para redirección fallback
from django.db import transaction, IntegrityError
from django.apps import apps
from django.forms.models import model_to_dict
# Añadido ValidationError
from django.core.exceptions import PermissionDenied, ValidationError
# Solo LoginRequiredMixin aquí
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
# Cambiado a get_license_info
from .licensing import activate_or_update_license, get_license_info
import logging
import os
from functools import reduce
import operator
from django.db import models
from io import BytesIO
from .notifications import crear_notificacion  # <--- Importante
from django.conf import settings
# Para resolver static en link_callback
from django.contrib.staticfiles import finders
# Añadidos JsonResponse, HttpResponseRedirect
from django.http import HttpResponse, HttpResponseServerError, Http404, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect  # Añadido redirect
from django.template.loader import get_template
from django.views import View
from xhtml2pdf import pisa  # Biblioteca para conversión PDF
from decimal import Decimal, ROUND_HALF_UP  # Añadido Decimal, ROUND_HALF_UP
from django.db.models import Prefetch, Value, ExpressionWrapper, DurationField, Case, When, CharField, IntegerField  # Añadidos
from django.db.models.functions import Cast, Replace, Substr, Length, Coalesce, Trim, Lower
from django.contrib.auth.decorators import login_required, permission_required
from django_filters.views import FilterView
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import (Sum, Avg, Q, Count)
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import caches
# from django.shortcuts import redirect, render # Ya importados arriba
import sys
# import chardet # Ya importado arriba
from . import graficas
from django.urls import reverse_lazy, reverse
from myapp.commons import CommonChoices
from django.db.models.deletion import ProtectedError
# FieldError añadido
from django.core.exceptions import PermissionDenied, FieldDoesNotExist
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST
from datetime import datetime, date, timedelta

# Importaciones de terceros (solo las necesarias para gráficos)
import logging
import csv
import html
import pandas as pd  # Añadido pandas
import plotly.express as px  # Añadido plotly express
import plotly.graph_objects as go  # Añadido plotly graph objects
from plotly.offline import plot  # Añadido plot

# Importaciones locales
from myapp.models import (
    ContratoIndividual, AfiliadoIndividual, AfiliadoColectivo,
    ContratoColectivo, Reclamacion, Intermediario, Factura,
    # Añadidos Notificacion, LicenseInfo
    Pago, Tarifa, AuditoriaSistema, Usuario, Notificacion, LicenseInfo, RegistroComision
)
from myapp.forms import (
    ContratoIndividualForm, AfiliadoColectivoForm,
    FormularioCreacionUsuario, FormularioEdicionUsuario,
    IntermediarioForm, AfiliadoIndividualForm, ContratoIndividualForm,
    ContratoColectivoForm, ReclamacionForm, PagoForm, TarifaForm,
    FacturaForm, AuditoriaSistemaForm, LicenseActivationForm
)
from myapp.graficas import *

from django import forms  # Añadido forms


class IntermediarioDataMixin:
    """
    Filtra los datos para que un usuario solo vea la información
    relacionada con su intermediario.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        intermediario_usuario = user.intermediario
        if not intermediario_usuario:
            return queryset.none()

        modelo = queryset.model

        # =========================================================================
        # === LÓGICA DE FILTRADO CORREGIDA Y MEJORADA ===
        # =========================================================================

        if modelo == Pago:
            # Para el modelo Pago, filtramos a través de la factura o la reclamación
            return queryset.filter(
                Q(factura__intermediario=intermediario_usuario) |
                Q(factura__contrato_individual__intermediario=intermediario_usuario) |
                Q(factura__contrato_colectivo__intermediario=intermediario_usuario) |
                Q(reclamacion__contrato_individual__intermediario=intermediario_usuario) |
                Q(reclamacion__contrato_colectivo__intermediario=intermediario_usuario)
            ).distinct()

        elif hasattr(modelo, 'intermediario'):
            # Para modelos con relación directa (Contratos, Afiliados, etc.)
            return queryset.filter(intermediario=intermediario_usuario)

        elif modelo == Intermediario:
            # El intermediario solo se ve a sí mismo
            return queryset.filter(pk=intermediario_usuario.pk)

        # Si no hay una regla de filtrado clara, por seguridad no mostramos nada.
        return queryset.none()


# Configuración del logger
logger = logging.getLogger(__name__)


def handler403(request, exception=None):
    # Pasamos el request explícitamente al contexto para que los context processors funcionen.
    return render(request, '403.html', {'request': request}, status=403)


def handler404(request, exception=None):
    return render(request, '404.html', {'request': request}, status=404)


def handler500(request):
    # No necesitamos pasar la excepción, Django lo hace si DEBUG=True.
    # Lo crucial es pasar el objeto 'request'.
    return render(request, '500.html', {'request': request}, status=500)


# Constantes
ITEMS_PER_PAGE = 9
DEFAULT_ORDER = '-fecha_creacion'
CACHE_TTL = 3600  # 1 hora

# Clases auxiliares


# Definición de cache_graphs a nivel del módulo
cache_graphs = caches['graphs']

GRAPH_GENERATORS = {
    f"{i:02d}": getattr(graficas, f"grafico_{i:02d}")
    for i in range(1, 53)  # Ajusta el rango si tienes más/menos gráficos
    if hasattr(graficas, f"grafico_{i:02d}")
}


def get_all_graphs_cached(request, graph_ids, force_refresh=False):
    # Diccionario para almacenar el HTML final de cada gráfica
    cached_graphs_html_output = {}
    logger.debug(
        f"[get_all_graphs_cached] Iniciando para IDs: {graph_ids}, Refresh: {force_refresh}")

    for graph_id in graph_ids:
        cache_key = f"graph_{graph_id}"
        graph_html = None  # Inicializar

        if not force_refresh:
            try:
                graph_html = cache_graphs.get(cache_key)
                if graph_html:
                    logger.debug(
                        f"[get_all_graphs_cached] Cache HIT para graph_{graph_id}")
                else:
                    logger.debug(
                        f"[get_all_graphs_cached] Cache MISS para graph_{graph_id}")
            except Exception as cache_err:
                logger.error(
                    f"[get_all_graphs_cached] Error leyendo cache para {cache_key}: {cache_err}")
                graph_html = None  # Tratar como cache miss si hay error

        # Si no está en caché o se fuerza refresco
        if graph_html is None:
            generator_func = GRAPH_GENERATORS.get(graph_id)
            if generator_func:
                logger.debug(
                    f"[get_all_graphs_cached] Generando gráfica {graph_id}...")
                try:
                    # Llamar a la función generadora (con o sin request)
                    if generator_func.__code__.co_argcount > 0:
                        graph_html = generator_func(request)
                    else:
                        graph_html = generator_func()

                    # Validar que el resultado sea un string antes de cachear
                    if isinstance(graph_html, str) and graph_html.strip():
                        cache_graphs.set(cache_key, graph_html, CACHE_TTL)
                        logger.debug(
                            f"[get_all_graphs_cached] Gráfica {graph_id} generada y cacheada.")
                    else:
                        logger.warning(
                            f"[get_all_graphs_cached] Función generadora para {graph_id} no devolvió HTML válido. Tipo: {type(graph_html)}")
                        graph_html = mark_safe(
                            f"<div class='alert alert-warning'>Gráfica {graph_id}: Generador no devolvió HTML.</div>")

                except Exception as e:
                    # Error durante la generación de la gráfica específica
                    error_msg = f"Error generando gráfico {graph_id}: {html.escape(str(e))}"
                    graph_html = mark_safe(
                        f"<div class='alert alert-danger'>{error_msg}</div>")
                    logger.error(error_msg, exc_info=True, extra={
                                 'user': request.user.username if request.user.is_authenticated else 'anon'})
            else:
                # La función generadora no existe en GRAPH_GENERATORS
                graph_html = mark_safe(
                    f"<div class='alert alert-warning'>Gráfico {graph_id} no configurado.</div>")
                logger.warning(
                    f"[get_all_graphs_cached] Intento de acceso a gráfico no configurado: {graph_id}")

        # Añadir el HTML (o mensaje de error) al diccionario final
        cached_graphs_html_output[graph_id] = graph_html

    logger.debug(
        f"[get_all_graphs_cached] Finalizado. Devolviendo {len(cached_graphs_html_output)} elementos.")
    # Devolver siempre el diccionario, aunque esté vacío o contenga errores
    return cached_graphs_html_output


@require_GET
def obtener_grafica(request, graph_id):
    """
    Devuelve el HTML de una gráfica específica, utilizando el sistema de caché existente.
    """
    graphs = get_all_graphs_cached(request, [graph_id])
    graph_html = graphs.get(graph_id)
    if graph_html:
        return HttpResponse(graph_html)
    else:
        return HttpResponse("Gráfica no encontrada", status=404)


@login_required
@permission_required('myapp.view_graficas', raise_exception=True)
def mi_vista_con_todos_los_graficos(request):
    all_graph_ids = [f"{i:02d}" for i in range(1, 53)]
    graphs_html = get_all_graphs_cached(request, all_graph_ids)
    graficas_list = []
    for key, html_content in graphs_html.items():
        # Extraemos el ID de la gráfica de la clave del diccionario (ej: 'grafico_01_html' -> '01')
        graph_id = key.replace('grafico_', '').replace('_html', '')
        graficas_list.append({'id': graph_id, 'html': html_content})

    context = {'graficas': graficas_list}
    return render(request, 'home.html', context)


# Vista principal Home (Completamente Optimizada)


def error_page(request):
    """
    Vista para mostrar una página de error genérica.
    """
    context = {
        'message': 'Lo sentimos, ha ocurrido un error inesperado.'
    }
    return HttpResponseServerError(render(request, '500.html', context))


@method_decorator(csrf_protect, name='dispatch')
class CustomLoginView(LoginView):
    template_name = 'login.html'
    form_class = LoginForm

    def _get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

    def post(self, request, *args, **kwargs):
        print(f"\n--- DEBUG CustomLoginView.post INICIO ---")
        form = self.get_form()
        print(f"Formulario obtenido en post(): {type(form)}")
        print(f"Datos del formulario (form.data): {form.data}")
        form_is_valid_result = form.is_valid()
        print(
            f"Resultado de form.is_valid() en post(): {form_is_valid_result}")
        if not form_is_valid_result:
            print(
                f"Errores del formulario en post() (form.errors): {form.errors.as_json()}")
        if form_is_valid_result:
            print(
                f"DEBUG CustomLoginView.post: El formulario ES VÁLIDO. Llamando a self.form_valid().")
            return self.form_valid(form)
        else:
            print(
                f"DEBUG CustomLoginView.post: El formulario ES INVÁLIDO. Llamando a self.form_invalid().")
            return self.form_invalid(form)

    def form_valid(self, form):
        user_autenticado = form.get_user()
        if not user_autenticado:
            logger.error(
                "CustomLoginView.form_valid: form.get_user() devolvió None.")
            return self.form_invalid(form)
        try:
            AuditoriaSistema.objects.create(
                usuario=user_autenticado, tipo_accion='LOGIN', resultado_accion='EXITO',
                direccion_ip=self._get_client_ip(),
                agente_usuario=self.request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception as e:
            logger.error(
                f"Error al crear auditoría de LOGIN exitoso: {e}", exc_info=True)
        messages.success(self.request, "¡Inicio de sesión exitoso!")
        return super().form_valid(form)

    def form_invalid(self, form):
        email_intentado = form.data.get('username', 'desconocido@ejemplo.com')
        error_message_text = "Error desconocido en login."
        resultado_auditoria = 'FALLIDO_DESCONOCIDO'
        error_code_from_form = None
        if form.errors:
            non_field_errors = form.errors.get('__all__')
            if non_field_errors:
                error_message_text = non_field_errors[0]
                if "inactiva" in error_message_text.lower():
                    resultado_auditoria = 'FALLIDO_INACTIVO'
                elif "incorrectos" in error_message_text.lower():
                    resultado_auditoria = 'FALLIDO_CREDENCIALES'
        user_obj_auditoria = None
        if error_code_from_form == 'inactive' and hasattr(form, 'user_cache') and form.user_cache:
            user_obj_auditoria = form.user_cache
        elif email_intentado != 'desconocido@ejemplo.com':
            try:
                user_obj_auditoria = Usuario.objects.filter(
                    email=email_intentado).first()
            except Exception:
                user_obj_auditoria = None
        try:
            AuditoriaSistema.objects.create(
                usuario=user_obj_auditoria, tipo_accion='LOGIN_FALLIDO', resultado_accion=resultado_auditoria,
                detalle_accion=f"Intento de login para: {email_intentado}. Error: {error_message_text}",
                direccion_ip=self._get_client_ip(),
                agente_usuario=self.request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception as e:
            logger.error(
                f"Error al crear auditoría de LOGIN_FALLIDO: {e}", exc_info=True)
        return super().form_invalid(form)

    def get_success_url(self):
        """
        Redirige al usuario al dashboard apropiado después de iniciar sesión.
        """
        user = self.request.user

        if user.is_superuser:
            # Los superusuarios van al reporte general.
            return reverse_lazy('myapp:home')
        elif user.intermediario:
            # Los usuarios con un intermediario asociado van a su dashboard personal.
            return reverse_lazy('myapp:intermediario_dashboard')
        else:
            # Cualquier otro usuario (ej. un cliente sin intermediario) va al home.
            return reverse_lazy('myapp:home')


@method_decorator(csrf_protect, name='dispatch')
class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('myapp:login')  # Usar reverse_lazy aquí también

    def _get_client_ip_address(self, request):  # Renombrado y toma request
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                AuditoriaSistema.objects.create(
                    usuario=request.user,
                    tipo_accion='LOGOUT',
                    resultado_accion='EXITO',
                    direccion_ip=self._get_client_ip_address(
                        request),  # Pasar request
                    agente_usuario=request.META.get(
                        'HTTP_USER_AGENT', '')[:500]
                )
            except Exception as e:
                logger.error(
                    f"Error al crear registro de auditoría en Logout: {e}", exc_info=True)
        return super().dispatch(request, *args, **kwargs)
# Vistas Base CRUD


# O MultipleObjectMixin si quieres get_ordering directamente de Django
class BaseCRUDView(View):  # Ajusta la herencia si es necesario
    model = None
    model_manager_name = 'objects'
    search_fields = []
    ordering_fields = []
    default_ordering_if_none_specified = ['pk']

    def get_manager(self):
        return getattr(self.model, self.model_manager_name)

    def get_ordering(self):
        return getattr(self, 'ordering', self.default_ordering_if_none_specified)

    def _apply_search(self, queryset, search_query):
        if search_query and self.search_fields:
            or_conditions = [Q(**{f"{field}__icontains": search_query})
                             for field in self.search_fields]
            if or_conditions:
                queryset = queryset.filter(reduce(operator.or_, or_conditions))
        return queryset

    def _apply_url_ordering(self, queryset):
        sort_param = self.request.GET.get('sort')
        order_param = self.request.GET.get('order', 'asc')
        view_instance_ordering_fields = getattr(self, 'ordering_fields', [])
        if sort_param and sort_param in view_instance_ordering_fields:
            prefix = "-" if order_param == "desc" else ""
            return queryset.order_by(f"{prefix}{sort_param}")
        return queryset

    def get_queryset(self):
        manager = self.get_manager()
        queryset = manager.all()
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = self._apply_search(queryset, search_query)
        default_ordering = self.get_ordering()
        if default_ordering:
            if isinstance(default_ordering, str):
                default_ordering = (default_ordering,)
            queryset = queryset.order_by(*default_ordering)
        queryset = self._apply_url_ordering(queryset)
        return queryset

    def _validate_lookup_path(self, model, field_path):
        related_model = model
        parts = field_path.split('__')
        for i, part in enumerate(parts):
            if i < len(parts) - 1:
                field_obj = related_model._meta.get_field(part)
                if field_obj.is_relation:
                    related_model = field_obj.related_model
                else:
                    raise FieldDoesNotExist(
                        f"'{part}' no es relación en '{field_path}'")
            else:
                related_model._meta.get_field(part)

    # Este método parece ser de BaseListView, no BaseCRUDView
    def _apply_ordering(self, queryset):
        sort_by = self.request.GET.get('sort')
        default_sort = self.get_ordering() or ['-pk']
        if not sort_by:
            sort_by = default_sort[0]
        order = self.request.GET.get(
            'order', 'asc' if not sort_by.startswith('-') else 'desc')
        prefix = '-' if order == 'desc' else ''
        sort_field = sort_by.lstrip('-')
        allowed_ordering_fields = getattr(self, 'ordering_fields', [])

        if sort_field and allowed_ordering_fields and sort_field in allowed_ordering_fields:
            try:
                self._validate_lookup_path(self.model, sort_field)
                if hasattr(self, f'_annotate_sort_{sort_field}'):
                    queryset = getattr(self, f'_annotate_sort_{sort_field}')(
                        queryset, prefix)
                else:
                    queryset = queryset.order_by(f'{prefix}{sort_field}')
                self.current_sort = sort_field
                self.current_order = order
            except FieldDoesNotExist:
                logger.warning(
                    f"Campo orden '{sort_field}' inválido. Usando defecto.")
                queryset = queryset.order_by(*default_sort)
                self.current_sort = default_sort[0].lstrip('-')
                self.current_order = 'desc' if default_sort[0].startswith(
                    '-') else 'asc'
            except Exception as e:
                logger.error(
                    f"Error aplicando orden '{prefix}{sort_field}': {e}")
                queryset = queryset.order_by(*default_sort)
                self.current_sort = default_sort[0].lstrip('-')
                self.current_order = 'desc' if default_sort[0].startswith(
                    '-') else 'asc'
        else:
            if sort_by:
                logger.warning(
                    f"Campo orden '{sort_by}' no permitido/inválido. Usando defecto.")
            queryset = queryset.order_by(*default_sort)
            self.current_sort = default_sort[0].lstrip('-')
            self.current_order = 'desc' if default_sort[0].startswith(
                '-') else 'asc'
        return queryset

    # Este es más típico de ListView/DetailView/TemplateView
    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            **kwargs) if hasattr(super(), 'get_context_data') else {}
        context.update({
            'search_query': escape(self.request.GET.get('search', '')),
            # Los siguientes son más para ListView, pero no hacen daño si están
            'order_by': escape(self.request.GET.get('order_by', '')),
            'direction': escape(self.request.GET.get('direction', 'asc')),
            'aria_current_page': ('Página actual'),
            'aria_goto_page': ('Ir a la página'),
            'aria_role': 'form',
            'aria_live': 'polite'
        })
        return context

    # --- MÉTODO FORM_VALID CORREGIDO Y ROBUSTO ---
    def form_valid(self, form):
        # Determinamos si es una operación de creación o actualización
        is_update = hasattr(self, 'object') and self.object and self.object.pk
        action_type = 'MODIFICACION' if is_update else 'CREACION'

        objeto_antes_dict = {}
        if is_update:
            try:
                # Obtenemos una foto del objeto ANTES de guardarlo
                db_instance = self.model.objects.get(pk=self.object.pk)
                fields_to_compare = [
                    f.name for f in db_instance._meta.fields if f.name in form.fields]
                objeto_antes_dict = model_to_dict(
                    db_instance, fields=fields_to_compare)
            except self.model.DoesNotExist:
                logger.warning(
                    f"No se encontró el objeto original PK={self.object.pk} en form_valid.")

        try:
            # Envolvemos el guardado en una transacción atómica
            with transaction.atomic():
                self.object = form.save()

            # --- Lógica Post-Guardado (Solo si fue exitoso) ---

            # 1. Enviar notificaciones
            try:
                if is_update:
                    if hasattr(self, 'enviar_notificacion_actualizacion'):
                        self.enviar_notificacion_actualizacion(
                            objeto_antes_dict, self.object, form.changed_data)
                else:  # Es creación
                    if hasattr(self, 'enviar_notificacion_creacion'):
                        self.enviar_notificacion_creacion(self.object)
            except Exception as notif_error:
                logger.error(
                    f"Error enviando notificación para {action_type} de {self.model._meta.verbose_name}: {notif_error}", exc_info=True)

            # 2. Crear la entrada de auditoría de ÉXITO
            self._create_audit_entry(
                action_type=action_type,
                resultado='EXITO',
                detalle=f"{action_type} exitosa de {self.model._meta.verbose_name}: {str(self.object)}"
            )

            # 3. Mostrar mensaje de éxito y redirigir
            messages.success(self.request, 'Operación realizada con éxito.')
            return HttpResponseRedirect(self.get_success_url())

        except (ValidationError, IntegrityError) as e:
            # Capturamos errores de validación o de integridad de la base de datos
            logger.error(
                f"Error de guardado en {self.__class__.__name__} ({action_type}): {e}", exc_info=True)

            # Añadimos el error al formulario para mostrarlo al usuario
            if isinstance(e, ValidationError) and hasattr(e, 'message_dict'):
                form._update_errors(e)
            else:
                form.add_error(None, str(e))

            # La lógica de auditoría de ERROR ahora se maneja en form_invalid
            return self.form_invalid(form)

        except Exception as e:
            # Capturamos cualquier otro error inesperado
            logger.error(
                f"Error inesperado en {self.__class__.__name__}.form_valid ({action_type}): {e}", exc_info=True)
            messages.error(
                self.request, f'Ocurrió un error inesperado al procesar el formulario: {str(e)}')

            # La lógica de auditoría de ERROR ahora se maneja en form_invalid
            return self.form_invalid(form)

    # --- MÉTODO FORM_INVALID CORREGIDO Y ROBUSTO ---

    def form_invalid(self, form):
        """
        Manejador para cuando el formulario no es válido.
        Se encarga de registrar la auditoría de fallo y mostrar el mensaje de error.
        """
        is_update = hasattr(self, 'object') and self.object and self.object.pk
        action_type = 'MODIFICACION' if is_update else 'CREACION'

        # Creamos el log de auditoría para el intento fallido
        self._create_audit_entry(
            action_type=action_type,
            resultado='ERROR_VALIDACION',
            detalle=f"Fallo de validación en formulario {self.model._meta.verbose_name}: {form.errors.as_json()}"
        )

        # Log y mensaje para el usuario
        logger.warning(
            f"[{self.__class__.__name__}] Formulario inválido: {form.errors.as_json()}")
        messages.error(
            self.request, "Error en el formulario. Por favor, corrija los campos indicados.")

        # Devolvemos la respuesta para renderizar el formulario con los errores
        return super().form_invalid(form)

    def _create_audit_entry(self, action_type, resultado, detalle):
        registro_pk = None
        if hasattr(self, 'object') and self.object and self.object.pk:
            registro_pk = self.object.pk

        AuditoriaSistema.objects.create(
            usuario=self.request.user if self.request.user.is_authenticated else None,
            tipo_accion=action_type,
            tabla_afectada=self.model._meta.db_table if self.model else "N/A",
            registro_id_afectado=registro_pk,
            detalle_accion=detalle[:500],
            direccion_ip=self._get_client_ip(),
            agente_usuario=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            resultado_accion=resultado
        )

    def _get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0].strip() if x_forwarded_for else self.request.META.get('REMOTE_ADDR', '')
# Vistas Base CRUD (Optimizadas)


class BaseListView(BaseCRUDView, FilterView):
    paginate_by = ITEMS_PER_PAGE
    filterset_class = None
    select_related_fields = []
    prefetch_related_fields = []

    def get_queryset(self):
        # Llama a BaseCRUDView.get_queryset(), que ya devuelve un queryset
        # buscado y ORDENADO (por defecto o por URL).
        queryset_from_base_crud = super().get_queryset()

        # FilterView aplicará self.filterset_class a este queryset_from_base_crud.
        # django-filter preserva el orden a menos que el FilterSet tenga un OrderingFilter.

        if self.select_related_fields:
            queryset_from_base_crud = queryset_from_base_crud.select_related(
                *self.select_related_fields)
        if self.prefetch_related_fields:
            queryset_from_base_crud = queryset_from_base_crud.prefetch_related(
                *self.prefetch_related_fields)

        return queryset_from_base_crud

    def get_ordering(self):
        # Este método es proporcionado por MultipleObjectMixin (padre de ListView y FilterView)
        # Devolverá el atributo 'ordering' de la clase hija (AfiliadoColectivoListView)
        # o el ordenamiento de los parámetros GET si se está usando un OrderingFilter.
        # BaseCRUDView.get_ordering() ya no es llamado directamente si BaseListView hereda de ListView/FilterView.
        # FilterView maneja el ordenamiento basado en GET params si hay un OrderingFilter.
        # Si no, ListView aplica el atributo self.ordering.

        # Si hay un OrderingFilter en el FilterSet y se usó un parámetro de orden:
        if hasattr(self, 'filterset') and self.filterset and self.filterset.form.is_valid():
            # El nombre del campo de ordenamiento en el form del filterset (usualmente 'o')
            ordering_filter_param_name = getattr(
                getattr(self.filterset, 'ordering_filter', None), 'param_name', 'o')
            url_ordering = self.filterset.form.cleaned_data.get(
                ordering_filter_param_name)
            if url_ordering:  # Puede ser una lista o un string
                return url_ordering

        # Si no, devuelve el 'ordering' atributo de la clase
        return getattr(self, 'ordering', super().get_ordering())

    def get_context_data(self, **kwargs):
        # FilterView y ListView configuran mucho aquí
        context = super().get_context_data(**kwargs)

        # Para los enlaces de ordenamiento en la plantilla
        # Necesitamos saber el campo actual y la dirección

        # 'ordering' puede ser una lista o una tupla de campos de ordenamiento.
        # El paginador de Django tomará el primer campo si hay múltiples.
        final_qs_for_pagination = self.object_list  # Este es el que se pagina

        # Si el object_list es un queryset (antes de ser convertido a lista por el paginador)
        # y tiene un ordenamiento, lo usamos. Si no, intentamos con self.get_ordering()
        current_order_fields = []
        if hasattr(final_qs_for_pagination, 'ordered') and final_qs_for_pagination.ordered:
            if hasattr(final_qs_for_pagination, 'query') and final_qs_for_pagination.query.order_by:
                current_order_fields = list(
                    final_qs_for_pagination.query.order_by)

        if not current_order_fields:  # Si no se pudo obtener del queryset paginado, usar get_ordering()
            order_setting = self.get_ordering()
            if order_setting:
                if isinstance(order_setting, str):
                    current_order_fields = [order_setting]
                else:
                    # Asegurar que sea una lista
                    current_order_fields = list(order_setting)

        if current_order_fields:
            first_order_field = current_order_fields[0]
            context['current_sort'] = first_order_field.lstrip('-')
            context['current_order'] = 'desc' if first_order_field.startswith(
                '-') else 'asc'
        else:  # Fallback absoluto si no hay ordenamiento
            context['current_sort'] = 'pk'
            context['current_order'] = 'asc'

        context['search_query'] = escape(self.request.GET.get('search', ''))
        return context

# --- BaseCreateView (Usa form_valid de BaseCRUDView) ---


@method_decorator(csrf_protect, name='dispatch')
class BaseCreateView(BaseCRUDView, CreateView):
    # form_valid es heredado de BaseCRUDView

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # Llama al de BaseCRUDView
        # CreateView añade 'form' al contexto
        context['view_type'] = 'create'
        context['form_title'] = f'Crear Nuevo {self.model._meta.verbose_name}'
        return context

    def form_invalid(self, form):
        logger.warning(
            f"[{self.__class__.__name__}] Formulario inválido: {form.errors.as_json()}")
        messages.error(
            self.request, "Error en el formulario. Por favor, corrija los campos indicados.")
        # Renderiza la plantilla con el form y los errores
        return super().form_invalid(form)


# --- BaseUpdateView (Usa form_valid de BaseCRUDView) ---
@method_decorator(csrf_protect, name='dispatch')
class BaseUpdateView(BaseCRUDView, UpdateView):
    # form_valid es heredado de BaseCRUDView

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # Llama al de BaseCRUDView
        # UpdateView añade 'form' y 'object'
        context['view_type'] = 'update'
        # Asegurarse que self.object exista antes de usarlo en el título
        obj_repr = str(self.object) if hasattr(
            self, 'object') and self.object else 'Registro'
        context['form_title'] = f'Editar {self.model._meta.verbose_name}: {obj_repr}'
        return context

    def form_invalid(self, form):
        logger.warning(
            f"[{self.__class__.__name__}] Formulario inválido: {form.errors.as_json()}")
        messages.error(
            self.request, "Error en el formulario. Por favor, corrija los campos indicados.")
        # Renderiza la plantilla con el form y los errores
        return super().form_invalid(form)


# Clase base para vistas de eliminación
@method_decorator(csrf_protect, name='dispatch')
class BaseDeleteView(PermissionRequiredMixin, DeleteView):  # No hereda de BaseCRUDView
    template_name = 'confirm_delete.html'
    # Asegurar redirección si no está logueado
    login_url = reverse_lazy('myapp:login')

    # Helper para obtener IP (duplicado para independencia)
    def _get_client_ip(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        return ip.split(',')[0].strip() if ip else request.META.get('REMOTE_ADDR', '')

    # Helper para auditoría (duplicado para independencia)
    def _create_audit_entry(self, request, action_type, resultado, detalle, obj_pk=None, obj_repr=""):
        try:
            AuditoriaSistema.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                tipo_accion=action_type, tabla_afectada=self.model._meta.db_table,
                registro_id_afectado=obj_pk, detalle_accion=f"{detalle}: {obj_repr}"[
                    :500],
                direccion_ip=self._get_client_ip(request), agente_usuario=request.META.get('HTTP_USER_AGENT', '')[:500],
                resultado_accion=resultado
            )
        except Exception as audit_e:
            logger.error(
                f"Error creando auditoría {action_type} {resultado}: {audit_e}")

    # Sobrescribir post para manejar la lógica completa aquí
    def post(self, request, *args, **kwargs):
        object_pk_for_audit = None  # Inicializar
        object_repr_for_audit = "Objeto Desconocido"
        try:
            self.object = self.get_object()
            object_pk_for_audit = self.object.pk
            # Capturar repr ANTES de borrar
            object_repr_for_audit = str(self.object)

            # Validación específica de la subclase (si existe)
            if hasattr(self, 'can_delete') and not self.can_delete(self.object):
                # El método can_delete debe encargarse de los messages.error
                # Redirigir aquí si can_delete no lo hizo (ej. al detalle)
                try:
                    return redirect(reverse(f'myapp:{self.model._meta.model_name}_detail', kwargs={'pk': object_pk_for_audit}))
                except:
                    return redirect(self.get_success_url())  # Fallback

            # Si pasa validación, intentar borrar dentro de transacción
            with transaction.atomic():
                self.object.delete()

            # Si el borrado fue exitoso
            messages.success(
                request, f"{self.model._meta.verbose_name} '{object_repr_for_audit}' eliminado correctamente.")
            self._create_audit_entry(request, 'ELIMINACION', 'EXITO',
                                     f"Eliminación de {self.model._meta.verbose_name}", object_pk_for_audit, object_repr_for_audit)

            return HttpResponseRedirect(self.get_success_url())

        except ProtectedError as e:
            logger.warning(
                f"ProtectedError eliminando {self.model._meta.verbose_name} {object_pk_for_audit}: {e}")
            messages.error(
                request, f"No se puede eliminar '{object_repr_for_audit}': registros asociados protegidos.")
            self._create_audit_entry(request, 'ELIMINACION', 'ERROR',
                                     f"ProtectedError: {e}", object_pk_for_audit, object_repr_for_audit)
            try:
                return redirect(reverse(f'myapp:{self.model._meta.model_name}_detail', kwargs={'pk': object_pk_for_audit}))
            except:
                return redirect(self.get_success_url())
        except self.model.DoesNotExist:
            logger.warning(
                f"Intento eliminar {self.model.__name__} inexistente (kwargs={kwargs}) por {request.user}.")
            messages.error(request, "Error: Registro a eliminar no existe.")
            return redirect(self.get_success_url())
        except Exception as e:
            current_pk = object_pk_for_audit if object_pk_for_audit else self.kwargs.get(
                'pk', 'N/A')
            logger.error(
                f"Error inesperado eliminando {self.model._meta.verbose_name} PK={current_pk}: {e}", exc_info=True)
            messages.error(request, f"Error inesperado al eliminar: {str(e)}")
            self._create_audit_entry(
                request, 'ELIMINACION', 'ERROR', f"Error inesperado: {str(e)[:200]}", current_pk)
            try:
                return redirect(reverse(f'myapp:{self.model._meta.model_name}_detail', kwargs={'pk': current_pk}))
            except:
                return redirect(self.get_success_url())

    # Opcional: get_context_data para pasar info extra a la plantilla de confirmación
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Puedes añadir aquí lógica para mostrar advertencias si hay dependencias, etc.
        # context['dependencias'] = ...
        return context

# --- BaseDetailView (Mantiene la auditoría de consulta) ---


# Hereda de BaseCRUDView para _get_client_ip etc.
class BaseDetailView(BaseCRUDView, DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # Llama al de BaseCRUDView
        # DetailView añade 'object'
        context['active_tab'] = self.request.GET.get('tab', 'detail')
        context['active_container'] = self.request.GET.get('container', 'main')

        # Auditoría de consulta (como estaba antes)
        if hasattr(self, 'object') and self.object:
            try:
                AuditoriaSistema.objects.create(
                    usuario=self.request.user if self.request.user.is_authenticated else None,
                    tipo_accion='CONSULTA', tabla_afectada=self.model._meta.db_table,
                    registro_id_afectado=self.object.pk, detalle_accion=f"Consulta de {self.model._meta.verbose_name}: {self.object}",
                    direccion_ip=self._get_client_ip(), agente_usuario=self.request.META.get('HTTP_USER_AGENT', '')[:500],
                    resultado_accion='EXITO'
                )
            except Exception as audit_e:
                logger.error(
                    f"Error auditoría CONSULTA {self.model.__name__} {self.object.pk}: {audit_e}")
        return context


# Vistas específicas (heredan de las nuevas bases)

# ==========================
# AuditoriaSistema Vistas
# ==========================

class AuditoriaSistemaListView(LoginRequiredMixin, ListView):
    model = AuditoriaSistema
    template_name = 'auditoria_sistema_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODAS las entradas de auditoría. DataTables se encargará del resto.
        """
        # Optimizamos la consulta para cargar la relación con el usuario
        return AuditoriaSistema.objects.select_related('usuario')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para la plantilla.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Registro de Auditoría del Sistema"
        # No hay campos cifrados, no se necesita bucle de seguridad.
        return context


class AuditoriaSistemaDetailView(BaseDetailView):
    model = AuditoriaSistema
    model_manager_name = 'objects'
    template_name = 'auditoria_sistema_detail.html'
    context_object_name = 'auditoria'
    permission_required = 'myapp.view_auditoriasistema'

    def get_queryset(self):
        # Optimizar la relación con usuario
        return super().get_queryset().select_related('usuario')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        auditoria = self.get_object()
        # Calcular tiempo de proceso si ambas fechas existen
        tiempo_proceso_seg = None
        if auditoria.tiempo_inicio and auditoria.tiempo_final:
            try:
                tiempo_proceso_seg = (
                    auditoria.tiempo_final - auditoria.tiempo_inicio).total_seconds()
            except TypeError:  # Si las fechas no son comparables
                pass
        context.update({
            'tiempo_proceso': tiempo_proceso_seg,
            'es_error': auditoria.resultado_accion == 'ERROR',
            'tipos_accion': CommonChoices.TIPO_ACCION,  # Pasar choices para display
            'resultados_accion': CommonChoices.RESULTADO_ACCION
        })
        return context


@method_decorator(csrf_protect, name='dispatch')
class AuditoriaSistemaCreateView(BaseCreateView):
    model = AuditoriaSistema
    model_manager_name = 'all_objects'
    template_name = 'auditoria_sistema_form.html'
    permission_required = 'myapp.add_auditoriasistema'
    form_class = AuditoriaSistemaForm
    success_url = reverse_lazy('myapp:auditoria_sistema_list')
    # La lógica de form_valid y la notificación están en BaseCreateView/BaseCRUDView

    # Este método para notificar NO se llamará porque Auditoría no debería tener notificaciones
    # def enviar_notificacion_creacion(self, auditoria): pass


@method_decorator(csrf_protect, name='dispatch')
class AuditoriaSistemaUpdateView(BaseUpdateView):
    model = AuditoriaSistema
    model_manager_name = 'all_objects'
    form_class = AuditoriaSistemaForm
    template_name = 'auditoria_sistema_form.html'
    context_object_name = 'auditoria'
    permission_required = 'myapp.change_auditoriasistema'
    success_url = reverse_lazy('myapp:auditoria_sistema_list')
    # La lógica de form_valid y la notificación están en BaseUpdateView/BaseCRUDView

    # Este método para notificar NO se llamará porque Auditoría no debería tener notificaciones
    # def enviar_notificacion_actualizacion(self, aud_antes, aud_despues, changed_data): pass


@method_decorator(csrf_protect, name='dispatch')
class AuditoriaSistemaDeleteView(BaseDeleteView):
    model = AuditoriaSistema
    # O tu genérico 'confirm_delete.html'
    template_name = 'auditoria_sistema_confirm_delete.html'
    context_object_name = 'auditoria'  # O 'object' si usas un template genérico
    permission_required = 'myapp.delete_auditoriasistema'
    success_url = reverse_lazy('myapp:auditoria_sistema_list')

    def can_delete(self, obj):  # Ahora devuelve (bool, str)
        # Usar django_timezone para comparaciones de fecha/hora conscientes
        if obj.tiempo_inicio and obj.tiempo_inicio > (django_timezone.now() - timedelta(days=30)):
            return False, 'Solo se pueden eliminar registros de auditoría con más de 30 días de antigüedad.'
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        # Título ejemplo
        context['page_title'] = f"Confirmar Eliminación de Auditoría: #{self.object.pk}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            # Redirigir a la lista ya que el detalle de auditoría podría no ser común
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)  # Llama a BaseDeleteView.post

# ==========================
# AfiliadoIndividual Vistas
# ==========================


class AfiliadoIndividualListView(LoginRequiredMixin, ListView):
    """
    Vista para listar todos los Afiliados Individuales.
    Está diseñada para ser usada con DataTables del lado del cliente.
    """
    model = AfiliadoIndividual
    template_name = 'afiliado_individual_list.html'
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODOS los afiliados activos, sin paginación del backend.
        DataTables se encargará de la paginación, búsqueda y ordenamiento.
        Optimizamos la consulta para incluir el intermediario.
        """
        # Usamos el manager 'objects' que ya filtra por activo=True por defecto
        return AfiliadoIndividual.objects.select_related('intermediario').order_by('-fecha_creacion')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para la plantilla.
        Añade un título y maneja de forma segura los errores de desencriptación.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Afiliados Individuales"

        # Bucle de seguridad para manejar registros que no se pueden desencriptar
        object_list_safe = []
        for obj in context['object_list']:
            try:
                # Forzamos la desencriptación de un campo para probar si el registro es válido
                str(obj.nombre_completo)
                obj.decryption_error = False
            except Exception as e:
                logger.error(
                    f"Error de desencriptación en AfiliadoIndividualListView para PK {obj.pk}: {e}")
                obj.decryption_error = True
            object_list_safe.append(obj)

        context['object_list'] = object_list_safe
        return context


class AfiliadoIndividualDetailView(BaseDetailView):
    model = AfiliadoIndividual
    model_manager_name = 'all_objects'
    template_name = 'afiliado_individual_detail.html'
    context_object_name = 'afiliado'
    permission_required = 'myapp.view_afiliadoindividual'

    def get_queryset(self):
        return super().get_queryset().select_related('intermediario').prefetch_related(
            Prefetch('contratos', queryset=ContratoIndividual.objects.select_related('intermediario').prefetch_related(
                'reclamacion_set', Prefetch('factura_set', queryset=Factura.objects.prefetch_related('pagos'))))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        afiliado = self.object
        contratos_list = list(afiliado.contratos.all())
        reclamaciones_list = [
            rec for c in contratos_list for rec in c.reclamacion_set.all()]
        facturas_list = [
            fac for c in contratos_list for fac in c.factura_set.all()]
        pagos_list = [p for f in facturas_list for p in f.pagos.all()]

        context.update({
            'edad': afiliado.edad,
            'nombre_completo': afiliado.nombre_completo,
            'tipo_identificacion_display': afiliado.get_tipo_identificacion_display(),
            'sexo_display': afiliado.get_sexo_display(),
            'parentesco_display': afiliado.get_parentesco_display(),
            'estado_civil_display': afiliado.get_estado_civil_display(),
            'estado_display': afiliado.get_estado_display() if afiliado.estado else 'No especificado',
            'contratos_asociados': contratos_list,
            'reclamaciones_asociadas': reclamaciones_list,
            'facturas_asociadas': facturas_list,
            'pagos_asociados': pagos_list,
            'total_contratos': len(contratos_list),
            'total_reclamaciones': len(reclamaciones_list),
            'total_facturas': len(facturas_list),
            'total_pagos': len(pagos_list),
            'monto_total_contratos': sum(c.monto_total for c in contratos_list if c.monto_total) or Decimal('0.0'),
            'monto_total_reclamado': sum(r.monto_reclamado for r in reclamaciones_list if r.monto_reclamado) or Decimal('0.0'),
            'monto_total_facturado': sum(f.monto for f in facturas_list if f.monto) or Decimal('0.0'),
            'monto_total_pagado': sum(p.monto_pago for p in pagos_list if p.monto_pago) or Decimal('0.0'),
            'monto_pendiente_facturas': sum(f.monto_pendiente for f in facturas_list if f.monto_pendiente) or Decimal('0.0')
        })
        return context


@method_decorator(csrf_protect, name='dispatch')
class AfiliadoIndividualCreateView(BaseCreateView):
    model = AfiliadoIndividual
    model_manager_name = 'all_objects'
    form_class = AfiliadoIndividualForm
    template_name = 'afiliado_individual_form.html'
    permission_required = 'myapp.add_afiliadoindividual'
    success_url = reverse_lazy('myapp:afiliado_individual_list')

    # form_valid heredado de BaseCRUDView llamará a enviar_notificacion_creacion

    def enviar_notificacion_creacion(self, afiliado):
        mensaje = f"Nuevo Afiliado Individual registrado: {afiliado.nombre_completo} (CI: {afiliado.cedula})."
        crear_notificacion(
            usuario_destino=Usuario.objects.filter(
                is_staff=True, is_active=True),
            mensaje=mensaje, tipo='success',
            url_path_name='myapp:afiliado_individual_detail', url_kwargs={'pk': afiliado.pk}
        )


@method_decorator(csrf_protect, name='dispatch')
class AfiliadoIndividualUpdateView(BaseUpdateView):
    model = AfiliadoIndividual
    model_manager_name = 'all_objects'
    template_name = 'afiliado_individual_form.html'
    context_object_name = 'afiliado'
    permission_required = 'myapp.change_afiliadoindividual'
    form_class = AfiliadoIndividualForm
    success_url = reverse_lazy('myapp:afiliado_individual_list')

    # form_valid heredado de BaseCRUDView llamará a enviar_notificacion_actualizacion

    def enviar_notificacion_actualizacion(self, afi_antes, afi_despues, changed_data):
        if not changed_data:
            return
        mensaje = f"Afiliado Individual {afi_despues.nombre_completo} actualizado. Cambios: {', '.join(changed_data)}."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        # Notificar intermediario?
        if admin_users:
            crear_notificacion(
                list(set(admin_users)),
                mensaje,
                tipo='info',
                url_path_name='myapp:afiliado_individual_detail',
                url_kwargs={'pk': afi_despues.pk}
            )


@method_decorator(csrf_protect, name='dispatch')
class AfiliadoIndividualDeleteView(BaseDeleteView):
    model = AfiliadoIndividual
    template_name = 'afiliado_individual_confirm_delete.html'  # O tu genérico
    context_object_name = 'afiliadoindividual'  # O 'object'
    success_url = reverse_lazy('myapp:afiliado_individual_list')
    permission_required = 'myapp.delete_afiliadoindividual'

    def can_delete(self, obj):  # Devuelve (bool, str)
        if hasattr(obj, 'contratos') and obj.contratos.exists():  # 'contratos' es el related_name
            return False, f"No se puede eliminar '{obj.nombre_completo}': tiene contratos vinculados."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        context['page_title'] = f"Confirmar Eliminación: {self.object.nombre_completo}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            try:
                return redirect(reverse('myapp:afiliado_individual_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, afiliado_repr):
        mensaje = f"Se eliminó el Afiliado Individual: {afiliado_repr}."
        crear_notificacion(
            usuario_destino=Usuario.objects.filter(
                is_superuser=True, is_active=True),
            mensaje=mensaje, tipo='warning'
        )


# ==========================
# AfiliadoColectivo Vistas
# ==========================


class AfiliadoColectivoListView(LoginRequiredMixin, ListView):
    model = AfiliadoColectivo
    template_name = 'afiliado_colectivo_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODOS los afiliados colectivos activos. DataTables se encargará del resto.
        """
        return AfiliadoColectivo.objects.filter(activo=True).select_related('intermediario')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto, manejando errores de desencriptación de forma segura.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Afiliados Colectivos"

        object_list_safe = []
        for obj in context['object_list']:
            try:
                # Forzamos la desencriptación de un campo para probar si el registro es válido
                str(obj.razon_social)
                obj.decryption_error = False
            except Exception:
                obj.decryption_error = True
            object_list_safe.append(obj)

        context['object_list'] = object_list_safe
        return context


class AfiliadoColectivoDetailView(BaseDetailView):
    model = AfiliadoColectivo
    model_manager_name = 'all_objects'
    template_name = 'afiliado_colectivo_detail.html'
    context_object_name = 'afiliado'
    permission_required = 'myapp.view_afiliadocolectivo'

    def get_queryset(self):
        return super().get_queryset().select_related('intermediario').prefetch_related(
            Prefetch('contratos_afiliados', queryset=ContratoColectivo.objects.select_related('intermediario').prefetch_related(
                'reclamacion_set', Prefetch('factura_set', queryset=Factura.objects.prefetch_related('pagos'))))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        afiliado = self.object
        contratos_list = list(afiliado.contratos_afiliados.all())
        reclamaciones_list = [
            rec for c in contratos_list for rec in c.reclamacion_set.all()]
        facturas_list = [
            fac for c in contratos_list for fac in c.factura_set.all()]
        pagos_list = [p for f in facturas_list for p in f.pagos.all()]
        intermediarios_contratos = {
            c.intermediario for c in contratos_list if c.intermediario}

        context.update({
            'nombre_completo_display': afiliado.nombre_completo,
            'tipo_empresa_display': afiliado.get_tipo_empresa_display(),
            'intermediario_directo': afiliado.intermediario,
            'contratos_asociados': contratos_list,
            'reclamaciones_asociadas': reclamaciones_list,
            'facturas_asociadas': facturas_list,
            'pagos_asociados': pagos_list,
            'intermediarios_via_contrato': list(intermediarios_contratos),
            'total_contratos': len(contratos_list),
            'total_reclamaciones': len(reclamaciones_list),
            'total_facturas': len(facturas_list),
            'total_pagos': len(pagos_list),
            'monto_total_contratos': sum(c.monto_total for c in contratos_list if c.monto_total) or Decimal('0.0'),
            'monto_total_reclamado': sum(r.monto_reclamado for r in reclamaciones_list if r.monto_reclamado) or Decimal('0.0'),
            'monto_total_facturado': sum(f.monto for f in facturas_list if f.monto) or Decimal('0.0'),
            'monto_total_pagado': sum(p.monto_pago for p in pagos_list if p.monto_pago) or Decimal('0.0'),
            'monto_pendiente_facturas': sum(f.monto_pendiente for f in facturas_list if f.monto_pendiente) or Decimal('0.0'),
            'cantidad_total_empleados_contratos': sum(c.cantidad_empleados for c in contratos_list if c.cantidad_empleados) or 0,
            'esta_vigente_algun_contrato': any(c.esta_vigente for c in contratos_list),
            'active_tab': 'afiliados_colectivos_detail',
        })
        return context


@method_decorator(csrf_protect, name='dispatch')
class AfiliadoColectivoCreateView(BaseCreateView):
    model = AfiliadoColectivo
    model_manager_name = 'all_objects'
    form_class = AfiliadoColectivoForm
    template_name = 'afiliado_colectivo_form.html'
    permission_required = 'myapp.add_afiliadocolectivo'
    success_url = reverse_lazy('myapp:afiliado_colectivo_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.activo = True  # O basado en alguna lógica
        return super().form_valid(form)

    # form_valid heredado

    def enviar_notificacion_creacion(self, afiliado_col):
        mensaje = f"Nueva Empresa/Colectivo registrado: {afiliado_col.razon_social} (RIF: {afiliado_col.rif})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        # Notificar intermediario?
        if admin_users:
            crear_notificacion(list(set(admin_users)), mensaje, tipo='success',
                               url_path_name='myapp:afiliado_colectivo_detail', url_kwargs={'pk': afiliado_col.pk})


@method_decorator(csrf_protect, name='dispatch')
class AfiliadoColectivoUpdateView(BaseUpdateView):
    model = AfiliadoColectivo
    model_manager_name = 'all_objects'
    form_class = AfiliadoColectivoForm
    template_name = 'afiliado_colectivo_form.html'
    context_object_name = 'afiliado'
    permission_required = 'myapp.change_afiliadocolectivo'
    success_url = reverse_lazy('myapp:afiliado_colectivo_list')

    # form_valid heredado

    def enviar_notificacion_actualizacion(self, afi_antes, afi_despues, changed_data):
        if not changed_data:
            return
        mensaje = f"Empresa/Colectivo {afi_despues.razon_social} actualizado. Cambios: {', '.join(changed_data)}."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        # Notificar intermediario?
        if admin_users:
            crear_notificacion(list(set(admin_users)), mensaje, tipo='info',
                               url_path_name='myapp:afiliado_colectivo_detail', url_kwargs={'pk': afi_despues.pk})


@method_decorator(csrf_protect, name='dispatch')
class AfiliadoColectivoDeleteView(BaseDeleteView):
    model = AfiliadoColectivo
    template_name = 'afiliado_colectivo_confirm_delete.html'  # O tu genérico
    context_object_name = 'afiliado'  # O 'object'
    permission_required = 'myapp.delete_afiliadocolectivo'
    success_url = reverse_lazy('myapp:afiliado_colectivo_list')

    def can_delete(self, obj):  # Devuelve (bool, str)
        # Usar related_name 'contratos_afiliados'
        if hasattr(obj, 'contratos_afiliados') and obj.contratos_afiliados.exists():
            return False, f"No se puede eliminar '{obj.razon_social}': tiene contratos asociados."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        context['page_title'] = f"Confirmar Eliminación: {self.object.razon_social}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            try:
                return redirect(reverse('myapp:afiliado_colectivo_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó Empresa/Colectivo: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')

# ==========================
# ContratoIndividual Vistas
# ==========================


class ContratoIndividualListView(LoginRequiredMixin, ListView):
    model = ContratoIndividual
    template_name = 'contrato_individual_list.html'
    context_object_name = 'object_list'

    def get_queryset(self):
        # Devolvemos todos los contratos activos con sus relaciones para mostrar en la tabla
        return ContratoIndividual.objects.filter(activo=True).select_related('afiliado', 'intermediario')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Contratos Individuales"

        # Bucle de seguridad para manejar errores de desencriptación
        object_list_safe = []
        for obj in context['object_list']:
            try:
                str(obj.contratante_nombre)  # Probar un campo cifrado
                obj.decryption_error = False
            except Exception:
                obj.decryption_error = True
            object_list_safe.append(obj)

        context['object_list'] = object_list_safe
        return context


class ContratoIndividualDetailView(BaseDetailView):
    model = ContratoIndividual
    template_name = 'contrato_individual_detail.html'
    context_object_name = 'object'
    permission_required = 'myapp.view_contratoindividual'
    model_manager_name = 'all_objects'

    def get_queryset(self):
        """
        Simplificamos la consulta para evitar prefetch conflictivos.
        La carga de datos se hará explícitamente en get_context_data.
        """
        queryset = super().get_queryset()
        return queryset.select_related('afiliado', 'intermediario', 'tarifa_aplicada')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto completo, asegurando que TODOS los datos relacionados
        se lean frescos desde la base de datos.
        """
        context = super().get_context_data(**kwargs)
        contrato = self.object

        # 1. Refrescar el objeto Contrato para el contador.
        contrato.refresh_from_db()

        # =========================================================================
        # === LECTURA FRESCA DE TODAS LAS RELACIONES ===
        # =========================================================================

        # 2. Obtener Facturas y sus Pagos con una consulta fresca.
        facturas_asociadas = list(Factura.objects.filter(
            contrato_individual=contrato
        ).prefetch_related(
            Prefetch('pagos', queryset=Pago.objects.filter(activo=True))
        ))

        # 3. Obtener Reclamaciones con una consulta fresca.
        #    Esto garantiza que obtengamos el estado más reciente ("Pagada").
        reclamaciones_asociadas = list(Reclamacion.objects.filter(
            contrato_individual=contrato
        ))

        # 4. Obtener los pagos de esas reclamaciones.
        pagos_de_reclamaciones = list(Pago.objects.filter(
            reclamacion__in=reclamaciones_asociadas,
            activo=True
        ))

        # 5. Calcular los totales financieros.
        total_pagado_a_facturas = sum(
            pago.monto_pago for factura in facturas_asociadas for pago in factura.pagos.all()
        ) or Decimal('0.00')

        saldo_pendiente_anual = (contrato.importe_anual_contrato or Decimal(
            '0.00')) - total_pagado_a_facturas

        monto_total_pagado_reclamaciones = sum(
            p.monto_pago for p in pagos_de_reclamaciones
        ) or Decimal('0.00')

        saldo_disponible_cobertura = (contrato.suma_asegurada or Decimal(
            '0.00')) - monto_total_pagado_reclamaciones

        porcentaje_cobertura_consumido = Decimal('0.0')
        if contrato.suma_asegurada and contrato.suma_asegurada > 0:
            porcentaje_cobertura_consumido = (
                monto_total_pagado_reclamaciones / contrato.suma_asegurada) * 100
        # Permisos para los botones.
        user_permissions = {
            'can_view_facturas': self.request.user.has_perm('myapp.view_factura'),
            'can_view_reclamaciones': self.request.user.has_perm('myapp.view_reclamacion'),
            'can_view_pagos': self.request.user.has_perm('myapp.view_pago'),
            'can_view_afiliadoindividual': self.request.user.has_perm('myapp.view_afiliadoindividual'),
            'can_view_intermediario': self.request.user.has_perm('myapp.view_intermediario'),
            'can_view_tarifa': self.request.user.has_perm('myapp.view_tarifa'),
        }

        # 4. Construir el contexto final para que coincida con tu template.
        context.update({
            'object': contrato,

            # Variables para la sección de resumen financiero
            'total_pagado_a_facturas': total_pagado_a_facturas,
            'saldo_pendiente_anual': saldo_pendiente_anual,

            # Variables para la sección de consumo de cobertura
            'monto_total_pagado_reclamaciones': monto_total_pagado_reclamaciones,
            'saldo_disponible_cobertura': saldo_disponible_cobertura,
            'porcentaje_cobertura_consumido': porcentaje_cobertura_consumido,

            # Listas para las tablas de relaciones
            'reclamaciones_asociadas': reclamaciones_asociadas,
            'pagos_de_reclamaciones': pagos_de_reclamaciones,
            'facturas_asociadas': facturas_asociadas,

            # Permisos
            'perms': self.request.user.get_all_permissions(),
            'user_perms': user_permissions,
        })

        return context


@method_decorator(csrf_protect, name='dispatch')
class ContratoIndividualCreateView(BaseCreateView):
    model = ContratoIndividual
    model_manager_name = 'all_objects'
    form_class = ContratoIndividualForm
    template_name = 'contrato_individual_form.html'
    success_url = reverse_lazy('myapp:contrato_individual_list')
    permission_required = 'myapp.add_contratoindividual'

    # form_valid heredado

    def enviar_notificacion_creacion(self, contrato):
        mensaje = f"Nuevo Contrato Individual creado: {contrato.numero_contrato} para {contrato.afiliado.nombre_completo if contrato.afiliado else 'N/A'}."
        url_k = {'pk': contrato.pk}
        destinatarios = []
        if contrato.intermediario and hasattr(contrato.intermediario, 'usuarios'):
            destinatarios.extend(
                list(contrato.intermediario.usuarios.filter(is_active=True)))
        # Siempre notificar admins?
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(
                list(set(destinatarios)),
                mensaje,
                tipo='success',
                url_path_name='myapp:contrato_individual_detail',
                url_kwargs=url_k
            )


@method_decorator(csrf_protect, name='dispatch')
class ContratoIndividualUpdateView(BaseUpdateView):
    model = ContratoIndividual
    model_manager_name = 'all_objects'
    form_class = ContratoIndividualForm
    template_name = 'contrato_individual_form.html'
    success_url = reverse_lazy('myapp:contrato_individual_list')
    permission_required = 'myapp.change_contratoindividual'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Aplicar 'disabled' en lugar de 'readonly' para usuarios no superusuarios
        if not self.request.user.is_superuser and self.object:
            fields_to_disable = [
                'fecha_inicio_vigencia',
                'fecha_fin_vigencia',
                'periodo_vigencia_meses'
            ]
            for field_name in fields_to_disable:
                if field_name in form.fields:
                    # Cambiar a disabled
                    form.fields[field_name].disabled = True
                    # Opcional: Añadir una clase para estilo visual si 'disabled' no es suficiente
                    # (aunque los navegadores suelen darle un estilo grisáceo por defecto)
                    widget_class = form.fields[field_name].widget.attrs.get(
                        'class', '')
                    # Evitar duplicar la clase si ya existe
                    if 'disabled-field' not in widget_class:
                        form.fields[field_name].widget.attrs['class'] = f"{widget_class} disabled-field".strip(
                        )

        return form

    def enviar_notificacion_actualizacion(self, cont_antes, cont_despues, changed_data):
        if not changed_data:
            return
        mensaje = f"Contrato Individual {cont_despues.numero_contrato} actualizado. Cambios: {', '.join(changed_data)}."
        destinatarios = []
        if cont_despues.intermediario and hasattr(cont_despues.intermediario, 'usuarios'):
            destinatarios.extend(
                list(cont_despues.intermediario.usuarios.filter(is_active=True)))
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(
                list(set(destinatarios)),
                mensaje,
                tipo='info',
                url_path_name='myapp:contrato_individual_detail',
                url_kwargs={'pk': cont_despues.pk}
            )


@method_decorator(csrf_protect, name='dispatch')
class ContratoIndividualDeleteView(BaseDeleteView):
    model = ContratoIndividual
    template_name = 'contrato_individual_confirm_delete.html'  # O tu genérico
    success_url = reverse_lazy('myapp:contrato_individual_list')
    permission_required = 'myapp.delete_contratoindividual'
    context_object_name = 'contratoindividual'  # O 'object'

    def can_delete(self, obj):  # Devuelve (bool, str)
        if hasattr(obj, 'puede_eliminarse') and callable(obj.puede_eliminarse):
            if not obj.puede_eliminarse():  # Asumiendo que puede_eliminarse() devuelve True/False
                return False, "No se puede eliminar este contrato: tiene facturas o reclamaciones asociadas."
        # Fallback si puede_eliminarse no existe
        elif hasattr(obj, 'factura_set') and obj.factura_set.exists():
            return False, "No se puede eliminar este contrato: tiene facturas asociadas."
        elif hasattr(obj, 'reclamacion_set') and obj.reclamacion_set.exists():  # Fallback
            return False, "No se puede eliminar este contrato: tiene reclamaciones asociadas."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        context['page_title'] = f"Confirmar Eliminación CI: {self.object.numero_contrato}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            # Si el mensaje ya fue añadido por puede_eliminarse() (si usa messages.error), no añadir otro.
            if not any(m.level == messages.ERROR for m in messages.get_messages(request)):
                messages.error(
                    request, reason_message or "Este contrato no puede ser eliminado.")
            try:
                return redirect(reverse('myapp:contrato_individual_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó el Contrato Individual: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


# ==========================
# ContratoColectivo Vistas
# ==========================


class ContratoColectivoListView(LoginRequiredMixin, ListView):
    model = ContratoColectivo
    template_name = 'contrato_colectivo_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODOS los contratos colectivos activos. DataTables se encargará del resto.
        """
        return ContratoColectivo.objects.filter(activo=True).select_related('intermediario', 'tarifa_aplicada')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto, manejando errores de desencriptación de forma segura.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Contratos Colectivos"

        object_list_safe = []
        for obj in context['object_list']:
            try:
                # Forzamos la desencriptación de un campo para probar si el registro es válido
                str(obj.razon_social)
                obj.decryption_error = False
            except Exception:
                obj.decryption_error = True
            object_list_safe.append(obj)

        context['object_list'] = object_list_safe
        return context


class ContratoColectivoDetailView(BaseDetailView):
    model = ContratoColectivo
    template_name = 'contrato_colectivo_detail.html'
    context_object_name = 'object'
    permission_required = 'myapp.view_contratocolectivo'
    model_manager_name = 'all_objects'

    def get_queryset(self):
        """
        Optimiza la consulta inicial.
        """
        queryset = super().get_queryset()
        return queryset.select_related('intermediario', 'tarifa_aplicada').prefetch_related('afiliados_colectivos')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto completo para la plantilla, realizando cálculos explícitos
        para garantizar que los datos mostrados sean 100% precisos y actuales.
        """
        context = super().get_context_data(**kwargs)
        contrato = self.object

        # 1. Refrescar el objeto principal. Esto es CLAVE para obtener el contador `pagos_realizados`.
        contrato.refresh_from_db()

        # 2. Obtener las facturas y sus pagos con una consulta fresca.
        facturas_asociadas = list(Factura.objects.filter(
            contrato_colectivo=contrato
        ).prefetch_related(
            Prefetch('pagos', queryset=Pago.objects.filter(activo=True))
        ))

        # 3. Calcular los totales financieros agregados para la sección de resumen.
        total_pagado_a_facturas = sum(
            pago.monto_pago for factura in facturas_asociadas for pago in factura.pagos.all()
        ) or Decimal('0.00')

        saldo_pendiente_contrato = (
            contrato.monto_total or Decimal('0.00')) - total_pagado_a_facturas

        # 4. Calcular el resto de los datos para el contexto, usando properties del modelo donde sea seguro.
        reclamaciones_asociadas = list(contrato.reclamacion_set.all())
        pagos_de_reclamaciones = list(Pago.objects.filter(
            reclamacion__contrato_colectivo=contrato, activo=True))
        # Usando la property
        monto_total_pagado_reclamaciones = contrato.monto_total_pagado_reclamaciones
        saldo_disponible_cobertura = contrato.saldo_disponible_cobertura  # Usando la property
        # Usando la property
        porcentaje_cobertura_consumido = contrato.porcentaje_cobertura_consumido

        # 5. Preparar los permisos para los botones de acción en el template.
        user_permissions = {
            'can_view_facturas': self.request.user.has_perm('myapp.view_factura'),
            'can_view_reclamaciones': self.request.user.has_perm('myapp.view_reclamacion'),
            'can_view_pagos': self.request.user.has_perm('myapp.view_pago'),
            'can_view_afiliadocolectivo': self.request.user.has_perm('myapp.view_afiliadocolectivo'),
        }

        # 6. Construir el contexto final con todas las variables que el template espera.
        context.update({
            # Objeto principal, ya está en el contexto como 'object', ahora refrescado

            # Variables para la sección de resumen financiero
            'total_pagado_a_facturas': total_pagado_a_facturas,
            # <-- Pasamos el valor calculado
            'saldo_pendiente_contrato': saldo_pendiente_contrato,

            # La property del modelo `saldo_pendiente_contrato` usará el cálculo anterior,
            # por lo que no es necesario pasarla explícitamente si el template usa `object.saldo_pendiente_contrato`.

            # Variables para la sección de consumo de cobertura
            'monto_total_pagado_reclamaciones': monto_total_pagado_reclamaciones,
            'saldo_disponible_cobertura': saldo_disponible_cobertura,
            'porcentaje_cobertura_consumido': porcentaje_cobertura_consumido,

            # Listas completas de objetos para las tablas
            'afiliados_asociados': list(contrato.afiliados_colectivos.all()),
            'total_afiliados_asociados': contrato.afiliados_colectivos.count(),

            'reclamaciones_asociadas': reclamaciones_asociadas,
            'total_reclamaciones': len(reclamaciones_asociadas),

            'pagos_de_reclamaciones': pagos_de_reclamaciones,
            'total_pagos_reclamaciones': len(pagos_de_reclamaciones),

            'facturas_asociadas': facturas_asociadas,
            'total_facturas': len(facturas_asociadas),

            # Permisos
            'perms': self.request.user.get_all_permissions(),
            'user_perms': user_permissions,
        })

        return context


@method_decorator(csrf_protect, name='dispatch')
class ContratoColectivoCreateView(BaseCreateView):
    model = ContratoColectivo
    model_manager_name = 'all_objects'
    template_name = 'contrato_colectivo_form.html'
    permission_required = 'myapp.add_contratocolectivo'
    form_class = ContratoColectivoForm
    success_url = reverse_lazy('myapp:contrato_colectivo_list')

    # form_valid heredado

    def enviar_notificacion_creacion(self, contrato):
        mensaje = f"Nuevo Contrato Colectivo: {contrato.numero_contrato} para {contrato.razon_social}."
        url_k = {'pk': contrato.pk}
        destinatarios = []
        if contrato.intermediario and hasattr(contrato.intermediario, 'usuarios'):
            destinatarios.extend(
                list(contrato.intermediario.usuarios.filter(is_active=True)))
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(list(set(destinatarios)), mensaje, tipo='success',
                               url_path_name='myapp:contrato_colectivo_detail', url_kwargs=url_k)


@method_decorator(csrf_protect, name='dispatch')
class ContratoColectivoUpdateView(BaseUpdateView):
    model = ContratoColectivo
    model_manager_name = 'all_objects'
    form_class = ContratoColectivoForm
    template_name = 'contrato_colectivo_form.html'
    context_object_name = 'contrato'
    permission_required = 'myapp.change_contratocolectivo'
    success_url = reverse_lazy('myapp:contrato_colectivo_list')
    success_message = "Contrato Colectivo actualizado exitosamente."
    form_invalid_message = "Error al actualizar el Contrato Colectivo. Revise los campos."

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('intermediario').prefetch_related('afiliados_colectivos')

    def get_form(self, form_class=None):
        """
        Obtiene la instancia del formulario base sin modificaciones
        adicionales de readonly/disabled en esta vista.
        """
        form = super().get_form(form_class)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = f"Editar Contrato Colectivo: {self.object.numero_contrato or self.object.razon_social}"
        return context

    def form_valid(self, form):
        objeto_antes = None
        datos_antes = {}
        try:
            objeto_antes = self.model.objects.get(pk=self.object.pk)
            fields_to_compare = [
                f.name for f in objeto_antes._meta.fields if f.name in form.fields]
            datos_antes = model_to_dict(objeto_antes, fields=fields_to_compare)
        except self.model.DoesNotExist:
            logger.warning(
                f"No se encontró el objeto original PK={self.object.pk} en form_valid.")

        # Llama al form_valid de BaseUpdateView/BaseCRUDView
        response = super().form_valid(form)

        if objeto_antes:
            datos_despues = form.cleaned_data
            campos_cambiados = []
            for field, initial_value in datos_antes.items():
                current_value = datos_despues.get(field)
                # Comparación cuidadosa
                if isinstance(initial_value, models.Model):
                    initial_value = initial_value.pk
                if isinstance(current_value, models.Model):
                    current_value = current_value.pk
                if current_value != initial_value:
                    field_label = form.fields[field].label if field in form.fields and form.fields[field].label else field
                    campos_cambiados.append(field_label)

            if campos_cambiados:
                try:
                    self.enviar_notificacion_actualizacion(
                        objeto_antes, self.object, campos_cambiados)
                except Exception as e_notif:
                    logger.error(
                        f"Error enviando notificación de actualización para ContratoColectivo {self.object.pk}: {e_notif}")
        return response

    def enviar_notificacion_actualizacion(self, cont_antes, cont_despues, changed_data):
        if not changed_data:
            return
        mensaje = f"Contrato Colectivo {cont_despues.numero_contrato or cont_despues.pk} actualizado. Cambios en: {', '.join(changed_data)}."
        destinatarios = list(Usuario.objects.filter(
            is_superuser=True, is_active=True))
        if cont_despues.intermediario and hasattr(cont_despues.intermediario, 'usuarios'):
            destinatarios.extend(
                list(cont_despues.intermediario.usuarios.filter(is_active=True)))
        if destinatarios:
            try:
                crear_notificacion(
                    list(set(destinatarios)), mensaje, tipo='info',
                    url_path_name='myapp:contrato_colectivo_detail', url_kwargs={'pk': cont_despues.pk}
                )
                logger.info(
                    f"Notificación enviada para actualización de ContratoColectivo {cont_despues.pk}")
            except NameError:
                logger.error(
                    "La función 'crear_notificacion' no está definida.")
            except Exception as e:
                logger.error(
                    f"Error al intentar enviar notificación para ContratoColectivo {cont_despues.pk}: {e}")


@method_decorator(csrf_protect, name='dispatch')
class ContratoColectivoDeleteView(BaseDeleteView):
    model = ContratoColectivo
    template_name = 'contrato_colectivo_confirm_delete.html'  # O tu genérico
    context_object_name = 'contrato'  # O 'object'
    permission_required = 'myapp.delete_contratocolectivo'
    success_url = reverse_lazy('myapp:contrato_colectivo_list')

    def can_delete(self, obj):  # Devuelve (bool, str)
        related_errors_details = []
        if hasattr(obj, 'factura_set') and obj.factura_set.exists():
            related_errors_details.append('facturas')
        if hasattr(obj, 'reclamacion_set') and obj.reclamacion_set.exists():
            related_errors_details.append('reclamaciones')
        # Usar el related_name correcto para el M2M con AfiliadoColectivo
        if hasattr(obj, 'afiliados_colectivos') and obj.afiliados_colectivos.exists():
            related_errors_details.append('afiliados colectivos asignados')

        if related_errors_details:
            return False, f"No se puede eliminar '{obj}': tiene {', '.join(related_errors_details)} vinculados."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        context['page_title'] = f"Confirmar Eliminación CC: {self.object.numero_contrato}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            try:
                return redirect(reverse('myapp:contrato_colectivo_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó Contrato Colectivo: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')
# ==========================
# Intermediario Vistas
# ==========================


class IntermediarioListView(LoginRequiredMixin, ListView):
    model = Intermediario
    template_name = 'intermediario_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODOS los intermediarios activos. DataTables se encargará del resto.
        """
        # Usamos el manager 'objects' que ya filtra por activo=True
        return Intermediario.objects.all()

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto, manejando errores de desencriptación de forma segura.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Intermediarios"

        object_list_safe = []
        for obj in context['object_list']:
            try:
                # Forzamos la desencriptación de un campo para probar si el registro es válido
                str(obj.nombre_completo)
                obj.decryption_error = False
            except Exception:
                obj.decryption_error = True
            object_list_safe.append(obj)

        context['object_list'] = object_list_safe
        return context


class IntermediarioDetailView(BaseDetailView):
    model = Intermediario
    template_name = 'intermediario_detail.html'
    # La plantilla usa 'intermediario' y 'object'
    context_object_name = 'intermediario'
    permission_required = 'myapp.view_intermediario'
    model_manager_name = 'all_objects'

    def get_context_data(self, **kwargs):
        # Obtenemos el contexto base, que ya incluye el objeto 'intermediario'
        context = super().get_context_data(**kwargs)
        intermediario = self.object

        # --- LÓGICA DIRECTA Y CLARA PARA OBTENER COMISIONES ---

        # 1. Obtenemos las comisiones pagadas para ESTE intermediario
        comisiones_pagadas = RegistroComision.objects.filter(
            intermediario=intermediario,
            estatus_pago_comision='PAGADA'
        ).select_related('factura_origen').order_by('-fecha_pago_a_intermediario')

        # 2. Obtenemos las comisiones pendientes para ESTE intermediario
        comisiones_pendientes = RegistroComision.objects.filter(
            intermediario=intermediario,
            estatus_pago_comision='PENDIENTE'
        ).select_related('factura_origen').order_by('fecha_calculo')

        # 3. Calculamos los totales a partir de estos querysets
        total_pagado = comisiones_pagadas.aggregate(
            total=Sum('monto_comision')
        )['total'] or Decimal('0.00')

        total_pendiente = comisiones_pendientes.aggregate(
            total=Sum('monto_comision')
        )['total'] or Decimal('0.00')

        total_generado = total_pagado + total_pendiente

        # --- PASAMOS TODO AL CONTEXTO ---
        context['comisiones_pagadas'] = comisiones_pagadas
        context['comisiones_pendientes'] = comisiones_pendientes
        context['total_comisiones_generadas'] = total_generado
        context['total_comisiones_pagadas'] = total_pagado
        context['total_comisiones_pendientes'] = total_pendiente

        # --- MANTENEMOS LA LÓGICA ORIGINAL PARA OTRAS RELACIONES ---
        # (Si aún la necesitas en la plantilla)
        context['contratos_individuales_asociados'] = intermediario.contratoindividual_set.all()
        context['contratos_colectivos_asociados'] = intermediario.contratos_colectivos.all()
        context['usuarios_asociados'] = intermediario.usuarios.all()

        # Permisos para los enlaces de acciones en las tablas
        context['user_perms'] = {
            'can_view_comisiones': self.request.user.has_perm('myapp.view_registrocomision'),
            'can_view_facturas': self.request.user.has_perm('myapp.view_factura'),
        }

        return context


@method_decorator(csrf_protect, name='dispatch')
class IntermediarioCreateView(BaseCreateView):
    model = Intermediario
    model_manager_name = 'all_objects'
    form_class = IntermediarioForm
    template_name = 'intermediario_form.html'
    permission_required = 'myapp.add_intermediario'
    success_url = reverse_lazy('myapp:intermediario_list')

    # form_valid heredado

    def enviar_notificacion_creacion(self, intermediario):
        mensaje = f"Nuevo Intermediario registrado: {intermediario.nombre_completo} (Código: {intermediario.codigo})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='success',
                               url_path_name='myapp:intermediario_detail', url_kwargs={'pk': intermediario.pk})


@method_decorator(csrf_protect, name='dispatch')
class IntermediarioUpdateView(BaseUpdateView):
    model = Intermediario
    model_manager_name = 'all_objects'
    form_class = IntermediarioForm
    template_name = 'intermediario_form.html'
    context_object_name = 'intermediario'
    permission_required = 'myapp.change_intermediario'
    success_url = reverse_lazy('myapp:intermediario_list')

    # form_valid heredado

    def enviar_notificacion_actualizacion(self, int_antes, int_despues, changed_data):
        if not changed_data:
            return
        mensaje = f"Intermediario {int_despues.nombre_completo} actualizado. Cambios: {', '.join(changed_data)}."
        destinatarios = list(Usuario.objects.filter(
            is_superuser=True, is_active=True))
        if hasattr(int_despues, 'usuarios'):
            destinatarios.extend(
                list(int_despues.usuarios.filter(is_active=True)))
        if destinatarios:
            crear_notificacion(list(set(destinatarios)), mensaje, tipo='info',
                               url_path_name='myapp:intermediario_detail', url_kwargs={'pk': int_despues.pk})


@method_decorator(csrf_protect, name='dispatch')
class IntermediarioDeleteView(BaseDeleteView):
    model = Intermediario
    template_name = 'intermediario_confirm_delete.html'  # O tu genérico
    context_object_name = 'intermediario'  # O 'object'
    permission_required = 'myapp.delete_intermediario'
    success_url = reverse_lazy('myapp:intermediario_list')

    def can_delete(self, obj):  # Devuelve (bool, str)
        # 'contratos_colectivos' es el related_name
        if obj.contratoindividual_set.exists() or obj.contratos_colectivos.exists():
            return False, "No se puede eliminar: tiene contratos asociados."
        if hasattr(obj, 'sub_intermediarios') and obj.sub_intermediarios.exists():
            return False, "No se puede eliminar: tiene sub-intermediarios asociados."
        # 'usuarios_asignados' es el related_name en Usuario
        if hasattr(obj, 'usuarios_asignados') and obj.usuarios_asignados.exists():
            return False, "No se puede eliminar: tiene usuarios del sistema asociados."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        context['page_title'] = f"Confirmar Eliminación Intermediario: {self.object.nombre_completo}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            try:
                return redirect(reverse('myapp:intermediario_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó Intermediario: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')

# ==========================
# Reclamacion Vistas
# ==========================


class ReclamacionListView(LoginRequiredMixin, ListView):
    """
    Vista para listar todas las Reclamaciones.
    Diseñada para funcionar con DataTables del lado del cliente.
    Hereda directamente de las clases de Django para máxima estabilidad.
    """
    model = Reclamacion
    template_name = 'reclamacion_list.html'
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODAS las reclamaciones, optimizadas para la tabla.
        DataTables se encargará de la paginación y el filtrado en el frontend.
        """
        return Reclamacion.objects.select_related(
            'contrato_individual__afiliado',
            'contrato_colectivo',
            'usuario_asignado'
        ).order_by('-fecha_reclamo')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para la plantilla.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Reclamaciones"

        # Mapa de colores para los badges de estado
        context['estado_badge_map'] = {
            'ABIERTA': 'badge-info',
            'EN_PROCESO': 'badge-info',
            'EN_ANALISIS': 'badge-info',
            'PENDIENTE_DOCS': 'badge-warning',
            'ESCALADA': 'badge-warning',
            'INVESTIGACION': 'badge-warning',
            'EN_ARBITRAJE': 'badge-warning',
            'APROBADA': 'badge-success',
            'CERRADA': 'badge-secondary',
            'RECHAZADA': 'badge-danger',
            'SUSPENDIDA': 'badge-danger',
        }
        return context


class ReclamacionDetailView(BaseDetailView):
    model = Reclamacion
    model_manager_name = 'all_objects'
    template_name = 'reclamacion_detail.html'
    context_object_name = 'reclamacion'  # Usar 'reclamacion' consistentemente
    permission_required = 'myapp.view_reclamacion'

    def get_queryset(self):
        """ Optimiza consulta incluyendo todas las relaciones necesarias. """
        queryset = super().get_queryset()
        return queryset.select_related(
            # Cargar contrato y sus relaciones importantes
            'contrato_individual__afiliado',
            'contrato_individual__intermediario',
            'contrato_colectivo__intermediario',
            'usuario_asignado'  # Usuario asignado a la reclamación
        ).prefetch_related(
            # Precargar pagos activos para la reclamación
            Prefetch('pagos', queryset=Pago.objects.filter(
                activo=True).order_by('-fecha_pago'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reclamacion = self.object  # El objeto ya está en el contexto

        # --- Determinar Contrato, Afiliado/Cliente e Intermediario ---
        contrato_vinculado = reclamacion.contrato_individual or reclamacion.contrato_colectivo
        afiliado_final_obj = None
        cliente_final_nombre = "(No determinado)"
        intermediario_obj = None
        intermediario_nombre = "No asignado"
        intermediario_url = None
        contrato_url = None
        contrato_display = "⚠️ No asociado a un contrato."  # Mensaje por defecto

        if contrato_vinculado:
            # Usar __str__ por defecto
            contrato_display = str(contrato_vinculado)
            intermediario_obj = contrato_vinculado.intermediario

            if isinstance(contrato_vinculado, ContratoIndividual):
                if contrato_vinculado.afiliado:
                    afiliado_final_obj = contrato_vinculado.afiliado
                    cliente_final_nombre = getattr(
                        afiliado_final_obj, 'nombre_completo', str(afiliado_final_obj))
                try:
                    contrato_url = reverse('myapp:contrato_individual_detail', kwargs={
                                           'pk': contrato_vinculado.pk})
                except NoReverseMatch:
                    logger.warning(
                        f"URL 'contrato_individual_detail' no encontrada para PK {contrato_vinculado.pk}")
                    contrato_url = None
            elif isinstance(contrato_vinculado, ContratoColectivo):
                # Para colectivo, el "cliente" es la razón social del contrato
                afiliado_final_obj = contrato_vinculado  # Referenciar el contrato
                cliente_final_nombre = getattr(
                    afiliado_final_obj, 'razon_social', str(afiliado_final_obj))
                try:
                    contrato_url = reverse('myapp:contrato_colectivo_detail', kwargs={
                                           'pk': contrato_vinculado.pk})
                except NoReverseMatch:
                    logger.warning(
                        f"URL 'contrato_colectivo_detail' no encontrada para PK {contrato_vinculado.pk}")
                    contrato_url = None

            # Preparar datos del intermediario si existe
            if intermediario_obj:
                intermediario_nombre = getattr(
                    intermediario_obj, 'nombre_completo', str(intermediario_obj))
                try:
                    intermediario_url = reverse('myapp:intermediario_detail', kwargs={
                                                'pk': intermediario_obj.pk})
                except NoReverseMatch:
                    logger.warning(
                        f"URL 'intermediario_detail' no encontrada para PK {intermediario_obj.pk}")
                    intermediario_url = None

        # --- Cálculos de Pagos y Pendiente de la Reclamación ---
        pagos_list = list(reclamacion.pagos.all())  # Usar los pagos prefetched
        total_pagado_reclamacion = sum(
            p.monto_pago for p in pagos_list if p.monto_pago) or Decimal('0.00')
        monto_pendiente_reclamacion = max(Decimal(
            '0.00'), (reclamacion.monto_reclamado or Decimal('0.00')) - total_pagado_reclamacion)

        # --- Cálculo Días en Proceso ---
        dias_proceso = None
        hoy = django_timezone.now().date()
        if reclamacion.fecha_reclamo:
            fecha_inicio_calculo = reclamacion.fecha_reclamo
            # Usar hoy si no está cerrada
            fecha_fin_calculo = reclamacion.fecha_cierre_reclamo or hoy

            if isinstance(fecha_inicio_calculo, datetime):
                fecha_inicio_calculo = fecha_inicio_calculo.date()
            if isinstance(fecha_fin_calculo, datetime):
                fecha_fin_calculo = fecha_fin_calculo.date()

            if isinstance(fecha_inicio_calculo, date) and isinstance(fecha_fin_calculo, date) and fecha_fin_calculo >= fecha_inicio_calculo:
                dias_proceso = (fecha_fin_calculo - fecha_inicio_calculo).days

        # --- Actualizar Contexto Final ---
        context.update({
            # 'reclamacion' ya está por context_object_name
            'tipo_reclamacion_display': reclamacion.get_tipo_reclamacion_display(),
            'estado_display': reclamacion.get_estado_display(),
            # Asumiendo que existe get_..._display
            'diagnostico_display': reclamacion.get_diagnostico_principal_display(),

            # Datos Asociados Corregidos
            'contrato_asociado_display': contrato_display,
            'contrato_asociado_url': contrato_url,
            'afiliado_final_display': cliente_final_nombre,  # Renombrado para claridad
            'intermediario_final_nombre': intermediario_nombre,  # Renombrado
            'intermediario_final_url': intermediario_url,  # URL para enlace

            # Pagos
            'pagos_asociados': pagos_list,
            'total_pagado_reclamacion': total_pagado_reclamacion,
            'monto_pendiente_reclamacion': monto_pendiente_reclamacion,

            # Otros Cálculos
            'dias_en_proceso': dias_proceso,
            # Añadir ANULADA si existe
            'esta_cerrada': reclamacion.estado in ['CERRADA', 'PAGADA', 'RECHAZADA', 'ANULADA'],

            'active_tab': 'reclamaciones_detail',  # O la clave que uses
        })
        return context


@method_decorator(csrf_protect, name='dispatch')
class ReclamacionCreateView(BaseCreateView):
    model = Reclamacion
    model_manager_name = 'all_objects'
    form_class = ReclamacionForm
    template_name = 'reclamacion_form.html'
    permission_required = 'myapp.add_reclamacion'
    success_url = reverse_lazy('myapp:reclamacion_list')

    # form_valid heredado

    def enviar_notificacion_creacion(self, reclamacion):
        mensaje = f"Nueva Reclamación #{reclamacion.pk} registrada ({reclamacion.get_tipo_reclamacion_display()})."
        destinatarios = []
        url_k = {'pk': reclamacion.pk}
        if reclamacion.usuario_asignado:
            destinatarios.append(reclamacion.usuario_asignado)
        # Notificar admins siempre?
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(list(set(destinatarios)), mensaje, tipo='info',
                               url_path_name='myapp:reclamacion_detail', url_kwargs=url_k)


@method_decorator(csrf_protect, name='dispatch')
class ReclamacionUpdateView(BaseUpdateView):
    model = Reclamacion
    model_manager_name = 'all_objects'
    form_class = ReclamacionForm
    template_name = 'reclamacion_form.html'
    context_object_name = 'reclamacion'
    permission_required = 'myapp.change_reclamacion'
    success_url = reverse_lazy('myapp:reclamacion_list')

    # form_valid heredado

    def enviar_notificacion_actualizacion(self, rec_antes, rec_despues, changed_data):
        if not changed_data:
            return
        notificados_ya = set()
        url_k = {'pk': rec_despues.pk}
        url_name = 'myapp:reclamacion_detail'

        # Notificación cambio de estado
        if 'estado' in changed_data:
            estado_ant_str = dict(CommonChoices.ESTADO_RECLAMACION).get(
                rec_antes.estado, rec_antes.estado)
            estado_nue_str = rec_despues.get_estado_display()
            mensaje_estado = f"Estado Reclamación #{rec_despues.pk} cambió: {estado_ant_str} -> {estado_nue_str}."
            tipo_notif_estado = 'success' if rec_despues.estado in ['APROBADA', 'PAGADA'] else (
                'error' if rec_despues.estado == 'RECHAZADA' else 'info')
            dest_estado = []
            if rec_despues.usuario_asignado:
                dest_estado.append(rec_despues.usuario_asignado)
            # Añadir admins?
            dest_estado.extend(list(Usuario.objects.filter(
                is_superuser=True, is_active=True)))
            if dest_estado:
                crear_notificacion(list(set(dest_estado)), mensaje_estado,
                                   tipo=tipo_notif_estado, url_path_name=url_name, url_kwargs=url_k)
                for user in dest_estado:
                    notificados_ya.add(user.pk)

        # Notificación cambio de asignación
        if 'usuario_asignado' in changed_data:
            user_anterior = rec_antes.usuario_asignado
            user_nuevo = rec_despues.usuario_asignado
            contrato_str = rec_despues.get_contrato_asociado_display()
            if user_nuevo and user_nuevo.pk not in notificados_ya:
                mensaje_nuevo = f"Se te asignó la Reclamación #{rec_despues.pk} ({contrato_str})."
                crear_notificacion(
                    user_nuevo, mensaje_nuevo, tipo='info', url_path_name=url_name, url_kwargs=url_k)
            if user_anterior and user_anterior != user_nuevo and user_anterior.pk not in notificados_ya:
                mensaje_anterior = f"Ya no estás asignado a la Reclamación #{rec_despues.pk}."
                # Sin link quizás
                crear_notificacion(
                    user_anterior, mensaje_anterior, tipo='info')

        # Podrías añadir notificaciones para otros campos si son críticos


@method_decorator(csrf_protect, name='dispatch')
class ReclamacionDeleteView(BaseDeleteView):
    model = Reclamacion
    template_name = 'reclamacion_confirm_delete.html'  # O tu genérico
    context_object_name = 'reclamacion'  # O 'object'
    permission_required = 'myapp.delete_reclamacion'
    success_url = reverse_lazy('myapp:reclamacion_list')

    def can_delete(self, obj):  # Devuelve (bool, str)
        if hasattr(obj, 'pagos') and obj.pagos.exists():  # 'pagos' es el related_name
            return False, "No se puede eliminar esta reclamación: tiene pagos asociados."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        context['page_title'] = f"Confirmar Eliminación Reclamo: {self.object.numero_reclamacion or self.object.pk}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            try:
                return redirect(reverse('myapp:reclamacion_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, rec_pk, rec_repr):
        mensaje = f"Se eliminó la Reclamación: {rec_repr} (ID: {rec_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


class ReclamacionStatusAPIView(View):
    """
    API simple para obtener el estado actualizado de una reclamación.
    """

    def get(self, request, *args, **kwargs):
        reclamacion_pk = kwargs.get('pk')
        if not reclamacion_pk:
            return JsonResponse({'error': 'Falta el ID de la reclamación.'}, status=400)

        try:
            # Obtenemos la reclamación directamente de la BD para asegurar datos frescos
            reclamacion = Reclamacion.objects.get(pk=reclamacion_pk)

            # Devolvemos los datos que el frontend necesita para actualizar la UI
            data = {
                'pk': reclamacion.pk,
                'estado_valor': reclamacion.estado,  # Ej: 'PAGADA'
                'estado_display': reclamacion.get_estado_display(),  # Ej: 'Pagada'
            }
            return JsonResponse(data)

        except Reclamacion.DoesNotExist:
            return JsonResponse({'error': 'Reclamación no encontrada.'}, status=404)
        except Exception as e:
            logger.error(
                f"Error en ReclamacionStatusAPIView para PK {reclamacion_pk}: {e}")
            return JsonResponse({'error': 'Error interno del servidor.'}, status=500)

# ==========================
# Pago Vistas
# ==========================


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = 'pago_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODOS los pagos activos. DataTables se encargará del resto.
        Optimizamos la consulta para cargar las relaciones que se mostrarán en la tabla.
        """
        # Usamos el manager 'objects' que ya filtra por activo=True
        return Pago.objects.select_related(
            'reclamacion',
            'factura__contrato_individual',
            'factura__contrato_colectivo'
        )

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para la plantilla.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Pagos Registrados"

        object_list_safe = []
        for obj in context['object_list']:
            try:
                # Forzamos la desencriptación de un campo para probar si el registro es válido
                str(obj.referencia_pago)
                obj.decryption_error = False
            except Exception:
                obj.decryption_error = True
            object_list_safe.append(obj)

        context['object_list'] = object_list_safe
        return context


class PagoDetailView(BaseDetailView):  # Asegúrate que BaseDetailView esté definida
    model = Pago
    model_manager_name = 'all_objects'
    template_name = 'pago_detail.html'  # O el nombre que uses
    context_object_name = 'pago'  # O 'object'
    permission_required = 'myapp.view_pago'  # Permiso

    def get_queryset(self):
        """ Optimiza la consulta incluyendo relaciones clave """
        return super().get_queryset().select_related(
            # Navegar profundo si es factura individual
            'factura__contrato_individual__afiliado',
            'factura__contrato_colectivo',          # Si es factura colectiva
            'factura__intermediario',               # Intermediario de la factura
            # Navegar profundo si es reclamo individual
            'reclamacion__contrato_individual__afiliado',
            'reclamacion__contrato_colectivo',          # Si es reclamo colectivo
            # Intermediario podría venir del contrato asociado al reclamo también
            'reclamacion__contrato_individual__intermediario',
            'reclamacion__contrato_colectivo__intermediario',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pago = self.object

        factura_asociada = pago.factura
        reclamacion_asociada = pago.reclamacion

        contrato_vinculado = None
        cliente_final_obj = None
        intermediario_obj = None
        contrato_url = None      # <-- NUEVO: Para la URL del contrato
        # <-- NUEVO: Para el texto del contrato
        contrato_display = "(No determinado)"

        if factura_asociada:
            contrato_vinculado = factura_asociada.contrato_individual or factura_asociada.contrato_colectivo
            intermediario_obj = factura_asociada.intermediario
        elif reclamacion_asociada:
            contrato_vinculado = reclamacion_asociada.contrato_individual or reclamacion_asociada.contrato_colectivo

        if contrato_vinculado:
            # Usar __str__ para el display por defecto
            contrato_display = str(contrato_vinculado)
            # Determinar URL y cliente/intermediario basado en el TIPO de contrato
            if isinstance(contrato_vinculado, ContratoIndividual):
                cliente_final_obj = contrato_vinculado.afiliado
                if not intermediario_obj:
                    intermediario_obj = contrato_vinculado.intermediario
                # Generar URL para ContratoIndividualDetailView
                try:
                    contrato_url = reverse('myapp:contrato_individual_detail', kwargs={
                                           'pk': contrato_vinculado.pk})
                except Exception:  # NoReverseMatch si la URL no existe o falta argumento
                    contrato_url = None  # Fallback
            elif isinstance(contrato_vinculado, ContratoColectivo):
                cliente_final_obj = contrato_vinculado  # Usar el contrato como "cliente"
                if not intermediario_obj:
                    intermediario_obj = contrato_vinculado.intermediario
                # Generar URL para ContratoColectivoDetailView
                try:
                    contrato_url = reverse('myapp:contrato_colectivo_detail', kwargs={
                                           'pk': contrato_vinculado.pk})
                except Exception:
                    contrato_url = None

        # Preparar nombres y PKs para el template
        cliente_final_nombre = "(No determinado)"
        if isinstance(cliente_final_obj, AfiliadoIndividual):
            cliente_final_nombre = cliente_final_obj.nombre_completo
        elif isinstance(cliente_final_obj, (ContratoColectivo, AfiliadoColectivo)):
            cliente_final_nombre = cliente_final_obj.razon_social

        # Asegurarse de pasar el PK del intermediario
        intermediario_nombre = intermediario_obj.nombre_completo if intermediario_obj else "No asignado"
        intermediario_pk = intermediario_obj.pk if intermediario_obj else None
        intermediario_url = None
        if intermediario_pk:
            try:
                intermediario_url = reverse('myapp:intermediario_detail', kwargs={
                                            'pk': intermediario_pk})
            except Exception:
                intermediario_url = None

        context.update({
            'factura_asociada': factura_asociada,
            'reclamacion_asociada': reclamacion_asociada,
            # Datos del contrato vinculado
            'contrato_vinculado_display': contrato_display,  # Texto a mostrar
            'contrato_vinculado_url': contrato_url,         # URL para el enlace
            # Datos del cliente final
            'cliente_final_nombre': cliente_final_nombre,
            # Datos del intermediario
            'intermediario_asociado_nombre': intermediario_nombre,
            # URL para el enlace (PK ya no es necesario)
            'intermediario_asociado_url': intermediario_url,
            # Otros datos
            'forma_pago_display': pago.get_forma_pago_display(),
            'active_tab': 'pagos',
        })

        return context


class PagoCreateView(BaseCreateView):
    model = Pago
    form_class = PagoForm
    template_name = 'pago_form.html'
    permission_required = 'myapp.add_pago'

    def get_success_url(self):
        # Esta lógica de redirección es correcta
        if hasattr(self, 'object') and self.object:
            if self.object.factura:
                contrato = self.object.factura.get_contrato_asociado
                if isinstance(contrato, ContratoIndividual):
                    return reverse('myapp:contrato_individual_detail', kwargs={'pk': contrato.pk})
                if isinstance(contrato, ContratoColectivo):
                    return reverse('myapp:contrato_colectivo_detail', kwargs={'pk': contrato.pk})
            elif self.object.reclamacion:
                return reverse('myapp:reclamacion_detail', kwargs={'pk': self.object.reclamacion.pk})
        return reverse('myapp:pago_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)

        factura = self.object.factura
        reclamacion = self.object.reclamacion

        if not factura and not reclamacion:
            form.add_error(
                None, "Debe asociar el pago a una Factura o a una Reclamación.")
            return self.form_invalid(form)

        # --- CÁLCULO AUTOMÁTICO DEL MONTO DEL PAGO ---
        if factura:
            self.object.monto_pago = factura.monto_pendiente
        elif reclamacion:
            total_pagado = reclamacion.pagos.filter(activo=True).aggregate(
                total=Coalesce(Sum('monto_pago'), Decimal('0.00'))
            )['total']
            saldo_pendiente = (
                reclamacion.monto_reclamado or Decimal('0.00')) - total_pagado
            self.object.monto_pago = max(Decimal('0.00'), saldo_pendiente)

        return super().form_valid(form)

    def enviar_notificacion_creacion(self, pago):
        """
        Envía una notificación tras la creación exitosa de un pago.
        """
        if pago.factura:
            contrato = pago.factura.get_contrato_asociado
            asociacion_str = f"para la factura {pago.factura.numero_recibo}"
            url_destino = reverse('myapp:factura_detail',
                                  kwargs={'pk': pago.factura.pk})
        elif pago.reclamacion:
            contrato = pago.reclamacion.contrato_individual or pago.reclamacion.contrato_colectivo
            asociacion_str = f"para la reclamación #{pago.reclamacion.pk}"
            url_destino = reverse('myapp:reclamacion_detail', kwargs={
                                  'pk': pago.reclamacion.pk})
        else:
            contrato = None
            asociacion_str = "sin una asociación clara"
            url_destino = reverse('myapp:pago_detail', kwargs={'pk': pago.pk})

        mensaje = f"Nuevo pago de ${pago.monto_pago:.2f} (Ref: {pago.referencia_pago or pago.pk}) se ha registrado {asociacion_str}."

        # Definir destinatarios
        destinatarios = set(Usuario.objects.filter(
            is_staff=True, is_active=True))
        if contrato and contrato.intermediario:
            for user in contrato.intermediario.usuarios_asignados.filter(is_active=True):
                destinatarios.add(user)

        if destinatarios:
            crear_notificacion(
                usuario_destino=list(destinatarios),
                mensaje=mensaje,
                tipo='success',
                url_destino=url_destino
            )


class PagoUpdateView(BaseUpdateView):
    model = Pago
    model_manager_name = 'all_objects'
    form_class = PagoForm
    template_name = 'pago_form.html'
    context_object_name = 'pago'
    permission_required = 'myapp.change_pago'

    def get_success_url(self):
        return reverse('myapp:pago_detail', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.object:
            # Pre-llenamos el campo de monto para que se muestre en el widget readonly
            form.fields['monto_pago'].initial = self.object.monto_pago
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pago = self.object

        info_label = ""
        saldo_pendiente = Decimal('0.00')

        if pago.factura:
            info_label = f"Factura {pago.factura.numero_recibo}"
            # El saldo pendiente de la factura ya está calculado en el modelo
            saldo_pendiente = pago.factura.monto_pendiente
        elif pago.reclamacion:
            info_label = f"Reclamación #{pago.reclamacion.pk}"
            # Calculamos el saldo que había ANTES de este pago
            total_pagado_otros = pago.reclamacion.pagos.filter(activo=True).exclude(pk=pago.pk).aggregate(
                total=Coalesce(Sum('monto_pago'), Decimal('0.00'))
            )['total']
            saldo_pendiente = (pago.reclamacion.monto_reclamado or Decimal(
                '0.00')) - total_pagado_otros

        context['info_label'] = info_label
        context['saldo_pendiente_valor'] = f"${saldo_pendiente:,.2f}"

        context['form_title'] = f"Editar Pago ID: {pago.pk}"
        return context

    def enviar_notificacion_actualizacion(self, pago_antes, pago_despues, changed_data):
        if not changed_data:
            return
        mensaje = f"Pago (Ref: {pago_despues.referencia_pago or pago_despues.pk}) act. Campos: {', '.join(changed_data)}."
        destinatarios = []
        # Lógica similar a la de creación para destinatarios
        if pago_despues.reclamacion and pago_despues.reclamacion.usuario_asignado:
            destinatarios.append(pago_despues.reclamacion.usuario_asignado)
        elif pago_despues.factura and pago_despues.factura.intermediario and hasattr(pago_despues.factura.intermediario, 'usuarios'):
            destinatarios.extend(
                list(pago_despues.factura.intermediario.usuarios.filter(is_active=True)))
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(list(set(destinatarios)), mensaje, tipo='info',
                               url_path_name='myapp:pago_detail', url_kwargs={'pk': pago_despues.pk})

# myapp/views.py


@login_required
@require_GET
def get_item_financial_info(request):
    """
    API para obtener el saldo pendiente de una Factura o una Reclamación.
    Usado en el formulario de creación de Pago.
    """
    factura_id = request.GET.get('factura_id')
    reclamacion_id = request.GET.get('reclamacion_id')

    if not factura_id and not reclamacion_id:
        return JsonResponse({'error': 'Debe proporcionar un ID de factura o reclamación.'}, status=400)

    try:
        if factura_id:
            factura = get_object_or_404(Factura, pk=int(factura_id))
            saldo_pendiente = factura.monto_pendiente
            monto_sugerido = saldo_pendiente
            info_label = f"Factura {factura.numero_recibo}"

        elif reclamacion_id:
            reclamacion = get_object_or_404(
                Reclamacion.objects.prefetch_related('pagos'), pk=int(reclamacion_id))
            total_pagado = reclamacion.pagos.filter(activo=True).aggregate(
                total=Coalesce(Sum('monto_pago'), Decimal('0.00'))
            )['total']
            saldo_pendiente = (
                reclamacion.monto_reclamado or Decimal('0.00')) - total_pagado
            monto_sugerido = max(Decimal('0.00'), saldo_pendiente)
            info_label = f"Reclamación #{reclamacion.pk}"

        return JsonResponse({
            'info_label': info_label,
            'saldo_pendiente': f"{saldo_pendiente:,.2f}",
            'monto_sugerido': f"{monto_sugerido:.2f}",
        })

    except (ValueError, TypeError):
        return JsonResponse({'error': 'ID inválido.'}, status=400)
    except Http404:
        return JsonResponse({'error': 'El objeto no fue encontrado.'}, status=404)
    except Exception as e:
        logger.error(f"Error en get_item_financial_info: {e}", exc_info=True)
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)


@method_decorator(csrf_protect, name='dispatch')
class PagoDeleteView(BaseDeleteView):
    model = Pago
    template_name = 'pago_confirm_delete.html'
    context_object_name = 'pago'  # O 'object'
    permission_required = 'myapp.delete_pago'
    success_url = reverse_lazy('myapp:pago_list')

    # Si no hay restricciones adicionales para borrar un Pago, no necesitas can_delete.
    # El método post personalizado que tenías es para asegurar que Pago.delete() se llame
    # si tiene lógica especial. Si BaseDeleteView.post() ya llama a self.object.delete(),
    # y eso es suficiente, puedes eliminar este método post personalizado.

    # Manteniendo tu post personalizado por si Pago.delete() tiene lógica importante:
    def post(self, request, *args, **kwargs):
        object_pk_for_audit = None
        object_repr_for_audit = "Objeto Pago Desconocido"
        try:
            self.object = self.get_object()
            object_pk_for_audit = self.object.pk
            object_repr_for_audit = str(self.object)

            with transaction.atomic():
                self.object.delete()  # Llama al delete del modelo Pago

            messages.success(
                request, f"Pago '{object_repr_for_audit}' eliminado y saldos actualizados correctamente.")
            # Asumo que _create_audit_entry está en BaseDeleteView o es un helper accesible
            if hasattr(self, '_create_audit_entry'):
                self._create_audit_entry(
                    request, 'ELIMINACION', 'EXITO', f"Eliminación de Pago", object_pk_for_audit, object_repr_for_audit)

            if hasattr(self, 'enviar_notificacion_eliminacion'):
                self.enviar_notificacion_eliminacion(
                    object_pk_for_audit, object_repr_for_audit)

            return HttpResponseRedirect(self.get_success_url())

        except ProtectedError as e:
            logger.warning(
                f"ProtectedError al eliminar Pago {object_pk_for_audit}: {e}")
            messages.error(
                request, f"No se puede eliminar '{object_repr_for_audit}': tiene registros asociados protegidos.")
            if hasattr(self, '_create_audit_entry'):
                self._create_audit_entry(
                    request, 'ELIMINACION', 'ERROR', f"ProtectedError: {e}", object_pk_for_audit, object_repr_for_audit)
            try:
                return redirect(reverse('myapp:pago_detail', kwargs={'pk': object_pk_for_audit}))
            except NoReverseMatch:
                return redirect(self.get_success_url())
        except self.model.DoesNotExist:
            logger.warning(
                f"Intento de eliminar Pago inexistente (kwargs={kwargs}) por {request.user}.")
            messages.error(
                request, "Error: El pago que intenta eliminar no existe.")
            return redirect(self.get_success_url())
        except Exception as e:
            current_pk = object_pk_for_audit if 'object_pk_for_audit' in locals(
            ) else self.kwargs.get('pk', 'N/A')
            logger.error(
                f"Error inesperado al eliminar Pago PK={current_pk}: {e}", exc_info=True)
            messages.error(
                request, f"Error inesperado al intentar eliminar el pago: {str(e)}")
            if hasattr(self, '_create_audit_entry'):
                self._create_audit_entry(
                    request, 'ELIMINACION', 'ERROR', f"Error inesperado: {str(e)[:200]}", current_pk)
            try:
                return redirect(reverse('myapp:pago_detail', kwargs={'pk': current_pk}))
            except:  # Captura más genérica para el redirect
                return redirect(self.get_success_url())

    def enviar_notificacion_eliminacion(self, pago_pk, pago_repr):
        mensaje = f"Se eliminó Pago: {pago_repr} (ID: {pago_pk}). Los saldos asociados fueron recalculados."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


# ==========================
# Tarifa Vistas
# ==========================


class TarifaListView(LoginRequiredMixin, ListView):
    model = Tarifa
    template_name = 'tarifa_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODAS las tarifas activas. DataTables se encargará del resto.
        """
        # Usamos el manager 'objects' que ya filtra por activo=True
        return Tarifa.objects.all()

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto. No hay campos cifrados en Tarifa, así que es más simple.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Tarifas"
        return context


class TarifaDetailView(BaseDetailView):
    model = Tarifa
    model_manager_name = 'all_objects'
    template_name = 'tarifa_detail.html'
    context_object_name = 'tarifa'  # Usa 'tarifa' consistentemente con tu plantilla
    permission_required = 'myapp.view_tarifa'

    # --- NUEVO: get_queryset con prefetch ---
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related(
            # Prefetch optimizado para mostrar info relevante en la tabla de detalle
            Prefetch('contratoindividual_set',
                     queryset=ContratoIndividual.objects.select_related(
                         'afiliado'  # Cargar afiliado para mostrar nombre
                     ).only(  # Cargar solo campos necesarios
                         'pk', 'numero_contrato', 'afiliado_id',  # FK es necesaria
                         # Añade campos del Afiliado si los muestras directamente en la tabla
                         'monto_total', 'estatus', 'fecha_inicio_vigencia', 'afiliado__primer_nombre', 'afiliado__primer_apellido'
                         # Ordenar como desees
                     ).order_by('-fecha_inicio_vigencia'),
                     # Opcional: nombre de atributo personalizado
                     to_attr='contratos_ind_relacionados'),

            Prefetch('contratocolectivo_set',
                     queryset=ContratoColectivo.objects.only(  # Cargar solo campos necesarios
                         'pk', 'numero_contrato', 'razon_social',
                         'monto_total', 'estatus', 'fecha_inicio_vigencia'
                         # Ordenar como desees
                     ).order_by('-fecha_inicio_vigencia'),
                     to_attr='contratos_col_relacionados')  # Opcional
        )
    # --- FIN get_queryset ---

    # --- get_context_data CORREGIDO ---
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tarifa = self.object  # 'tarifa' porque context_object_name es 'tarifa'

        # Acceder a los contratos prefetched usando related_name o el atributo 'to_attr' si se definió
        # Usando related_name (por defecto o el definido con %class%):
        contratos_ind_asociados = list(tarifa.contratoindividual_set.all())
        contratos_col_asociados = list(tarifa.contratocolectivo_set.all())
        # O si usaste to_attr en prefetch:
        # contratos_ind_asociados = list(getattr(tarifa, 'contratos_ind_relacionados', []))
        # contratos_col_asociados = list(getattr(tarifa, 'contratos_col_relacionados', []))

        context.update({
            'ramo_display': tarifa.get_ramo_display(),
            'rango_etario_display': tarifa.get_rango_etario_display(),
            # Pasar las listas correctas a la plantilla
            'contratos_individuales_asociados': contratos_ind_asociados,
            'contratos_colectivos_asociados': contratos_col_asociados,
            'total_contratos_individuales': len(contratos_ind_asociados),
            'total_contratos_colectivos': len(contratos_col_asociados),
            'active_tab': 'tarifas_detail',  # O lo que uses
            'ramos_choices': CommonChoices.RAMO,
            'rangos_etarios_choices': CommonChoices.RANGO_ETARIO,
        })
        return context


@method_decorator(csrf_protect, name='dispatch')
class TarifaCreateView(BaseCreateView):
    model = Tarifa
    model_manager_name = 'all_objects'
    template_name = 'tarifa_form.html'
    permission_required = 'myapp.add_tarifa'
    form_class = TarifaForm
    success_url = reverse_lazy('myapp:tarifa_list')

    # form_valid heredado

    def enviar_notificacion_creacion(self, tarifa):
        mensaje = f"Nueva Tarifa creada: Ramo={tarifa.get_ramo_display()}, Rango={tarifa.get_rango_etario_display()}, Fecha={tarifa.fecha_aplicacion}."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='info',
                               url_path_name='myapp:tarifa_detail', url_kwargs={'pk': tarifa.pk})


@method_decorator(csrf_protect, name='dispatch')
class TarifaUpdateView(BaseUpdateView):
    model = Tarifa
    model_manager_name = 'all_objects'
    template_name = 'tarifa_form.html'
    context_object_name = 'tarifa'
    permission_required = 'myapp.change_tarifa'
    form_class = TarifaForm
    success_url = reverse_lazy('myapp:tarifa_list')

    # form_valid heredado

    def enviar_notificacion_actualizacion(self, tar_antes, tar_despues, changed_data):
        if not changed_data:
            return
        mensaje = f"Tarifa {tar_despues.pk} actualizada. Cambios: {', '.join(changed_data)}."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='info',
                               url_path_name='myapp:tarifa_detail', url_kwargs={'pk': tar_despues.pk})


@method_decorator(csrf_protect, name='dispatch')
class TarifaDeleteView(BaseDeleteView):
    model = Tarifa
    template_name = 'tarifa_confirm_delete.html'
    context_object_name = 'object'
    permission_required = 'myapp.delete_tarifa'
    success_url = reverse_lazy('myapp:tarifa_list')

    def can_delete(self, obj):  # Renombrado para consistencia, devuelve (bool, str)
        en_uso_individual = ContratoIndividual.objects.filter(
            tarifa_aplicada=obj).exists()
        en_uso_colectivo = ContratoColectivo.objects.filter(
            tarifa_aplicada=obj).exists()
        if en_uso_individual or en_uso_colectivo:
            return False, "No se puede eliminar la Tarifa porque está asignada a uno o más contratos."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        # El template de tarifa ya usa 'tarifa_en_uso', así que podemos mantenerlo o cambiarlo
        context['tarifa_en_uso'] = not can_delete_flag
        context['page_title'] = f"Confirmar Eliminación Tarifa: {self.object.codigo_tarifa}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            try:
                return redirect(reverse('myapp:tarifa_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó la Tarifa: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


class RegistroComisionListView(LoginRequiredMixin, ListView):
    model = RegistroComision
    template_name = 'registro_comision_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODOS los registros de comisiones. DataTables se encargará del resto.
        """
        # Optimizamos la consulta para cargar todas las relaciones necesarias
        return RegistroComision.objects.select_related(
            'intermediario',
            'contrato_individual',
            'contrato_colectivo',
            'pago_cliente',
            'factura_origen',
            'intermediario_vendedor',
            'usuario_que_liquido'
        ).order_by('-fecha_calculo')  # Un orden por defecto razonable

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para la plantilla.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Comisiones Registradas"
        # Este modelo no tiene campos cifrados, no se necesita bucle de seguridad.
        return context


class RegistroComisionDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = RegistroComision
    model_manager_name = 'all_objects'
    template_name = 'registro_comision_detail.html'
    context_object_name = 'comision'
    permission_required = 'myapp.view_registro_comision'

    def get_queryset(self):
        # Optimizar la consulta para incluir objetos relacionados
        return super().get_queryset().select_related(
            'intermediario',
            'factura_origen',
            'pago_cliente',
            'contrato_individual',
            'contrato_colectivo',
            'intermediario_vendedor',
            'usuario_que_liquido'  # Incluir el nuevo campo
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Detalle Comisión #{self.object.pk}"
        context['active_tab'] = "comisiones"
        return context


# Función helper para ordenar una lista de diccionarios (si es necesario para totales)
def sort_list_of_dicts(list_of_dicts, sort_key, reverse=False):
    # Simple sort, puede necesitar manejo de errores para claves no existentes
    try:
        return sorted(list_of_dicts, key=lambda x: x.get(sort_key, 0), reverse=reverse)
    except TypeError:  # Si intentas ordenar tipos mixtos (ej. Decimal y None)
        # Intenta un ordenamiento más robusto, tratando None como 0 o un valor muy bajo/alto
        return sorted(list_of_dicts, key=lambda x: x.get(sort_key) if x.get(sort_key) is not None else Decimal('-Infinity' if reverse else 'Infinity'), reverse=reverse)


class MisComisionesListView(LoginRequiredMixin, ListView):
    model = RegistroComision
    template_name = 'mis_comisiones_list.html'
    context_object_name = 'comisiones'

    def get_queryset(self):
        user = self.request.user
        intermediario_del_usuario = user.intermediario if hasattr(
            user, 'intermediario') else None

        if not intermediario_del_usuario:
            # Intentar buscar por la relación inversa si no está directa
            try:
                intermediario_del_usuario = Intermediario.objects.get(
                    usuarios=user)
            except (Intermediario.DoesNotExist, Intermediario.MultipleObjectsReturned):
                messages.warning(
                    self.request, "No se encontró un intermediario único asociado a tu cuenta.")
                return RegistroComision.objects.none()

        # Devolvemos el queryset completo para el intermediario. DataTables hará el resto.
        return RegistroComision.objects.filter(
            Q(intermediario=intermediario_del_usuario) |
            Q(intermediario_vendedor__intermediario_relacionado=intermediario_del_usuario,
              tipo_comision='OVERRIDE')
        ).select_related(
            'intermediario', 'factura_origen', 'pago_cliente',
            'intermediario_vendedor', 'usuario_que_liquido'
        ).distinct().order_by('-fecha_calculo')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Mis Comisiones"
        return context


@login_required
def liquidacion_comisiones_view(request):
    # La lógica de búsqueda y ordenamiento ahora la hará DataTables en el frontend.
    # La vista solo necesita calcular los saldos y pasar los datos.

    base_intermediarios_qs = Intermediario.objects.filter(activo=True)

    intermediarios_con_saldos = base_intermediarios_qs.annotate(
        total_directa_pendiente_db=Coalesce(Sum(Case(When(comisiones_ganadas__tipo_comision='DIRECTA', comisiones_ganadas__estatus_pago_comision='PENDIENTE',
                                            then='comisiones_ganadas__monto_comision'), default=Value(Decimal('0.00')))), Value(Decimal('0.00'))),
        total_override_pendiente_db=Coalesce(Sum(Case(When(comisiones_ganadas__tipo_comision='OVERRIDE', comisiones_ganadas__estatus_pago_comision='PENDIENTE',
                                             then='comisiones_ganadas__monto_comision'), default=Value(Decimal('0.00')))), Value(Decimal('0.00')))
    ).annotate(
        total_general_pendiente_db=F(
            'total_directa_pendiente_db') + F('total_override_pendiente_db')
    ).distinct()

    # Filtramos para mostrar solo los que tienen saldo pendiente
    intermediarios_final_qs = intermediarios_con_saldos.filter(
        total_general_pendiente_db__gt=Decimal('0.00')
    ).prefetch_related(
        Prefetch('comisiones_ganadas',
                 queryset=RegistroComision.objects.filter(estatus_pago_comision='PENDIENTE').select_related(
                     'factura_origen', 'pago_cliente', 'intermediario_vendedor'),
                 to_attr='comisiones_pendientes_para_modal')
    )

    context = {
        'title': 'Liquidación de Comisiones Pendientes',
        'page_heading': '💸 Liquidación de Comisiones Pendientes por Intermediario',
        'liquidacion_data': intermediarios_final_qs,
    }
    return render(request, 'liquidacion_comisiones.html', context)


# myapp/views.py

@login_required
def marcar_comisiones_pagadas_view(request):
    if request.method != 'POST':
        messages.error(request, "Acción no permitida (solo se acepta POST).")
        return redirect('myapp:liquidacion_comisiones')

    comisiones_ids_str = request.POST.getlist('comisiones_a_pagar_ids')
    fecha_pago_str = request.POST.get('fecha_pago_efectiva')
    comprobante_archivo = request.FILES.get('comprobante_pago_liquidacion')

    if not comisiones_ids_str:
        messages.warning(
            request, "No se seleccionaron comisiones para liquidar.")
        return redirect('myapp:liquidacion_comisiones')

    try:
        comisiones_ids_int = [int(id_str) for id_str in comisiones_ids_str]
    except ValueError:
        messages.error(request, "La selección de comisiones es inválida.")
        return redirect('myapp:liquidacion_comisiones')

    fecha_pago = django_timezone.now().date()
    if fecha_pago_str:
        try:
            fecha_pago = datetime.strptime(fecha_pago_str, '%d/%m/%Y').date()
            if fecha_pago > django_timezone.now().date():
                messages.warning(
                    request, "La fecha de pago no puede ser futura. Se usará la fecha actual.")
                fecha_pago = django_timezone.now().date()
        except ValueError:
            messages.error(
                request, "Formato de fecha de pago inválido (DD/MM/AAAA). Se usará la fecha actual.")

    comisiones_a_liquidar = list(RegistroComision.objects.filter(
        id__in=comisiones_ids_int,
        estatus_pago_comision='PENDIENTE'
    ).select_related('intermediario'))

    if not comisiones_a_liquidar:
        messages.warning(
            request, "No se encontraron comisiones pendientes válidas en la selección.")
        return redirect('myapp:liquidacion_comisiones')

    comisiones_actualizadas_count = 0
    try:
        with transaction.atomic():
            for comision in comisiones_a_liquidar:
                comision.estatus_pago_comision = 'PAGADA'
                comision.fecha_pago_a_intermediario = fecha_pago
                comision.usuario_que_liquido = request.user

                # --- [INICIO DE LA CORRECCIÓN] ---
                if comprobante_archivo:
                    # Rebobinamos el puntero del archivo al principio en cada iteración
                    comprobante_archivo.seek(0)
                    comision.comprobante_pago.save(
                        comprobante_archivo.name, comprobante_archivo, save=False)
                # --- [FIN DE LA CORRECCIÓN] ---

                # Guardamos la comisión con todos los cambios
                comision.save()
                comisiones_actualizadas_count += 1

    except Exception as e:
        logger.error(
            f"Error durante la transacción de liquidación de comisiones: {e}", exc_info=True)
        messages.error(
            request, f"Ocurrió un error inesperado durante la liquidación: {e}")
        return redirect('myapp:liquidacion_comisiones')

    fecha_pago = django_timezone.now().date()
    if fecha_pago_str:
        try:
            fecha_pago = datetime.strptime(fecha_pago_str, '%d/%m/%Y').date()
            if fecha_pago > django_timezone.now().date():
                messages.warning(
                    request, "La fecha de pago no puede ser futura. Se usará la fecha actual.")
                fecha_pago = django_timezone.now().date()
        except ValueError:
            messages.error(
                request, "Formato de fecha de pago inválido (DD/MM/AAAA). Se usará la fecha actual.")

    # 3. Obtener los objetos de la base de datos
    comisiones_a_liquidar = list(RegistroComision.objects.filter(
        id__in=comisiones_ids_int,
        estatus_pago_comision='PENDIENTE'
    ).select_related('intermediario'))

    if not comisiones_a_liquidar:
        messages.warning(
            request, "No se encontraron comisiones pendientes válidas en la selección.")
        return redirect('myapp:liquidacion_comisiones')

    # 4. Procesar la actualización dentro de una transacción atómica
    comisiones_actualizadas_count = 0
    try:
        with transaction.atomic():
            for comision in comisiones_a_liquidar:
                comision.estatus_pago_comision = 'PAGADA'
                comision.fecha_pago_a_intermediario = fecha_pago
                comision.usuario_que_liquido = request.user

                # Asignar el mismo archivo de comprobante a todas las comisiones del lote
                if comprobante_archivo:
                    comprobante_archivo.seek(0)
                    comision.comprobante_pago = comprobante_archivo

                # Guardar cada objeto individualmente para que el FileField se procese correctamente
                comision.save()
                comisiones_actualizadas_count += 1

    except Exception as e:
        logger.error(
            f"Error durante la transacción de liquidación de comisiones: {e}", exc_info=True)
        messages.error(
            request, f"Ocurrió un error inesperado durante la liquidación: {e}")
        return redirect('myapp:liquidacion_comisiones')

    # 5. Enviar notificaciones y mensajes de éxito si todo salió bien
    if comisiones_actualizadas_count > 0:
        intermediario = comisiones_a_liquidar[0].intermediario
        total_liquidado = sum(c.monto_comision for c in comisiones_a_liquidar)

        messages.success(
            request, f"{comisiones_actualizadas_count} comisión(es) para '{intermediario.nombre_completo}' han sido marcadas como pagadas.")

        # Notificación para el administrador que realizó la acción
        mensaje_admin = f"Liquidaste {comisiones_actualizadas_count} comisiones por un total de ${total_liquidado:,.2f} para {intermediario.nombre_completo}."
        crear_notificacion(
            usuario_destino=[request.user],
            mensaje=mensaje_admin,
            tipo='success',
            url_path_name='myapp:historial_liquidaciones_list'
        )

        # Notificación para los usuarios del intermediario
        mensaje_intermediario = f"Hemos procesado el pago de {comisiones_actualizadas_count} de tus comisiones por un total de ${total_liquidado:,.2f}."
        usuarios_intermediario = intermediario.usuarios_asignados.filter(
            is_active=True)
        if usuarios_intermediario.exists():
            crear_notificacion(
                usuario_destino=usuarios_intermediario,
                mensaje=mensaje_intermediario,
                tipo='success',
                url_path_name='myapp:mis_comisiones_list'
            )

    else:
        messages.warning(
            request, "No se liquidó ninguna comisión. Es posible que ya estuvieran pagadas.")

    return redirect('myapp:liquidacion_comisiones')


@login_required
@require_POST
def marcar_comision_pagada_ajax_view(request):
    try:
        comision_id_str = request.POST.get('comision_id')
        if not comision_id_str:
            return JsonResponse({'status': 'error', 'message': 'ID de comisión no proporcionado.'}, status=400)

        comision_id = int(comision_id_str)
        comision = get_object_or_404(
            RegistroComision.objects.select_related('intermediario'), pk=comision_id)

        intermediario_obj = comision.intermediario

        if comision.estatus_pago_comision == 'PAGADA':
            nuevos_totales_actuales = calcular_totales_pendientes_intermediario(
                intermediario_obj)
            return JsonResponse({
                'status': 'info',
                'message': 'Esta comisión ya estaba marcada como pagada.',
                'comision_id': comision.pk,
                'nuevo_estatus': comision.get_estatus_pago_comision_display(),
                'fecha_pago': comision.fecha_pago_a_intermediario.strftime('%Y-%m-%d') if comision.fecha_pago_a_intermediario else None,
                'usuario_liquido': comision.usuario_que_liquido.get_full_name() if comision.usuario_que_liquido else 'N/A',
                'intermediario_id': intermediario_obj.id,
                'nuevos_totales': nuevos_totales_actuales
            })

        comision.estatus_pago_comision = 'PAGADA'
        comision.fecha_pago_a_intermediario = django_timezone.now().date()
        comision.usuario_que_liquido = request.user
        comision.save(update_fields=[
                      'estatus_pago_comision', 'fecha_pago_a_intermediario', 'usuario_que_liquido'])
        logger.info(
            f"Comisión ID {comision.id} marcada como PAGADA (AJAX) por {request.user.username}")

        nuevos_totales_despues_pago = calcular_totales_pendientes_intermediario(
            intermediario_obj)

        mensaje_notif_backend = (
            f"Liquidaste (AJAX) la comisión ID {comision.id} "
            f"por {comision.monto_comision:.2f} Bs. "
            f"al intermediario {intermediario_obj.nombre_completo} ({intermediario_obj.codigo})."
        )
        crear_notificacion(
            usuario_destino=request.user,
            mensaje=mensaje_notif_backend,
            tipo='success',
            url_path_name='myapp:liquidacion_comisiones'
        )
        logger.info(
            f"Notificación de backend creada para {request.user.username} por liquidación AJAX de comisión ID {comision.id}.")

        return JsonResponse({
            'status': 'success',
            'message': f'Comisión ID {comision.pk} marcada como pagada.',
            'comision_id': comision.pk,
            'nuevo_estatus': comision.get_estatus_pago_comision_display(),
            'fecha_pago': comision.fecha_pago_a_intermediario.strftime('%Y-%m-%d') if comision.fecha_pago_a_intermediario else None,
            'usuario_liquido': comision.usuario_que_liquido.get_full_name() if comision.usuario_que_liquido else 'N/A',
            'intermediario_id': intermediario_obj.id,
            'nuevos_totales': nuevos_totales_despues_pago
        })

    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'ID de comisión inválido.'}, status=400)
    except RegistroComision.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Comisión no encontrada.'}, status=404)
    except Exception as e:
        # >>> INICIO DE LA CORRECCIÓN DE SEGURIDAD <<<
        # Logueamos el error detallado para nosotros
        logger.error(
            f"Error en marcar_comision_pagada_ajax_view: {e}", exc_info=True)
        # Devolvemos un mensaje genérico y seguro al cliente
        return JsonResponse({'status': 'error', 'message': 'Ocurrió un error interno en el servidor.'}, status=500)
        # >>> FIN DE LA CORRECCIÓN DE SEGURIDAD <<<


@login_required
@require_POST
def marcar_comision_individual_pagada_view(request, pk):
    comision = get_object_or_404(RegistroComision, pk=pk)
    if comision.estatus_pago_comision == 'PENDIENTE':
        comision.estatus_pago_comision = 'PAGADA'
        comision.fecha_pago_a_intermediario = django_timezone.now().date()
        comision.save(
            update_fields=['estatus_pago_comision', 'fecha_pago_a_intermediario'])
        messages.success(
            request, f"Comisión #{comision.pk} marcada como pagada.")
    else:
        messages.warning(
            request, f"Comisión #{comision.pk} no estaba pendiente o ya fue procesada.")

    # >>> INICIO DE LA CORRECCIÓN DE SEGURIDAD <<<
    next_url = request.POST.get('next')
    # Validar que la URL es segura y pertenece a nuestro sitio
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    # Si no es segura o no existe, redirigir a un lugar seguro por defecto
    return redirect('myapp:registro_comision_detail', pk=comision.pk)
    # >>> FIN DE LA CORRECCIÓN DE SEGURIDAD <<<


def calcular_totales_pendientes_intermediario(intermediario):
    """
    Calcula los totales de comisiones pendientes para un intermediario específico.
    """
    if not intermediario:
        return {'directa': '0.00', 'override': '0.00', 'general': '0.00'}

    # Sumar comisiones PENDIENTES para este intermediario
    agregados = intermediario.comisiones_ganadas.filter(
        estatus_pago_comision='PENDIENTE'
    ).aggregate(
        total_directa=Coalesce(Sum(Case(When(tipo_comision='DIRECTA', then=F(
            'monto_comision')), default=Value(0))), Value(Decimal('0.00')), output_field=DecimalField()),
        total_override=Coalesce(Sum(Case(When(tipo_comision='OVERRIDE', then=F(
            'monto_comision')), default=Value(0))), Value(Decimal('0.00')), output_field=DecimalField())
    )

    total_directa_pendiente = agregados['total_directa']
    total_override_pendiente = agregados['total_override']
    total_general_pendiente = total_directa_pendiente + total_override_pendiente

    return {
        # Devolver como string formateado
        'directa': f"{total_directa_pendiente:.2f}",
        'override': f"{total_override_pendiente:.2f}",
        'general': f"{total_general_pendiente:.2f}"
    }


# --- VISTA 3: Historial de Liquidaciones ---
class HistorialLiquidacionesListView(LoginRequiredMixin, ListView):
    model = RegistroComision
    template_name = 'historial_liquidaciones_list.html'
    context_object_name = 'liquidaciones'

    def get_queryset(self):
        # Solo comisiones pagadas, con todas sus relaciones para mostrar en la tabla.
        return RegistroComision.objects.filter(
            estatus_pago_comision='PAGADA'
        ).select_related(
            'intermediario', 'usuario_que_liquido', 'factura_origen',
            'pago_cliente', 'intermediario_vendedor'
        ).order_by('-fecha_pago_a_intermediario')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Historial de Liquidaciones"
        return context


# ==========================
# Usuario Vistas
# ==========================


# ==========================
# Usuario Vistas (CORREGIDAS)
# ==========================

class UsuarioListView(LoginRequiredMixin, ListView):
    model = Usuario
    template_name = 'usuario_list.html'
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve los usuarios. Los superusuarios ven a todos.
        Los demás usuarios no ven a los de tipo ADMIN.
        """
        user = self.request.user
        if user.is_superuser:
            # El superusuario puede ver a todos, incluyendo inactivos.
            queryset = Usuario.all_objects.all()
        else:
            # Los demás usuarios ven a todos excepto a los de tipo ADMIN.
            # Usamos el manager 'objects' que filtra por activo=True por defecto.
            queryset = Usuario.objects.exclude(tipo_usuario='ADMIN')

        return queryset.select_related('intermediario').prefetch_related('groups').order_by('primer_apellido', 'primer_nombre')

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto, manejando errores de desencriptación de forma segura.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Usuarios del Sistema"

        object_list_safe = []
        for obj in context['object_list']:
            try:
                # Forzamos la desencriptación de un campo para probar si el registro es válido
                str(obj.get_full_name())
                obj.decryption_error = False
            except Exception:
                obj.decryption_error = True
            object_list_safe.append(obj)

        context['object_list'] = object_list_safe
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioDetailView(BaseDetailView):
    model = Usuario
    model_manager_name = 'all_objects'
    template_name = 'usuario_detail.html'
    context_object_name = 'usuario_detalle'
    permission_required = 'myapp.view_usuario'

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = Usuario.all_objects.all()
        else:
            qs = Usuario.objects.all()
        return qs.select_related('intermediario').prefetch_related('groups', 'user_permissions')

    def get_object(self, queryset=None):
        """
        Sobrescribe para añadir una capa de seguridad: un usuario no puede ver
        el perfil de un ADMIN a menos que sea superusuario.
        """
        obj = super().get_object(queryset)
        user = self.request.user

        # Un no-superusuario no puede ver el perfil de un ADMIN.
        if not user.is_superuser and obj.tipo_usuario == 'ADMIN':
            raise PermissionDenied(
                "No tiene permiso para ver el perfil de este usuario.")

        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario_obj = context[self.context_object_name]

        context['tipo_usuario_display'] = usuario_obj.get_tipo_usuario_display()
        context['departamento_display'] = usuario_obj.get_departamento_display()
        # 'groups' y 'user_permissions' ya están en usuario_obj por prefetch_related
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioCreateView(BaseCreateView):
    model = Usuario
    model_manager_name = 'all_objects'
    form_class = FormularioCreacionUsuario
    template_name = 'usuario_form.html'
    permission_required = 'myapp.add_usuario'
    success_url = reverse_lazy('myapp:usuario_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campos_seccion_personal'] = [
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'fecha_nacimiento', 'telefono', 'direccion'
        ]
        context['campos_seccion_roles'] = [
            'tipo_usuario', 'departamento', 'intermediario',
            'activo', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
        ]
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioUpdateView(BaseUpdateView):
    model = Usuario
    model_manager_name = 'all_objects'
    form_class = FormularioEdicionUsuario
    template_name = 'usuario_form.html'
    permission_required = 'myapp.change_usuario'
    context_object_name = 'object'

    def get_success_url(self):
        return reverse_lazy('myapp:usuario_detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['campos_seccion_personal'] = [
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'fecha_nacimiento', 'telefono', 'direccion'
        ]

        campos_roles_edicion = [
            'tipo_usuario',
            'departamento', 'intermediario', 'activo',
            'is_staff', 'is_superuser',
            'groups', 'user_permissions'
        ]

        context['campos_seccion_roles'] = campos_roles_edicion
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioDeleteView(BaseDeleteView):
    model = Usuario
    template_name = 'usuario_confirm_delete.html'
    permission_required = 'myapp.delete_usuario'
    success_url = reverse_lazy('myapp:usuario_list')

    def can_delete(self, obj_to_delete):
        """
        Verifica si el usuario puede ser eliminado, ahora basado en roles.
        Devuelve: (True, "") si se puede eliminar.
                  (False, "Mensaje de error") si no se puede eliminar.
        """
        user = self.request.user

        # Regla 1: Nadie puede eliminar su propia cuenta.
        if obj_to_delete == user:
            return False, "Acción denegada: No puedes eliminar tu propia cuenta."

        # Regla 2: Solo los superusuarios pueden eliminar a otros usuarios con rol 'ADMIN'.
        if obj_to_delete.tipo_usuario == 'ADMIN' and not user.is_superuser:
            return False, "Acción denegada: No tienes permiso para eliminar a un Administrador."

        # Aquí puedes añadir más chequeos si es necesario.
        # Por ejemplo, verificar si el usuario es un intermediario con contratos activos.
        # if hasattr(obj_to_delete, 'intermediario') and obj_to_delete.intermediario:
        #     if obj_to_delete.intermediario.contratoindividual_set.exists() or \
        #        obj_to_delete.intermediario.contratos_colectivos.exists():
        #         return False, "No se puede eliminar, el intermediario asociado a este usuario tiene contratos activos."

        return True, ""  # Si pasa todas las validaciones, se puede eliminar.

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['usuario_puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo_eliminacion'] = reason_message
        context['page_title'] = f"Confirmar Eliminación de Usuario: {self.object.get_full_name() or self.object.username}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)

        if not can_delete_flag:
            messages.error(
                request, reason_message or "Este usuario no puede ser eliminado.")
            try:
                return redirect(reverse('myapp:usuario_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.get_success_url())

        # Si puede ser eliminado, procede con la lógica de la clase base.
        return super().post(request, *args, **kwargs)

# ==========================
# Factura Vistas
# ==========================


class FacturaListView(LoginRequiredMixin, ListView):
    model = Factura
    template_name = 'factura_list.html'  # Nuevo nombre de plantilla
    context_object_name = 'object_list'

    def get_queryset(self):
        """
        Devuelve TODAS las facturas activas. DataTables se encargará del resto.
        """
        # Usamos el manager 'objects' que ya filtra por activo=True
        # Optimizamos la consulta para cargar las relaciones que se mostrarán en la tabla
        return Factura.objects.select_related(
            'contrato_individual__afiliado',
            'contrato_colectivo',
            'intermediario'
        )

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para la plantilla.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = "Listado de Facturas"
        # No hay campos cifrados directamente en Factura, así que no se necesita bucle de seguridad.
        return context


class FacturaDetailView(BaseDetailView):
    model = Factura
    model_manager_name = 'all_objects'
    template_name = 'factura_detail.html'
    context_object_name = 'object'
    permission_required = 'myapp.view_factura'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'contrato_individual__afiliado',
            # Asegurar que el intermediario del CI esté
            'contrato_individual__intermediario',
            # Asegurar que el intermediario del CC esté
            'contrato_colectivo__intermediario',
            'intermediario'  # Intermediario directo de la factura
        ).prefetch_related(
            Prefetch('pagos', queryset=Pago.objects.order_by('-fecha_pago'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        factura = self.object
        pagos_list = list(factura.pagos.all())
        total_pagado = sum(
            p.monto_pago for p in pagos_list if p.monto_pago) or Decimal('0.00')

        # --- LÓGICA PARA CONTRATO ASOCIADO E INTERMEDIARIO ---
        contrato_asociado = factura.contrato_individual or factura.contrato_colectivo
        contrato_asociado_display = "N/A"
        contrato_asociado_url = None
        # intermediario_final_obj se usará para el template
        # Intermediario directo de la factura primero
        intermediario_final_obj = factura.intermediario

        if contrato_asociado:
            # Usa el __str__ del modelo de contrato
            contrato_asociado_display = str(contrato_asociado)
            if not intermediario_final_obj:  # Si la factura no tiene uno directo, tomar el del contrato
                intermediario_final_obj = contrato_asociado.intermediario

            if isinstance(contrato_asociado, ContratoIndividual):
                try:
                    contrato_asociado_url = reverse('myapp:contrato_individual_detail', kwargs={
                                                    'pk': contrato_asociado.pk})
                except NoReverseMatch:
                    logger.warning(
                        f"URL 'contrato_individual_detail' no encontrada para PK {contrato_asociado.pk}")
            elif isinstance(contrato_asociado, ContratoColectivo):
                try:
                    contrato_asociado_url = reverse('myapp:contrato_colectivo_detail', kwargs={
                                                    'pk': contrato_asociado.pk})
                except NoReverseMatch:
                    logger.warning(
                        f"URL 'contrato_colectivo_detail' no encontrada para PK {contrato_asociado.pk}")
        # --- FIN LÓGICA CONTRATO E INTERMEDIARIO ---

        base_imponible = factura.monto or Decimal('0.00')
        tasa_iva = Decimal('0.16')
        monto_iva = (base_imponible *
                     tasa_iva).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_con_iva = base_imponible + monto_iva
        monto_igtf = Decimal('0.00')
        tasa_igtf = Decimal('0.03')
        if factura.aplica_igtf:
            monto_igtf = (
                total_con_iva * tasa_igtf).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_a_pagar = total_con_iva + monto_igtf

        context.update({
            # 'factura': factura, # Ya está como 'object'
            'estatus_factura_display': factura.get_estatus_factura_display(),
            'estatus_emision_display': factura.get_estatus_emision_display(),

            # El objeto en sí, por si lo necesitas
            'contrato_asociado_obj': contrato_asociado,
            'contrato_asociado_display': contrato_asociado_display,  # Para mostrar
            'contrato_asociado_url': contrato_asociado_url,  # Para el enlace <a>

            # Para el template (usa este nombre)
            'intermediario_final_obj': intermediario_final_obj,

            'pagos_asociados': pagos_list,
            'total_pagado': total_pagado,
            'monto_pendiente_factura': factura.monto_pendiente,
            'cantidad_pagos': len(pagos_list),
            'base_imponible': base_imponible,
            'monto_iva': monto_iva,
            'total_con_iva': total_con_iva,
            'monto_igtf': monto_igtf,
            'total_a_pagar': total_a_pagar,
            'tasa_iva_display': f"{tasa_iva:.0%}",
            'tasa_igtf_display': f"{tasa_igtf:.0%}",
            'active_tab': 'facturas',
        })
        return context


class FacturaCreateView(BaseCreateView):
    model = Factura
    form_class = FacturaForm
    template_name = 'factura_form.html'
    permission_required = 'myapp.add_factura'

    def get_success_url(self):
        contrato = getattr(self.object, 'get_contrato_asociado', None)
        if contrato:
            if isinstance(contrato, ContratoIndividual):
                return reverse('myapp:contrato_individual_detail', kwargs={'pk': contrato.pk})
            if isinstance(contrato, ContratoColectivo):
                return reverse('myapp:contrato_colectivo_detail', kwargs={'pk': contrato.pk})
        return reverse('myapp:factura_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        contrato = self.object.get_contrato_asociado

        if not contrato:
            form.add_error(None, "Debe asociar un contrato a la factura.")
            return self.form_invalid(form)

        # --- ASIGNACIÓN DE TODOS LOS VALORES ANTES DE GUARDAR ---
        self.object.estatus_factura = 'GENERADA'
        self.object.estatus_emision = 'SIN_EMITIR'

        monto_calculado = getattr(
            contrato, 'monto_cuota_estimada', Decimal('0.00'))
        self.object.monto = monto_calculado if monto_calculado is not None else Decimal(
            '0.00')

        if self.object.vigencia_recibo_desde and self.object.vigencia_recibo_hasta:
            if self.object.vigencia_recibo_hasta >= self.object.vigencia_recibo_desde:
                delta = self.object.vigencia_recibo_hasta - self.object.vigencia_recibo_desde
                self.object.dias_periodo_cobro = delta.days + 1

        # --- CORRECCIÓN CLAVE: ASIGNAR MONTO PENDIENTE AQUÍ ---
        # Asignamos el monto pendiente DESPUÉS de haber calculado el monto de la factura.
        self.object.monto_pendiente = self.object.monto

        # Los valores por defecto del modelo se encargarán del resto (estatus, pagada=False, etc.)
        return super().form_valid(form)


class FacturaUpdateView(BaseUpdateView):
    model = Factura
    model_manager_name = 'all_objects'
    form_class = FacturaForm
    template_name = 'factura_form.html'
    permission_required = 'myapp.change_factura'

    def get_success_url(self):
        return reverse('myapp:factura_detail', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        """
        Sobrescribimos get_form para pre-llenar los campos de solo lectura.
        """
        form = super().get_form(form_class)

        # --- CORRECCIÓN CLAVE: PRE-LLENAR CAMPOS DE SOLO LECTURA ---
        if self.object:
            # Llenamos los campos del formulario con los valores actuales del objeto
            # Esto asegura que el widget readonly tenga un valor para mostrar.
            form.fields['monto'].initial = self.object.monto
            form.fields['dias_periodo_cobro'].initial = self.object.dias_periodo_cobro

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        factura = self.object
        contrato = factura.get_contrato_asociado

        if contrato:
            context['monto_total_contrato_valor'] = f"${contrato.monto_total:,.2f}" if contrato.monto_total is not None else "N/A"
            context['saldo_contrato_display_valor'] = f"${contrato.saldo_pendiente_contrato:,.2f}" if contrato.saldo_pendiente_contrato is not None else "N/A"

        context['form_title'] = f'Editar Factura: {factura.numero_recibo}'
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)

        if self.object.vigencia_recibo_desde and self.object.vigencia_recibo_hasta:
            if self.object.vigencia_recibo_hasta >= self.object.vigencia_recibo_desde:
                delta = self.object.vigencia_recibo_hasta - self.object.vigencia_recibo_desde
                self.object.dias_periodo_cobro = delta.days + 1

        return super().form_valid(form)

    def enviar_notificacion_actualizacion(self, fac_antes, fac_despues, changed_data):
        if not changed_data:
            return
        mensaje_base = f"Factura {fac_despues.numero_recibo} actualizada."
        detalles = []
        tipo_notif = 'info'  # Default

        if 'pagada' in changed_data:
            estado_nuevo = 'PAGADA' if fac_despues.pagada else 'PENDIENTE'
            detalles.append(f" marcada como {estado_nuevo}")
            tipo_notif = 'success' if fac_despues.pagada else 'warning'
        if 'monto' in changed_data:
            detalles.append(
                f" Monto: ${fac_antes.monto:.2f} -> ${fac_despues.monto:.2f}")
        if 'monto_pendiente' in changed_data:  # Esto usualmente cambia por pagos, no directo
            detalles.append(
                f" Pendiente: ${fac_antes.monto_pendiente:.2f} -> ${fac_despues.monto_pendiente:.2f}")
        if 'estatus_factura' in changed_data:
            detalles.append(
                f" Estatus: {fac_antes.get_estatus_factura_display()} -> {fac_despues.get_estatus_factura_display()}")
            if fac_despues.estatus_factura == 'ANULADA':
                tipo_notif = 'error'

        mensaje = mensaje_base + \
            (", ".join(detalles)
             if detalles else f" Cambios: {', '.join(changed_data)}.")

        destinatarios = []
        if fac_despues.intermediario and hasattr(fac_despues.intermediario, 'usuarios'):
            destinatarios.extend(
                list(fac_despues.intermediario.usuarios.filter(is_active=True)))
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(list(set(destinatarios)), mensaje, tipo=tipo_notif,
                               url_path_name='myapp:factura_detail', url_kwargs={'pk': fac_despues.pk})


@method_decorator(csrf_protect, name='dispatch')
class FacturaDeleteView(BaseDeleteView):
    model = Factura
    template_name = 'factura_confirm_delete.html'  # O tu genérico
    context_object_name = 'object'
    permission_required = 'myapp.delete_factura'
    success_url = reverse_lazy('myapp:factura_list')

    def can_delete(self, obj):
        # [CORRECCIÓN] Contamos solo los pagos activos.
        if obj.pagos.filter(activo=True).exists():
            return False, f"No se puede eliminar: la factura '{obj.numero_recibo}' tiene pagos activos asociados."
        return True, ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_delete_flag, reason_message = self.can_delete(self.object)
        context['puede_ser_eliminado'] = can_delete_flag
        context['mensaje_bloqueo'] = reason_message
        context['page_title'] = f"Confirmar Eliminación Factura: {self.object.numero_recibo}"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete_flag, reason_message = self.can_delete(self.object)
        if not can_delete_flag:
            messages.error(request, reason_message)
            try:
                return redirect(reverse('myapp:factura_detail', kwargs={'pk': self.object.pk}))
            except NoReverseMatch:
                return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó la Factura: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='error')


# =============================================================================
# 1. DEFINE TUS COLORES CORPORATIVOS
#    Reemplaza estos con TUS colores hexadecimales reales.
# =============================================================================
COLOR_PALETTE = {
    'primary': '#004B8D',        # Azul oscuro principal
    'secondary': '#00AEEF',      # Azul claro/cian secundario
    'accent1': '#FDB913',        # Amarillo/dorado como primer acento
    'accent2': '#8CC63F',        # Verde como segundo acento
    'neutral_dark': '#616161',
    'neutral_medium': '#BDBDBD',
    'neutral_light': '#F5F5F5',
    'text_main': '#212121',
    'white': '#FFFFFF',
    'success': '#388E3C',        # Verde para éxito
    'warning': '#FFA000',        # Naranja/Amarillo para advertencia
    'danger': '#D32F2F',         # Rojo para error/peligro
    # Puedes añadir más si los necesitas para usos semánticos específicos
}

# =============================================================================
# 2. SECUENCIA DE COLORES POR DEFECTO PARA USAR EN GRÁFICOS
#    Define el orden en que quieres que los colores se apliquen.
# =============================================================================
DEFAULT_PLOTLY_COLORS_CORPORATE = [
    COLOR_PALETTE['primary'],
    # Antes causaba KeyError si 'accent1' no estaba en COLOR_PALETTE
    COLOR_PALETTE['accent1'],
    COLOR_PALETTE['secondary'],
    COLOR_PALETTE['accent2'],
    COLOR_PALETTE['neutral_dark'],  # Un color más neutro
    COLOR_PALETTE['warning'],       # Un color de advertencia
    # Puedes añadir más colores de tu COLOR_PALETTE aquí si tienes más de 6 series comunes
]

# =============================================================================
# 3. LAYOUT BASE PARA TUS GRÁFICOS DE DASHBOARD
# =============================================================================
BASE_LAYOUT_DASHBOARD = {
    'paper_bgcolor': COLOR_PALETTE.get('white', 'rgba(255, 255, 255, 0.95)'),
    'plot_bgcolor': COLOR_PALETTE.get('neutral_light', 'rgba(245, 245, 245, 0.9)'),
    'font': {
        'family': 'Arial, Helvetica, sans-serif',
        'size': 12,
        'color': COLOR_PALETTE.get('text_main', '#212121')
    },
    'title': {  # Título principal del gráfico
        'x': 0.5, 'xanchor': 'center',
        'font': {'size': 18, 'color': COLOR_PALETTE.get('primary')}
    },
    'xaxis': {
        'gridcolor': COLOR_PALETTE.get('neutral_medium', '#BDBDBD'),
        'linecolor': COLOR_PALETTE.get('neutral_dark', '#616161'),
        'tickfont': {'color': COLOR_PALETTE.get('text_main', '#212121')},
        'title': {  # Para el título del eje X
            'font': {
                'color': COLOR_PALETTE.get('primary'),
                'size': 14
            }
        }
    },
    'yaxis': {
        'gridcolor': COLOR_PALETTE.get('neutral_medium', '#BDBDBD'),
        'linecolor': COLOR_PALETTE.get('neutral_dark', '#616161'),
        'tickfont': {'color': COLOR_PALETTE.get('text_main', '#212121')},
        'title': {  # Para el título del eje Y
            'font': {
                'color': COLOR_PALETTE.get('primary'),
                'size': 14
            }
        }
    },
    'legend': {
        'font': {'color': COLOR_PALETTE.get('text_main', '#212121')},
        'bgcolor': 'rgba(255,255,255,0.7)',
        'bordercolor': COLOR_PALETTE.get('neutral_medium', '#BDBDBD'),
        'borderwidth': 1
    },
    'margin': {'t': 70, 'l': 70, 'r': 30, 'b': 70},  # Márgenes por defecto
    # <-- APLICA LA SECUENCIA POR DEFECTO
    'colorway': DEFAULT_PLOTLY_COLORS_CORPORATE,
}

# =============================================================================
# 4. CONFIGURACIÓN GENERAL DE GRÁFICOS PLOTLY
# =============================================================================
GRAPH_CONFIG = {'displayModeBar': False, 'responsive': True}


# =============================================================================
# FUNCIONES DE GENERACIÓN DE GRÁFICOS (SIN CAMBIOS EN LÓGICA DE DATOS)
# Los cambios son solo en cómo se aplican los colores y el layout.
# =============================================================================

# Renombrado
def generar_figura_sin_datos_plotly(mensaje="No hay datos disponibles"):
    fig = go.Figure()
    color_texto = COLOR_PALETTE.get('neutral_dark', "#666666")
    fig.add_annotation(text=mensaje, xref="paper", yref="paper", x=0.5,
                       y=0.5, showarrow=False, font={"size": 16, "color": color_texto})
    layout_para_vacio = BASE_LAYOUT_DASHBOARD.copy()
    layout_para_vacio.update({
        'xaxis': {'visible': False, 'showgrid': False, 'zeroline': False, 'title': {'text': ''}},
        'yaxis': {'visible': False, 'showgrid': False, 'zeroline': False, 'title': {'text': ''}},
        'margin': dict(t=10, b=10, l=10, r=10), 'paper_bgcolor': 'rgba(0,0,0,0)', 'plot_bgcolor': 'rgba(0,0,0,0)', 'colorway': [color_texto]
    })
    fig.update_layout(**layout_para_vacio)
    return fig


# Nuevo nombre para la nueva lógica
def generar_grafico_total_primas_ramo_barras(data_ignorada=None):
    try:
        fecha_fin_periodo_date = py_date.today()
        # Periodo: últimos 12 meses para tener una buena visión general
        fecha_inicio_periodo_date = fecha_fin_periodo_date - \
            relativedelta(years=1) + relativedelta(days=1)
        ramo_map = dict(CommonChoices.RAMO)

        fecha_inicio_periodo_aware = django_timezone.make_aware(
            py_datetime.combine(fecha_inicio_periodo_date,
                                py_datetime.min.time()),
            django_timezone.get_current_timezone()
        )
        fecha_fin_periodo_aware = django_timezone.make_aware(
            py_datetime.combine(fecha_fin_periodo_date,
                                py_datetime.max.time()),
            django_timezone.get_current_timezone()
        )

        periodo_display_str = f"{fecha_inicio_periodo_date.strftime('%b %Y')} - {fecha_fin_periodo_date.strftime('%b %Y')}"
        logger_graficas_debug.debug(
            f"Periodo para total primas por ramo (barras): {periodo_display_str}")

        primas_por_ramo = collections.defaultdict(Decimal)

        for contrato_model_class in [ContratoIndividual, ContratoColectivo]:
            # Filtramos por fecha_emision dentro del periodo.
            # Si un contrato se emitió antes pero sigue vigente y generando primas DENTRO de este periodo,
            # esta lógica NO lo capturará. Esta lógica es para PRIMAS EMITIDAS en el periodo.
            # Si quieres PRIMAS DEVENGADAS o PAGADAS en el periodo, la consulta sería sobre Facturas/Pagos.
            # Por ahora, mantenemos la lógica de primas basada en la emisión del contrato.
            qs = contrato_model_class.objects.filter(
                activo=True, fecha_emision__isnull=False,
                fecha_emision__gte=fecha_inicio_periodo_aware,
                fecha_emision__lte=fecha_fin_periodo_aware,
                monto_total__gt=Decimal('0.00')
            ).values('ramo').annotate(total_primas_ramo=Sum('monto_total'))

            for item in qs:
                ramo_label = ramo_map.get(
                    item['ramo'], str(item['ramo'] or "Desconocido"))
                primas_por_ramo[ramo_label] += item['total_primas_ramo'] or Decimal(
                    '0.00')

        if not primas_por_ramo:
            return plot(generar_figura_sin_datos_plotly(f"No hay datos de primas para el periodo."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Convertir a DataFrame para facilitar el ordenamiento y el gráfico
        df_primas = pd.DataFrame(list(primas_por_ramo.items()), columns=[
                                 'ramo_label', 'total_prima_ramo'])
        df_primas['total_prima_ramo'] = pd.to_numeric(
            df_primas['total_prima_ramo'], errors='coerce').fillna(0.0)

        # Ordenar por total de primas para que la barra más larga esté arriba (o abajo)
        # Ascending True para que la más grande esté arriba en barras horizontales
        df_primas = df_primas.sort_values(
            by='total_prima_ramo', ascending=True)

        # Limitar a N ramos principales si hay demasiados
        TOP_N_RAMOS_BARRAS = 7  # Puedes ajustar esto
        if len(df_primas) > TOP_N_RAMOS_BARRAS:
            # Todos excepto los N-1 más grandes
            df_otros = df_primas[:-TOP_N_RAMOS_BARRAS+1]
            df_plot = df_primas[-TOP_N_RAMOS_BARRAS+1:]  # Los N-1 más grandes
            if not df_otros.empty:
                otros_sum = df_otros['total_prima_ramo'].sum()
                if otros_sum > 0:
                    df_plot = pd.concat([df_plot, pd.DataFrame(
                        [{'ramo_label': 'Otros Ramos', 'total_prima_ramo': otros_sum}])], ignore_index=True)
            # Re-ordenar después de añadir "Otros"
            df_plot = df_plot.sort_values(
                by='total_prima_ramo', ascending=True)
        else:
            df_plot = df_primas

        if df_plot.empty or df_plot['total_prima_ramo'].sum() == 0:
            return plot(generar_figura_sin_datos_plotly(f"No hay primas significativas para el periodo."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = px.bar(df_plot,
                     # Ramos en el eje Y (barras horizontales)
                     y='ramo_label',
                     x='total_prima_ramo',
                     orientation='h',      # Barras horizontales
                     labels={'ramo_label': 'Ramo',
                             'total_prima_ramo': 'Total Primas Emitidas ($)'},
                     title=f'Total Primas por Ramo ({periodo_display_str})',
                     text='total_prima_ramo'  # Mostrar el valor en las barras
                     )

        # Usar el ciclo de colores por defecto de tu BASE_LAYOUT_DASHBOARD
        fig.update_traces(
            texttemplate='$%{text:,.0f}',
            textposition='outside',
            hovertemplate="<b>%{y}</b><br>Total Primas: $%{x:,.0f}<extra></extra>"
        )

        layout_actualizado = BASE_LAYOUT_DASHBOARD.copy()
        layout_actualizado.update(
            xaxis={
                'title': {'text': "Total Primas Emitidas ($)"}, 'tickprefix': '$'},
            # Automargin para nombres largos de ramos
            yaxis={'title': {'text': None}, 'automargin': True},
            # Altura dinámica basada en número de ramos
            height=max(500, len(df_plot) * 40 + 100),
            showlegend=False,  # No necesaria si cada barra es un ramo y tiene color del ciclo
            # Margen izquierdo amplio para nombres de ramos
            margin=dict(t=60, b=50, l=200, r=30)
        )
        fig.update_layout(**layout_actualizado)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e_global:
        return plot(generar_figura_sin_datos_plotly(f"Error generando gráfico totales ramo ({type(e_global).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_estados_contrato(data_antiguedad_estatus):
    if not data_antiguedad_estatus or not any(isinstance(v, (int, float, Decimal)) and v > 0 for v in data_antiguedad_estatus.values()):
        return plot(generar_figura_sin_datos_plotly("Antigüedad de contratos no disponible."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    try:
        valid_data = {k: v for k, v in data_antiguedad_estatus.items(
        ) if isinstance(v, (int, float, Decimal)) and v > 0}
        if not valid_data:
            return plot(generar_figura_sin_datos_plotly("No hay datos válidos de antigüedad."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df = pd.DataFrame(list(valid_data.items()), columns=[
                          'Estatus Vigencia', 'Antigüedad Promedio (días)'])
        df = df.sort_values('Antigüedad Promedio (días)', ascending=True)

        # Colores específicos para este gráfico si el ciclo por defecto no es adecuado
        # (Opcional, si el colorway del layout no da el resultado deseado aquí)
        estatus_map_display = {v: k for k, v in CommonChoices.ESTADOS_VIGENCIA}
        mapa_colores_especificos = {
            estatus_map_display.get('Vigente', 'VIGENTE'): COLOR_PALETTE.get('success'),
            estatus_map_display.get('Vencido', 'VENCIDO'): COLOR_PALETTE.get('neutral_dark'),
            estatus_map_display.get('No Vigente Aún', 'NO_VIGENTE_AUN'): COLOR_PALETTE.get('warning'),
        }

        fig = px.bar(df, x='Antigüedad Promedio (días)', y='Estatus Vigencia', orientation='h',
                     text='Antigüedad Promedio (días)', color='Estatus Vigencia',
                     color_discrete_map=mapa_colores_especificos  # Prioriza este mapa
                     )
        fig.update_traces(
            texttemplate='%{text:.0f} días', textposition='outside')

        layout_actualizado = BASE_LAYOUT_DASHBOARD.copy()
        if mapa_colores_especificos:
            # Para que el mapa tenga efecto
            layout_actualizado.pop('colorway', None)
        layout_actualizado.update(
            title_text='Antigüedad Prom. Contratos por Estatus',
            # xaxis_title="Antigüedad Promedio (días)", # Se define en BASE_LAYOUT_DASHBOARD.xaxis.title.text
            # yaxis_title=None,
            # Establecer texto del título del eje
            xaxis={'title': {'text': "Antigüedad Promedio (días)"}},
            yaxis={'categoryorder': 'total ascending',
                   'automargin': True, 'title': {'text': None}},
            showlegend=False,
            margin=dict(t=70, b=50, l=180, r=30), height=500
        )
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error en generar_grafico_estados_contrato: {e}", exc_info=True)
        return plot(generar_figura_sin_datos_plotly(f"Error ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_estados_reclamacion(data_top_tipos_costosos):
    if not data_top_tipos_costosos:
        return plot(generar_figura_sin_datos_plotly("No hay datos de tipos de reclamación."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    try:
        df = pd.DataFrame(data_top_tipos_costosos, columns=[
                          'Tipo de Reclamación', 'Monto Promedio ($)'])
        df = df.sort_values('Monto Promedio ($)', ascending=True)
        if df.empty:
            return plot(generar_figura_sin_datos_plotly("No hay tipos de reclamación válidos."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = px.bar(df, x='Monto Promedio ($)', y='Tipo de Reclamación', orientation='h',
                     text='Monto Promedio ($)', color='Tipo de Reclamación')
        # El 'colorway' de BASE_LAYOUT_DASHBOARD se aplicará
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')

        layout_actualizado = BASE_LAYOUT_DASHBOARD.copy()
        layout_actualizado.update(
            title_text='Tipos Reclamo Pendientes (Mayor Costo Prom.)',
            xaxis={
                'title': {'text': "Monto Promedio ($)"}, 'automargin': True},
            yaxis={'title': {'text': None}, 'automargin': True},
            showlegend=False,
            legend_title_text='Tipo de Reclamación',
            margin=dict(t=70, b=50, l=250, r=30), height=500,
        )
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error en generar_grafico_estados_reclamacion: {e}", exc_info=True)
        return plot(generar_figura_sin_datos_plotly(f"Error ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


logger_graficas_debug = logging.getLogger("myapp.graficas.debug_monto_ramo")


def generar_grafico_monto_ramo(data_ignorada=None):  # Nueva versión
    try:
        fecha_fin_periodo_date = py_date.today()
        fecha_inicio_periodo_date = fecha_fin_periodo_date - \
            relativedelta(years=2)
        ramo_map = dict(CommonChoices.RAMO)

        fecha_inicio_periodo_aware = django_timezone.make_aware(
            py_datetime.combine(fecha_inicio_periodo_date,
                                py_datetime.min.time()),
            django_timezone.get_current_timezone()
        )
        fecha_fin_periodo_aware = django_timezone.make_aware(
            py_datetime.combine(fecha_fin_periodo_date,
                                py_datetime.max.time()),
            django_timezone.get_current_timezone()
        )

        # --- Contratos Individuales ---
        prima_ind_data = []
        qs_ind = ContratoIndividual.objects.filter(
            activo=True, fecha_emision__isnull=False,
            fecha_emision__gte=fecha_inicio_periodo_aware,
            fecha_emision__lte=fecha_fin_periodo_aware,
            monto_total__gt=Decimal('0.00')
        ).annotate(mes_emision_trunc=TruncMonth('fecha_emision')) \
         .values('ramo', 'mes_emision_trunc') \
         .annotate(prima_mes_ramo=Sum('monto_total'))

        for item in qs_ind:
            mes_trunc_val = item.get('mes_emision_trunc')
            mes_str = "ErrorFecha"
            if isinstance(mes_trunc_val, (py_datetime, py_date)):
                mes_str = mes_trunc_val.strftime('%Y-%m')
            prima_ind_data.append({
                'ramo': item['ramo'],
                'mes_str': mes_str,  # Usar el string
                'prima_mes_ramo': item['prima_mes_ramo']
            })
        df_prima_ind = pd.DataFrame(prima_ind_data)

        # --- Contratos Colectivos ---
        prima_col_data = []
        qs_col = ContratoColectivo.objects.filter(
            activo=True, fecha_emision__isnull=False,
            fecha_emision__gte=fecha_inicio_periodo_aware,
            fecha_emision__lte=fecha_fin_periodo_aware,
            monto_total__gt=Decimal('0.00')
        ).annotate(mes_emision_trunc=TruncMonth('fecha_emision')) \
         .values('ramo', 'mes_emision_trunc') \
         .annotate(prima_mes_ramo=Sum('monto_total'))

        for item in qs_col:
            mes_trunc_val = item.get('mes_emision_trunc')
            mes_str = "ErrorFecha"
            if isinstance(mes_trunc_val, (py_datetime, py_date)):
                mes_str = mes_trunc_val.strftime('%Y-%m')
            prima_col_data.append({
                'ramo': item['ramo'],
                'mes_str': mes_str,  # Usar el string
                'prima_mes_ramo': item['prima_mes_ramo']
            })
        df_prima_col = pd.DataFrame(prima_col_data)

        # --- Combinación y Procesamiento ---
        if df_prima_ind.empty and df_prima_col.empty:
            return plot(generar_figura_sin_datos_plotly("No hay datos de primas por ramo."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        df_total_primas = pd.concat(
            [df_prima_ind, df_prima_col], ignore_index=True)
        if df_total_primas.empty or 'prima_mes_ramo' not in df_total_primas.columns:
            return plot(generar_figura_sin_datos_plotly("No hay datos de primas tras combinar."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Agrupar por el string del mes
        df_agrupado = df_total_primas.groupby(['ramo', 'mes_str'])[
            'prima_mes_ramo'].sum().reset_index()
        df_agrupado['ramo_label'] = df_agrupado['ramo'].apply(
            lambda x: ramo_map.get(x, str(x or "Desconocido")))
        df_agrupado['prima_mes_ramo'] = pd.to_numeric(
            df_agrupado['prima_mes_ramo'], errors='coerce').fillna(0.0)

        # El rellenado con date_range es más complejo si el eje X es string.
        # Por ahora, lo omitimos para simplificar y ver si las advertencias desaparecen.
        # Si necesitas el rellenado, se puede hacer, pero requiere más lógica con los strings de mes.
        df_final_rellenado = df_agrupado.sort_values(
            by=['ramo_label', 'mes_str'])

        # ... (lógica para seleccionar ramos_principales y df_plot, sin cambios) ...
        primas_totales_ramo_periodo = df_final_rellenado.groupby('ramo_label')[
            'prima_mes_ramo'].sum()
        total_primas_sum = primas_totales_ramo_periodo.sum()
        umbral_prima_ramo = max(Decimal(str(total_primas_sum if pd.notna(
            total_primas_sum) else 0.0)) * Decimal('0.005'), Decimal('1.0'))
        TOP_N_RAMOS_PARA_LINEAS = 5

        ramos_significativos_df = primas_totales_ramo_periodo[
            primas_totales_ramo_periodo >= umbral_prima_ramo]
        if ramos_significativos_df.empty and not primas_totales_ramo_periodo.empty:
            ramos_principales = primas_totales_ramo_periodo.astype(float).nlargest(
                min(TOP_N_RAMOS_PARA_LINEAS, len(primas_totales_ramo_periodo))).index.tolist()
        elif not ramos_significativos_df.empty:
            ramos_principales = ramos_significativos_df.astype(
                float).nlargest(TOP_N_RAMOS_PARA_LINEAS).index.tolist()
        else:
            ramos_principales = []

        df_plot = df_final_rellenado[df_final_rellenado['ramo_label'].isin(
            ramos_principales)]

        if df_plot.empty:
            return plot(generar_figura_sin_datos_plotly("No hay ramos principales con primas suficientes."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        fig = px.line(df_plot, x='mes_str', y='prima_mes_ramo', color='ramo_label',  # x ahora es 'mes_str'
                      labels={
                          'mes_str': 'Mes', 'prima_mes_ramo': 'Prima Emitida ($)', 'ramo_label': 'Ramo'},
                      title='Evolución Primas Mensuales por Ramo', markers=False)
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Mes: %{x}<br>Prima: $%{y:,.0f}<extra></extra>")

        layout_actualizado = BASE_LAYOUT_DASHBOARD.copy()
        layout_actualizado.update(
            xaxis={'title': {'text': None}, 'type': 'category',
                   'tickangle': 30},  # type: 'category' para strings
            yaxis={'title': {'text': "Prima ($)"}, 'tickprefix': '$'},
            height=500, legend_title_text='Ramo',
            legend=dict(orientation="h", yanchor="bottom",
                        y=-0.5, xanchor="center", x=0.5),
            margin=dict(t=70, b=150, l=70, r=30)
        )
        fig.update_layout(**layout_actualizado)

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    except Exception as e_global:
        return plot(generar_figura_sin_datos_plotly(f"Error generando gráfico ({type(e_global).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_resolucion_gauge(data_resolucion_recientes):
    if not data_resolucion_recientes or (data_resolucion_recientes.get('Resueltas', 0) == 0 and data_resolucion_recientes.get('Pendientes', 0) == 0):
        return plot(generar_figura_sin_datos_plotly("No hay datos de resolución reciente."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    try:
        data_filtrada = {k: v for k, v in data_resolucion_recientes.items(
        ) if isinstance(v, (int, float, Decimal)) and v >= 0}
        if not data_filtrada or sum(data_filtrada.values()) == 0:
            return plot(generar_figura_sin_datos_plotly("No hay reclamaciones recientes."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        labels = list(data_filtrada.keys())
        values = list(data_filtrada.values())

        colores_especificos_torta = []
        color_idx = 0
        for label in labels:
            if label == 'Resueltas':
                colores_especificos_torta.append(COLOR_PALETTE.get('success'))
            elif label == 'Pendientes':
                colores_especificos_torta.append(COLOR_PALETTE.get('warning'))
            else:
                colores_especificos_torta.append(
                    DEFAULT_PLOTLY_COLORS_CORPORATE[color_idx % len(DEFAULT_PLOTLY_COLORS_CORPORATE)])
                color_idx += 1

        fig = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=.35,
            marker_colors=colores_especificos_torta,
            textinfo='percent+label+value', hoverinfo='label+value+percent',
            insidetextorientation='radial')])

        layout_actualizado = BASE_LAYOUT_DASHBOARD.copy()
        layout_actualizado.pop('colorway', None)
        layout_actualizado.update(
            title_text='Estado Resolución Reclamos Recientes', showlegend=False,
            legend=dict(orientation="h", yanchor="bottom",
                        y=-0.15, xanchor="center", x=0.5),
            margin=dict(t=70, b=70, l=20, r=20), height=500
        )
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error en generar_grafico_resolucion_gauge: {e}", exc_info=True)
        return plot(generar_figura_sin_datos_plotly(f"Error ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_impuestos_por_categoria(data_dict):
    if not data_dict or not data_dict.get('Categoria') or not data_dict.get('IGTF') or not data_dict['Categoria']:
        return plot(generar_figura_sin_datos_plotly("No hay datos de IGTF por categoría."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    try:
        df = pd.DataFrame(
            {'Categoria': data_dict['Categoria'], 'IGTF': data_dict['IGTF']})
        df['IGTF'] = pd.to_numeric(df['IGTF'], errors='coerce').fillna(0.0)
        df = df[df['IGTF'] > 0].copy()  # Mantener solo categorías con valor
        if df.empty:
            return plot(generar_figura_sin_datos_plotly("No se recaudó IGTF en ninguna categoría."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

        # Ordenar por valor para una mejor visualización de la dona si hay muchas categorías
        df = df.sort_values(by='IGTF', ascending=False)

        labels = df['Categoria'].tolist()
        values = df['IGTF'].tolist()

        # Los colores vendrán del 'colorway' del BASE_LAYOUT_DASHBOARD
        # que ya tiene tu DEFAULT_PLOTLY_COLORS_CORPORATE

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.45,  # Para el efecto dona
            textinfo='percent',  # Mostrar solo porcentaje DENTRO del segmento
            insidetextorientation='radial',
            outsidetextfont=dict(size=10, color=COLOR_PALETTE.get(
                'text_main')),  # Fuente para etiquetas EXTERNAS
            marker=dict(
                # colors=DEFAULT_PLOTLY_COLORS_CORPORATE, # Opcional: forzar aquí si el layout no lo toma
                line=dict(color=COLOR_PALETTE.get(
                    'white', '#FFFFFF'), width=1.5)
            ),
            hoverinfo='label+value+percent',
            hovertemplate='<b>%{label}</b><br>IGTF: $%{value:,.2f}<br>Porcentaje: %{percent}<extra></extra>',
            # Para mostrar las etiquetas fuera con líneas:
            # Mueve las etiquetas (definidas por texttemplate en update_layout o aquí) fuera
            textposition='outside',
        )])

        total_igtf = df['IGTF'].sum()

        layout_actualizado = BASE_LAYOUT_DASHBOARD.copy()
        layout_actualizado.update(
            title_text='Distribución IGTF por Origen',
            showlegend=False,  # Leyenda oculta como solicitaste
            uniformtext_minsize=8,  # Tamaño mínimo para texto, puede ayudar
            uniformtext_mode='hide',  # Oculta texto si no cabe
            # Ajustar márgenes, 'pad' añade espacio entre el gráfico y el borde del margen
            margin=dict(t=80, b=50, l=30, r=30, pad=4),
            height=500,  # Altura fija
            # width=500, # Puedes probar fijando el ancho también si es necesario
            annotations=[dict(
                text=f'Total IGTF<br><b>${total_igtf:,.2f}</b>',
                x=0.5, y=0.5, font_size=16, showarrow=False,
                font_color=COLOR_PALETTE.get('text_main')
            )]
        )
        # Configuración específica para las etiquetas externas de la torta/dona
        fig.update_layout(**layout_actualizado)

        # Esto es para controlar cómo se muestran las etiquetas cuando textposition='outside'
        # Puedes experimentar con esto.
        # fig.update_traces(texttemplate="%{label}<br>%{percent}") # Ejemplo de qué mostrar fuera

        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(f"Error generando gráfico dona IGTF: {e}", exc_info=True)
        return plot(generar_figura_sin_datos_plotly(f"Error al generar gráfico IGTF ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


def generar_grafico_rentabilidad_neta_intermediario(data_intermediarios_bubble):
    if not data_intermediarios_bubble:
        return plot(generar_figura_sin_datos_plotly("No hay datos de cartera."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    try:
        # ... (Lógica de datos idéntica hasta tener df)
        df = pd.DataFrame(data_intermediarios_bubble)
        df['prima_total'] = pd.to_numeric(
            df['prima_total'], errors='coerce').fillna(0.0)
        df['rentabilidad_neta'] = pd.to_numeric(
            df['rentabilidad_neta'], errors='coerce').fillna(0.0)
        df['numero_contratos'] = pd.to_numeric(
            df['numero_contratos'], errors='coerce').fillna(0).astype(int)
        df['siniestros_totales'] = pd.to_numeric(
            df.get('siniestros_totales', 0.0), errors='coerce').fillna(0.0)
        df['comisiones_estimadas'] = pd.to_numeric(
            df.get('comisiones_estimadas', 0.0), errors='coerce').fillna(0.0)
        df = df[(df['prima_total'] > 0) & (df['numero_contratos'] > 0)]
        if df.empty:
            return plot(generar_figura_sin_datos_plotly("No hay intermediarios válidos."), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
        if not df['numero_contratos'].empty:
            min_c, max_c = df['numero_contratos'].min(
            ), df['numero_contratos'].max()
            if max_c > min_c:
                df['size_bubble'] = (
                    (df['numero_contratos'] - min_c) / (max_c - min_c)) * 20 + 10
            else:
                df['size_bubble'] = 15
        else:
            df['size_bubble'] = 10
        # --- FIN LÓGICA DATOS ---

        escala_color_rentabilidad_corp = [
            # Rojo corporativo para negativo
            [0.0, COLOR_PALETTE.get('danger')],
            [0.5, COLOR_PALETTE.get('neutral_light')],  # Neutro para cero
            # Verde corporativo para positivo
            [1.0, COLOR_PALETTE.get('success')]
        ]

        fig = px.scatter(
            df, x="rentabilidad_neta", y="prima_total",
            size="size_bubble", color="rentabilidad_neta",
            color_continuous_scale=escala_color_rentabilidad_corp,
            color_continuous_midpoint=0,
            hover_name="nombre_intermediario", size_max=30,
            labels={"rentabilidad_neta": "Rentabilidad Neta ($)", "prima_total": "Prima Total ($)", "size_bubble": "N° Contratos"})
        fig.update_traces(customdata=df[['numero_contratos', 'siniestros_totales', 'comisiones_estimadas']], hovertemplate=(
            "<b>%{hovertext}</b><br>" "Rentabilidad Neta: $%{x:,.0f}<br>" "Prima Total: $%{y:,.0f}<br>" "N° Contratos: %{customdata[0]}<br>" "<details><summary>Detalle</summary>" "Siniestros: $%{customdata[1]:,.0f}<br>" "Comisiones: $%{customdata[2]:,.0f}" "</details><extra></extra>"))
        fig.add_vline(x=0, line_width=1, line_dash="dash",
                      line_color=COLOR_PALETTE.get('neutral_dark', "grey"))

        layout_actualizado = BASE_LAYOUT_DASHBOARD.copy()
        # Para que color_continuous_scale funcione
        layout_actualizado.pop('colorway', None)
        layout_actualizado.update(
            title_text='Cartera Intermediarios: Prima vs. Rentabilidad',
            xaxis={'title': {
                'text': "Rentabilidad Neta ($)"}, 'tickprefix': '$', 'tickformat': ',.0f'},
            yaxis={'title': {
                'text': "Prima Emitida ($)"}, 'tickprefix': '$', 'tickformat': ',.0f'},
            coloraxis_colorbar_title_text='Rent.Neta', height=500, showlegend=False,
            margin=dict(t=70, b=50, l=70, r=30)
        )
        fig.update_layout(**layout_actualizado)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        logger.error(
            f"Error en generar_grafico_rentabilidad_neta_intermediario: {e}", exc_info=True)
        return plot(generar_figura_sin_datos_plotly(f"Error ({type(e).__name__})"), output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)


logger_rgv_debug = logging.getLogger(
    "myapp.views.ReporteGeneralView_DEBUG_FULL")


def log_estado_contratos_problematicos(logger_instance, momento_descripcion, fechas_problematicas_obj):
    logger_instance.info(
        f"--- {momento_descripcion}: Verificando ContratosIndividuales con fechas problemáticas ---")
    contratos_ind_debug = ContratoIndividual.objects.filter(
        fecha_emision__date__in=fechas_problematicas_obj)
    if not contratos_ind_debug.exists():
        logger_instance.info(
            f"    No se encontraron ContratosIndividuales con esas fechas en este punto.")
    for c_ind in contratos_ind_debug:
        fecha_em = c_ind.fecha_emision
        is_naive = django_timezone.is_naive(
            fecha_em) if fecha_em else "N/A (None)"
        tz_info = getattr(fecha_em, 'tzinfo', 'N/A') if fecha_em else "N/A"
        logger_instance.info(
            f"    CI PK {c_ind.pk} - fecha_emision: {fecha_em} (Naive: {is_naive}, TZ: {tz_info})"
        )
        if is_naive is True:
            logger_instance.error(
                f"    !!!!!!!!!! CI PK {c_ind.pk} ES NAIVE EN: {momento_descripcion} !!!!!!!!!!!")

    logger_instance.info(
        f"--- {momento_descripcion}: Verificando ContratosColectivos con fechas problemáticas ---")
    contratos_col_debug = ContratoColectivo.objects.filter(
        fecha_emision__date__in=fechas_problematicas_obj)
    if not contratos_col_debug.exists():
        logger_instance.info(
            f"    No se encontraron ContratosColectivos con esas fechas en este punto.")
    for c_col in contratos_col_debug:
        fecha_em = c_col.fecha_emision
        is_naive = django_timezone.is_naive(
            fecha_em) if fecha_em else "N/A (None)"
        tz_info = getattr(fecha_em, 'tzinfo', 'N/A') if fecha_em else "N/A"
        logger_instance.info(
            f"    CC PK {c_col.pk} - fecha_emision: {fecha_em} (Naive: {is_naive}, TZ: {tz_info})"
        )
        if is_naive is True:
            logger_instance.error(
                f"    !!!!!!!!!! CC PK {c_col.pk} ES NAIVE EN: {momento_descripcion} !!!!!!!!!!!")
    logger_instance.info(f"--- {momento_descripcion}: Fin de verificación ---")


logger_rgv = logging.getLogger(
    "myapp.views.ReporteGeneralView")  # Logger para esta vista

# Si tienes esta función auxiliar, asegúrate de que esté definida o importada


def obtener_datos_tabla_resumen_comisiones():
    # Implementación de ejemplo, ajusta a tu lógica real
    # Esta función debe existir o el código fallará.
    try:

        return {
            'total_registrado_comisiones': RegistroComision.objects.aggregate(total=Coalesce(Sum('monto_comision'), Decimal('0.00')))['total'],
            'total_pagado_comisiones': RegistroComision.objects.filter(estatus_pago_comision='PAGADA').aggregate(total=Coalesce(Sum('monto_comision'), Decimal('0.00')))['total'],
            'total_pendiente_comisiones': RegistroComision.objects.filter(estatus_pago_comision='PENDIENTE').aggregate(total=Coalesce(Sum('monto_comision'), Decimal('0.00')))['total'],
            'total_anulado_comisiones': RegistroComision.objects.filter(estatus_pago_comision='ANULADA').aggregate(total=Coalesce(Sum('monto_comision'), Decimal('0.00')))['total'],
        }
    except Exception as e:
        logger_rgv.error(
            f"Error en obtener_datos_tabla_resumen_comisiones: {e}")
        return {}


class ReporteGeneralView(LoginRequiredMixin, TemplateView):
    template_name = 'reporte_general.html'
    TASA_IGTF = Decimal('0.03')

    # --- MÉTODOS PRIVADOS PARA GENERAR GRÁFICOS ---
    def _generar_figura_sin_datos(self, mensaje="No hay datos disponibles"):
        fig = go.Figure()
        fig.add_annotation(text=mensaje, xref="paper", yref="paper", x=0.5,
                           y=0.5, showarrow=False, font={"size": 16, "color": "#888"})
        fig.update_layout(xaxis={'visible': False}, yaxis={
                          'visible': False}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_antiguedad_contratos(self):
        hoy = date.today()
        antiguedad_data = []
        for c in list(self.qs_contratos_ind.filter(fecha_inicio_vigencia__lte=hoy).values('estatus', 'fecha_inicio_vigencia')) + \
                list(self.qs_contratos_col.filter(fecha_inicio_vigencia__lte=hoy).values('estatus', 'fecha_inicio_vigencia')):
            if c.get('fecha_inicio_vigencia'):
                antiguedad_data.append({'estatus_code': c['estatus'], 'antiguedad_dias': (
                    hoy - c['fecha_inicio_vigencia']).days})
        if not antiguedad_data:
            return self._generar_figura_sin_datos("No hay datos de antigüedad.")
        df = pd.DataFrame(antiguedad_data)
        df_avg = df.groupby('estatus_code')['antiguedad_dias'].mean().round(0)
        data_antiguedad = {dict(CommonChoices.ESTADOS_VIGENCIA).get(
            k, k): float(v) for k, v in df_avg.to_dict().items()}
        df_plot = pd.DataFrame(list(data_antiguedad.items()), columns=[
                               'Estatus', 'Antigüedad Promedio (días)']).sort_values('Antigüedad Promedio (días)')
        fig = px.bar(df_plot, x='Antigüedad Promedio (días)', y='Estatus',
                     orientation='h', title='Antigüedad Promedio Contratos', text_auto=True)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', font_color='#fff')
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_tipos_reclamacion(self):
        tipo_rec_map = dict(CommonChoices.TIPO_RECLAMACION)
        data_top_tipos = [(tipo_rec_map.get(i['tipo_reclamacion'], i['tipo_reclamacion']), float(i['avg_monto'])) for i in self.qs_reclamaciones.filter(estado__in=[
            'ABIERTA', 'EN_PROCESO']).values('tipo_reclamacion').annotate(avg_monto=Avg('monto_reclamado')).filter(avg_monto__gt=0).order_by('-avg_monto')[:5]]
        if not data_top_tipos:
            return self._generar_figura_sin_datos("No hay reclamaciones pendientes.")
        df = pd.DataFrame(data_top_tipos, columns=['Tipo', 'Monto Promedio ($)']).sort_values(
            'Monto Promedio ($)', ascending=True)
        fig = px.bar(df, x='Monto Promedio ($)', y='Tipo', orientation='h',
                     title='Tipos de Reclamo Pendientes (Costo Prom.)', text_auto='.2s')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', font_color='#fff')
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_primas_ramo(self):
        primas_por_ramo = collections.defaultdict(Decimal)
        ramo_map = dict(CommonChoices.RAMO)
        for item in self.qs_contratos_ind.values('ramo').annotate(total=Sum('monto_total')):
            primas_por_ramo[ramo_map.get(
                item['ramo'], "N/A")] += item['total'] or Decimal('0.0')
        for item in self.qs_contratos_col.values('ramo').annotate(total=Sum('monto_total')):
            primas_por_ramo[ramo_map.get(
                item['ramo'], "N/A")] += item['total'] or Decimal('0.0')
        if not primas_por_ramo:
            return self._generar_figura_sin_datos("No hay primas.")
        df = pd.DataFrame(list(primas_por_ramo.items()), columns=[
                          'Ramo', 'Total Primas']).sort_values('Total Primas', ascending=False)
        fig = px.pie(df, names='Ramo', values='Total Primas',
                     title='Distribución de Primas por Ramo', hole=.4)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#fff',
                          showlegend=False, legend={'orientation': 'h', 'yanchor': 'bottom', 'y': -0.2})
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_resolucion_gauge(self):
        hoy = date.today()
        recs_recientes = self.qs_reclamaciones.filter(Q(fecha_reclamo__gte=hoy - timedelta(
            days=90)) | Q(fecha_modificacion__gte=django_timezone.now() - timedelta(days=90)))
        resueltas_count = recs_recientes.filter(
            estado__in=['CERRADA', 'PAGADA', 'RECHAZADA']).count()
        pendientes_count = recs_recientes.exclude(
            estado__in=['CERRADA', 'PAGADA', 'RECHAZADA']).count()
        total = resueltas_count + pendientes_count
        if total == 0:
            return self._generar_figura_sin_datos("No hay reclamaciones recientes.")
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=resueltas_count,
            title={'text': "Resolución Reclamos (90 días)"},
            gauge={'axis': {'range': [None, total]},
                   'bar': {'color': "#198754"}}
        ))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='#fff')
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_igtf(self):
        pagos_con_igtf = Pago.objects.filter(activo=True, aplica_igtf_pago=True, monto_pago__gt=0).select_related(
            'factura__contrato_individual', 'factura__contrato_colectivo')
        if not pagos_con_igtf:
            return self._generar_figura_sin_datos("No hay recaudación de IGTF.")
        data_igtf = collections.defaultdict(Decimal)
        ramo_map = dict(CommonChoices.RAMO)
        for pago in pagos_con_igtf:
            igtf_pago = (pago.monto_pago / (Decimal('1') +
                         self.TASA_IGTF)) * self.TASA_IGTF
            contrato = pago.factura.get_contrato_asociado if pago.factura else None
            categoria = f"Ramo: {ramo_map.get(contrato.ramo, contrato.ramo)}" if contrato and contrato.ramo else "Otros Pagos"
            data_igtf[categoria] += igtf_pago
        df = pd.DataFrame(list(data_igtf.items()),
                          columns=['Categoria', 'IGTF'])
        fig = px.pie(df, names='Categoria', values='IGTF',
                     title='Distribución IGTF por Origen', hole=.4)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#fff',
                          showlegend=False, legend={'orientation': 'h', 'yanchor': 'bottom', 'y': -0.2})
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_rentabilidad(self):
        data_inter_bubble = [{'nombre_intermediario': i.nombre_completo, 'prima_total': float(i.pt), 'rentabilidad_neta': float(i.pt - i.st - (i.pt * i.porcentaje_comision / 100)), 'numero_contratos': i.n_ct} for i in Intermediario.objects.filter(activo=True).annotate(pt=Coalesce(Sum('contratoindividual__monto_total'), Decimal('0.0')) + Coalesce(Sum(
            'contratos_colectivos__monto_total'), Decimal('0.0')), st=Coalesce(Sum('contratoindividual__reclamacion__monto_reclamado'), Decimal('0.0')) + Coalesce(Sum('contratos_colectivos__reclamacion__monto_reclamado'), Decimal('0.0')), n_ct=Count('contratoindividual', distinct=True) + Count('contratos_colectivos', distinct=True)).filter(pt__gt=0).order_by('-pt')[:15]]
        if not data_inter_bubble:
            return self._generar_figura_sin_datos("No hay datos de cartera.")
        df = pd.DataFrame(data_inter_bubble)
        fig = px.scatter(df, x="rentabilidad_neta", y="prima_total", size="numero_contratos", color="nombre_intermediario",
                         hover_name="nombre_intermediario", title='Cartera Intermediarios: Prima vs. Rentabilidad')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', font_color='#fff', showlegend=False)
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'active_tab': 'reportes',
                       'page_title': 'Reporte General del Sistema', 'error': None})

        try:
            # FASE 0: Definir Querysets base
            self.qs_contratos_ind = ContratoIndividual.objects.filter(
                activo=True)
            self.qs_contratos_col = ContratoColectivo.objects.filter(
                activo=True)
            self.qs_reclamaciones = Reclamacion.objects.filter(activo=True)
            self.qs_comisiones = RegistroComision.objects.all()

            # FASE 1: KPIs
            hoy = date.today()
            kpi_total_contratos_individuales_count = self.qs_contratos_ind.count()
            kpi_total_contratos_colectivos_count = self.qs_contratos_col.count()
            kpi_total_contratos = kpi_total_contratos_individuales_count + \
                kpi_total_contratos_colectivos_count
            ganancias_brutas_pool = self.qs_contratos_ind.aggregate(t=Coalesce(Sum('monto_total'), Decimal(
                '0.0')))['t'] + self.qs_contratos_col.aggregate(t=Coalesce(Sum('monto_total'), Decimal('0.0')))['t']
            total_comisiones_generadas = self.qs_comisiones.filter(estatus_pago_comision__in=[
                                                                   'PENDIENTE', 'PAGADA']).aggregate(t=Coalesce(Sum('monto_comision'), Decimal('0.0')))['t']
            total_siniestros_incurridos = self.qs_reclamaciones.filter(
                estado__in=['APROBADA', 'PAGADA']).aggregate(t=Coalesce(Sum('monto_reclamado'), Decimal('0.0')))['t']
            promedio_duracion = self.qs_reclamaciones.filter(fecha_cierre_reclamo__isnull=False, fecha_reclamo__isnull=False).annotate(
                d=ExpressionWrapper(F('fecha_cierre_reclamo') - F('fecha_reclamo'), output_field=DurationField())).aggregate(p=Avg('d'))['p']
            facturas_vencidas_qs = Factura.objects.filter(
                activo=True, pagada=False, estatus_factura='VENCIDA')
            comisiones_pendientes_qs = self.qs_comisiones.filter(
                estatus_pago_comision='PENDIENTE')
            pagos_con_igtf = Pago.objects.filter(
                activo=True, aplica_igtf_pago=True, monto_pago__gt=0)
            total_igtf = sum((p.monto_pago / (Decimal('1') + self.TASA_IGTF))
                             * self.TASA_IGTF for p in pagos_con_igtf)

            context.update({
                'kpi_monto_total_contratos': ganancias_brutas_pool,
                'kpi_total_comisiones_generadas': total_comisiones_generadas,
                'kpi_ganancia_neta_pool': ganancias_brutas_pool - total_comisiones_generadas,
                'kpi_monto_total_pagado_facturas': Pago.objects.filter(activo=True, factura__isnull=False).aggregate(t=Coalesce(Sum('monto_pago'), Decimal('0.0')))['t'],
                'kpi_ratio_siniestralidad': (total_siniestros_incurridos / ganancias_brutas_pool * 100) if ganancias_brutas_pool > 0 else Decimal('0.0'),
                'kpi_total_siniestros_incurridos': total_siniestros_incurridos,
                'kpi_tiempo_promedio_resolucion': promedio_duracion.days if promedio_duracion else 0,
                'kpi_total_contratos': kpi_total_contratos,
                'kpi_total_contratos_individuales_count': kpi_total_contratos_individuales_count,
                'kpi_total_contratos_colectivos_count': kpi_total_contratos_colectivos_count,
                'kpi_total_afiliados_ind': AfiliadoIndividual.objects.filter(activo=True).count(),
                'kpi_total_afiliados_col': AfiliadoColectivo.objects.filter(activo=True).count(),
                'kpi_total_reclamaciones': self.qs_reclamaciones.count(),
                'kpi_facturas_vencidas_conteo': facturas_vencidas_qs.count(),
                'kpi_facturas_vencidas_monto': facturas_vencidas_qs.aggregate(t=Coalesce(Sum('monto_pendiente'), Decimal('0.0')))['t'],
                'kpi_comisiones_pendientes_conteo': comisiones_pendientes_qs.count(),
                'kpi_comisiones_pendientes_monto': comisiones_pendientes_qs.aggregate(t=Coalesce(Sum('monto_comision'), Decimal('0.0')))['t'],
                'kpi_total_igtf_recaudado': total_igtf.quantize(Decimal('0.01')),
            })

            # FASE 2: GRÁFICOS
            context['plotly_contratos_estado_html'] = self._generar_grafico_antiguedad_contratos()
            context['plotly_reclamaciones_estado_html'] = self._generar_grafico_tipos_reclamacion()
            context['plotly_ramos_monto_html'] = self._generar_grafico_primas_ramo()
            context['plotly_resolucion_gauge_html'] = self._generar_grafico_resolucion_gauge()
            context['plotly_impuestos_categoria_html'] = self._generar_grafico_igtf()
            context['plotly_rentabilidad_intermediario_html'] = self._generar_grafico_rentabilidad()

            # FASE 3: TABLAS
            context['datos_tabla_comisiones'] = obtener_datos_tabla_resumen_comisiones()
            context['table_top_tipos_reclamacion'] = [{'tipo': dict(CommonChoices.TIPO_RECLAMACION).get(i['tipo_reclamacion'], i['tipo_reclamacion']), 'cantidad': i['cantidad']}
                                                      for i in self.qs_reclamaciones.values('tipo_reclamacion').annotate(cantidad=Count('id')).filter(cantidad__gt=0).order_by('-cantidad')[:10]]
            context['table_facturas_antiguas'] = facturas_vencidas_qs.select_related('contrato_individual__afiliado', 'contrato_colectivo').annotate(
                dias_vencida=ExpressionWrapper(django_timezone.now().date() - F('vigencia_recibo_hasta'), output_field=DurationField())).order_by('-dias_vencida')[:10]
            context['table_top_intermediarios'] = Intermediario.objects.filter(activo=True).annotate(num_contratos=(Count('contratoindividual', distinct=True) + Count('contratos_colectivos', distinct=True)), monto_contratos=(
                Coalesce(Sum('contratoindividual__monto_total'), Decimal('0.0')) + Coalesce(Sum('contratos_colectivos__monto_total'), Decimal('0.0')))).filter(num_contratos__gt=0).order_by('-monto_contratos')[:10]

            resumen_ramo = []
            ramo_map = dict(CommonChoices.RAMO)
            for ramo_code in set(self.qs_contratos_ind.values_list('ramo', flat=True)) | set(self.qs_contratos_col.values_list('ramo', flat=True)):
                primas = self.qs_contratos_ind.filter(ramo=ramo_code).aggregate(t=Coalesce(Sum('monto_total'), Decimal('0.0')))[
                    't'] + self.qs_contratos_col.filter(ramo=ramo_code).aggregate(t=Coalesce(Sum('monto_total'), Decimal('0.0')))['t']
                siniestros = self.qs_reclamaciones.filter(Q(contrato_individual__ramo=ramo_code) | Q(contrato_colectivo__ramo=ramo_code), estado__in=[
                                                          'APROBADA', 'PAGADA']).aggregate(t=Coalesce(Sum('monto_reclamado'), Decimal('0.0')))['t']
                resumen_ramo.append({'ramo_nombre': ramo_map.get(ramo_code, ramo_code), 'total_primas': primas,
                                    'total_siniestros': siniestros, 'ratio_siniestralidad': (siniestros / primas * 100) if primas > 0 else Decimal('0.0')})
            context['table_resumen_por_ramo'] = sorted(
                resumen_ramo, key=lambda x: x['total_primas'], reverse=True)

        except Exception as e:
            logger.error(
                f"Error CRÍTICO generando datos para ReporteGeneralView: {e}", exc_info=True)
            context[
                'error'] = f"Ocurrió un error grave al calcular los datos del reporte: {e}"

        return context


# Diccionario modelos_busqueda (sin cambios)
modelos_busqueda = {
    'usuario': {'nombre': ('Usuario'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('email', 'Correo Electrónico'), ('tipo_usuario', 'Tipo Usuario'), ('fecha_nacimiento', 'Fecha Nacimiento'), ('departamento', 'Departamento'), ('telefono', 'Teléfono'), ('direccion', 'Dirección'), ('intermediario', 'Intermediario'), ('username', 'Nombre de Usuario'), ('is_staff', 'Es Staff'), ('is_active', 'Está Activo'), ('is_superuser', 'Es Superusuario'), ('last_login', 'Último Login'), ('date_joined', 'Fecha de Registro')]},
    'contratoindividual': {'nombre': ('Contrato Individual'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('fecha_creacion', 'Fecha de Creación'), ('fecha_modificacion', 'Fecha de modificación'), ('ramo', 'Ramo'), ('forma_pago', 'Forma de Pago'), ('pagos_realizados', 'Pagos Realizados'), ('estatus', 'Estatus'), ('estado_contrato', 'Estado Contrato'), ('numero_contrato', 'Número de Contrato'), ('numero_poliza', 'Número de Póliza'), ('fecha_emision', 'Fecha de Emisión del Contrato'), ('fecha_inicio_vigencia', 'Fecha de Inicio de Vigencia'), ('fecha_fin_vigencia', 'Fecha de Fin de Vigencia'), ('monto_total', 'Monto Total del Contrato'), ('intermediario', 'Intermediario'), ('consultar_afiliados_activos', 'Consultar en data de afiliados activos'), ('tipo_identificacion_contratante', 'Tipo de Identificación del Contratante'), ('contratante_cedula', 'Cédula del Contratante'), ('contratante_nombre', 'Nombre del Contratante'), ('direccion_contratante', 'Dirección del Contratante'), ('telefono_contratante', 'Teléfono del Contratante'), ('email_contratante', 'Email del Contratante'), ('cantidad_cuotas', 'Cantidad de Cuotas'), ('afiliado', 'Afiliado'), ('plan_contratado', 'Plan Contratado'), ('comision_recibo', 'Comisión Recibo'), ('certificado', 'Certificado'), ('importe_anual_contrato', 'Importe Anual del Contrato'), ('importe_recibo_contrato', 'Importe Recibo del Contrato'), ('fecha_inicio_vigencia_recibo', 'Fecha Inicio Vigencia Recibo'), ('fecha_fin_vigencia_recibo', 'Fecha Fin Vigencia Recibo'), ('criterio_busqueda', 'Criterio de Búsqueda'), ('dias_transcurridos_ingreso', 'Días Transcurridos Ingreso'), ('estatus_detalle', 'Estatus Detalle'), ('estatus_emision_recibo', 'Estatus Emisión Recibo')]},
    'afiliadoindividual': {'nombre': ('Afiliado Individual'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('tipo_identificacion', 'Tipo de Identificación'), ('cedula', 'Cédula'), ('estado_civil', 'Estado Civil'), ('sexo', 'Sexo'), ('parentesco', 'Parentesco'), ('fecha_nacimiento', 'Fecha Nacimiento'), ('nacionalidad', 'Nacionalidad'), ('zona_postal', 'Zona Postal'), ('estado', 'Estado'), ('municipio', 'Municipio'), ('ciudad', 'Ciudad'), ('fecha_ingreso', 'Fecha Ingreso'), ('direccion_habitacion', 'Dirección Habitación'), ('telefono_habitacion', 'Teléfono Habitación'), ('direccion_oficina', 'Dirección Oficina'), ('telefono_oficina', 'Teléfono Oficina'), ('codigo_validacion', 'Código de Validación'), ('activo', 'Estado activo')]},
    'afiliadocolectivo': {'nombre': ('Afiliado Colectivo'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('activo', 'Activo'), ('razon_social', 'Razón Social'), ('rif', 'RIF'), ('tipo_empresa', 'Tipo Empresa'), ('direccion_comercial', 'Dirección Fiscal'), ('estado', 'Estado'), ('municipio', 'Municipio'), ('ciudad', 'Ciudad'), ('zona_postal', 'Zona Postal'), ('telefono_contacto', 'Teléfono Contacto'), ('email_contacto', 'Email Contacto')]},
    'contratocolectivo': {'nombre': ('Contrato Colectivo'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('tipo_empresa', 'Tipo Empresa'), ('criterio_busqueda', 'Criterio de Búsqueda'), ('razon_social', 'Razón Social'), ('rif', 'RIF'), ('cantidad_empleados', 'Cantidad Empleados'), ('direccion_comercial', 'Dirección Comercial'), ('zona_postal', 'Zona Postal'), ('numero_recibo', 'Número Recibo'), ('comision_recibo', 'Comisión Recibo'), ('estado', 'Estado'), ('codigo_validacion', 'Código de Validación')]},
    'intermediario': {'nombre': ('Intermediario'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('codigo', 'Código'), ('nombre_completo', 'Nombre Completo'), ('rif', 'RIF'), ('direccion_fiscal', 'Dirección Fiscal'), ('telefono_contacto', 'Teléfono Contacto'), ('email_contacto', 'Email Contacto'), ('intermediario_relacionado', 'Intermediario Relacionado'), ('porcentaje_comision', 'Porcentaje Comisión')]},
    'factura': {'nombre': ('Factura'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('estatus_factura', 'Estatus Factura'), ('contrato_individual', 'Contrato Individual'), ('contrato_colectivo', 'Contrato Colectivo'), ('ramo', 'Ramo'), ('vigencia_recibo_desde', 'Vigencia Recibo Desde'), ('vigencia_recibo_hasta', 'Vigencia Recibo Hasta'), ('observaciones', 'Observaciones de la Factura')]},
    'reclamacion': {'nombre': ('Reclamación'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('tipo_reclamacion', 'Tipo Reclamación'), ('estado', 'Estado'), ('descripcion_reclamo', 'Descripción Reclamo'), ('monto_reclamado', 'Monto Reclamado'), ('contrato_individual', 'Contrato Individual'), ('contrato_colectivo', 'Contrato Colectivo'), ('fecha_reclamo', 'Fecha Reclamo'), ('usuario_asignado', 'Usuario Asignado'), ('observaciones_internas', 'Observaciones Internas'), ('observaciones_cliente', 'Observaciones Cliente')]},
    'pago': {'nombre': ('Pago'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('forma_pago', 'Forma de Pago'), ('reclamacion', 'Reclamación'), ('fecha_pago', 'Fecha Pago'), ('monto_pago', 'Monto Pago'), ('referencia_pago', 'Referencia Pago'), ('fecha_notificacion_pago', 'Fecha Notificación Pago'), ('observaciones_pago', 'Observaciones Pago'), ('factura', 'Factura')]},
    'tarifa': {'nombre': ('Tarifa'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('rango_etario', 'Rango Etario'), ('ramo', 'Ramo'), ('fecha_aplicacion', 'Fecha Aplicación'), ('monto_anual', 'Monto Anual'), ('tipo_fraccionamiento', 'Tipo Fraccionamiento')]},
    'auditoriasistema': {'nombre': ('Auditoria Sistema'), 'campos': [('id', 'ID'), ('tipo_accion', 'Tipo Acción'), ('resultado_accion', 'Resultado Acción'), ('usuario__username', 'Usuario'), ('tabla_afectada', 'Tabla Afectada'), ('registro_id_afectado', 'Registro ID Afectado'), ('detalle_accion', 'Detalle Acción'), ('direccion_ip', 'Dirección IP'), ('agente_usuario', 'Agente Usuario'), ('tiempo_inicio', 'Tiempo Inicio'), ('tiempo_final', 'Tiempo Final'), ('control_fecha_actual', 'Control Fecha Actual')]},
}


@require_GET
def get_campos_por_modelo(request):
    modelo = request.GET.get('modelo')
    if modelo and modelo in modelos_busqueda:
        campos = modelos_busqueda[modelo]['campos']
        return JsonResponse({'campos': campos})
    else:
        return JsonResponse({'campos': [], 'error': 'Modelo no encontrado'}, status=400)


@method_decorator(csrf_protect, name='dispatch')
class BusquedaAvanzadaView(LoginRequiredMixin, TemplateView):
    template_name = 'busqueda_avanzada.html'
    MODELOS_VALIDOS = {
        'contratoindividual': ContratoIndividual, 'contratocolectivo': ContratoColectivo,
        'afiliadoindividual': AfiliadoIndividual, 'afiliadocolectivo': AfiliadoColectivo,
        'reclamacion': Reclamacion, 'intermediario': Intermediario, 'factura': Factura,
        'pago': Pago, 'tarifa': Tarifa, 'auditoriasistema': AuditoriaSistema, 'usuario': Usuario,
    }
    OPTIMIZACIONES_BUSQUEDA = {
        'contratoindividual': ['select_related', ('intermediario', 'afiliado')], 'contratocolectivo': ['select_related', ('intermediario',)],
        'afiliadocolectivo': [], 'reclamacion': ['select_related', ('contrato_individual', 'contrato_colectivo', 'usuario_asignado')],
        'factura': ['select_related', ('contrato_individual', 'contrato_colectivo', 'intermediario')], 'pago': ['select_related', ('reclamacion', 'factura')],
        'auditoriasistema': ['select_related', ('usuario',)], 'usuario': ['select_related', ('intermediario',)],
        'intermediario': [], 'tarifa': [],
    }

    def realizar_busqueda(self, modelo_str, campo, valor, fecha_desde=None, fecha_hasta=None):
        if modelo_str not in self.MODELOS_VALIDOS:
            return [], "Modelo no válido para búsqueda."
        ModelClass = self.MODELOS_VALIDOS[modelo_str]
        permiso_requerido = f'myapp.view_{ModelClass._meta.model_name}'
        if not self.request.user.has_perm(permiso_requerido):
            return [], f"No tiene permiso para ver registros de {ModelClass._meta.verbose_name_plural}."

        try:
            # Obtenemos la instancia del campo para verificar sus propiedades
            field_instance = ModelClass._meta.get_field(campo.split('__')[0])
        except FieldDoesNotExist:
            return [], f"Campo '{campo}' no es válido para buscar en {ModelClass._meta.verbose_name}."

        # --- INICIO DE LA LÓGICA DE CORRECCIÓN ---

        campo_de_busqueda = campo
        valor_de_busqueda = valor
        lookup_exacto = False  # Flag para forzar una búsqueda exacta

        # 1. Manejar campos únicos encriptados que ahora tienen un hash
        campo_hash_asociado = f"{campo}_hash"
        if hasattr(ModelClass, campo_hash_asociado):
            logger.info(
                f"Búsqueda detectada en campo con hash: '{campo}'. Usando '{campo_hash_asociado}'.")
            # Si el usuario busca por cédula o RIF, usamos el hash para una búsqueda exacta.
            hash_a_buscar = hashlib.sha256(valor.encode('utf-8')).hexdigest()

            # Actualizamos las variables que usaremos para construir la consulta Q
            campo_de_busqueda = campo_hash_asociado
            valor_de_busqueda = hash_a_buscar
            # Forzamos una búsqueda exacta (ej. campo_hash='valor')
            lookup_exacto = True

        # 2. Advertir sobre búsquedas en otros campos encriptados sin hash
        elif 'encrypted_model_fields' in str(type(field_instance.__class__)):
            logger.warning(f"ADVERTENCIA: Se está intentando una búsqueda por el campo encriptado '{campo}' "
                           f"en el modelo '{modelo_str}'. Esta búsqueda probablemente no devolverá resultados.")
            # Opcional: devolver un error amigable al usuario
            # return [], f"La búsqueda por '{field_instance.verbose_name}' no está permitida por razones de seguridad."

        queryset = ModelClass.objects.all()
        opt_config = self.OPTIMIZACIONES_BUSQUEDA.get(modelo_str)
        if opt_config:
            opt_type, opt_fields = opt_config
            if opt_type == 'select_related':
                queryset = queryset.select_related(*opt_fields)
            elif opt_type == 'prefetch_related':
                queryset = queryset.prefetch_related(*opt_fields)

        filtros = Q()
        error_filtro = None
        try:
            field_type = type(field_instance)
            if field_type in (models.DateField, models.DateTimeField) and fecha_desde and fecha_hasta:
                try:
                    dt_desde = datetime.strptime(fecha_desde, '%Y-%m-%d')
                    dt_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                    if field_type == models.DateField:
                        dt_hasta = dt_hasta.replace(
                            hour=23, minute=59, second=59, microsecond=999999)
                    filtros &= Q(**{f'{campo}__range': (dt_desde, dt_hasta)})
                    if valor:
                        # Asume texto si hay valor extra
                        filtros &= Q(**{f'{campo}__icontains': valor})
                except ValueError:
                    error_filtro = "Formato de fecha inválido (use DD/MM/YYYY)."
            elif valor:
                if field_type in (models.CharField, models.TextField, models.EmailField):
                    filtros &= Q(**{f'{campo}__icontains': valor})
                elif field_type in (models.IntegerField, models.AutoField, models.PositiveIntegerField):
                    try:
                        filtros &= Q(**{campo: int(valor)})
                    except ValueError:
                        error_filtro = f"Valor '{valor}' debe ser un número entero."
                elif field_type in (models.DecimalField, models.FloatField):
                    try:
                        # Reemplazar coma por punto
                        filtros &= Q(
                            **{campo: Decimal(valor.replace(',', '.'))})
                    except ValueError:
                        error_filtro = f"Valor '{valor}' debe ser un número decimal."
                elif field_type == models.BooleanField:
                    if valor.lower() in ['true', '1', 'si', 'sí', 'activo']:
                        filtros &= Q(**{campo: True})
                    elif valor.lower() in ['false', '0', 'no', 'inactivo']:
                        filtros &= Q(**{campo: False})
                    else:
                        error_filtro = f"Valor '{valor}' no válido (use true/false, 1/0)."
                elif field_type in (models.ForeignKey, models.OneToOneField):
                    if valor.isdigit():
                        filtros &= Q(**{f'{campo}__pk': int(valor)})
                    else:
                        # Ajustar campo representativo
                        filtros &= Q(
                            **{f'{campo}__nombre_completo__icontains': valor})
                else:
                    filtros &= Q(**{f'{campo}__icontains': valor})
            elif not (fecha_desde and fecha_hasta):
                pass  # No hacer nada si no hay criterio

            if error_filtro:
                return [], error_filtro
            resultados = queryset.filter(filtros)

        except Exception as e:
            logger.error(
                f"Error filtrando búsqueda ({modelo_str}, {campo}, {valor}): {e}", exc_info=True)
            return [], f"Error en parámetros de búsqueda: {e}"

        order_by_field = campo if '__' not in campo else '-fecha_creacion'
        try:
            ModelClass._meta.get_field(order_by_field.lstrip('-'))
        except FieldDoesNotExist:
            order_by_field = '-fecha_creacion' if hasattr(
                ModelClass, 'fecha_creacion') else '-pk'
        resultados = resultados.order_by(order_by_field)[:500]
        return resultados, None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resultados = []
        total_resultados = 0
        error_mensaje = None
        modelo_param = self.request.GET.get('modelo', '')
        campo_param = self.request.GET.get('campo', '')
        valor_param = self.request.GET.get('valor', '')
        fecha_desde_param = self.request.GET.get('fecha_desde', '')
        fecha_hasta_param = self.request.GET.get('fecha_hasta', '')

        try:
            modelos_permitidos = {k: data['nombre'] for k, data in modelos_busqueda.items(
            ) if k in self.MODELOS_VALIDOS and self.request.user.has_perm(f'myapp.view_{self.MODELOS_VALIDOS[k]._meta.model_name}')}
            context['modelos_busqueda'] = modelos_permitidos
            context['campos_modelo_actual'] = modelos_busqueda.get(
                modelo_param, {}).get('campos', [])

            if modelo_param and campo_param and (valor_param or (fecha_desde_param and fecha_hasta_param)):
                resultados, error_mensaje = self.realizar_busqueda(
                    modelo_param, campo_param, valor_param, fecha_desde_param, fecha_hasta_param)
                total_resultados = len(resultados)
                if not error_mensaje:
                    try:
                        AuditoriaSistema.objects.create(
                            usuario=self.request.user, tipo_accion='CONSULTA_AVANZADA', tabla_afectada=modelo_param,
                            detalle_accion=f"Modelo: {modelo_param}, Campo: {campo_param}, Valor: '{valor_param}', Fechas: {fecha_desde_param}-{fecha_hasta_param}",
                            direccion_ip=self.request.META.get('REMOTE_ADDR', ''), agente_usuario=self.request.META.get('HTTP_USER_AGENT', ''),
                            resultado_accion='EXITO', registro_id_afectado=total_resultados
                        )
                    except Exception as audit_e:
                        logger.error(
                            f"Error auditoría búsqueda avanzada: {audit_e}")

        except PermissionDenied as e:
            error_mensaje = str(e)
            messages.error(self.request, error_mensaje)
        except Exception as e:
            logger.error(
                "Error en BusquedaAvanzadaView.get_context_data: %s", str(e), exc_info=True)
            error_mensaje = "Ocurrió un error inesperado al preparar la búsqueda."
            messages.error(self.request, error_mensaje)
            # Auditoría de error
            if self.request.user.is_authenticated:
                try:
                    AuditoriaSistema.objects.create(usuario=self.request.user, tipo_accion='CONSULTA_AVANZADA', tabla_afectada=modelo_param or 'desconocida', detalle_accion=f"Error preparando búsqueda: {str(e)[:200]}", direccion_ip=self.request.META.get(
                        'REMOTE_ADDR', ''), agente_usuario=self.request.META.get('HTTP_USER_AGENT', ''), resultado_accion='ERROR')
                except:
                    pass

        context['resultados'] = resultados
        context['total_resultados'] = total_resultados
        context['error_mensaje'] = error_mensaje
        context['selected_modelo'] = modelo_param
        context['selected_campo'] = campo_param
        context['search_valor'] = valor_param
        context['search_fecha_desde'] = fecha_desde_param
        context['search_fecha_hasta'] = fecha_hasta_param
        return context


# ============================================
# VISTA HOME DINÁMICA CORREGIDA
# ============================================
GRAFICAS_TITULOS = {
    "01": "Distribución Total de Contratos por Ramo", "02": "Composición de la Cartera de Contratos Individuales por Antigüedad.",
    "03": "Indicadores Financieros Clave", "04": "Distribución de Edades", "05": "Tiempo Promedio Autorización Médica (días)",
    "06": "Estado de Morosidad", "07": "Flujo de Pagos Mensuales", "08": "Estado de Reclamaciones",
    "09": "Distribución de Reclamaciones por Edad del Afiliado", "10": "Frecuencia de Tipos de Reclamación",
    "11": "Distribución del Tiempo de Resolución de Reclamaciones", "12": "Ahorro Estimado por Pago Anual",
    "13": "Distribución por Edad y Ramo (Conteo)", "14": "Concentración Suma Asegurada por Ramo y Edad",
    "15": "Edad vs Monto Asegurado (Individual)", "16": "Top 10 Intermediarios por Prima Emitida (Prima vs Siniestro vs Comisión)",
    "17": "Evolución de Montos Contratados", "18": "Ratio Siniestralidad Estimado por Rango de Edad",
    "19": "Estados de Contratos (Individuales)", "20": "Top 10 Contratos Individuales por Monto",
    "21": "Tendencia Mensual Ratio Siniestralidad (Pagados / Prima Emitida)", "22": "Distribución de Montos Reclamados",
    "23": "Prima Emitida vs. Siniestros Incurridos por Rango Edad (Ind.)", "24": "Contratos Colectivos por Año",
    "25": "Comisiones vs Número de Contratos (Intermediarios)", "26": "Top 15 Reclamaciones (Aprob/Pagadas) por Monto",
    "27": "Tiempo Promedio de Resolución por Tipo de Reclamación", "28": "Reclamaciones por Tipo y Estado (Heatmap Conteo)",
    "29": "Monto Prom. Reclamado vs. Antigüedad Contrato (Ind.)", "30": "Distribución de Montos de Siniestros Incurridos",
    "31": "Distribución de Pagos por Forma (Últimos Meses)", "32": "Comparación de Tarifas por Ramo",
    "33": "Distribución Montos Contratados por Edad y Ramo (Heatmap Monto)", "34": "Rentabilidad Estimada por Ramo",
    "35": "Rentabilidad de Intermediarios (Scatter)", "36": "Estado de Facturación (Monto Total vs Saldo)",
    "37": "Ratio de Siniestralidad por Ramo (%)", "38": "Antigüedad de Saldos Pendientes (Facturas Vencidas)",
    "39": "Evolución Mensual del Costo Promedio por Siniestro (Incurrido)", "40": "Frecuencia y Severidad de Reclamaciones por Edad",
    "41": "Correlación Ramos-Reclamaciones (Heatmap Conteo)", "42": "Top 10 Intermediarios (Comisión y % Retención)",
    "43": "Descomposición Prima Emitida por Tipo y Ramo (Sunburst)", "44": "Top 15 Contratos por Mayor Monto Asegurado",
    "45": "Tendencia de Renovaciones vs Nuevos Contratos", "46": "Distribución Mensual de Prima Emitida (Heatmap Monto)",
    "47": "Segmentación de Contratos Individuales (Treemap)", "48": "Contratos Vigentes Próximos a Vencer (30 días)",
    "49": "Distribución Geográfica de Contratos Activos", "50": "Distribución de Contratos por Tipo y Estado (Sunburst)",
    "51": "Concentración de Siniestros (Análisis Pareto Simplificado", "52": "Flujo Mensual de Comisiones",
}


class DynamicHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'home.html'

    # --- CONFIGURACIÓN CENTRALIZADA DE MODELOS (La misma que tenías) ---
    MODEL_CONFIG = {
        'contrato_individual': {
            'model': ContratoIndividual, 'list_view': 'myapp:contrato_individual_list', 'create_view': 'myapp:contrato_individual_create',
            'detail_view': 'myapp:contrato_individual_detail', 'update_view': 'myapp:contrato_individual_update', 'delete_view': 'myapp:contrato_individual_delete',
            'fields': ['numero_contrato', 'afiliado', 'fecha_inicio_vigencia', 'estatus', 'tarifa_aplicada', 'importe_recibo_contrato'],
            # CORREGIDO: Eliminados contratante_nombre, afiliado__cedula, etc.
            'search_fields': ['numero_contrato'],
            'verbose_name': 'Contrato Individual', 'verbose_name_plural': 'Contratos Individuales',
            'related_fields': ['intermediario', 'afiliado', 'tarifa_aplicada'],
            'permissions': {'list': 'myapp.view_contratoindividual', 'create': 'myapp.add_contratoindividual', 'change': 'myapp.change_contratoindividual', 'delete': 'myapp.delete_contratoindividual', }
        },
        'afiliado_individual': {
            'model': AfiliadoIndividual, 'list_view': 'myapp:afiliado_individual_list', 'create_view': 'myapp:afiliado_individual_create',
            'detail_view': 'myapp:afiliado_individual_detail', 'update_view': 'myapp:afiliado_individual_update', 'delete_view': 'myapp:afiliado_individual_delete',
            'fields': ['cedula', 'primer_nombre', 'primer_apellido', 'fecha_nacimiento', 'activo'],
            # CORREGIDO: Eliminados todos los campos encriptados. La búsqueda por hash se manejaría en una vista dedicada.
            'search_fields': [],
            'verbose_name': 'Afiliado Individual', 'verbose_name_plural': 'Afiliados Individuales',
            'related_fields': [],
            'permissions': {'list': 'myapp.view_afiliadoindividual', 'create': 'myapp.add_afiliadoindividual', 'change': 'myapp.change_afiliadoindividual', 'delete': 'myapp.delete_afiliadoindividual', }
        },
        'auditoria_sistema': {
            'model': AuditoriaSistema, 'list_view': 'myapp:auditoria_sistema_list', 'create_view': 'myapp:auditoria_sistema_create',
            'detail_view': 'myapp:auditoria_sistema_detail', 'update_view': 'myapp:auditoria_sistema_update', 'delete_view': 'myapp:auditoria_sistema_delete',
            'fields': ['usuario', 'tipo_accion', 'tiempo_inicio', 'tabla_afectada', 'resultado_accion'],
            # CORREGIDO: Eliminados detalle_accion y direccion_ip.
            'search_fields': ['usuario__username', 'tipo_accion', 'tabla_afectada'],
            'verbose_name': 'Auditoría de Sistema', 'verbose_name_plural': 'Auditorías de Sistema',
            'related_fields': ['usuario'],
            'permissions': {'list': 'myapp.view_auditoriasistema', 'create': 'myapp.add_auditoriasistema', 'change': 'myapp.change_auditoriasistema', 'delete': 'myapp.delete_auditoriasistema', }
        },
        'afiliado_colectivo': {
            'model': AfiliadoColectivo, 'list_view': 'myapp:afiliado_colectivo_list', 'create_view': 'myapp:afiliado_colectivo_create',
            'detail_view': 'myapp:afiliado_colectivo_detail', 'update_view': 'myapp:afiliado_colectivo_update', 'delete_view': 'myapp:afiliado_colectivo_delete',
            'fields': ['rif', 'razon_social', 'email_contacto', 'activo'],
            # CORREGIDO: Eliminados todos los campos encriptados.
            'search_fields': [],
            'verbose_name': 'Afiliado Colectivo', 'verbose_name_plural': 'Afiliados Colectivos',
            'related_fields': [],
            'permissions': {'list': 'myapp.view_afiliadocolectivo', 'create': 'myapp.add_afiliadocolectivo', 'change': 'myapp.change_afiliadocolectivo', 'delete': 'myapp.delete_afiliadocolectivo', }
        },
        'contrato_colectivo': {
            'model': ContratoColectivo, 'list_view': 'myapp:contrato_colectivo_list', 'create_view': 'myapp:contrato_colectivo_create',
            'detail_view': 'myapp:contrato_colectivo_detail', 'update_view': 'myapp:contrato_colectivo_update', 'delete_view': 'myapp:contrato_colectivo_delete',
            'fields': ['numero_contrato', 'razon_social', 'fecha_inicio_vigencia', 'estatus', 'tarifa_aplicada', 'importe_recibo_contrato'],
            # CORREGIDO: Eliminados razon_social y rif.
            'search_fields': ['numero_contrato'],
            'verbose_name': 'Contrato Colectivo', 'verbose_name_plural': 'Contratos Colectivos',
            'related_fields': ['intermediario', 'tarifa_aplicada'],
            'permissions': {'list': 'myapp.view_contratocolectivo', 'create': 'myapp.add_contratocolectivo', 'change': 'myapp.change_contratocolectivo', 'delete': 'myapp.delete_contratocolectivo', }
        },
        'intermediario': {
            'model': Intermediario, 'list_view': 'myapp:intermediario_list', 'create_view': 'myapp:intermediario_create',
            'detail_view': 'myapp:intermediario_detail', 'update_view': 'myapp:intermediario_update', 'delete_view': 'myapp:intermediario_delete',
            'fields': ['codigo', 'nombre_completo', 'rif', 'porcentaje_comision', 'activo'],
            # CORREGIDO: Eliminados nombre_completo, rif, email_contacto.
            'search_fields': ['codigo'],
            'verbose_name': 'Intermediario', 'verbose_name_plural': 'Intermediarios',
            'related_fields': [],
            'permissions': {'list': 'myapp.view_intermediario', 'create': 'myapp.add_intermediario', 'change': 'myapp.change_intermediario', 'delete': 'myapp.delete_intermediario', }
        },
        'factura': {
            'model': Factura, 'list_view': 'myapp:factura_list', 'create_view': 'myapp:factura_create',
            'detail_view': 'myapp:factura_detail', 'update_view': 'myapp:factura_update', 'delete_view': 'myapp:factura_delete',
            'fields': ['numero_recibo', 'monto', 'vigencia_recibo_desde', 'vigencia_recibo_hasta', 'pagada'],
            # CORRECTO: Todos estos campos son buscables y no están encriptados.
            'search_fields': ['numero_recibo', 'contrato_individual__numero_contrato', 'contrato_colectivo__numero_contrato', 'relacion_ingreso'],
            'verbose_name': 'Factura', 'verbose_name_plural': 'Facturas',
            'related_fields': ['contrato_individual', 'contrato_colectivo', 'intermediario'],
            'permissions': {'list': 'myapp.view_factura', 'create': 'myapp.add_factura', 'change': 'myapp.change_factura', 'delete': 'myapp.delete_factura', }
        },
        'pago': {
            'model': Pago, 'list_view': 'myapp:pago_list', 'create_view': 'myapp:pago_create',
            'detail_view': 'myapp:pago_detail', 'update_view': 'myapp:pago_update', 'delete_view': 'myapp:pago_delete',
            'fields': ['id', 'factura', 'fecha_pago', 'monto_pago', 'forma_pago'],
            # CORREGIDO: referencia_pago está encriptado.
            'search_fields': ['reclamacion__id', 'factura__numero_recibo'],
            'verbose_name': 'Pago', 'verbose_name_plural': 'Pagos',
            'related_fields': ['reclamacion', 'factura'],
            'permissions': {'list': 'myapp.view_pago', 'create': 'myapp.add_pago', 'change': 'myapp.change_pago', 'delete': 'myapp.delete_pago', }
        },
        'tarifa': {
            'model': Tarifa, 'list_view': 'myapp:tarifa_list', 'create_view': 'myapp:tarifa_create',
            'detail_view': 'myapp:tarifa_detail', 'update_view': 'myapp:tarifa_update', 'delete_view': 'myapp:tarifa_delete',
            'fields': ['ramo', 'rango_etario', 'fecha_aplicacion', 'monto_anual', 'activo'],
            # CORRECTO: Ninguno de estos está encriptado.
            'search_fields': ['ramo', 'rango_etario'],
            'verbose_name': 'Tarifa', 'verbose_name_plural': 'Tarifas',
            'related_fields': [],
            'permissions': {'list': 'myapp.view_tarifa', 'create': 'myapp.add_tarifa', 'change': 'myapp.change_tarifa', 'delete': 'myapp.delete_tarifa', }
        },
        'reclamacion': {
            'model': Reclamacion, 'list_view': 'myapp:reclamacion_list', 'create_view': 'myapp:reclamacion_create',
            'detail_view': 'myapp:reclamacion_detail', 'update_view': 'myapp:reclamacion_update', 'delete_view': 'myapp:reclamacion_delete',
            'fields': ['id', 'tipo_reclamacion', 'estado', 'fecha_reclamo', 'monto_reclamado'],
            # CORREGIDO: descripcion_reclamo está encriptado.
            'search_fields': ['id', 'tipo_reclamacion', 'estado', 'contrato_individual__numero_contrato', 'contrato_colectivo__numero_contrato'],
            'verbose_name': 'Reclamación', 'verbose_name_plural': 'Reclamaciones',
            'related_fields': ['contrato_individual', 'contrato_colectivo', 'usuario_asignado'],
            'permissions': {'list': 'myapp.view_reclamacion', 'create': 'myapp.add_reclamacion', 'change': 'myapp.change_reclamacion', 'delete': 'myapp.delete_reclamacion', }
        },
        'usuario': {
            'model': Usuario, 'list_view': 'myapp:usuario_list', 'create_view': 'myapp:usuario_create',
            'detail_view': 'myapp:usuario_detail', 'update_view': 'myapp:usuario_update', 'delete_view': 'myapp:usuario_delete',
            'fields': ['username', 'primer_nombre', 'primer_apellido', 'email', 'tipo_usuario', 'is_active'],
            # CORREGIDO: Eliminados primer_nombre, primer_apellido.
            'search_fields': ['username', 'email', 'intermediario__nombre_completo'],
            'verbose_name': 'Usuario', 'verbose_name_plural': 'Usuarios',
            'related_fields': ['intermediario'],
            'permissions': {'list': 'myapp.view_usuario', 'create': 'myapp.add_usuario', 'change': 'myapp.change_usuario', 'delete': 'myapp.delete_usuario', }
        }
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = django_timezone.now().date()
        user = self.request.user

        # --- Preparar Configuración de Modelos Permitidos (Sin cambios) ---
        models_config_allowed = []
        for key, config in self.MODEL_CONFIG.items():
            if 'permissions' in config and 'list' in config['permissions'] and user.has_perm(config['permissions']['list']):
                try:
                    list_url = reverse_lazy(config['list_view'])
                    can_create = 'create' in config['permissions'] and user.has_perm(
                        config['permissions']['create'])
                    create_url = reverse_lazy(
                        config['create_view']) if can_create else None
                    can_edit = 'change' in config['permissions'] and user.has_perm(
                        config['permissions']['change'])
                    can_delete = 'delete' in config['permissions'] and user.has_perm(
                        config['permissions']['delete'])
                    models_config_allowed.append({
                        'key': key, 'name': config['verbose_name'], 'plural': config['verbose_name_plural'],
                        'list_url': list_url, 'create_url': create_url, 'can_create': can_create,
                        'can_edit': can_edit, 'can_delete': can_delete,
                        'fields': config.get('fields', []), 'search_fields': config.get('search_fields', []),
                        'related_fields': config.get('related_fields', []), 'model': config['model'],
                        'detail_view_name': config.get('detail_view'), 'update_view_name': config.get('update_view'),
                        'delete_view_name': config.get('delete_view'),
                    })
                except Exception as e:
                    logger.error(
                        f"Error configurando modelo '{key}' para dashboard: {e}", exc_info=True)
            elif 'permissions' not in config or 'list' not in config['permissions']:
                logger.warning(
                    f"Modelo '{key}' omitido por falta de 'permissions[list]'.")
        context['models_config'] = models_config_allowed
        logger.debug(
            f"[HomeView] Modelos permitidos para dashboard: {len(models_config_allowed)}")

        # --- Cargar Datos para el Dashboard ---
        try:
            # Totales
            totales = {config['key']: config['model'].objects.count()
                       for config in models_config_allowed}
            context['totales'] = totales
            logger.debug(f"[HomeView] Totales calculados: {totales}")

            # Recientes (Asegúrate que esta lógica funcione y no lance errores)
            recientes = {}
            # Ejemplo para ContratoIndividual si está permitido
            ci_config = next(
                (c for c in models_config_allowed if c['key'] == 'contrato_individual'), None)
            if ci_config:
                try:
                    # Usar select_related si es útil para mostrar en la tabla del home
                    recientes['contrato_individual'] = ci_config['model'].objects.select_related(
                        'afiliado', 'intermediario').order_by('-fecha_creacion')[:5]
                except Exception as e_rec:
                    logger.error(
                        f"Error obteniendo recientes para contrato_individual: {e_rec}")
                    # Fallback a lista vacía
                    recientes['contrato_individual'] = []
            # Añadir lógica similar para otros modelos si los muestras en "recientes"
            context['recientes'] = recientes
            logger.debug(
                f"[HomeView] Datos recientes cargados: {{k: len(v) for k, v in recientes.items()}}")

            # --- Gráficas ---
            all_graph_ids = list(GRAPH_GENERATORS.keys())
            graph_ids_to_show = all_graph_ids  # Mostrar todos por ahora
            force_refresh = self.request.GET.get('refresh_cache') == '1'
            logger.info(
                f"[HomeView] Obteniendo gráficas (IDs: {graph_ids_to_show}, Refresh: {force_refresh})")

            # Llamar a la función auxiliar revisada
            graficas_html_dict = get_all_graphs_cached(
                self.request, graph_ids_to_show, force_refresh)
            logger.debug(
                f"[HomeView] get_all_graphs_cached devolvió {len(graficas_html_dict)} elementos.")

            graficas_list = []
            if isinstance(graficas_html_dict, dict):
                for graph_id_str, html_content in graficas_html_dict.items():
                    titulo_real = GRAFICAS_TITULOS.get(
                        graph_id_str, f"Gráfica {graph_id_str}")
                    # Usar html_content directamente
                    graficas_list.append(
                        {'id': graph_id_str, 'title': titulo_real, 'html': html_content})
            else:
                logger.error(
                    "[HomeView] ¡ERROR! get_all_graphs_cached no devolvió un diccionario.")
                messages.error(
                    self.request, "Error interno al cargar las gráficas.")

            logger.info(
                f"[HomeView] Procesadas {len(graficas_list)} gráficas para el contexto.")
            # Asegurarse de que esta es la variable final
            context['graficas'] = graficas_list

            # --- Tablas (Lógica sin cambios, parece correcta) ---
            table_search = escape(self.request.GET.get('table_search', ''))
            tablas = []
            for config in models_config_allowed:
                try:
                    model = config['model']
                    queryset = model.objects.all()
                    if config['related_fields']:
                        valid_related = [
                            f for f in config['related_fields'] if '__' not in f]
                        if valid_related:
                            queryset = queryset.select_related(*valid_related)
                    if table_search and config['search_fields']:
                        filters = Q()
                        for field in config['search_fields']:
                            try:
                                model._meta.get_field(field.split('__')[0])
                                filters |= Q(
                                    **{f"{field}__icontains": table_search})
                            except:
                                pass
                        if filters:
                            queryset = queryset.filter(filters)
                    order_field = '-fecha_creacion' if hasattr(
                        model, 'fecha_creacion') else '-pk'
                    try:
                        model._meta.get_field(order_field.lstrip('-'))
                        queryset = queryset.order_by(order_field)
                    except:
                        queryset = queryset.order_by('-pk')
                    tablas.append({
                        'key': config['key'], 'title': config['plural'], 'fields': config['fields'],
                        'data': queryset[:10], 'list_url': config['list_url'], 'create_url': config['create_url'],
                        'can_create': config['can_create'], 'detail_view_name': config.get('detail_view_name'),
                        'update_view_name': config.get('update_view_name'), 'delete_view_name': config.get('delete_view_name'),
                        'can_edit': config['can_edit'], 'can_delete': config['can_delete'],
                    })
                except Exception as e:
                    logger.error(
                        f"Error generando tabla para {config['key']}: {e}", exc_info=True)
            context['tablas'] = tablas
            logger.debug(f"[HomeView] Procesadas {len(tablas)} tablas.")

            # --- Actualizar Contexto Final ---
            context.update({
                'active_tab': self.request.GET.get('tab', 'dashboard'),
                'table_search': table_search,
                # 'graficas': graficas_list, # Ya se añadió arriba
            })
            logger.info("[HomeView] Contexto final preparado.")

        except Exception as e:
            messages.error(
                self.request, f'Error crítico al cargar datos del dashboard: {str(e)}')
            logger.error(
                "Error fatal en DynamicHomeView.get_context_data: %s", str(e), exc_info=True)
            context['dashboard_error'] = "Error al cargar información del dashboard."
            # Resetear en caso de error
            context.update({'totales': {}, 'recientes': {},
                           'graficas': [], 'tablas': []})

        return context
# ============================================
# == VISTA PARA IMPORTAR DATOS CSV ==
# ============================================


class FacturaPdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'myapp.view_factura'
    template_name = 'factura_pdf.html'

    def link_callback(self, uri, rel):
        result = finders.find(uri)
        if result:
            if not isinstance(result, (list, tuple)):
                result = [result]
            for path_candidate in result:
                path = os.path.realpath(path_candidate)
                if os.path.isfile(path):
                    return path
        return uri

    def get(self, request, pk, *args, **kwargs):
        try:
            factura = get_object_or_404(
                Factura.objects.select_related(
                    'contrato_individual__afiliado',
                    'contrato_colectivo',
                    'intermediario'
                ),
                pk=pk
            )

            monto_prima = factura.monto or Decimal('0.00')
            context = {
                'factura': factura,
                'contrato_asociado': factura.get_contrato_asociado,
                'monto_prima': monto_prima,
                'total_a_pagar': monto_prima,
                'cliente_nombre': "(No identificado)",
                'cliente_doc': "N/A",
                'intermediario_factura': factura.intermediario
            }

            if factura.contrato_individual and factura.contrato_individual.afiliado:
                afiliado = factura.contrato_individual.afiliado
                # --- CORRECCIÓN: Acceder como propiedad, sin paréntesis ---
                context['cliente_nombre'] = afiliado.nombre_completo
                context['cliente_doc'] = f"C.I.: {afiliado.cedula}"
            elif factura.contrato_colectivo:
                colectivo = factura.contrato_colectivo
                context['cliente_nombre'] = colectivo.razon_social
                context['cliente_doc'] = f"RIF: {colectivo.rif}"

            template = get_template(self.template_name)
            html = template.render(context)
            result = BytesIO()
            pdf_status = pisa.pisaDocument(BytesIO(html.encode(
                'UTF-8')), result, encoding='UTF-8', link_callback=self.link_callback)

            if pdf_status.err:
                logger.error(
                    f"xhtml2pdf error code {pdf_status.err} para factura {pk}.")
                return HttpResponse("Error al generar el PDF.", status=500)

            response = HttpResponse(
                result.getvalue(), content_type='application/pdf')
            filename = f"factura_{factura.numero_recibo or factura.pk}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response

        except Exception as e:
            logger.error(
                f"Error inesperado en FacturaPdfView (pk={pk}): {e}", exc_info=True)
            return HttpResponseServerError("Ocurrió un error inesperado al generar el PDF.")


class PagoPdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'myapp.view_pago'
    template_name = 'pago_pdf.html'
    TASA_IGTF_PAGO = Decimal('0.03')

    def link_callback(self, uri, rel):
        result = finders.find(uri)
        if result:
            if not isinstance(result, (list, tuple)):
                result = [result]
            for path_candidate in result:
                path = os.path.realpath(path_candidate)
                if os.path.isfile(path):
                    return path
        return uri

    def get(self, request, pk, *args, **kwargs):
        try:
            pago = get_object_or_404(
                Pago.objects.select_related(
                    'factura__contrato_individual__afiliado',
                    'factura__contrato_colectivo',
                    'reclamacion__contrato_individual__afiliado',
                    'reclamacion__contrato_colectivo'
                ),
                pk=pk
            )

            monto_total_recibido = pago.monto_pago or Decimal('0.00')
            monto_igtf_percibido = Decimal('0.00')
            if pago.aplica_igtf_pago and monto_total_recibido > 0:
                monto_igtf_percibido = (
                    monto_total_recibido * self.TASA_IGTF_PAGO).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            monto_abonado_neto = monto_total_recibido - monto_igtf_percibido

            cliente_nombre = "No identificado"
            cliente_doc = "N/A"
            contrato_ref = pago.factura.get_contrato_asociado if pago.factura else (
                pago.reclamacion.contrato_individual or pago.reclamacion.contrato_colectivo if pago.reclamacion else None)

            if contrato_ref:
                if isinstance(contrato_ref, ContratoIndividual) and contrato_ref.afiliado:
                    afiliado = contrato_ref.afiliado
                    # --- CORRECCIÓN: Acceder como propiedad, sin paréntesis ---
                    cliente_nombre = afiliado.nombre_completo
                    cliente_doc = f"C.I.: {afiliado.cedula}"
                elif isinstance(contrato_ref, ContratoColectivo):
                    cliente_nombre = contrato_ref.razon_social
                    cliente_doc = f"RIF: {contrato_ref.rif}"

            context = {
                'pago': pago,
                'factura_asociada': pago.factura,
                'reclamacion_asociada': pago.reclamacion,
                'contrato_ref': contrato_ref,
                'cliente_nombre': cliente_nombre,
                'cliente_doc': cliente_doc,
                'pago_con_igtf': pago.aplica_igtf_pago,
                'monto_igtf_percibido': monto_igtf_percibido,
                'tasa_igtf_display': f"{self.TASA_IGTF_PAGO:.0%}",
                'monto_abonado_neto': monto_abonado_neto,
                'monto_total_recibido': monto_total_recibido
            }

            template = get_template(self.template_name)
            html = template.render(context)
            result = BytesIO()
            pdf_status = pisa.pisaDocument(BytesIO(html.encode(
                'UTF-8')), result, encoding='UTF-8', link_callback=self.link_callback)

            if pdf_status.err:
                logger.error(
                    f"xhtml2pdf error code {pdf_status.err} para pago {pk}.")
                return HttpResponse("Error al generar el PDF.", status=500)

            response = HttpResponse(
                result.getvalue(), content_type='application/pdf')
            filename = f"recibo_pago_{pago.referencia_pago or pago.pk}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response

        except Exception as e:
            logger.error(
                f"Error inesperado en PagoPdfView (pk={pk}): {e}", exc_info=True)
            return HttpResponseServerError("Ocurrió un error inesperado al generar el PDF.")
# License View


@method_decorator(csrf_protect, name='dispatch')
class ActivateLicenseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = 'activate_license.html'
    form_class = LicenseActivationForm
    http_method_names = ['get', 'post', 'head', 'options', 'trace']
    permission_required = 'myapp.change_licenseinfo'

    def get_context_data(self, form=None, **kwargs):
        if form is None:
            form = self.form_class()
        current_license_info = get_license_info()
        if current_license_info is None:
            current_license_info = {'key': None, 'key_fragment': 'N/A',
                                    'expiry_date': None, 'is_valid': False, 'last_updated': None}
        context = {
            'form': form, 'license_status': current_license_info,
            'title': "Activar o Actualizar Licencia", 'active_tab': 'licencia',
            'MAX_LICENSE_DURATION_DAYS': 0
        }
        context.update(kwargs)
        return context

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        context_data = self.get_context_data(form=form)

        if form.is_valid():
            license_key = form.cleaned_data['license_key']
            user_email_for_log = "UsuarioTest"
            if request.user and request.user.is_authenticated:
                user_email_for_log = request.user.email

            logger.info(
                f"Intento de activación de licencia por {user_email_for_log} con clave: ...{license_key[-6:]}")

            success, message_from_activation = activate_or_update_license(
                provided_key=license_key)
            # print(f"DEBUG ActivateLicenseView: activate_or_update_license devolvió: success={success}, message='{message_from_activation}'")

            if success:
                messages.success(request, message_from_activation)
                return redirect(reverse('myapp:activate_license'))
            else:
                messages.error(request, message_from_activation)
                logger.error(
                    f"Fallo en activate_or_update_license para {user_email_for_log}: Clave=...{license_key[-6:]}, Mensaje='{message_from_activation}'")
        else:
            user_email_for_log = "UsuarioTest"
            if request.user and request.user.is_authenticated:
                user_email_for_log = request.user.email
            logger.warning(
                f"Formulario de activación de licencia inválido para {user_email_for_log}: {form.errors.as_json()}")

        return render(request, self.template_name, context_data)


@method_decorator(csrf_protect, name='dispatch')
@method_decorator(require_POST, name='dispatch')
class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notification_id = request.POST.get('notification_id')
        mark_all = request.POST.get('mark_all') == 'true'
        if mark_all:
            try:
                updated_count = Notificacion.objects.filter(
                    usuario=request.user, leida=False).update(leida=True)
                logger.info(
                    f"Usuario {request.user.email} marcó {updated_count} notificaciones como leídas.")
                return JsonResponse({'status': 'success', 'message': f'{updated_count} notificacione(s) marcada(s) como leída(s).', 'new_count': 0})
            except Exception as e:
                logger.error(
                    f"Error marcando todas leídas para {request.user.email}: {e!r}")
                return JsonResponse({'status': 'error', 'message': 'Error al marcar notificaciones.'}, status=500)
        elif notification_id:
            try:
                notif = get_object_or_404(
                    Notificacion, pk=notification_id, usuario=request.user)
                if not notif.leida:
                    notif.leida = True
                    notif.save(update_fields=['leida'])
                new_count = Notificacion.objects.filter(
                    usuario=request.user, leida=False).count()
                return JsonResponse({'status': 'success', 'message': 'Notificación marcada como leída.', 'new_count': new_count})
            except Http404:
                logger.warning(
                    f"Intento marcar notificación inexistente/ajena {request.user.email}: ID {notification_id}")
                return JsonResponse({'status': 'error', 'message': 'Notificación no encontrada.'}, status=404)
            except Exception as e:
                logger.error(
                    f"Error marcando notificación {notification_id} leída para {request.user.email}: {e!r}")
                return JsonResponse({'status': 'error', 'message': 'Error al marcar notificación.'}, status=500)
        else:
            return JsonResponse({'status': 'error', 'message': 'Falta ID o parámetro mark_all.'}, status=400)


def license_invalid_view(request):
    # Puedes pasar el email de soporte al contexto si lo usas en la plantilla
    # from django.conf import settings
    # support_email = getattr(settings, 'SUPPORT_EMAIL', 'soporte@example.com')
    # context = {'support_email': support_email}
    context = {}
    # Ajusta la ruta a tu plantilla
    return render(request, 'license_invalid.html', context)


def serve_media_file(request, file_path):
    # Construir la ruta completa y segura al archivo
    # file_path vendrá de la URL y será relativa a MEDIA_ROOT
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)

    # Medidas de seguridad: evitar path traversal
    if not os.path.abspath(full_path).startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise Http404("Acceso denegado a la ruta del archivo.")

    if os.path.exists(full_path) and os.path.isfile(full_path):
        # Determinar el content type (opcional pero bueno para el navegador)
        import mimetypes
        content_type, encoding = mimetypes.guess_type(full_path)
        content_type = content_type or 'application/octet-stream'

        # Usar FileResponse para archivos grandes o binarios
        return FileResponse(open(full_path, 'rb'), content_type=content_type)
    else:
        raise Http404("Archivo no encontrado.")


class CalcularMontoContratoAPI(View):
    def get(self, request, *args, **kwargs):
        tarifa_id = request.GET.get('tarifa_id')
        periodo_meses_str = request.GET.get('periodo_meses')

        if not tarifa_id or not periodo_meses_str:
            return JsonResponse({'error': 'Faltan parámetros tarifa_id o periodo_meses.'}, status=400)

        try:
            tarifa = Tarifa.objects.get(pk=tarifa_id)
            periodo_meses = int(periodo_meses_str)

            if tarifa.monto_anual is None or periodo_meses <= 0:
                raise ValueError("Datos inválidos para el cálculo.")

            # La lógica de cálculo que ya conocemos
            monto_total = (tarifa.monto_anual / Decimal(12)) * \
                Decimal(periodo_meses)

            return JsonResponse({
                # Devolvemos como string con 2 decimales
                'monto_total': f"{monto_total:.2f}"
            })

        except Tarifa.DoesNotExist:
            return JsonResponse({'error': 'La tarifa especificada no existe.'}, status=404)
        except (ValueError, TypeError, InvalidOperation):
            return JsonResponse({'error': 'Parámetros inválidos para el cálculo.'}, status=400)
        except Exception as e:
            # Loguear el error real en el servidor
            # logger.error(f"Error en CalcularMontoContratoAPI: {e}")
            return JsonResponse({'error': 'Ocurrió un error interno en el servidor.'}, status=500)


def generar_grafico_total_primas_ramo_barras(qs_contratos_ind, qs_contratos_col):
    try:
        ramo_map = dict(CommonChoices.RAMO)
        primas_por_ramo = collections.defaultdict(Decimal)

        # Ya no filtramos por fecha aquí, trabajamos con los querysets que nos pasan
        for item in qs_contratos_ind.values('ramo').annotate(total=Sum('monto_total')):
            ramo_label = ramo_map.get(
                item['ramo'], str(item['ramo'] or "Desconocido"))
            primas_por_ramo[ramo_label] += item['total'] or Decimal('0.00')

        for item in qs_contratos_col.values('ramo').annotate(total=Sum('monto_total')):
            ramo_label = ramo_map.get(
                item['ramo'], str(item['ramo'] or "Desconocido"))
            primas_por_ramo[ramo_label] += item['total'] or Decimal('0.00')

        if not primas_por_ramo:
            return generar_figura_sin_datos_plotly("No hay primas en la cartera.")

        df = pd.DataFrame(list(primas_por_ramo.items()),
                          columns=['Ramo', 'Total Primas'])
        df = df.sort_values('Total Primas', ascending=True)

        fig = px.bar(df, y='Ramo', x='Total Primas', orientation='h',
                     title='Primas por Ramo en Cartera', text='Total Primas')
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
        fig.update_layout(**BASE_LAYOUT_DASHBOARD)  # Usando tu layout base
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        return generar_figura_sin_datos_plotly(f"Error: {e}")


def generar_grafico_estados_contrato(data_estados):
    try:
        if not data_estados:
            return generar_figura_sin_datos_plotly("No hay contratos en la cartera.")

        estatus_map = dict(CommonChoices.ESTADOS_VIGENCIA)
        df = pd.DataFrame(data_estados)
        df['estatus_display'] = df['estatus'].apply(
            lambda x: estatus_map.get(x, x))

        conteo_estados = df['estatus_display'].value_counts().reset_index()
        conteo_estados.columns = ['Estado', 'Cantidad']

        fig = px.pie(conteo_estados, names='Estado', values='Cantidad',
                     title='Distribución de Estatus de Contratos', hole=.4)
        fig.update_layout(**BASE_LAYOUT_DASHBOARD)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        return generar_figura_sin_datos_plotly(f"Error: {e}")


def generar_grafico_estados_reclamacion(data_reclamaciones):
    try:
        if not data_reclamaciones:
            return generar_figura_sin_datos_plotly("No hay reclamaciones en la cartera.")

        estado_map = dict(CommonChoices.ESTADO_RECLAMACION)
        df = pd.DataFrame(data_reclamaciones)
        df['estado_display'] = df['estado'].apply(
            lambda x: estado_map.get(x, x))

        conteo_estados = df['estado_display'].value_counts().reset_index()
        conteo_estados.columns = ['Estado', 'Cantidad']

        fig = px.bar(conteo_estados, x='Estado', y='Cantidad',
                     title='Estado de Reclamaciones en Cartera', text='Cantidad')
        fig.update_layout(**BASE_LAYOUT_DASHBOARD)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)
    except Exception as e:
        return generar_figura_sin_datos_plotly(f"Error: {e}")


logger_idv = logging.getLogger("myapp.views.IntermediarioDashboardView")


class IntermediarioDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'intermediario_dashboard.html'

    def get(self, request, *args, **kwargs):
        if not request.user.is_superuser and not hasattr(request.user, 'intermediario'):
            raise PermissionDenied(
                "No tienes un intermediario asociado para ver este dashboard.")
        return super().get(request, *args, **kwargs)

    # --- MÉTODOS PRIVADOS PARA GENERAR GRÁFICOS ---
    def _generar_figura_sin_datos(self, mensaje="No hay datos disponibles"):
        fig = go.Figure()
        fig.add_annotation(text=mensaje, xref="paper", yref="paper", x=0.5,
                           y=0.5, showarrow=False, font={"size": 16, "color": "#888"})
        fig.update_layout(xaxis={'visible': False}, yaxis={
                          'visible': False}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_primas_ramo(self):
        primas_por_ramo = collections.defaultdict(Decimal)
        ramo_map = dict(CommonChoices.RAMO)
        for item in self.qs_contratos_ind.values('ramo').annotate(total=Sum('monto_total')):
            primas_por_ramo[ramo_map.get(
                item['ramo'], "N/A")] += item['total'] or Decimal('0.0')
        for item in self.qs_contratos_col.values('ramo').annotate(total=Sum('monto_total')):
            primas_por_ramo[ramo_map.get(
                item['ramo'], "N/A")] += item['total'] or Decimal('0.0')
        if not primas_por_ramo:
            return self._generar_figura_sin_datos("No hay primas en tu cartera.")
        df = pd.DataFrame(list(primas_por_ramo.items()), columns=[
                          'Ramo', 'Total Primas']).sort_values('Total Primas', ascending=True)
        fig = px.bar(df, y='Ramo', x='Total Primas', orientation='h',
                     title='Tus Primas por Ramo', text_auto='.2s')
        fig.update_traces(marker_color='#00AEEF', textposition='outside')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#fff', yaxis={'title': ''}, xaxis={'title': 'Primas ($)'})
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_estados_contrato(self):
        data_estados = list(self.qs_contratos_ind.values(
            'estatus')) + list(self.qs_contratos_col.values('estatus'))
        if not data_estados:
            return self._generar_figura_sin_datos("No hay contratos en tu cartera.")
        estatus_map = dict(CommonChoices.ESTADOS_VIGENCIA)
        df = pd.DataFrame(data_estados)
        df['estatus_display'] = df['estatus'].apply(
            lambda x: estatus_map.get(x, x))
        conteo_estados = df['estatus_display'].value_counts().reset_index()
        conteo_estados.columns = ['Estado', 'Cantidad']
        fig = px.pie(conteo_estados, names='Estado', values='Cantidad',
                     title='Distribución de Estatus de tus Contratos', hole=.4)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#fff',
                          showlegend=True, legend={'orientation': 'h', 'yanchor': 'bottom', 'y': -0.2})
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def _generar_grafico_estados_reclamacion(self):
        data_reclamaciones = list(self.qs_reclamaciones.values('estado'))
        if not data_reclamaciones:
            return self._generar_figura_sin_datos("No hay reclamaciones en tu cartera.")
        estado_map = dict(CommonChoices.ESTADO_RECLAMACION)
        df = pd.DataFrame(data_reclamaciones)
        df['estado_display'] = df['estado'].apply(
            lambda x: estado_map.get(x, x))
        conteo_estados = df['estado_display'].value_counts().reset_index()
        conteo_estados.columns = ['Estado', 'Cantidad']
        fig = px.bar(conteo_estados, x='Estado', y='Cantidad',
                     title='Estado de tus Reclamaciones', text_auto=True)
        fig.update_traces(marker_color='#8CC63F')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#fff', xaxis={'title': ''}, yaxis={'title': 'Cantidad'})
        return plot(fig, output_type='div', include_plotlyjs=False, config={'displayModeBar': False})

    def generar_grafico_distribucion_estatus_contratos(qs_contratos_ind, qs_contratos_col, titulo="Distribución de Estatus de Contratos"):
        data_estados = list(qs_contratos_ind.values(
            'estatus')) + list(qs_contratos_col.values('estatus'))
        if not data_estados:
            return generar_figura_sin_datos_plotly("No hay contratos para analizar.")

        estatus_map = dict(CommonChoices.ESTADOS_VIGENCIA)
        df = pd.DataFrame(data_estados)
        df['estatus_display'] = df['estatus'].apply(
            lambda x: estatus_map.get(x, x))
        conteo_estados = df['estatus_display'].value_counts().reset_index()
        conteo_estados.columns = ['Estado', 'Cantidad']

        fig = px.pie(conteo_estados, names='Estado',
                     values='Cantidad', title=titulo, hole=.4)
        # Asumiendo que BASE_LAYOUT_DASHBOARD está en graficas.py
        fig.update_layout(**BASE_LAYOUT_DASHBOARD)
        return plot(fig, output_type='div', include_plotlyjs=False, config=GRAPH_CONFIG)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        intermediario_a_filtrar = None

        # --- LÓGICA PARA DETERMINAR QUÉ DASHBOARD MOSTRAR ---
        if user.is_superuser:
            # Si es superusuario, puede ver el dashboard de CUALQUIER intermediario
            # pasando un ID en la URL (ej. /mi-dashboard/?intermediario_id=5)
            intermediario_id = self.request.GET.get('intermediario_id')
            if intermediario_id:
                try:
                    intermediario_a_filtrar = Intermediario.objects.get(
                        pk=intermediario_id)
                    context['dashboard_title'] = f"Dashboard: {intermediario_a_filtrar.nombre_completo}"
                except Intermediario.DoesNotExist:
                    context['dashboard_title'] = "Reporte General (Intermediario no encontrado)"
            else:
                # Si es superusuario pero no especifica un ID, puede ver los datos globales
                context['dashboard_title'] = "Reporte General (Agregado)"
        else:
            # Si NO es superusuario, SIEMPRE verá su propio dashboard.
            # No necesita pasar ningún ID. La vista lo toma de request.user.
            intermediario_a_filtrar = user.intermediario
            context['dashboard_title'] = "Mi Dashboard de Intermediario"

        # --- Querysets Base Filtrados (o no) ---
        self.qs_contratos_ind = ContratoIndividual.objects.filter(activo=True)
        self.qs_contratos_col = ContratoColectivo.objects.filter(activo=True)
        self.qs_reclamaciones = Reclamacion.objects.filter(activo=True)
        self.qs_comisiones = RegistroComision.objects.all()

        if intermediario_a_filtrar:
            self.qs_contratos_ind = self.qs_contratos_ind.filter(
                intermediario=intermediario_a_filtrar)
            self.qs_contratos_col = self.qs_contratos_col.filter(
                intermediario=intermediario_a_filtrar)
            self.qs_reclamaciones = self.qs_reclamaciones.filter(
                Q(contrato_individual__intermediario=intermediario_a_filtrar) |
                Q(contrato_colectivo__intermediario=intermediario_a_filtrar)
            )
            self.qs_comisiones = self.qs_comisiones.filter(
                intermediario=intermediario_a_filtrar)

        # --- Cálculo de KPIs ---
        hoy = date.today()
        fecha_limite_vencimiento = hoy + timedelta(days=60)
        total_contratos = self.qs_contratos_ind.count() + self.qs_contratos_col.count()
        primas_brutas = self.qs_contratos_ind.aggregate(t=Coalesce(Sum('monto_total'), Decimal('0.0')))['t'] + \
            self.qs_contratos_col.aggregate(t=Coalesce(
                Sum('monto_total'), Decimal('0.0')))['t']
        siniestros_incurridos = self.qs_reclamaciones.filter(estado__in=['APROBADA', 'PAGADA']).aggregate(
            t=Coalesce(Sum('monto_reclamado'), Decimal('0.0')))['t']

        context.update({
            'kpi_total_contratos': total_contratos,
            'kpi_primas_brutas': primas_brutas,
            'kpi_comisiones_pagadas': self.qs_comisiones.filter(estatus_pago_comision='PAGADA').aggregate(t=Coalesce(Sum('monto_comision'), Decimal('0.0')))['t'],
            'kpi_comisiones_pendientes': self.qs_comisiones.filter(estatus_pago_comision='PENDIENTE').aggregate(t=Coalesce(Sum('monto_comision'), Decimal('0.0')))['t'],
            'kpi_ratio_siniestralidad': (siniestros_incurridos / primas_brutas * 100) if primas_brutas > 0 else Decimal('0.0'),
            'kpi_contratos_a_vencer': self.qs_contratos_ind.filter(fecha_fin_vigencia__range=[hoy, fecha_limite_vencimiento], estatus='VIGENTE').count() + self.qs_contratos_col.filter(fecha_fin_vigencia__range=[hoy, fecha_limite_vencimiento], estatus='VIGENTE').count(),
            'kpi_reclamaciones_abiertas': self.qs_reclamaciones.filter(estado='ABIERTA').count(),
            'kpi_ticket_promedio': (primas_brutas / total_contratos) if total_contratos > 0 else Decimal('0.0')
        })

        # --- Generación de Gráficos ---
        context['plotly_primas_por_ramo'] = graficas.generar_grafico_primas_por_ramo(
            qs_contratos_ind=self.qs_contratos_ind,
            qs_contratos_col=self.qs_contratos_col,
            titulo="Tus Primas por Ramo")
        context['plotly_estados_contratos'] = self._generar_grafico_estados_contrato()
        context['plotly_estados_reclamaciones'] = self._generar_grafico_estados_reclamacion()
        context['plotly_estados_contratos'] = graficas.generar_grafico_distribucion_estatus_contratos(
            self.qs_contratos_ind,
            self.qs_contratos_col,
            titulo="Estatus de Tus Contratos"
        )

        return context


@login_required  # ¡Importante! Asegura que solo usuarios logueados puedan ver los archivos
def serve_media_file(request, file_path):
    """
    Sirve de forma segura los archivos de la carpeta MEDIA_ROOT.
    Funciona tanto en desarrollo como en el ejecutable de PyInstaller.
    """
    # Construye la ruta completa al archivo solicitado
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)

    # Normaliza la ruta para evitar ataques de "path traversal"
    full_path = os.path.abspath(full_path)

    # Medida de seguridad: Asegurarse de que la ruta solicitada esté DENTRO de MEDIA_ROOT
    if not full_path.startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise Http404("Acceso denegado.")

    if os.path.exists(full_path) and os.path.isfile(full_path):
        # Usamos FileResponse, que es eficiente para servir archivos
        return FileResponse(open(full_path, 'rb'))
    else:
        raise Http404("Archivo no encontrado.")


@login_required
@require_GET
def get_financial_data_for_item(request):
    """
    API unificada para obtener datos financieros de un item (Factura o Reclamación).
    - Para Factura: Devuelve el saldo pendiente.
    - Para Reclamación: Devuelve el saldo pendiente por pagar.
    """
    factura_id = request.GET.get('factura_id')
    reclamacion_id = request.GET.get('reclamacion_id')

    if not factura_id and not reclamacion_id:
        return JsonResponse({'error': 'Debe proporcionar un ID de factura o reclamación.'}, status=400)

    try:
        if factura_id:
            factura = get_object_or_404(Factura, pk=int(factura_id))
            saldo_pendiente = factura.monto_pendiente or Decimal('0.00')
            monto_sugerido = saldo_pendiente
            return JsonResponse({
                'saldo_pendiente': f"{saldo_pendiente:,.2f}",
                'monto_sugerido': f"{monto_sugerido:.2f}",
                'moneda': 'USD'  # O la moneda que uses
            })

        elif reclamacion_id:
            reclamacion = get_object_or_404(
                Reclamacion.objects.prefetch_related('pagos'), pk=int(reclamacion_id))
            total_pagado = reclamacion.pagos.filter(activo=True).aggregate(
                total=Coalesce(Sum('monto_pago'), Decimal('0.00'))
            )['total']
            saldo_pendiente = (
                reclamacion.monto_reclamado or Decimal('0.00')) - total_pagado
            monto_sugerido = max(Decimal('0.00'), saldo_pendiente)
            return JsonResponse({
                'saldo_pendiente': f"{saldo_pendiente:,.2f}",
                'monto_sugerido': f"{monto_sugerido:.2f}",
                'moneda': 'USD'
            })

    except (ValueError, TypeError):
        return JsonResponse({'error': 'ID inválido.'}, status=400)
    except Http404:
        return JsonResponse({'error': 'El objeto no fue encontrado.'}, status=404)
    except Exception as e:
        logger.error(
            f"Error en get_financial_data_for_item: {e}", exc_info=True)
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)
