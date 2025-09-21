from django import template

register = template.Library()


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
