from django import template

register = template.Library()


@register.filter
def floatval(value):
    try:
        return float(value)
    except:
        return 0


@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except:
        return 0
