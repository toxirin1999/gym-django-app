from django import template

register = template.Library()

@register.filter
def sum_volumen(series):
    """
    Calcula el volumen total (peso * repeticiones) de una lista de series.
    Redondea el resultado a 1 decimal para evitar números excesivamente largos.
    """
    total = 0
    for serie in series:
        try:
            peso = float(serie.peso_kg) if hasattr(serie, 'peso_kg') else 0
            reps = int(serie.repeticiones) if hasattr(serie, 'repeticiones') else 0
            total += peso * reps
        except (ValueError, TypeError, AttributeError):
            pass
    return round(total, 1)

@register.filter
def subtract(value, arg):
    """
    Resta arg de value.
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def multiply(value, arg):
    """
    Multiplica value por arg.
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """
    Divide value entre arg. Devuelve 0 si arg es 0.
    """
    try:
        arg = float(arg)
        if arg == 0:
            return 0
        return float(value) / arg
    except (ValueError, TypeError):
        return 0
