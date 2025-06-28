# myapp/templatetags/querystring_tags.py

from django import template
from django.utils.http import urlencode

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """
    Permite manipular los parámetros GET de la URL actual de forma segura.
    Esta versión es robusta y no falla si 'request' no está en el contexto,
    lo cual es crucial para que las páginas de error 500 no se rompan.
    """
    # Intenta obtener el objeto request del contexto.
    # Si no existe (ej. en una página de error 500), usa un diccionario vacío.
    request = context.get('request')
    if request:
        query_params = request.GET.copy()
    else:
        # Si no hay request, no podemos saber los parámetros actuales.
        # Empezamos con un diccionario vacío.
        query_params = {}

    # Itera sobre los argumentos que nos pasaron al llamar el tag
    for key, value in kwargs.items():
        # Si el valor es None, elimina ese parámetro de la URL
        if value is None:
            query_params.pop(key, None)  # pop de forma segura
        else:
            # Si no, añade o actualiza el parámetro
            query_params[key] = str(value)  # Convertir a string para seguridad

    # Codifica los parámetros de nuevo en un string de URL.
    # El método 'urlencode' se asegura de que todo esté correctamente escapado.
    return urlencode(query_params)
