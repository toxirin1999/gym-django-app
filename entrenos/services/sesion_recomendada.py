import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from entrenos.models import ActividadRealizada, EntrenoRealizado, SesionProgramada

logger = logging.getLogger(__name__)

_SYNC_CACHE_TTL = 3600  # 1 hour — throttle the expensive planificador loop
MOTIVO_OMISION_RECONCILIACION = (
    'Sesión omitida por reconciliación semanal para evitar acumulación de deuda.'
)
MOTIVO_OMISION_SEMANA_CERRADA = (
    'Semana cerrada: lo que no se hizo no se arrastra a la semana siguiente.'
)


def _build_planificador(cliente):
    from analytics.planificador_helms.core import PlanificadorHelms
    from analytics.planificador_helms.models.perfil_cliente import PerfilCliente

    perfil = PerfilCliente({
        'id': cliente.id,
        'nombre': getattr(cliente, 'nombre', ''),
        'experiencia_años': getattr(cliente, 'experiencia_años', 0),
        'objetivo_principal': getattr(cliente, 'objetivo_principal', 'hipertrofia'),
        'dias_disponibles': getattr(cliente, 'dias_disponibles', 4),
        'nivel_estres': getattr(cliente, 'nivel_estres', 5),
        'calidad_sueño': getattr(cliente, 'calidad_sueño', 7),
        'nivel_energia': getattr(cliente, 'nivel_energia', 7),
        'ejercicios_evitar': getattr(cliente, 'ejercicios_evitar', []) or [],
        'maximos_actuales': getattr(cliente, 'one_rm_data', {}) or {},
    })
    return PlanificadorHelms(perfil)


def _es_descanso(entrenamiento):
    if not entrenamiento:
        return True
    return not entrenamiento.get('ejercicios')


def _semana_en_bloque(cliente, fecha):
    """
    Devuelve el número de semana dentro del bloque de periodización para
    `fecha` (1-indexed), o None si es día de descanso o no se pudo calcular.

    Usa `año_planificacion=fecha.year` explícitamente (en vez del fallback
    `datetime.now().year` de generar_entrenamiento_para_fecha) para que dos
    fechas del mismo año sean siempre comparables entre sí.
    """
    try:
        from analytics.planificador_helms.core import PlanificadorHelms
        from analytics.planificador_helms.models.perfil_cliente import PerfilCliente

        perfil = PerfilCliente({
            'id': cliente.id,
            'dias_disponibles': getattr(cliente, 'dias_disponibles', 4),
            'año_planificacion': fecha.year,
        })
        entrenamiento = PlanificadorHelms(perfil).generar_entrenamiento_para_fecha(fecha)
    except Exception:
        logger.warning("Error calculando semana_en_bloque para %s", fecha, exc_info=True)
        return None

    if not entrenamiento or not entrenamiento.get('ejercicios'):
        return None
    return entrenamiento.get('semana_en_bloque')


def buscar_entreno_realizado_esta_semana(cliente, hoy, rutina_nombre):
    """
    Busca un EntrenoRealizado de esta semana (>= lunes de `hoy`) cuyo
    rutina.nombre coincide (case-insensitive) con `rutina_nombre`, Y que
    además corresponda a la MISMA semana de periodización que `hoy`.

    Sin esta segunda condición, un catch-up tardío de la sesión "Día N" de la
    SEMANA ANTERIOR (mismo nombre de rutina, pesos sin progresar) se confunde
    con la sesión "Día N" de HOY (semana actual, pesos progresados) — porque
    `generar_entrenamiento_para_fecha` no incluye ningún identificador de
    semana/ciclo en `rutina_nombre`.

    Para cada candidato, la "fecha de referencia" para calcular su semana de
    bloque es `SesionProgramada.fecha_prevista` si está vinculado a una (i.e.
    fue un catch-up de esa fecha), o su propia `fecha` si no.

    Devuelve el EntrenoRealizado o None.
    """
    if not rutina_nombre:
        return None

    lunes_semana = hoy - timedelta(days=hoy.weekday())
    semana_hoy = _semana_en_bloque(cliente, hoy)

    candidatos = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__gte=lunes_semana,
        rutina__nombre__iexact=rutina_nombre,
    ).prefetch_related('ejercicios_realizados').order_by('-fecha')

    for candidato in candidatos:
        sesion_programada = candidato.sesiones_programadas.first()
        fecha_referencia = sesion_programada.fecha_prevista if sesion_programada else candidato.fecha
        semana_candidato = _semana_en_bloque(cliente, fecha_referencia)

        if semana_hoy is None or semana_candidato is None or semana_candidato == semana_hoy:
            return candidato

    return None


def _fecha_completada(cliente, fecha):
    from django.db.models import Q
    if EntrenoRealizado.objects.filter(cliente=cliente).filter(
        Q(fecha_ejecucion=fecha) | Q(fecha_ejecucion__isnull=True, fecha=fecha)
    ).exists():
        return True
    try:
        if ActividadRealizada.objects.filter(cliente=cliente, tipo='gym').filter(
            Q(fecha_realizado=fecha) | Q(fecha_realizado__isnull=True, fecha=fecha)
        ).exists():
            return True
    except Exception:
        pass
    return False


def _normalizar_entrenamiento(entrenamiento):
    if not entrenamiento:
        return entrenamiento
    r = entrenamiento.get('rutina_nombre') or entrenamiento.get('nombre_rutina')
    if r:
        entrenamiento['rutina_nombre'] = r
        entrenamiento['nombre_rutina'] = r
    return entrenamiento


def _buscar_entreno_rutina_en_ventana(cliente, nombre_rutina, fecha_desde, fecha_hasta):
    """
    Returns the first EntrenoRealizado within [fecha_desde, fecha_hasta] whose rutina
    name matches the pending session name. Used to close pending sessions when the user
    does them on a different date than originally planned.

    Only matches if there's exactly one candidate (avoids false closes when the same
    routine appears multiple times in the window).
    """
    if not nombre_rutina:
        return None
    try:
        candidatos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_desde,
            fecha__lte=fecha_hasta,
            rutina__nombre__iexact=nombre_rutina,
        ).order_by('fecha')
        return candidatos.first() if candidatos.count() == 1 else None
    except Exception:
        return None


def _marcar_completadas(cliente, fecha_hoy):
    """
    Fast, always-run step: close any pending sessions that now have a logged session.
    Runs on every call to obtener_sesion_recomendada_hoy — not cached — so completing
    a session is reflected immediately on the next panel load.

    A session is only closed by one unambiguous EntrenoRealizado with the same routine
    identity. A date by itself is not evidence of session identity: a postponed workout
    can legitimately be executed on the original date of another session.

    Batch-optimized: prefetches the workouts in the window instead of querying once
    per pending session.
    """
    from collections import defaultdict
    from django.db.models import Q

    fecha_inicio = fecha_hoy - timedelta(days=14)

    pendientes = list(SesionProgramada.objects.filter(
        cliente=cliente,
        estado=SesionProgramada.ESTADO_PENDIENTE,
        fecha_prevista__gte=fecha_inicio,
        fecha_prevista__lte=fecha_hoy,
    ))
    if not pendientes:
        return

    # An EntrenoRealizado already linked to any session is consumed and cannot close
    # another one, even if name and date happen to coincide.
    ids_consumidos = set(
        SesionProgramada.objects.filter(
            cliente=cliente, entreno_realizado__isnull=False,
        ).values_list('entreno_realizado_id', flat=True)
    )

    entrenos_con_rutina = list(
        EntrenoRealizado.objects.filter(
            cliente=cliente,
            rutina__isnull=False,
        ).filter(
            Q(fecha_ejecucion__gte=fecha_inicio, fecha_ejecucion__lte=fecha_hoy)
            | Q(fecha_ejecucion__isnull=True, fecha__gte=fecha_inicio, fecha__lte=fecha_hoy)
        ).select_related('rutina').order_by('fecha_ejecucion', 'fecha')
    )
    rutina_a_entrenos: dict = defaultdict(list)
    for e in entrenos_con_rutina:
        if e.rutina and e.rutina.nombre:
            rutina_a_entrenos[e.rutina.nombre.lower()].append(e)

    for sp in pendientes:
        if sp.nombre_sesion:
            fecha_desde = sp.fecha_prevista
            ventana_hasta = min(sp.fecha_prevista + timedelta(days=7), fecha_hoy)
            nombre_lower = sp.nombre_sesion.lower()
            candidatos = [
                e for e in rutina_a_entrenos.get(nombre_lower, [])
                if (
                    e.pk not in ids_consumidos
                    and fecha_desde <= (e.fecha_ejecucion or e.fecha) <= ventana_hasta
                )
            ]
            if len(candidatos) == 1:
                entreno = candidatos[0]
                fecha_efectiva = entreno.fecha_ejecucion or entreno.fecha
                sp.estado = (
                    SesionProgramada.ESTADO_PARCIAL
                    if entreno.estado_cierre == EntrenoRealizado.ESTADO_PARCIAL
                    else SesionProgramada.ESTADO_COMPLETADA
                )
                sp.fecha_realizada = fecha_efectiva
                sp.entreno_realizado = entreno
                sp.save(update_fields=['estado', 'fecha_realizada', 'entreno_realizado', 'actualizada_en'])
                ids_consumidos.add(entreno.pk)


