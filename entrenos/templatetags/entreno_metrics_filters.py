from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def absval(value):
    try:
        return abs(float(value))
    except Exception:
        return value


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
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError, InvalidOperation):
        return 0


@register.filter(name='to_float')
def to_float(value):
    try:
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


@register.filter(name='tipo_icono')
def tipo_icono(tipo):
    iconos = {
        'gym': '🏋️', 'hyrox': '⚡', 'carrera': '🏃', 'ciclismo': '🚴',
        'remo': '🚣', 'futbol': '⚽', 'natacion': '🏊', 'yoga': '🧘',
        'estiramientos': '🤸', 'movilidad': '🔄', 'otro': '🎯',
    }
    return iconos.get(tipo, '🎯')
