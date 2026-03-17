# diario/services/habitos_service.py

from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q


class HabitosService:
    """Servicio centralizado para lógica de hábitos - Fase 1"""
    
    @staticmethod
    def calcular_progreso(habito):
        """
        Calcula progreso completo del hábito considerando si es positivo o negativo
        """
        dias_completados = habito.get_dias_completados()
        total_dias_trackeados = habito.dias_completados.count()
        porcentaje = habito.get_porcentaje_exito()
        racha = habito.get_racha_actual()
        
        if habito.tipo_habito == 'negativo':
            # Para hábitos a eliminar
            dias_sin_habito = habito.get_dias_sin_habito()
            
            return {
                'tipo': 'eliminacion',
                'dias_sin_habito': dias_sin_habito,
                'dias_recaida': dias_completados,
                'total_dias_trackeados': total_dias_trackeados,
                'porcentaje_exito': porcentaje,
                'racha_actual': racha,
                'mensaje': habito.get_mensaje_progreso(),
                'color': 'success' if porcentaje >= 80 else 'warning' if porcentaje >= 50 else 'danger',
                'icono': '🚫' if dias_sin_habito > 0 else '⚠️'
            }
        else:
            # Para hábitos a formar
            dias_faltantes = habito.objetivo_dias - dias_completados
            
            return {
                'tipo': 'formacion',
                'dias_completados': dias_completados,
                'dias_faltantes': max(0, dias_faltantes),
                'total_dias_trackeados': total_dias_trackeados,
                'porcentaje_exito': porcentaje,
                'racha_actual': racha,
                'mensaje': habito.get_mensaje_progreso(),
                'color': 'success' if porcentaje >= 80 else 'warning' if porcentaje >= 50 else 'danger',
                'icono': '✅' if dias_completados > 0 else '📝'
            }
    
    @staticmethod
    def verificar_milestone(habito):
        """
        Verifica si el hábito ha alcanzado un milestone importante
        Retorna dict con info del milestone o None
        """
        if habito.tipo_habito == 'negativo':
            dias_sin = habito.get_dias_sin_habito()
            
            # Milestones para hábitos a eliminar
            if dias_sin == 1:
                return {
                    'nivel': 'inicio',
                    'titulo': '¡Primer día sin {habito}!',
                    'mensaje': 'El primer paso es el más difícil. ¡Lo lograste!',
                    'icono': '🎯'
                }
            elif dias_sin == 3:
                return {
                    'nivel': 'bronce',
                    'titulo': '3 días de libertad',
                    'mensaje': 'Las primeras 72 horas son críticas. ¡Vas por buen camino!',
                    'icono': '🥉'
                }
            elif dias_sin == 7:
                return {
                    'nivel': 'plata',
                    'titulo': '¡Una semana completa!',
                    'mensaje': 'Has superado la primera semana, la más difícil. Tu cerebro está empezando a cambiar.',
                    'icono': '🥈'
                }
            elif dias_sin == 21:
                return {
                    'nivel': 'oro',
                    'titulo': '21 días de transformación',
                    'mensaje': 'Estás formando nuevos patrones neuronales. El hábito está perdiendo fuerza.',
                    'icono': '🥇'
                }
            elif dias_sin == 30:
                return {
                    'nivel': 'diamante',
                    'titulo': '¡Un mes de victoria!',
                    'mensaje': 'Has completado 30 días. Este es un logro monumental.',
                    'icono': '💎'
                }
            elif dias_sin == 90:
                return {
                    'nivel': 'legendario',
                    'titulo': '90 días - Has roto el hábito',
                    'mensaje': 'Según la ciencia, has superado el período crítico. El hábito ya no tiene poder sobre ti.',
                    'icono': '👑'
                }
        else:
            # Milestones para hábitos a formar
            dias_con = habito.get_dias_completados()
            
            if dias_con == 1:
                return {
                    'nivel': 'inicio',
                    'titulo': '¡Primer día completado!',
                    'mensaje': 'Todo viaje comienza con un solo paso. ¡Excelente comienzo!',
                    'icono': '🎯'
                }
            elif dias_con == 7:
                return {
                    'nivel': 'plata',
                    'titulo': '¡Una semana de constancia!',
                    'mensaje': 'Has demostrado compromiso durante 7 días. El hábito está tomando forma.',
                    'icono': '🥈'
                }
            elif dias_con == 21:
                return {
                    'nivel': 'oro',
                    'titulo': '21 días - El hábito se consolida',
                    'mensaje': 'Tu cerebro está creando nuevas conexiones. El hábito se está volviendo automático.',
                    'icono': '🥇'
                }
            elif dias_con == 30:
                return {
                    'nivel': 'diamante',
                    'titulo': '¡30 días de éxito!',
                    'mensaje': 'Has completado un mes entero. Este hábito es ahora parte de tu vida.',
                    'icono': '💎'
                }
            elif dias_con == 66:
                return {
                    'nivel': 'legendario',
                    'titulo': '66 días - Hábito automático',
                    'mensaje': 'Según estudios, 66 días es el promedio para automatizar un hábito. ¡Lo lograste!',
                    'icono': '👑'
                }
        
        return None
    
    @staticmethod
    def obtener_habitos_por_tipo(prosoche_mes):
        """
        Obtiene hábitos separados por tipo con su progreso
        """
        habitos_positivos = []
        habitos_negativos = []
        
        for habito in prosoche_mes.habitos.all():
            progreso = HabitosService.calcular_progreso(habito)
            milestone = HabitosService.verificar_milestone(habito)
            
            habito_data = {
                'habito': habito,
                'progreso': progreso,
                'milestone': milestone
            }
            
            if habito.tipo_habito == 'negativo':
                habitos_negativos.append(habito_data)
            else:
                habitos_positivos.append(habito_data)
        
        return {
            'positivos': habitos_positivos,
            'negativos': habitos_negativos,
            'total_positivos': len(habitos_positivos),
            'total_negativos': len(habitos_negativos)
        }
    
    @staticmethod
    def generar_insights_basicos(habito):
        """
        Genera insights básicos sobre el hábito
        """
        progreso = HabitosService.calcular_progreso(habito)
        insights = []
        
        if habito.tipo_habito == 'negativo':
            # Insights para hábitos a eliminar
            if progreso['racha_actual'] >= 3:
                insights.append({
                    'tipo': 'motivacion',
                    'mensaje': f"¡Llevas {progreso['racha_actual']} días consecutivos sin {habito.nombre}! Mantén el impulso."
                })
            
            if progreso['dias_recaida'] > 0:
                tasa_recaida = (progreso['dias_recaida'] / progreso['total_dias_trackeados']) * 100
                if tasa_recaida < 20:
                    insights.append({
                        'tipo': 'exito',
                        'mensaje': f"Solo has recaído en el {round(tasa_recaida)}% de los días. ¡Excelente control!"
                    })
        else:
            # Insights para hábitos a formar
            if progreso['racha_actual'] >= 3:
                insights.append({
                    'tipo': 'motivacion',
                    'mensaje': f"¡Racha de {progreso['racha_actual']} días! La consistencia es clave."
                })
            
            if progreso['porcentaje_exito'] >= 80:
                insights.append({
                    'tipo': 'exito',
                    'mensaje': f"Estás completando el hábito el {progreso['porcentaje_exito']}% del tiempo. ¡Increíble!"
                })
        
        return insights
