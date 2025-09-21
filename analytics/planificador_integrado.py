# analytics/planificador_integrado.py
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

# Importar tu planificador actual
from .planificador import PlanificadorAnualIA

# Importar el planificador Helms
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'helms'))
from .planificador_helms_completo import (
    PlanificadorHelms,
    PerfilCliente,
    NivelExperiencia,
    ObjetivoEntrenamiento,
    GrupoMuscular
)


class PlanificadorIntegrado:
    """
    Integra tu PlanificadorAnualIA existente con el PlanificadorHelms
    Mantiene compatibilidad total con tu código actual
    """

    def __init__(self, cliente_id: int):
        self.cliente_id = cliente_id
        self.cliente = self._obtener_cliente(cliente_id)

        # Inicializar ambos planificadores
        self.planificador_actual = PlanificadorAnualIA(cliente_id)
        self.planificador_helms = self._crear_planificador_helms()

        # Configuración de integración
        self.usar_helms_como_principal = True  # Cambiar a False para usar como validador
        self.incluir_validacion_helms = True

    def _obtener_cliente(self, cliente_id: int):
        """Obtiene el cliente desde tu modelo actual"""
        from clientes.models import Cliente  # Ajustar import según tu estructura
        return Cliente.objects.get(id=cliente_id)

    def _crear_planificador_helms(self) -> PlanificadorHelms:
        """Crea el perfil Helms desde tu modelo Cliente"""

        # Mapear nivel de experiencia
        if self.cliente.experiencia_años < 1:
            nivel_exp = NivelExperiencia.PRINCIPIANTE
        elif self.cliente.experiencia_años < 3:
            nivel_exp = NivelExperiencia.INTERMEDIO
        else:
            nivel_exp = NivelExperiencia.AVANZADO

        # Mapear objetivo
        objetivo_map = {
            'hipertrofia': ObjetivoEntrenamiento.HIPERTROFIA,
            'fuerza': ObjetivoEntrenamiento.FUERZA,
            'potencia': ObjetivoEntrenamiento.POTENCIA
        }
        objetivo = objetivo_map.get(self.cliente.objetivo_principal, ObjetivoEntrenamiento.HIPERTROFIA)

        # Crear perfil Helms
        perfil_helms = PerfilCliente(
            cliente_id=self.cliente.id,
            experiencia_años=self.cliente.experiencia_años,
            objetivo_principal=objetivo,

            # Datos de adherencia (nuevos campos)
            dias_disponibles=getattr(self.cliente, 'dias_disponibles', 4),
            tiempo_por_sesion=getattr(self.cliente, 'tiempo_por_sesion', 90),
            ejercicios_preferidos=getattr(self.cliente, 'ejercicios_preferidos', []),
            ejercicios_evitar=getattr(self.cliente, 'ejercicios_evitar', []),
            flexibilidad_horario=getattr(self.cliente, 'flexibilidad_horario', True),

            # Datos técnicos
            one_rm_data=getattr(self.cliente, 'one_rm_data', {}),
            historial_volumen=getattr(self.cliente, 'historial_volumen', {}),

            # Autorregulación
            nivel_estres=getattr(self.cliente, 'nivel_estres', 5),
            calidad_sueño=getattr(self.cliente, 'calidad_sueño', 7),
            nivel_energia=getattr(self.cliente, 'nivel_energia', 7)
        )

        return PlanificadorHelms(perfil_helms)

    def generar_plan_anual(self) -> Dict:
        """
        Genera el plan anual usando la estrategia configurada
        """
        if self.usar_helms_como_principal:
            return self._generar_con_helms_principal()
        else:
            return self._generar_con_validacion_helms()

    def _generar_con_helms_principal(self) -> Dict:
        """
        Usa PlanificadorHelms como generador principal
        Fallback a tu planificador si hay problemas
        """
        try:
            # Generar plan con Helms
            plan_helms = self.planificador_helms.generar_plan_completo()

            if plan_helms['status'] == 'success':
                # Convertir formato Helms a tu formato
                plan_convertido = self._convertir_helms_a_formato_actual(plan_helms)

                # Añadir metadatos de integración
                plan_convertido['metadata'] = {
                    'generado_por': 'helms',
                    'version_helms': '1.0',
                    'fecha_generacion': datetime.now().isoformat(),
                    'adherencia_score': plan_helms.get('adherencia_score', 0),
                    'factor_recuperacion': self.cliente.get_factor_recuperacion()
                }

                return plan_convertido
            else:
                # Fallback a tu planificador actual
                print(f"⚠️ Helms falló: {plan_helms.get('error', 'Error desconocido')}")
                return self._generar_fallback()

        except Exception as e:
            print(f"❌ Error en PlanificadorHelms: {str(e)}")
            return self._generar_fallback()

    def _generar_con_validacion_helms(self) -> Dict:
        """
        Usa tu planificador actual como principal
        Helms como validador y mejorador
        """
        # Generar plan con tu sistema actual
        plan_actual = self.planificador_actual.generar_plan()

        if self.incluir_validacion_helms:
            try:
                # Validar con Helms
                validacion = self.planificador_helms.validar_plan_existente(plan_actual)

                # Aplicar mejoras sugeridas
                plan_mejorado = self._aplicar_mejoras_helms(plan_actual, validacion)

                # Añadir información de validación
                plan_mejorado['validacion_helms'] = {
                    'score_adherencia': validacion.get('score_adherencia', 0),
                    'mejoras_aplicadas': validacion.get('mejoras_aplicadas', []),
                    'advertencias': validacion.get('advertencias', [])
                }

                return plan_mejorado

            except Exception as e:
                print(f"⚠️ Error en validación Helms: {str(e)}")
                return plan_actual

        return plan_actual

    def _generar_fallback(self) -> Dict:
        """Genera plan con tu sistema actual como fallback"""
        plan = self.planificador_actual.generar_plan()
        plan['metadata'] = {
            'generado_por': 'fallback',
            'razon_fallback': 'Error en PlanificadorHelms',
            'fecha_generacion': datetime.now().isoformat()
        }
        return plan

    def _convertir_helms_a_formato_actual(self, plan_helms: Dict) -> Dict:
        """
        Convierte el formato de salida de Helms a tu formato actual
        Preserva toda la funcionalidad existente
        """
        plan_convertido = {
            'cliente_id': self.cliente_id,
            'fecha_creacion': datetime.now().isoformat(),
            'duracion_semanas': plan_helms.get('duracion_total_semanas', 52),
            'objetivo': self.cliente.objetivo_principal,
            'nivel_experiencia': self.cliente.get_nivel_experiencia(),

            # Estructura de tu formato actual
            'fases': [],
            'ejercicios_por_semana': {},
            'progresion': {},

            # Nuevos campos de Helms
            'datos_helms': {
                'rpe_por_ejercicio': {},
                'tiempos_descanso': {},
                'tempo_por_ejercicio': {},
                'volumen_semanal': {},
                'intensidad_promedio': {}
            }
        }

        # Convertir cada fase del plan Helms
        for fase_helms in plan_helms.get('fases', []):
            fase_convertida = self._convertir_fase_helms(fase_helms)
            plan_convertido['fases'].append(fase_convertida)

        # Convertir ejercicios semanales
        for semana, ejercicios in plan_helms.get('ejercicios_por_semana', {}).items():
            plan_convertido['ejercicios_por_semana'][semana] = self._convertir_ejercicios_semana(ejercicios)

        return plan_convertido

    def _convertir_fase_helms(self, fase_helms: Dict) -> Dict:
        """Convierte una fase de Helms a tu formato"""
        return {
            'nombre': fase_helms.get('nombre', 'Fase'),
            'duracion_semanas': fase_helms.get('duracion', 4),
            'enfoque': fase_helms.get('enfoque', 'general'),
            'descripcion': fase_helms.get('descripcion', ''),

            # Datos específicos de Helms
            'volumen_objetivo': fase_helms.get('volumen_objetivo', {}),
            'intensidad_rango': fase_helms.get('intensidad_rango', {}),
            'rpe_objetivo': fase_helms.get('rpe_objetivo', {}),
            'frecuencia_grupos': fase_helms.get('frecuencia_grupos', {})
        }

    def _convertir_ejercicios_semana(self, ejercicios_helms: List[Dict]) -> List[Dict]:
        """Convierte ejercicios de una semana de Helms a tu formato"""
        ejercicios_convertidos = []

        for ejercicio_helms in ejercicios_helms:
            ejercicio_convertido = {
                # Tu formato actual
                'nombre': ejercicio_helms.get('nombre', ''),
                'series': ejercicio_helms.get('series', 3),
                'repeticiones': ejercicio_helms.get('repeticiones', '8-12'),
                'peso_kg': ejercicio_helms.get('peso_kg', 0),
                'porcentaje_1rm': ejercicio_helms.get('porcentaje_1rm', 0),
                'grupo_muscular': ejercicio_helms.get('grupo_muscular', ''),
                'tipo_ejercicio': ejercicio_helms.get('tipo', 'compuesto'),

                # Nuevos campos de Helms
                'rpe_objetivo': ejercicio_helms.get('rpe_objetivo', 8),
                'rpe_descripcion': self._obtener_descripcion_rpe(ejercicio_helms.get('rpe_objetivo', 8)),
                'descanso_minutos': ejercicio_helms.get('descanso_minutos', 3),
                'tempo': ejercicio_helms.get('tempo', '2-0-X-0'),
                'notas_tecnicas': ejercicio_helms.get('notas_tecnicas', ''),

                # Metadatos
                'es_ejercicio_helms': True,
                'prioridad': ejercicio_helms.get('prioridad', 'media')
            }

            ejercicios_convertidos.append(ejercicio_convertido)

        return ejercicios_convertidos

    def _obtener_descripcion_rpe(self, rpe: float) -> str:
        """Obtiene descripción educativa del RPE"""
        descripciones = {
            6: "Muy fácil - Podrías hacer muchas repeticiones más",
            7: "Moderado - Podrías hacer 3-4 repeticiones más",
            8: "Intenso - Podrías hacer 2-3 repeticiones más",
            9: "Muy intenso - Podrías hacer 1-2 repeticiones más",
            10: "Máximo esfuerzo - Al fallo muscular"
        }
        return descripciones.get(int(rpe), "Intensidad moderada")

    def _aplicar_mejoras_helms(self, plan_actual: Dict, validacion: Dict) -> Dict:
        """Aplica mejoras sugeridas por Helms a tu plan actual"""
        plan_mejorado = plan_actual.copy()

        mejoras = validacion.get('mejoras_sugeridas', [])

        for mejora in mejoras:
            tipo_mejora = mejora.get('tipo')

            if tipo_mejora == 'ajustar_volumen':
                self._aplicar_mejora_volumen(plan_mejorado, mejora)
            elif tipo_mejora == 'ajustar_intensidad':
                self._aplicar_mejora_intensidad(plan_mejorado, mejora)
            elif tipo_mejora == 'añadir_rpe':
                self._aplicar_mejora_rpe(plan_mejorado, mejora)
            elif tipo_mejora == 'optimizar_descansos':
                self._aplicar_mejora_descansos(plan_mejorado, mejora)

        return plan_mejorado

    def _aplicar_mejora_volumen(self, plan: Dict, mejora: Dict):
        """Aplica mejoras de volumen según Helms"""
        grupo_muscular = mejora.get('grupo_muscular')
        nuevo_volumen = mejora.get('volumen_sugerido')

        # Ajustar volumen en el plan
        if 'datos_helms' not in plan:
            plan['datos_helms'] = {}

        if 'volumen_semanal' not in plan['datos_helms']:
            plan['datos_helms']['volumen_semanal'] = {}

        plan['datos_helms']['volumen_semanal'][grupo_muscular] = nuevo_volumen

    def _aplicar_mejora_intensidad(self, plan: Dict, mejora: Dict):
        """Aplica mejoras de intensidad según Helms"""
        ejercicio = mejora.get('ejercicio')
        nueva_intensidad = mejora.get('intensidad_sugerida')

        # Buscar y actualizar ejercicio en el plan
        for semana, ejercicios in plan.get('ejercicios_por_semana', {}).items():
            for ejercicio_data in ejercicios:
                if ejercicio_data.get('nombre') == ejercicio:
                    ejercicio_data['porcentaje_1rm'] = nueva_intensidad

    def _aplicar_mejora_rpe(self, plan: Dict, mejora: Dict):
        """Añade información de RPE a ejercicios"""
        if 'datos_helms' not in plan:
            plan['datos_helms'] = {}

        plan['datos_helms']['rpe_por_ejercicio'] = mejora.get('rpe_sugerido', {})

    def _aplicar_mejora_descansos(self, plan: Dict, mejora: Dict):
        """Optimiza tiempos de descanso según Helms"""
        if 'datos_helms' not in plan:
            plan['datos_helms'] = {}

        plan['datos_helms']['tiempos_descanso'] = mejora.get('descansos_sugeridos', {})

    def obtener_estadisticas_integracion(self) -> Dict:
        """Obtiene estadísticas sobre la integración Helms"""
        return {
            'cliente_id': self.cliente_id,
            'nivel_experiencia': self.cliente.get_nivel_experiencia(),
            'factor_recuperacion': self.cliente.get_factor_recuperacion(),
            'necesita_descarga': self.cliente.necesita_descarga(),
            'dias_disponibles': self.cliente.dias_disponibles,
            'tiempo_semanal_total': self.cliente.dias_disponibles * self.cliente.tiempo_por_sesion,
            'ejercicios_preferidos_count': len(self.cliente.ejercicios_preferidos),
            'ejercicios_evitar_count': len(self.cliente.ejercicios_evitar),
            'planificador_principal': 'helms' if self.usar_helms_como_principal else 'actual',
            'validacion_helms_activa': self.incluir_validacion_helms
        }
