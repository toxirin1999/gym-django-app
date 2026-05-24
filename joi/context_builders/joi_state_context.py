"""
Contexto de estado JOI: historial de mensajes enviados y narrativa activa.
Permite a JOI no repetirse y construir continuidad narrativa longitudinal.
"""
from datetime import date


def build_joi_state_context(cliente, hoy: date) -> dict:
    ctx = {}

    # ── 8. MEMORIA JOI ───────────────────────────────────────────────────────
    from joi.models import MensajeJOI
    mensajes_previos = (
        MensajeJOI.objects
        .filter(user=cliente.user)
        .order_by('-creado_en')[:5]
    )
    historial = []
    for m in mensajes_previos:
        dias = (hoy - m.creado_en.date()).days
        ignorado = (not m.leido) and dias >= 1
        historial.append({
            'trigger':   m.trigger,
            'dias_hace': dias,
            'resumen':   m.mensaje[:100],
            'leido':     m.leido,
            'ignorado':  ignorado,
        })
    ctx['historial_joi'] = historial

    # ── NarrativaActiva ──────────────────────────────────────────────────────
    try:
        from joi.models import NarrativaActiva
        narrativa = NarrativaActiva.objects.get(
            user=cliente.user, estado__in=('borrador', 'activa')
        )
        ctx['narrativa_joi'] = {
            'texto':     narrativa.texto,
            'estado':    narrativa.estado,
            'confianza': narrativa.confianza,
            'version':   narrativa.version,
        }
    except Exception:
        pass

    return ctx
