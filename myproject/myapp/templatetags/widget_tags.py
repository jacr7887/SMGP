# myapp/templatetags/widget_tags.py
from django import template
# Importar para una comprobación más robusta
from django.forms import CheckboxSelectMultiple

register = template.Library()


@register.filter(name='widget_type')
def widget_type(bound_field):
    """
    Devuelve el nombre de la clase del widget del campo en minúsculas.
    Ejemplo de uso: {% if field.field.widget|widget_type == "checkboxselectmultiple" %}
    """
    if hasattr(bound_field, 'field') and hasattr(bound_field.field, 'widget'):
        return bound_field.field.widget.__class__.__name__.lower()
    return ''


@register.filter(name='is_checkboxselectmultiple')
def is_checkboxselectmultiple(bound_field):
    """
    Verifica si el widget del campo es una instancia de CheckboxSelectMultiple.
    Ejemplo de uso: {% if field|is_checkboxselectmultiple %}
    """
    if hasattr(bound_field, 'field') and hasattr(bound_field.field, 'widget'):
        return isinstance(bound_field.field.widget, CheckboxSelectMultiple)
    return False
