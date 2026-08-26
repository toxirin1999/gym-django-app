from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hyrox.models import UserInjury
from rehab.models import EpisodioRehab, EventoAltaRehab


@transaction.atomic
def confirmar_alta_rehab(
    *, episodio, actor, confirmacion_usuario, nota_evidencia='',
    lesion_hyrox_id=None, fecha=None,
):
    """Cierra el episodio y, solo si está explícitamente vinculada, la lesión."""
    fecha = fecha or timezone.localdate()
    episodio = EpisodioRehab.objects.select_for_update().get(pk=episodio.pk)
    existente = EventoAltaRehab.objects.select_for_update().filter(
        episodio=episodio
    ).first()
    if existente:
        return existente
    if episodio.estado not in ('ACTIVO', 'PAUSADO'):
        raise ValidationError('Solo un episodio activo o pausado puede darse de alta.')
    if not confirmacion_usuario:
        raise ValidationError('Debes confirmar explícitamente que entrenas sin restricciones.')
    if actor is None or actor.pk is None or episodio.cliente.user_id != actor.pk:
        raise ValidationError('El actor no es propietario del episodio.')

    lesion = None
    if episodio.lesion_hyrox_id:
        lesion = UserInjury.objects.select_for_update().filter(
            pk=episodio.lesion_hyrox_id, cliente=episodio.cliente
        ).first()
        if lesion is None:
            raise ValidationError('El vínculo de lesión del episodio no es válido.')
        if lesion_hyrox_id and int(lesion_hyrox_id) != lesion.pk:
            raise ValidationError('La lesión confirmada no coincide con el vínculo del episodio.')
    elif lesion_hyrox_id:
        lesion = UserInjury.objects.select_for_update().filter(
            pk=lesion_hyrox_id, cliente=episodio.cliente
        ).first()
        if lesion is None:
            raise ValidationError('La lesión elegida no pertenece al episodio del usuario.')
        episodio.lesion_hyrox = lesion

    episodio.estado = 'ALTA'
    episodio.save(update_fields=['estado', 'lesion_hyrox'])
    if lesion is not None:
        # Update deliberado: el alta no ejecuta el hook prescriptivo de UserInjury.save().
        UserInjury.objects.filter(pk=lesion.pk).update(
            fase=UserInjury.Fase.RECUPERADO,
            activa=False,
            fecha_resolucion=fecha,
        )

    return EventoAltaRehab.objects.create(
        episodio=episodio,
        lesion_hyrox=lesion,
        fecha=fecha,
        actor=actor,
        nota_evidencia=str(nota_evidencia or '').strip(),
        motivo=EventoAltaRehab.MOTIVO_CONFIRMACION_USUARIO,
        confirmacion_usuario=True,
    )
