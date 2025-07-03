from django import template
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal

register = template.Library()


@register.simple_tag
def get_factura_estado_actual(factura_obj):
    """
    Recalcula el estado de una factura en tiempo real.
    Devuelve un diccionario con el pendiente y el estado de pagada.
    """
    if not factura_obj:
        return {'monto_pendiente': Decimal('0.00'), 'esta_pagada': False}

    # Consulta fresca a los pagos de esta factura
    total_pagado = factura_obj.pagos.filter(activo=True).aggregate(
        total=Coalesce(Sum('monto_pago'), Value(
            Decimal('0.00')), output_field=DecimalField())
    )['total']

    monto_factura = factura_obj.monto or Decimal('0.00')
    monto_pendiente_actual = max(Decimal('0.00'), monto_factura - total_pagado)

    # Asumo que tienes una constante de tolerancia en tu modelo Factura
    TOLERANCE = getattr(type(factura_obj), 'TOLERANCE', Decimal('0.01'))
    esta_pagada_actual = monto_pendiente_actual <= TOLERANCE

    return {
        'monto_pendiente': monto_pendiente_actual,
        'esta_pagada': esta_pagada_actual,
    }


register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """Permite acceder a un item de un diccionario usando una variable en las plantillas."""
    return dictionary.get(key)


@register.filter(name='split')
def split(value, key):
    """Permite hacer split a un string en la plantilla."""
    return value.split(key)
