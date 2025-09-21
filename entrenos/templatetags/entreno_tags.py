from django import template

register = template.Library()


@register.filter
def sum_volumen(series):
    """
    Calcula el volumen total (peso x repeticiones) para una lista de series.
    Versión corregida que redondea a 1 decimal para evitar números excesivamente largos.

    Args:
        series: Lista de objetos serie con atributos peso_kg y repeticiones

    Returns:
        Volumen total redondeado a 1 decimal
    """
    try:
        total = sum(serie.peso_kg * serie.repeticiones for serie in series)
        # Redondear a 1 decimal para evitar números excesivamente largos
        return round(total, 1)
    except (AttributeError, TypeError) as e:
        # Manejar el caso donde series no es iterable o los objetos no tienen los atributos esperados
        return 0
