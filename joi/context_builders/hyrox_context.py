"""
Contexto Hyrox: objetivo activo, readiness, sesiones recientes,
progreso vs estándares y comparativa temporal por estación.
"""
from datetime import date, timedelta


def build_hyrox_context(cliente, hoy: date, semana_reciente: date) -> dict:
    ctx = {}

    # ── 9. HYROX ─────────────────────────────────────────────────────────────
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
                    'fecha':   str(ultima_hyrox.fecha),
                    'titulo':  ultima_hyrox.titulo or '',
                    'rpe':     ultima_hyrox.rpe_global,
                    'minutos': ultima_hyrox.tiempo_total_minutos,
                }
                if (hoy - ultima_hyrox.fecha).days <= 14:
                    ctx['tsb_hyrox'] = ultima_hyrox.tsb

            ctx['sesiones_hyrox_semana'] = HyroxSession.objects.filter(
                objective=objetivo_hyrox,
                estado='completado',
                fecha__gte=semana_reciente,
            ).count()

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

            scores_all = list(
                HyroxReadinessLog.objects.filter(objective=objetivo_hyrox)
                .order_by('-fecha').values_list('score', flat=True)[:14]
            )
            if scores_all:
                score_actual = scores_all[0]
                plateau = 0
                for s in scores_all:
                    if abs(s - score_actual) <= 2:
                        plateau += 1
                    else:
                        break
                ctx['readiness_plateau_dias'] = plateau

                if len(scores_all) >= 6:
                    media_reciente = sum(scores_all[:3]) / 3
                    media_anterior = sum(scores_all[3:6]) / 3
                    diff = media_reciente - media_anterior
                    ctx['readiness_trend'] = (
                        'subiendo' if diff > 3
                        else 'bajando' if diff < -3
                        else 'estable'
                    )
                    ctx['readiness_trend_puntos'] = round(diff, 1)

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

            ctx['readiness_benchmark']    = benchmark
            ctx['readiness_fase']         = fase_nombre
            ctx['readiness_vs_benchmark'] = (ctx.get('readiness_hyrox') or 0) - benchmark

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

    # ── 14. COMPARATIVA TEMPORAL (estaciones Hyrox) ───────────────────────────
    try:
        from hyrox.models import HyroxActivity, HyroxObjective
        _obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if _obj:
            _ESTACIONES = ['Sled Push', 'Sled Pull', 'Farmers Carry',
                           'Sandbag Lunges', 'Wall Balls', 'Burpees Broad Jump']
            comparativa = []
            for _nombre in _ESTACIONES:
                _acts = list(
                    HyroxActivity.objects
                    .filter(sesion__objective=_obj,
                            nombre_ejercicio__icontains=_nombre)
                    .order_by('sesion__fecha')
                )
                _acts = [
                    a for a in _acts
                    if a.data_metricas
                    and not a.data_metricas.get('planificado')
                    and a.data_metricas.get('peso_kg')
                ]
                if len(_acts) < 4:
                    continue
                _mitad   = len(_acts) // 2
                _primera = _acts[:_mitad]
                _segunda = _acts[_mitad:]
                _max_ant = max(float(a.data_metricas['peso_kg']) for a in _primera)
                _max_rec = max(float(a.data_metricas['peso_kg']) for a in _segunda)
                if _max_ant <= 0:
                    continue
                _pct = round((_max_rec - _max_ant) / _max_ant * 100, 1)
                if abs(_pct) >= 3:
                    comparativa.append({
                        'estacion':    _nombre,
                        'anterior_kg': _max_ant,
                        'reciente_kg': _max_rec,
                        'cambio_pct':  _pct,
                        'n_sesiones':  len(_acts),
                    })
            if comparativa:
                comparativa.sort(key=lambda x: abs(x['cambio_pct']), reverse=True)
                ctx['comparativa_temporal'] = comparativa[:4]
    except Exception:
        pass

    return ctx
