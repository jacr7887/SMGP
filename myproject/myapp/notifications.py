# myapp/notifications.py
from .models import Notificacion, Usuario
from django.urls import reverse, NoReverseMatch
from django.db.models.query import QuerySet
import logging

logger = logging.getLogger(__name__)  # Se llamará 'myapp.notifications'


def crear_notificacion(usuario_destino, mensaje, tipo='info', url_path_name=None, url_kwargs=None):
    logger.info(
        f"[myapp.notifications.crear_notificacion] Iniciando. Mensaje: '{mensaje[:50]}...', Tipo destino: {type(usuario_destino)}")

    usuarios_a_procesar = []
    if isinstance(usuario_destino, Usuario):
        usuarios_a_procesar.append(usuario_destino)
        logger.debug(
            f"  Caso 1: Destino es instancia Usuario: {usuario_destino.email}")
    elif isinstance(usuario_destino, QuerySet):
        # Convertir QuerySet a lista
        usuarios_a_procesar.extend(list(usuario_destino))
        logger.debug(
            f"  Caso 2: Destino es QuerySet. Cantidad: {len(usuarios_a_procesar)}")
    elif isinstance(usuario_destino, list) and all(isinstance(u, Usuario) for u in usuario_destino):
        usuarios_a_procesar.extend(usuario_destino)
        logger.debug(
            f"  Caso 3: Destino es lista de Usuarios. Cantidad: {len(usuarios_a_procesar)}")
    elif isinstance(usuario_destino, (int, str)):  # Asumir que es un ID
        logger.debug(f"  Caso 4: Destino parece un ID: {usuario_destino}")
        try:
            user_id = int(usuario_destino)
            user = Usuario.objects.get(pk=user_id)
            usuarios_a_procesar.append(user)
            logger.debug(
                f"    Usuario encontrado por ID {user_id}: {user.email}")
        except Usuario.DoesNotExist:
            logger.error(
                f"    Usuario con ID '{usuario_destino}' no existe. No se creará notificación para este ID.")
        except (ValueError, TypeError):
            logger.error(
                f"    ID de usuario '{usuario_destino}' no es un entero válido. No se creará notificación para este ID.")
    else:
        logger.error(
            f"  Tipo de usuario_destino no manejado o inválido: {type(usuario_destino)}. Valor: {str(usuario_destino)[:100]}")
        return []  # Devolver lista vacía si el tipo de destino es incorrecto

    if not usuarios_a_procesar:
        logger.warning(
            "  No hay usuarios válidos para notificar después del procesamiento inicial.")
        return []

    # Filtrar usuarios inactivos si no quieres notificarles (opcional, pero buena práctica)
    usuarios_activos_finales = [u for u in usuarios_a_procesar if u.activo]
    if not usuarios_activos_finales:
        logger.info(
            f"  No quedaron usuarios activos después de filtrar. Usuarios originales: {len(usuarios_a_procesar)}")
        return []

    logger.info(
        f"  Se notificarán {len(usuarios_activos_finales)} usuarios activos.")

    url_final = None
    if url_path_name:
        try:
            url_final = reverse(url_path_name, kwargs=url_kwargs or {})
            logger.debug(f"  URL de destino generada: {url_final}")
        except NoReverseMatch:
            logger.warning(
                f"  No se pudo generar URL para notificación: path='{url_path_name}', kwargs={url_kwargs}. Notificación se creará sin URL.")
        except Exception as e_url:  # Captura otros posibles errores de reverse
            logger.error(
                f"  Error inesperado generando URL: path='{url_path_name}', kwargs={url_kwargs}, Error: {e_url}", exc_info=True)

    notificaciones_creadas_lista = []
    for user_obj in usuarios_activos_finales:
        try:
            if not isinstance(user_obj, Usuario):  # Doble chequeo
                logger.error(
                    f"    Error interno: user_obj no es instancia de Usuario: {type(user_obj)}. Saltando.")
                continue

            notif = Notificacion.objects.create(
                usuario=user_obj,
                mensaje=mensaje[:990],  # Limitar longitud del mensaje
                tipo=tipo,
                # Limitar longitud URL
                url_destino=url_final[:490] if url_final else None
            )
            notificaciones_creadas_lista.append(notif)
            logger.info(
                f"    Notificación PK={notif.pk} CREADA para {user_obj.email} (Tipo: {tipo})")
        except Exception as e_create:
            logger.error(
                f"    Error al crear notificación individual para {getattr(user_obj, 'email', 'Usuario Desconocido')}: {e_create!r}", exc_info=True)

    logger.info(
        f"[myapp.notifications.crear_notificacion] Finalizado. Creadas {len(notificaciones_creadas_lista)} notificaciones.")
    return notificaciones_creadas_lista  # Devolver la lista de objetos creados
