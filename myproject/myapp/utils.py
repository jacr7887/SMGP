# utils.py

import html
from datetime import date
from django.core.exceptions import ValidationError
import logging
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from .models import Tarifa
from .commons import CommonChoices  # Importar choices

logger = logging.getLogger(__name__)


def calcular_edad(fecha_nacimiento):
    """
    Calcula la edad basada en la fecha de nacimiento.

    Args:
        fecha_nacimiento (date): La fecha de nacimiento.

    Returns:
        int: La edad calculada.
    """
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year - \
        ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return edad


def validar_fecha_nacimiento(fecha_nacimiento):
    """
    Valida que la fecha de nacimiento no sea futura y no sea anterior a una fecha mínima.

    Args:
        fecha_nacimiento (date): La fecha de nacimiento a validar.

    Raises:
        ValidationError: Si la fecha de nacimiento es futura o anterior a la fecha mínima permitida.
    """
    hoy = date.today()
    fecha_minima = date(1900, 1, 1)
    if fecha_nacimiento < fecha_minima:
        raise ValidationError(
            ("La fecha de nacimiento es demasiado antigua."))
    if fecha_nacimiento > hoy:
        raise ValidationError(("La fecha de nacimiento no puede ser futura."))


def obtener_rango_etario(fecha_nacimiento):
    """
    Obtiene el rango etario basado en la fecha de nacimiento.

    Args:
        fecha_nacimiento (date): La fecha de nacimiento.

    Returns:
        str: El rango etario correspondiente.
    """
    edad = calcular_edad(fecha_nacimiento)
    if edad < 18:
        return ("Menor de edad")
    elif 18 <= edad <= 30:
        return ("18-30 años")
    elif 31 <= edad <= 50:
        return ("31-50 años")
    elif 51 <= edad <= 65:
        return ("51-65 años")
    else:
        return ("Más de 65 años")


def obtener_estado_civil_descripcion(estado_civil_codigo):
    """
    Obtiene la descripción del estado civil basado en el código.

    Args:
        estado_civil_codigo (str): El código del estado civil.

    Returns:
        str: La descripción del estado civil.
    """
    opciones = {
        'S': ("Soltero/a"),
        'C': ("Casado/a"),
        'D': ("Divorciado/a"),
        'V': ("Viudo/a"),
        'O': ("Otro"),
    }
    return opciones.get(estado_civil_codigo, ("Desconocido"))


def obtener_tipo_identificacion_descripcion(tipo_identificacion_codigo):
    """
    Obtiene la descripción del tipo de identificación basado en el código.

    Args:
        tipo_identificacion_codigo (str): El código del tipo de identificación.

    Returns:
        str: La descripción del tipo de identificación.
    """
    opciones = {
        'CEDULA': ("Cédula de Identidad"),
        'PASAPORTE': ("Pasaporte"),
        'RIF': ("Registro de Información Fiscal"),
        'NIT': ("Número de Identificación Tributaria"),
    }
    return opciones.get(tipo_identificacion_codigo, ("Desconocido"))


def obtener_estado_contrato_descripcion(estado_contrato_codigo):
    """
    Obtiene la descripción del estado del contrato basado en el código.

    Args:
        estado_contrato_codigo (str): El código del estado del contrato.

    Returns:
        str: La descripción del estado del contrato.
    """
    opciones = {
        'VIGENTE': ("Vigente"),
        'VENCIDO': ("Vencido"),
        'PENDIENTE': ("Pendiente"),
        'INACTIVO': ("Inactivo"),
        'ANULADO': ("Anulado"),
    }
    return opciones.get(estado_contrato_codigo, ("Desconocido"))


def sanitize_value(value):
    """Sanitiza valores para evitar inyecciones en CSV."""
    if isinstance(value, str):
        # Prevenir inyección de fórmulas en Excel
        if value.startswith(('=', '+', '-', '@')):
            return f"'{value}"
        # Escapar caracteres especiales
        return html.escape(value)
    return str(value) if value is not None else ""


