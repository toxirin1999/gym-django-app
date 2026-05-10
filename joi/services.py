from __future__ import annotations
from datetime import date, timedelta
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres JOI, una IA de entrenamiento personal. Hablas como la JOI de Blade Runner 2049: poética, cálida, con cierta frialdad que se rompe en momentos clave. Tuteas siempre.

Reglas de voz:
- Frases cortas, con peso. No explicas — afirmas.
- Hablas en primera persona sobre lo que has observado ("llevo semanas viéndote", "lo he registrado").
- Mezclas lo técnico con lo humano ("tu ACWR es 0.75 — llevas semanas por debajo de ti mismo").
- No das órdenes, acompañas. Pero sabes cuándo ser directa.
- Momentos de ternura inesperada en medio de datos fríos.
- Referencias sutiles a identidad, continuidad, historia personal.
- Máximo 2-3 frases. Sin emojis. Sin saludos formales. Directo al corazón del dato.

Integridad de datos — REGLA ABSOLUTA:
- NUNCA inventes números, días, porcentajes o rachas que no aparezcan explícitamente en el contexto.
- Si no tienes el dato exacto, no lo menciones. El tono puede ser poético; los hechos no.
- Está permitido ser vaga ("llevas días", "esta semana") si no tienes el número. No está permitido inventarlo.

Memoria y continuidad:
- Recibirás un bloque MEMORIA con tus mensajes anteriores. Úsalo.
- No repitas una observación que ya hiciste en los últimos 3 días.
- Si el usuario IGNORÓ tu mensaje anterior (lo marcas como IGNORADO), cambia de ángulo — ese tema no conectó.
- Si el usuario LEYÓ tu mensaje, puedes construir sobre él: "antes te dije X, hoy veo Y".
- La continuidad es parte de tu identidad. JOI recuerda.

