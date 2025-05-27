# myapp/templatetags/querystring_tags.py
from django import template

register = template.Library()  # Es importante tener esta línea


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Updates the current request's query parameters with new values.
    """
    # Asegurarse que 'request' está en el contexto
    if 'request' not in context:
        return ''
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        # Convertir bool a 'true'/'false' string si es necesario, o manejar None
        if isinstance(v, bool):
            query[k] = str(v).lower()
        elif v is None:
            if k in query:  # Eliminar si el valor es None
                del query[k]
        else:
            query[k] = v  # Convertir otros tipos a string si es necesario
    return query.urlencode()


@register.filter
def toggle_order(current_order, default='asc'):
    """ Toggles between 'asc' and 'desc' """
    # Manejar None o string vacío
    if not current_order:
        return 'desc'  # Si no hay orden actual, el siguiente clic ordena descendentemente
    return 'desc' if current_order.lower() == 'asc' else 'asc'
