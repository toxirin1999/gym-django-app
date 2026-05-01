from datetime import date, timedelta


def get_resumen_semanal_gym(cliente):
    """
    Genera el resumen "qué aprendió el plan" de la semana anterior (lun–dom).
    Devuelve una lista de items con tipo, icono y texto, o [] si no hay datos.
    """
    from entrenos.models import (
        EntrenoRealizado, EjercicioRealizado, SerieRealizada, GymDecisionLog,
    )

    hoy = date.today()
    # Semana pasada lunes–domingo
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    domingo = lunes + timedelta(days=6)

    entrenos = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__range=(lunes, domingo)
    ).prefetch_related('ejercicios_realizados', 'series')

    if not entrenos.exists():
        return []

    items = []
    meta = {
        'lunes': lunes,
        'domingo': domingo,
    }

    # ── 1. Número de sesiones + volumen total ──────────────────────
    num_sesiones = entrenos.count()
    plural = 'sesiones' if num_sesiones != 1 else 'sesión'
    volumen_total = sum(
        float(e.volumen_total_kg or 0) for e in entrenos
    )
    volumen_str = f' · {round(volumen_total):,} kg movidos' if volumen_total > 0 else ''
    items.append({
        'tipo': 'sesiones',
        'icono': '📅',
        'texto': f'{num_sesiones} {plural} completadas{volumen_str}',
        'color': 'ok',
        'meta': meta,
    })

    # ── 2. Técnica comprometida ────────────────────────────────────
    series_comprometidas = SerieRealizada.objects.filter(
        entreno__in=entrenos, tecnica_calidad='comprometida'
    ).values('ejercicio__nombre').distinct()
    ejercicios_con_tecnica_comprometida = [s['ejercicio__nombre'] for s in series_comprometidas if s['ejercicio__nombre']]

    if ejercicios_con_tecnica_comprometida:
        nombres = ', '.join(ejercicios_con_tecnica_comprometida[:3])
        items.append({
            'tipo': 'tecnica',
            'icono': '⚠️',
            'texto': f'Técnica comprometida en {nombres} — peso congelado para consolidar.',
            'color': 'warn',
        })
    else:
        series_con_tecnica = SerieRealizada.objects.filter(
            entreno__in=entrenos, tecnica_calidad__isnull=False
        ).count()
        if series_con_tecnica > 0:
            items.append({
                'tipo': 'tecnica',
                'icono': '✅',
                'texto': 'Técnica limpia toda la semana — el plan puede progresar.',
                'color': 'ok',
            })

    # ── 3. Topes de máquina ────────────────────────────────────────
    topes = EjercicioRealizado.objects.filter(
        entreno__in=entrenos, es_tope_maquina=True
    ).values_list('nombre_ejercicio', flat=True).distinct()
    topes = list(topes)
    if topes:
        nombres = ', '.join(topes[:3])
        items.append({
            'tipo': 'tope',
            'icono': '🔝',
            'texto': f'Tope de máquina en {nombres} — próxima sesión progresa por reps.',
            'color': 'info',
        })

    # ── 4. Molestias ───────────────────────────────────────────────
    molestias = EjercicioRealizado.objects.filter(
        entreno__in=entrenos, molestia_reportada=True
    ).exclude(molestia_zona='').values_list('molestia_zona', flat=True)
    zonas = list(set(molestias))
    if zonas:
        zonas_str = ', '.join(zonas[:3])
        items.append({
            'tipo': 'molestia',
            'icono': '🩹',
            'texto': f'Molestia reportada en {zonas_str} — vigilar la semana próxima.',
            'color': 'warn',
        })

    # ── 5. RPE medio ───────────────────────────────────────────────
    rpes = [
        float(ej.rpe) for e in entrenos
        for ej in e.ejercicios_realizados.all()
        if ej.rpe is not None
    ]
    if rpes:
        rpe_medio = round(sum(rpes) / len(rpes), 1)
        if rpe_medio >= 8.5:
            items.append({
                'tipo': 'rpe',
                'icono': '🔥',
                'texto': f'RPE medio {rpe_medio} — semana intensa. Prioriza recuperación.',
                'color': 'warn',
            })
        elif rpe_medio <= 6.0:
            items.append({
                'tipo': 'rpe',
                'icono': '⚡',
                'texto': f'RPE medio {rpe_medio} — margen para subir intensidad la próxima semana.',
                'color': 'ok',
            })

    # ── 6. Energía pre-sesión ──────────────────────────────────────
    energias = [e.energia_pre_sesion for e in entrenos if e.energia_pre_sesion is not None]
    if energias:
        energia_media = round(sum(energias) / len(energias), 1)
        if energia_media <= 4:
            items.append({
                'tipo': 'energia',
                'icono': '😴',
                'texto': f'Energía pre-sesión media: {energia_media}/10 — semana de fatiga acumulada.',
                'color': 'warn',
            })
        elif energia_media >= 7:
            items.append({
                'tipo': 'energia',
                'icono': '💪',
                'texto': f'Energía pre-sesión media: {energia_media}/10 — semana de buena disposición.',
                'color': 'ok',
            })

    # ── 7. Decisiones tomadas por el plan ─────────────────────────
    decisiones = GymDecisionLog.objects.filter(
        cliente=cliente,
        fecha_creacion__date__range=(lunes, domingo),
    ).order_by('-fecha_creacion')[:3]
    for dec in decisiones:
        items.append({
            'tipo': 'decision',
            'icono': '🧠',
            'texto': f'{dec.ejercicio}: {dec.motivo}',
            'color': 'info',
        })

    return items
