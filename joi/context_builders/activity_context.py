"""
Contexto de actividad reciente, carga unificada y ACWR — para JOI.

Phase 59X.B: los campos comunes (sesiones_gym_semana, sesiones_hyrox_semana,
sesiones_semana_total, actividad_semana, ultima_actividad, racha_dias,
fase_plan) ahora provienen de core.context.actividad_context — fuente única
compartida con el semáforo. Este builder agrega solo los enriquecimientos
específicos de JOI: sesiones_recientes, racha_dias_previa, carga_semanas, acwr.
"""
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Sum
from django.db.models.functions import Coalesce

from core.context.actividad_context import get_actividad_context
from entrenos.models import ActividadRealizada


def build_activity_context(cliente, hoy: date, semana_reciente: date) -> dict:
    # ── Campos comunes desde la fuente canónica ──────────────────────────────
    ctx = get_actividad_context(cliente, hoy)

    # ── Enriquecimientos específicos JOI ─────────────────────────────────────

    # Últimas 7 sesiones con detalle para el prompt
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

    # Racha previa (si la racha actual es 0) — contexto narrativo
    if ctx['racha_dias'] == 0:
        def _tiene_actividad_en(d):
            return (
                ActividadRealizada.objects
                .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
                .annotate(fecha_ef=Coalesce('fecha_realizado', 'fecha'))
                .filter(fecha_ef=d).exists()
            )
        racha_previa = 0
        dia_prev = hoy - timedelta(days=1)
        while _tiene_actividad_en(dia_prev):
            racha_previa += 1
            dia_prev -= timedelta(days=1)
        if racha_previa > 0:
            ctx['racha_dias_previa'] = racha_previa

    # Carga por semana (últimas 4 semanas)
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

    # ACWR calculado por EstadisticasService
    try:
        from entrenos.services.services import EstadisticasService
        acwr_data = EstadisticasService.analizar_acwr_unificado(cliente)
        ctx['acwr'] = round(acwr_data['acwr_actual'], 2) if acwr_data.get('acwr_actual') else None
    except Exception:
        ctx['acwr'] = None

    return ctx
