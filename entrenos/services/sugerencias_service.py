"""
Phase 10B — Plan suggestion management.

CONTRACT:
- get_sugerencia_activa() returns the current SugerenciaPlan for display (creates lazily).
- An ignored suggestion respects COOLDOWN_DIAS before reappearing.
- Accepting a suggestion does NOT auto-modify the plan. The user decides what to do.
- The plan can propose, but must know when to be silent.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from entrenos.models import IntervencionPlan, SugerenciaPlan

logger = logging.getLogger(__name__)


def get_sugerencia_activa(cliente, fecha_ref=None):
    """
    Returns the SugerenciaPlan to display today, or None if:
    - No pattern detected this week.
    - The suggestion was recently ignored (cooldown active).
    - The suggestion was discarded.

    Creates a new SugerenciaPlan(pendiente) lazily if a pattern is detected and none exists.
    """
    fecha_ref = fecha_ref or timezone.localdate()

    try:
        from entrenos.services.analisis_semanal_service import obtener_sugerencia_con_patron
        sugerencia_datos = obtener_sugerencia_con_patron(cliente, fecha_ref=fecha_ref)
    except Exception:
        logger.exception('get_sugerencia_activa: error generating suggestion')
        return None

    if not sugerencia_datos:
        return None

    patron = sugerencia_datos['patron']
    texto = sugerencia_datos['texto']

    # Check for an existing record for this pattern
    existente = (
        SugerenciaPlan.objects
        .filter(cliente=cliente, patron=patron)
        .order_by('-fecha_generada')
        .first()
    )

    if existente:
        if existente.estado == SugerenciaPlan.ESTADO_DESCARTADA:
            return None  # permanently dismissed

        if existente.estado == SugerenciaPlan.ESTADO_IGNORADA:
            if existente.cooldown_hasta and existente.cooldown_hasta > fecha_ref:
                return None  # still in cooldown
            # Cooldown expired — reset to pendiente for re-display
            existente.estado = SugerenciaPlan.ESTADO_PENDIENTE
            existente.cooldown_hasta = None
            existente.save(update_fields=['estado', 'cooldown_hasta'])
            return existente

        if existente.estado in (SugerenciaPlan.ESTADO_ACEPTADA, SugerenciaPlan.ESTADO_APLICADA):
            return None  # already acted on this week

        return existente  # estado == pendiente

    # No record exists — create one
    try:
        return SugerenciaPlan.objects.create(
            cliente=cliente,
            patron=patron,
            texto=texto,
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
    except Exception:
        logger.exception('get_sugerencia_activa: error creating SugerenciaPlan')
        return None


def ignorar_sugerencia(sugerencia):
    """
    User chose "Ignorar por ahora".
    The suggestion won't reappear for COOLDOWN_DIAS days.
    """
    sugerencia.estado = SugerenciaPlan.ESTADO_IGNORADA
    sugerencia.cooldown_hasta = timezone.localdate() + timedelta(days=SugerenciaPlan.COOLDOWN_DIAS)
    sugerencia.fecha_respuesta = timezone.now()
    sugerencia.save(update_fields=['estado', 'cooldown_hasta', 'fecha_respuesta'])
    return sugerencia


_PATRON_A_INTERVENCION = {
    # Carga patterns (expire Sunday of current week)
    'carga_alta_sostenida':     'no_subir_cargas',
    'bloque_parcial_repetido':  'no_subir_cargas',
    'esenciales_frecuentes':    'no_subir_cargas',
    'margen_bajo_repetido':     'reducir_accesorios',
    'alta_continuidad':         'mantener_estructura',
    # Distribution patterns (expire in 14 days — Phase 18)
    'distribucion_dia_pospone_frecuente':    'redistrib_dia_frecuente',
    'distribucion_dias_reales_menores':      'redistrib_dias_menores',
    'distribucion_pierna_tras_futbol':       'redistrib_pierna_futbol',
    'distribucion_esenciales_concentradas':  'redistrib_aligerar_dia',
}

_DISTRIBUCION_PATRONES = {
    'redistrib_dia_frecuente', 'redistrib_dias_menores',
    'redistrib_pierna_futbol', 'redistrib_aligerar_dia',
}


def _fin_de_semana(fecha):
    """Returns the Sunday (end of week) for the given date."""
    return fecha + timedelta(days=(6 - fecha.weekday()))


def aceptar_sugerencia(sugerencia, fecha_ref=None):
    """
    Phase 10C/18A — User chose to apply the suggestion.
    - Carga suggestions: IntervencionPlan until end of current week.
    - Distribution suggestions (Phase 18): IntervencionPlan for 14 days.
    The freno contextual reads carga interventions; distribution interventions
    are shown as visible probes but don't auto-restructure the plan.
    """
    from entrenos.models import IntervencionPlan

    fecha_ref = fecha_ref or timezone.localdate()
    tipo = _PATRON_A_INTERVENCION.get(sugerencia.patron, IntervencionPlan.TIPO_MANTENER)

    # Distribution interventions last 2 weeks; carga ones expire on Sunday
    if tipo in _DISTRIBUCION_PATRONES:
        fecha_fin = fecha_ref + timedelta(days=14)
    else:
        fecha_fin = _fin_de_semana(fecha_ref)

    IntervencionPlan.objects.create(
        cliente=sugerencia.cliente,
        sugerencia=sugerencia,
        tipo=tipo,
        origen_patron=sugerencia.patron,
        fecha_inicio=fecha_ref,
        fecha_fin=fecha_fin,
        estado=IntervencionPlan.ESTADO_ACTIVA,
    )

    sugerencia.estado = SugerenciaPlan.ESTADO_ACEPTADA
    sugerencia.fecha_respuesta = timezone.now()
    sugerencia.save(update_fields=['estado', 'fecha_respuesta'])
    return sugerencia


def evaluar_intervencion_semana(cliente, fecha_ref=None):
    """
    Phase 12 — Evaluates the outcome of accepted interventions from the previous week.

    Returns a dict or None if no interventions were active last week.

    Return dict:
        tipo_intervencion: str
        resultado: 'favorable' | 'neutral' | 'sin_datos'
        lectura: str  (human-readable, JOI-safe, no blame)
    """
    from entrenos.models import IntervencionPlan
    from entrenos.services.analisis_semanal_service import analizar_semana_entrenamiento

    fecha_ref = fecha_ref or timezone.localdate()
    semana_pasada = fecha_ref - timedelta(weeks=1)

    try:
        intervenciones = IntervencionPlan.objects.filter(
            cliente=cliente,
            estado__in=[IntervencionPlan.ESTADO_ACTIVA, IntervencionPlan.ESTADO_EXPIRADA],
            fecha_inicio__lte=semana_pasada + timedelta(days=6),
            fecha_fin__gte=semana_pasada,
        ).exclude(tipo=IntervencionPlan.TIPO_MANTENER)

        if not intervenciones.exists():
            return None

        semana_data = analizar_semana_entrenamiento(cliente, semana_pasada)
        if not semana_data or not semana_data.get('hay_datos'):
            return None

        for intervencion in intervenciones:
            resultado = _evaluar_resultado_intervencion(intervencion, semana_data)
            if resultado:
                return resultado

    except Exception:
        logger.exception('evaluar_intervencion_semana: error para cliente %s', cliente.id)

    return None


def _evaluar_resultado_intervencion(intervencion, semana_data):
    from entrenos.models import IntervencionPlan

    tipo = intervencion.tipo
    estado_semana = semana_data.get('estado_semana', 'sin_datos')
    pct_principal = semana_data.get('porcentaje_principal_medio')

    if tipo == IntervencionPlan.TIPO_NO_SUBIR:
        if estado_semana in ('solida', 'margen_extra'):
            return {
                'tipo_intervencion': tipo,
                'resultado': 'favorable',
                'lectura': 'La semana anterior mantuviste cargas y la semana se sostuvo. La intervención parece haber liberado margen.',
            }
        elif estado_semana == 'carga_alta':
            return {
                'tipo_intervencion': tipo,
                'resultado': 'neutral',
                'lectura': 'Mantuviste cargas, pero la semana siguió siendo exigente. Puede que el problema sea de volumen, no solo de progresión.',
            }
        return {
            'tipo_intervencion': tipo,
            'resultado': 'sin_datos',
            'lectura': 'No hay suficientes datos de la semana pasada para evaluar la intervención.',
        }

    elif tipo == IntervencionPlan.TIPO_REDUCIR:
        if pct_principal is not None and pct_principal >= 80:
            return {
                'tipo_intervencion': tipo,
                'resultado': 'favorable',
                'lectura': 'Redujiste accesorios y el bloque principal se sostuvo. La intervención parece haber sido útil.',
            }
        elif estado_semana in ('solida', 'margen_extra'):
            return {
                'tipo_intervencion': tipo,
                'resultado': 'favorable',
                'lectura': 'La semana con accesorios reducidos fue sólida. El plan puede absorber ese ajuste.',
            }
        return {
            'tipo_intervencion': tipo,
            'resultado': 'neutral',
            'lectura': 'Reducir accesorios no cambió visiblemente el patrón. El plan puede necesitar un ajuste más profundo.',
        }

    return None


_RECOMENDACION_REPETIR = {
    'no_subir_cargas':    'La semana anterior el ajuste funcionó. Mantener cargas sin subir una semana más.',
    'reducir_accesorios': 'Reducir accesorios liberó margen. Mantener el mismo criterio esta semana.',
}

_RECOMENDACION_PROFUNDIZAR = {
    'no_subir_cargas':    'Mantener cargas no fue suficiente. Puede ser momento de revisar el volumen total o repetir el microciclo actual.',
    'reducir_accesorios': 'Reducir accesorios no cambió el patrón. El volumen total puede estar por encima del margen real de la semana.',
}


def generar_recomendacion_continuidad(cliente, fecha_ref=None):
    """
    Phase 13 — Generates a continuation recommendation based on last week's evaluation.

    CONTRACT (Phase 13.1 update):
    - Returns None if no evaluation, active intervention, or user dismissed recently.
    - 'repetir': the same intervention type, applied this week.
    - 'profundizar': a different, deeper suggestion.
    - NEVER auto-applies. Waits for user consent.
    - A favorable intervention is NOT made permanent; it becomes a candidate to repeat.
    - If user dismisses "No por ahora": cooldown 7 days via SugerenciaPlan patron='continuidad_X'.
    """
    fecha_ref = fecha_ref or timezone.localdate()

    # Don't pile up if there's already an active intervention this week
    if get_intervencion_activa(cliente, fecha_ref):
        return None

    evaluacion = evaluar_intervencion_semana(cliente, fecha_ref)
    if not evaluacion:
        return None

    # Phase 13.1: check cooldown from "No por ahora" dismissal
    tipo_eval = evaluacion.get('tipo_intervencion', '')
    patron_clave = f'continuidad_{tipo_eval}'
    cooldown_activo = SugerenciaPlan.objects.filter(
        cliente=cliente,
        patron=patron_clave,
        estado=SugerenciaPlan.ESTADO_IGNORADA,
        cooldown_hasta__gt=fecha_ref,
    ).exists()
    if cooldown_activo:
        return None

    tipo = evaluacion.get('tipo_intervencion')
    resultado = evaluacion.get('resultado')

    if resultado == 'favorable':
        texto = _RECOMENDACION_REPETIR.get(tipo, 'Mantener el ajuste una semana más.')
        return {
            'accion': 'repetir',
            'tipo_intervencion': tipo,
            'texto': texto,
        }
    elif resultado == 'neutral':
        texto = _RECOMENDACION_PROFUNDIZAR.get(tipo, 'El ajuste puede necesitar revisión más profunda.')
        return {
            'accion': 'profundizar',
            'tipo_intervencion': tipo,
            'texto': texto,
        }

    return None


def repetir_intervencion(cliente, tipo_intervencion, fecha_ref=None):
    """
    Phase 13 — Creates a new IntervencionPlan this week (same type as last week).
    Called when the user accepts 'Repetir esta semana'.
    """
    from entrenos.models import IntervencionPlan

    fecha_ref = fecha_ref or timezone.localdate()
    fecha_fin = _fin_de_semana(fecha_ref)

    return IntervencionPlan.objects.create(
        cliente=cliente,
        tipo=tipo_intervencion,
        origen_patron='continuidad_fase13',
        fecha_inicio=fecha_ref,
        fecha_fin=fecha_fin,
        estado=IntervencionPlan.ESTADO_ACTIVA,
    )


def generar_recomendacion_continuidad_distribucion(cliente, fecha_ref=None):
    """
    Phase 21 — If a distribution probe was favorable, suggests repeating it.
    Returns None if neutral, no data, or cooldown active.

    CONTRACT (matches Phase 13 pattern):
    - 'repetir': same type of probe for 14 more days.
    - Cooldown via SugerenciaPlan(patron='continuidad_distribucion_X').
    - NEVER auto-applies. Waits for user consent.
    - A favorable probe is NOT made permanent; it's a candidate to repeat.
    """
    fecha_ref = fecha_ref or timezone.localdate()

    # Don't suggest if there's already an active distribution probe
    _REDISTRIB = {
        IntervencionPlan.TIPO_REDISTRIB_DIA, IntervencionPlan.TIPO_REDISTRIB_DIAS,
        IntervencionPlan.TIPO_REDISTRIB_PIERNA, IntervencionPlan.TIPO_REDISTRIB_LIGERO,
    }
    if IntervencionPlan.objects.filter(
        cliente=cliente, tipo__in=_REDISTRIB,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        fecha_inicio__lte=fecha_ref, fecha_fin__gte=fecha_ref,
    ).exists():
        return None

    evaluacion = evaluar_prueba_distribucion(cliente, fecha_ref)
    if not evaluacion or evaluacion.get('resultado') != 'favorable':
        return None

    tipo = evaluacion.get('tipo')
    patron_cooldown = f'continuidad_distribucion_{tipo}'

    # Check cooldown
    if SugerenciaPlan.objects.filter(
        cliente=cliente, patron=patron_cooldown,
        estado=SugerenciaPlan.ESTADO_IGNORADA,
        cooldown_hasta__gt=fecha_ref,
    ).exists():
        return None

    texto = _RECOMENDACION_REPETIR_DIST.get(
        tipo, 'La prueba parece haber ayudado. Puedes repetirla 2 semanas más antes de convertirla en estructura.'
    )
    return {
        'accion': 'repetir',
        'tipo_intervencion': tipo,
        'texto': texto,
    }


_RECOMENDACION_REPETIR_DIST = {
    IntervencionPlan.TIPO_REDISTRIB_DIA:    'La fricción en ese día se redujo durante la prueba. Repetirla 2 semanas más confirmaría si el ajuste encaja.',
    IntervencionPlan.TIPO_REDISTRIB_DIAS:   'La semana fue más sostenible con menos días. Probar 2 semanas más antes de ajustar la configuración.',
    IntervencionPlan.TIPO_REDISTRIB_PIERNA: 'Separar pierna del fútbol parece haber dado resultado. Repitir el criterio 2 semanas más.',
    IntervencionPlan.TIPO_REDISTRIB_LIGERO: 'Aligerar ese día conservó mejor el bloque principal. Vale la pena repetirlo 2 semanas más.',
}


def repetir_prueba_distribucion(cliente, tipo_intervencion, fecha_ref=None):
    """Creates a new distribution IntervencionPlan for 14 more days."""
    fecha_ref = fecha_ref or timezone.localdate()
    return IntervencionPlan.objects.create(
        cliente=cliente,
        tipo=tipo_intervencion,
        origen_patron='continuidad_fase21',
        fecha_inicio=fecha_ref,
        fecha_fin=fecha_ref + timedelta(days=14),
        estado=IntervencionPlan.ESTADO_ACTIVA,
    )


def evaluar_prueba_distribucion(cliente, fecha_ref=None):
    """
    Phase 20 — Evaluates completed distribution probes.

    Compares the 2 weeks BEFORE the probe vs DURING the probe.
    Returns a reading dict or None if no completed probe to evaluate.

    CONTRACT:
    - Uses "parece", "puede", "durante la prueba" — never absolute claims.
    - 2 weeks is not enough to prove a truth; it's enough to form a hypothesis.
    - Returns None if no data or probe too recent.
    - NEVER writes to ManualDavid.
    """
    from entrenos.models import IntervencionPlan, EntrenoRealizado, SesionProgramada

    fecha_ref = fecha_ref or timezone.localdate()

    # Find a distribution probe that just ended (within last 7 days)
    _REDISTRIB = {
        IntervencionPlan.TIPO_REDISTRIB_DIA,
        IntervencionPlan.TIPO_REDISTRIB_DIAS,
        IntervencionPlan.TIPO_REDISTRIB_PIERNA,
        IntervencionPlan.TIPO_REDISTRIB_LIGERO,
    }

    intervencion = (
        IntervencionPlan.objects
        .filter(
            cliente=cliente,
            tipo__in=_REDISTRIB,
            estado__in=[IntervencionPlan.ESTADO_ACTIVA, IntervencionPlan.ESTADO_EXPIRADA],
            fecha_fin__gte=fecha_ref - timedelta(days=7),
            fecha_fin__lt=fecha_ref,
        )
        .order_by('-fecha_fin')
        .first()
    )

    if not intervencion:
        return None

    fecha_inicio = intervencion.fecha_inicio
    fecha_fin = intervencion.fecha_fin

    # "Before" window: same duration before the probe
    duracion = (fecha_fin - fecha_inicio).days + 1
    antes_inicio = fecha_inicio - timedelta(days=duracion)
    antes_fin = fecha_inicio - timedelta(days=1)

    tipo = intervencion.tipo

    try:
        if tipo == IntervencionPlan.TIPO_REDISTRIB_DIA:
            return _evaluar_redistrib_dia(
                cliente, fecha_inicio, fecha_fin, antes_inicio, antes_fin, intervencion
            )
        elif tipo == IntervencionPlan.TIPO_REDISTRIB_PIERNA:
            return _evaluar_redistrib_pierna(
                cliente, fecha_inicio, fecha_fin, antes_inicio, antes_fin
            )
        elif tipo == IntervencionPlan.TIPO_REDISTRIB_LIGERO:
            return _evaluar_redistrib_ligero(
                cliente, fecha_inicio, fecha_fin, antes_inicio, antes_fin, intervencion
            )
        elif tipo == IntervencionPlan.TIPO_REDISTRIB_DIAS:
            return _evaluar_redistrib_dias(
                cliente, fecha_inicio, fecha_fin, antes_inicio, antes_fin
            )
    except Exception:
        logger.exception('evaluar_prueba_distribucion: error para cliente %s', cliente.id)

    return None


def _tasa_caidas(cliente, fecha_desde, fecha_hasta):
    """Proportion of sessions that were skipped or omitted in the given range."""
    from entrenos.models import SesionProgramada
    total = SesionProgramada.objects.filter(
        cliente=cliente, fecha_prevista__range=(fecha_desde, fecha_hasta)
    ).count()
    caidas = SesionProgramada.objects.filter(
        cliente=cliente, fecha_prevista__range=(fecha_desde, fecha_hasta),
        estado__in=[SesionProgramada.ESTADO_SALTADA_USUARIO, SesionProgramada.ESTADO_OMITIDA_SISTEMA],
    ).count()
    return (caidas / total) if total > 0 else None


def _evaluar_redistrib_dia(cliente, inicio, fin, antes_ini, antes_fin, intervencion):
    """redistrib_dia_frecuente: did the problematic day improve?"""
    from entrenos.models import SesionProgramada

    dia_problema = (intervencion.origen_patron or '').lower()
    dow_names = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    try:
        dow = dow_names.index(dia_problema)
    except ValueError:
        return None

    def _tasa_caidas_dia(fecha_d, fecha_h):
        qs = SesionProgramada.objects.filter(
            cliente=cliente, fecha_prevista__range=(fecha_d, fecha_h)
        )
        dia_total = sum(1 for sp in qs if sp.fecha_prevista.weekday() == dow)
        dia_caidas = sum(
            1 for sp in qs
            if sp.fecha_prevista.weekday() == dow
            and sp.estado in (SesionProgramada.ESTADO_SALTADA_USUARIO, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        )
        return (dia_caidas / dia_total) if dia_total > 0 else None

    tasa_antes = _tasa_caidas_dia(antes_ini, antes_fin)
    tasa_durante = _tasa_caidas_dia(inicio, fin)

    if tasa_antes is None or tasa_durante is None:
        return None

    if tasa_durante < tasa_antes - 0.2:
        return {
            'tipo': intervencion.tipo,
            'resultado': 'favorable',
            'lectura': f'Durante la prueba, las sesiones del {dia_problema} cayeron menos. El experimento parece haber liberado algo.',
        }
    return {
        'tipo': intervencion.tipo,
        'resultado': 'neutral',
        'lectura': f'El patrón del {dia_problema} no cambió claramente. Puede que el problema no sea solo el día.',
    }


def _evaluar_redistrib_pierna(cliente, inicio, fin, antes_ini, antes_fin):
    """redistrib_pierna_futbol: did leg sessions stop being essential near football?"""
    from entrenos.models import EntrenoRealizado, ActividadRealizada

    def _ratio_esencial_pierna(fecha_d, fecha_h):
        futbol = set(
            ActividadRealizada.objects.filter(
                cliente=cliente, tipo='futbol', fecha__range=(fecha_d, fecha_h)
            ).values_list('fecha', flat=True)
        )
        pierna_total, pierna_esencial = 0, 0
        for er in EntrenoRealizado.objects.filter(cliente=cliente, fecha__range=(fecha_d, fecha_h)):
            nombre = (er.rutina.nombre if er.rutina_id else '').lower()
            es_pierna = any(kw in nombre for kw in ['pierna', 'leg', 'quad'])
            if es_pierna and any(abs((er.fecha - f).days) <= 2 for f in futbol):
                pierna_total += 1
                if er.modo_reducido:
                    pierna_esencial += 1
        return (pierna_esencial / pierna_total) if pierna_total > 0 else None

    antes = _ratio_esencial_pierna(antes_ini, antes_fin)
    durante = _ratio_esencial_pierna(inicio, fin)

    if antes is None or durante is None:
        return None

    if durante < antes - 0.2:
        return {
            'tipo': IntervencionPlan.TIPO_REDISTRIB_PIERNA,
            'resultado': 'favorable',
            'lectura': 'Separar pierna del fútbol parece haber dejado más margen. Las versiones esenciales de pierna bajaron durante la prueba.',
        }
    return {
        'tipo': IntervencionPlan.TIPO_REDISTRIB_PIERNA,
        'resultado': 'neutral',
        'lectura': 'La interferencia sigue apareciendo. Puede que haya que revisar la carga de pierna o el día del fútbol.',
    }


def _evaluar_redistrib_ligero(cliente, inicio, fin, antes_ini, antes_fin, intervencion):
    """redistrib_aligerar_dia: did the problematic day have fewer esencials?"""
    from entrenos.models import EntrenoRealizado

    dia_problema = (intervencion.origen_patron or '').lower()
    dow_names = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    try:
        dow = dow_names.index(dia_problema)
    except ValueError:
        dow = None

    def _ratio_esencial_dia(fecha_d, fecha_h):
        qs = list(EntrenoRealizado.objects.filter(cliente=cliente, fecha__range=(fecha_d, fecha_h)))
        if dow is not None:
            qs = [e for e in qs if e.fecha.weekday() == dow]
        if not qs:
            return None
        return sum(1 for e in qs if e.modo_reducido) / len(qs)

    antes = _ratio_esencial_dia(antes_ini, antes_fin)
    durante = _ratio_esencial_dia(inicio, fin)

    if antes is None or durante is None:
        return None

    if durante < antes - 0.2:
        return {
            'tipo': intervencion.tipo,
            'resultado': 'favorable',
            'lectura': 'Aligerar ese día parece haber conservado mejor el bloque principal. Hubo menos versiones esenciales.',
        }
    return {
        'tipo': intervencion.tipo,
        'resultado': 'neutral',
        'lectura': 'La concentración de versiones esenciales en ese día no cambió claramente durante la prueba.',
    }


def _evaluar_redistrib_dias(cliente, inicio, fin, antes_ini, antes_fin):
    """redistrib_dias_menores: did continuity improve with fewer days?"""
    from entrenos.models import EntrenoRealizado, SesionProgramada

    def _tasa_saltadas(fecha_d, fecha_h):
        total = SesionProgramada.objects.filter(cliente=cliente, fecha_prevista__range=(fecha_d, fecha_h)).count()
        saltadas = SesionProgramada.objects.filter(
            cliente=cliente, fecha_prevista__range=(fecha_d, fecha_h),
            estado=SesionProgramada.ESTADO_SALTADA_USUARIO,
        ).count()
        return (saltadas / total) if total > 0 else None

    antes = _tasa_saltadas(antes_ini, antes_fin)
    durante = _tasa_saltadas(inicio, fin)

    if antes is None or durante is None:
        return None

    if durante < antes - 0.15:
        return {
            'tipo': IntervencionPlan.TIPO_REDISTRIB_DIAS,
            'resultado': 'favorable',
            'lectura': 'Priorizar menos sesiones parece haber hecho la semana más sostenible. Las caídas bajaron durante la prueba.',
        }
    return {
        'tipo': IntervencionPlan.TIPO_REDISTRIB_DIAS,
        'resultado': 'neutral',
        'lectura': 'El número de sesiones completadas no cambió claramente. Puede que el problema no sea solo la cantidad de días.',
    }


def get_intervencion_activa(cliente, fecha_ref=None):
    """
    Returns the active IntervencionPlan for today, or None.
    Called by evaluar_permiso_progresion — takes precedence over pattern detection.
    """
    from entrenos.models import IntervencionPlan

    fecha_ref = fecha_ref or timezone.localdate()

    # Expire stale active interventions
    IntervencionPlan.objects.filter(
        cliente=cliente,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        fecha_fin__lt=fecha_ref,
    ).update(estado=IntervencionPlan.ESTADO_EXPIRADA)

    return (
        IntervencionPlan.objects
        .filter(
            cliente=cliente,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio__lte=fecha_ref,
            fecha_fin__gte=fecha_ref,
        )
        .exclude(tipo=IntervencionPlan.TIPO_MANTENER)  # mantener_estructura = no freno effect
        .order_by('-creada_en')
        .first()
    )
