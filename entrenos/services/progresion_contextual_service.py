"""
Phase 9.2 — Contextual progression brake.

ARCHITECTURE:
    PlanificadorHelms proposes a weight for each exercise.
    This service decides whether that proposal is authorized.

CONTRACT:
    - evaluar_permiso_progresion() reads weekly/multiweek context, never the plan itself.
    - aplicar_freno_contextual() post-processes the planificador output; does NOT modify
      the planificador internals.
    - 'reducir_accesorios' blocks non-compuesto_principal exercises only.
    - 'mantener_carga' blocks all exercises.
    - Original proposed weights are preserved as peso_kg_propuesto for audit/display.
    - If no weekly data: behavior falls through to planificador defaults (backward compat).
    - Mode esencial completed ≠ permission to auto-progress.

RULE: La progresión automática propone; el contexto del plan autoriza.
"""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# Pattern → action mapping (Phase 9.2)
# 'progresion_permitida' | 'mantener_carga' | 'reducir_accesorios'
_PATRON_A_ACCION = {
    'carga_alta_sostenida':     'mantener_carga',
    'bloque_parcial_repetido':  'mantener_carga',
    'esenciales_frecuentes':    'mantener_carga',
    'margen_bajo_repetido':     'reducir_accesorios',  # only accessories; principals can progress
    'alta_continuidad':         'progresion_permitida',
}

_MENSAJES_PROGRESION = {
    'progresion_permitida':          'Semana con margen. La progresión está autorizada.',
    'mantener_carga':                'El plan frena la subida de cargas esta semana.',
    'reducir_accesorios':            'El volumen accesorio no cabe esta semana. Los ejercicios principales pueden progresar.',
    'modo_reducido':                 'La sesión fue versión esencial. No se aplica progresión automática.',
    'carga_alta_semanal':            'El plan detecta carga alta esta semana (bloque principal incompleto). No se sube peso.',
    'prudencia_semanal':             'El plan operó en modo esencial. La progresión sigue abierta si los patrones lo permiten.',
    'intervencion_no_subir_cargas':  'Intervención activa: decidiste no subir cargas esta semana.',
    'intervencion_reducir_accesorios': 'Intervención activa: decidiste reducir el volumen accesorio esta semana.',
    # Phase 28.1 — per-exercise injury brake
    'lesion_activa':  'Carga mantenida por lesión activa en esta zona.',
    'lesion_retorno': 'Carga mantenida por fase de retorno. La articulación necesita progresión gradual.',
    # Phase Continuidad 1.1 — freno por pausa de entrenamiento
    'retorno_pausa':  'Vienes de una pausa. El plan mantiene cargas y no sube esta sesión: volver con margen, sin compensar de golpe.',
}

# GRUPOS_GRANDES proxy (avoids importing planificador config in tests)
_GRUPOS_GRANDES = {'pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos'}


def evaluar_permiso_progresion(cliente, fecha_ref=None):
    """
    Returns the progression permission for the current week as a dict:
        accion:              'progresion_permitida' | 'mantener_carga' | 'reducir_accesorios'
        motivo:              str (pattern key, weekly state, or 'ok')
        mensaje:             str
        aplica_a_principales: bool  — True if principals are also blocked
        aplica_a_accesorios:  bool  — True if accessories are blocked
        hay_datos_semana:    bool
    """
    fecha_ref = fecha_ref or timezone.localdate()

    try:
        # Phase 10C: explicit user intervention takes precedence over pattern detection
        try:
            from entrenos.services.sugerencias_service import get_intervencion_activa
            from entrenos.models import IntervencionPlan
            intervencion = get_intervencion_activa(cliente, fecha_ref)
            if intervencion:
                accion = (
                    'mantener_carga' if intervencion.tipo == IntervencionPlan.TIPO_NO_SUBIR
                    else 'reducir_accesorios'
                )
                return _permiso(accion, f'intervencion_{intervencion.tipo}', hay_datos=True)
        except Exception:
            pass  # degrade silently

        # Phase Continuidad 1.1: una pausa de entrenamiento (≥6 días sin gym)
        # congela la subida de cargas — prudencia física por duración. La
        # intervención explícita del usuario (arriba) manda sobre la pausa; la
        # lesión se aplica por-ejercicio en aplicar_freno_contextual (encima).
        try:
            from core.continuidad import evaluar_continuidad_entrenamiento
            cont = evaluar_continuidad_entrenamiento(cliente, fecha_ref=fecha_ref)
            if cont.get('congelar_progresion'):
                return _permiso('mantener_carga', 'retorno_pausa', hay_datos=True)
        except Exception:
            pass  # degrade silently

        from entrenos.services.analisis_semanal_service import (
            analizar_semana_entrenamiento,
            _detectar_patrones_activos,
            _recopilar_semanas,
        )
        import math

        semana = analizar_semana_entrenamiento(cliente, fecha_ref)
        hay_datos = semana.get('hay_datos', False) if semana else False

        if not hay_datos:
            return _permiso('progresion_permitida', 'ok', hay_datos=False)

        # Weekly state takes priority
        estado = semana.get('estado_semana', 'sin_datos')
        if estado == 'carga_alta':
            return _permiso('mantener_carga', 'carga_alta_semanal', hay_datos=True)
        if estado == 'prudencia_semanal':
            # Plan activated esencial mode; no physiological overload evidence → allow progression
            pass
        if estado == 'margen_extra':
            return _permiso('progresion_permitida', 'ok', hay_datos=True)

        # Multiweek patterns
        semanas_data = _recopilar_semanas(cliente, 3, fecha_ref)
        if len(semanas_data) >= 2:
            umbral = math.ceil(3 / 2)
            patrones = _detectar_patrones_activos(semanas_data, umbral)
            for patron in patrones:
                accion = _PATRON_A_ACCION.get(patron)
                if accion and accion != 'progresion_permitida':
                    return _permiso(accion, patron, hay_datos=True)

        return _permiso('progresion_permitida', 'ok', hay_datos=True)

    except Exception:
        logger.exception('evaluar_permiso_progresion: error para cliente %s', cliente.id)
        return _permiso('progresion_permitida', 'ok', hay_datos=False)