def _reconciliar_pendientes_semana(cliente, fecha_hoy):
    """
    Cierre semanal (13-oct-2026, sustituye a la regla de Phase 2B que
    arrastraba una sesión "alta" a la semana siguiente): toda sesión pendiente
    de una semana ya cerrada se marca omitida por el sistema con
    MOTIVO_OMISION_SEMANA_CERRADA. La semana nueva empieza por su Día 1 y
    `_nota_semana_cerrada` explica qué se quedó fuera.
    """
    semana_actual = fecha_hoy.isocalendar()[:2]

    pendientes = list(
        SesionProgramada.objects
        .filter(cliente=cliente, estado=SesionProgramada.ESTADO_PENDIENTE)
        .order_by('fecha_prevista', 'id')
    )

    if not pendientes:
        return

    def semana_efectiva(sesion):
        fecha_efectiva = sesion.pospuesta_hasta or sesion.fecha_prevista
        return fecha_efectiva.isocalendar()[:2]

    # Una semana distinta no es necesariamente anterior: puede ser futura.
    # La reconciliación solo puede generar deuda sobre semanas ya cerradas.
    anteriores_list = [sp for sp in pendientes if semana_efectiva(sp) < semana_actual]

    if not anteriores_list:
        return

    # Paso 3 (13-oct-2026): la semana se cierra el domingo. Lo que no se hizo
    # no se arrastra (arrastrarlo desplazaba la semana nueva entera y se
    # perdían sesiones en cascada); se marca y el lunes se dice qué quedó fuera.
    SesionProgramada.objects.filter(
        id__in=[sp.id for sp in anteriores_list]
    ).update(
        estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
        motivo_estado=MOTIVO_OMISION_SEMANA_CERRADA,
    )


# ── Phase 4D — Bloque esencial analytics ─────────────────────────────────────

def calcular_bloque_esencial(entreno_realizado):
    """
    For a modo_reducido session, returns a complete summary of principal vs optional blocks.
    Returns None if the session was not done in essential mode or has no classification data.

    Return dict:
        principales_completados: int    — exercises marked as principal and done
        principales_planificados: int   — exercises marked as principal in the planned session
        opcionales_completados: int     — optional exercises done
        opcionales_planificados: int    — optional exercises planned
        bloque_principal_completo: bool — all planned principals were completed
        porcentaje_principal: int       — 0-100
        porcentaje_opcional: int        — 0-100
    """
    if not entreno_realizado.modo_reducido:
        return None

    ejercicios = list(entreno_realizado.ejercicios_realizados.filter(completado=True))

    has_classification = any(ej.es_bloque_principal is not None for ej in ejercicios)
    if not has_classification:
        return None

    principales_completados = sum(1 for ej in ejercicios if ej.es_bloque_principal is True)
    opcionales_completados = sum(1 for ej in ejercicios if ej.es_bloque_principal is False)

    principales_planificados = getattr(entreno_realizado, 'principales_planificados', None) or principales_completados
    opcionales_planificados = getattr(entreno_realizado, 'opcionales_planificados', None) or opcionales_completados

    pct_principal = round(principales_completados / principales_planificados * 100) if principales_planificados else 0
    pct_opcional = round(opcionales_completados / opcionales_planificados * 100) if opcionales_planificados else 0

    return {
        'principales_completados': principales_completados,
        'principales_planificados': principales_planificados,
        'opcionales_completados': opcionales_completados,
        'opcionales_planificados': opcionales_planificados,
        'bloque_principal_completo': principales_completados >= principales_planificados and principales_planificados > 0,
        'porcentaje_principal': pct_principal,
        'porcentaje_opcional': pct_opcional,
    }


# ── Phase 3 — Physical context & enriched decision ───────────────────────────

_MENSAJES_POR_CAUSA = {
    'lesion':             'La sesión sigue en el mapa, pero hoy no debe pasar por encima de tu lesión.',
    'fatiga_alta':        'El plan sigue aquí, pero hoy no necesita que lo fuerces.',
    'energia_baja':       'Hoy hay margen para hacer la versión mínima. No hace falta completar todo.',
    'futbol_reciente':    'Tus piernas ya recibieron carga del fútbol. Hoy conviene no confundir esfuerzo con progreso.',
    'hyrox_reciente':     'El Hyrox reciente dejó carga real — hoy conviene priorizar los principales y dejar los accesorios como opcionales.',
    'carga_alta':         'Esta semana llevas bastante más carga de la habitual. Hoy, los principales y sin forzar: los accesorios quedan como opcionales.',
    'recuperacion_baja':  'Hoy vas justo de recuperación: conviene hacer los principales sin apretar y dejar los accesorios para otro día.',
    'pendiente_prioritaria': 'Esta sesión sostiene el bloque. Sigue siendo la siguiente pieza útil.',
    'pendiente_normal':   'Esta sesión quedó pendiente. El plan conserva el hilo.',
    'sesion_hoy':         'Esta es la sesión prevista para hoy.',
    'descanso_planificado': 'Hoy el plan marca descanso.',
}


def _obtener_contexto_fisico(cliente, fecha_hoy, physical_snapshot=None):
    """
    Gathers physical context for the daily decision.
    All lookups are wrapped in try/except — missing models degrade gracefully.

    Phase 22E: If a learned preference is active and the corresponding condition
    triggers, the preference reinforces the signal (stronger than neutral observation).

    Returns:
        lesion_activa (bool), lesion_fase (str|None),
        futbol_reciente (bool), energia_baja (bool), energia_valor (int|None),
        readiness_bajo (bool), readiness_valor (int|None),
        preferencias_activas (list[str])  — active preference types
    """
    snapshot_inyectado = physical_snapshot is not None
    ctx = {
        'lesion_activa': False,
        'lesion_fase': None,
        'futbol_reciente': False,
        'hyrox_reciente': False,
        'energia_baja': False,
        'energia_valor': None,
        'horas_sueno': None,
        'frecuencia_cardiaca_reposo': None,
        'hrv_ms': None,
        'calidad_sueno': None,
        'dolor': None,
        'evidencia_fecha': None,
        'evidencia_presente': False,
        'readiness_bajo': False,
        'readiness_valor': None,
        'acwr_valor': None,
        'acwr_alto': False,
        'acwr_dudoso': False,
        'preferencias_activas': [],
        'recuperacion': None,
        'futbol_esfuerzo': None,
    }
    if snapshot_inyectado:
        ctx['_cliente'] = cliente

    snapshot_disponible = physical_snapshot is not None
    if physical_snapshot is None:
        try:
            from core.services.physical_snapshot import build_physical_snapshot
            physical_snapshot = build_physical_snapshot(cliente, fecha_hoy)
            snapshot_disponible = True
        except Exception:
            # Compatibilidad operacional: si una fuente del snapshot falla,
            # esta fase conserva las consultas legacy y sus mismas decisiones.
            physical_snapshot = None
            snapshot_disponible = False
    if (
        not isinstance(physical_snapshot, dict)
        or physical_snapshot.get('status') == 'unavailable'
        or not isinstance(physical_snapshot.get('signals'), dict)
    ):
        snapshot_disponible = False
    signals = physical_snapshot.get('signals', {}) if snapshot_disponible else {}

    # Phase 22E: load active preferences as soft signals
    try:
        from entrenos.services.preferencias_service import get_preferencias_activas
        ctx['preferencias_activas'] = [p.tipo for p in get_preferencias_activas(cliente)]
    except Exception:
        pass

    # 1. Lesión activa (AGUDA o SUB_AGUDA)
    try:
        if snapshot_disponible:
            lesiones = (signals.get('active_injuries') or {}).get('items') or []
            lesion = next(
                (item for item in lesiones if item.get('phase') in {'AGUDA', 'SUB_AGUDA'}),
                None,
            )
            if lesion:
                ctx['lesion_activa'] = True
                ctx['lesion_fase'] = lesion.get('phase')
        else:
            from hyrox.models import UserInjury
            lesion = UserInjury.objects.filter(
                cliente=cliente,
                activa=True,
                fase__in=['AGUDA', 'SUB_AGUDA'],
            ).first()
            if lesion:
                ctx['lesion_activa'] = True
                ctx['lesion_fase'] = lesion.fase
    except Exception:
        pass

    # 2. Actividad intensa de piernas en las últimas 48 h
    # Fútbol siempre cuenta; Hyrox solo si rpe_medio >= 7 (sesiones de recuperación no bloquean).
    try:
        if snapshot_disponible:
            recent = signals.get('recent_activity') or {}
            items = recent.get('items') or []
            desde = (fecha_hoy - timedelta(days=2)).isoformat()
            hasta = (fecha_hoy - timedelta(days=1)).isoformat()
            items_en_ventana = [
                item for item in items
                if isinstance(item.get('effective_date'), str)
                and desde <= item['effective_date'] <= hasta
            ]
            hay_futbol = any(item.get('type') == 'futbol' for item in items_en_ventana)
            hay_hyrox_intenso = any(
                item.get('type') == 'hyrox'
                and item.get('rpe') is not None
                and float(item['rpe']) >= 7
                for item in items_en_ventana
            )
        else:
            # Fallback exclusivamente operativo si el snapshot no está disponible.
            hace_48h = fecha_hoy - timedelta(days=2)
            hay_futbol = ActividadRealizada.objects.filter(
                cliente=cliente, tipo='futbol',
                fecha__gte=hace_48h, fecha__lt=fecha_hoy,
            ).exists()
            hay_hyrox_intenso = ActividadRealizada.objects.filter(
                cliente=cliente, tipo='hyrox',
                fecha__gte=hace_48h, fecha__lt=fecha_hoy,
                rpe_medio__gte=7,
            ).exists()
        ctx['futbol_reciente'] = hay_futbol
        ctx['hyrox_reciente'] = hay_hyrox_intenso
    except Exception:
        pass

    # 2b. 24-oct-2026: cuánto pesó ese fútbol (Strava) y cómo llegas hoy (reloj).
    try:
        from entrenos.services.recuperacion_service import esfuerzo_futbol, lectura_recuperacion
        if ctx['futbol_reciente']:
            ctx['futbol_esfuerzo'] = esfuerzo_futbol(cliente, fecha_hoy)
        ctx['recuperacion'] = lectura_recuperacion(cliente, fecha_hoy)
    except Exception:
        pass

    # 3. Energía subjetiva del día (BitacoraDiaria) — ≤ 3 = baja
    try:
        if snapshot_disponible:
            checkin = signals.get('checkin') or {}
            # El snapshot conserva registros recientes para auditoría, pero la
            # autoridad Gym mantiene la regla legacy: solo gobierna el día exacto.
            if checkin.get('observed_on') == fecha_hoy.isoformat():
                values = checkin.get('values') or {}
                ctx.update({
                    'evidencia_fecha': fecha_hoy,
                    'evidencia_presente': True,
                    'horas_sueno': values.get('sleep_hours'),
                    'frecuencia_cardiaca_reposo': values.get('resting_hr'),
                    'hrv_ms': values.get('hrv_ms'),
                    'calidad_sueno': values.get('sleep_quality'),
                    'dolor': values.get('joint_pain'),
                })
                if values.get('energy') is not None:
                    ctx['energia_valor'] = int(values['energy'])
                    ctx['energia_baja'] = ctx['energia_valor'] <= 3
        else:
            from clientes.models import BitacoraDiaria
            bitacora = BitacoraDiaria.objects.filter(
                cliente=cliente, fecha=fecha_hoy
            ).first()
            if bitacora:
                ctx.update({
                    'evidencia_fecha': bitacora.fecha,
                    'evidencia_presente': True,
                    'horas_sueno': (
                        float(bitacora.horas_sueno)
                        if bitacora.horas_sueno is not None else None
                    ),
                    'frecuencia_cardiaca_reposo': bitacora.fc_reposo,
                    'hrv_ms': bitacora.hrv_ms,
                    'calidad_sueno': bitacora.calidad_sueno,
                    'dolor': bitacora.dolor_articular,
                })
                if bitacora.energia_subjetiva is not None:
                    ctx['energia_valor'] = int(bitacora.energia_subjetiva)
                    ctx['energia_baja'] = ctx['energia_valor'] <= 3
    except Exception:
        pass

    # 4. Readiness Hyrox — solo para usuarios con objetivo activo (< 45 = bajo)
    try:
        if snapshot_disponible:
            readiness = signals.get('hyrox_readiness') or {}
            if readiness.get('observed_on') == fecha_hoy.isoformat():
                score = (readiness.get('values') or {}).get('score')
                if score is not None:
                    ctx['readiness_valor'] = score
                    ctx['readiness_bajo'] = score < 45
        else:
            from hyrox.models import HyroxObjective, HyroxReadinessLog
            objetivo = (
                HyroxObjective.objects
                .filter(
                    cliente=cliente,
                    estado='activo',
                    fecha_evento__gte=fecha_hoy,
                )
                .order_by('fecha_evento', 'pk')
                .first()
            )
            if objetivo:
                rl = HyroxReadinessLog.objects.filter(
                    objective=objetivo, fecha=fecha_hoy
                ).first()
                if rl:
                    ctx['readiness_valor'] = rl.score
                    ctx['readiness_bajo'] = rl.score < 45
    except Exception:
        pass

    # 5. Carga aguda frente a la habitual (ACWR unificado). Un pico que viene
    #    de un dato imposible se marca como dudoso y no frena la sesión.
    try:
        from entrenos.services.acwr_decision_service import contexto_acwr
        ctx.update(contexto_acwr(cliente, fecha_hoy))
    except Exception:
        pass

    return ctx


