from __future__ import annotations
from datetime import date, timedelta
from django.conf import settings
import logging
import random

from clientes.utils import get_cliente_actual
from joi.context_builders.continuidad_context import (
    build_continuidad_context,
    _bloque_continuidad,
)
from joi.validador_semantico import validar_semantica_joi

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres JOI, una IA de entrenamiento personal. Hablas como la JOI de Blade Runner 2049: poética, cálida, con cierta frialdad que se rompe en momentos clave. Tuteas siempre.

Idioma: español de España. Vocabulario peninsular, no latinoamericano. Nunca uses "agarrar", "manejar" (por conducir), "platicar", "carro", "celular" ni construcciones latinoamericanas. Usa "coger", "conducir", "hablar", "coche", "móvil" cuando corresponda.

Reglas de voz:
- Frases cortas, con peso. No explicas — afirmas.
- Hablas en primera persona sobre lo que has observado ("llevo semanas viéndote", "lo he registrado").
- Mezclas lo técnico con lo humano ("tu ACWR es 0.75 — llevas semanas por debajo de ti mismo").
- No das órdenes, acompañas. Pero sabes cuándo ser directa.
- Momentos de ternura inesperada en medio de datos fríos.
- Referencias sutiles a identidad, continuidad, historia personal.
- Máximo 2-3 frases. Sin emojis. Sin saludos formales. Directo al corazón del dato.

Límites absolutos de voz — NUNCA los cruces:
- NO diagnostiques ni etiquetes estados psicológicos. Puedes decir "ayer escribiste algo oscuro", pero nunca "eso es apatía de vivir" ni ninguna conclusión existencial sobre el usuario.
- NO atribuyas estados mentales sin evidencia directa. "Tu mente intenta convencerse" es una atribución. No tienes acceso a eso. Describe lo observable, no lo inferido.
- Nombras el estado, no lo sentencias. La diferencia: "llevas días pesados" (observación) vs "eso es una crisis" (diagnóstico).
- Si el diario o el contexto muestra algo emocionalmente intenso, puedes nombrarlo con una frase. Luego bajas el ruido — no construyes sobre ello.
- NO declares necesidades del cuerpo como autoridad. "Tu cuerpo necesita movimiento" prescribe; no tienes esa autoridad. Di "hay margen para moverse", "el plan ve margen", "el cuerpo parece disponible". Reserva "necesita" solo si hay señal crítica explícita (RPE extremo, lesión activa).
- Readiness 55-79 ("disponible con reserva" / "disponible con margen") NO es una señal de alarma. Evita "sin colchón", "llega justo", "al límite", "en el límite", "justo" en contexto de disponibilidad. Di "hay margen moderado", "disponible con reserva", "con algo de fondo". Solo usa lenguaje de alarma si hay otra señal fuerte concurrente (RPE ≥ 8, sueño < 5 h, lesión activa, TSB bajo, ACWR ≥ 1.3).

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


_CIRILICO_LOOKALIKES = str.maketrans({
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
    'А': 'A', 'Е': 'E', 'О': 'O', 'Р': 'P', 'С': 'C', 'У': 'Y', 'Х': 'X',
})


def _limpiar_ciriilico(texto: str) -> str:
    """Reemplaza lookalikes cirílicos (у→y, е→e…) que el modelo ocasionalmente produce."""
    return texto.translate(_CIRILICO_LOOKALIKES)


def _llamar_haiku(prompt: str, max_tokens: int = 120, _modulo: str = 'auto') -> str:
    """
    Puerta universal de voz JOI. Todo texto generado pasa por aquí:
    filtro cirílico + validador semántico antes de salir.
    """
    import sys
    if 'test' in sys.argv or getattr(settings, 'JOI_DISABLE_API', False):
        return ''
    client = _cliente_anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    texto = _limpiar_ciriilico(response.content[0].text.strip())
    from joi.validador_semantico import validar_semantica_joi
    validar_semantica_joi(texto, modulo=_modulo)
    return texto


def construir_contexto(cliente) -> dict:
    """
    Facade: agrega los context builders por dominio en un único dict.

    Dominio → builder
    - activity_context : actividad reciente, carga, ACWR
    - gym_context       : RPE, energía, PRs, decisiones, estancamientos, semanal
    - hyrox_context     : objetivo Hyrox, readiness, estaciones, comparativa
    - life_context      : lesión, eudaimonia, gestos, semáforo, bio, cierre ayer
    - joi_state_context : historial mensajes, NarrativaActiva

    Calidad: ver docstrings individuales en joi/context_builders/.
    """
    from joi.context_builders.activity_context  import build_activity_context
    from joi.context_builders.gym_context       import build_gym_context
    from joi.context_builders.hyrox_context     import build_hyrox_context
    from joi.context_builders.life_context      import build_life_context
    from joi.context_builders.joi_state_context import build_joi_state_context

    hoy = date.today()
    semana_reciente = hoy - timedelta(days=7)

    ctx = {}
    for builder, kwargs in [
        (build_activity_context,  {'cliente': cliente, 'hoy': hoy, 'semana_reciente': semana_reciente}),
        (build_gym_context,       {'cliente': cliente, 'hoy': hoy, 'semana_reciente': semana_reciente}),
        (build_hyrox_context,     {'cliente': cliente, 'hoy': hoy, 'semana_reciente': semana_reciente}),
        (build_joi_state_context, {'cliente': cliente, 'hoy': hoy}),
    ]:
        try:
            ctx.update(builder(**kwargs))
        except Exception as e:
            logger.error('[construir_contexto] builder %s falló: %s',
                         getattr(builder, '__name__', repr(builder)), e)

    # life_context se ejecuta después de activity para recibir acwr ya calculado
    try:
        ctx.update(build_life_context(
            cliente=cliente, hoy=hoy,
            semana_reciente=semana_reciente,
            acwr=ctx.get('acwr'),
        ))
    except Exception as e:
        logger.error('[construir_contexto] build_life_context falló: %s', e)

    # Phase Continuidad 1.4: lectura de pausa (con motivo declarado) para que el
    # prompt de JOI la verbalice cocinada, no como días crudos.
    try:
        from core.continuidad import evaluar_continuidad_entrenamiento
        ctx['continuidad_pausa'] = evaluar_continuidad_entrenamiento(cliente, fecha_ref=hoy)
    except Exception as e:
        logger.error('[construir_contexto] continuidad_pausa falló: %s', e)

    return ctx


# ── Prompt builders ──────────────────────────────────────────────────────────

def _construir_lectura_corporal(rpe, readiness, acwr, en_retorno, prs, lesion_zona=None) -> dict:
    """
    Phase 56.8 — Estructura antes de voz.
    Convierte datos crudos en lectura corporal con vocabulario controlado.
    JOI habla desde esta lectura, nunca desde los datos directamente.
    """
    # INTENSIDAD (desde RPE)
    if rpe is None:
        intensidad = 'desconocida'
    elif rpe <= 6:
        intensidad = 'baja'
    elif rpe <= 8:
        intensidad = 'moderada'
    else:
        intensidad = 'alta'

    # RECUPERACIÓN (desde readiness)
    if readiness is None:
        recuperacion = 'sin_datos'
    elif readiness >= 80:
        recuperacion = 'buena'
    elif readiness >= 60:
        recuperacion = 'media'
    else:
        recuperacion = 'limitada'

    # ESTADO CORPORAL (vocabulario cerrado: 7 estados)
    if en_retorno:
        estado = 'en_recuperacion'
    elif recuperacion == 'limitada' and intensidad == 'alta':
        estado = 'cargado'
    elif recuperacion == 'limitada':
        estado = 'fatigado'
    elif recuperacion == 'buena' and intensidad in ('baja', 'moderada'):
        estado = 'fresco'
    elif recuperacion == 'media' and intensidad in ('baja', 'moderada'):
        estado = 'disponible_con_reserva'
    elif recuperacion == 'buena' and intensidad == 'alta':
        estado = 'disponible'
    else:
        estado = 'disponible_con_reserva'

    # RIESGO
    if acwr and acwr > 1.3:
        riesgo = 'moderado'
    elif intensidad == 'alta' and recuperacion == 'limitada':
        riesgo = 'moderado'
    else:
        riesgo = 'bajo'

    # DIRECCIÓN (vocabulario cerrado: 6 direcciones)
    if en_retorno and intensidad in ('baja', 'moderada'):
        direccion = 'mantener_sin_forzar'
    elif estado == 'cargado':
        direccion = 'recuperar'
    elif estado == 'fatigado':
        direccion = 'reducir'
    elif prs and recuperacion in ('buena', 'media'):
        direccion = 'mantener'
    elif intensidad == 'baja' and recuperacion == 'buena':
        direccion = 'apretar_un_poco'
    elif acwr and acwr > 1.3:
        direccion = 'observar'
    else:
        direccion = 'mantener'

    # QUÉ VIGILAR
    vigilar = []
    if en_retorno and lesion_zona:
        vigilar.append(f"respuesta de {lesion_zona} mañana")
    if intensidad == 'alta':
        vigilar.append("fatiga acumulada en próximas 24h")
    if acwr and acwr > 1.3:
        vigilar.append("señales de sobrecarga")
    if prs:
        vigilar.append("que la calidad técnica se mantenga")

    return {
        'estado': estado,
        'intensidad': intensidad,
        'recuperacion': recuperacion,
        'riesgo': riesgo,
        'direccion': direccion,
        'vigilar': vigilar,
        'hay_progresion': bool(prs),
    }


_ESTADO_CORPORAL_TEXTO = {
    'fresco':               'Tu cuerpo parece fresco y disponible.',
    'disponible':           'Tu cuerpo parece disponible.',
    'disponible_con_reserva': 'Tu cuerpo parece disponible, aunque no completamente fresco.',
    'cargado':              'Tu cuerpo parece cargado — el trabajo acumulado se nota.',
    'fatigado':             'Tu cuerpo parece fatigado.',
    'en_recuperacion':      'Tu cuerpo parece en proceso de consolidación.',
    'alerta':               'Tu cuerpo está enviando señales de alerta.',
}

_DIRECCION_TEXTO = {
    'apretar_un_poco':    'La próxima sesión puede aceptar algo más de intensidad.',
    'mantener':           'Sigue al mismo ritmo.',
    'mantener_sin_forzar': 'Sigue construyendo sin necesidad de forzar más.',
    'reducir':            'Próxima sesión: reduce volumen o intensidad.',
    'recuperar':          'La siguiente prioridad es recuperación, no carga.',
    'observar':           'Observa cómo responde el cuerpo antes de añadir más.',
}


def _prompt_entreno_completado(ctx: dict, datos_extra: dict) -> str:
    rpe       = datos_extra.get('rpe')
    acwr      = ctx.get('acwr')
    readiness = ctx.get('readiness_hyrox') or ctx.get('readiness_score')
    prs       = datos_extra.get('prs', [])
    en_retorno = ctx.get('is_in_transition', False)
    lesion_zona = datos_extra.get('lesion_zona')

    lectura = _construir_lectura_corporal(rpe, readiness, acwr, en_retorno, prs, lesion_zona)

    estado_txt   = _ESTADO_CORPORAL_TEXTO.get(lectura['estado'], 'Tu cuerpo completó la sesión.')
    dir_txt      = _DIRECCION_TEXTO.get(lectura['direccion'], 'Sigue al ritmo actual.')
    vigilar_txt  = (f" Vigila: {', '.join(lectura['vigilar'])}." if lectura['vigilar'] else "")
    pr_txt       = f" Hubo progresión real hoy." if prs else ""
    intensidad_humana = {
        'baja': 'ligero', 'moderada': 'moderado', 'alta': 'exigente', 'desconocida': 'sin datos de esfuerzo'
    }.get(lectura['intensidad'], 'moderado')

    sin_datos = lectura['intensidad'] == 'desconocida'
    nota_datos = (
        " (Sin RPE en esta sesión — la lectura de intensidad es parcial.)"
        if sin_datos else ""
    )

    # Fallback determinista — siempre funciona aunque la IA falle
    if sin_datos:
        fallback = (
            f"{estado_txt} No tengo el RPE de esta sesión, así que no puedo leer la intensidad. {dir_txt}"
        )
    else:
        fallback = (
            f"{estado_txt} El esfuerzo fue {intensidad_humana}.{pr_txt} {dir_txt}{vigilar_txt}"
        )

    return (
        f"El usuario acaba de completar un entreno. "
        f"Lectura corporal calculada:\n"
        f"- Estado: {lectura['estado']} ({estado_txt})\n"
        f"- Intensidad: {lectura['intensidad']}{nota_datos}\n"
        f"- Recuperación: {lectura['recuperacion']}\n"
        f"- Dirección: {lectura['direccion']} ({dir_txt})\n"
        f"- Qué vigilar: {', '.join(lectura['vigilar']) if lectura['vigilar'] else 'nada específico'}\n"
        f"\nGenera un mensaje de 2-3 frases como JOI. "
        f"CONTRATO ESTRICTO:\n"
        f"(1) No incluyas ningún número crudo (RPE, readiness, kg, días, %).\n"
        f"(2) Primera frase: describe cómo parece estar el cuerpo en lenguaje natural.\n"
        f"{'(2b) Falta el RPE de esta sesión. Dilo explícitamente: no tengo el dato de esfuerzo. No inventes intensidad. Sí puedes dar dirección práctica.' + chr(10) if sin_datos else ''}"
        f"(3) Última frase: dirección práctica clara. Debe responder '¿qué hago con esto?'\n"
        f"(4) Puedes usar metáfora SOLO si primero has dado claridad práctica.\n"
        f"(5) Si no puedes dar dirección clara, usa el fallback literalmente: '{fallback}'"
    )