def _permiso(accion, motivo, hay_datos=True):
    return {
        'accion': accion,
        'motivo': motivo,
        'mensaje': _MENSAJES_PROGRESION.get(motivo, _MENSAJES_PROGRESION.get(accion, '')),
        'aplica_a_principales': accion == 'mantener_carga',
        'aplica_a_accesorios': accion in ('mantener_carga', 'reducir_accesorios'),
        'hay_datos_semana': hay_datos,
    }


def _es_ejercicio_principal(ejercicio):
    """True if this exercise is a structural compound in a main muscle group."""
    return (
        ejercicio.get('tipo_ejercicio') == 'compuesto_principal'
        and ejercicio.get('grupo_muscular', '').lower() in _GRUPOS_GRANDES
    )


def _obtener_peso_actual(cliente, nombre_ejercicio):
    """
    Returns the last logged weight for this exercise (before any proposed progression).
    Used to revert weight when progression is blocked.
    """
    try:
        from entrenos.models import EjercicioRealizado
        ej = (
            EjercicioRealizado.objects
            .filter(
                entreno__cliente=cliente,
                nombre_ejercicio__icontains=nombre_ejercicio[:18],
                completado=True,
            )
            .order_by('-entreno__fecha', '-id')
            .first()
        )
        return float(ej.peso_kg) if ej and ej.peso_kg else None
    except Exception:
        return None


def _peso_congelado(peso_actual, peso_propuesto):
    """
    El freno es un techo, no una sustitución: nunca debe subir el peso por
    encima de lo que el plan ya proponía para hoy. Si el plan ya bajó (p.ej.
    por RPE alto o recalibración), esa bajada se respeta.
    """
    if peso_actual is None:
        return peso_propuesto
    if peso_propuesto is None:
        return peso_actual
    return min(peso_actual, peso_propuesto)


