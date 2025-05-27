from django import template

register = template.Library()


@register.simple_tag
def sort_arrow(field, current_sort):
    if field == current_sort:
        return " ▲"  # Flecha hacia arriba si el campo está ordenado ascendentemente
    else:
        return " ▼"  # Flecha hacia abajo si el campo está ordenado descendentemente
