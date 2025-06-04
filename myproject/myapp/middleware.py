# myapp/middleware.py

import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import logout, get_user_model
from django.shortcuts import redirect, render, resolve_url
from django.core.cache import caches
from django.db import connection, transaction
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden, HttpResponseServerError
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
import traceback
import re
from .licensing import check_license
import time
from django.utils import timezone
from django.urls import reverse, NoReverseMatch, reverse_lazy

logger = logging.getLogger(__name__)
UserModel = get_user_model()
AUDITORIA_ENABLED = True

try:
    AuditoriaSistema = apps.get_model('myapp', 'AuditoriaSistema')
except LookupError:
    logger.error(
        "MODELO AuditoriaSistema NO ENCONTRADO. Middleware de auditoría desactivado.")
    AuditoriaSistema = None
    AUDITORIA_ENABLED = False


class AuditoriaMiddleware:
    URL_MODEL_MAP = {
        '/contratos_individuales/': 'ContratoIndividual',
        '/contratos_colectivos/': 'ContratoColectivo',
        '/afiliados_individuales/': 'AfiliadoIndividual',
        '/afiliados_colectivos/': 'AfiliadoColectivo',
        '/intermediarios/': 'Intermediario',
        '/reclamaciones/': 'Reclamacion',
        '/pagos/': 'Pago',
        '/tarifas/': 'Tarifa',
        '/facturas/': 'Factura',
        '/usuarios/': 'Usuario',
        '/admin/myapp/contratoindividual/': 'ContratoIndividual',
        '/admin/myapp/contratocolectivo/': 'ContratoColectivo',
        '/admin/myapp/afiliadoindividual/': 'AfiliadoIndividual',
        '/admin/myapp/afiliadocolectivo/': 'AfiliadoColectivo',
        '/admin/myapp/intermediario/': 'Intermediario',
        '/admin/myapp/reclamacion/': 'Reclamacion',
        '/admin/myapp/pago/': 'Pago',
        '/admin/myapp/tarifa/': 'Tarifa',
        '/admin/myapp/factura/': 'Factura',
        '/admin/myapp/usuario/': 'Usuario',
        '/admin/myapp/auditoriasistema/': 'AuditoriaSistema',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.audit_start_time = timezone.now()
        response = None
        exception_occurred = None
        try:
            response = self.get_response(request)
        except Exception as e:
            exception_occurred = e
            logger.error(
                f"Excepción capturada por AuditoriaMiddleware antes de _log_auditoria: {e}", exc_info=True)
            raise
        finally:
            if AUDITORIA_ENABLED and AuditoriaSistema:
                try:
                    self._log_auditoria(request, response, exception_occurred)
                except Exception as audit_log_error:
                    logger.error(
                        f"[AuditoriaMiddleware.__call__] Error CRÍTICO al intentar _log_auditoria: {audit_log_error}",
                        exc_info=True
                    )
            elif not AUDITORIA_ENABLED or not AuditoriaSistema:
                logger.debug(
                    "[AuditoriaMiddleware.__call__] Auditoría desactivada o modelo no disponible. Omitiendo log.")
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        model = getattr(getattr(view_func, 'view_class', None), 'model', None)
        if model:
            request._audit_model_from_view = model
        if 'pk' in view_kwargs:
            request._audit_pk_from_kwargs = view_kwargs['pk']
        return None

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR', 'N/A')

    def _get_object_pk_from_response(self, request, response):
        pk = getattr(request, '_audit_pk_from_kwargs', None)
        if pk:
            return pk
        if request.method in ['POST', 'PUT', 'PATCH'] and response and hasattr(response, 'status_code') and 300 <= response.status_code < 400:
            location = response.get('Location', '')
            if location:
                match = re.search(r'/(\d+)/?$', location)
                if match:
                    try:
                        return int(match.group(1))
                    except (ValueError, TypeError):
                        pass
        parts = request.path.strip('/').split('/')
        if parts and parts[-1].isdigit():
            try:
                return int(parts[-1])
            except (ValueError, TypeError):
                pass
        return None

    def _get_model_info_from_request(self, request):
        model_name, table_name = None, None
        model_class = getattr(request, '_audit_model_from_view', None)
        if model_class:
            model_name = model_class.__name__
            try:
                table_name = model_class._meta.db_table
            except AttributeError:
                logger.warning(
                    f"[AuditoriaMiddleware] _audit_model_from_view ('{model_name}') no tiene _meta.db_table.")
                table_name = model_name
        else:
            path_lower = request.path.lower()
            sorted_prefixes = sorted(
                self.URL_MODEL_MAP.keys(), key=len, reverse=True)
            for url_prefix in sorted_prefixes:
                if path_lower.startswith(url_prefix):
                    model_name = self.URL_MODEL_MAP[url_prefix]
                    try:
                        # Verificar app y modelo
                        if apps.is_installed('myapp') and apps.get_model('myapp', model_name):
                            table_name = apps.get_model(
                                'myapp', model_name)._meta.db_table
                        else:
                            table_name = model_name
                    except LookupError:
                        logger.warning(
                            f"[AuditoriaMiddleware] Modelo '{model_name}' no encontrado en app 'myapp' para URL {url_prefix}.")
                        table_name = model_name
                    break
        return model_name, table_name

    def _log_auditoria(self, request, response, exception):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            logger.debug(
                "[AuditoriaMiddleware._log] Usuario no autenticado. Omitiendo log.")
            return
        if request.method == 'GET':
            logger.debug(
                "[AuditoriaMiddleware._log] Petición GET. Omitiendo log de cambios.")
            return

        start_log_time = time.time()
        try:
            action_map = {'POST': 'CREACION', 'PUT': 'ACTUALIZACION',
                          'PATCH': 'ACTUALIZACION_PARCIAL', 'DELETE': 'ELIMINACION'}
            action = action_map.get(request.method, f'OTRO ({request.method})')

            status_code_for_log = 'N/A'
            if response and hasattr(response, 'status_code'):
                status_code_for_log = response.status_code

            if exception:
                result = 'ERROR_EXCEPCION'
                detalle_base = f"Excepción: {type(exception).__name__} - {str(exception)}"
            elif response and 200 <= status_code_for_log < 300:
                result = 'EXITO'
                detalle_base = f"{action} en {request.path}"
            elif response and 300 <= status_code_for_log < 400:
                result = 'EXITO_REDIRECCION'
                detalle_base = f"{action} en {request.path} -> Redirección a {response.get('Location', 'N/A')}"
            else:
                result = 'FALLO_RESPUESTA'
                detalle_base = f"{action} en {request.path}"

            detalle_final = f"{detalle_base} - Status: {status_code_for_log}"
            model_name, table_name = self._get_model_info_from_request(request)
            record_pk = self._get_object_pk_from_response(request, response)
            user_to_log = request.user

            if not isinstance(user_to_log, UserModel) or not user_to_log.pk:
                logger.warning(
                    f"[AuditoriaMiddleware._log] Intento de log con usuario inválido o anónimo (PK: {getattr(user_to_log, 'pk', 'N/A')}). Omitiendo.")
                return

            AuditoriaSistema.objects.create(
                usuario=user_to_log, tipo_accion=action, resultado_accion=result,
                tabla_afectada=table_name if table_name else "N/A",
                registro_id_afectado=record_pk,
                detalle_accion=detalle_final[:490],
                direccion_ip=self._get_client_ip(request),
                agente_usuario=request.META.get('HTTP_USER_AGENT', '')[:490],
                tiempo_inicio=getattr(
                    request, 'audit_start_time', timezone.now()),
                tiempo_final=timezone.now()
            )
            log_duration = time.time() - start_log_time
            logger.info(
                f"[AuditoriaMiddleware._log] Auditoría guardada ({log_duration:.4f}s) para {action} en {request.path}. User PK: {user_to_log.pk}. Result: {result}.")
        except Exception as e_create_log:
            log_duration = time.time() - start_log_time
            logger.error(
                f"[AuditoriaMiddleware._log] !! ERROR CRÍTICO AL GUARDAR EN BD AuditoriaSistema !! ({log_duration:.4f}s) para {request.method} {request.path}. User PK: {getattr(request.user, 'pk', 'N/A')}. Error: {type(e_create_log).__name__} - {e_create_log}",
                exc_info=True
            )


class CustomSessionMiddleware:
    SESSION_TIMEOUT_SECONDS = getattr(settings, 'SESSION_COOKIE_AGE', 3600)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_auth_before = hasattr(
            request, 'user') and request.user.is_authenticated
        session_key_before = request.session.session_key if request.session else "N/A"

        if user_auth_before:
            session = request.session
            last_activity_str = session.get('ultima_actividad')
            current_time = timezone.now()
            try:
                session['ultima_actividad'] = current_time.isoformat()
                if not settings.SESSION_SAVE_EVERY_REQUEST:
                    session.modified = True
            except Exception as e_session_save:
                logger.error(
                    f"[CustomSessionMiddleware] Error actualizando 'ultima_actividad' para user PK {request.user.pk} / session {session_key_before}: {e_session_save}")

            if last_activity_str:
                try:
                    last_activity_dt = datetime.fromisoformat(
                        last_activity_str)
                    if settings.USE_TZ and timezone.is_naive(last_activity_dt):
                        last_activity_dt = timezone.make_aware(
                            last_activity_dt, timezone.get_default_timezone())
                    elif not settings.USE_TZ and timezone.is_aware(last_activity_dt):
                        last_activity_dt = timezone.make_naive(
                            last_activity_dt, timezone.get_default_timezone())

                    inactivity_seconds = (
                        current_time - last_activity_dt).total_seconds()
                    if inactivity_seconds > self.SESSION_TIMEOUT_SECONDS:
                        user_pk_before_logout = request.user.pk
                        logger.warning(
                            f"[CustomSessionMiddleware] SESIÓN EXPIRADA por inactividad ({inactivity_seconds:.0f}s > {self.SESSION_TIMEOUT_SECONDS}s) para user PK {user_pk_before_logout}. Deslogueando.")
                        logout(request)
                        try:
                            return redirect(reverse_lazy('myapp:login'))
                        except NoReverseMatch:
                            logger.error(
                                "[CustomSessionMiddleware] No se pudo resolver 'myapp:login' para redirección post-logout.")
                            from django.http import HttpResponseRedirect
                            return HttpResponseRedirect('/')
                except (ValueError, TypeError) as e_parse:
                    logger.error(
                        f"[CustomSessionMiddleware] Error parseando 'ultima_actividad' ('{last_activity_str}') para user PK {request.user.pk}: {e_parse}. Reiniciando timestamp.")
                    session['ultima_actividad'] = current_time.isoformat()
                except Exception as e_check_exp:
                    logger.exception(
                        f"[CustomSessionMiddleware] Error INESPERADO validando expiración para user PK {request.user.pk}: {e_check_exp}")

        response = self.get_response(request)
        user_auth_after = hasattr(
            request, 'user') and request.user.is_authenticated
        if user_auth_before and not user_auth_after:
            try:
                logout_url_path = resolve_url(reverse_lazy('myapp:logout'))
                if request.path != logout_url_path:
                    logger.warning(
                        f"[CustomSessionMiddleware] Usuario (sesión {session_key_before}) desautenticado INESPERADAMENTE durante vista {request.path}!")
            except NoReverseMatch:
                pass
        return response


class GraphCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self.cache = caches['graphs']
        except Exception as e:
            logger.error(
                f"Error inicializando cache 'graphs': {e}. Middleware de caché de gráficos desactivado.")
            self.cache = None

    def __call__(self, request):
        if self.cache and 'graph' in request.GET:
            graph_id = request.GET['graph']
            cache_key = f"graph_data_{graph_id}"
            cached_response_data = self.cache.get(cache_key)
            if cached_response_data is not None:
                logger.debug(
                    f"[GraphCacheMiddleware] Sirviendo gráfico '{graph_id}' desde caché.")
                return cached_response_data
            response = self.get_response(request)
            if response.status_code == 200:
                logger.debug(
                    f"[GraphCacheMiddleware] Guardando gráfico '{graph_id}' en caché.")
                self.cache.set(cache_key, response, timeout=3600)
            return response
        return self.get_response(request)


class QueryMonitorMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if settings.DEBUG and 'queries' in request.GET:
            try:
                from django.db import connection
                queries = connection.queries
                num_queries = len(queries)
                total_time = sum(float(q.get('time', 0)) for q in queries)
                logger.info(
                    f"[QueryMonitor] Path: {request.path} | Queries: {num_queries} | Time: {total_time:.4f}s")
            except Exception as e:
                logger.error(
                    f"[QueryMonitorMiddleware] Error: {e}", exc_info=True)
        return response


class ErrorHandlerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception as e:
            logger.exception(
                f"[ErrorHandlerMiddleware] EXCEPCIÓN NO CAPTURADA en {request.method} {request.path}")
            if settings.DEBUG:
                raise
            try:
                return render(request, '500.html', status=500)
            except Exception as render_e:
                logger.critical(
                    f"[ErrorHandlerMiddleware] !! ERROR CRÍTICO AL RENDERIZAR 500.html !!: {render_e}", exc_info=True)
                return HttpResponseServerError("Error Interno del Servidor. Por favor, contacte al administrador.", content_type="text/plain")
        return response


class LicenseCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_url_names_from_settings = frozenset(
            getattr(settings, 'LICENSE_EXEMPT_URL_NAMES', []))
        self.exempt_path_prefixes = tuple(filter(None, [
            getattr(settings, 'STATIC_URL', '/static/'),
            getattr(settings, 'MEDIA_URL', '/media/'),
            '/admin/'
        ]))
        self.license_invalid_url_name = 'myapp:license_invalid'
        self.activate_license_url_name = 'myapp:activate_license'
        logger.debug(
            f"LicenseCheckMiddleware inicializado. Exentos (nombres): {self.exempt_url_names_from_settings}, Exentos (prefijos): {self.exempt_path_prefixes}")

    def __call__(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)

        try:
            license_invalid_path = resolve_url(self.license_invalid_url_name)
            activate_license_path = resolve_url(self.activate_license_url_name)
            if request.path_info in [license_invalid_path, activate_license_path]:
                logger.debug(
                    f"[LicenseCheck] Acceso permitido a PATH exento directo de licencia: {request.path_info}")
                return self.get_response(request)
        except NoReverseMatch:
            logger.error(
                f"[LicenseCheck] Error CRÍTICO resolviendo URLs de licencia '{self.license_invalid_url_name}' o '{self.activate_license_url_name}'.")
            # return HttpResponseServerError("Error de configuración interna de licencia.") # Descomentar si se quiere bloquear

        for prefix in self.exempt_path_prefixes:
            if request.path_info.startswith(prefix):
                logger.debug(
                    f"[LicenseCheck] Acceso permitido a PREFIJO exento: {request.path_info} (prefijo: {prefix})")
                return self.get_response(request)

        current_url_name = None
        if request.resolver_match:
            current_url_name = f"{request.resolver_match.namespace}:{request.resolver_match.url_name}" if request.resolver_match.namespace else request.resolver_match.url_name
            if current_url_name in self.exempt_url_names_from_settings:
                logger.debug(
                    f"[LicenseCheck] Acceso permitido a URL_NAME exento de settings: {current_url_name} ({request.path_info})")
                return self.get_response(request)

        license_valid, license_details = check_license(detailed=True)
        if not license_valid:
            user_type_log = "Superusuario" if request.user.is_superuser else "Usuario Normal"
            log_message = (
                f"[LicenseCheck] Acceso DENEGADO para {user_type_log} {getattr(request.user, 'email', request.user.username)} "
                f"a '{request.path_info}' (URL name: {current_url_name}) por licencia inválida/expirada. "
                f"Detalles: {license_details}. Redirigiendo a '{self.license_invalid_url_name}'..."
            )
            logger.warning(log_message)
            try:
                return redirect(reverse_lazy(self.license_invalid_url_name))
            except Exception as e_redirect:
                logger.error(
                    f"[LicenseCheck] Fallo al redirigir a '{self.license_invalid_url_name}' para usuario {getattr(request.user, 'email', request.user.username)}: {e_redirect}. Devolviendo 403.", exc_info=True)
                return HttpResponseForbidden(f"Error de Licencia: Su licencia es inválida o ha expirado. Detalles: {license_details}")

        logger.debug(
            f"[LicenseCheck] Acceso PERMITIDO (licencia válida) para {getattr(request.user, 'email', request.user.username)} a '{request.path_info}'. Detalles: {license_details}")
        return self.get_response(request)
