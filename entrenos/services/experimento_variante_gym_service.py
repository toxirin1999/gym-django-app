import re
import unicodedata
from copy import deepcopy
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, ExperimentoVarianteGym, GymDecisionLog


def normalizar_nombre(nombre):
    texto = unicodedata.normalize('NFKD', str(nombre or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', texto.lower()).strip()


def _es_estancamiento(decision):
    motivo = normalizar_nombre(decision.motivo)
    return decision.accion == 'cambiar_variante' and 'sin progresion' in motivo


@transaction.atomic
def asegurar_experimento_variante(decision, original, variante):
    """Crea una única prueba causal; una decisión nunca puede reelegir variante."""
    if not _es_estancamiento(decision):
        return None
    existente = ExperimentoVarianteGym.objects.select_for_update().filter(
        decision_origen=decision,
    ).first()
    if existente:
        return existente
    Cliente.objects.select_for_update().get(pk=decision.cliente_id)
    original_normalizado = normalizar_nombre(original.get('nombre'))
    activo = ExperimentoVarianteGym.objects.select_for_update().filter(
        cliente=decision.cliente,
        original_normalizado=original_normalizado,
        estado=ExperimentoVarianteGym.ESTADO_ACTIVA,
    ).order_by('-iniciada_en', '-pk').first()
    if activo:
        return activo
    ahora = timezone.now()
    return ExperimentoVarianteGym.objects.create(
        cliente=decision.cliente,
        decision_origen=decision,
        original=deepcopy(original),
        original_normalizado=original_normalizado,
        variante=deepcopy(variante),
        variante_normalizada=normalizar_nombre(variante.get('nombre')),
        baseline={
            'version': 1,
            'peso': original.get('peso_kg') or original.get('peso_recomendado_kg') or 0,
            'repeticiones': original.get('repeticiones') or original.get('reps') or 0,
        },
        iniciada_en=ahora,
        vence_en=ahora + timedelta(days=21),
    )


def experimento_para_original(cliente, nombre):
    return ExperimentoVarianteGym.objects.filter(
        cliente=cliente,
        original_normalizado=normalizar_nombre(nombre),
        estado=ExperimentoVarianteGym.ESTADO_ACTIVA,
    ).order_by('-iniciada_en', '-pk').first()


@transaction.atomic
def evaluar_experimento(experimento):
    experimento = ExperimentoVarianteGym.objects.select_for_update().get(pk=experimento.pk)
    if experimento.estado != ExperimentoVarianteGym.ESTADO_ACTIVA:
        return experimento
    ejecuciones = list(
        experimento.ejecuciones.filter(completado=True)
        .order_by('entreno__fecha_ejecucion', 'entreno__fecha', 'pk')[:2]
    )
    ahora = timezone.now()
    fallida = next((ej for ej in ejecuciones if (
        ej.molestia_reportada or ej.fallo_muscular or (ej.rpe is not None and ej.rpe >= 9.5)
    )), None)
    if fallida:
        experimento.estado = ExperimentoVarianteGym.ESTADO_FALLIDA
        experimento.motivo_cierre = 'La variante produjo molestia, fallo muscular o RPE crítico.'
    elif len(ejecuciones) >= 2:
        primera, segunda = ejecuciones
        rpes_validos = all(ej.rpe is not None and ej.rpe <= 8.5 for ej in ejecuciones)
        rendimiento_primero = primera.repeticiones * (primera.peso_kg or 1)
        rendimiento_segundo = segunda.repeticiones * (segunda.peso_kg or 1)
        if rpes_validos and rendimiento_segundo >= rendimiento_primero:
            experimento.estado = ExperimentoVarianteGym.ESTADO_FAVORABLE
            experimento.motivo_cierre = 'Dos ejecuciones seguras y rendimiento no decreciente.'
        else:
            experimento.estado = ExperimentoVarianteGym.ESTADO_INSUFICIENTE
            experimento.motivo_cierre = 'Dos ejecuciones sin evidencia favorable suficiente.'
    elif ahora >= experimento.vence_en:
        experimento.estado = ExperimentoVarianteGym.ESTADO_INSUFICIENTE
        experimento.motivo_cierre = 'Vencida antes de completar dos ejecuciones evaluables.'
    else:
        return experimento
    experimento.finalizada_en = ahora
    experimento.save(update_fields=['estado', 'motivo_cierre', 'finalizada_en', 'actualizado_en'])
    return experimento


@transaction.atomic
def enlazar_y_evaluar_ejecucion(ejecucion):
    if ejecucion.experimento_variante_id:
        return evaluar_experimento(ejecucion.experimento_variante)
    normalizado = normalizar_nombre(ejecucion.nombre_ejercicio)
    experimento = ExperimentoVarianteGym.objects.select_for_update().filter(
        cliente=ejecucion.entreno.cliente,
        estado=ExperimentoVarianteGym.ESTADO_ACTIVA,
        variante_normalizada=normalizado,
    ).order_by('-iniciada_en', '-pk').first()
    if not experimento:
        return None
    fecha_efectiva = ejecucion.entreno.fecha_ejecucion or ejecucion.entreno.fecha
    if fecha_efectiva < experimento.iniciada_en.date():
        return None
    experimento = evaluar_experimento(experimento)
    if experimento.estado != ExperimentoVarianteGym.ESTADO_ACTIVA:
        return experimento
    EjercicioRealizado.objects.filter(pk=ejecucion.pk).update(experimento_variante=experimento)
    ejecucion.experimento_variante = experimento
    return evaluar_experimento(experimento)
