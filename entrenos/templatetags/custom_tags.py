from django import template

register = template.Library()


@register.filter
def dict_get(diccionario, clave):
    try:
        return diccionario.get(clave, 0)
    except (AttributeError, TypeError):
        return 0


@register.filter
def make_range(value):
    try:
        return range(int(value))
    except:
        return range(0)
