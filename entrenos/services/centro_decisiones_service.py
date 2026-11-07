"""
Phase 62G.1 — Agrupadores para el Centro de decisiones 2.0.

CONTRATO:
    - No introduce motor nuevo: agrupa listas que el panel ya construye
      (traces humanizados de decision_trace_service, GymDecisionLog,
      preferencias/intervenciones/hipótesis activas).
    - El Centro no debe mostrar más datos; debe mostrar mejor qué
      evidencias siguen vivas (Phase 62G, frase de fase).
    - Las listas de entrada vienen ordenadas más reciente primero
      (igual que get_traces_recientes y plan_decisiones_view); los
      agrupadores conservan ese orden para "última vez" / "más reciente".
"""

from datetime import timedelta

from django.utils import timezone

from entrenos.models import ContratoSemanalGym, SesionProgramada


def construir_resumen_operativo_centro(
    cliente,
    bloque_colaborativo,
    analisis_semanal,
    fecha_ref,
) -> dict:
    """Proyección factual y allowlisted para la cabecera operativa del Centro.

    La función es estrictamente de lectura: no materializa contratos ni corrige
    estados. Sin acuerdo de bloque ni acuerdo semanal, el bloque y la semana
    salen de la periodización (``SemanaPlanGym``), la misma fuente que la
    Memoria y que el briefing (14-oct-2026). Sin ninguna de las dos, la
    ausencia se expresa como desconocida.
    """
    periodizacion = _periodizacion_en_curso(cliente, fecha_ref)
    # 7-nov-2026: el bloque y la semana salen del mismo estado que Plan
    # (proyectar_trayectoria_plan). En la semana de descarga no hay bloque «en
    # curso» de contenido y el Centro decía «Bloque sin semana actual».
    como_plan = _estado_como_plan(cliente, fecha_ref)
    bloque = (bloque_colaborativo or {}).get('bloque')
    bloque_dto = {
        'estado': None,
        'semana_actual': None,
        'semanas_total': None,
    }
    if bloque is not None:
        semana_actual = None
        if bloque.semana_inicio <= fecha_ref <= bloque.semana_fin_prevista:
            semana_actual = ((fecha_ref - bloque.semana_inicio).days // 7) + 1
        bloque_dto = {
            'estado': bloque.estado,
            'semana_actual': semana_actual,
            'semanas_total': bloque.semanas_previstas,
        }
    if bloque_dto['semana_actual'] is None and como_plan and como_plan.get('semana'):
        bloque_dto = {
            'estado': 'periodizacion',
            'semana_actual': como_plan['semana'],
            'semanas_total': como_plan['de'],
            'nombre': como_plan['nombre'],
            'descarga': como_plan['descarga'],
            'siguiente_nombre': como_plan.get('siguiente_nombre'),
            'siguiente_inicio': como_plan.get('siguiente_inicio'),
            'inicio': como_plan.get('inicio'),
        }
    elif bloque_dto['semana_actual'] is None and periodizacion and periodizacion.get('semana'):
        bloque_dto = {
            'estado': 'periodizacion',
            'semana_actual': periodizacion['semana'],
            'semanas_total': periodizacion['de'],
            'nombre': periodizacion['nombre'],
            'descarga': periodizacion['descarga_ahora'],
        }

    lunes = fecha_ref - timedelta(days=fecha_ref.weekday())
    contrato = (
        ContratoSemanalGym.objects.filter(cliente=cliente, semana=lunes)
        .prefetch_related('sesiones')
        .order_by('-id')
        .first()
    )
    if contrato is None and como_plan and como_plan.get('previstas') is not None:
        semana_dto = {
            'estado': 'periodizacion',
            'completadas': como_plan['hechas'],
            'sesiones_completadas': como_plan['hechas'],
            'sesiones_parciales': None,
            'sesiones_realizadas': como_plan['hechas'],
            'objetivo': como_plan['previstas'],
            'minimo': None,
            'hecha_hoy': como_plan.get('hecha_hoy'),
        }
    elif contrato is None and periodizacion:
        from entrenos.services.revision_bloque_service import semana_en_curso
        semana = semana_en_curso(cliente, fecha_ref)
        semana_dto = {
            'estado': 'periodizacion',
            'completadas': semana['hechas'],
            'sesiones_completadas': semana['hechas'],
            'sesiones_parciales': None,
            'sesiones_realizadas': semana['hechas'],
            'objetivo': semana['previstas'],
            'minimo': None,
        }
    elif contrato is None:
        semana_dto = {
            'estado': 'desconocido',
            'completadas': None,
            'sesiones_completadas': None,
            'sesiones_parciales': None,
            'sesiones_realizadas': None,
            'objetivo': None,
            'minimo': None,
        }
    else:
        completadas = contrato.sesiones.filter(estado=SesionProgramada.ESTADO_COMPLETADA).count()
        parciales = contrato.sesiones.filter(estado=SesionProgramada.ESTADO_PARCIAL).count()
        semana_dto = {
            'estado': 'materializada',
            'completadas': completadas,
            'sesiones_completadas': completadas,
            'sesiones_parciales': parciales,
            'sesiones_realizadas': completadas + parciales,
            'objetivo': contrato.objetivo_sesiones,
            'minimo': contrato.minimo_valido,
        }

    pendientes = SesionProgramada.objects.filter(
        cliente=cliente,
        estado=SesionProgramada.ESTADO_PENDIENTE,
    ).only('nombre_sesion', 'fecha_prevista', 'pospuesta_hasta')
    candidatas = []
    for sesion in pendientes:
        fecha_efectiva = sesion.pospuesta_hasta or sesion.fecha_prevista
        if fecha_efectiva >= fecha_ref:
            candidatas.append((fecha_efectiva, sesion.pk, sesion))
    candidatas.sort(key=lambda item: (item[0], item[1]))
    if candidatas:
        fecha_efectiva, _, sesion = candidatas[0]
        proxima_dto = {
            'estado': 'disponible',
            'nombre': sesion.nombre_sesion or 'Sesión Gym',
            'fecha': fecha_efectiva,
            'es_pospuesta': sesion.pospuesta_hasta is not None,
        }
    else:
        # 14-oct-2026: sin sesiones programadas (no hay acuerdo semanal), la
        # próxima sesión es la de la cola de la semana, la misma que Ahora.
        proxima_dto = _proxima_desde_cola(cliente, fecha_ref) or {
            'estado': 'desconocido',
            'nombre': None,
            'fecha': None,
            'es_pospuesta': False,
        }

    carga_dto = {
        'estado': 'desconocido',
        'causa_codigo': None,
        'explicacion': None,
    }
    if analisis_semanal:
        if analisis_semanal.get('carga_alta_objetiva'):
            motivo = analisis_semanal.get('motivo_carga')
            if motivo == 'rpe_alto':
                rpe = analisis_semanal.get('rpe_medio_semana')
                rpe_label = str(rpe).replace('.', ',') if rpe is not None else 'alto'
                carga_dto = {
                    'estado': 'alta',
                    'causa_codigo': motivo,
                    'explicacion': f'RPE medio {rpe_label}: la exigencia percibida fue alta esta semana.',
                }
            elif motivo == 'bloque_incompleto':
                carga_dto = {
                    'estado': 'alta',
                    'causa_codigo': motivo,
                    'explicacion': 'Parte del bloque principal quedó incompleta; el plan conserva margen.',
                }
        else:
            carga_dto = {
                'estado': 'sin_alerta',
                'causa_codigo': None,
                'explicacion': None,
            }

    return {
        'bloque': bloque_dto,
        'semana': semana_dto,
        'proxima_sesion': proxima_dto,
        'carga': carga_dto,
    }

def _estado_como_plan(cliente, fecha_ref):
    """Fase, semana y sesiones tal y como las enseña Plan, o None.

    Solo con periodización dinámica (``SemanaPlanGym``): sin ella el Centro
    sigue con los acuerdos o dice que no lo sabe.
    """
    try:
        from entrenos.models import SemanaPlanGym
        from entrenos.services.periodizacion_dinamica_service import lunes_de
        from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan

        lunes = lunes_de(fecha_ref)
        if not SemanaPlanGym.objects.filter(cliente=cliente, lunes__lte=lunes).exists():
            return None
        registro = SemanaPlanGym.objects.filter(cliente=cliente, lunes=lunes).first()
        trayectoria = proyectar_trayectoria_plan(cliente, fecha=fecha_ref)
    except Exception:
        return None
    fase = trayectoria.get('periodizacion') or {}
    semana = trayectoria.get('semana') or {}
    siguiente = (trayectoria.get('macrociclo') or {}).get('siguiente_fase') or {}
    sesiones = semana.get('sesiones') or []
    hecha_hoy = next((s for s in sesiones if s.get('realizada') and s.get('fecha_realizada') == fecha_ref), None)
    return {
        'nombre': fase.get('nombre'),
        'inicio': fase.get('inicio'),
        'semana': fase.get('semana_actual'),
        'de': fase.get('semanas'),
        'descarga': bool(registro and registro.descarga),
        'siguiente_nombre': siguiente.get('nombre'),
        'siguiente_inicio': siguiente.get('inicio'),
        'hechas': sum(1 for s in sesiones if s.get('realizada')) if semana else None,
        'previstas': semana.get('objetivo_sesiones') if semana else None,
        'hecha_hoy': {
            'nombre': (hecha_hoy.get('nombre') or '').split(' - ')[0].strip(),
            'completa': bool(hecha_hoy.get('completa')),
        } if hecha_hoy else None,
    }


def _periodizacion_en_curso(cliente, fecha_ref):
    """Bloque en curso de la periodización, o None (nunca rompe el Centro)."""
    try:
        from entrenos.services.revision_bloque_service import estado_bloques
        return estado_bloques(cliente, hoy=fecha_ref)['en_curso']
    except Exception:
        return None


# Phase 62G.1 — etiquetas de grupo para "Carga por ejercicio". Distintas de
# accion_label (que dice "Mantener"): aquí se nombra el grupo tal y como
# aparece en el Centro 2.0 ("Mantener carga", "Reducir peso", ...).
_ACCION_GROUP_LABELS = {
    'subir_peso': 'Subir peso',
    'subir_reps': 'Subir repeticiones',
    'mantener': 'Mantener carga',
    'bajar_peso': 'Reducir peso',
    'deload': 'Descarga',
    'cambiar_variante': 'Cambiar variante',
}


# 7-nov-2026 · «Carga por ejercicio»: vigente frente a historial.
_ACCIONES_QUE_CAMBIAN = ('subir_peso', 'subir_reps', 'bajar_peso', 'cambiar_variante')
_ESTADO_VIGENTE = {'pospuesta': 'pospuesta', 'aplicada': 'aplicada', 'pendiente': 'para la próxima sesión'}


def _fecha_entreno(entreno):
    return getattr(entreno, 'fecha_ejecucion', None) or getattr(entreno, 'fecha', None)


def decisiones_por_vigencia(cliente, decisiones, desde, hoy):
    """Separa las decisiones de carga en vigentes e historial.

    Vigente: la última decisión de cada ejercicio, si cambia algo (sube,
    baja o cambia la variante), aún no se ha evaluado y el ejercicio no se ha
    vuelto a hacer después (si se hizo, la sesión siguiente ya la sustituyó).
    No importa su fecha: una anterior al bloque puede seguir vigente.
    Historial: el resto, desde que empezó el bloque (``desde``), con fecha.

    ``decisiones``: GymDecisionLog, más reciente primero.
    """
    from django.db.models import Q
    from entrenos.models import EjercicioRealizado
    from entrenos.services.decision_log_service import normalizar_ejercicio

    ultima_vez = {}
    for nombre, fe, f in EjercicioRealizado.objects.filter(entreno__cliente=cliente).filter(
        Q(entreno__fecha_ejecucion__lte=hoy) | Q(entreno__fecha_ejecucion__isnull=True, entreno__fecha__lte=hoy)
    ).values_list('nombre_ejercicio', 'entreno__fecha_ejecucion', 'entreno__fecha'):
        clave, fecha = normalizar_ejercicio(nombre), fe or f
        if fecha and (clave not in ultima_vez or fecha > ultima_vez[clave]):
            ultima_vez[clave] = fecha

    vistos, vigentes, historial = set(), [], []
    for log in decisiones:
        clave = log.ejercicio_normalizado or normalizar_ejercicio(log.ejercicio)
        fecha = _fecha_entreno(log.entreno_origen) if log.entreno_origen_id else None
        fecha = fecha or timezone.localtime(log.fecha_creacion).date()
        item = {
            'ejercicio': log.ejercicio.title() if log.ejercicio.islower() else log.ejercicio,
            'accion': log.accion,
            'label': _ACCION_GROUP_LABELS.get(log.accion, log.accion_label),
            'motivo': log.motivo,
            'fecha': fecha,
            'estado': None,
            'motivo_postergacion': log.motivo_postergacion if log.estado_aplicacion == 'pospuesta' else None,
        }
        primera = clave not in vistos
        vistos.add(clave)
        if (primera and log.accion in _ACCIONES_QUE_CAMBIAN and log.resultado is None
                and not (ultima_vez.get(clave) and ultima_vez[clave] > fecha)):
            item['estado'] = _ESTADO_VIGENTE.get(log.estado_aplicacion, 'para la próxima sesión')
            vigentes.append(item)
        elif desde is None or fecha >= desde:
            historial.append(item)
    return {'vigentes': vigentes, 'historial': historial, 'desde': desde}


def agrupar_traces_recientes(traces: list[dict]) -> list[dict]:
    """
    Agrupa traces humanizados por su clave semántica estable. La explicación
    puede variar entre días sin fragmentar una misma decisión de estado.

    Devuelve una lista de grupos, en el orden de primera aparición de
    `traces` (más reciente primero), cada uno con:
        decision_label, explicacion, lesion_label, count,
        fecha_label (de la ocurrencia más reciente), items (originales).
    """
    grupos: dict[str, dict] = {}
    orden: list[str] = []

    for trace in traces:
        clave = trace.get('group_key') or (
            f"decision_estado:{trace['decision_estado']}"
            if trace.get('decision_estado')
            else f"decision_label:{trace['decision_label']}"
        )
        if clave not in grupos:
            grupos[clave] = {
                'group_key': clave,
                'fecha': trace.get('fecha'),
                'decision_label': trace['decision_label'],
                'explicacion': trace['explicacion'],
                'lesion_label': trace['lesion_label'],
                'fecha_label': trace['fecha_label'],
                'count': 0,
                'items': [],
            }
            orden.append(clave)
        grupo = grupos[clave]
        grupo['count'] += 1
        grupo['items'].append(trace)

    return [grupos[clave] for clave in orden]


def agrupar_decisiones_carga(decisiones: list) -> list[dict]:
    """
    Agrupa GymDecisionLog por accion.

    Devuelve una lista de grupos, en el orden de primera aparición de
    `decisiones` (más reciente primero), cada uno con:
        accion, label, count, ejercicios (nombres formateados, sin
        repetir), motivo_principal (del log más reciente del grupo),
        items (logs originales).

    Un mismo ejercicio puede tener varios logs en la ventana de 30 días
    (p.ej. subir_peso el día 10 y mantener el día 15). Solo el log más
    reciente de cada ejercicio decide su grupo — si no, el ejercicio
    aparecería repetido en dos grupos distintos a la vez.
    """
    decision_mas_reciente_por_ejercicio: dict[str, object] = {}
    orden_ejercicios: list[str] = []

    for log in decisiones:
        nombre = log.ejercicio.title()
        if nombre not in decision_mas_reciente_por_ejercicio:
            decision_mas_reciente_por_ejercicio[nombre] = log
            orden_ejercicios.append(nombre)

    grupos: dict[str, dict] = {}
    orden: list[str] = []

    for nombre in orden_ejercicios:
        log = decision_mas_reciente_por_ejercicio[nombre]
        accion = log.accion
        if accion not in grupos:
            grupos[accion] = {
                'accion': accion,
                'label': _ACCION_GROUP_LABELS.get(accion, log.accion_label),
                'count': 0,
                'ejercicios': [],
                'motivo_principal': log.motivo,
                'items': [],
            }
            orden.append(accion)
        grupo = grupos[accion]
        grupo['count'] += 1
        grupo['items'].append(log)
        grupo['ejercicios'].append(nombre)

    # Phase 62I — cuántas de las decisiones del grupo quedaron pospuestas
    # por el freno contextual la última vez que se calculó el plan.
    for grupo in grupos.values():
        grupo['pospuestas_count'] = sum(
            1 for it in grupo['items'] if it.estado_aplicacion == 'pospuesta'
        )

    return [grupos[accion] for accion in orden]


# Phase 62G.1 — narrativa del hero cuando no hay señales activas (62G.0,
# validada por el usuario). No renderizar secciones fantasma si esto aplica.
_NARRATIVA_MODO_NORMAL = (
    'El plan opera en modo normal. No hay preferencias, ajustes ni hipótesis '
    'activas — las decisiones de hoy se basan solo en lo que pasó esta semana.'
)
_NARRATIVA_CONTINUIDAD_DESCONOCIDA = (
    'La lectura de continuidad no está disponible ahora. El plan conserva las '
    'señales conocidas sin afirmar que la continuidad sea normal.'
)
_NARRATIVA_PAUSA = (
    'Hay una pausa significativa en la continuidad. El plan la trata como '
    'contexto activo antes de decidir el siguiente paso.'
)
_CONTINUIDAD_NO_INFORMADA = object()


def construir_estado_plan(
    preferencias_activas,
    intervenciones_activas,
    hipotesis_abiertas,
    continuidad=_CONTINUIDAD_NO_INFORMADA,
) -> dict:
    """
    Construye la narrativa del hero del Centro de decisiones a partir de las
    señales activas (preferencias aprendidas, intervenciones, hipótesis).

    Devuelve {'narrativa': str, 'hay_senales_activas': bool}.
    Si no hay ninguna señal, narrativa = modo normal y hay_senales_activas=False
    (el template no debe renderizar secciones de "activo ahora").
    """
    senales = []

    for pref in preferencias_activas:
        senales.append(pref.descripcion or pref.get_tipo_display())

    for interv in intervenciones_activas:
        senales.append(interv.get_tipo_display())

    for hip in hipotesis_abiertas:
        texto = hip.get('texto') if isinstance(hip, dict) else None
        if texto:
            senales.append(texto)

    continuidad_desconocida = continuidad is None
    if continuidad_desconocida:
        estado_continuidad = 'desconocida'
    elif (
        continuidad is not _CONTINUIDAD_NO_INFORMADA
        and continuidad.get('hay_pausa_significativa')
    ):
        estado_continuidad = 'pausa_confirmada'
    else:
        estado_continuidad = 'sin_pausa_confirmada'

    if continuidad_desconocida and not senales:
        return {
            'narrativa': _NARRATIVA_CONTINUIDAD_DESCONOCIDA,
            'hay_senales_activas': False,
            'estado_continuidad': estado_continuidad,
        }
    elif (
        continuidad is not _CONTINUIDAD_NO_INFORMADA
        and continuidad.get('hay_pausa_significativa')
    ):
        senales.insert(0, _NARRATIVA_PAUSA)

    if not senales:
        return {
            'narrativa': _NARRATIVA_MODO_NORMAL,
            'hay_senales_activas': False,
            'estado_continuidad': estado_continuidad,
        }

    if len(senales) == 1:
        cuerpo = senales[0]
    else:
        cuerpo = '; '.join(senales[:-1]) + ' y ' + senales[-1]

    plural = 'señal activa' if len(senales) == 1 else 'señales activas'
    cuerpo = cuerpo.rstrip()
    cierre = '' if cuerpo.endswith(('.', '!', '?')) else '.'
    narrativa = f'El plan está usando {len(senales)} {plural}: {cuerpo}{cierre}'
    if continuidad_desconocida:
        narrativa = f'{narrativa} {_NARRATIVA_CONTINUIDAD_DESCONOCIDA}'

    return {
        'narrativa': narrativa,
        'hay_senales_activas': True,
        'estado_continuidad': estado_continuidad,
    }


def _proxima_desde_cola(cliente, fecha_ref, dias=7):
    """La siguiente sesión según la cola semanal y el plan (lo que propone Ahora)."""
    try:
        from entrenos.services.sesion_recomendada import (
            _build_planificador, _es_descanso, _normalizar_entrenamiento, _siguiente_de_cola,
        )
        planificador = None
        for d in range(dias + 1):
            fecha = fecha_ref + timedelta(days=d)
            siguiente = _siguiente_de_cola(cliente, fecha)
            if siguiente:
                return {'estado': 'disponible', 'nombre': siguiente['nombre'], 'fecha': fecha,
                        'es_pospuesta': siguiente['fecha'] < fecha}
            planificador = planificador or _build_planificador(cliente)
            sesion = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(fecha))
            if not _es_descanso(sesion):
                from entrenos.models import EntrenoRealizado
                from django.db.models import Q
                hecho = EntrenoRealizado.objects.filter(cliente=cliente).filter(
                    Q(fecha_ejecucion=fecha) | Q(fecha_ejecucion__isnull=True, fecha=fecha)
                ).exists()
                if not hecho:
                    return {'estado': 'disponible', 'nombre': (sesion.get('rutina_nombre') or '').strip(),
                            'fecha': fecha, 'es_pospuesta': False}
    except Exception:
        return None
    return None