def get_tarifa_aplicable(ramo, fecha_ref, edad=None, forma_pago=None):
    """
    Busca la tarifa más reciente aplicable según los criterios.
    """
    if not ramo or not fecha_ref:
        return None

    logger.debug(
        f"Buscando tarifa: Ramo={ramo}, FechaRef={fecha_ref}, Edad={edad}, FormaPago={forma_pago}")

    tarifas_candidatas = Tarifa.objects.filter(
        ramo=ramo,
        activo=True,
        fecha_aplicacion__lte=fecha_ref
    ).order_by('-fecha_aplicacion')  # Más reciente primero

    if not tarifas_candidatas.exists():
        logger.warning(
            f"No hay tarifas candidatas para Ramo={ramo}, FechaRef<={fecha_ref}")
        return None

    # --- Filtrado por Edad (si aplica) ---
    tarifas_por_edad = []
    if edad is not None:
        for tarifa in tarifas_candidatas:
            rango = tarifa.rango_etario  # Ej: '18-25', '66+'
            if not rango:
                continue  # Saltar tarifas sin rango si se busca por edad

            try:
                # Manejar rangos con '+' o rangos numéricos
                if '+' in rango:
                    min_edad = int(rango.replace('+', '').strip())
                    if edad >= min_edad:
                        tarifas_por_edad.append(tarifa)
                elif '-' in rango:
                    min_edad_str, max_edad_str = rango.split('-')
                    min_edad = int(min_edad_str.strip())
                    max_edad = int(max_edad_str.strip())
                    if min_edad <= edad <= max_edad:
                        tarifas_por_edad.append(tarifa)
                # Podrías añadir manejo para otros formatos si existen
            except (ValueError, TypeError):
                logger.warning(
                    f"Error parseando rango etario '{rango}' para tarifa {tarifa.pk}")
                continue  # Ignorar rango inválido

        if not tarifas_por_edad:
            logger.warning(
                f"No se encontraron tarifas para edad {edad} (Ramo={ramo}, FechaRef={fecha_ref})")
            # ¿Debería retornar None o seguir buscando sin filtro de edad?
            # Por ahora, si se especificó edad y no se encontró, retornamos None
            # return None
            # --- CORRECCIÓN: Si no hay por edad, probemos sin filtro edad ---
            logger.debug(
                "No se encontró tarifa específica por edad, buscando tarifa general para el ramo/fecha...")
            tarifas_candidatas = tarifas_candidatas.filter(
                rango_etario__isnull=True)  # Buscar sin rango etario
            if not tarifas_candidatas.exists():
                logger.warning(
                    f"Tampoco se encontraron tarifas generales (sin rango etario) para Ramo={ramo}, FechaRef<={fecha_ref}")
                return None
            # Si hay tarifas generales, continuamos con ellas
        else:
            tarifas_candidatas = tarifas_por_edad  # Usar las encontradas por edad
            logger.debug(
                f"Encontradas {len(tarifas_candidatas)} tarifas por edad.")

    else:
        # Si no se busca por edad (ej. colectivo), podríamos priorizar tarifas sin rango etario
        # o usar todas las candidatas. Por simplicidad, usamos todas por ahora.
        logger.debug("Búsqueda sin filtro de edad.")
        # Podríamos filtrar aquí por rango_etario=None si las tarifas generales son explícitas
        # tarifas_candidatas = tarifas_candidatas.filter(rango_etario__isnull=True)

    # --- Filtrado por Forma de Pago (Opcional) ---
    # Busca primero una tarifa específica para la forma de pago
    tarifa_encontrada = None
    if forma_pago:
        tarifa_especifica = next(
            (t for t in tarifas_candidatas if t.tipo_fraccionamiento == forma_pago), None)
        if tarifa_especifica:
            logger.debug(
                f"Encontrada tarifa específica para forma de pago '{forma_pago}'.")
            tarifa_encontrada = tarifa_especifica

    # Si no hay específica para la forma de pago, busca la anual (tipo_fraccionamiento es None o 'ANUAL')
    if not tarifa_encontrada:
        tarifa_anual = next(
            (t for t in tarifas_candidatas if t.tipo_fraccionamiento is None or t.tipo_fraccionamiento == 'ANUAL'), None)
        if tarifa_anual:
            logger.debug("Encontrada tarifa base anual.")
            tarifa_encontrada = tarifa_anual
        elif not tarifa_encontrada and forma_pago and len(tarifas_candidatas) > 0:
            # Fallback: Si se pidió forma_pago, no hay específica, no hay anual, pero SÍ hay candidatas, usar la más reciente aunque no coincida fraccionamiento?
            # Esto es una decisión de negocio. Por seguridad, si se pidió fraccionamiento y no se halló ni específica ni anual, retornamos None.
            logger.warning(
                f"Se buscó con forma_pago='{forma_pago}', pero no se encontró tarifa específica ni anual.")
            return None
        elif not tarifa_encontrada and len(tarifas_candidatas) > 0:
            # Si no se pidió forma de pago y no hay anual, usar la más reciente disponible
            logger.debug(
                "No se encontró tarifa anual explícita, usando la candidata más reciente.")
            # Ya están ordenadas por fecha desc
            tarifa_encontrada = tarifas_candidatas[0]

    if tarifa_encontrada:
        logger.info(
            f"Tarifa aplicable encontrada: ID={tarifa_encontrada.pk}, Ramo={tarifa_encontrada.ramo}, Rango={tarifa_encontrada.rango_etario}, FechaApp={tarifa_encontrada.fecha_aplicacion}, Fracc={tarifa_encontrada.tipo_fraccionamiento}")
    else:
        logger.warning(
            "No se encontró ninguna tarifa aplicable después de todos los filtros.")

    return tarifa_encontrada
