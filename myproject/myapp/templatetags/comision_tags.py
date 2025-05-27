from django import template

register = template.Library()


@register.filter
def filter_has_override(comisiones_queryset):
    if not comisiones_queryset:
        return False
    for comision in comisiones_queryset:
        if comision.tipo_comision == 'OVERRIDE':
            return True
    return False
