# analytics/autorregulacion.py

from dataclasses import dataclass


@dataclass
class AjusteSesion:
    modificacion_rpe: int = 0  # ej. -1, 0, +1
    modificacion_volumen: float = 1.0  # ej. 0.85, 1.0, 1.05
    mensaje: str = "Parámetros normales. ¡A darlo todo!"
    color: str = "green"


def calcular_ajuste_sesion(energia: int, dolor: int, sueno: int) -> AjusteSesion:
    """
    Calcula los ajustes para la sesión de hoy basándose en el feedback del usuario.
    """
    # --- INICIO DE LA CORRECCIÓN ---
    # Convertimos todos los inputs a float para asegurar compatibilidad matemática.
    # Usamos un valor por defecto de 5 si el dato es None.
    energia = float(energia or 5)
    dolor = float(dolor or 5)
    sueno = float(sueno or 5)
    # --- FIN DE LA CORRECCIÓN ---

    # Normalizar valores a una escala de -1 (malo) a 1 (bueno)
    energia_norm = (energia - 5.5) / 4.5
    dolor_norm = ((10 - dolor) - 5.5) / 4.5  # El dolor se invierte
    sueno_norm = (sueno - 5.5) / 4.5

    # Puntuación de "Readiness" (disponibilidad para entrenar)
    readiness_score = (energia_norm * 0.2) + (dolor_norm * 0.4) + (sueno_norm * 0.4)

    if readiness_score < -0.5:  # Readiness muy bajo
        return AjusteSesion(
            modificacion_rpe=-1,
            modificacion_volumen=0.85,  # Reducción del 15% del volumen
            mensaje="He detectado que tu recuperación es baja. Hoy nos enfocaremos en la técnica, reduciendo la intensidad y el volumen. Escucha a tu cuerpo.",
            color="red"
        )
    elif readiness_score < -0.1:  # Readiness bajo
        return AjusteSesion(
            modificacion_rpe=-1,
            modificacion_volumen=1.0,  # Mismo volumen, menos intensidad
            mensaje="Tu readiness es algo bajo. Te recomiendo bajar 1 punto el RPE objetivo de hoy para asegurar una buena recuperación.",
            color="yellow"
        )
    elif readiness_score > 0.6:  # Readiness excelente
        return AjusteSesion(
            modificacion_rpe=0,
            modificacion_volumen=1.0,
            mensaje="¡Tus métricas de recuperación son excelentes! Tienes luz verde para entrenar con la intensidad planificada.",
            color="cyan"
        )
    else:  # Readiness normal
        return AjusteSesion()
