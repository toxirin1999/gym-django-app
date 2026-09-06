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
    **extras,
):
    payload = {
        'fecha': referencia.isoformat(),
        'modo': 'apply' if aplicar else 'dry-run',
        'operacion': operacion,
        'resultados': resultados,
        'semana': semana,
        'solo_lectura': (not aplicar if solo_lectura is None else solo_lectura),
    }
    payload.update(extras)
    return payload


def _cerrar_semana(semana, referencia, aplicar, *, solo_si_concluida=False):
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
            elif solo_si_concluida:
                sesiones_total = contrato.sesiones.count()
                sesiones_pendientes = contrato.sesiones.filter(estado='pendiente').count()
                if not sesiones_total or sesiones_pendientes:
                    fila.update({
                        'estado': 'pendiente_hasta_lunes',
                        'sesiones_pendientes': sesiones_pendientes,
                    })
                    resultados.append(fila)
                    continue
                if aplicar:
                    # El evaluador considera la semana abierta durante el propio
                    # domingo. Aquí solo llegamos cuando todas sus sesiones ya
                    # concluyeron, así que usamos el instante lógico de cierre
                    # (lunes) sin alterar la fecha real de referencia del ciclo.
                    hoy_evaluacion = referencia + timedelta(days=1)
                    evaluacion = evaluar_y_persistir_contrato_semanal_gym(
                        contrato, hoy=hoy_evaluacion,
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


def _cerrar_semana_anterior(referencia, aplicar):
    return _cerrar_semana(
        referencia - timedelta(days=7), referencia, aplicar,
    )


def operar_semana_gym(*, fecha_referencia=None, aplicar=False):
    """Cierra si procede y abre el domingo; el lunes completa el cierre pendiente."""
    referencia = fecha_referencia or timezone.localdate()
    if referencia.weekday() == 6:
        semana_actual = referencia - timedelta(days=6)
        cierre = _cerrar_semana(
            semana_actual,
            referencia,
            aplicar,
            solo_si_concluida=True,
        )
        apertura = preparar_semana_gym(
            fecha_referencia=referencia,
            aplicar=aplicar,
            solo_domingo=True,
        )
        return _base(
            referencia, aplicar, 'apertura_semanal', apertura.get('resultados', []),
            semana=apertura.get('semana'),
            cierre_semana_actual=cierre,
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
