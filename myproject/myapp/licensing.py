# myapp/licensing.py
import logging
import json
# Asegúrate que timedelta esté si la usas aquí
from datetime import date, datetime, timedelta
from django.utils import timezone  # Para timezone.localdate()
from django.core.exceptions import ValidationError
from django.conf import settings
import nacl.signing
import nacl.encoding

# Asumiendo que LicenseInfo está en el mismo directorio de modelos
# Si está en myapp.models, la importación actual es correcta.
# Si está en otro lugar, ajusta la importación.
from .models import LicenseInfo

logger = logging.getLogger(__name__)  # Usar el logger específico del módulo

MIN_KEY_LENGTH = 16  # Usado por el formulario, por ejemplo
# Longitud mínima para que una clave sea parseable internamente
MIN_EXPECTED_KEY_LENGTH = 50

# Placeholder para la clave pública en settings, si lo usas en tu settings.py real
SMGP_LICENSE_VERIFY_KEY_B64_PLACEHOLDER = "TU_CLAVE_PUBLICA_EN_BASE64_GENERADA_EN_PASO_1"


def _get_verify_key_object():  # Unificada y usada internamente
    """
    Obtiene y valida la clave pública de verificación desde settings.
    Lanza ValidationError si la clave no está configurada o es inválida.
    """
    key_b64 = getattr(settings, 'SMGP_LICENSE_VERIFY_KEY_B64', None)

    # logger.error(f"[DEBUGGING] _get_verify_key_object: Clave leída de settings: {key_b64}") # Log de debug

    if not key_b64 or key_b64 == SMGP_LICENSE_VERIFY_KEY_B64_PLACEHOLDER:
        logger.critical(
            "Clave pública SMGP_LICENSE_VERIFY_KEY_B64 no configurada o es un placeholder. "
            "El sistema de licencias no funcionará."
        )
        # MENSAJE PARA test_07_parse_key_no_public_key_in_settings
        raise ValidationError(
            "Sistema de licencias no operativo (clave pública no configurada).")

    try:
        key_obj = nacl.signing.VerifyKey(key_b64.encode('utf-8'),  # Asegurar encode si es str
                                         encoder=nacl.encoding.Base64Encoder)
        return key_obj
    except Exception as e:  # Captura más general para errores de PyNaCl
        logger.critical(
            f"Error CRÍTICO al cargar/decodificar la clave pública (SMGP_LICENSE_VERIFY_KEY_B64): {type(e).__name__} - {e}.",
            exc_info=True  # Incluir traceback para errores críticos
        )
        # Mensaje si la clave está pero es inválida
        raise ValidationError(
            f"Error al cargar la clave pública de licencia: {e}")


def _get_license_object_from_db():  # Renombrado para evitar confusión con get_license_info
    """Helper para obtener el objeto LicenseInfo de la BD."""
    try:
        return LicenseInfo.objects.get(pk=LicenseInfo.SINGLETON_ID)
    except LicenseInfo.DoesNotExist:
        logger.info(
            "Registro de licencia (ID=%s) no encontrado en la base de datos.", LicenseInfo.SINGLETON_ID)
        return None
    except Exception as e:  # Captura más genérica para problemas de BD inesperados
        logger.error(
            f"Error crítico al acceder a LicenseInfo: {e!r}", exc_info=True)
        return None


def check_license():
    """Verifica si la licencia almacenada en la BD es válida (no expirada)."""
    logger.debug("Realizando chequeo de licencia desde la BD...")
    license_obj = _get_license_object_from_db()

    if not license_obj:
        logger.warning(
            "Chequeo licencia: FALLIDO (Registro de licencia no encontrado en BD)")
        return False

    if not license_obj.license_key or not license_obj.expiry_date:
        logger.error(
            "Chequeo licencia: FALLIDO (Registro de licencia en BD incompleto - falta clave o fecha de expiración)")
        return False

    if not isinstance(license_obj.expiry_date, date):
        logger.error(
            f"Chequeo licencia: FALLIDO (Fecha de expiración almacenada es inválida: {license_obj.expiry_date}, tipo: {type(license_obj.expiry_date)})")
        return False

    if timezone.localdate() <= license_obj.expiry_date:  # Usar timezone.localdate()
        logger.info(
            f"Chequeo licencia: VÁLIDA (Almacenada en BD, Expira: {license_obj.expiry_date.isoformat()})")
        return True
    else:
        logger.warning(
            f"Chequeo licencia: EXPIRADA (Almacenada en BD, Expiró el: {license_obj.expiry_date.isoformat()})")
        return False


