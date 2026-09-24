"""
Phase 36 — Acumulación de hipótesis desde senal_no_captada.

CONTRACT:
- Read-only: no escribe en el motor, no modifica decisiones.
- Una señal no captada no corrige el plan; enseña al sistema dónde mirar.
- Solo genera observación cuando hay ≥ MIN_OCURRENCIAS de senal_no_captada.
- Lenguaje: "parece que", "puede que", "en N decisiones", "quizá".
- NO dice: "el motor falló", "debes cambiar", "esto es incorrecto".
- Silencio honesto: si no hay patrón, devuelve lista vacía.
"""

import logging
from datetime import timedelta as _td

logger = logging.getLogger(__name__)

_MIN_OCURRENCIAS = 3   # mínimo de senal_no_captada para generar observación
_VENTANA_DIAS   = 30  # ventana de búsqueda en días


# Textos de observación por tipo de decisión
# Subject: "el sistema" (not the user), tentative tone.
_OBSERVACIONES = {
    'posponer': (
        'En {n} decisiones recientes de posponer, la sesión siguiente tuvo '
        'margen bajo. Puede que el sistema deba mirar mejor si la causa de '
        'posponer resuelve la fatiga o solo la desplaza.'
    ),
    'recuperar': (
        'En {n} decisiones de recuperación, las señales posteriores sugieren '
        'que quizá el margen no mejoró tanto como cabría esperar. '
        'Puede que haya una fuente de fatiga que el sistema todavía no capta.'
    ),
    'entrenar': (
        'En {n} sesiones propuestas como normales, apareció margen bajo después. '
        'Quizá el sistema deba mirar mejor señales de fatiga acumulada antes de '
        'proponer entrenar sin condiciones.'
    ),
    'version_reducida': (
        'En {n} sesiones en versión esencial, la continuidad no mejoró tan claramente '
        'como sugería la señal. Puede que la causa que activó el modo esencial '
        'persista más allá de una sesión.'
    ),
}

_DEFAULT_OBSERVACION = (
    'En {n} decisiones recientes de tipo "{estado}", aparecieron señales posteriores '
    'de margen bajo. Quizá haya una señal que el sistema todavía no está mirando bien.'
)


_PATRON_PREFIX = 'hipotesis_senal_'  # SugerenciaPlan.patron prefix for hypothesis suggestions
_DURACION_EXPERIMENTO = 14  # days

_ETIQUETAS_ESTADO = {
    'entrenar': 'propuestas de entrenar con normalidad',
    'posponer': 'decisiones de posponer una sesión',
    'recuperar': 'decisiones de priorizar recuperación',
    'version_reducida': 'propuestas de versión esencial',
}


def _estado_desde_patron(patron: str) -> str | None:
    if not (patron or '').startswith(_PATRON_PREFIX):
        return None
    return patron[len(_PATRON_PREFIX):] or None


def presentar_sugerencia_hipotesis(sugerencia) -> dict:
    """DTO humano estable, también para filas legacy con texto genérico."""
    estado = _estado_desde_patron(sugerencia.patron)
    senal = _ETIQUETAS_ESTADO.get(estado, 'una señal de decisión todavía no explicada')
    return {
        'id': sugerencia.pk,
        'senal': senal,
        'texto': sugerencia.texto,
        'que_observa': f'Durante 14 días contará si se repite margen bajo después de {senal}.',
        'que_no_cambia': 'No cambia cargas, ejercicios ni el calendario: solo observa y compara.',
        'como_termina': 'Al completar 14 días, el sistema cerrará la prueba y mostrará si la señal disminuyó, persistió o faltaron datos.',
    }


def _hipotesis_mas_relevante(hipotesis: list[dict]) -> dict | None:
    """Returns the single most repeated hypothesis (highest ocurrencias)."""
    if not hipotesis:
        return None
    return max(hipotesis, key=lambda h: h['ocurrencias'])


