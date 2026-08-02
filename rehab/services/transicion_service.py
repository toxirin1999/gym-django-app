from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import FaseProtocolo, RegistroDiarioRehab, SesionRehab, TransicionFase

COOLDOWN_DIAS_RETROCESO = 14
UMBRAL_DOLOR_RETROCESO_INMEDIATO = 8
DIAS_TENDENCIA_CRECIENTE = 5
MULTIPLICADOR_ESTANCAMIENTO = 1.5

__all__ = [
    'COOLDOWN_DIAS_RETROCESO',
    'UMBRAL_DOLOR_RETROCESO_INMEDIATO',
    'DIAS_TENDENCIA_CRECIENTE',
    'MULTIPLICADOR_ESTANCAMIENTO',
    'evaluar_elegibilidad_avance',
    'confirmar_avance',
    'evaluar_retroceso',
    'aplicar_retroceso_automatico',
    'detectar_estancamiento',
]


def evaluar_elegibilidad_avance(episodio, fecha):
    fase_actual = episodio.fase_actual
    evidencia = {}

    siguiente_fase = FaseProtocolo.objects.filter(
        protocolo=fase_actual.protocolo, orden=fase_actual.orden + 1
    ).first()
    if siguiente_fase is None:
        return {
            'elegible': False,
            'motivo': 'ultima_fase_sin_siguiente',
            'evidencia': evidencia,
            'siguiente_fase': None,
        }

    dias_en_fase = (fecha - episodio.fase_actual_desde).days
    evidencia['dias_en_fase'] = dias_en_fase
    if dias_en_fase < fase_actual.duracion_minima_dias:
        return {
            'elegible': False,
            'motivo': 'dias_minimos_no_cumplidos',
            'evidencia': evidencia,
            'siguiente_fase': siguiente_fase,
        }

    reglas_avance = fase_actual.reglas_avance or {}
    min_sesiones = reglas_avance.get('min_sesiones', 0)
    sesiones_completadas = SesionRehab.objects.filter(
        episodio=episodio,
        fase=fase_actual,
        estado='COMPLETADA',
        fecha__gte=episodio.fase_actual_desde,
        fecha__lte=fecha,
    ).count()
    evidencia['sesiones_completadas'] = sesiones_completadas
    if sesiones_completadas < min_sesiones:
        return {
            'elegible': False,
            'motivo': 'sesiones_insuficientes',
            'evidencia': evidencia,
            'siguiente_fase': siguiente_fase,
        }

    umbral_dolor = reglas_avance.get('umbral_dolor')
    dolores_sesiones = list(
        SesionRehab.objects.filter(
            episodio=episodio, fase=fase_actual, fecha__gte=episodio.fase_actual_desde, fecha__lte=fecha,
        ).values_list('dolor_durante', flat=True)
    )
    dolores_registros = list(
        RegistroDiarioRehab.objects.filter(
            episodio=episodio, fecha__gte=episodio.fase_actual_desde, fecha__lte=fecha,
        ).values_list('dolor_manana', flat=True)
    )
    dolores = [d for d in dolores_sesiones + dolores_registros if d is not None]
    dolor_maximo_reciente = max(dolores) if dolores else 0
    evidencia['dolor_maximo_reciente'] = dolor_maximo_reciente
    if umbral_dolor is not None and dolor_maximo_reciente > umbral_dolor:
        return {
            'elegible': False,
            'motivo': 'dolor_por_encima_del_umbral',
            'evidencia': evidencia,
            'siguiente_fase': siguiente_fase,
        }

    frecuencia_max = max(
        (p.frecuencia_semanal for p in fase_actual.prescripciones.all()), default=0
    )
    sesiones_esperadas_14d = frecuencia_max * 2
    desde_14d = fecha - timedelta(days=14)
    sesiones_completadas_14d = SesionRehab.objects.filter(
        episodio=episodio, fase=fase_actual, estado='COMPLETADA', fecha__gt=desde_14d, fecha__lte=fecha,
    ).count()
    adherencia_14d = (
        sesiones_completadas_14d / sesiones_esperadas_14d if sesiones_esperadas_14d else 0.0
    )
    evidencia['adherencia_14d'] = round(adherencia_14d, 2)
    min_adherencia = reglas_avance.get('min_adherencia')
    if min_adherencia is not None and adherencia_14d < min_adherencia:
        return {
            'elegible': False,
            'motivo': 'adherencia_insuficiente',
            'evidencia': evidencia,
            'siguiente_fase': siguiente_fase,
        }

    cooldown_limite = fecha - timedelta(days=COOLDOWN_DIAS_RETROCESO)
    retroceso_reciente = TransicionFase.objects.filter(
        episodio=episodio, direccion='RETROCESO', fecha__gt=cooldown_limite, fecha__lte=fecha,
    ).exists()
    if retroceso_reciente:
        return {
            'elegible': False,
            'motivo': 'cooldown_retroceso',
            'evidencia': evidencia,
            'siguiente_fase': siguiente_fase,
        }

    return {
        'elegible': True,
        'motivo': 'criterios_cumplidos',
        'evidencia': evidencia,
        'siguiente_fase': siguiente_fase,
    }


