from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import EjercicioSesionRehab, EpisodioRehab, RegistroDiarioRehab, SesionRehab, TransicionFase
from .prescripcion_service import UMBRAL_DOLOR_PARADA, prescripcion_de_hoy

__all__ = [
    'iniciar_episodio',
    'registrar_dolor_diario',
    'registrar_sesion',
    'prescripcion_de_hoy',
    'UMBRAL_DOLOR_PARADA',
]


def iniciar_episodio(cliente, protocolo, lateralidad, fecha_inicio, dolor_basal_inicial, notas=''):
    if EpisodioRehab.objects.filter(cliente=cliente, protocolo=protocolo, estado='ACTIVO').exists():
        raise ValidationError(
            f'Ya existe un episodio activo del protocolo "{protocolo.nombre}" para este cliente.'
        )

    primera_fase = protocolo.fases.order_by('orden').first()
    if primera_fase is None:
        raise ValidationError(f'El protocolo "{protocolo.nombre}" no tiene fases definidas.')

    with transaction.atomic():
        episodio = EpisodioRehab.objects.create(
            cliente=cliente,
            protocolo=protocolo,
            protocolo_version=protocolo.version,
            fase_actual=primera_fase,
            lateralidad=lateralidad,
            fecha_inicio=fecha_inicio,
            fase_actual_desde=fecha_inicio,
            estado='ACTIVO',
            dolor_basal_inicial=dolor_basal_inicial,
            notas=notas,
        )
        TransicionFase.objects.create(
            episodio=episodio,
            fase_desde=None,
            fase_hasta=primera_fase,
            fecha=fecha_inicio,
            direccion='INICIO',
            motivo='inicio_episodio',
            automatica=False,
            evidencia={},
            confirmada_por_usuario=True,
        )
    return episodio


def registrar_dolor_diario(episodio, fecha, dolor_manana, rigidez_manana, notas=''):
    registro, _ = RegistroDiarioRehab.objects.update_or_create(
        episodio=episodio,
        fecha=fecha,
        defaults={
            'dolor_manana': dolor_manana,
            'rigidez_manana': rigidez_manana,
            'notas': notas,
        },
    )
    return registro


def registrar_sesion(
    episodio,
    fecha,
    estado,
    dolor_durante,
    ejercicios_data,
    dolor_post_24h=None,
    duracion_min=None,
    notas='',
):
    fase = episodio.fase_actual
    prescripciones = fase.prescripciones.select_related('ejercicio').all()
    snapshot = [
        {
            'prescripcion_id': p.id,
            'ejercicio': p.ejercicio.nombre,
            'series': p.series,
            'frecuencia_semanal': p.frecuencia_semanal,
            'parametros': p.parametros,
        }
        for p in prescripciones
    ]

    with transaction.atomic():
        sesion = SesionRehab.objects.create(
            episodio=episodio,
            fase=fase,
            fecha=fecha,
            estado=estado,
            dolor_durante=dolor_durante,
            dolor_post_24h=dolor_post_24h,
            duracion_min=duracion_min,
            prescripcion_snapshot=snapshot,
            notas=notas,
        )
        for item in ejercicios_data:
            EjercicioSesionRehab.objects.create(
                sesion=sesion,
                prescripcion_id=item['prescripcion_id'],
                series_completadas=item['series_completadas'],
                carga_kg=item.get('carga_kg'),
                dolor_ejercicio=item.get('dolor_ejercicio'),
                completado=item.get('completado', False),
            )
    return sesion