def get_sugerencia_hipotesis_activa(cliente) -> 'SugerenciaPlan | None':
    """
    Phase 37 — Returns pending hypothesis suggestion if one exists.
    Only one active at a time (prevents Centro becoming a lab).
    """
    try:
        from entrenos.models import SugerenciaPlan
        return SugerenciaPlan.objects.filter(
            cliente=cliente,
            patron__startswith=_PATRON_PREFIX,
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        ).order_by('-fecha_generada').first()
    except Exception:
        logger.exception('No se pudo consultar la sugerencia de hipótesis activa')
        raise


def generar_sugerencia_hipotesis(cliente, fecha_ref=None) -> 'SugerenciaPlan | None':
    """
    Phase 37 — Creates a SugerenciaPlan from the most repeated hypothesis.

    Rules:
    - Only if ≥ MIN_OCURRENCIAS senal_no_captada.
    - Only one pending hypothesis suggestion at a time.
    - Only if no vigilar_senal IntervencionPlan is currently active.
    - Text: experimental, no verdicts. "Probar" not "Aplicar".
    """
    from entrenos.models import SugerenciaPlan, IntervencionPlan
    from django.utils import timezone

    fecha_ref = fecha_ref or timezone.localdate()

    # Guard: no active vigilar_senal intervention
    if IntervencionPlan.objects.filter(
        cliente=cliente,
        tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        fecha_inicio__lte=fecha_ref,
        fecha_fin__gte=fecha_ref,
    ).exists():
        return None

    # Idempotencia: el productor puede recibir varias evaluaciones seguidas.
    if get_sugerencia_hipotesis_activa(cliente):
        return None

    hipotesis = detectar_hipotesis_abiertas(cliente, fecha_ref=fecha_ref)
    mejor = _hipotesis_mas_relevante(hipotesis)
    if not mejor:
        return None

    estado = mejor['estado']
    n = mejor['ocurrencias']
    patron = f"{_PATRON_PREFIX}{estado}"

    # Guard: no recent cooldown for this pattern
    if SugerenciaPlan.objects.filter(
        cliente=cliente,
        patron=patron,
        estado=SugerenciaPlan.ESTADO_IGNORADA,
        cooldown_hasta__gte=fecha_ref,
    ).exists():
        return None

    # Antes se descartaba mejor['texto'] (la observación concreta por tipo de
    # decisión, ya construida en detectar_hipotesis_abiertas/_OBSERVACIONES) y
    # se generaba un texto genérico ("esta señal", "esta variable") que no
    # decía a qué se refería. Ahora se reutiliza esa observación real: ya
    # nombra el patrón detectado (posponer/recuperar/entrenar/versión
    # reducida) con lenguaje tentativo, cumpliendo el contrato del módulo.
    texto = (
        f"{mejor['texto']}\n\n"
        f"¿Quieres probar durante {_DURACION_EXPERIMENTO} días que el plan "
        f"vigile esta señal con más atención antes de proponer entrenar?"
    )

    return SugerenciaPlan.objects.create(
        cliente=cliente,
        patron=patron,
        texto=texto,
        estado=SugerenciaPlan.ESTADO_PENDIENTE,
    )


def producir_sugerencia_hipotesis(cliente, fecha_ref=None) -> 'SugerenciaPlan | None':
    """Productor explícito e idempotente disparado al persistir una evaluación."""
    existente = get_sugerencia_hipotesis_activa(cliente)
    if existente:
        return existente
    return generar_sugerencia_hipotesis(cliente, fecha_ref=fecha_ref)


