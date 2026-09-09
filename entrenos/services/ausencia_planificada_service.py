from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce

from entrenos.models import AusenciaPlanificadaGym, SesionProgramada


def _sesiones_afectadas(cliente, inicio, fin, *, bloquear=False):
    sesiones = SesionProgramada.objects
    if bloquear:
        sesiones = sesiones.select_for_update()
    return (
        sesiones
        .filter(cliente=cliente, estado=SesionProgramada.ESTADO_PENDIENTE)
        .filter(
            Q(pospuesta_hasta__isnull=True, fecha_prevista__range=(inicio, fin))
            | Q(pospuesta_hasta__range=(inicio, fin))
        )
        .annotate(fecha_efectiva_orden=Coalesce('pospuesta_hasta', 'fecha_prevista'))
        .order_by('fecha_efectiva_orden', 'id')
    )


def previsualizar_ausencia_planificada(cliente, inicio, fin):
    return [
        {
            'id': sesion.id,
            'nombre': sesion.nombre_sesion or 'Sesión Gym',
            'fecha_prevista': sesion.fecha_prevista,
            'fecha_efectiva': sesion.pospuesta_hasta or sesion.fecha_prevista,
        }
        for sesion in _sesiones_afectadas(cliente, inicio, fin)
    ]


def _omitir_sesiones(sesiones, ausencia):
    etiqueta = ausencia.get_motivo_display()
    for sesion in sesiones:
        sesion.estado = SesionProgramada.ESTADO_OMITIDA_USUARIO
        sesion.ausencia_planificada = ausencia
        sesion.motivo_estado = f'Ausencia planificada: {etiqueta}.'
        sesion.save(update_fields=['estado', 'ausencia_planificada', 'motivo_estado', 'actualizada_en'])


@transaction.atomic
def confirmar_ausencia_planificada(*, cliente, inicio, fin, motivo, nota=''):
    sesiones = list(_sesiones_afectadas(cliente, inicio, fin, bloquear=True))
    snapshot = [
        {
            'id': s.id,
            'nombre': s.nombre_sesion or 'Sesión Gym',
            'fecha_prevista': s.fecha_prevista.isoformat(),
            'pospuesta_hasta': s.pospuesta_hasta.isoformat() if s.pospuesta_hasta else None,
            'fecha_efectiva': (s.pospuesta_hasta or s.fecha_prevista).isoformat(),
        }
        for s in sesiones
    ]
    ausencia = AusenciaPlanificadaGym(
        cliente=cliente, inicio=inicio, fin=fin, motivo=motivo, nota=nota,
        sesiones_afectadas=len(sesiones), sesiones_snapshot=snapshot, deuda_generada=0,
    )
    ausencia.full_clean()
    ausencia.save()
    _omitir_sesiones(sesiones, ausencia)
    return ausencia
