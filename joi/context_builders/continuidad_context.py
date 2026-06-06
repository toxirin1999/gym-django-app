"""
Phase 56.15 — JOI continuity context builder.

Builds a context object that informs prompts about recent feedback
and blocked references, without interpreting message content.

Rule: JOI does not use memory to build more narrative;
it uses it to avoid repeating what did not resonate.
"""

from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

_DIAS_VENTANA_DEFAULT = 14
_DIAS_FEEDBACK_REDUCIDA = 7
_DIAS_FEEDBACK_SILENCIO = 3
_COUNT_SILENCIO = 2

# DB value → neutral context label
_FEEDBACK_LABEL = {
    'clavado':    'lo_has_leido_bien',
    'equivocado': 'no_encajo',
}


def build_continuidad_context(cliente, hoy=None, dias_ventana=_DIAS_VENTANA_DEFAULT):
    """
    Returns the continuity context dict for a cliente.

    Shape:
      hay_continuidad         bool
      modo                    "normal" | "reducida" | "silencio"
      feedback_negativo_reciente bool
      ultimo_mensaje          {id, tipo, fecha, feedback, extracto}
      referencias_bloqueadas  [{tipo, valor, motivo}]
      dias_ventana_referencias int
      instrucciones           [str]
    """
    if hoy is None:
        hoy = date.today()

    base = {
        'hay_continuidad': False,
        'modo': 'normal',
        'feedback_negativo_reciente': False,
        'ultimo_mensaje': {
            'id': None,
            'tipo': None,
            'fecha': None,
            'feedback': None,
            'extracto': None,
        },
        'referencias_bloqueadas': [],
        'dias_ventana_referencias': dias_ventana,
        'instrucciones': [],
    }

    try:
        ctx = _calcular_modo(cliente, hoy, base)
        ctx = _calcular_referencias_bloqueadas(cliente, hoy, ctx, dias_ventana)
        ctx = _generar_instrucciones(ctx)
        return ctx
    except Exception as e:
        logger.error('[build_continuidad_context] falló: %s', e)
        return base


# ── Capa 1: modo ─────────────────────────────────────────────────────────────

def _calcular_modo(cliente, hoy, ctx):
    from joi.models import MensajeJOI

    ultimo = (
        MensajeJOI.objects
        .filter(user=cliente.user)
        .order_by('-creado_en')
        .first()
    )

    if not ultimo:
        return ctx

    ctx['hay_continuidad'] = True
    extracto = (ultimo.mensaje or '')[:120]
    ctx['ultimo_mensaje'] = {
        'id': ultimo.id,
        'tipo': ultimo.trigger,
        'fecha': ultimo.creado_en.date(),
        'feedback': _FEEDBACK_LABEL.get(ultimo.feedback),
        'extracto': extracto or None,
    }

    ventana_silencio = hoy - timedelta(days=_DIAS_FEEDBACK_SILENCIO)
    ventana_reducida = hoy - timedelta(days=_DIAS_FEEDBACK_REDUCIDA)

    count_no_encajo = MensajeJOI.objects.filter(
        user=cliente.user,
        feedback='equivocado',
        creado_en__date__gte=ventana_silencio,
    ).count()

    if count_no_encajo >= _COUNT_SILENCIO:
        ctx['modo'] = 'silencio'
        ctx['feedback_negativo_reciente'] = True
    elif MensajeJOI.objects.filter(
        user=cliente.user,
        feedback='equivocado',
        creado_en__date__gte=ventana_reducida,
    ).exists():
        ctx['modo'] = 'reducida'
        ctx['feedback_negativo_reciente'] = True

    return ctx


# ── Capa 2: referencias bloqueadas ───────────────────────────────────────────

