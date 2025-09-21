from django import template
from django.utils import timezone
from datetime import timedelta

# Importamos los modelos con los nombres correctos de tu models.py
# El modelo de misiones se llama 'Quest', no 'Mision'.
from ..models import QuestUsuario, Quest, PerfilGamificacion

# Creamos la instancia de Library UNA SOLA VEZ.
register = template.Library()


# --- FILTROS EXISTENTES ---
@register.filter
def porcentaje(valor, total):
    if total == 0:
        return 0
    return min(100, int((valor / total) * 100))


@register.filter
def add_days(date, days):
    return date + timedelta(days=days)


@register.filter
def timeuntil(date1, date2):
    if not date1 or not date2:
        return ""
    delta = date2 - date1
    days = delta.days
    if days <= 0:
        return "hoy"
    elif days == 1:
        return "1 día"
    else:
        return f"{days} días"


# --- NUEVO SIMPLE TAG (CORREGIDO) ---
@register.simple_tag
def get_progreso_mision(perfil, mision):
    """
    Obtiene el progreso de un usuario en una misión específica y devuelve
    un diccionario con el valor actual, la meta, y el porcentaje.
    """
    # La variable 'mision' que llega aquí es en realidad un objeto 'Quest'.
    # El nombre de la variable no importa, pero el tipo de objeto sí.
    if not isinstance(perfil, PerfilGamificacion):
        return {'valor_actual': 0, 'meta_valor': mision.meta_valor, 'porcentaje': 0}

    try:
        # Usamos el modelo y los campos correctos: QuestUsuario, quest, progreso_actual
        progreso = QuestUsuario.objects.get(perfil=perfil, quest=mision)
        valor_actual = progreso.progreso_actual
    except QuestUsuario.DoesNotExist:
        valor_actual = 0

    meta_valor = mision.meta_valor

    if meta_valor > 0:
        porcentaje = min((valor_actual / meta_valor) * 100, 100)
    else:
        porcentaje = 100 if valor_actual >= meta_valor else 0

    return {
        'valor_actual': valor_actual,
        'meta_valor': meta_valor,
        'porcentaje': int(porcentaje)
    }
