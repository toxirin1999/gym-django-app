# diario/services/cierre_service.py
#
# Fase 2 del CONTRATO_ANALIZADOR_GESTOS.md — núcleo transaccional del cierre.
#
# persistir_nucleo_cierre() aísla la persistencia crítica de presencia_cierre
# (reflexión, SeguimientoVires, sincronización de RegistroGesto, marcador de
# cierre confirmado) en una única transacción: si algo falla de forma
# inesperada a mitad de camino, no queda un cierre a medias. El
# enriquecimiento JOI/Gemini y la comprobación de Simbiosis se quedan fuera
# a propósito — son best-effort y no deben poder bloquear ni revertir el
# núcleo (ya tienen su propio try/except en la vista).

import json

from django.db import transaction
from django.utils import timezone

from ..models import RegistroGesto, SeguimientoVires
from .habitos_service import HabitosService


@transaction.atomic
def persistir_nucleo_cierre(
    usuario,
    fecha,
    entrada,
    texto_libre,
    friccion_raw,
    cuerpo_raw,
    habitos_completados_raw,
    gestos_activos,
):
    """
    Persiste el núcleo del cierre diario de forma atómica.

    Los fallos de parseo esperables (fricción no numérica, JSON de hábitos
    malformado) se ignoran localmente igual que hacía la vista antes de
    esta extracción — capturarlos dentro de la función evita que
    provoquen un rollback del resto del núcleo, exactamente el
    comportamiento previo. Solo un fallo inesperado (p. ej. un error de
    base de datos) revierte todo lo escrito en esta llamada.
    """
    if friccion_raw or cuerpo_raw:
        try:
            vires, _ = SeguimientoVires.objects.get_or_create(usuario=usuario, fecha=fecha)
            if friccion_raw:
                vires.nivel_estres = int(friccion_raw)
            if cuerpo_raw:
                vires.cuerpo_cierre = cuerpo_raw
            vires.save()
        except (ValueError, TypeError):
            pass

    if texto_libre:
        entrada.reflexiones_dia = texto_libre
        entrada.save()

    try:
        habitos_completados_ids = json.loads(habitos_completados_raw)
    except (json.JSONDecodeError, ValueError):
        habitos_completados_ids = []

    cumplidos_hoy_ids = set(
        RegistroGesto.objects.filter(
            gesto__in=gestos_activos, fecha=fecha, estado='cumplido'
        ).values_list('gesto_id', flat=True)
    )
    for gesto in gestos_activos:
        deseado = gesto.id in habitos_completados_ids
        actual = gesto.id in cumplidos_hoy_ids
        if deseado != actual:
            HabitosService.toggle_dia(gesto, fecha)

    if entrada.cierre_confirmado_en is None:
        entrada.cierre_confirmado_en = timezone.now()
        entrada.save(update_fields=['cierre_confirmado_en'])
