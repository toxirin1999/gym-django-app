# en analytics/monitor_adherencia.py

from dataclasses import dataclass, field
from datetime import datetime
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum
from django.utils import timezone


# (Las clases TipoAlerta, SesionEntrenamiento, MetricasAdherencia y Alerta se quedan igual)
class TipoAlerta(Enum):
    ADHERENCIA_BAJA = "adherencia_baja"
    AUSENCIA_PROLONGADA = "ausencia_prolongada"
    PATRON_INCONSISTENTE = "patron_inconsistente"
    MOTIVACION_BAJA = "motivacion_baja"


@dataclass
class SesionEntrenamiento:
    fecha: datetime
    completada: bool
    satisfaccion: int | None = None


@dataclass
class MetricasAdherencia:
    sesiones_completadas: int = 0
    sesiones_planificadas: int = 0
    dias_consecutivos_perdidos: int = 0
    porcentaje_adherencia_semanal: float = 0.0
    satisfaccion_promedio: float = 0.0
    tendencia_adherencia: str = "estable"
    ultima_actualizacion: datetime = field(default_factory=timezone.now)


@dataclass
class Alerta:
    tipo: TipoAlerta
    severidad: int
    mensaje: str
    recomendaciones: List[str]
    activa: bool = True


class MonitorAdherencia:
    def __init__(self, cliente_id: int):
        self.cliente_id = cliente_id
        self.metricas_actuales = MetricasAdherencia()
        self.alertas_activas: List[Alerta] = []
        self.umbrales = {'adherencia_minima': 70.0, 'dias_ausencia_maximos': 3}

    def actualizar_y_evaluar(self, completadas: int, planificadas: int, dias_perdidos: int):
        """
        Método único que recibe los datos ya calculados desde la vista.
        """
        self.metricas_actuales.sesiones_completadas = completadas
        self.metricas_actuales.sesiones_planificadas = planificadas
        self.metricas_actuales.dias_consecutivos_perdidos = dias_perdidos

        if planificadas > 0:
            self.metricas_actuales.porcentaje_adherencia_semanal = (completadas / planificadas) * 100
        else:
            self.metricas_actuales.porcentaje_adherencia_semanal = 100.0  # O 0.0 si prefieres

        self.metricas_actuales.ultima_actualizacion = timezone.now()
        self._evaluar_alertas()

    def _evaluar_alertas(self):
        # Esta lógica se mantiene, pero ahora usa datos más fiables
        self.alertas_activas.clear()  # Limpiamos para re-evaluar desde cero

        if self.metricas_actuales.porcentaje_adherencia_semanal < self.umbrales['adherencia_minima']:
            self.alertas_activas.append(Alerta(
                tipo=TipoAlerta.ADHERENCIA_BAJA, severidad=3,
                mensaje=f"Adherencia semanal baja: {self.metricas_actuales.porcentaje_adherencia_semanal:.1f}%",
                recomendaciones=["Revisar si el programa es demasiado demandante.",
                                 "Considerar reducir volumen temporalmente."]
            ))

        if self.metricas_actuales.dias_consecutivos_perdidos >= self.umbrales['dias_ausencia_maximos']:
            self.alertas_activas.append(Alerta(
                tipo=TipoAlerta.AUSENCIA_PROLONGADA, severidad=4,
                mensaje=f"Ausencia prolongada: {self.metricas_actuales.dias_consecutivos_perdidos} días consecutivos",
                recomendaciones=["Contactar al cliente para identificar problemas.",
                                 "Simplificar el programa temporalmente."]
            ))

    def obtener_reporte_adherencia(self) -> Dict:
        return {
            'metricas': self.metricas_actuales,
            'alertas_activas': self.alertas_activas
        }
