# myapp/tasks.py
"""Módulo avanzado para gestión de caché de gráficos con soporte multi-backend"""
from typing import Optional, Union
from django.core.cache import caches
from django.core.cache.backends.base import BaseCache, InvalidCacheBackendError
import logging
import warnings

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
