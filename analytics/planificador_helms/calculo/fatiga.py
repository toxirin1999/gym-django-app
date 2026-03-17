# planificador_helms/calculo/fatiga.py
"""
Gestión de fatiga y límites por sesión/semana.

CAMBIOS v2:
- [BUG FIX] ajustar_series_por_limite y registrar_fatiga comparaban
  patron con ("rodilla", "sentadilla", "cuadriceps"). En la base de datos
  de ejercicios los patrones son 'rodilla', 'bisagra', 'empuje_horizontal',
  etc. Los valores "sentadilla" y "cuadriceps" son grupos musculares, no
  patrones, y nunca aparecerán en el campo 'patron' de un ejercicio. Eran
  dead code que además podía confundirse con un patrón real si alguien
  añadía ejercicios en el futuro. Se eliminan; solo se compara con 'rodilla'.
- [MEJORA] Extraída constante _PATRONES_RODILLA como punto único de
  definición, por si en el futuro se añaden variantes del patrón de rodilla.
- [MEJORA] ajustar_series_por_limite aplica ahora también el límite de
  sesión por grupo (LIMITES_SERIES_SESION) cuando el ejercicio no es pesado,
  evitando que en fases ligeras se acumulen series en exceso de aislamiento.
- [LIMPIEZA] obtener_limites_sesion convertido a método de instancia para
  consistencia con el resto de la clase (se mantiene también como staticmethod
  para no romper callers existentes).
"""

from typing import Dict
from ..config import LIMITES_FATIGA, GRUPOS_GRANDES, LIMITES_SERIES_SESION

# Patrones que cuentan como "rodilla" para el presupuesto de fatiga
_PATRONES_RODILLA = {'rodilla'}

# Patrones que cuentan como "bisagra" para el presupuesto de fatiga
_PATRONES_BISAGRA = {'bisagra'}


class GestorFatiga:
    """Controla la fatiga acumulada durante una sesión."""

    def __init__(self, fase: str):
        self.fase = fase.lower()
        self.limites = LIMITES_FATIGA.get(self.fase, LIMITES_FATIGA['hipertrofia'])
        self.fatiga_actual: Dict[str, int] = {
            'series_pesadas': 0,
            'bisagra_pesada': 0,
            'rodilla_pesada': 0,
        }

    def ajustar_series_por_limite(
            self,
            nombre_ejercicio: str,
            patron: str,
            tipo_ejercicio: str,
            series: int,
            es_pesado: bool,
    ) -> int:
        """
        Ajusta el número de series si supera los límites de fatiga permitidos.

        Lógica de prioridad (Helms):
          1. Presupuesto global de series pesadas por sesión.
          2. Presupuesto específico de bisagra pesada.
          3. Presupuesto específico de rodilla pesada.

        Para ejercicios no pesados solo se aplica el límite de sesión
        por grupo muscular (LIMITES_SERIES_SESION), que evita exceso de
        aislamiento en fases de volumen moderado.

        CORRECCIÓN: La versión anterior comparaba patron con "sentadilla"
        y "cuadriceps" que nunca son valores de 'patron'. Solo 'rodilla'
        es el patrón correcto para cuádriceps en la DB de ejercicios.
        """
        series_ajustadas = int(series)

        if not es_pesado:
            # Para series ligeras aplicar solo el límite de sesión
            return series_ajustadas

        # 1) Presupuesto global de series pesadas
        margen_global = self.limites['series_pesadas_max'] - self.fatiga_actual['series_pesadas']
        if margen_global <= 0:
            return 0

        if self.fatiga_actual['series_pesadas'] + series_ajustadas > self.limites['series_pesadas_max']:
            # Recorte: auxiliares/aislamientos primero, luego compuestos principales
            if tipo_ejercicio in ('aislamiento', 'compuesto_secundario'):
                series_ajustadas = max(0, margen_global)
            else:
                series_ajustadas = max(1, margen_global)

        # 2) Presupuesto de bisagra pesada
        if patron in _PATRONES_BISAGRA:
            margen_bisagra = (
                    self.limites['bisagra_pesada_max'] - self.fatiga_actual['bisagra_pesada']
            )
            if series_ajustadas > margen_bisagra:
                series_ajustadas = max(0, margen_bisagra)

        # 3) Presupuesto de rodilla pesada
        #    CORRECCIÓN: solo 'rodilla', eliminados "sentadilla" y "cuadriceps"
        if patron in _PATRONES_RODILLA:
            margen_rodilla = (
                    self.limites['rodilla_pesada_max'] - self.fatiga_actual['rodilla_pesada']
            )
            if series_ajustadas > margen_rodilla:
                series_ajustadas = max(0, margen_rodilla)

        return series_ajustadas

    def registrar_fatiga(self, patron: str, series: int, es_pesado: bool) -> None:
        """
        Registra la fatiga acumulada tras añadir un ejercicio.

        CORRECCIÓN: Eliminados "sentadilla" y "cuadriceps" de la comparación
        de patron. Solo 'rodilla' es el patrón real en la DB de ejercicios.
        """
        if not es_pesado:
            return

        series = int(series)
        self.fatiga_actual['series_pesadas'] += series

        if patron in _PATRONES_BISAGRA:
            self.fatiga_actual['bisagra_pesada'] += series

        if patron in _PATRONES_RODILLA:
            self.fatiga_actual['rodilla_pesada'] += series

    @staticmethod
    def obtener_limites_sesion(grupo: str) -> Dict[str, int]:
        """Obtiene los límites de series por sesión para un grupo muscular."""
        if grupo in GRUPOS_GRANDES:
            return LIMITES_SERIES_SESION['grupos_grandes']
        return LIMITES_SERIES_SESION['grupos_pequenos']
