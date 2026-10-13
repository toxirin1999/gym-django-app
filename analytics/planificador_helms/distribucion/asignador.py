# planificador_helms/distribucion/asignador.py
"""
Motor de asignación grupo→día para el planificador Helms.

Aislado de core.py — NO está conectado a producción todavía (X.7, gated).
Función pura determinista: mismo input → mismo output, sin random, sin dicts
sin ordenar antes de iterar.

Algoritmo (6 pasos, ejecutados dentro de un bucle de convergencia — ver más abajo):
  1. Placements: una entrada por cada sesión que el grupo necesita (calcular_frecuencia).
  2. Orden de prioridad: 1º toques grandes → 1º toques pequeños → 2º → 3º.
     Dentro de cada categoría, alfabético por nombre de grupo.
  3. Capacidad por día: CAPACIDAD_SERIES_DIA (ajustable en config).
  4. Best-fit: colocación greedy con restricciones duras + desempate blando.
  5. Degradación: placements que no caben se descartan. Regla de oro: ningún
     grupo con volumen>0 queda en 0 sesiones — excepción si ocurre.
  6. Fusión: días con pocas series se intentan mover al adyacente con más hueco.

Bucle de convergencia (coste real vs coste presupuestado):
  `cap_sesion_para_grupo` (10 grandes / 8 pequeños) es un coste FIJO usado para
  decidir qué cabe en cada día durante la colocación. Pero el coste REAL que un
  grupo termina costando en una sesión es ceil(volumen_objetivo / frecuencia
  efectiva) — mayor que el coste fijo cuando el grupo queda degradado (menos
  sesiones de las deseadas, cada sesión restante carga más). Verificado en
  producción: con el coste fijo, un día prometía 36 series y entregaba 44.
  Los pasos 1-5 se ejecutan repetidamente, cada vez con el coste por grupo
  actualizado al coste real de la iteración anterior, hasta que el resultado
  se estabiliza (el coste real ya no cambia) o se agota el límite de
  iteraciones — en cuyo caso se usa el último resultado calculado.
"""

import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Set, Tuple

