from datetime import date, timedelta


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
            peso_sugerido = round(float(tope_ej.peso_kg or 0) + 2.5, 1)
            alertas.append({'tipo': 'tope', 'icono': '🔝', 'texto': f'Tope alcanzado — prueba {peso_sugerido} kg'})

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
            'texto': f'{nombres_str}: llegaste al tope la última vez. Hoy sube el peso (+2.5 kg) y baja las reps.',
        })

    # Sin alertas — sesión limpia
    if not mensajes:
        if num_sesiones_recientes >= 3:
            mensajes.append({
                'icono': '✅',
                'tipo': 'ok',
                'texto': 'Sin alertas activas. Sigue el plan — todo en orden.',
            })

    return {
        'mensajes': mensajes,
        'rpe_medio': rpe_medio,
        'energia_media': energia_media,
        'num_sesiones_recientes': num_sesiones_recientes,
        'alertas_por_ejercicio': alertas_por_ejercicio,
    }
