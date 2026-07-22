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

CAMBIOS v3 (fix bug grupos-desapareciendo-con-rpe9):
- [BUG FIX] El presupuesto de series_pesadas_max era un contador GLOBAL por
  sesión, compartido entre todos los grupos del día. Con rpe≥9 (todos los
  ejercicios son "pesados"), los primeros grupos procesados agotaban el
  presupuesto y los siguientes recibían 0 series (desaparecían del plan).
- [NUEVO PARAM] __init__ acepta `grupos_dia: Optional[List[str]]` (None por
  defecto para retrocompatibilidad total). Cuando se pasa la lista, el
  presupuesto se reparte a partes iguales entre los grupos (división entera +
  resto asignado a los primeros grupos de la lista, determinista sin random).
- [RETROCOMPAT DURA] Sin `grupos_dia`, el comportamiento es IDÉNTICO al
  v2 — un único contador global, todos los callers existentes sin cambios.
- [SCOPE LIMITADO] Solo `series_pesadas_max` cambia de modelo (global →
  per-grupo). `bisagra_pesada_max` y `rodilla_pesada_max` siguen siendo
  presupuestos globales por patrón de movimiento (fatiga SNC/lumbar real,
  rara vez compartidos entre más de 1-2 grupos en el mismo día, y no son
  la causa del bug reportado).
"""

from typing import Dict, List, Optional
from ..config import LIMITES_FATIGA, GRUPOS_GRANDES, LIMITES_SERIES_SESION

_PATRONES_RODILLA = {'rodilla'}
_PATRONES_BISAGRA = {'bisagra'}
# Clave interna para modo retrocompatible (sin grupos_dia)
_CLAVE_GLOBAL = '_global_'


class GestorFatiga:
    """Controla la fatiga acumulada durante una sesión."""

    def __init__(self, fase: str, grupos_dia: Optional[List[str]] = None):
        self.fase = fase.lower()
        self.limites = LIMITES_FATIGA.get(self.fase, LIMITES_FATIGA['hipertrofia'])
        # bisagra/rodilla: presupuestos globales por patrón de movimiento (sin cambios v3)
        self.fatiga_actual: Dict[str, int] = {
            'bisagra_pesada': 0,
            'rodilla_pesada': 0,
        }
        presupuesto = self.limites['series_pesadas_max']
        self._modo_global = grupos_dia is None

        if self._modo_global:
            # Retrocompatibilidad: presupuesto único global, clave interna fija.
            # GestorFatiga(fase) sin más argumentos = comportamiento v2 exacto.
            self.cupo_pesadas_por_grupo: Dict[str, int] = {_CLAVE_GLOBAL: presupuesto}
            self.fatiga_por_grupo: Dict[str, int] = {_CLAVE_GLOBAL: 0}
        else:
            # Reparto igual + suelo mínimo: división entera + resto a los primeros
            # grupos de la lista (determinista, sin random — invariante duro del motor).
            # Si len(grupos_dia) > presupuesto, los últimos grupos reciben 0 —
            # límite físico real del presupuesto, no corregible sin subir series_pesadas_max.
            n = len(grupos_dia)
            cuota_base = presupuesto // n if n > 0 else presupuesto
            resto = presupuesto % n if n > 0 else 0
            self.cupo_pesadas_por_grupo = {
                g: cuota_base + (1 if i < resto else 0)
                for i, g in enumerate(grupos_dia)
            }
            self.fatiga_por_grupo = {g: 0 for g in grupos_dia}

    def _clave_pesadas(self, grupo: str) -> Optional[str]:
        """Devuelve la clave de seguimiento para el presupuesto de series pesadas.
        Retorna None si el grupo no tiene cupo asignado (defensivo — no debería
        ocurrir en producción, pero evita KeyError ante datos inesperados)."""
        if self._modo_global:
            return _CLAVE_GLOBAL
        # Grupo no estaba en grupos_dia → cupo=0, no se registra (defensivo)
        return grupo if grupo in self.cupo_pesadas_por_grupo else None

    def ajustar_series_por_limite(
            self,
            nombre_ejercicio: str,
            patron: str,
            tipo_ejercicio: str,
            series: int,
            es_pesado: bool,
            grupo: str = '',
    ) -> int:
        """
        Ajusta el número de series si supera los límites de fatiga permitidos.

        Lógica de prioridad (Helms):
          1. Presupuesto de series pesadas por grupo (v3) o global (modo retrocompat).
          2. Presupuesto específico de bisagra pesada (siempre global).
          3. Presupuesto específico de rodilla pesada (siempre global).

        Para ejercicios no pesados solo se aplica el límite de sesión
        por grupo muscular (LIMITES_SERIES_SESION), que evita exceso de
        aislamiento en fases de volumen moderado.
        """
        series_ajustadas = int(series)

        if not es_pesado:
            if grupo:
                limites = self.obtener_limites_sesion(grupo)
                series_ajustadas = min(series_ajustadas, limites['max'])
            return series_ajustadas

        # 1) Presupuesto de series pesadas (per-grupo en modo nuevo, global en retrocompat)
        clave = self._clave_pesadas(grupo)
        if clave is None:
            return 0  # grupo desconocido sin cupo asignado (defensivo)

        cupo = self.cupo_pesadas_por_grupo[clave]
        consumido = self.fatiga_por_grupo.get(clave, 0)
        margen = cupo - consumido
        if margen <= 0:
            return 0

        if consumido + series_ajustadas > cupo:
            if tipo_ejercicio in ('aislamiento', 'compuesto_secundario'):
                series_ajustadas = max(0, margen)
            else:
                series_ajustadas = max(1, margen)

        # 2) Presupuesto de bisagra pesada (siempre global — fatiga SNC/lumbar)
        if patron in _PATRONES_BISAGRA:
            margen_bisagra = (
                self.limites['bisagra_pesada_max'] - self.fatiga_actual['bisagra_pesada']
            )
            if series_ajustadas > margen_bisagra:
                series_ajustadas = max(0, margen_bisagra)

        # 3) Presupuesto de rodilla pesada (siempre global)
        if patron in _PATRONES_RODILLA:
            margen_rodilla = (
                self.limites['rodilla_pesada_max'] - self.fatiga_actual['rodilla_pesada']
            )
            if series_ajustadas > margen_rodilla:
                series_ajustadas = max(0, margen_rodilla)

        return series_ajustadas

    def registrar_fatiga(self, patron: str, series: int, es_pesado: bool, grupo: str = '') -> None:
        """
        Registra la fatiga acumulada tras añadir un ejercicio.

        `grupo` se usa para actualizar el contador per-grupo de series pesadas.
        En modo retrocompat (sin grupos_dia), el valor de `grupo` se ignora
        y se usa el contador global interno.
        """
        if not es_pesado:
            return

        series = int(series)
        clave = self._clave_pesadas(grupo)
        if clave is not None:
            self.fatiga_por_grupo[clave] = self.fatiga_por_grupo.get(clave, 0) + series

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
