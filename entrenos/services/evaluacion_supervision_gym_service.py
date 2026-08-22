"""Cierre conservador de las intervenciones manuales de autoridad Gym."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from entrenos.models import EntrenoRealizado, EvaluacionSupervisionGym, GymDecisionVersion


SCHEMA_VERSION = 1
CALCULO_VERSION = 1
ORIGENES_MANUALES = {
    GymDecisionVersion.ORIGEN_CORRECCION,
    GymDecisionVersion.ORIGEN_REVERSION,
}


def _fecha_efectiva_query(fecha):
    return Q(fecha_ejecucion=fecha) | Q(fecha_ejecucion__isnull=True, fecha=fecha)


def _es_evaluable(version, hoy):
    return bool(
        version
        and version.origen in ORIGENES_MANUALES
        and version.vigente
        and version.fecha < hoy
        and not GymDecisionVersion.objects.filter(
            cliente_id=version.cliente_id,
            fecha=version.fecha,
            version__gt=version.version,
        ).exists()
    )


def _evidencia(version, entrenos):
    filas = []
    for entreno in entrenos:
        filas.append({
            'entreno_id': entreno.pk,
            'version_decision_id': entreno.gym_decision_version_id,
            'estado_causal': entreno.gym_decision_estado_causal,
            'modo_reducido': bool(entreno.modo_reducido),
            'emitida_en': (
                entreno.gym_decision_emitida_en.isoformat()
                if entreno.gym_decision_emitida_en else None
            ),
        })
    exactos = [
        e.pk for e in entrenos
        if e.gym_decision_version_id == version.pk
        and e.gym_decision_estado_causal == 'exacta'
    ]
    superados = [
        e.pk for e in entrenos
        if e.gym_decision_version_id == version.pk
        and e.gym_decision_estado_causal == 'superada_durante_ejecucion'
    ]
    return {
        'schema_version': SCHEMA_VERSION,
        'calculo_version': CALCULO_VERSION,
        'version_decision_id': version.pk,
        'decision_id': version.decision_id,
        'cliente_id': version.cliente_id,
        'fecha': version.fecha.isoformat(),
        'postura': version.postura,
        'entrenos_exactos': exactos,
        'entrenos_superados': superados,
        'entrenos': filas,
    }


def evaluar_supervision_gym(version, *, hoy=None):
    """Calcula sin escribir. La ausencia de vínculo jamás se infiere favorable."""
    hoy = hoy or timezone.localdate()
    if not _es_evaluable(version, hoy):
        return None

    entrenos = list(
        EntrenoRealizado.objects.filter(cliente_id=version.cliente_id)
        .filter(_fecha_efectiva_query(version.fecha))
        .select_related('gym_decision_version')
        .order_by('pk')
    )
    evidencia = _evidencia(version, entrenos)
    exactos = [
        e for e in entrenos
        if e.gym_decision_version_id == version.pk
        and e.gym_decision_estado_causal == 'exacta'
    ]

    if version.postura == 'proteger':
        posteriores = [
            e for e in entrenos
            if e.gym_decision_emitida_en is not None
            and e.gym_decision_emitida_en >= version.creado_en
        ]
        if exactos or posteriores:
            resultado = EvaluacionSupervisionGym.DESVIADA
        elif entrenos:
            # Entreno anterior o legacy: no se atribuye retroactivamente.
            resultado = EvaluacionSupervisionGym.INCONCLUSA
        else:
            resultado = EvaluacionSupervisionGym.PROTECCION_CUMPLIDA
    elif not exactos:
        resultado = EvaluacionSupervisionGym.INCONCLUSA
    elif version.postura == 'sostener':
        exige_reduccion = bool(
            (version.ajustes or {}).get('modo_reducido')
            or (version.snapshot or {}).get('modo_reducido')
            or (version.snapshot or {}).get('estado') == 'version_reducida'
        )
        if exige_reduccion and any(not e.modo_reducido for e in exactos):
            resultado = EvaluacionSupervisionGym.DESVIADA
        else:
            resultado = EvaluacionSupervisionGym.EJECUTADA_CONFORME
    elif version.postura == 'empujar':
        resultado = EvaluacionSupervisionGym.EJECUTADA_CONFORME
    else:
        resultado = EvaluacionSupervisionGym.INCONCLUSA

    return {
        'resultado': resultado,
        'evidencia_snapshot': evidencia,
        'schema_version': SCHEMA_VERSION,
        'calculo_version': CALCULO_VERSION,
    }


def cerrar_supervisiones_gym(
    *,
    cliente_id=None,
    desde=None,
    hasta=None,
    limite=500,
    aplicar=False,
    hoy=None,
):
    """Evalúa el lote elegible; en dry-run no realiza ninguna escritura."""
    hoy = hoy or timezone.localdate()
    hasta_cerrado = hoy - timedelta(days=1)
    hasta = min(hasta or hasta_cerrado, hasta_cerrado)

    version_final = GymDecisionVersion.objects.filter(
        cliente_id=OuterRef('cliente_id'),
        fecha=OuterRef('fecha'),
    ).order_by('-version').values('version')[:1]
    qs = GymDecisionVersion.objects.filter(
        origen__in=ORIGENES_MANUALES,
        vigente=True,
        fecha__lte=hasta,
        evaluacion_supervision__isnull=True,
        version=Subquery(version_final),
    ).select_related('cliente').order_by('fecha', 'pk')
    if cliente_id is not None:
        qs = qs.filter(cliente_id=cliente_id)
    if desde is not None:
        qs = qs.filter(fecha__gte=desde)
    versiones = list(qs[:limite])

    conteos = Counter()
    aplicados = 0
    for version in versiones:
        calculada = evaluar_supervision_gym(version, hoy=hoy)
        if calculada is None:
            continue
        conteos[calculada['resultado']] += 1
        if aplicar:
            with transaction.atomic():
                _, creada = EvaluacionSupervisionGym.objects.get_or_create(
                    version_decision=version,
                    defaults=calculada,
                )
                aplicados += int(creada)

    return {
        'tipo_registro': 'resumen',
        'schema_version': SCHEMA_VERSION,
        'modo': 'apply' if aplicar else 'dry-run',
        'solo_lectura': not aplicar,
        'cliente_id': cliente_id,
        'desde': desde.isoformat() if desde else None,
        'hasta': hasta.isoformat(),
        'limite': limite,
        'candidatos': len(versiones),
        'aplicados': aplicados,
        'conteos_por_resultado': dict(sorted(conteos.items())),
    }
