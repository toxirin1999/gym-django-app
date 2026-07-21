# planificador_helms/ejercicios/variacion.py
"""
Variación intra-semanal: rep_range/RPE por toque y selección de ejercicios
distintos para los toques 2 y 3 de un grupo muscular en la misma semana.

Módulo puro — sin I/O, sin Django, sin acceso a BD.
Recibe todo por parámetro y devuelve datos; cero efectos secundarios.
"""

from typing import Any

from ..config import (
    REP_RANGE_TOQUE,
    ROL_TOQUE,
    KEYWORDS_VERTICAL,
    KEYWORDS_HORIZONTAL,
)
from ..utils.helpers import extraer_nombre_ejercicio


def derivar_rep_rpe_toque(
    rep_range_base: str,
    rpe_objetivo: int,
    toque: int,
) -> tuple[str, int]:
    """
    Devuelve (rep_range, rpe) ajustados para el toque indicado.

    Toque 1: identidad exacta, (rep_range_base, rpe_objetivo) sin cambio.
    Toque ≥2: rep_range sube un peldaño (más reps) según REP_RANGE_TOQUE;
              RPE = max(6, rpe_objetivo - 1) — contraste moderado, suelo en 6.
    Clave ausente en la tabla: devuelve rep_range_base (fallback seguro,
    nunca lanza excepción por rangos no contemplados).
    """
    if toque == 1:
        return (rep_range_base, rpe_objetivo)

    remapeo = REP_RANGE_TOQUE.get(toque, {})
    nuevo_rep_range = remapeo.get(rep_range_base, rep_range_base)
    nuevo_rpe = max(6, rpe_objetivo - 1)
    return (nuevo_rep_range, nuevo_rpe)


def _nombre_lower(ej: Any) -> str:
    return extraer_nombre_ejercicio(ej).strip().lower()


def _es_vertical(nombre: str) -> bool:
    return any(k in nombre for k in KEYWORDS_VERTICAL)


def _es_horizontal(nombre: str) -> bool:
    return any(k in nombre for k in KEYWORDS_HORIZONTAL)


def _asegurar_oposicion_espalda(seleccion: list, disponibles: list) -> list:
    """
    Garantiza que la selección de 2 ejercicios de espalda tenga 1 vertical
    y 1 horizontal. Si la selección natural ya lo cumple, la devuelve intacta.
    Si no, busca una pareja válida en disponibles (ya filtrados por exclusión
    de nombres). Si el pool no permite la oposición, devuelve la selección
    tal cual — nunca lanza excepción.
    """
    vert = [e for e in seleccion if _es_vertical(_nombre_lower(e))]
    horiz = [e for e in seleccion if _es_horizontal(_nombre_lower(e))]
    if vert and horiz:
        return seleccion

    all_vert = [e for e in disponibles if _es_vertical(_nombre_lower(e))]
    all_horiz = [e for e in disponibles if _es_horizontal(_nombre_lower(e))]
    if all_vert and all_horiz:
        return [all_vert[0], all_horiz[0]]

    return seleccion


def construir_variantes_por_toque(
    grupo: str,
    frecuencia: int,
    es_grande: bool,
    pool_seguro: dict,
    ejercicios_toque1: list,
) -> dict[int, list]:
    """
    Construye la selección de ejercicios para cada toque semanal de un grupo.

    Args:
        grupo: nombre del grupo muscular.
        frecuencia: cuántas veces por semana aparece el grupo (1, 2 o 3).
        es_grande: True si el grupo pertenece a GRUPOS_GRANDES.
        pool_seguro: dict con claves 'compuesto_principal', 'compuesto_secundario',
                     'aislamiento' — ejercicios ya filtrados por seguridad biológica.
        ejercicios_toque1: lista de dicts ya elegidos para el toque 1; no se modifica.

    Returns:
        Dict {toque: [lista de ejercicios]}, claves 1..frecuencia.
        El toque 1 es exactamente ejercicios_toque1, sin copiar ni modificar.

    Garantías:
        - Toque 1 byte-idéntico a ejercicios_toque1.
        - Cada toque ≥2 excluye por nombre (case-insensitive) los ejercicios
          de todos los toques anteriores.
        - Dentro de los candidatos disponibles, prioriza el perfil_preferido
          del rol (sin descartar los demás si no alcanza el número necesario).
        - Fallback: si el pool queda insuficiente, rellena con los ejercicios
          de toque 1 (nunca lista más corta, nunca vacía si toque1 no lo era).
        - Espalda con 2 ejercicios: fuerza oposición vertical/horizontal si el
          pool lo permite; si no, continúa sin levantar excepción.
    """
    resultado: dict[int, list] = {1: ejercicios_toque1}
    n_needed = len(ejercicios_toque1)

    for toque in range(2, frecuencia + 1):
        rol = ROL_TOQUE[toque]
        perfil_preferido = rol['perfil_preferido']
        orden_categoria = rol['orden_categoria']

        # Candidatos concatenados en el orden de categoría del rol
        candidatos: list[Any] = []
        for cat in orden_categoria:
            candidatos.extend(pool_seguro.get(cat, []))

        # Nombres ya usados en toques anteriores (comparación normalizada)
        nombres_usados: set[str] = set()
        for t in range(1, toque):
            for ej in resultado[t]:
                nombres_usados.add(_nombre_lower(ej))

        # Filtrar por exclusión de nombres
        disponibles = [
            ej for ej in candidatos
            if _nombre_lower(ej) not in nombres_usados
        ]

        # Priorizar perfil preferido: los que lo tienen van primero,
        # el resto se añade a continuación (no se descarta ninguno).
        if perfil_preferido:
            con_perfil = [ej for ej in disponibles if ej.get('perfil') == perfil_preferido]
            sin_perfil = [ej for ej in disponibles if ej.get('perfil') != perfil_preferido]
            disponibles = con_perfil + sin_perfil

        seleccion = list(disponibles[:n_needed])

        # Espalda: garantizar oposición vertical/horizontal si hay 2 ejercicios
        if grupo == 'espalda' and n_needed == 2 and len(seleccion) == 2:
            seleccion = _asegurar_oposicion_espalda(seleccion, disponibles)

        # Fallback: pool insuficiente → completar con ejercicios de toque 1
        while len(seleccion) < n_needed:
            idx = len(seleccion)
            seleccion.append(ejercicios_toque1[idx])

        resultado[toque] = seleccion

    return resultado
