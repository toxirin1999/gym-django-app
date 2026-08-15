from copy import deepcopy
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, ExperimentoVarianteGym, GymDecisionLog, IntervencionMolestiaGym
from entrenos.services.experimento_variante_gym_service import normalizar_nombre
from entrenos.services.zona_molestia_service import normalizar_zona, risk_tags_zona


@transaction.atomic
def procesar_molestias_recurrentes(entreno):
    fecha_ref = entreno.fecha_ejecucion or entreno.fecha
    desde = fecha_ref - timedelta(days=21)
    creadas = []
    actuales = entreno.ejercicios_realizados.filter(
        completado=True, molestia_reportada=True, molestia_severidad=1,
    )
    for actual in actuales:
        zona = normalizar_zona(actual.molestia_zona)
        if zona == 'otro':
            continue
        candidatas = EjercicioRealizado.objects.filter(
            entreno__cliente=entreno.cliente, molestia_reportada=True,
        ).select_related('entreno')
        evidencias = [item for item in candidatas if (
            normalizar_zona(item.molestia_zona) == zona
            and desde <= (item.entreno.fecha_ejecucion or item.entreno.fecha) <= fecha_ref
        )]
        if any((item.molestia_severidad or 0) >= 2 for item in evidencias):
            continue
        if len({item.entreno_id for item in evidencias if item.molestia_severidad == 1}) < 3:
            continue
        original_norm = normalizar_nombre(actual.nombre_ejercicio)
        Cliente.objects.select_for_update().get(pk=entreno.cliente_id)
        activa = IntervencionMolestiaGym.objects.select_for_update().filter(
            cliente=entreno.cliente, zona_canonica=zona,
            original_normalizado=original_norm, estado=IntervencionMolestiaGym.ESTADO_ACTIVA,
        ).first()
        if activa:
            creadas.append(activa); continue
        tags = risk_tags_zona(zona)
        from entrenos.services.alternativas_lesion_service import buscar_alternativas_lesion
        alternativas = buscar_alternativas_lesion(actual.nombre_ejercicio, actual.grupo_muscular or '', tags, 'RETORNO', 1)
        alternativa = alternativas[0] if alternativas else {}
        decision = GymDecisionLog.objects.create(
            cliente=entreno.cliente, entreno_origen=entreno,
            ejercicio=actual.nombre_ejercicio, ejercicio_normalizado=original_norm,
            accion='cambiar_variante', motivo=f'Molestia recurrente leve en {zona}: intervención acotada.', confianza='alta',
        )
        ahora = timezone.now()
        creadas.append(IntervencionMolestiaGym.objects.create(
            cliente=entreno.cliente, decision_origen=decision, zona_canonica=zona,
            risk_tags_snapshot=tags,
            original={'nombre': actual.nombre_ejercicio, 'grupo_muscular': actual.grupo_muscular},
            original_normalizado=original_norm, alternativa=deepcopy(alternativa),
            alternativa_normalizada=normalizar_nombre(alternativa.get('nombre')),
            iniciada_en=ahora, vence_en=ahora + timedelta(days=21),
        ))
    return creadas


@transaction.atomic
def evaluar_intervencion(intervencion):
    intervencion = IntervencionMolestiaGym.objects.select_for_update().get(pk=intervencion.pk)
    if intervencion.estado != IntervencionMolestiaGym.ESTADO_ACTIVA:
        return intervencion
    ejecuciones = list(intervencion.ejecuciones.filter(completado=True).order_by('pk')[:2])
    ahora = timezone.now()
    fallo = any(e.fallo_muscular or (e.rpe is not None and e.rpe >= 9.5) or (
        e.molestia_reportada and normalizar_zona(e.molestia_zona) == intervencion.zona_canonica
    ) or (e.molestia_severidad or 0) >= 2 for e in ejecuciones)
    if fallo:
        estado, motivo = intervencion.ESTADO_FALLIDA, 'Señal de seguridad durante la alternativa.'
    elif len(ejecuciones) >= 2:
        favorable = all(not e.molestia_reportada and not e.fallo_muscular and e.rpe is not None and e.rpe <= 8.5 for e in ejecuciones)
        estado = intervencion.ESTADO_FAVORABLE if favorable else intervencion.ESTADO_INSUFICIENTE
        motivo = 'Dos ejecuciones seguras.' if favorable else 'Segunda ejecución sin evidencia suficiente.'
    elif ahora >= intervencion.vence_en:
        estado, motivo = intervencion.ESTADO_INSUFICIENTE, 'Vencida sin dos ejecuciones.'
    else:
        return intervencion
    intervencion.estado, intervencion.motivo_cierre = estado, motivo
    intervencion.finalizada_en = ahora
    intervencion.save(update_fields=['estado', 'motivo_cierre', 'finalizada_en', 'actualizado_en'])
    return intervencion


@transaction.atomic
def enlazar_y_evaluar_ejecucion_molestia(ejecucion):
    if ejecucion.intervencion_molestia_id:
        return evaluar_intervencion(ejecucion.intervencion_molestia)
    intervencion = IntervencionMolestiaGym.objects.select_for_update().filter(
        cliente=ejecucion.entreno.cliente, estado='activa',
        alternativa_normalizada=normalizar_nombre(ejecucion.nombre_ejercicio),
    ).order_by('-iniciada_en').first()
    if not intervencion:
        return None
    fecha = ejecucion.entreno.fecha_ejecucion or ejecucion.entreno.fecha
    if fecha < intervencion.iniciada_en.date():
        return None
    EjercicioRealizado.objects.filter(pk=ejecucion.pk).update(intervencion_molestia=intervencion)
    ejecucion.intervencion_molestia = intervencion
    return evaluar_intervencion(intervencion)


def interrumpir_experimento_estancamiento(cliente, original_norm):
    ahora = timezone.now()
    ExperimentoVarianteGym.objects.filter(
        cliente=cliente, original_normalizado=original_norm, estado='activa',
    ).update(estado='insuficiente', finalizada_en=ahora, motivo_cierre='Interrumpido por seguridad: molestia recurrente.')