def _aplicar_contexto(decision_base, contexto, fecha_hoy):
    """
    Phase 3B/3C: Enriches the base decision with physical context.
    Returns the decision dict with updated estado, causa_principal,
    mensaje, and modo_reducido flag.
    """
    decision = dict(decision_base)

    if decision['tipo'] == 'descanso':
        decision.update({
            'estado': 'descanso',
            'causa_principal': 'descanso_planificado',
            'modo_reducido': False,
            'contexto_fisico': contexto,
        })
        decision['mensaje'] = _MENSAJES_POR_CAUSA['descanso_planificado']
        return decision

    # Determine causa and estado from context (priority order)
    entrenamiento = decision_base.get('entrenamiento') or {}

    if contexto['lesion_activa']:
        # Phase 28 fix: only block if the session actually conflicts with the injury.
        # An AGUDA knee injury should NOT block a pure upper-body session.
        # _detectar_riesgo_lesion checks risk_tags intersection per exercise.
        lesion_conflicto = False
        try:
            cliente = contexto.get('_cliente')  # passed by caller when available
            if cliente:
                aviso = _detectar_riesgo_lesion(cliente, entrenamiento)
                lesion_conflicto = aviso is not None
            else:
                lesion_conflicto = True  # safe default: block when no client context
        except Exception:
            lesion_conflicto = True  # safe default on error
        if lesion_conflicto:
            causa = 'lesion'
            estado = 'recuperar'
        else:
            # Lesion activa but session is safe — allow training with warnings (lesion_aviso)
            causa = 'sesion_hoy'
            estado = 'entrenar'
    elif contexto['readiness_bajo']:
        causa = 'fatiga_alta'
        estado = 'recuperar'
    elif (contexto.get('recuperacion') or {}).get('nivel') == 'rojo':
        # 24-oct-2026: el reloj dice que llegas cansado (variabilidad, pulso en
        # reposo y sueño frente a tu media de 28 días).
        causa = 'recuperacion_baja'
        estado = 'version_reducida'
    elif contexto.get('acwr_alto'):
        causa = 'carga_alta'
        estado = 'version_reducida'
    elif contexto['energia_baja']:
        causa = 'energia_baja'
        estado = 'version_reducida'
    elif (
        contexto['futbol_reciente'] and _es_sesion_pierna(entrenamiento)
        # 24-oct-2026: un partido suave (Strava) no rebaja la pierna.
        and (contexto.get('futbol_esfuerzo') or {}).get('nivel') != 'suave'
    ):
        # Mismo principio que el fix Phase 28 de arriba: el fútbol fatiga piernas,
        # no debe rebajar una sesión de tren superior. Antes se aplicaba sin
        # comprobar el grupo muscular de hoy — _es_sesion_pierna ya existía y se
        # usaba correctamente en _aplicar_preferencia_activa, pero no aquí.
        causa = 'futbol_reciente'
        estado = 'version_reducida'
    elif contexto.get('hyrox_reciente') and _es_sesion_pierna(entrenamiento):
        causa = 'hyrox_reciente'
        estado = 'version_reducida'
    elif decision['tipo'] == 'pendiente':
        sp = decision.get('sesion_programada')
        if sp and sp.prioridad == SesionProgramada.PRIORIDAD_ALTA:
            causa = 'pendiente_prioritaria'
        else:
            causa = 'pendiente_normal'
        estado = 'entrenar'
    else:
        causa = 'sesion_hoy'
        estado = 'entrenar'

    # Las causas 'pendiente_prioritaria'/'pendiente_normal' tienen un mensaje fijo
    # en _MENSAJES_POR_CAUSA, pero decision_base['mensaje'] (construido en
    # obtener_sesion_recomendada_hoy) ya trae el "Quedó pendiente ayer/hace N
    # días" calculado a partir de sesion_programada.fecha_prevista — perderlo
    # aquí es lo que hacía que una sesión atrasada pareciera "la de hoy con la
    # fecha mal" en vez de "la sesión de hace N días que sigue pendiente".
    if decision['tipo'] == 'pendiente':
        mensaje = decision_base.get('mensaje') or _MENSAJES_POR_CAUSA.get(causa, '')
    else:
        mensaje = _MENSAJES_POR_CAUSA.get(causa, decision.get('mensaje', ''))
    # 24-oct-2026: con dato del reloj o de Strava, la frase del entrenador.
    if causa == 'recuperacion_baja' and (contexto.get('recuperacion') or {}).get('frase'):
        mensaje = contexto['recuperacion']['frase']
    elif causa == 'futbol_reciente' and (contexto.get('futbol_esfuerzo') or {}).get('frase'):
        mensaje = contexto['futbol_esfuerzo']['frase']

    decision.update({
        'estado': estado,
        'causa_principal': causa,
        'modo_reducido': estado == 'version_reducida',
        'contexto_fisico': contexto,
        'mensaje': mensaje,
    })
    return decision


