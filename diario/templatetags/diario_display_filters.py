from django import template

register = template.Library()

_MESES_ES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
_DIAS_SEMANA_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


@register.filter
def fecha_es(value):
    if not value:
        return ''
    return f"{value.day} de {_MESES_ES[value.month]} de {value.year}"


@register.filter
def fecha_es_dia(value):
    if not value:
        return ''
    return f"{_DIAS_SEMANA_ES[value.weekday()]}, {value.day} de {_MESES_ES[value.month]}"


@register.filter(name='split')
def split(value, key):
    return str(value).split(key) if value else []


@register.filter(name='trim')
def trim(value):
    return value.strip()


@register.filter
def lookup(dictionary, key):
    if hasattr(dictionary, key):
        return getattr(dictionary, key)
    return dictionary.get(key, '') if hasattr(dictionary, 'get') else ''


@register.filter
def add(value, arg):
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value


@register.filter(name='mul')
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value


@register.filter(name='get_range')
def get_range(value):
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return []