def confirmar_avance(episodio, fecha, forzado=False):
    # Vía de escape explícita para el humano: permite forzar el avance cuando el
    # criterio automático es demasiado conservador para el caso concreto, sin
    # tocar la regla madre (nunca se dispara solo desde este mismo módulo).
    resultado = evaluar_elegibilidad_avance(episodio, fecha)
    if not forzado and not resultado['elegible']:
        raise ValidationError(f"No se puede avanzar de fase: {resultado['motivo']}")

    siguiente_fase = resultado['siguiente_fase']
    if siguiente_fase is None:
        raise ValidationError('No hay una fase siguiente definida en el protocolo.')

    evidencia = resultado['evidencia']
    if forzado:
        evidencia = {'forzado': True, **evidencia}

    with transaction.atomic():
        fase_anterior = episodio.fase_actual
        episodio.fase_actual = siguiente_fase
        episodio.fase_actual_desde = fecha
        episodio.save(update_fields=['fase_actual', 'fase_actual_desde'])
        transicion = TransicionFase.objects.create(
            episodio=episodio,
            fase_desde=fase_anterior,
            fase_hasta=siguiente_fase,
            fecha=fecha,
            direccion='AVANCE',
            motivo=resultado['motivo'],
            automatica=False,
            confirmada_por_usuario=True,
            evidencia=evidencia,
        )
    return transicion


def evaluar_retroceso(episodio, fecha):
    fase_actual = episodio.fase_actual

    if fase_actual.orden == 1:
        return {
            'aplica': False,
            'motivo': 'primera_fase_sin_retroceso_posible',
            'evidencia': {},
        }

    reglas_retroceso = fase_actual.reglas_retroceso or {}
    dolor_post_24h_umbral = reglas_retroceso.get('dolor_post_24h_umbral')
    sesiones_consecutivas_con_dolor = reglas_retroceso.get('sesiones_consecutivas_con_dolor')

    if dolor_post_24h_umbral is not None and sesiones_consecutivas_con_dolor:
        ultimas_sesiones = list(
            SesionRehab.objects.filter(episodio=episodio, fase=fase_actual, fecha__lte=fecha)
            .order_by('-fecha')[:sesiones_consecutivas_con_dolor]
        )
        if len(ultimas_sesiones) == sesiones_consecutivas_con_dolor and all(
            s.dolor_durante >= dolor_post_24h_umbral for s in ultimas_sesiones
        ):
            return {
                'aplica': True,
                'motivo': 'dolor_sesiones_consecutivas',
                'evidencia': {'dolores_sesiones': [s.dolor_durante for s in ultimas_sesiones]},
            }

    # Definición operacional deliberada de "tendencia creciente": exactamente los
    # últimos DIAS_TENDENCIA_CRECIENTE registros diarios sin huecos de fecha, con
    # dolor no decreciente día a día y el último valor estrictamente mayor que el
    # primero. No intenta detectar tendencias con ruido ni ventanas parciales.
    registros = list(
        RegistroDiarioRehab.objects.filter(episodio=episodio, fecha__lte=fecha)
        .order_by('-fecha')[:DIAS_TENDENCIA_CRECIENTE]
    )
    if len(registros) == DIAS_TENDENCIA_CRECIENTE:
        registros_asc = list(reversed(registros))
        fechas = [r.fecha for r in registros_asc]
        sin_huecos = all((fechas[i + 1] - fechas[i]).days == 1 for i in range(len(fechas) - 1))
        valores = [r.dolor_manana for r in registros_asc]
        no_decreciente = all(valores[i + 1] >= valores[i] for i in range(len(valores) - 1))
        if sin_huecos and no_decreciente and valores[-1] > valores[0]:
            return {
                'aplica': True,
                'motivo': 'tendencia_dolor_creciente',
                'evidencia': {'dolores_manana': valores},
            }

    registro_alto = (
        RegistroDiarioRehab.objects.filter(
            episodio=episodio,
            fecha__gte=episodio.fase_actual_desde,
            fecha__lte=fecha,
            dolor_manana__gte=UMBRAL_DOLOR_RETROCESO_INMEDIATO,
        )
        .order_by('-fecha')
        .first()
    )
    if registro_alto is not None:
        return {
            'aplica': True,
            'motivo': 'dolor_matutino_inmediato',
            'evidencia': {'dolor_manana': registro_alto.dolor_manana},
        }

    return {
        'aplica': False,
        'motivo': 'sin_condiciones_retroceso',
        'evidencia': {},
    }


def aplicar_retroceso_automatico(episodio, fecha):
    resultado = evaluar_retroceso(episodio, fecha)
    if not resultado['aplica']:
        return None

    fase_actual = episodio.fase_actual
    fase_destino = FaseProtocolo.objects.get(
        protocolo=fase_actual.protocolo, orden=fase_actual.orden - 1
    )

    with transaction.atomic():
        episodio.fase_actual = fase_destino
        episodio.fase_actual_desde = fecha
        episodio.save(update_fields=['fase_actual', 'fase_actual_desde'])
        transicion = TransicionFase.objects.create(
            episodio=episodio,
            fase_desde=fase_actual,
            fase_hasta=fase_destino,
            fecha=fecha,
            direccion='RETROCESO',
            motivo=resultado['motivo'],
            automatica=True,
            confirmada_por_usuario=False,
            evidencia=resultado['evidencia'],
        )
    return transicion


def detectar_estancamiento(episodio, fecha):
    fase_actual = episodio.fase_actual
    dias_en_fase = (fecha - episodio.fase_actual_desde).days
    limite = fase_actual.duracion_tipica_dias * MULTIPLICADOR_ESTANCAMIENTO

    if dias_en_fase > limite and not evaluar_elegibilidad_avance(episodio, fecha)['elegible']:
        mensaje = (
            f"Llevas {dias_en_fase} días en esta fase (lo típico son {fase_actual.duracion_tipica_dias}). "
            "El plan no está progresando como se esperaba — considera consultar a un profesional."
        )
        return {'estancado': True, 'mensaje': mensaje}

    return {'estancado': False, 'mensaje': None}
