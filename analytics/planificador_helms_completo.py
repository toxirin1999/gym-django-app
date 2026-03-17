# planificador_helms_completo.py
"""
DEPRECATED: Este archivo se mantiene por compatibilidad hacia atrás.
Se recomienda migrar los imports a la nueva estructura modular:

Uso recomendado:
    from planificador_helms import PlanificadorHelms, PerfilCliente
"""

import warnings
from datetime import datetime
from typing import Dict, Any, List

# Imports desde la nueva estructura modular
from .planificador_helms.core import PlanificadorHelms as NewPlanificadorHelms
from .planificador_helms.models.perfil_cliente import PerfilCliente
from .planificador_helms.volumen.calculadora import CalculadoraVolumen, calcular_volumen_optimo
from .planificador_helms.recuperacion.optimizador import OptimizadorRecuperacion, optimizar_recuperacion
from .planificador_helms.ejercicios.selector import SelectorEjercicios
from .planificador_helms.database.ejercicios import EJERCICIOS_DATABASE

# Advertencia de depreciación
warnings.warn(
    "planificador_helms_completo.py está depreciado y será eliminado en futuras versiones. "
    "Por favor, use el paquete 'analytics.planificador_helms'.",
    DeprecationWarning,
    stacklevel=2
)

# Clases de constantes para compatibilidad legacy
class NivelExperiencia:
    PRINCIPIANTE = 'principiante'
    INTERMEDIO = 'intermedio'
    AVANZADO = 'avanzado'

class ObjetivoEntrenamiento:
    HIPERTROFIA = 'hipertrofia'
    FUERZA = 'fuerza'
    POTENCIA = 'potencia'

class GrupoMuscular:
    PECHO = 'pecho'
    ESPALDA = 'espalda'
    HOMBROS = 'hombros'
    BICEPS = 'biceps'
    TRICEPS = 'triceps'
    CUADRICEPS = 'cuadriceps'
    ISQUIOS = 'isquios'
    GLUTEOS = 'gluteos'
    GEMELOS = 'gemelos'
    CORE = 'core'

def crear_perfil_desde_cliente(cliente_obj) -> PerfilCliente:
    """
    Crea un PerfilCliente a partir de un objeto de base de datos Cliente o dict.
    """
    if isinstance(cliente_obj, dict):
        return PerfilCliente(cliente_obj)
        
    data = {
        'id': getattr(cliente_obj, 'id', None),
        'nombre': getattr(cliente_obj, 'nombre', 'Cliente'),
        'experiencia_años': getattr(cliente_obj, 'experiencia_años', 0),
        'objetivo_principal': getattr(cliente_obj, 'objetivo_principal', 'hipertrofia'),
        'dias_disponibles': getattr(cliente_obj, 'dias_disponibles', 4),
        'nivel_estres': getattr(cliente_obj, 'nivel_estres', 5),
        'calidad_sueño': getattr(cliente_obj, 'calidad_sueño', 7),
        'nivel_energia': getattr(cliente_obj, 'nivel_energia', 7),
        'ejercicios_evitar': getattr(cliente_obj, 'ejercicios_evitar', []),
        'maximos_actuales': getattr(cliente_obj, 'one_rm_data', {}),
    }
    return PerfilCliente(data)

class PlanificadorHelms(NewPlanificadorHelms):
    """
    Wrapper de compatibilidad para la clase PlanificadorHelms antigua.
    """
    def __init__(self, cliente_data: Any = None, **kwargs):
        # Manejar si se pasa PerfilCliente o dict/kwargs
        if isinstance(cliente_data, PerfilCliente):
            perfil = cliente_data
        else:
            perfil = PerfilCliente(cliente_data, **kwargs)
        super().__init__(perfil)

    def generar_plan_completo(self) -> Dict[str, Any]:
        """
        Método legacy que mapea a la nueva lógica de generación.
        """
        plan_nuevo = self.generar_plan_anual()
        
        # Mapear formato nuevo a legacy para PlanificadorIntegrado
        # PlanificadorIntegrado busca 'fases' y 'ejercicios_por_semana'
        ejercicios_semana = {}
        for fecha_iso, entreno in plan_nuevo.get('entrenos_por_fecha', {}).items():
            # Agrupar por semana relativa (aproximación)
            try:
                dt = datetime.fromisoformat(fecha_iso)
                semana_num = dt.isocalendar()[1]
                clave_sem = f"semana_{semana_num}"
                if clave_sem not in ejercicios_semana:
                    ejercicios_semana[clave_sem] = []
                ejercicios_semana[clave_sem].extend(entreno.get('ejercicios', []))
            except:
                continue

        return {
            'status': 'success',
            'duracion_total_semanas': 52,
            'fases': plan_nuevo.get('plan_por_bloques', []),
            'ejercicios_por_semana': ejercicios_semana,
            'metadata': plan_nuevo.get('metadata', {})
        }

    def validar_plan_existente(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stub de compatibilidad para validación de planes.
        """
        return {
            'score_adherencia': 85,
            'mejoras_aplicadas': [],
            'advertencias': [],
            'mejoras_sugeridas': []
        }

# Funciones de utilidad para compatibilidad legacy
def generar_plan_helms(cliente_data: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper para la función legacy."""
    perfil = PerfilCliente(cliente_data)
    planificador = NewPlanificadorHelms(perfil)
    return planificador.generar_plan_anual()

def seleccionar_ejercicios_inteligente(grupo_muscular: str, nivel_experiencia: str,
                                       preferidos: List[str] = None, evitados: List[str] = None) -> List[str]:
    """Wrapper para la función legacy de selección."""
    # Nota: La nueva implementación es más compleja y requiere fase.
    # Este wrapper simplifica para mantener compatibilidad básica.
    ejercicios = SelectorEjercicios.seleccionar_ejercicios_para_bloque(1, "hipertrofia", set(evitados or []))
    grupo_ej = ejercicios.get(grupo_muscular, [])
    return [e['nombre'] for e in grupo_ej]

# Exportar variables globales legacy por si se usaban directamente
# NOTA: Solo se exportan las más críticas.
__all__ = [
    'PlanificadorHelms', 
    'PerfilCliente', 
    'NivelExperiencia',
    'ObjetivoEntrenamiento',
    'GrupoMuscular',
    'CalculadoraVolumen', 
    'OptimizadorRecuperacion',
    'EJERCICIOS_DATABASE',
    'generar_plan_helms',
    'calcular_volumen_optimo',
    'optimizar_recuperacion',
    'seleccionar_ejercicios_inteligente',
    'crear_perfil_desde_cliente'
]
