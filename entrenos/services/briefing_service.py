from datetime import date, timedelta


def _get_rpe_bias(cliente):
    """
    Devuelve el sesgo RPE del usuario desde sus sesiones Hyrox.
    bias > 0 → sobreestima (dice 8, es 6). bias < 0 → subestima.
    Retorna 0.0 si no hay datos suficientes.
    """
    try:
        from hyrox.models import HyroxObjective
        from hyrox.training_engine import RPECalibrator
        obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if not obj:
            return 0.0
        info = RPECalibrator.get_bias(obj)
        if info['nivel'] == 'insuficiente':
            return 0.0
        return info['bias']
    except Exception:
        return 0.0


def necesita_deload_gym(cliente, hoy=None):
    """
    Retorna True si el cliente acumula suficiente fatiga para una semana de descarga.
    Criterio A: RPE medio ≥ 8.5 últimas 2 semanas (≥4 sesiones) Y RPE ≥ 8.0 las 2 semanas previas.
    Criterio B: Energía media ≤ 3.5 últimas 2 semanas (≥3 sesiones).
    """
    from entrenos.models import EntrenoRealizado, EjercicioRealizado

    hoy = hoy or date.today()
    hace_14 = hoy - timedelta(days=14)
    hace_28 = hoy - timedelta(days=28)

    recientes = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__range=(hace_14, hoy)
    ).prefetch_related('ejercicios_realizados')

    if recientes.count() < 3:
        return False

    rpes_rec = [
        float(ej.rpe)
        for e in recientes
        for ej in e.ejercicios_realizados.all()
        if ej.rpe is not None
    ]
    rpe_rec = sum(rpes_rec) / len(rpes_rec) if rpes_rec else None

    energias = [e.energia_pre_sesion for e in recientes if e.energia_pre_sesion is not None]
    energia_media = sum(energias) / len(energias) if energias else None

    # Criterio B: energía crónicamente baja
    if energia_media is not None and energia_media <= 3.5 and recientes.count() >= 3:
        return True

    # Aplicar calibración personal de RPE (sesgo detectado desde sesiones Hyrox)
    bias = _get_rpe_bias(cliente)
    # bias > 0 → sobreestima: corregir restando el sesgo
    def _rpe_calibrado(rpe_raw):
        return rpe_raw - bias if abs(bias) >= 1.0 else rpe_raw

    # Criterio A: RPE calibrado alto 2 semanas seguidas
    rpe_rec_cal = _rpe_calibrado(rpe_rec) if rpe_rec is not None else None
    if rpe_rec_cal is not None and rpe_rec_cal >= 8.5 and recientes.count() >= 4:
        previas = EntrenoRealizado.objects.filter(
            cliente=cliente, fecha__range=(hace_28, hace_14)
        ).prefetch_related('ejercicios_realizados')
        rpes_prev = [
            float(ej.rpe)
            for e in previas
            for ej in e.ejercicios_realizados.all()
            if ej.rpe is not None
        ]
        rpe_prev = sum(rpes_prev) / len(rpes_prev) if rpes_prev else None
        if rpe_prev is not None and _rpe_calibrado(rpe_prev) >= 8.0:
            return True

    return False


