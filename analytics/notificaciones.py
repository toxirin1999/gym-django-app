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

    # 1. Eliminated Nudges (Tu cuerpo te extraña logic removed as per redesign)

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
