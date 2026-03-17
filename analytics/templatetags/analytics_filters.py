from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Obtiene un item de un diccionario por clave.
    Uso: {{ mi_dict|get_item:clave }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