# Nombre con guion bajo, consistencia
def _parse_and_validate_license_key(license_key: str):
    """
    Parsea y valida una clave de licencia.
    Retorna (expiry_date, payload_dict) si es válida.
    Lanza ValidationError si es inválida.
    """
    current_verify_key = _get_verify_key_object()  # Llama a la versión unificada
    # La validación de current_verify_key (si es None) ya la hace _get_verify_key_object() lanzando ValidationError

    if not isinstance(license_key, str) or not license_key.startswith("SMGP-"):
        raise ValidationError(
            "Formato de clave inválido (debe comenzar con SMGP-).")

    # MIN_EXPECTED_KEY_LENGTH es para la clave completa "SMGP-..."
    if len(license_key) < MIN_EXPECTED_KEY_LENGTH:
        raise ValidationError(
            f"Formato de clave inválido (longitud de clave insuficiente, se esperan al menos {MIN_EXPECTED_KEY_LENGTH} caracteres).")

    try:
        key_content = license_key[len("SMGP-"):]
        payload_b64, signature_b64 = key_content.split('.', 1)
    except ValueError:
        # MENSAJE PARA test_activate_license_view_post_invalid_key_structure_after_form
        raise ValidationError(
            "Formato de clave inválido (estructura SMGP-Payload.Firma incorrecta).")

    try:
        payload_bytes = nacl.encoding.Base64Encoder.decode(
            payload_b64.encode('utf-8'))
        signature_bytes = nacl.encoding.Base64Encoder.decode(
            signature_b64.encode('utf-8'))

        # logger.debug(f"_parse_and_validate_license_key: Decodificando firma B64: '{signature_b64}'")
        # logger.debug(f"_parse_and_validate_license_key: Firma bytes (hex): {signature_bytes.hex()}")

        current_verify_key.verify(payload_bytes, signature_bytes)

        payload_dict = json.loads(payload_bytes.decode('utf-8'))

        exp_date_str = payload_dict.get("exp")
        activate_by_date_str = payload_dict.get("act_by")

        if not exp_date_str or not activate_by_date_str:
            raise ValidationError(
                "Datos de licencia corruptos (faltan fechas 'exp' o 'act_by' en la clave).")

        final_expiry_date_service = date.fromisoformat(exp_date_str)
        activation_deadline_key = date.fromisoformat(activate_by_date_str)

        if timezone.localdate() > activation_deadline_key:  # Usar timezone.localdate()
            logger.warning(
                f"Intento de activar clave '{license_key[:15]}...' después de su fecha límite ({activation_deadline_key.isoformat()}). Fecha actual: {timezone.localdate().isoformat()}")
            # MENSAJE PARA test_activate_license_view_post_unactivatable_key
            raise ValidationError(
                f"Esta clave de licencia ha caducado para su activación (debía activarse antes del {activation_deadline_key.strftime('%d/%m/%Y')}).")

        logger.info(
            f"Clave verificada y parseada correctamente. Payload: {payload_dict}. Fecha expiración del servicio: {final_expiry_date_service.isoformat()}")
        return final_expiry_date_service, payload_dict

    except nacl.exceptions.BadSignatureError:
        logger.warning(
            f"Firma de licencia INVÁLIDA para la clave: ...{license_key[-20:] if len(license_key) > 20 else license_key}")
        raise ValidationError(
            "Clave de licencia inválida o ha sido manipulada (firma no coincide).")
    except ValidationError:
        raise
    # Errores de parseo, base64, etc.
    except (json.JSONDecodeError, TypeError, ValueError, nacl.exceptions.CryptoError) as e:
        logger.error(
            f"Error decodificando, parseando payload/firma o fechas de la licencia: {type(e).__name__} - {e}", exc_info=True)
        # Este mensaje podría ser el que ve el test de estructura inválida si el error es de base64
        raise ValidationError(
            "Error procesando los datos internos de la clave de licencia (formato incorrecto).")
    except Exception as e:
        logger.error(
            f"Error inesperado en _parse_and_validate_license_key: {type(e).__name__} - {e}", exc_info=True)
        raise ValidationError(
            "Error inesperado al validar la clave de licencia.")


def activate_or_update_license(provided_key: str):
    key_fragment_for_log = f"...{provided_key[-6:]}" if provided_key and len(
        provided_key) >= 6 else 'N/A'
    logger.info(
        f"Intentando activar/actualizar licencia con clave (últimos 6 chars): {key_fragment_for_log}")
    try:
        derived_expiry_date, _ = _parse_and_validate_license_key(provided_key)

        license_obj, created = LicenseInfo.objects.update_or_create(
            pk=LicenseInfo.SINGLETON_ID,
            defaults={
                'license_key': provided_key,
                'expiry_date': derived_expiry_date
            }
        )

        action = "activada" if created else "actualizada"
        # MENSAJE PARA test_activate_license_view_post_valid_key
        msg = f"Licencia {action} exitosamente. Válida hasta: {derived_expiry_date.strftime('%d/%m/%Y')}."
        logger.info(msg + f" (Clave: {key_fragment_for_log})")
        # print(f"DEBUG activate_or_update_license: Devolviendo éxito: '{msg}'") # DEBUG
        return True, msg

    except ValidationError as ve:
        error_message = ve.messages[0] if ve.messages else "Error de validación de clave desconocido."
        logger.warning(
            f"Fallo de validación de clave al activar/actualizar: {error_message} (Clave: {key_fragment_for_log})")
        # print(f"DEBUG activate_or_update_license: Devolviendo error: '{error_message}'") # DEBUG
        return False, error_message
    except Exception as e:
        logger.error(
            f"Error inesperado al guardar/actualizar la licencia en la BD: {type(e).__name__} - {e!r}", exc_info=True)
        return False, "Error interno del servidor al procesar la licencia. Por favor, contacte al soporte."


def get_license_info():
    license_obj = _get_license_object_from_db()
    if license_obj:
        # Llama a check_license para el estado actual
        current_validity_status = check_license()
        return {
            'key': license_obj.license_key,
            'key_fragment': f"...{license_obj.license_key[-6:]}" if license_obj.license_key and len(license_obj.license_key) >= 6 else "N/A",
            'expiry_date': license_obj.expiry_date,
            'is_valid': current_validity_status,
            'last_updated': license_obj.last_updated
        }
    return {'key': None, 'key_fragment': None, 'expiry_date': None, 'is_valid': False, 'last_updated': None}


# Código de inicialización a nivel de módulo
try:
    _initial_verify_key = _get_verify_key_object()
    if _initial_verify_key:
        logger.info(
            "Verificación inicial: Clave pública de licencia cargada y válida al inicio del módulo.")
except ValidationError as e:
    logger.warning(
        f"Verificación inicial: Problema al cargar clave pública: {e.messages[0] if e.messages else e}")
except Exception as e:
    logger.error(
        f"Verificación inicial: Error inesperado al cargar clave pública: {e}", exc_info=True)
