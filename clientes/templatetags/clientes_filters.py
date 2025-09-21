from django import template
from decimal import Decimal, InvalidOperation

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


@register.filter(name='humanize_number')
def humanize_number(value):
    """
    Convierte un número grande en un formato legible por humanos.
    Ej: 1234 -> 1.2 K, 1234567 -> 1.2 M
    """
    try:
        value = int(value)
    except (ValueError, TypeError):
        return value

    if value < 1000:
        return str(value)
    elif value < 1000000:
        # Formato K (miles) con un decimal
        return f'{value / 1000:.1f} K'.replace('.0', '')
    elif value < 1000000000:
        # Formato M (millones) con un decimal
        return f'{value / 1000000:.1f} M'.replace('.0', '')
    else:
        # Formato B (billones) con un decimal
        return f'{value / 1000000000:.1f} B'.replace('.0', '')


@register.filter(name='replace_underscore')
def replace_underscore(value):
    """
    Reemplaza los guiones bajos (_) con espacios.
    Uso: {{ mi_string|replace_underscore }}
    """
    return str(value).replace('_', ' ')


@register.filter(name='multiply')
def multiply(value, arg):
    """
    Multiplica el valor por el argumento.
    Uso: {{ mi_valor|multiply:100 }}
    """
    try:
        # Esta parte ya es correcta
        return Decimal(value) * Decimal(arg)
    except (ValueError, TypeError, InvalidOperation):  # Ahora Python sabe qué es InvalidOperation
        return value


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def horas_a_horas_minutos(valor):
    try:
        valor = float(valor)
        horas = int(valor)
        minutos = int(round((valor - horas) * 60))
        return f"{horas}:{minutos:02d}"
    except:
        return "–:–"


@register.filter
def get_attr(obj, attr_name):
    return getattr(obj, attr_name, None)


@register.filter(name='get_severidad_color')
def get_severidad_color(severidad):
    if severidad == 'alta':
        return {'border': 'border-red-500', 'bg': 'bg-red-900/30', 'text': 'text-red-400'}
    elif severidad == 'media':
        return {'border': 'border-yellow-500', 'bg': 'bg-yellow-900/30', 'text': 'text-yellow-400'}
    else:  # baja
        return {'border': 'border-blue-500', 'bg': 'bg-blue-900/30', 'text': 'text-blue-400'}


@register.filter(name='add_class')
def add_class(field, css):
    return field.as_widget(attrs={"class": css})


def attr(obj, attr_name):
    return getattr(obj, attr_name)