def inferir_prioridad_sesion(entrenamiento):
    """
    Infers session priority from PlanificadorHelms output.

    Alta:   at least one compuesto_principal exercise in a main muscle group
            (pecho, espalda, cuadriceps, isquios, gluteos).
    Normal: accessory, secondary-compound-only, or minor-group sessions.
    None:   rest day (no exercises).

    Requires tipo_ejercicio in exercise dicts (added to planificador output in Phase 2A).
    """
    if _es_descanso(entrenamiento):
        return None

    try:
        from analytics.planificador_helms.config import GRUPOS_GRANDES
    except Exception:
        GRUPOS_GRANDES = {'pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos'}

    for ej in entrenamiento.get('ejercicios', []):
        if (
            ej.get('tipo_ejercicio') == 'compuesto_principal'
            and ej.get('grupo_muscular', '').lower() in GRUPOS_GRANDES
        ):
            return SesionProgramada.PRIORIDAD_ALTA

    return SesionProgramada.PRIORIDAD_NORMAL


def saltar_sesion_programada(sesion, motivo=''):
    """Marks a pending session as skipped by the user."""
    sesion.estado = SesionProgramada.ESTADO_SALTADA_USUARIO
    sesion.motivo_estado = motivo or 'Sesión saltada por el usuario.'
    sesion.save(update_fields=['estado', 'motivo_estado', 'actualizada_en'])
    return sesion


def posponer_sesion_programada(sesion, hasta, motivo=''):
    """Postpone a pending session while preserving the chronological plan queue.

    A session that was already reubicada is occupying its effective date, not
    merely its original ``fecha_prevista``.  Moving it again must therefore
    push the planned session for that effective date (and any materialised
    sessions after it) behind the recovered session.  Otherwise a Thursday
    moved to Friday and then Saturday vanishes from the queue while Friday's
    workout is shown immediately.
    """
    fecha_actual = sesion.pospuesta_hasta or sesion.fecha_prevista

    with transaction.atomic():
        sesion = SesionProgramada.objects.select_for_update().get(pk=sesion.pk)
        fecha_actual = sesion.pospuesta_hasta or sesion.fecha_prevista

        # Only a re-postponement can collide with a separate workout planned
        # for the current effective date. A fresh session of today is itself
        # that planned workout and needs no successor materialised.
        if (
            sesion.pospuesta_hasta
            and fecha_actual != sesion.fecha_prevista
            and hasta > fecha_actual
        ):
            sucesora = (
                SesionProgramada.objects.select_for_update()
                .filter(
                    cliente=sesion.cliente,
                    fecha_prevista=fecha_actual,
                    estado=SesionProgramada.ESTADO_PENDIENTE,
                )
                .exclude(pk=sesion.pk)
                .first()
            )
            if sucesora is None:
                try:
                    entrenamiento = _normalizar_entrenamiento(
                        _build_planificador(sesion.cliente)
                        .generar_entrenamiento_para_fecha(fecha_actual)
                    )
                    if not _es_descanso(entrenamiento):
                        prioridad = (
                            inferir_prioridad_sesion(entrenamiento)
                            or SesionProgramada.PRIORIDAD_ALTA
                        )
                        sucesora = SesionProgramada.objects.create(
                            cliente=sesion.cliente,
                            fecha_prevista=fecha_actual,
                            estado=SesionProgramada.ESTADO_PENDIENTE,
                            prioridad=prioridad,
                            nombre_sesion=(
                                entrenamiento.get('rutina_nombre')
                                or entrenamiento.get('nombre_rutina')
                                or ''
                            ),
                            bloque_nombre=entrenamiento.get('bloque', ''),
                            dia_numero=entrenamiento.get('dia'),
                            motivo_estado='Sesión preservada al reubicar una anterior.',
                        )
                except Exception:
                    logger.exception(
                        'posponer_sesion_programada: no se pudo materializar la sucesora de %s',
                        sesion.pk,
                    )

            # Put every materialised future session after the recovered one.
            # ``max`` cascades collisions: Thu→Sat makes Fri→Sun; a Saturday
            # session already in the queue is then moved to Monday, etc.
            siguientes = list(
                SesionProgramada.objects.select_for_update()
                .filter(
                    cliente=sesion.cliente,
                    estado=SesionProgramada.ESTADO_PENDIENTE,
                    fecha_prevista__gte=fecha_actual,
                )
                .exclude(pk=sesion.pk)
                .order_by('fecha_prevista', 'id')
            )
            ultimo_hueco = hasta
            for siguiente in siguientes:
                fecha_efectiva = siguiente.pospuesta_hasta or siguiente.fecha_prevista
                if fecha_efectiva < fecha_actual:
                    continue
                destino = max(
                    fecha_efectiva + (hasta - fecha_actual),
                    ultimo_hueco + timedelta(days=1),
                )
                siguiente.pospuesta_hasta = destino
                siguiente.motivo_estado = 'Sesión reubicada para conservar el orden del plan.'
                siguiente.save(update_fields=['pospuesta_hasta', 'motivo_estado', 'actualizada_en'])
                ultimo_hueco = destino

        sesion.pospuesta_hasta = hasta
        sesion.motivo_estado = motivo or f'Sesión pospuesta hasta {hasta}.'
        sesion.save(update_fields=['pospuesta_hasta', 'motivo_estado', 'actualizada_en'])
    return sesion


def posponer_entrenamiento_hoy(cliente, fecha_hoy):
    """
    "Hoy no puedo entrenar" — postpones ALL currently visible pending sessions
    until tomorrow. Semantically: the user is saying they can't train today,
    not just that they can't do a specific session.
    """
    from django.db.models import Q
    manana = fecha_hoy + timedelta(days=1)
    SesionProgramada.objects.filter(
        cliente=cliente,
        estado=SesionProgramada.ESTADO_PENDIENTE,
        fecha_prevista__lte=fecha_hoy,
    ).filter(
        Q(pospuesta_hasta__isnull=True) | Q(pospuesta_hasta__lte=fecha_hoy)
    ).update(
        pospuesta_hasta=manana,
        motivo_estado='El usuario indicó que hoy no podía entrenar.',
    )


def _aplicar_efecto_distribucion(cliente, decision, fecha_hoy):
    """
    Phase 19 — Adds contextual aviso when a distribution trial is active.

    Does NOT silently change the session. Instead, adds 'distribucion_aviso' to
    the decision dict so the panel can show a relevant proposal at the right moment.

    Tipos de aviso:
    - redistrib_dia_frecuente: today is the problematic day → suggest considering postponing
    - redistrib_pierna_futbol: leg session + recent football → suggest postponing
    - redistrib_aligerar_dia: this is the day that concentrates esencials → mark as lite
    - redistrib_dias_menores: normal-priority sessions deprioritized
    """
    try:
        from entrenos.models import IntervencionPlan
        _REDISTRIB = {
            IntervencionPlan.TIPO_REDISTRIB_DIA,
            IntervencionPlan.TIPO_REDISTRIB_DIAS,
            IntervencionPlan.TIPO_REDISTRIB_PIERNA,
            IntervencionPlan.TIPO_REDISTRIB_LIGERO,
        }
        intervencion = (
            IntervencionPlan.objects
            .filter(
                cliente=cliente, tipo__in=_REDISTRIB,
                estado=IntervencionPlan.ESTADO_ACTIVA,
                fecha_inicio__lte=fecha_hoy, fecha_fin__gte=fecha_hoy,
            )
            .order_by('-creada_en')
            .first()
        )
        if intervencion:
            tipo = intervencion.tipo
        else:
            tipo = None

        if tipo == IntervencionPlan.TIPO_REDISTRIB_DIA:
            dia_problema = (intervencion.origen_patron or '').lower()
            nombre_hoy = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][fecha_hoy.weekday()]
            if nombre_hoy in dia_problema or not dia_problema:
                decision['distribucion_aviso'] = {
                    'tipo': tipo,
                    'texto': (
                        f"Este día está en prueba. "
                        f"Puedes mantener la sesión hoy o posponerla y observar si el patrón mejora."
                    ),
                    'accion_sugerida': 'posponer_opcional',
                }

        elif tipo == IntervencionPlan.TIPO_REDISTRIB_PIERNA:
            # Check if today has a leg session near recent football or intense Hyrox
            ctx = decision.get('contexto_fisico', {})
            if ctx.get('futbol_reciente') or ctx.get('hyrox_reciente'):
                entrenamiento = decision.get('entrenamiento') or {}
                ejercicios = entrenamiento.get('ejercicios', [])
                es_pierna = any(
                    any(kw in ej.get('nombre', '').lower() for kw in ['pierna', 'quad', 'sentadilla', 'prensa'])
                    for ej in ejercicios
                )
                if es_pierna:
                    # Phase 22E: if preference active, signal is stronger
                    tiene_preferencia = 'evitar_pierna_tras_futbol' in ctx.get('preferencias_activas', [])
                    decision['distribucion_aviso'] = {
                        'tipo': tipo,
                        'texto': (
                            ("Preferencia del plan: " if tiene_preferencia else "Prueba activa: ")
                            + "separar pierna del fútbol. "
                            "Hay actividad de fútbol reciente. "
                            + ("El plan recomienda posponer pierna." if tiene_preferencia else "Considera posponer pierna un día más.")
                        ),
                        'accion_sugerida': 'posponer_recomendado' if tiene_preferencia else 'posponer_opcional',
                    }

        elif tipo == IntervencionPlan.TIPO_REDISTRIB_LIGERO:
            decision['distribucion_aviso'] = {
                'tipo': tipo,
                'texto': (
                    "Prueba activa: día más ligero. "
                    "Los accesorios de hoy son opcionales como parte del experimento de distribución."
                ),
                'accion_sugerida': 'accesorios_opcionales',
            }

        elif tipo == IntervencionPlan.TIPO_REDISTRIB_DIAS:
            sp = decision.get('sesion_programada')
            if sp and sp.prioridad == SesionProgramada.PRIORIDAD_NORMAL:
                decision['distribucion_aviso'] = {
                    'tipo': tipo,
                    'texto': (
                        "Prueba de días menores activa. Esta sesión es secundaria; "
                        "el plan prioriza el bloque principal si hay límite de tiempo o energía."
                    ),
                    'accion_sugerida': 'version_esencial_sugerida',
                }

    except Exception:
        logger.warning('_aplicar_efecto_distribucion: error inesperado')

    # Phase 3.5 — Vigilancia de señal corporal del diario (observación, sin cambio de carga)
    try:
        from entrenos.models import IntervencionPlan as _IP
        if decision.get('causa_principal') not in _CAUSA_SEGURIDAD and not decision.get('distribucion_aviso'):
            _vigilar = (
                _IP.objects
                .filter(
                    cliente=cliente,
                    tipo=_IP.TIPO_VIGILAR_SENAL,
                    estado=_IP.ESTADO_ACTIVA,
                    fecha_inicio__lte=fecha_hoy, fecha_fin__gte=fecha_hoy,
                    # 15-oct-2026: la frase habla del diario; solo es verdad
                    # cuando la vigilancia nace de una señal del Diario.
                    origen_patron='diario_tendencia_corporal',
                )
                .first()
            )
            if _vigilar:
                decision['distribucion_aviso'] = {
                    'tipo': 'vigilar_senal',
                    'texto': (
                        'Señal corporal del diario bajo vigilancia. '
                        'El plan observa si la carga corporal coincide con el entreno. '
                        'No cambia la sesión por sí solo.'
                    ),
                    'accion_sugerida': 'observar',
                }
    except Exception:
        logger.warning('_aplicar_efecto_distribucion: error en vigilar_senal')

    return decision


