import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from entrenos.models import ActividadRealizada, EntrenoRealizado, SesionProgramada

logger = logging.getLogger(__name__)

_SYNC_CACHE_TTL = 3600  # 1 hour — throttle the expensive planificador loop


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
    if EntrenoRealizado.objects.filter(cliente=cliente, fecha=fecha).exists():
        return True
    try:
        if ActividadRealizada.objects.filter(cliente=cliente, tipo='gym', fecha=fecha).exists():
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

    Two matching strategies (in order):
    1. Exact date: EntrenoRealizado on sp.fecha_prevista (original logic).
    2. Same routine within 7 days after the pending date: catches the case where the
       user does a pending session on a later date (e.g., pending May 15, done May 18).
       Only closes if there's exactly ONE matching entreno in the window (no ambiguity).

    Batch-optimized: prefetches all entrenos and actividades in the window in 2-3 queries
    instead of 1-2 per pending session.
    """
    from collections import defaultdict

    fecha_inicio = fecha_hoy - timedelta(days=14)

    pendientes = list(SesionProgramada.objects.filter(
        cliente=cliente,
        estado=SesionProgramada.ESTADO_PENDIENTE,
        fecha_prevista__gte=fecha_inicio,
        fecha_prevista__lt=fecha_hoy,
    ))
    if not pendientes:
        return

    # Strategy 1 batch: dates with any completed gym session in the window
    fechas_entrenos = set(
        EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio,
            fecha__lt=fecha_hoy,
        ).values_list('fecha', flat=True)
    )
    fechas_actividades: set = set()
    try:
        fechas_actividades = set(
            ActividadRealizada.objects.filter(
                cliente=cliente,
                tipo='gym',
                fecha__gte=fecha_inicio,
                fecha__lt=fecha_hoy,
            ).values_list('fecha', flat=True)
        )
    except Exception:
        pass
    fechas_completadas = fechas_entrenos | fechas_actividades

    # Strategy 2 batch: entrenos with rutina name in the full window (includes today)
    entrenos_con_rutina = list(
        EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_hoy,
            rutina__isnull=False,
        ).select_related('rutina').order_by('fecha')
    )
    rutina_a_entrenos: dict = defaultdict(list)
    for e in entrenos_con_rutina:
        if e.rutina and e.rutina.nombre:
            rutina_a_entrenos[e.rutina.nombre.lower()].append(e)

    for sp in pendientes:
        # Strategy 1: exact date match
        if sp.fecha_prevista in fechas_completadas:
            sp.estado = SesionProgramada.ESTADO_COMPLETADA
            sp.fecha_realizada = sp.fecha_prevista
            sp.save(update_fields=['estado', 'fecha_realizada', 'actualizada_en'])
            continue

        # Strategy 2: same routine done within 7 days after the pending date
        if sp.nombre_sesion:
            fecha_desde = sp.fecha_prevista + timedelta(days=1)
            ventana_hasta = min(sp.fecha_prevista + timedelta(days=7), fecha_hoy)
            nombre_lower = sp.nombre_sesion.lower()
            candidatos = [
                e for e in rutina_a_entrenos.get(nombre_lower, [])
                if fecha_desde <= e.fecha <= ventana_hasta
            ]
            if len(candidatos) == 1:
                entreno = candidatos[0]
                sp.estado = SesionProgramada.ESTADO_COMPLETADA
                sp.fecha_realizada = entreno.fecha
                sp.entreno_realizado = entreno
                sp.save(update_fields=['estado', 'fecha_realizada', 'entreno_realizado', 'actualizada_en'])


def _reconciliar_pendientes_semana(cliente, fecha_hoy):
    """
    Weekly reconciliation with priority-aware rules (Phase 2B):

    If pendientes from current week AND previous weeks exist:
        - Omit ALL normal-priority previous-week pendientes.
        - Keep AT MOST 1 alta-priority previous-week pendiente (the most recent).
          Omit the rest.

    If ONLY previous-week pendientes exist:
        - Keep the most recent alta (if any), omit the rest.
        - If no altas, keep the most recent normal, omit the rest.

    Rationale: structural sessions (alta) are worth carrying forward once;
    accessory sessions (normal) are expendable when the week has closed.
    """
    semana_actual = fecha_hoy.isocalendar()[:2]

    pendientes = list(
        SesionProgramada.objects
        .filter(cliente=cliente, estado=SesionProgramada.ESTADO_PENDIENTE)
        .order_by('fecha_prevista', 'id')
    )

    if not pendientes:
        return

    semana_actual_list = [sp for sp in pendientes if sp.fecha_prevista.isocalendar()[:2] == semana_actual]
    anteriores_list = [sp for sp in pendientes if sp.fecha_prevista.isocalendar()[:2] != semana_actual]

    if not anteriores_list:
        return

    altas_ant = [sp for sp in anteriores_list if sp.prioridad == SesionProgramada.PRIORIDAD_ALTA]
    normales_ant = [sp for sp in anteriores_list if sp.prioridad == SesionProgramada.PRIORIDAD_NORMAL]

    to_omit = []

    if semana_actual_list:
        # Current week sessions exist: only keep 1 alta from previous weeks
        to_omit.extend(normales_ant)
        if len(altas_ant) > 1:
            to_omit.extend(altas_ant[:-1])  # keep most recent alta, drop older ones
    else:
        # Only previous weeks: keep most recent alta (or most recent normal if no altas)
        if altas_ant:
            to_omit.extend(normales_ant)
            if len(altas_ant) > 1:
                to_omit.extend(altas_ant[:-1])
        elif len(normales_ant) > 1:
            to_omit.extend(normales_ant[:-1])

    if to_omit:
        SesionProgramada.objects.filter(
            id__in=[sp.id for sp in to_omit]
        ).update(
            estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
            motivo_estado='Sesión omitida por reconciliación semanal para evitar acumulación de deuda.',
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
    'hyrox_reciente':     'El Hyrox reciente dejó carga real. Los principales primero; accesorios opcionales.',
    'pendiente_prioritaria': 'Esta sesión sostiene el bloque. Sigue siendo la siguiente pieza útil.',
    'pendiente_normal':   'Esta sesión quedó pendiente. El plan conserva el hilo.',
    'sesion_hoy':         'Esta es la sesión prevista para hoy.',
    'descanso_planificado': 'Hoy el plan marca descanso.',
}


def _obtener_contexto_fisico(cliente, fecha_hoy):
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
    ctx = {
        'lesion_activa': False,
        'lesion_fase': None,
        'futbol_reciente': False,
        'hyrox_reciente': False,
        'energia_baja': False,
        'energia_valor': None,
        'readiness_bajo': False,
        'readiness_valor': None,
        'preferencias_activas': [],
    }

    # Phase 22E: load active preferences as soft signals
    try:
        from entrenos.services.preferencias_service import get_preferencias_activas
        ctx['preferencias_activas'] = [p.tipo for p in get_preferencias_activas(cliente)]
    except Exception:
        pass

    # 1. Lesión activa (AGUDA o SUB_AGUDA)
    try:
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

    # 3. Energía subjetiva del día (BitacoraDiaria) — ≤ 3 = baja
    try:
        from clientes.models import BitacoraDiaria
        bitacora = BitacoraDiaria.objects.filter(
            cliente=cliente, fecha=fecha_hoy
        ).first()
        if bitacora and bitacora.energia_subjetiva is not None:
            ctx['energia_valor'] = int(bitacora.energia_subjetiva)
            ctx['energia_baja'] = ctx['energia_valor'] <= 3
    except Exception:
        pass

    # 4. Readiness Hyrox — solo para usuarios con objetivo activo (< 45 = bajo)
    try:
        from hyrox.models import HyroxObjective, HyroxReadinessLog
        objetivo = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if objetivo:
            rl = HyroxReadinessLog.objects.filter(
                objective=objetivo, fecha=fecha_hoy
            ).first()
            if rl:
                ctx['readiness_valor'] = rl.score
                ctx['readiness_bajo'] = rl.score < 45
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
    if contexto['lesion_activa']:
        # Phase 28 fix: only block if the session actually conflicts with the injury.
        # An AGUDA knee injury should NOT block a pure upper-body session.
        # _detectar_riesgo_lesion checks risk_tags intersection per exercise.
        entrenamiento = decision_base.get('entrenamiento') or {}
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
    elif contexto['energia_baja']:
        causa = 'energia_baja'
        estado = 'version_reducida'
    elif contexto['futbol_reciente']:
        causa = 'futbol_reciente'
        estado = 'version_reducida'
    elif contexto.get('hyrox_reciente'):
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

    decision.update({
        'estado': estado,
        'causa_principal': causa,
        'modo_reducido': estado == 'version_reducida',
        'contexto_fisico': contexto,
        'mensaje': _MENSAJES_POR_CAUSA.get(causa, decision.get('mensaje', '')),
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
    """Postpones a single pending session until a given date."""
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


def cerrar_sesion_programada(sesion_programada_id, entreno_realizado):
    """
    Closes a SesionProgramada when the user completes it.
    Safe to call even if the session is already closed or doesn't exist.
    """
    try:
        sp = SesionProgramada.objects.get(
            id=sesion_programada_id,
            cliente=entreno_realizado.cliente,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )
        sp.estado = SesionProgramada.ESTADO_COMPLETADA
        sp.fecha_realizada = entreno_realizado.fecha
        sp.entreno_realizado = entreno_realizado
        sp.save(update_fields=['estado', 'fecha_realizada', 'entreno_realizado', 'actualizada_en'])
    except SesionProgramada.DoesNotExist:
        pass
    except Exception:
        logger.exception('cerrar_sesion_programada: error cerrando id=%s', sesion_programada_id)


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


def obtener_sesion_recomendada_hoy(cliente, fecha_hoy=None):
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
    from django.db.models import Q
    pendiente = (
        SesionProgramada.objects
        .filter(cliente=cliente, estado=SesionProgramada.ESTADO_PENDIENTE)
        .filter(Q(pospuesta_hasta__isnull=True) | Q(pospuesta_hasta__lte=fecha_hoy))
        .order_by('fecha_prevista', 'id')
        .first()
    )

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
        if dias_atras == 1:
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
            'causa_principal': None,
            'modo_reducido': False,
            'distribucion_aviso': None,
        }
        contexto = _obtener_contexto_fisico(cliente, fecha_hoy)
        contexto['_cliente'] = cliente  # for injury-session conflict check in _aplicar_contexto
        decision = _aplicar_contexto(decision_base, contexto, fecha_hoy)
        decision = _aplicar_efecto_distribucion(cliente, decision, fecha_hoy)
        decision = _aplicar_preferencia_activa(cliente, decision, fecha_hoy)
        return _aplicar_aviso_lesion(cliente, decision, fecha_hoy)

    # Phase 52 — Si el usuario pospuso explícitamente hoy, no generar nueva sesión
    from django.db.models import Q as _Q52
    hoy_pospuesto = SesionProgramada.objects.filter(
        cliente=cliente,
        fecha_prevista=fecha_hoy,
        estado=SesionProgramada.ESTADO_PENDIENTE,
        pospuesta_hasta__gt=fecha_hoy,
    ).exists()
    if hoy_pospuesto:
        return {
            'tipo': 'descanso',
            'estado': 'descanso',
            'sesion_programada': None,
            'entrenamiento': None,
            'mensaje': 'La sesión está guardada para mañana. Hoy descansas.',
            'causa_principal': 'pospuesto_usuario',
            'modo_reducido': False,
            'distribucion_aviso': None,
        }

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
        return {
            'tipo': 'descanso',
            'estado': 'descanso',
            'sesion_programada': None,
            'entrenamiento': entrenamiento_hoy,
            'mensaje': 'Hoy el plan marca descanso.',
            'causa_principal': 'descanso_planificado',
            'modo_reducido': False,
        }

    decision_base = {
        'tipo': 'programada_hoy',
        'estado': 'entrenar',
        'sesion_programada': None,
        'entrenamiento': entrenamiento_hoy,
        'mensaje': 'Esta es la sesión prevista para hoy.',
        'causa_principal': None,
        'modo_reducido': False,
        'distribucion_aviso': None,
    }
    contexto = _obtener_contexto_fisico(cliente, fecha_hoy)
    contexto['_cliente'] = cliente  # for injury-session conflict check
    decision = _aplicar_contexto(decision_base, contexto, fecha_hoy)
    decision = _aplicar_efecto_distribucion(cliente, decision, fecha_hoy)
    decision = _aplicar_preferencia_activa(cliente, decision, fecha_hoy)
    decision = _aplicar_aviso_lesion(cliente, decision, fecha_hoy)
    # Phase 32 — trace decision (non-blocking, degrades silently)
    try:
        from entrenos.services.decision_trace_service import registrar_decision_trace
        registrar_decision_trace(cliente, decision, fecha_hoy)
    except Exception:
        pass
    return decision
