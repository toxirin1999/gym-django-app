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


def etiqueta_objetivo_plan(objetivo):
    """Hace legible un identificador interno sin alterar su valor canónico."""
    if not objetivo:
        return None
    etiquetas = {
        'hipertrofia_metabolica': 'Hipertrofia metabólica',
        'hipertrofia': 'Hipertrofia',
        'fuerza': 'Fuerza',
        'acondicionamiento': 'Acondicionamiento',
        'descarga_activa': 'Descarga activa',
    }
    return etiquetas.get(str(objetivo), str(objetivo).replace('_', ' ').capitalize())


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
    # Paso 4 (13-oct-2026): con periodización dinámica la semana del plan no es
    # la del calendario. Se recoloca el año para que la fase y la semana que
    # enseña el Plan coincidan con las de la sesión de hoy.
    try:
        from entrenos.services.periodizacion_dinamica_service import lunes_de, resolver_semana
        info = resolver_semana(cliente, fecha)
        if not info.get('legacy'):
            primer_lunes = lunes_de(fecha) - timedelta(weeks=info['semana_plan'] - 1)
    except Exception:
        pass
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
            'objetivo_raw': bloque.get('objetivo'),
            'objetivo': etiqueta_objetivo_plan(bloque.get('objetivo')),
            'objetivo_display': etiqueta_objetivo_plan(bloque.get('objetivo')),
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
                'objetivo_raw': bloque.get('objetivo'),
                'objetivo': etiqueta_objetivo_plan(bloque.get('objetivo')),
                'objetivo_display': etiqueta_objetivo_plan(bloque.get('objetivo')),
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


def _sesiones_helms_semana(plan, inicio, fin):
    """Lee la prescripción semanal sin materializar contratos ni sesiones."""
    sesiones = []
    for fecha_raw, entreno in (plan or {}).get('entrenos_por_fecha', {}).items():
        if not isinstance(entreno, dict):
            continue
        try:
            fecha_sesion = (
                fecha_raw if isinstance(fecha_raw, date)
                else date.fromisoformat(str(fecha_raw)[:10])
            )
        except (TypeError, ValueError):
            continue
        if not inicio <= fecha_sesion <= fin or not entreno.get('ejercicios'):
            continue
        sesiones.append({
            'id': None,
            'nombre': entreno.get('nombre_rutina') or 'Sesión programada',
            'estado': 'prevista',
            'fecha_prevista': fecha_sesion,
            'fecha_pospuesta': None,
            'fecha_efectiva': fecha_sesion,
            'fecha_realizada': None,
            'realizada': False,
            'completa': False,
            'parcial': False,
        })
    return sorted(sesiones, key=lambda sesion: sesion['fecha_efectiva'])


def _normalizar_nombre(nombre):
    return ' '.join(str(nombre or '').casefold().split())


def _marcar_sesiones_helms_realizadas(cliente, sesiones, inicio, fin):
    """Cruza la prescripción Helms de una semana sin contrato con lo entrenado.

    Sin contrato no hay SesionProgramada que el cierre pueda marcar, así que la
    evidencia es el EntrenoRealizado de esa rutina: primero el guardado para la
    misma fecha del plan; si no, cualquiera de la semana (hecho otro día). Cada
    entreno cubre una sola sesión. Solo lectura: no materializa nada.
    """
    from django.db.models import Q
    from entrenos.models import EntrenoRealizado

    if not sesiones:
        return sesiones
    entrenos = list(
        EntrenoRealizado.objects.filter(cliente=cliente)
        .filter(Q(fecha__range=(inicio, fin)) | Q(fecha_ejecucion__range=(inicio, fin)))
        .select_related('rutina')
        .order_by('fecha', 'pk')
    )
    usados = set()

    def _asignar(sesion, entreno):
        usados.add(entreno.pk)
        completa = entreno.estado_cierre != EntrenoRealizado.ESTADO_PARCIAL
        sesion.update({
            'estado': SesionProgramada.ESTADO_COMPLETADA if completa else SesionProgramada.ESTADO_PARCIAL,
            'fecha_realizada': entreno.fecha_ejecucion or entreno.fecha,
            'realizada': True,
            'completa': completa,
            'parcial': not completa,
        })

    def _mismo_nombre(sesion, entreno):
        nombre = entreno.nombre_rutina_liftin or (entreno.rutina.nombre if entreno.rutina else '')
        return _normalizar_nombre(nombre) == _normalizar_nombre(sesion['nombre'])

    for exacta in (True, False):
        for sesion in sesiones:
            if sesion['realizada']:
                continue
            for entreno in entrenos:
                if entreno.pk in usados or not _mismo_nombre(sesion, entreno):
                    continue
                if exacta and entreno.fecha != sesion['fecha_prevista']:
                    continue
                _asignar(sesion, entreno)
                break
    return sesiones


