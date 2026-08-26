from django.db import IntegrityError, transaction
from django.utils import timezone

from .campaign_authority import exigir_registro_manual
from .models import HyroxObjective, HyroxSession, SolicitudHyroxPuntual


class IdempotencyKeyReutilizada(ValueError):
    """La clave ya representa una solicitud con contenido diferente."""


def objetivo_historico_para_extra(cliente):
    """Referencia propia, estable y puramente histórica para colgar el hecho."""
    return HyroxObjective.objects.filter(cliente=cliente).order_by(
        '-fecha_evento', '-fecha_creacion', '-pk'
    ).first()


def idempotency_key_extra_hoy(cliente, fecha=None):
    fecha = fecha or timezone.localdate()
    return f'hyrox-extra:{cliente.pk}:{fecha.isoformat()}'


def snapshots_extra(cliente, fecha=None):
    """Captura contexto verificable; no escribe ni decide sobre el plan Gym."""
    from entrenos.models import SesionProgramada
    from .campaign_authority import resolver_autoridad_campana
    from .models import UserInjury

    fecha = fecha or timezone.localdate()
    gym = SesionProgramada.objects.filter(
        cliente=cliente, fecha_prevista=fecha
    ).order_by('pk').first()
    lesion = UserInjury.objects.filter(cliente=cliente, activa=True).order_by('pk').first()
    return {
        'safety_snapshot': {
            'lesion_id': lesion.pk if lesion else None,
            'fase': lesion.fase if lesion else None,
            'tags_restringidos': list(lesion.tags_restringidos or []) if lesion else [],
        },
        'gym_contract_snapshot': {
            'sesion_programada_id': gym.pk if gym else None,
            'estado': gym.estado if gym else None,
            'fecha_prevista': str(gym.fecha_prevista) if gym else None,
        },
        'authority': resolver_autoridad_campana(cliente, fecha),
    }


def modulo_archivado_para_extra(cliente):
    """El CTA puntual no es una vía paralela durante una campaña declarada activa."""
    from .models import ContratoCampanaHyrox
    contrato = ContratoCampanaHyrox.objects.filter(cliente=cliente).order_by(
        '-version', '-pk'
    ).first()
    return contrato is None or contrato.estado in ('inactiva', 'finalizada')


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


@transaction.atomic
def abrir_registro_extra(*, cliente, actor, fecha=None):
    """Crea/reutiliza la única solicitud y su único esqueleto factual del día."""
    fecha = fecha or timezone.localdate()
    if not modulo_archivado_para_extra(cliente):
        raise PermissionError('El registro puntual extra solo está disponible con Hyrox archivado.')
    objective = objetivo_historico_para_extra(cliente)
    if objective is None:
        raise HyroxObjective.DoesNotExist('No hay objetivo Hyrox histórico propio.')
    snapshots = snapshots_extra(cliente, fecha)
    solicitud = autorizar_solicitud_extra(
        cliente=cliente,
        objective=objective,
        idempotency_key=idempotency_key_extra_hoy(cliente, fecha),
        fecha=fecha,
        safety_snapshot=snapshots['safety_snapshot'],
        gym_contract_snapshot=snapshots['gym_contract_snapshot'],
        actor=actor,
    )
    if solicitud.hyrox_session_id is None:
        sesion = HyroxSession.objects.create(
            objective=objective,
            fecha=fecha,
            estado='planificado',
            titulo='Sesión Hyrox puntual',
        )
        solicitud.hyrox_session = sesion
        solicitud.estado = 'en_registro'
        solicitud.save(update_fields=['hyrox_session', 'estado', 'actualizado_en'])
    elif solicitud.estado == 'autorizada':
        solicitud.estado = 'en_registro'
        solicitud.save(update_fields=['estado', 'actualizado_en'])
    return solicitud
