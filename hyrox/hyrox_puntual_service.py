from django.db import IntegrityError, transaction
from django.utils import timezone

from .campaign_authority import exigir_registro_manual
from .models import SolicitudHyroxPuntual


class IdempotencyKeyReutilizada(ValueError):
    """La clave ya representa una solicitud con contenido diferente."""


def _payload_coincide(solicitud, *, fecha, authority_snapshot, safety_snapshot,
                      gym_contract_snapshot, actor):
    return (
        solicitud.fecha == fecha
        and solicitud.modo == 'extra'
        and solicitud.resolucion_gym == 'ninguna'
        and solicitud.sesion_gym_programada_id is None
        and solicitud.fecha_reubicacion is None
        and solicitud.authority_snapshot == authority_snapshot
        and solicitud.safety_snapshot == safety_snapshot
        and solicitud.gym_contract_snapshot == gym_contract_snapshot
        and solicitud.actor_id == getattr(actor, 'pk', None)
    )


@transaction.atomic
def autorizar_solicitud_extra(*, cliente, objective, idempotency_key,
                              safety_snapshot, gym_contract_snapshot,
                              actor=None, fecha=None, modo='extra'):
    """Autoriza una captura puntual factual sin alterar la planificación Gym."""
    hoy = timezone.localdate()
    fecha = fecha or hoy
    if fecha != hoy:
        raise ValueError('Solo se puede autorizar una solicitud puntual para hoy.')
    if modo != 'extra':
        raise ValueError('Este servicio solo autoriza solicitudes en modo extra.')
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError('idempotency_key es obligatoria.')

    autoridad = exigir_registro_manual(
        cliente, fecha=fecha, objective=objective,
    )
    authority_snapshot = {
        **autoridad,
        'objective_id': objective.pk,
    }
    existente = SolicitudHyroxPuntual.objects.filter(
        cliente=cliente, idempotency_key=idempotency_key,
    ).first()
    payload = {
        'fecha': fecha,
        'authority_snapshot': authority_snapshot,
        'safety_snapshot': safety_snapshot,
        'gym_contract_snapshot': gym_contract_snapshot,
        'actor': actor,
    }
    if existente:
        if _payload_coincide(existente, **payload):
            return existente
        raise IdempotencyKeyReutilizada(
            'La idempotency_key ya fue usada con un payload diferente.'
        )

    try:
        with transaction.atomic():
            return SolicitudHyroxPuntual.objects.create(
                cliente=cliente,
                idempotency_key=idempotency_key,
                modo='extra',
                resolucion_gym='ninguna',
                estado='autorizada',
                **payload,
            )
    except IntegrityError:
        existente = SolicitudHyroxPuntual.objects.get(
            cliente=cliente, idempotency_key=idempotency_key,
        )
        if _payload_coincide(existente, **payload):
            return existente
        raise IdempotencyKeyReutilizada(
            'La idempotency_key ya fue usada con un payload diferente.'
        )
