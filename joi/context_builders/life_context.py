"""
Contexto de vida: lesión activa, eudaimonia, gestos/hábitos,
semáforo de intención, bio signals del checkin y cierre de ayer.

Nota: recibe acwr como parámetro porque la detección de fatiga extragym
combina ACWR (calculado en activity_context) con señales vitales.
"""
from datetime import date, timedelta


def build_life_context(cliente, hoy: date, semana_reciente: date, acwr=None) -> dict:
    ctx = {}

    # ── 7. LESIÓN ACTIVA ─────────────────────────────────────────────────────
    try:
        from hyrox.models import UserInjury
        lesion = UserInjury.objects.filter(
            cliente=cliente, fase__in=['AGUDA', 'SUB_AGUDA', 'RETORNO']
        ).first()
        if lesion:
            ctx['lesion'] = {'zona': lesion.zona_afectada, 'fase': lesion.fase}
    except Exception:
        pass

    # ── 10. EUDAIMONIA ───────────────────────────────────────────────────────
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

    # ── 10.5 GESTOS ──────────────────────────────────────────────────────────
    try:
        from diario.models import ProsocheMes, ProsocheHabito, ProsocheHabitoDia, TriggerHabito
        mes_gestos = ProsocheMes.objects.filter(
            usuario=cliente.user,
            mes=hoy.strftime('%B'),
            año=hoy.year,
        ).first()
        if mes_gestos:
            dias_ventana = list(range(max(1, hoy.day - 6), hoy.day + 1))
            dias_previos = list(range(max(1, hoy.day - 13), max(1, hoy.day - 6)))
            gestos_señales = []

            for habito in ProsocheHabito.objects.filter(
                prosoche_mes=mes_gestos, tipo_habito='positivo'
            ):
                presencias = ProsocheHabitoDia.objects.filter(
                    habito=habito, dia__in=dias_ventana, completado=True
                ).count()
                presencias_previas = ProsocheHabitoDia.objects.filter(
                    habito=habito, dia__in=dias_previos, completado=True
                ).count() if dias_previos else 0

                if presencias >= 4:
                    gestos_señales.append({
                        'nombre': habito.nombre,
                        'señal': 'aparecio_varias',
                        'presencias': presencias,
                    })
                elif presencias == 0 and presencias_previas >= 3:
                    ultima = ProsocheHabitoDia.objects.filter(
                        habito=habito, completado=True, dia__lte=hoy.day
                    ).order_by('-dia').first()
                    dias_sin = (hoy.day - ultima.dia) if ultima else len(dias_ventana)
                    if dias_sin >= 3:
                        gestos_señales.append({
                            'nombre': habito.nombre,
                            'señal': 'ausente',
                            'dias_sin': dias_sin,
                        })

            for habito in ProsocheHabito.objects.filter(
                prosoche_mes=mes_gestos, tipo_habito='negativo'
            ):
                reapariciones = TriggerHabito.objects.filter(
                    habito=habito,
                    fecha__gte=semana_reciente,
                    fecha__lte=hoy,
                    cediste=True,
                ).count()
                if reapariciones >= 1:
                    gestos_señales.append({
                        'nombre': habito.nombre,
                        'señal': 'reaparecio',
                        'veces': reapariciones,
                    })

            if gestos_señales:
                ctx['gestos_señales'] = gestos_señales[:3]
    except Exception:
        pass

    # ── 11. SEMÁFORO DE INTENCIÓN ────────────────────────────────────────────
    try:
        from core.daily_decision import DailyDecisionEngine
        estado_hoy = DailyDecisionEngine.get_estado_hoy(cliente)
        ctx['semaforo'] = estado_hoy
    except Exception:
        pass

    # ── 12. BIO SIGNALS ──────────────────────────────────────────────────────
    try:
        from core.bio_context import BioContextProvider
        bio = BioContextProvider.get_bio_signals(cliente)
        if bio['has_data']:
            ctx['bio_signals'] = bio

            energia_baja = bio['energia'] is not None and bio['energia'] <= 4
            sueno_malo   = bio['horas_sueno'] is not None and bio['horas_sueno'] < 6
            if acwr is not None and acwr < 0.8 and (energia_baja or sueno_malo):
                ctx['fatiga_extragym'] = {
                    'acwr':    acwr,
                    'energia': bio['energia'],
                    'sueno':   bio['horas_sueno'],
                    'fc':      bio['fc_reposo'],
                    'hrv':     bio['hrv_ms'],
                }
    except Exception:
        pass

    # ── 13. CIERRE DE AYER ───────────────────────────────────────────────────
    try:
        from diario.models import ProsocheDiario, ProsocheMes, SeguimientoVires
        ayer = hoy - timedelta(days=1)
        mes_ayer = ProsocheMes.objects.filter(
            usuario=cliente.user,
            mes=ayer.strftime('%B'),
            año=ayer.year,
        ).first()
        if mes_ayer:
            entrada_ayer = ProsocheDiario.objects.filter(
                prosoche_mes=mes_ayer, fecha=ayer
            ).first()
            if entrada_ayer and entrada_ayer.reflexiones_dia:
                soberania = ''
                tareas = entrada_ayer.tareas_dia or []
                for t in tareas:
                    if isinstance(t, dict) and t.get('es_soberania'):
                        soberania = t.get('texto', '')
                        break
                vires_ayer = SeguimientoVires.objects.filter(
                    usuario=cliente.user, fecha=ayer
                ).first()
                ctx['cierre_ayer'] = {
                    'texto':        entrada_ayer.reflexiones_dia[:600],
                    'estado_animo': entrada_ayer.estado_animo,
                    'etiquetas':    entrada_ayer.etiquetas or '',
                    'soberania':    soberania,
                    'friccion_no':  vires_ayer.nivel_estres if vires_ayer else None,
                }
    except Exception:
        pass

    return ctx
