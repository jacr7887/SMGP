# myapp/validators.py

import logging
import time
import re
from datetime import date, datetime, MAXYEAR, MINYEAR
import mimetypes
from django.core.exceptions import ValidationError
from django.core.cache import cache
from .commons import CommonChoices
from django.utils import timezone as django_timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
try:
    import magic
except ImportError:
    magic = None

logger = logging.getLogger(__name__)

# --- Patrones Regex Ajustados ---
# RIF: Letra(VEJPG)-8Digitos-1Digito. Formato con guiones requerido por el validador.
RIF_PATTERN = r'^[JGVEP]-\d{8}-\d$'  # Formato: X-12345678-9
# <-- CORREGIDO a \d{8}
# Definir el patrón SIN guion y permitiendo 7 u 8 dígitos
CEDULA_PATTERN_PROCESSED = r'^[VE]\d{7,8}$'
# Pasaporte: Genérico Alfanumérico 6-12 chars.
PASAPORTE_PATTERN = r"^[A-Za-z0-9]{6,12}$"
# Contrato: Formato específico de la app.
CONTRATO_PATTERN = r"^CONT-(?:IND|COL)-\d{8}-\d{4}$"
CERTIFICADO_PATTERN = r"^[A-Za-z0-9\-]{5,50}$"
# Email: Estándar razonable.
EMAIL_DOMAIN_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?$'
# Teléfono VE: Fijos (02xx+7) o Móviles (04xx+7).
TELEFONO_VE_PATTERN = r'^(0)?(4(12|14|16|24|26)\d{7}|2\d{9})$'
# Código Postal VE: Exactamente 4 dígitos.
CODIGO_POSTAL_VE_PATTERN = r'^\d{4}$'

# --- Validadores Revisados ---


def validate_rif(rif):
    if rif is None:
        return None
    if not isinstance(rif, str):
        raise ValidationError("El RIF debe ser una cadena de texto.")

    rif_cleaned = rif.strip().upper()

    # Usar el patrón corregido que exige 8 dígitos numéricos
    if not re.match(RIF_PATTERN, rif_cleaned):
        raise ValidationError(
            # Mensaje actualizado
            "Formato RIF inválido. Use Letra-8Números-1Número (Ej: J-12345678-9)."
        )
    return rif  # Devolver original (o rif_cleaned si prefieres)


def validate_cedula(value):
    """
    Valida cédulas venezolanas (V/E) con o sin guion, permitiendo 7 u 8 dígitos.
    Devuelve el valor original si es válido.
    """
    if value is None:
        # Considerar si None es válido o debería lanzar error/default.
        # Por ahora, lo permitimos pasar.
        return None
    if not isinstance(value, str):
        raise ValidationError("Cédula debe ser una cadena de texto.")

    # 1. Limpiar y estandarizar: quitar espacios, a mayúsculas, quitar guion
    cedula_procesada = value.strip().upper().replace('-', '')

    # 2. Validar longitud (debe ser 8 o 9 caracteres: V+7, V+8, E+7, E+8)
    if not (8 <= len(cedula_procesada) <= 9):
        raise ValidationError(
            f"Longitud inválida para cédula '{value}'. Debe tener 7 u 8 dígitos después de V/E."
        )

    # 3. Validar formato con la regex (SIN guion)
    if not re.match(CEDULA_PATTERN_PROCESSED, cedula_procesada):
        # Mensaje de error más claro
        raise ValidationError(
            f"Formato de cédula '{value}' inválido. Debe ser V o E seguido de 7 u 8 dígitos (guion opcional)."
        )

    # Si pasa todas las validaciones, retornar el valor original (con o sin guion, como entró)
    # O podrías retornar `cedula_procesada` si quieres guardar siempre sin guion.
    # Por consistencia con el ejemplo, retornamos el original.
    return value