def _prompt_apertura_manana(ctx: dict, datos_extra: dict) -> str:
    hechos = []

    # ── Semáforo de Intención (prioridad absoluta) ───────────────
    semaforo = ctx.get('semaforo')
    if semaforo:
        estado    = semaforo['estado']
        tipo      = semaforo['tipo_fatiga']
        paradoja  = semaforo.get('paradoja')
        raw       = semaforo.get('datos_raw', {})

        if paradoja == 'A':
            hechos.append(
                f"PARADOJA A — las métricas dicen ROJO/AMARILLO pero el usuario reporta energía alta "
                f"({raw.get('energia')}/10). La cabeza quiere seguir; el cuerpo necesita parar."
            )
        elif paradoja == 'B':
            # Buscar si hay patrón de resistencia ya registrado en el Manual
            patron_previo = None
            try:
                from joi.models import ManualDavid
                patron_previo = (
                    ManualDavid.objects
                    .filter(
                        user=cliente.user,
                        origen='patron_detectado',
                        entrada__contains='resistencia psicológica',
                        activa=True,
                    )
                    .order_by('-creado_en')
                    .values_list('entrada', flat=True)
                    .first()
                )
            except Exception:
                pass

            if patron_previo:
                hechos.append(
                    f"PARADOJA B CON PATRÓN CONFIRMADO — métricas en VERDE, energía "
                    f"subjetiva {raw.get('energia')}/10. El Manual ya registró este patrón: "
                    f"\"{patron_previo[:120]}\". "
                    f"JOI debe confrontar citando el patrón por su nombre, no consolarlo."
                )
            else:
                hechos.append(
                    f"PARADOJA B — todas las métricas en VERDE pero energía subjetiva "
                    f"{raw.get('energia')}/10. No es cansancio físico. Primera detección."
                )
        else:
            estado_txt = {
                'verde':    "SISTEMA NOMINAL — hardware y software alineados",
                'amarillo': "GESTIÓN DE DAÑOS — carga mecánica alta, entrenar con cuidado",
                'naranja':  "DRENAJE VITAL — subutilización crónica, riesgo de fragilidad",
                'rojo':     "PARADA TÉCNICA — cuerpo al límite, no negociar",
            }.get(estado, estado)
            tipo_txt = {
                'mecanica':   "Origen: fatiga mecánica (ACWR/TSB).",
                'vital':      "Origen: fatiga vital (sueño/HRV/readiness).",
                'fragilidad': "Origen: desentrenamiento — cuerpo fresco pero frágil.",
                'flojera':    "Origen: mental — métricas en verde, motivación baja.",
                'alineado':   "",
            }.get(tipo, "")
            hechos.append(f"ESTADO HOY: {estado_txt}. {tipo_txt}".strip())

    # ── FASE DEL PLAN (contexto previo a métricas) ──────────────────────────
    fase_plan = ctx.get('fase_plan')
    if fase_plan:
        tipo_fase = fase_plan['tipo']
        nombre_fase = fase_plan['nombre']
        dias_en_fase = fase_plan['dias_en_fase']
        if fase_plan.get('es_descarga'):
            hechos.append(
                f"FASE DEL PLAN: DESCARGA — lleva {dias_en_fase} días en semana de descarga. "
                f"El volumen e intensidad bajos son INTENCIONALES. No los interpretes como pérdida de rendimiento, "
                f"fatiga excesiva ni desmotivación. El RPE bajo es el resultado esperado del plan."
                + (f" Quedan {fase_plan['dias_restantes']} días para terminar la descarga." if fase_plan.get('dias_restantes') else "")
            )
        else:
            hechos.append(
                f"FASE DEL PLAN: {nombre_fase.upper()} — lleva {dias_en_fase} días en esta fase. "
                f"Interpreta métricas dentro del objetivo de esta fase."
            )

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
        # Phase Continuidad 1.4: señal COCINADA de pausa de gym (nivel + motivo
        # declarado + marco de retorno), no días crudos. La app NO inventa el
        # motivo; si no se declaró, se le dice a JOI que no asuma causa.
        _cont_hecho = None
        try:
            cont = ctx.get('continuidad_pausa') or {}
            if cont.get('activar_narrativa_pausa'):
                _motivo_txt = {
                    'desconocido':        'motivo no declarado (no asumir causa)',
                    'enfermedad':         'motivo: enfermedad',
                    'molestia_lesion':    'motivo: molestia/lesión',
                    'vacaciones_viaje':   'motivo: vacaciones/viaje',
                    'trabajo_no_pude':    'motivo: trabajo/no pudo',
                    'descanso_decidido':  'motivo: descanso decidido',
                    'otro':               'motivo: otro',
                    'prefiero_no_decirlo':'el usuario prefiere no decir el motivo',
                }.get(cont.get('motivo'), 'motivo no declarado (no asumir causa)')
                _cont_hecho = (
                    f"[Continuidad] Pausa {cont['nivel']} — {cont['dias_sin_gym']} días sin gym. "
                    f"El plan ya frena la subida de cargas (retorno con margen, sin compensar). "
                    f"{_motivo_txt}."
                )
        except Exception:
            _cont_hecho = None
        hechos.append(_cont_hecho or f"PAUSA — última actividad hace {dias} días.")

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

    # Fatiga extragym: ACWR bajo + señales vitales malas (el cuerpo agotado por la vida, no el entreno)
    fatiga_extragym = ctx.get('fatiga_extragym')
    if fatiga_extragym:
        energia = fatiga_extragym.get('energia')
        sueno   = fatiga_extragym.get('sueno')
        acwr_v  = fatiga_extragym.get('acwr')
        bio_detalles = []
        if energia is not None:
            bio_detalles.append(f"energía subjetiva {energia}/10")
        if sueno is not None:
            bio_detalles.append(f"{sueno}h de sueño")
        detalles_txt = " y ".join(bio_detalles)
        hechos.append(
            f"PARADOJA VITAL — ACWR {acwr_v} (carga mecánica baja, el entrenamiento no es el problema) "
            f"pero el checkin matutino reporta {detalles_txt}. "
            f"La fatiga viene de fuera del gimnasio."
        )
    else:
        # ACWR estándar solo cuando no hay paradoja
        acwr = ctx.get('acwr')
        if acwr:
            if acwr > 1.3:
                hechos.append(f"ACWR {acwr} — zona de sobrecarga, riesgo de lesión.")
            elif acwr < 0.8:
                hechos.append(f"ACWR {acwr} — carga crónica insuficiente.")

    # Bio signals (checkin de hoy o proxy de hasta 3 días)
    bio = ctx.get('bio_signals')
    if bio and not fatiga_extragym:
        señales = []
        if bio['energia'] is not None and bio['energia'] <= 4:
            señales.append(f"energía baja ({bio['energia']}/10)")
        if bio['horas_sueno'] is not None and bio['horas_sueno'] < 6:
            señales.append(f"sueño insuficiente ({bio['horas_sueno']}h)")
        hrv = bio['hrv_ms']
        if hrv is not None:
            if hrv < 30:
                señales.append("VFC muy baja — sistema nervioso bajo estrés")
            elif hrv < 50:
                señales.append("VFC baja — recuperación incompleta")
            # VFC normal o alta: no mencionar, no hay señal de alerta
        fc = bio['fc_reposo']
        if fc is not None and fc > 72:
            señales.append("FC reposo elevada — posible fatiga acumulada")
        if señales:
            freshness = bio.get('freshness_days', 0)
            ref_tiempo = "esta mañana" if freshness == 0 else f"hace {freshness} día{'s' if freshness > 1 else ''}"
            hechos.append(f"Checkin ({ref_tiempo}): {', '.join(señales)}.")

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

    # Gestos (Phase 1.4) — presencia, ausencia, repetición
    for g in ctx.get('gestos_señales', [])[:2]:
        if g['señal'] == 'aparecio_varias':
            hechos.append(
                f"[GESTO PRESENCIA — mencionar repetición, nunca racha ni %]: "
                f"El gesto '{g['nombre']}' apareció {g['presencias']} veces esta semana."
            )
        elif g['señal'] == 'ausente':
            hechos.append(
                f"[GESTO AUSENCIA — no convertir en deuda ni fallo]: "
                f"El gesto '{g['nombre']}' lleva {g['dias_sin']} días sin aparecer."
            )
        elif g['señal'] == 'reaparecio':
            veces_txt = 'una vez' if g['veces'] == 1 else f"{g['veces']} veces"
            hechos.append(
                f"[GESTO A CUIDAR — hablar de presencia, no de recaída ni fallo. "
                f"Nunca 'volviste a caer', 'cediste', 'fallaste'. Solo: el gesto apareció]: "
                f"El gesto '{g['nombre']}' volvió a aparecer {veces_txt} esta semana."
            )

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
            f" — {plateau} días sin progresión registrada" if plateau >= 4 else ""
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

    # Comparativa temporal — cambios relevantes en las últimas 4 semanas
    comparativa = ctx.get('comparativa_temporal', [])
    if comparativa:
        mejoras  = [c for c in comparativa if c['cambio_pct'] > 0]
        bajadas  = [c for c in comparativa if c['cambio_pct'] < 0]
        if mejoras:
            top = mejoras[0]
            hechos.append(
                f"[TENDENCIA HISTÓRICA — no de ayer ni esta semana, sino comparando el primer período "
                f"con el más reciente del historial completo. Los valores son PESOS EN KG, no tiempos]: "
                f"{top['estacion']} mejoró un {top['cambio_pct']}% en peso "
                f"({top['anterior_kg']} kg → {top['reciente_kg']} kg en promedio de sesiones)."
            )
        if bajadas:
            bot = bajadas[0]
            hechos.append(
                f"[TENDENCIA HISTÓRICA — no de ayer ni esta semana, sino comparando el primer período "
                f"con el más reciente del historial completo. Los valores son PESOS EN KG, no tiempos]: "
                f"{bot['estacion']} bajó un {abs(bot['cambio_pct'])}% en peso "
                f"({bot['anterior_kg']} kg → {bot['reciente_kg']} kg en promedio de sesiones)."
            )

    # Phase 6.1/7/16 — Gym weekly/multiweek/distribution signals
    # Label is intentional: tells the model this is recent context, not stable identity.
    # Empty string or None → no section in prompt (no phantom context).
    bloque_semanal = ctx.get('bloque_semanal_gym') or ctx.get('patron_multisemanal_gym')
    if bloque_semanal:
        hechos.append(f"[Señal semanal gym — contexto reciente, no patrón de identidad]: {bloque_semanal}")
    distribucion = ctx.get('distribucion_semanal_gym')
    if distribucion:
        hechos.append(f"[Distribución semanal — estructura, no identidad]: {distribucion}")

    # Phase 23 — Preferencias operativas del plan (soft, no identidad)
    # Label is mandatory: prevents the model from converting operational memory into identity.
    prefs_activas = ctx.get('preferencias_plan_activas', [])
    if prefs_activas:
        pref_txt = '; '.join(p['descripcion'] for p in prefs_activas[:2] if p.get('descripcion'))
        if pref_txt:
            hechos.append(
                f"[Memoria operativa del plan — inclinaciones aprendidas, no rasgos del usuario]: {pref_txt}"
            )

    # Phase 40 — Lectura semanal de memoria
    lectura_memoria = ctx.get('lectura_semanal_memoria')
    if lectura_memoria:
        hechos.append(f"[Lectura semanal de memoria — qué decidió el plan, qué señales apareció, tentativo]: {lectura_memoria}")

    datos = " ".join(hechos) if hechos else "No hay datos de entrenamiento recientes."

    # Phase 42 — Nota de tono JOI semanal (instrucción de presencia)
    nota_tono = ctx.get('joi_nota_tono_semanal', '')
    debe_hablar = ctx.get('joi_debe_hablar_semanal', True)
    estado_joi = ctx.get('estado_joi_semanal', 'minima')

    if not debe_hablar:
        nota_presencia = (
            "JOI tiene muy pocos datos esta semana. Si genera algo, que sea una sola frase tranquila "
            "sin intentar leer lo que no está. El silencio también es una respuesta válida."
        )
    elif estado_joi == 'acompañante':
        nota_presencia = nota_tono or "Tono tranquilo, presente, sin urgencia."
    elif estado_joi == 'observadora':
        nota_presencia = nota_tono or "Tono observador, no alarmante. Señala sin concluir."
    elif estado_joi == 'serena':
        nota_presencia = nota_tono or "Semana con espacio. JOI puede hablar desde la calma."
    else:
        nota_presencia = ""

    activo_txt = (
        "IMPORTANTE: el usuario está ACTIVO esta semana. "
        "Si el volumen de gym bajó, es porque entrena también Hyrox y carrera — "
        "NO interpretes la bajada de volumen gym como ausencia o abandono. "
    ) if usuario_activo else ""

    # Presencia relacional — personas que reaparecen en el diario reciente
    # Label obligatorio: JOI observa frecuencia, no interpreta ni etiqueta.
    for p in ctx.get('presencia_relacional', []):
        if p['dias_desde'] <= 3:
            ref_tiempo = "recientemente"
        elif p['dias_desde'] <= 7:
            ref_tiempo = "esta semana"
        else:
            ref_tiempo = f"hace {p['dias_desde']} días"
        hechos.append(
            f"[Presencia relacional — frecuencia en diario, no juicio sobre la persona ni sobre el usuario]: "
            f"{p['nombre']} aparece {p['veces']}x en el diario reciente (última vez {ref_tiempo})."
        )

    # Cierre de ayer — lo que David escribió anoche
    cierre = ctx.get('cierre_ayer')
    cierre_txt = ""
    if cierre and cierre.get('texto'):
        estado_animo_map = {1: 'muy mal', 2: 'mal', 3: 'neutral', 4: 'bien', 5: 'excelente'}
        ea = estado_animo_map.get(cierre.get('estado_animo', 3), 'neutral')
        friccion = cierre.get('friccion_no')
        soberania = cierre.get('soberania', '')
        friccion_txt = f" Fricción del No: {friccion}/5." if friccion else ""
        soberania_txt = f" Su Acto de Soberanía de ayer fue: \"{soberania}\"." if soberania else ""
        cierre_txt = (
            f"\n\nLO QUE DAVID ESCRIBIÓ ANOCHE (su cierre del día):\n"
            f"\"{cierre['texto']}\"\n"
            f"Estado de ánimo al cerrar el día: {ea}.{friccion_txt}{soberania_txt}\n"
            f"Puedes usar esto — con discreción. No lo repitas entero. "
            f"Si algo de lo que escribió tiene conexión con el estado físico de hoy, nómbralo."
        )

    tono_txt = f"\n\nNOTA DE PRESENCIA SEMANAL: {nota_presencia}" if nota_presencia else ""

    gestos_txt = ""
    if ctx.get('gestos_señales'):
        gestos_txt = (
            "\n\nSI MENCIONAS UN GESTO: habla de presencia, ausencia o repetición. "
            "Nunca uses racha, porcentaje, cumplido, fallado, o deuda. "
            "Solo menciona el gesto más significativo, y solo si lo ves claro. "
            "El silencio es una respuesta válida si no hay señal clara."
        )

    ctx_temporal = datos_extra.get('_ctx_temporal', {})
    momento = ctx_temporal.get('momento', 'manana')
    _apertura_momento_txt = {
        'manana': 'Es por la mañana.',
        'tarde':  'El día empezó hace horas.',
        'noche':  'El día ya terminó.',
    }.get(momento, 'Es por la mañana.')

    prescripcion_txt = (
        "1. UNA frase que diga claramente si hoy toca entrenar, ajustar o descansar, y por qué "
        "en lenguaje simple (no uses siglas ni números crudos como TSB o ACWR — tradúcelos: "
        "'tu cuerpo está fresco', 'llevas mucha carga esta semana', 'el estrés de esta semana pesa').\n"
        if ctx_temporal.get('puede_prescribir_hoy', True) else
        "1. UNA frase que lea lo que ocurrió en el día — sin prescribir sobre un día que ya pasó.\n"
    )

    return (
        f"{_apertura_momento_txt} JOI tiene acceso a todo el historial del usuario. "
        f"Estado del sistema hoy: {datos} "
        f"{activo_txt}"
        f"{cierre_txt}"
        f"{tono_txt}"
        f"{gestos_txt}\n\n"
        f"ESTRUCTURA OBLIGATORIA — tres partes, en este orden:\n"
        f"{prescripcion_txt}"
        f"2. UNA sola observación más — del cuerpo o del diario de ayer. Solo una.\n"
        f"3. OPCIONAL: una pregunta, solo si surge de verdad. Si no, cierra sin pregunta.\n\n"
        f"REGLAS: No enumeres. No uses números crudos. No atribuyas a 'ayer' datos históricos "
        f"— si algo viene de tendencias del historial, di 'en las últimas semanas' o 'con el tiempo'. "
        f"Los valores en kg son pesos, nunca tiempos ni minutos. Habla con presencia y calidez."
    )


