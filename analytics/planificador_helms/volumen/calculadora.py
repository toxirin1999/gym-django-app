# planificador_helms/volumen/calculadora.py
"""
Calculadora de volumen según principios de Helms / Israetel.

CAMBIOS v2:
- [BUG FIX] calcular_volumen_mantenimiento y calcular_volumen_maximo_adaptativo:
  solo cubrían 3 grupos musculares (pecho, espalda, piernas) con un fallback
  de 6/20 para todo lo demás. Grupos como hombros, bíceps, glúteos, core,
  trapecios o antebrazos siempre caían al fallback silenciosamente.
  Ahora los métodos usan directamente VOLUMENES_BASE y VOLUMENES_MAXIMOS de
  config.py, cubriendo los 12 grupos del sistema con una única fuente de verdad.
- [BUG FIX] DEFAULTS_1RM['mancuerna'] era 60kg (total para dos mancuernas = 30kg
  cada una), un valor demasiado alto como fallback universal para principiantes.
  La CalculadoraVolumen no usa DEFAULTS_1RM directamente, pero se documenta
  aquí como referencia para CalculadorPeso.
- [MEJORA] calcular_volumen_optimo ahora aplica el multiplicador de objetivo
  con límites inferior/superior para no salir del rango MEV–MRV.
- [MEJORA] Añadido calcular_rango_volumen para exponer MEV y MRV juntos,
  que es como Israetel los presenta en la práctica.
- [NOTA] Esta clase era código muerto porque core.py iba directamente a
  VOLUMENES_BASE. Ahora ambos acceden a la misma fuente y CalculadoraVolumen
  añade la lógica de ajuste por objetivo y recuperación que core.py delega
  a PerfilCliente. Están bien separados.
"""

from typing import Dict, Tuple
from ..config import VOLUMENES_BASE

# ─── Volúmenes máximos adaptativos (MRV) por nivel ───────────────────────────
# Basados en Israetel et al. "Scientific Principles of Strength Training" y
# las guías de volumen de Renaissance Periodization.
# Estos son límites de recuperación, no objetivos: superarlos acumula fatiga
# sin adaptación adicional.
VOLUMENES_MAXIMOS: Dict[str, Dict[str, int]] = {
    'principiante': {
        'pecho': 14,
        'espalda': 16,
        'hombros': 12,
        'biceps': 10,
        'triceps': 10,
        'cuadriceps': 16,
        'isquios': 12,
        'gluteos': 12,
        'gemelos': 10,
        'core': 10,
        'trapecios': 8,
        'antebrazos': 6,
    },
    'intermedio': {
        'pecho': 20,
        'espalda': 22,
        'hombros': 16,
        'biceps': 14,
        'triceps': 14,
        'cuadriceps': 20,
        'isquios': 16,
        'gluteos': 18,
        'gemelos': 14,
        'core': 14,
        'trapecios': 12,
        'antebrazos': 8,
    },
    'avanzado': {
        'pecho': 22,
        'espalda': 25,
        'hombros': 20,
        'biceps': 18,
        'triceps': 18,
        'cuadriceps': 25,
        'isquios': 20,
        'gluteos': 22,
        'gemelos': 18,
        'core': 16,
        'trapecios': 14,
        'antebrazos': 10,
    },
}

# Multiplicadores de volumen por objetivo
# Fuente: Helms, "The Muscle and Strength Pyramid - Training", cap. 5
_MULT_OBJETIVO: Dict[str, float] = {
    'hipertrofia': 1.15,
    'fuerza_hipertrofia': 1.0,
    'fuerza': 0.85,
    'potencia': 0.70,
    'resistencia': 1.25,
}


