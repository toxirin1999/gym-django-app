from django import template

register = template.Library()


@register.filter
def duracion_a_horas_minutos(value):
    if value is None:
        return "0:00"
    try:
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}:{minutes:02d}"
    except:
        return "0:00"
