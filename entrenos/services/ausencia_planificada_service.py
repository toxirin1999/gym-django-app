from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

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


def _validar_propietario(ausencia, cliente):
    if ausencia.cliente_id != cliente.id:
        raise PermissionError('La ausencia no pertenece al cliente.')


def previsualizar_ampliacion_ausencia(ausencia, nuevo_fin, *, cliente):
    _validar_propietario(ausencia, cliente)
    if ausencia.cancelada_en:
        raise ValueError('Una ausencia cancelada no se puede ampliar.')
    if nuevo_fin <= ausencia.fin:
        raise ValueError('La nueva fecha final debe ser posterior a la actual.')
    return previsualizar_ausencia_planificada(cliente, ausencia.fin + timedelta(days=1), nuevo_fin)


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


def _snapshot_sesion(sesion):
    return {
        'id': sesion.id,
        'nombre': sesion.nombre_sesion or 'Sesión Gym',
        'fecha_prevista': sesion.fecha_prevista.isoformat(),
        'pospuesta_hasta': sesion.pospuesta_hasta.isoformat() if sesion.pospuesta_hasta else None,
        'fecha_efectiva': (sesion.pospuesta_hasta or sesion.fecha_prevista).isoformat(),
    }


@transaction.atomic
def ampliar_ausencia_planificada(*, ausencia, nuevo_fin, cliente):
    ausencia = AusenciaPlanificadaGym.objects.select_for_update().get(pk=ausencia.pk)
    _validar_propietario(ausencia, cliente)
    if ausencia.cancelada_en:
        raise ValueError('Una ausencia cancelada no se puede ampliar.')
    if nuevo_fin <= ausencia.fin:
        raise ValueError('La nueva fecha final debe ser posterior a la actual.')
    sesiones = list(_sesiones_afectadas(
        cliente, ausencia.fin + timedelta(days=1), nuevo_fin, bloquear=True,
    ))
    ids_existentes = {item.get('id') for item in ausencia.sesiones_snapshot}
    nuevos_snapshot = [_snapshot_sesion(s) for s in sesiones if s.id not in ids_existentes]
    _omitir_sesiones(sesiones, ausencia)
    ausencia.fin = nuevo_fin
    ausencia.sesiones_snapshot = [*ausencia.sesiones_snapshot, *nuevos_snapshot]
    ausencia.sesiones_afectadas = len({item.get('id') for item in ausencia.sesiones_snapshot})
    ausencia.full_clean()
    ausencia.save(update_fields=['fin', 'sesiones_snapshot', 'sesiones_afectadas'])
    return ausencia


@transaction.atomic
def cancelar_tramo_restante_ausencia(*, ausencia, cliente):
    ausencia = AusenciaPlanificadaGym.objects.select_for_update().get(pk=ausencia.pk)
    _validar_propietario(ausencia, cliente)
    if ausencia.cancelada_en:
        return 0
    hoy = timezone.localdate()
    etiqueta_esperada = f'Ausencia planificada: {ausencia.get_motivo_display()}.'
    sesiones = list(
        SesionProgramada.objects.select_for_update()
        .filter(
            cliente=cliente, ausencia_planificada=ausencia,
            estado=SesionProgramada.ESTADO_OMITIDA_USUARIO,
            motivo_estado=etiqueta_esperada,
        )
        .filter(
            Q(pospuesta_hasta__isnull=True, fecha_prevista__gte=hoy)
            | Q(pospuesta_hasta__gte=hoy)
        )
    )
    snapshots = {item.get('id'): item for item in ausencia.sesiones_snapshot}
    restaurables = []
    for sesion in sesiones:
        snapshot = snapshots.get(sesion.id)
        fecha_prevista_actual = sesion.fecha_prevista.isoformat()
        pospuesta_actual = sesion.pospuesta_hasta.isoformat() if sesion.pospuesta_hasta else None
        if not snapshot or (
            snapshot.get('fecha_prevista') != fecha_prevista_actual
            or snapshot.get('pospuesta_hasta') != pospuesta_actual
        ):
            continue
        restaurables.append(sesion)
    for sesion in restaurables:
        sesion.estado = SesionProgramada.ESTADO_PENDIENTE
        sesion.ausencia_planificada = None
        sesion.motivo_estado = ''
        sesion.save(update_fields=['estado', 'ausencia_planificada', 'motivo_estado', 'actualizada_en'])
    ausencia.cancelada_en = timezone.now()
    ausencia.fecha_cancelacion_efectiva = hoy
    ausencia.save(update_fields=['cancelada_en', 'fecha_cancelacion_efectiva'])
    return len(restaurables)
