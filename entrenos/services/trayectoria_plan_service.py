"""Lectura longitudinal del plan Gym sin crear ni alterar autoridad."""

from datetime import date, timedelta

from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
from django.utils import timezone

from entrenos.models import (
    ContratoBloqueGym,
    ContratoSemanalGym,
    EvaluacionSemanalGym,
    SesionProgramada,
)
from entrenos.services.proyeccion_bloque_gym_service import proyectar_bloque_gym


def _inicio_semana(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _generar_plan_helms(cliente, anio):
    """Usa deliberadamente la misma fuente canónica que el calendario anual."""
    perfil = crear_perfil_desde_cliente(cliente)
    perfil.maximos_actuales = cliente.one_rm_data or {}
    perfil.año_planificacion = anio
    return PlanificadorHelms(perfil).generar_plan_anual()


def _periodizacion_actual(cliente, fecha, limitations):
    try:
        plan = _generar_plan_helms(cliente, fecha.year) or {}
    except Exception:  # la trayectoria sigue disponible aunque el plan anual no lo esté
        limitations.append('plan_helms_no_disponible')
        return None, None

    bloques = plan.get('plan_por_bloques') or []
    primer_lunes = date(fecha.year, 1, 1)
    primer_lunes += timedelta(days=(7 - primer_lunes.weekday()) % 7)
    cursor = primer_lunes
    for indice, bloque in enumerate(bloques, start=1):
        duracion = bloque.get('duracion')
        if not isinstance(duracion, int) or duracion < 1:
            limitations.append('duracion_fase_helms_no_determinable')
            return None, plan
        fin = cursor + timedelta(weeks=duracion) - timedelta(days=1)
        if cursor <= fecha <= fin:
            return {
                'carril': 'Fase de periodización',
                'fuente': 'PlanificadorHelms.generar_plan_anual',
                'indice': indice,
                'nombre': bloque.get('nombre'),
                'objetivo': bloque.get('objetivo'),
                'inicio': cursor,
                'fin': fin,
                'semana_actual': ((fecha - cursor).days // 7) + 1,
                'semanas': duracion,
            }, plan
        cursor = fin + timedelta(days=1)
    limitations.append('fase_helms_fuera_de_ventana')
    return None, plan


def _serializar_evaluacion_semanal(contrato):
    evaluacion = EvaluacionSemanalGym.objects.filter(contrato=contrato).first()
    if evaluacion is None:
        return None
    return {
        'id': evaluacion.pk,
        'estado_cumplimiento': evaluacion.estado_cumplimiento,
        'sesiones_completadas': evaluacion.sesiones_completadas,
        'estado_revision': evaluacion.estado_revision,
    }


def _serializar_sesion(sesion):
    efectiva = sesion.pospuesta_hasta or sesion.fecha_prevista
    return {
        'id': sesion.pk,
        'nombre': sesion.nombre_sesion or f'Sesión {sesion.dia_numero or sesion.pk}',
        'estado': sesion.estado,
        'fecha_prevista': sesion.fecha_prevista,
        'fecha_pospuesta': sesion.pospuesta_hasta,
        'fecha_efectiva': efectiva,
        'fecha_realizada': sesion.fecha_realizada,
        'realizada': sesion.estado == SesionProgramada.ESTADO_COMPLETADA,
    }


def _proximo_hito(fecha, sesiones, evaluacion, bloque, periodizacion):
    candidatas = sorted(
        (s for s in sesiones if s['estado'] == SesionProgramada.ESTADO_PENDIENTE and s['fecha_efectiva'] >= fecha),
        key=lambda s: (s['fecha_efectiva'], s['id']),
    )
    if candidatas:
        sesion = candidatas[0]
        return {
            'tipo': 'sesion', 'fecha': sesion['fecha_efectiva'],
            'etiqueta': sesion['nombre'], 'sesion_id': sesion['id'],
        }
    if evaluacion and evaluacion['estado_revision'] == EvaluacionSemanalGym.ESTADO_PENDIENTE:
        return {'tipo': 'revision_semanal', 'fecha': None, 'etiqueta': 'Revisar la semana'}
    if bloque and bloque.get('rango', {}).get('fin') and bloque['rango']['fin'] >= fecha:
        return {'tipo': 'fin_bloque', 'fecha': bloque['rango']['fin'], 'etiqueta': 'Cierre del bloque'}
    if periodizacion and periodizacion.get('fin') and periodizacion['fin'] >= fecha:
        return {'tipo': 'fin_fase', 'fecha': periodizacion['fin'], 'etiqueta': 'Fin de la fase'}
    return None


def proyectar_trayectoria_plan(cliente, *, fecha=None):
    """Compone evidencia persistida y el plan Helms; nunca materializa ni evalúa."""
    fecha = fecha or timezone.localdate()
    limitations = []
    bloque_base = proyectar_bloque_gym(cliente, fecha=fecha)
    periodizacion, _plan = _periodizacion_actual(cliente, fecha, limitations)

    if not bloque_base.get('disponible'):
        limitations.append(bloque_base.get('estado_evidencia', 'bloque_no_disponible'))
        return {
            'schema_version': 1,
            'solo_lectura': True,
            'fecha_corte': fecha,
            'estado': 'unknown',
            'periodizacion': periodizacion,
            'bloque': None,
            'semana': None,
            'proximo_hito': None,
            'limitations': list(dict.fromkeys(limitations)),
        }

    bloque_modelo = ContratoBloqueGym.objects.filter(
        pk=bloque_base['bloque_id'], cliente=cliente,
    ).first()
    bloque = {
        'carril': 'Objetivo del bloque',
        'id': bloque_base['bloque_id'],
        'version': bloque_base['version'],
        'estado': bloque_base['estado'],
        'objetivo': bloque_base['objetivo_principal'],
        'objetivos_secundarios': bloque_base['objetivos_secundarios'],
        'inicio': bloque_base['rango']['inicio'],
        'fin': bloque_base['rango']['fin'],
        'semana_actual': bloque_base.get('semana_actual'),
        'semanas': bloque_base['semanas_previstas'],
        'rango': bloque_base['rango'],
    }

    semana = None
    contrato = ContratoSemanalGym.objects.filter(
        cliente=cliente,
        bloque_id=bloque_base['bloque_id'],
        semana=_inicio_semana(fecha),
    ).first()
    if contrato is None:
        limitations.append('semana_no_materializada')
    else:
        sesiones = sorted(
            (_serializar_sesion(s) for s in contrato.sesiones.filter(cliente=cliente)),
            key=lambda s: (s['fecha_efectiva'], s['id']),
        )
        semana = {
            'id': contrato.pk,
            'indice': contrato.indice_semana_bloque,
            'inicio': contrato.semana,
            'fin': contrato.semana + timedelta(days=6),
            'objetivo_sesiones': contrato.objetivo_sesiones,
            'minimo_valido': contrato.minimo_valido,
            'sesiones': sesiones,
            'evaluacion': _serializar_evaluacion_semanal(contrato),
        }

    evaluacion_bloque = None
    if bloque_modelo is not None:
        persistida = bloque_modelo.evaluaciones.order_by('-version_calculo', '-pk').first()
        if persistida is not None:
            evaluacion_bloque = {
                'id': persistida.pk,
                'estado_resultado': persistida.estado_resultado,
                'estado_revision': persistida.estado_revision,
            }

    proximo = _proximo_hito(
        fecha,
        semana['sesiones'] if semana else [],
        semana['evaluacion'] if semana else None,
        bloque,
        periodizacion,
    )
    if proximo is None:
        limitations.append('proximo_hito_no_determinable')

    return {
        'schema_version': 1,
        'solo_lectura': True,
        'fecha_corte': fecha,
        'estado': 'available' if periodizacion else 'partial',
        'periodizacion': periodizacion,
        'bloque': bloque,
        'semana': semana,
        'evaluacion_bloque': evaluacion_bloque,
        'proximo_hito': proximo,
        'limitations': list(dict.fromkeys(limitations)),
    }
