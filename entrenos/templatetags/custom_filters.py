from django import template

register = template.Library()


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
