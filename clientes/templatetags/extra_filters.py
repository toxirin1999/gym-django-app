from django import template

register = template.Library()


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