def aplicar_freno_contextual(cliente, entrenamiento, permiso, modo_reducido=False):
    """
    Post-processes planificador exercise list to apply the progression brake.

    Each exercise gets:
        progresion_bloqueada: bool
        motivo_bloqueo: str | None
        peso_kg_propuesto: float | None  (original planificador weight, for audit)

    When blocked:
        peso_kg is replaced with the last actual logged weight (or kept if not found).

    Args:
        permiso: result of evaluar_permiso_progresion()
        modo_reducido: True if the session being generated comes from a pending esencial session
    """
    if not entrenamiento or not entrenamiento.get('ejercicios'):
        return entrenamiento

    accion = permiso.get('accion', 'progresion_permitida')
    motivo = permiso.get('motivo', 'ok')

    # Mode esencial completed → always freeze (regardless of other signals)
    if modo_reducido:
        accion = 'mantener_carga'
        motivo = 'modo_reducido'

    if accion == 'progresion_permitida':
        # Annotate as permitted, no weight change
        for ej in entrenamiento['ejercicios']:
            ej['progresion_bloqueada'] = False
            ej['motivo_bloqueo'] = None
            ej['peso_kg_propuesto'] = None
        return entrenamiento

    ejercicios_modificados = []
    for ej in entrenamiento['ejercicios']:
        ej_mod = dict(ej)
        es_principal = _es_ejercicio_principal(ej)

        bloqueado = (
            accion == 'mantener_carga'
            or (accion == 'reducir_accesorios' and not es_principal)
        )

        if bloqueado:
            peso_propuesto = ej_mod.get('peso_kg')
            peso_actual = _obtener_peso_actual(cliente, ej_mod.get('nombre', ''))
            ej_mod['peso_kg_propuesto'] = peso_propuesto
            ej_mod['peso_kg'] = _peso_congelado(peso_actual, peso_propuesto)
            ej_mod['progresion_bloqueada'] = True
            ej_mod['motivo_bloqueo'] = motivo
            # Phase 11.1: track the origin of optional treatment
            if accion == 'reducir_accesorios' and not es_principal:
                ej_mod['origen_opcional'] = 'intervencion_reducir_accesorios'
        else:
            ej_mod['progresion_bloqueada'] = False
            ej_mod['motivo_bloqueo'] = None
            ej_mod['peso_kg_propuesto'] = None
            ej_mod['origen_opcional'] = None

        ejercicios_modificados.append(ej_mod)

    entrenamiento = dict(entrenamiento)
    entrenamiento['ejercicios'] = ejercicios_modificados
    entrenamiento['permiso_progresion'] = permiso
    return entrenamiento


# ── Phase 28.1 — Per-exercise injury brake ────────────────────────────────────

def _obtener_info_lesion(cliente):
    """Returns [{tags, motivo, fase, zona}] for active injuries with restricted tags."""
    try:
        from hyrox.models import UserInjury
        result = []
        for lesion in UserInjury.objects.filter(cliente=cliente, activa=True).exclude(fase='RECUPERADO'):
            tags = set(lesion.tags_restringidos or [])
            if not tags:
                continue
            motivo = (
                'lesion_activa' if lesion.fase in ('AGUDA', 'SUB_AGUDA')
                else 'lesion_retorno'
            )
            result.append({'tags': tags, 'motivo': motivo, 'fase': lesion.fase, 'zona': lesion.zona_afectada})
        return result
    except Exception:
        return []


def aplicar_freno_lesion(cliente, entrenamiento):
    """
    Phase 28.1 — Per-exercise progression brake based on active injuries.

    CONTRACT:
    - Only acts on exercises whose risk_tags intersect with an injury's tags_restringidos.
    - Does NOT change exercises already blocked by aplicar_freno_contextual.
    - Does NOT substitute exercises. Does NOT change the session structure.
    - AGUDA/SUB_AGUDA → motivo_bloqueo = 'lesion_activa'
    - RETORNO         → motivo_bloqueo = 'lesion_retorno'
    - Sets motivo_bloqueo_lesion=True for UI to distinguish from contextual brake.
    - Preserves peso_kg_propuesto for audit.
    - If no last logged weight found, keeps the proposed weight (no increase implied).
    """
    if not entrenamiento or not entrenamiento.get('ejercicios'):
        return entrenamiento

    info_lesiones = _obtener_info_lesion(cliente)
    if not info_lesiones:
        return entrenamiento

    ejercicios_modificados = []
    for ej in entrenamiento['ejercicios']:
        ej_mod = dict(ej)

        # Respect contextual brake — don't overwrite its decision
        if ej_mod.get('progresion_bloqueada'):
            ejercicios_modificados.append(ej_mod)
            continue

        ej_tags = set(ej_mod.get('risk_tags') or [])

        matched = False
        for info in info_lesiones:
            if not (ej_tags & info['tags']):
                continue
            # Intersection found — freeze this exercise
            peso_propuesto = ej_mod.get('peso_kg')
            peso_actual = _obtener_peso_actual(cliente, ej_mod.get('nombre', ''))
            ej_mod['peso_kg_propuesto'] = peso_propuesto
            ej_mod['peso_kg'] = _peso_congelado(peso_actual, peso_propuesto)
            ej_mod['progresion_bloqueada'] = True
            ej_mod['motivo_bloqueo'] = info['motivo']
            ej_mod['motivo_bloqueo_lesion'] = True
            matched = True
            break  # first matching injury is sufficient

        if not matched:
            ej_mod.setdefault('progresion_bloqueada', False)
            ej_mod.setdefault('motivo_bloqueo', None)
            ej_mod.setdefault('motivo_bloqueo_lesion', False)

        ejercicios_modificados.append(ej_mod)

    entrenamiento = dict(entrenamiento)
    entrenamiento['ejercicios'] = ejercicios_modificados
    return entrenamiento
