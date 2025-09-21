# vendor/convertidor_formatos.py
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class ConvertidorFormatos:
    """
    Convierte entre formato Helms y formato actual
    Mantiene compatibilidad bidireccional
    """

    def __init__(self):
        # Mapeo de grupos musculares
        self.mapeo_grupos = {
            'pecho': 'chest',
            'espalda': 'back',
            'hombros': 'shoulders',
            'biceps': 'biceps',
            'triceps': 'triceps',
            'cuadriceps': 'quads',
            'isquios': 'hamstrings',
            'gluteos': 'glutes',
            'gemelos': 'calves'
        }

        # Mapeo inverso
        self.mapeo_grupos_inv = {v: k for k, v in self.mapeo_grupos.items()}

        # Mapeo de tipos de ejercicio
        self.mapeo_tipos = {
            'compuesto': 'compound',
            'aislamiento': 'isolation',
            'accesorio': 'accessory'
        }

        # Descripciones de RPE para educación
        self.descripciones_rpe = {
            6: "Muy fácil - Podrías hacer muchas repeticiones más",
            7: "Moderado - Podrías hacer 3-4 repeticiones más",
            8: "Intenso - Podrías hacer 2-3 repeticiones más",
            9: "Muy intenso - Podrías hacer 1-2 repeticiones más",
            10: "Máximo esfuerzo - Al fallo muscular"
        }

    def helms_a_formato_actual(self, plan_helms: Dict) -> Dict:
        """
        Convierte plan de Helms a tu formato actual
        Preserva toda la funcionalidad existente
        """
        plan_convertido = {
            # Estructura base de tu formato
            'id': plan_helms.get('id', f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            'cliente_id': plan_helms.get('cliente_id'),
            'fecha_creacion': plan_helms.get('fecha_creacion', datetime.now().isoformat()),
            'duracion_semanas': plan_helms.get('duracion_total_semanas', 52),
            'objetivo': self._convertir_objetivo_helms(plan_helms.get('objetivo', 'hipertrofia')),
            'nivel_experiencia': plan_helms.get('nivel_experiencia', 'intermedio'),

            # Tu estructura existente
            'fases': self._convertir_fases_helms(plan_helms.get('fases', [])),
            'ejercicios_por_semana': self._convertir_ejercicios_helms(plan_helms.get('ejercicios_por_semana', {})),
            'progresion': self._convertir_progresion_helms(plan_helms.get('progresion', {})),

            # Nuevos campos de Helms integrados
            'datos_helms': {
                'rpe_por_ejercicio': self._extraer_rpe_ejercicios(plan_helms),
                'tiempos_descanso': self._extraer_tiempos_descanso(plan_helms),
                'tempo_por_ejercicio': self._extraer_tempo_ejercicios(plan_helms),
                'volumen_semanal': self._extraer_volumen_semanal(plan_helms),
                'intensidad_promedio': self._calcular_intensidad_promedio(plan_helms),
                'factor_adherencia': plan_helms.get('adherencia_score', 0),
                'recomendaciones_educativas': self._generar_recomendaciones_educativas(plan_helms)
            },

            # Metadatos de conversión
            'metadata': {
                'generado_por': 'helms',
                'version_helms': plan_helms.get('version', '1.0'),
                'fecha_conversion': datetime.now().isoformat(),
                'formato_origen': 'helms',
                'formato_destino': 'actual',
                'adherencia_score': plan_helms.get('adherencia_score', 0)
            }
        }

        return plan_convertido

    def formato_actual_a_helms(self, plan_actual: Dict) -> Dict:
        """
        Convierte tu formato actual a formato Helms
        Para validación y mejoras
        """
        plan_helms = {
            'cliente_id': plan_actual.get('cliente_id'),
            'objetivo': self._convertir_objetivo_actual(plan_actual.get('objetivo', 'hipertrofia')),
            'nivel_experiencia': plan_actual.get('nivel_experiencia', 'intermedio'),
            'duracion_total_semanas': plan_actual.get('duracion_semanas', 52),

            # Convertir estructura
            'fases': self._convertir_fases_actual(plan_actual.get('fases', [])),
            'ejercicios_por_semana': self._convertir_ejercicios_actual(plan_actual.get('ejercicios_por_semana', {})),
            'progresion': self._convertir_progresion_actual(plan_actual.get('progresion', {})),

            # Metadatos
            'metadata': {
                'formato_origen': 'actual',
                'formato_destino': 'helms',
                'fecha_conversion': datetime.now().isoformat(),
                'requiere_validacion': True
            }
        }

        return plan_helms

    def _convertir_fases_helms(self, fases_helms: List[Dict]) -> List[Dict]:
        """Convierte fases de Helms a tu formato"""
        fases_convertidas = []

        for fase in fases_helms:
            fase_convertida = {
                # Tu formato existente
                'nombre': fase.get('nombre', 'Fase'),
                'duracion_semanas': fase.get('duracion', 4),
                'enfoque': fase.get('enfoque', 'general'),
                'descripcion': fase.get('descripcion', ''),
                'orden': fase.get('orden', len(fases_convertidas) + 1),

                # Información adicional de Helms
                'volumen_objetivo': fase.get('volumen_objetivo', {}),
                'intensidad_rango': fase.get('intensidad_rango', {}),
                'rpe_objetivo': fase.get('rpe_objetivo', {}),
                'frecuencia_grupos': fase.get('frecuencia_grupos', {}),
                'tipo_periodizacion': fase.get('tipo_periodizacion', 'lineal'),

                # Educación para el usuario
                'explicacion_cientifica': self._generar_explicacion_fase(fase),
                'beneficios_esperados': self._generar_beneficios_fase(fase)
            }

            fases_convertidas.append(fase_convertida)

        return fases_convertidas

    def _convertir_ejercicios_helms(self, ejercicios_helms: Dict) -> Dict:
        """Convierte ejercicios de Helms a tu formato"""
        ejercicios_convertidos = {}

        for semana, ejercicios in ejercicios_helms.items():
            ejercicios_semana = []

            for ejercicio in ejercicios:
                ejercicio_convertido = {
                    # Tu formato base
                    'id': ejercicio.get('id', f"ej_{len(ejercicios_semana)}"),
                    'nombre': ejercicio.get('nombre', ''),
                    'series': ejercicio.get('series', 3),
                    'repeticiones': ejercicio.get('repeticiones', '8-12'),
                    'peso_kg': ejercicio.get('peso_kg', 0),
                    'porcentaje_1rm': ejercicio.get('porcentaje_1rm', 0),
                    'grupo_muscular': self.mapeo_grupos_inv.get(
                        ejercicio.get('grupo_muscular', ''),
                        ejercicio.get('grupo_muscular', 'general')
                    ),
                    'tipo_ejercicio': self.mapeo_tipos.get(
                        ejercicio.get('tipo', ''),
                        ejercicio.get('tipo', 'compuesto')
                    ),
                    'orden_ejecucion': ejercicio.get('orden', len(ejercicios_semana) + 1),

                    # Campos específicos de Helms
                    'rpe_objetivo': ejercicio.get('rpe_objetivo', 8),
                    'rpe_descripcion': self.descripciones_rpe.get(
                        int(ejercicio.get('rpe_objetivo', 8)),
                        "Intensidad moderada"
                    ),
                    'descanso_minutos': ejercicio.get('descanso_minutos', 3),
                    'tempo': ejercicio.get('tempo', '2-0-X-0'),
                    'notas_tecnicas': ejercicio.get('notas_tecnicas', ''),
                    'prioridad': ejercicio.get('prioridad', 'media'),

                    # Flags de identificación
                    'es_ejercicio_helms': True,
                    'requiere_educacion': ejercicio.get('requiere_educacion', False),
                    'es_ejercicio_principal': ejercicio.get('es_principal', False),

                    # Información educativa
                    'beneficios': ejercicio.get('beneficios', []),
                    'consejos_ejecucion': ejercicio.get('consejos_ejecucion', []),
                    'variaciones': ejercicio.get('variaciones', [])
                }

                ejercicios_semana.append(ejercicio_convertido)

            ejercicios_convertidos[semana] = ejercicios_semana

        return ejercicios_convertidos

    def _convertir_progresion_helms(self, progresion_helms: Dict) -> Dict:
        """Convierte progresión de Helms a tu formato"""
        return {
            # Tu formato existente
            'tipo': progresion_helms.get('tipo', 'lineal'),
            'incremento_peso': progresion_helms.get('incremento_peso', 2.5),
            'incremento_volumen': progresion_helms.get('incremento_volumen', 1),
            'frecuencia_evaluacion': progresion_helms.get('frecuencia_evaluacion', 2),

            # Información adicional de Helms
            'criterios_progresion': progresion_helms.get('criterios', []),
            'indicadores_descarga': progresion_helms.get('indicadores_descarga', []),
            'autoregulacion_activa': progresion_helms.get('autoregulacion', True),
            'metodo_periodizacion': progresion_helms.get('metodo', 'lineal'),

            # Educación sobre progresión
            'explicacion_metodo': self._generar_explicacion_progresion(progresion_helms),
            'señales_sobreentrenamiento': [
                'Disminución del rendimiento',
                'Fatiga persistente',
                'Pérdida de motivación',
                'Alteraciones del sueño'
            ]
        }

    def _extraer_rpe_ejercicios(self, plan_helms: Dict) -> Dict:
        """Extrae información de RPE por ejercicio"""
        rpe_ejercicios = {}

        for semana, ejercicios in plan_helms.get('ejercicios_por_semana', {}).items():
            for ejercicio in ejercicios:
                nombre = ejercicio.get('nombre', '')
                if nombre:
                    rpe_ejercicios[nombre] = {
                        'rpe_objetivo': ejercicio.get('rpe_objetivo', 8),
                        'descripcion': self.descripciones_rpe.get(
                            int(ejercicio.get('rpe_objetivo', 8)),
                            "Intensidad moderada"
                        ),
                        'rango_permitido': [
                            ejercicio.get('rpe_objetivo', 8) - 1,
                            ejercicio.get('rpe_objetivo', 8) + 1
                        ]
                    }

        return rpe_ejercicios

    def _extraer_tiempos_descanso(self, plan_helms: Dict) -> Dict:
        """Extrae tiempos de descanso por tipo de ejercicio"""
        tiempos_descanso = {}

        for semana, ejercicios in plan_helms.get('ejercicios_por_semana', {}).items():
            for ejercicio in ejercicios:
                tipo = ejercicio.get('tipo', 'compuesto')
                if tipo not in tiempos_descanso:
                    tiempos_descanso[tipo] = {
                        'minimo': ejercicio.get('descanso_minutos', 3),
                        'recomendado': ejercicio.get('descanso_minutos', 3),
                        'maximo': ejercicio.get('descanso_minutos', 3) + 1
                    }

        return tiempos_descanso

    def _extraer_tempo_ejercicios(self, plan_helms: Dict) -> Dict:
        """Extrae información de tempo por ejercicio"""
        tempo_ejercicios = {}

        for semana, ejercicios in plan_helms.get('ejercicios_por_semana', {}).items():
            for ejercicio in ejercicios:
                nombre = ejercicio.get('nombre', '')
                if nombre:
                    tempo_ejercicios[nombre] = {
                        'tempo': ejercicio.get('tempo', '2-0-X-0'),
                        'explicacion': self._explicar_tempo(ejercicio.get('tempo', '2-0-X-0')),
                        'objetivo': self._objetivo_tempo(ejercicio.get('tempo', '2-0-X-0'))
                    }

        return tempo_ejercicios

    def _extraer_volumen_semanal(self, plan_helms: Dict) -> Dict:
        """Calcula volumen semanal por grupo muscular"""
        volumen_semanal = {}

        # Inicializar contadores
        for grupo in self.mapeo_grupos.keys():
            volumen_semanal[grupo] = 0

        # Contar series por grupo muscular
        for semana, ejercicios in plan_helms.get('ejercicios_por_semana', {}).items():
            for ejercicio in ejercicios:
                grupo = self.mapeo_grupos_inv.get(
                    ejercicio.get('grupo_muscular', ''),
                    'general'
                )
                if grupo in volumen_semanal:
                    volumen_semanal[grupo] += ejercicio.get('series', 0)

        return volumen_semanal

    def _calcular_intensidad_promedio(self, plan_helms: Dict) -> Dict:
        """Calcula intensidad promedio por semana"""
        intensidad_promedio = {}

        for semana, ejercicios in plan_helms.get('ejercicios_por_semana', {}).items():
            intensidades = [
                ejercicio.get('porcentaje_1rm', 0)
                for ejercicio in ejercicios
                if ejercicio.get('porcentaje_1rm', 0) > 0
            ]

            if intensidades:
                intensidad_promedio[semana] = {
                    'promedio': sum(intensidades) / len(intensidades),
                    'minima': min(intensidades),
                    'maxima': max(intensidades),
                    'rpe_promedio': sum([
                        ejercicio.get('rpe_objetivo', 8)
                        for ejercicio in ejercicios
                    ]) / len(ejercicios) if ejercicios else 8
                }

        return intensidad_promedio

    def _generar_recomendaciones_educativas(self, plan_helms: Dict) -> List[Dict]:
        """Genera recomendaciones educativas basadas en el plan"""
        recomendaciones = []

        # Recomendación sobre RPE
        recomendaciones.append({
            'tipo': 'rpe',
            'titulo': 'Uso del RPE (Rate of Perceived Exertion)',
            'descripcion': 'El RPE te ayuda a entrenar con la intensidad correcta sin depender solo del peso.',
            'consejos': [
                'Aprende a identificar cada nivel de RPE',
                'Usa RPE 7-8 para hipertrofia',
                'Usa RPE 8-9 para fuerza',
                'Ajusta el peso según tu RPE del día'
            ]
        })

        # Recomendación sobre adherencia
        adherencia_score = plan_helms.get('adherencia_score', 0)
        if adherencia_score < 7:
            recomendaciones.append({
                'tipo': 'adherencia',
                'titulo': 'Mejora tu Adherencia',
                'descripcion': 'Tu score de adherencia puede mejorar con pequeños ajustes.',
                'consejos': [
                    'Reduce días de entrenamiento si es necesario',
                    'Incluye más ejercicios que disfrutes',
                    'Ajusta el tiempo por sesión a tu realidad',
                    'Mantén flexibilidad en tu horario'
                ]
            })

        # Recomendación sobre progresión
        recomendaciones.append({
            'tipo': 'progresion',
            'titulo': 'Progresión Inteligente',
            'descripcion': 'La progresión debe ser gradual y sostenible.',
            'consejos': [
                'Aumenta peso solo cuando puedas hacer todas las repeticiones en RPE objetivo',
                'Si no puedes progresar, revisa tu recuperación',
                'Considera semanas de descarga cada 4-6 semanas',
                'Escucha a tu cuerpo y ajusta según sea necesario'
            ]
        })

        return recomendaciones

    def _generar_explicacion_fase(self, fase: Dict) -> str:
        """Genera explicación científica de la fase"""
        enfoque = fase.get('enfoque', 'general')

        explicaciones = {
            'acumulacion': 'Fase de acumulación de volumen para crear adaptaciones musculares',
            'intensificacion': 'Fase de intensificación para mejorar la fuerza y potencia',
            'descarga': 'Fase de descarga para permitir recuperación y supercompensación',
            'hipertrofia': 'Fase enfocada en maximizar el crecimiento muscular',
            'fuerza': 'Fase enfocada en desarrollar fuerza máxima'
        }

        return explicaciones.get(enfoque, 'Fase de entrenamiento general')

    def _generar_beneficios_fase(self, fase: Dict) -> List[str]:
        """Genera lista de beneficios esperados de la fase"""
        enfoque = fase.get('enfoque', 'general')

        beneficios = {
            'acumulacion': [
                'Aumento del volumen muscular',
                'Mejora de la capacidad de trabajo',
                'Adaptaciones metabólicas',
                'Preparación para fases intensas'
            ],
            'intensificacion': [
                'Aumento de la fuerza máxima',
                'Mejora de la coordinación neuromuscular',
                'Optimización del rendimiento',
                'Preparación para competencias'
            ],
            'descarga': [
                'Recuperación completa',
                'Reducción de fatiga acumulada',
                'Supercompensación',
                'Preparación mental'
            ]
        }

        return beneficios.get(enfoque, ['Mejora general del rendimiento'])

    def _explicar_tempo(self, tempo: str) -> str:
        """Explica qué significa un tempo específico"""
        if tempo == '2-0-X-0':
            return '2 segundos bajada, sin pausa, explosiva subida, sin pausa'
        elif tempo == '3-1-1-1':
            return '3 segundos bajada, 1 segundo pausa, 1 segundo subida, 1 segundo pausa'
        elif tempo == '1-0-X-0':
            return '1 segundo bajada, sin pausa, explosiva subida, sin pausa'
        else:
            return f'Tempo personalizado: {tempo}'

    def _objetivo_tempo(self, tempo: str) -> str:
        """Explica el objetivo de un tempo específico"""
        if 'X' in tempo:
            return 'Desarrollo de potencia y fuerza'
        elif '3' in tempo.split('-')[0]:
            return 'Control y hipertrofia'
        else:
            return 'Tempo natural'

    def validar_conversion(self, plan_original: Dict, plan_convertido: Dict) -> Dict:
        """
        Valida que la conversión mantenga la información esencial
        """
        validacion = {
            'exitosa': True,
            'errores': [],
            'advertencias': [],
            'metricas': {}
        }

        # Validar campos esenciales
        campos_esenciales = ['cliente_id', 'objetivo', 'ejercicios_por_semana']
        for campo in campos_esenciales:
            if campo not in plan_convertido:
                validacion['errores'].append(f'Campo esencial faltante: {campo}')
                validacion['exitosa'] = False

        # Validar ejercicios
        ejercicios_original = len(plan_original.get('ejercicios_por_semana', {}).get('1', []))
        ejercicios_convertido = len(plan_convertido.get('ejercicios_por_semana', {}).get('1', []))

        if ejercicios_original != ejercicios_convertido:
            validacion['advertencias'].append(
                f'Diferencia en número de ejercicios: {ejercicios_original} vs {ejercicios_convertido}'
            )

        # Métricas de conversión
        validacion['metricas'] = {
            'ejercicios_originales': ejercicios_original,
            'ejercicios_convertidos': ejercicios_convertido,
            'campos_helms_añadidos': len(plan_convertido.get('datos_helms', {})),
            'tiene_rpe': bool(plan_convertido.get('datos_helms', {}).get('rpe_por_ejercicio')),
            'tiene_tempo': bool(plan_convertido.get('datos_helms', {}).get('tempo_por_ejercicio'))
        }

        return validacion


# Funciones de utilidad para usar en views
def convertir_plan_para_vista(plan_helms: Dict) -> Dict:
    """Función de conveniencia para convertir en views"""
    convertidor = ConvertidorFormatos()
    plan_convertido = convertidor.helms_a_formato_actual(plan_helms)
    validacion = convertidor.validar_conversion(plan_helms, plan_convertido)

    return {
        'plan': plan_convertido,
        'validacion': validacion
    }


def extraer_datos_educativos(plan_convertido: Dict) -> Dict:
    """Extrae datos educativos para mostrar en templates"""
    datos_helms = plan_convertido.get('datos_helms', {})

    return {
        'info_rpe': {
            6: "Muy fácil - Podrías hacer muchas repeticiones más",
            7: "Moderado - Podrías hacer 3-4 repeticiones más",
            8: "Intenso - Podrías hacer 2-3 repeticiones más",
            9: "Muy intenso - Podrías hacer 1-2 repeticiones más",
            10: "Máximo esfuerzo - Al fallo muscular"
        },
        'info_tempo': {
            'descripcion': 'Formato: Excéntrica-Pausa-Concéntrica-Pausa',
            'ejemplo': '2-0-X-0 = 2 seg bajada, sin pausa, explosiva subida, sin pausa'
        },
        'recomendaciones': datos_helms.get('recomendaciones_educativas', []),
        'volumen_total': sum(datos_helms.get('volumen_semanal', {}).values()),
        'intensidad_promedio': datos_helms.get('intensidad_promedio', {})
    }