class CalculadoraVolumen:
    """
    Calculadora de volumen semanal (series) según principios de Helms/Israetel.

    Terminología:
      MEV  Minimum Effective Volume   — mínimo para provocar adaptación
      MAV  Maximum Adaptive Volume    — rango óptimo de ganancias
      MRV  Maximum Recoverable Volume — límite antes de acumular fatiga neta
    """

    @staticmethod
    def calcular_volumen_mantenimiento(grupo_muscular: str, experiencia: str) -> int:
        """
        Calcula volumen mínimo de mantenimiento (MEV) en series semanales.

        CORRECCIÓN: La versión anterior solo cubría pecho/espalda/piernas.
        Ahora usa VOLUMENES_BASE de config.py que cubre los 12 grupos del sistema.
        El MEV se aproxima al 60-70% del volumen base (que representa el MAV bajo).
        """
        nivel = experiencia if experiencia in VOLUMENES_BASE else 'principiante'
        vol_base = VOLUMENES_BASE[nivel].get(grupo_muscular)

        if vol_base is None:
            # Grupo no reconocido: fallback conservador con aviso implícito
            return 4

        # MEV ≈ 60% del MAV base. Mínimo 4 series/semana.
        return max(round(vol_base * 0.60), 4)

    @staticmethod
    def calcular_volumen_maximo_adaptativo(grupo_muscular: str, experiencia: str) -> int:
        """
        Calcula el volumen máximo adaptativo (MRV) en series semanales.

        CORRECCIÓN: La versión anterior solo cubría pecho/espalda/piernas
        con un fallback de 20 para todo lo demás. Hombros, bíceps, glúteos,
        core, etc., siempre devolvían 20 silenciosamente.
        Ahora usa VOLUMENES_MAXIMOS que cubre los 12 grupos del sistema.
        """
        nivel = experiencia if experiencia in VOLUMENES_MAXIMOS else 'principiante'
        mrv = VOLUMENES_MAXIMOS[nivel].get(grupo_muscular)

        if mrv is None:
            return 20  # fallback explícito y documentado

        return mrv

    @staticmethod
    def calcular_rango_volumen(
            grupo_muscular: str,
            experiencia: str,
    ) -> Tuple[int, int]:
        """
        Devuelve (MEV, MRV) para un grupo muscular y nivel dados.

        Uso típico:
            mev, mrv = CalculadoraVolumen.calcular_rango_volumen('pecho', 'intermedio')
            # → (8, 20)
            volumen_semana_1 = mev          # inicio de bloque
            volumen_semana_4 = mrv - 2      # final de bloque antes de deload
        """
        mev = CalculadoraVolumen.calcular_volumen_mantenimiento(grupo_muscular, experiencia)
        mrv = CalculadoraVolumen.calcular_volumen_maximo_adaptativo(grupo_muscular, experiencia)
        return mev, mrv


def calcular_volumen_optimo(
        grupo_muscular: str,
        experiencia: str,
        objetivo: str,
        factor_recuperacion: float = 1.0,
) -> int:
    """
    Calcula volumen óptimo semanal (series) para un grupo muscular.

    Args:
        grupo_muscular:      Nombre del grupo ('pecho', 'espalda', etc.)
        experiencia:         'principiante' | 'intermedio' | 'avanzado'
        objetivo:            'hipertrofia' | 'fuerza' | 'fuerza_hipertrofia' | etc.
        factor_recuperacion: Float 0.7–1.3 del PerfilCliente (default 1.0)

    Returns:
        Volumen en series, acotado entre MEV y MRV.

    CORRECCIÓN: La versión anterior calculaba int(mev * 1.5) para hipertrofia
    y int(mev * 1.2) para fuerza, lo que podía superar el MRV para avanzados.
    Ahora se aplica el multiplicador de objetivo al volumen base (MAV) y se
    acota explícitamente entre MEV y MRV.
    """
    calculadora = CalculadoraVolumen()
    mev = calculadora.calcular_volumen_mantenimiento(grupo_muscular, experiencia)
    mrv = calculadora.calcular_volumen_maximo_adaptativo(grupo_muscular, experiencia)

    nivel = experiencia if experiencia in VOLUMENES_BASE else 'principiante'
    vol_base = VOLUMENES_BASE[nivel].get(grupo_muscular, mev)

    mult = _MULT_OBJETIVO.get(objetivo.lower().replace(' ', '_'), 1.0)
    volumen_calculado = round(vol_base * mult * factor_recuperacion)

    # Acotar entre MEV y MRV
    return max(mev, min(volumen_calculado, mrv))
