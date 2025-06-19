# myapp/tasks.py
"""Módulo avanzado para gestión de caché de gráficos con soporte multi-backend"""
from typing import Optional, Union
from django.core.cache import caches
from django.core.cache.backends.base import BaseCache, InvalidCacheBackendError
import logging
import warnings
from celery import shared_task
from django.db import transaction
from django.db.models import Q
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import logging


from .models import ContratoIndividual, ContratoColectivo, Factura

logger = logging.getLogger(__name__)


# Configuración inicial de logging
logger = logging.getLogger(__name__)
# Suprime warnings de conexiones
warnings.simplefilter("ignore", ResourceWarning)


def clear_graph_cache(backend_name: str = 'default') -> Optional[int]:
    """Elimina todas las entradas de caché relacionadas con gráficos de forma segura.

    Args:
        backend_name (str): Nombre del backend configurado en settings.CACHES.
                            Default: 'default'

    Returns:
        int: Número de entradas eliminadas (None si falla críticamente)

    Raises:
        ValueError: Si el backend no existe
        TypeError: Si el backend no soporta las operaciones necesarias

    Ejemplos:
        >>> clear_graph_cache()
        42  # Entradas eliminadas

        >>> clear_graph_cache('memcached')
        15
    """
    try:
        backend = caches[backend_name]
        return _handle_cache_clean(backend)

    except KeyError as e:
        logger.critical("Backend de caché no encontrado: %s", backend_name)
        raise ValueError(f"Backend '{backend_name}' no existe") from e

    except InvalidCacheBackendError as e:
        logger.error("Backend inválido: %s", str(e))
        return None

    except Exception as e:
        logger.error("Error no controlado: %s", str(e), exc_info=True)
        return None


def _handle_cache_clean(backend: BaseCache) -> Optional[int]:
    """Estrategia de limpieza según tipo de backend."""
    try:
        # Optimización para Redis
        if 'redis' in backend.__class__.__name__.lower():
            if hasattr(backend, 'delete_pattern'):
                return backend.delete_pattern("graph_*")
            return _redis_fallback_clean(backend)

        # Optimización para Memcached
        elif 'memcached' in backend.__class__.__name__.lower():
            return _memcached_clean(backend)

        # Método estándar para otros backends
        return _generic_cache_clean(backend)

    except AttributeError as e:
        logger.warning("Backend no soporta operaciones bulk: %s", str(e))
        return _fallback_sequential_clean(backend)


def _generic_cache_clean(backend: BaseCache) -> int:
    """Limpieza genérica para la mayoría de backends."""
    keys = backend.keys("graph_*")
    if not keys:
        logger.debug("No se encontraron claves para limpiar")
        return 0
    backend.delete_many(keys)
    return len(keys)


def _redis_fallback_clean(backend: BaseCache) -> int:
    """Limpieza alternativa para Redis sin delete_pattern."""
    from redis import Redis  # type: ignore
    client: Redis = backend.get_client()
    keys = client.keys("graph_*")
    if not keys:
        return 0
    return client.delete(*keys)


def _memcached_clean(backend: BaseCache) -> int:
    """Limpieza optimizada para Memcached."""
    from pylibmc import Client  # type: ignore
    client: Client = backend._cache  # pylint: disable=protected-access
    all_keys = client.get_multi(client.keys()).keys()
    target_keys = [k for k in all_keys if k.startswith(b'graph_')]
    if not target_keys:
        return 0
    client.delete_multi(target_keys)
    return len(target_keys)


def _fallback_sequential_clean(backend: BaseCache) -> int:
    """Limpieza secuencial para backends limitados."""
    deleted = 0
    for key in backend.iter_keys("graph_*"):
        backend.delete(key)
        deleted += 1
    return deleted


# Ejemplo de uso básico (opcional)
if __name__ == "__main__":
    import django
    django.setup()
    result = clear_graph_cache()
    print(f"Entradas eliminadas: {result or 0}")