def _aplicar_cola_semanal(sesiones, fecha_corte, fin_semana):
    """Recoloca las sesiones atrasadas como hace la cola de Ahora (paso 3).

    Lo que no se hizo no se pierde: la primera sesión pendiente atrasada pasa a
    hoy y las siguientes se corren a los próximos días de la semana (incluido
    el fin de semana). Si hoy ya hay una sesión hecha, la cola empieza mañana.
    Solo cambia cómo se enseña la semana (fecha_pospuesta/fecha_efectiva), no
    guarda nada. Lo que no cabe antes del domingo se queda como no registrado.
    """
    pendientes_estados = {SesionProgramada.ESTADO_PENDIENTE, 'prevista'}
    pendientes = sorted(
        (s for s in sesiones
         if s['estado'] in pendientes_estados and not s['realizada'] and not s['fecha_pospuesta']),
        key=lambda s: (s['fecha_prevista'], s['id'] or 0),
    )
    if not any(s['fecha_efectiva'] < fecha_corte for s in pendientes):
        return sesiones
    hecha_hoy = any(s['realizada'] and s.get('fecha_realizada') == fecha_corte for s in sesiones)
    inicio = fecha_corte + timedelta(days=1) if hecha_hoy else fecha_corte
    huecos = []
    dia = inicio
    while dia <= fin_semana:
        huecos.append(dia)
        dia += timedelta(days=1)
    # Primero los días con sesión prevista (el ritmo de la semana) y, si no
    # bastan, el resto de días hasta el domingo.
    previstos = sorted({s['fecha_prevista'] for s in pendientes if s['fecha_prevista'] >= inicio})
    libres = [d for d in huecos if d not in previstos]
    orden = sorted(set(previstos + ([inicio] if inicio in huecos else [])))
    orden += [d for d in libres if d not in orden]
    for sesion, hueco in zip(pendientes, sorted(orden[:len(pendientes)])):
        if hueco != sesion['fecha_prevista']:
            sesion['fecha_pospuesta'] = hueco
            sesion['fecha_efectiva'] = hueco
            sesion['en_cola'] = True
    return sorted(sesiones, key=lambda s: (s['fecha_efectiva'], s['id'] or 0))


def _contar_sesiones_no_registradas(sesiones, fecha_corte):
    """Cuenta pendientes ya pasadas para ofrecer una siguiente acción amable."""
    return sum(
        1 for sesion in sesiones
        if not sesion['realizada'] and sesion['fecha_efectiva'] < fecha_corte
    )


def _proximo_hito(fecha, semana, bloque, periodizacion):
    sesiones = semana['sesiones'] if semana else []
    evaluacion = semana['evaluacion'] if semana else None
    candidatas = sorted(
        (
            s for s in sesiones
            if s['estado'] in {SesionProgramada.ESTADO_PENDIENTE, 'prevista'}
            and s['fecha_efectiva'] >= fecha
        ),
        key=lambda s: (s['fecha_efectiva'], s['id'] is None, s['id'] or 0),
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


def _semana_desde_cola(cliente, fecha, periodizacion):
    """Semana de la periodización dinámica (SemanaPlanGym) contada con la cola, o None."""
    if not periodizacion:
        return None
    try:
        from entrenos.models import SemanaPlanGym
        if not SemanaPlanGym.objects.filter(cliente=cliente, lunes__lte=fecha).exists():
            return None
        from entrenos.services.semana_rutina_service import sesiones_para_plan
        sesiones, datos = sesiones_para_plan(cliente, fecha)
    except Exception:
        return None
    inicio = _inicio_semana(fecha)
    return {
        'id': None,
        'indice': periodizacion.get('semana_actual'),
        'inicio': inicio,
        'fin': inicio + timedelta(days=6),
        'objetivo_sesiones': datos['previstas'],
        'minimo_valido': None,
        'sesiones': sesiones,
        'sesiones_no_registradas': 0,
        'evaluacion': None,
        'origen': 'cola',
        'fuera': datos['fuera'],
    }


def proyectar_trayectoria_plan(cliente, *, fecha=None):
    """Compone evidencia persistida y el plan Helms; nunca materializa ni evalúa."""
    fecha = fecha or timezone.localdate()
    limitations = []
    bloque_base = proyectar_bloque_gym(cliente, fecha=fecha)
    periodizacion, plan, fases_anio = _periodizacion_actual(cliente, fecha, limitations)
    macrociclo = _macrociclo(fases_anio, periodizacion)

    if not bloque_base.get('disponible'):
        limitations.append(bloque_base.get('estado_evidencia', 'bloque_no_disponible'))
        # 14-oct-2026: sin acuerdo de bloque, si la periodización dinámica está
        # en marcha ella lleva el bloque; la semana es la misma cola que Ahora.
        semana_cola = _semana_desde_cola(cliente, fecha, periodizacion)
        if semana_cola is not None:
            return {
                'schema_version': 1,
                'solo_lectura': True,
                'fecha_corte': fecha,
                'estado': 'available',
                'periodizacion': periodizacion,
                'macrociclo': macrociclo,
                'bloque': None,
                'semana': semana_cola,
                'evaluacion_bloque': None,
                'proximo_hito': _proximo_hito(fecha, semana_cola, None, periodizacion),
                'limitations': list(dict.fromkeys(limitations)),
            }
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
        inicio_semana = _inicio_semana(fecha)
        sesiones_planificadas = _marcar_sesiones_helms_realizadas(
            cliente,
            _sesiones_helms_semana(plan, inicio_semana, inicio_semana + timedelta(days=6)),
            inicio_semana, inicio_semana + timedelta(days=6),
        )
        sesiones_planificadas = _aplicar_cola_semanal(
            sesiones_planificadas, fecha, inicio_semana + timedelta(days=6),
        )
        if sesiones_planificadas:
            semana = {
                'id': None,
                'indice': periodizacion.get('semana_actual') if periodizacion else None,
                'inicio': inicio_semana,
                'fin': inicio_semana + timedelta(days=6),
                'objetivo_sesiones': len(sesiones_planificadas),
                'minimo_valido': None,
                'sesiones': sesiones_planificadas,
                'sesiones_no_registradas': _contar_sesiones_no_registradas(
                    sesiones_planificadas, fecha,
                ),
                'evaluacion': None,
                'origen': 'plan_helms',
            }
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
            'sesiones_no_registradas': _contar_sesiones_no_registradas(sesiones, fecha),
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
