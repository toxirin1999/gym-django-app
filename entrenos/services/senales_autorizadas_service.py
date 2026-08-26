"""API pública mínima de señales que Diario autorizó para el entrenador Gym."""

from django.db import transaction
from django.utils import timezone


SCHEMA_VERSION = 1
SIN_SENAL = {'hay_senal': False, 'schema_version': SCHEMA_VERSION}


def obtener_proyeccion_senal_autorizada(cliente, fecha_ref=None):
    """Devuelve únicamente campos deportivos consentidos y estructurados."""
    from entrenos.models import SenalEntrenamientoAutorizada

    fecha_ref = fecha_ref or timezone.localdate()
    senal = (
        SenalEntrenamientoAutorizada.objects
        .filter(
            cliente=cliente,
            estado=SenalEntrenamientoAutorizada.ESTADO_AUTORIZADA,
            vigente_desde__lte=fecha_ref,
            vigente_hasta__gte=fecha_ref,
            intervencion__estado='activa',
            intervencion__fecha_inicio__lte=fecha_ref,
            intervencion__fecha_fin__gte=fecha_ref,
        )
        .order_by('-autorizada_en', '-id')
        .first()
    )
    if senal is None:
        return dict(SIN_SENAL)
    return {
        'hay_senal': True,
        'schema_version': senal.schema_version,
        'senal_id': senal.id,
        'categoria': senal.categoria,
        'intensidad': senal.intensidad,
        'alcance': 'observacion',
        'vigente_desde': senal.vigente_desde.isoformat(),
        'vigente_hasta': senal.vigente_hasta.isoformat(),
        'sugerencia_id': senal.sugerencia_id,
        'intervencion_id': senal.intervencion_id,
        'origen': {'sistema': 'diario', 'tipo': 'tendencia_corporal'},
    }


@transaction.atomic
def revocar_senal_autorizada(senal, fecha_ref=None):
    """Retira consentimiento sin borrar la evidencia histórica; es idempotente."""
    from entrenos.models import IntervencionPlan, SenalEntrenamientoAutorizada

    senal = SenalEntrenamientoAutorizada.objects.select_for_update().get(pk=senal.pk)
    if senal.estado == SenalEntrenamientoAutorizada.ESTADO_REVOCADA:
        return senal
    senal.estado = SenalEntrenamientoAutorizada.ESTADO_REVOCADA
    senal.revocada_en = timezone.now()
    senal.save(update_fields=['estado', 'revocada_en', 'actualizada_en'])
    if senal.intervencion_id:
        IntervencionPlan.objects.filter(
            pk=senal.intervencion_id,
            estado=IntervencionPlan.ESTADO_ACTIVA,
        ).update(estado=IntervencionPlan.ESTADO_CANCELADA)
    return senal
