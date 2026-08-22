"""Registro epistemológico v1: proyección determinista y estrictamente read-only.

No promueve, corrige ni fusiona conocimiento. Los adaptadores conservan la
procedencia que los modelos realmente almacenan y declaran lo ausente.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import hashlib
from typing import Any, Iterable

from django.db.models import Q


SCHEMA_VERSION = 1
LEVELS = {
    'hecho', 'senal', 'patron', 'hipotesis', 'conocimiento_provisional',
    'conocimiento_consolidado', 'preferencia', 'narrativa',
}


def _iso(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _record_id(instance) -> str:
    return f'{instance._meta.label_lower}:{instance.pk}'


def _subject(kind: str, pk: int) -> str:
    return f'{kind}:{pk}'


def _record(
    instance,
    *,
    subject_id: str,
    domain: str,
    level: str,
    claim_code: str | None = None,
    claim_text: str | None = None,
    status: str | None = None,
    confidence_value: Any = None,
    confidence_scale: str | None = None,
    confidence_source: str | None = None,
    observed_at=None,
    valid_from=None,
    valid_until=None,
    evidence_refs: Iterable[str] = (),
    derived_by: str | None = None,
    consent: dict | None = None,
    conditions: dict | None = None,
    owner: dict | None = None,
    supersedes: Iterable[str] = (),
    contradictions: Iterable[dict] = (),
    reversible: bool = True,
    missing_fields: Iterable[str] = (),
) -> dict:
    if level not in LEVELS:
        raise ValueError(f'Nivel epistemológico inválido: {level}')
    missing = set(missing_fields)
    if confidence_value is None:
        missing.update(('confidence.value', 'confidence.scale', 'confidence.source'))
    if observed_at is None:
        missing.add('observed_at')
    if valid_from is None:
        missing.add('valid_from')
    if valid_until is None:
        missing.add('valid_until')
    if not evidence_refs:
        missing.add('evidence_refs')
    if derived_by is None:
        missing.add('derived_by')
    if owner is None:
        missing.add('owner')
    if not consent or consent.get('status') == 'not_recorded':
        missing.add('consent')
    return {
        'schema_version': SCHEMA_VERSION,
        'record_id': _record_id(instance),
        'subject_id': subject_id,
        'domain': domain,
        'level': level,
        'claim_code': claim_code,
        'claim_text': claim_text,
        'status': status,
        'confidence': {
            'value': confidence_value,
            'scale': confidence_scale,
            'source': confidence_source,
        },
        'observed_at': _iso(observed_at),
        'valid_from': _iso(valid_from),
        'valid_until': _iso(valid_until),
        'evidence_refs': sorted(set(evidence_refs)),
        'derived_by': derived_by,
        'consent': consent or {'status': 'not_recorded', 'source': None},
        'conditions': conditions or {},
        'owner': owner,
        'supersedes': sorted(set(supersedes)),
        'contradictions': list(contradictions),
        'reversible': bool(reversible),
        'missing_fields': sorted(missing),
    }


def adaptar_preferencia_plan(preferencia) -> dict:
    metadata = preferencia.metadata if isinstance(preferencia.metadata, dict) else {}
    refs = [str(ref) for ref in metadata.get('evidence_refs', []) if ref]
    revocation_ref = metadata.get('revocation_ref')
    if revocation_ref:
        refs.append(str(revocation_ref))
    consent_explicit = metadata.get('consentimiento', None)
    if consent_explicit is False:
        consent = {'status': 'denied', 'source': 'metadata.consentimiento'}
    elif consent_explicit is True:
        consent = {'status': 'confirmed', 'source': 'metadata.consentimiento'}
    else:
        consent = {
            'status': 'contract_asserted',
            'source': 'PreferenciaPlanAprendida.CONTRACT',
        }
    valid_until = metadata.get('revoked_at') if preferencia.estado == 'revocada' else None
    missing = []
    if 'evidence_refs' not in metadata:
        missing.append('evidence_refs')
    if preferencia.estado != 'revocada':
        missing.append('valid_until')
    conditions = {
        'evidence_count': preferencia.evidencia_count,
        'evidence_refs_count': len(metadata.get('evidence_refs', [])),
        'evidence_refs_declared': 'evidence_refs' in metadata,
        'origen_patron': preferencia.origen_patron or None,
    }
    if metadata.get('manual_david_id') is not None:
        conditions['manual_david_id'] = metadata['manual_david_id']
    return _record(
        preferencia,
        subject_id=_subject('cliente', preferencia.cliente_id),
        domain='gym.plan', level='preferencia', claim_code=preferencia.tipo,
        claim_text=None, status=preferencia.estado,
        observed_at=preferencia.ultima_confirmacion,
        valid_from=preferencia.fecha_inicio, valid_until=valid_until,
        evidence_refs=refs, derived_by='entrenos.PreferenciaPlanAprendida',
        consent=consent, conditions=conditions,
        owner={'type': 'subject', 'id': _subject('cliente', preferencia.cliente_id)},
        reversible=True, missing_fields=missing,
    )


def adaptar_decision_log(decision) -> dict:
    refs = []
    if decision.entreno_origen_id:
        refs.append(f'entrenos.entrenorealizado:{decision.entreno_origen_id}')
    candidata_consolidacion = decision.resultado == 'validada'
    missing = [] if refs else ['evidence_refs']
    if candidata_consolidacion:
        # ``validada`` describe el resultado de esta decisión, no demuestra por
        # sí solo la regla de promoción ni dos evaluaciones independientes.
        missing.extend(['consolidation_rule', 'independent_evaluations'])
    return _record(
        decision,
        subject_id=_subject('cliente', decision.cliente_id), domain='gym.progresion',
        level='conocimiento_provisional',
        claim_code=decision.motivo_codigo or decision.accion, claim_text=None,
        status=decision.resultado or decision.estado_aplicacion,
        confidence_value=decision.confianza, confidence_scale='alta_media_baja',
        confidence_source='GymDecisionLog.confianza',
        observed_at=decision.fecha_creacion,
        valid_from=decision.fecha_aplicacion or decision.fecha_creacion,
        evidence_refs=refs, derived_by='entrenos.GymDecisionLog',
        conditions={
            'accion': decision.accion,
            'estado_aplicacion': decision.estado_aplicacion,
            'ejercicio_normalizado': decision.ejercicio_normalizado or None,
            'resultado': decision.resultado or None,
            'candidate_for_consolidation': candidata_consolidacion,
        },
        owner={'type': 'subject', 'id': _subject('cliente', decision.cliente_id)},
        missing_fields=missing,
    )


def adaptar_trace(trace) -> dict:
    motor = trace.senales_motor if isinstance(trace.senales_motor, dict) else {}
    version_keys = ('schema_version', 'decision_id', 'version')
    refs = []
    if trace.sesion_programada_id:
        refs.append(f'entrenos.sesionprogramada:{trace.sesion_programada_id}')
    return _record(
        trace,
        subject_id=_subject('cliente', trace.cliente_id), domain='gym.autoridad_diaria',
        level='senal', claim_code=trace.causa_principal or trace.decision_estado,
        status=trace.decision_estado, observed_at=trace.actualizado_en,
        valid_from=trace.fecha, valid_until=trace.fecha,
        evidence_refs=refs, derived_by='entrenos.GymDecisionTrace',
        conditions={
            'trace_version_identifiable': any(motor.get(key) is not None for key in version_keys),
            'capas_visibles': trace.capas_visibles,
            'capas_suprimidas': trace.capas_suprimidas,
        },
        owner={'type': 'subject', 'id': _subject('cliente', trace.cliente_id)},
        missing_fields=[] if refs else ['evidence_refs'],
    )


def adaptar_evaluacion_trace(evaluacion) -> dict:
    trace = evaluacion.trace
    return _record(
        evaluacion,
        subject_id=_subject('cliente', trace.cliente_id), domain='gym.autoridad_diaria',
        level='conocimiento_provisional', claim_code=evaluacion.resultado,
        status='evaluada', observed_at=evaluacion.creado_en,
        evidence_refs=[_record_id(trace)],
        derived_by='entrenos.GymDecisionTraceEvaluation',
        conditions={'senales_posteriores': evaluacion.senales_posteriores},
        owner={'type': 'subject', 'id': _subject('cliente', trace.cliente_id)},
        missing_fields=['valid_from', 'valid_until'],
    )


def adaptar_perfil_adaptacion(perfil) -> dict:
    return _record(
        perfil,
        subject_id=_subject('cliente', perfil.cliente_id), domain='gym.adaptacion',
        level='conocimiento_provisional', claim_code='perfil_adaptacion_ejercicio',
        status='vigente', confidence_value=perfil.confianza,
        confidence_scale='legacy_text', confidence_source='GymAdaptationProfile.confianza',
        observed_at=perfil.fecha_actualizacion,
        evidence_refs=(), derived_by='entrenos.GymAdaptationProfile',
        conditions={
            'ejercicio': perfil.ejercicio,
            'decisiones_totales': perfil.decisiones_totales,
            'decisiones_validadas': perfil.decisiones_validadas,
            'decisiones_fallidas': perfil.decisiones_fallidas,
        },
        owner={'type': 'subject', 'id': _subject('cliente', perfil.cliente_id)},
        missing_fields=['evidence_refs', 'valid_from', 'valid_until'],
    )


def _operaciones_cierre_para_manual(manual) -> list:
    from diario.models import CierreNocturnoOperacion

    candidatas = CierreNocturnoOperacion.objects.filter(
        entrada__prosoche_mes__usuario_id=manual.user_id,
        estado__in=('completed', 'superseded'), resultado__schema_version=2,
    ).order_by('pk')
    return [
        op for op in candidatas
        if any(
            isinstance(item, dict) and item.get('id') == manual.pk
            for item in (((op.resultado or {}).get('ledger') or {}).get('manual') or [])
        )
    ]


def adaptar_manual_david(manual, *, operaciones_cierre=None) -> dict:
    operaciones = (
        _operaciones_cierre_para_manual(manual)
        if operaciones_cierre is None else operaciones_cierre
    )
    refs = []
    if manual.fuente_mensaje_id:
        refs.append(f'joi.mensajejoi:{manual.fuente_mensaje_id}')
    refs.extend(_record_id(op) for op in operaciones)
    automatic_synthesis = bool(operaciones)
    nivel = {
        'preferencia': 'preferencia', 'patron': 'patron',
        'hipotesis': 'hipotesis', 'contradiccion': 'hipotesis',
    }.get(manual.tipo, 'conocimiento_provisional')
    contradictions = []
    if manual.hipotesis_contraria:
        contradictions.append({
            'claim_fingerprint': hashlib.sha256(
                manual.hipotesis_contraria.encode('utf-8')
            ).hexdigest(),
            'status': 'reported', 'winner': None,
        })
    return _record(
        manual,
        subject_id=_subject('user', manual.user_id), domain='joi.manual', level=nivel,
        claim_code=manual.tipo, claim_text=None,
        status=manual.estado, confidence_value=manual.confianza,
        confidence_scale='0_1', confidence_source='ManualDavid.confianza',
        observed_at=manual.ultima_evidencia or manual.creado_en,
        valid_from=manual.creado_en, evidence_refs=refs,
        derived_by='diario.cierre_nocturno' if automatic_synthesis else f'joi.ManualDavid.{manual.origen}',
        consent={
            'status': 'not_recorded' if manual.origen == 'patron_detectado' else 'user_correction',
            'source': 'ManualDavid.origen',
        },
        conditions={
            'automatic_synthesis': automatic_synthesis,
            'correction_status': 'not_recorded' if automatic_synthesis else 'source_feedback_error',
            'activa_flag': manual.activa,
            'estado_flag': manual.estado,
        },
        owner={'type': 'subject', 'id': _subject('user', manual.user_id)},
        contradictions=contradictions,
        missing_fields=(['evidence_refs'] if not refs else []) + ['valid_until'],
    )


def adaptar_narrativa(narrativa) -> dict:
    return _record(
        narrativa,
        subject_id=_subject('user', narrativa.user_id), domain='joi.narrativa',
        level='narrativa', claim_code='narrativa_activa', claim_text=None,
        status=narrativa.estado, confidence_value=narrativa.confianza,
        confidence_scale='0_1', confidence_source='NarrativaActiva.confianza',
        observed_at=narrativa.actualizado_en, valid_from=narrativa.creado_en,
        evidence_refs=(), derived_by='joi.NarrativaActiva',
        conditions={
            'version': narrativa.version,
            'capas_presentes': [
                name for name in ('capa_corta', 'capa_media', 'capa_larga')
                if getattr(narrativa, name)
            ],
        },
        owner={'type': 'subject', 'id': _subject('user', narrativa.user_id)},
        missing_fields=['evidence_refs', 'valid_until'],
    )


def adaptar_recuerdo(recuerdo) -> dict:
    return _record(
        recuerdo,
        subject_id=_subject('user', recuerdo.user_id), domain='joi.memoria_emocional',
        level='hecho', claim_code='recuerdo_emocional', claim_text=None,
        status='registrado', observed_at=recuerdo.fecha,
        valid_from=recuerdo.fecha, valid_until=recuerdo.fecha,
        evidence_refs=[_record_id(recuerdo)], derived_by='joi.RecuerdoEmocional',
        conditions={'contexto_presente': bool(recuerdo.contexto)},
        owner={'type': 'subject', 'id': _subject('user', recuerdo.user_id)},
    )


def adaptar_cierre_diario(entrada) -> dict:
    refs = [_record_id(entrada)]
    refs.extend(
        _record_id(op) for op in entrada.operaciones_cierre.all()
        if op.estado in ('completed', 'superseded')
    )
    return _record(
        entrada,
        subject_id=_subject('user', entrada.prosoche_mes.usuario_id),
        domain='diario.cierre', level='hecho', claim_code='cierre_diario_confirmado',
        status='confirmado' if entrada.cierre_confirmado_en else 'no_confirmado',
        observed_at=entrada.cierre_confirmado_en or entrada.fecha_actualizacion,
        valid_from=entrada.fecha, valid_until=entrada.fecha,
        evidence_refs=refs, derived_by='diario.ProsocheDiario',
        conditions={
            'cierre_version': entrada.cierre_version,
            'payload_hash_presente': bool(entrada.cierre_payload_hash),
        },
        owner={'type': 'subject', 'id': _subject('user', entrada.prosoche_mes.usuario_id)},
    )


def adaptar_seguimiento_vires(seguimiento) -> dict:
    """Puente corporal factual; excluye deliberadamente campos de texto libre."""
    señales = {
        'horas_sueno': float(seguimiento.horas_sueno) if seguimiento.horas_sueno is not None else None,
        'calidad_sueno': seguimiento.calidad_sueno,
        'nivel_energia': seguimiento.nivel_energia,
        'nivel_estres': seguimiento.nivel_estres,
        'molestia_zona': seguimiento.molestia_zona or None,
        'cuerpo_cierre': seguimiento.cuerpo_cierre or None,
        'entrenamiento_realizado': seguimiento.entrenamiento_realizado,
    }
    return _record(
        seguimiento,
        subject_id=_subject('user', seguimiento.usuario_id),
        domain='diario.puente_fisico', level='hecho', claim_code='seguimiento_vires',
        status='registrado', observed_at=seguimiento.fecha,
        valid_from=seguimiento.fecha, valid_until=seguimiento.fecha,
        evidence_refs=[_record_id(seguimiento)], derived_by='diario.SeguimientoVires',
        conditions={'signals': señales, 'free_text_excluded': True},
        owner={'type': 'subject', 'id': _subject('user', seguimiento.usuario_id)},
    )


def _finding(code: str, record: dict, **evidence) -> dict:
    return {
        'tipo_registro': 'hallazgo', 'code': code,
        'record_id': record['record_id'], 'subject_id': record['subject_id'],
        'evidence': evidence, 'schema_version': SCHEMA_VERSION,
    }


def auditar_registros(records: Iterable[dict]) -> list[dict]:
    findings = []
    for record in sorted(records, key=lambda item: item['record_id']):
        conditions = record.get('conditions') or {}
        if record['level'] == 'conocimiento_consolidado' and not record['evidence_refs']:
            findings.append(_finding('promocion_sin_evidencia', record))
        if record['level'] == 'hipotesis' and record['valid_until'] is None:
            findings.append(_finding('hipotesis_sin_vigencia', record))
        if record['level'] == 'preferencia' and record['consent']['status'] not in (
            'confirmed', 'contract_asserted', 'user_correction',
        ):
            findings.append(_finding('preferencia_sin_consentimiento', record))
        if record['level'] == 'preferencia' and conditions.get('manual_david_id') is not None:
            findings.append(_finding(
                'preferencia_duplicada_manual_gym', record,
                manual_david_id=conditions['manual_david_id'],
            ))
        if record['domain'] == 'joi.manual' and (
            conditions.get('activa_flag') != (conditions.get('estado_flag') == 'activa')
        ):
            findings.append(_finding('manual_estado_activa_divergente', record))
        if record['domain'] == 'gym.autoridad_diaria' and record['level'] == 'senal' and not conditions.get('trace_version_identifiable'):
            findings.append(_finding('trace_version_no_identificable', record))
        if record['domain'] == 'gym.adaptacion' and (
            record['valid_from'] is None or record['valid_until'] is None
        ):
            findings.append(_finding('perfil_sin_ventana', record))
        if conditions.get('evidence_refs_declared') and (
            conditions.get('evidence_count') != conditions.get('evidence_refs_count')
        ):
            findings.append(_finding(
                'evidencia_count_divergente', record,
                evidence_count=conditions.get('evidence_count'),
                evidence_refs_count=conditions.get('evidence_refs_count'),
            ))
        if conditions.get('used_as_source') is True and record['level'] == 'narrativa':
            findings.append(_finding('narrativa_usada_como_fuente', record))
        if not record.get('owner'):
            findings.append(_finding('registro_sin_owner', record))
        if record['status'] == 'revocada' and (
            record['valid_until'] is None
            or not any('revocar' in ref or 'revocation' in ref for ref in record['evidence_refs'])
        ):
            findings.append(_finding('revocacion_sin_trazabilidad', record))
        if conditions.get('raw_diary_text_crossed') is True:
            findings.append(_finding('texto_diario_cruzado', record))
    return sorted(findings, key=lambda item: (item['code'], item['record_id']))


def recopilar_memoria(cliente_id: int, *, desde=None, hasta=None, limit: int = 500) -> dict:
    """Recopila proyecciones sin escribir. ``limit`` se aplica globalmente."""
    from clientes.models import Cliente
    from diario.models import ProsocheDiario, SeguimientoVires
    from entrenos.models import (
        GymAdaptationProfile, GymDecisionLog, GymDecisionTrace,
        GymDecisionTraceEvaluation, PreferenciaPlanAprendida,
    )
    from joi.models import ManualDavid, NarrativaActiva, RecuerdoEmocional

    cliente = Cliente.objects.only('pk', 'user_id').get(pk=cliente_id)
    desde = date.fromisoformat(desde) if isinstance(desde, str) else desde
    hasta = date.fromisoformat(hasta) if isinstance(hasta, str) else hasta
    records = []

    preferencias = PreferenciaPlanAprendida.objects.filter(cliente_id=cliente_id)
    if desde:
        preferencias = preferencias.filter(ultima_confirmacion__gte=desde)
    if hasta:
        preferencias = preferencias.filter(fecha_inicio__lte=hasta)
    records.extend(adaptar_preferencia_plan(x) for x in preferencias.order_by('pk'))

    decisiones = GymDecisionLog.objects.filter(cliente_id=cliente_id)
    if desde:
        decisiones = decisiones.filter(fecha_creacion__date__gte=desde)
    if hasta:
        decisiones = decisiones.filter(fecha_creacion__date__lte=hasta)
    records.extend(adaptar_decision_log(x) for x in decisiones.order_by('pk'))

    traces = GymDecisionTrace.objects.filter(cliente_id=cliente_id)
    if desde:
        traces = traces.filter(fecha__gte=desde)
    if hasta:
        traces = traces.filter(fecha__lte=hasta)
    traces = list(traces.order_by('pk'))
    records.extend(adaptar_trace(x) for x in traces)
    evaluations = GymDecisionTraceEvaluation.objects.filter(trace__cliente_id=cliente_id)
    if desde:
        evaluations = evaluations.filter(trace__fecha__gte=desde)
    if hasta:
        evaluations = evaluations.filter(trace__fecha__lte=hasta)
    records.extend(adaptar_evaluacion_trace(x) for x in evaluations.select_related('trace').order_by('pk'))

    records.extend(
        adaptar_perfil_adaptacion(x)
        for x in GymAdaptationProfile.objects.filter(cliente_id=cliente_id).order_by('pk')
    )

    manuals = ManualDavid.objects.filter(user_id=cliente.user_id)
    if desde:
        manuals = manuals.filter(Q(ultima_evidencia__gte=desde) | Q(ultima_evidencia__isnull=True, creado_en__date__gte=desde))
    if hasta:
        manuals = manuals.filter(creado_en__date__lte=hasta)
    records.extend(adaptar_manual_david(x) for x in manuals.order_by('pk'))

    narratives = NarrativaActiva.objects.filter(user_id=cliente.user_id)
    if desde:
        narratives = narratives.filter(actualizado_en__date__gte=desde)
    if hasta:
        narratives = narratives.filter(creado_en__date__lte=hasta)
    records.extend(adaptar_narrativa(x) for x in narratives.order_by('pk'))

    recuerdos = RecuerdoEmocional.objects.filter(user_id=cliente.user_id)
    if desde:
        recuerdos = recuerdos.filter(fecha__date__gte=desde)
    if hasta:
        recuerdos = recuerdos.filter(fecha__date__lte=hasta)
    records.extend(adaptar_recuerdo(x) for x in recuerdos.order_by('pk'))

    cierres = ProsocheDiario.objects.filter(
        prosoche_mes__usuario_id=cliente.user_id,
        cierre_confirmado_en__isnull=False,
    ).select_related('prosoche_mes').prefetch_related('operaciones_cierre')
    if desde:
        cierres = cierres.filter(fecha__gte=desde)
    if hasta:
        cierres = cierres.filter(fecha__lte=hasta)
    records.extend(adaptar_cierre_diario(x) for x in cierres.order_by('pk'))

    vires = SeguimientoVires.objects.filter(usuario_id=cliente.user_id)
    if desde:
        vires = vires.filter(fecha__gte=desde)
    if hasta:
        vires = vires.filter(fecha__lte=hasta)
    records.extend(adaptar_seguimiento_vires(x) for x in vires.order_by('pk'))

    records.sort(key=lambda item: item['record_id'])
    total = len(records)
    limited = records[:max(0, limit)]
    findings = auditar_registros(limited)
    return {
        'records': limited,
        'findings': findings,
        'total': total,
        'truncated': max(0, total - len(limited)),
    }


def construir_resumen(resultado: dict, *, cliente_id: int, desde=None, hasta=None, limit=500) -> dict:
    counts = Counter(item['code'] for item in resultado['findings'])
    return {
        'tipo_registro': 'resumen', 'schema_version': SCHEMA_VERSION,
        'cliente_id': cliente_id, 'desde': _iso(desde), 'hasta': _iso(hasta),
        'limit': limit, 'evaluados': resultado['total'],
        'emitidos': len(resultado['records']), 'truncados': resultado['truncated'],
        'hallazgos': len(resultado['findings']),
        'counts_by_code': dict(sorted(counts.items())),
        'solo_lectura': True,
        'omitidos_no_determinables': [
            'narrativa_usada_como_fuente', 'texto_diario_cruzado',
        ],
    }
