# diario/templatetags/custom_filters.py

from django import template

register = template.Library()


@register.filter(name='split')
def split(value, key):
    """
    Devuelve la lista de cadenas de texto divididas por 'key'.
    Uso en plantilla: {{ some_string|split:"," }}
    """
    # Asegurarse de que el valor es un string antes de hacer split
    if value:
        return str(value).split(key)
    return []


@register.filter(name='trim')
def trim(value):
    """
    Elimina los espacios en blanco al principio y al final de una cadena.
    """
    return value.strip()


@register.filter
def lookup(dictionary, key):
    """Filtro para acceder a valores dinámicos en templates"""
    if hasattr(dictionary, key):
        return getattr(dictionary, key)
    return dictionary.get(key, '') if hasattr(dictionary, 'get') else ''


@register.filter
def add(value, arg):
    """Filtro para sumar valores"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def get_item(dictionary, key):
    """Obtener item de diccionario"""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key, '')
    return ''


@register.filter(name='mul')
def mul(value, arg):
    """
    Filtro para multiplicar un valor por un argumento en la plantilla.
    Uso: {{ valor|mul:5 }}
    """
    try:
        # Intenta convertir ambos a float para permitir decimales
        return float(value) * float(arg)
    except (ValueError, TypeError):
        # Si la conversión falla, devuelve el valor original o una cadena vacía
        try:
            return value
        except:
            return ''


@register.filter(name='get_range')
def get_range(value):
    """
    Filtro para crear un rango de números.
    Uso: {{ 5|get_range }} -> [0, 1, 2, 3, 4]
    """
    try:
        num = int(value)
        return range(num)
    except (ValueError, TypeError):
        return []
