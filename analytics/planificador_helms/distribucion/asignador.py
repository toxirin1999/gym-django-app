# planificador_helms/distribucion/asignador.py
"""
Motor de asignación grupo→día para el planificador Helms.

Aislado de core.py — NO está conectado a producción todavía (X.7, gated).
Función pura determinista: mismo input → mismo output, sin random, sin dicts
sin ordenar antes de iterar.

Algoritmo (6 pasos):
  1. Placements: una entrada por cada sesión que el grupo necesita (calcular_frecuencia).
  2. Orden de prioridad: 1º toques grandes → 1º toques pequeños → 2º → 3º.
     Dentro de cada categoría, alfabético por nombre de grupo.
  3. Capacidad por día: CAPACIDAD_SERIES_DIA (ajustable en config).
  4. Best-fit: colocación greedy con restricciones duras + desempate blando.
  5. Degradación: placements que no caben se descartan. Regla de oro: ningún
     grupo con volumen>0 queda en 0 sesiones — excepción si ocurre.
  6. Fusión: días con pocas series se intentan mover al adyacente con más hueco.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..config import (
    CAPACIDAD_SERIES_DIA,
    GRUPOS_SINERGICOS,
    UMBRAL_FUSION_SESION,
)
from ..distribucion.frecuencia import calcular_frecuencia, cap_sesion_para_grupo


class AsignacionImposibleError(ValueError):
    """
    El motor no puede garantizar ni siquiera 1 sesión a todos los grupos
    con volumen_objetivo > 0 dentro de la capacidad disponible.

    Causas típicas: demasiados grupos para los días disponibles, o
    restricciones estructurales que bloquean todas las opciones.
    """


# ──────────────────────────────────────────────────────────────────────────────
# Estructuras de datos
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class GrupoParaAsignar:
    """
    Descripción de un grupo muscular que el asignador debe colocar en días.

    patron_dominante: resultado de PatronManager.obtener_patron_ejercicio para
        el ejercicio principal del grupo (lo proporciona el caller, no el asignador).
    variante_peso: solo relevante cuando patron_dominante=='bisagra'. Indica si
        el ejercicio principal de isquios/glúteos es 'pesada' (PM, sumo) o 'ligera'
        (RDL, Hip Thrust). Determina la restricción de días adyacentes.
    """
    nombre: str
    volumen_objetivo: int
    mev: int
    es_grande: bool
    patron_dominante: str
    variante_peso: Optional[str] = None  # 'pesada' | 'ligera' | None


@dataclass
class ResultadoAsignacion:
    """Resultado completo del asignador."""
    # dia_key ('dia_1', 'dia_2', ...) → lista ordenada de nombres de grupo
    asignacion: Dict[str, List[str]] = field(default_factory=dict)
    # grupo → número de días efectivamente asignados
    frecuencia_efectiva: Dict[str, int] = field(default_factory=dict)
    # grupos cuya frecuencia se redujo por falta de cabida
    grupos_degradados: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

def _sinergicos_para(nombre: str) -> Set[str]:
    """Devuelve el conjunto de grupos sinérgicos de 'nombre' (sin incluirlo a él)."""
    for grupo_set in GRUPOS_SINERGICOS:
        if nombre in grupo_set:
            return grupo_set - {nombre}
    return set()


def _es_bisagra_pesada(grupo: GrupoParaAsignar) -> bool:
    return (grupo.patron_dominante == 'bisagra'
            and grupo.variante_peso == 'pesada')


def _encontrar_mejor_dia(
    grupo: GrupoParaAsignar,
    num_dias: int,
    dia_series: Dict[int, int],
    dia_grupos: Dict[int, List[str]],
    grupo_dias: Dict[str, List[int]],
    bisagra_pesada_dias: Set[int],
    *,
    ignorar_budget: bool = False,
) -> Optional[int]:
    """
    Devuelve el índice de día (1-based) donde colocar el grupo, o None si no hay
    ninguno válido.

    Restricciones duras (nunca violadas):
      - budget: dia_series[d] + cap ≤ CAPACIDAD_SERIES_DIA  (ignorar_budget lo omite)
      - separación: |d - d_prev| ≥ 2 entre toques del mismo grupo
      - bisagra pesada: si grupo es bisagra pesada y d' ∈ bisagra_pesada_dias → |d-d'| ≠ 1

    Desempate blando (en este orden):
      1. Día con al menos un grupo sinérgico ya colocado
      2. Día con más presupuesto libre
    """
    cap = cap_sesion_para_grupo(grupo.nombre)
    dias_previos = grupo_dias.get(grupo.nombre, [])
    sinergicos = _sinergicos_para(grupo.nombre)
    es_bp = _es_bisagra_pesada(grupo)

    candidatos: List[Tuple[int, int, int]] = []  # (dia, tiene_sinergico, espacio_libre)

    for d in range(1, num_dias + 1):
        # Restricción de separación
        if any(abs(d - dp) < 2 for dp in dias_previos):
            continue

        # Restricción bisagra pesada en días adyacentes
        if es_bp:
            if any(abs(d - bp) == 1 for bp in bisagra_pesada_dias):
                continue

        # Restricción de presupuesto
        if not ignorar_budget:
            if dia_series[d] + cap > CAPACIDAD_SERIES_DIA:
                continue

        tiene_sinergico = int(bool(sinergicos & set(dia_grupos[d])))
        espacio_libre = CAPACIDAD_SERIES_DIA - dia_series[d] - cap

        candidatos.append((d, tiene_sinergico, espacio_libre))

    if not candidatos:
        return None

    # Orden determinista: sinérgico primero, luego más espacio libre, luego índice menor
    candidatos.sort(key=lambda x: (-x[1], -x[2], x[0]))
    return candidatos[0][0]


# ──────────────────────────────────────────────────────────────────────────────
# Función pública principal
# ──────────────────────────────────────────────────────────────────────────────

def asignar_semana(
    grupos: Dict[str, GrupoParaAsignar],
    dias_disponibles: int,
) -> ResultadoAsignacion:
    """
    Asigna grupos musculares a días de la semana de forma greedy y determinista.

    Args:
        grupos:           Mapa nombre→GrupoParaAsignar. Solo se procesan los
                          grupos con volumen_objetivo > 0.
        dias_disponibles: Número de días de entrenamiento en la semana (1-6).

    Returns:
        ResultadoAsignacion con asignacion, frecuencia_efectiva y grupos_degradados.

    Raises:
        AsignacionImposibleError: si la capacidad total de los días es insuficiente
            para garantizar al menos 1 sesión a cada grupo activo, o si un primer
            toque no puede colocarse ni siquiera ignorando el presupuesto.
    """
    # ── Filtrar solo grupos activos ────────────────────────────────────────────
    activos = {
        nombre: g for nombre, g in grupos.items()
        if g.volumen_objetivo > 0
    }

    if not activos:
        return ResultadoAsignacion()

    # ── Pre-check de capacidad estructural ────────────────────────────────────
    # Si la suma mínima de series (1 sesión por grupo) supera el presupuesto
    # total disponible, la asignación es matemáticamente imposible.
    series_minimas = sum(cap_sesion_para_grupo(n) for n in activos)
    capacidad_total = dias_disponibles * CAPACIDAD_SERIES_DIA
    if series_minimas > capacidad_total:
        raise AsignacionImposibleError(
            f"Capacidad insuficiente: se necesitan {series_minimas} series mínimas "
            f"pero solo hay {capacidad_total} disponibles "
            f"({dias_disponibles} días × {CAPACIDAD_SERIES_DIA}). "
            f"Grupos activos: {sorted(activos)}."
        )

    # ── Estado mutable del algoritmo ──────────────────────────────────────────
    # dia_series: series acumuladas por día (1-based)
    dia_series: Dict[int, int] = {d: 0 for d in range(1, dias_disponibles + 1)}
    # dia_grupos: grupos colocados en cada día (en orden de inserción)
    dia_grupos: Dict[int, List[str]] = {d: [] for d in range(1, dias_disponibles + 1)}
    # grupo_dias: días en que cada grupo ha sido colocado
    grupo_dias: Dict[str, List[int]] = {}
    # días con al menos un grupo de bisagra pesada
    bisagra_pesada_dias: Set[int] = set()

    grupos_degradados_set: Set[str] = set()

    # ── Paso 1 + 2: generar placements en orden de prioridad ──────────────────
    # Un "placement" es (grupo, toque_num), donde toque_num ∈ {1, 2, 3}.
    # Orden:
    #   A: 1er toque grandes  (es_grande=True,  toque=1)
    #   B: 1er toque pequeños (es_grande=False, toque=1)
    #   C: 2do toque          (toque=2)
    #   D: 3er toque          (toque=3)
    # Dentro de cada categoría, orden alfabético por nombre de grupo.

    def _categoria(nombre: str, toque: int) -> Tuple[int, str]:
        g = activos[nombre]
        if toque == 1 and g.es_grande:
            return (0, nombre)
        if toque == 1 and not g.es_grande:
            return (1, nombre)
        if toque == 2:
            return (2, nombre)
        return (3, nombre)

    placements: List[Tuple[str, int]] = []
    for nombre in sorted(activos):  # sort garantiza determinismo en el origen
        freq = calcular_frecuencia(nombre, activos[nombre].volumen_objetivo, dias_disponibles)
        for toque in range(1, freq + 1):
            placements.append((nombre, toque))

    placements.sort(key=lambda p: _categoria(p[0], p[1]))

    # ── Pasos 3-5: colocación greedy ─────────────────────────────────────────
    for nombre, toque in placements:
        grupo = activos[nombre]
        cap = cap_sesion_para_grupo(nombre)

        dia = _encontrar_mejor_dia(
            grupo, dias_disponibles,
            dia_series, dia_grupos, grupo_dias, bisagra_pesada_dias,
        )

        if dia is None:
            # Comprobar si es el primer toque (el grupo no tiene sesiones aún)
            if not grupo_dias.get(nombre):
                # Regla de oro: intentar ignorar presupuesto
                dia = _encontrar_mejor_dia(
                    grupo, dias_disponibles,
                    dia_series, dia_grupos, grupo_dias, bisagra_pesada_dias,
                    ignorar_budget=True,
                )
                if dia is None:
                    raise AsignacionImposibleError(
                        f"Imposible colocar el primer toque de '{nombre}': "
                        f"no existe ningún día válido ni ignorando presupuesto. "
                        f"Comprueba restricciones de bisagra o separación."
                    )
                # Forzado con presupuesto excedido — registrar igualmente
            else:
                # Toque no prioritario que no cabe → degradar
                grupos_degradados_set.add(nombre)
                continue

        # Registrar la colocación
        dia_series[dia] += cap
        dia_grupos[dia].append(nombre)
        grupo_dias.setdefault(nombre, []).append(dia)
        if _es_bisagra_pesada(grupo):
            bisagra_pesada_dias.add(dia)

    # ── Paso 6: fusión de sesiones cortas ────────────────────────────────────
    dias_a_fusionar = sorted(
        (d for d in range(1, dias_disponibles + 1)
         if 0 < dia_series[d] < UMBRAL_FUSION_SESION),
        key=lambda d: dia_series[d],  # intentar el más corto primero
    )
    for dia_corto in dias_a_fusionar:
        if dia_series[dia_corto] == 0:
            # Ya fue vaciado en iteración anterior
            continue

        # Candidatos adyacentes (d-1, d+1) con más espacio libre
        adyacentes = [
            d for d in (dia_corto - 1, dia_corto + 1)
            if 1 <= d <= dias_disponibles and d != dia_corto
        ]
        if not adyacentes:
            continue

        adyacentes.sort(
            key=lambda d: -(CAPACIDAD_SERIES_DIA - dia_series[d]),
        )
        destino = adyacentes[0]

        # Verificar que el traslado no viola restricciones
        grupos_a_mover = list(dia_grupos[dia_corto])
        puede_mover = True
        for nombre in grupos_a_mover:
            grupo = activos[nombre]
            cap = cap_sesion_para_grupo(nombre)

            # Presupuesto
            if dia_series[destino] + cap > CAPACIDAD_SERIES_DIA:
                puede_mover = False
                break

            # Separación: otros días del mismo grupo (excluyendo dia_corto)
            otros_dias = [d for d in grupo_dias.get(nombre, []) if d != dia_corto]
            if any(abs(destino - d) < 2 for d in otros_dias):
                puede_mover = False
                break

            # Bisagra pesada
            if _es_bisagra_pesada(grupo):
                bp_otros = bisagra_pesada_dias - {dia_corto}
                if any(abs(destino - bp) == 1 for bp in bp_otros):
                    puede_mover = False
                    break

        if not puede_mover:
            continue

        # Realizar el traslado
        for nombre in grupos_a_mover:
            grupo = activos[nombre]
            cap = cap_sesion_para_grupo(nombre)
            dia_series[destino] += cap
            dia_grupos[destino].append(nombre)
            # Actualizar grupo_dias: quitar dia_corto, añadir destino
            dias_grupo = grupo_dias[nombre]
            dias_grupo[dias_grupo.index(dia_corto)] = destino
            dias_grupo.sort()
            if _es_bisagra_pesada(grupo):
                bisagra_pesada_dias.add(destino)

        # Vaciar el día corto
        dia_series[dia_corto] = 0
        dia_grupos[dia_corto] = []
        if dia_corto in bisagra_pesada_dias:
            # Verificar si sigue habiendo bisagra pesada en ese día (tras vaciarlo)
            bisagra_pesada_dias.discard(dia_corto)

    # ── Construir resultado ───────────────────────────────────────────────────
    asignacion: Dict[str, List[str]] = {}
    for d in range(1, dias_disponibles + 1):
        grupos_dia = dia_grupos[d]
        if grupos_dia:
            asignacion[f'dia_{d}'] = sorted(grupos_dia)

    frecuencia_efectiva: Dict[str, int] = {
        nombre: len(dias) for nombre, dias in grupo_dias.items()
    }
    # Grupos activos con 0 sesiones también deben aparecer (aunque no deberían)
    for nombre in activos:
        if nombre not in frecuencia_efectiva:
            frecuencia_efectiva[nombre] = 0

    return ResultadoAsignacion(
        asignacion=asignacion,
        frecuencia_efectiva=frecuencia_efectiva,
        grupos_degradados=sorted(grupos_degradados_set),
    )
