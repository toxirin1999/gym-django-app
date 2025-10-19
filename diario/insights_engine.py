# diario/insights_engine.py

from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg
from .models import ProsocheDiario, SeguimientoVires
from django.urls import reverse


def generar_insights_semanales(user):
    """
    Genera una lista de insights y sugerencias de acción basadas en los datos de la última semana.
    """
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday() + 7)
    fin_semana = inicio_semana + timedelta(days=6)

    insights = []

    # Obtener datos de la semana
    entradas = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=user,
        fecha__range=[inicio_semana, fin_semana]
    )
    seguimientos = SeguimientoVires.objects.filter(
        usuario=user,
        fecha__range=[inicio_semana, fin_semana]
    )

    if not entradas.exists() and not seguimientos.exists():
        insights.append({
            'titulo': 'Una Semana de Datos',
            'mensaje': 'Has completado otra semana de seguimiento. Cada dato que registras es un paso más hacia el autoconocimiento. Sigue así, el camino del filósofo se construye día a día.',
            'tipo': 'info',
            'sugerencia_accion': {
                'texto': 'Hacer Revisión Semanal',
                'url': reverse('diario:prosoche_revision_semanal')
            }
        })
        return insights

    # --- Insight 1: Correlación Sueño y Energía ---
    if seguimientos.count() >= 3:
        # Días con buen sueño vs mal sueño
        buen_sueno = seguimientos.filter(horas_sueno__gte=7).aggregate(avg_energia=Avg('nivel_energia'))
        mal_sueno = seguimientos.filter(horas_sueno__lt=7).aggregate(avg_energia=Avg('nivel_energia'))

        if buen_sueno['avg_energia'] and mal_sueno['avg_energia'] and buen_sueno['avg_energia'] > mal_sueno[
            'avg_energia']:
            mejora = round(((buen_sueno['avg_energia'] / mal_sueno['avg_energia']) - 1) * 100)
            insights.append({
                'titulo': 'El Descanso es tu Poder',
                'mensaje': f"Análisis de la semana: los días que duermes 7 horas o más, tu nivel de energía promedio es un {mejora}% más alto. El descanso no es tiempo perdido, es una inversión.",
                'tipo': 'success',
                'sugerencia_accion': {
                    'texto': 'Planificar Descanso',
                    'url': reverse('diario:prosoche_revision_semanal')  # URL para añadir un objetivo de sueño
                }
            })

    # --- Insight 2: Correlación Ánimo y Estrés ---
    if seguimientos.count() >= 3 and entradas.count() >= 3:
        dias_alto_estres = seguimientos.filter(nivel_estres__gte=4).values_list('fecha', flat=True)
        animo_alto_estres = entradas.filter(fecha__in=dias_alto_estres).aggregate(avg_animo=Avg('estado_animo'))
        animo_bajo_estres = entradas.exclude(fecha__in=dias_alto_estres).aggregate(avg_animo=Avg('estado_animo'))

        if animo_alto_estres['avg_animo'] and animo_bajo_estres['avg_animo'] and animo_alto_estres['avg_animo'] < \
                animo_bajo_estres['avg_animo']:
            insights.append({
                'titulo': 'La Fortaleza ante la Tensión',
                'mensaje': 'Hemos observado que en tus días de mayor estrés, tu estado de ánimo tiende a bajar. Recuerda las herramientas estoicas: enfócate en lo que puedes controlar y acepta lo demás.',
                'tipo': 'warning',
                'sugerencia_accion': {
                    'texto': 'Reflexionar sobre el Estrés',
                    'url': reverse('diario:analiticas_personales')  # URL para ver los gráficos
                }
            })

    # Si no se generó ningún insight específico, añadir uno genérico
    if not insights:
        insights.append({
            'titulo': 'El Viaje Continúa',
            'mensaje': 'Sigue registrando tus datos para descubrir patrones más profundos. La constancia es la clave de la sabiduría.',
            'tipo': 'info',
            'sugerencia_accion': {
                'texto': 'Ver mi Progreso',
                'url': reverse('diario:analiticas_personales')
            }
        })

    return insights
