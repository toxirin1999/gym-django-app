"""Ciclo contractual de la intervención ``esenciales_frecuentes``."""

import logging

from django.db import transaction
from django.utils import timezone
from datetime import date

from entrenos.models import EntrenoRealizado, IntervencionPlan, SugerenciaPlan
from entrenos.services.contrato_sugerencia_service import (
    PATRON_V1, construir_contrato_sugerencia, validar_contrato_snapshot,
)

logger = logging.getLogger(__name__)


def producir_sugerencia_tras_finalizacion(cliente_id, fecha_ref=None):
    """Productor explícito e idempotente; se invoca tras finalizar una sesión."""
    from clientes.models import Cliente
    fecha_ref = fecha_ref or timezone.localdate()
    contrato = construir_contrato_sugerencia(
        Cliente.objects.get(pk=cliente_id), PATRON_V1, fecha_ref,
    )
    if not contrato.get('vigente'):
        return None
    with transaction.atomic():
        cliente = Cliente.objects.select_for_update().get(pk=cliente_id)
        if IntervencionPlan.objects.select_for_update().filter(
            cliente=cliente, origen_patron=PATRON_V1,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio__lte=fecha_ref, fecha_fin__gte=fecha_ref,
        ).exists():
            return None
        existentes = SugerenciaPlan.objects.filter(
            cliente=cliente, patron=PATRON_V1,
        ).exclude(estado=SugerenciaPlan.ESTADO_DESCARTADA).order_by('-pk')
        for existente in existentes:
            misma = (existente.contrato_snapshot or {}).get('evidencia') == contrato.get('evidencia')
            if (
                existente.estado == SugerenciaPlan.ESTADO_IGNORADA
                and existente.cooldown_hasta and existente.cooldown_hasta > fecha_ref
            ):
                return None
            if existente.estado == SugerenciaPlan.ESTADO_PENDIENTE and misma:
                return existente
            if existente.estado == SugerenciaPlan.ESTADO_PENDIENTE and not misma:
                existente.estado = SugerenciaPlan.ESTADO_DESCARTADA
                existente.save(update_fields=['estado'])
        return SugerenciaPlan.objects.create(
            cliente=cliente, patron=PATRON_V1,
            texto='Las versiones esenciales se están repitiendo.',
            contrato_snapshot=contrato,
        )


def programar_produccion_tras_finalizacion(entreno):
    """Registra el productor después del commit; nunca desde post_save."""
    def producir_seguro():
        try:
            producir_sugerencia_tras_finalizacion(entreno.cliente_id, timezone.localdate())
        except Exception:
            # La inteligencia posterior nunca invalida una sesión ya guardada.
            logger.exception('No se pudo producir la sugerencia tras finalizar entreno=%s', entreno.pk)
    transaction.on_commit(producir_seguro)


def _resultado_existente(intervencion):
    if not intervencion.sugerencia_id:
        return None
    return ((intervencion.sugerencia.contrato_snapshot or {}).get('evaluacion') or {}).get('resultado')


