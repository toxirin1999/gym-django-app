"""
Phase 15 — Visual plan memory calendar.

Shows the last N weeks as a color-coded grid of dots.
Not an obligation calendar — a memory of how the plan adapted to real life.

States (priority order when a day has multiple records):
    completada_normal    — green:      session done, full
    completada_esencial  — amber:      session done, essential mode
    saltada              — gray:       user explicitly skipped
    omitida_sistema      — gray_tenue: system reconciliation dropped it
    pendiente            — blue:       still pending (future or recent)
    pospuesta            — blue_dim:   pending but postponed
    sin_registro         — None:       no SesionProgramada or EntrenoRealizado

Additional markers (shown on top of the state dot):
    intervencion_activa  — violet indicator: IntervencionPlan was active this day
    carga_mantenida      — small lock: any EjercicioRealizado had progresion_bloqueada

The calendar does NOT call PlanificadorHelms — only reads persisted records.
This makes it fast and independent of algorithmic plan changes.
"""

from datetime import timedelta
from django.utils import timezone

from entrenos.models import EntrenoRealizado, SesionProgramada, IntervencionPlan


_COLOR_MAP = {
    'completada_normal':    'verde',
    'completada_esencial':  'ambar',
    'saltada':              'gris',
    'omitida_sistema':      'gris_tenue',
    'pendiente':            'azul',
    'pospuesta':            'azul_dim',
    'sin_registro':         None,
}


def _determinar_estado(sp, er, fecha, hoy):
    """
    Priority: completada > saltada > omitida > pendiente > pospuesta > sin_registro
    """
    if er:
        return 'completada_esencial' if er.modo_reducido else 'completada_normal'

    if sp:
        if sp.estado == SesionProgramada.ESTADO_COMPLETADA:
            return 'completada_normal'  # completed via sesion_programada link but no er today
        if sp.estado == SesionProgramada.ESTADO_SALTADA_USUARIO:
            return 'saltada'
        if sp.estado == SesionProgramada.ESTADO_OMITIDA_SISTEMA:
            return 'omitida_sistema'
        if sp.estado == SesionProgramada.ESTADO_CANCELADA_LESION:
            return 'omitida_sistema'
        if sp.estado == SesionProgramada.ESTADO_PENDIENTE:
            if sp.pospuesta_hasta and sp.pospuesta_hasta > fecha:
                return 'pospuesta'
            return 'pendiente'

    return 'sin_registro'


def generar_calendario_plan(cliente, num_semanas=4, fecha_ref=None):
    """
    Returns a list of week dicts, oldest first, each with 7 day dicts.

    Week dict:
        lunes: date
        dias: list of 7 day dicts

    Day dict:
        fecha: date
        estado: str (see _COLOR_MAP)
        color: str | None
        es_hoy: bool
        es_futuro: bool
        intervencion_activa: bool
        carga_mantenida: bool
        sesion_programada: SesionProgramada | None
        entreno_realizado: EntrenoRealizado | None
        detalle: dict (for tooltip/panel)
    """
    fecha_ref = fecha_ref or timezone.localdate()
    lunes_actual = fecha_ref - timedelta(days=fecha_ref.weekday())
    lunes_inicio = lunes_actual - timedelta(weeks=num_semanas - 1)
    fecha_fin = lunes_actual + timedelta(days=6)

    # Batch-fetch all SesionProgramada and EntrenoRealizado in range
    sesiones_sp = {
        sp.fecha_prevista: sp
        for sp in SesionProgramada.objects.filter(
            cliente=cliente,
            fecha_prevista__gte=lunes_inicio,
            fecha_prevista__lte=fecha_fin,
        )
    }

    entrenos = {
        er.fecha: er
        for er in EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=lunes_inicio,
            fecha__lte=fecha_fin,
        ).order_by('-fecha')  # latest if multiple (keep last)
    }

    # Batch-fetch active interventions per date range
    intervenciones = list(IntervencionPlan.objects.filter(
        cliente=cliente,
        fecha_inicio__lte=fecha_fin,
        fecha_fin__gte=lunes_inicio,
        estado=IntervencionPlan.ESTADO_ACTIVA,
    ))

    def _tiene_intervencion(fecha):
        return any(i.fecha_inicio <= fecha <= i.fecha_fin for i in intervenciones)

    def _carga_mantenida(er):
        if not er:
            return False
        try:
            return er.ejercicios_realizados.filter(progresion_bloqueada=True).exists()
        except Exception:
            return False

    semanas = []
    fecha_iter = lunes_inicio
    while fecha_iter <= lunes_actual:
        dias = []
        for offset in range(7):
            fecha = fecha_iter + timedelta(days=offset)
            sp = sesiones_sp.get(fecha)
            er = entrenos.get(fecha)
            estado = _determinar_estado(sp, er, fecha, fecha_ref)
            es_futuro = fecha > fecha_ref

            nombre_sesion = (
                (sp.nombre_sesion if sp else None)
                or (er.rutina.nombre if er and er.rutina_id else None)
                or ''
            )
            fecha_realizada = er.fecha if er else (sp.fecha_realizada if sp else None)

            detalle = {
                'nombre_sesion':     nombre_sesion,
                'estado':            estado,
                'fecha_prevista':    sp.fecha_prevista if sp else None,
                'fecha_realizada':   fecha_realizada,
                'modo_reducido':     er.modo_reducido if er else False,
                'carga_mantenida':   _carga_mantenida(er),
                'motivo':            sp.motivo_estado if sp else '',
            }

            dias.append({
                'fecha':              fecha,
                'estado':             estado if not es_futuro else 'futuro',
                'color':              _COLOR_MAP.get(estado) if not es_futuro else None,
                'es_hoy':             fecha == fecha_ref,
                'es_futuro':          es_futuro,
                'intervencion_activa': _tiene_intervencion(fecha) and not es_futuro,
                'carga_mantenida':    _carga_mantenida(er),
                'sesion_programada':  sp,
                'entreno_realizado':  er,
                'detalle':            detalle,
            })

        semanas.append({
            'lunes': fecha_iter,
            'dias': dias,
        })
        fecha_iter += timedelta(weeks=1)

    return semanas
