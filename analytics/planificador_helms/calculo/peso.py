# planificador_helms/calculo/peso.py
"""
Lógica para el cálculo de pesos de trabajo.
"""

import math
from typing import Dict, Any, Optional
from ..config import PROGRESION, REDONDEO, DEFAULTS_1RM, KEYWORDS_BARRA, KEYWORDS_MANCUERNA, KEYWORDS_CABLE, \
    KEYWORDS_MAQUINA
from ..utils.helpers import normalizar_nombre


class CalculadorPeso:
    """Clase encargada de calcular los pesos de trabajo según el sistema Helms."""

    @staticmethod
    def inferir_tipo_carga(nombre_ejercicio: str) -> str:
        """
        Inferencia del tipo de carga según el nombre del ejercicio.
        Devuelve: 'mancuerna' | 'barra' | 'maquina' | 'cable' | 'general'
        """
        n = normalizar_nombre(nombre_ejercicio)

        if any(k in n for k in KEYWORDS_MANCUERNA):
            return "mancuerna"
        if any(k in n for k in KEYWORDS_CABLE):
            return "cable"
        if any(k in n for k in KEYWORDS_MAQUINA):
            return "maquina"
        if any(k in n for k in KEYWORDS_BARRA):
            return "barra"

        return "general"

    @staticmethod
    def redondear_peso(peso: float, nombre_ejercicio: str) -> float:
        """
        Redondeo "de gimnasio real" basado en el tipo de carga.
        """
        if peso is None:
            return 0.0

        try:
            peso = float(peso)
        except (ValueError, TypeError):
            return 0.0

        tipo = CalculadorPeso.inferir_tipo_carga(nombre_ejercicio)

        # Obtener incremento según configuración
        inc = REDONDEO.get(tipo, REDONDEO['general'])

        # Redondeo al múltiplo más cercano
        if inc <= 0:
            return round(peso, 1)

        return round(peso / inc) * inc

    @classmethod
    def calcular_peso_trabajo(cls, nombre_ejercicio: str, repeticiones_str: str, rpe_objetivo: int,
                              maximos_actuales: Dict[str, float] = None,
                              rpe_real_anterior: Optional[float] = None) -> float:
        """
        Calcula el peso de trabajo teórico para un ejercicio dado.
        rpe_real_anterior: RPE real registrado en la última sesión de este ejercicio.
        Si se proporciona, modula la progresión automáticamente.
        """
        nombre_normalizado = normalizar_nombre(nombre_ejercicio)
        maximos_actuales = maximos_actuales or {}

        def _es_mancuerna(nombre: str) -> bool:
            return any(k in nombre for k in KEYWORDS_MANCUERNA)

        def _default_one_rm(nombre: str) -> float:
            # Primero intentar por nombre exacto en defaults
            for key, val in DEFAULTS_1RM.items():
                if key in nombre:
                    return val

            # TODO: Aquí se podría integrar la lógica de patrones si se tuviera acceso al PatronManager
            # Por ahora usamos el default general de aislamiento si no hay match
            return DEFAULTS_1RM['aislamiento']

        # 1) 1RM real si existe; si no, default
        one_rm_estimado = maximos_actuales.get(nombre_normalizado)
        if not one_rm_estimado or one_rm_estimado <= 0:
            one_rm_estimado = _default_one_rm(nombre_normalizado)

        try:
            reps_planificadas = int(repeticiones_str.split('-')[0].strip())
        except:
            reps_planificadas = 8

        try:
            # 1. Calcular el peso de trabajo teórico para el RPE y repeticiones objetivo.
            peso_rpe_10 = one_rm_estimado / (1 + (reps_planificadas / 30))
            reduccion_por_rpe = (10 - rpe_objetivo) * 0.03
            peso_base_calculado = peso_rpe_10 * (1 - reduccion_por_rpe)

            # 2. Determinar progresión basada en RPE real anterior si existe
            umbral = PROGRESION['umbral_ejercicio_pesado']
            es_pesado = one_rm_estimado > umbral

            if rpe_real_anterior is not None:
                diferencia_rpe = rpe_real_anterior - rpe_objetivo
                if diferencia_rpe <= -2:
                    # RPE muy por debajo del objetivo — subir agresivo
                    if es_pesado:
                        peso_con_progresion = peso_base_calculado * 1.075
                    else:
                        peso_con_progresion = peso_base_calculado + PROGRESION['fijo_grande']
                elif diferencia_rpe <= 0:
                    # RPE igual o ligeramente por debajo — subir normal
                    if es_pesado:
                        peso_con_progresion = peso_base_calculado * PROGRESION['porcentual']
                    else:
                        peso_con_progresion = peso_base_calculado + PROGRESION['fijo_pequeno']
                elif diferencia_rpe <= 2:
                    # RPE por encima del objetivo — mantener peso
                    peso_con_progresion = peso_base_calculado
                else:
                    # RPE muy por encima — bajar ligeramente
                    if es_pesado:
                        peso_con_progresion = peso_base_calculado * 0.95
                    else:
                        peso_con_progresion = peso_base_calculado - PROGRESION['fijo_pequeno']
            else:
                # Sin historial de RPE — progresión estándar
                if es_pesado:
                    peso_con_progresion = peso_base_calculado * PROGRESION['porcentual']
                else:
                    peso_con_progresion = peso_base_calculado + PROGRESION['fijo_pequeno']

            # 3. Redondear al múltiplo más cercano.
            peso_final = cls.redondear_peso(peso_con_progresion, nombre_ejercicio)
            return peso_final

        except ZeroDivisionError:
            return 20.0
