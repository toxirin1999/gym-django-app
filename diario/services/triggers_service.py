# diario/services/triggers_service.py

from collections import Counter
from django.db.models import Count, Avg
from ..models import TriggerHabito


class TriggersService:
    """Servicio para análisis de patrones de recaída en hábitos negativos"""
    
    @staticmethod
    def analizar_patrones_recaida(habito):
        """
        Analiza los patrones de recaída de un hábito negativo.
        Retorna un diccionario con insights sobre triggers comunes.
        """
        triggers = habito.triggers.all()
        
        if not triggers.exists():
            return {
                'tiene_datos': False,
                'mensaje': 'Aún no hay registros de impulsos para analizar.'
            }
        
        total_triggers = triggers.count()
        recaidas = triggers.filter(cediste=True)
        resistidos = triggers.filter(cediste=False)
        
        # Análisis de emociones
        emociones_recaida = list(recaidas.values_list('emocion_previa', flat=True))
        emociones_resistido = list(resistidos.values_list('emocion_previa', flat=True))
        
        emocion_mas_peligrosa = None
        if emociones_recaida:
            counter = Counter(emociones_recaida)
            emocion_mas_peligrosa = counter.most_common(1)[0]
        
        emocion_mas_fuerte = None
        if emociones_resistido:
            counter = Counter(emociones_resistido)
            emocion_mas_fuerte = counter.most_common(1)[0]
        
        # Análisis de horarios
        horas_recaida = [t.hora.hour for t in recaidas if t.hora]
        hora_mas_peligrosa = None
        if horas_recaida:
            counter = Counter(horas_recaida)
            hora_mas_peligrosa = counter.most_common(1)[0]
        
        # Intensidad promedio
        intensidad_promedio_recaida = recaidas.aggregate(
            promedio=Avg('intensidad_deseo')
        )['promedio'] or 0
        
        intensidad_promedio_resistido = resistidos.aggregate(
            promedio=Avg('intensidad_deseo')
        )['promedio'] or 0
        
        # Tasa de éxito
        tasa_exito = (resistidos.count() / total_triggers * 100) if total_triggers > 0 else 0
        
        return {
            'tiene_datos': True,
            'total_impulsos': total_triggers,
            'recaidas': recaidas.count(),
            'resistidos': resistidos.count(),
            'tasa_exito': round(tasa_exito, 1),
            'emocion_mas_peligrosa': emocion_mas_peligrosa,
            'emocion_mas_fuerte': emocion_mas_fuerte,
            'hora_mas_peligrosa': hora_mas_peligrosa,
            'intensidad_promedio_recaida': round(intensidad_promedio_recaida, 1),
            'intensidad_promedio_resistido': round(intensidad_promedio_resistido, 1),
        }
    
    @staticmethod
    def obtener_estrategias_exitosas(habito):
        """
        Obtiene las estrategias que han funcionado para resistir impulsos.
        """
        triggers_resistidos = habito.triggers.filter(
            cediste=False,
            estrategia_usada__isnull=False
        ).exclude(estrategia_usada='')
        
        estrategias = []
        for trigger in triggers_resistidos:
            estrategias.append({
                'fecha': trigger.fecha,
                'estrategia': trigger.estrategia,
                'intensidad': trigger.intensidad_deseo,
                'emocion': trigger.get_emocion_previa_display()
            })
        
        return estrategias
    
    @staticmethod
    def generar_recomendaciones(analisis):
        """
        Genera recomendaciones basadas en el análisis de patrones.
        """
        if not analisis['tiene_datos']:
            return []
        
        recomendaciones = []
        
        # Recomendación por emoción peligrosa
        if analisis['emocion_mas_peligrosa']:
            emocion, veces = analisis['emocion_mas_peligrosa']
            recomendaciones.append({
                'tipo': 'emocion',
                'titulo': f'Cuidado con {emocion}',
                'mensaje': f'Has recaído {veces} veces cuando sientes {emocion}. Prepara una estrategia específica para este estado emocional.',
                'icono': '⚠️'
            })
        
        # Recomendación por hora peligrosa
        if analisis['hora_mas_peligrosa']:
            hora, veces = analisis['hora_mas_peligrosa']
            recomendaciones.append({
                'tipo': 'horario',
                'titulo': f'Zona de peligro: {hora}:00',
                'mensaje': f'Has recaído {veces} veces alrededor de las {hora}:00. Planifica actividades alternativas en este horario.',
                'icono': '🕐'
            })
        
        # Recomendación por tasa de éxito
        if analisis['tasa_exito'] >= 70:
            recomendaciones.append({
                'tipo': 'exito',
                'titulo': '¡Vas muy bien!',
                'mensaje': f'Tienes una tasa de éxito del {analisis["tasa_exito"]}%. Sigue así, estás desarrollando fortaleza.',
                'icono': '💪'
            })
        elif analisis['tasa_exito'] < 30:
            recomendaciones.append({
                'tipo': 'advertencia',
                'titulo': 'Necesitas reforzar',
                'mensaje': f'Tu tasa de éxito es del {analisis["tasa_exito"]}%. Considera revisar tus estrategias o buscar apoyo adicional.',
                'icono': '🆘'
            })
        
        return recomendaciones
