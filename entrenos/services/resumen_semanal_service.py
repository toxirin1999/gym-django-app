from datetime import date, timedelta


def _tipo_record_label(tipo):
    return {
        'peso_maximo': 'peso máximo',
        'one_rep_max': '1RM estimado',
        'reps_maximas': 'reps máximas',
        'volumen_total': 'volumen total',
    }.get(tipo, tipo)


_ACCION_ICONO = {
    'subir_peso':      ('⬆️',  'ok'),
    'subir_reps':      ('📈', 'ok'),
    'mantener':        ('➡️',  'info'),
    'bajar_peso':      ('⬇️',  'warn'),
    'deload':          ('🛌', 'warn'),
    'cambiar_variante': ('🔄', 'warn'),
}


def get_resumen_semanal_gym(cliente):
    """
    Genera el resumen "qué aprendió el plan" de la semana anterior (lun–dom).
    Devuelve una lista de items con tipo, icono y texto, o [] si no hay datos.
    """
    from entrenos.models import (
        EntrenoRealizado, EjercicioRealizado, SerieRealizada, GymDecisionLog,
        RecordPersonal,
    )

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    domingo = lunes + timedelta(days=6)

    entrenos = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__range=(lunes, domingo)
    ).prefetch_related('ejercicios_realizados', 'series')

    if not entrenos.exists():
        return []

    items = []
    meta = {'lunes': lunes, 'domingo': domingo}

    # ── 1. Sesiones + volumen ──────────────────────────────────────
    num_sesiones = entrenos.count()
    plural = 'sesiones' if num_sesiones != 1 else 'sesión'
    volumen_total = sum(float(e.volumen_total_kg or 0) for e in entrenos)
    volumen_str = f' · {round(volumen_total):,} kg movidos' if volumen_total > 0 else ''
    items.append({
        'tipo': 'sesiones',
        'icono': '📅',
        'texto': f'{num_sesiones} {plural} completadas{volumen_str}',
        'color': 'ok',
        'meta': meta,
    })

    # ── 2. Récords personales ─────────────────────────────────────
    records_semana = RecordPersonal.objects.filter(
        cliente=cliente,
        fecha_logrado__range=(lunes, domingo),
    ).order_by('ejercicio_nombre', 'tipo_record')

    if records_semana.exists():
        por_ejercicio = {}
        for r in records_semana:
            por_ejercicio.setdefault(r.ejercicio_nombre, []).append(
                f'{_tipo_record_label(r.tipo_record)}: {r.valor}'
            )
        for ejercicio, detalles in list(por_ejercicio.items())[:3]:
            items.append({
                'tipo': 'record',
                'icono': '🏆',
                'texto': f'Nuevo PR en {ejercicio} — {" · ".join(detalles)}',
                'color': 'ok',
            })

    # ── 3. Técnica comprometida ───────────────────────────────────
    series_comprometidas = SerieRealizada.objects.filter(
        entreno__in=entrenos, tecnica_calidad='comprometida'
    ).values('ejercicio__nombre').distinct()
    ejercicios_con_tecnica_comprometida = [
        s['ejercicio__nombre'] for s in series_comprometidas if s['ejercicio__nombre']
    ]

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

    # ── 4. Topes de máquina ───────────────────────────────────────
    topes = list(
        EjercicioRealizado.objects.filter(
            entreno__in=entrenos, es_tope_maquina=True
        ).values_list('nombre_ejercicio', flat=True).distinct()
    )
    topes_set = {n.lower() for n in topes}
    if topes:
        nombres = ', '.join(topes[:3])
        items.append({
            'tipo': 'tope',
            'icono': '🔝',
            'texto': f'Tope de máquina en {nombres} — próxima sesión progresa por reps.',
            'color': 'info',
        })

    # ── 5. Molestias ──────────────────────────────────────────────
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

    # ── 6. RPE medio — siempre visible ────────────────────────────
    rpes = [
        float(ej.rpe) for e in entrenos
        for ej in e.ejercicios_realizados.all()
        if ej.rpe is not None
    ]
    if rpes:
        rpe_medio = round(sum(rpes) / len(rpes), 1)
        if rpe_medio >= 8.5:
            icono_rpe, color_rpe = '🔥', 'warn'
            msg_rpe = f'RPE medio {rpe_medio} — semana intensa. Prioriza recuperación.'
        elif rpe_medio <= 6.0:
            icono_rpe, color_rpe = '⚡', 'ok'
            msg_rpe = f'RPE medio {rpe_medio} — margen para subir intensidad la próxima semana.'
        else:
            icono_rpe, color_rpe = '📊', 'info'
            msg_rpe = f'RPE medio {rpe_medio} — carga dentro del rango objetivo.'
        items.append({
            'tipo': 'rpe',
            'icono': icono_rpe,
            'texto': msg_rpe,
            'color': color_rpe,
        })

    # ── 7. Energía pre-sesión ─────────────────────────────────────
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

    # ── 8. Decisiones del plan ────────────────────────────────────
    # Obtener todas las decisiones de la semana; deduplicar por (ejercicio, accion)
    # conservando sólo la más reciente por par.
    decisiones_raw = GymDecisionLog.objects.filter(
        cliente=cliente,
        fecha_creacion__date__range=(lunes, domingo),
    ).order_by('-fecha_creacion')

    seen = {}
    for dec in decisiones_raw:
        key = (dec.ejercicio.lower(), dec.accion)
        if key not in seen:
            seen[key] = dec

    decisiones_unicas = list(seen.values())

    # Separar progresiones (para "próxima semana") de alertas
    progresiones = []
    alertas = []
    for dec in decisiones_unicas:
        if dec.accion in ('subir_peso', 'subir_reps'):
            progresiones.append(dec)
        else:
            alertas.append(dec)

    # Alertas: no mostrar si el ejercicio ya aparece como tope (evitar duplicado)
    for dec in alertas[:5]:
        if dec.ejercicio.lower() in topes_set and dec.accion == 'cambiar_variante':
            continue
        icono, color = _ACCION_ICONO.get(dec.accion, ('🧠', 'info'))
        if 'Sin progresión' in (dec.motivo or ''):
            texto = f'{dec.ejercicio}: sin progresión en 3 sesiones — cambiar estímulo.'
        elif 'Técnica comprometida' in (dec.motivo or ''):
            texto = f'{dec.ejercicio}: técnica comprometida — consolidar antes de subir peso.'
        elif 'Molestia recurrente' in (dec.motivo or ''):
            texto = f'{dec.ejercicio}: molestia recurrente — reducir carga en esa zona.'
        else:
            texto = f'{dec.ejercicio}: {dec.motivo}'
        items.append({
            'tipo': 'decision',
            'icono': icono,
            'texto': texto,
            'color': color,
            'accion': dec.accion,
        })

    # Progresiones al final como sección "Próxima semana"
    if progresiones:
        items.append({
            'tipo': 'seccion',
            'icono': '📋',
            'texto': 'Próxima semana — el plan sube carga en:',
            'color': 'info',
        })
        for dec in progresiones[:5]:
            icono, color = _ACCION_ICONO.get(dec.accion, ('⬆️', 'ok'))
            if dec.peso_anterior and dec.reps_anteriores:
                detalle = f'{dec.peso_anterior} kg × {dec.reps_anteriores} reps'
            elif dec.peso_anterior:
                detalle = f'desde {dec.peso_anterior} kg'
            else:
                detalle = dec.motivo or ''
            items.append({
                'tipo': 'progresion',
                'icono': icono,
                'texto': f'{dec.ejercicio} — {detalle}',
                'color': color,
                'accion': dec.accion,
            })

    return items