def get_briefing_gym(cliente, ejercicios_planificados, fecha):
    """
    Genera el contenido del briefing pre-sesión de gym.
    Devuelve un dict con mensajes del entrenador, estado físico y alertas por ejercicio.
    """
    from entrenos.models import (
        EntrenoRealizado, EjercicioRealizado, GymDecisionLog,
    )

    hoy = fecha or date.today()
    dos_semanas = hoy - timedelta(days=14)
    tres_semanas = hoy - timedelta(days=21)

    nombres_hoy = [e.get('nombre', '') for e in ejercicios_planificados if e.get('nombre')]

    # ── Estado físico reciente ─────────────────────────────────────
    entrenos_recientes = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__range=(dos_semanas, hoy)
    ).prefetch_related('ejercicios_realizados')

    rpes = [
        float(ej.rpe)
        for e in entrenos_recientes
        for ej in e.ejercicios_realizados.all()
        if ej.rpe is not None
    ]
    rpe_medio = round(sum(rpes) / len(rpes), 1) if rpes else None

    energias = [
        e.energia_pre_sesion for e in entrenos_recientes
        if e.energia_pre_sesion is not None
    ]
    energia_media = round(sum(energias) / len(energias), 1) if energias else None

    num_sesiones_recientes = entrenos_recientes.count()

    # ── Alertas por ejercicio ──────────────────────────────────────
    alertas_por_ejercicio = {}
    for nombre in nombres_hoy:
        alertas = []

        # Estancamiento
        if GymDecisionLog.objects.filter(
            cliente=cliente,
            ejercicio__iexact=nombre,
            accion='cambiar_variante',
            motivo__icontains='Sin progresión',
            fecha_creacion__date__gte=tres_semanas,
        ).exists():
            alertas.append({'tipo': 'estancado', 'icono': '⚡', 'texto': 'Sin progresión en 3 sesiones'})

        # Tope de máquina
        tope_ej = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            nombre_ejercicio__iexact=nombre,
            es_tope_maquina=True,
            entreno__fecha__gte=dos_semanas,
        ).order_by('-entreno__fecha').first()
        if tope_ej:
            reps_tope = int(tope_ej.repeticiones or 0)
            alertas.append({'tipo': 'tope', 'icono': '🔝', 'texto': f'Tope de máquina — mismo peso, apunta a {reps_tope + 1} reps'})

        # Técnica comprometida reciente
        from entrenos.models import SerieRealizada, EjercicioBase
        ej_base = EjercicioBase.objects.filter(nombre__iexact=nombre).first()
        if ej_base:
            tecnica_comprometida = SerieRealizada.objects.filter(
                entreno__cliente=cliente,
                ejercicio=ej_base,
                tecnica_calidad='comprometida',
                entreno__fecha__gte=dos_semanas,
            ).exists()
            if tecnica_comprometida:
                alertas.append({'tipo': 'tecnica', 'icono': '⚠️', 'texto': 'Técnica comprometida recientemente — prioriza forma sobre peso'})

        # Molestia reciente en zona relacionada
        molestia_ej = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            nombre_ejercicio__iexact=nombre,
            molestia_reportada=True,
            entreno__fecha__gte=tres_semanas,
        ).order_by('-entreno__fecha').first()
        if molestia_ej and molestia_ej.molestia_zona:
            alertas.append({'tipo': 'molestia', 'icono': '🩹', 'texto': f'Molestia en {molestia_ej.molestia_zona} reportada — vigila el rango de movimiento'})

        if alertas:
            alertas_por_ejercicio[nombre] = alertas

    # ── Mensajes del entrenador ────────────────────────────────────
    mensajes = []

    # Estado general basado en RPE
    if rpe_medio is not None:
        if rpe_medio >= 8.5:
            mensajes.append({
                'icono': '🔥',
                'tipo': 'carga',
                'texto': f'Llevas 2 semanas con RPE medio {rpe_medio} — sesión intensa. Hoy para en RIR 2, no vayas al fallo.',
            })
        elif rpe_medio <= 6.0:
            mensajes.append({
                'icono': '⚡',
                'tipo': 'carga',
                'texto': f'RPE medio {rpe_medio} las últimas 2 semanas — tienes margen. Puedes intentar subir peso en el primer ejercicio.',
            })

    # Energía baja
    if energia_media is not None and energia_media <= 4:
        mensajes.append({
            'icono': '😴',
            'tipo': 'energia',
            'texto': f'Energía media {energia_media}/10 esta semana — reduce 1 serie por ejercicio si notas fatiga acumulada.',
        })

    # Ejercicios estancados hoy
    estancados_hoy = [n for n in nombres_hoy if any(
        a['tipo'] == 'estancado' for a in alertas_por_ejercicio.get(n, [])
    )]
    if estancados_hoy:
        nombres_str = ', '.join(estancados_hoy[:2])
        mensajes.append({
            'icono': '📊',
            'tipo': 'estancamiento',
            'texto': f'{nombres_str}: sin progresión en 3 sesiones. Prueba cambiar el tempo (3-1-2) o el rango de reps.',
        })

    # Técnica comprometida reciente en ejercicios de hoy
    tecnica_hoy = [n for n in nombres_hoy if any(
        a['tipo'] == 'tecnica' for a in alertas_por_ejercicio.get(n, [])
    )]
    if tecnica_hoy:
        nombres_str = ', '.join(tecnica_hoy[:2])
        mensajes.append({
            'icono': '⚠️',
            'tipo': 'tecnica',
            'texto': f'{nombres_str}: técnica comprometida la última vez. Baja el ego — misma carga, mejor ejecución.',
        })

    # Topes con sugerencia de peso
    topes_hoy = [n for n in nombres_hoy if any(
        a['tipo'] == 'tope' for a in alertas_por_ejercicio.get(n, [])
    )]
    if topes_hoy:
        nombres_str = ', '.join(topes_hoy[:2])
        mensajes.append({
            'icono': '🔝',
            'tipo': 'tope',
            'texto': f'{nombres_str}: llegaste al tope de la máquina. Mismo peso — intenta hacer una rep más.',
        })

    # Calibración RPE personal
    bias = _get_rpe_bias(cliente)
    if abs(bias) >= 1.5:
        dir_bias = "sobreestimas" if bias > 0 else "subestimas"
        ajuste = "el plan sube los umbrales de carga" if bias > 0 else "el plan baja los umbrales de carga"
        mensajes.append({
            'icono': '⚖️',
            'tipo': 'ok',
            'texto': (
                f"Tu escala RPE: {dir_bias} el esfuerzo en ~{abs(bias):.1f} puntos vs tu FC real. "
                f"{ajuste.capitalize()} para compensar."
            ),
        })

    # Deload automático
    deload = necesita_deload_gym(cliente, hoy)
    if deload:
        razon = 'energía crónicamente baja' if (energia_media and energia_media <= 3.5) else f'RPE medio {rpe_medio} durante 4+ semanas'
        mensajes.insert(0, {
            'icono': '🔄',
            'tipo': 'carga',
            'texto': f'SEMANA DE DESCARGA — {razon}. El volumen se ha reducido automáticamente. Recupera sin culpa.',
        })

    # Sin alertas — sesión limpia
    if not mensajes:
        if num_sesiones_recientes >= 3:
            mensajes.append({
                'icono': '✅',
                'tipo': 'ok',
                'texto': 'Sin alertas activas. Sigue el plan — todo en orden.',
            })

    # ── Comparativa temporal por ejercicio ────────────────────────
    comparativas = _comparativa_temporal(cliente, nombres_hoy, hoy)

    return {
        'mensajes': mensajes,
        'rpe_medio': rpe_medio,
        'energia_media': energia_media,
        'num_sesiones_recientes': num_sesiones_recientes,
        'alertas_por_ejercicio': alertas_por_ejercicio,
        'comparativas': comparativas,
        'necesita_deload': deload,
    }


