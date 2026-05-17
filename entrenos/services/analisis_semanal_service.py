"""
Gym weekly learning analysis — Phase 5/6/7.

CONTRACT (do not break):
────────────────────────────────────────────────────────────────────────────
1. bloque_semanal_para_joi() NEVER writes to ManualDavid.
   It produces ephemeral context, not persistent identity.

2. estado_semana == 'sin_datos' → bloque_semanal_para_joi() returns None.
   JOI must not receive an empty or placeholder block.

3. The weekly block is recent context, not a stable pattern.
   Language rules:
   - No identity words: "eres", "siempre", "nunca", "tu patrón", "tu identidad"
   - No blame: "fallaste", "fracaso", "incumpliste"
   - Observations use "esta semana", "parece", "puede ser"

4. construir_contexto() must degrade gracefully if this service fails.
   A missing block does not break JOI.

5. One week → signal. Several weeks → observable pattern.
   Only an explicit review converts a pattern into stable narrative.
────────────────────────────────────────────────────────────────────────────
"""

from datetime import timedelta

from django.utils import timezone

from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.sesion_recomendada import calcular_bloque_esencial


def analizar_semana_entrenamiento(cliente, fecha_ref=None):
    """
    Returns a dict with the week's training pattern:
        lunes, domingo (date)
        sesiones_completadas, sesiones_normales, sesiones_esenciales
        sesiones_pospuestas, sesiones_saltadas, sesiones_omitidas
        bloques_principales_completos, bloques_principales_parciales
        porcentaje_principal_medio (int|None)
        porcentaje_opcional_medio (int|None)
        lectura_textual (str)
        hay_datos (bool)
    """
    fecha_ref = fecha_ref or timezone.localdate()
    lunes = fecha_ref - timedelta(days=fecha_ref.weekday())
    domingo = lunes + timedelta(days=6)

    entrenos_semana = list(
        EntrenoRealizado.objects.filter(cliente=cliente, fecha__range=(lunes, domingo))
    )
    sesiones_sp = list(
        SesionProgramada.objects.filter(
            cliente=cliente,
            fecha_prevista__range=(lunes, domingo),
        )
    )

    sesiones_completadas = len(entrenos_semana)
    sesiones_esenciales = sum(1 for e in entrenos_semana if e.modo_reducido)
    sesiones_normales = sesiones_completadas - sesiones_esenciales
    sesiones_saltadas = sum(1 for sp in sesiones_sp if sp.estado == SesionProgramada.ESTADO_SALTADA_USUARIO)
    sesiones_omitidas = sum(1 for sp in sesiones_sp if sp.estado == SesionProgramada.ESTADO_OMITIDA_SISTEMA)
    sesiones_pospuestas = sum(
        1 for sp in sesiones_sp
        if sp.estado == SesionProgramada.ESTADO_PENDIENTE and sp.pospuesta_hasta is not None
    )

    bloques_principales_completos = 0
    bloques_principales_parciales = 0
    pct_principal_list = []
    pct_opcional_list = []

    for entreno in entrenos_semana:
        if entreno.modo_reducido:
            bloque = calcular_bloque_esencial(entreno)
            if bloque:
                if bloque['bloque_principal_completo']:
                    bloques_principales_completos += 1
                else:
                    bloques_principales_parciales += 1
                pct_principal_list.append(bloque['porcentaje_principal'])
                if bloque['opcionales_planificados'] > 0:
                    pct_opcional_list.append(bloque['porcentaje_opcional'])

    pct_principal_medio = (
        round(sum(pct_principal_list) / len(pct_principal_list))
        if pct_principal_list else None
    )
    pct_opcional_medio = (
        round(sum(pct_opcional_list) / len(pct_opcional_list))
        if pct_opcional_list else None
    )

    hay_datos = sesiones_completadas > 0 or sesiones_saltadas > 0 or sesiones_omitidas > 0

    lectura = _generar_lectura(
        sesiones_completadas=sesiones_completadas,
        sesiones_normales=sesiones_normales,
        sesiones_esenciales=sesiones_esenciales,
        sesiones_saltadas=sesiones_saltadas,
        bloques_principales_completos=bloques_principales_completos,
        bloques_principales_parciales=bloques_principales_parciales,
        pct_principal_medio=pct_principal_medio,
        pct_opcional_medio=pct_opcional_medio,
    )

    estado_semana, continuidad, suficiencia, margen = _clasificar_estado(
        sesiones_completadas=sesiones_completadas,
        sesiones_normales=sesiones_normales,
        sesiones_esenciales=sesiones_esenciales,
        bloques_principales_completos=bloques_principales_completos,
        bloques_principales_parciales=bloques_principales_parciales,
        pct_principal_medio=pct_principal_medio,
        pct_opcional_medio=pct_opcional_medio,
    )

    return {
        'lunes': lunes,
        'domingo': domingo,
        'sesiones_completadas': sesiones_completadas,
        'sesiones_normales': sesiones_normales,
        'sesiones_esenciales': sesiones_esenciales,
        'sesiones_pospuestas': sesiones_pospuestas,
        'sesiones_saltadas': sesiones_saltadas,
        'sesiones_omitidas': sesiones_omitidas,
        'bloques_principales_completos': bloques_principales_completos,
        'bloques_principales_parciales': bloques_principales_parciales,
        'porcentaje_principal_medio': pct_principal_medio,
        'porcentaje_opcional_medio': pct_opcional_medio,
        'lectura_textual': lectura,
        'hay_datos': hay_datos,
        # Phase 6 — semantic state for JOI and future learning
        'estado_semana': estado_semana,   # 'solida' | 'carga_alta' | 'margen_extra' | 'parcial' | 'sin_datos'
        'continuidad': continuidad,        # 'alta' | 'media' | 'baja'
        'suficiencia': suficiencia,        # 'completa' | 'parcial'
        'margen': margen,                  # 'alto' | 'medio' | 'bajo'
    }


