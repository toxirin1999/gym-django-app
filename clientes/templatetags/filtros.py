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

@register.filter
def num_es(valor):
    """1.5 -> '1,5'; 3.0 -> '3' (series, coma decimal, 18-nov-2026)."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return valor
    texto = str(int(v)) if v.is_integer() else f'{v:.2f}'.rstrip('0').rstrip('.')
    return texto.replace('.', ',')
