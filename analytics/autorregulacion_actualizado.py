
# analytics/autorregulacion.py (actualizado)
# Compatible con tu versión previa y ampliado con progresión por RIR,
# gestión dinámica de series y deload flexible por señales.

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# ===============================================================
# SECCIÓN 0: Objetos existentes (compatibilidad hacia atrás)
# ===============================================================

@dataclass
class AjusteSesion:
    modificacion_rpe: int = 0  # ej. -1, 0, +1
    modificacion_volumen: float = 1.0  # ej. 0.85, 1.0, 1.05
    mensaje: str = "Parámetros normales. ¡A darlo todo!"
    color: str = "green"


def calcular_ajuste_sesion(energia: int, dolor: int, sueno: int) -> AjusteSesion:
    """
    Calcula los ajustes para la sesión de hoy basándose en el feedback del usuario.
    Escalas esperadas: 1–10 (pueden venir None -> se asumen 5).
    """
    # Compatibilidad con tu implementación anterior
    energia = float(energia or 5)
    dolor = float(dolor or 5)
    sueno = float(sueno or 5)

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
            mensaje=(
                "He detectado que tu recuperación es baja. Hoy nos enfocaremos en la técnica, "
                "reduciendo la intensidad y el volumen. Escucha a tu cuerpo."
            ),
            color="red",
        )
    elif readiness_score < -0.1:  # Readiness bajo
        return AjusteSesion(
            modificacion_rpe=-1,
            modificacion_volumen=1.0,  # Mismo volumen, menos intensidad
            mensaje=(
                "Tu readiness es algo bajo. Te recomiendo bajar 1 punto el RPE objetivo de hoy "
                "para asegurar una buena recuperación."
            ),
            color="yellow",
        )
    elif readiness_score > 0.6:  # Readiness excelente
        return AjusteSesion(
            modificacion_rpe=0,
            modificacion_volumen=1.0,
            mensaje="¡Tus métricas de recuperación son excelentes! Tienes luz verde para entrenar con la intensidad planificada.",
            color="cyan",
        )
    else:  # Readiness normal
        return AjusteSesion()


# ===============================================================
# SECCIÓN 1: Progresión por RIR
# ===============================================================

@dataclass
class RIRProgression:
    """
    Progresión autorregulada por RIR.
    - Aplica ajustes de carga en % o kg según la desviación vs. RIR objetivo.
    - Redondea al incremento estándar del gimnasio (p. ej., 2.5 kg).
    """
    incremento_redondeo: float = 2.5
    ajuste_suave_pct: float = 0.03     # ±3% por paso
    ajuste_fuerte_pct: float = 0.05    # ±5% si hay gran desviación
    umbral_rep_gap: int = 2            # reps por encima del objetivo -> subir

    def ajustar_peso(
        self,
        peso_actual: float,
        rir_obj: int,
        rir_real: Optional[int],
        rep_gap: int = 0,
        limite_min_kg: float = 0.0
    ) -> float:
        """
        Args:
            peso_actual: carga usada la última vez.
            rir_obj: RIR objetivo (0–3 típico para hipertrofia).
            rir_real: RIR alcanzado (None si no hay dato).
            rep_gap: reps por ENCIMA del objetivo (si trackeas rangos).
            limite_min_kg: no bajar por debajo de este peso.
        """
        if peso_actual <= 0:
            return max(limite_min_kg, 0.0)

        # Si no hay feedback, mantener o realizar micro-progresión prudente
        if rir_real is None:
            return self._redondear(peso_actual)

        delta = rir_real - rir_obj  # + => más lejos del fallo que lo deseado

        if delta <= -2:
            # Fuiste más cerca del fallo de lo previsto (p. ej., querías 2 RIR y saliste 0)
            nuevo = peso_actual * (1 - self.ajuste_fuerte_pct)
        elif delta == -1:
            # Un poco más cerca del fallo
            nuevo = peso_actual * (1 - self.ajuste_suave_pct)
        elif delta == 0:
            # Clavado al objetivo: micro-progresión si además sobran reps
            if rep_gap >= self.umbral_rep_gap:
                nuevo = peso_actual * (1 + self.ajuste_suave_pct)
            else:
                nuevo = peso_actual
        elif delta == 1:
            # Más lejos del fallo (te sobró 1 RIR más)
            nuevo = peso_actual * (1 + self.ajuste_suave_pct)
        else:  # delta >= 2
            # Bastante lejos del fallo
            nuevo = peso_actual * (1 + self.ajuste_fuerte_pct)

        if limite_min_kg:
            nuevo = max(nuevo, limite_min_kg)

        return self._redondear(nuevo)

    def _redondear(self, peso: float) -> float:
        inc = self.incremento_redondeo
        if inc <= 0:
            return round(peso, 2)
        # Redondeo al múltiplo de inc más cercano y con 2 decimales
        return round(round(peso / inc) * inc, 2)