def evaluar_intervencion(intervencion, fecha_ref=None, aplicar=False):
    """Evalúa exactamente [inicio, fin], únicamente al día posterior o más tarde."""
    fecha_ref = fecha_ref or timezone.localdate()
    if isinstance(fecha_ref, str):
        fecha_ref = date.fromisoformat(fecha_ref)
    if aplicar:
        return _evaluar_intervencion_atomica(intervencion.pk, fecha_ref)
    if (
        intervencion.estado == IntervencionPlan.ESTADO_CANCELADA
        or intervencion.origen_patron != PATRON_V1
        or not intervencion.sugerencia_id
        or fecha_ref <= intervencion.fecha_fin
    ):
        return None
    existente = _resultado_existente(intervencion)
    if existente:
        return (intervencion.sugerencia.contrato_snapshot or {})['evaluacion']
    sesiones = EntrenoRealizado.objects.filter(
        cliente=intervencion.cliente,
        fecha__range=(intervencion.fecha_inicio, intervencion.fecha_fin),
    )
    completadas = sesiones.count()
    esenciales = sesiones.filter(modo_reducido=True).count()
    porcentaje = round(esenciales * 100 / completadas) if completadas else 0
    if completadas < 2:
        codigo = 'datos_insuficientes'
    elif porcentaje < 50:
        codigo = 'senal_reducida'
    else:
        codigo = 'persistente'
    resultado = {
        'resultado': codigo,
        'sesiones_completadas': completadas,
        'sesiones_esenciales': esenciales,
        'porcentaje_esenciales': porcentaje,
        'fecha_evaluacion': fecha_ref.isoformat(),
        'ventana': {'desde': intervencion.fecha_inicio.isoformat(), 'hasta': intervencion.fecha_fin.isoformat()},
    }
    return resultado


@transaction.atomic
def _evaluar_intervencion_atomica(intervencion_id, fecha_ref):
    """Orden estable de locks: Cliente → Intervención → Sugerencia."""
    from clientes.models import Cliente
    referencia = IntervencionPlan.objects.only('cliente_id').get(pk=intervencion_id)
    Cliente.objects.select_for_update().get(pk=referencia.cliente_id)
    bloqueada = IntervencionPlan.objects.select_for_update().select_related('sugerencia').get(pk=intervencion_id)
    if bloqueada.sugerencia_id:
        sugerencia = SugerenciaPlan.objects.select_for_update().get(pk=bloqueada.sugerencia_id)
        bloqueada.sugerencia = sugerencia
    resultado = evaluar_intervencion(bloqueada, fecha_ref, aplicar=False)
    if resultado is None:
        return None
    ya = _resultado_existente(bloqueada)
    if ya:
        return bloqueada.sugerencia.contrato_snapshot['evaluacion']
    snap = dict(bloqueada.sugerencia.contrato_snapshot or {})
    evaluacion = dict(snap.get('evaluacion') or {})
    evaluacion.update(resultado)
    evaluacion['joi'] = {'estado': 'pendiente', 'mensaje_id': None}
    snap['evaluacion'] = evaluacion
    bloqueada.sugerencia.contrato_snapshot = snap
    bloqueada.sugerencia.save(update_fields=['contrato_snapshot'])
    bloqueada.estado = IntervencionPlan.ESTADO_EXPIRADA
    bloqueada.save(update_fields=['estado'])
    return evaluacion


def candidatos(fecha_ref=None, cliente_id=None, limit=None):
    fecha_ref = fecha_ref or timezone.localdate()
    if isinstance(fecha_ref, str):
        fecha_ref = date.fromisoformat(fecha_ref)
    qs = IntervencionPlan.objects.filter(
        estado=IntervencionPlan.ESTADO_ACTIVA,
        origen_patron=PATRON_V1,
        fecha_fin__lt=fecha_ref,
        sugerencia__contrato_snapshot__isnull=False,
    ).select_related('cliente', 'sugerencia').order_by('fecha_fin', 'pk')
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)
    return list(qs[:limit] if limit else qs)


@transaction.atomic
def cancelar_intervencion(intervencion_id, cliente_id):
    from clientes.models import Cliente
    Cliente.objects.select_for_update().get(pk=cliente_id)
    iv = IntervencionPlan.objects.select_for_update().select_related('sugerencia').get(
        pk=intervencion_id, cliente_id=cliente_id,
        origen_patron=PATRON_V1, sugerencia__patron=PATRON_V1,
    )
    if iv.estado == IntervencionPlan.ESTADO_ACTIVA and iv.fecha_inicio <= timezone.localdate() <= iv.fecha_fin:
        iv.estado = IntervencionPlan.ESTADO_CANCELADA
        iv.save(update_fields=['estado'])
    return iv
