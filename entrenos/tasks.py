from celery import shared_task
from django.utils import timezone


@shared_task
def evaluar_intervenciones_esenciales_diarias():
    from entrenos.models import IntervencionPlan
    from entrenos.services.ciclo_intervencion_esenciales_service import candidatos, evaluar_intervencion
    from joi.tasks import generar_resultado_intervencion_joi
    evaluadas = 0
    ids_encolados = set()
    for iv in candidatos(timezone.localdate()):
        if evaluar_intervencion(iv, timezone.localdate(), aplicar=True):
            evaluadas += 1
            generar_resultado_intervencion_joi.delay(iv.pk)
            ids_encolados.add(iv.pk)
    pendientes_joi = IntervencionPlan.objects.filter(
        estado=IntervencionPlan.ESTADO_EXPIRADA,
        origen_patron='esenciales_frecuentes',
        sugerencia__contrato_snapshot__evaluacion__resultado__isnull=False,
    ).exclude(
        sugerencia__contrato_snapshot__evaluacion__joi__mensaje_id__isnull=False,
    ).exclude(pk__in=ids_encolados)
    reencoladas = 0
    for iv in pendientes_joi:
        generar_resultado_intervencion_joi.delay(iv.pk)
        reencoladas += 1
    return {'evaluadas': evaluadas, 'joi_reencoladas': reencoladas}
