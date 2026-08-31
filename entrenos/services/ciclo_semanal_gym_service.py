"""Orquestación semanal Gym invocable, segura e idempotente."""

from datetime import timedelta

from django.utils import timezone

from entrenos.models import ContratoSemanalGym, EvaluacionSemanalGym
from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym
from entrenos.services.evaluacion_semanal_gym_service import (
    _snapshot,
    evaluar_y_persistir_contrato_semanal_gym,
)


def _base(
    referencia, aplicar, operacion, resultados, *, semana=None, solo_lectura=None,
):
    return {
        'fecha': referencia.isoformat(),
        'modo': 'apply' if aplicar else 'dry-run',
        'operacion': operacion,
        'resultados': resultados,
        'semana': semana,
        'solo_lectura': (not aplicar if solo_lectura is None else solo_lectura),
    }


def _cerrar_semana_anterior(referencia, aplicar):
    semana = referencia - timedelta(days=7)
    contratos = list(
        ContratoSemanalGym.objects.filter(semana=semana)
        .select_related('cliente')
        .prefetch_related('sesiones')
        .order_by('cliente_id', 'pk')
    )
    resultados = []
    for contrato in contratos:
        fila = {
            'cliente_id': contrato.cliente_id,
            'contrato_id': contrato.pk,
            'semana': semana.isoformat(),
        }
        try:
            existente = EvaluacionSemanalGym.objects.filter(contrato=contrato).first()
            if existente is not None:
                fila.update({
                    'estado': 'ya_evaluada',
                    'estado_revision': existente.estado_revision,
                    'evaluacion_id': existente.pk,
                })
            elif aplicar:
                evaluacion = evaluar_y_persistir_contrato_semanal_gym(
                    contrato, hoy=referencia,
                )
                fila.update({
                    'estado': 'evaluada',
                    'estado_cumplimiento': evaluacion.estado_cumplimiento,
                    'estado_revision': evaluacion.estado_revision,
                    'evaluacion_id': evaluacion.pk,
                    'sesiones_completadas': evaluacion.sesiones_completadas,
                })
            else:
                evidencia = _snapshot(contrato)
                fila.update({
                    'estado': 'previsualizada',
                    'estado_cumplimiento': evidencia['estado_cumplimiento'],
                    'evaluacion_id': None,
                    'sesiones_completadas': evidencia['sesiones_completadas'],
                })
        except Exception as exc:  # aislamiento operativo por contrato/cliente
            fila.update({
                'codigo': type(exc).__name__,
                'detalle': str(exc),
                'estado': 'error',
            })
        resultados.append(fila)
    return resultados


def operar_semana_gym(*, fecha_referencia=None, aplicar=False):
    """Abre el domingo, cierra el lunes y no opera el resto de días."""
    referencia = fecha_referencia or timezone.localdate()
    if referencia.weekday() == 6:
        apertura = preparar_semana_gym(
            fecha_referencia=referencia,
            aplicar=aplicar,
            solo_domingo=True,
        )
        return _base(
            referencia, aplicar, 'apertura_semanal', apertura.get('resultados', []),
            semana=apertura.get('semana'),
        )
    if referencia.weekday() == 0:
        return _base(
            referencia,
            aplicar,
            'cierre_semanal',
            _cerrar_semana_anterior(referencia, aplicar),
            semana=(referencia - timedelta(days=7)).isoformat(),
        )
    return _base(
        referencia, aplicar, 'sin_operacion', [], solo_lectura=True,
    )
