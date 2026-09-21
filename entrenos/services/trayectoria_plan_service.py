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
        return None, None, []

    bloques = plan.get('plan_por_bloques') or []
    # periodizacion_completa trae los parametros reales (reps/RPE/descanso) del
    # mismo generador que ya produce plan_por_bloques; se cruzan por nombre
    # porque es la unica clave estable comun a ambas listas (una las resume,
    # la otra las detalla) y evita una segunda llamada al planificador.
    detalle_por_nombre = {
        item.get('nombre'): item
        for item in (plan.get('metadata') or {}).get('periodizacion_completa') or []
    }
    primer_lunes = date(fecha.year, 1, 1)
    primer_lunes += timedelta(days=(7 - primer_lunes.weekday()) % 7)
    cursor = primer_lunes
    fases_anio = []
    actual = None
    for indice, bloque in enumerate(bloques, start=1):
        duracion = bloque.get('duracion')
        if not isinstance(duracion, int) or duracion < 1:
            limitations.append('duracion_fase_helms_no_determinable')
            return actual, plan, fases_anio
        fin = cursor + timedelta(weeks=duracion) - timedelta(days=1)
        detalle = detalle_por_nombre.get(bloque.get('nombre')) or {}
        estado_fase = 'completada' if fin < fecha else ('actual' if cursor <= fecha <= fin else 'pendiente')
        fase_info = {
            'indice': indice,
            'nombre': bloque.get('nombre'),
            'objetivo': bloque.get('objetivo'),
            'inicio': cursor,
            'fin': fin,
            'semanas': duracion,
            'estado': estado_fase,
            'semana_actual': ((fecha - cursor).days // 7) + 1 if estado_fase == 'actual' else None,
            'reps': detalle.get('rep_range'),
            'rpe_inicio': detalle.get('rpe_inicio'),
            'rpe_fin': detalle.get('rpe_fin'),
            'descanso_seg': detalle.get('descanso'),
        }
        fases_anio.append(fase_info)
        if estado_fase == 'actual':
            actual = {
                'carril': 'Fase de periodización',
                'fuente': 'PlanificadorHelms.generar_plan_anual',
                'indice': indice,
                'nombre': bloque.get('nombre'),
                'objetivo': bloque.get('objetivo'),
                'inicio': cursor,
                'fin': fin,
                'semana_actual': fase_info['semana_actual'],
                'semanas': duracion,
                'reps': fase_info['reps'],
                'rpe_inicio': fase_info['rpe_inicio'],
                'rpe_fin': fase_info['rpe_fin'],
                'descanso_seg': fase_info['descanso_seg'],
            }
        cursor = fin + timedelta(days=1)
    if actual is None:
        limitations.append('fase_helms_fuera_de_ventana')
    return actual, plan, fases_anio


def _macrociclo(fases_anio, periodizacion):
    """Deriva 'siguiente fase' y 'fases cerradas' del mismo listado que ya
    calculo _periodizacion_actual; no vuelve a llamar al planificador ni
    inventa datos que ese listado no traiga."""
    if not fases_anio:
        return None
    fases_cerradas = [f for f in fases_anio if f['estado'] == 'completada']
    siguiente_fase = None
    if periodizacion:
        candidatas = [f for f in fases_anio if f['indice'] == periodizacion['indice'] + 1]
        siguiente_fase = candidatas[0] if candidatas else None
    return {
        'fases': fases_anio,
        'siguiente_fase': siguiente_fase,
        'fases_cerradas': fases_cerradas,
    }


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
    completa = sesion.estado == SesionProgramada.ESTADO_COMPLETADA
    parcial = sesion.estado == SesionProgramada.ESTADO_PARCIAL
    return {
        'id': sesion.pk,
        'nombre': sesion.nombre_sesion or f'Sesión {sesion.dia_numero or sesion.pk}',
        'estado': sesion.estado,
        'fecha_prevista': sesion.fecha_prevista,
        'fecha_pospuesta': sesion.pospuesta_hasta,
        'fecha_efectiva': efectiva,
        'fecha_realizada': sesion.fecha_realizada,
        'realizada': completa or parcial,
        'completa': completa,
        'parcial': parcial,
    }


def _proximo_hito(fecha, semana, bloque, periodizacion):
    sesiones = semana['sesiones'] if semana else []
    evaluacion = semana['evaluacion'] if semana else None
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
    completadas = sum(1 for sesion in sesiones if sesion['realizada'])
    if (
        semana
        and bloque
        and completadas >= semana['objetivo_sesiones']
        and semana['indice'] < bloque['semanas']
    ):
        siguiente_inicio = semana['fin'] + timedelta(days=1)
        if siguiente_inicio > fecha and siguiente_inicio <= bloque['fin']:
            siguiente_indice = semana['indice'] + 1
            return {
                'tipo': 'inicio_semana',
                'fecha': siguiente_inicio,
                'etiqueta': f'Inicio de la semana {siguiente_indice}',
            }
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
    periodizacion, _plan, fases_anio = _periodizacion_actual(cliente, fecha, limitations)
    macrociclo = _macrociclo(fases_anio, periodizacion)

    if not bloque_base.get('disponible'):
        limitations.append(bloque_base.get('estado_evidencia', 'bloque_no_disponible'))
        return {
            'schema_version': 1,
            'solo_lectura': True,
            'fecha_corte': fecha,
            'estado': 'unknown',
            'periodizacion': periodizacion,
            'macrociclo': macrociclo,
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
                'estado_resultado_display': persistida.get_estado_resultado_display(),
                'estado_revision': persistida.estado_revision,
                'estado_revision_display': persistida.get_estado_revision_display(),
            }

    proximo = _proximo_hito(fecha, semana, bloque, periodizacion)
    if proximo is None:
        limitations.append('proximo_hito_no_determinable')

    return {
        'schema_version': 1,
        'solo_lectura': True,
        'fecha_corte': fecha,
        'estado': 'available' if periodizacion else 'partial',
        'periodizacion': periodizacion,
        'macrociclo': macrociclo,
        'bloque': bloque,
        'semana': semana,
        'evaluacion_bloque': evaluacion_bloque,
        'proximo_hito': proximo,
        'limitations': list(dict.fromkeys(limitations)),
    }
