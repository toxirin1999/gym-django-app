"""
Agrega las alertas más relevantes del día desde todos los módulos.
Retorna una lista ordenada por prioridad (máx 5 items).
"""
from datetime import date, timedelta


# Niveles: critico > alerta > info > positivo
_NIVEL_ORDEN = {'critico': 0, 'alerta': 1, 'info': 2, 'positivo': 3}


def get_alertas_sistema(cliente):
    alertas = []
    hoy = date.today()
    hace_21 = hoy - timedelta(days=21)
    hace_7 = hoy - timedelta(days=7)

    # ── 1. LESIÓN ACTIVA ─────────────────────────────────────────────────────
    try:
        from hyrox.models import UserInjury
        lesion = UserInjury.objects.filter(cliente=cliente, activa=True).first()
        if lesion:
            from django.urls import reverse
            alertas.append({
                'nivel': 'critico',
                'icono': '🩹',
                'titulo': f'Lesión activa — {lesion.zona_afectada}',
                'texto': f'Fase {lesion.fase}. El plan filtra ejercicios incompatibles automáticamente.',
                'url': reverse('hyrox:reportar_recuperacion', args=[lesion.id]),
                'url_label': 'Gestionar lesión',
            })
    except Exception:
        pass

    # ── 2. DELOAD GYM ACTIVO ─────────────────────────────────────────────────
    try:
        from entrenos.services.briefing_service import necesita_deload_gym
        if necesita_deload_gym(cliente, hoy):
            alertas.append({
                'nivel': 'critico',
                'icono': '🔄',
                'titulo': 'Semana de descarga activa',
                'texto': 'Fatiga acumulada detectada. Volumen reducido en tus sesiones de hoy.',
                'url': None,
            })
    except Exception:
        pass

    # ── 3. FATIGA GYM → HYROX ────────────────────────────────────────────────
    try:
        from hyrox.training_engine import HyroxTrainingEngine
        gym_load = HyroxTrainingEngine._get_gym_external_load(cliente, dias=4)
        if gym_load['fatiga_gym'] == 'Alta':
            parte = 'piernas' if gym_load.get('fatiga_piernas') else 'torso'
            alertas.append({
                'nivel': 'alerta',
                'icono': '⚡',
                'titulo': f'Fatiga gym alta ({parte})',
                'texto': (
                    f'{gym_load["entrenos_count"]} sesiones de gym · RPE {gym_load["rpe_medio_gym"]}. '
                    f'Reduce la carga en {"carrera y Wall Balls" if parte == "piernas" else "SkiErg y Remo"} hoy.'
                ),
                'url': None,
            })
    except Exception:
        pass

    # ── 4. ESTANCAMIENTO GYM ─────────────────────────────────────────────────
    try:
        from entrenos.models import GymDecisionLog
        estancados = list(
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='cambiar_variante',
                    motivo__icontains='Sin progresión',
                    fecha_creacion__date__gte=hace_21)
            .values_list('ejercicio', flat=True)
            .distinct()[:2]
        )
        if estancados:
            alertas.append({
                'nivel': 'alerta',
                'icono': '📊',
                'titulo': f'Estancamiento detectado',
                'texto': f'{", ".join(estancados)}: sin progresión en 3 sesiones. Considera cambiar el estímulo.',
                'url': None,
            })
    except Exception:
        pass

    # ── 5. MOLESTIA RECURRENTE ────────────────────────────────────────────────
    try:
        from entrenos.models import GymDecisionLog
        molestias = list(
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='cambiar_variante',
                    motivo__icontains='Molestia',
                    fecha_creacion__date__gte=hace_21)
            .values_list('ejercicio', flat=True)
            .distinct()[:2]
        )
        if molestias:
            alertas.append({
                'nivel': 'alerta',
                'icono': '⚠️',
                'titulo': 'Molestia recurrente',
                'texto': f'{", ".join(molestias)}: molestia reportada en 3+ sesiones. Variante sugerida.',
                'url': None,
            })
    except Exception:
        pass

    # ── 6. ESTANCAMIENTO HYROX ────────────────────────────────────────────────
    try:
        from hyrox.models import HyroxObjective, HyroxActivity
        from hyrox.training_engine import StagnationEngine
        obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if obj:
            _NOMBRE_CANON = {
                'skierg': 'SkiErg', 'sled push': 'Sled Push', 'sled pull': 'Sled Pull',
                'burpee broad jump': 'Burpee Broad Jumps', 'rowing': 'Rowing', 'remo': 'Rowing',
                'farmer': 'Farmers Carry', 'sandbag': 'Sandbag Lunges', 'wall ball': 'Wall Balls',
            }
            _TIPOS = ('hyrox_station', 'ergometro', 'skierg', 'remo')
            _hace_8_semanas = hoy - timedelta(weeks=8)
            acts = (HyroxActivity.objects
                    .filter(sesion__objective=obj, sesion__estado='completado',
                            tipo_actividad__in=_TIPOS,
                            sesion__fecha__gte=_hace_8_semanas)
                    .exclude(data_metricas={})
                    .select_related('sesion').order_by('sesion__fecha'))
            tiempos = {}
            for a in acts:
                t = a.data_metricas.get('tiempo_segundos') or a.data_metricas.get('tiempo_s')
                if not t or int(t) <= 0:
                    continue
                nl = (a.nombre_ejercicio or '').lower()
                c = next((v for k, v in _NOMBRE_CANON.items() if k in nl), None)
                if c:
                    tiempos.setdefault(c, []).append(int(t))

            stag = StagnationEngine.check(tiempos)
            estancadas = [st for st, info in stag.items()
                          if info.get('estancada') and info.get('sesiones_analizadas', 0) >= 3]
            if estancadas:
                alertas.append({
                    'nivel': 'info',
                    'icono': '🏁',
                    'titulo': f'Estación Hyrox estancada',
                    'texto': f'{estancadas[0]}: sin mejora en 3+ sesiones. Ver sugerencia en dashboard Hyrox.',
                    'url': None,
                })
    except Exception:
        pass

    # ── 7. CALIBRACIÓN RPE ────────────────────────────────────────────────────
    try:
        from hyrox.models import HyroxObjective
        from hyrox.training_engine import RPECalibrator
        obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if obj:
            bias_info = RPECalibrator.get_bias(obj)
            if bias_info['nivel'] == 'severo':
                dir_bias = 'sobreestimas' if bias_info['bias'] > 0 else 'subestimas'
                alertas.append({
                    'nivel': 'info',
                    'icono': '⚖️',
                    'titulo': 'Calibración RPE ajustada',
                    'texto': (
                        f'{dir_bias} el esfuerzo en ~{abs(bias_info["bias"]):.1f} pts vs tu FC real. '
                        f'El plan lo compensa automáticamente.'
                    ),
                    'url': None,
                })
    except Exception:
        pass

    # ── 8. PR RECIENTE (positivo) ─────────────────────────────────────────────
    try:
        from entrenos.models import RecordPersonal
        pr = (RecordPersonal.objects
              .filter(cliente=cliente, superado=False,
                      tipo_record='peso_maximo', fecha_logrado__gte=hace_7)
              .order_by('-valor').first())
        if pr:
            alertas.append({
                'nivel': 'positivo',
                'icono': '🏆',
                'titulo': f'PR esta semana — {pr.ejercicio_nombre}',
                'texto': f'{pr.valor} kg · {pr.fecha_logrado.strftime("%d/%m")}. El plan ha actualizado tu RM.',
                'url': None,
            })
    except Exception:
        pass

    # ── 9. MEJORA MENSUAL (positivo) ──────────────────────────────────────────
    try:
        from entrenos.models import EjercicioRealizado
        from django.db.models import Max
        hace_30 = hoy - timedelta(days=30)
        hace_60 = hoy - timedelta(days=60)
        mejoras = []
        nombres = list(
            EjercicioRealizado.objects
            .filter(entreno__cliente=cliente, entreno__fecha__gte=hace_30, peso_kg__gt=0)
            .values_list('nombre_ejercicio', flat=True).distinct()[:10]
        )
        for nombre in nombres:
            qs = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente, nombre_ejercicio=nombre, peso_kg__gt=0)
            ahora = qs.filter(entreno__fecha__range=(hace_30, hoy)).aggregate(mx=Max('peso_kg'))['mx']
            antes = qs.filter(entreno__fecha__range=(hace_60, hace_30)).aggregate(mx=Max('peso_kg'))['mx']
            if ahora and antes and antes > 0:
                pct = (float(ahora) - float(antes)) / float(antes) * 100
                if pct >= 5:
                    mejoras.append((nombre, round(pct, 1)))
        if mejoras:
            mejoras.sort(key=lambda x: -x[1])
            nombre, pct = mejoras[0]
            alertas.append({
                'nivel': 'positivo',
                'icono': '📈',
                'titulo': f'+{pct}% este mes — {nombre}',
                'texto': 'El plan ha registrado tu progreso y ajustará la carga progresivamente.',
                'url': None,
            })
    except Exception:
        pass

    # Ordenar por prioridad y limitar a 5
    alertas.sort(key=lambda x: _NIVEL_ORDEN.get(x['nivel'], 9))
    return alertas[:5]
