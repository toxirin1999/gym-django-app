"""Lectura explicable de la distribución de contratos semanales aceptados."""

from django.utils import timezone

from entrenos.models import ContratoSemanalGym, EvaluacionSemanalGym, SesionProgramada


MINIMO_SEMANAS = 3
_CONTEOS_VACIOS = {
    'completada': 0,
    'reubicada': 0,
    'omitida': 0,
    'protegida': 0,
}


def _clasificar_sesion(sesion):
    """Clasifica una identidad sin inferir cumplimiento fuera de sus campos."""
    base = {
        'sesion_id': sesion.pk,
        'nombre': sesion.nombre_sesion,
        'estado_origen': sesion.estado,
        'fecha_prevista': sesion.fecha_prevista.isoformat(),
        'fecha_realizada': (
            sesion.fecha_realizada.isoformat() if sesion.fecha_realizada else None
        ),
    }
    if sesion.estado == SesionProgramada.ESTADO_COMPLETADA:
        resultado = (
            'reubicada'
            if (
                sesion.fecha_realizada is not None
                and sesion.fecha_realizada != sesion.fecha_prevista
            )
            else 'completada'
        )
        return {**base, 'resultado': resultado, 'causa': None}
    if sesion.estado == SesionProgramada.ESTADO_SALTADA_USUARIO:
        return {**base, 'resultado': 'omitida', 'causa': 'usuario'}
    if sesion.estado == SesionProgramada.ESTADO_OMITIDA_SISTEMA:
        return {**base, 'resultado': 'omitida', 'causa': 'sistema'}
    if sesion.estado == SesionProgramada.ESTADO_CANCELADA_LESION:
        return {**base, 'resultado': 'protegida', 'causa': 'lesion'}

    # Una evaluación aceptada puede conservar una identidad no terminal. No se
    # fuerza dentro de otra categoría causal: queda visible pero fuera del
    # agregado de distribución.
    return {**base, 'resultado': 'sin_clasificar', 'causa': None}


def analizar_distribucion_semanal_contractual(cliente, *, hasta=None):
    """Analiza, sin mutaciones, contratos cerrados y aceptados de un cliente."""
    hasta = hasta or timezone.localdate()
    contratos = list(
        ContratoSemanalGym.objects.filter(
            cliente=cliente,
            semana__lte=hasta,
            evaluacion__estado_revision=EvaluacionSemanalGym.ESTADO_ACEPTADA,
        )
        .select_related('evaluacion')
        .prefetch_related('sesiones')
        .order_by('semana', 'pk')
    )
    base = {
        'cliente_id': cliente.pk,
        'hasta': hasta.isoformat(),
        'minimo_semanas': MINIMO_SEMANAS,
        'semanas_aceptadas': len(contratos),
    }
    if len(contratos) < MINIMO_SEMANAS:
        return {
            **base,
            'estado': 'evidencia_insuficiente',
            'conteos': dict(_CONTEOS_VACIOS),
            'semanas': [],
        }

    conteos = dict(_CONTEOS_VACIOS)
    semanas = []
    for contrato in contratos:
        sesiones = [
            _clasificar_sesion(sesion)
            for sesion in sorted(contrato.sesiones.all(), key=lambda item: item.pk)
        ]
        conteos_semana = dict(_CONTEOS_VACIOS)
        for sesion in sesiones:
            if sesion['resultado'] in conteos_semana:
                conteos_semana[sesion['resultado']] += 1
                conteos[sesion['resultado']] += 1
        semanas.append({
            'contrato_id': contrato.pk,
            'evaluacion_id': contrato.evaluacion.pk,
            'semana': contrato.semana.isoformat(),
            'conteos': conteos_semana,
            'sesiones': sesiones,
        })

    return {
        **base,
        'estado': 'evaluada',
        'conteos': conteos,
        'semanas': semanas,
    }
