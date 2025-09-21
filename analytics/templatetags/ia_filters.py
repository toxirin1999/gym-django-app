# analytics/templatetags/ia_filters.py

import json
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()


@register.filter(name='ia_jsonify')
def ia_jsonify(data):
    """
    Convierte de forma segura un objeto de Python a una cadena JSON,
    escapando caracteres para que sea seguro dentro de un atributo HTML.
    """
    if data is None:
        return ''

    # Convertimos el diccionario a una cadena JSON
    json_string = json.dumps(data)

    # Escapamos la cadena para que sea segura en HTML (convierte comillas, etc.)
    escaped_json = escape(json_string)

    return mark_safe(escaped_json)