from ..config import (
    CAPACIDAD_SERIES_DIA,
    GRUPOS_GRANDES,
    GRUPOS_SINERGICOS,
    LIMITES_SERIES_SESION,
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
    # grupo degradado → series semanales que caben respetando el límite por
    # sesión (solo aparecen los grupos degradados): si no caben todas
    # sus sesiones, cada sesión sube como mucho hasta el límite duro (10/8) y
    # el resto del volumen se pierde esa semana en vez de amontonarse.
    volumen_efectivo: Dict[str, int] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

# Día de la semana (0 = lunes) de cada índice de sesión, igual que en
# PlanificadorHelms (core.py). La separación entre toques de un mismo grupo y
# la de bisagras pesadas se mide en días reales, no en índices: con 4 días
# (lun, mar, jue, vie) martes y jueves están a 48 h aunque sus índices sean
# contiguos.
OFFSETS_DIAS_SEMANA = {
    3: [0, 2, 4],
    4: [0, 1, 3, 4],
    5: [0, 1, 2, 3, 4],
    6: [0, 1, 2, 3, 4, 5],
}


def _dist(d1: int, d2: int, num_dias: int) -> int:
    """Días reales entre dos sesiones (1-based) dentro de la semana."""
    offsets = OFFSETS_DIAS_SEMANA.get(num_dias)
    if not offsets or not (1 <= d1 <= len(offsets)) or not (1 <= d2 <= len(offsets)):
        return abs(d1 - d2)
    return abs(offsets[d1 - 1] - offsets[d2 - 1])


def _limite_duro_sesion(nombre: str) -> int:
    clave = 'grupos_grandes' if nombre in GRUPOS_GRANDES else 'grupos_pequenos'
    return LIMITES_SERIES_SESION[clave]['max']


def _coste_sesion(grupo: 'GrupoParaAsignar', freq: int) -> int:
    """Series por sesión con ``freq`` sesiones, sin pasar del límite duro."""
    if freq <= 0:
        return 0
    return min(math.ceil(grupo.volumen_objetivo / freq), _limite_duro_sesion(grupo.nombre))


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
    costo_por_grupo: Dict[str, int],
    *,
    ignorar_budget: bool = False,
    objetivo_dia: Optional[int] = None,
) -> Optional[int]:
    """
    Devuelve el índice de día (1-based) donde colocar el grupo, o None si no hay
    ninguno válido.

    Restricciones duras (nunca violadas):
      - budget: dia_series[d] + cap ≤ CAPACIDAD_SERIES_DIA  (ignorar_budget lo omite)
      - separación: |d - d_prev| ≥ 2 entre toques del mismo grupo
      - bisagra pesada: si grupo es bisagra pesada y d' ∈ bisagra_pesada_dias → |d-d'| ≠ 1

    Desempate blando (en este orden):
      0. Día que, con este grupo, no supera ``objetivo_dia`` (la media de
         series por sesión de la semana). Evita que la preferencia por
         sinérgicos amontone seis grupos en un día y deje otro a medias.
      1. Día con al menos un grupo sinérgico ya colocado
      2. Día con más presupuesto libre

    `costo_por_grupo` es el coste (series) que se asume que este grupo consume
    en una sesión — viene de la iteración de convergencia en `asignar_semana`,
    no siempre es el coste fijo `cap_sesion_para_grupo`.
    """
    cap = costo_por_grupo[grupo.nombre]
    dias_previos = grupo_dias.get(grupo.nombre, [])
    sinergicos = _sinergicos_para(grupo.nombre)
    es_bp = _es_bisagra_pesada(grupo)

    candidatos: List[Tuple[int, int, int, int]] = []  # (dia, sinergico, libre, se_pasa)

    for d in range(1, num_dias + 1):
        # Restricción de separación
        if any(_dist(d, dp, num_dias) < 2 for dp in dias_previos):
            continue

        # Restricción bisagra pesada en días adyacentes
        if es_bp:
            if any(_dist(d, bp, num_dias) == 1 for bp in bisagra_pesada_dias):
                continue

        # Restricción de presupuesto
        if not ignorar_budget:
            if dia_series[d] + cap > CAPACIDAD_SERIES_DIA:
                continue

        tiene_sinergico = int(bool(sinergicos & set(dia_grupos[d])))
        espacio_libre = CAPACIDAD_SERIES_DIA - dia_series[d] - cap

        se_pasa = int(objetivo_dia is not None and dia_series[d] + cap > objetivo_dia)

        candidatos.append((d, tiene_sinergico, espacio_libre, se_pasa))

    if not candidatos:
        return None

    # Orden determinista: sin pasarse de la media, sinérgico, más espacio libre, índice menor
    candidatos.sort(key=lambda x: (x[3], -x[1], -x[2], x[0]))
    return candidatos[0][0]


