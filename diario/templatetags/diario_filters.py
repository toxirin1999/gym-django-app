from django import template

register = template.Library()

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