_LECTURAS_JOI = {
    # (estado_semana, suficiencia) → JOI-appropriate text
    ('carga_alta', 'completa'): 'Esta semana el plan acusó carga, pero lo principal se sostuvo.',
    ('carga_alta', 'parcial'):  'Esta semana la carga desbordó el plan. El bloque principal no se completó del todo.',
    ('margen_extra', 'completa'): 'Esta semana el plan encontró margen: se completó también el volumen accesorio.',
    ('solida', 'completa'):     'Semana sólida: continuidad sin adaptaciones.',
    ('parcial', 'parcial'):     'La semana fue irregular. No todo lo planificado encontró su momento.',
}


def bloque_semanal_para_joi(cliente, fecha_ref=None):
    """
    Returns a compact text block for JOI prompts/context.
    Returns None if there is no relevant data this week.

    CONTRACT:
    - Returns None when estado_semana == 'sin_datos' (no data → no signal → silence).
    - Speaks in weekly observations, never identity claims.
    - NEVER writes to ManualDavid or any persistent store.
    - Maximum ~250 chars so it fits cleanly in prompt context.
    - Call sites must handle None gracefully (no empty section in prompts).
    """
    try:
        analisis = analizar_semana_entrenamiento(cliente, fecha_ref)
    except Exception:
        return None

    if not analisis or not analisis.get('hay_datos'):
        return None

    estado = analisis.get('estado_semana', 'sin_datos')
    if estado == 'sin_datos':
        return None

    suficiencia = analisis.get('suficiencia', 'completa')
    continuidad = analisis.get('continuidad', 'media')
    margen = analisis.get('margen', 'bajo')

    texto_joi = _LECTURAS_JOI.get((estado, suficiencia), analisis.get('lectura_textual', ''))

    sesiones = analisis['sesiones_completadas']
    esenciales = analisis['sesiones_esenciales']
    sesiones_str = f"{sesiones} sesión{'es' if sesiones != 1 else ''}"
    esencial_str = f" ({esenciales} esencial{'es' if esenciales != 1 else ''})" if esenciales else ''

    return (
        f"Gym esta semana: {sesiones_str}{esencial_str}. "
        f"Continuidad: {continuidad}. Suficiencia: {suficiencia}. Margen: {margen}. "
        f"{texto_joi}"
    )


_OBSERVACIONES_PATRON = {
    'margen_bajo_repetido':     'En varias semanas seguidas el margen de los opcionales es bajo. El volumen accesorio puede estar por encima de lo que cabe en tu semana real.',
    'carga_alta_sostenida':     'El plan lleva varias semanas acusando carga. Es una señal de acumulación sostenida, no un evento aislado.',
    'bloque_parcial_repetido':  'El bloque principal no se completó del todo en varias semanas consecutivas. Puede ser señal de que el plan está por encima del margen real de recuperación.',
    'alta_continuidad':         'Varias semanas seguidas con alta continuidad. El plan está encontrando su ritmo.',
    'esenciales_frecuentes':    'Las versiones esenciales se repiten semana a semana. El plan puede estar generando más carga de la que el cuerpo absorbe.',
}