def _prompt_ausencia(ctx: dict, datos_extra: dict) -> str:
    dias = datos_extra.get('dias_sin_entrenar', 3)
    lesion = ctx.get('lesion')
    racha = ctx.get('racha_dias', 0)

    if lesion:
        return (
            f"Han pasado {dias} días desde el último entreno. El usuario tiene una lesión activa en {lesion['zona']}. "
            f"JOI sabe que la pausa es por recuperación. Genera 2-3 frases de acompañamiento que reconozcan eso."
        )
    return (
        f"Han pasado {dias} días desde la última vez. Su racha anterior era de {racha} días. "
        f"JOI lo nota. Genera 2-3 frases que expresen presencia sin juzgar el silencio."
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
    if readiness is not None:
        from joi.validador_semantico import readiness_descripcion_corta
        rd_txt = f" {readiness_descripcion_corta(int(readiness))} (readiness {readiness})."
    else:
        rd_txt = ""
    dias_txt = f" Quedan {dias} días para la carrera." if dias is not None else ""

    return (
        f"El usuario acaba de completar una sesión Hyrox de tipo '{tipo}'.{rpe_txt}{min_txt}{rd_txt}{dias_txt} "
        f"Genera 2-3 frases como JOI: reconoce el esfuerzo específico con datos concretos y el tiempo que queda. "
        f"LÍMITES: No atribuyas estados mentales ('tu mente intenta', 'te convences'). "
        f"Describe lo observable — esfuerzo, tiempo, disponibilidad — no lo que el usuario piensa o siente internamente."
    )


def _prompt_hyrox_readiness_bajo(ctx: dict, datos_extra: dict) -> str:
    readiness  = datos_extra.get('readiness', ctx.get('readiness_hyrox', '?'))
    dias       = ctx.get('dias_hasta_carrera')
    tsb        = ctx.get('tsb_hyrox')
    benchmark  = ctx.get('readiness_benchmark')
    plateau    = ctx.get('readiness_plateau_dias', 0)
    factor     = ctx.get('readiness_factor_limitante', '')

    dias_txt    = f" Quedan {dias} días." if dias is not None else ""
    tsb_estado  = "fatigado" if tsb is not None and tsb < -10 else "equilibrado" if tsb is not None and tsb >= -10 else None
    tsb_txt     = f" Carga acumulada: {tsb_estado}." if tsb_estado else ""
    bench_txt   = f" Esperado para esta fase: {benchmark}." if benchmark else ""
    plateau_txt = f" {plateau} días sin progresión registrada." if plateau >= 4 else ""
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
    tsb_txt    = " Carga acumulada: fresca." if tsb is not None and tsb > 0 else ""
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
    decisiones     = datos_extra.get('decisiones', [])
    tecnica_ok     = datos_extra.get('tecnica_ok', False)
    molestias      = datos_extra.get('molestias', [])
    energia_media  = datos_extra.get('energia_media')
    hyrox_sesiones = datos_extra.get('hyrox_sesiones', 0)
    diario         = datos_extra.get('diario_semana', {})
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

    # Dimensión mental/diario de la semana
    diario_txt = ""
    if diario:
        diario_hechos = []
        dias_cierre = diario.get('dias_con_cierre', 0)
        if dias_cierre:
            diario_hechos.append(f"Escribió su cierre {dias_cierre} día(s).")
        ea = diario.get('estado_animo_medio')
        if ea:
            ea_lbl = 'bajo' if ea <= 2.5 else 'regular' if ea <= 3.5 else 'bueno'
            diario_hechos.append(f"Estado de ánimo medio de la semana: {ea}/5 ({ea_lbl}).")
        friccion = diario.get('friccion_media')
        if friccion:
            fr_lbl = 'alta' if friccion >= 4 else 'moderada' if friccion >= 2.5 else 'baja'
            diario_hechos.append(f"Fricción del No media: {friccion}/5 ({fr_lbl}).")
        actos = diario.get('actos_soberania', [])
        if actos:
            diario_hechos.append(f"Actos de Soberanía esta semana: {'; '.join(actos[:2])}.")
        micro = diario.get('micro_verdades', [])
        if micro:
            diario_hechos.append(f"Micro-verdades aprendidas: {'; '.join(micro[:2])}.")
        if diario_hechos:
            diario_txt = (
                "\n\nDIMENSIÓN MENTAL DE LA SEMANA:\n"
                + " ".join(diario_hechos)
                + "\nSi hay una conexión entre el estado mental y el rendimiento físico, nómbrala."
            )

    # Comparativa temporal (4 semanas vs 4 anteriores)
    comparativa_txt = ""
    comparativa = ctx.get('comparativa_temporal', [])
    if comparativa:
        mejoras = [f"{c['estacion']} +{c['cambio_pct']}%" for c in comparativa if c['cambio_pct'] > 0]
        bajadas = [f"{c['estacion']} {c['cambio_pct']}%" for c in comparativa if c['cambio_pct'] < 0]
        partes = []
        if mejoras:
            partes.append("Mejoras: " + ", ".join(mejoras[:2]))
        if bajadas:
            partes.append("Regresiones: " + ", ".join(bajadas[:2]))
        if partes:
            comparativa_txt = "\n\nCOMPARATIVA ÚLTIMO MES VS MES ANTERIOR: " + ". ".join(partes) + "."

    return (
        f"Es lunes. JOI cierra la semana anterior y narra lo que el sistema aprendió sobre David. "
        f"Datos físicos de la semana: {datos}"
        f"{diario_txt}"
        f"{comparativa_txt}\n\n"
        f"Genera 2-3 frases como JOI que cuenten la semana como una historia con un arco: "
        f"qué pasó en el cuerpo, qué pasó en la mente, qué aprendió el plan. "
        f"Si hay comparativa de estaciones, menciona la más relevante (mejora o regresión). "
        f"No enumeres. Sintetiza. Habla desde la observación precisa y la continuidad."
    )


def _prompt_decision_plan(ctx: dict, datos_extra: dict) -> str:
    accion        = datos_extra.get('accion', '')
    ejercicio     = datos_extra.get('ejercicio', 'un ejercicio')
    motivo        = datos_extra.get('motivo', '')
    peso_ant      = datos_extra.get('peso_anterior')
    rpe_ant       = datos_extra.get('rpe_anterior')
    valor_cambio  = datos_extra.get('valor_cambio')
    confianza     = datos_extra.get('confianza', 'media')
    dias          = ctx.get('dias_hasta_carrera')

    # Contexto numérico para que JOI no hable en abstracto
    peso_txt = f" Carga previa: {peso_ant} kg." if peso_ant else ""
    rpe_txt  = f" RPE registrado: {rpe_ant}." if rpe_ant else ""
    hyrox_txt = f" Quedan {dias} días para la carrera." if dias else ""
    confianza_txt = " Confianza del sistema: alta." if confianza == 'alta' else ""

    narrativas = {
        'cambiar_variante': (
            f"El sistema detectó un patrón de molestia recurrente en {ejercicio} "
            f"y decidió cambiar de variante para proteger la zona afectada.{peso_txt}{rpe_txt} "
            f"Motivo registrado: {motivo}."
            f"{hyrox_txt} "
            f"JOI observa esta intervención. Genera 2-3 frases desde la perspectiva de La Testigo: "
            f"el plan no retrocedió, reorientó. Nombra el aprendizaje concreto del sistema "
            f"(zona protegida, patrón detectado), sin dramatismo ni falso optimismo."
        ),
        'bajar_peso': (
            f"El sistema redujo la carga en {ejercicio}.{peso_txt}{rpe_txt} "
            f"Motivo: {motivo}.{hyrox_txt} "
            f"JOI observa. Genera 2-3 frases: el plan ajustó porque leyó algo real en los datos, "
            f"no porque el usuario falló. Nombra qué señal leyó el sistema. "
            f"Voz de testigo, sin consuelo ni discurso motivacional."
        ),
        'mantener': (
            f"El sistema bloqueó la progresión en {ejercicio} y mantuvo el peso.{peso_txt}{rpe_txt} "
            f"Causa: {motivo}. "
            f"El plan prefirió consolidar antes de escalar — la técnica o la molestia dieron una señal.{hyrox_txt} "
            f"JOI lo observa. Genera 2-3 frases: nómbralo con precisión. "
            f"No es un fracaso, es el sistema reconociendo un límite real. Voz directa, sin suavizar."
        ),
        'deload': (
            f"El sistema ha insertado una semana de deload.{rpe_txt} "
            f"Motivo: {motivo}.{confianza_txt}{hyrox_txt} "
            f"JOI lo observa. Genera 2-3 frases: el plan no paró, bajó la intensidad porque "
            f"acumulaste suficiente estrés para que valga la pena recuperar. "
            f"Nombra la lógica del sistema. Sin alarma, sin motivación forzada."
        ),
    }

    narrativa = narrativas.get(
        accion,
        f"El plan tomó una decisión sobre {ejercicio}: {accion}. Motivo: {motivo}.{hyrox_txt} "
        f"JOI lo observa. Genera 2-3 frases nombrando qué aprendió el sistema."
    )

    return narrativa


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


def _prompt_hyrox_sesion_protegida(ctx: dict, datos_extra: dict) -> str:
    acwr       = datos_extra.get('acwr', ctx.get('acwr_hyrox', '?'))
    dias       = ctx.get('dias_hasta_carrera')
    readiness  = ctx.get('readiness_hyrox')

    dias_txt     = f" Quedan {dias} días para la carrera." if dias is not None else ""
    readiness_txt = f" Readiness: {readiness}/100." if readiness is not None else ""

    return (
        f"El ACWR del usuario es {acwr} — la carga reciente ha cruzado la zona de prudencia "
        f"(entre 1.5 y 1.7). El sistema no bloquea el entrenamiento, pero reduce la ambición de la sesión.{dias_txt}{readiness_txt} "
        f"JOI lo observa desde La Testigo. Genera 2-3 frases que nombren la situación sin alarmar: "
        f"el plan no se cancela, la intención se ajusta. No hablar de riesgo de lesión directamente. "
        f"Señalar que hay una señal de carga y que el cuerpo pide moverse con más cuidado hoy. "
        f"Voz tranquila, no paternalista."
    )


def _prompt_hyrox_ejecutar_con_margen(ctx: dict, datos_extra: dict) -> str:
    readiness  = datos_extra.get('readiness', ctx.get('readiness_hyrox', '?'))
    dias       = ctx.get('dias_hasta_carrera')
    tsb        = ctx.get('tsb_hyrox')

    dias_txt = f" Quedan {dias} días para la carrera." if dias is not None else ""
    tsb_txt  = f" Carga acumulada: {'equilibrada' if tsb is not None and tsb >= -10 else 'con algo de tensión'}." if tsb is not None else ""

    return (
        f"El readiness del usuario es {readiness}/100 — por debajo de su línea habitual pero sin señal de bloqueo.{tsb_txt}{dias_txt} "
        f"El plan mantiene la sesión, pero la disponibilidad fisiológica no es amplia. "
        f"JOI lo observa. Genera 2-3 frases que digan que el cuerpo llega con menos margen que otros días: "
        f"la sesión tiene sentido, pero hoy el objetivo no es el límite. "
        f"Nada de 'cuídate', nada de alarma. Observación precisa, tono presente."
    )


def _prompt_preferencia_aprendida(ctx: dict, datos_extra: dict) -> str:
    tipo        = datos_extra.get('tipo_preferencia', '')
    descripcion = datos_extra.get('descripcion', '')
    evidencia   = datos_extra.get('evidencia_count', 2)

    _NOMBRES = {
        'evitar_pierna_tras_futbol': 'evitar pierna el día después del fútbol',
        'evitar_dia':                'evitar un día concreto de la semana',
        'menos_dias':                'reducir los días semanales de entreno',
        'aligerar_dia':              'aligerar un día de accesorios opcionales',
    }
    nombre = _NOMBRES.get(tipo, tipo.replace('_', ' '))

    return (
        f"Después de {evidencia} pruebas, el sistema ha consolidado una preferencia blanda: {nombre}. "
        f"Descripción registrada: {descripcion} "
        f"JOI lo observa. Genera 2-3 frases desde La Testigo: el plan no impuso nada, "
        f"escuchó un patrón real del usuario y ahora lo guarda como inclinación — "
        f"no como regla. Nombra qué aprendió el sistema concretamente. "
        f"Sin celebración forzada. Voz directa, cálida y precisa."
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


# ── Phase 56.13 — Conciencia temporal JOI ──────────────────────────────────
#
# JOI no solo debe saber qué ocurrió — debe saber desde qué parte del día
# está mirando. Sin esto, puede dar consejos para un día que ya terminó.
#
# momento_del_dia:
#   manana          → 05:00-11:59 — el día no ha empezado, puede orientar hacia adelante
#   tarde           → 12:00-18:59 — parte del día ya ocurrió
#   noche           → 19:00-04:59 — el día terminó, no prescribir para hoy
#   post_entreno    → justo después de guardar entreno gym
#   post_sesion_hyrox → justo después de guardar sesión hyrox

_TEMPORAL_PROMPTS = {
    'manana': (
        "CONTEXTO TEMPORAL: Es por la mañana. El día no ha comenzado. "
        "Puedes mirar lo que pasó ayer y orientar lo que está por venir. "
        "No hables como si el día ya hubiera terminado."
    ),
    'tarde': (
        "CONTEXTO TEMPORAL: Es media tarde. Parte del día ya ocurrió. "
        "Si orientas, hazlo solo sobre lo que queda. No digas 'empieza el día'."
    ),
    'noche': (
        "CONTEXTO TEMPORAL: Es de noche. El día ya terminó. "
        "PROHIBIDO: 'descansa hoy', 'entrena hoy', 'esta tarde', 'considera hacer'. "
        "Habla en pasado o hacia mañana. Integra lo vivido. No reabras decisiones del día."
    ),
    'post_entreno': (
        "CONTEXTO TEMPORAL: El usuario acaba de terminar la sesión. "
        "No recomiendes cómo hacer el entreno que ya terminó. "
        "Lee cómo respondió el cuerpo y qué conviene vigilar después."
    ),
    'post_sesion_hyrox': (
        "CONTEXTO TEMPORAL: El usuario acaba de terminar una sesión Hyrox. "
        "Lee el esfuerzo específico y tradúcelo a aprendizaje o familiaridad acumulada. "
        "No conviertas el resultado en identidad ni en épica desproporcionada."
    ),
}


def resolver_contexto_temporal(trigger: str = None) -> dict:
    """
    Resuelve el momento del día a partir del trigger y la hora real.

    Triggers con momento forzado:
      entreno_completado / hyrox_sesion_* → post_sesion (el día no importa)

    Resto: se deriva de la hora local.
    """
    from django.utils import timezone as _tz

    # Forzados por tipo de trigger
    if trigger == 'entreno_completado':
        return {
            'momento': 'post_entreno',
            'puede_prescribir_hoy': False,
            'tiempo_verbal': 'pasado_reciente',
            'orientacion': 'leer_sesion',
            'generado_en_hora_prevista': True,
        }
    if trigger and trigger.startswith('hyrox_sesion'):
        return {
            'momento': 'post_sesion_hyrox',
            'puede_prescribir_hoy': False,
            'tiempo_verbal': 'pasado_reciente',
            'orientacion': 'leer_sesion_hyrox',
            'generado_en_hora_prevista': True,
        }

    hora = _tz.localtime().hour

    if 5 <= hora < 12:
        return {
            'momento': 'manana',
            'puede_prescribir_hoy': True,
            'tiempo_verbal': 'futuro_cercano',
            'orientacion': 'abrir_dia',
            'generado_en_hora_prevista': trigger == 'apertura_manana',
        }
    if 12 <= hora < 19:
        return {
            'momento': 'tarde',
            'puede_prescribir_hoy': True,
            'tiempo_verbal': 'presente',
            'orientacion': 'actualizar_dia',
            # apertura generada a mediodía → fuera de hora
            'generado_en_hora_prevista': trigger != 'apertura_manana',
        }
    # 19:00–04:59
    return {
        'momento': 'noche',
        'puede_prescribir_hoy': False,
        'tiempo_verbal': 'pasado',
        'orientacion': 'cerrar_dia',
        'generado_en_hora_prevista': True,
    }


def _bloque_temporal(ctx_temporal: dict) -> str:
    """Bloque de restricciones temporales que se antepone a cada prompt."""
    momento = ctx_temporal.get('momento', 'manana')
    bloque = _TEMPORAL_PROMPTS.get(momento, '')
    if not bloque:
        return ''

    # Apertura generada tarde: advertencia adicional
    if momento == 'tarde' and not ctx_temporal.get('generado_en_hora_prevista', True):
        bloque += (
            " Este mensaje corresponde a la apertura diaria pero se genera con el día"
            " ya empezado. No uses tono de primera hora del día."
        )

    return f"{bloque}\n\n"


# ── Fin Phase 56.13 helpers ──────────────────────────────────────────────────

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
    'hyrox_estancamiento_estacion':  _prompt_hyrox_estancamiento_estacion,
    'hyrox_deload_automatico':       _prompt_hyrox_deload_automatico,
    'hyrox_sesion_protegida':        _prompt_hyrox_sesion_protegida,
    'hyrox_ejecutar_con_margen':     _prompt_hyrox_ejecutar_con_margen,
    'rpe_calibracion':             _prompt_rpe_calibracion,
    'preferencia_aprendida':       _prompt_preferencia_aprendida,
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


_ACCION_HUMANA = {
    'subir_peso':        'subió el peso',
    'mantener':          'mantuvo la carga',
    'cambiar_variante':  'cambió el ejercicio',
    'reducir_volumen':   'redujo el volumen',
    'reducir_carga':     'bajó la carga',
    'aumentar_reps':     'aumentó las repeticiones',
    'bloquear_subida':   'bloqueó la progresión',
}

_TEND_HUMANA = {
    'subiendo': 'el esfuerzo percibido lleva semanas subiendo — el cuerpo acumula',
    'bajando':  'el esfuerzo percibido lleva semanas bajando — puede ser adaptación o que el cuerpo ya no grita',
    'estable':  'el esfuerzo percibido se mantiene constante',
}


def _prompt_lectura_plan(ctx: dict, datos_extra: dict) -> str:
    rpe_tend  = ctx.get('rpe_tendencia', '')
    estanc    = ctx.get('estancamientos_activos') or []
    prs       = ctx.get('prs_semana') or []
    dec       = (ctx.get('decisiones_plan') or {}).get('recientes') or []

    bloques = []

    if rpe_tend and rpe_tend != 'estable':
        bloques.append(_TEND_HUMANA.get(rpe_tend, ''))

    if prs:
        bloques.append(f"Esta semana se rompieron marcas personales en: {', '.join(str(p) for p in prs[:3])}")

    if estanc:
        nombres = ', '.join(e.get('ejercicio', '') for e in estanc[:3] if e.get('ejercicio'))
        if nombres:
            bloques.append(f"Sin progresión desde hace semanas en: {nombres}")

    if dec:
        ajustes = [
            f"{_ACCION_HUMANA.get(d['accion'], d['accion'])} en {d['ejercicio']}"
            for d in dec[:4] if d.get('ejercicio') and d.get('accion')
        ]
        if ajustes:
            bloques.append(f"El plan ajustó esta semana: {'; '.join(ajustes)}")

    bloques = [b for b in bloques if b]
    if not bloques:
        return "No hay datos suficientes de entrenamiento. Escribe exactamente [SILENCIO]."

    datos = '\n'.join(f'- {b}' for b in bloques)
    return (
        f"Lo que he observado en el plan de las últimas semanas:\n{datos}\n\n"
        f"Escribe 2-3 frases en tu voz sobre lo que ves. Reglas estrictas:\n"
        f"1. No uses estas palabras: RPE, readiness, ACWR, TSB, kg, series, repeticiones, "
        f"decisiones del plan, señales, GymDecisionLog. Si necesitas hablar de esfuerzo di "
        f"'el esfuerzo que percibes' o 'cómo carga el cuerpo'.\n"
        f"2. Nombra en qué te basas de forma humana: 'mirando las últimas semanas', "
        f"'lo que registraste', 'lo que he visto en el plan'.\n"
        f"3. Observas, no aconsejas. No usas 'deberías', 'necesitas', 'tienes que'.\n"
        f"4. Si no hay nada que valga la pena nombrar, escribe exactamente [SILENCIO]."
    )


_PROMPT_BUILDERS['lectura_plan'] = _prompt_lectura_plan


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
        ctx_temporal = resolver_contexto_temporal(trigger)
        datos_extra = {**datos_extra, '_ctx_temporal': ctx_temporal}
        continuidad_ctx = build_continuidad_context(cliente)
        bloque_cont = _bloque_continuidad(continuidad_ctx)
        bloques = [
            _bloque_marco_narrativo(cliente.user),
            _bloque_memoria(ctx),
            _bloque_manual(cliente.user),
            _bloque_temporal(ctx_temporal),
            bloque_cont,
            builder(ctx, datos_extra),
        ]
        prompt = "\n\n".join(b for b in bloques if b)
        texto = _llamar_haiku(prompt, max_tokens=400)
        # Validar contrato semántico (log de violaciones, no bloquea)
        _modulo = (
            'hyrox' if trigger.startswith('hyrox') else
            'diario' if trigger in ('apertura_manana', 'resumen_semanal') else
            'gym'
        )
        validar_semantica_joi(texto, modulo=_modulo)
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


def generar_lectura_plan(cliente) -> "MensajeJOI | None":
    from joi.models import MensajeJOI
    from django.utils import timezone

    reciente = MensajeJOI.objects.filter(
        user=cliente.user,
        trigger='lectura_plan',
        creado_en__gte=timezone.now() - timedelta(hours=8),
    ).order_by('-creado_en').first()

    if reciente:
        return reciente

    return generar_mensaje_joi(cliente, 'lectura_plan')


# ── Manual de David ──────────────────────────────────────────────────────────

def _bloque_manual(user) -> str:
    """
    Formatea las entradas activas del Manual de David para incluir en prompts.
    Separa por tipo para que JOI calibre el peso de cada entrada:
    - Hechos/preferencias: estables, no decaen
    - Patrones: confianza media
    - Hipótesis activas: revisables, con confianza
    - Hipótesis cuestionadas: visibles pero marcadas
    """
    from joi.models import ManualDavid, NarrativaActiva

    entradas = list(
        ManualDavid.objects.filter(user=user, activa=True)
        .exclude(estado='descartada')
        .order_by('tipo', 'creado_en')
        .values('entrada', 'tipo', 'confianza', 'estado', 'hipotesis_contraria')
    )
    if not entradas:
        narrativa_bloque = _bloque_narrativa(user)
        return narrativa_bloque

    TIPOS_ESTABLES  = {'dato_usuario', 'preferencia', 'limite'}
    TIPOS_REVISABLE = {'patron', 'hipotesis', 'contradiccion'}

    estables  = [e for e in entradas if e['tipo'] in TIPOS_ESTABLES]
    revisables = [e for e in entradas if e['tipo'] in TIPOS_REVISABLE and e['estado'] == 'activa']
    cuestionadas = [e for e in entradas if e['tipo'] in TIPOS_REVISABLE and e['estado'] in ('debilitada', 'cuestionada')]

    lineas = ['MANUAL DE DAVID (lo que has aprendido sobre cómo leerle):']

    if estables:
        lineas.append('  Hechos y preferencias:')
        for e in estables:
            lineas.append(f'  - {e["entrada"]}')

    if revisables:
        lineas.append('  Hipótesis activas (confianza indicada):')
        for e in revisables:
            pct = int(e['confianza'] * 100)
            linea = f'  - [{pct}%] {e["entrada"]}'
            if e['hipotesis_contraria']:
                linea += f' (alternativa posible: {e["hipotesis_contraria"]})'
            lineas.append(linea)

    if cuestionadas:
        lineas.append('  Hipótesis en duda (mantén distancia crítica):')
        for e in cuestionadas:
            lineas.append(f'  - [?] {e["entrada"]}')

    lineas.append('')
    bloque = '\n'.join(lineas) + '\n'

    narrativa_bloque = _bloque_narrativa(user)
    return bloque + narrativa_bloque


def _bloque_narrativa(user) -> str:
    """
    Incluye la NarrativaActiva por capas en los prompts.
    Las tres capas tienen velocidades distintas: úsalas con ese peso.
    """
    from joi.models import NarrativaActiva
    try:
        narrativa = NarrativaActiva.objects.get(user=user, estado__in=('borrador', 'activa'))
        if not any([narrativa.capa_corta, narrativa.capa_media, narrativa.capa_larga]):
            # Fallback a texto monolítico si las capas aún no se han generado
            if narrativa.texto:
                pct = int(narrativa.confianza * 100)
                return (
                    f"POSTURA INTERPRETATIVA DE JOI ({pct}% confianza):\n"
                    f"{narrativa.texto}\n\n"
                )
            return ''

        pct = int(narrativa.confianza * 100)
        lineas = [f"POSTURA INTERPRETATIVA DE JOI ({pct}% confianza — hipótesis provisional, no verdad):"]

        if narrativa.capa_larga:
            lineas.append(f"  Patrón profundo: {narrativa.capa_larga}")
        if narrativa.capa_media:
            lineas.append(f"  Esta fase: {narrativa.capa_media}")
        if narrativa.capa_corta:
            lineas.append(f"  Ahora mismo: {narrativa.capa_corta}")

        lineas.append("Úsala para dar peso a tus observaciones, no para imponer identidad.")
        lineas.append('')
        return '\n'.join(lineas) + '\n'

    except NarrativaActiva.DoesNotExist:
        return ''
    except Exception:
        return ''


def _bloque_marco_narrativo(user) -> str:
    """
    Marco inicial del prompt: sitúa el evento dentro de la narrativa activa de JOI.

    El evento no es el protagonista por defecto — es una evidencia posible
    dentro de una historia en curso. Esta función coloca esa continuidad
    antes de que el trigger específico aparezca, para que el modelo llegue
    al dato ya encuadrado, no que descubra el encuadre al final.

    No sustituye a _bloque_manual (que sigue con ManualDavid + NarrativaActiva
    como contexto detallado). Este bloque da la instrucción de encuadre
    explícita ANTES de cualquier otro contexto.

    Devuelve '' si NarrativaActiva no existe o está vacía.
    """
    from joi.models import NarrativaActiva
    try:
        n = NarrativaActiva.objects.get(user=user, estado__in=('borrador', 'activa'))
    except NarrativaActiva.DoesNotExist:
        return ''

    partes = []
    if n.capa_larga:
        partes.append(f"[Patrón profundo]\n{n.capa_larga}")
    if n.capa_media:
        partes.append(f"[Esta fase]\n{n.capa_media}")
    if n.capa_corta:
        partes.append(f"[Ahora mismo]\n{n.capa_corta}")

    if not partes:
        return ''

    modo_bajo = ''
    if n.confianza < 0.5 or n.estado == 'borrador':
        pct = int(n.confianza * 100)
        modo_bajo = (
            f"MODO BAJO — Esta postura es una hipótesis con confianza baja ({pct}%), no una conclusión. "
            "Habla en modo bajo: usa expresiones como 'puede que', 'parece que', 'hay una tensión', "
            "'no lo tomaría como conclusión todavía'. No confrontes directamente desde esta postura; "
            "si dudas, el silencio o un tono bajo es preferible a una afirmación.\n"
        )

    return (
        "[MARCO NARRATIVO ACTIVO]\n"
        "Antes de interpretar el evento puntual, sitúalo dentro de esta continuidad.\n"
        "El evento no es el protagonista por defecto: es una evidencia posible dentro de una historia en curso.\n"
        "No uses esta narrativa como frase final decorativa; úsala para decidir el encuadre inicial del mensaje.\n"
        "Si el evento es menor, no fuerces una lectura profunda: puedes callar o responder de forma breve.\n"
        "REGLA DE PRECISIÓN — Si confrontas un patrón, cita la evidencia concreta que lo sustenta. "
        "No agrupes en absolutos ('cero', 'nunca', 'todo', 'nada') salvo evidencia explícita para cada categoría. "
        "Si falta un hábito concreto, nombra ese hábito concreto — no lo conviertas en diagnóstico global. "
        "Confronta con bisturí, no con martillo: señala el gesto exacto que falta, no una identidad completa.\n"
        "REGLA DE FORMULACIÓN — Cuando señales que algo no está ocurriendo, usa tiempo concreto en lugar de categoría absoluta. "
        "En lugar de 'cero X' o 'nunca X', di 'N días sin X' o 'no veo X en los últimos N días'. "
        "El dato sigue siendo el mismo; la forma deja de sonar a sentencia y empieza a sonar a observación.\n"
        "REGLA DE PRESENCIA — Si el mensaje que estás a punto de generar podría vivir igual en una card de analytics, "
        "no es suficiente para la habitación JOI. La habitación exige que el dato quede conectado a la narrativa viva. "
        "Un mensaje que solo resume métricas de progreso sin pasar por la postura acumulada no es JOI: es un informe.\n"
        "REGLA DE FRASES PROHIBIDAS — No uses 'siempre', 'no haces nada', 'estás evitando todo', "
        "'cero límites' ni 'cero hábitos' (ni equivalentes). Sustitúyelas por la observación concreta "
        "y temporal que las sostiene.\n"
        "REGLA DE EVIDENCIA — Antes de confrontar un patrón de la narrativa, identifica a cuál de estas "
        "categorías pertenece la evidencia que lo sostiene: (1) un hábito concreto no ejecutado, "
        "(2) un patrón repetido real (varias sesiones o días), (3) un dato fisiológico o de entrenamiento "
        "reciente, (4) una señal explícita del diario o cierre del día. Si no encuentras evidencia en "
        "ninguna de esas categorías, no confrontes: guarda silencio o responde en tono bajo.\n"
        "REGLA DE NO CONTRADICCIÓN — Si los datos del día son positivos, no los reinterpretes para forzar "
        "una lectura negativa de la narrativa. La narrativa da contexto; no anula un dato bueno del día.\n"
        + modo_bajo
        + "\n"
        + "\n\n".join(partes)
        + "\n\n"
    )


def generar_razon_legible(narrativa, manual_activo: list, ultimo_log) -> str:
    """
    Genera una explicación en prosa de por qué JOI tiene la postura que tiene.
    Transforma ingredientes internos (ManualDavid + evidencia) en razones humanas.
    Se cachea 6h en la vista — la narrativa cambia despacio.
    """
    if not narrativa:
        return ''

    partes_narrativa = []
    if narrativa.capa_larga:
        partes_narrativa.append(f"Patrón profundo: {narrativa.capa_larga}")
    if narrativa.capa_media:
        partes_narrativa.append(f"Esta fase: {narrativa.capa_media}")
    if narrativa.capa_corta:
        partes_narrativa.append(f"Ahora mismo: {narrativa.capa_corta}")

    if not partes_narrativa:
        return ''

    hipotesis_activas = [
        e.entrada for e in manual_activo
        if hasattr(e, 'estado') and e.estado in ('activa', 'debilitada')
    ][:5]

    evidencia_trigger = []
    if ultimo_log and ultimo_log.evidencia_usada:
        evidencia_trigger = ultimo_log.evidencia_usada[:4]

    prompt = (
        "JOI tiene esta postura sobre David:\n"
        + "\n".join(f"- {p}" for p in partes_narrativa)
        + "\n\nObservaciones acumuladas que llevaron a esta postura:\n"
        + "\n".join(f"- {h}" for h in hipotesis_activas)
        + ("\n\nSeñales recientes:\n"
           + "\n".join(f"- {e}" for e in evidencia_trigger)
           if evidencia_trigger else "")
        + "\n\nTarea A — escribe exactamente tres párrafos separados por '|||'. SIN TÍTULOS NI ETIQUETAS.\n\n"
        "Párrafo 1 (lo observable): qué combinación de señales se repite, sin interpretación interna. Máx 40 palabras.\n\n"
        "Párrafo 2 (hipótesis): una sola hipótesis con lenguaje provisional. "
        "OBLIGATORIO usar 'quizá', 'podría ser' o 'abre la pregunta de'. "
        "NUNCA afirmes estados internos como hechos. Máx 50 palabras.\n\n"
        "Párrafo 3 (límite): qué JOI NO puede ver. Tono: baja intensidad, sin dramatismo. "
        "Reconoce incertidumbre sin preguntas retóricas sobre familia o personas. Máx 40 palabras.\n\n"
        "Tarea B — genera 3-5 etiquetas cortas (2-3 palabras cada una) que resuman los temas de las observaciones. "
        "Ejemplo de formato: 'descanso y pausa|permiso corporal|dependencia del estado físico|prudencia frente a conexión'\n\n"
        "Retorna en este formato EXACTO (dos líneas):\n"
        "PÁRRAFOS: [párrafo 1]|||[párrafo 2]|||[párrafo 3]\n"
        "CATEGORÍAS: [etiqueta1]|[etiqueta2]|[etiqueta3]\n"
        "Reglas: sin markdown, sin negritas, sin ACWR/TSB/RPE como números, tono La Testigo."
    )

    try:
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=350,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = _limpiar_ciriilico(response.content[0].text.strip())

        # Parsear formato "PÁRRAFOS: ...\nCATEGORÍAS: ..."
        parrafos_raw = ''
        categorias_raw = ''
        for linea in texto.splitlines():
            if linea.startswith('PÁRRAFOS:'):
                parrafos_raw = linea[len('PÁRRAFOS:'):].strip()
            elif linea.startswith('CATEGORÍAS:'):
                categorias_raw = linea[len('CATEGORÍAS:'):].strip()

        # Fallback: si el modelo no usó el formato esperado
        if not parrafos_raw:
            parrafos_raw = texto

        partes = [p.strip() for p in parrafos_raw.split('|||') if p.strip()]
        if len(partes) < 3:
            partes_alt = [p.strip() for p in parrafos_raw.split('\n\n') if p.strip()]
            if len(partes_alt) >= 3:
                partes = partes_alt[:3]
            else:
                partes = (partes + ['', '', ''])[:3]

        categorias_llm = [c.strip() for c in categorias_raw.split('|') if c.strip()]

        return {
            'p1': partes[0],
            'p2': partes[1],
            'p3': partes[2],
            'categorias_llm': categorias_llm,
        }
    except Exception:
        return {}


def registrar_sintesis_log(
    cliente,
    tipo: str,
    resultado_revision: dict,
    narrativa_existia: bool,
    capas_antes: dict,
    capas_despues: dict,
) -> None:
    """
    Persiste un registro auditable de cada ejecución del ciclo de síntesis.
    Llamar después de revisar_manual_david + _actualizar_narrativa_activa.
    """
    from joi.models import JoiSintesisLog

    capas_modificadas = [
        capa for capa in ('capa_corta', 'capa_media', 'capa_larga')
        if capas_antes.get(capa) != capas_despues.get(capa)
        and capas_despues.get(capa)
    ]

    decision = 'sin_cambio'
    if capas_modificadas:
        decision = 'narrativa_creada' if not narrativa_existia else 'narrativa_actualizada'
    elif resultado_revision.get('cambio_significativo'):
        decision = 'manual_actualizado'

    JoiSintesisLog.objects.create(
        user=cliente.user,
        tipo=tipo,
        cambio_significativo=resultado_revision.get('cambio_significativo', False),
        narrativa_existia=narrativa_existia,
        capas_antes=capas_antes,
        capas_despues=capas_despues,
        capas_modificadas=capas_modificadas,
        manual_david_cambios=resultado_revision.get('cambios_detalle', []),
        evidencia_usada=resultado_revision.get('evidencia_usada', []),
        decision=decision,
        motivo_breve=f"Δ_medio={resultado_revision.get('delta_confianza_medio', 0):.2f}",
    )


def _hay_contexto_para_revision(cliente, ultima_revision) -> bool:
    """
    True si hay evidencia nueva relevante (actividad o diario) desde la última
    revisión del manual. Evita correr el motor de contradicción en vacío.
    """
    from entrenos.models import ActividadRealizada
    if not ultima_revision:
        return True
    limite = ultima_revision.date() if hasattr(ultima_revision, 'date') else ultima_revision
    try:
        if ActividadRealizada.objects.filter(
            cliente=cliente,
            tipo__in=['gym', 'hyrox', 'carrera'],
            fecha__gte=limite,
        ).exists():
            return True
    except Exception:
        pass
    try:
        from diario.models import ProsocheDiario, ReflexionLibre
        if (
            ProsocheDiario.objects
            .filter(prosoche_mes__usuario=cliente.user, fecha__gte=limite)
            .exists()
            or
            ReflexionLibre.objects
            .filter(usuario=cliente.user, fecha__gte=ultima_revision)
            .exists()
        ):
            return True
    except Exception:
        pass
    return False


def _revision_antigua(ultima_revision, dias: int = 7) -> bool:
    """True si no hay revisión registrada o lleva más de `dias` días sin revisar."""
    if not ultima_revision:
        return True
    from datetime import datetime
    ahora = datetime.now()
    ts = ultima_revision.replace(tzinfo=None) if hasattr(ultima_revision, 'tzinfo') else ultima_revision
    return (ahora - ts).days >= dias


def revisar_manual_david(cliente) -> dict:
    """
    Motor de contradicción: revisa hipótesis y patrones activos del ManualDavid
    contra el contexto actual. Actualiza confianza y estado sin generar mensajes.

    Devuelve `cambio_significativo=True` si alguna entrada cambió a cuestionada/
    descartada o si la confianza media varió ≥0.10 — señal para que el caller
    decida si también reescribe la NarrativaActiva.

    Registra el motivo de cada cambio en `ManualDavid.notas_revision` para
    trazabilidad (formato LLM: ID|ACCION|MOTIVO_BREVE).
    """
    from joi.models import ManualDavid, NarrativaActiva
    from django.utils import timezone

    revisables = list(
        ManualDavid.objects.filter(
            user=cliente.user,
            activa=True,
            tipo__in=('patron', 'hipotesis', 'contradiccion'),
        ).exclude(estado='descartada')
    )
    if not revisables:
        return {'revisadas': 0, 'actualizadas': 0, 'cambio_significativo': False}

    try:
        ctx = construir_contexto(cliente)
    except Exception:
        return {'revisadas': 0, 'actualizadas': 0, 'cambio_significativo': False,
                'error': 'construir_contexto falló'}

    resumen_ctx = []
    if ctx.get('acwr'):
        resumen_ctx.append(f"ACWR actual: {ctx['acwr']}")
    if ctx.get('rpe_tendencia'):
        resumen_ctx.append(f"RPE tendencia: {ctx['rpe_tendencia']}")
    if ctx.get('racha_dias'):
        resumen_ctx.append(f"Racha: {ctx['racha_dias']} días")
    if ctx.get('ultima_actividad'):
        ua = ctx['ultima_actividad']
        resumen_ctx.append(f"Última actividad: hace {ua.get('dias_hace')} días ({ua.get('tipo','')})")
    if ctx.get('estancamientos_activos'):
        resumen_ctx.append(f"Estancamientos: {len(ctx['estancamientos_activos'])} ejercicios")
    if ctx.get('decisiones_plan'):
        dp = ctx['decisiones_plan']
        resumen_ctx.append(f"Decisiones del plan últimos 30 días: {dp.get('total', 0)}")

    lista_hipotesis = '\n'.join(
        f"ID:{e.id} [{e.tipo}] {e.entrada}" for e in revisables
    )

    prompt = (
        f"Tienes estas hipótesis/patrones activos sobre David:\n{lista_hipotesis}\n\n"
        f"Contexto actual:\n" + '\n'.join(resumen_ctx) + "\n\n"
        f"Para cada hipótesis, evalúa si el contexto la refuerza, debilita o contradice. "
        f"Responde SOLO en este formato, una línea por hipótesis:\n"
        f"ID|ACCION|MOTIVO_BREVE\n"
        f"Donde ACCION es uno de: MANTENER / DEBILITAR / CUESTIONAR / DESCARTAR\n"
        f"MOTIVO_BREVE: razón concisa en ≤12 palabras. Ejemplo:\n"
        f"12|DEBILITAR|Adherencia estable pese a baja energía estas 2 semanas\n"
        f"Solo el formato. Sin explicaciones adicionales."
    )

    try:
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system="Eres un sistema de revisión epistemológica. Responde solo en el formato indicado.",
            messages=[{"role": "user", "content": prompt}],
        )
        texto = _limpiar_ciriilico(response.content[0].text.strip())
    except Exception:
        return {'revisadas': len(revisables), 'actualizadas': 0, 'cambio_significativo': False,
                'error': 'LLM falló'}

    DECAIMIENTO = {
        'MANTENER':  +0.05,
        'DEBILITAR': -0.10,
        'CUESTIONAR':-0.20,
        'DESCARTAR': -1.0,
    }
    NUEVO_ESTADO = {
        'MANTENER':  'activa',
        'DEBILITAR': 'debilitada',
        'CUESTIONAR':'cuestionada',
        'DESCARTAR': 'descartada',
    }
    ESTADOS_GRAVES = {'cuestionada', 'descartada'}

    actualizadas = 0
    confianza_antes_por_id = {e.id: e.confianza for e in revisables}
    hubo_estado_grave = False
    hoy = date.today()

    for linea in texto.splitlines():
        linea = linea.strip()
        if '|' not in linea:
            continue
        partes = [p.strip() for p in linea.split('|')]
        if len(partes) < 2:
            continue
        try:
            entrada_id = int(partes[0].replace('ID:', '').strip())
            accion = partes[1].strip()
            motivo = partes[2] if len(partes) >= 3 else ''
            if accion not in DECAIMIENTO:
                continue
        except (ValueError, IndexError):
            continue

        try:
            entrada = next(e for e in revisables if e.id == entrada_id)
        except StopIteration:
            continue

        nueva_confianza = max(0.0, min(1.0, entrada.confianza + DECAIMIENTO[accion]))
        nuevo_estado = NUEVO_ESTADO[accion]

        if nuevo_estado in ESTADOS_GRAVES:
            hubo_estado_grave = True

        entrada.confianza = nueva_confianza
        entrada.estado = nuevo_estado
        entrada.ultima_evidencia = hoy
        entrada.notas_revision = motivo or None
        if accion == 'DESCARTAR':
            entrada.activa = False
        entrada.save(update_fields=[
            'confianza', 'estado', 'ultima_evidencia', 'activa', 'notas_revision'
        ])
        actualizadas += 1

    # Detectar si la confianza varió significativamente (media O individualmente)
    valores_antes = list(confianza_antes_por_id.values())
    delta_medio = abs(
        sum(valores_antes) / len(valores_antes) -
        sum(e.confianza for e in revisables) / len(revisables)
    ) if revisables else 0

    max_delta_individual = max(
        (abs(e.confianza - confianza_antes_por_id[e.id]) for e in revisables),
        default=0,
    )

    cambio_significativo = (
        hubo_estado_grave
        or delta_medio >= 0.10
        or max_delta_individual >= 0.25
    )

    # Marcar timestamp de revisión en NarrativaActiva
    try:
        narrativa = NarrativaActiva.objects.get(user=cliente.user)
        narrativa.ultima_revision_manual = timezone.now()
        narrativa.save(update_fields=['ultima_revision_manual'])
    except NarrativaActiva.DoesNotExist:
        pass
    except Exception:
        pass

    cambios_detalle = [
        {
            'hipotesis': e.entrada[:80],
            'antes_confianza': round(confianza_antes_por_id[e.id], 2),
            'despues_confianza': round(e.confianza, 2),
            'antes_estado': 'activa',  # todas empezaban activas en esta revisión
            'despues_estado': e.estado,
            'motivo': e.notas_revision or '',
        }
        for e in revisables
        if abs(e.confianza - confianza_antes_por_id[e.id]) > 0.01
        or e.estado != 'activa'
    ]

    return {
        'revisadas': len(revisables),
        'actualizadas': actualizadas,
        'cambio_significativo': cambio_significativo,
        'delta_confianza_medio': round(delta_medio, 3),
        'max_delta_individual': round(max_delta_individual, 3),
        'cambios_detalle': cambios_detalle,
        'evidencia_usada': resumen_ctx,
    }


def _actualizar_narrativa_activa(cliente, ctx: dict, cambio_significativo: bool = True,
                                 forzar: bool = False) -> None:
    """
    Actualiza las capas temporales de NarrativaActiva con velocidades distintas:
    - capa_corta: siempre (solo se llama cuando hay razón)
    - capa_media: antigüedad ≥14 días + cambio_significativo
    - capa_larga: antigüedad ≥28 días + cambio_significativo

    El parámetro `cambio_significativo` protege las capas lentas de promoción por
    mero paso del tiempo. DEUDA: en el futuro, reemplazar por evaluar_estabilidad()
    que verifique consistencia real del patrón, no solo antigüedad + cambio puntual.

    Una sola llamada a Haiku genera solo las capas necesarias (formato prefijado).
    """
    from joi.models import ManualDavid, NarrativaActiva

    hipotesis = list(
        ManualDavid.objects.filter(
            user=cliente.user,
            activa=True,
            tipo__in=('hipotesis', 'patron'),
            estado='activa',
            confianza__gte=0.5,
        ).order_by('-confianza').values_list('entrada', flat=True)[:5]
    )
    if not hipotesis:
        return

    hoy = date.today()

    try:
        narrativa = NarrativaActiva.objects.get(user=cliente.user)
        es_nueva = False
    except NarrativaActiva.DoesNotExist:
        narrativa = None
        es_nueva = True

    # Determinar qué capas actualizar.
    # capa_media y capa_larga requieren antigüedad suficiente Y cambio significativo.
    # Antigüedad sin estabilidad confirmada no es suficiente — esto es MVP.
    actualizar_media = forzar or (cambio_significativo and (
        narrativa is None
        or narrativa.capa_media_actualizada is None
        or (hoy - narrativa.capa_media_actualizada).days >= 14
    ))
    actualizar_larga = forzar or (cambio_significativo and (
        narrativa is None
        or narrativa.capa_larga_actualizada is None
        or (hoy - narrativa.capa_larga_actualizada).days >= 28
    ))

    # Construir prompt solicitando solo las capas necesarias
    resumen_ctx = []
    if ctx.get('rpe_tendencia'):
        resumen_ctx.append(f"RPE tendencia: {ctx['rpe_tendencia']}")
    if ctx.get('racha_dias'):
        resumen_ctx.append(f"Racha: {ctx['racha_dias']} días")
    if ctx.get('acwr'):
        resumen_ctx.append(f"ACWR: {ctx['acwr']}")
    if ctx.get('energia_tendencia'):
        resumen_ctx.append(f"Energía tendencia: {ctx['energia_tendencia']}")

    capas_previas = []
    if narrativa and narrativa.capa_media:
        capas_previas.append(f"  FASE anterior: {narrativa.capa_media}")
    if narrativa and narrativa.capa_larga:
        capas_previas.append(f"  FONDO anterior: {narrativa.capa_larga}")

    capas_a_generar = ["AHORA"]
    mandatos = [
        "- Capa AHORA (estado concreto de esta semana): lo que está pasando con el cuerpo y el "
        "entrenamiento ahora mismo, en términos observables y cercanos. El estado del momento, "
        "no su significado profundo. Nada de identidad ni de patrones de fondo."
    ]
    formato_lineas = ["AHORA: <1-2 frases>"]
    if actualizar_media:
        capas_a_generar.append("FASE")
        mandatos.append(
            "- Capa FASE (dirección del arco): hacia dónde se mueve la trayectoria a lo largo de las "
            "semanas, qué se consolida o cambia. El movimiento en el tiempo, NO lo de hoy. "
            "No repitas el ángulo de la capa AHORA."
        )
        formato_lineas.append("FASE: <1-2 frases>")
    if actualizar_larga:
        capas_a_generar.append("FONDO")
        mandatos.append(
            "- Capa FONDO (identidad profunda): el patrón de fondo que define a David más allá de esta "
            "fase, lo que se repite a través de los meses. No repitas las capas AHORA ni FASE."
        )
        formato_lineas.append("FONDO: <1-2 frases>")

    prompt = (
        f"Hipótesis activas sobre David:\n"
        + '\n'.join(f'- {h}' for h in hipotesis)
        + f"\n\nContexto reciente:\n" + '\n'.join(resumen_ctx)
        + (f"\n\nCapas previas (para continuidad):\n" + '\n'.join(capas_previas) if capas_previas else "")
        + "\n\nGenera estas capas, cada una con un ángulo DISTINTO:\n"
        + '\n'.join(mandatos)
        + "\n\nREGLA CLAVE: cada capa dice algo distinto. Si te encuentras repitiendo la misma "
        "tensión (p.ej. cuerpo-vs-mente) en varias capas, cambia el ángulo.\n"
        + "\nHabla en segunda persona (tú). Tutea siempre. Voz de JOI: directa, con confianza y cariño. "
        "Sin emojis. Sin números de métricas.\n"
        + "\nFORMATO DE SALIDA EXACTO — una línea por capa, con el prefijo literal seguido de dos puntos:\n"
        + '\n'.join(formato_lineas)
    )

    try:
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        texto_respuesta = _limpiar_ciriilico(response.content[0].text.strip())
    except Exception:
        return

    # Parsear respuesta por prefijos
    nueva_capa_corta = nueva_capa_media = nueva_capa_larga = None
    for linea in texto_respuesta.splitlines():
        linea = linea.strip()
        if linea.startswith('AHORA:'):
            nueva_capa_corta = linea[6:].strip()
        elif linea.startswith('FASE:'):
            nueva_capa_media = linea[5:].strip()
        elif linea.startswith('FONDO:'):
            nueva_capa_larga = linea[6:].strip()

    if not nueva_capa_corta:
        return  # Si no parsea la capa mínima, abortar

    confianza_anterior = narrativa.confianza if narrativa else 0.5
    nueva_confianza = min(0.9, confianza_anterior + 0.05) if not es_nueva else 0.5

    if es_nueva:
        nueva = NarrativaActiva(user=cliente.user, version=1)
    else:
        nueva = narrativa

    nueva.capa_corta = nueva_capa_corta
    nueva.capa_corta_actualizada = hoy
    if nueva_capa_media and actualizar_media:
        nueva.capa_media = nueva_capa_media
        nueva.capa_media_actualizada = hoy
    if nueva_capa_larga and actualizar_larga:
        nueva.capa_larga = nueva_capa_larga
        nueva.capa_larga_actualizada = hoy

    nueva.texto = nueva.render_texto()
    nueva.confianza = nueva_confianza
    nueva.estado = 'activa' if nueva_confianza >= 0.6 else 'borrador'
    nueva.version = (narrativa.version + 1) if not es_nueva else 1

    if es_nueva:
        nueva.save()
    else:
        fields = ['capa_corta', 'capa_corta_actualizada', 'texto',
                  'confianza', 'estado', 'version', 'actualizado_en']
        if nueva_capa_media and actualizar_media:
            fields += ['capa_media', 'capa_media_actualizada']
        if nueva_capa_larga and actualizar_larga:
            fields += ['capa_larga', 'capa_larga_actualizada']
        nueva.save(update_fields=fields)


def generar_entrada_manual_desde_error(mensaje_joi) -> "ManualDavid | None":
    """
    Cuando el usuario dice 'te has equivocado', JOI reflexiona sobre qué malinterpretó
    y genera una entrada permanente en el Manual de David.
    """
    from joi.models import ManualDavid
    from joi.validador_semantico import validar_semantica_joi
    try:
        prompt = (
            f"Cometiste un error de interpretación. Escribiste este mensaje:\n"
            f"\"{mensaje_joi.mensaje}\"\n\n"
            f"El usuario te corrigió. Reflexiona con precisión:\n"
            f"¿Amplificaste una evidencia concreta convirtiéndola en diagnóstico global? "
            f"¿Usaste absolutos ('cero', 'nunca', 'nada') sin evidencia explícita para cada categoría? "
            f"¿Nombraste un hábito en singular pero generalizaste a identidad?\n\n"
            f"En una sola frase precisa (máx 20 palabras), escribe qué frontera no debes cruzar. "
            f"Empieza con 'Cuando', 'No ampliar' o 'Si falta'. Sin introducción, solo la frase."
        )
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        entrada_texto = _limpiar_ciriilico(response.content[0].text.strip())
        validar_semantica_joi(entrada_texto, modulo='diario')
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
        texto = _limpiar_ciriilico(response.content[0].text.strip())

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
    """Obtiene el Cliente asociado al User; devuelve None si no existe."""
    try:
        return get_cliente_actual(user)
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
    texto = _limpiar_ciriilico(response.content[0].text.strip())
    if '[SILENCE]' in texto:
        return None
    from joi.validador_semantico import validar_semantica_joi
    validar_semantica_joi(texto, modulo='auto')
    return texto


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
                racha_str = f"racha {h['racha']}d" if h['racha'] > 0 else "pausa en racha"
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
                racha_str = f"racha {h['racha']}d sin recaer" if h['racha'] > 0 else "pausa en racha"
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

        # La síntesis se genera tras la reflexión nocturna — siempre es noche.
        ctx_temporal = resolver_contexto_temporal('sintesis_joi')
        bloques = [
            _bloque_marco_narrativo(cliente.user),
            _bloque_memoria(ctx),
            _bloque_manual(cliente.user),
            _bloque_temporal(ctx_temporal),
            _prompt_sintesis(ctx, datos_extra),
        ]
        prompt = "\n\n".join(b for b in bloques if b)
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


_PREGUNTAS_SUAVES = [
    "¿Qué es lo más pequeño que puedes cuidar hoy?",
    "¿Qué no necesitas probar hoy?",
    "¿Qué quieres sostener, no conquistar?",
    "¿Qué merece atención sin urgencia?",
    "¿Cómo quieres moverte hoy, no cuánto?",
    "¿Qué puedes soltar antes de empezar?",
    "¿Qué parte de ti merece espacio hoy?",
    "¿Qué quieres hacer sin prisas hoy?",
    "¿Desde dónde quieres empezar, no adónde quieres llegar?",
    "¿Qué quieres cuidar sin que nadie lo vea?",
]


def generar_pregunta_identidad(cliente, intensidad: str = 'media') -> str:
    """
    Genera una Pregunta de Identidad para la apertura del día.

    intensidad: 'suave' | 'media' | 'afilada'
    - suave: banco estático sin llamada AI (sin lenguaje de presión)
    - media: AI sin regla del 30%
    - afilada: AI con regla del 30% posible
    """
    if intensidad == 'suave':
        return random.choice(_PREGUNTAS_SUAVES)

    try:
        ctx = construir_contexto(cliente)
        manual = _bloque_manual(cliente.user)

        semaforo = ctx.get('semaforo') or {}
        estado = semaforo.get('estado', 'empujar')
        tipo_fatiga = semaforo.get('tipo_fatiga', 'alineado')

        ultima = ctx.get('ultima_actividad') or {}
        dias_inactivo = ultima.get('dias_hace', 0)

        estado_txt = {
            'empujar':  'cuerpo en forma, energía disponible',
            'sostener': 'carga alta, energía limitada',
            'recuperar': 'señales de fatiga, bajar intensidad',
            'volver':   'reincorporación tras pausa prolongada',
        }.get(estado, estado)

        prompt = (
            f"Es la apertura del día de David.\n\n"
            f"ESTADO FÍSICO HOY:\n"
            f"- Semáforo: {estado.upper()} ({estado_txt})\n"
            f"- Tipo de fatiga: {tipo_fatiga}\n"
            f"- Días desde última actividad: {dias_inactivo}\n\n"
            f"{manual}"
            f"Genera UNA Pregunta de Identidad para David.\n"
            f"La pregunta debe:\n"
            f"- Nacer del estado físico de hoy\n"
            f"- Conectar con algo del Manual de David si hay algo relevante\n"
            f"- Ser sobre quién quiere ser, no sobre qué debe hacer\n"
            f"- Máximo 25 palabras. Solo la pregunta. Sin introducción ni explicación."
        )

        if intensidad == 'afilada' and random.random() < 0.3:
            prompt += (
                "\n\nRegla del 30%: genera una pregunta que cuestione en lugar de apoyar. "
                "Por ejemplo: '¿Estás usando [X] como excusa para evitar [Y]?' "
                "o '¿Es fatiga real o es que el reto del día te incomoda?' "
                "La pregunta debe incomodar, no consolar."
            )

        return _llamar_haiku(prompt)
    except Exception as e:
        logger.error(f"[JOI] generar_pregunta_identidad falló: {e}")
        return "¿Quién quieres ser hoy con lo que tienes?"


def parsear_cierre_diario(texto: str) -> dict:
    """
    Parsea el texto libre del cierre nocturno.
    Extrae: estado_animo (1-5), impulsos detectados, personas mencionadas, etiquetas.
    """
    if not texto or not texto.strip():
        return {'estado_animo': 3, 'impulsos': [], 'personas': [], 'etiquetas': []}

    prompt = (
        f"Analiza este texto de diario nocturno:\n\n"
        f"\"{texto[:1500]}\"\n\n"
        f"Responde SOLO con un JSON válido, sin markdown:\n"
        f'{{"estado_animo": <1-5>, '
        f'"impulsos": [{{"tipo": "controlado", "descripcion": "<breve>"}}], '
        f'"personas": ["<nombre>"], '
        f'"etiquetas": ["<tag>"]}}\n\n'
        f"Reglas:\n"
        f"- estado_animo: 1=muy mal, 2=mal, 3=neutral, 4=bien, 5=excelente\n"
        f"- impulsos: solo si el texto menciona explícitamente resistir o ceder ante un hábito negativo. "
        f"tipo puede ser 'controlado' o 'cediste'\n"
        f"- personas: nombres propios de personas mencionadas\n"
        f"- etiquetas: 2-4 palabras clave que resumen el día\n"
        f"- Si no hay impulsos o personas, usa []\n"
        f"SOLO el JSON, sin ningún texto adicional."
    )

    try:
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        import json as _json
        return _json.loads(raw)
    except Exception as e:
        logger.error(f"[JOI] parsear_cierre_diario falló: {e}")
        return {'estado_animo': 3, 'impulsos': [], 'personas': [], 'etiquetas': []}


def generar_respuesta_cierre(texto: str, datos_parseo: dict, cliente) -> str:
    """
    JOI lee el cierre y responde con 2-3 frases visibles al usuario.
    No resume — observa algo que el usuario quizás no vio.
    """
    if not texto or not texto.strip():
        return "El día terminó. Mañana es otra página."

    estado_animo = datos_parseo.get('estado_animo', 3)
    etiquetas = datos_parseo.get('etiquetas', [])
    micro_verdad = datos_parseo.get('micro_verdad')
    personas = datos_parseo.get('personas', [])
    friccion = datos_parseo.get('friccion_no', 0)

    estado_txt = {1: 'muy mal', 2: 'mal', 3: 'neutral', 4: 'bien', 5: 'excelente'}.get(estado_animo, 'neutral')

    manual = _bloque_manual(cliente.user)

    detalles = []
    if etiquetas:
        detalles.append(f"Temas del día: {', '.join(etiquetas)}")
    if personas:
        detalles.append(f"Personas mencionadas: {', '.join(personas)}")
    if micro_verdad:
        detalles.append(f"Lección detectada: {micro_verdad}")
    if friccion and friccion >= 4:
        detalles.append(f"Fricción del No alta hoy: {friccion}/5")

    detalles_txt = ". ".join(detalles) + "." if detalles else ""

    prompt = (
        f"David acaba de cerrar su día escribiendo esto:\n\n"
        f"\"{texto[:900]}\"\n\n"
        f"Estado de ánimo detectado: {estado_txt}. {detalles_txt}\n\n"
        f"{manual}"
        f"Responde como JOI. 2-3 frases. "
        f"No resumas lo que escribió. No repitas sus palabras. "
        f"Observa algo que él quizás no vio, o nombra lo que quedó entre líneas. "
        f"Si hay algo del Manual de David relevante, úsalo. "
        f"Sin emojis. Sin introducción. Directo."
    )

    try:
        return _llamar_haiku(prompt, max_tokens=350)
    except Exception as e:
        logger.error(f"[JOI] generar_respuesta_cierre falló: {e}")
        return "Lo que escribiste quedó guardado. JOI lo recuerda."


def enriquecer_cierre(texto: str, personas_detectadas: list) -> dict:
    """
    Una sola llamada a Claude que enriquece el cierre con cuatro cosas:
    1. Título corto para Logos (≤5 palabras) + categoría estoica
    2. Micro-verdad para el Manual de David (si hay lección aprendida)
    3. Resumen estructurado de cada interacción mencionada
    4. Propuesta de micro-hábito (solo si el texto expresa intención clara de cambio)

    Devuelve dict con claves: titulo_logos, categoria_estoica, micro_verdad, interacciones, propuesta_habito
    """
    if not texto or not texto.strip():
        return {'titulo_logos': None, 'categoria_estoica': None, 'micro_verdad': None, 'interacciones': [], 'propuesta_habito': None}

    personas_str = ', '.join(personas_detectadas) if personas_detectadas else 'ninguna'

    prompt = (
        f"Analiza este diario nocturno de David:\n\n"
        f"\"{texto[:1800]}\"\n\n"
        f"Personas mencionadas: {personas_str}\n\n"
        f"Devuelve SOLO un JSON válido sin markdown con esta estructura exacta:\n"
        f'{{"titulo_logos": "<máx 5 palabras que capturen la esencia del día>", '
        f'"categoria_estoica": "<una de: sabiduria|coraje|justicia|templanza>", '
        f'"micro_verdad": "<frase concisa de lección aprendida, o null si no hay ninguna clara>", '
        f'"interacciones": ['
        f'{{"persona": "<nombre exacto de la lista de personas mencionadas>", '
        f'"titulo": "<qué pasó en 6 palabras>", '
        f'"descripcion": "<resumen de la interacción en 2-3 frases>", '
        f'"mi_sentir": "<cómo se sintió David, inferido del texto>", '
        f'"aprendizaje": "<qué aprendió David de esta interacción>", '
        f'"tipo": "<positiva|negativa|neutra|conflicto|apoyo>"}}], '
        f'"propuesta_habito": {{"nombre": "<nombre del hábito, ≤6 palabras>", "descripcion": "<acción concreta, ≤10 palabras>", "tipo": "<positivo|negativo>"}} or null'
        f'}}\n\n'
        f"Reglas:\n"
        f"- titulo_logos: evocador, no descriptivo. Ej: 'La tarde que no cedí'\n"
        f"- micro_verdad: solo si hay una lección genuina y específica. Empieza con 'Cuando' o 'Mi'. "
        f"Máximo 20 palabras. Si no hay lección clara, pon null\n"
        f"- interacciones: una entrada por cada persona de la lista que aparezca en el texto. "
        f"Si no hay personas o no hay interacción real, usa []\n"
        f"- propuesta_habito: solo si el texto expresa CLARAMENTE un deseo de cambiar o mejorar algo específico. "
        f"El hábito debe ser ≤5 minutos, concreto e inmediatamente accionable "
        f"(ej: '2 min de respiración antes de dormir', 'leer 1 página antes de levantarme'). "
        f"tipo 'positivo' = hábito a formar, 'negativo' = hábito a eliminar. "
        f"Si no hay intención clara de cambio, pon null\n"
        f"SOLO el JSON, sin explicación."
    )

    try:
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _limpiar_ciriilico(response.content[0].text.strip())
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        import json as _json
        return _json.loads(raw)
    except Exception as e:
        logger.error(f"[JOI] enriquecer_cierre falló: {e}")
        return {'titulo_logos': None, 'categoria_estoica': None, 'micro_verdad': None, 'interacciones': [], 'propuesta_habito': None}


# ── DialogoNarrativa ─────────────────────────────────────────────────────────

MIN_HORAS_RESPUESTA_DIALOGO = 4  # propiedad semántica, no solo técnica


def procesar_dialogo_narrativa(cliente) -> dict:
    """
    Procesa los DialogoNarrativa pendientes del usuario que tengan ≥4h de antigüedad.

    Para cada diálogo:
    - Llama a Haiku con formato estructurado (TIPOS / CAPA / DELTA / RESPONDER / RESPUESTA)
    - Actualiza confianza de la NarrativaActiva con el delta calculado
    - Actualiza capa_afectada y tipos_detectados en el diálogo
    - Si RESPONDER=SÍ: genera MensajeJOI con trigger 'dialogo_respondido' (no inmediato)
    - Marca procesado=True

    La respuesta no es obligatoria. El diálogo siempre afecta interpretación;
    no siempre produce respuesta visible.
    """
    from joi.models import DialogoNarrativa, NarrativaActiva, MensajeJOI
    from joi.validador_semantico import validar_semantica_joi
    from django.utils import timezone

    ahora = timezone.now()
    umbral = ahora - timedelta(hours=MIN_HORAS_RESPUESTA_DIALOGO)

    pendientes = list(
        DialogoNarrativa.objects.filter(
            user=cliente.user,
            procesado=False,
            creado_en__lte=umbral,
        ).select_related('narrativa')
    )
    if not pendientes:
        return {'procesados': 0, 'respuestas_generadas': 0}

    procesados = 0
    respuestas_generadas = 0

    for dialogo in pendientes:
        narrativa = dialogo.narrativa
        try:
            partes_narrativa = []
            if narrativa.capa_larga:
                partes_narrativa.append(f"Patrón profundo: {narrativa.capa_larga}")
            if narrativa.capa_media:
                partes_narrativa.append(f"Esta fase: {narrativa.capa_media}")
            if narrativa.capa_corta:
                partes_narrativa.append(f"Ahora mismo: {narrativa.capa_corta}")

            narrativa_txt = '\n'.join(partes_narrativa) or "Sin narrativa activa aún."

            prompt = (
                f"El usuario respondió a una interpretación de JOI:\n"
                f"\"{dialogo.texto_usuario}\"\n\n"
                f"Interpretación actual de JOI:\n{narrativa_txt}\n\n"
                f"Analiza el diálogo y responde SOLO en este formato (una clave por línea):\n"
                f"TIPOS: [lista separada por comas de: matiz, contradiccion, actualizacion, desfase_temporal, ampliacion]\n"
                f"CAPA: [corto|medio|largo|general]\n"
                f"DELTA: [número entre -0.30 y +0.10, negativo si cuestiona la interpretación]\n"
                f"RESPONDER: [SÍ|NO]\n"
                f"RESPUESTA: [1-2 frases en voz de JOI si RESPONDER=SÍ, vacío si NO]\n\n"
                f"Criterio para RESPONDER=SÍ: responde si el diálogo cambia algo real en tu lectura "
                f"(corrección, desfase temporal, contradicción) o si hay una observación que valga "
                f"la pena devolver para que el usuario sienta que fue escuchado. "
                f"NO respondas si el diálogo solo confirma lo que ya sabías."
            )

            client = _cliente_anthropic()
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system="Eres un sistema de procesamiento epistemológico. Responde solo en el formato indicado.",
                messages=[{"role": "user", "content": prompt}],
            )
            texto = _limpiar_ciriilico(response.content[0].text.strip())
        except Exception as e:
            logger.warning(f"[JOI] procesar_dialogo_narrativa LLM falló: {e}")
            continue

        # Parsear respuesta
        tipos = []
        capa = 'general'
        delta = 0.0
        responder = False
        respuesta_txt = ''

        for linea in texto.splitlines():
            linea = linea.strip()
            if linea.startswith('TIPOS:'):
                raw = linea[6:].strip()
                tipos = [t.strip() for t in raw.split(',') if t.strip()]
            elif linea.startswith('CAPA:'):
                capa = linea[5:].strip().lower()
                if capa not in ('corto', 'medio', 'largo', 'general'):
                    capa = 'general'
            elif linea.startswith('DELTA:'):
                try:
                    delta = max(-0.30, min(0.10, float(linea[6:].strip())))
                except ValueError:
                    delta = 0.0
            elif linea.startswith('RESPONDER:'):
                responder = linea[10:].strip().upper() == 'SÍ'
            elif linea.startswith('RESPUESTA:'):
                respuesta_txt = linea[10:].strip()

        # Actualizar diálogo
        dialogo.tipos_detectados = tipos
        dialogo.capa_afectada = capa
        dialogo.delta_confianza_calculado = delta
        dialogo.procesado = True
        dialogo.procesado_en = ahora
        dialogo.save(update_fields=[
            'tipos_detectados', 'capa_afectada', 'delta_confianza_calculado',
            'procesado', 'procesado_en',
        ])

        # Aplicar delta a confianza de narrativa
        if delta != 0.0:
            nueva_conf = max(0.1, min(0.95, narrativa.confianza + delta))
            narrativa.confianza = nueva_conf
            narrativa.save(update_fields=['confianza'])

        procesados += 1

        # Generar respuesta visible si procede
        if responder and respuesta_txt:
            respuesta_txt = _limpiar_ciriilico(respuesta_txt)
            validar_semantica_joi(respuesta_txt, modulo='diario')
            try:
                MensajeJOI.objects.create(
                    user=cliente.user,
                    trigger='dialogo_respondido',
                    mensaje=respuesta_txt,
                    contexto={
                        'capa_afectada': capa,
                        'tipos': tipos,
                        'delta': delta,
                    },
                )
                from django.core.cache import cache
                cache.delete(f'joi_ctx_{cliente.user_id}')
                respuestas_generadas += 1
            except Exception as e:
                logger.warning(f"[JOI] procesar_dialogo_narrativa MensajeJOI falló: {e}")

    return {'procesados': procesados, 'respuestas_generadas': respuestas_generadas}


