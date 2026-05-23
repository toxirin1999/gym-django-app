"""
Phase Diario-Gym 3.5 — Sugerencia corporal autorizable.

El diario no interviene el entrenamiento; pide permiso para que el plan vigile una señal.

CONTRACT:
- Solo crea sugerencia si tendencia corporal es 'notable'.
- No duplica: respeta cooldown, descarte y aceptación previa.
- No crea si ya hay IntervencionPlan vigilar_senal activa.
- No modifica el plan.
"""

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

_PATRON = 'diario_tendencia_corporal'
_TEXTO = (
    'El diario y los entrenos vienen dejando una señal corporal repetida. '
    'Puedes vigilarla durante 14 días sin cambiar el plan.'
)


def get_sugerencia_diario(cliente, fecha_ref=None):
    """
    Devuelve la SugerenciaPlan pendiente de tipo diario_tendencia_corporal,
    creándola si hay tendencia notable y no existe una activa.

    Returns SugerenciaPlan | None.
    """
    from entrenos.models import IntervencionPlan, SugerenciaPlan

    fecha_ref = fecha_ref or timezone.localdate()

    # Si ya hay intervención de vigilancia activa, no mostrar propuesta
    ya_activa = IntervencionPlan.objects.filter(
        cliente=cliente,
        tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        estado=IntervencionPlan.ESTADO_ACTIVA,
        fecha_fin__gte=fecha_ref,
    ).exists()
    if ya_activa:
        return None

    existente = (
        SugerenciaPlan.objects
        .filter(cliente=cliente, patron=_PATRON)
        .order_by('-fecha_generada')
        .first()
    )

    if existente:
        if existente.estado == SugerenciaPlan.ESTADO_DESCARTADA:
            return None
        if existente.estado in (SugerenciaPlan.ESTADO_ACEPTADA, SugerenciaPlan.ESTADO_APLICADA):
            return None
        if existente.estado == SugerenciaPlan.ESTADO_IGNORADA:
            if existente.cooldown_hasta and existente.cooldown_hasta > fecha_ref:
                return None
            # Cooldown expirado — re-verificar tendencia antes de re-mostrar
            tendencia = _calcular_tendencia(cliente)
            if tendencia.get('nivel') != 'notable':
                return None
            existente.estado = SugerenciaPlan.ESTADO_PENDIENTE
            existente.cooldown_hasta = None
            existente.save(update_fields=['estado', 'cooldown_hasta'])
            return existente
        # pendiente
        return existente

    # Sin registro previo: verificar tendencia y crear
    tendencia = _calcular_tendencia(cliente)
    if tendencia.get('nivel') != 'notable':
        return None

    try:
        return SugerenciaPlan.objects.create(
            cliente=cliente,
            patron=_PATRON,
            texto=_TEXTO,
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
    except Exception:
        logger.exception('get_sugerencia_diario: error creando SugerenciaPlan')
        return None


def _calcular_tendencia(cliente):
    try:
        from diario.services.senales_entrenamiento import calcular_tendencia_senal
        return calcular_tendencia_senal(cliente.user)
    except Exception:
        return {'hay_tendencia': False}