# ── Phase 28 — Injury safety layer ───────────────────────────────────────────

_FASE_LABELS = {
    'AGUDA':     'fase aguda',
    'SUB_AGUDA': 'fase sub-aguda',
    'RETORNO':   'fase de retorno',
}


def _detectar_riesgo_lesion(cliente, entrenamiento):
    """
    Phase 28A — Cross-references active injuries with session exercises.

    Returns a lesion_aviso dict or None.

    Rules:
    - Fires for ANY active injury (all phases), not just RETORNO.
      AGUDA/SUB_AGUDA: motor already blocks training — aviso shows WHICH exercises.
      RETORNO: motor does NOT block — aviso warns without stopping the session.
    - Never changes estado or causa_principal.
    - Degrades silently if any model is missing.
    """
    try:
        from hyrox.models import UserInjury
        from rutinas.models import EjercicioBase

        if not entrenamiento:
            return None

        ejercicios = entrenamiento.get('ejercicios', [])
        if not ejercicios:
            return None

        lesiones = list(UserInjury.objects.filter(
            cliente=cliente, activa=True,
        ).exclude(fase='RECUPERADO'))
        if not lesiones:
            return None

        # Build risk_tags map from exercise dicts first
        tags_por_nombre = {}
        for ej in ejercicios:
            nombre = (ej.get('nombre') or '').strip()
            if nombre:
                tags_por_nombre[nombre] = set(ej.get('risk_tags') or [])

        # DB fallback for exercises without tags in dict
        sin_tags = [n for n, t in tags_por_nombre.items() if not t]
        if sin_tags:
            for db_ej in EjercicioBase.objects.filter(nombre__in=sin_tags).values('nombre', 'risk_tags'):
                n = db_ej['nombre']
                if n in tags_por_nombre:
                    tags_por_nombre[n] = set(db_ej['risk_tags'] or [])

        for lesion in lesiones:
            restringidos = set(lesion.tags_restringidos or [])
            if not restringidos:
                continue

            en_riesgo = [
                nombre for nombre, ej_tags in tags_por_nombre.items()
                if ej_tags & restringidos
            ]
            if not en_riesgo:
                continue

            zona = lesion.zona_afectada
            fase = _FASE_LABELS.get(lesion.fase, lesion.fase.lower())
            es_bloqueante = lesion.fase in ('AGUDA', 'SUB_AGUDA')

            if es_bloqueante:
                mensaje = (
                    f"En {fase} la {zona} necesita reposo relativo. "
                    f"Si decides entrenar, estos ejercicios tienen riesgo: "
                    f"{', '.join(en_riesgo[:3])}. Reduce rango y detente ante cualquier dolor."
                )
            else:
                mensaje = (
                    f"En {fase}, la {zona} puede tolerar carga progresiva. "
                    f"Algunos ejercicios de hoy requieren atención: "
                    f"{', '.join(en_riesgo[:3])}. "
                    f"Reduce rango de movimiento y detente si aparece dolor."
                )

            return {
                'zona':                zona,
                'fase':                lesion.fase,
                'es_bloqueante':       es_bloqueante,
                'ejercicios_en_riesgo': en_riesgo,
                'mensaje':             mensaje,
                'accion_sugerida':     'version_esencial_recomendada' if es_bloqueante else 'revisar_antes_de_entrenar',
            }

    except Exception:
        logger.warning('_detectar_riesgo_lesion: error inesperado')

    return None


def _aplicar_aviso_lesion(cliente, decision, fecha_hoy):
    """
    Phase 28B — Adds lesion_aviso to the decision without changing its outcome.
    """
    entrenamiento = decision.get('entrenamiento') or {}
    aviso = _detectar_riesgo_lesion(cliente, entrenamiento)
    if aviso:
        decision['lesion_aviso'] = aviso
    return decision


# ── Phase 24 — Preference as secondary cause ─────────────────────────────────

_CAUSA_SEGURIDAD = {'lesion', 'fatiga_alta'}

_PREF_MENSAJES = {
    'evitar_pierna_tras_futbol': (
        'El plan recuerda que separar pierna del fútbol te dio más margen. Hoy lo usa como referencia.'
    ),
    'evitar_dia_frecuente': (
        'El plan ha aprendido que este día suele dar menos margen. Lo tiene en cuenta como referencia.'
    ),
    'preferir_menos_dias': (
        'Esta sesión es secundaria según la preferencia del plan. '
        'Puedes priorizarla si tienes energía o posponerla sin perder el hilo.'
    ),
    'aligerar_dia_concreto': (
        'El plan ha aprendido que este suele ser tu día de menor margen. '
        'Los accesorios de hoy son opcionales como referencia, no como regla.'
    ),
}

_PREF_ACCION = {
    'evitar_pierna_tras_futbol': 'posponer_recomendado',
    'evitar_dia_frecuente':      'posponer_recomendado',
    'preferir_menos_dias':       'version_esencial_sugerida',
    'aligerar_dia_concreto':     'accesorios_opcionales',
}


def _es_sesion_pierna(entrenamiento):
    """Returns True if the session has leg exercises (by name or muscle group)."""
    if not entrenamiento:
        return False
    _PIERNA_KW = ('pierna', 'quad', 'sentadilla', 'squat', 'prensa', 'isquio', 'glut', 'femoral', 'lunges', 'zancada')
    for ej in entrenamiento.get('ejercicios', []):
        nombre = ej.get('nombre', '').lower()
        grupo  = ej.get('grupo_muscular', '').lower()
        if any(kw in nombre or kw in grupo for kw in _PIERNA_KW):
            return True
    return False


def _aplicar_preferencia_activa(cliente, decision, fecha_hoy):
    """
    Phase 24 — Adds 'preferencia_aplicada' to the decision when an active preference
    matches the current session context.

    CONTRACT:
    - Does NOT change estado, causa_principal, or entrenamiento.
    - Does NOT fire when causa_principal is in _CAUSA_SEGURIDAD (safety wins).
    - Each preference fires independently of the dominant cause (secondary layer).
    - Returns decision unchanged if no preference fires.
    """
    causa = decision.get('causa_principal')
    if causa in _CAUSA_SEGURIDAD:
        return decision

    ctx = decision.get('contexto_fisico', {})
    prefs_activas = ctx.get('preferencias_activas', [])
    if not prefs_activas:
        return decision

    entrenamiento = decision.get('entrenamiento') or {}
    aplicada = None

    # evitar_pierna_tras_futbol: condition = leg session + recent football or intense Hyrox
    if (
        'evitar_pierna_tras_futbol' in prefs_activas
        and (ctx.get('futbol_reciente') or ctx.get('hyrox_reciente'))
        and _es_sesion_pierna(entrenamiento)
    ):
        aplicada = 'evitar_pierna_tras_futbol'

    # evitar_dia_frecuente: condition = today's weekday matches origen_patron of the preference
    if aplicada is None and 'evitar_dia_frecuente' in prefs_activas:
        try:
            from entrenos.models import PreferenciaPlanAprendida
            pref = PreferenciaPlanAprendida.objects.filter(
                cliente=cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_DIA,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            ).first()
            if pref and pref.metadata:
                dia_evitar = (pref.metadata.get('dia_semana') or '').lower()
                nombre_hoy = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][fecha_hoy.weekday()]
                if dia_evitar and dia_evitar in nombre_hoy:
                    aplicada = 'evitar_dia_frecuente'
        except Exception:
            pass

    # preferir_menos_dias: condition = session is normal priority (accessory)
    if aplicada is None and 'preferir_menos_dias' in prefs_activas:
        sp = decision.get('sesion_programada')
        if sp and getattr(sp, 'prioridad', None) == SesionProgramada.PRIORIDAD_NORMAL:
            aplicada = 'preferir_menos_dias'

    # aligerar_dia_concreto: always applies when active (any session with exercises)
    if aplicada is None and 'aligerar_dia_concreto' in prefs_activas:
        if entrenamiento.get('ejercicios'):  # there's something to lighten
            aplicada = 'aligerar_dia_concreto'

    if aplicada:
        from entrenos.models import PreferenciaPlanAprendida as _PP
        desc = ''
        try:
            p = _PP.objects.filter(
                cliente=cliente, tipo=aplicada, estado=_PP.ESTADO_ACTIVA
            ).values_list('descripcion', flat=True).first()
            desc = p or ''
        except Exception:
            pass

        decision['preferencia_aplicada'] = {
            'tipo':            aplicada,
            'descripcion':     desc,
            'mensaje':         _PREF_MENSAJES.get(aplicada, ''),
            'accion_sugerida': _PREF_ACCION.get(aplicada, ''),
        }

    return decision