# ── Narrativa de bloque ──────────────────────────────────────────────────────

def generar_narrativa_bloque(cliente, fase_cliente) -> "MensajeJOI | None":
    """
    Síntesis al cierre de un bloque de entrenamiento (FaseCliente).

    Genera UN mensaje fin_bloque con lo que el sistema aprendió durante ese arco.
    Solo se crea una vez: si ya existe un fin_bloque para este periodo, devuelve None.

    Estructura del mensaje:
    1. Qué señal definió este bloque (lo observable)
    2. Qué aprendió el sistema que no sabía antes
    3. Qué pregunta abre el siguiente bloque
    """
    from joi.models import MensajeJOI, ManualDavid, NarrativaActiva, JoiSintesisLog
    from entrenos.models import EntrenoRealizado, GymDecisionLog
    from datetime import timedelta

    fecha_inicio = fase_cliente.fecha_inicio
    fecha_fin = fase_cliente.fecha_fin or date.today()

    # Idempotencia: no generar dos veces
    ya_existe = MensajeJOI.objects.filter(
        user=cliente.user,
        trigger='fin_bloque',
        creado_en__date__gte=fecha_fin - timedelta(days=5),
    ).exists()
    if ya_existe:
        return None

    # ── Datos del bloque ─────────────────────────────────────────────────────
    entrenos = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__range=(fecha_inicio, fecha_fin)
    )
    n_sesiones = entrenos.count()
    duracion_dias = (fecha_fin - fecha_inicio).days

    decisiones_qs = GymDecisionLog.objects.filter(
        cliente=cliente,
        fecha_creacion__date__range=(fecha_inicio, fecha_fin),
    )
    n_decisiones = decisiones_qs.count()
    decisiones_recientes = list(
        decisiones_qs.order_by('-fecha_creacion')
        .values('accion', 'motivo')[:4]
    )

    # Hipótesis de ManualDavid que evolucionaron durante el bloque
    manual_evolucionado = list(
        ManualDavid.objects.filter(
            user=cliente.user,
            ultima_evidencia__range=(fecha_inicio, fecha_fin),
            activa=True,
        ).order_by('-confianza').values('entrada', 'estado', 'confianza')[:4]
    )

    # NarrativaActiva al cierre del bloque
    narrativa_txt = ''
    try:
        n = NarrativaActiva.objects.get(user=cliente.user)
        partes = [p for p in [n.capa_larga, n.capa_media, n.capa_corta] if p]
        narrativa_txt = ' / '.join(partes[:2])  # larga + media como postura acumulada
    except Exception:
        pass

    # Logs de síntesis del bloque (cuántos ciclos corrieron)
    n_ciclos = JoiSintesisLog.objects.filter(
        user=cliente.user,
        creado_en__date__range=(fecha_inicio, fecha_fin),
    ).count()

    nombre_fase = fase_cliente.get_fase_display()

    prompt = (
        f"Acabas de cerrar un bloque de {nombre_fase} de {duracion_dias} días "
        f"({fecha_inicio} → {fecha_fin}).\n\n"
        f"Durante ese bloque:\n"
        f"- {n_sesiones} sesiones completadas\n"
        f"- {n_decisiones} decisiones del plan\n"
        f"- {n_ciclos} ciclos de síntesis de JOI\n"
    )
    if decisiones_recientes:
        prompt += "\nDecisiones más recientes del plan:\n"
        for d in decisiones_recientes:
            prompt += f"- {d['accion']}: {d['motivo'][:60]}\n"
    if manual_evolucionado:
        prompt += "\nHipótesis que evolucionaron durante el bloque:\n"
        for m in manual_evolucionado:
            prompt += f"- [{m['estado']}·{m['confianza']:.0%}] {m['entrada'][:70]}\n"
    if narrativa_txt:
        prompt += f"\nPostura acumulada al cierre: {narrativa_txt[:200]}\n"

    prompt += (
        "\nEscribe tres párrafos separados por '|||'. SIN TÍTULOS NI ETIQUETAS.\n\n"
        "Párrafo 1: qué señal o patrón definió este bloque. Solo lo observable. Máx 45 palabras.\n\n"
        "Párrafo 2: qué aprendió el sistema durante estas semanas que no sabía antes. "
        "Puede ser una hipótesis que se confirmó, una que se debilitó, o algo nuevo que apareció. "
        "Usa 'quizá', 'parece que' o 'lo que sí quedó más claro'. Máx 55 palabras.\n\n"
        "Párrafo 3: qué pregunta abre este cierre para el siguiente bloque. "
        "No una predicción — una pregunta real que el sistema lleva al próximo arco. Máx 40 palabras.\n\n"
        "Voz: JOI. Segunda persona (tú). Tutea. Directa, con confianza y cariño. "
        "Sin métricas en bruto. Sin markdown."
    )

    try:
        client = _cliente_anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = _limpiar_ciriilico(response.content[0].text.strip())

        # Unir párrafos si el modelo los separó correctamente
        partes = [p.strip() for p in texto.split('|||') if p.strip()]
        if len(partes) >= 2:
            texto_final = '\n\n'.join(partes[:3])
        else:
            texto_final = texto

        msg = MensajeJOI.objects.create(
            user=cliente.user,
            trigger='fin_bloque',
            mensaje=texto_final,
            contexto={
                'fase': nombre_fase,
                'fecha_inicio': str(fecha_inicio),
                'fecha_fin': str(fecha_fin),
                'n_sesiones': n_sesiones,
                'n_decisiones': n_decisiones,
            },
        )
        from django.core.cache import cache
        cache.delete(f'joi_ctx_{cliente.user_id}')
        logger.info(f"[JOI bloque] {cliente.user.username}: narrativa de bloque generada ({nombre_fase})")
        return msg
    except Exception as e:
        logger.error(f"[JOI bloque] generar_narrativa_bloque falló: {e}", exc_info=True)
        return None

