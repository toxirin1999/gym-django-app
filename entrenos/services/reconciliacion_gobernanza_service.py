"""Auditoría conservadora de incoherencias del Centro de decisiones."""

from collections import Counter

from django.db import models, transaction
from django.utils import timezone

from entrenos.models import (
    GymDecisionLog,
    GymDecisionTraceEvaluation,
    IntervencionPlan,
    PreferenciaPlanAprendida,
    SugerenciaPlan,
)


def _hallazgo(code, obj, before, proposed=None, evidence=None,
              confidence='high', reversible=True):
    return {
        'code': code,
        'model': obj._meta.label,
        'pk': obj.pk,
        'before': before,
        'proposed': proposed,
        'evidence': evidence or {},
        'confidence': confidence,
        'reversible': reversible,
    }


def detectar_hallazgos(cliente_id=None, limit=100, fecha_ref=None):
    """Devuelve hallazgos deterministas. Nunca escribe."""
    hoy = fecha_ref or timezone.localdate()
    limit = max(0, limit)
    hallazgos = []

    def limitado():
        return len(hallazgos) >= limit

    logs = GymDecisionLog.objects.all().order_by('pk')
    if cliente_id:
        logs = logs.filter(cliente_id=cliente_id)
    for log in logs.iterator():
        if bool(log.resultado) != bool(log.fecha_evaluacion):
            hallazgos.append(_hallazgo(
                'decision_resultado_fecha_incoherente', log,
                {'resultado': log.resultado, 'fecha_evaluacion': log.fecha_evaluacion},
                evidence={'regla': 'resultado y fecha_evaluacion deben coexistir'},
            ))
        if (
            log.estado_aplicacion in {'aplicada', 'pospuesta'}
            and not log.fecha_aplicacion
        ):
            hallazgos.append(_hallazgo(
                'decision_estado_fecha_incoherente', log,
                {'estado_aplicacion': log.estado_aplicacion,
                 'fecha_aplicacion': log.fecha_aplicacion},
                evidence={
                    'regla': 'aplicada y pospuesta requieren fecha_aplicacion',
                    'legacy_pendiente_no_se_promueve': True,
                },
            ))
        if limitado():
            return hallazgos[:limit]

    sugerencias = SugerenciaPlan.objects.all().order_by('pk')
    if cliente_id:
        sugerencias = sugerencias.filter(cliente_id=cliente_id)
    pendientes_por_cliente_patron = Counter(
        sugerencias.filter(estado=SugerenciaPlan.ESTADO_PENDIENTE)
        .values_list('cliente_id', 'patron')
    )
    for sugerencia in sugerencias.select_related('cliente').iterator():
        if (sugerencia.estado == SugerenciaPlan.ESTADO_PENDIENTE
                and pendientes_por_cliente_patron[
                    (sugerencia.cliente_id, sugerencia.patron)
                ] > 1):
            cantidad = pendientes_por_cliente_patron[
                (sugerencia.cliente_id, sugerencia.patron)
            ]
            hallazgos.append(_hallazgo(
                'sugerencias_pendientes_multiples', sugerencia,
                {'pendientes_cliente_patron': cantidad},
                evidence={
                    'cliente_id': sugerencia.cliente_id,
                    'patron': sugerencia.patron,
                },
                confidence='medium',
            ))
        if (sugerencia.estado == SugerenciaPlan.ESTADO_ACEPTADA
                and not sugerencia.intervenciones.exists()):
            hallazgos.append(_hallazgo(
                'sugerencia_aceptada_sin_intervencion', sugerencia,
                {'estado': sugerencia.estado},
            ))
        if limitado():
            return hallazgos[:limit]

    intervenciones = (
        IntervencionPlan.objects.select_related('sugerencia').all().order_by('pk')
    )
    if cliente_id:
        intervenciones = intervenciones.filter(cliente_id=cliente_id)
    activas = list(intervenciones.filter(estado=IntervencionPlan.ESTADO_ACTIVA))
    for intervencion in activas:
        if intervencion.fecha_fin < hoy:
            hallazgos.append(_hallazgo(
                'intervencion_activa_expirada', intervencion,
                {'estado': intervencion.estado, 'fecha_fin': intervencion.fecha_fin},
                proposed={'estado': IntervencionPlan.ESTADO_EXPIRADA},
                evidence={'hoy': hoy},
            ))
        if (intervencion.sugerencia_id and
                (intervencion.sugerencia.cliente_id != intervencion.cliente_id
                 or intervencion.sugerencia.estado != SugerenciaPlan.ESTADO_ACEPTADA)):
            hallazgos.append(_hallazgo(
                'intervencion_relacion_incoherente', intervencion,
                {'cliente_id': intervencion.cliente_id,
                 'sugerencia_id': intervencion.sugerencia_id,
                 'sugerencia_estado': intervencion.sugerencia.estado},
            ))
        if limitado():
            return hallazgos[:limit]

    for i, actual in enumerate(activas):
        solapadas = [
            otra.pk for otra in activas[i + 1:]
            if otra.cliente_id == actual.cliente_id
            and otra.fecha_inicio <= actual.fecha_fin
            and actual.fecha_inicio <= otra.fecha_fin
        ]
        if solapadas:
            hallazgos.append(_hallazgo(
                'intervenciones_activas_duplicadas_o_solapadas', actual,
                {'estado': actual.estado},
                evidence={'solapadas_ids': solapadas},
                confidence='medium',
            ))
        if limitado():
            return hallazgos[:limit]

    preferencias = PreferenciaPlanAprendida.objects.filter(
        estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
    ).order_by('pk')
    if cliente_id:
        preferencias = preferencias.filter(cliente_id=cliente_id)
    for preferencia in preferencias:
        conflictos = [
            i.pk for i in activas
            if i.cliente_id == preferencia.cliente_id
            and i.origen_patron and preferencia.origen_patron
            and i.origen_patron != preferencia.origen_patron
        ]
        if conflictos:
            hallazgos.append(_hallazgo(
                'preferencia_intervencion_posible_conflicto', preferencia,
                {'estado': preferencia.estado},
                evidence={'intervenciones_ids': conflictos},
                confidence='low',
            ))
        if limitado():
            return hallazgos[:limit]

    # "Stale" significa que la fuente cambió después de ser evaluada; la mera
    # antigüedad no invalida una evaluación histórica.
    evals = (
        GymDecisionTraceEvaluation.objects.select_related('trace')
        .filter(trace__actualizado_en__gt=models.F('creado_en'))
        .order_by('pk')
    )
    if cliente_id:
        evals = evals.filter(trace__cliente_id=cliente_id)
    for evaluacion in evals:
        hallazgos.append(_hallazgo(
            'evaluacion_trace_stale', evaluacion,
            {'trace_actualizado_en': evaluacion.trace.actualizado_en,
             'evaluacion_creado_en': evaluacion.creado_en,
             'resultado': evaluacion.resultado},
            evidence={'regla': 'trace.actualizado_en > evaluacion.creado_en'},
            confidence='high',
        ))
        if limitado():
            break
    return hallazgos[:limit]


def reconciliar(cliente_id=None, limit=100, apply=False, fecha_ref=None):
    hallazgos = detectar_hallazgos(cliente_id, limit, fecha_ref)
    aplicados = 0
    if apply:
        ids = [
            h['pk'] for h in hallazgos
            if h['code'] == 'intervencion_activa_expirada'
        ]
        with transaction.atomic():
            objetos = IntervencionPlan.objects.select_for_update().filter(
                pk__in=ids,
                estado=IntervencionPlan.ESTADO_ACTIVA,
                fecha_fin__lt=fecha_ref or timezone.localdate(),
            )
            aplicados = objetos.update(estado=IntervencionPlan.ESTADO_EXPIRADA)
    return {'hallazgos': hallazgos, 'aplicados': aplicados, 'apply': apply}