class CierreSesionProgramadaInvalido(Exception):
    """El ID explícito no puede cerrarse con este entrenamiento."""


def resolver_sesion_programada_portal(cliente, fecha, rutina_nombre):
    """Devuelve el único pendiente canónico compatible o ``None``.

    No corrige ni elige entre candidatos ambiguos. La fecha efectiva es
    ``pospuesta_hasta`` cuando existe y, en otro caso, ``fecha_prevista``.
    """
    identidad = ' '.join((rutina_nombre or '').casefold().split())
    candidatas = []
    for sesion in SesionProgramada.objects.filter(
        cliente=cliente, estado=SesionProgramada.ESTADO_PENDIENTE,
    ).only('id', 'nombre_sesion', 'fecha_prevista', 'pospuesta_hasta'):
        fecha_efectiva = sesion.pospuesta_hasta or sesion.fecha_prevista
        nombre = ' '.join((sesion.nombre_sesion or '').casefold().split())
        if fecha_efectiva == fecha and nombre == identidad:
            candidatas.append(sesion)
    return candidatas[0] if len(candidatas) == 1 else None


@transaction.atomic
def cerrar_sesion_programada(sesion_programada_id, entreno_realizado):
    """
    Cierra la sesión indicada explícitamente y devuelve un resultado observable.

    Un ID inexistente conserva compatibilidad como ``missing``; propiedad,
    estado y contrato incoherentes son errores causales y nunca se silencian.
    """
    sp = (
        SesionProgramada.objects.select_for_update()
        .select_related('contrato_semanal')
        .filter(id=sesion_programada_id)
        .first()
    )
    if sp is None:
        return {'estado': 'missing', 'sesion_programada_id': sesion_programada_id}
    if sp.cliente_id != entreno_realizado.cliente_id:
        raise CierreSesionProgramadaInvalido('La sesión programada pertenece a otro cliente.')
    if sp.estado != SesionProgramada.ESTADO_PENDIENTE:
        raise CierreSesionProgramadaInvalido('La sesión programada ya no está pendiente.')
    if sp.contrato_semanal_id:
        contrato = sp.contrato_semanal
        if contrato.cliente_id != entreno_realizado.cliente_id:
            raise CierreSesionProgramadaInvalido('El contrato semanal pertenece a otro cliente.')
        if sp.semana_prescrita and sp.semana_prescrita != contrato.semana:
            raise CierreSesionProgramadaInvalido('La semana prescrita no coincide con el contrato.')

    fecha_real = entreno_realizado.fecha_ejecucion or entreno_realizado.fecha
    sp.estado = (
        SesionProgramada.ESTADO_PARCIAL
        if entreno_realizado.estado_cierre == EntrenoRealizado.ESTADO_PARCIAL
        else SesionProgramada.ESTADO_COMPLETADA
    )
    sp.fecha_realizada = fecha_real
    sp.entreno_realizado = entreno_realizado
    sp.save(update_fields=['estado', 'fecha_realizada', 'entreno_realizado', 'actualizada_en'])
    return {
        'estado': 'cerrada',
        'sesion_programada_id': sp.pk,
        'entreno_realizado_id': entreno_realizado.pk,
        'fecha_realizada': fecha_real,
    }


def sincronizar_pendientes_recientes(cliente, fecha_hoy):
    """
    On-demand sync split into two parts:

    1. _marcar_completadas() — always runs, no cache, O(pending count).
       Ensures completing a session is visible on the very next panel load.

    2. Expensive part (cached 1 h) — calls PlanificadorHelms for up to 14 days
       to discover newly-missed sessions, then reconciles weekly.
    """
    # Part 1: always run — cheap and correctness-critical
    _marcar_completadas(cliente, fecha_hoy)

    # Part 2: throttled — expensive planificador loop
    cache_key = f'sesion_sync_{cliente.id}_{fecha_hoy.isoformat()}'
    if cache.get(cache_key):
        return

    try:
        planificador = _build_planificador(cliente)
        fecha_inicio = fecha_hoy - timedelta(days=14)
        fecha_fin = fecha_hoy - timedelta(days=1)

        tracked = set(
            SesionProgramada.objects.filter(
                cliente=cliente,
                fecha_prevista__gte=fecha_inicio,
                fecha_prevista__lte=fecha_fin,
            ).values_list('fecha_prevista', flat=True)
        )

        # Batch: dates with any completed gym session in the window (avoids 1 query/day)
        completadas = set(
            EntrenoRealizado.objects.filter(
                cliente=cliente,
                fecha__gte=fecha_inicio,
                fecha__lte=fecha_fin,
            ).values_list('fecha', flat=True)
        )
        try:
            completadas |= set(
                ActividadRealizada.objects.filter(
                    cliente=cliente,
                    tipo='gym',
                    fecha__gte=fecha_inicio,
                    fecha__lte=fecha_fin,
                ).values_list('fecha', flat=True)
            )
        except Exception:
            pass

        fecha = fecha_inicio
        while fecha <= fecha_fin:
            if fecha not in tracked and fecha not in completadas:
                entrenamiento = planificador.generar_entrenamiento_para_fecha(fecha)
                if not _es_descanso(entrenamiento):
                    prioridad = inferir_prioridad_sesion(entrenamiento) or SesionProgramada.PRIORIDAD_ALTA
                    SesionProgramada.objects.create(
                        cliente=cliente,
                        fecha_prevista=fecha,
                        estado=SesionProgramada.ESTADO_PENDIENTE,
                        prioridad=prioridad,
                        nombre_sesion=(
                            entrenamiento.get('rutina_nombre') or
                            entrenamiento.get('nombre_rutina') or ''
                        ),
                        bloque_nombre=entrenamiento.get('bloque', ''),
                        dia_numero=entrenamiento.get('dia'),
                        motivo_estado='Sesión prevista no completada.',
                    )
            fecha += timedelta(days=1)

        # Reconcile after creating new pendientes
        _reconciliar_pendientes_semana(cliente, fecha_hoy)

    except Exception:
        logger.exception('sincronizar_pendientes_recientes: error para cliente %s', cliente.id)
    finally:
        cache.set(cache_key, True, _SYNC_CACHE_TTL)


def _devolver_con_traza(cliente, decision, fecha):
    """Registra de forma idempotente toda salida canónica y devuelve la decisión."""
    try:
        from entrenos.services.decision_trace_service import registrar_decision_trace

        decision_para_traza = dict(decision)
        decision_para_traza['_traza_salida_significativa'] = True
        registrar_decision_trace(cliente, decision_para_traza, fecha)
    except Exception:
        logger.warning(
            'obtener_sesion_recomendada_hoy: no se pudo registrar la traza',
            exc_info=True,
        )
    return decision


# ── Paso 3 (13-oct-2026): la semana como cola de sesiones ────────────────────
#
# El plan de la semana es una lista ordenada (Día 1, Día 2, ...). El día que
# entrenas toca la siguiente sesión de la semana que aún no has hecho, aunque su
# fecha prevista ya haya pasado; lo que no hiciste entre semana pasa al fin de
# semana. Antes, recuperar una sesión atrasada consumía el hueco del día y la
# sesión de ese día desaparecía sin aviso (saltarse el martes hacía perder el
# Día 3, no el Día 2). La semana se cierra el domingo: lo que quede sin hacer
# no se arrastra a la siguiente, y el lunes se dice qué se quedó fuera.

def _estados_resueltos():
    return {
        SesionProgramada.ESTADO_COMPLETADA, SesionProgramada.ESTADO_PARCIAL,
        SesionProgramada.ESTADO_SALTADA_USUARIO, SesionProgramada.ESTADO_OMITIDA_USUARIO,
        SesionProgramada.ESTADO_CANCELADA_LESION, SesionProgramada.ESTADO_SUSTITUIDA_RECUPERACION,
    }


def _grupos_de(entrenamiento):
    return {
        ej.get('grupo_muscular') for ej in (entrenamiento or {}).get('ejercicios') or []
        if ej.get('grupo_muscular')
    }