def _calcular_referencias_bloqueadas(cliente, hoy, ctx, dias_ventana):
    """
    Blocks Hyrox stations that appear in JOI context data
    but were NOT trained in the last dias_ventana days.
    Returns without blocking if there is no active HyroxObjective.
    """
    desde = hoy - timedelta(days=dias_ventana)
    bloqueadas = []

    try:
        from hyrox.models import HyroxActivity, HyroxObjective
        # Phase 59X.0: antes filtraba por un campo booleano inexistente en
        # HyroxObjective; el except lo tragaba y referencias_bloqueadas quedaba
        # mudo en silencio. El campo real es 'estado'.
        obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if not obj:
            ctx['referencias_bloqueadas'] = []
            return ctx

        entrenadas = set(
            HyroxActivity.objects
            .filter(
                sesion__objective=obj,
                sesion__fecha__gte=desde,
                nombre_ejercicio__isnull=False,
            )
            .exclude(nombre_ejercicio='')
            .values_list('nombre_ejercicio', flat=True)
            .distinct()
        )

        from joi.context_builders.hyrox_context import build_hyrox_context
        hyrox_ctx = build_hyrox_context(
            cliente=cliente, hoy=hoy,
            semana_reciente=hoy - timedelta(days=7),
        )

        en_contexto = set()
        for e in hyrox_ctx.get('estaciones_penalizadas', []):
            en_contexto.add(e['nombre'])
        for e in hyrox_ctx.get('estaciones_debiles_estandar', []):
            en_contexto.add(e['nombre'])
        for e in hyrox_ctx.get('comparativa_temporal', []):
            en_contexto.add(e.get('estacion', ''))

        for estacion in sorted(en_contexto):
            if estacion and estacion not in entrenadas:
                bloqueadas.append({
                    'tipo': 'ejercicio',
                    'valor': estacion,
                    'motivo': f'no_aparece_en_los_ultimos_{dias_ventana}_dias',
                })

    except Exception as e:
        logger.warning('[continuidad_context] referencias_bloqueadas falló: %s', e)

    ctx['referencias_bloqueadas'] = bloqueadas
    return ctx


# ── Capa 3: instrucciones para el prompt ─────────────────────────────────────

def _generar_instrucciones(ctx):
    instrucciones = []
    modo = ctx['modo']
    dias = ctx['dias_ventana_referencias']

    if modo == 'reducida':
        instrucciones.extend([
            "El mensaje anterior no encajó con el usuario. No sigas en la misma dirección.",
            "Baja la intensidad narrativa. Usa una lectura corporal simple y verificable.",
            "No conectes diario con cuerpo salvo señal corporal explícita en los datos.",
        ])
    elif modo == 'silencio':
        instrucciones.extend([
            "Varios mensajes recientes no encajaron. No intentes construir relato.",
            "Si no hay señal corporal clara, devuelve silencio.",
            "Si hay señal corporal clara, una sola frase práctica, nada más.",
        ])

    for ref in ctx['referencias_bloqueadas']:
        instrucciones.append(
            f"No menciones {ref['valor']} — "
            f"no aparece en los últimos {dias} días de entrenamiento."
        )

    ctx['instrucciones'] = instrucciones
    return ctx


# ── Capa B: bloque de texto para inyectar en prompts ─────────────────────────

def _bloque_continuidad(ctx: dict) -> str:
    """
    Converts a continuidad context dict into a prompt instruction block.
    Returns an empty string when there is nothing to restrict.
    """
    if not ctx.get('instrucciones') and not ctx.get('hay_continuidad'):
        return ''

    partes = []

    if ctx.get('instrucciones'):
        partes.append("RESTRICCIONES DE CONTINUIDAD:")
        for inst in ctx['instrucciones']:
            partes.append(f"- {inst}")

    ultimo = ctx.get('ultimo_mensaje') or {}
    if ultimo.get('feedback') == 'no_encajo' and ultimo.get('extracto'):
        partes.append(
            f"\nMensaje anterior que NO encajó (no continuar en esa dirección):\n"
            f"\"{ultimo['extracto']}\""
        )

    return '\n'.join(partes)
