# myapp/templatetags/form_filters.py
from django import template

register = template.Library()


@register.filter(name='add_class')
def add_class(field_widget, css_class):
    """Añade una clase CSS a un widget de formulario."""
    return field_widget.as_widget(attrs={'class': css_class})


@register.filter(name='set_placeholder')
def set_placeholder(field_widget, placeholder_text):
    """Establece el placeholder para un widget de formulario."""
    return field_widget.as_widget(attrs={'placeholder': placeholder_text})
