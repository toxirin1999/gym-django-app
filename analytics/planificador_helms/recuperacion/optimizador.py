# planificador_helms/recuperacion/optimizador.py
"""
Optimizador de recuperación basado en factores de Helms.

CAMBIOS v2:
- [BUG FIX] calcular_factor_recuperacion usaba pesos 0.3/0.4/0.3 (estrés,
  sueño, energía), mientras que PerfilCliente usaba 0.25/0.35/0.25/0.15.
  Misma función, resultados distintos. Unificados con PerfilCliente.
- [BUG FIX] optimizar_recuperacion devolvía None en la lista de recomendaciones
  cuando la condición no se cumplía. Filtrados correctamente.
- [MEJORA] nutricion_calidad añadido como parámetro opcional (default 7)
  para compatibilidad con callers legacy de 3 argumentos.
- [MEJORA] Recomendaciones para energía baja y nutrición deficiente.
"""

from typing import Dict, Any, List


class OptimizadorRecuperacion:
    """
    Pesos (alineados con PerfilCliente v2):
      Sueño 0.35 / Estrés 0.25 / Energía 0.25 / Nutrición 0.15
    """

    def __init__(
            self,
            nivel_estres: int,
            calidad_sueño: int,
            nivel_energia: int,
            nutricion_calidad: int = 7,
    ):
        self.nivel_estres = nivel_estres
        self.calidad_sueño = calidad_sueño
        self.nivel_energia = nivel_energia
        self.nutricion_calidad = nutricion_calidad

    def calcular_factor_recuperacion(self) -> float:
        estres_norm = (10 - self.nivel_estres) / 10
        sueño_norm = self.calidad_sueño / 10
        energia_norm = self.nivel_energia / 10
        nutricion_norm = self.nutricion_calidad / 10

        factor_base = (
                estres_norm * 0.25 +
                sueño_norm * 0.35 +
                energia_norm * 0.25 +
                nutricion_norm * 0.15
        )
        return round(0.7 + (factor_base * 0.6), 3)

    def necesita_descarga(self) -> bool:
        return self.calcular_factor_recuperacion() < 0.85

    def generar_recomendaciones(self) -> List[str]:
        recomendaciones: List[str] = []

        if self.calidad_sueño < 7:
            recomendaciones.append(
                'Priorizar 7-9h de sueño: mayor impacto en recuperación muscular y GH nocturna.'
            )
        if self.nivel_estres > 7:
            recomendaciones.append(
                'Estrés elevado: reduce volumen un 10-15% esta semana.'
            )
        if self.nivel_energia < 6:
            recomendaciones.append(
                'Energía baja: revisa déficit calórico y timing de carbohidratos peri-entreno.'
            )
        if self.nutricion_calidad < 6:
            recomendaciones.append(
                'Nutrición deficiente: asegura 1.6-2.2g proteína/kg y micronutrientes.'
            )
        if self.necesita_descarga():
            recomendaciones.append(
                'Semana de descarga recomendada: 50% volumen, RPE máximo 6.'
            )

        return recomendaciones


def optimizar_recuperacion(
        nivel_estres: int,
        calidad_sueño: int,
        nivel_energia: int,
        nutricion_calidad: int = 7,
) -> Dict[str, Any]:
    opt = OptimizadorRecuperacion(nivel_estres, calidad_sueño, nivel_energia, nutricion_calidad)
    factor = opt.calcular_factor_recuperacion()

    return {
        'factor_recuperacion': factor,
        'necesita_descarga': opt.necesita_descarga(),
        'nivel_recuperacion': _clasificar_nivel(factor),
        'recomendaciones': opt.generar_recomendaciones(),
    }


def _clasificar_nivel(factor: float) -> str:
    if factor >= 1.1:  return 'óptimo'
    if factor >= 0.95: return 'bueno'
    if factor >= 0.85: return 'moderado'
    return 'bajo'
