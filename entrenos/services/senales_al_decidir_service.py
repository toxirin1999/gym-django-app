"""«Qué sabía el entrenador al decidir» (17-nov-2026).

Cada decisión de carga guarda, en el momento de crearse, qué señales tenía el
entrenador y desde cuándo las tenía. Así, al revisar una decisión, se puede
distinguir «decidió mal» de «no sabía aún» (p. ej. la variabilidad del reloj
llegó después). Cada señal lleva ``disponible_desde`` (ISO) o None si no consta.
Nunca rompe el guardado: ante cualquier fallo devuelve lo que pudo calcular.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _num(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _iso(dt):
    return dt.isoformat() if dt else None


def calcular_senales(decision, ahora=None):
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    cliente = decision.cliente
    out = {'calculado_en': _iso(ahora)}

    try:
        from entrenos.services.estado_carga_service import estado_carga
        est = estado_carga(cliente, hoy)
        out['veredicto_dia'] = {
            'valor': est.get('respuesta'),
            'ratio_carga': _num((est.get('carga') or {}).get('ratio')),
            'disponible_desde': _iso(ahora),
            'nota': 'calculado al decidir; no es la hora en que se mostró en el panel',
        }
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: veredicto')

    try:
        from clientes.models import BitacoraDiaria
        b = (BitacoraDiaria.objects.filter(cliente=cliente, fecha=hoy).order_by('-id').first())
        if b is not None:
            out['salud_hoy'] = {
                'hrv_ms': b.hrv_ms,
                'horas_sueno': float(b.horas_sueno) if b.horas_sueno is not None else None,
                'disponible_desde': _iso(b.salud_importado_en),
            }
        else:
            out['salud_hoy'] = None
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: salud')

    try:
        origen = decision.entreno_origen
        if origen is not None:
            from entrenos.models import SerieRealizada
            editadas = SerieRealizada.objects.filter(
                entreno=origen, reps_editadas=True,
            ).count()
            out['sesion_origen'] = {
                'entreno_id': origen.pk,
                'fecha_plan': origen.fecha.isoformat(),
                'fecha_ejecucion': _iso(getattr(origen, 'fecha_ejecucion', None)),
                'series_con_reps_editadas': editadas,
            }
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: origen')

    out['ultima_vez'] = {
        'peso': _num(decision.peso_anterior),
        'reps': _num(decision.reps_anteriores),
        'rpe': _num(decision.rpe_anterior),
    }
    return out


def registrar_senales(decision):
    """Guarda las señales con .update() (sin disparar señales de nuevo)."""
    try:
        if decision.senales_al_decidir:
            return
        datos = calcular_senales(decision)
        type(decision).objects.filter(pk=decision.pk).update(senales_al_decidir=datos)
        decision.senales_al_decidir = datos
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: registrar')


def lineas_para_mostrar(decision):
    """Frases cortas para el detalle de la decisión; [] si no hay registro."""
    s = getattr(decision, 'senales_al_decidir', None) or {}
    lineas = []
    v = s.get('veredicto_dia')
    if v and v.get('valor'):
        lineas.append(f"Veredicto del día al decidir: {v['valor']} (carga {v.get('ratio_carga')}).")
    h = s.get('salud_hoy')
    if h:
        llegada = h.get('disponible_desde')
        lineas.append('Reloj de hoy: variabilidad %s ms, sueño %s h%s.' % (
            h.get('hrv_ms') if h.get('hrv_ms') is not None else '—',
            h.get('horas_sueno') if h.get('horas_sueno') is not None else '—',
            f', llegó {llegada[:16].replace("T", " ")}' if llegada else ', sin hora de llegada'))
    elif 'salud_hoy' in s:
        lineas.append('Reloj de hoy: sin datos cuando decidió.')
    o = s.get('sesion_origen')
    if o and o.get('series_con_reps_editadas'):
        lineas.append(f"{o['series_con_reps_editadas']} series con reps editadas a mano en la sesión de origen.")
    return lineas
