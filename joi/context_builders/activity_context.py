"""
Contexto de actividad reciente, carga unificada y ACWR.
Fuente canónica: ActividadRealizada (hub compartido entrenos+hyrox).
"""
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from entrenos.models import ActividadRealizada


def build_activity_context(cliente, hoy: date, semana_reciente: date) -> dict:
    ctx = {}

    # ── 1. ACTIVIDAD RECIENTE ────────────────────────────────────────────────
    ultima_actividad = (
        ActividadRealizada.objects
        .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
        .annotate(fecha_efectiva=Coalesce('fecha_realizado', 'fecha'))
        .order_by('-fecha_efectiva').first()
    )
    if ultima_actividad:
        fecha_ef = ultima_actividad.fecha_realizado or ultima_actividad.fecha
        ctx['ultima_actividad'] = {
            'fecha':     str(fecha_ef),
            'dias_hace': (hoy - fecha_ef).days,
            'tipo':      ultima_actividad.tipo,
            'titulo':    ultima_actividad.titulo or '',
        }

    acts_semana = (
        ActividadRealizada.objects
        .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
        .annotate(fecha_ef=Coalesce('fecha_realizado', 'fecha'))
        .filter(fecha_ef__gte=semana_reciente)
        .values('tipo').annotate(n=Count('id'))
    )
    ctx['actividad_semana']      = {a['tipo']: a['n'] for a in acts_semana}
    ctx['sesiones_semana_total'] = sum(ctx['actividad_semana'].values())
    ctx['sesiones_gym_semana']   = ctx['actividad_semana'].get('gym', 0)

    sesiones_recientes = list(
        ActividadRealizada.objects
        .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
        .annotate(fecha_efectiva=Coalesce('fecha_realizado', 'fecha'))
        .order_by('-fecha_efectiva')[:7]
        .values('fecha_efectiva', 'tipo', 'titulo', 'rpe_medio', 'duracion_minutos', 'carga_ua')
    )
    por_dia = defaultdict(list)
    for s in sesiones_recientes:
        por_dia[str(s['fecha_efectiva'])].append({
            'tipo':   s['tipo'],
            'titulo': (s['titulo'] or '').strip(),
            'rpe':    s['rpe_medio'],
            'min':    s['duracion_minutos'],
        })
    ctx['sesiones_recientes'] = [
        {'fecha': fecha, 'sesiones': sess}
        for fecha, sess in sorted(por_dia.items(), reverse=True)
    ]

    def _tiene_actividad_en(d):
        return (
            ActividadRealizada.objects
            .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
            .annotate(fecha_ef=Coalesce('fecha_realizado', 'fecha'))
            .filter(fecha_ef=d).exists()
        )

    racha = 0
    dia = hoy
    while _tiene_actividad_en(dia):
        racha += 1
        dia -= timedelta(days=1)
    ctx['racha_dias'] = racha

    if racha == 0:
        racha_previa = 0
        dia_prev = hoy - timedelta(days=1)
        while _tiene_actividad_en(dia_prev):
            racha_previa += 1
            dia_prev -= timedelta(days=1)
        if racha_previa > 0:
            ctx['racha_dias_previa'] = racha_previa

    # ── 2. CARGA UNIFICADA ───────────────────────────────────────────────────
    carga_semanas = []
    for i in range(3, -1, -1):
        ini = hoy - timedelta(days=7 * (i + 1))
        fin = hoy - timedelta(days=7 * i)
        total = ActividadRealizada.objects.filter(
            cliente=cliente, fecha__range=(ini, fin),
            carga_ua__isnull=False, tipo__in=['gym', 'hyrox', 'carrera']
        ).aggregate(total=Sum('carga_ua'))['total']
        carga_semanas.append(round(total) if total else 0)
    ctx['carga_semanas'] = carga_semanas if sum(1 for c in carga_semanas if c > 0) >= 2 else None

    # ── 3. ACWR ──────────────────────────────────────────────────────────────
    try:
        from entrenos.services.services import EstadisticasService
        acwr_data = EstadisticasService.analizar_acwr_unificado(cliente)
        ctx['acwr'] = round(acwr_data['acwr_actual'], 2) if acwr_data.get('acwr_actual') else None
    except Exception:
        ctx['acwr'] = None

    return ctx
