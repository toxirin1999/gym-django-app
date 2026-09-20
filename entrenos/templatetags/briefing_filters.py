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


@register.filter(name='sin_campo')
def sin_campo(items, spec):
    """Filtra una lista de dicts EXCLUYENDO los que coinciden con un campo.

    Uso en template: {{ lista|sin_campo:"tipo:tope,carga" }}
    Es el complementario de con_campo: devuelve los elementos cuyo `campo`
    NO coincide con ninguno de los valores indicados (separados por coma).
    Se usa para saber si a una lista le queda contenido tras excluir los
    elementos que ya se muestran en otra tarjeta (evita imprimir un
    encabezado de sección huerfano sobre una lista vacia). Nunca lanza
    excepcion: ante cualquier entrada inesperada devuelve una lista vacia.
    """
    try:
        campo, valores = spec.split(':', 1)
        valores_set = {v.strip() for v in valores.split(',')}
        return [it for it in items if isinstance(it, dict) and it.get(campo) not in valores_set]
    except Exception:
        return []