def aceptar_sugerencia_hipotesis(sugerencia, fecha_ref=None) -> 'IntervencionPlan':
    """
    Phase 37 — Converts an accepted hypothesis suggestion into a 14-day experiment.
    Creates IntervencionPlan(tipo='vigilar_senal'). Does NOT change loads.
    """
    from clientes.models import Cliente
    from entrenos.models import IntervencionPlan, SugerenciaPlan
    from django.db import transaction
    from django.utils import timezone

    with transaction.atomic():
        # El lock del cliente da un orden estable y serializa dos respuestas
        # simultáneas incluso en motores donde el lock de una fila es limitado.
        Cliente.objects.select_for_update().get(pk=sugerencia.cliente_id)
        sugerencia = SugerenciaPlan.objects.select_for_update().get(pk=sugerencia.pk)
        if not sugerencia.patron.startswith(_PATRON_PREFIX):
            raise ValueError('La sugerencia no pertenece al flujo de hipótesis.')
        if sugerencia.estado != SugerenciaPlan.ESTADO_PENDIENTE:
            existente = IntervencionPlan.objects.filter(sugerencia=sugerencia).first()
            if existente is not None:
                return existente
            raise ValueError('La hipótesis ya no está pendiente.')

        fecha_ref = fecha_ref or timezone.localdate()
        # La fecha inicial cuenta como el día 1: inicio + 13 abarca 14 fechas.
        fecha_fin = fecha_ref + _td(days=_DURACION_EXPERIMENTO - 1)
        snapshot = dict(sugerencia.contrato_snapshot or {})
        snapshot['experimento_hipotesis'] = {
            'version': 1,
            'estado_observado': _estado_desde_patron(sugerencia.patron),
            'duracion_dias': _DURACION_EXPERIMENTO,
            'fecha_inicio': fecha_ref.isoformat(),
            'fecha_fin': fecha_fin.isoformat(),
            'modifica_plan': False,
        }
        sugerencia.estado = SugerenciaPlan.ESTADO_ACEPTADA
        sugerencia.fecha_respuesta = timezone.now()
        sugerencia.contrato_snapshot = snapshot
        sugerencia.save(update_fields=['estado', 'fecha_respuesta', 'contrato_snapshot'])

        return IntervencionPlan.objects.create(
            cliente=sugerencia.cliente,
            sugerencia=sugerencia,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            origen_patron=sugerencia.patron,
            fecha_inicio=fecha_ref,
            fecha_fin=fecha_fin,
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )


def ignorar_sugerencia_hipotesis(sugerencia, fecha_ref=None):
    """Ignora una hipótesis pendiente durante siete días, sin aceptar ordinarias."""
    from clientes.models import Cliente
    from entrenos.models import SugerenciaPlan
    from django.db import transaction
    from django.utils import timezone

    fecha_ref = fecha_ref or timezone.localdate()
    with transaction.atomic():
        Cliente.objects.select_for_update().get(pk=sugerencia.cliente_id)
        sugerencia = SugerenciaPlan.objects.select_for_update().get(pk=sugerencia.pk)
        if not sugerencia.patron.startswith(_PATRON_PREFIX):
            raise ValueError('La sugerencia no pertenece al flujo de hipótesis.')
        if sugerencia.estado != SugerenciaPlan.ESTADO_PENDIENTE:
            return sugerencia

        sugerencia.estado = SugerenciaPlan.ESTADO_IGNORADA
        sugerencia.cooldown_hasta = fecha_ref + _td(days=7)
        sugerencia.fecha_respuesta = timezone.now()
        sugerencia.save(update_fields=['estado', 'cooldown_hasta', 'fecha_respuesta'])
        return sugerencia


