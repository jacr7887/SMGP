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
