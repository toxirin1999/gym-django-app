from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    return dictionary.get(key)


register = template.Library()


@register.filter
def make_range(value):
    try:
        return range(int(value))
    except:
        return range(0)


@register.filter
def subtract(value, arg):
    """
    Resta el argumento del valor.
    Uso: {{ mi_numero|subtract:3 }}
    """
    try:
        # Intenta convertir ambos a entero y restar
        return int(value) - int(arg)
    except (ValueError, TypeError):
        # Si falla la conversión, devuelve el valor original sin hacer nada
        return value