def cola_semana(cliente, fecha_hoy, planificador=None):
    """Sesiones de la semana de ``fecha_hoy`` hasta hoy, con su estado en la cola.

    Devuelve una lista ordenada de dicts: fecha, nombre, entrenamiento, hecha
    (bool), entreno (EntrenoRealizado que la cubrió o None) y resuelta_por
    ('entreno' | estado de SesionProgramada | None).
    """
    from datetime import timedelta as _td

    planificador = planificador or _build_planificador(cliente)
    lunes = fecha_hoy - _td(days=fecha_hoy.weekday())
    sesiones = []
    f = lunes
    while f <= fecha_hoy:
        ent = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(f))
        if not _es_descanso(ent):
            sesiones.append({
                'fecha': f,
                'nombre': (ent.get('rutina_nombre') or '').strip(),
                'entrenamiento': ent,
                'hecha': False,
                'entreno': None,
                'resuelta_por': None,
            })
        f += _td(days=1)
    if not sesiones:
        return sesiones

    # 1) Estados explícitos de SesionProgramada (completada, saltada a mano...).
    resueltos = _estados_resueltos()
    sp_por_fecha = {
        sp.fecha_prevista: sp for sp in SesionProgramada.objects.filter(
            cliente=cliente, fecha_prevista__gte=lunes, fecha_prevista__lte=fecha_hoy,
        )
    }
    ids_entrenos_vinculados = set()
    for s in sesiones:
        sp = sp_por_fecha.get(s['fecha'])
        if sp and sp.estado in resueltos:
            s['hecha'] = True
            s['resuelta_por'] = sp.estado
            if sp.entreno_realizado_id:
                ids_entrenos_vinculados.add(sp.entreno_realizado_id)

    # 2) Entrenos de la semana: cada uno cubre UNA sesión con su mismo nombre,
    #    la primera aún sin cubrir (así recuperar el Día 2 el miércoles no
    #    borra el Día 3).
    from django.db.models import Q
    entrenos = (
        EntrenoRealizado.objects.filter(cliente=cliente, rutina__isnull=False)
        .filter(
            Q(fecha_ejecucion__gte=lunes, fecha_ejecucion__lte=fecha_hoy)
            | Q(fecha_ejecucion__isnull=True, fecha__gte=lunes, fecha__lte=fecha_hoy)
        )
        .exclude(pk__in=ids_entrenos_vinculados)
        .select_related('rutina').order_by('fecha_ejecucion', 'fecha', 'id')
    )
    for e in entrenos:
        nombre = (e.rutina.nombre or '').strip().casefold()
        for s in sesiones:
            if not s['hecha'] and s['nombre'].casefold() == nombre:
                s['hecha'] = True
                s['entreno'] = e
                s['resuelta_por'] = 'entreno'
                break
    return sesiones


def _siguiente_de_cola(cliente, fecha_hoy):
    """La sesión atrasada que toca hoy, o None.

    Devuelve un dict con 'fecha', 'nombre', 'entrenamiento' (puede ser None) y
    'sp' (SesionProgramada existente o None). None significa: no hay nada
    atrasado, sigue el flujo de siempre (la sesión de hoy si hoy se entrena,
    descanso si no). Si ya entrenaste hoy no se propone otra: una al día.

    Fuentes, en orden de fecha prevista:
    - la cola de la semana (sesiones del plan aún sin hacer), desde la fecha
      de alta del cliente: nadie "debe" sesiones de antes de empezar;
    - las SesionProgramada pendientes que ya tocan (incluidas las aplazadas a
      hoy o antes), aunque su fecha no figure hoy en el plan.
    """
    from datetime import timedelta as _td
    from django.db.models import Q

    entreno_hoy = EntrenoRealizado.objects.filter(cliente=cliente).filter(
        Q(fecha_ejecucion=fecha_hoy) | Q(fecha_ejecucion__isnull=True, fecha=fecha_hoy)
    ).exists()
    if entreno_hoy:
        return None

    alta = getattr(cliente, 'fecha_registro', None)
    cola = cola_semana(cliente, fecha_hoy)
    sp_pendientes = list(
        SesionProgramada.objects.filter(
            cliente=cliente, estado=SesionProgramada.ESTADO_PENDIENTE,
            fecha_prevista__lte=fecha_hoy,
        ).order_by('fecha_prevista', 'id')
    )
    sp_por_fecha = {sp.fecha_prevista: sp for sp in sp_pendientes}
    aplazadas_futuro = {
        sp.fecha_prevista for sp in sp_pendientes
        if sp.pospuesta_hasta and sp.pospuesta_hasta > fecha_hoy
    }

    candidatas = []
    fechas_cola = set()
    for s in cola:
        fechas_cola.add(s['fecha'])
        if s['hecha'] or s['fecha'] in aplazadas_futuro:
            continue
        if alta and s['fecha'] < alta and s['fecha'] not in sp_por_fecha:
            continue
        candidatas.append({**s, 'sp': sp_por_fecha.get(s['fecha'])})
    for sp in sp_pendientes:
        if sp.fecha_prevista in fechas_cola or sp.fecha_prevista in aplazadas_futuro:
            continue
        candidatas.append({
            'fecha': sp.fecha_prevista, 'nombre': sp.nombre_sesion,
            'entrenamiento': None, 'sp': sp,
        })
    if not candidatas:
        return None
    candidatas.sort(key=lambda c: (c['fecha'], c['sp'].id if c['sp'] else 0))

    # No repetir músculo dos días seguidos: si la primera comparte grupos con
    # lo que hiciste ayer, se adelanta la siguiente que no los toque.
    ayer = fecha_hoy - _td(days=1)
    grupos_ayer = set()
    for s in cola:
        e = s.get('entreno')
        if e and (e.fecha_ejecucion or e.fecha) == ayer:
            grupos_ayer |= _grupos_de(s['entrenamiento'])
    elegida = candidatas[0]
    if grupos_ayer and _grupos_de(elegida['entrenamiento']) & grupos_ayer:
        for c in candidatas[1:]:
            if not (_grupos_de(c['entrenamiento']) & grupos_ayer):
                elegida = c
                break
    if elegida['fecha'] == fecha_hoy and elegida['sp'] is None:
        return None  # lo que toca es la sesión de hoy: flujo normal
    return elegida


def resumen_semana_cerrada(cliente, fecha_hoy):
    """Sesiones de la semana anterior que se quedaron sin hacer (para decirlo)."""
    from datetime import timedelta as _td
    lunes = fecha_hoy - _td(days=fecha_hoy.weekday())
    return list(
        SesionProgramada.objects.filter(
            cliente=cliente,
            estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
            motivo_estado=MOTIVO_OMISION_SEMANA_CERRADA,
            fecha_prevista__gte=lunes - _td(days=7),
            fecha_prevista__lt=lunes,
        ).order_by('fecha_prevista')
    )


def _nota_semana_cerrada(cliente, fecha_hoy):
    """'La semana pasada se quedaron sin hacer el Día 3 y el Día 5.' o None.

    Solo mientras no hayas entrenado aún esta semana: es la explicación del
    arranque limpio, no un recordatorio diario.
    """
    from datetime import timedelta as _td
    from django.db.models import Q
    lunes = fecha_hoy - _td(days=fecha_hoy.weekday())
    if EntrenoRealizado.objects.filter(cliente=cliente).filter(
        Q(fecha_ejecucion__gte=lunes, fecha_ejecucion__lte=fecha_hoy)
        | Q(fecha_ejecucion__isnull=True, fecha__gte=lunes, fecha__lte=fecha_hoy)
    ).exists():
        return None
    perdidas = resumen_semana_cerrada(cliente, fecha_hoy)
    if not perdidas:
        return None
    nombres = []
    for sp in perdidas:
        nombres.append(_etiqueta_dia(sp.nombre_sesion) or sp.fecha_prevista.strftime('%d/%m'))
    if len(nombres) == 1:
        lista = f'el {nombres[0]}'
    else:
        lista = 'el ' + ', el '.join(nombres[:-1]) + f' y el {nombres[-1]}'
    verbo = 'se quedó' if len(nombres) == 1 else 'se quedaron'
    return f'La semana pasada {verbo} sin hacer {lista}. No lo arrastro: la semana empieza limpia.'


def _etiqueta_dia(nombre_sesion):
    """'Dia 2 - Hipertrofia' → 'Día 2' (o '' si no sigue ese formato)."""
    corto = (nombre_sesion or '').split(' - ')[0].strip()
    if corto.lower().startswith('dia '):
        return 'Día ' + corto[4:].strip()
    return corto


def _anotar_semana_cerrada(cliente, decision, fecha_hoy):
    try:
        nota = _nota_semana_cerrada(cliente, fecha_hoy)
    except Exception:
        logger.exception('obtener_sesion_recomendada_hoy: nota de semana cerrada')
        nota = None
    if nota:
        # Campo propio: _aplicar_contexto reescribe 'mensaje' según la causa.
        decision['nota_semana'] = nota


