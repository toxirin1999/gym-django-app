from django import template
from django.template.defaultfilters import stringfilter
import json
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
@stringfilter
def replace(value, arg):
    """
    Reemplaza una subcadena por otra en una cadena de texto.
    Uso: {{ "Hola Mundo"|replace:"Mundo,Planeta" }}
    """
    try:
        old, new = arg.split(',')
        return value.replace(old, new)
    except (ValueError, TypeError):
        return value


@register.filter(name='jsonify')
def jsonify(data):
    """
    Convierte un diccionario de Python a una cadena JSON válida y segura para HTML.
    """
    # json.dumps convierte el objeto de Python en una cadena de texto con formato JSON correcto.
    json_string = json.dumps(data)
    # mark_safe es necesario para que Django no escape las comillas en el HTML.
    return mark_safe(json_string)
# =================================================================