def evaluar_fin_experimento_hipotesis(cliente, fecha_ref=None, intervencion=None) -> dict | None:
    """
    Phase 37 — After the vigilar_senal experiment ends, check if senal_no_captada
    occurrences decreased during the experiment window.

    Returns {resultado: 'atenuada' | 'persiste' | 'insuficiente', texto: str} or None.
    Does NOT change the motor. Just records the observation.
    """
    from entrenos.models import IntervencionPlan, GymDecisionTraceEvaluation
    from django.utils import timezone

    fecha_ref = fecha_ref or timezone.localdate()

    # Find recently expired vigilar_senal intervention
    if intervencion is None:
        intervencion = IntervencionPlan.objects.filter(
            cliente=cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            estado__in=[IntervencionPlan.ESTADO_EXPIRADA, IntervencionPlan.ESTADO_ACTIVA],
            fecha_fin__lte=fecha_ref,
        ).order_by('-fecha_fin').first()

    if not intervencion:
        return None

    estado_observado = _estado_desde_patron(intervencion.origen_patron)
    filtros_estado = {'trace__decision_estado': estado_observado} if estado_observado else {}

    # Count senal_no_captada during and before experiment. Los históricos sin
    # origen conservan el comportamiento antiguo; los nuevos miden su señal.
    antes_desde = intervencion.fecha_inicio - _td(days=_DURACION_EXPERIMENTO)
    antes_n = GymDecisionTraceEvaluation.objects.filter(
        trace__cliente=cliente,
        trace__fecha__gte=antes_desde,
        trace__fecha__lt=intervencion.fecha_inicio,
        resultado='senal_no_captada',
        **filtros_estado,
    ).count()

    durante_n = GymDecisionTraceEvaluation.objects.filter(
        trace__cliente=cliente,
        trace__fecha__gte=intervencion.fecha_inicio,
        trace__fecha__lte=intervencion.fecha_fin,
        resultado='senal_no_captada',
        **filtros_estado,
    ).count()

    if antes_n == 0:
        return {
            'resultado': 'insuficiente', 'texto': 'Sin datos previos suficientes para comparar.',
            'antes': antes_n, 'durante': durante_n, 'estado_observado': estado_observado,
        }

    if durante_n < antes_n * 0.6:  # 40%+ reduction
        return {
            'resultado': 'atenuada',
            'texto': (
                f'Durante el experimento, la señal apareció {durante_n} vez/veces '
                f'(antes: {antes_n}). Parece que observar esta variable con más '
                f'atención coincidió con menos apariciones. Hipótesis provisionalmente atenuada.'
            ),
            'antes': antes_n, 'durante': durante_n, 'estado_observado': estado_observado,
        }
    return {
        'resultado': 'persiste',
        'texto': (
            f'La señal siguió apareciendo ({durante_n} vez/veces durante el experimento). '
            f'La hipótesis permanece abierta. Puede que haya otras variables implicadas.'
        ),
        'antes': antes_n, 'durante': durante_n, 'estado_observado': estado_observado,
    }


def cerrar_experimentos_hipotesis_vencidos(fecha_ref=None) -> int:
    """Cierra y persiste experimentos vencidos. Idempotente; nunca se llama desde GET."""
    from django.db import transaction
    from django.utils import timezone
    from entrenos.models import IntervencionPlan, SugerenciaPlan

    fecha_ref = fecha_ref or timezone.localdate()
    ids = list(IntervencionPlan.objects.filter(
        tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        fecha_fin__lt=fecha_ref,
    ).values_list('pk', flat=True))
    cerradas = 0
    for pk in ids:
        with transaction.atomic():
            iv = IntervencionPlan.objects.select_for_update().select_related('sugerencia').get(pk=pk)
            if iv.estado != IntervencionPlan.ESTADO_ACTIVA or iv.fecha_fin >= fecha_ref:
                continue
            resultado = evaluar_fin_experimento_hipotesis(
                iv.cliente, fecha_ref=fecha_ref, intervencion=iv,
            )
            if iv.sugerencia_id:
                sugerencia = SugerenciaPlan.objects.select_for_update().get(pk=iv.sugerencia_id)
                snap = dict(sugerencia.contrato_snapshot or {})
                snap['evaluacion_hipotesis'] = {
                    **(resultado or {
                        'resultado': 'insuficiente',
                        'texto': 'Sin evidencia suficiente para evaluar la prueba.',
                        'antes': 0, 'durante': 0,
                        'estado_observado': _estado_desde_patron(iv.origen_patron),
                    }),
                    'fecha_cierre': fecha_ref.isoformat(),
                }
                sugerencia.contrato_snapshot = snap
                sugerencia.save(update_fields=['contrato_snapshot'])
            iv.estado = IntervencionPlan.ESTADO_EXPIRADA
            iv.save(update_fields=['estado'])
            cerradas += 1
    return cerradas


