
# views.py
from myapp.commons import CommonChoices  # Ajusta la ruta de importación
# Ajusta según necesidad
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
import plotly.graph_objects as go
import pandas as pd
# Renombrado para evitar conflicto
from datetime import date as py_date, datetime as py_datetime
from .commons import CommonChoices
from .models import Pago, Factura, Reclamacion, AuditoriaSistema
from xhtml2pdf import pisa
from django.db.models import Q
from django.http import HttpResponse
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
from .filters import (
    AuditoriaSistemaFilter,
    UsuarioFilter,
    AfiliadoIndividualFilter,
    AfiliadoColectivoFilter,
    ContratoIndividualFilter,
    ContratoColectivoFilter,
    IntermediarioFilter,
    FacturaFilter,
    PagoFilter,
    ReclamacionFilter,
    TarifaFilter,
    RegistroComisionFilter
)
from django import forms  # Añadido forms


# Configuración del logger
logger = logging.getLogger(__name__)


def handler500(request):
    context = {
        'debug': settings.DEBUG,
    }
    if settings.DEBUG:
        # Obtener la información de la excepción actual
        exc_type, exc_value, exc_traceback = sys.exc_info()
        context['exception'] = exc_value  # Pasar el mensaje de la excepción
        # También podrías querer pasar el traceback completo si lo necesitas,
        # pero el mensaje suele ser suficiente para la plantilla.
    return render(request, '500.html', context, status=500)


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
class BaseCRUDView(View):
    model = None
    model_manager_name = 'objects'
    search_fields = []
    ordering_fields = []
    default_ordering_if_none_specified = ['pk']

    def get_manager(self):
        return getattr(self.model, self.model_manager_name)

    def get_ordering(self):
        # Este método es crucial. Las subclases (ListViews) definirán 'ordering'.
        # Si esta BaseCRUDView fuera a ser usada por algo que no es una ListView,
        # necesitaría un fallback más robusto, pero en el contexto de BaseListView,
        # 'self' será la instancia de la ListView hija.
        return getattr(self, 'ordering', self.default_ordering_if_none_specified)

    def _apply_search(self, queryset, search_query):
        if search_query and self.search_fields:
            from functools import reduce
            import operator
            or_conditions = [Q(**{f"{field}__icontains": search_query})
                             for field in self.search_fields]
            if or_conditions:
                queryset = queryset.filter(reduce(operator.or_, or_conditions))
        return queryset

    def _apply_url_ordering(self, queryset):  # Renombrado para claridad
        sort_param = self.request.GET.get('sort')
        order_param = self.request.GET.get('order', 'asc')

        # Usa 'ordering_fields' de la instancia (que debería ser la ListView hija)
        view_instance_ordering_fields = getattr(self, 'ordering_fields', [])

        if sort_param and sort_param in view_instance_ordering_fields:
            prefix = "-" if order_param == "desc" else ""
            return queryset.order_by(f"{prefix}{sort_param}")
        return queryset  # Devuelve el queryset sin cambios si no hay orden por URL

    def get_queryset(self):
        manager = self.get_manager()
        queryset = manager.all()

        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = self._apply_search(queryset, search_query)

        # Aplicar ordenamiento por defecto de la vista hija ANTES del ordenamiento por URL
        default_ordering = self.get_ordering()
        if default_ordering:
            if isinstance(default_ordering, str):
                default_ordering = (default_ordering,)
            queryset = queryset.order_by(*default_ordering)

        # Aplicar ordenamiento dinámico por URL (si existe)
        # Esto sobrescribirá el ordenamiento por defecto si se especifica un 'sort' en la URL
        queryset = self._apply_url_ordering(queryset)

        return queryset
    # Helper para validar rutas (asegúrate que esté en la clase)

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
                related_model._meta.get_field(part)  # Validar campo final

    # Helper para ordenar (asegúrate que esté en la clase)
    def _apply_ordering(self, queryset):
        sort_by = self.request.GET.get('sort')
        # get_ordering() viene de MultipleObjectMixin
        default_sort = self.get_ordering() or ['-pk']
        if not sort_by:
            sort_by = default_sort[0]

        order = self.request.GET.get(
            'order', 'asc' if not sort_by.startswith('-') else 'desc')
        prefix = '-' if order == 'desc' else ''
        sort_field = sort_by.lstrip('-')

        # Usar self.ordering_fields definido en la subclase
        allowed_ordering_fields = getattr(self, 'ordering_fields', [])

        if sort_field and allowed_ordering_fields and sort_field in allowed_ordering_fields:
            logger.debug(
                f"[{self.__class__.__name__}] Aplicando orden: {prefix}{sort_field}")
            try:
                self._validate_lookup_path(self.model, sort_field)
                # Lógica de anotación específica para orden (si existe en subclase)
                if hasattr(self, f'_annotate_sort_{sort_field}'):
                    queryset = getattr(self, f'_annotate_sort_{sort_field}')(
                        queryset, prefix)
                else:
                    queryset = queryset.order_by(f'{prefix}{sort_field}')
                self.current_sort = sort_field  # Guardar para contexto
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'search_query': escape(self.request.GET.get('search', '')),
            'order_by': escape(self.request.GET.get('order_by', '')),
            'direction': escape(self.request.GET.get('direction', 'asc')),
            'aria_current_page': ('Página actual'),
            'aria_goto_page': ('Ir a la página'),
            'aria_role': 'form',
            'aria_live': 'polite'
        })
        # Las subclases (ListView) añadirán 'filter', 'page_obj', 'paginator'
        return context

    # --- Método form_valid para Create/Update ---
    def form_valid(self, form):
        is_update = hasattr(self, 'object') and self.object is not None
        action_type = 'MODIFICACION' if is_update else 'CREACION'
        # Guardar estado anterior para Update
        objeto_antes = self.get_object() if is_update else None

        try:
            # Guardar el objeto a través del formulario
            self.object = form.save()

            try:
                if is_update:
                    if hasattr(self, 'enviar_notificacion_actualizacion'):
                        self.enviar_notificacion_actualizacion(
                            objeto_antes, self.object, form.changed_data)
                else:  # Es creación
                    if hasattr(self, 'enviar_notificacion_creacion'):
                        self.enviar_notificacion_creacion(self.object)
            except Exception as notif_error:
                # Auditoría de éxito
                self._create_audit_entry(
                    action_type=action_type,
                    resultado='EXITO',
                    detalle=f"{action_type} exitosa de {self.model._meta.verbose_name}: {self.object}"
                )
            messages.success(self.request, ('Operación exitosa'))
            # Redirigir a success_url (definido en la subclase)
            return HttpResponseRedirect(self.get_success_url())

        except ValidationError as e:
            logger.error(
                f"ValidationError en {self.__class__.__name__} - {action_type}: {e.message_dict}", exc_info=True)
            form._update_errors(e)  # Añade errores al formulario
            messages.error(self.request, "Error de validación al guardar.")
            self._create_audit_entry(
                action_type=action_type, resultado='ERROR', detalle=f"ValidationError: {e.message_dict}")
            return self.form_invalid(form)
        except IntegrityError as e:
            logger.error(
                f"IntegrityError en {self.__class__.__name__} - {action_type}: {e}", exc_info=True)
            # Intenta dar un mensaje más útil
            error_msg = "Error de base de datos (posible duplicado o FK inválida)."
            if "violates unique constraint" in str(e):
                error_msg = "Error: Ya existe un registro con uno de estos valores únicos."
            elif "violates foreign key constraint" in str(e):
                error_msg = "Error: No se puede asignar una relación a un registro que no existe."
            elif "violates not-null constraint" in str(e):
                error_msg = "Error: Uno de los campos obligatorios está vacío."
            form.add_error(None, error_msg)
            messages.error(self.request, error_msg)
            self._create_audit_entry(
                action_type=action_type, resultado='ERROR', detalle=f"IntegrityError: {str(e)[:200]}")
            return self.form_invalid(form)
        except Exception as e:
            logger.error(
                f"Error inesperado en {self.__class__.__name__}.form_valid ({action_type}): {e}", exc_info=True)
            messages.error(
                self.request, f'Error inesperado al procesar el formulario: {str(e)}')
            self._create_audit_entry(
                action_type=action_type,
                resultado='ERROR',
                detalle=f"Error inesperado en {action_type.lower()}: {str(e)[:200]}"
            )
            return self.form_invalid(form)

    def _create_audit_entry(self, action_type, resultado, detalle):
        # Usar self.object.pk si existe (creación/update exitoso), sino None
        registro_pk = self.object.pk if hasattr(
            self, 'object') and self.object and self.object.pk else None
        AuditoriaSistema.objects.create(
            usuario=self.request.user if self.request.user.is_authenticated else None,
            tipo_accion=action_type,
            tabla_afectada=self.model._meta.db_table,
            registro_id_afectado=registro_pk,
            detalle_accion=detalle[:500],  # Limitar longitud
            direccion_ip=self._get_client_ip(),
            agente_usuario=self.request.META.get('HTTP_USER_AGENT', '')[
                :500],  # Limitar longitud
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
class AuditoriaSistemaListView(BaseListView):
    model = AuditoriaSistema
    model_manager_name = 'objects'
    template_name = 'auditoria_sistema_list.html'
    filterset_class = AuditoriaSistemaFilter
    context_object_name = 'auditorias'
    permission_required = 'myapp.view_auditoriasistema'
    paginate_by = ITEMS_PER_PAGE
    search_fields = ['usuario__username',
                     'tabla_afectada', 'tipo_accion', 'detalle_accion', 'direccion_ip']
    ordering_fields = ['tiempo_inicio', 'tipo_accion', 'activo',
                       'resultado_accion', 'usuario__username', 'tabla_afectada']
    ordering = ['-tiempo_inicio']  # Orden por defecto

    # get_queryset es heredado de BaseListView (maneja filtro, búsqueda, orden)

    # Sobrescribir get_context_data para añadir estadísticas específicas
    def get_context_data(self, **kwargs):
        # Obtiene contexto base con paginación, filtro, orden, etc.
        context = super().get_context_data(**kwargs)
        # Calcular estadísticas sobre el queryset filtrado (self.filterset.qs)
        # Fallback a object_list si no hay filtro
        qs_stats = self.filterset.qs if self.filterset else self.object_list

        stats = qs_stats.aggregate(
            total_auditorias=Count('id'),
            auditorias_exitosas=Count(
                Case(When(resultado_accion='EXITO', then=1))),
            auditorias_fallidas=Count(
                Case(When(resultado_accion='ERROR', then=1)))
        )
        context.update(stats)  # Añade las estadísticas al contexto
        context['active_tab'] = 'auditorias'
        context['tipos_accion'] = CommonChoices.TIPO_ACCION
        context['resultados_accion'] = CommonChoices.RESULTADO_ACCION
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
    template_name = 'auditoria_sistema_confirm_delete.html'
    context_object_name = 'auditoria'
    permission_required = 'myapp.delete_auditoriasistema'
    success_url = reverse_lazy('myapp:auditoria_sistema_list')

    # Añadir validación específica si es necesaria
    def can_delete(self, obj):
        if obj.tiempo_inicio and obj.tiempo_inicio > (timezone.now() - timedelta(days=30)):
            messages.error(
                self.request, ('Solo se pueden eliminar registros de auditoría con más de 30 días.'))
            return False
        return True
    # La lógica de post/delete y la notificación están en BaseDeleteView

    # Este método para notificar NO se llamará porque Auditoría no debería tener notificaciones
    # def enviar_notificacion_eliminacion(self, obj_pk, obj_repr): pass

# ==========================
# AfiliadoIndividual Vistas
# ==========================


class AfiliadoIndividualListView(BaseListView):
    model = AfiliadoIndividual
    model_manager_name = 'all_objects'  # Para BaseCRUDView
    template_name = 'afiliado_individual_list.html'
    filterset_class = AfiliadoIndividualFilter
    context_object_name = 'afiliados'
    permission_required = 'myapp.view_afiliadoindividual'
    search_fields = [
        'cedula', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
        'nacionalidad', 'municipio', 'ciudad', 'zona_postal', 'codigo_validacion',
        'telefono_habitacion', 'telefono_oficina', 'direccion_habitacion', 'direccion_oficina',
        'estado', 'intermediario__nombre_completo', 'intermediario__codigo'
    ]
    ordering_fields = [
        'primer_apellido', 'primer_nombre', 'cedula', 'tipo_identificacion', 'estado_civil',
        'sexo', 'parentesco', 'fecha_nacimiento', 'nacionalidad', 'fecha_ingreso',
        'intermediario__nombre_completo', 'activo', 'telefono_habitacion', 'telefono_oficina',
        'direccion_habitacion', 'direccion_oficina', 'estado', 'municipio', 'ciudad',
        'zona_postal', 'codigo_validacion', 'segundo_nombre', 'segundo_apellido',
        'fecha_creacion', 'fecha_modificacion'
        # 'cedula_numeric' # Necesitaría anotación si se usa
    ]
    ordering = ['primer_apellido', 'primer_nombre']

    def get_context_data(self, **kwargs):
        # Llama a BaseListView.get_context_data
        context = super().get_context_data(**kwargs)

        qs_stats = self.filterset.qs if self.filterset and self.filterset.qs.exists(
        ) else self.model.objects.none()

        stats = qs_stats.aggregate(
            total_afiliados=Count('id'),
            afiliados_activos=Count(Case(When(activo=True, then=1))),
            afiliados_titulares=Count(Case(When(parentesco='TITULAR', then=1)))
        )
        context.update(stats)
        context['active_tab'] = 'afiliados_individuales'
        context['tipos_identificacion'] = CommonChoices.TIPO_IDENTIFICACION
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
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        # Notificar también al intermediario si se asignó?
        # if afiliado.intermediario and hasattr(afiliado.intermediario, 'usuarios'):
        #     admin_users = list(admin_users) + list(afiliado.intermediario.usuarios.filter(is_active=True))
        if admin_users:
            crear_notificacion(
                list(set(admin_users)),  # Evitar duplicados
                mensaje,
                tipo='success',
                url_path_name='myapp:afiliado_individual_detail',
                url_kwargs={'pk': afiliado.pk}
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
    template_name = 'afiliado_individual_confirm_delete.html'
    context_object_name = 'afiliadoindividual'
    success_url = reverse_lazy('myapp:afiliado_individual_list')
    permission_required = 'myapp.delete_afiliadoindividual'

    # Añadir validación específica si es necesaria
    def can_delete(self, obj):
        if hasattr(obj, 'contratos') and obj.contratos.exists():
            messages.error(
                self.request, f"No se puede eliminar '{obj}': tiene contratos vinculados.")
            return False
        return True
    # post/delete heredado de BaseDeleteView llamará a enviar_notificacion_eliminacion

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó el Afiliado Individual: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')

# ==========================
# AfiliadoColectivo Vistas
# ==========================


class AfiliadoColectivoListView(BaseListView):
    model = AfiliadoColectivo
    model_manager_name = 'objects'
    template_name = 'afiliado_colectivo_list.html'
    filterset_class = AfiliadoColectivoFilter
    context_object_name = 'afiliados'
    permission_required = 'myapp.view_afiliadocolectivo'
    search_fields = [
        'razon_social', 'rif', 'tipo_empresa', 'direccion_comercial', 'estado',
        'municipio', 'ciudad', 'zona_postal', 'telefono_contacto', 'email_contacto',
        'intermediario__nombre_completo', 'intermediario__codigo'
    ]
    ordering_fields = [
        'activo', 'razon_social', 'rif', 'tipo_empresa', 'direccion_comercial',
        'estado', 'municipio', 'ciudad', 'zona_postal', 'telefono_contacto',
        'email_contacto', 'intermediario__nombre_completo', 'fecha_creacion',
        'fecha_modificacion'
        # 'rif_numeric' # Necesitaría anotación
    ]
    ordering = ['razon_social']

    # get_queryset es heredado

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_stats = self.filterset.qs if self.filterset else self.object_list
        stats = qs_stats.aggregate(
            total_afiliados=Count('id'),
            afiliados_activos=Count(Case(When(activo=True, then=1)))
        )
        context.update(stats)
        context['active_tab'] = 'afiliados_colectivos'
        context['tipos_empresa'] = CommonChoices.TIPO_EMPRESA
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
    template_name = 'afiliado_colectivo_confirm_delete.html'
    context_object_name = 'afiliado'
    permission_required = 'myapp.delete_afiliadocolectivo'
    success_url = reverse_lazy('myapp:afiliado_colectivo_list')

    # Añadir validación específica
    def can_delete(self, obj):
        # Usar related_name 'contratos_afiliados' definido en el modelo AfiliadoColectivo
        if hasattr(obj, 'contratos_afiliados') and obj.contratos_afiliados.exists():
            messages.error(
                self.request, f"No se puede eliminar '{obj}': tiene contratos asociados.")
            return False
        # Puedes añadir más validaciones aquí si es necesario
        return True
    # post/delete heredado

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó Empresa/Colectivo: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')

# ==========================
# ContratoIndividual Vistas
# ==========================


class ContratoIndividualListView(BaseListView):
    model = ContratoIndividual
    model_manager_name = 'objects'
    template_name = 'contrato_individual_list.html'
    filterset_class = ContratoIndividualFilter
    context_object_name = 'contratos'
    permission_required = 'myapp.view_contratoindividual'
    search_fields = [  # Mantener como estaba o ajustar según necesidad
        'ramo', 'forma_pago', 'estatus', 'estado_contrato', 'numero_contrato',
        'numero_poliza', 'certificado', 'intermediario__nombre_completo', 'intermediario__codigo',
        'afiliado__primer_nombre', 'afiliado__primer_apellido', 'afiliado__cedula',
        'contratante_cedula', 'contratante_nombre', 'plan_contratado', 'criterio_busqueda',
        'estatus_detalle', 'estatus_emision_recibo', 'suma_asegurada',
        # 'monto_total' # Buscar por monto total histórico
    ]
    ordering_fields = [  # Añadir campos calculados y tarifa si se desea ordenar por ellos
        'ramo', 'forma_pago', 'pagos_realizados', 'estatus', 'estado_contrato',
        'numero_contrato', 'numero_poliza', 'fecha_emision', 'fecha_inicio_vigencia',
        'fecha_fin_vigencia', 'monto_total', 'suma_asegurada', 'certificado', 'intermediario__nombre_completo',
        'afiliado__cedula', 'afiliado__primer_apellido', 'tipo_identificacion_contratante',
        'contratante_cedula', 'contratante_nombre', 'plan_contratado',
        'comision_recibo',  # Este campo parece que ya no existe o no aplica, REVISAR/QUITAR
        'fecha_inicio_vigencia_recibo', 'fecha_fin_vigencia_recibo',
        'dias_transcurridos_ingreso', 'estatus_detalle', 'estatus_emision_recibo',
        'comision_anual', 'activo', 'fecha_creacion', 'fecha_modificacion',
        # --- AÑADIDOS ---
        'cantidad_cuotas', 'importe_recibo_contrato', 'importe_anual_contrato',
        'tarifa_aplicada__id', 'tarifa_aplicada__monto_anual',
        # --- FIN AÑADIDOS ---
    ]
    ordering = ['-fecha_emision']

    # get_queryset heredado
    # get_context_data heredado (las estadísticas deberían seguir funcionando)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_stats = self.filterset.qs if self.filterset else self.object_list
        stats = qs_stats.aggregate(
            total_contratos=Count('id'),
            contratos_activos=Count(Case(When(activo=True, then=1))),
            contratos_vigentes=Count(Case(When(estatus='VIGENTE', then=1))),
            monto_total_general=Sum('monto_total')
        )
        context['total_contratos'] = stats.get('total_contratos', 0)
        context['contratos_activos'] = stats.get('contratos_activos', 0)
        context['contratos_vigentes'] = stats.get('contratos_vigentes', 0)
        context['monto_total_general'] = stats.get(
            'monto_total_general', Decimal('0.0')) or Decimal('0.0')
        context['active_tab'] = 'contratos_individuales'
        return context


# O directamente DetailView si BaseDetailView no existe o no es adecuada
class ContratoIndividualDetailView(BaseDetailView):
    model = ContratoIndividual
    template_name = 'contrato_individual_detail.html'
    context_object_name = 'contrato'  # Esto es lo que usa tu plantilla
    permission_required = 'myapp.view_contratoindividual'
    # model_manager_name = 'all_objects' # Descomenta si BaseDetailView usa esta lógica y quieres ver inactivos

    def get_queryset(self):
        # Si usas model_manager_name en una clase base:
        # queryset = super().get_queryset()
        # Si no, y quieres asegurar que ves todos (incluyendo inactivos si accedes por PK):
        # O ContratoIndividual.objects.all() si solo activos
        queryset = ContratoIndividual.all_objects.all()

        return super().get_queryset().select_related(
            'afiliado',
            'intermediario',
            'tarifa_aplicada'
        ).prefetch_related(
            Prefetch('reclamacion_set', queryset=Reclamacion.objects.select_related('usuario_asignado').prefetch_related(
                Prefetch('pagos', queryset=Pago.objects.filter(activo=True).order_by('-fecha_pago'), to_attr='pagos_activos_de_reclamacion'))
                .only('pk', 'monto_reclamado', 'estado', 'fecha_reclamo', 'tipo_reclamacion', 'usuario_asignado_id', 'contrato_individual_id'),
                to_attr='reclamaciones_con_pagos'),
            Prefetch('factura_set', queryset=Factura.objects.select_related('intermediario').prefetch_related(
                Prefetch('pagos', queryset=Pago.objects.filter(activo=True).only('pk', 'monto_pago'), to_attr='pagos_activos_de_factura')))
        )  # No es necesario añadir prefetch para RegistroComision si solo usas la propiedad agregada

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contrato = self.object

        logger.info(
            f"--- ContratoIndividualDetailView.get_context_data para Contrato PK: {contrato.pk} ---")

        # Procesar Facturas y sus Pagos
        facturas_asociadas = list(
            contrato.factura_set.all())  # Usa el prefetch
        monto_total_pagado_facturas = Decimal('0.00')
        for factura_obj in facturas_asociadas:
            # Acceder a los pagos prefetched usando el to_attr
            for pago_obj in getattr(factura_obj, 'pagos_activos_de_factura', []):
                if pago_obj.monto_pago:  # activo=True ya está en el prefetch
                    monto_total_pagado_facturas += pago_obj.monto_pago

        saldo_pendiente_facturas = sum(
            f.monto_pendiente for f in facturas_asociadas if f.monto_pendiente is not None
        ) or Decimal('0.00')

        # Procesar Reclamaciones y sus Pagos
        reclamaciones_con_sus_pagos = list(
            getattr(contrato, 'reclamaciones_con_pagos', []))
        pagos_de_reclamaciones_list = []
        for rec in reclamaciones_con_sus_pagos:
            # Acceder a los pagos prefetched usando el to_attr
            pagos_de_esta_reclamacion = list(
                getattr(rec, 'pagos_activos_de_reclamacion', []))
            pagos_de_reclamaciones_list.extend(pagos_de_esta_reclamacion)
            logger.info(
                f"  Reclamación PK {rec.pk} procesada, {len(pagos_de_esta_reclamacion)} pagos activos encontrados.")

        monto_total_pagado_reclamaciones = sum(
            p.monto_pago for p in pagos_de_reclamaciones_list if p.monto_pago) or Decimal('0.0')
        logger.info(
            f"  Total pagos de reclamaciones para el contexto: {len(pagos_de_reclamaciones_list)}, Monto: {monto_total_pagado_reclamaciones}")

        # Consumo de Cobertura (basado en todas las reclamaciones asociadas)
        monto_total_reclamado_general = sum(
            # Usa la lista de reclamaciones ya obtenida
            r.monto_reclamado for r in reclamaciones_con_sus_pagos if r.monto_reclamado
        ) or Decimal('0.00')

        saldo_cobertura = (contrato.suma_asegurada or Decimal(
            '0.00')) - monto_total_reclamado_general
        porcentaje_consumido = 0
        if contrato.suma_asegurada and contrato.suma_asegurada > 0:
            try:
                porcentaje_consumido = int(
                    (monto_total_reclamado_general / contrato.suma_asegurada * 100).quantize(Decimal('1.'), rounding=ROUND_HALF_UP))
                porcentaje_consumido = min(max(porcentaje_consumido, 0), 100)
            except (ZeroDivisionError, InvalidOperation):
                porcentaje_consumido = 0 if monto_total_reclamado_general == Decimal(
                    '0.00') else 100

        context.update({
            'page_title': f"Detalle CI: {contrato.numero_contrato or '(Sin número)'}",
            'afiliado': contrato.afiliado,
            'intermediario': contrato.intermediario,
            'tarifa_aplicada_obj': contrato.tarifa_aplicada,

            'duracion_contrato_meses': contrato.periodo_vigencia_meses or contrato.duracion_calculada_meses,
            'dias_desde_ingreso_afiliado': contrato.dias_transcurridos_ingreso,
            'esta_vigente_contrato': contrato.esta_vigente,
            'monto_total_contrato': contrato.monto_total,
            'importe_anual_referencial': contrato.importe_anual_contrato,
            'cantidad_cuotas_calculada': contrato.cantidad_cuotas_estimadas,
            'importe_recibo_calculado': contrato.monto_cuota_estimada,
            'forma_pago_display': contrato.get_forma_pago_display(),
            'estatus_emision_recibo_display': contrato.get_estatus_emision_recibo_display() if hasattr(contrato, 'get_estatus_emision_recibo_display') else contrato.estatus_emision_recibo,
            'suma_asegurada_contrato': contrato.suma_asegurada,
            'prima_anual_contrato': contrato.importe_anual_contrato,

            'facturas_asociadas': facturas_asociadas,
            'total_facturas': len(facturas_asociadas),
            'monto_total_pagado_facturas': monto_total_pagado_facturas,
            'saldo_pendiente_facturas': saldo_pendiente_facturas,
            'saldo_pendiente_anual': max(Decimal('0.00'), (contrato.importe_anual_contrato or Decimal('0.00')) - monto_total_pagado_facturas),

            'reclamaciones_asociadas': reclamaciones_con_sus_pagos,
            'total_reclamaciones': len(reclamaciones_con_sus_pagos),
            'monto_total_reclamado_general': monto_total_reclamado_general,

            'pagos_de_reclamaciones': pagos_de_reclamaciones_list,
            'total_pagos_reclamaciones': len(pagos_de_reclamaciones_list),
            'monto_total_pagado_reclamaciones': monto_total_pagado_reclamaciones,

            'saldo_cobertura': saldo_cobertura,
            'porcentaje_consumido': porcentaje_consumido,
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
    template_name = 'contrato_individual_confirm_delete.html'
    success_url = reverse_lazy('myapp:contrato_individual_list')
    permission_required = 'myapp.delete_contratoindividual'
    context_object_name = 'contratoindividual'

    # Añadir validación
    def can_delete(self, obj):
        if hasattr(obj, 'puede_eliminarse') and not obj.puede_eliminarse():
            messages.error(
                self.request, "No se puede eliminar: tiene facturas o reclamaciones asociadas.")
            return False
        return True
    # post/delete heredado

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó el Contrato Individual: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


# ==========================
# ContratoColectivo Vistas
# ==========================
class ContratoColectivoListView(BaseListView):
    model = ContratoColectivo
    model_manager_name = 'objects'
    template_name = 'contrato_colectivo_list.html'
    filterset_class = ContratoColectivoFilter
    context_object_name = 'contratos'
    permission_required = 'myapp.view_contratocolectivo'
    search_fields = [  # Revisar si son adecuados
        'ramo', 'forma_pago', 'estatus', 'estado_contrato', 'suma_asegurada', 'numero_contrato', 'numero_poliza',
        'certificado', 'intermediario__nombre_completo', 'intermediario__codigo', 'tipo_empresa',
        'criterio_busqueda', 'razon_social', 'rif', 'direccion_comercial', 'zona_postal',
        'numero_recibo', 'codigo_validacion', 'tarifa_aplicada'
        # 'monto_total' # Buscar por monto histórico
    ]
    ordering_fields = [  # Añadir campos calculados y tarifa
        'ramo', 'forma_pago', 'pagos_realizados', 'estatus', 'estado_contrato', 'numero_contrato',
        'numero_poliza', 'fecha_emision', 'fecha_inicio_vigencia', 'fecha_fin_vigencia', 'suma_asegurada',
        'monto_total', 'certificado', 'intermediario__nombre_completo', 'activo', 'tipo_empresa',
        'criterio_busqueda', 'razon_social', 'rif', 'cantidad_empleados', 'direccion_comercial',
        'zona_postal', 'numero_recibo', 'codigo_validacion', 'fecha_creacion', 'fecha_modificacion',
        # 'comision_recibo' # Quitar si ya no existe/aplica
        # --- AÑADIDOS ---
        'cantidad_cuotas', 'importe_recibo_contrato', 'importe_anual_contrato',
        'tarifa_aplicada__id', 'tarifa_aplicada__monto_anual',
        # --- FIN AÑADIDOS ---
    ]
    ordering = ['-fecha_emision']

    # get_queryset heredado

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_stats = self.filterset.qs if self.filterset else self.object_list
        stats = qs_stats.aggregate(
            total_contratos=Count('id'),
            contratos_activos=Count(Case(When(activo=True, then=1))),
            contratos_vigentes=Count(Case(When(estatus='VIGENTE', then=1))),
            total_empleados=Sum('cantidad_empleados'),
            total_monto=Sum('monto_total')
        )
        context['total_contratos'] = stats.get('total_contratos', 0)
        context['contratos_activos'] = stats.get('contratos_activos', 0)
        context['contratos_vigentes'] = stats.get('contratos_vigentes', 0)
        context['total_empleados'] = stats.get('total_empleados', 0) or 0
        context['total_monto'] = stats.get(
            'total_monto', Decimal('0.0')) or Decimal('0.0')
        context['active_tab'] = 'contratos_colectivos'
        return context


class ContratoColectivoDetailView(BaseDetailView):  # O directamente DetailView
    model = ContratoColectivo
    template_name = 'contrato_colectivo_detail.html'
    context_object_name = 'contrato'
    permission_required = 'myapp.view_contratocolectivo'
    # model_manager_name = 'all_objects' # Si es necesario

    def get_queryset(self):
        # queryset = super().get_queryset() # Si BaseDetailView usa model_manager_name
        # O ContratoColectivo.objects.all()
        queryset = ContratoColectivo.all_objects.all()

        return queryset.select_related(
            'intermediario',
            'tarifa_aplicada'
        ).prefetch_related(
            Prefetch('afiliados_colectivos',
                     queryset=AfiliadoColectivo.objects.only('pk', 'razon_social', 'rif')),
            Prefetch('reclamacion_set',
                     queryset=Reclamacion.objects.filter(
                         contrato_colectivo__isnull=False)
                     .select_related('usuario_asignado')
                     .prefetch_related(
                         Prefetch('pagos',
                                  queryset=Pago.objects.filter(
                                      activo=True).order_by('-fecha_pago'),
                                  to_attr='pagos_activos_de_reclamacion')
                     ).only('pk', 'monto_reclamado', 'estado', 'fecha_reclamo', 'tipo_reclamacion', 'usuario_asignado_id', 'contrato_colectivo_id'),
                     to_attr='reclamaciones_con_pagos'),
            Prefetch('factura_set',
                     queryset=Factura.objects.filter(
                         contrato_colectivo__isnull=False)
                     .select_related('intermediario')
                     .prefetch_related(
                         Prefetch('pagos',
                                  queryset=Pago.objects.filter(
                                      activo=True).only('pk', 'monto_pago'),
                                  to_attr='pagos_activos_de_factura')
                     ).only('pk', 'monto', 'monto_pendiente', 'pagada', 'vigencia_recibo_desde', 'vigencia_recibo_hasta', 'numero_recibo', 'intermediario_id', 'contrato_colectivo_id'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contrato = self.object
        logger.info(
            f"--- ContratoColectivoDetailView.get_context_data para Contrato PK: {contrato.pk} ---")

        facturas_asociadas = list(contrato.factura_set.all())
        monto_total_pagado_facturas = Decimal('0.00')
        for factura_obj in facturas_asociadas:
            for pago_obj in getattr(factura_obj, 'pagos_activos_de_factura', []):
                if pago_obj.monto_pago:
                    monto_total_pagado_facturas += pago_obj.monto_pago

        saldo_pendiente_facturas = sum(
            f.monto_pendiente for f in facturas_asociadas if f.monto_pendiente is not None
        ) or Decimal('0.00')

        reclamaciones_con_sus_pagos = list(
            getattr(contrato, 'reclamaciones_con_pagos', []))
        pagos_de_reclamaciones_list = []
        for rec in reclamaciones_con_sus_pagos:
            pagos_de_esta_reclamacion = list(
                getattr(rec, 'pagos_activos_de_reclamacion', []))
            pagos_de_reclamaciones_list.extend(pagos_de_esta_reclamacion)

        monto_total_pagado_reclamaciones = sum(
            p.monto_pago for p in pagos_de_reclamaciones_list if p.monto_pago) or Decimal('0.0')

        monto_total_reclamado_general = sum(
            r.monto_reclamado for r in reclamaciones_con_sus_pagos if r.monto_reclamado and r.estado in ['APROBADA', 'PAGADA', 'CERRADA']
        ) or Decimal('0.00')

        saldo_cobertura = (contrato.suma_asegurada or Decimal(
            '0.00')) - monto_total_reclamado_general
        porcentaje_consumido = 0
        if contrato.suma_asegurada and contrato.suma_asegurada > 0:
            try:
                porcentaje_consumido = int(
                    (monto_total_reclamado_general / contrato.suma_asegurada * 100).quantize(Decimal('1.'), rounding=ROUND_HALF_UP))
                porcentaje_consumido = min(max(porcentaje_consumido, 0), 100)
            except (ZeroDivisionError, InvalidOperation):
                porcentaje_consumido = 0 if monto_total_reclamado_general == Decimal(
                    '0.00') else 100

        prima_anual = contrato.importe_anual_contrato or Decimal(
            '0.00')  # Usar la propiedad del modelo

        context.update({
            'page_title': f"Detalle CC: {contrato.numero_contrato or contrato.razon_social}",
            'intermediario': contrato.intermediario,
            'tarifa_aplicada_obj': contrato.tarifa_aplicada,

            'duracion_contrato_meses': contrato.periodo_vigencia_meses or contrato.duracion_calculada_meses,
            'esta_vigente_contrato': contrato.esta_vigente,
            'monto_total_contrato': contrato.monto_total,
            'importe_anual_referencial': contrato.importe_anual_contrato,  # Usar la propiedad
            'cantidad_cuotas_calculada': contrato.cantidad_cuotas_estimadas,
            'importe_recibo_calculado': contrato.monto_cuota_estimada,
            'forma_pago_display': contrato.get_forma_pago_display(),
            'suma_asegurada_contrato': contrato.suma_asegurada,
            'prima_anual_contrato': prima_anual,

            'facturas_asociadas': facturas_asociadas,
            'total_facturas': len(facturas_asociadas),
            'monto_total_pagado_facturas': monto_total_pagado_facturas,
            'saldo_pendiente_facturas': saldo_pendiente_facturas,
            'saldo_pendiente_anual': max(Decimal('0.00'), prima_anual - monto_total_pagado_facturas),

            'reclamaciones_asociadas': reclamaciones_con_sus_pagos,
            'total_reclamaciones': len(reclamaciones_con_sus_pagos),
            'monto_total_reclamado_general': monto_total_reclamado_general,

            'pagos_de_reclamaciones': pagos_de_reclamaciones_list,
            'total_pagos_reclamaciones': len(pagos_de_reclamaciones_list),
            'monto_total_pagado_reclamaciones': monto_total_pagado_reclamaciones,

            'saldo_cobertura': saldo_cobertura,
            'porcentaje_consumido': porcentaje_consumido,

            # Ya prefetched
            'afiliados_asociados': list(contrato.afiliados_colectivos.all()),
            'total_afiliados_asociados': contrato.afiliados_colectivos.count(),
            'porcentaje_ejecucion_vigencia': contrato.porcentaje_ejecucion_vigencia,

            # 'active_tab': 'contratos_colectivos_detail', # Tu active_tab
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

    # --- MÉTODO get_form CORREGIDO ---
    def get_form(self, form_class=None):
        """
        Obtiene la instancia del formulario base sin modificaciones
        adicionales de readonly/disabled en esta vista.
        """
        form = super().get_form(form_class)
        # SE ELIMINÓ EL BLOQUE if not self.request.user.is_superuser ...
        return form
    # --- FIN MÉTODO get_form CORREGIDO ---

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = f"Editar Contrato Colectivo: {self.object.numero_contrato or self.object.razon_social}"
        return context

    def form_valid(self, form):
        # ... (lógica de form_valid y notificación como estaba) ...
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
        # ... (código de notificación como estaba) ...
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
    template_name = 'contrato_colectivo_confirm_delete.html'
    context_object_name = 'contrato'
    permission_required = 'myapp.delete_contratocolectivo'
    success_url = reverse_lazy('myapp:contrato_colectivo_list')

    # Añadir validación
    def can_delete(self, obj):
        related_errors = []
        if hasattr(obj, 'factura_set') and obj.factura_set.exists():
            related_errors.append('facturas')
        if hasattr(obj, 'reclamacion_set') and obj.reclamacion_set.exists():
            related_errors.append('reclamaciones')
        if hasattr(obj, 'afiliados_colectivos') and obj.afiliados_colectivos.exists():
            related_errors.append('afiliados colectivos')

        if related_errors:
            error_msg = f"No se puede eliminar '{obj}': tiene {', '.join(related_errors)} vinculados."
            messages.error(self.request, error_msg)
            return False
        return True
    # post/delete heredado

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó Contrato Colectivo: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')

# ==========================
# Intermediario Vistas
# ==========================


class IntermediarioListView(BaseListView):
    model = Intermediario
    model_manager_name = 'objects'
    template_name = 'intermediario_list.html'
    filterset_class = IntermediarioFilter
    context_object_name = 'intermediarios'
    permission_required = 'myapp.view_intermediario'
    search_fields = [
        'codigo', 'nombre_completo', 'rif', 'direccion_fiscal', 'telefono_contacto',
        'email_contacto', 'intermediario_relacionado__nombre_completo',
        'usuarios__username', 'usuarios__email'
    ]
    ordering_fields = [
        'activo', 'codigo', 'nombre_completo', 'rif', 'direccion_fiscal',
        'telefono_contacto', 'email_contacto', 'intermediario_relacionado__nombre_completo',
        'porcentaje_comision', 'fecha_creacion', 'fecha_modificacion'
        # 'codigo_numeric', 'rif_numeric' # Necesitan anotación
    ]
    ordering = ['nombre_completo']

    # get_queryset heredado

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_stats = self.filterset.qs if self.filterset else self.object_list
        stats = qs_stats.aggregate(
            total_intermediarios=Count('id'),
            intermediarios_activos=Count(Case(When(activo=True, then=1))),
            comision_promedio=Avg('porcentaje_comision')
        )
        context['total_intermediarios'] = stats.get('total_intermediarios', 0)
        context['intermediarios_activos'] = stats.get(
            'intermediarios_activos', 0)
        context['comision_promedio'] = stats.get('comision_promedio', 0) or 0
        context['active_tab'] = 'intermediarios'
        return context


class IntermediarioDetailView(BaseDetailView):
    model = Intermediario
    model_manager_name = 'all_objects'
    template_name = 'intermediario_detail.html'
    context_object_name = 'intermediario'
    permission_required = 'myapp.view_intermediario'

    def get_queryset(self):
        return super().get_queryset().select_related('intermediario_relacionado').prefetch_related(
            Prefetch('contratoindividual_set',
                     queryset=ContratoIndividual.objects.select_related('afiliado')),
            Prefetch('contratos_colectivos', queryset=ContratoColectivo.objects.select_related(
                'intermediario')),
            Prefetch('usuarios', queryset=Usuario.objects.only(
                'id', 'username', 'email'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        intermediario = self.object
        contratos_individuales = list(
            intermediario.contratoindividual_set.all())
        contratos_colectivos = list(intermediario.contratos_colectivos.all())
        usuarios_asociados = list(intermediario.usuarios.all())
        monto_total_individual = sum(
            c.monto_total for c in contratos_individuales if c.monto_total) or Decimal('0.0')
        monto_total_colectivo = sum(
            c.monto_total for c in contratos_colectivos if c.monto_total) or Decimal('0.0')
        monto_total_contratos = monto_total_individual + monto_total_colectivo
        comision_estimada = (monto_total_contratos * intermediario.porcentaje_comision /
                             Decimal('100.0')) if intermediario.porcentaje_comision else Decimal('0.0')

        context.update({
            'intermediario_relacionado_obj': intermediario.intermediario_relacionado,
            'contratos_individuales_asociados': contratos_individuales,
            'contratos_colectivos_asociados': contratos_colectivos,
            'usuarios_asociados': usuarios_asociados,
            'total_contratos': len(contratos_individuales) + len(contratos_colectivos),
            'total_contratos_individuales': len(contratos_individuales),
            'total_contratos_colectivos': len(contratos_colectivos),
            'monto_total_contratos': monto_total_contratos,
            'comision_estimada_total': comision_estimada,
            'active_tab': 'intermediarios_detail',
        })
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
    template_name = 'intermediario_confirm_delete.html'
    context_object_name = 'intermediario'
    permission_required = 'myapp.delete_intermediario'
    success_url = reverse_lazy('myapp:intermediario_list')

    # Añadir validación
    def can_delete(self, obj):
        if obj.contratoindividual_set.exists() or obj.contratos_colectivos.exists():
            messages.error(
                self.request, "No se puede eliminar: tiene contratos asociados.")
            return False
        if hasattr(obj, 'sub_intermediarios') and obj.sub_intermediarios.exists():
            messages.error(
                self.request, "No se puede eliminar: tiene sub-intermediarios asociados.")
            return False
        # Comentar o eliminar si los usuarios no deben impedir borrar
        # if hasattr(obj, 'usuarios') and obj.usuarios.exists():
        #    messages.error(self.request, "No se puede eliminar: tiene usuarios asociados.")
        #    return False
        return True
    # post/delete heredado

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó Intermediario: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


# ==========================
# Reclamacion Vistas
# ==========================
class ReclamacionListView(BaseListView):
    model = Reclamacion
    model_manager_name = 'objects'
    template_name = 'reclamacion_list.html'
    filterset_class = ReclamacionFilter
    context_object_name = 'reclamaciones'
    permission_required = 'myapp.view_reclamacion'
    search_fields = [
        'tipo_reclamacion', 'estado', 'descripcion_reclamo', 'observaciones_internas',
        'observaciones_cliente', 'contrato_individual__numero_contrato',
        'contrato_individual__afiliado__primer_nombre', 'contrato_individual__afiliado__primer_apellido',
        'contrato_individual__afiliado__cedula', 'contrato_colectivo__numero_contrato',
        'contrato_colectivo__razon_social', 'contrato_colectivo__rif', 'usuario_asignado__username',
        'usuario_asignado__email', 'usuario_asignado__primer_nombre', 'usuario_asignado__primer_apellido'
    ]
    ordering_fields = [
        'id', 'activo', 'tipo_reclamacion', 'estado', 'descripcion_reclamo', 'monto_reclamado',
        'fecha_reclamo', 'fecha_cierre_reclamo', 'contrato_individual__numero_contrato',
        'contrato_colectivo__razon_social', 'usuario_asignado__username',
        'contrato_individual__afiliado__primer_apellido', 'fecha_creacion', 'fecha_modificacion'
    ]
    ordering = ['-fecha_reclamo', '-fecha_creacion']

    # get_queryset heredado

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_stats = self.filterset.qs if self.filterset else self.object_list
        stats = qs_stats.aggregate(
            total_reclamaciones=Count('id'),
            reclamaciones_abiertas=Count(Case(When(estado='ABIERTA', then=1))),
            reclamaciones_cerradas=Count(Case(When(estado='CERRADA', then=1))),
            monto_total_reclamado=Sum('monto_reclamado'),
            monto_promedio_reclamado=Avg('monto_reclamado')
        )
        context['total_reclamaciones'] = stats.get('total_reclamaciones', 0)
        context['reclamaciones_abiertas'] = stats.get(
            'reclamaciones_abiertas', 0)
        context['reclamaciones_cerradas'] = stats.get(
            'reclamaciones_cerradas', 0)
        context['monto_total_reclamado'] = stats.get(
            'monto_total_reclamado', Decimal('0.0')) or Decimal('0.0')
        context['monto_promedio_reclamado'] = stats.get(
            'monto_promedio_reclamado', Decimal('0.0')) or Decimal('0.0')
        context['active_tab'] = 'reclamaciones'
        context['estados_reclamacion'] = CommonChoices.ESTADO_RECLAMACION
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
    template_name = 'reclamacion_confirm_delete.html'
    context_object_name = 'reclamacion'
    permission_required = 'myapp.delete_reclamacion'
    success_url = reverse_lazy('myapp:reclamacion_list')

    # Añadir validación
    def can_delete(self, obj):
        if hasattr(obj, 'pagos') and obj.pagos.exists():
            messages.error(
                self.request, "No se puede eliminar: tiene pagos asociados.")
            return False
        return True
    # post/delete heredado

    def enviar_notificacion_eliminacion(self, rec_pk, rec_repr):
        mensaje = f"Se eliminó la Reclamación: {rec_repr} (ID: {rec_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


# ==========================
# Pago Vistas
# ==========================
class PagoListView(BaseListView):
    model = Pago
    model_manager_name = 'objects'
    template_name = 'pago_list.html'
    filterset_class = PagoFilter
    context_object_name = 'pagos'
    permission_required = 'myapp.view_pago'
    search_fields = [
        'referencia_pago', 'observaciones_pago', 'reclamacion__id', 'reclamacion__descripcion_reclamo',
        'factura__numero_recibo', 'factura__contrato_individual__numero_contrato',
        'factura__contrato_colectivo__numero_contrato'
        # 'forma_pago' se maneja con anotación en get_queryset
    ]
    ordering_fields = [
        'activo', 'forma_pago', 'fecha_pago', 'monto_pago', 'referencia_pago',
        'fecha_notificacion_pago', 'observaciones_pago', 'reclamacion__id',
        'reclamacion__fecha_reclamo', 'factura__numero_recibo', 'factura__monto',
        'factura__fecha_creacion', 'fecha_creacion', 'fecha_modificacion'
    ]
    ordering = ['-fecha_pago', '-fecha_creacion']

    def get_queryset(self):
        queryset = self.model.objects.select_related(
            'reclamacion__contrato_individual__afiliado',
            'reclamacion__contrato_colectivo',
            'reclamacion__usuario_asignado',
            'factura__contrato_individual__afiliado',
            'factura__contrato_colectivo',
            'factura__intermediario'
        )

        self.filterset = self.filterset_class(
            self.request.GET, queryset=queryset)
        queryset = self.filterset.qs

        search_query = escape(self.request.GET.get('search', '')).strip()
        if search_query:
            filters = Q()
            # Anotación para forma_pago_display
            forma_pago_cases = [When(forma_pago=key, then=Value(
                display)) for key, display in CommonChoices.FORMA_PAGO_RECLAMACION]
            if forma_pago_cases:
                queryset = queryset.annotate(forma_pago_display=Case(
                    *forma_pago_cases, default=Value(''), output_field=CharField()))
                filters |= Q(forma_pago_display__icontains=search_query)

            # Búsqueda en otros campos (excluyendo forma_pago directo)
            for field in self.search_fields:
                try:
                    if field == 'monto_pago':
                        try:
                            filters |= Q(
                                **{f"{field}__exact": Decimal(search_query.replace(',', '.'))})
                        except:
                            pass
                    elif field == 'reclamacion__id':
                        try:
                            filters |= Q(**{f"{field}": int(search_query)})
                        except:
                            pass
                    else:
                        # Validar ruta antes de añadir __icontains
                        self._validate_lookup_path(self.model, field)
                        filters |= Q(**{f"{field}__icontains": search_query})
                except FieldDoesNotExist:
                    logger.warning(f"Campo búsqueda '{field}' inválido.")
                except Exception as e:
                    logger.error(
                        f"Error procesando campo búsqueda {field}: {e}")

            if filters:
                queryset = queryset.filter(filters).distinct()

        # Ordenamiento (heredado/reutilizado de BaseListView)
        # Llama a un método helper de ordenación
        return super(PagoListView, self)._apply_ordering(queryset)

    # Método auxiliar para validar rutas (puede estar en BaseListView)
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
                related_model._meta.get_field(part)  # Validar campo final

    # Método auxiliar para ordenar (puede estar en BaseListView)
    def _apply_ordering(self, queryset):
        sort_by = self.request.GET.get('sort')
        default_sort = self.get_ordering() or ['-pk']
        if not sort_by:
            sort_by = default_sort[0]

        order = self.request.GET.get(
            'order', 'asc' if not sort_by.startswith('-') else 'desc')
        prefix = '-' if order == 'desc' else ''
        sort_field = sort_by.lstrip('-')

        if sort_field and hasattr(self, 'ordering_fields') and sort_field in self.ordering_fields:
            try:
                self._validate_lookup_path(self.model, sort_field)
                # Lógica de anotación específica si existe
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
        else:
            if sort_by:
                logger.warning(
                    f"Campo orden '{sort_by}' no permitido/inválido. Usando defecto.")
            queryset = queryset.order_by(*default_sort)
            self.current_sort = default_sort[0].lstrip('-')
            self.current_order = 'desc' if default_sort[0].startswith(
                '-') else 'asc'
        return queryset

    def get_context_data(self, **kwargs):
        # BaseListView añade filter, current_sort, current_order
        context = super().get_context_data(**kwargs)
        qs_stats = self.filterset.qs if self.filterset else self.object_list

        # Recalcular filtros para estadísticas si hubo búsqueda general (incluye anotación)
        search_query = escape(self.request.GET.get('search', '')).strip()
        if qs_stats is not None and search_query:
            filters_stats = Q()
            forma_pago_cases_stats = [When(forma_pago=key, then=Value(
                display)) for key, display in CommonChoices.FORMA_PAGO_RECLAMACION]
            if forma_pago_cases_stats:
                qs_stats_annotated = qs_stats.annotate(forma_pago_display_stats=Case(
                    *forma_pago_cases_stats, default=Value(''), output_field=CharField()))
                filters_stats |= Q(
                    forma_pago_display_stats__icontains=search_query)
                qs_stats = qs_stats_annotated  # Usar el anotado para el resto de filtros

            if self.search_fields:
                for field in self.search_fields:
                    try:
                        if field == 'monto_pago':
                            try:
                                filters_stats |= Q(
                                    **{f"{field}__exact": Decimal(search_query.replace(',', '.'))})
                            except:
                                pass
                        elif field == 'reclamacion__id':
                            try:
                                filters_stats |= Q(
                                    **{f"{field}": int(search_query)})
                            except:
                                pass
                        else:
                            self._validate_lookup_path(self.model, field)
                            filters_stats |= Q(
                                **{f"{field}__icontains": search_query})
                    except:
                        pass  # Ignorar errores en stats
            if filters_stats:
                qs_stats = qs_stats.filter(filters_stats).distinct()
        # FIN Recalcular filtros para estadísticas

        stats = qs_stats.aggregate(
            total_pagos=Count('id'),
            total_monto=Sum('monto_pago'),
            promedio_monto=Avg('monto_pago')
        )
        context['total_pagos'] = stats.get('total_pagos', 0)
        context['total_monto'] = stats.get(
            'total_monto', Decimal('0.0')) or Decimal('0.0')
        context['promedio_monto'] = stats.get(
            'promedio_monto', Decimal('0.0')) or Decimal('0.0')
        context['active_tab'] = 'pagos'
        context['formas_pago'] = CommonChoices.FORMA_PAGO_RECLAMACION
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


@method_decorator(csrf_protect, name='dispatch')
class PagoCreateView(BaseCreateView):
    model = Pago
    model_manager_name = 'all_objects'
    form_class = PagoForm
    template_name = 'pago_form.html'
    success_url = reverse_lazy('myapp:pago_list')
    permission_required = 'myapp.add_pago'

    # --- Sobrescribir form_valid para manejar específicamente errores de Pago.save() ---
    def form_valid(self, form):
        try:
            # Intentar guardar el objeto Pago (esto llamará a Pago.save() con su lógica)
            with transaction.atomic():
                self.object = form.save()

            # --- INICIO NOTIFICACIÓN (CREATE) ---
            try:
                if hasattr(self, 'enviar_notificacion_creacion'):
                    self.enviar_notificacion_creacion(self.object)
            except Exception as notif_error:
                logger.error(
                    f"Error al enviar notificación de creación para Pago {self.object.pk}: {notif_error}", exc_info=True)
                messages.warning(
                    self.request, "El pago se guardó, pero hubo un problema al enviar la notificación.")
            # --- FIN NOTIFICACIÓN ---

            # Auditoría y mensaje de éxito (manejados por BaseCreateView/BaseCRUDView si form_valid no se sobrescribiera)
            self._create_audit_entry(
                action_type='CREACION', resultado='EXITO', detalle=f"Pago creado: {self.object}")
            messages.success(self.request, "Pago guardado exitosamente.")
            return HttpResponseRedirect(self.get_success_url())

        except ValidationError as e:
            # Errores específicos lanzados desde Pago.clean o Pago.save
            logger.warning(
                f"ValidationError al guardar Pago: {e.message_dict if hasattr(e, 'message_dict') else e.messages}")
            if hasattr(e, 'message_dict'):
                for field, errors in e.message_dict.items():
                    form.add_error(field if field !=
                                   '__all__' else None, errors)
            else:
                form.add_error(None, e.messages)
            self._create_audit_entry(
                action_type='CREACION', resultado='ERROR', detalle=f"ValidationError: {e.messages}")
            return self.form_invalid(form)
        except IntegrityError as e:
            logger.error(f"IntegrityError al guardar Pago: {e}", exc_info=True)
            form.add_error(None, "Error de base de datos al guardar.")
            self._create_audit_entry(
                action_type='CREACION', resultado='ERROR', detalle=f"IntegrityError: {str(e)[:200]}")
            return self.form_invalid(form)
        except Exception as e:
            logger.exception(f"Error inesperado al guardar Pago: {e!r}")
            form.add_error(
                None, "Ocurrió un error inesperado al guardar el pago.")
            self._create_audit_entry(
                action_type='CREACION', resultado='ERROR', detalle=f"Error inesperado: {str(e)[:200]}")
            return self.form_invalid(form)

    def enviar_notificacion_creacion(self, pago):
        mensaje = f"Nuevo pago (Ref: {pago.referencia_pago or pago.pk}) por ${pago.monto_pago:.2f}."
        url_name = 'myapp:pago_detail'
        url_k = {'pk': pago.pk}
        destinatarios = []
        if pago.reclamacion and pago.reclamacion.usuario_asignado:
            destinatarios.append(pago.reclamacion.usuario_asignado)
            mensaje += f" Asoc. a Reclamo #{pago.reclamacion.pk}."
        elif pago.factura:
            # Lógica para intermediario de la factura
            if pago.factura.intermediario and hasattr(pago.factura.intermediario, 'usuarios'):
                destinatarios.extend(
                    list(pago.factura.intermediario.usuarios.filter(is_active=True)))
            mensaje += f" Asoc. a Factura {pago.factura.numero_recibo}."
        # Siempre notificar admins?
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(list(set(destinatarios)), mensaje,
                               tipo='success', url_path_name=url_name, url_kwargs=url_k)


@method_decorator(csrf_protect, name='dispatch')
class PagoUpdateView(BaseUpdateView):
    model = Pago
    model_manager_name = 'all_objects'
    form_class = PagoForm
    template_name = 'pago_form.html'
    context_object_name = 'pago'
    permission_required = 'myapp.change_pago'
    success_url = reverse_lazy('myapp:pago_list')

    # --- Sobrescribir form_valid para manejar errores específicos de Pago.save() ---
    def form_valid(self, form):
        objeto_antes = self.get_object()  # Necesario para notificaciones
        try:
            # Intentar guardar (esto llamará a Pago.save() con su lógica)
            with transaction.atomic():
                self.object = form.save()

            # --- INICIO NOTIFICACIÓN (UPDATE) ---
            try:
                if hasattr(self, 'enviar_notificacion_actualizacion'):
                    self.enviar_notificacion_actualizacion(
                        objeto_antes, self.object, form.changed_data)
            except Exception as notif_error:
                logger.error(
                    f"Error al enviar notificación de actualización para Pago {self.object.pk}: {notif_error}", exc_info=True)
                messages.warning(
                    self.request, "El pago se actualizó, pero hubo un problema al enviar la notificación.")
            # --- FIN NOTIFICACIÓN ---

            # Auditoría y mensaje de éxito
            self._create_audit_entry(
                action_type='MODIFICACION', resultado='EXITO', detalle=f"Pago actualizado: {self.object}")
            messages.success(self.request, "Pago actualizado exitosamente.")
            return HttpResponseRedirect(self.get_success_url())

        except ValidationError as e:
            logger.warning(
                f"ValidationError al actualizar Pago {objeto_antes.pk}: {e.message_dict if hasattr(e, 'message_dict') else e.messages}")
            if hasattr(e, 'message_dict'):
                for field, errors in e.message_dict.items():
                    form.add_error(field if field !=
                                   '__all__' else None, errors)
            else:
                form.add_error(None, e.messages)
            self._create_audit_entry(
                action_type='MODIFICACION', resultado='ERROR', detalle=f"ValidationError: {e.messages}")
            return self.form_invalid(form)
        except IntegrityError as e:
            logger.error(
                f"IntegrityError al actualizar Pago {objeto_antes.pk}: {e}", exc_info=True)
            form.add_error(None, "Error de base de datos al actualizar.")
            self._create_audit_entry(
                action_type='MODIFICACION', resultado='ERROR', detalle=f"IntegrityError: {str(e)[:200]}")
            return self.form_invalid(form)
        except Exception as e:
            logger.exception(
                f"Error inesperado al actualizar Pago {objeto_antes.pk}: {e!r}")
            form.add_error(
                None, "Ocurrió un error inesperado al actualizar el pago.")
            self._create_audit_entry(
                action_type='MODIFICACION', resultado='ERROR', detalle=f"Error inesperado: {str(e)[:200]}")
            return self.form_invalid(form)

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


@method_decorator(csrf_protect, name='dispatch')
class PagoDeleteView(BaseDeleteView):
    model = Pago
    template_name = 'pago_confirm_delete.html'
    context_object_name = 'pago'
    permission_required = 'myapp.delete_pago'
    success_url = reverse_lazy('myapp:pago_list')

    # --- Sobrescribir post para llamar a Pago.delete() explícitamente ---
    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            object_pk_for_audit = self.object.pk
            object_repr_for_audit = str(self.object)

            # Llamar al método delete personalizado del MODELO Pago
            # Esto ejecutará la lógica de actualización de Factura/Reclamación
            with transaction.atomic():  # Asegurar atomicidad en delete + actualizaciones
                self.object.delete()

            # Si no hubo excepciones en Pago.delete():
            messages.success(
                request, f"Pago '{object_repr_for_audit}' eliminado y saldos actualizados correctamente.")
            self._create_audit_entry(request, 'ELIMINACION', 'EXITO',
                                     f"Eliminación de Pago", object_pk_for_audit, object_repr_for_audit)

            # --- INICIO NOTIFICACIÓN (DELETE) ---
            try:
                if hasattr(self, 'enviar_notificacion_eliminacion'):
                    self.enviar_notificacion_eliminacion(
                        object_pk_for_audit, object_repr_for_audit)
            except Exception as notif_error:
                logger.error(
                    f"Error al enviar notificación de eliminación para Pago {object_pk_for_audit}: {notif_error}", exc_info=True)
                messages.warning(
                    self.request, "El pago se eliminó, pero hubo un problema al enviar la notificación.")
            # --- FIN NOTIFICACIÓN ---

            return HttpResponseRedirect(self.get_success_url())

        except ProtectedError as e:
            # ... (manejo de ProtectedError como en BaseDeleteView) ...
            logger.warning(
                f"ProtectedError al eliminar Pago {object_pk_for_audit}: {e}")
            messages.error(
                request, f"No se puede eliminar '{object_repr_for_audit}': tiene registros asociados protegidos.")
            self._create_audit_entry(request, 'ELIMINACION', 'ERROR',
                                     f"ProtectedError: {e}", object_pk_for_audit, object_repr_for_audit)
            try:
                return redirect('myapp:pago_detail', pk=object_pk_for_audit)
            except NoReverseMatch:
                return redirect(self.get_success_url())
        except self.model.DoesNotExist:
            # ... (manejo de DoesNotExist como en BaseDeleteView) ...
            logger.warning(
                f"Intento de eliminar Pago inexistente (kwargs={kwargs}) por {request.user}.")
            messages.error(
                request, "Error: El pago que intenta eliminar no existe.")
            return redirect(self.get_success_url())
        except Exception as e:  # Captura errores de Pago.delete() o cualquier otro
            # ... (manejo de Exception como en BaseDeleteView) ...
            current_pk = object_pk_for_audit if 'object_pk_for_audit' in locals(
            ) else self.kwargs.get('pk', 'N/A')
            logger.error(
                f"Error inesperado al eliminar Pago PK={current_pk}: {e}", exc_info=True)
            messages.error(
                request, f"Error inesperado al intentar eliminar el pago: {str(e)}")
            self._create_audit_entry(
                request, 'ELIMINACION', 'ERROR', f"Error inesperado: {str(e)[:200]}", current_pk)
            try:
                return redirect('myapp:pago_detail', pk=current_pk)
            except:
                return redirect(self.get_success_url())

    def enviar_notificacion_eliminacion(self, pago_pk, pago_repr):
        mensaje = f"Se eliminó Pago: {pago_repr} (ID: {pago_pk}). Los saldos asociados fueron recalculados."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


# ==========================
# Tarifa Vistas
# ==========================
class TarifaListView(BaseListView):
    model = Tarifa
    model_manager_name = 'objects'
    template_name = 'tarifa_list.html'
    filterset_class = TarifaFilter
    context_object_name = 'tarifas'
    permission_required = 'myapp.view_tarifa'
    search_fields = ['rango_etario', 'ramo', 'tipo_fraccionamiento']
    ordering_fields = [
        'activo', 'rango_etario', 'ramo', 'fecha_aplicacion', 'monto_anual',
        'tipo_fraccionamiento', 'comision_intermediario', 'fecha_creacion', 'fecha_modificacion'
    ]
    ordering = ['ramo', 'rango_etario', '-fecha_aplicacion']

    # get_queryset heredado

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_stats = self.filterset.qs if self.filterset else self.object_list
        stats = qs_stats.aggregate(
            total_tarifas=Count('id'),
            tarifas_activas=Count(Case(When(activo=True, then=1))),
            promedio_monto=Avg('monto_anual'),
            promedio_comision=Avg('comision_intermediario')
        )
        context['total_tarifas'] = stats.get('total_tarifas', 0)
        context['tarifas_activas'] = stats.get('tarifas_activas', 0)
        context['promedio_monto'] = stats.get(
            'promedio_monto', Decimal('0.0')) or Decimal('0.0')
        context['promedio_comision'] = stats.get(
            'promedio_comision', Decimal('0.0')) or Decimal('0.0')
        context['active_tab'] = 'tarifas'
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
# Asegúrate que herede de tu BaseDeleteView
class TarifaDeleteView(BaseDeleteView):
    model = Tarifa
    template_name = 'tarifa_confirm_delete.html'  # Tu plantilla
    context_object_name = 'object'  # Usar 'object' como en la plantilla
    permission_required = 'myapp.delete_tarifa'
    success_url = reverse_lazy('myapp:tarifa_list')

    # --- NUEVO: Añadir contexto para saber si está en uso ---
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tarifa = self.object
        # Verificar si algún contrato (de cualquier tipo) usa esta tarifa
        en_uso_individual = ContratoIndividual.objects.filter(
            tarifa_aplicada=tarifa).exists()
        en_uso_colectivo = ContratoColectivo.objects.filter(
            tarifa_aplicada=tarifa).exists()
        context['tarifa_en_uso'] = en_uso_individual or en_uso_colectivo
        if context['tarifa_en_uso']:
            logger.warning(
                f"Intento de borrar Tarifa {tarifa.pk} que está en uso.")
        return context
    # --- FIN NUEVO ---

    # --- Sobrescribir POST para prevenir borrado si está en uso ---
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        tarifa_en_uso = ContratoIndividual.objects.filter(tarifa_aplicada=self.object).exists() or \
            ContratoColectivo.objects.filter(
                tarifa_aplicada=self.object).exists()

        if tarifa_en_uso:
            messages.error(
                request, f"No se puede eliminar la Tarifa '{self.object}' porque está asignada a uno o más contratos.")
            # Redirigir de vuelta al detalle o a la lista
            # O a la lista
            return redirect('myapp:tarifa_detail', pk=self.object.pk)

        # Si no está en uso, proceder con la lógica de borrado de BaseDeleteView
        return super().post(request, *args, **kwargs)

    def enviar_notificacion_eliminacion(self, obj_pk, obj_repr):
        mensaje = f"Se eliminó la Tarifa: {obj_repr} (ID: {obj_pk})."
        admin_users = Usuario.objects.filter(is_superuser=True, is_active=True)
        if admin_users:
            crear_notificacion(list(admin_users), mensaje, tipo='warning')


class RegistroComisionListView(LoginRequiredMixin, FilterView):
    model = RegistroComision
    model_manager_name = 'objects'
    template_name = 'registro_comision_list.html'
    context_object_name = 'object_list'
    paginate_by = ITEMS_PER_PAGE
    filterset_class = RegistroComisionFilter

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'intermediario', 'factura_origen', 'pago_cliente',
            'intermediario_vendedor', 'usuario_que_liquido'
        )

        # Búsqueda simple con el nuevo nombre de parámetro
        self.search_query = self.request.GET.get(
            'search_query', None)  # <--- CAMBIO AQUÍ
        if self.search_query:
            queryset = queryset.filter(
                Q(id__icontains=self.search_query) |
                Q(intermediario__nombre_completo__icontains=self.search_query) |
                Q(intermediario__codigo__icontains=self.search_query) |
                Q(factura_origen__numero_recibo__icontains=self.search_query) |
                Q(pago_cliente__referencia_pago__icontains=self.search_query) |
                Q(intermediario_vendedor__nombre_completo__icontains=self.search_query) |
                Q(intermediario_vendedor__codigo__icontains=self.search_query) |
                Q(usuario_que_liquido__username__icontains=self.search_query)
            ).distinct()

        # Lógica de ordenación
        self.current_sort = self.request.GET.get('sort', '-fecha_calculo')
        self.current_order = self.request.GET.get('order', 'desc')
        if self.current_order not in ['asc', 'desc']:
            self.current_order = 'desc'

        sort_param = self.current_sort
        if self.current_order == 'desc' and not self.current_sort.startswith('-'):
            sort_param = f"-{self.current_sort}"
        elif self.current_order == 'asc' and self.current_sort.startswith('-'):
            sort_param = self.current_sort[1:]

        if sort_param:
            queryset = queryset.order_by(sort_param)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasa el search_query actual
        context['search_query'] = self.search_query or ''
        context['current_sort'] = self.current_sort
        context['current_order'] = self.current_order

        # Construir filter_params_pagination para preservar solo los filtros de django-filter
        # al usar los enlaces de ordenación/paginación generados por query_transform.
        filter_params = {}
        if self.filterset and self.filterset.form.is_valid():  # Usar self.filterset que es la instancia
            for name, value in self.filterset.form.cleaned_data.items():
                if value:  # Solo añadir si el filtro tiene un valor
                    # Para campos que pueden tener múltiples valores (como ModelMultipleChoiceFilter)
                    if isinstance(value, list):
                        # django-filter y los parámetros GET pueden manejar esto de diferentes maneras.
                        # A menudo, necesitarás pasar el parámetro múltiples veces.
                        # urlencode lo maneja bien si value es una lista de strings.
                        filter_params[name] = [str(v.pk) if hasattr(
                            v, 'pk') else str(v) for v in value]
                    else:
                        filter_params[name] = str(value.pk) if hasattr(
                            value, 'pk') else str(value)

        context['filter_params_pagination'] = "&" + \
            urlencode(filter_params, doseq=True) if filter_params else ""

        # Ya no necesitas search_params_pagination y sort_params_pagination si query_transform los maneja
        # y pasas search_query a query_transform.

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
    context_object_name = 'comisiones'  # El nombre que usa tu plantilla
    paginate_by = ITEMS_PER_PAGE  # O tu ITEMS_PER_PAGE
    # permission_required = 'myapp.view_registrocomision' # O un permiso para ver "mis comisiones"

    search_fields_config = {  # Campos para la búsqueda simple
        'id_comision': ['pk'],
        'factura': ['factura_origen__numero_recibo__icontains'],
        'tipo': ['tipo_comision__iexact'],
        # Para buscar por "PAGADA", "PENDIENTE"
        'estado_pago': ['estatus_pago_comision__iexact'],
        'vendedor_override': ['intermediario_vendedor__nombre_completo__icontains', 'intermediario_vendedor__codigo__icontains']
    }

    ordering_options = {  # Campos para ordenar y sus etiquetas
        'id': 'ID',
        'tipo_comision': 'Tipo',
        'monto_comision': 'Monto Comisión',
        'monto_base_calculo': 'Base Cálculo',
        'porcentaje_aplicado': '% Aplicado',
        'factura_origen__numero_recibo': 'Factura Origen',
        'intermediario_vendedor__nombre_completo': 'Venta de',
        'estatus_pago_comision': 'Estado Pago',
        'fecha_calculo': 'Fecha Cálculo',
        'fecha_pago_a_intermediario': 'Fecha Pago'
    }
    default_ordering = ['-fecha_calculo', '-id']  # Orden por defecto

    def get_queryset(self):
        user = self.request.user
        intermediario_del_usuario = None

        if hasattr(user, 'intermediario_id') and user.intermediario_id:
            intermediario_del_usuario = user.intermediario
        else:
            try:
                intermediario_del_usuario = Intermediario.objects.get(
                    usuarios=user)
            except Intermediario.DoesNotExist:
                pass  # Se manejará abajo
            except Intermediario.MultipleObjectsReturned:
                intermediario_del_usuario = Intermediario.objects.filter(
                    usuarios=user).first()
                if intermediario_del_usuario:
                    messages.info(
                        self.request, "Múltiples asociaciones de intermediario, mostrando comisiones del primero.")

        if not intermediario_del_usuario:
            messages.warning(
                self.request, "No se encontró un intermediario asociado a tu cuenta para mostrar comisiones.")
            return RegistroComision.objects.none()

        queryset = RegistroComision.objects.filter(
            Q(intermediario=intermediario_del_usuario) |
            Q(intermediario_vendedor__intermediario_relacionado=intermediario_del_usuario,
              tipo_comision='OVERRIDE')
        ).select_related(
            'intermediario', 'contrato_individual', 'contrato_colectivo',
            'pago_cliente', 'factura_origen', 'intermediario_vendedor', 'usuario_que_liquido'
        ).distinct()

        # Búsqueda simple
        self.search_query = self.request.GET.get('search', '').strip()
        if self.search_query:
            q_objects = Q()
            for field_group, lookups in self.search_fields_config.items():
                for lookup in lookups:
                    if field_group == 'id_comision':
                        try:
                            q_objects |= Q(pk=int(self.search_query))
                        except ValueError:
                            pass
                    else:
                        q_objects |= Q(**{lookup: self.search_query})
            if q_objects:
                queryset = queryset.filter(q_objects).distinct()

        # Ordenamiento
        sort_param = self.request.GET.get('sort')
        order_direction = self.request.GET.get('order', 'asc').lower()

        if sort_param and sort_param.lstrip('-') in self.ordering_options.keys():
            self.current_sort = sort_param.lstrip('-')
            self.current_order = 'desc' if order_direction == 'desc' else 'asc'
            if self.current_order == 'desc':
                queryset = queryset.order_by(f"-{self.current_sort}")
            else:
                queryset = queryset.order_by(self.current_sort)
        else:
            queryset = queryset.order_by(*self.default_ordering)
            self.current_sort = self.default_ordering[0].lstrip('-')
            self.current_order = 'desc' if self.default_ordering[0].startswith(
                '-') else 'asc'

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Mis Comisiones"
        # O la pestaña que corresponda
        context['active_tab'] = "mis_comisiones"

        context['search_query'] = getattr(self, 'search_query', '')
        context['current_sort'] = getattr(self, 'current_sort', self.default_ordering[0].lstrip(
            '-') if self.default_ordering else 'id')
        context['current_order'] = getattr(
            self, 'current_order', 'desc' if self.default_ordering and self.default_ordering[0].startswith('-') else 'asc')

        # Para que los filtros de ordenamiento funcionen con la búsqueda
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['preserved_filters_for_ordering'] = urlencode(
            {k: v for k, v in self.request.GET.items() if k not in ['sort', 'order', 'page']})
        context['preserved_filters_for_pagination'] = query_params.urlencode()

        context['ordering_options'] = self.ordering_options
        # Para el tag filter_has_override
        # Pasa la lista de comisiones al tag
        context['comisiones_list_for_tag'] = context['comisiones']
        return context


@login_required
def liquidacion_comisiones_view(request):
    logger.info(
        f"Accediendo a liquidacion_comisiones_view. Usuario: {request.user.username}")
    logger.info(f"Todos los GET params recibidos por la vista: {request.GET}")

    # Leer el parámetro 'search' de la URL, que es lo que envía scripts.js
    search_term = request.GET.get('search', '').strip()
    sort_param = request.GET.get('sort', 'nombre')
    order_param = request.GET.get('order', 'asc')

    logger.info(f"Término de búsqueda (parámetro 'search'): '{search_term}'")

    base_intermediarios_qs = Intermediario.objects.filter(activo=True)
    logger.info(
        f"Intermediarios activos INICIAL: {base_intermediarios_qs.count()}")

    if search_term:
        logger.info(f"Aplicando filtro de texto para: '{search_term}'")
        base_intermediarios_qs = base_intermediarios_qs.filter(
            Q(nombre_completo__icontains=search_term) |
            Q(codigo__icontains=search_term) |
            Q(rif__icontains=search_term)
        )
        logger.info(
            f"Intermediarios DESPUÉS de filtro de texto: {base_intermediarios_qs.count()}")
    else:
        logger.info("No se aplicó filtro de texto (search_term vacío).")

    intermediarios_con_saldos = base_intermediarios_qs.annotate(
        total_directa_pendiente_db=Coalesce(Sum(Case(When(comisiones_ganadas__tipo_comision='DIRECTA', comisiones_ganadas__estatus_pago_comision='PENDIENTE',
                                            then='comisiones_ganadas__monto_comision'), default=Value(Decimal('0.00')), output_field=DecimalField())), Value(Decimal('0.00'))),
        total_override_pendiente_db=Coalesce(Sum(Case(When(comisiones_ganadas__tipo_comision='OVERRIDE', comisiones_ganadas__estatus_pago_comision='PENDIENTE',
                                             then='comisiones_ganadas__monto_comision'), default=Value(Decimal('0.00')), output_field=DecimalField())), Value(Decimal('0.00')))
    ).annotate(
        total_general_pendiente_db=F(
            'total_directa_pendiente_db') + F('total_override_pendiente_db')
    ).distinct()
    logger.info(
        f"Intermediarios DESPUÉS de anotaciones de saldo: {intermediarios_con_saldos.count()}")

    # DECIDE SI QUIERES FILTRAR POR SALDO PENDIENTE > 0 DESPUÉS DE LA BÚSQUEDA
    # Si solo quieres mostrar los que tienen saldo pendiente y coinciden con la búsqueda:
    intermediarios_final_qs = intermediarios_con_saldos.filter(
        total_general_pendiente_db__gt=Decimal('0.00'))
    logger.info(
        f"Intermediarios DESPUÉS de filtro de saldo > 0: {intermediarios_final_qs.count()}")
    # Si quieres mostrar todos los que coinciden con la búsqueda, incluso con saldo 0:
    # intermediarios_final_qs = intermediarios_con_saldos

    ordering_map = {'codigo': 'codigo', 'nombre': 'nombre_completo', 'total_directa': 'total_directa_pendiente_db',
                    'total_override': 'total_override_pendiente_db', 'total_general': 'total_general_pendiente_db', }
    order_by_field = ordering_map.get(sort_param, 'nombre_completo')
    if order_param == 'desc':
        order_by_field = f"-{order_by_field}"
    intermediarios_ordenados_qs = intermediarios_final_qs.order_by(
        order_by_field)

    paginator = Paginator(intermediarios_ordenados_qs, 10)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    intermediario_ids_on_page = [interm.id for interm in page_obj.object_list]
    intermediarios_con_detalles_para_pagina = Intermediario.objects.filter(id__in=intermediario_ids_on_page).prefetch_related(
        Prefetch('comisiones_ganadas', queryset=RegistroComision.objects.filter(estatus_pago_comision='PENDIENTE').select_related('factura_origen', 'pago_cliente', 'contrato_individual__afiliado', 'contrato_colectivo', 'intermediario_vendedor', 'usuario_que_liquido').order_by('-fecha_calculo'), to_attr='comisiones_pendientes_para_modal'))
    map_interm_con_detalle = {
        interm.id: interm for interm in intermediarios_con_detalles_para_pagina}

    liquidacion_data_final = []
    for interm_page_obj in page_obj.object_list:
        interm_con_detalle_especifico = map_interm_con_detalle.get(
            interm_page_obj.id)
        comisiones_del_modal = getattr(interm_con_detalle_especifico, 'comisiones_pendientes_para_modal', [
        ]) if interm_con_detalle_especifico else []
        liquidacion_data_final.append({
            'intermediario': interm_page_obj,
            'total_directa_pendiente': interm_page_obj.total_directa_pendiente_db,
            'total_override_pendiente': interm_page_obj.total_override_pendiente_db,
            'total_general_pendiente': interm_page_obj.total_general_pendiente_db,
            'detalle_comisiones': comisiones_del_modal,
        })
    logger.info(
        f"Mostrando página {page_obj.number} con {len(liquidacion_data_final)}. Total intermediarios (filtrados, ordenados, con saldo > 0): {paginator.count}")

    ordering_options_display = [('codigo', 'Código', True), ('nombre', 'Nombre Completo', True), ('total_directa',
                                                                                                  'Directas Pend.', True), ('total_override', 'Override Pend.', True), ('total_general', 'Total General Pend.', True)]

    context = {
        'title': 'Liquidación de Comisiones Pendientes',
        'page_heading': '💸 Liquidación de Comisiones Pendientes por Intermediario',
        'liquidacion_data': liquidacion_data_final,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'active_tab': 'liquidacion_comisiones',
        # Pasar el valor del parámetro 'search' a la plantilla
        'search_query_param_value': search_term,
        'current_sort': sort_param,
        'current_order': order_param,
        'ordering_options_display': ordering_options_display,
        'preserved_filters': urlencode({'search': search_term, 'sort': sort_param, 'order': order_param, }),
    }
    return render(request, 'liquidacion_comisiones.html', context)


@login_required
def marcar_comisiones_pagadas_view(request):
    if request.method == 'POST':
        comisiones_ids_a_pagar = request.POST.getlist('comisiones_a_pagar_ids')
        fecha_pago_efectiva_str = request.POST.get('fecha_pago_efectiva')

        fecha_pago_a_usar = django_timezone.now().date()  # Default a hoy

        if fecha_pago_efectiva_str:
            try:
                # Parsear formato DD/MM/AAAA
                fecha_pago_a_usar = datetime.strptime(
                    fecha_pago_efectiva_str, '%d/%m/%Y').date()
                if fecha_pago_a_usar > django_timezone.now().date():
                    messages.error(
                        request, "La fecha de pago no puede ser futura. Se usará la fecha actual.")
                    fecha_pago_a_usar = django_timezone.now().date()
            except ValueError:
                messages.error(
                    request, "Formato de fecha de pago inválido (DD/MM/AAAA). Se usará la fecha actual.")
                # fecha_pago_a_usar ya es django_timezone.now().date() por defecto

        if comisiones_ids_a_pagar:
            try:
                comisiones_ids_int = [int(id_str)
                                      for id_str in comisiones_ids_a_pagar]
            except ValueError:
                messages.error(request, "Selección de comisiones inválida.")
                return redirect('myapp:liquidacion_comisiones')

            comisiones_a_actualizar = RegistroComision.objects.filter(
                id__in=comisiones_ids_int,
                estatus_pago_comision='PENDIENTE'
            )

            count_updated = comisiones_a_actualizar.update(
                estatus_pago_comision='PAGADA',
                fecha_pago_a_intermediario=fecha_pago_a_usar
            )

            if count_updated > 0:
                messages.success(
                    request, f"{count_updated} comisión(es) marcada(s) como pagada(s) con fecha {fecha_pago_a_usar.strftime('%d/%m/%Y')}.")
            else:
                messages.warning(
                    request, "No se marcaron comisiones. Pueden haber sido pagadas previamente o la selección fue inválida.")
        else:
            messages.warning(
                request, "No se seleccionaron comisiones para marcar como pagadas.")

        return redirect('myapp:liquidacion_comisiones')

    messages.error(request, "Acción no permitida (solo POST).")
    return redirect('myapp:liquidacion_comisiones')


# Nota el nombre diferente
def marcar_comision_individual_pagada_view(request, pk):
    if request.method == 'POST':
        comision = get_object_or_404(RegistroComision, pk=pk)
        if comision.estatus_pago_comision == 'PENDIENTE':
            comision.estatus_pago_comision = 'PAGADA'
            comision.fecha_pago_a_intermediario = django_timezone.now().date()
            # No necesitas el campo fecha_pago_efectiva aquí a menos que quieras añadirlo
            comision.save(
                update_fields=['estatus_pago_comision', 'fecha_pago_a_intermediario'])
            messages.success(
                request, f"Comisión #{comision.pk} marcada como pagada.")
        else:
            messages.warning(
                request, f"Comisión #{comision.pk} no estaba pendiente o ya fue procesada.")

        # Redirigir a donde sea apropiado, quizás a la misma página de detalle o a la lista
        next_url = request.POST.get('next', reverse(
            'myapp:registro_comision_detail', args=[comision.pk]))
        return redirect(next_url)

    messages.error(request, "Acción no permitida.")
    # Volver al detalle si no es POST
    return redirect('myapp:registro_comision_detail', pk=pk)

# ==========================
# Usuario Vistas
# ==========================

# --- VISTAS DE USUARIO ---


@method_decorator(csrf_protect, name='dispatch')
class UsuarioListView(BaseListView):
    model = Usuariomodel_manager_name = 'objects'
    template_name = 'usuario_list.html'
    context_object_name = 'object_list'
    filterset_class = UsuarioFilter
    permission_required = 'myapp.view_usuario'
    search_fields = ['email', 'primer_nombre', 'primer_apellido',
                     'tipo_usuario', 'departamento', 'intermediario__nombre_completo']
    ordering = ['-date_joined']  # Ejemplo de orden por defecto

    def get_queryset(self):
        # El queryset base (todos o activos)
        if self.request.user.is_superuser:
            base_qs = Usuario.all_objects.all()  # Superuser ve todos, incluyendo inactivos
        else:
            base_qs = Usuario.objects.all()  # Otros ven solo activos (por defecto del manager)

        # Aplicar filtrado/búsqueda de BaseListView
        # Para que BaseListView.get_queryset() funcione, necesita un queryset inicial.
        # Se lo pasamos temporalmente y luego aplicamos nuestra lógica de nivel.
        # Esto es un poco enrevesado, idealmente BaseListView permitiría pasar el qs base.

        # Solución más limpia: Llama a super() con el qs base correcto para el usuario.
        # Necesitaríamos que BaseListView acepte un queryset inicial o lo obtenga de self.model
        # y luego nosotros filtramos por nivel.

        # Vamos a asumir que super().get_queryset() usa self.model.objects.all() o similar
        # y luego nosotros aplicamos el filtro de nivel.

        # Primero, obtener el queryset de la clase base (que aplica filtros, búsqueda, ordenación)
        # Esto se aplicará sobre Usuario.objects.all() (o lo que defina BaseListView)
        # queryset = super().get_queryset() # Esto podría estar mal si BaseListView ya usa el manager por defecto

        # Corrección: aplicar filtros/búsqueda DESPUÉS de seleccionar el queryset base
        if self.request.user.is_superuser:
            initial_queryset = Usuario.all_objects.all()
        else:
            initial_queryset = Usuario.objects.all()  # Manager por defecto (activos)

        # Aplicar filtros de filterset_class
        if self.filterset_class:
            self.filterset = self.filterset_class(
                self.request.GET, queryset=initial_queryset, request=self.request)
            processed_queryset = self.filterset.qs
        else:
            processed_queryset = initial_queryset

        # Aplicar búsqueda general (si BaseListView no lo hizo ya con el filterset)
        search_query = self.request.GET.get('q', '').strip()
        if search_query and self.search_fields:
            # Si search_fields está definido y hay 'q', aplicamos la búsqueda
            # Esta lógica debería estar idealmente en BaseListView para reutilizar
            q_objects = [Q(**{f"{field}__icontains": search_query})
                         for field in self.search_fields]
            if q_objects:
                processed_queryset = processed_queryset.filter(
                    reduce(operator.or_, q_objects))

        # Aplicar filtro de seguridad de nivel
        if not self.request.user.is_superuser:
            processed_queryset = processed_queryset.filter(
                Q(nivel_acceso__lte=self.request.user.nivel_acceso) | Q(
                    pk=self.request.user.pk)
            )

        # Aplicar ordenación
        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, str):
                ordering = (ordering,)
            processed_queryset = processed_queryset.order_by(*ordering)

        return processed_queryset.select_related('intermediario').prefetch_related('groups')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # self.object_list ya es la página actual del queryset final

        # Para estadísticas, usar el queryset antes de la paginación
        # El queryset final de get_queryset() es el que queremos para stats
        # Esto re-ejecuta la query, no ideal.
        qs_for_stats = self.get_queryset()
        # Mejor si BaseListView expone el queryset filtrado no paginado.
        # O si el filterset está disponible y es sobre el queryset correcto.

        # Simplificación: si el filterset se aplicó sobre el queryset correcto, usarlo.
        if hasattr(self, 'filterset') and self.filterset:
            qs_for_stats = self.filterset.qs
            # Aplicar filtro de nivel aquí de nuevo si el filterset no lo hizo
            if not self.request.user.is_superuser:
                qs_for_stats = qs_for_stats.filter(
                    Q(nivel_acceso__lte=self.request.user.nivel_acceso) | Q(pk=self.request.user.pk))
        else:  # Fallback (puede no ser el queryset completo filtrado)
            # Solo la página actual, no ideal para stats totales
            qs_for_stats = self.object_list

        stats = qs_for_stats.aggregate(
            total_usuarios=Count('id'),
            usuarios_activos=Count(
                Case(When(activo=True, then=Value(1)), output_field=models.IntegerField())),
        )
        context['total_usuarios'] = stats.get('total_usuarios', 0)
        context['usuarios_activos'] = stats.get('usuarios_activos', 0)
        context['active_tab'] = 'usuarios'
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioDetailView(BaseDetailView):  # O tu clase base
    model = Usuario
    model_manager_name = 'all_objects'
    template_name = 'usuario_detail.html'
    context_object_name = 'usuario_detalle'  # Correcto
    permission_required = 'myapp.view_usuario'

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = Usuario.all_objects.all()
        else:
            qs = Usuario.objects.all()
        return qs.select_related('intermediario').prefetch_related('groups', 'user_permissions')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not self.request.user.is_superuser:
            if obj.nivel_acceso > self.request.user.nivel_acceso:
                raise PermissionDenied(
                    "No tiene permiso para ver el perfil de este usuario (nivel superior).")
            if not obj.activo and obj.pk != self.request.user.pk:
                raise PermissionDenied(
                    "No tiene permiso para ver el perfil de este usuario (inactivo).")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario_obj = context[self.context_object_name]  # o self.object

        context['nivel_acceso_display'] = usuario_obj.get_nivel_acceso_display()
        context['tipo_usuario_display'] = usuario_obj.get_tipo_usuario_display()
        context['departamento_display'] = usuario_obj.get_departamento_display()
        # 'groups' y 'user_permissions' ya están en usuario_obj por prefetch_related
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioCreateView(BaseCreateView):  # O tu clase base
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
            'tipo_usuario', 'nivel_acceso', 'departamento', 'intermediario',
            'activo', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
        ]
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioUpdateView(BaseUpdateView):  # O tu clase base
    model = Usuario
    model_manager_name = 'all_objects'
    form_class = FormularioEdicionUsuario
    template_name = 'usuario_form.html'
    permission_required = 'myapp.change_usuario'
    context_object_name = 'object'  # o 'usuario_detalle' si cambiaste el template

    def get_success_url(self):
        return reverse_lazy('myapp:usuario_detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # Llama a la base primero

        # 'form' y 'object' ya están en el contexto por la clase base UpdateView.
        # No accedas a self.form directamente.

        context['campos_seccion_personal'] = [
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'fecha_nacimiento', 'telefono', 'direccion'
        ]
        # Para edición, según tu FormularioEdicionUsuario.Meta.fields:
        campos_roles_edicion = [
            'tipo_usuario', 'nivel_acceso', 'departamento', 'intermediario',
            'activo', 'is_staff',
            'groups', 'user_permissions'
            # Solo añade 'is_superuser' si está en FormularioEdicionUsuario.Meta.fields
            # Y si la lógica en el __init__ del form lo permite para el usuario actual.
        ]
        # Para saber si 'is_superuser' está realmente disponible para edición en ESTE formulario
        # para ESTE usuario, es mejor verificar el formulario que ya está en el contexto.
        form_in_context = context.get('form')
        if form_in_context and 'is_superuser' in form_in_context.fields and not form_in_context.fields['is_superuser'].disabled:
            campos_roles_edicion.append('is_superuser')

        context['campos_seccion_roles'] = campos_roles_edicion
        return context


@method_decorator(csrf_protect, name='dispatch')
class UsuarioDeleteView(BaseDeleteView):
    model = Usuario
    # Para hard delete o confirmación de soft
    template_name = 'usuario_confirm_delete.html'
    permission_required = 'myapp.delete_usuario'
    success_url = reverse_lazy('myapp:usuario_list')

    def can_delete(self, obj_to_delete):  # Método auxiliar
        if obj_to_delete == self.request.user:
            messages.error(
                self.request, "Acción denegada: No puedes eliminar tu propia cuenta.")
            return False
        if not self.request.user.is_superuser:
            if obj_to_delete.nivel_acceso >= self.request.user.nivel_acceso:
                messages.error(
                    self.request, "Acción denegada: No puedes eliminar usuarios con nivel de acceso igual o superior al tuyo.")
                return False
            if obj_to_delete.is_superuser:
                messages.error(
                    self.request, "Acción denegada: No puedes eliminar a un superusuario.")
                return False
        return True


# ==========================
# Factura Vistas
# ==========================
class FacturaListView(BaseListView):
    model = Factura
    model_manager_name = 'objects'
    template_name = 'factura_list.html'
    filterset_class = FacturaFilter
    context_object_name = 'object_list'
    permission_required = 'myapp.view_factura'
    search_fields = [  # Asegúrate que estos estén completos según tu necesidad
        'estatus_factura', 'numero_recibo', 'relacion_ingreso', 'estatus_emision', 'observaciones',
        'contrato_individual__numero_contrato', 'contrato_individual__ramo',
        'contrato_individual__afiliado__primer_nombre', 'contrato_individual__afiliado__primer_apellido',
        'contrato_individual__afiliado__cedula', 'contrato_colectivo__numero_contrato',
        'contrato_colectivo__razon_social', 'contrato_colectivo__ramo', 'contrato_colectivo__rif',
        'intermediario__nombre_completo', 'intermediario__codigo'
    ]
    ordering_fields = [
        'id', 'activo', 'estatus_factura', 'vigencia_recibo_desde', 'vigencia_recibo_hasta',
        'monto', 'monto_pendiente', 'numero_recibo', 'dias_periodo_cobro', 'estatus_emision',
        'pagada', 'relacion_ingreso',  # 'recibos_pendientes_cache' fue reemplazado
        'aplica_igtf',
        'contrato_individual__numero_contrato', 'contrato_colectivo__razon_social',
        'intermediario__nombre_completo', 'intermediario__codigo',
        'contrato_individual__afiliado__primer_apellido', 'contrato_individual__afiliado__cedula',
        'fecha_creacion', 'fecha_modificacion',
        'ramo_anotado',
        'numero_recibo_numeric',  # Si lo usas, asegúrate de anotarlo también
        'live_installments_remaining'
    ]
    ordering = ['-fecha_creacion']

    def get_queryset(self):
        sort_param_url = self.request.GET.get('sort')
        order_param_url = self.request.GET.get('order', 'asc')

        campos_anotados_en_esta_vista = [
            'ramo_anotado', 'numero_recibo_numeric', 'live_installments_remaining']

        queryset_base = None
        if sort_param_url in campos_anotados_en_esta_vista:
            original_get = self.request.GET
            temp_get = self.request.GET.copy()
            temp_get.pop('sort', None)
            temp_get.pop('order', None)
            self.request.GET = temp_get
            try:
                queryset_base = super().get_queryset()
            finally:
                self.request.GET = original_get
        else:
            queryset_base = super().get_queryset()

        queryset_anotado = queryset_base.annotate(
            ramo_anotado=Coalesce(
                'contrato_individual__ramo',
                'contrato_colectivo__ramo',
                Value('-', output_field=CharField())
            )
        )

        paid_receipts_ci_subquery = Factura.objects.filter(
            contrato_individual_id=OuterRef('contrato_individual_id'),
            estatus_factura='PAGADA',
            activo=True
        ).values('contrato_individual_id').annotate(count=Count('id')).values('count')

        paid_receipts_cc_subquery = Factura.objects.filter(
            contrato_colectivo_id=OuterRef('contrato_colectivo_id'),
            estatus_factura='PAGADA',
            activo=True
        ).values('contrato_colectivo_id').annotate(count=Count('id')).values('count')

        # Para la división, es más seguro castear a FloatField y luego a IntegerField si es necesario
        # o usar funciones de base de datos para división entera si están disponibles y son necesarias.
        # Aquí usamos división flotante y luego se tratará como entero.

        # Lógica para calcular cuotas estimadas para ContratoIndividual
        total_installments_ci_expr = Case(
            When(contrato_individual__forma_pago='CONTADO', then=Value(1)),
            When(Q(contrato_individual__periodo_vigencia_meses__isnull=False) &
                 Q(contrato_individual__periodo_vigencia_meses__gt=0),
                 then=Case(
                When(contrato_individual__forma_pago='MENSUAL', then=F(
                    'contrato_individual__periodo_vigencia_meses')),
                When(contrato_individual__forma_pago='TRIMESTRAL', then=Cast(Cast(
                    F('contrato_individual__periodo_vigencia_meses'), FloatField()) + 2.0, FloatField()) / 3.0),
                When(contrato_individual__forma_pago='SEMESTRAL', then=Cast(Cast(
                    F('contrato_individual__periodo_vigencia_meses'), FloatField()) + 5.0, FloatField()) / 6.0),
                When(contrato_individual__forma_pago='ANUAL', then=Cast(Cast(
                    F('contrato_individual__periodo_vigencia_meses'), FloatField()) + 11.0, FloatField()) / 12.0),
                default=Value(0.0),
                output_field=FloatField()  # Salida como Float para la división
            )
            ),
            default=Value(0.0),
            output_field=FloatField()
        )

        # Lógica para calcular cuotas estimadas para ContratoColectivo
        total_installments_cc_expr = Case(
            When(contrato_colectivo__forma_pago='CONTADO', then=Value(1)),
            When(Q(contrato_colectivo__periodo_vigencia_meses__isnull=False) &
                 Q(contrato_colectivo__periodo_vigencia_meses__gt=0),
                 then=Case(
                When(contrato_colectivo__forma_pago='MENSUAL', then=F(
                    'contrato_colectivo__periodo_vigencia_meses')),
                When(contrato_colectivo__forma_pago='TRIMESTRAL', then=Cast(Cast(
                    F('contrato_colectivo__periodo_vigencia_meses'), FloatField()) + 2.0, FloatField()) / 3.0),
                When(contrato_colectivo__forma_pago='SEMESTRAL', then=Cast(Cast(
                    F('contrato_colectivo__periodo_vigencia_meses'), FloatField()) + 5.0, FloatField()) / 6.0),
                When(contrato_colectivo__forma_pago='ANUAL', then=Cast(Cast(
                    F('contrato_colectivo__periodo_vigencia_meses'), FloatField()) + 11.0, FloatField()) / 12.0),
                default=Value(0.0),
                output_field=FloatField()
            )
            ),
            default=Value(0.0),
            output_field=FloatField()
        )

        queryset_anotado = queryset_anotado.annotate(
            total_installments_contract_float=Coalesce(  # Mantenemos como float para el cálculo intermedio
                ExpressionWrapper(total_installments_ci_expr,
                                  output_field=FloatField()),
                ExpressionWrapper(total_installments_cc_expr,
                                  output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            ),
            paid_installments_contract=Coalesce(
                Subquery(paid_receipts_ci_subquery,
                         output_field=IntegerField()),
                Subquery(paid_receipts_cc_subquery,
                         output_field=IntegerField()),
                Value(0),
                output_field=IntegerField()
            )
        ).annotate(
            # Convertir el total de installments a entero DESPUÉS de los cálculos de división
            # CEIL para redondear hacia arriba
            total_installments_contract=Cast(
                Func(F('total_installments_contract_float'), function='CEIL'), IntegerField())
        ).annotate(
            # Calcular la diferencia
            installments_diff=ExpressionWrapper(
                F('total_installments_contract') -
                F('paid_installments_contract'),
                output_field=IntegerField()
            )
        ).annotate(
            # Aplicar la lógica final para live_installments_remaining
            live_installments_remaining=Case(
                When(total_installments_contract=0, then=Value(0)),
                # Comparar la expresión envuelta
                When(installments_diff__lt=0, then=Value(0)),
                default=F('installments_diff'),
                output_field=IntegerField()
            )
        )

        # Si también necesitas 'numero_recibo_numeric' para ordenar, anótalo aquí.
        # Ejemplo (si es solo la parte numérica de 'numero_recibo'):
        # from django.db.models.functions import Substr, Length, Cast
        # if 'numero_recibo_numeric' in campos_anotados_en_esta_vista or sort_param_url == 'numero_recibo_numeric':
        #     queryset_anotado = queryset_anotado.annotate(
        #         # Asumiendo que numero_recibo es algo como "REC-123" y quieres ordenar por 123
        #         # Esta es una suposición y necesitaría ajustarse a tu formato exacto.
        #         # Si numero_recibo ya es numérico o tiene un prefijo fijo:
        #         # numero_recibo_numeric_val=Cast(Substr('numero_recibo', 5), IntegerField()) # Ejemplo: si el prefijo es "REC-"
        #         # O si es más complejo, podrías necesitar RegexExtract o similar si tu DB lo soporta
        #         # Por ahora, un placeholder si no es el foco principal:
        #         numero_recibo_numeric=Value(0, output_field=IntegerField())
        #     )

        if sort_param_url in campos_anotados_en_esta_vista:
            prefix = "-" if order_param_url.lower() == "desc" else ""
            queryset_final = queryset_anotado.order_by(
                f"{prefix}{sort_param_url}")
        else:
            queryset_final = queryset_anotado

        return queryset_final

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort_param_url = self.request.GET.get('sort')
        order_param_url = self.request.GET.get('order', 'asc')

        campos_anotados_en_esta_vista = [
            'ramo_anotado', 'numero_recibo_numeric', 'live_installments_remaining']

        if sort_param_url in campos_anotados_en_esta_vista:
            context['current_sort'] = sort_param_url
            context['current_order'] = order_param_url.lower()

        return context


class FacturaDetailView(BaseDetailView):
    model = Factura
    model_manager_name = 'all_objects'
    template_name = 'factura_detail.html'
    context_object_name = 'object'  # Usa 'object' o 'factura' consistentemente
    permission_required = 'myapp.view_factura'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'contrato_individual__afiliado', 'contrato_colectivo', 'intermediario'
        ).prefetch_related(
            Prefetch('pagos', queryset=Pago.objects.order_by('-fecha_pago'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        factura = self.object  # Obtener objeto del contexto base
        pagos_list = list(factura.pagos.all())
        total_pagado = sum(
            p.monto_pago for p in pagos_list if p.monto_pago) or Decimal('0.00')
        contrato_asociado = factura.contrato_individual or factura.contrato_colectivo

        # Calcular IVA y total CON IVA (antes de IGTF)
        base_imponible = factura.monto or Decimal('0.00')
        tasa_iva = Decimal('0.16')  # Podría venir de settings
        monto_iva = (base_imponible *
                     tasa_iva).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_con_iva = base_imponible + monto_iva

        # Calcular IGTF si aplica
        monto_igtf = Decimal('0.00')
        tasa_igtf = Decimal('0.03')  # Podría venir de settings
        if factura.aplica_igtf:
            monto_igtf = (
                total_con_iva * tasa_igtf).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        total_a_pagar = total_con_iva + monto_igtf  # Total final

        context.update({
            'factura': factura,  # Pasar explícitamente si context_object_name es 'object'
            'estatus_factura_display': factura.get_estatus_factura_display(),
            'estatus_emision_display': factura.get_estatus_emision_display(),
            'contrato_asociado': contrato_asociado,
            'intermediario_factura': factura.intermediario,
            'pagos_asociados': pagos_list,
            'total_pagado': total_pagado,
            # Mostrar pendiente del modelo que se actualiza con pagos
            'monto_pendiente_factura': factura.monto_pendiente,
            'cantidad_pagos': len(pagos_list),
            'base_imponible': base_imponible,
            'monto_iva': monto_iva,
            'total_con_iva': total_con_iva,
            'monto_igtf': monto_igtf,
            'total_a_pagar': total_a_pagar,
            'tasa_iva_display': f"{tasa_iva:.0%}",
            'tasa_igtf_display': f"{tasa_igtf:.0%}",
            'active_tab': 'facturas',  # O 'facturas_detail'
        })
        return context


@method_decorator(csrf_protect, name='dispatch')
class FacturaCreateView(BaseCreateView):
    model = Factura
    model_manager_name = 'all_objects'
    form_class = FacturaForm
    template_name = 'factura_form.html'
    success_url = reverse_lazy('myapp:factura_list')
    permission_required = 'myapp.add_factura'

    # form_valid heredado

    def enviar_notificacion_creacion(self, factura):
        mensaje = f"Nueva Factura generada: {factura.numero_recibo} por ${factura.monto:.2f}."
        url_k = {'pk': factura.pk}
        destinatarios = []
        if factura.intermediario and hasattr(factura.intermediario, 'usuarios'):
            destinatarios.extend(
                list(factura.intermediario.usuarios.filter(is_active=True)))
        # Lógica para notificar al cliente si es necesario...
        destinatarios.extend(
            list(Usuario.objects.filter(is_superuser=True, is_active=True)))
        if destinatarios:
            crear_notificacion(list(set(destinatarios)), mensaje, tipo='info',
                               url_path_name='myapp:factura_detail', url_kwargs=url_k)


@method_decorator(csrf_protect, name='dispatch')
class FacturaUpdateView(BaseUpdateView):
    model = Factura
    model_manager_name = 'all_objects'
    form_class = FacturaForm
    template_name = 'factura_form.html'
    context_object_name = 'object'
    permission_required = 'myapp.change_factura'
    success_url = reverse_lazy('myapp:factura_list')

    # get_queryset heredado de BaseUpdateView

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        factura = self.object
        context['tiene_pagos'] = factura.pagos.exists()
        context['cantidad_pagos'] = factura.pagos.count()
        # Título específico
        context['form_title'] = f'Editar Factura: {factura.numero_recibo}'
        return context

    # form_valid heredado

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

        # Añadir otros campos si son relevantes
        # ...

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
    template_name = 'factura_confirm_delete.html'
    context_object_name = 'object'
    permission_required = 'myapp.delete_factura'
    success_url = reverse_lazy('myapp:factura_list')

    # Añadir validación
    def can_delete(self, obj):
        if hasattr(obj, 'pagos') and obj.pagos.exists():
            messages.error(
                self.request, f"No se puede eliminar: la factura '{obj.numero_recibo}' tiene pagos asociados.")
            return False
        return True
    # post/delete heredado

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


# En tu archivo de vistas
# ... (importaciones existentes) ...

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


# --- Clase ReporteGeneralView ---


logger_rgv_debug = logging.getLogger(
    "myapp.views.ReporteGeneralView_DEBUG_FULL")

# --- Función auxiliar para loguear el estado de los contratos problemáticos ---


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_tab'] = 'reportes'
        context['page_title'] = 'Reporte General del Sistema SMGP'

        # Inicialización de KPIs y placeholders
        kpi_counts = ['kpi_total_contratos', 'kpi_total_afiliados_ind', 'kpi_total_afiliados_col',
                      'kpi_total_reclamaciones', 'kpi_total_facturas', 'kpi_total_pagos',
                      'kpi_facturas_vencidas_conteo', 'kpi_comisiones_pendientes_conteo',
                      'kpi_total_contratos_individuales_count', 'kpi_total_contratos_colectivos_count']
        for kpi in kpi_counts:
            context[kpi] = 0
        kpi_decimals = ['kpi_monto_total_contratos', 'kpi_monto_total_pagado_facturas',
                        'kpi_monto_pendiente_facturas', 'kpi_total_igtf_recaudado',
                        'kpi_facturas_vencidas_monto', 'kpi_comisiones_pendientes_monto']
        for kpi in kpi_decimals:
            context[kpi] = Decimal('0.00')

        graficas_context_names = [
            'plotly_contratos_estado_html', 'plotly_reclamaciones_estado_html',
            'plotly_ramos_monto_html', 'plotly_resolucion_gauge_html',
            'plotly_impuestos_categoria_html', 'plotly_rentabilidad_intermediario_html'
        ]
        for g_ctx_name in graficas_context_names:
            context[g_ctx_name] = generar_figura_sin_datos_plotly(
                "Cargando...")

        context['datos_tabla_comisiones'] = {}
        context['table_top_tipos_reclamacion'] = []
        context['table_facturas_antiguas'] = []
        context['table_top_intermediarios'] = []
        context['url_lista_facturas_vencidas'] = '#'
        context['url_liquidacion_comisiones'] = '#'
        try:
            context['url_historial_liquidaciones'] = reverse(
                'myapp:historial_liquidaciones_list')
        except NoReverseMatch:
            context['url_historial_liquidaciones'] = '#'
        context['error'] = None

        hoy = py_date.today()
        ramo_map = dict(CommonChoices.RAMO)
        estatus_map_vigencia = dict(CommonChoices.ESTADOS_VIGENCIA)
        tipo_rec_map = dict(CommonChoices.TIPO_RECLAMACION)

        try:
            # --- Cálculo de KPIs ---
            logger_rgv.debug("Calculando KPIs...")
            context['kpi_total_contratos_individuales_count'] = ContratoIndividual.objects.filter(
                activo=True).count()
            context['kpi_total_contratos_colectivos_count'] = ContratoColectivo.objects.filter(
                activo=True).count()
            context['kpi_total_contratos'] = context['kpi_total_contratos_individuales_count'] + \
                context['kpi_total_contratos_colectivos_count']
            context['kpi_total_afiliados_ind'] = AfiliadoIndividual.objects.filter(
                activo=True).count()
            context['kpi_total_afiliados_col'] = AfiliadoColectivo.objects.filter(
                activo=True).count()
            context['kpi_total_reclamaciones'] = Reclamacion.objects.filter(
                activo=True).count()
            context['kpi_total_facturas'] = Factura.objects.filter(
                activo=True).count()
            context['kpi_total_pagos'] = Pago.objects.filter(
                activo=True).count()
            monto_contratos_ind = ContratoIndividual.objects.filter(activo=True).aggregate(
                total_monto=Coalesce(Sum('monto_total'), Value(Decimal('0.0'))))['total_monto']
            monto_contratos_col = ContratoColectivo.objects.filter(activo=True).aggregate(
                total_monto=Coalesce(Sum('monto_total'), Value(Decimal('0.0'))))['total_monto']
            context['kpi_monto_total_contratos'] = monto_contratos_ind + \
                monto_contratos_col
            context['kpi_monto_total_pagado_facturas'] = Pago.objects.filter(activo=True, factura__isnull=False).aggregate(
                total_pagado=Coalesce(Sum('monto_pago'), Value(Decimal('0.0'))))['total_pagado']
            context['kpi_monto_pendiente_facturas'] = Factura.objects.filter(pagada=False, activo=True).aggregate(
                total_pendiente=Coalesce(Sum('monto_pendiente'), Value(Decimal('0.0'))))['total_pendiente']
            facturas_vencidas_qs = Factura.objects.filter(
                activo=True, pagada=False, estatus_factura='VENCIDA')
            context['kpi_facturas_vencidas_conteo'] = facturas_vencidas_qs.count()
            context['kpi_facturas_vencidas_monto'] = facturas_vencidas_qs.aggregate(
                total_monto_vencido=Coalesce(Sum('monto_pendiente'), Value(Decimal('0.0'))))['total_monto_vencido']
            try:
                context['url_lista_facturas_vencidas'] = f"{reverse('myapp:factura_list')}?{urlencode({'estatus_factura': 'VENCIDA', 'pagada': '0', 'activo': '1'})}"
            except NoReverseMatch:
                pass
            comisiones_pendientes_qs = RegistroComision.objects.filter(
                estatus_pago_comision='PENDIENTE')
            context['kpi_comisiones_pendientes_conteo'] = comisiones_pendientes_qs.count()
            context['kpi_comisiones_pendientes_monto'] = comisiones_pendientes_qs.aggregate(
                total_monto_comision=Coalesce(Sum('monto_comision'), Value(Decimal('0.0'))))['total_monto_comision']
            try:
                context['url_liquidacion_comisiones'] = reverse(
                    'myapp:liquidacion_comisiones')
            except NoReverseMatch:
                pass
            context['datos_tabla_comisiones'] = obtener_datos_tabla_resumen_comisiones()
            logger_rgv.debug("KPIs calculados.")

            # --- DATOS PARA GRÁFICOS DEL DASHBOARD ---
            logger_rgv.debug("Iniciando generación de gráficos...")
            # 1. Antigüedad Promedio por Estatus
            data_antiguedad_estatus_final = {}
            antiguedad_data = []
            for ci_val in ContratoIndividual.objects.filter(activo=True, fecha_inicio_vigencia__isnull=False, fecha_inicio_vigencia__lte=hoy).values('estatus', 'fecha_inicio_vigencia'):
                if ci_val['estatus'] and ci_val['fecha_inicio_vigencia']:
                    antiguedad_data.append({'estatus_code': ci_val['estatus'], 'antiguedad_dias': (
                        hoy - ci_val['fecha_inicio_vigencia']).days})
            for cc_val in ContratoColectivo.objects.filter(activo=True, fecha_inicio_vigencia__isnull=False, fecha_inicio_vigencia__lte=hoy).values('estatus', 'fecha_inicio_vigencia'):
                if cc_val['estatus'] and cc_val['fecha_inicio_vigencia']:
                    antiguedad_data.append({'estatus_code': cc_val['estatus'], 'antiguedad_dias': (
                        hoy - cc_val['fecha_inicio_vigencia']).days})
            if antiguedad_data:
                df_ant = pd.DataFrame(antiguedad_data)
                df_ant = df_ant[df_ant['antiguedad_dias'] >= 0]
                if not df_ant.empty:
                    df_ant_avg = df_ant.groupby('estatus_code')[
                        'antiguedad_dias'].mean().round(0)
                    data_antiguedad_estatus_final = {estatus_map_vigencia.get(
                        code, str(code)): float(avg) for code, avg in df_ant_avg.to_dict().items()}
            context['plotly_contratos_estado_html'] = generar_grafico_estados_contrato(
                data_antiguedad_estatus_final)

            # 2. Top Tipos Reclamación
            top_n_tipos_rec_dash = 5
            estados_pendientes_rec_dash = [
                'ABIERTA', 'EN_PROCESO', 'PENDIENTE_DOCS', 'EN_ANALISIS', 'INVESTIGACION']
            data_top_tipos_qs_dash = Reclamacion.objects.filter(estado__in=estados_pendientes_rec_dash, monto_reclamado__isnull=False, activo=True).values(
                'tipo_reclamacion').annotate(avg_monto=Avg('monto_reclamado')).filter(avg_monto__gt=Decimal('0.00')).order_by('-avg_monto')[:top_n_tipos_rec_dash]
            data_list_top_tipos_rec_dash = [(tipo_rec_map.get(item['tipo_reclamacion'], str(item['tipo_reclamacion'])), float(
                item['avg_monto'])) for item in data_top_tipos_qs_dash if item.get('avg_monto')]
            context['plotly_reclamaciones_estado_html'] = generar_grafico_estados_reclamacion(
                data_list_top_tipos_rec_dash)

            # 3. Mix Cartera (Usa la versión corregida)
            # Llama a la versión corregida
            context['plotly_ramos_monto_html'] = generar_grafico_total_primas_ramo_barras

            # 4. Resolución Recientes
            dias_atras_res_dash = 90
            fecha_limite_res_dash_date = hoy - \
                timedelta(days=dias_atras_res_dash)
            naive_datetime_limite_res = py_datetime.combine(
                fecha_limite_res_dash_date, py_datetime.min.time())
            aware_datetime_limite_res = django_timezone.make_aware(
                naive_datetime_limite_res)
            recs_recientes_qs_dash = Reclamacion.objects.filter(Q(fecha_reclamo__gte=fecha_limite_res_dash_date) | Q(
                fecha_modificacion__gte=aware_datetime_limite_res), activo=True)
            estados_resueltos_def_rec_dash = ['CERRADA', 'PAGADA', 'RECHAZADA']
            resueltas_rec_count_dash = recs_recientes_qs_dash.filter(
                estado__in=estados_resueltos_def_rec_dash).count()
            pendientes_rec_count_dash = recs_recientes_qs_dash.exclude(
                estado__in=estados_resueltos_def_rec_dash).count()
            data_para_res_recientes_dash = {
                'Resueltas': resueltas_rec_count_dash, 'Pendientes': pendientes_rec_count_dash}
            context['plotly_resolucion_gauge_html'] = generar_grafico_resolucion_gauge(
                data_para_res_recientes_dash)

            # --- 5. IGTF (KPI y Datos para Gráfico) ---
            logger_rgv.debug("Calculando datos para IGTF (KPI y Gráfico)...")
            total_igtf_calculado_para_kpi = Decimal('0.00')
            data_igtf_para_grafico_dict = collections.defaultdict(Decimal)
            TASA_IGTF_CALC = self.TASA_IGTF  # Tasa definida en la clase

            # Definir ramo_map aquí si no está definido antes en el método
            # Cache simple para evitar re-crear el dict
            if not hasattr(self, '_ramo_map_cache_rgv'):
                self._ramo_map_cache_rgv = dict(CommonChoices.RAMO)
            ramo_map = self._ramo_map_cache_rgv

            pagos_con_igtf_qs = Pago.objects.filter(
                activo=True,
                aplica_igtf_pago=True,
                monto_pago__gt=Decimal('0.00')
            ).select_related(
                'factura__contrato_individual',  # Traer el ContratoIndividual completo
                'factura__contrato_colectivo'  # Traer el ContratoColectivo completo
            )
            # OJO: Si ContratoIndividual o ContratoColectivo tienen FKs a 'ramo' como un modelo separado,
            # entonces sería 'factura__contrato_individual__ramo_modelo', etc.
            # Pero por tus modelos, 'ramo' es un CharField.

            for pago_obj in pagos_con_igtf_qs:
                if (Decimal('1') + TASA_IGTF_CALC) == 0:
                    logger_rgv.error(
                        f"TASA_IGTF_CALC es -1, lo que causa división por cero. Pago PK: {pago_obj.pk}")
                    continue

                monto_base_para_igtf = pago_obj.monto_pago / \
                    (Decimal('1') + TASA_IGTF_CALC)
                igtf_del_pago = (
                    monto_base_para_igtf * TASA_IGTF_CALC).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                total_igtf_calculado_para_kpi += igtf_del_pago

                categoria_igtf = "Otros Pagos IGTF"
                if pago_obj.factura:
                    factura_asociada = pago_obj.factura
                    contrato_asociado = factura_asociada.contrato_individual or factura_asociada.contrato_colectivo
                    # Acceder al atributo 'ramo'
                    if contrato_asociado and hasattr(contrato_asociado, 'ramo') and contrato_asociado.ramo:
                        categoria_igtf = f"Ramo: {ramo_map.get(contrato_asociado.ramo, str(contrato_asociado.ramo))}"
                    elif factura_asociada.contrato_individual:
                        categoria_igtf = "Cont. Individual"
                    elif factura_asociada.contrato_colectivo:
                        categoria_igtf = "Cont. Colectivo"

                data_igtf_para_grafico_dict[categoria_igtf] += igtf_del_pago

            context['kpi_total_igtf_recaudado'] = total_igtf_calculado_para_kpi.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            logger_rgv.debug(
                f"KPI Total IGTF Recaudado asignado: {context['kpi_total_igtf_recaudado']}")

            data_igtf_para_dona_plotly = {'Categoria': [], 'IGTF': []}
            for categoria, valor_igtf in data_igtf_para_grafico_dict.items():
                if valor_igtf > 0:
                    data_igtf_para_dona_plotly['Categoria'].append(categoria)
                    data_igtf_para_dona_plotly['IGTF'].append(
                        float(valor_igtf))

            context['plotly_impuestos_categoria_html'] = generar_grafico_impuestos_por_categoria(
                data_igtf_para_dona_plotly
            )
            logger_rgv.debug(
                "Datos para gráfico IGTF por categoría preparados y gráfico generado.")
            # --- FIN Bloque IGTF ---
            # 6. Cartera Intermediarios Bubble
            top_n_inter_bubble_dash = 10
            siniestros_ind_sub_dash = Subquery(Reclamacion.objects.filter(contrato_individual__intermediario_id=OuterRef('pk'), activo=True, contrato_individual__activo=True).values(
                'contrato_individual__intermediario_id').annotate(total_siniestro=Coalesce(Sum('monto_reclamado'), Value(Decimal('0.0')))).values('total_siniestro')[:1], output_field=DecimalField(decimal_places=2))
            siniestros_col_sub_dash = Subquery(Reclamacion.objects.filter(contrato_colectivo__intermediario_id=OuterRef('pk'), activo=True, contrato_colectivo__activo=True).values(
                'contrato_colectivo__intermediario_id').annotate(total_siniestro=Coalesce(Sum('monto_reclamado'), Value(Decimal('0.0')))).values('total_siniestro')[:1], output_field=DecimalField(decimal_places=2))
            data_inter_bubble_qs_dash = (Intermediario.objects.filter(activo=True).annotate(pi=Coalesce(Sum('contratoindividual__monto_total', filter=Q(contratoindividual__activo=True)), Value(Decimal('0.0'))), pc=Coalesce(Sum('contratos_colectivos__monto_total', filter=Q(contratos_colectivos__activo=True)), Value(Decimal('0.0'))), si=Coalesce(siniestros_ind_sub_dash, Value(Decimal('0.0'))), sc=Coalesce(siniestros_col_sub_dash, Value(Decimal('0.0'))), n_ci=Count('contratoindividual', filter=Q(contratoindividual__activo=True), distinct=True), n_cc=Count('contratos_colectivos', filter=Q(contratos_colectivos__activo=True), distinct=True)).annotate(pt=ExpressionWrapper(
                F('pi') + F('pc'), output_field=DecimalField(decimal_places=2)), st=ExpressionWrapper(F('si') + F('sc'), output_field=DecimalField(decimal_places=2)), ce=Case(When(Q(porcentaje_comision__isnull=False) & Q(pt__gt=Decimal('0.0')), then=ExpressionWrapper(F('pt') * F('porcentaje_comision') / Decimal('100.0'), output_field=DecimalField(decimal_places=2))), default=Value(Decimal('0.0')), output_field=DecimalField(decimal_places=2)), n_ct=F('n_ci') + F('n_cc')).annotate(rn=ExpressionWrapper(F('pt') - F('st') - F('ce'), output_field=DecimalField(decimal_places=2))).filter(Q(pt__gt=Decimal('0.005')) & Q(n_ct__gt=0)).order_by('-pt')[:top_n_inter_bubble_dash])
            data_list_bubble_dash = [{'nombre_intermediario': inter.nombre_completo, 'prima_total': float(inter.pt), 'rentabilidad_neta': float(inter.rn), 'numero_contratos': int(
                inter.n_ct), 'siniestros_totales': float(inter.st), 'comisiones_estimadas': float(inter.ce)} for inter in data_inter_bubble_qs_dash]
            context['plotly_rentabilidad_intermediario_html'] = generar_grafico_rentabilidad_neta_intermediario(
                data_list_bubble_dash)

            logger_rgv.debug("ReporteGeneralView: Fin generación de gráficos.")

            # --- Cálculo de Tablas ---
            logger_rgv.debug(
                "ReporteGeneralView: Calculando datos para tablas...")
            context['table_top_tipos_reclamacion'] = [{'tipo': tipo_rec_map.get(i['tipo_reclamacion'], str(i['tipo_reclamacion'])), 'cantidad': i['cantidad']} for i in Reclamacion.objects.filter(
                activo=True).values('tipo_reclamacion').annotate(cantidad=Count('id')).filter(cantidad__gt=0).order_by('-cantidad')[:10]]
            context['table_facturas_antiguas'] = Factura.objects.filter(activo=True, pagada=False, monto_pendiente__gt=Decimal('0.01'), vigencia_recibo_hasta__lt=hoy).select_related(
                'contrato_individual__afiliado', 'contrato_colectivo__intermediario').annotate(dias_vencida=ExpressionWrapper(Value(hoy) - F('vigencia_recibo_hasta'), output_field=DurationField())).order_by('vigencia_recibo_hasta')[:10]
            context['table_top_intermediarios'] = Intermediario.objects.filter(activo=True).annotate(num_contratos=(Count('contratoindividual', filter=Q(contratoindividual__activo=True), distinct=True) + Count('contratos_colectivos', filter=Q(contratos_colectivos__activo=True), distinct=True)), monto_contratos=(
                Coalesce(Sum('contratoindividual__monto_total', filter=Q(contratoindividual__activo=True)), Value(Decimal('0.0'))) + Coalesce(Sum('contratos_colectivos__monto_total', filter=Q(contratos_colectivos__activo=True)), Value(Decimal('0.0'))))).filter(num_contratos__gt=0).order_by('-monto_contratos')[:10]
            logger_rgv.debug(
                "ReporteGeneralView: Datos para tablas calculados.")

        except Exception as e_main:
            logger_rgv.error(
                f"Error CRÍTICO generando datos para ReporteGeneralView: {e_main}", exc_info=True)
            context[
                'error'] = f"Ocurrió un error grave al calcular los datos del reporte: {escape(str(e_main))}"
            for g_ctx_name in graficas_context_names:  # Resetear gráficos a "error"
                context[g_ctx_name] = generar_figura_sin_datos_plotly(
                    f"Error al cargar datos ({g_ctx_name.replace('plotly_', '').replace('_html', '')}).")

        return context


# Diccionario modelos_busqueda (sin cambios)
modelos_busqueda = {
    'usuario': {'nombre': ('Usuario'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('email', 'Correo Electrónico'), ('tipo_usuario', 'Tipo Usuario'), ('fecha_nacimiento', 'Fecha Nacimiento'), ('departamento', 'Departamento'), ('telefono', 'Teléfono'), ('direccion', 'Dirección'), ('intermediario', 'Intermediario'), ('nivel_acceso', 'Nivel Acceso'), ('username', 'Nombre de Usuario'), ('is_staff', 'Es Staff'), ('is_active', 'Está Activo'), ('is_superuser', 'Es Superusuario'), ('last_login', 'Último Login'), ('date_joined', 'Fecha de Registro')]},
    'contratoindividual': {'nombre': ('Contrato Individual'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('fecha_creacion', 'Fecha de Creación'), ('fecha_modificacion', 'Fecha de modificación'), ('ramo', 'Ramo'), ('forma_pago', 'Forma de Pago'), ('pagos_realizados', 'Pagos Realizados'), ('estatus', 'Estatus'), ('estado_contrato', 'Estado Contrato'), ('numero_contrato', 'Número de Contrato'), ('numero_poliza', 'Número de Póliza'), ('fecha_emision', 'Fecha de Emisión del Contrato'), ('fecha_inicio_vigencia', 'Fecha de Inicio de Vigencia'), ('fecha_fin_vigencia', 'Fecha de Fin de Vigencia'), ('monto_total', 'Monto Total del Contrato'), ('intermediario', 'Intermediario'), ('consultar_afiliados_activos', 'Consultar en data de afiliados activos'), ('tipo_identificacion_contratante', 'Tipo de Identificación del Contratante'), ('contratante_cedula', 'Cédula del Contratante'), ('contratante_nombre', 'Nombre del Contratante'), ('direccion_contratante', 'Dirección del Contratante'), ('telefono_contratante', 'Teléfono del Contratante'), ('email_contratante', 'Email del Contratante'), ('cantidad_cuotas', 'Cantidad de Cuotas'), ('afiliado', 'Afiliado'), ('plan_contratado', 'Plan Contratado'), ('comision_recibo', 'Comisión Recibo'), ('certificado', 'Certificado'), ('importe_anual_contrato', 'Importe Anual del Contrato'), ('importe_recibo_contrato', 'Importe Recibo del Contrato'), ('fecha_inicio_vigencia_recibo', 'Fecha Inicio Vigencia Recibo'), ('fecha_fin_vigencia_recibo', 'Fecha Fin Vigencia Recibo'), ('criterio_busqueda', 'Criterio de Búsqueda'), ('dias_transcurridos_ingreso', 'Días Transcurridos Ingreso'), ('estatus_detalle', 'Estatus Detalle'), ('estatus_emision_recibo', 'Estatus Emisión Recibo'), ('comision_anual', 'Comisión Anual')]},
    'afiliadoindividual': {'nombre': ('Afiliado Individual'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('tipo_identificacion', 'Tipo de Identificación'), ('cedula', 'Cédula'), ('estado_civil', 'Estado Civil'), ('sexo', 'Sexo'), ('parentesco', 'Parentesco'), ('fecha_nacimiento', 'Fecha Nacimiento'), ('nacionalidad', 'Nacionalidad'), ('zona_postal', 'Zona Postal'), ('estado', 'Estado'), ('municipio', 'Municipio'), ('ciudad', 'Ciudad'), ('fecha_ingreso', 'Fecha Ingreso'), ('direccion_habitacion', 'Dirección Habitación'), ('telefono_habitacion', 'Teléfono Habitación'), ('direccion_oficina', 'Dirección Oficina'), ('telefono_oficina', 'Teléfono Oficina'), ('codigo_validacion', 'Código de Validación'), ('activo', 'Estado activo')]},
    'afiliadocolectivo': {'nombre': ('Afiliado Colectivo'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('activo', 'Activo'), ('razon_social', 'Razón Social'), ('rif', 'RIF'), ('tipo_empresa', 'Tipo Empresa'), ('direccion_comercial', 'Dirección Fiscal'), ('estado', 'Estado'), ('municipio', 'Municipio'), ('ciudad', 'Ciudad'), ('zona_postal', 'Zona Postal'), ('telefono_contacto', 'Teléfono Contacto'), ('email_contacto', 'Email Contacto')]},
    'contratocolectivo': {'nombre': ('Contrato Colectivo'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('tipo_empresa', 'Tipo Empresa'), ('criterio_busqueda', 'Criterio de Búsqueda'), ('razon_social', 'Razón Social'), ('rif', 'RIF'), ('cantidad_empleados', 'Cantidad Empleados'), ('direccion_comercial', 'Dirección Comercial'), ('zona_postal', 'Zona Postal'), ('numero_recibo', 'Número Recibo'), ('comision_recibo', 'Comisión Recibo'), ('estado', 'Estado'), ('codigo_validacion', 'Código de Validación')]},
    'intermediario': {'nombre': ('Intermediario'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('codigo', 'Código'), ('nombre_completo', 'Nombre Completo'), ('rif', 'RIF'), ('direccion_fiscal', 'Dirección Fiscal'), ('telefono_contacto', 'Teléfono Contacto'), ('email_contacto', 'Email Contacto'), ('intermediario_relacionado', 'Intermediario Relacionado'), ('porcentaje_comision', 'Porcentaje Comisión')]},
    'factura': {'nombre': ('Factura'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('estatus_factura', 'Estatus Factura'), ('contrato_individual', 'Contrato Individual'), ('contrato_colectivo', 'Contrato Colectivo'), ('ramo', 'Ramo'), ('vigencia_recibo_desde', 'Vigencia Recibo Desde'), ('vigencia_recibo_hasta', 'Vigencia Recibo Hasta'), ('observaciones', 'Observaciones de la Factura')]},
    'reclamacion': {'nombre': ('Reclamación'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('tipo_reclamacion', 'Tipo Reclamación'), ('estado', 'Estado'), ('descripcion_reclamo', 'Descripción Reclamo'), ('monto_reclamado', 'Monto Reclamado'), ('contrato_individual', 'Contrato Individual'), ('contrato_colectivo', 'Contrato Colectivo'), ('fecha_reclamo', 'Fecha Reclamo'), ('usuario_asignado', 'Usuario Asignado'), ('observaciones_internas', 'Observaciones Internas'), ('observaciones_cliente', 'Observaciones Cliente')]},
    'pago': {'nombre': ('Pago'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('forma_pago', 'Forma de Pago'), ('reclamacion', 'Reclamación'), ('fecha_pago', 'Fecha Pago'), ('monto_pago', 'Monto Pago'), ('referencia_pago', 'Referencia Pago'), ('fecha_notificacion_pago', 'Fecha Notificación Pago'), ('observaciones_pago', 'Observaciones Pago'), ('factura', 'Factura')]},
    'tarifa': {'nombre': ('Tarifa'), 'campos': [('id', 'ID'), ('primer_nombre', 'Primer Nombre'), ('segundo_nombre', 'Segundo Nombre'), ('primer_apellido', 'Primer Apellido'), ('segundo_apellido', 'Segundo Apellido'), ('rango_etario', 'Rango Etario'), ('ramo', 'Ramo'), ('fecha_aplicacion', 'Fecha Aplicación'), ('monto_anual', 'Monto Anual'), ('tipo_fraccionamiento', 'Tipo Fraccionamiento'), ('comision_intermediario', 'Comisión Intermediario')]},
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
            field_instance = ModelClass._meta.get_field(campo.split('__')[0])
        except FieldDoesNotExist:
            return [], f"Campo '{campo}' no es válido para buscar en {ModelClass._meta.verbose_name}."

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
    "13": "Distribución por Edad y Ramo (Conteo)", "14": "Estado de Continuidad de Contratos del Último Mes Completo",
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
            # --- AJUSTADO fields: Quitado monto_total, añadido tarifa_aplicada y calculados si relevantes para home ---
            'fields': ['numero_contrato', 'afiliado', 'fecha_inicio_vigencia', 'estatus', 'tarifa_aplicada', 'importe_recibo_contrato'],
            'search_fields': ['numero_contrato', 'contratante_nombre', 'afiliado__cedula', 'afiliado__primer_nombre', 'afiliado__primer_apellido'],
            'verbose_name': 'Contrato Individual', 'verbose_name_plural': 'Contratos Individuales',
            # Añadido tarifa
            'related_fields': ['intermediario', 'afiliado', 'tarifa_aplicada'],
            'permissions': {'list': 'myapp.view_contratoindividual', 'create': 'myapp.add_contratoindividual', 'change': 'myapp.change_contratoindividual', 'delete': 'myapp.delete_contratoindividual', }
        },  'afiliado_individual': {'model': AfiliadoIndividual, 'list_view': 'myapp:afiliado_individual_list', 'create_view': 'myapp:afiliado_individual_create', 'detail_view': 'myapp:afiliado_individual_detail', 'update_view': 'myapp:afiliado_individual_update', 'delete_view': 'myapp:afiliado_individual_delete', 'fields': ['cedula', 'primer_nombre', 'primer_apellido', 'fecha_nacimiento', 'activo'], 'search_fields': ['cedula', 'primer_nombre', 'primer_apellido'], 'verbose_name': 'Afiliado Individual', 'verbose_name_plural': 'Afiliados Individuales', 'related_fields': [], 'permissions': {'list': 'myapp.view_afiliadoindividual', 'create': 'myapp.add_afiliadoindividual', 'change': 'myapp.change_afiliadoindividual', 'delete': 'myapp.delete_afiliadoindividual', }},
        'auditoria_sistema': {'model': AuditoriaSistema, 'list_view': 'myapp:auditoria_sistema_list', 'create_view': 'myapp:auditoria_sistema_create', 'detail_view': 'myapp:auditoria_sistema_detail', 'update_view': 'myapp:auditoria_sistema_update', 'delete_view': 'myapp:auditoria_sistema_delete', 'fields': ['usuario', 'tipo_accion', 'tiempo_inicio', 'tabla_afectada', 'resultado_accion'], 'search_fields': ['usuario__username', 'tipo_accion', 'tabla_afectada', 'detalle_accion', 'direccion_ip'], 'verbose_name': 'Auditoría de Sistema', 'verbose_name_plural': 'Auditorías de Sistema', 'related_fields': ['usuario'], 'permissions': {'list': 'myapp.view_auditoriasistema', 'create': 'myapp.add_auditoriasistema', 'change': 'myapp.change_auditoriasistema', 'delete': 'myapp.delete_auditoriasistema', }},
        'afiliado_colectivo': {'model': AfiliadoColectivo, 'list_view': 'myapp:afiliado_colectivo_list', 'create_view': 'myapp:afiliado_colectivo_create', 'detail_view': 'myapp:afiliado_colectivo_detail', 'update_view': 'myapp:afiliado_colectivo_update', 'delete_view': 'myapp:afiliado_colectivo_delete', 'fields': ['rif', 'razon_social', 'email_contacto', 'activo'], 'search_fields': ['rif', 'razon_social', 'email_contacto'], 'verbose_name': 'Afiliado Colectivo', 'verbose_name_plural': 'Afiliados Colectivos', 'related_fields': [], 'permissions': {'list': 'myapp.view_afiliadocolectivo', 'create': 'myapp.add_afiliadocolectivo', 'change': 'myapp.change_afiliadocolectivo', 'delete': 'myapp.delete_afiliadocolectivo', }},
        'contrato_colectivo': {
            'model': ContratoColectivo, 'list_view': 'myapp:contrato_colectivo_list', 'create_view': 'myapp:contrato_colectivo_create',
            'detail_view': 'myapp:contrato_colectivo_detail', 'update_view': 'myapp:contrato_colectivo_update', 'delete_view': 'myapp:contrato_colectivo_delete',
            # --- AJUSTADO fields: Quitado monto_total, añadido tarifa_aplicada y calculados si relevantes ---
            'fields': ['numero_contrato', 'razon_social', 'fecha_inicio_vigencia', 'estatus', 'tarifa_aplicada', 'importe_recibo_contrato'],
            'search_fields': ['numero_contrato', 'razon_social', 'rif'],
            'verbose_name': 'Contrato Colectivo', 'verbose_name_plural': 'Contratos Colectivos',
            # Añadido tarifa
            'related_fields': ['intermediario', 'tarifa_aplicada'],
            'permissions': {'list': 'myapp.view_contratocolectivo', 'create': 'myapp.add_contratocolectivo', 'change': 'myapp.change_contratocolectivo', 'delete': 'myapp.delete_contratocolectivo', }
        },
        'intermediario': {'model': Intermediario, 'list_view': 'myapp:intermediario_list', 'create_view': 'myapp:intermediario_create', 'detail_view': 'myapp:intermediario_detail', 'update_view': 'myapp:intermediario_update', 'delete_view': 'myapp:intermediario_delete', 'fields': ['codigo', 'nombre_completo', 'rif', 'porcentaje_comision', 'activo'], 'search_fields': ['codigo', 'nombre_completo', 'rif', 'email_contacto'], 'verbose_name': 'Intermediario', 'verbose_name_plural': 'Intermediarios', 'related_fields': [], 'permissions': {'list': 'myapp.view_intermediario', 'create': 'myapp.add_intermediario', 'change': 'myapp.change_intermediario', 'delete': 'myapp.delete_intermediario', }},
        'factura': {'model': Factura, 'list_view': 'myapp:factura_list', 'create_view': 'myapp:factura_create', 'detail_view': 'myapp:factura_detail', 'update_view': 'myapp:factura_update', 'delete_view': 'myapp:factura_delete', 'fields': ['numero_recibo', 'monto', 'vigencia_recibo_desde', 'vigencia_recibo_hasta', 'pagada'], 'search_fields': ['numero_recibo', 'contrato_individual__numero_contrato', 'contrato_colectivo__numero_contrato', 'relacion_ingreso'], 'verbose_name': 'Factura', 'verbose_name_plural': 'Facturas', 'related_fields': ['contrato_individual', 'contrato_colectivo', 'intermediario'], 'permissions': {'list': 'myapp.view_factura', 'create': 'myapp.add_factura', 'change': 'myapp.change_factura', 'delete': 'myapp.delete_factura', }},
        'pago': {'model': Pago, 'list_view': 'myapp:pago_list', 'create_view': 'myapp:pago_create', 'detail_view': 'myapp:pago_detail', 'update_view': 'myapp:pago_update', 'delete_view': 'myapp:pago_delete', 'fields': ['id', 'factura', 'fecha_pago', 'monto_pago', 'forma_pago'], 'search_fields': ['referencia_pago', 'reclamacion__id', 'factura__numero_recibo'], 'verbose_name': 'Pago', 'verbose_name_plural': 'Pagos', 'related_fields': ['reclamacion', 'factura'], 'permissions': {'list': 'myapp.view_pago', 'create': 'myapp.add_pago', 'change': 'myapp.change_pago', 'delete': 'myapp.delete_pago', }},
        'tarifa': {'model': Tarifa, 'list_view': 'myapp:tarifa_list', 'create_view': 'myapp:tarifa_create', 'detail_view': 'myapp:tarifa_detail', 'update_view': 'myapp:tarifa_update', 'delete_view': 'myapp:tarifa_delete', 'fields': ['ramo', 'rango_etario', 'fecha_aplicacion', 'monto_anual', 'activo'], 'search_fields': ['ramo', 'rango_etario'], 'verbose_name': 'Tarifa', 'verbose_name_plural': 'Tarifas', 'related_fields': [], 'permissions': {'list': 'myapp.view_tarifa', 'create': 'myapp.add_tarifa', 'change': 'myapp.change_tarifa', 'delete': 'myapp.delete_tarifa', }},
        'reclamacion': {'model': Reclamacion, 'list_view': 'myapp:reclamacion_list', 'create_view': 'myapp:reclamacion_create', 'detail_view': 'myapp:reclamacion_detail', 'update_view': 'myapp:reclamacion_update', 'delete_view': 'myapp:reclamacion_delete', 'fields': ['id', 'tipo_reclamacion', 'estado', 'fecha_reclamo', 'monto_reclamado'], 'search_fields': ['id', 'descripcion_reclamo', 'tipo_reclamacion', 'estado', 'contrato_individual__numero_contrato', 'contrato_colectivo__numero_contrato'], 'verbose_name': 'Reclamación', 'verbose_name_plural': 'Reclamaciones', 'related_fields': ['contrato_individual', 'contrato_colectivo', 'usuario_asignado'], 'permissions': {'list': 'myapp.view_reclamacion', 'create': 'myapp.add_reclamacion', 'change': 'myapp.change_reclamacion', 'delete': 'myapp.delete_reclamacion', }},
        'usuario': {'model': Usuario, 'list_view': 'myapp:usuario_list', 'create_view': 'myapp:usuario_create', 'detail_view': 'myapp:usuario_detail', 'update_view': 'myapp:usuario_update', 'delete_view': 'myapp:usuario_delete', 'fields': ['username', 'primer_nombre', 'primer_apellido', 'email', 'tipo_usuario', 'is_active'], 'search_fields': ['username', 'primer_nombre', 'primer_apellido', 'email', 'intermediario__nombre_completo'], 'verbose_name': 'Usuario', 'verbose_name_plural': 'Usuarios', 'related_fields': ['intermediario'], 'permissions': {'list': 'myapp.view_usuario', 'create': 'myapp.add_usuario', 'change': 'myapp.change_usuario', 'delete': 'myapp.delete_usuario', }}
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
    """
    Genera un PDF para una Factura específica.
    Asume que la plantilla se llama 'factura_pdf.html' y está en un directorio de plantillas raíz.
    """
    permission_required = 'myapp.view_factura'
    template_name = 'factura_pdf.html'  # <--- Nombre directo del template

    def link_callback(self, uri, rel):
        """
        Convierte URIs de HTML a rutas absolutas del sistema para xhtml2pdf.
        Busca en STATICFILES_DIRS, STATIC_ROOT y MEDIA_ROOT.
        """
        # Intenta resolver usando el buscador de estáticos de Django (más robusto)
        result = finders.find(uri)
        if result:
            if not isinstance(result, (list, tuple)):
                result = [result]
            # Tomar la primera ruta válida que sea un archivo
            for path_candidate in result:
                path = os.path.realpath(path_candidate)
                if os.path.isfile(path):
                    logger.debug(
                        f"link_callback: URI '{uri}' resuelta a '{path}' vía finders.")
                    return path
            logger.warning(
                f"link_callback: Recurso encontrado por finders para URI '{uri}' pero ninguna ruta es un archivo válido: {result}")

        # Fallback: intentar construir ruta desde STATIC_URL/ROOT
        if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
            # Probar en STATIC_ROOT
            path = os.path.join(settings.STATIC_ROOT,
                                uri.replace(settings.STATIC_URL, "", 1))
            if os.path.isfile(path):
                logger.debug(
                    f"link_callback: URI '{uri}' resuelta a '{path}' vía STATIC_ROOT.")
                return path
            # Probar en STATICFILES_DIRS
            for static_dir in settings.STATICFILES_DIRS:
                path_in_dir = os.path.join(
                    static_dir, uri.replace(settings.STATIC_URL, "", 1))
                if os.path.isfile(path_in_dir):
                    logger.debug(
                        f"link_callback: URI '{uri}' resuelta a '{path_in_dir}' vía STATICFILES_DIRS.")
                    return path_in_dir

        # Fallback para MEDIA_URL/ROOT
        if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT,
                                uri.replace(settings.MEDIA_URL, "", 1))
            if os.path.isfile(path):
                logger.debug(
                    f"link_callback: URI '{uri}' resuelta a '{path}' vía MEDIA_ROOT.")
                return path

        logger.warning(
            f"link_callback: URI no resuelta a ruta de archivo: '{uri}'")
        return uri  # Devolver URI original si no se resuelve

    def _get_client_ip(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        return ip.split(',')[0].strip() if ip else request.META.get('REMOTE_ADDR', '')

    def _create_audit_log(self, request, resultado, pk, detalle):
        try:
            AuditoriaSistema.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                tipo_accion='GENERACION_PDF',
                tabla_afectada=Factura._meta.db_table,
                registro_id_afectado=pk,
                detalle_accion=f"Factura PDF {pk}: {detalle}",
                direccion_ip=self._get_client_ip(request),
                agente_usuario=request.META.get('HTTP_USER_AGENT', '')[:500],
                resultado_accion=resultado
            )
        except Exception as audit_e:
            logger.error(
                f"Error auditoría PDF factura {pk}: {audit_e}", exc_info=True)

    def get(self, request, pk, *args, **kwargs):
        try:
            # Obtener la factura con relaciones optimizadas
            factura = get_object_or_404(
                Factura.objects.select_related(
                    'contrato_individual__afiliado',  # Para nombre y CI
                    'contrato_colectivo',            # Para razón social y RIF
                    'intermediario'                  # Para datos del intermediario
                ),
                pk=pk
            )

            # Verificar permisos adicionales si es necesario (ej. solo ver propias facturas?)
            # if not request.user.is_superuser and factura.propietario != request.user:
            #     raise PermissionDenied

            # --- Preparar contexto para el template PDF ---
            monto_prima = factura.monto or Decimal('0.00')
            total_a_pagar = monto_prima  # Asumiendo exento de IVA/IGTF para el PDF de factura

            context = {
                'factura': factura,
                'contrato_asociado': factura.contrato_individual or factura.contrato_colectivo,
                'monto_prima': monto_prima,
                'total_a_pagar': total_a_pagar,
                'cliente_nombre': "(No identificado)",
                'cliente_doc': "N/A",
                'intermediario_factura': factura.intermediario  # Pasar objeto completo
            }

            # Obtener datos del cliente final
            if factura.contrato_individual and factura.contrato_individual.afiliado:
                afiliado = factura.contrato_individual.afiliado
                context['cliente_nombre'] = afiliado.get_full_name() if hasattr(
                    afiliado, 'get_full_name') else f"{afiliado.primer_nombre} {afiliado.primer_apellido}".strip()
                context['cliente_doc'] = f"C.I.: {afiliado.cedula}" if hasattr(
                    afiliado, 'cedula') else "C.I. N/A"
            elif factura.contrato_colectivo:
                colectivo = factura.contrato_colectivo
                context['cliente_nombre'] = colectivo.razon_social if hasattr(
                    colectivo, 'razon_social') else "(Colectivo)"
                context['cliente_doc'] = f"RIF: {colectivo.rif}" if hasattr(
                    colectivo, 'rif') and colectivo.rif else "RIF N/A"

            # --- Renderizar HTML ---
            try:
                template = get_template(self.template_name)
                html = template.render(context)
                if not isinstance(html, str):
                    raise TypeError(
                        "El renderizado del template no devolvió un string.")
            except Exception as render_error:
                logger.error(
                    f"Error renderizando template PDF para factura {pk}: {render_error}", exc_info=True)
                self._create_audit_log(
                    request, 'ERROR', pk, f"Error render template: {render_error}")
                return HttpResponseServerError("Error interno generando contenido del PDF.")

            # --- Generar PDF ---
            result = BytesIO()
            pdf_status = pisa.pisaDocument(
                BytesIO(html.encode('UTF-8')),  # Codificar HTML a bytes
                result,
                encoding='UTF-8',
                link_callback=self.link_callback  # Usar el método de la instancia
            )

            if pdf_status.err:
                error_detail = f"xhtml2pdf error: {pdf_status.err}"
                logger.error(
                    f"Error generando PDF para factura {pk}: {error_detail}")
                self._create_audit_log(request, 'ERROR', pk, error_detail)
                return HttpResponse(f"Error al generar el PDF ({pdf_status.err}). Por favor, contacte soporte.", status=500)

            # --- Respuesta HTTP con el PDF ---
            response = HttpResponse(
                result.getvalue(), content_type='application/pdf')
            filename = f"factura_{factura.numero_recibo or factura.pk}.pdf"
            # 'inline' para ver en navegador, 'attachment' para descargar
            response['Content-Disposition'] = f'inline; filename="{filename}"'

            # --- Auditoría Éxito ---
            self._create_audit_log(request, 'EXITO', pk,
                                   "PDF generado/visualizado")

            return response

        except Http404:
            logger.warning(
                f"Intento de acceso a PDF de Factura inexistente: PK={pk}")
            raise  # Dejar que Django maneje el 404 estándar
        except PermissionDenied as e:
            logger.warning(
                f"Acceso denegado a PDF Factura PK={pk} por usuario {request.user.email}: {e}")
            # Podrías redirigir a una página de 'acceso denegado' o mostrar un mensaje
            messages.error(
                request, "No tiene permiso para ver este documento.")
            return redirect('myapp:home')  # O a donde sea apropiado
        except Exception as e:
            logger.error(
                f"Error inesperado en FacturaPdfView (pk={pk}): {e}", exc_info=True)
            self._create_audit_log(request, 'ERROR', pk,
                                   f"Error inesperado: {e}")
            # Devolver un error 500 genérico al usuario
            return HttpResponseServerError("Ocurrió un error inesperado al intentar generar el documento PDF.")


class PagoPdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Genera un PDF para un Recibo de Pago específico.
    Asume que la plantilla se llama 'pago_pdf.html' y está en un directorio de plantillas raíz.
    """
    permission_required = 'myapp.view_pago'  # Permiso para ver pagos
    template_name = 'pago_pdf.html'     # Nombre directo del template
    TASA_IGTF_PAGO = Decimal('0.03')    # Tasa IGTF (podría venir de settings)

    def link_callback(self, uri, rel):
        """
        Convierte URIs de HTML a rutas absolutas del sistema para xhtml2pdf.
        (Misma lógica que en FacturaPdfView)
        """
        result = finders.find(uri)
        if result:
            if not isinstance(result, (list, tuple)):
                result = [result]
            for path_candidate in result:
                path = os.path.realpath(path_candidate)
                if os.path.isfile(path):
                    logger.debug(
                        f"link_callback: URI '{uri}' resuelta a '{path}' vía finders.")
                    return path
            logger.warning(
                f"link_callback: Recurso encontrado por finders para URI '{uri}' pero ninguna ruta es un archivo válido: {result}")

        if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
            path = os.path.join(settings.STATIC_ROOT,
                                uri.replace(settings.STATIC_URL, "", 1))
            if os.path.isfile(path):
                logger.debug(
                    f"link_callback: URI '{uri}' resuelta a '{path}' vía STATIC_ROOT.")
                return path
            for static_dir in settings.STATICFILES_DIRS:
                path_in_dir = os.path.join(
                    static_dir, uri.replace(settings.STATIC_URL, "", 1))
                if os.path.isfile(path_in_dir):
                    logger.debug(
                        f"link_callback: URI '{uri}' resuelta a '{path_in_dir}' vía STATICFILES_DIRS.")
                    return path_in_dir

        if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT,
                                uri.replace(settings.MEDIA_URL, "", 1))
            if os.path.isfile(path):
                logger.debug(
                    f"link_callback: URI '{uri}' resuelta a '{path}' vía MEDIA_ROOT.")
                return path

        logger.warning(
            f"link_callback: URI no resuelta a ruta de archivo: '{uri}'")
        return uri

    def _get_client_ip(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        return ip.split(',')[0].strip() if ip else request.META.get('REMOTE_ADDR', '')

    def _create_audit_log(self, request, resultado, pk, detalle):
        try:
            AuditoriaSistema.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                tipo_accion='GENERACION_PDF',
                tabla_afectada=Pago._meta.db_table,
                registro_id_afectado=pk,
                detalle_accion=f"Pago PDF {pk}: {detalle}",
                direccion_ip=self._get_client_ip(request),
                agente_usuario=request.META.get('HTTP_USER_AGENT', '')[:500],
                resultado_accion=resultado
            )
        except Exception as audit_e:
            logger.error(
                f"Error auditoría PDF pago {pk}: {audit_e}", exc_info=True)

    def get(self, request, pk, *args, **kwargs):
        try:
            # Obtener el pago con relaciones optimizadas para obtener datos del cliente
            pago = get_object_or_404(
                Pago.objects.select_related(
                    'factura__contrato_individual__afiliado',
                    'factura__contrato_colectivo',
                    'reclamacion__contrato_individual__afiliado',
                    'reclamacion__contrato_colectivo'
                ),
                pk=pk
            )

            # Verificar permisos adicionales si es necesario
            # (ej. solo ver pagos relacionados con contratos/reclamaciones que el usuario puede ver)
            # ...

            # --- Preparar contexto para el template PDF ---
            monto_igtf_percibido = Decimal('0.00')
            monto_total_recibido = pago.monto_pago or Decimal(
                '0.00')  # Monto total que se pagó
            monto_abonado_neto = monto_total_recibido  # Por defecto, todo abona

            if pago.aplica_igtf_pago and monto_total_recibido > 0:
                # Calcular IGTF sobre el monto total recibido
                monto_igtf_percibido = (monto_total_recibido * self.TASA_IGTF_PAGO).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                # Lo que realmente abona a la deuda es el total menos el IGTF
                monto_abonado_neto = monto_total_recibido - monto_igtf_percibido

            # --- Obtener info del cliente (lógica similar a PagoDetailView) ---
            cliente_nombre = "No identificado"
            cliente_doc = "N/A"
            contrato_ref = None  # Para referencia en el PDF

            if pago.factura:
                contrato_ref = pago.factura.contrato_individual or pago.factura.contrato_colectivo
                if pago.factura.contrato_individual and pago.factura.contrato_individual.afiliado:
                    afiliado = pago.factura.contrato_individual.afiliado
                    cliente_nombre = afiliado.get_full_name()
                    cliente_doc = f"C.I.: {afiliado.cedula}"
                elif pago.factura.contrato_colectivo:
                    colectivo = pago.factura.contrato_colectivo
                    cliente_nombre = colectivo.razon_social
                    cliente_doc = f"RIF: {colectivo.rif}"
            elif pago.reclamacion:
                contrato_ref = pago.reclamacion.contrato_individual or pago.reclamacion.contrato_colectivo
                if pago.reclamacion.contrato_individual and pago.reclamacion.contrato_individual.afiliado:
                    afiliado = pago.reclamacion.contrato_individual.afiliado
                    cliente_nombre = afiliado.get_full_name()
                    cliente_doc = f"C.I.: {afiliado.cedula}"
                elif pago.reclamacion.contrato_colectivo:
                    colectivo = pago.reclamacion.contrato_colectivo
                    cliente_nombre = colectivo.razon_social
                    cliente_doc = f"RIF: {colectivo.rif}"

            context = {
                'pago': pago,
                'factura_asociada': pago.factura,
                'reclamacion_asociada': pago.reclamacion,
                'contrato_ref': contrato_ref,  # Pasar referencia del contrato
                'cliente_nombre': cliente_nombre,
                'cliente_doc': cliente_doc,
                'pago_con_igtf': pago.aplica_igtf_pago,
                'monto_igtf_percibido': monto_igtf_percibido,
                # Mostrar tasa como %
                'tasa_igtf_display': f"{self.TASA_IGTF_PAGO:.0%}",
                'monto_abonado_neto': monto_abonado_neto,  # Monto que abona a deuda
                'monto_total_recibido': monto_total_recibido  # Monto total del pago
            }

            # --- Renderizar HTML ---
            try:
                template = get_template(self.template_name)
                html = template.render(context)
                if not isinstance(html, str):
                    raise TypeError(
                        "El renderizado del template no devolvió un string.")
            except Exception as render_error:
                logger.error(
                    f"Error renderizando template PDF para pago {pk}: {render_error}", exc_info=True)
                self._create_audit_log(
                    request, 'ERROR', pk, f"Error render template: {render_error}")
                return HttpResponseServerError("Error interno generando contenido del PDF.")

            # --- Generar PDF ---
            result = BytesIO()
            pdf_status = pisa.pisaDocument(
                BytesIO(html.encode('UTF-8')),
                result,
                encoding='UTF-8',
                link_callback=self.link_callback  # Usar el método de esta instancia
            )

            if pdf_status.err:
                error_detail = f"xhtml2pdf error: {pdf_status.err}"
                logger.error(
                    f"Error generando PDF para pago {pk}: {error_detail}")
                self._create_audit_log(request, 'ERROR', pk, error_detail)
                return HttpResponse(f"Error al generar el PDF ({pdf_status.err}). Por favor, contacte soporte.", status=500)

            # --- Respuesta HTTP con el PDF ---
            response = HttpResponse(
                result.getvalue(), content_type='application/pdf')
            filename = f"recibo_pago_{pago.referencia_pago or pago.pk}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'

            # --- Auditoría Éxito ---
            self._create_audit_log(request, 'EXITO', pk,
                                   "PDF generado/visualizado")

            return response

        except Http404:
            logger.warning(
                f"Intento de acceso a PDF de Pago inexistente: PK={pk}")
            raise
        except PermissionDenied as e:
            logger.warning(
                f"Acceso denegado a PDF Pago PK={pk} por usuario {request.user.email}: {e}")
            messages.error(
                request, "No tiene permiso para ver este documento.")
            return redirect('myapp:home')  # O a donde sea apropiado
        except Exception as e:
            logger.error(
                f"Error inesperado en PagoPdfView (pk={pk}): {e}", exc_info=True)
            self._create_audit_log(request, 'ERROR', pk,
                                   f"Error inesperado: {e}")
            return HttpResponseServerError("Ocurrió un error inesperado al intentar generar el documento PDF.")
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


@login_required
# Esta es la que maneja el POST del modal
def marcar_comisiones_pagadas_view(request):
    if request.method == 'POST':
        comisiones_ids_a_pagar = request.POST.getlist('comisiones_a_pagar_ids')
        fecha_pago_efectiva_str = request.POST.get('fecha_pago_efectiva')
        intermediario_id_pago = request.POST.get(
            'intermediario_id_pago')  # Asegúrate que tu form lo envía

        fecha_pago_a_usar = django_timezone.now().date()

        if fecha_pago_efectiva_str:
            try:
                fecha_pago_a_usar = datetime.strptime(
                    fecha_pago_efectiva_str, '%d/%m/%Y').date()
                if fecha_pago_a_usar > django_timezone.now().date():  # Corregido para usar timezone.now()
                    messages.error(
                        request, "La fecha de pago no puede ser futura. Se usará la fecha actual.")
                    fecha_pago_a_usar = django_timezone.now().date()
            except ValueError:
                messages.error(
                    request, "Formato de fecha de pago inválido (DD/MM/AAAA). Se usará la fecha actual.")

        if comisiones_ids_a_pagar:
            try:
                comisiones_ids_int = [int(id_str)
                                      for id_str in comisiones_ids_a_pagar]
            except ValueError:
                messages.error(request, "Selección de comisiones inválida.")
                return redirect('myapp:liquidacion_comisiones')

            # Obtener info para notificación ANTES del update masivo
            comisiones_a_procesar_qs = RegistroComision.objects.filter(
                id__in=comisiones_ids_int,
                estatus_pago_comision='PENDIENTE'
                # Para obtener el nombre del intermediario
            ).select_related('intermediario')

            info_para_notificacion = []
            intermediario_obj_para_notif = None

            if intermediario_id_pago:
                try:
                    intermediario_obj_para_notif = Intermediario.objects.get(
                        pk=intermediario_id_pago)
                except Intermediario.DoesNotExist:
                    logger.warning(
                        f"Intermediario ID {intermediario_id_pago} no encontrado para notificación en pago múltiple.")
            elif comisiones_a_procesar_qs.exists():
                intermediario_obj_para_notif = comisiones_a_procesar_qs.first().intermediario

            # Necesitamos iterar para construir el mensaje, incluso si usamos update masivo
            # Esta lista es solo para el mensaje.
            comisiones_procesadas_para_mensaje = list(comisiones_a_procesar_qs)

            if not comisiones_procesadas_para_mensaje:
                messages.warning(
                    request, "No se encontraron comisiones pendientes válidas para la selección.")
                return redirect('myapp:liquidacion_comisiones')

            # Realizar el update masivo
            count_updated = RegistroComision.objects.filter(
                # Usar los IDs de las que realmente se procesarán
                id__in=[c.id for c in comisiones_procesadas_para_mensaje],
                estatus_pago_comision='PENDIENTE'  # Doble chequeo
            ).update(
                estatus_pago_comision='PAGADA',
                fecha_pago_a_intermediario=fecha_pago_a_usar,
                usuario_que_liquido=request.user  # Añadir quién liquidó
            )

            if count_updated > 0:
                messages.success(
                    request, f"{count_updated} comisión(es) marcada(s) como pagada(s) con fecha {fecha_pago_a_usar.strftime('%d/%m/%Y')}.")

                # *** CREAR NOTIFICACIÓN EN EL BACKEND ***
                # Construir info_para_notificacion a partir de comisiones_procesadas_para_mensaje
                for com_obj in comisiones_procesadas_para_mensaje:  # Iterar sobre los objetos que se iban a pagar
                    info_para_notificacion.append(
                        f"ID {com_obj.id} (Monto: {com_obj.monto_comision:.2f})")

                nombre_intermediario_str = "a un intermediario"  # Default
                if intermediario_obj_para_notif:
                    nombre_intermediario_str = f"al intermediario {intermediario_obj_para_notif.nombre_completo} ({intermediario_obj_para_notif.codigo})"

                if info_para_notificacion:  # Asegurar que haya algo que notificar
                    mensaje_notif_backend = (
                        f"Liquidaste {count_updated} comisiones {nombre_intermediario_str}. "
                        f"Detalles (hasta 3): {', '.join(info_para_notificacion[:3])}"
                        f"{'...' if len(info_para_notificacion) > 3 else '.'}"
                    )
                    crear_notificacion(
                        usuario_destino=request.user,
                        mensaje=mensaje_notif_backend,
                        tipo='success',
                        url_path_name='myapp:liquidacion_comisiones'
                    )
                    logger.info(
                        f"Notificación de backend creada para {request.user.username} por liquidación múltiple de {count_updated} comisiones.")
            else:
                messages.warning(
                    request, "No se marcaron comisiones. Pueden haber sido pagadas previamente o la selección fue inválida.")
        else:
            messages.warning(
                request, "No se seleccionaron comisiones para marcar como pagadas.")

        return redirect('myapp:liquidacion_comisiones')

    messages.error(request, "Acción no permitida (solo POST).")
    return redirect('myapp:liquidacion_comisiones')


@login_required
@require_POST
def marcar_comision_pagada_ajax_view(request):
    try:
        comision_id_str = request.POST.get('comision_id')
        if not comision_id_str:
            return JsonResponse({'status': 'error', 'message': 'ID de comisión no proporcionado.'}, status=400)

        comision_id = int(comision_id_str)  # Convertir a int
        comision = get_object_or_404(RegistroComision.objects.select_related(
            'intermediario'), pk=comision_id)  # Añadir select_related

        # CORRECCIÓN: Asegúrate que el campo ForeignKey a Intermediario en RegistroComision se llama 'intermediario'
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
        comision.fecha_pago_a_intermediario = django_timezone.now().date()  # Usar timezone.now()
        comision.usuario_que_liquido = request.user
        comision.save(update_fields=[
                      'estatus_pago_comision', 'fecha_pago_a_intermediario', 'usuario_que_liquido'])
        logger.info(
            f"Comisión ID {comision.id} marcada como PAGADA (AJAX) por {request.user.username}")

        # Calcular totales DESPUÉS de guardar
        nuevos_totales_despues_pago = calcular_totales_pendientes_intermediario(
            intermediario_obj)

        # *** CREAR NOTIFICACIÓN EN EL BACKEND ***
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

    except ValueError:  # Para el int(comision_id_str)
        return JsonResponse({'status': 'error', 'message': 'ID de comisión inválido.'}, status=400)
    except RegistroComision.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Comisión no encontrada.'}, status=404)
    except Exception as e:
        logger.error(
            f"Error en marcar_comision_pagada_ajax_view: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Error interno del servidor: {str(e)}'}, status=500)


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


class HistorialLiquidacionesListView(LoginRequiredMixin, ListView):
    model = RegistroComision
    template_name = 'historial_liquidaciones_list.html'
    context_object_name = 'liquidaciones'
    paginate_by = ITEMS_PER_PAGE

    search_fields_config = {
        'id_comision': ['pk'],
        'intermediario': ['intermediario__nombre_completo__icontains', 'intermediario__codigo__icontains'],
        'factura': ['factura_origen__numero_recibo__icontains'],
        'liquidador': [
            'usuario_que_liquido__username__icontains',
            'usuario_que_liquido__primer_nombre__icontains',
            'usuario_que_liquido__primer_apellido__icontains',
            'usuario_que_liquido__segundo_nombre__icontains',
            'usuario_que_liquido__segundo_apellido__icontains',
            'usuario_que_liquido__email__icontains',
        ],
        'tipo': ['tipo_comision__iexact'],
    }
    ordering_options = {
        'id': 'ID', 'intermediario__nombre_completo': 'Intermediario', 'monto_comision': 'Monto',
        'tipo_comision': 'Tipo', 'fecha_pago_a_intermediario': 'Fecha Pago',
        'usuario_que_liquido__username': 'Liquidado Por', 'fecha_calculo': 'F. Cálculo'
    }
    default_ordering = ['-fecha_pago_a_intermediario', '-id']

    def get_queryset(self):
        logger.debug(f"[{self.__class__.__name__}] Iniciando get_queryset.")
        queryset = RegistroComision.objects.filter(
            estatus_pago_comision='PAGADA')

        queryset = queryset.select_related(
            'intermediario', 'usuario_que_liquido', 'factura_origen',
            'pago_cliente', 'contrato_individual', 'contrato_colectivo',
            'intermediario_vendedor'
        )

        self.search_query = self.request.GET.get('search', '').strip()
        logger.debug(f"Término de búsqueda recibido: '{self.search_query}'")

        if self.search_query:
            q_objects = Q()
            for field_group, lookups in self.search_fields_config.items():
                for lookup in lookups:
                    if field_group == 'id_comision':
                        try:
                            q_objects |= Q(pk=int(self.search_query))
                            logger.debug(
                                f"Añadido filtro de búsqueda por PK: {self.search_query}")
                        except ValueError:
                            pass
                    else:
                        q_objects |= Q(**{lookup: self.search_query})
                        logger.debug(
                            f"Añadido filtro de búsqueda: {lookup} = {self.search_query}")

            if q_objects:
                queryset = queryset.filter(q_objects).distinct()
                logger.info(
                    f"Queryset filtrado por búsqueda. Nuevo count: {queryset.count()}")
            else:
                logger.info("No se generaron Q objects para la búsqueda.")
        else:
            logger.debug(
                "No hay término de búsqueda, no se aplica filtro de búsqueda.")

        sort_param = self.request.GET.get('sort')
        order_direction = self.request.GET.get(
            'order', '').lower()  # Default a '' para chequear luego

        # Usar el ordering por defecto de la clase si no hay parámetros GET específicos
        # O si el sort_param no es válido
        final_ordering_fields = list(
            self.default_ordering)  # Empezar con el default

        if sort_param and sort_param.lstrip('-') in self.ordering_options.keys():
            self.current_sort = sort_param.lstrip('-')
            # Si no se especifica order, tomar el del default_ordering para ese campo si existe, o 'asc'
            if not order_direction:
                for default_o_field in self.default_ordering:
                    if default_o_field.lstrip('-') == self.current_sort:
                        order_direction = 'desc' if default_o_field.startswith(
                            '-') else 'asc'
                        break
                if not order_direction:  # Si no estaba en los defaults
                    order_direction = 'asc'

            self.current_order = order_direction

            prefix = "-" if self.current_order == 'desc' else ""
            final_ordering_fields = [f"{prefix}{self.current_sort}"]
            logger.debug(f"Aplicando orden: {final_ordering_fields}")
        else:
            self.current_sort = self.default_ordering[0].lstrip(
                '-') if self.default_ordering else 'id'
            self.current_order = 'desc' if self.default_ordering and self.default_ordering[0].startswith(
                '-') else 'asc'
            logger.debug(f"Usando orden por defecto: {final_ordering_fields}")

        queryset = queryset.order_by(*final_ordering_fields)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Historial de Liquidaciones de Comisiones"
        context['active_tab'] = "comisiones"

        context['search_query'] = getattr(self, 'search_query', '')
        context['current_sort'] = getattr(self, 'current_sort', self.default_ordering[0].lstrip(
            '-') if self.default_ordering else 'id')
        context['current_order'] = getattr(
            self, 'current_order', 'desc' if self.default_ordering and self.default_ordering[0].startswith('-') else 'asc')

        query_params = self.request.GET.copy()
        # Preservar search para ordenamiento y paginación
        preserved_for_ordering = {}
        if self.search_query:
            preserved_for_ordering['search'] = self.search_query
        context['preserved_filters_for_ordering'] = urlencode(
            preserved_for_ordering)

        # Preservar search y orden para paginación
        preserved_for_pagination = {}
        if self.search_query:
            preserved_for_pagination['search'] = self.search_query
        if hasattr(self, 'current_sort') and self.current_sort:  # Usar el atributo de instancia
            preserved_for_pagination['sort'] = self.current_sort
            preserved_for_pagination['order'] = getattr(
                self, 'current_order', 'asc')  # Usar el atributo de instancia

        context['preserved_filters_for_pagination'] = urlencode(
            preserved_for_pagination)

        context['ordering_options'] = self.ordering_options
        return context


def license_invalid_view(request):
    # Puedes pasar el email de soporte al contexto si lo usas en la plantilla
    # from django.conf import settings
    # support_email = getattr(settings, 'SUPPORT_EMAIL', 'soporte@example.com')
    # context = {'support_email': support_email}
    context = {}
    # Ajusta la ruta a tu plantilla
    return render(request, 'license_invalid.html', context)
