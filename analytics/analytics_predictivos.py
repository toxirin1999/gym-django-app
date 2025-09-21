# analytics/analytics_predictivos.py

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class PrediccionRiesgo:
    riesgo: str  # 'bajo', 'medio', 'alto'
    probabilidad: float  # 0.0 a 1.0
    mensaje: str
    recomendaciones: List[str]
    color: str


def predecir_riesgo_abandono(historial_adherencia: List[float]) -> PrediccionRiesgo:
    """
    Analiza el historial de adherencia semanal para predecir el riesgo de abandono.
    """
    if len(historial_adherencia) < 4:
        return PrediccionRiesgo(
            riesgo='insuficientes_datos',
            probabilidad=0.0,
            mensaje="No hay suficientes datos semanales para predecir tendencias.",
            recomendaciones=["Sigue registrando tus entrenamientos para activar el análisis predictivo."],
            color="gray"
        )

    # Calculamos la tendencia comparando las últimas 2 semanas con las 2 anteriores
    media_reciente = sum(historial_adherencia[-2:]) / 2
    media_anterior = sum(historial_adherencia[-4:-2]) / 2
    tendencia = media_reciente - media_anterior

    adherencia_actual = historial_adherencia[-1]

    if adherencia_actual < 60 and tendencia < -10:
        return PrediccionRiesgo(
            riesgo='alto',
            probabilidad=0.75,
            mensaje="Se ha detectado un riesgo alto de abandono debido a una baja adherencia y una tendencia negativa.",
            recomendaciones=[
                "Revisar si el plan es demasiado demandante.",
                "Contactar para identificar barreras (falta de tiempo, motivación, etc.).",
                "Considerar simplificar el programa temporalmente."
            ],
            color="red"
        )
    elif adherencia_actual < 75 or tendencia < 0:
        return PrediccionRiesgo(
            riesgo='medio',
            probabilidad=0.40,
            mensaje="La adherencia muestra signos de inconsistencia. Es un buen momento para hacer ajustes preventivos.",
            recomendaciones=[
                "Asegúrate de que los horarios de entrenamiento son realistas.",
                "Revisa si la selección de ejercicios sigue siendo motivadora."
            ],
            color="yellow"
        )
    else:
        return PrediccionRiesgo(
            riesgo='bajo',
            probabilidad=0.10,
            mensaje="Tu adherencia es sólida y consistente. ¡Excelente trabajo!",
            recomendaciones=["Sigue manteniendo esta rutina. Estás en el camino correcto."],
            color="green"
        )