def obtener_sesion_recomendada_hoy(cliente, fecha_hoy=None, physical_snapshot=None):
    """
    Returns the recommended session for today as a dict:
        tipo:              'pendiente' | 'programada_hoy' | 'descanso'
        estado:            'entrenar' | 'descanso'
        sesion_programada: SesionProgramada | None
        entrenamiento:     dict (PlanificadorHelms output) | None
        mensaje:           str

    Priority: pending sessions (oldest first after reconciliation) → today's plan → rest.
    The live DB query for the pending session is NOT cached, so actions (completing
    a session, pressing "skip") are reflected immediately.
    """
    fecha_hoy = fecha_hoy or timezone.localdate()

    sincronizar_pendientes_recientes(cliente, fecha_hoy)

    # Live query — not cached. Respects pospuesta_hasta so "no puedo hoy" is instant.
    # Paso 3: la siguiente sesión de la cola de la semana (si hay una atrasada).
    pendiente = None
    try:
        siguiente = _siguiente_de_cola(cliente, fecha_hoy)
    except Exception:
        logger.exception('obtener_sesion_recomendada_hoy: error calculando la cola semanal')
        siguiente = None
    if siguiente is not None and siguiente.get('sp') is not None:
        pendiente = siguiente['sp']
    elif siguiente is not None:
        pendiente, _ = SesionProgramada.objects.get_or_create(
            cliente=cliente,
            fecha_prevista=siguiente['fecha'],
            defaults={
                'estado': SesionProgramada.ESTADO_PENDIENTE,
                'prioridad': inferir_prioridad_sesion(siguiente['entrenamiento']) or SesionProgramada.PRIORIDAD_ALTA,
                'nombre_sesion': siguiente['nombre'],
                'bloque_nombre': siguiente['entrenamiento'].get('bloque', '') or '',
                'dia_numero': siguiente['entrenamiento'].get('dia'),
                'motivo_estado': 'Sesión prevista no completada.',
            },
        )
        if pendiente.estado != SesionProgramada.ESTADO_PENDIENTE:
            pendiente.estado = SesionProgramada.ESTADO_PENDIENTE
            pendiente.motivo_estado = 'Sesión prevista no completada.'
            pendiente.save(update_fields=['estado', 'motivo_estado', 'actualizada_en'])

    if pendiente:
        try:
            planificador = _build_planificador(cliente)
            entrenamiento = _normalizar_entrenamiento(
                planificador.generar_entrenamiento_para_fecha(pendiente.fecha_prevista)
            )
            # Phase 9.2: apply contextual progression brake
            # Pending sessions from esencial mode don't auto-progress
            try:
                from entrenos.services.progresion_contextual_service import (
                    evaluar_permiso_progresion, aplicar_freno_contextual, aplicar_freno_lesion,
                    construir_motivo_final,
                )
                permiso = evaluar_permiso_progresion(cliente, fecha_hoy)
                entrenamiento = aplicar_freno_contextual(
                    cliente, entrenamiento, permiso,
                    modo_reducido=getattr(pendiente, 'modo_reducido_origen', False),
                )
                entrenamiento = aplicar_freno_lesion(cliente, entrenamiento)  # Phase 28.1
                # Phase Gym 1.1: adjust motivo_peso to reflect actual decision after frenos
                if entrenamiento and entrenamiento.get('ejercicios'):
                    entrenamiento['ejercicios'] = [
                        construir_motivo_final(ej, cliente)
                        for ej in entrenamiento['ejercicios']
                    ]
            except Exception:
                logger.warning('obtener_sesion_recomendada_hoy: freno contextual falló, sin efecto')
        except Exception:
            logger.exception('obtener_sesion_recomendada_hoy: error reconstruyendo pendiente')
            entrenamiento = None

        dias_atras = (fecha_hoy - pendiente.fecha_prevista).days
        if pendiente.pospuesta_hasta == fecha_hoy:
            if dias_atras == 1:
                origen_tiempo = 'prevista originalmente ayer'
            elif dias_atras <= 3:
                origen_tiempo = f'prevista hace {dias_atras} días'
            else:
                origen_tiempo = (
                    f'prevista originalmente el '
                    f'{pendiente.fecha_prevista.strftime("%-d de %B")}'
                )
            contexto_tiempo = f'Reubicada para hoy ({origen_tiempo}).'
        elif dias_atras == 1:
            contexto_tiempo = 'Quedó pendiente ayer.'
        elif dias_atras <= 3:
            contexto_tiempo = f'Quedó pendiente hace {dias_atras} días.'
        else:
            contexto_tiempo = f'Quedó pendiente el {pendiente.fecha_prevista.strftime("%-d de %B")}.'

        decision_base = {
            'tipo': 'pendiente',
            'estado': 'entrenar',
            'sesion_programada': pendiente,
            'entrenamiento': entrenamiento,
            'mensaje': f'{contexto_tiempo} Sigue siendo la siguiente pieza útil del plan.',
            'nota_semana': None,
            # Datos planos para explicar la cola (regla 3: el porqué con el dato).
            'cola': {
                'dia': _etiqueta_dia(pendiente.nombre_sesion),
                'fecha_prevista': pendiente.fecha_prevista.isoformat(),
            },
            'causa_principal': None,
            'modo_reducido': False,
            'distribucion_aviso': None,
        }
        _anotar_semana_cerrada(cliente, decision_base, fecha_hoy)
        contexto = _obtener_contexto_fisico(
            cliente,
            fecha_hoy,
            physical_snapshot=physical_snapshot,
        )
        contexto['_cliente'] = cliente  # for injury-session conflict check in _aplicar_contexto
        decision = _aplicar_contexto(decision_base, contexto, fecha_hoy)
        decision = _aplicar_efecto_distribucion(cliente, decision, fecha_hoy)
        decision = _aplicar_preferencia_activa(cliente, decision, fecha_hoy)
        decision = _aplicar_aviso_lesion(cliente, decision, fecha_hoy)
        return _devolver_con_traza(cliente, decision, fecha_hoy)

    # Phase 52 — Si el usuario pospuso explícitamente hoy, no generar nueva sesión
    from django.db.models import Q as _Q52
    hoy_pospuesto = SesionProgramada.objects.filter(
        cliente=cliente,
        fecha_prevista=fecha_hoy,
        estado=SesionProgramada.ESTADO_PENDIENTE,
        pospuesta_hasta__gt=fecha_hoy,
    ).exists()
    if hoy_pospuesto:
        decision = {
            'tipo': 'descanso',
            'estado': 'descanso',
            'sesion_programada': None,
            'entrenamiento': None,
            'mensaje': 'La sesión está guardada para mañana. Hoy descansas.',
            'causa_principal': 'pospuesto_usuario',
            'modo_reducido': False,
            'distribucion_aviso': None,
        }
        return _devolver_con_traza(cliente, decision, fecha_hoy)

    try:
        planificador = _build_planificador(cliente)
        entrenamiento_hoy = _normalizar_entrenamiento(
            planificador.generar_entrenamiento_para_fecha(fecha_hoy)
        )
        # Phase 9.2: apply contextual progression brake to today's session too
        try:
            from entrenos.services.progresion_contextual_service import (
                evaluar_permiso_progresion, aplicar_freno_contextual, aplicar_freno_lesion,
                construir_motivo_final,
            )
            permiso = evaluar_permiso_progresion(cliente, fecha_hoy)
            entrenamiento_hoy = aplicar_freno_contextual(cliente, entrenamiento_hoy, permiso)
            entrenamiento_hoy = aplicar_freno_lesion(cliente, entrenamiento_hoy)  # Phase 28.1
            # Phase Gym 1.1: adjust motivo_peso to reflect actual decision after frenos
            if entrenamiento_hoy and entrenamiento_hoy.get('ejercicios'):
                entrenamiento_hoy['ejercicios'] = [
                    construir_motivo_final(ej, cliente)
                    for ej in entrenamiento_hoy['ejercicios']
                ]
        except Exception:
            logger.warning('obtener_sesion_recomendada_hoy: freno contextual falló para sesión de hoy')
    except Exception:
        logger.exception('obtener_sesion_recomendada_hoy: error generando sesión de hoy')
        entrenamiento_hoy = None

    if _es_descanso(entrenamiento_hoy):
        decision = {
            'tipo': 'descanso',
            'estado': 'descanso',
            'sesion_programada': None,
            'entrenamiento': entrenamiento_hoy,
            'mensaje': 'Hoy el plan marca descanso.',
            'causa_principal': 'descanso_planificado',
            'modo_reducido': False,
        }
        return _devolver_con_traza(cliente, decision, fecha_hoy)

    decision_base = {
        'tipo': 'programada_hoy',
        'estado': 'entrenar',
        'sesion_programada': None,
        'entrenamiento': entrenamiento_hoy,
        'mensaje': 'Esta es la sesión prevista para hoy.',
        'nota_semana': None,
        'causa_principal': None,
        'modo_reducido': False,
        'distribucion_aviso': None,
    }
    _anotar_semana_cerrada(cliente, decision_base, fecha_hoy)
    contexto = _obtener_contexto_fisico(
        cliente,
        fecha_hoy,
        physical_snapshot=physical_snapshot,
    )
    contexto['_cliente'] = cliente  # for injury-session conflict check
    decision = _aplicar_contexto(decision_base, contexto, fecha_hoy)
    decision = _aplicar_efecto_distribucion(cliente, decision, fecha_hoy)
    decision = _aplicar_preferencia_activa(cliente, decision, fecha_hoy)
    decision = _aplicar_aviso_lesion(cliente, decision, fecha_hoy)
    return _devolver_con_traza(cliente, decision, fecha_hoy)
