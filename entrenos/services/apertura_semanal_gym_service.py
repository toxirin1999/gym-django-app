"""Apertura operativa, explícita e idempotente de la próxima semana Gym."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from entrenos.models import ContratoBloqueGym, ContratoSemanalGym
from entrenos.services.contrato_bloque_gym_service import _estrategia_vigente
from entrenos.services.estrategia_semanal_gym_service import (
    ContratoSemanalIncompleto,
    DivergenciaBloqueSemanal,
    materializar_contrato_semanal_gym,
    previsualizar_contrato_semanal_gym,
)


def semana_objetivo(fecha_referencia=None):
    """Devuelve el lunes inclusivo siguiente a la fecha de referencia."""
    referencia = fecha_referencia or timezone.localdate()
    return referencia + timedelta(days=(-referencia.weekday()) % 7)


def _validar_coherencia(bloque, estrategia, contrato=None):
    if estrategia is None or (
        bloque.estrategia_id != estrategia.pk
        or bloque.objetivo_sesiones != estrategia.objetivo_sesiones
        or bloque.minimo_valido != estrategia.minimo_valido
    ):
        raise DivergenciaBloqueSemanal(
            'La estrategia semanal vigente diverge del snapshot aprobado del bloque.'
        )
    if contrato is not None:
        indice = ((contrato.semana - bloque.semana_inicio).days // 7) + 1
        if (
            contrato.bloque_id != bloque.pk
            or contrato.estrategia_id != estrategia.pk
            or contrato.indice_semana_bloque != indice
            or contrato.objetivo_sesiones != bloque.objetivo_sesiones
            or contrato.minimo_valido != bloque.minimo_valido
        ):
            raise DivergenciaBloqueSemanal(
                'El contrato semanal existente diverge del snapshot aprobado del bloque.'
            )


def _error(cliente_id, bloque_id, exc, codigo):
    return {
        'bloque_id': bloque_id,
        'cliente_id': cliente_id,
        'codigo': codigo,
        'detalle': str(exc),
        'estado': 'error',
    }


@transaction.atomic
def _materializar_desde_bloque(bloque, estrategia, semana):
    """Impide que un cambio concurrente deje un contrato semanal sin bloque."""
    vigente = ContratoBloqueGym.objects.select_for_update().get(pk=bloque.pk)
    if (
        vigente.estado != ContratoBloqueGym.ESTADO_ACTIVO
        or vigente.semana_inicio > semana
        or vigente.semana_fin_prevista < semana
    ):
        raise DivergenciaBloqueSemanal(
            'El bloque dejó de estar activo o de incluir la semana objetivo.'
        )
    _validar_coherencia(vigente, estrategia)
    contrato = materializar_contrato_semanal_gym(vigente.cliente, semana)
    _validar_coherencia(vigente, estrategia, contrato)
    return contrato


def preparar_semana_gym(*, fecha_referencia=None, aplicar=False, solo_domingo=False):
    """Previsualiza o materializa la semana de todos los bloques elegibles."""
    referencia = fecha_referencia or timezone.localdate()
    semana = semana_objetivo(referencia)
    if solo_domingo and referencia.weekday() != 6:
        return {
            'estado': 'omitida_programacion',
            'fecha_referencia': referencia.isoformat(),
            'modo': 'apply' if aplicar else 'dry-run',
            'resultados': [],
            'semana': semana.isoformat(),
            'solo_domingo': True,
            'solo_lectura': True,
        }

    bloques = list(
        ContratoBloqueGym.objects.filter(
            estado=ContratoBloqueGym.ESTADO_ACTIVO,
            semana_inicio__lte=semana,
            semana_fin_prevista__gte=semana,
        ).select_related('cliente', 'estrategia').order_by('cliente_id', 'pk')
    )
    resultados = []
    for bloque in bloques:
        cliente = bloque.cliente
        try:
            estrategia = _estrategia_vigente(cliente, semana)
            existente = ContratoSemanalGym.objects.filter(
                cliente=cliente, semana=semana,
            ).first()
            _validar_coherencia(bloque, estrategia, existente)
            if existente is not None:
                resultados.append({
                    'bloque_id': bloque.pk,
                    'cliente_id': cliente.pk,
                    'contrato_id': existente.pk,
                    'estado': 'ya_materializada',
                })
                continue

            if not aplicar:
                propuestas = previsualizar_contrato_semanal_gym(cliente, semana)
                resultados.append({
                    'bloque_id': bloque.pk,
                    'cliente_id': cliente.pk,
                    'estado': 'previsualizada',
                    'sesiones_previstas': len(propuestas),
                })
                continue

            contrato = _materializar_desde_bloque(bloque, estrategia, semana)
            resultados.append({
                'bloque_id': bloque.pk,
                'cliente_id': cliente.pk,
                'contrato_id': contrato.pk,
                'estado': 'materializada',
                'sesiones_materializadas': contrato.sesiones.count(),
            })
        except DivergenciaBloqueSemanal as exc:
            resultados.append(_error(cliente.pk, bloque.pk, exc, 'divergencia_bloque'))
        except IntegrityError as exc:
            # La transacción interna del materializador ya se revirtió. Una
            # carrera legítima puede haber materializado la misma identidad.
            concurrente = ContratoSemanalGym.objects.filter(
                cliente=cliente, semana=semana,
            ).first()
            if concurrente is not None:
                try:
                    _validar_coherencia(bloque, _estrategia_vigente(cliente, semana), concurrente)
                except DivergenciaBloqueSemanal as divergencia:
                    resultados.append(_error(
                        cliente.pk, bloque.pk, divergencia, 'divergencia_bloque',
                    ))
                else:
                    resultados.append({
                        'bloque_id': bloque.pk, 'cliente_id': cliente.pk,
                        'contrato_id': concurrente.pk,
                        'estado': 'ya_materializada', 'origen': 'carrera_concurrente',
                    })
            else:
                resultados.append(_error(
                    cliente.pk,
                    bloque.pk,
                    ValueError(
                        'Conflicto de integridad al materializar; no quedó un '
                        'contrato semanal coherente.'
                    ),
                    'carrera_integridad',
                ))
        except (ValueError, ContratoSemanalIncompleto) as exc:
            resultados.append(_error(cliente.pk, bloque.pk, exc, 'error_controlado'))

    return {
        'modo': 'apply' if aplicar else 'dry-run',
        'resultados': resultados,
        'semana': semana.isoformat(),
        'solo_lectura': not aplicar,
    }
