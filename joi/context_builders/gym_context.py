"""
Contexto específico de gym: RPE, energía, PRs, decisiones del plan,
estancamientos, señales semanales y preferencias aprendidas.
"""
from datetime import date, timedelta

from django.db.models import Avg, Count, Q

from entrenos.models import (
    EntrenoRealizado, EjercicioRealizado,
    RecordPersonal, GymDecisionLog,
)


def build_gym_context(cliente, hoy: date, semana_reciente: date) -> dict:
    ctx = {}

    # ── 4. RPE GYM ───────────────────────────────────────────────────────────
    rpe_gym = []
    for i in range(3, -1, -1):
        ini = hoy - timedelta(days=7 * (i + 1))
        fin = hoy - timedelta(days=7 * i)
        entrenos_sem = EntrenoRealizado.objects.filter(cliente=cliente, fecha__range=(ini, fin))
        rpe_avg = EjercicioRealizado.objects.filter(
            entreno__in=entrenos_sem, rpe__isnull=False
        ).aggregate(avg=Avg('rpe'))['avg']
        rpe_gym.append(round(rpe_avg, 1) if rpe_avg else None)
    ctx['rpe_gym_semanas'] = rpe_gym if sum(1 for r in rpe_gym if r is not None) >= 2 else None

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

    # ── 4b. ENERGÍA PRE-SESIÓN ───────────────────────────────────────────────
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

    # ── 5. RÉCORDS PERSONALES ────────────────────────────────────────────────
    ctx['prs_semana'] = list(
        RecordPersonal.objects.filter(
            cliente=cliente, fecha_logrado__gte=semana_reciente
        ).values_list('ejercicio_nombre', flat=True)[:5]
    )

    # ── 6. DECISIONES DEL PLAN GYM ───────────────────────────────────────────
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

    # ── 8b. ESTANCAMIENTOS ACTIVOS ───────────────────────────────────────────
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

    # ── Phase 6.1/7/16 — Gym weekly, multiweek & distribution signals ────────
    try:
        from entrenos.services.analisis_semanal_service import (
            bloque_semanal_para_joi,
            detectar_patron_multisemanal,
            analizar_distribucion_semanal,
        )
        bloque = bloque_semanal_para_joi(cliente)
        if bloque:
            ctx['bloque_semanal_gym'] = bloque
        patron = detectar_patron_multisemanal(cliente)
        if patron:
            ctx['patron_multisemanal_gym'] = patron
        distribucion = analizar_distribucion_semanal(cliente)
        if distribucion:
            ctx['distribucion_semanal_gym'] = distribucion[0]['texto']
    except Exception:
        pass

    # ── 15. PREFERENCIAS DEL PLAN ────────────────────────────────────────────
    try:
        from entrenos.models import PreferenciaPlanAprendida
        prefs = list(
            PreferenciaPlanAprendida.objects.filter(
                cliente=cliente, estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            ).values('tipo', 'descripcion', 'evidencia_count')
        )
        if prefs:
            ctx['preferencias_plan_activas'] = [
                {'tipo': p['tipo'], 'descripcion': p['descripcion'], 'evidencia': p['evidencia_count']}
                for p in prefs
            ]
    except Exception:
        pass

    # ── 16. LECTURA SEMANAL DE MEMORIA + ESTADO JOI ──────────────────────────
    try:
        from entrenos.services.lectura_semanal_service import construir_lectura_semanal_memoria
        lectura = construir_lectura_semanal_memoria(cliente)
        if lectura.get('hay_datos') and lectura.get('texto_joi'):
            ctx['lectura_semanal_memoria'] = lectura['texto_joi']
            ctx['lectura_semanal_senales_no_captadas'] = lectura['senales_no_captadas']
            ctx['lectura_semanal_hipotesis'] = lectura['n_hipotesis_abiertas']
        estado_joi = lectura.get('estado_joi', {})
        if estado_joi:
            ctx['estado_joi_semanal'] = estado_joi.get('estado', 'minima')
            ctx['joi_debe_hablar_semanal'] = estado_joi.get('debe_hablar', False)
            ctx['joi_nota_tono_semanal'] = estado_joi.get('nota_tono', '')
    except Exception:
        pass

    # ── FASE DEL PLAN ACTUAL ─────────────────────────────────────────────────
    try:
        from clientes.models import FaseCliente
        fase_actual = (
            FaseCliente.objects
            .filter(
                cliente=cliente,
            )
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
            .order_by('-fecha_inicio')
            .first()
        )
        if fase_actual:
            dias_en_fase = (hoy - fase_actual.fecha_inicio).days
            fase_info = {
                'tipo': fase_actual.fase,
                'nombre': fase_actual.get_fase_display(),
                'dias_en_fase': dias_en_fase,
                'es_descarga': fase_actual.fase == 'descarga',
            }
            if fase_actual.fecha_fin:
                fase_info['dias_restantes'] = (fase_actual.fecha_fin - hoy).days
            ctx['fase_plan'] = fase_info
    except Exception:
        pass

    return ctx
