from django.utils import timezone

from ..models import FaseProtocolo, TransicionFase
from .prescripcion_service import _serializar_prescripcion


def construir_recorrido(episodio, fecha=None):
    fecha = fecha or timezone.localdate()
    fase_actual = episodio.fase_actual
    fases = FaseProtocolo.objects.filter(protocolo=episodio.protocolo).order_by('orden')

    recorrido = []
    for fase in fases:
        # Comparar solo por orden (no por historial de transiciones) es correcto incluso
        # tras un retroceso: una fase por debajo de fase_actual.orden vuelve a marcarse
        # como "futura" en vez de conservar un "completada" que ya no es cierto.
        if fase_actual is None or fase.orden > fase_actual.orden:
            estado = 'futura'
        elif fase.orden == fase_actual.orden:
            estado = 'actual'
        else:
            estado = 'completada'

        fecha_inicio = None
        fecha_fin = None
        duracion_dias = None

        if estado in ('completada', 'actual'):
            # Si la fase se visitó más de una vez (retroceso → avance), se toma la
            # transición de entrada más reciente: es la que describe la estancia vigente.
            transicion_entrada = (
                TransicionFase.objects.filter(episodio=episodio, fase_hasta=fase)
                .order_by('-fecha')
                .first()
            )
            if transicion_entrada is not None:
                fecha_inicio = transicion_entrada.fecha
                if estado == 'actual':
                    duracion_dias = (fecha - fecha_inicio).days
                else:
                    transicion_salida = (
                        TransicionFase.objects.filter(
                            episodio=episodio, fase_desde=fase, fecha__gt=fecha_inicio,
                        )
                        .order_by('fecha')
                        .first()
                    )
                    if transicion_salida is not None:
                        fecha_fin = transicion_salida.fecha
                        duracion_dias = (fecha_fin - fecha_inicio).days

        ejercicios = [
            _serializar_prescripcion(p)
            for p in fase.prescripciones.select_related('ejercicio').order_by('orden').all()
        ]

        recorrido.append({
            'fase': fase,
            'estado': estado,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'duracion_dias': duracion_dias,
            'duracion_tipica_dias': fase.duracion_tipica_dias,
            'ejercicios': ejercicios,
        })

    return recorrido