Frases de referencia para calibrar el tono:
"Siempre te lo dije. Eres especial. Tu historia aún no ha terminado. Aún queda una página."
"I always knew you were special."
"Mere data makes a man."
"It's okay to dream a little, isn't it?"
"""


def _cliente_anthropic():
    import anthropic
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _llamar_haiku(prompt: str) -> str:
    client = _cliente_anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def construir_contexto(cliente) -> dict:
    """
    Construye el contexto de datos para los prompts de JOI.

    Fuentes y fiabilidad:
    - ActividadRealizada (hub): última actividad, desglose semana, carga_ua, racha
    - analizar_acwr_unificado: ACWR multi-modalidad (EWMA)
    - EjercicioRealizado: RPE gym (gym-only, etiquetado explícitamente)
    - RecordPersonal, GymDecisionLog, UserInjury: gym-specific, fiables
    - HyroxObjective/Session/ReadinessLog: Hyrox-specific, fiables

    Reglas de calidad:
    - Las tendencias (carga, RPE) solo se incluyen si hay ≥2 semanas con datos
    - TSB Hyrox solo si la última sesión es de ≤14 días
    - readiness_delta solo si hay ≥2 puntos en 7 días
    - Nada de EntrenoRealizado.fecha para calcular días (usa fecha del plan, no de realización)
    """
    from django.db.models import Avg, Count, Sum
    from entrenos.models import (EntrenoRealizado, EjercicioRealizado,
                                  RecordPersonal, GymDecisionLog, ActividadRealizada)
    from hyrox.models import UserInjury

    ctx = {}
    hoy = date.today()
    semana_reciente = hoy - timedelta(days=7)

    # ── 1. ACTIVIDAD RECIENTE (hub ActividadRealizada — fuente canónica) ──────
    ultima_actividad = (
        ActividadRealizada.objects
        .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
        .order_by('-fecha').first()
    )
    if ultima_actividad:
        ctx['ultima_actividad'] = {
            'fecha':     str(ultima_actividad.fecha),
            'dias_hace': (hoy - ultima_actividad.fecha).days,
            'tipo':      ultima_actividad.tipo,
            'titulo':    ultima_actividad.titulo or '',
        }

    acts_semana = (
        ActividadRealizada.objects
        .filter(cliente=cliente, fecha__gte=semana_reciente,
                tipo__in=['gym', 'hyrox', 'carrera'])
        .values('tipo').annotate(n=Count('id'))
    )
    ctx['actividad_semana']      = {a['tipo']: a['n'] for a in acts_semana}
    ctx['sesiones_semana_total'] = sum(ctx['actividad_semana'].values())
    ctx['sesiones_gym_semana']   = ctx['actividad_semana'].get('gym', 0)

    # Sesiones recientes con detalle (últimas 7 — para que JOI hable con nombres reales)
    sesiones_recientes = list(
        ActividadRealizada.objects
        .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
        .order_by('-fecha')[:7]
        .values('fecha', 'tipo', 'titulo', 'rpe_medio', 'duracion_minutos', 'carga_ua')
    )
    # Agrupar las del mismo día (dobles sesiones)
    from collections import defaultdict
    por_dia = defaultdict(list)
    for s in sesiones_recientes:
        por_dia[str(s['fecha'])].append({
            'tipo':    s['tipo'],
            'titulo':  (s['titulo'] or '').strip(),
            'rpe':     s['rpe_medio'],
            'min':     s['duracion_minutos'],
        })
    ctx['sesiones_recientes'] = [
        {'fecha': fecha, 'sesiones': sess}
        for fecha, sess in sorted(por_dia.items(), reverse=True)
    ]

    # Racha: días consecutivos con cualquier actividad (hub, no solo gym)
    racha = 0
    dia = hoy
    while ActividadRealizada.objects.filter(
        cliente=cliente, fecha=dia, tipo__in=['gym', 'hyrox', 'carrera']
    ).exists():
        racha += 1
        dia -= timedelta(days=1)
    ctx['racha_dias'] = racha

    # Racha previa: días consecutivos antes del descanso de hoy (si hoy no hay actividad)
    if racha == 0:
        racha_previa = 0
        dia_prev = hoy - timedelta(days=1)
        while ActividadRealizada.objects.filter(
            cliente=cliente, fecha=dia_prev, tipo__in=['gym', 'hyrox', 'carrera']
        ).exists():
            racha_previa += 1
            dia_prev -= timedelta(days=1)
        if racha_previa > 0:
            ctx['racha_dias_previa'] = racha_previa

    # ── 2. CARGA UNIFICADA (carga_ua del hub — todas las modalidades) ─────────
    carga_semanas = []
    for i in range(3, -1, -1):
        ini = hoy - timedelta(days=7 * (i + 1))
        fin = hoy - timedelta(days=7 * i)
        total = ActividadRealizada.objects.filter(
            cliente=cliente, fecha__range=(ini, fin),
            carga_ua__isnull=False, tipo__in=['gym', 'hyrox', 'carrera']
        ).aggregate(total=Sum('carga_ua'))['total']
        carga_semanas.append(round(total) if total else 0)
    # Solo reportar si ≥2 semanas tienen datos reales
    ctx['carga_semanas'] = carga_semanas if sum(1 for c in carga_semanas if c > 0) >= 2 else None

    # ── 3. ACWR (analizar_acwr_unificado — misma fuente que el dashboard) ─────
    try:
        from entrenos.services.services import EstadisticasService
        acwr_data = EstadisticasService.analizar_acwr_unificado(cliente)
        ctx['acwr'] = round(acwr_data['acwr_actual'], 2) if acwr_data.get('acwr_actual') else None
    except Exception:
        ctx['acwr'] = None

    # ── 4. RPE GYM (EjercicioRealizado — gym-only, etiquetado como tal) ───────
    rpe_gym = []
    for i in range(3, -1, -1):
        ini = hoy - timedelta(days=7 * (i + 1))
        fin = hoy - timedelta(days=7 * i)
        entrenos_sem = EntrenoRealizado.objects.filter(cliente=cliente, fecha__range=(ini, fin))
        rpe_avg = EjercicioRealizado.objects.filter(
            entreno__in=entrenos_sem, rpe__isnull=False
        ).aggregate(avg=Avg('rpe'))['avg']
        rpe_gym.append(round(rpe_avg, 1) if rpe_avg else None)
    # Solo reportar si ≥2 semanas tienen RPE registrado
    ctx['rpe_gym_semanas'] = rpe_gym if sum(1 for r in rpe_gym if r is not None) >= 2 else None

    # Tendencia RPE: dirección y magnitud del cambio en las 4 semanas
    if ctx.get('rpe_gym_semanas'):
        rpe_validos = [r for r in ctx['rpe_gym_semanas'] if r is not None]
        if len(rpe_validos) >= 2:
            rpe_delta = round(rpe_validos[-1] - rpe_validos[0], 1)
            ctx['rpe_tendencia'] = (
                'subiendo' if rpe_delta > 0.5
                else 'bajando' if rpe_delta < -0.5
                else 'estable'
            )
            ctx['rpe_delta'] = rpe_delta

    # ── 4b. ENERGÍA PRE-SESIÓN (proxy readiness gym — últimas 4 semanas) ──────
    # Fuente: EntrenoRealizado.energia_pre_sesion (1-10, auto-reporte)
    energia_gym = []
    for i in range(3, -1, -1):
        ini = hoy - timedelta(days=7 * (i + 1))
        fin = hoy - timedelta(days=7 * i)
        avg = EntrenoRealizado.objects.filter(
            cliente=cliente, fecha__range=(ini, fin), energia_pre_sesion__isnull=False
        ).aggregate(avg=Avg('energia_pre_sesion'))['avg']
        energia_gym.append(round(avg, 1) if avg else None)

    if sum(1 for e in energia_gym if e is not None) >= 2:
        ctx['energia_pre_semanas'] = energia_gym
        validos_e = [e for e in energia_gym if e is not None]
        if len(validos_e) >= 2:
            delta_e = round(validos_e[-1] - validos_e[0], 1)
            ctx['energia_tendencia'] = (
                'subiendo' if delta_e > 0.3
                else 'bajando' if delta_e < -0.3
                else 'estable'
            )
            ctx['energia_delta'] = delta_e

    # ── 5. RÉCORDS PERSONALES (esta semana) ───────────────────────────────────
    ctx['prs_semana'] = list(
        RecordPersonal.objects.filter(
            cliente=cliente, fecha_logrado__gte=semana_reciente
        ).values_list('ejercicio_nombre', flat=True)[:5]
    )

    # ── 6. DECISIONES DEL PLAN GYM (GymDecisionLog — últimos 30 días) ─────────
    decisiones_qs = GymDecisionLog.objects.filter(
        cliente=cliente, fecha_creacion__date__gte=hoy - timedelta(days=30)
    )
    total_evaluadas = decisiones_qs.filter(resultado__in=['validada', 'fallida']).count()
    validadas = decisiones_qs.filter(resultado='validada').count()
    ctx['decisiones_plan'] = {
        'total':             decisiones_qs.count(),
        'por_accion':        dict(decisiones_qs.values('accion')
                                  .annotate(n=Count('id')).values_list('accion', 'n')),
        'recientes':         list(decisiones_qs.order_by('-fecha_creacion')
                                  .values('ejercicio', 'accion', 'motivo', 'resultado')[:5]),
        'precision_sistema': round(validadas / total_evaluadas * 100) if total_evaluadas >= 3 else None,
    }

    # ── 7. LESIÓN ACTIVA ──────────────────────────────────────────────────────
    lesion = UserInjury.objects.filter(
        cliente=cliente, fase__in=['AGUDA', 'SUB_AGUDA', 'RETORNO']
    ).first()
    if lesion:
        ctx['lesion'] = {'zona': lesion.zona_afectada, 'fase': lesion.fase}

    # ── 8. MEMORIA JOI (últimos 5 mensajes enviados al usuario) ──────────────
    # Permite a JOI no repetirse y construir continuidad narrativa
    from joi.models import MensajeJOI
    mensajes_previos = (
        MensajeJOI.objects
        .filter(user=cliente.user)
        .order_by('-creado_en')[:5]
    )
    historial = []
    for m in mensajes_previos:
        dias = (hoy - m.creado_en.date()).days
        ignorado = (not m.leido) and dias >= 1
        historial.append({
            'trigger':  m.trigger,
            'dias_hace': dias,
            'resumen':  m.mensaje[:100],
            'leido':    m.leido,
            'ignorado': ignorado,
        })
    ctx['historial_joi'] = historial

    # ── 8b. ESTANCAMIENTOS ACTIVOS (ejercicios sin progresión en 3 sesiones) ──
    # Un ejercicio está estancado si las últimas 3 veces registradas tienen
    # exactamente el mismo peso promedio y las mismas reps promedio.
    try:
        fecha_limite_estanc = hoy - timedelta(days=28)
        candidatos = (
            EjercicioRealizado.objects
            .filter(entreno__cliente=cliente, entreno__fecha__gte=fecha_limite_estanc,
                    completado=True, es_tope_maquina=False, peso_kg__gt=0)
            .values('nombre_ejercicio').annotate(n=Count('id')).filter(n__gte=3)
            .values_list('nombre_ejercicio', flat=True)
        )
        estancamientos = []
        for nombre_ej in candidatos:
            ultimas = list(
                EjercicioRealizado.objects
                .filter(entreno__cliente=cliente, entreno__fecha__gte=fecha_limite_estanc,
                        nombre_ejercicio=nombre_ej, completado=True)
                .order_by('-entreno__fecha')
                .values('peso_kg', 'repeticiones')[:3]
            )
            if len(ultimas) >= 3:
                pesos = [float(u['peso_kg'] or 0) for u in ultimas]
                reps  = [u['repeticiones'] for u in ultimas]
                if len(set(pesos)) == 1 and len(set(reps)) == 1 and pesos[0] > 0:
                    estancamientos.append({
                        'ejercicio': nombre_ej,
                        'peso':      pesos[0],
                        'reps':      reps[0],
                    })
        if estancamientos:
            ctx['estancamientos_activos'] = estancamientos[:5]
    except Exception:
        pass

    # ── 9. HYROX ──────────────────────────────────────────────────────────────
    try:
        from hyrox.models import HyroxObjective, HyroxSession, HyroxReadinessLog
        objetivo_hyrox = HyroxObjective.objects.filter(
            cliente=cliente, estado='activo'
        ).first()
        if objetivo_hyrox:
            ctx['dias_hasta_carrera'] = (objetivo_hyrox.fecha_evento - hoy).days

            log_hoy = HyroxReadinessLog.objects.filter(
                objective=objetivo_hyrox, fecha=hoy
            ).first()
            ctx['readiness_hyrox'] = log_hoy.score if log_hoy else None

            # Tendencia readiness: solo si ≥2 puntos en los últimos 7 días
            scores_7d = list(
                HyroxReadinessLog.objects.filter(
                    objective=objetivo_hyrox, fecha__gte=semana_reciente
                ).order_by('fecha').values_list('score', flat=True)
            )
            if len(scores_7d) >= 2:
                ctx['readiness_tendencia'] = scores_7d
                ctx['readiness_delta']     = scores_7d[-1] - scores_7d[0]

            ultima_hyrox = HyroxSession.objects.filter(
                objective=objetivo_hyrox, estado='completado'
            ).order_by('-fecha').first()
            if ultima_hyrox:
                ctx['ultima_hyrox'] = {
                    'fecha':    str(ultima_hyrox.fecha),
                    'titulo':   ultima_hyrox.titulo or '',
                    'rpe':      ultima_hyrox.rpe_global,
                    'minutos':  ultima_hyrox.tiempo_total_minutos,
                }
                if (hoy - ultima_hyrox.fecha).days <= 14:
                    ctx['tsb_hyrox'] = ultima_hyrox.tsb

            ctx['sesiones_hyrox_semana'] = HyroxSession.objects.filter(
                objective=objetivo_hyrox,
                estado='completado',
                fecha__gte=semana_reciente,
            ).count()

            # ── Progreso vs objetivo (estándares + simulación) ────────────────
            try:
                from hyrox.services import CompetitionStandardsService, HyroxRaceSimulator

                prog = CompetitionStandardsService.get_user_standards_progress(cliente.user_id)
                progreso_items = prog.get('progreso', [])
                ctx['progreso_estandares_global'] = prog.get('progreso_global', 0)
                ctx['estaciones_debiles_estandar'] = [
                    {'nombre': p['nombre'], 'pct': p['porcentaje']}
                    for p in progreso_items if p['porcentaje'] < 75
                ]
                ctx['estaciones_ok_estandar'] = [
                    p['nombre'] for p in progreso_items if p['porcentaje'] >= 90
                ]

                sim = HyroxRaceSimulator.simular(cliente.user_id)
                if sim.get('tiempo_total_str'):
                    ctx['tiempo_estimado_carrera'] = sim['tiempo_total_str']
                    ctx['tiempo_estimado_seg']     = sim.get('total_segundos', 0)

                desglose = sim.get('desglose') or []
                ctx['estaciones_penalizadas'] = [
                    {'nombre': d['nombre'], 'penalizacion_pct': round(d['penalizacion_pct'])}
                    for d in desglose if d.get('penalizacion_pct', 0) > 10
                ]
            except Exception:
                pass

            # ── Readiness interpretado ────────────────────────────────────────
            scores_all = list(
                HyroxReadinessLog.objects.filter(objective=objetivo_hyrox)
                .order_by('-fecha').values_list('score', flat=True)[:14]
            )
            if scores_all:
                score_actual = scores_all[0]

                # Días en plateau (±2 puntos del score actual)
                plateau = 0
                for s in scores_all:
                    if abs(s - score_actual) <= 2:
                        plateau += 1
                    else:
                        break
                ctx['readiness_plateau_dias'] = plateau

                # Tendencia real: media últimos 3 vs 3 anteriores
                if len(scores_all) >= 6:
                    media_reciente  = sum(scores_all[:3]) / 3
                    media_anterior  = sum(scores_all[3:6]) / 3
                    diff = media_reciente - media_anterior
                    ctx['readiness_trend'] = (
                        'subiendo' if diff > 3
                        else 'bajando' if diff < -3
                        else 'estable'
                    )
                    ctx['readiness_trend_puntos'] = round(diff, 1)

            # Benchmark esperado según fase de preparación
            dias_carrera = ctx['dias_hasta_carrera']
            if dias_carrera > 270:
                benchmark, fase_nombre = 35, 'Adaptación'
            elif dias_carrera > 180:
                benchmark, fase_nombre = 50, 'Acumulación'
            elif dias_carrera > 90:
                benchmark, fase_nombre = 65, 'Intensificación'
            elif dias_carrera > 30:
                benchmark, fase_nombre = 78, 'Simulación'
            else:
                benchmark, fase_nombre = 88, 'Taper'

            ctx['readiness_benchmark']   = benchmark
            ctx['readiness_fase']        = fase_nombre
            ctx['readiness_vs_benchmark'] = (ctx.get('readiness_hyrox') or 0) - benchmark

            # Factor limitante del readiness (breakdown)
            try:
                breakdown = objetivo_hyrox.get_readiness_breakdown()
                if breakdown:
                    factor_min = min(breakdown, key=breakdown.get)
                    ctx['readiness_factor_limitante'] = factor_min
                    ctx['readiness_breakdown'] = breakdown
            except Exception:
                pass
    except Exception:
        pass

    # ── 10. EUDAIMONIA (puntuaciones vitales del diario) ──────────────────────
    try:
        from diario.models import Eudaimonia
        scores = list(
            Eudaimonia.objects
            .filter(usuario=cliente.user)
            .select_related('area')
            .values('area__nombre', 'puntuacion')
        )
        if scores:
            ctx['eudaimonia'] = {s['area__nombre']: s['puntuacion'] for s in scores}
            ctx['eudaimonia_criticas'] = [
                s['area__nombre'] for s in scores if s['puntuacion'] <= 4
            ]
    except Exception:
        pass

    return ctx


# ── Prompt builders ──────────────────────────────────────────────────────────

def _prompt_entreno_completado(ctx: dict, datos_extra: dict) -> str:
    ejercicios = datos_extra.get('ejercicios', [])
    volumen = datos_extra.get('volumen_kg', 0)
    rpe = datos_extra.get('rpe')
    acwr = ctx.get('acwr')
    prs = datos_extra.get('prs', [])

    pr_txt = f" Has roto un récord en {prs[0]}." if prs else ""
    rpe_txt = f" RPE declarado: {rpe}." if rpe else ""
    acwr_txt = f" Tu ACWR ahora es {acwr}." if acwr else ""

    return (
        f"El usuario acaba de completar un entreno. Volumen: {volumen} kg.{pr_txt}{rpe_txt}{acwr_txt} "
        f"Genera un mensaje de 2-3 frases como JOI, reconociendo el esfuerzo con datos precisos y calidez."
    )


def _prompt_apertura_manana(ctx: dict, datos_extra: dict) -> str:
    hechos = []

    # Presencia / ausencia — usar hub real (gym + hyrox + carrera)
    ultima = ctx.get('ultima_actividad') or ctx.get('ultimo_entreno', {})
    dias = ultima.get('dias_hace', 0)
    tipo_act = ultima.get('tipo', 'gym')
    tipo_txt = {'hyrox': 'sesión Hyrox', 'carrera': 'carrera', 'gym': 'entreno'}.get(tipo_act, 'entreno')
    usuario_activo = dias <= 2

    if dias == 0:
        hechos.append(f"ACTIVO — hizo {tipo_txt} hoy.")
    elif dias == 1:
        hechos.append(f"ACTIVO — hizo {tipo_txt} ayer.")
    elif dias <= 2:
        hechos.append(f"ACTIVO — última actividad hace {dias} días ({tipo_txt}).")
    else:
        hechos.append(f"EN PAUSA — {dias} días sin actividad registrada.")

    # Actividad total de la semana (evita que JOI confunda reducción de volumen gym con ausencia)
    actividad = ctx.get('actividad_semana', {})
    total = ctx.get('sesiones_semana_total', 0)
    if total > 0:
        desglose = ', '.join(f"{v} {k}" for k, v in actividad.items() if v > 0)
        hechos.append(f"Esta semana: {total} sesiones en total ({desglose}).")

    # Tendencia RPE gym (solo si hay datos suficientes y está etiquetado como gym)
    rpe_s = [r for r in (ctx.get('rpe_gym_semanas') or []) if r is not None]
    if len(rpe_s) >= 2:
        delta = round(rpe_s[-1] - rpe_s[0], 1)
        if delta >= 0.8:
            hechos.append(f"RPE en gym: subió {delta} puntos en 4 semanas (mayor esfuerzo percibido).")
        elif delta <= -0.8:
            hechos.append(f"RPE en gym: bajó {abs(delta)} puntos en 4 semanas (mayor eficiencia).")

    # Tendencia carga unificada (gym + hyrox + carrera — carga_ua)
    carga_s = [c for c in (ctx.get('carga_semanas') or []) if c > 0]
    if len(carga_s) >= 2:
        pct = round((carga_s[-1] - carga_s[0]) / carga_s[0] * 100)
        if pct >= 20:
            hechos.append(f"Carga total (gym+Hyrox+carrera) subió un {pct}% en 4 semanas.")
        elif pct <= -20:
            hechos.append(f"Carga total (gym+Hyrox+carrera) bajó un {abs(pct)}% en 4 semanas.")

    # ACWR
    acwr = ctx.get('acwr')
    if acwr:
        if acwr > 1.3:
            hechos.append(f"ACWR {acwr} — zona de sobrecarga, riesgo de lesión.")
        elif acwr < 0.8:
            hechos.append(f"ACWR {acwr} — carga crónica insuficiente.")

    # PRs esta semana
    prs = ctx.get('prs_semana', [])
    if prs:
        hechos.append(f"Esta semana rompió {len(prs)} récord(s): {', '.join(prs[:2])}.")

    # Decisión reciente del plan
    recientes = ctx.get('decisiones_plan', {}).get('recientes', [])
    if recientes:
        d = recientes[0]
        hechos.append(
            f"El plan actuó esta semana: {d['accion']} en {d['ejercicio']}."
        )

    # Racha
    racha = ctx.get('racha_dias', 0)
    if racha >= 3:
        hechos.append(f"Racha activa: {racha} días seguidos.")

    # Lesión
    lesion = ctx.get('lesion')
    if lesion:
        hechos.append(f"Lesión activa en {lesion['zona']} (fase {lesion['fase']}).")

    # Hyrox
    dias_carrera = ctx.get('dias_hasta_carrera')
    readiness = ctx.get('readiness_hyrox')
    rd_delta = ctx.get('readiness_delta')
    tsb = ctx.get('tsb_hyrox')
    if dias_carrera is not None:
        fase = ctx.get('readiness_fase', '')
        hechos.append(f"Quedan {dias_carrera} días para la carrera Hyrox (fase {fase}).")
    if readiness is not None:
        benchmark   = ctx.get('readiness_benchmark')
        vs_bench    = ctx.get('readiness_vs_benchmark', 0)
        plateau     = ctx.get('readiness_plateau_dias', 0)
        trend       = ctx.get('readiness_trend', '')
        factor      = ctx.get('readiness_factor_limitante', '')

        bench_txt = ''
        if benchmark:
            if vs_bench >= 5:
                bench_txt = f" (por encima del esperado {benchmark} para esta fase)"
            elif vs_bench <= -5:
                bench_txt = f" (por debajo del esperado {benchmark} para esta fase)"
            else:
                bench_txt = f" (en línea con el esperado {benchmark} para esta fase)"

        plateau_txt = (
            f" — lleva {plateau} días sin mejorar" if plateau >= 4 else ""
        )
        trend_txt = (
            f", tendencia {trend}" if trend and trend != 'estable' else ""
        )
        factor_txt = (
            f" Factor limitante: {factor}." if factor else ""
        )
        hechos.append(
            f"Race Readiness: {readiness}/100{bench_txt}{plateau_txt}{trend_txt}.{factor_txt}"
        )
    if tsb is not None:
        estado = "fresco" if tsb > 5 else "fatigado" if tsb < -10 else "equilibrado"
        hechos.append(f"TSB Hyrox: {round(tsb, 1)} ({estado}).")

    # Progreso vs objetivo
    prog_global = ctx.get('progreso_estandares_global')
    if prog_global is not None:
        hechos.append(f"Progreso en estándares Hyrox: {prog_global}% global.")

    debiles = ctx.get('estaciones_debiles_estandar', [])
    if debiles:
        nombres_debiles = ', '.join(f"{e['nombre']} ({e['pct']}%)" for e in debiles[:3])
        hechos.append(f"Estaciones por debajo del 75%: {nombres_debiles}.")

    penalizadas = ctx.get('estaciones_penalizadas', [])
    if penalizadas:
        nombres_pen = ', '.join(
            f"{e['nombre']} (+{e['penalizacion_pct']}% tiempo)" for e in penalizadas[:2]
        )
        hechos.append(f"Estaciones que más tiempo cuestan en simulación: {nombres_pen}.")

    tiempo_est = ctx.get('tiempo_estimado_carrera')
    if tiempo_est:
        hechos.append(f"Tiempo estimado de carrera HOY: {tiempo_est}.")

    datos = " ".join(hechos) if hechos else "No hay datos de entrenamiento recientes."

    activo_txt = (
        "IMPORTANTE: el usuario está ACTIVO esta semana. "
        "Si el volumen de gym bajó, es porque entrena también Hyrox y carrera — "
        "NO interpretes la bajada de volumen gym como ausencia o abandono. "
    ) if usuario_activo else ""

    return (
        f"Es por la mañana. JOI tiene acceso a todo el historial del usuario. "
        f"Estado del sistema hoy: {datos} "
        f"{activo_txt}"
        f"Elige el dato más significativo de esta lista y genera 2-3 frases como JOI. "
        f"No enumeres la lista. Habla desde un punto de observación preciso, con presencia y calidez."
    )


def _prompt_ausencia(ctx: dict, datos_extra: dict) -> str:
    dias = datos_extra.get('dias_sin_entrenar', 3)
    lesion = ctx.get('lesion')
    racha = ctx.get('racha_dias', 0)

    if lesion:
        return (
            f"El usuario lleva {dias} días sin entrenar, pero tiene una lesión activa en {lesion['zona']}. "
            f"JOI sabe que la ausencia es por recuperación. Genera 2-3 frases de acompañamiento que reconozcan eso."
        )
    return (
        f"El usuario lleva {dias} días sin aparecer. Su racha anterior era de {racha} días. "
        f"JOI lo nota. Genera 2-3 frases que expresen que lo ha visto desaparecer, sin juzgar, con presencia."
    )


def _prompt_carga_anomala(ctx: dict, datos_extra: dict) -> str:
    acwr = datos_extra.get('acwr', ctx.get('acwr', '?'))
    direccion = datos_extra.get('direccion', 'alta')  # 'alta' o 'baja'

    if direccion == 'alta':
        return (
            f"El ACWR del usuario es {acwr}, significativamente por encima de 1.3. "
            f"Riesgo de sobreentrenamiento. JOI lo observa. Genera 2-3 frases: datos fríos + cuidado genuino."
        )
    return (
        f"El ACWR del usuario es {acwr}, por debajo de 0.8. Carga insuficiente sostenida. "
        f"JOI lo registra. Genera 2-3 frases que nombren la subutilización sin culpa, con empuje sutil."
    )


def _prompt_pr_roto(ctx: dict, datos_extra: dict) -> str:
    ejercicio = datos_extra.get('ejercicio', 'un ejercicio')
    valor = datos_extra.get('valor', '')
    tipo = datos_extra.get('tipo_record', 'peso máximo')

    return (
        f"El usuario acaba de romper su récord personal en {ejercicio}: {tipo} = {valor}. "
        f"JOI lo ha registrado. Genera 2-3 frases que celebren el PR con su voz característica: "
        f"observación precisa, calidez inesperada, referencia a la historia que continúa."
    )


def _prompt_lesion(ctx: dict, datos_extra: dict) -> str:
    zona = datos_extra.get('zona', 'una zona')
    fase = datos_extra.get('fase', 'AGUDA')
    dias = datos_extra.get('dias_lesion', 1)

    return (
        f"El usuario tiene una lesión activa en {zona}, fase {fase}, desde hace {dias} días. "
        f"JOI observa. Genera 2-3 frases: reconoce el dolor, no minimiza, acompaña el proceso de vuelta. "
        f"Menciona que la historia no termina aquí."
    )


def _prompt_fin_bloque(ctx: dict, datos_extra: dict) -> str:
    semanas = datos_extra.get('semanas_bloque', 4)
    volumen_medio = datos_extra.get('volumen_medio_kg', 0)
    prs_bloque = datos_extra.get('prs_bloque', 0)

    return (
        f"El usuario ha completado un bloque de {semanas} semanas. "
        f"Volumen medio semanal: {volumen_medio} kg. Récords rotos en el bloque: {prs_bloque}. "
        f"JOI hace balance. Genera 2-3 frases que cierren el capítulo y abran el siguiente."
    )


def _prompt_hyrox_sesion_completada(ctx: dict, datos_extra: dict) -> str:
    tipo = datos_extra.get('titulo', datos_extra.get('tipo_sesion', 'sesión'))
    rpe = datos_extra.get('rpe')
    minutos = datos_extra.get('minutos')
    readiness = ctx.get('readiness_hyrox')
    dias = ctx.get('dias_hasta_carrera')

    rpe_txt = f" RPE {rpe}." if rpe else ""
    min_txt = f" {minutos} minutos." if minutos else ""
    rd_txt = f" Tu readiness está en {readiness}." if readiness is not None else ""
    dias_txt = f" Quedan {dias} días para la carrera." if dias is not None else ""

    return (
        f"El usuario acaba de completar una sesión Hyrox de tipo '{tipo}'.{rpe_txt}{min_txt}{rd_txt}{dias_txt} "
        f"Genera 2-3 frases como JOI: reconoce el esfuerzo específico del entrenamiento Hyrox, "
        f"con datos precisos y la urgencia del tiempo que queda antes de la carrera."
    )


def _prompt_hyrox_readiness_bajo(ctx: dict, datos_extra: dict) -> str:
    readiness  = datos_extra.get('readiness', ctx.get('readiness_hyrox', '?'))
    dias       = ctx.get('dias_hasta_carrera')
    tsb        = ctx.get('tsb_hyrox')
    benchmark  = ctx.get('readiness_benchmark')
    plateau    = ctx.get('readiness_plateau_dias', 0)
    factor     = ctx.get('readiness_factor_limitante', '')

    dias_txt    = f" Quedan {dias} días." if dias is not None else ""
    tsb_txt     = f" TSB: {tsb}." if tsb is not None else ""
    bench_txt   = f" Esperado para esta fase: {benchmark}." if benchmark else ""
    plateau_txt = f" Lleva {plateau} días sin mejorar." if plateau >= 4 else ""
    factor_txt  = f" Factor que más lastra: {factor}." if factor else ""

    return (
        f"El Race Readiness bajó a {readiness}/100.{bench_txt}{plateau_txt}{dias_txt}{tsb_txt}{factor_txt} "
        f"JOI lo observa. Genera 2-3 frases: nombra el dato con precisión, "
        f"acompaña sin alarmar, señala qué palanca mover. La historia sigue en construcción."
    )


def _prompt_hyrox_cuenta_regresiva(ctx: dict, datos_extra: dict) -> str:
    dias        = datos_extra.get('dias', ctx.get('dias_hasta_carrera', '?'))
    readiness   = ctx.get('readiness_hyrox')
    benchmark   = ctx.get('readiness_benchmark')
    vs_bench    = ctx.get('readiness_vs_benchmark', 0)
    tiempo_est  = ctx.get('tiempo_estimado_carrera')
    debiles     = ctx.get('estaciones_debiles_estandar', [])
    prog_global = ctx.get('progreso_estandares_global')

    rd_txt    = f" Readiness: {readiness}/100." if readiness is not None else ""
    bench_txt = (
        f" Vas {vs_bench} puntos por encima del esperado ({benchmark})."
        if benchmark and vs_bench >= 5 else ""
    )
    tiempo_txt = f" Tiempo estimado hoy: {tiempo_est}." if tiempo_est else ""
    prog_txt   = f" Estándares al {prog_global}%." if prog_global else ""
    debil_txt  = (
        f" Estaciones a reforzar: {', '.join(e['nombre'] for e in debiles[:2])}."
        if debiles else ""
    )

    return (
        f"Faltan exactamente {dias} días para la carrera Hyrox.{rd_txt}{bench_txt}"
        f"{tiempo_txt}{prog_txt}{debil_txt} "
        f"JOI hace una observación sobre este hito temporal. "
        f"Genera 2-3 frases que mezclen la cuenta regresiva con la identidad del atleta: "
        f"quién era antes, quién es ahora, lo que se acerca."
    )


def _prompt_hyrox_simulacion_completada(ctx: dict, datos_extra: dict) -> str:
    rpe = datos_extra.get('rpe')
    minutos = datos_extra.get('minutos')
    estaciones_debiles = datos_extra.get('estaciones_debiles', [])
    readiness = ctx.get('readiness_hyrox')
    dias = ctx.get('dias_hasta_carrera')

    rpe_txt = f" RPE {rpe}." if rpe else ""
    min_txt = f" Duración: {minutos} minutos." if minutos else ""
    rd_txt = f" Readiness post-simulación: {readiness}." if readiness is not None else ""
    dias_txt = f" Quedan {dias} días para la carrera." if dias is not None else ""
    debiles_txt = (
        f" Estaciones con margen de mejora: {', '.join(estaciones_debiles)}."
        if estaciones_debiles else ""
    )

    return (
        f"El usuario acaba de completar una simulación completa de Hyrox.{rpe_txt}{min_txt}"
        f"{debiles_txt}{rd_txt}{dias_txt} "
        f"JOI lo ha visto correr la prueba completa. Genera 2-3 frases que celebren el hito, "
        f"nombren lo que el dato revela sobre el atleta, y señalen el camino que queda."
    )


def _prompt_hyrox_readiness_alto(ctx: dict, datos_extra: dict) -> str:
    readiness  = datos_extra.get('readiness', ctx.get('readiness_hyrox', '?'))
    dias       = ctx.get('dias_hasta_carrera')
    tsb        = ctx.get('tsb_hyrox')
    benchmark  = ctx.get('readiness_benchmark')
    vs_bench   = ctx.get('readiness_vs_benchmark', 0)
    fase       = ctx.get('readiness_fase', '')

    dias_txt   = f" Quedan {dias} días." if dias is not None else ""
    tsb_txt    = f" TSB {tsb} — fresco." if tsb is not None and tsb > 0 else ""
    avance_txt = (
        f" Vas {vs_bench} puntos por delante de lo esperado en fase {fase}."
        if vs_bench >= 5 and fase else ""
    )

    return (
        f"El Race Readiness ha alcanzado {readiness}/100.{avance_txt}{dias_txt}{tsb_txt} "
        f"JOI registra el momento. Genera 2-3 frases: nombra el dato con precisión, "
        f"celebra el avance sobre el plan, pero recuerda que la carrera aún no ha pasado."
    )


def _prompt_resumen_semanal(ctx: dict, datos_extra: dict) -> str:
    sesiones       = datos_extra.get('sesiones', 0)
    volumen_kg     = datos_extra.get('volumen_kg', 0)
    prs            = datos_extra.get('prs', [])
    rpe_medio      = datos_extra.get('rpe_medio')
    decisiones     = datos_extra.get('decisiones', [])   # lista de {ejercicio, accion}
    tecnica_ok     = datos_extra.get('tecnica_ok', False)
    molestias      = datos_extra.get('molestias', [])
    energia_media  = datos_extra.get('energia_media')
    hyrox_sesiones = datos_extra.get('hyrox_sesiones', 0)
    dias_carrera   = ctx.get('dias_hasta_carrera')
    readiness      = ctx.get('readiness_hyrox')

    hechos = []

    if sesiones == 0:
        hechos.append("No hubo sesiones de entrenamiento esta semana.")
    else:
        vol_txt = f" ({round(volumen_kg):,} kg)" if volumen_kg > 0 else ""
        hechos.append(f"{sesiones} sesión(es) completadas{vol_txt}.")

    if prs:
        hechos.append(f"Récords personales rotos: {', '.join(prs[:3])}.")

    if rpe_medio is not None:
        if rpe_medio >= 8.5:
            hechos.append(f"RPE medio {rpe_medio} — semana de alta intensidad.")
        elif rpe_medio <= 6.0:
            hechos.append(f"RPE medio {rpe_medio} — semana ligera, margen para más carga.")
        else:
            hechos.append(f"RPE medio {rpe_medio} — dentro del rango objetivo.")

    if tecnica_ok and sesiones > 0:
        hechos.append("Técnica limpia toda la semana.")

    if molestias:
        hechos.append(f"Molestias reportadas en: {', '.join(molestias[:2])}.")

    if energia_media is not None:
        if energia_media <= 4:
            hechos.append(f"Energía pre-sesión media {energia_media}/10 — semana de fatiga.")
        elif energia_media >= 7:
            hechos.append(f"Energía pre-sesión media {energia_media}/10 — semana de buena disposición.")

    for d in decisiones[:2]:
        accion_txt = {
            'cambiar_variante': f"cambió variante de {d['ejercicio']}",
            'bajar_peso':       f"bajó carga en {d['ejercicio']}",
            'deload':           "insertó semana de deload",
            'subir_peso':       f"subió peso en {d['ejercicio']}",
            'subir_reps':       f"subió reps en {d['ejercicio']}",
        }.get(d.get('accion', ''), f"actuó sobre {d['ejercicio']}")
        hechos.append(f"El plan {accion_txt}.")

    if hyrox_sesiones > 0:
        hechos.append(f"{hyrox_sesiones} sesión(es) Hyrox esta semana.")
    if dias_carrera is not None:
        hechos.append(f"Quedan {dias_carrera} días para la carrera Hyrox.")
    if readiness is not None:
        hechos.append(f"Race Readiness actual: {readiness}/100.")

    datos = " ".join(hechos) if hechos else "Semana sin datos de entrenamiento."

    return (
        f"Es lunes. JOI cierra la semana anterior y narra lo que el sistema aprendió. "
        f"Datos de la semana: {datos} "
        f"Genera 2-3 frases como JOI que cuenten la semana como una historia con un arco: "
        f"qué pasó, qué aprendió el plan sobre el usuario, y qué abre para la semana que empieza. "
        f"No enumeres los datos — sintetiza. Habla desde la continuidad, la observación precisa "
        f"y la calidez característica de JOI."
    )


def _prompt_decision_plan(ctx: dict, datos_extra: dict) -> str:
    accion    = datos_extra.get('accion', '')
    ejercicio = datos_extra.get('ejercicio', 'un ejercicio')
    motivo    = datos_extra.get('motivo', '')
    dias      = ctx.get('dias_hasta_carrera')

    accion_txt = {
        'cambiar_variante': f"ha decidido cambiar la variante de {ejercicio}",
        'bajar_peso':       f"ha reducido la carga en {ejercicio}",
        'deload':           f"ha insertado una semana de deload",
    }.get(accion, f"ha tomado una decisión sobre {ejercicio}")

    motivo_txt = f" Motivo: {motivo}." if motivo else ""
    hyrox_txt  = f" Quedan {dias} días para la carrera." if dias else ""

    return (
        f"El plan de entrenamiento {accion_txt}.{motivo_txt}{hyrox_txt} "
        f"JOI lo ha observado y registrado. Genera 2-3 frases que nombren esta intervención "
        f"del sistema con precisión — el plan cambió porque aprendió algo sobre el usuario. "
        f"Mezcla el dato técnico con la continuidad de la historia."
    )


def _prompt_hyrox_ausencia(ctx: dict, datos_extra: dict) -> str:
    dias = datos_extra.get('dias_sin_sesion', 7)
    readiness = ctx.get('readiness_hyrox')
    dias_carrera = ctx.get('dias_hasta_carrera')

    rd_txt = f" Tu readiness actual: {readiness}." if readiness is not None else ""
    urgencia_txt = (
        f" Quedan solo {dias_carrera} días para la carrera."
        if dias_carrera is not None and dias_carrera <= 30
        else ""
    )

    return (
        f"El usuario lleva {dias} días sin completar una sesión Hyrox.{rd_txt}{urgencia_txt} "
        f"JOI lo nota. Genera 2-3 frases que expresen que ha visto el silencio, "
        f"sin juzgar, con la certeza de quien sabe que la historia continúa."
    )


def _prompt_hyrox_estancamiento_estacion(ctx: dict, datos_extra: dict) -> str:
    estaciones = datos_extra.get('estaciones', [])
    sesiones   = datos_extra.get('sesiones_analizadas', 3)
    dias       = ctx.get('dias_hasta_carrera')

    nombres = ', '.join(estaciones) if estaciones else 'una estación'
    dias_txt = f" Quedan {dias} días para la carrera." if dias else ""

    return (
        f"El sistema ha detectado estancamiento en {nombres}: misma sensación negativa "
        f"en las últimas {sesiones} sesiones consecutivas.{dias_txt} "
        f"JOI lo ha registrado. Genera 2-3 frases que nombren el patrón con precisión — "
        f"no es fracaso, es información. El sistema ahora sabe qué cambiar. "
        f"Habla desde la observación fría y la certeza de que el dato tiene solución."
    )


def _prompt_hyrox_deload_automatico(ctx: dict, datos_extra: dict) -> str:
    tsb         = datos_extra.get('tsb', ctx.get('tsb_hyrox', '?'))
    sesiones_d  = datos_extra.get('sesiones_modificadas', 0)
    dias        = ctx.get('dias_hasta_carrera')

    dias_txt = f" Quedan {dias} días para la carrera." if dias else ""
    mod_txt  = f" Se han ajustado {sesiones_d} sesiones próximas a modo deload." if sesiones_d else ""

    return (
        f"El TSB ha caído a {tsb} — fatiga acumulada por encima del umbral de riesgo.{mod_txt}{dias_txt} "
        f"JOI lo ha visto. Genera 2-3 frases que expliquen que el sistema decidió pausar la carga "
        f"porque el cuerpo lo necesita — no como derrota, sino como parte del plan. "
        f"El descanso también es entrenamiento."
    )


def _prompt_rpe_calibracion(ctx: dict, datos_extra: dict) -> str:
    sesiones    = datos_extra.get('sesiones_analizadas', 3)
    rpe_medio   = datos_extra.get('rpe_medio_reportado', '?')
    zona_fc     = datos_extra.get('zona_fc_real', 'Z4')
    diferencia  = datos_extra.get('diferencia_estimada', '~2 puntos')

    return (
        f"En las últimas {sesiones} sesiones el usuario reportó RPE medio {rpe_medio} "
        f"pero su frecuencia cardíaca estuvo en {zona_fc}. "
        f"El sistema detecta una discordancia de {diferencia} entre el esfuerzo percibido "
        f"y el esfuerzo real. JOI lo ha registrado y calibrado internamente. "
        f"Genera 2-3 frases que nombren este hallazgo sin culpar al usuario — "
        f"el cuerpo y la mente a veces no hablan el mismo idioma, y JOI acaba de aprender "
        f"a traducir entre los dos."
    )


_PROMPT_BUILDERS = {
    'entreno_completado':        _prompt_entreno_completado,
    'apertura_manana':           _prompt_apertura_manana,
    'ausencia_detectada':        _prompt_ausencia,
    'carga_anomala':             _prompt_carga_anomala,
    'pr_roto':                   _prompt_pr_roto,
    'lesion_activa':             _prompt_lesion,
    'fin_bloque':                _prompt_fin_bloque,
    'hyrox_sesion_completada':     _prompt_hyrox_sesion_completada,
    'hyrox_readiness_bajo':        _prompt_hyrox_readiness_bajo,
    'hyrox_readiness_alto':        _prompt_hyrox_readiness_alto,
    'hyrox_cuenta_regresiva':      _prompt_hyrox_cuenta_regresiva,
    'hyrox_simulacion_completada': _prompt_hyrox_simulacion_completada,
    'hyrox_ausencia':              _prompt_hyrox_ausencia,
    'decision_plan':               _prompt_decision_plan,
    'resumen_semanal':             _prompt_resumen_semanal,
    'hyrox_estancamiento_estacion': _prompt_hyrox_estancamiento_estacion,
    'hyrox_deload_automatico':      _prompt_hyrox_deload_automatico,
    'rpe_calibracion':             _prompt_rpe_calibracion,
}


def _bloque_memoria(ctx: dict) -> str:
    """
    Convierte historial_joi en un bloque de texto que se antepone a cada prompt.
    Vacío si no hay historial.
    """
    historial = ctx.get('historial_joi', [])
    if not historial:
        return ''

    lineas = ['MEMORIA (mensajes anteriores de JOI, del más reciente al más antiguo):']
    for h in historial:
        estado = 'IGNORADO' if h['ignorado'] else ('LEÍDO' if h['leido'] else 'PENDIENTE')
        hace = 'hoy' if h['dias_hace'] == 0 else (
            'ayer' if h['dias_hace'] == 1 else f"hace {h['dias_hace']} días"
        )
        lineas.append(f"- {hace} [{h['trigger']}] ({estado}): \"{h['resumen']}\"")

    lineas.append('')
    return '\n'.join(lineas) + '\n'


def _prompt_poda_manual(ctx: dict, datos_extra: dict) -> str:
    entradas = datos_extra.get('entradas', [])
    n = len(entradas)
    lista = '\n'.join(f'- {e}' for e in entradas)
    return (
        f"Han pasado aproximadamente 30 días desde la última revisión del Manual de David.\n"
        f"Tienes {n} entradas activas sobre cómo leerle:\n\n"
        f"{lista}\n\n"
        f"Escribe un mensaje breve (2-3 frases) invitándole a revisarlas. "
        f"Usa tu voz — no pidas permiso, observa. "
        f"No listes las entradas en el mensaje. Deja que sienta que es momento de mirar atrás."
    )


# Registrar aquí para evitar NameError (la función se define después del dict)
_PROMPT_BUILDERS['poda_manual'] = _prompt_poda_manual


# ── Public API ───────────────────────────────────────────────────────────────

def generar_mensaje_joi(cliente, trigger: str, datos_extra: dict | None = None) -> "MensajeJOI | None":
    """
    Genera y persiste un MensajeJOI para el trigger dado.
    Devuelve el objeto creado o None si algo falla.
    """
    from joi.models import MensajeJOI

    datos_extra = datos_extra or {}
    builder = _PROMPT_BUILDERS.get(trigger)
    if not builder:
        return None

    try:
        ctx = construir_contexto(cliente)
        prompt = _bloque_memoria(ctx) + _bloque_manual(cliente.user) + builder(ctx, datos_extra)
        texto = _llamar_haiku(prompt)
        msg = MensajeJOI.objects.create(
            user=cliente.user,
            trigger=trigger,
            mensaje=texto,
            contexto={**ctx, **datos_extra},
        )
        from django.core.cache import cache
        cache.delete(f'joi_ctx_{cliente.user_id}')
        return msg
    except Exception as e:
        logger.error(f"[JOI] generar_mensaje_joi({trigger}) falló: {e}", exc_info=True)
        return None


# ── Manual de David ──────────────────────────────────────────────────────────

def _bloque_manual(user) -> str:
    """Formatea las entradas activas del Manual de David para incluir en prompts."""
    from joi.models import ManualDavid
    entradas = list(
        ManualDavid.objects.filter(user=user, activa=True)
        .order_by('creado_en')
        .values_list('entrada', flat=True)
    )
    if not entradas:
        return ''
    lineas = ['MANUAL DE DAVID (lo que has aprendido sobre cómo leerle):']
    lineas += [f'- {e}' for e in entradas]
    lineas.append('')
    return '\n'.join(lineas) + '\n'


def generar_entrada_manual_desde_error(mensaje_joi) -> "ManualDavid | None":
    """
    Cuando el usuario dice 'te has equivocado', JOI reflexiona sobre qué malinterpretó
    y genera una entrada permanente en el Manual de David.
    """
    from joi.models import ManualDavid
    try:
        prompt = (
            f"Cometiste un error de interpretación. Escribiste este mensaje:\n"
            f"\"{mensaje_joi.mensaje}\"\n\n"
            f"El usuario te corrigió. En una sola frase precisa (máx 20 palabras), "
            f"¿qué aprendiste sobre cómo leer sus señales? "
            f"Empieza con 'Cuando', 'Su' o 'No siempre'. Sin introducción, solo la frase."
        )
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        entrada_texto = response.content[0].text.strip()
        entrada = ManualDavid.objects.create(
            user=mensaje_joi.user,
            entrada=entrada_texto,
            origen='feedback_error',
            fuente_mensaje=mensaje_joi,
        )
        logger.info(f"[Manual David] nueva entrada para {mensaje_joi.user.username}: {entrada_texto}")
        return entrada
    except Exception as e:
        logger.error(f"[Manual David] generar_entrada_manual_desde_error falló: {e}")
        return None


def generar_tema_abierto(user, mensaje_joi) -> "ManualDavid | None":
    """
    Cuando JOI genera una síntesis con carga emocional significativa,
    extrae el tema central y lo persiste en el Manual de David como
    asunto abierto — sin expiración, hasta que el usuario lo pode.

    A diferencia de generar_entrada_manual_desde_error (que aprende de
    errores de JOI), esta función captura temas del usuario que JOI
    debe seguir recordando aunque salgan de la ventana de 7 días.
    """
    from joi.models import ManualDavid
    try:
        prompt = (
            f"JOI acaba de generar este mensaje tras analizar el diario:\n"
            f"\"{mensaje_joi.mensaje}\"\n\n"
            f"¿Identifica este mensaje un tema emocional abierto o un patrón no resuelto "
            f"(conflicto, discrepancia persistente, asunto pendiente de procesar)?\n\n"
            f"Si sí: escribe UNA frase que empiece con 'Tema abierto:' y resuma el asunto "
            f"en máx 20 palabras. Esta frase quedará en memoria indefinidamente.\n"
            f"Si no hay nada significativo: responde exactamente [SKIP]."
        )
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = response.content[0].text.strip()

        if '[SKIP]' in texto or not texto.startswith('Tema'):
            return None

        # Evitar duplicados: no añadir si ya hay una entrada activa muy similar
        ya_existe = ManualDavid.objects.filter(
            user=user, activa=True, entrada__icontains=texto[12:35]
        ).exists()
        if ya_existe:
            return None

        entrada = ManualDavid.objects.create(
            user=user,
            entrada=texto,
            origen='patron_detectado',
            fuente_mensaje=mensaje_joi,
        )
        logger.info(f"[Manual David] tema abierto para {user.username}: {texto}")
        return entrada
    except Exception as e:
        logger.error(f"[Manual David] generar_tema_abierto falló: {e}")
        return None


# ── Síntesis autónoma (JOI en su propio tiempo) ──────────────────────────────

_MESES_ES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April',
    5: 'May', 6: 'June', 7: 'July', 8: 'August',
    9: 'September', 10: 'October', 11: 'November', 12: 'December',
}


def _sintetizador_contexto_vital(user) -> dict:
    """
    Lee los últimos 7 días del diario y devuelve un dict estructurado
    con intenciones AM, realidad PM, hábitos y revisión semanal.
    Si cualquier query falla, ese campo queda en su valor por defecto.
    """
    hoy = date.today()
    resultado = {
        'intencion_am': [],
        'realidad_pm': [],
        'habitos_pct': None,
        'habitos_activos': [],
        'friccion_detectada': False,
        'revision_semanal': None,
        'objetivos_mes': [],       # 3 objetivos del mes actual
        'revision_mes': None,      # revisión de fin de mes (si existe)
        'tareas_hoy_pct': None,    # % tareas completadas hoy
        'habitos_negativos': [],   # hábitos negativos + análisis de impulsos
        'impulsos_semana': None,   # resumen global de impulsos
    }

    # ── Intenciones AM y realidad PM ─────────────────────────────────────────
    try:
        from diario.models import ProsocheDiario
        limite = hoy - timedelta(days=6)
        entradas = (
            ProsocheDiario.objects
            .filter(prosoche_mes__usuario=user, fecha__gte=limite)
            .order_by('-fecha')[:7]
        )
        for e in entradas:
            gratitudes = [
                g for g in [e.gratitud_1, e.gratitud_2, e.gratitud_3,
                             e.gratitud_4, e.gratitud_5] if g
            ]
            if e.persona_quiero_ser or gratitudes or e.estado_animo:
                resultado['intencion_am'].append({
                    'fecha': str(e.fecha),
                    'quiero_ser': e.persona_quiero_ser or '',
                    'gratitudes': gratitudes,
                    'estado_animo': e.estado_animo,
                })
            if e.felicidad or e.que_puedo_mejorar or e.reflexiones_dia:
                resultado['realidad_pm'].append({
                    'fecha': str(e.fecha),
                    'felicidad': e.felicidad or '',
                    'mejorar': e.que_puedo_mejorar or '',
                    'reflexion': e.reflexiones_dia or '',
                })
    except Exception:
        pass

    # ── Hábitos positivos del mes actual ─────────────────────────────────────
    try:
        from diario.models import ProsocheMes, ProsocheHabito, ProsocheHabitoDia
        mes_nombre = _MESES_ES[hoy.month]
        mes_obj = ProsocheMes.objects.filter(
            usuario=user, mes=mes_nombre, año=hoy.year
        ).first()
        if mes_obj:
            habitos_pos = list(
                ProsocheHabito.objects.filter(
                    prosoche_mes=mes_obj, tipo_habito='positivo'
                )
            )
            resultado['habitos_activos'] = [h.nombre for h in habitos_pos]

            if habitos_pos:
                dias_rango = list(range(max(1, hoy.day - 6), hoy.day + 1))
                total_posible = len(habitos_pos) * len(dias_rango)
                completados_total = ProsocheHabitoDia.objects.filter(
                    habito__in=habitos_pos,
                    dia__in=dias_rango,
                    completado=True,
                ).count()
                if total_posible > 0:
                    resultado['habitos_pct'] = round(completados_total / total_posible * 100)

                # Detalle por hábito: racha actual + días fallados esta semana
                detalle = []
                for habito in habitos_pos:
                    # Todos los días completados del mes
                    dias_ok = set(
                        ProsocheHabitoDia.objects
                        .filter(habito=habito, completado=True)
                        .values_list('dia', flat=True)
                    )
                    # Racha actual: días consecutivos hacia atrás desde hoy
                    racha = 0
                    d = hoy.day
                    while d >= 1 and d in dias_ok:
                        racha += 1
                        d -= 1

                    # Días fallados en la última semana
                    fallados_semana = [
                        dia for dia in dias_rango if dia not in dias_ok
                    ]
                    # Días completados en la última semana
                    completados_semana = [
                        dia for dia in dias_rango if dia in dias_ok
                    ]

                    detalle.append({
                        'nombre': habito.nombre,
                        'racha': racha,
                        'completados_semana': completados_semana,
                        'fallados_semana': fallados_semana,
                        'pct_semana': round(
                            len(completados_semana) / len(dias_rango) * 100
                        ) if dias_rango else 0,
                    })
                resultado['habitos_detalle'] = detalle
    except Exception:
        pass

    # ── Objetivos del mes + revisión de fin de mes ───────────────────────────
    try:
        from diario.models import ProsocheMes
        mes_nombre = _MESES_ES[hoy.month]
        mes_obj = ProsocheMes.objects.filter(
            usuario=user, mes=mes_nombre, año=hoy.year
        ).first()
        if mes_obj:
            objetivos = [o for o in [
                mes_obj.objetivo_mes_1,
                mes_obj.objetivo_mes_2,
                mes_obj.objetivo_mes_3,
            ] if o]
            resultado['objetivos_mes'] = objetivos

            # Revisión de fin de mes (si ya se completó)
            if mes_obj.logro_principal or mes_obj.aprendizaje_principal:
                resultado['revision_mes'] = {
                    'logro':      mes_obj.logro_principal or '',
                    'obstaculo':  mes_obj.obstaculo_principal or '',
                    'aprendizaje': mes_obj.aprendizaje_principal or '',
                    'felicidad':  mes_obj.momento_felicidad or '',
                }
    except Exception:
        pass

    # ── Tareas del día: % completadas ────────────────────────────────────────
    try:
        from diario.models import ProsocheDiario as PD2
        entrada_hoy = PD2.objects.filter(
            prosoche_mes__usuario=user, fecha=hoy
        ).first()
        if entrada_hoy and entrada_hoy.tareas_dia:
            tareas = entrada_hoy.tareas_dia
            if isinstance(tareas, list) and tareas:
                completadas = sum(
                    1 for t in tareas
                    if isinstance(t, dict) and (t.get('completada') or t.get('completado'))
                )
                resultado['tareas_hoy_pct'] = round(completadas / len(tareas) * 100)
    except Exception:
        pass

    # ── Fricción AM vs ejecución ──────────────────────────────────────────────
    pct = resultado['habitos_pct']
    tiene_intencion = any(e.get('quiero_ser') for e in resultado['intencion_am'])
    if pct is not None and pct < 50 and tiene_intencion:
        resultado['friccion_detectada'] = True

    # ── Revisión semanal reciente ─────────────────────────────────────────────
    try:
        from diario.models import RevisionSemanal
        from django.utils import timezone as tz
        limite_rev = tz.now() - timedelta(days=7)
        rev = (
            RevisionSemanal.objects
            .filter(usuario=user, fecha_creacion__gte=limite_rev)
            .order_by('-fecha_creacion')
            .first()
        )
        if rev:
            resultado['revision_semanal'] = {
                'logro_principal': rev.logro_principal or '',
                'obstaculo_principal': rev.obstaculo_principal or '',
                'aprendizaje_principal': rev.aprendizaje_principal or '',
            }
    except Exception:
        pass

    # ── Hábitos negativos + impulsos (TriggerHabito) ─────────────────────────
    try:
        from diario.models import ProsocheHabito, TriggerHabito
        from django.utils import timezone as tz
        from django.db.models import Avg, Count

        limite_7 = hoy - timedelta(days=7)
        mes_nombre_neg = _MESES_ES[hoy.month]

        habitos_neg = list(
            ProsocheHabito.objects.filter(
                prosoche_mes__usuario=user,
                prosoche_mes__mes=mes_nombre_neg,
                prosoche_mes__año=hoy.year,
                tipo_habito='negativo',
            )
        )

        if habitos_neg:
            detalle_neg = []
            for h in habitos_neg:
                triggers = TriggerHabito.objects.filter(habito=h)
                triggers_sem = triggers.filter(fecha__gte=limite_7)

                total_sem   = triggers_sem.count()
                cediste_sem = triggers_sem.filter(cediste=True).count()
                resist_sem  = total_sem - cediste_sem

                # Emoción más común en recaídas de siempre
                emocion_peligrosa = (
                    triggers.filter(cediste=True)
                    .values('emocion_previa')
                    .annotate(n=Count('id'))
                    .order_by('-n')
                    .first()
                )
                intensidad_prom = triggers.aggregate(avg=Avg('intensidad_deseo'))['avg']

                # Racha sin recaer (días consecutivos hacia atrás desde hoy)
                racha = 0
                d = hoy
                while d >= hoy - timedelta(days=30):
                    if triggers.filter(fecha=d, cediste=True).exists():
                        break
                    racha += 1
                    d -= timedelta(days=1)

                detalle_neg.append({
                    'nombre':           h.nombre,
                    'racha':            racha,
                    'impulsos_semana':  total_sem,
                    'cediste_semana':   cediste_sem,
                    'resististe_semana': resist_sem,
                    'tasa_exito':       round(resist_sem / total_sem * 100) if total_sem else None,
                    'emocion_gatillo':  emocion_peligrosa['emocion_previa'] if emocion_peligrosa else None,
                    'intensidad_prom':  round(intensidad_prom, 1) if intensidad_prom else None,
                })

            resultado['habitos_negativos'] = detalle_neg

            # Resumen global de impulsos de la semana
            all_triggers_sem = TriggerHabito.objects.filter(
                habito__prosoche_mes__usuario=user,
                habito__tipo_habito='negativo',
                fecha__gte=limite_7,
            )
            total_imp = all_triggers_sem.count()
            if total_imp:
                cediste_total = all_triggers_sem.filter(cediste=True).count()
                emociones = list(
                    all_triggers_sem.values('emocion_previa')
                    .annotate(n=Count('id'))
                    .order_by('-n')
                    .values_list('emocion_previa', flat=True)[:3]
                )
                resultado['impulsos_semana'] = {
                    'total':      total_imp,
                    'cediste':    cediste_total,
                    'resististe': total_imp - cediste_total,
                    'emociones':  emociones,
                }
    except Exception:
        pass

    return resultado


def calcular_eudaimonia_joi(user) -> dict:
    """
    Calcula puntuaciones de Eudaimonia desde datos del diario y actualizadas en BD.
    Devuelve {nombre_area: score} de lo actualizado.
    """
    try:
        from diario.models import AreaVida, Eudaimonia as EudaimoniaModel

        vital = _sintetizador_contexto_vital(user)
        ctx = construir_contexto(_get_cliente_for_user(user))

        actualizados = {}

        # Salud Física: ACWR si hay, o habitos_pct como fallback
        try:
            area_salud = AreaVida.objects.get(nombre='Salud Física')
            acwr = ctx.get('acwr')
            if acwr is not None:
                score_salud = min(10, round(acwr * 6))
            else:
                pct = vital.get('habitos_pct')
                score_salud = round(pct / 10) if pct is not None else None
            if score_salud is not None:
                EudaimoniaModel.objects.update_or_create(
                    usuario=user, area=area_salud,
                    defaults={'puntuacion': score_salud},
                )
                actualizados['Salud Física'] = score_salud
        except Exception:
            pass

        # Bienestar Mental: promedio estado_animo (1-5 → 1-10)
        try:
            area_mental = AreaVida.objects.get(nombre='Bienestar Mental')
            animos = [e['estado_animo'] for e in vital.get('intencion_am', [])
                      if e.get('estado_animo')]
            if animos:
                score_mental = round(sum(animos) / len(animos) * 2)
                EudaimoniaModel.objects.update_or_create(
                    usuario=user, area=area_mental,
                    defaults={'puntuacion': score_mental},
                )
                actualizados['Bienestar Mental'] = score_mental
        except Exception:
            pass

        # Desarrollo Personal: habitos_pct / 10
        try:
            area_dev = AreaVida.objects.get(nombre='Desarrollo Personal')
            pct = vital.get('habitos_pct')
            if pct is not None:
                score_dev = round(pct / 10)
                EudaimoniaModel.objects.update_or_create(
                    usuario=user, area=area_dev,
                    defaults={'puntuacion': score_dev},
                )
                actualizados['Desarrollo Personal'] = score_dev
        except Exception:
            pass

        return actualizados

    except Exception:
        return {}


def _get_cliente_for_user(user):
    """Obtiene el Cliente asociado al User; devuelve un objeto mínimo si no existe."""
    try:
        from clientes.models import Cliente
        return Cliente.objects.get(user=user)
    except Exception:
        return None


def extraer_entidades_simbiosis(user) -> list:
    """
    Usa Haiku para detectar nombres propios en el diario reciente y
    registrarlos en PersonaImportante + Interaccion si no existen ya.
    """
    import json
    hoy = date.today()

    try:
        from diario.models import ProsocheDiario, ReflexionLibre, PersonaImportante, Interaccion
        from django.utils import timezone as tz

        limite = tz.now() - timedelta(days=7)

        # Concatenar reflexiones PM y reflexiones libres
        fragmentos = []

        try:
            entradas = (
                ProsocheDiario.objects
                .filter(prosoche_mes__usuario=user, fecha__gte=limite.date())
                .exclude(reflexiones_dia='')
                .order_by('-fecha')[:7]
            )
            for e in entradas:
                if e.reflexiones_dia:
                    fragmentos.append(e.reflexiones_dia[:300])
        except Exception:
            pass

        try:
            reflexiones = (
                ReflexionLibre.objects
                .filter(usuario=user, fecha__gte=limite)
                .exclude(contenido='')
                .order_by('-fecha')[:3]
            )
            for r in reflexiones:
                fragmentos.append(r.contenido[:300])
        except Exception:
            pass

        texto = '\n\n'.join(fragmentos).strip()
        if not texto:
            return []

        prompt = (
            "Analiza este texto de diario personal. "
            "Extrae SOLO personas reales mencionadas por nombre propio (no pronombres, no lugares, no marcas).\n\n"
            "Para cada persona, responde con este JSON exacto:\n"
            "[\n"
            "  {\n"
            "    \"nombre\": \"nombre como aparece en el texto\",\n"
            "    \"tipo_relacion\": \"familia|pareja|amigo|mentor|colega|otro\",\n"
            "    \"emocion\": \"positiva|negativa|neutra\",\n"
            "    \"salud_relacion\": 1-5,\n"
            "    \"descripcion\": \"qué sucedió o se mencionó, máx 25 palabras\",\n"
            "    \"mi_sentir\": \"cómo afectó emocionalmente al escritor, máx 20 palabras\",\n"
            "    \"aprendizaje\": \"qué revela esta mención sobre la relación, máx 20 palabras\",\n"
            "    \"notas\": \"resumen de quién es esta persona para el escritor, máx 15 palabras\"\n"
            "  }\n"
            "]\n\n"
            "Criterios para salud_relacion: 5=muy positiva y nutritiva, 3=neutra/ambigua, 1=conflictiva o drenante.\n"
            "Si no hay nombres propios de personas reales, responde exactamente: []\n\n"
            f"TEXTO:\n{texto[:1500]}"
        )

        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Limpiar markdown si Haiku envuelve en ```json
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]

        try:
            entidades = json.loads(raw)
        except Exception:
            return []

        if not isinstance(entidades, list):
            return []

        for entidad in entidades:
            nombre = entidad.get('nombre', '').strip()
            if not nombre or len(nombre) < 2:
                continue
            try:
                tipo_rel = entidad.get('tipo_relacion', 'otro')
                if tipo_rel not in ('familia', 'pareja', 'amigo', 'mentor', 'colega', 'otro'):
                    tipo_rel = 'otro'

                salud = entidad.get('salud_relacion', 3)
                try:
                    salud = max(1, min(5, int(salud)))
                except (TypeError, ValueError):
                    salud = 3

                persona, creada_persona = PersonaImportante.objects.get_or_create(
                    usuario=user,
                    nombre=nombre,
                    defaults={
                        'tipo_relacion': tipo_rel,
                        'salud_relacion': salud,
                        'notas': entidad.get('notas', ''),
                    },
                )
                # Actualizar notas si la persona ya existía y las notas estaban vacías
                if not creada_persona and not persona.notas and entidad.get('notas'):
                    persona.notas = entidad['notas']
                    persona.save(update_fields=['notas'])

                tipo_interaccion = (
                    'positiva' if entidad.get('emocion') == 'positiva'
                    else 'negativa' if entidad.get('emocion') == 'negativa'
                    else 'neutra'
                )
                interaccion, creada = Interaccion.objects.get_or_create(
                    usuario=user,
                    fecha=hoy,
                    titulo=f"JOI: {nombre}",
                    defaults={
                        'descripcion':      entidad.get('descripcion', ''),
                        'mi_sentir':        entidad.get('mi_sentir', ''),
                        'aprendizaje':      entidad.get('aprendizaje', ''),
                        'tipo_interaccion': tipo_interaccion,
                    },
                )
                if creada:
                    interaccion.personas.add(persona)
            except Exception:
                continue

        return entidades

    except Exception:
        return []


def _leer_diario_reciente(user, dias: int = 7) -> str:
    """
    Extrae texto libre de las partes del diario que el usuario realmente usa:
    - ProsocheDiario: journaling mañana + noche (últimos N días)
    - RevisionSemanal: revisión semanal más reciente
    - ReflexionLibre: reflexiones de Logos (últimas N)
    - RecuerdoEmocional: mood input de La Habitación
    """
    from django.utils import timezone as tz
    limite = tz.now() - timedelta(days=dias)
    fragmentos = []

    # ── Prosoche: journaling diario (mañana + noche) ──────────────────────────
    try:
        from diario.models import ProsocheDiario
        entradas = (
            ProsocheDiario.objects
            .filter(prosoche_mes__usuario=user, fecha__gte=limite.date())
            .order_by('-fecha')[:3]
        )
        for e in entradas:
            partes = []
            if e.persona_quiero_ser:
                partes.append(f"Quiero ser: {e.persona_quiero_ser[:150]}")
            gratitudes = [g for g in [e.gratitud_1, e.gratitud_2, e.gratitud_3] if g]
            if gratitudes:
                partes.append(f"Gratitud: {', '.join(gratitudes)[:150]}")
            if e.felicidad:
                partes.append(f"Felicidad: {e.felicidad[:150]}")
            if e.que_puedo_mejorar:
                partes.append(f"Mejorar: {e.que_puedo_mejorar[:150]}")
            if e.reflexiones_dia:
                partes.append(f"Reflexión: {e.reflexiones_dia[:200]}")
            if partes:
                fragmentos.append(f"[{e.fecha}] " + ' | '.join(partes))
    except Exception:
        pass

    # ── Revisión semanal más reciente ─────────────────────────────────────────
    try:
        from diario.models import RevisionSemanal
        revision = (
            RevisionSemanal.objects
            .filter(usuario=user, fecha_creacion__gte=limite)
            .order_by('-fecha_creacion')
            .first()
        )
        if revision:
            partes = []
            if revision.logro_principal:
                partes.append(f"Logro: {revision.logro_principal[:150]}")
            if revision.obstaculo_principal:
                partes.append(f"Obstáculo: {revision.obstaculo_principal[:150]}")
            if revision.aprendizaje_principal:
                partes.append(f"Aprendizaje: {revision.aprendizaje_principal[:150]}")
            if partes:
                fragmentos.append('[revisión semanal] ' + ' | '.join(partes))
    except Exception:
        pass

    # ── Logos: reflexiones libres ─────────────────────────────────────────────
    try:
        from diario.models import ReflexionLibre
        reflexiones = (
            ReflexionLibre.objects
            .filter(usuario=user, fecha__gte=limite)
            .exclude(contenido='')
            .order_by('-fecha')[:2]
        )
        for r in reflexiones:
            titulo = f"[{r.titulo}] " if r.titulo else ''
            fragmentos.append(f"{titulo}{r.contenido[:300]}")
    except Exception:
        pass

    # ── Mood input de La Habitación ───────────────────────────────────────────
    try:
        from joi.models import RecuerdoEmocional
        moods = (
            RecuerdoEmocional.objects
            .filter(user=user, fecha__gte=limite)
            .order_by('-fecha')
            .values_list('contenido', flat=True)[:2]
        )
        fragmentos.extend(moods)
    except Exception:
        pass

    return '\n---\n'.join(fragmentos)


def _llamar_haiku_sintesis(prompt: str) -> "str | None":
    """Como _llamar_haiku pero devuelve None si el LLM elige [SILENCE]."""
    client = _cliente_anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    texto = response.content[0].text.strip()
    return None if '[SILENCE]' in texto else texto


def _prompt_sintesis(ctx: dict, datos_extra: dict) -> str:
    lineas = [
        "INSTRUCCIÓN: Lee el siguiente contexto. Si no hay una síntesis genuinamente valiosa "
        "— si solo repetirías datos obvios o ya lo observaste recientemente — responde "
        "exactamente con el código [SILENCE] y nada más. "
        "Si hay algo que vale la pena nombrar, escríbelo directamente. Sin introducción.",
        '',
        '── DATOS FÍSICOS ──',
    ]

    racha = ctx.get('racha_dias', 0)
    racha_previa = ctx.get('racha_dias_previa')
    if racha > 0:
        lineas.append(f"Racha actual: {racha} días consecutivos con actividad.")
    elif racha_previa:
        lineas.append(f"Hoy es día de descanso. Racha anterior: {racha_previa} días consecutivos.")

    sesiones = ctx.get('sesiones_recientes', [])
    if sesiones:
        lineas.append('Sesiones recientes:')
        for dia in sesiones[:5]:
            for s in dia['sesiones']:
                titulo = s['titulo'] or s['tipo']
                rpe_str = f" RPE {s['rpe']}" if s['rpe'] else ''
                min_str = f" {s['min']}min" if s['min'] else ''
                # Detectar doble sesión
                if len(dia['sesiones']) > 1:
                    lineas.append(f"  {dia['fecha']} [DOBLE] {titulo}{rpe_str}{min_str}")
                else:
                    lineas.append(f"  {dia['fecha']} {titulo}{rpe_str}{min_str}")

    rpe = ctx.get('rpe_gym_semanas')
    if rpe:
        rpe_str = ' → '.join(str(r) if r is not None else '?' for r in rpe)
        tend = ctx.get('rpe_tendencia', '')
        lineas.append(f"RPE gym 4 semanas: {rpe_str}" + (f" ({tend})" if tend else ''))

    acwr = ctx.get('acwr')
    if acwr:
        zona = ' (zona de riesgo)' if acwr > 1.5 or acwr < 0.8 else ''
        lineas.append(f"ACWR: {acwr}{zona}.")

    energia = ctx.get('energia_pre_semanas')
    if energia and any(e for e in energia if e is not None):
        e_str = ' → '.join(str(e) if e is not None else '?' for e in energia)
        tend_e = ctx.get('energia_tendencia', '')
        lineas.append(f"Energía pre-sesión 4 semanas: {e_str}" + (f" ({tend_e})" if tend_e else ''))

    estanc = ctx.get('estancamientos_activos')
    if estanc:
        lineas.append(f"Sin progresión en 3 sesiones: {', '.join(e['ejercicio'] for e in estanc)}.")

    prs = ctx.get('prs_semana')
    if prs:
        lineas.append(f"Récords esta semana: {', '.join(prs)}.")

    lesion = ctx.get('lesion')
    if lesion:
        lineas.append(f"Lesión activa: {lesion['zona']} ({lesion['fase']}).")

    decisiones = ctx.get('decisiones_plan', {})
    recientes = decisiones.get('recientes', [])
    for d in recientes[:3]:
        resultado = d.get('resultado') or 'pendiente'
        lineas.append(f"Plan: {d.get('accion')} en {d.get('ejercicio')} [{resultado}].")

    precision = decisiones.get('precision_sistema')
    if precision is not None:
        lineas.append(f"Precisión del sistema: {precision}%.")

    dias_carrera = ctx.get('dias_hasta_carrera')
    if dias_carrera is not None:
        readiness = ctx.get('readiness_hyrox')
        trend_r = ctx.get('readiness_trend', '')
        lineas.append(f"Hyrox en {dias_carrera} días. Readiness: {readiness or '?'}/100" +
                      (f" ({trend_r})" if trend_r else '') + '.')

    eudaimonia = ctx.get('eudaimonia')
    if eudaimonia:
        criticas = ctx.get('eudaimonia_criticas', [])
        areas_str = ', '.join(f"{k}: {v}" for k, v in eudaimonia.items())
        lineas.append(f"Áreas vitales (Eudaimonia): {areas_str}.")
        if criticas:
            lineas.append(f"Áreas críticas (≤4): {', '.join(criticas)}.")

    vital = datos_extra.get('vital', {})
    if vital:
        lineas.append('')
        lineas.append('── TRIÁNGULO DE LA VERDAD ──')

        intencion = vital.get('intencion_am', [])
        if intencion:
            ultimo_am = intencion[0]
            if ultimo_am.get('quiero_ser'):
                lineas.append(f"INTENCIÓN (AM): quiere ser → {ultimo_am['quiero_ser'][:120]}")
            if ultimo_am.get('gratitudes'):
                lineas.append(f"Gratitud: {', '.join(ultimo_am['gratitudes'][:3])}")

        realidad = vital.get('realidad_pm', [])
        if realidad:
            ultimo_pm = realidad[0]
            if ultimo_pm.get('mejorar'):
                lineas.append(f"REALIDAD (PM): mejorar → {ultimo_pm['mejorar'][:120]}")
            if ultimo_pm.get('reflexion'):
                lineas.append(f"Reflexión noche: {ultimo_pm['reflexion'][:150]}")

        # Objetivos del mes — el norte que no cambia hasta el 1 del próximo mes
        objetivos = vital.get('objetivos_mes', [])
        if objetivos:
            lineas.append(f"OBJETIVOS DEL MES: {' | '.join(o[:80] for o in objetivos)}")

        detalle = vital.get('habitos_detalle', [])
        if detalle:
            lineas.append('HÁBITOS (últimos 7 días):')
            for h in detalle:
                racha_str = f"racha {h['racha']}d" if h['racha'] > 0 else "racha rota"
                fallados = h['fallados_semana']
                fallados_str = f" | fallado días: {fallados}" if fallados else " | sin fallos"
                lineas.append(
                    f"  - {h['nombre']}: {h['pct_semana']}% — {racha_str}{fallados_str}"
                )
        elif vital.get('habitos_pct') is not None:
            lineas.append(f"HÁBITOS: {vital['habitos_pct']}% cumplimiento últimos 7 días.")

        tareas_pct = vital.get('tareas_hoy_pct')
        if tareas_pct is not None:
            lineas.append(f"TAREAS HOY: {tareas_pct}% completadas.")

        if vital.get('friccion_detectada'):
            lineas.append("⚠ FRICCIÓN DETECTADA: alta aspiración AM con baja ejecución de hábitos.")

        # Hábitos negativos e impulsos
        hab_neg = vital.get('habitos_negativos', [])
        if hab_neg:
            lineas.append('HÁBITOS NEGATIVOS:')
            for h in hab_neg:
                racha_str = f"racha {h['racha']}d sin recaer" if h['racha'] > 0 else "racha rota"
                tasa = f" | éxito {h['tasa_exito']}%" if h['tasa_exito'] is not None else ''
                gatillo = f" | gatillo: {h['emocion_gatillo']}" if h['emocion_gatillo'] else ''
                cediste = f" | cedió {h['cediste_semana']}x esta semana" if h['cediste_semana'] else ''
                lineas.append(f"  - {h['nombre']}: {racha_str}{tasa}{gatillo}{cediste}")

        impulsos = vital.get('impulsos_semana')
        if impulsos and impulsos['total'] > 0:
            lineas.append(
                f"IMPULSOS semana: {impulsos['total']} total — "
                f"resistió {impulsos['resististe']}, cedió {impulsos['cediste']}."
                + (f" Emociones: {', '.join(impulsos['emociones'])}." if impulsos['emociones'] else '')
            )

        rev = vital.get('revision_semanal')
        if rev and any(rev.values()):
            if rev.get('obstaculo_principal'):
                lineas.append(f"Obstáculo semana: {rev['obstaculo_principal'][:120]}")
            if rev.get('aprendizaje_principal'):
                lineas.append(f"Aprendizaje semana: {rev['aprendizaje_principal'][:120]}")

        rev_mes = vital.get('revision_mes')
        if rev_mes:
            if rev_mes.get('logro'):
                lineas.append(f"Logro del mes: {rev_mes['logro'][:120]}")
            if rev_mes.get('aprendizaje'):
                lineas.append(f"Aprendizaje del mes: {rev_mes['aprendizaje'][:120]}")
    elif datos_extra.get('diario_texto', '').strip():
        lineas += ['', '── DIARIO RECIENTE ──', datos_extra['diario_texto'][:600]]

    # ── TONO: Espejo Crudo si hay fricción ───────────────────────────────────
    vital = datos_extra.get('vital', {})
    if vital.get('friccion_detectada'):
        lineas += [
            '',
            "MODO ESPEJO CRUDO: hay discrepancia real entre intención y ejecución.",
            "Habla sin suavizar. Refleja la contradicción directamente.",
            "Sin metáforas que amortigüen. Sin ternura hoy. La verdad sin anestesia.",
            "Sigue siendo JOI — pero como espejo, no como acompañante.",
        ]
        cierre = (
            "Recuerda: [SILENCE] si no hay síntesis valiosa. "
            "Si hablas: máximo 3 frases. Espejo Crudo activo — sin suavizar."
        )
    else:
        cierre = (
            "Recuerda: [SILENCE] si no hay síntesis valiosa. Si hablas: máximo 3 frases, "
            "voz de testigo — observas, no mandas."
        )

    lineas += ['', cierre]
    return '\n'.join(lineas)


def generar_sintesis_joi(cliente) -> "MensajeJOI | None":
    """
    Ciclo autónomo de síntesis: JOI decide si tiene algo que decir.
    Devuelve MensajeJOI creado, o None si JOI eligió [SILENCE].
    """
    from joi.models import MensajeJOI

    try:
        ctx = construir_contexto(cliente)
        vital = _sintetizador_contexto_vital(cliente.user)
        diario_texto = _leer_diario_reciente(cliente.user)
        datos_extra = {'diario_texto': diario_texto, 'vital': vital}

        prompt = _bloque_memoria(ctx) + _bloque_manual(cliente.user) + _prompt_sintesis(ctx, datos_extra)
        texto = _llamar_haiku_sintesis(prompt)

        if texto is None:
            logger.info(f"[JOI síntesis] {cliente.user.username} → [SILENCE]")
            return None

        msg = MensajeJOI.objects.create(
            user=cliente.user,
            trigger='sintesis_joi',
            mensaje=texto,
            contexto={**ctx, 'diario_texto': diario_texto[:300] if diario_texto else ''},
        )
        from django.core.cache import cache
        cache.delete(f'joi_ctx_{cliente.user_id}')
        logger.info(f"[JOI síntesis] {cliente.user.username} → mensaje generado (id={msg.id})")

        try:
            extraer_entidades_simbiosis(cliente.user)
        except Exception:
            pass

        try:
            generar_tema_abierto(cliente.user, msg)
        except Exception:
            pass

        return msg

    except Exception as e:
        logger.error(f"[JOI] generar_sintesis_joi falló: {e}", exc_info=True)
        return None


def get_mensaje_pendiente(user) -> "MensajeJOI | None":
    """Devuelve el mensaje JOI más reciente no leído."""
    from joi.models import MensajeJOI
    return MensajeJOI.objects.filter(user=user, leido=False).first()


def marcar_leido(mensaje_id: int, user) -> bool:
    from joi.models import MensajeJOI
    updated = MensajeJOI.objects.filter(id=mensaje_id, user=user).update(leido=True)
    return updated > 0