def validate_pasaporte(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Pasaporte debe ser una cadena de texto.")
    if not re.match(PASAPORTE_PATTERN, value):
        raise ValidationError(
            "Pasaporte debe contener de 6 a 12 caracteres alfanuméricos.")
    return value


def validate_telefono_venezuela(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Teléfono debe ser una cadena de texto.")
    t_cleaned = re.sub(r'[^\d]', '', value)
    t_validate = t_cleaned
    if len(t_cleaned) == 11 and t_cleaned.startswith('0'):
        t_validate = t_cleaned
    elif len(t_cleaned) == 10 and not t_cleaned.startswith('0'):
        t_validate = t_cleaned
    if not re.match(TELEFONO_VE_PATTERN, t_validate):
        raise ValidationError(
            "Formato teléfono inválido. Use 04XX-XXXXXXX o 02XX-XXXXXXX.")
    return value


def validate_telefono_internacional(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Teléfono internacional debe ser cadena.")
    t_cleaned = re.sub(r'[\s\-\(\)]', '', value)
    if not re.fullmatch(r'^\+?\d{10,15}$', t_cleaned):
        raise ValidationError(
            "Formato inválido. Use prefijo '+' si aplica. Ej: +584121234567")
    return value


def validate_email_domain(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Email debe ser cadena.")
    if not re.match(EMAIL_DOMAIN_PATTERN, value):
        raise ValidationError("Correo no tiene formato válido.")
    return value


def validate_codigo_postal_ve(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Código postal debe ser cadena.")
    cp_cleaned = value.strip()
    if not re.match(CODIGO_POSTAL_VE_PATTERN, cp_cleaned):
        raise ValidationError(
            "Código postal inválido. Debe tener 4 dígitos (Ej: 1010).")
    return cp_cleaned


def validate_direccion_ve(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Dirección debe ser cadena.")
    if not value.strip():
        raise ValidationError("Dirección no puede estar vacía.")
    if len(value.strip()) < 10:
        raise ValidationError(
            "Dirección parece demasiado corta (mínimo 10 caracteres).")
    return value


def validate_tipo_empresa(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Tipo empresa debe ser cadena.")
    validos = [c[0] for c in CommonChoices.TIPO_EMPRESA]
    if value.upper() not in validos:
        raise ValidationError(
            f"Tipo empresa inválido. Válidos: {', '.join(validos)}")
    return value.upper()


def validate_positive_decimal(value):
    if value is None:
        return None
    try:
        d_val = Decimal(str(value))
        if d_val <= Decimal('0.00'):
            raise ValidationError("Valor debe ser mayor que cero.")
        return d_val
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Valor debe ser número decimal válido.")


def validate_percentage(value):
    if value is None:
        return None
    try:
        d_val = Decimal(str(value))
        if not (Decimal('0.00') <= d_val <= Decimal('100.00')):
            raise ValidationError("Porcentaje debe estar entre 0 y 100.")
        return d_val
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Porcentaje debe ser número decimal válido.")


def validate_porcentaje_comision(intermediario_instance):
    # *** Mover a Intermediario.clean() ***
    if not hasattr(intermediario_instance, 'porcentaje_comision') or not hasattr(intermediario_instance, 'rif'):
        logger.error(
            "[validate_porcentaje_comision] Instancia sin atributos necesarios.")
        return
    p = intermediario_instance.porcentaje_comision
    rif = intermediario_instance.rif
    if p is not None and p > 10 and not rif:
        raise ValidationError("RIF obligatorio para comisiones > 10%")


def validate_past_date(value):
    if value is None:
        return None
    hoy_fecha = date.today()
    hoy_dt = django_timezone.now()
    if isinstance(value, datetime):
        val_dt = value.astimezone(None).replace(
            tzinfo=None) if value.tzinfo else value
        if val_dt > hoy_dt:
            raise ValidationError("Fecha/hora no puede ser futura.")
    elif isinstance(value, date):
        if value > hoy_fecha:
            raise ValidationError("Fecha no puede ser futura.")
    else:
        raise ValidationError("Tipo fecha inválido para validación pasado.")
    return value


def validate_date_range(start_date, end_date):
    if start_date is None or end_date is None:
        return
    s_date = start_date.date() if isinstance(start_date, datetime) else start_date
    e_date = end_date.date() if isinstance(end_date, datetime) else end_date
    if not isinstance(s_date, date) or not isinstance(e_date, date):
        raise ValidationError(
            "Ambas fechas deben ser válidas para comparar rango.")
    if s_date >= e_date:
        raise ValidationError("Fecha inicio debe ser anterior a fecha fin.")


def validate_fecha_nacimiento(value):
    if value is None:
        return None
    if not isinstance(value, date):
        raise ValidationError("Fecha nacimiento debe ser tipo fecha válido.")
    hoy = date.today()
    if value > hoy:
        raise ValidationError("Fecha nacimiento no puede ser futura.")
    try:
        # Usar datetime.MINYEAR y MAXYEAR si están disponibles
        if not (date(datetime.MINYEAR, 1, 1) <= value <= date(datetime.MAXYEAR, 12, 31)):
            raise ValidationError(
                f"Año de nacimiento fuera del rango soportado.")
    # Manejar si datetime no tiene MINYEAR/MAXYEAR (raro)
    except AttributeError:
        pass
    try:
        edad = hoy.year - value.year - \
            ((hoy.month, hoy.day) < (value.month, value.day))
    except ValueError:
        raise ValidationError("Fecha nacimiento inválida para calcular edad.")
    if edad < 0:
        raise ValidationError("Fecha nacimiento inválida (edad negativa).")
    if edad > 120:
        raise ValidationError("Edad máxima permitida: 120 años.")
    return value


def validate_contrato_vigencia(fecha_inicio, fecha_fin):
    validate_date_range(fecha_inicio, fecha_fin)


def validate_numero_contrato(value):
    """Valida el formato CONT-TIPO-YYYYMMDD-NNNN."""
    if value is None:
        # Permitir None si el modelo lo permite (blank=True, null=True)
        # Si es obligatorio, elimina esta condición o lanza ValidationError aquí
        return None
    if not isinstance(value, str):
        raise ValidationError(
            "Número de contrato debe ser una cadena de texto.")

    valor_limpio = value.strip()  # Quitar espacios al inicio/fin

    logger.debug(
        f"Validando numero_contrato: '{valor_limpio}' (Tipo: {type(valor_limpio)}) contra patrón: '{CONTRATO_PATTERN}'")
    match = re.match(CONTRATO_PATTERN, valor_limpio)

    if not match:
        logger.error(
            f"FALLO validate_numero_contrato: Valor='{valor_limpio}', Patrón='{CONTRATO_PATTERN}'")
        raise ValidationError(
            "Formato número contrato inválido. Debe ser CONT-TIPO-YYYYMMDD-NNNN (ej. CONT-IND-20230101-0001).")
    else:
        # Opcional: Validar la fecha si es necesario (ej. que sea una fecha real)
        # date_part = match.group(2)
        # try:
        #     datetime.strptime(date_part, '%Y%m%d')
        # except ValueError:
        #     raise ValidationError("La parte de la fecha en el número de contrato no es válida.")
        logger.debug(f"ÉXITO validate_numero_contrato para: '{valor_limpio}'")
        return valor_limpio  # Devolver valor limpio si es válido


def validate_certificado(certificado):
    if certificado is None:
        return None
    if not isinstance(certificado, str):
        raise ValidationError("Certificado debe ser cadena.")
    if not re.match(CERTIFICADO_PATTERN, certificado.strip()):
        raise ValidationError("Formato certificado inválido.")
    return certificado.strip()


def validate_afiliado_contrato(afiliado, contrato):
    # *** Mover a Model.clean() o Form.clean() ***
    from myapp.models import ContratoIndividual, ContratoColectivo, AfiliadoIndividual
    if not afiliado or not contrato:
        return
    if not isinstance(afiliado, AfiliadoIndividual):
        raise ValidationError("Tipo 'afiliado' inválido.")
    if isinstance(contrato, ContratoIndividual):
        if afiliado.pk != contrato.afiliado_id:
            raise ValidationError(
                f"Afiliado ({afiliado.pk}) no coincide con CI ({contrato.afiliado_id}).")
    elif isinstance(contrato, ContratoColectivo):
        try:
            if not contrato.afiliados_colectivos.filter(pk=afiliado.pk).exists():
                raise ValidationError(
                    f"Afiliado ({afiliado.pk}) no asociado a CC ({contrato.pk}).")
        except Exception as db_err:
            logger.exception(f"Error BD validando afiliado vs CC: {db_err}")
            raise ValidationError(
                "Error BD validando afiliado vs CC.") from db_err
    else:
        raise ValidationError(
            f"Tipo contrato ({type(contrato).__name__}) no soportado.")


def validate_reclamacion_monto(monto_solicitado, monto_contrato):
    if monto_solicitado is None or monto_contrato is None:
        return
    try:
        m_sol = Decimal(str(monto_solicitado)).quantize(Decimal('0.01'))
        m_cont = Decimal(str(monto_contrato)).quantize(Decimal('0.01'))
        if m_sol > m_cont:
            raise ValidationError(
                f"Monto reclamado ({m_sol}) excede monto del contrato ({m_cont}).")
    except (InvalidOperation, TypeError, ValueError) as e:
        raise ValidationError(
            "Montos deben ser valores numéricos válidos.") from e


def validate_estado_reclamacion(estado_actual, nuevo_estado):
    validos = {"ABIERTA": ["APROBADA", "RECHAZADA", "EN_PROCESO"], "EN_PROCESO": [
        "APROBADA", "RECHAZADA"], "APROBADA": ["PAGADA"], "RECHAZADA": [], "PAGADA": []}
    permitidas = validos.get(estado_actual, [])
    if nuevo_estado != estado_actual and nuevo_estado not in permitidas:
        raise ValidationError(
            f"Transición inválida: '{estado_actual}' a '{nuevo_estado}'. Permitidas: {permitidas}")


def validate_metodo_pago(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Método pago debe ser cadena.")
    if value.upper() not in [c[0] for c in CommonChoices.FORMA_PAGO_RECLAMACION]:
        raise ValidationError(f"Método pago '{value}' inválido.")
    return value.upper()


def validate_monto_pago(monto_pago, monto_referencia):
    if monto_pago is None or monto_referencia is None:
        return
    try:
        m_pag = Decimal(str(monto_pago)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        m_ref = Decimal(str(monto_referencia)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Considerar si la tolerancia es necesaria o debe ser exactamente <=
        if m_pag > m_ref + Decimal('0.01'):
            raise ValidationError(
                f"Monto del pago ({m_pag}) excede el monto de referencia ({m_ref}).")
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Montos deben ser números decimales válidos.")


def validate_monto_pago_factura(monto_pago, monto_factura):
    validate_monto_pago(monto_pago, monto_factura)


def es_tipo_cedula(instance):
    # Asegúrate que los valores 'V', 'E' etc. coincidan con Usuario.TIPO_IDENTIFICACION
    tipo = getattr(instance, 'tipo_identificacion_contratante', None)
    return tipo in ['V', 'E']


def es_tipo_rif(instance):
    # Asegúrate que los valores 'J', 'G' etc. coincidan con Usuario.TIPO_IDENTIFICACION
    tipo = getattr(instance, 'tipo_identificacion_contratante', None)
    return tipo in ['J', 'G']


def validate_file_size(value):
    """
    Valida que el tamaño de un archivo subido no exceda el límite especificado.
    """
    # Verificar si el objeto tiene el atributo 'size' (para evitar errores con None o tipos inesperados)
    if not hasattr(value, 'size'):
        logger.debug(
            "validate_file_size recibió un valor sin atributo 'size'. Saltando validación.")
        return  # No se puede validar si no tiene tamaño

    # --- ¡LÍMITE MODIFICADO! ---
    limit_mb = 50  # Establecer el nuevo límite en Megabytes
    # --------------------------

    # Calcular el límite en bytes
    limit_bytes = limit_mb * 1024 * 1024

    # Comparar el tamaño del archivo con el límite
    if value.size > limit_bytes:
        # Calcular tamaño real en MB para el mensaje de error
        file_size_mb = value.size / (1024 * 1024)
        # Lanzar error de validación con mensaje claro
        raise ValidationError(
            f"El archivo excede el límite de {limit_mb} MB (Tamaño actual: {file_size_mb:.2f} MB)."
        )


# --- validate_file_type MODIFICADO ---
def validate_file_type(value):
    """
    Valida el tipo MIME real de un archivo subido usando python-magic,
    permitiendo más tipos de imagen comunes.
    """
    if magic is None:
        logger.warning(
            "Librería 'python-magic' no encontrada. Saltando validación de tipo MIME.")
        return  # No valida si la librería no está

    # --- ¡LISTA MODIFICADA PARA ACEPTAR MÁS IMÁGENES! ---
    allowed_mimes = [
        'application/pdf',      # PDF (Mantenido)
        'image/jpeg',           # JPG / JPEG
        'image/png',            # PNG
        # --- Tipos de Imagen Adicionales ---
        'image/gif',            # GIF
        'image/bmp',            # BMP
        'image/tiff',           # TIFF / TIF
        'image/webp',           # WebP
        # 'image/svg+xml',      # SVG (Descomentar con precaución)
        # --- Puedes añadir otros tipos aquí si es necesario ---
        # 'application/msword', # .doc
        # 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', # .docx
    ]
    # ----------------------------------------------------

    try:
        # Leer inicio del archivo para detectar MIME type
        initial_pos = value.file.tell()
        value.file.seek(0)
        file_start = value.file.read(2048)  # Buffer razonable
        value.file.seek(initial_pos)

        # Obtener MIME usando python-magic
        mime = magic.from_buffer(file_start, mime=True)
        logger.debug(
            f"Archivo '{value.name}' detectado como tipo MIME: {mime}")

        # Verificar si el MIME está permitido
        if mime not in allowed_mimes:
            # Crear un mensaje de error más legible
            friendly_allowed = []
            mime_map = {  # Mapeo simple para nombres comunes
                'application/pdf': 'PDF', 'image/jpeg': 'JPG/JPEG', 'image/png': 'PNG',
                'image/gif': 'GIF', 'image/bmp': 'BMP', 'image/tiff': 'TIF/TIFF',
                'image/webp': 'WEBP', 'image/svg+xml': 'SVG',
                'application/msword': 'DOC',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
            }
            for allowed in allowed_mimes:
                # Usar mapeo o el MIME si no está
                friendly_allowed.append(mime_map.get(allowed, allowed))

            raise ValidationError(
                f"Tipo de archivo no permitido ('{mime}'). Permitidos: {', '.join(friendly_allowed)}."
            )

    except AttributeError:
        logger.error(
            "validate_file_type recibió un valor inesperado sin atributo 'file'.")
        # Decide cómo manejar esto: ¿error o permitir? Por defecto, no hace nada.
        # raise ValidationError("Error interno validando el archivo.")
        pass
    except Exception as e:
        logger.error(
            f"Error validando tipo de archivo '{getattr(value, 'name', 'N/A')}' con python-magic: {e!r}", exc_info=True)
        # Decide si fallar seguro o permitir si magic da error
        # raise ValidationError("No se pudo verificar el tipo de archivo. Intente de nuevo.")
        pass  # Permite pasar si magic falla, pero loguea el error


class ConditionalValidator:
    # *** RECOMENDACIÓN: Eliminar si no se usa. Mover lógica a Model.clean() o Form.clean() ***
    def __init__(self, validator, condition_func):
        self.validator = validator
        self.condition_func = condition_func

    def __call__(self, instance):
        if self.condition_func(instance):
            pass


def validate_cached_data(cached_data):
    if not isinstance(cached_data, dict):
        return False
    req_keys = ['html', 'generated_at', 'generation_time']
    if not all(k in cached_data for k in req_keys):
        logger.warning("validate_cached_data: Faltan claves.")
        return False
    if not isinstance(cached_data.get('html'), str):
        logger.warning("validate_cached_data: 'html' no string.")
        return False
    return True


def get_cached_graph(force_refresh, cache_key):
    logger.debug(
        f"get_cached_graph: key='{cache_key}', refresh={force_refresh}")
    if not force_refresh:
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                if validate_cached_data(cached_data):
                    logger.info(f"Usando caché válido para '{cache_key}'.")
                    return cached_data
                else:
                    logger.warning(
                        f"Cache inválido para '{cache_key}'. Se procederá a regenerar.")
            else:
                logger.debug(f"Cache miss para '{cache_key}'.")
        except Exception as e:
            logger.exception(
                f"Error accediendo o validando caché para '{cache_key}'.")
    logger.debug(
        f"No se usó caché para '{cache_key}'. Se requiere generación.")
    return None