def generar_facturas_para_contrato(contrato):
    """
    Función helper que contiene la lógica para un solo contrato.
    Devuelve el número de facturas creadas.
    """
    hoy = date.today()
    if not contrato.esta_vigente:
        return 0

    # Determinar el intervalo de pago
    intervalo = None
    if contrato.forma_pago == 'MENSUAL':
        intervalo = relativedelta(months=1)
    elif contrato.forma_pago == 'TRIMESTRAL':
        intervalo = relativedelta(months=3)
    elif contrato.forma_pago == 'SEMESTRAL':
        intervalo = relativedelta(months=6)
    elif contrato.forma_pago == 'ANUAL':
        intervalo = relativedelta(years=1)

    # Si es 'CONTADO' o no se puede determinar, no se generan facturas periódicas
    if not intervalo:
        return 0

    # Buscar la última factura generada para este contrato
    ultima_factura = Factura.objects.filter(
        Q(contrato_individual=contrato) | Q(contrato_colectivo=contrato)
    ).order_by('-vigencia_recibo_hasta').first()

    fecha_inicio_siguiente_factura = contrato.fecha_inicio_vigencia
    if ultima_factura:
        fecha_inicio_siguiente_factura = ultima_factura.vigencia_recibo_hasta + \
            timedelta(days=1)

    # Comprobar si ya debemos generar la siguiente factura
    # Generamos si la fecha de inicio de la próxima factura ya pasó o es hoy
    if fecha_inicio_siguiente_factura > hoy:
        return 0  # Aún no es tiempo

    fecha_fin_siguiente_factura = fecha_inicio_siguiente_factura + \
        intervalo - timedelta(days=1)

    # No generar facturas más allá de la vigencia del contrato
    if fecha_fin_siguiente_factura > contrato.fecha_fin_vigencia:
        fecha_fin_siguiente_factura = contrato.fecha_fin_vigencia

    # Evitar crear una factura duplicada para el mismo período
    if Factura.objects.filter(
        Q(contrato_individual=contrato) | Q(contrato_colectivo=contrato),
        vigencia_recibo_desde=fecha_inicio_siguiente_factura
    ).exists():
        logger.warning(
            f"Factura para contrato {contrato.numero_contrato} y período desde {fecha_inicio_siguiente_factura} ya existe. Omitiendo.")
        return 0

    # Crear la nueva factura
    try:
        nueva_factura = Factura.objects.create(
            contrato_individual=contrato if isinstance(
                contrato, ContratoIndividual) else None,
            contrato_colectivo=contrato if isinstance(
                contrato, ContratoColectivo) else None,
            monto=contrato.monto_cuota_estimada,
            vigencia_recibo_desde=fecha_inicio_siguiente_factura,
            vigencia_recibo_hasta=fecha_fin_siguiente_factura,
            intermediario=contrato.intermediario,
            estatus_factura='GENERADA'  # O 'PENDIENTE' según tu flujo
        )
        logger.info(
            f"ÉXITO: Factura {nueva_factura.numero_recibo} creada para contrato {contrato.numero_contrato} para el período {fecha_inicio_siguiente_factura} a {fecha_fin_siguiente_factura}.")
        return 1
    except Exception as e:
        logger.error(
            f"Error creando factura para contrato {contrato.numero_contrato}: {e}")
        return 0


@shared_task(name="generar_facturas_periodicas")
def generar_facturas_periodicas_task():
    """
    Tarea principal de Celery que recorre todos los contratos activos
    y genera las facturas que correspondan.
    """
    logger.info(
        "--- INICIANDO TAREA PROGRAMADA: Generación de Facturas Periódicas ---")

    contratos_a_procesar = list(ContratoIndividual.objects.filter(activo=True)) + \
        list(ContratoColectivo.objects.filter(activo=True))

    total_facturas_creadas = 0

    for contrato in contratos_a_procesar:
        with transaction.atomic():
            total_facturas_creadas += generar_facturas_para_contrato(contrato)

    logger.info(
        f"--- TAREA FINALIZADA: Se crearon {total_facturas_creadas} nuevas facturas. ---")
    return f"Se crearon {total_facturas_creadas} nuevas facturas."