def cancelar_experimento_hipotesis(intervencion):
    """Cancela solo una vigilancia activa; no admite otros ajustes del plan."""
    from django.db import transaction
    from entrenos.models import IntervencionPlan
    with transaction.atomic():
        iv = IntervencionPlan.objects.select_for_update().get(pk=intervencion.pk)
        if iv.tipo != IntervencionPlan.TIPO_VIGILAR_SENAL:
            raise ValueError('La intervención no es un experimento de hipótesis.')
        if iv.estado == IntervencionPlan.ESTADO_ACTIVA:
            iv.estado = IntervencionPlan.ESTADO_CANCELADA
            iv.save(update_fields=['estado'])
        return iv


def resultados_hipotesis_recientes(cliente, limite=3):
    """Consulta pura de cierres persistidos, lista para mostrar."""
    from entrenos.models import IntervencionPlan
    resultados = []
    qs = IntervencionPlan.objects.filter(
        cliente=cliente,
        tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        estado=IntervencionPlan.ESTADO_EXPIRADA,
        sugerencia__contrato_snapshot__evaluacion_hipotesis__isnull=False,
    ).select_related('sugerencia').order_by('-fecha_fin')[:limite]
    for iv in qs:
        resultados.append({
            'intervencion': iv,
            'senal': _ETIQUETAS_ESTADO.get(
                _estado_desde_patron(iv.origen_patron), 'señal observada'
            ),
            'evaluacion': iv.sugerencia.contrato_snapshot['evaluacion_hipotesis'],
        })
    return resultados


def detectar_hipotesis_abiertas(cliente, ventana_dias=_VENTANA_DIAS, min_ocurrencias=_MIN_OCURRENCIAS, fecha_ref=None) -> list[dict]:
    """
    Phase 36 — Detects repeated senal_no_captada patterns for a client.

    Returns a list of observations (not corrections). Each observation:
        estado:      decision type where the pattern appeared
        ocurrencias: number of senal_no_captada instances
        texto:       human-readable, tentative observation
        fechas:      dates of the pattern (up to 3, for context)

    Returns [] when:
    - No senal_no_captada exists
    - Fewer than min_ocurrencias in the window
    - Any error (degrades silently)
    """
    try:
        from django.utils import timezone
        from entrenos.models import GymDecisionTraceEvaluation, GymDecisionTrace

        hoy = fecha_ref or timezone.localdate()
        desde = hoy - _td(days=ventana_dias)

        # Fetch all senal_no_captada evaluations in the window
        evaluaciones = list(
            GymDecisionTraceEvaluation.objects.filter(
                trace__cliente=cliente,
                trace__fecha__gte=desde,
                resultado='senal_no_captada',
            ).select_related('trace').order_by('-trace__fecha')
        )

        if not evaluaciones:
            return []

        # Group by decision_estado
        from collections import defaultdict
        por_estado = defaultdict(list)
        for ev in evaluaciones:
            por_estado[ev.trace.decision_estado].append(ev.trace.fecha)

        hipotesis = []
        for estado, fechas in por_estado.items():
            n = len(fechas)
            if n < min_ocurrencias:
                continue

            texto_template = _OBSERVACIONES.get(estado, _DEFAULT_OBSERVACION)
            texto = texto_template.format(n=n, estado=estado)

            hipotesis.append({
                'estado':      estado,
                'ocurrencias': n,
                'texto':       texto,
                'fechas':      sorted(fechas, reverse=True)[:3],
            })

        # Sort by ocurrencias desc (most repeated first)
        hipotesis.sort(key=lambda x: x['ocurrencias'], reverse=True)
        return hipotesis

    except Exception as e:
        logger.warning('detectar_hipotesis_abiertas falló: %s', e)
        return []
