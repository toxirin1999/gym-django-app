from django.utils import timezone

from ..models import EpisodioRehab, RegistroDiarioRehab, SesionRehab

UMBRAL_DOLOR_PARADA = 7
UMBRAL_DOLOR_PRECAUCION_MIN = 4
UMBRAL_DOLOR_PRECAUCION_MAX = 6


def _prescripciones_fase(fase):
    return list(fase.prescripciones.select_related('ejercicio').all())


def _serializar_prescripcion(prescripcion, reducir=False):
    series = prescripcion.series
    if reducir:
        series = -(-series // 2)
    return {
        'id': prescripcion.id,
        'ejercicio': prescripcion.ejercicio.nombre,
        'orden': prescripcion.orden,
        'series': series,
        'frecuencia_semanal': prescripcion.frecuencia_semanal,
        'parametros': prescripcion.parametros,
        'notas': prescripcion.notas,
    }


def _frecuencia_semanal_max(fase):
    prescripciones = fase.prescripciones.all()
    if not prescripciones:
        return 0
    return max(p.frecuencia_semanal for p in prescripciones)


def _sesiones_completadas_ventana(episodio, fase, fecha, dias):
    desde = fecha - timezone.timedelta(days=dias)
    return SesionRehab.objects.filter(
        episodio=episodio,
        fase=fase,
        estado='COMPLETADA',
        fecha__gt=desde,
        fecha__lte=fecha,
    ).count()


def _dolores_manana_consecutivos(episodio, fecha, cantidad):
    registros = list(
        RegistroDiarioRehab.objects.filter(episodio=episodio, fecha__lte=fecha)
        .order_by('-fecha')[:cantidad]
    )
    return registros


def _calcular_progreso_avance(episodio, fase, fecha):
    reglas_avance = fase.reglas_avance or {}
    min_sesiones = reglas_avance.get('min_sesiones')
    umbral_dolor = reglas_avance.get('umbral_dolor')
    min_adherencia = reglas_avance.get('min_adherencia')

    sesiones_completadas = SesionRehab.objects.filter(
        episodio=episodio,
        fase=fase,
        estado='COMPLETADA',
        fecha__gte=episodio.fase_actual_desde,
        fecha__lte=fecha,
    ).count()

    dolores_sesiones = list(
        SesionRehab.objects.filter(
            episodio=episodio,
            fase=fase,
            fecha__gte=episodio.fase_actual_desde,
            fecha__lte=fecha,
        ).values_list('dolor_durante', flat=True)
    )
    dolores_registros = list(
        RegistroDiarioRehab.objects.filter(
            episodio=episodio,
            fecha__gte=episodio.fase_actual_desde,
            fecha__lte=fecha,
        ).values_list('dolor_manana', flat=True)
    )
    dolores = [d for d in dolores_sesiones + dolores_registros if d is not None]
    dolor_maximo_reciente = max(dolores) if dolores else 0

    frecuencia_max = _frecuencia_semanal_max(fase)
    sesiones_esperadas_14d = frecuencia_max * 2
    sesiones_completadas_14d = _sesiones_completadas_ventana(episodio, fase, fecha, 14)
    adherencia_14d = (
        sesiones_completadas_14d / sesiones_esperadas_14d if sesiones_esperadas_14d else 0.0
    )

    progreso = {
        'sesiones_completadas': sesiones_completadas,
        'sesiones_requeridas': min_sesiones,
        'adherencia_14d': round(adherencia_14d, 2),
        'dolor_maximo_reciente': dolor_maximo_reciente,
    }

    texto = (
        f"Llevas {sesiones_completadas} de {min_sesiones} sesiones necesarias en esta fase, "
        f"dolor máximo reciente {dolor_maximo_reciente}/10 (límite {umbral_dolor}), "
        f"adherencia {round(adherencia_14d * 100)}%"
    )
    if min_adherencia is not None:
        texto += f" (objetivo {round(min_adherencia * 100)}%)."
    else:
        texto += "."

    return texto, progreso


def prescripcion_de_hoy(cliente, fecha=None):
    fecha = fecha or timezone.localdate()

    episodio = (
        EpisodioRehab.objects.filter(cliente=cliente, estado='ACTIVO')
        .order_by('fecha_inicio')
        .first()
    )
    if episodio is None:
        return {
            'estado': 'SIN_EPISODIO',
            'titulo': 'No hay ningún episodio de rehabilitación activo.',
            'ejercicios': [],
            'motivo': 'sin_episodio_activo',
            'puede_entrenar': False,
            'alerta': None,
            'dias_en_fase': None,
            'criterio_avance_texto': None,
            'progreso_hacia_avance': None,
        }

    fase = episodio.fase_actual
    dias_en_fase = (fecha - episodio.fase_actual_desde).days

    criterio_avance_texto = None
    progreso_hacia_avance = None
    if fase is not None:
        criterio_avance_texto, progreso_hacia_avance = _calcular_progreso_avance(episodio, fase, fecha)

    base = {
        'dias_en_fase': dias_en_fase,
        'criterio_avance_texto': criterio_avance_texto,
        'progreso_hacia_avance': progreso_hacia_avance,
    }

    registro_hoy = RegistroDiarioRehab.objects.filter(episodio=episodio, fecha=fecha).first()

    if registro_hoy is not None and registro_hoy.bandera_roja:
        return {
            **base,
            'estado': 'PARAR',
            'titulo': 'Bandera roja activa',
            'ejercicios': [],
            'motivo': 'bandera_roja',
            'puede_entrenar': False,
            'alerta': 'Bandera roja marcada — no entrenar, consulta un profesional.',
        }

    if registro_hoy is not None and registro_hoy.dolor_manana >= UMBRAL_DOLOR_PARADA:
        if fase is not None and fase.orden == 1:
            sugerencia = (
                'Ya estás en la fase más básica del protocolo — no hay margen para '
                'retroceder más. Este nivel de dolor está fuera de lo que la app puede '
                'gestionar sola: busca valoración de un profesional.'
            )
        else:
            sugerencia = 'Considera retroceder de fase.'
        return {
            **base,
            'estado': 'PARAR',
            'titulo': 'Dolor demasiado alto para entrenar hoy',
            'ejercicios': [],
            'motivo': 'dolor_hoy_umbral',
            'puede_entrenar': False,
            'alerta': (
                f'Dolor matinal {registro_hoy.dolor_manana}/10 supera el umbral de parada '
                f'({UMBRAL_DOLOR_PARADA}). {sugerencia}'
            ),
        }

    reglas_retroceso = fase.reglas_retroceso if fase else {}
    umbral_retroceso = reglas_retroceso.get('dolor_post_24h_umbral') if reglas_retroceso else None
    sesiones_consecutivas = reglas_retroceso.get('sesiones_consecutivas_con_dolor') if reglas_retroceso else None

    if umbral_retroceso is not None and sesiones_consecutivas:
        registros_recientes = _dolores_manana_consecutivos(episodio, fecha, sesiones_consecutivas)
        if len(registros_recientes) == sesiones_consecutivas and all(
            r.dolor_manana >= umbral_retroceso for r in registros_recientes
        ):
            if fase is not None and fase.orden == 1:
                sugerencia = (
                    'Ya estás en la fase más básica del protocolo — no hay margen para '
                    'retroceder más. Este nivel de dolor está fuera de lo que la app puede '
                    'gestionar sola: busca valoración de un profesional.'
                )
            else:
                sugerencia = 'Considera retroceder de fase.'
            return {
                **base,
                'estado': 'PARAR',
                'titulo': 'Dolor matinal persistente',
                'ejercicios': [],
                'motivo': 'dolor_matinal_persistente',
                'puede_entrenar': False,
                'alerta': (
                    f'Dolor matinal >= {umbral_retroceso}/10 durante {sesiones_consecutivas} días '
                    f'consecutivos. {sugerencia}'
                ),
            }

    if registro_hoy is None:
        return {
            **base,
            'estado': 'SIN_DATOS',
            'titulo': 'Registra tu dolor matinal antes de nada',
            'ejercicios': [],
            'motivo': 'sin_registro_diario',
            'puede_entrenar': False,
            'alerta': None,
        }

    # El modelo no tiene un campo de horas mínimas de descanso entre sesiones;
    # se aproxima "frecuencia cumplida" contando sesiones completadas en los últimos
    # 7 días naturales contra la frecuencia_semanal máxima de la fase, en vez de
    # exigir un espaciado real (p.ej. 48h) entre sesiones. Simplificación deliberada.
    frecuencia_semanal_max = _frecuencia_semanal_max(fase) if fase else 0
    sesiones_completadas_7d = _sesiones_completadas_ventana(episodio, fase, fecha, 7) if fase else 0
    if fase is not None and frecuencia_semanal_max and sesiones_completadas_7d >= frecuencia_semanal_max:
        return {
            **base,
            'estado': 'DESCANSO_PROGRAMADO',
            'titulo': 'Descanso programado',
            'ejercicios': [],
            'motivo': 'frecuencia_semanal_cumplida',
            'puede_entrenar': False,
            'alerta': None,
        }

    prescripciones = _prescripciones_fase(fase) if fase else []

    if UMBRAL_DOLOR_PRECAUCION_MIN <= registro_hoy.dolor_manana <= UMBRAL_DOLOR_PRECAUCION_MAX:
        return {
            **base,
            'estado': 'PRECAUCION',
            'titulo': 'Entrena con precaución, volumen reducido',
            'ejercicios': [_serializar_prescripcion(p, reducir=True) for p in prescripciones],
            'motivo': 'dolor_moderado',
            'puede_entrenar': True,
            'alerta': None,
        }

    return {
        **base,
        'estado': 'ENTRENAR_HOY',
        'titulo': 'Toca entrenar hoy',
        'ejercicios': [_serializar_prescripcion(p) for p in prescripciones],
        'motivo': 'normal',
        'puede_entrenar': True,
        'alerta': None,
    }
