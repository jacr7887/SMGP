# myapp/middleware.py

import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import logout, get_user_model
from django.shortcuts import redirect, render
from django.core.cache import caches
from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse, HttpResponseServerError
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
import traceback
import re
from .licensing import check_license  # Importar la función principal
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
                f"Excepción durante get_response en AuditoriaMiddleware: {e}", exc_info=True)
            raise e
        finally:
            if AUDITORIA_ENABLED and AuditoriaSistema:
                # Evitar loggear si la conexión ya está cerrada (causa común del error crítico)
                try:
                    connection.ensure_connection()
                    if not connection.is_usable():
                        logger.error(
                            "[AuditoriaMiddleware._log] Conexión a BD no usable, omitiendo log de auditoría.")
                    else:
                        self._log_auditoria(
                            request, response, exception_occurred)
                except Exception as db_error:
                    logger.error(
                        f"[AuditoriaMiddleware._log] Error de conexión al intentar loggear auditoría: {db_error}")

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
        return x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')

    def _get_object_pk_from_response(self, request, response):
        pk = getattr(request, '_audit_pk_from_kwargs', None)
        if pk:
            return pk
        if request.method in ['POST', 'PUT', 'PATCH'] and response and 300 <= response.status_code < 400:
            location = response.get('Location', '')
            match = re.search(r'/(\d+)/?$', location)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, TypeError):
                    pass
        parts = request.path.strip('/').split('/')
        if len(parts) > 1 and parts[-1].isdigit():
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
            table_name = model_class._meta.db_table
        else:
            path_lower = request.path.lower()
            sorted_prefixes = sorted(
                self.URL_MODEL_MAP.keys(), key=len, reverse=True)
            for url_prefix in sorted_prefixes:
                if path_lower.startswith(url_prefix):
                    model_name = self.URL_MODEL_MAP[url_prefix]
                    try:
                        table_name = apps.get_model(
                            'myapp', model_name)._meta.db_table
                    except LookupError:
                        table_name = model_name
                    break
        return model_name, table_name

    def _log_auditoria(self, request, response, exception):
        if not hasattr(request, 'user') or not request.user.is_authenticated or request.method == 'GET':
            return

        start_log_time = time.time()
        try:
            action = {'POST': 'CREACION', 'PUT': 'ACTUALIZACION', 'PATCH': 'ACTUALIZACION',
                      'DELETE': 'ELIMINACION'}.get(request.method, 'OTRO')
            result = 'ERROR' if exception else (
                'EXITO' if response and 200 <= response.status_code < 400 else 'FALLO')
            detalle = f"Excepción: {str(exception)[:200]}" if exception else f"{action} {request.path} - Status: {response.status_code if response else 'N/A'}"
            model_name, table_name = self._get_model_info_from_request(request)
            record_pk = self._get_object_pk_from_response(request, response)
            user_to_log = request.user

            if not isinstance(user_to_log, UserModel):
                try:
                    user_to_log = UserModel.objects.get(
                        pk=getattr(user_to_log, 'pk', None))
                except (UserModel.DoesNotExist, AttributeError, ValueError, TypeError):
                    user_to_log = None

            if user_to_log:
                AuditoriaSistema.objects.create(
                    usuario=user_to_log, tipo_accion=action, resultado_accion=result,
                    tabla_afectada=table_name, registro_id_afectado=record_pk,
                    detalle_accion=detalle[:490], direccion_ip=self._get_client_ip(
                        request),
                    agente_usuario=request.META.get(
                        'HTTP_USER_AGENT', '')[:490],
                    tiempo_inicio=getattr(
                        request, 'audit_start_time', timezone.now()),
                    tiempo_final=timezone.now()
                )
        except Exception as e:
            log_duration = time.time() - start_log_time
            logger.error(
                f"[AuditoriaMiddleware._log] !! ERROR CRÍTICO AL GUARDAR AUDITORÍA !! ({log_duration:.4f}s) para {request.method} {request.path}. User: {getattr(request.user, 'pk', 'N/A')}. Error: {e}", exc_info=True)


class CustomSessionMiddleware:
    SESSION_TIMEOUT_SECONDS = getattr(settings, 'SESSION_COOKIE_AGE', 3600)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_auth_before = hasattr(
            request, 'user') and request.user.is_authenticated
        session_key_before = request.session.session_key

        if user_auth_before:
            session = request.session
            last_activity_str = session.get('ultima_actividad')
            now = timezone.now() if settings.USE_TZ else datetime.now()
            now_iso = now.isoformat()

            try:
                session['ultima_actividad'] = now_iso
                if not settings.SESSION_SAVE_EVERY_REQUEST:
                    session.save()
            except Exception as e:
                logger.error(
                    f"[CustomSessionMiddleware] Error ACTUALIZANDO ultima_actividad user {request.user.pk} / session {session_key_before}: {e}")

            if last_activity_str:
                try:
                    try:
                        last_activity_dt = datetime.fromisoformat(
                            last_activity_str)
                    except ValueError:
                        last_activity_dt = datetime.strptime(
                            last_activity_str, '%Y-%m-%dT%H:%M:%S')

                    if settings.USE_TZ and last_activity_dt.tzinfo is None:
                        last_activity_dt = timezone.make_aware(
                            last_activity_dt, timezone.get_default_timezone())
                    elif not settings.USE_TZ and last_activity_dt.tzinfo is not None:
                        last_activity_dt = timezone.make_naive(
                            last_activity_dt, timezone.get_default_timezone())

                    inactivity_seconds = (
                        now - last_activity_dt).total_seconds()

                    if inactivity_seconds > self.SESSION_TIMEOUT_SECONDS:
                        user_pk_before_logout = request.user.pk
                        logger.warning(
                            f"[CustomSessionMiddleware] SESIÓN EXPIRADA por inactividad para user {user_pk_before_logout}. Deslogueando.")
                        logout(request)
                        return redirect('myapp:login')
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"[CustomSessionMiddleware] Error parseando ultima_actividad ('{last_activity_str}') user {request.user.pk}: {e}")
                    session['ultima_actividad'] = now_iso
                except Exception as e:
                    logger.exception(
                        f"[CustomSessionMiddleware] Error INESPERADO validando expiración user {request.user.pk}: {e}")

        response = self.get_response(request)

        user_auth_after = hasattr(
            request, 'user') and request.user.is_authenticated
        try:
            logout_url = reverse('myapp:logout')
            if user_auth_before and not user_auth_after and request.path != logout_url:
                logger.warning(
                    f"[CustomSessionMiddleware] Usuario ({session_key_before}) desautenticado INESPERADAMENTE durante vista {request.path}!")
        except NoReverseMatch:
            pass  # Ignorar si la URL de logout no existe

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
            cache_key = f"graph_{request.GET['graph']}"
            response = self.cache.get(cache_key)
            if not response:
                response = self.get_response(request)
                if response.status_code == 200:
                    self.cache.set(cache_key, response, 3600)
            return response
        return self.get_response(request)


class QueryMonitorMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if settings.DEBUG and 'queries' in request.GET:
            try:
                q = connection.queries
                t = sum(float(i.get('time', 0)) for i in q)
                n = len(q)
                msg = f"\n--- DB Queries ({request.path}) ---\nTotal:{n}\nTime:{t:.4f}s\n"
                logger.debug(msg)
            except Exception as e:
                logger.error(f"[QueryMonitorMiddleware] Error: {e}")
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
                    f"[ErrorHandlerMiddleware] !! ERROR AL RENDERIZAR 500.html !!: {render_e}")
                return HttpResponseServerError("Error Interno del Servidor", content_type="text/plain")
        return response


# Asegúrate que 'license_invalid' exista en urls.py
LICENSE_EXEMPT_URL_NAMES = ['myapp:login',
                            'myapp:logout', 'myapp:license_invalid']


class LicenseCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Construir las rutas exentas una vez
        self.exempt_paths = []
        try:
            self.exempt_paths.append(reverse('myapp:license_invalid'))
            self.exempt_paths.append(reverse('myapp:activate_license'))
            # Añade otras URLs que se resuelven desde nombres si es necesario
        except Exception as e:
            logger.error(
                f"Error resolviendo URLs exentas en LicenseCheckMiddleware __init__: {e}")

        # Añadir prefijos de path directamente
        self.exempt_path_prefixes = [
            getattr(settings, 'STATIC_URL', '/static/'),
            getattr(settings, 'MEDIA_URL', '/media/'),
            '/admin/'  # Para el login y navegación básica del admin
        ]
        # Lista de nombres de URL exentos de settings.py
        self.exempt_url_names_from_settings = getattr(
            settings, 'LICENSE_EXEMPT_URL_NAMES', [])

        logger.debug("Middleware de Licencia inicializado.")

    def __call__(self, request):
        if not request.user or not request.user.is_authenticated:
            return self.get_response(request)

        # 1. Chequeo por PATH directo para las páginas de gestión de licencia
        if request.path_info in self.exempt_paths:
            logger.debug(
                f"Acceso permitido a PATH exento: {request.path_info}")
            return self.get_response(request)

        # 2. Chequeo por prefijo de PATH (static, media, admin)
        for prefix in self.exempt_path_prefixes:
            if prefix and request.path_info.startswith(prefix):
                logger.debug(
                    f"Acceso permitido a PREFIJO exento: {request.path_info}")
                return self.get_response(request)

        # 3. Chequeo por NOMBRE de URL (resolver_match)
        current_url_name = None
        if request.resolver_match:
            current_url_name = f"{request.resolver_match.namespace}:{request.resolver_match.url_name}" if request.resolver_match.namespace else request.resolver_match.url_name
            if current_url_name in self.exempt_url_names_from_settings:
                logger.debug(
                    f"Acceso permitido a URL_NAME exento: {current_url_name} ({request.path_info})")
                return self.get_response(request)

        # 4. Si no está exenta por ninguno de los métodos anteriores, verificar licencia
        if not check_license():
            user_type_log = "Superusuario" if request.user.is_superuser else "Usuario"
            logger.warning(
                f"Acceso DENEGADO para {user_type_log} {request.user.email} a '{request.path}' (URL name: {current_url_name}) por licencia inválida/expirada. Redirigiendo a 'myapp:license_invalid'.")
            try:
                # No necesitamos chequear de nuevo si es 'myapp:license_invalid' porque
                # ya debería haber sido capturado por self.exempt_paths
                return redirect(reverse_lazy('myapp:license_invalid'))
            except Exception as e_redirect:
                from django.http import HttpResponseForbidden
                logger.error(
                    f"Fallo al redirigir a 'myapp:license_invalid' para {request.user.email}: {e_redirect}. Devolviendo 403.", exc_info=True)
                return HttpResponseForbidden("Error de Licencia: Su licencia es inválida o ha expirado.")

        # Si la licencia es válida y la página no estaba exenta, permitir acceso
        logger.debug(
            f"Acceso PERMITIDO (licencia válida) para {request.user.email} a '{request.path}'")
        return self.get_response(request)