def _colocar(
    activos: Dict[str, GrupoParaAsignar],
    dias_disponibles: int,
    costo_por_grupo: Dict[str, int],
) -> Tuple[Dict[int, List[str]], Dict[str, List[int]], Dict[int, int], Set[str]]:
    """
    Ejecuta los pasos 1-5 (placements, orden de prioridad, colocación best-fit,
    degradación) usando el coste por grupo indicado. Función pura: no muta
    nada fuera de sus propias estructuras locales, así que se puede volver a
    llamar con costes distintos dentro del bucle de convergencia.

    Devuelve (dia_grupos, grupo_dias, dia_series, grupos_degradados).
    """
    dia_series: Dict[int, int] = {d: 0 for d in range(1, dias_disponibles + 1)}
    dia_grupos: Dict[int, List[str]] = {d: [] for d in range(1, dias_disponibles + 1)}
    grupo_dias: Dict[str, List[int]] = {}
    bisagra_pesada_dias: Set[int] = set()
    grupos_degradados_set: Set[str] = set()

    def _categoria(nombre: str, toque: int) -> Tuple[int, int, str]:
        # Dentro de cada categoría, primero el grupo con más volumen semanal:
        # si un segundo toque no cabe, que se quede sin él quien menos series
        # acumularía en una sola sesión (antes era alfabético y espalda o
        # pecho podían quedarse con 20 series en un día).
        g = activos[nombre]
        if toque == 1 and g.es_grande:
            return (0, -g.volumen_objetivo, nombre)
        if toque == 1 and not g.es_grande:
            return (1, -g.volumen_objetivo, nombre)
        if toque == 2:
            return (2, -g.volumen_objetivo, nombre)
        return (3, -g.volumen_objetivo, nombre)

    placements: List[Tuple[str, int]] = []
    for nombre in sorted(activos):  # sort garantiza determinismo en el origen
        freq = calcular_frecuencia(nombre, activos[nombre].volumen_objetivo, dias_disponibles)
        for toque in range(1, freq + 1):
            placements.append((nombre, toque))

    placements.sort(key=lambda p: _categoria(p[0], p[1]))
    # Media de series por sesión si todo cabe: referencia blanda para repartir.
    objetivo_dia = math.ceil(
        sum(costo_por_grupo[n] for n, _ in placements) / dias_disponibles
    ) if dias_disponibles else None

    for nombre, toque in placements:
        grupo = activos[nombre]
        cap = costo_por_grupo[nombre]

        dia = _encontrar_mejor_dia(
            grupo, dias_disponibles,
            dia_series, dia_grupos, grupo_dias, bisagra_pesada_dias, costo_por_grupo,
            objetivo_dia=objetivo_dia,
        )

        if dia is None:
            # Comprobar si es el primer toque (el grupo no tiene sesiones aún)
            if not grupo_dias.get(nombre):
                # Regla de oro: intentar ignorar presupuesto
                dia = _encontrar_mejor_dia(
                    grupo, dias_disponibles,
                    dia_series, dia_grupos, grupo_dias, bisagra_pesada_dias, costo_por_grupo,
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

    return dia_grupos, grupo_dias, dia_series, grupos_degradados_set


def _equilibrar_dias(
    activos: Dict[str, GrupoParaAsignar],
    dias_disponibles: int,
    costo_por_grupo: Dict[str, int],
    dia_grupos: Dict[int, List[str]],
    grupo_dias: Dict[str, List[int]],
    dia_series: Dict[int, int],
) -> None:
    """Mueve toques del día más cargado a otro válido mientras reduzca el pico."""
    max_movimientos = sum(len(v) for v in grupo_dias.values()) * dias_disponibles
    for _ in range(max_movimientos):
        dia_max = max(range(1, dias_disponibles + 1), key=lambda d: (dia_series[d], -d))
        bp_dias = {
            d for d in range(1, dias_disponibles + 1)
            if any(_es_bisagra_pesada(activos[n]) for n in dia_grupos[d])
        }
        mejor = None  # (nueva_carga_destino, nombre, destino)
        for nombre in sorted(dia_grupos[dia_max]):
            coste = costo_por_grupo[nombre]
            otros = [d for d in grupo_dias[nombre] if d != dia_max]
            es_bp = _es_bisagra_pesada(activos[nombre])
            for d in range(1, dias_disponibles + 1):
                if d == dia_max or d in otros:
                    continue
                if any(_dist(d, dp, dias_disponibles) < 2 for dp in otros):
                    continue
                if es_bp and any(_dist(d, bp, dias_disponibles) == 1 for bp in (bp_dias - {dia_max})):
                    continue
                if dia_series[d] + coste > CAPACIDAD_SERIES_DIA:
                    continue
                # Solo si el destino queda por debajo del pico actual: baja la
                # dispersión sin crear un pico nuevo igual o mayor.
                if dia_series[d] + coste >= dia_series[dia_max]:
                    continue
                candidato = (dia_series[d] + coste, nombre, d)
                if mejor is None or candidato < mejor:
                    mejor = candidato
        if mejor is None:
            return
        _, nombre, destino = mejor
        coste = costo_por_grupo[nombre]
        dia_grupos[dia_max].remove(nombre)
        dia_grupos[destino].append(nombre)
        dia_series[dia_max] -= coste
        dia_series[destino] += coste
        grupo_dias[nombre] = sorted([d for d in grupo_dias[nombre] if d != dia_max] + [destino])


def _colocar_por_patrones(
    activos: Dict[str, GrupoParaAsignar],
    dias_disponibles: int,
) -> Tuple[Dict[int, List[str]], Dict[str, List[int]], Dict[int, int], Set[str], Dict[str, int]]:
    """Coloca cada grupo eligiendo de una vez TODOS sus días (12-oct-2026).

    El greedy por toques sueltos dejaba los segundos toques sin sitio: los
    primeros toques ocupaban días que la separación prohibía después. Aquí,
    para cada grupo (los que piden más sesiones primero, luego más volumen),
    se prueban todas las combinaciones de días válidas para su frecuencia
    deseada y se elige la que deja la semana más equilibrada. Si ninguna cabe,
    se prueba con una sesión menos (cada sesión carga como mucho el límite
    duro por sesión; el volumen que no cabe se pierde esa semana).

    Restricciones duras: presupuesto diario, ≥48 h entre sesiones del mismo
    grupo, bisagras pesadas no en días consecutivos. Desempate: menor pico
    diario, más grupos sinérgicos compartiendo día, menor suma de cuadrados.
    """
    from itertools import combinations

    dia_series: Dict[int, int] = {d: 0 for d in range(1, dias_disponibles + 1)}
    dia_grupos: Dict[int, List[str]] = {d: [] for d in range(1, dias_disponibles + 1)}
    grupo_dias: Dict[str, List[int]] = {}
    coste_final: Dict[str, int] = {}
    degradados: Set[str] = set()
    bp_dias: Set[int] = set()
    dias = list(range(1, dias_disponibles + 1))

    freq_deseada = {
        n: max(1, calcular_frecuencia(n, g.volumen_objetivo, dias_disponibles))
        for n, g in activos.items()
    }
    orden = sorted(activos, key=lambda n: (-freq_deseada[n], -activos[n].volumen_objetivo, n))

    def _valida(combo, es_bp):
        for a, b in combinations(combo, 2):
            if _dist(a, b, dias_disponibles) < 2:
                return False
        if es_bp and any(_dist(d, bp, dias_disponibles) == 1 for d in combo for bp in bp_dias):
            return False
        return True

    for nombre in orden:
        grupo = activos[nombre]
        es_bp = _es_bisagra_pesada(grupo)
        sinergicos = _sinergicos_para(nombre)
        elegido = None
        for freq in range(freq_deseada[nombre], 0, -1):
            coste = _coste_sesion(grupo, freq)
            mejores = []
            for combo in combinations(dias, freq):
                if not _valida(combo, es_bp):
                    continue
                if any(dia_series[d] + coste > CAPACIDAD_SERIES_DIA for d in combo):
                    continue
                cargas = dict(dia_series)
                for d in combo:
                    cargas[d] += coste
                syn = sum(1 for d in combo if sinergicos & set(dia_grupos[d]))
                clave = (max(cargas.values()), -syn, sum(v * v for v in cargas.values()), combo)
                mejores.append((clave, combo, coste))
            if mejores:
                mejores.sort()
                elegido = (mejores[0][1], mejores[0][2], freq)
                break
        if elegido is None:
            # Regla de oro: ningún grupo con volumen se queda fuera. Semana
            # saturada (más series que capacidad): una sesión en el día menos
            # cargado, recortada al hueco que queda (mínimo 2 series). Así el
            # recorte cae en este grupo y no desencadena degradaciones en
            # cascada de los que ya estaban bien colocados.
            candidatos = [d for d in dias if _valida((d,), es_bp)] or dias
            d = min(candidatos, key=lambda x: (dia_series[x], x))
            hueco = CAPACIDAD_SERIES_DIA - dia_series[d]
            coste = max(2, min(_coste_sesion(grupo, 1), hueco))
            elegido = ((d,), coste, 1)
        combo, coste, freq = elegido
        if freq < freq_deseada[nombre]:
            degradados.add(nombre)
        for d in combo:
            dia_series[d] += coste
            dia_grupos[d].append(nombre)
        grupo_dias[nombre] = sorted(combo)
        coste_final[nombre] = coste
        if es_bp:
            bp_dias.update(combo)

    return dia_grupos, grupo_dias, dia_series, degradados, coste_final


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

    # ── Pre-check de capacidad estructural (heurística rápida con coste fijo) ──
    # Si la suma mínima de series (1 sesión por grupo, coste fijo) supera el
    # presupuesto total disponible, la asignación es matemáticamente imposible
    # incluso en el mejor de los casos.
    # Mínimo por grupo con una sola sesión: su volumen, como mucho el límite
    # duro por sesión de GestorFatiga (10 grandes / 8 pequeños). No se usa el
    # tope de reparto (8): ese decide cuántas sesiones conviene, no cuántas
    # series caben como mínimo.
    series_minimas = sum(
        min(g.volumen_objetivo, _limite_duro_sesion(n)) for n, g in activos.items()
    )
    capacidad_total = dias_disponibles * CAPACIDAD_SERIES_DIA
    if series_minimas > capacidad_total:
        raise AsignacionImposibleError(
            f"Capacidad insuficiente: se necesitan {series_minimas} series mínimas "
            f"pero solo hay {capacidad_total} disponibles "
            f"({dias_disponibles} días × {CAPACIDAD_SERIES_DIA}). "
            f"Grupos activos: {sorted(activos)}."
        )

    # ── Semana saturada: recorte proporcional hacia el MEV (12-oct-2026) ──
    # Si la demanda supera lo que cabe (días × presupuesto, con un margen para
    # redondeos), se recorta el volumen de TODOS los grupos en proporción a lo
    # que tienen por encima de su MEV, en vez de dejar que los últimos en
    # colocarse se queden con 4 series o que un día acumule 60.
    volumen_original = {n: g.volumen_objetivo for n, g in activos.items()}
    demanda = sum(volumen_original.values())
    capacidad_util = int(dias_disponibles * CAPACIDAD_SERIES_DIA * 0.92)
    recortados: Set[str] = set()
    if demanda > capacidad_util:
        suma_mev = sum(min(g.mev, g.volumen_objetivo) for g in activos.values())
        exceso = demanda - suma_mev
        k = max(0.0, (capacidad_util - suma_mev) / exceso) if exceso > 0 else 0.0
        nuevos = {}
        for n, g in activos.items():
            base = min(g.mev, g.volumen_objetivo)
            vol = max(1, base + math.floor((g.volumen_objetivo - base) * k))
            if vol < g.volumen_objetivo:
                recortados.add(n)
            nuevos[n] = replace(g, volumen_objetivo=vol)
        activos = nuevos

    # ── Colocación por patrones de días (12-oct-2026) ──────────────────────
    # Sustituye a la colocación greedy por toques (``_colocar``, que se
    # conserva solo como referencia): presupuestaba cada toque con el techo
    # fijo por sesión y colocaba los toques de uno en uno, así que los
    # segundos toques se quedaban sin día y grupos como isquios, glúteos,
    # bíceps o tríceps acababan con 10–20 series en una única sesión. Ahora
    # cada grupo elige todos sus días a la vez, con su coste real por sesión.
    dia_grupos, grupo_dias, dia_series, grupos_degradados_set, costo_por_grupo = _colocar_por_patrones(
        activos, dias_disponibles,
    )
    freq_colocada = {n: len(d) for n, d in grupo_dias.items()}

    # ── Paso 5b: equilibrado (12-oct-2026) ────────────────────────────────────
    # La colocación greedy puede dejar un día con 36 series y otro con 19
    # porque los primeros toques ocupan días que luego la regla de separación
    # prohíbe a los segundos. Se mueven toques sueltos del día más cargado al
    # que más alivia, solo si respetan separación y bisagra y reducen de verdad
    # la diferencia. Termina siempre: cada movimiento baja estrictamente la
    # suma de cuadrados de las cargas diarias.
    _equilibrar_dias(activos, dias_disponibles, costo_por_grupo, dia_grupos, grupo_dias, dia_series)

    # ── Paso 6: fusión de sesiones cortas ────────────────────────────────────
    dias_a_fusionar = sorted(
        (d for d in range(1, dias_disponibles + 1)
         if 0 < dia_series[d] < UMBRAL_FUSION_SESION),
        key=lambda d: dia_series[d],  # intentar el más corto primero
    )
    bisagra_pesada_dias_final: Set[int] = {
        d for d, grupos_dia in dia_grupos.items()
        if any(_es_bisagra_pesada(activos[n]) for n in grupos_dia)
    }
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

        # Presupuesto: el coste TOTAL del lote que se mueve junto, no cada
        # grupo por separado contra el hueco original — si no, dos grupos que
        # individualmente caben pero juntos no, se aceptarían por error.
        costo_total_lote = sum(costo_por_grupo[n] for n in grupos_a_mover)
        puede_mover = (dia_series[destino] + costo_total_lote) <= CAPACIDAD_SERIES_DIA

        for nombre in grupos_a_mover:
            if not puede_mover:
                break
            grupo = activos[nombre]

            # Separación: otros días del mismo grupo (excluyendo dia_corto)
            otros_dias = [d for d in grupo_dias.get(nombre, []) if d != dia_corto]
            if any(_dist(destino, d, dias_disponibles) < 2 for d in otros_dias):
                puede_mover = False
                break

            # Bisagra pesada
            if _es_bisagra_pesada(grupo):
                bp_otros = bisagra_pesada_dias_final - {dia_corto}
                if any(_dist(destino, bp, dias_disponibles) == 1 for bp in bp_otros):
                    puede_mover = False
                    break

        if not puede_mover:
            continue

        # Realizar el traslado
        for nombre in grupos_a_mover:
            grupo = activos[nombre]
            cap = costo_por_grupo[nombre]
            dia_series[destino] += cap
            dia_grupos[destino].append(nombre)
            # Actualizar grupo_dias: quitar dia_corto, añadir destino
            dias_grupo = grupo_dias[nombre]
            dias_grupo[dias_grupo.index(dia_corto)] = destino
            dias_grupo.sort()
            if _es_bisagra_pesada(grupo):
                bisagra_pesada_dias_final.add(destino)

        # Vaciar el día corto
        dia_series[dia_corto] = 0
        dia_grupos[dia_corto] = []
        bisagra_pesada_dias_final.discard(dia_corto)

    # ── Red de seguridad final: el invariante de presupuesto se cumple SIEMPRE ─
    # El bucle de convergencia (coste presupuestado ↔ coste real) puede, en
    # casos raros, oscilar entre dos estados sin estabilizarse antes de
    # max_iteraciones, o la fusión (Paso 6) puede juntar grupos cuyo coste
    # real conjunto no se reevaluó del todo. En vez de confiar en que el
    # proceso anterior fue perfecto, se verifica el resultado FINAL con los
    # costes reales de la asignación que de verdad quedó, y si algún día se
    # pasa, se degrada el grupo que más aporta al exceso (nunca el último de
    # un grupo — regla de oro) hasta que el presupuesto se cumple en todos
    # los días. Esta pasada solo puede reducir series, nunca añadir — termina
    # siempre porque cada iteración quita un placement de un conjunto finito.
    def _costo_real_final(nombre: str) -> int:
        freq_final = len(grupo_dias.get(nombre, []))
        if freq_final <= 0:
            return 0
        if freq_final == freq_colocada.get(nombre):
            return costo_por_grupo[nombre]
        return _coste_sesion(activos[nombre], freq_final)

    for _ in range(sum(len(v) for v in grupo_dias.values()) + 1):
        costos_finales = {n: _costo_real_final(n) for n in activos}
        dia_total_real = {
            d: sum(costos_finales[n] for n in dia_grupos[d])
            for d in range(1, dias_disponibles + 1)
        }
        dias_excedidos = [
            d for d in range(1, dias_disponibles + 1)
            if dia_total_real[d] > CAPACIDAD_SERIES_DIA
        ]
        if not dias_excedidos:
            break

        dia_objetivo = max(dias_excedidos, key=lambda d: dia_total_real[d])
        elegibles = [
            n for n in dia_grupos[dia_objetivo]
            if len(grupo_dias.get(n, [])) > 1
        ]
        if elegibles:
            candidato = max(elegibles, key=lambda n: (costos_finales[n], n))
            dia_grupos[dia_objetivo].remove(candidato)
            grupo_dias[candidato].remove(dia_objetivo)
            grupos_degradados_set.add(candidato)
            continue

        # Nadie es degradable sin romper la regla de oro (todos freq=1 en
        # este día) — probablemente varios grupos degradados de forma
        # independiente coincidieron en el mismo día. Intentar REUBICAR uno
        # a otro día con hueco, en vez de rendirse.
        candidatos_reubicar = sorted(
            dia_grupos[dia_objetivo],
            key=lambda n: (-costos_finales[n], n),
        )
        reubicado = False
        for nombre in candidatos_reubicar:
            grupo = activos[nombre]
            costo = costos_finales[nombre]
            es_bp = _es_bisagra_pesada(grupo)
            otros_dias_nombre = [d for d in grupo_dias.get(nombre, []) if d != dia_objetivo]
            for d in range(1, dias_disponibles + 1):
                if d == dia_objetivo:
                    continue
                # Separación: si el grupo tiene OTRO día (freq>1), el nuevo
                # destino debe seguir respetando la separación ≥1 día completo
                # respecto a ese otro día — reubicar un toque no debe romper
                # la restricción que protege al resto de sus toques.
                if any(_dist(d, dp, dias_disponibles) < 2 for dp in otros_dias_nombre):
                    continue
                if sum(costos_finales[n] for n in dia_grupos[d]) + costo > CAPACIDAD_SERIES_DIA:
                    continue
                if es_bp and any(
                    _dist(d, bp, dias_disponibles) == 1 for bp in (bisagra_pesada_dias_final - {dia_objetivo})
                ):
                    continue
                # Reubicar: sustituir SOLO la entrada dia_objetivo dentro de
                # grupo_dias[nombre] — si el grupo tiene freq>1, sus otros
                # días deben seguir intactos (bug corregido: antes se
                # reemplazaba la lista entera, perdiendo el resto de toques).
                dia_grupos[dia_objetivo].remove(nombre)
                dia_grupos[d].append(nombre)
                grupo_dias[nombre] = sorted(otros_dias_nombre + [d])
                if es_bp:
                    if not any(_es_bisagra_pesada(activos[n]) for n in dia_grupos[dia_objetivo]):
                        bisagra_pesada_dias_final.discard(dia_objetivo)
                    bisagra_pesada_dias_final.add(d)
                reubicado = True
                break
            if reubicado:
                break

        if not reubicado:
            # No hay ningún día con hueco suficiente para absorber el grupo
            # entero (déficit estructural: la demanda semanal total supera la
            # capacidad total disponible — no es un problema de reparto).
            # Repartir el exceso lo más parejo posible en vez de dejarlo todo
            # concentrado: mover al día (no bisagra-incompatible, respetando
            # separación) con el total más bajo, aunque siga quedando por
            # encima del presupuesto, solo si eso reduce de verdad el pico
            # máximo de la semana.
            mejor_dia, mejor_total = None, None
            mejor_nombre = mejor_costo = mejor_bp = None
            for nombre in candidatos_reubicar:
                grupo = activos[nombre]
                costo = costos_finales[nombre]
                es_bp = _es_bisagra_pesada(grupo)
                otros_dias_nombre = [d for d in grupo_dias.get(nombre, []) if d != dia_objetivo]
                for d in range(1, dias_disponibles + 1):
                    if d == dia_objetivo:
                        continue
                    if any(_dist(d, dp, dias_disponibles) < 2 for dp in otros_dias_nombre):
                        continue
                    if es_bp and any(
                        _dist(d, bp, dias_disponibles) == 1 for bp in (bisagra_pesada_dias_final - {dia_objetivo})
                    ):
                        continue
                    total_d = sum(costos_finales[n] for n in dia_grupos[d])
                    if mejor_total is None or total_d < mejor_total:
                        mejor_dia, mejor_total, mejor_nombre, mejor_costo, mejor_bp = (
                            d, total_d, nombre, costo, es_bp,
                        )
            if (
                mejor_dia is not None
                and mejor_total + mejor_costo < dia_total_real[dia_objetivo]
            ):
                otros_dias_mejor = [d for d in grupo_dias.get(mejor_nombre, []) if d != dia_objetivo]
                dia_grupos[dia_objetivo].remove(mejor_nombre)
                dia_grupos[mejor_dia].append(mejor_nombre)
                grupo_dias[mejor_nombre] = sorted(otros_dias_mejor + [mejor_dia])
                if mejor_bp:
                    if not any(_es_bisagra_pesada(activos[n]) for n in dia_grupos[dia_objetivo]):
                        bisagra_pesada_dias_final.discard(dia_objetivo)
                    bisagra_pesada_dias_final.add(mejor_dia)
                reubicado = True

        if not reubicado:
            # No hay ninguna reubicación que mejore el reparto — se acepta
            # el exceso (déficit estructural real: la demanda semanal total
            # supera la capacidad total disponible, no un fallo del algoritmo).
            break

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

    volumen_efectivo: Dict[str, int] = {
        nombre: min(g.volumen_objetivo, _costo_real_final(nombre) * frecuencia_efectiva[nombre])
        for nombre, g in activos.items()
        if nombre in grupos_degradados_set or nombre in recortados
    }

    return ResultadoAsignacion(
        asignacion=asignacion,
        frecuencia_efectiva=frecuencia_efectiva,
        grupos_degradados=sorted(grupos_degradados_set),
        volumen_efectivo=volumen_efectivo,
    )
