"""La misma sesión aunque se escriba distinto (2-nov-2026).

El plan llama a la sesión «Dia 1 - Descarga Activa» y la de hoy se guardó como
«Día 1 - Descarga Activa»: comparando el texto tal cual, la cola de la semana
no la daba por hecha y el martes volvía a proponer el Día 1. Para comparar
nombres de sesión: sin tildes, sin mayúsculas, con los guiones iguales y los
espacios colapsados.
"""

import unicodedata


def clave_rutina(nombre):
    if not nombre:
        return ''
    texto = ''.join(
        c for c in unicodedata.normalize('NFKD', str(nombre)) if not unicodedata.combining(c)
    )
    for raya in ('—', '–', '‒', '―'):
        texto = texto.replace(raya, '-')
    return ' '.join(texto.casefold().split())
