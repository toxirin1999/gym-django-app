"""Nombres con los que se enseña un ejercicio (25-oct-2026).

El nombre interno no se cambia (el planificador, el historial y las decisiones
lo usan como clave): solo cómo se lee en pantalla. "Fondos en Paralelas (con
lastre)" en el gimnasio de David es una máquina sentada de discos, y el
"(con lastre)" hacía pensar que el peso incluía el del cuerpo.
"""

ALIAS = {
    'fondos en paralelas (con lastre)': 'Fondos en Máquina (sentado)',
}


def nombre_visible(nombre):
    if not nombre:
        return nombre
    return ALIAS.get(str(nombre).strip().casefold(), nombre)
