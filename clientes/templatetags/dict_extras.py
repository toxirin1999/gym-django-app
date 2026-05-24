from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    return d.get(key)


@register.filter
def get_item(dictionary, key):
    """Accede a un valor de diccionario por clave dinámica en templates.

    Uso: {{ mi_dict|get_item:clave }}
    Devuelve None si el diccionario es None o si la clave no existe.
    """
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except AttributeError:
        return None
