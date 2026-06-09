"""
core/context/actividad_context.py — Phase 59X.B

Módulo neutral: agrega actividad reciente y fase del plan sin depender
de JOI. Pueden consumirlo tanto el semáforo (core/daily_decision.py)
como los builders de JOI sin introducir imports circulares.

Fuente canónica: ActividadRealizada + FaseCliente.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count
from django.db.models.functions import Coalesce

from clientes.models import FaseCliente
from entrenos.models import ActividadRealizada

_TIPOS_ACTIVIDAD = ['gym', 'hyrox', 'carrera']


def get_actividad_context(cliente, hoy: date | None = None) -> dict:
    """
    Devuelve un dict con la actividad reciente del cliente.

    Campos garantizados (nunca KeyError):
        sesiones_gym_semana   int
        sesiones_hyrox_semana int
        sesiones_semana_total int
        actividad_semana      dict  {tipo: count}
        ultima_actividad      dict | None  {fecha, dias_hace, tipo, titulo}
        racha_dias            int
        fase_plan             dict | None  {tipo, nombre, es_descarga,
                                            dias_en_fase, dias_restantes?}
    """
    if hoy is None:
        hoy = date.today()
    semana_reciente = hoy - timedelta(days=7)

    ctx: dict = {
        'sesiones_gym_semana': 0,
        'sesiones_hyrox_semana': 0,
        'sesiones_semana_total': 0,
        'actividad_semana': {},
        'ultima_actividad': None,
        'racha_dias': 0,
        'fase_plan': None,
    }

    # ── 1. Última actividad ───────────────────────────────────────
    try:
        ultima = (
            ActividadRealizada.objects
            .filter(cliente=cliente, tipo__in=_TIPOS_ACTIVIDAD)
            .annotate(fecha_efectiva=Coalesce('fecha_realizado', 'fecha'))
            .order_by('-fecha_efectiva')
            .first()
        )
        if ultima:
            fecha_ef = ultima.fecha_realizado or ultima.fecha
            ctx['ultima_actividad'] = {
                'fecha':     str(fecha_ef),
                'dias_hace': (hoy - fecha_ef).days,
                'tipo':      ultima.tipo,
                'titulo':    ultima.titulo or '',
            }
    except Exception:
        pass

    # ── 2. Conteo de sesiones esta semana por tipo ────────────────
    try:
        acts_semana = (
            ActividadRealizada.objects
            .filter(cliente=cliente, tipo__in=_TIPOS_ACTIVIDAD)
            .annotate(fecha_ef=Coalesce('fecha_realizado', 'fecha'))
            .filter(fecha_ef__gte=semana_reciente)
            .values('tipo')
            .annotate(n=Count('id'))
        )
        por_tipo = {a['tipo']: a['n'] for a in acts_semana}
        ctx['actividad_semana']       = por_tipo
        ctx['sesiones_gym_semana']    = por_tipo.get('gym', 0)
        ctx['sesiones_hyrox_semana']  = por_tipo.get('hyrox', 0)
        ctx['sesiones_semana_total']  = sum(por_tipo.values())
    except Exception:
        pass

    # ── 3. Racha de días consecutivos con actividad ───────────────
    try:
        racha = 0
        dia = hoy
        while (
            ActividadRealizada.objects
            .filter(cliente=cliente, tipo__in=_TIPOS_ACTIVIDAD)
            .annotate(fecha_ef=Coalesce('fecha_realizado', 'fecha'))
            .filter(fecha_ef=dia)
            .exists()
        ):
            racha += 1
            dia -= timedelta(days=1)
        ctx['racha_dias'] = racha
    except Exception:
        pass

    # ── 4. Fase del plan activa (FaseCliente) ─────────────────────
    try:
        from django.db.models import Q
        fase_actual = (
            FaseCliente.objects
            .filter(cliente=cliente)
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
            .order_by('-fecha_inicio')
            .first()
        )
        if fase_actual:
            dias_en_fase = (hoy - fase_actual.fecha_inicio).days
            fp = {
                'tipo':         fase_actual.fase,
                'nombre':       fase_actual.get_fase_display(),
                'es_descarga':  fase_actual.fase == 'descarga',
                'dias_en_fase': dias_en_fase,
            }
            if fase_actual.fecha_fin:
                fp['dias_restantes'] = (fase_actual.fecha_fin - hoy).days
            ctx['fase_plan'] = fp
    except Exception:
        pass

    return ctx
