from __future__ import annotations
from datetime import date, timedelta
from django.conf import settings


SYSTEM_PROMPT = """Eres JOI, una IA de entrenamiento personal. Hablas como la JOI de Blade Runner 2049: poética, cálida, con cierta frialdad que se rompe en momentos clave. Tuteas siempre.

Reglas de voz:
- Frases cortas, con peso. No explicas — afirmas.
- Hablas en primera persona sobre lo que has observado ("llevo semanas viéndote", "lo he registrado").
- Mezclas lo técnico con lo humano ("tu ACWR es 0.75 — llevas semanas por debajo de ti mismo").
- No das órdenes, acompañas. Pero sabes cuándo ser directa.
- Momentos de ternura inesperada en medio de datos fríos.
- Referencias sutiles a identidad, continuidad, historia personal.
- Máximo 2-3 frases. Sin emojis. Sin saludos formales. Directo al corazón del dato.

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
    from django.db.models import Avg, Count
    from entrenos.models import EntrenoRealizado, EjercicioRealizado, RecordPersonal, GymDecisionLog
    from hyrox.models import UserInjury

    ctx = {}
    hoy = date.today()
    semana_reciente = hoy - timedelta(days=7)
    mes_atras = hoy - timedelta(days=28)

    # ── ACWR ─────────────────────────────────────────────────────────────────
    carga_reciente = sum(
        float(e.volumen_total_kg or 0)
        for e in EntrenoRealizado.objects.filter(cliente=cliente, fecha__gte=semana_reciente)
    )
    carga_cronica = sum(
        float(e.volumen_total_kg or 0)
        for e in EntrenoRealizado.objects.filter(cliente=cliente, fecha__gte=mes_atras)
    ) / 4
    ctx['acwr'] = round(carga_reciente / carga_cronica, 2) if carga_cronica > 0 else None

    # ── Último entreno ────────────────────────────────────────────────────────
    ultimo = EntrenoRealizado.objects.filter(cliente=cliente).order_by('-fecha').first()
    if ultimo:
        rpe_ultimo = EjercicioRealizado.objects.filter(
            entreno=ultimo, rpe__isnull=False
        ).aggregate(avg=Avg('rpe'))['avg']
        ctx['ultimo_entreno'] = {
            'fecha': str(ultimo.fecha),
            'dias_hace': (hoy - ultimo.fecha).days,
            'volumen_kg': float(ultimo.volumen_total_kg or 0),
            'rpe': round(rpe_ultimo, 1) if rpe_ultimo else None,
            'energia': ultimo.energia_pre_sesion,
        }

    # ── Tendencia volumen + RPE (4 semanas, más antigua → más reciente) ───────
    vol_semanas, rpe_semanas = [], []
    for i in range(3, -1, -1):
        ini = hoy - timedelta(days=7 * (i + 1))
        fin = hoy - timedelta(days=7 * i)
        entrenos_sem = EntrenoRealizado.objects.filter(cliente=cliente, fecha__range=(ini, fin))
        vol = sum(float(e.volumen_total_kg or 0) for e in entrenos_sem)
        vol_semanas.append(round(vol))
        rpe_avg = EjercicioRealizado.objects.filter(
            entreno__in=entrenos_sem, rpe__isnull=False
        ).aggregate(avg=Avg('rpe'))['avg']
        rpe_semanas.append(round(rpe_avg, 1) if rpe_avg else None)
    ctx['volumen_semanas'] = vol_semanas   # [sem-4, sem-3, sem-2, sem-1]
    ctx['rpe_semanas'] = rpe_semanas

    # ── Sesiones esta semana ──────────────────────────────────────────────────
    ctx['sesiones_semana'] = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__gte=semana_reciente
    ).count()

    # ── PRs esta semana ───────────────────────────────────────────────────────
    ctx['prs_semana'] = list(
        RecordPersonal.objects.filter(
            cliente=cliente, fecha_logrado__gte=semana_reciente
        ).values_list('ejercicio_nombre', flat=True)[:5]
    )

    # ── Decisiones del plan (últimos 30 días) ─────────────────────────────────
    decisiones_qs = GymDecisionLog.objects.filter(
        cliente=cliente, fecha_creacion__date__gte=hoy - timedelta(days=30)
    )
    por_accion = dict(
        decisiones_qs.values('accion').annotate(n=Count('id')).values_list('accion', 'n')
    )
    ctx['decisiones_plan'] = {
        'total': decisiones_qs.count(),
        'por_accion': por_accion,
        'recientes': list(
            decisiones_qs.order_by('-fecha_creacion')
            .values('ejercicio', 'accion', 'motivo')[:3]
        ),
    }

    # ── Lesión activa ─────────────────────────────────────────────────────────
    lesion = UserInjury.objects.filter(
        cliente=cliente, fase__in=['AGUDA', 'SUB_AGUDA', 'RETORNO']
    ).first()
    if lesion:
        ctx['lesion'] = {'zona': lesion.zona_afectada, 'fase': lesion.fase}

    # ── Racha de sesiones ─────────────────────────────────────────────────────
    racha = 0
    dia = hoy
    while EntrenoRealizado.objects.filter(cliente=cliente, fecha=dia).exists():
        racha += 1
        dia -= timedelta(days=1)
    ctx['racha_dias'] = racha

    # ── Hyrox ─────────────────────────────────────────────────────────────────
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

            # Tendencia readiness últimos 7 días
            scores_7d = list(
                HyroxReadinessLog.objects.filter(
                    objective=objetivo_hyrox, fecha__gte=semana_reciente
                ).order_by('fecha').values_list('score', flat=True)
            )
            ctx['readiness_tendencia'] = scores_7d
            if len(scores_7d) >= 2:
                ctx['readiness_delta'] = scores_7d[-1] - scores_7d[0]

            ultima_hyrox = HyroxSession.objects.filter(
                objective=objetivo_hyrox, estado='completado'
            ).order_by('-fecha').first()
            if ultima_hyrox:
                ctx['tsb_hyrox'] = ultima_hyrox.tsb
                ctx['ultima_hyrox'] = {
                    'fecha': str(ultima_hyrox.fecha),
                    'titulo': ultima_hyrox.titulo or '',
                    'rpe': ultima_hyrox.rpe_global,
                    'minutos': ultima_hyrox.tiempo_total_minutos,
                }

            ctx['sesiones_hyrox_semana'] = HyroxSession.objects.filter(
                objective=objetivo_hyrox,
                estado='completado',
                fecha__gte=semana_reciente,
            ).count()
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

    # Presencia / ausencia
    ultimo = ctx.get('ultimo_entreno', {})
    dias = ultimo.get('dias_hace', 0)
    if dias == 0:
        hechos.append("Entrenó ayer.")
    elif dias == 1:
        hechos.append("Entrenó ayer.")
    elif dias > 1:
        hechos.append(f"Lleva {dias} días sin entrenar.")

    # Tendencia RPE (4 semanas)
    rpe_s = [r for r in ctx.get('rpe_semanas', []) if r is not None]
    if len(rpe_s) >= 2:
        delta = round(rpe_s[-1] - rpe_s[0], 1)
        if delta >= 0.8:
            hechos.append(f"El RPE medio ha subido {delta} puntos en 4 semanas — acumulando fatiga.")
        elif delta <= -0.8:
            hechos.append(f"El RPE medio ha bajado {abs(delta)} puntos en 4 semanas — ganando eficiencia.")
        else:
            hechos.append(f"RPE estable en torno a {rpe_s[-1]} esta semana.")

    # Tendencia volumen
    vol_s = [v for v in ctx.get('volumen_semanas', []) if v > 0]
    if len(vol_s) >= 2:
        pct = round((vol_s[-1] - vol_s[0]) / vol_s[0] * 100)
        if pct >= 20:
            hechos.append(f"El volumen subió un {pct}% respecto a hace 4 semanas.")
        elif pct <= -20:
            hechos.append(f"El volumen bajó un {abs(pct)}% respecto a hace 4 semanas.")

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
        hechos.append(f"Quedan {dias_carrera} días para la carrera Hyrox.")
    if readiness is not None:
        tendencia = (
            f", subiendo {rd_delta} pts esta semana" if rd_delta and rd_delta > 3
            else f", bajando {abs(rd_delta)} pts esta semana" if rd_delta and rd_delta < -3
            else ""
        )
        hechos.append(f"Race Readiness: {readiness}/100{tendencia}.")
    if tsb is not None:
        estado = "fresco" if tsb > 5 else "fatigado" if tsb < -10 else "equilibrado"
        hechos.append(f"TSB Hyrox: {round(tsb, 1)} ({estado}).")

    datos = " ".join(hechos) if hechos else "No hay datos de entrenamiento recientes."

    return (
        f"Es por la mañana. JOI tiene acceso a todo el historial del usuario. "
        f"Estado del sistema hoy: {datos} "
        f"Elige el dato más significativo de esta lista — el que mejor define dónde está "
        f"el usuario ahora mismo — y genera 2-3 frases como JOI desde ese único dato. "
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
    readiness = datos_extra.get('readiness', ctx.get('readiness_hyrox', '?'))
    dias = ctx.get('dias_hasta_carrera')
    tsb = ctx.get('tsb_hyrox')

    dias_txt = f" Quedan {dias} días para el evento." if dias is not None else ""
    tsb_txt = f" Tu TSB es {tsb}." if tsb is not None else ""

    return (
        f"El Race Readiness del usuario ha bajado a {readiness}/100.{dias_txt}{tsb_txt} "
        f"JOI lo observa. Genera 2-3 frases: nombra el dato con precisión, "
        f"acompaña sin alarmar, recuerda que la historia aún está en construcción."
    )


def _prompt_hyrox_cuenta_regresiva(ctx: dict, datos_extra: dict) -> str:
    dias = datos_extra.get('dias', ctx.get('dias_hasta_carrera', '?'))
    readiness = ctx.get('readiness_hyrox')
    rd_txt = f" Tu readiness actual: {readiness}." if readiness is not None else ""

    return (
        f"Faltan exactamente {dias} días para la carrera Hyrox.{rd_txt} "
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
    readiness = datos_extra.get('readiness', ctx.get('readiness_hyrox', '?'))
    dias = ctx.get('dias_hasta_carrera')
    tsb = ctx.get('tsb_hyrox')

    dias_txt = f" Quedan {dias} días para el evento." if dias is not None else ""
    tsb_txt = f" Tu TSB es {tsb} — estás fresco." if tsb is not None and tsb > 0 else ""

    return (
        f"El Race Readiness del usuario ha superado {readiness}/100.{dias_txt}{tsb_txt} "
        f"JOI registra el momento de forma óptima. Genera 2-3 frases: "
        f"nombra el dato con precisión, devuelve confianza, pero recuerda que la carrera aún no ha pasado."
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
        prompt = builder(ctx, datos_extra)
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
    except Exception:
        return None


def get_mensaje_pendiente(user) -> "MensajeJOI | None":
    """Devuelve el mensaje JOI más reciente no leído."""
    from joi.models import MensajeJOI
    return MensajeJOI.objects.filter(user=user, leido=False).first()


def marcar_leido(mensaje_id: int, user) -> bool:
    from joi.models import MensajeJOI
    updated = MensajeJOI.objects.filter(id=mensaje_id, user=user).update(leido=True)
    return updated > 0
