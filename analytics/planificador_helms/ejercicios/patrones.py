# planificador_helms/ejercicios/patrones.py
"""
Gestión de patrones de movimiento y detección de fatiga por patrón.

CAMBIOS v2:
- [BUG FIX] obtener_patron_ejercicio tenía las keywords de detección
  hardcodeadas e independientes de config.py. Si se añadía una keyword
  en KEYWORDS_VERTICAL o KEYWORDS_HORIZONTAL de config, patrones.py no
  la detectaba. Ahora importa directamente KEYWORDS_VERTICAL, KEYWORDS_HORIZONTAL
  y KEYWORDS_PRINCIPALES de config para la detección de patrones, eliminando
  la duplicación.
- [MEJORA] Añadida detección de patrón 'aislamiento' para ejercicios
  de brazos y gemelos, que antes devolvían string vacío y forzaban un
  fallback tardío en core.py.
- [LIMPIEZA] Eliminadas keywords duplicadas en la heurística de patrones
  que ya estaban cubiertas por las constantes de config.
"""

from typing import Dict, Set, Optional
from ..config import (
    PATRONES_OBJETIVO,
    BISAGRA_PESADAS, BISAGRA_LIGERAS,
    MAX_DIAS_BISAGRA,
    KEYWORDS_VERTICAL, KEYWORDS_HORIZONTAL, KEYWORDS_PRINCIPALES,
)
from ..utils.helpers import normalizar_nombre


