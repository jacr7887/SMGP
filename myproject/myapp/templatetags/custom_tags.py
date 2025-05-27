from django.urls import reverse
from django import template

register = template.Library()


@register.filter
def getattr(obj, attr):
    return getattr(obj, attr)


@register.filter
def get_list_url(model):
    return f'{model._meta.model_name}_list'


@register.filter
def get_update_url(model, pk):
    return f'{model._meta.model_name}_update'


@register.filter
def get_delete_url(model, pk):
    return f'{model._meta.model_name}_delete'


# myapp/templatetags/custom_tags.py

register = template.Library()


@register.simple_tag(takes_context=True)
def sort_arrow(context, field):
    """
    Devuelve flechas de ordenación con estado actual
    Uso: {% sort_arrow 'nombre_campo' %}
    """
    request = context['request']
    current_sort = request.GET.get('sort', '')
    current_direction = request.GET.get('direction', 'asc')

    if current_sort == field:
        return '⬆️' if current_direction == 'asc' else '⬇️'
    return ''


@register.simple_tag
def model_url(model_instance, action):
    """
    Genera URLs CRUD dinámicas
    Uso: {% model_url object 'update' %}
    """
    model_name = model_instance._meta.model_name
    return reverse(f'{model_name}_{action}', args=[model_instance.pk])
