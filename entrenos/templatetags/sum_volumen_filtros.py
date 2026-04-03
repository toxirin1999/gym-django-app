from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
def subtract(value, arg):
    try:
        return round(float(value) - float(arg), 1)
    except (ValueError, TypeError):
        return ''


@register.filter(name='sum_volumen')
def sum_volumen(ejercicios):
    """
    Calcula el volumen total de una lista de ejercicios (peso * reps * series)
    """
    total = 0
    if not ejercicios:
        return total

    for ej in ejercicios:
        try:
            # Intentar obtener de diccionario o de objeto
            if isinstance(ej, dict):
                peso = float(ej.get('peso', 0) or 0)
                reps = int(ej.get('repeticiones', 0) or 0)
                series = int(ej.get('series', 0) or 0)
            else:
                peso = float(getattr(ej, 'peso', 0) or 0)
                reps = int(getattr(ej, 'repeticiones', 0) or 0)
                series = int(getattr(ej, 'series', 0) or 0)
            total += peso * reps * series
        except (ValueError, TypeError, AttributeError):
            continue
    return total


@register.filter(name='hex_to_rgba')
@stringfilter
def hex_to_rgba(hex_color, alpha):
    """
    Convierte un color HEX (ej: #FF2D92) a un string RGBA (ej: rgba(255, 45, 146, 0.1)).
    """
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return f"rgba(0, 0, 0, {alpha})"

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        return f"rgba({r}, {g}, {b}, {alpha})"
    except Exception:
        return f"rgba(0, 0, 0, {alpha})"


@register.filter
def absval(value):
    try:
        return abs(float(value))
    except Exception:
        return value


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def floatdiv(value, divisor):
    try:
        return float(value) / float(divisor)
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def percent_diff(value, base):
    try:
        return round(((float(value) - float(base)) / float(base)) * 100, 0)
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter(name='mul')
def mul(value, arg):
    """Multiplica el valor por el argumento de forma segura."""
    from decimal import Decimal, InvalidOperation
    try:
        # Intenta convertir ambos a Decimal para mayor precisión con los pesos
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError, InvalidOperation):
        # Si algo falla (ej. el valor no es un número), devuelve 0
        return 0


# Pega esto al final de tu archivo custom_filters.py

@register.filter(name='to_float')
def to_float(value):
    """Convierte un valor a float, reemplazando comas por puntos."""
    try:
        # Reemplaza la coma por un punto y convierte a float
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        # Si falla la conversión, devuelve 0.0
        return 0.0