# ===============================================================
# SECCIÓN 2: Gestión dinámica de series
# ===============================================================

@dataclass
class SeriesManager:
    """
    Ajusta dinámicamente el nº de series por ejercicio/sesión según:
    - RIR real vs. objetivo
    - Rendimiento (reps alcanzadas vs. target del día)
    - Límites por grupo muscular (rango de series efectivas por semana)
    """
    min_series_ej: int = 2
    max_series_ej: int = 6
    step_series: int = 1

    def sugerir_series(
        self,
        series_actuales: int,
        rir_obj: int,
        rir_median_real: Optional[float],
        logro_reps: Optional[bool] = None
    ) -> int:
        """
        Args:
            series_actuales: series planificadas hoy para ese ejercicio.
            rir_obj: 0–3 típico.
            rir_median_real: mediana de RIR alcanzado en las series previas (None si no hay dato).
            logro_reps: True si cumpliste el mínimo de reps del rango objetivo; False si no.

        Regla simple:
          - Si vas DEMASIADO lejos del fallo (rir_median_real >= rir_obj+1) y encima cumples reps fácil -> +1 serie
          - Si vas DEMASIADO cerca del fallo (rir_median_real <= rir_obj-1) o no cumples reps -> -1 serie
          - Si estás clavado, mantén.
        """
        s = series_actuales

        if rir_median_real is None:
            return max(self.min_series_ej, min(self.max_series_ej, s))

        if (rir_median_real >= rir_obj + 1) and (logro_reps is True):
            s += self.step_series
        elif (rir_median_real <= rir_obj - 1) or (logro_reps is False):
            s -= self.step_series

        return max(self.min_series_ej, min(self.max_series_ej, s))

    def respetar_rango_musculo(
        self,
        totales_semana: int,
        rango_musculo: Tuple[int, int]
    ) -> int:
        """
        Recorta o eleva el total semanal de series de un músculo al rango permitido.
        """
        lo, hi = rango_musculo
        return max(lo, min(hi, totales_semana))


# ===============================================================
# SECCIÓN 3: Deload flexible por señales
# ===============================================================

@dataclass
class SeñalesDeload:
    """
    Contenedor sencillo con las señales de fatiga para tomar decisión de deload.
    """
    rendimiento_clave_cae: bool = False  # p. ej., 2 sesiones seguidas rinden peor a misma carga
    rpe_mas_alto_misma_carga: bool = False
    recuperacion_baja: bool = False      # p. ej., HRV peor, sueño pobre, cuestionario, etc.


@dataclass
class DeloadManager:
    """
    Decide si aplicar deload esta semana y cómo.
    """
    # Política: cuántas señales activas disparan deload
    min_seniales_para_deload: int = 2

    # Plantillas de deload (recomendadas por defecto)
    reduccion_volumen_pct: float = 0.4     # -40% series totales
    mantener_intensidad_relativa: bool = True  # Mantener %1RM/RIR similar, o bajar un poco si hace falta
    reducir_frecuencia_dias: int = 0        # 0 = misma frecuencia, 1–2 = “estirar” frecuencia

    def decidir_deload(self, s: SeñalesDeload) -> bool:
        activas = sum([s.rendimiento_clave_cae, s.rpe_mas_alto_misma_carga, s.recuperacion_baja])
        return activas >= self.min_seniales_para_deload

    def aplicar_plantilla(
        self,
        series_planificadas_por_ejercicio: Dict[str, int]
    ) -> Dict[str, int]:
        """
        Devuelve un nuevo dict con series reducidas para la semana de deload.
        """
        factor = 1.0 - max(0.0, min(0.8, self.reduccion_volumen_pct))  # límite por seguridad
        ajustadas = {}
        for ej, s in series_planificadas_por_ejercicio.items():
            nuevo = max(1, int(round(s * factor)))
            ajustadas[ej] = nuevo
        return ajustadas
