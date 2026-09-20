from django import template

register = template.Library()


@register.filter(name='con_campo')
def con_campo(items, spec):
    """Filtra una lista de dicts por el valor de un campo.

    Uso en template: {{ lista|con_campo:"tipo:tope,carga" }}
    Devuelve solo los elementos cuyo `campo` coincide con alguno de los
    valores indicados (separados por coma). Nunca lanza excepción: ante
    cualquier entrada inesperada devuelve una lista vacía.
    """
    try:
        campo, valores = spec.split(':', 1)
        valores_set = {v.strip() for v in valores.split(',')}
        return [it for it in items if isinstance(it, dict) and it.get(campo) in valores_set]
    except Exception:
        return []
