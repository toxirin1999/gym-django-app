# analytics/validador_jerarquia_helms.py

from enum import Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass

# Asumimos que PerfilCliente está en este módulo, si no, ajústalo
from .planificador_helms_completo import PerfilCliente


class NivelPiramide(Enum):
    ADHERENCIA = 1
    VOLUMEN_INTENSIDAD_FRECUENCIA = 2
    PROGRESION = 3
    SELECCION_EJERCICIOS = 4
    TIMING = 5


@dataclass
class CriterioValidacion:
    nombre: str
    descripcion: str
    funcion_validacion: callable
    peso: float
    requerido: bool = True


@dataclass
class ResultadoValidacion:
    nivel: NivelPiramide
    puntuacion: float
    criterios_cumplidos: List[str]
    criterios_faltantes: List[str]
    recomendaciones: List[str]
    puede_avanzar: bool


class ValidadorJerarquiaHelms:
    def __init__(self, perfil_cliente: PerfilCliente):
        self.perfil = perfil_cliente
        self.criterios_por_nivel = self._definir_criterios()
        self.umbrales_avance = {
            NivelPiramide.ADHERENCIA: 80.0,
            NivelPiramide.VOLUMEN_INTENSIDAD_FRECUENCIA: 75.0,
            NivelPiramide.PROGRESION: 70.0,
            NivelPiramide.SELECCION_EJERCICIOS: 65.0,
            NivelPiramide.TIMING: 60.0
        }

    def _definir_criterios(self) -> Dict[NivelPiramide, List[CriterioValidacion]]:
        return {
            NivelPiramide.ADHERENCIA: [
                CriterioValidacion("datos_disponibilidad", "Días y tiempo por sesión definidos",
                                   self._validar_datos_disponibilidad, 0.4),
                CriterioValidacion("preferencias_ejercicios", "Preferencias y limitaciones capturadas",
                                   self._validar_preferencias_ejercicios, 0.3),
                CriterioValidacion("factores_lifestyle", "Factores de estilo de vida evaluados",
                                   self._validar_factores_lifestyle, 0.3),
            ],
            # Añadiremos más niveles en los siguientes pasos
        }

    def validar_nivel(self, nivel: NivelPiramide) -> ResultadoValidacion:
        criterios = self.criterios_por_nivel.get(nivel, [])
        puntuacion_total = 0.0
        criterios_cumplidos = []
        criterios_faltantes = []

        for criterio in criterios:
            try:
                cumple, puntuacion_criterio = criterio.funcion_validacion()
                puntuacion_ponderada = puntuacion_criterio * criterio.peso
                puntuacion_total += puntuacion_ponderada
                if cumple:
                    criterios_cumplidos.append(criterio.nombre)
                else:
                    criterios_faltantes.append(criterio.nombre)
            except Exception as e:
                print(f"Error validando criterio {criterio.nombre}: {e}")
                criterios_faltantes.append(criterio.nombre)

        puntuacion_final = min(100.0, puntuacion_total)
        puede_avanzar = puntuacion_final >= self.umbrales_avance.get(nivel, 101)

        return ResultadoValidacion(
            nivel=nivel,
            puntuacion=puntuacion_final,
            criterios_cumplidos=criterios_cumplidos,
            criterios_faltantes=criterios_faltantes,
            recomendaciones=self._generar_recomendaciones(nivel, criterios_faltantes),
            puede_avanzar=puede_avanzar
        )

    # --- Funciones de validación específicas ---
    def _validar_datos_disponibilidad(self) -> Tuple[bool, float]:
        puntuacion = 0.0
        if getattr(self.perfil, 'dias_disponibles', 0) > 0:
            puntuacion += 50.0
        if getattr(self.perfil, 'tiempo_por_sesion', 0) > 0:
            puntuacion += 50.0
        return puntuacion >= 70.0, puntuacion

    def _validar_preferencias_ejercicios(self) -> Tuple[bool, float]:
        puntuacion = 0.0
        if hasattr(self.perfil, 'ejercicios_preferidos'):
            puntuacion += 33.3
        if hasattr(self.perfil, 'ejercicios_evitar'):
            puntuacion += 33.3
        if hasattr(self.perfil, 'limitaciones_fisicas'):
            puntuacion += 33.4
        return puntuacion >= 70.0, puntuacion

    def _validar_factores_lifestyle(self) -> Tuple[bool, float]:
        puntuacion = 0.0
        factores = ['nivel_estres', 'calidad_sueño', 'nivel_energia']
        for factor in factores:
            if isinstance(getattr(self.perfil, factor, None), (int, float)):
                puntuacion += 33.33
        return puntuacion >= 70.0, puntuacion

    def _generar_recomendaciones(self, nivel: NivelPiramide, criterios_faltantes: List[str]) -> List[str]:
        recomendaciones_map = {
            "datos_disponibilidad": "Define tus días y tiempo de entrenamiento en tu perfil.",
            "preferencias_ejercicios": "Añade tus ejercicios preferidos y limitaciones para personalizar tu plan.",
            "factores_lifestyle": "Completa tu evaluación de estrés, sueño y energía para ajustar la intensidad."
        }
        return [recomendaciones_map[c] for c in criterios_faltantes if c in recomendaciones_map]


# --- Función Helper para usar en las vistas ---
def validar_adherencia_basica(perfil_cliente: PerfilCliente) -> ResultadoValidacion:
    """Función helper que valida el primer nivel de la pirámide."""
    validador = ValidadorJerarquiaHelms(perfil_cliente)
    return validador.validar_nivel(NivelPiramide.ADHERENCIA)