def _comparativa_temporal(cliente, nombres, hoy):
    """
    Para cada ejercicio de la sesión, compara el mejor peso del último mes
    con el del mes anterior. Devuelve lista de mejoras > 2%.
    """
    from entrenos.models import EjercicioRealizado
    from django.db.models import Max

    hace_30 = hoy - timedelta(days=30)
    hace_60 = hoy - timedelta(days=60)

    comparativas = []
    for nombre in nombres:
        qs = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            nombre_ejercicio__iexact=nombre,
            peso_kg__gt=0,
        )
        mes_actual = qs.filter(
            entreno__fecha__range=(hace_30, hoy)
        ).aggregate(mx=Max('peso_kg'))['mx']

        mes_anterior = qs.filter(
            entreno__fecha__range=(hace_60, hace_30)
        ).aggregate(mx=Max('peso_kg'))['mx']

        if not mes_actual or not mes_anterior:
            continue

        pct = round((float(mes_actual) - float(mes_anterior)) / float(mes_anterior) * 100, 1)
        if pct >= 2:
            comparativas.append({
                'ejercicio': nombre,
                'pct': pct,
                'peso_antes': float(mes_anterior),
                'peso_ahora': float(mes_actual),
            })

    comparativas.sort(key=lambda x: x['pct'], reverse=True)
    return comparativas[:3]  # máximo 3 para no saturar
