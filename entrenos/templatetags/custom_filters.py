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
