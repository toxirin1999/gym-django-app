# analytics/notificaciones.py

from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Notificacion:
    tipo: str
    titulo: str
    mensaje: str
    icono: str
    color: str


def generar_notificaciones_contextuales(cliente: Any, entrenos_recientes: List[Any]) -> List[Notificacion]:
    """
    Genera una lista de notificaciones basadas en el estado actual del cliente.
    """
    notificaciones = []

    # 1. Notificación de Recordatorio de Entrenamiento
    if entrenos_recientes:
        ultimo_entreno = entrenos_recientes[0]
        dias_sin_entrenar = (datetime.now().date() - ultimo_entreno.fecha).days

        if dias_sin_entrenar >= 3:
            notificaciones.append(Notificacion(
                tipo='recordatorio',
                titulo='Tu cuerpo te extraña',
                mensaje=f"Han pasado {dias_sin_entrenar} días desde tu último entreno. ¿Qué tal una sesión hoy?",
                icono='fa-dumbbell',
                color='cyan'
            ))

    # 2. Notificación de Nuevo Récord (simplificado)
    # En una implementación real, esto se detectaría al guardar un entreno.
    # Aquí simulamos que el último entreno tuvo un récord.
    if entrenos_recientes and (entrenos_recientes[0].id % 5 == 0):  # Simulación
        notificaciones.append(Notificacion(
            tipo='logro',
            titulo='¡Nuevo Récord Personal!',
            mensaje="¡Felicidades! Has superado tu marca anterior en Press de Banca.",
            icono='fa-trophy',
            color='yellow'
        ))

    return notificaciones