class PatronManager:
    """Gestiona los patrones de movimiento y asegura la cobertura semanal."""

    def __init__(self, fase: str = 'hipertrofia'):
        self.fase = fase.lower()
        self.estado_semana: Dict[str, Dict] = {
            'bisagra': {
                'dias_usados_pesada': 0, 'dias_usados_ligera': 0,
                'ultimo_indice_dia': None, 'ultima_variante': 'ligera',
            },
            'empuje_vertical': {'dias_usados': 0, 'ultimo_indice_dia': None},
            'empuje_horizontal': {'dias_usados': 0, 'ultimo_indice_dia': None},
            'traccion_vertical': {'dias_usados': 0, 'ultimo_indice_dia': None},
            'traccion_horizontal': {'dias_usados': 0, 'ultimo_indice_dia': None},
        }
        self.patrones_usados_por_grupo: Dict[str, Set[str]] = {}

    def obtener_patron_ejercicio(self, nombre_ejercicio: str) -> str:
        """
        Determina el patrón de movimiento de un ejercicio por heurística.

        CORRECCIÓN: Las keywords de detección estaban hardcodeadas aquí,
        duplicando las constantes de config.py. Si se añadía una keyword
        en config, este método no la detectaba. Ahora usa las constantes
        importadas directamente de config.

        Orden de detección:
          1. Tracción (vertical > horizontal)
          2. Empuje (horizontal > vertical)
          3. Pierna (rodilla > bisagra)
          4. Aislamiento (brazos, gemelos, core)
          5. String vacío si no hay match (aislamiento genérico en core.py)
        """
        nombre = normalizar_nombre(nombre_ejercicio)

        # ── Tracción ──────────────────────────────────────────────────────────
        # KEYWORDS_VERTICAL = ['dominad', 'jalón', 'jalon']  ← desde config
        if any(k in nombre for k in KEYWORDS_VERTICAL):
            return 'traccion_vertical'

        # KEYWORDS_HORIZONTAL = ['remo', 'polea baja', 'gironda', 'pendlay']
        if any(k in nombre for k in KEYWORDS_HORIZONTAL):
            return 'traccion_horizontal'

        if 'face pull' in nombre or 'pull-over' in nombre or 'pullover' in nombre:
            return 'traccion_horizontal'

        # ── Empuje ────────────────────────────────────────────────────────────
        if any(k in nombre for k in [
            'press banca', 'press inclinado', 'fondos', 'pec deck',
            'apertur', 'cruce de poleas', 'low-to-high', 'convergent',
        ]):
            return 'empuje_horizontal'

        if any(k in nombre for k in [
            'press militar', 'push press', 'press arnold',
            'machine shoulder', 'elevaciones',
        ]):
            return 'empuje_vertical'

        # ── Pierna ────────────────────────────────────────────────────────────
        if any(k in nombre for k in [
            'sentadilla', 'prensa', 'zancad', 'extension', 'sissy',
        ]):
            return 'rodilla'

        if any(k in nombre for k in [
            'peso muerto', 'rumano', 'buenos días', 'buenos dias',
            'good morning', 'hip thrust', 'hiperext',
        ]):
            return 'bisagra'

        # ── Aislamiento (brazos, gemelos, core) ───────────────────────────────
        if any(k in nombre for k in [
            'curl', 'rosca', 'rompecráneos', 'rompecraneos', 'patada',
            'gemelo', 'talón', 'talon', 'plancha', 'crunch', 'abdom',
            'encogimiento', 'farmer', 'agarre', 'muñeca',
        ]):
            return 'aislamiento'

        return ''

    def puede_usar_bisagra(self, dia_index: int, nombre_ejercicio: str = '') -> bool:
        """
        Verifica si se puede usar un patrón de bisagra en el día actual.

        Reglas (versión corregida X.2 + fix presupuesto por variante):
          - Mismo día (diff=0): SIEMPRE permitido. Dos bisagras en la misma sesión
            (ej. RDL isquios + Hip Thrust glúteos) es diseño de entrenamiento legítimo.
            La restricción original (<=1) bloqueaba erróneamente este caso.
          - Días adyacentes (diff=1): solo bloqueado si CUALQUIERA de las dos variantes
            involucradas es 'pesada' (PM convencional/sumo — fatiga SNC/lumbar alta).
            Dos variantes ligeras (RDL, Hip Thrust) en días consecutivos tienen
            demanda sistémica baja y se permiten.
          - Más de 1 día de distancia: siempre permitido.
          - Presupuesto semanal (MAX_DIAS_BISAGRA): solo se aplica a variantes
            'pesada'. Es un límite de fatiga SNC/lumbar real, y esa fatiga es la
            que justifica capar cuántas veces por semana se puede hacer peso
            muerto convencional/sumo. Las variantes 'ligera' NO cargan ese riesgo
            sistémico, así que no deben competir por un presupuesto semanal
            compartido con otro grupo distinto (isquios vs glúteos) — antes de
            que la frecuencia fuera dinámica (X.6/X.7) esto nunca se notaba
            porque cada grupo bisagra aparecía como máximo 1x/semana; con
            frecuencia dinámica, un grupo con freq=2 podía agotar él solo el
            presupuesto y dejar sin cupo al otro grupo bisagra, aunque su
            ejercicio fuera igual de ligero y seguro.
        """
        info = self.estado_semana['bisagra']
        variante_actual = (
            self.clasificar_variante_bisagra(nombre_ejercicio)
            if nombre_ejercicio else 'ligera'
        )

        if info['ultimo_indice_dia'] is not None:
            diff = abs(dia_index - info['ultimo_indice_dia'])
            if diff == 1:
                # Días adyacentes: bloquear solo si alguna variante es pesada
                ultima_variante = info.get('ultima_variante', 'ligera')
                if ultima_variante == 'pesada' or variante_actual == 'pesada':
                    return False
            # diff == 0: mismo día → siempre permitido (no aplicar restricción)
            # diff > 1: no adyacente → siempre permitido

        if variante_actual != 'pesada':
            # Ligera: sin tope semanal, solo sujeta a la restricción de arriba.
            return True

        max_bisagra = MAX_DIAS_BISAGRA.get(self.fase, MAX_DIAS_BISAGRA['hipertrofia'])
        return info['dias_usados_pesada'] < max_bisagra

    def registrar_uso_patron(
            self,
            patron: str,
            dia_index: int,
            grupo: Optional[str] = None,
            nombre_ejercicio: str = '',
    ) -> None:
        """Registra el uso de un patrón en un día específico."""
        if patron in self.estado_semana:
            self.estado_semana[patron]['ultimo_indice_dia'] = dia_index
            if patron == 'bisagra':
                variante = (
                    self.clasificar_variante_bisagra(nombre_ejercicio)
                    if nombre_ejercicio else 'ligera'
                )
                # Guardar variante para que puede_usar_bisagra sepa si la última fue pesada
                self.estado_semana['bisagra']['ultima_variante'] = variante
                if variante == 'pesada':
                    self.estado_semana['bisagra']['dias_usados_pesada'] += 1
                else:
                    self.estado_semana['bisagra']['dias_usados_ligera'] += 1
            else:
                self.estado_semana[patron]['dias_usados'] += 1

        if grupo:
            if grupo not in self.patrones_usados_por_grupo:
                self.patrones_usados_por_grupo[grupo] = set()
            self.patrones_usados_por_grupo[grupo].add(patron)

    def obtener_faltantes_grupo(self, grupo: str) -> Set[str]:
        """Obtiene los patrones obligatorios aún no usados para un grupo muscular."""
        objetivo = PATRONES_OBJETIVO.get(grupo, set())
        usados = self.patrones_usados_por_grupo.get(grupo, set())
        return objetivo - usados

    @staticmethod
    def clasificar_variante_bisagra(nombre_ejercicio: str) -> str:
        """
        Clasifica una variante de bisagra como 'pesada' o 'ligera'.

        Usa BISAGRA_PESADAS y BISAGRA_LIGERAS de config para la detección,
        con fallback conservador a 'ligera'.
        """
        nombre = normalizar_nombre(nombre_ejercicio)
        if any(kw in nombre for kw in BISAGRA_LIGERAS):
            return 'ligera'
        if any(kw in nombre for kw in BISAGRA_PESADAS):
            return 'pesada'
        return 'ligera'  # fallback conservador
