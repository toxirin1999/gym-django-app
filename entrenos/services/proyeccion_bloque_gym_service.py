"""Proyección read-only del contrato de bloque Gym para superficies de lectura."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from entrenos.models import (
    ContratoBloqueGym,
    ContratoSemanalGym,
    EvaluacionBloqueGym,
    EvaluacionSemanalGym,
    SesionProgramada,
)


def _inicio_semana(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _estado_cumplimiento(completadas, objetivo, minimo):
    if completadas >= objetivo:
        return 'objetivo'
    if completadas >= minimo:
        return 'minimo_valido'
    return 'insuficiente'


def proyectar_bloque_gym(cliente, *, fecha=None):
    """Devuelve evidencia ya persistida; nunca materializa ni evalúa contratos."""
    fecha = fecha or timezone.localdate()
    bloques_abiertos = list((
        ContratoBloqueGym.objects
        .filter(
            cliente=cliente,
            estado__in=(
                ContratoBloqueGym.ESTADO_ACTIVO,
                ContratoBloqueGym.ESTADO_PAUSADO,
            ),
        )
        .select_related('estrategia')
        [:2]
    ))
    if not bloques_abiertos:
        return {
            'disponible': False,
            'estado_evidencia': 'evidencia_no_disponible',
            'progreso_disponible': False,
            'requiere_decision': False,
        }
    if len(bloques_abiertos) > 1:
        return {
            'disponible': False,
            'estado_evidencia': 'autoridad_ambigua',
            'progreso_disponible': False,
            'requiere_decision': False,
        }
    bloque = bloques_abiertos[0]

    if fecha < bloque.semana_inicio:
        fase_temporal = 'proximo'
    elif fecha > bloque.semana_fin_prevista:
        fase_temporal = 'pendiente_cierre'
    else:
        fase_temporal = 'en_curso'
    resultado = {
        'disponible': True,
        'bloque_id': bloque.pk,
        'version': bloque.version,
        'estado': bloque.estado,
        'fase_temporal': fase_temporal,
        'semanas_previstas': bloque.semanas_previstas,
        'objetivo_principal': bloque.objetivo_principal,
        'objetivos_secundarios': list(bloque.objetivos_secundarios or []),
        'rango': {
            'inicio': bloque.semana_inicio,
            'fin': bloque.semana_fin_prevista,
        },
        'estado_evidencia': 'evidencia_no_disponible',
        'progreso_disponible': False,
        'requiere_decision': False,
    }

    if fase_temporal == 'en_curso':
        resultado['semana_actual'] = ((fecha - bloque.semana_inicio).days // 7) + 1

    contrato = None
    if fase_temporal == 'en_curso':
        contrato = (
        ContratoSemanalGym.objects
        .filter(
            cliente=cliente,
            bloque=bloque,
            semana=_inicio_semana(fecha),
        )
        .first()
        )
    if contrato is not None:
        completadas = contrato.sesiones.filter(
            cliente=cliente,
            estado=SesionProgramada.ESTADO_COMPLETADA,
        ).count()
        resultado.update({
            'contrato_semanal_id': contrato.pk,
            'progreso_disponible': True,
            'estado_evidencia': 'evidencia_disponible',
            'sesiones_completadas': completadas,
            'objetivo_sesiones': contrato.objetivo_sesiones,
            'minimo_valido': contrato.minimo_valido,
            'estado_cumplimiento': _estado_cumplimiento(
                completadas, contrato.objetivo_sesiones, contrato.minimo_valido,
            ),
        })
        evaluacion = EvaluacionSemanalGym.objects.filter(contrato=contrato).first()
        if evaluacion is not None:
            resultado['evaluacion_semanal'] = {
                'id': evaluacion.pk,
                'estado_revision': evaluacion.estado_revision,
                'estado_cumplimiento': evaluacion.estado_cumplimiento,
            }
            if evaluacion.estado_revision == EvaluacionSemanalGym.ESTADO_PENDIENTE:
                resultado['requiere_decision'] = True

    cierre = (
        EvaluacionBloqueGym.objects
        .filter(
            bloque=bloque,
            estado_revision=EvaluacionBloqueGym.REVISION_PENDIENTE,
        )
        .order_by('-version_calculo', '-pk')
        .first()
    )
    if cierre is not None:
        resultado['cierre_bloque'] = {
            'id': cierre.pk,
            'estado_revision': cierre.estado_revision,
            'estado_resultado': cierre.estado_resultado,
        }
        resultado['requiere_decision'] = True

    if resultado['requiere_decision']:
        resultado['url_decision'] = reverse('clientes:plan_decisiones')
    return resultado