_SUGERENCIAS_PATRON = {
    'margen_bajo_repetido':     'Considerar reducir el volumen accesorio. El patrón sugiere que esa parte del plan no cabe en la semana real.',
    'carga_alta_sostenida':     'No subir cargas esta semana. Mantener la versión esencial disponible. El cuerpo lleva semanas acumulando.',
    'bloque_parcial_repetido':  'Valorar repetir el microciclo actual o reducir la exigencia principal. El bloque no se está completando con regularidad.',
    'alta_continuidad':         'Mantener la estructura actual. El plan está funcionando.',
    'esenciales_frecuentes':    'Revisar si el volumen total encaja con la semana real. Las versiones esenciales se están convirtiendo en la norma.',
}


def _detectar_patrones_activos(semanas_data, umbral):
    """
    Returns a list of pattern keys detected in semanas_data (Phase 7/9 internal helper).
    Centralizes detection so both observation text and suggestions use the same logic.
    """
    patrones = []

    def _cuenta(cond):
        return sum(1 for d in semanas_data if cond(d))

    if _cuenta(lambda d: d.get('margen') == 'bajo') >= umbral:
        patrones.append('margen_bajo_repetido')

    if _cuenta(lambda d: d.get('estado_semana') == 'carga_alta') >= umbral:
        patrones.append('carga_alta_sostenida')

    if _cuenta(lambda d: d.get('bloques_principales_parciales', 0) > 0) >= umbral:
        patrones.append('bloque_parcial_repetido')

    if _cuenta(lambda d: d.get('continuidad') == 'alta') >= umbral:
        patrones.append('alta_continuidad')

    def _ratio_esencial_alto(d):
        total = d.get('sesiones_completadas', 0)
        return total > 0 and (d.get('sesiones_esenciales', 0) / total) >= 0.5

    if _cuenta(_ratio_esencial_alto) >= umbral:
        patrones.append('esenciales_frecuentes')

    return patrones


def _recopilar_semanas(cliente, n_semanas, fecha_ref):
    """Collects weekly analysis data for the last n_semanas with data."""
    semanas = []
    for i in range(n_semanas):
        fecha_semana = fecha_ref - timedelta(weeks=i)
        try:
            datos = analizar_semana_entrenamiento(cliente, fecha_semana)
        except Exception:
            continue
        if datos and datos.get('hay_datos'):
            semanas.append(datos)
    return semanas


def obtener_sugerencia_con_patron(cliente, n_semanas=3, fecha_ref=None):
    """
    Returns {'patron': str, 'texto': str} for the most important detected pattern, or None.
    Used by Phase 10B to create SugerenciaPlan records.
    """
    import math

    fecha_ref = fecha_ref or timezone.localdate()
    umbral = math.ceil(n_semanas / 2)
    semanas_data = _recopilar_semanas(cliente, n_semanas, fecha_ref)

    if len(semanas_data) < 2:
        return None

    patrones = _detectar_patrones_activos(semanas_data, umbral)
    if not patrones:
        return None

    patron = patrones[0]
    texto = _SUGERENCIAS_PATRON.get(patron)
    if not texto:
        return None

    return {'patron': patron, 'texto': texto}


def generar_sugerencia_plan(cliente, n_semanas=3, fecha_ref=None):
    """
    Phase 9 — Non-automatic plan suggestion based on multiweek patterns.

    CONTRACT:
    - Suggests, never applies. The user decides.
    - Returns None if no pattern or insufficient data.
    - One suggestion per call (the most important pattern first).
    - NEVER writes to ManualDavid or changes PlanificadorHelms.
    """
    import math

    fecha_ref = fecha_ref or timezone.localdate()
    umbral = math.ceil(n_semanas / 2)
    semanas_data = _recopilar_semanas(cliente, n_semanas, fecha_ref)

    if len(semanas_data) < 2:
        return None

    patrones = _detectar_patrones_activos(semanas_data, umbral)
    if not patrones:
        return None

    return _SUGERENCIAS_PATRON.get(patrones[0])


def detectar_patron_multisemanal(cliente, n_semanas=3, fecha_ref=None):
    """
    Phase 7 — Multiweek pattern detection (observation text).
    Requires ≥2 weeks with data. Returns None if no pattern.
    NEVER writes to ManualDavid.
    """
    import math

    fecha_ref = fecha_ref or timezone.localdate()
    umbral = math.ceil(n_semanas / 2)
    semanas_data = _recopilar_semanas(cliente, n_semanas, fecha_ref)

    if len(semanas_data) < 2:
        return None

    patrones = _detectar_patrones_activos(semanas_data, umbral)
    if not patrones:
        return None

    observaciones = [_OBSERVACIONES_PATRON[p] for p in patrones if p in _OBSERVACIONES_PATRON]
    if not observaciones:
        return None

    n_con_datos = len(semanas_data)
    return (
        f"[Últimas {n_con_datos} semanas con datos] "
        + " ".join(observaciones[:2])
    )


def _clasificar_estado(
    sesiones_completadas, sesiones_normales, sesiones_esenciales,
    bloques_principales_completos, bloques_principales_parciales,
    pct_principal_medio, pct_opcional_medio,
):
    """
    Returns (estado_semana, continuidad, suficiencia, margen) as semantic labels.
    These feed JOI and future learning layers (Phase 6+).
    """
    if sesiones_completadas == 0:
        return 'sin_datos', 'baja', 'parcial', 'bajo'

    # Estado semana
    if bloques_principales_parciales > 0:
        estado = 'carga_alta'
    elif sesiones_esenciales > 0 and sesiones_normales == 0:
        estado = 'carga_alta'
    elif pct_opcional_medio is not None and pct_opcional_medio >= 75 and sesiones_normales > 0:
        estado = 'margen_extra'
    elif bloques_principales_completos > 0 or sesiones_normales > 0:
        estado = 'solida'
    else:
        estado = 'parcial'

    # Continuidad
    if sesiones_completadas >= 3:
        continuidad = 'alta'
    elif sesiones_completadas == 2:
        continuidad = 'media'
    else:
        continuidad = 'baja'

    # Suficiencia
    if bloques_principales_parciales == 0 and (sesiones_esenciales == 0 or bloques_principales_completos == sesiones_esenciales):
        suficiencia = 'completa'
    else:
        suficiencia = 'parcial'

    # Margen (optional completion as proxy)
    if pct_opcional_medio is not None:
        if pct_opcional_medio >= 75:
            margen = 'alto'
        elif pct_opcional_medio >= 40:
            margen = 'medio'
        else:
            margen = 'bajo'
    elif sesiones_normales > 0:
        margen = 'medio'  # normal sessions completed = some margin existed
    else:
        margen = 'bajo'

    return estado, continuidad, suficiencia, margen


def _pl(n, singular, plural=None):
    """Helper: pluralize based on count."""
    return singular if n == 1 else (plural or singular + 's')


def _generar_lectura(
    sesiones_completadas, sesiones_normales, sesiones_esenciales,
    sesiones_saltadas, bloques_principales_completos, bloques_principales_parciales,
    pct_principal_medio, pct_opcional_medio,
):
    """
    Deterministic narrative. Priority order:
    1. No data
    2. Incomplete principals in esencial sessions (warning)
    3. All esencial, all principals complete (sustained under load)
    4. Mixed normal+esencial, all principals complete
    5. All normal, high optional completion (margin found)
    6. All normal (solid)
    7. Fallback
    """
    if sesiones_completadas == 0:
        if sesiones_saltadas > 0:
            return (
                "Esta semana no se registraron sesiones. "
                "Las que quedaron pendientes ya fueron gestionadas por el sistema."
            )
        return "Todavía no hay sesiones esta semana."

    # Incomplete principals — highest priority warning
    if bloques_principales_parciales > 0:
        return (
            f"En {bloques_principales_parciales} "
            f"{_pl(bloques_principales_parciales, 'sesión', 'sesiones')} "
            "el bloque principal no se completó del todo. "
            "Puede ser señal de carga alta. Conviene observar si se repite la semana siguiente."
        )

    # All esencial, all principals complete
    if sesiones_esenciales > 0 and sesiones_normales == 0:
        return (
            f"Esta semana el cuerpo pidió versión esencial en "
            f"{sesiones_esenciales} "
            f"{_pl(sesiones_esenciales, 'sesión', 'sesiones')}. "
            "El bloque principal se completó en todas. La continuidad sigue intacta."
        )

    # Mixed: some normal, some esencial, all principals complete
    if sesiones_esenciales > 0 and sesiones_normales > 0:
        return (
            f"Semana mixta: {sesiones_normales} "
            f"{_pl(sesiones_normales, 'sesión completa', 'sesiones completas')} "
            f"y {sesiones_esenciales} "
            f"{_pl(sesiones_esenciales, 'esencial', 'esenciales')}. "
            "Los bloques principales se mantuvieron. El plan sigue en dirección."
        )

    # All normal sessions
    if pct_opcional_medio is not None and pct_opcional_medio >= 75:
        return (
            f"Semana completa: {sesiones_completadas} "
            f"{_pl(sesiones_completadas, 'sesión', 'sesiones')} "
            "sin adaptaciones, incluyendo buena parte del bloque accesorio. "
            "El plan encontró margen esta semana."
        )

    return (
        f"Semana completa: {sesiones_completadas} "
        f"{_pl(sesiones_completadas, 'sesión', 'sesiones')} "
        "sin adaptaciones. La continuidad sigue sólida."
    )
