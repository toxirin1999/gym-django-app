import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime, timedelta
from django.db.models import Count, Sum, Avg, F, Q
from django.utils import timezone


class AnalisisGamificacionService:
    """
    Servicio para analizar datos de gamificación y generar insights
    """

    @classmethod
    def analisis_global_clientes(cls, periodo_dias=90):
        """
        Genera un análisis global de todos los clientes para el período especificado

        Args:
            periodo_dias: Número de días hacia atrás para analizar

        Returns:
            Diccionario con los resultados del análisis
        """
        from .models import PerfilGamificacion, LogroUsuario, QuestUsuario, HistorialPuntos
        from clientes.models import Cliente

        # Fecha de inicio del período de análisis
        fecha_inicio = timezone.now() - timedelta(days=periodo_dias)

        # Estadísticas básicas
        total_clientes = Cliente.objects.count()
        clientes_activos = Cliente.objects.filter(
            perfil_gamificacion__fecha_ultimo_entreno__gte=fecha_inicio
        ).count()

        # Porcentaje de clientes activos
        porcentaje_activos = (clientes_activos / total_clientes * 100) if total_clientes > 0 else 0

        # Logros y misiones en el período
        logros_desbloqueados = LogroUsuario.objects.filter(
            fecha_desbloqueo__gte=fecha_inicio,
            completado=True
        ).count()

        misiones_completadas = QuestUsuario.objects.filter(
            fecha_fin__gte=fecha_inicio,
            completada=True
        ).count()

        # Puntos totales ganados en el período
        puntos_periodo = HistorialPuntos.objects.filter(
            fecha__gte=fecha_inicio
        ).aggregate(total=Sum('puntos'))['total'] or 0

        # Promedio de puntos por cliente activo
        promedio_puntos = puntos_periodo / clientes_activos if clientes_activos > 0 else 0

        # Distribución de niveles
        distribucion_niveles = PerfilGamificacion.objects.values(
            'nivel_actual__numero', 'nivel_actual__nombre'
        ).annotate(
            total=Count('id')
        ).order_by('nivel_actual__numero')

        # Logros más populares en el período
        logros_populares = LogroUsuario.objects.filter(
            fecha_desbloqueo__gte=fecha_inicio,
            completado=True
        ).values(
            'logro__nombre', 'logro__tipo__categoria'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:10]

        # Misiones más completadas en el período
        misiones_populares = QuestUsuario.objects.filter(
            fecha_fin__gte=fecha_inicio,
            completada=True
        ).values(
            'quest__nombre', 'quest__tipo__periodo'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:10]

        # Tendencia de puntos diarios en el período
        puntos_diarios = HistorialPuntos.objects.filter(
            fecha__gte=fecha_inicio
        ).values('fecha__date').annotate(
            total=Sum('puntos')
        ).order_by('fecha__date')

        # Generar gráfico de tendencia de puntos
        grafico_tendencia = cls._generar_grafico_tendencia(puntos_diarios)

        # Distribución de logros por categoría
        logros_por_categoria = LogroUsuario.objects.filter(
            fecha_desbloqueo__gte=fecha_inicio,
            completado=True
        ).values(
            'logro__tipo__categoria'
        ).annotate(
            total=Count('id')
        ).order_by('-total')

        # Generar gráfico de distribución por categoría
        grafico_categorias = cls._generar_grafico_categorias(logros_por_categoria)

        # Rachas activas
        rachas_activas = PerfilGamificacion.objects.filter(
            racha_actual__gt=0
        ).count()

        porcentaje_rachas = (rachas_activas / total_clientes * 100) if total_clientes > 0 else 0

        # Retención de clientes (clientes que han entrenado en la última semana)
        retencion_semanal = Cliente.objects.filter(
            perfil_gamificacion__fecha_ultimo_entreno__gte=timezone.now() - timedelta(days=7)
        ).count()

        porcentaje_retencion = (retencion_semanal / total_clientes * 100) if total_clientes > 0 else 0

        return {
            'total_clientes': total_clientes,
            'clientes_activos': clientes_activos,
            'porcentaje_activos': round(porcentaje_activos, 1),
            'logros_desbloqueados': logros_desbloqueados,
            'misiones_completadas': misiones_completadas,
            'puntos_periodo': puntos_periodo,
            'promedio_puntos': round(promedio_puntos, 1),
            'distribucion_niveles': list(distribucion_niveles),
            'logros_populares': list(logros_populares),
            'misiones_populares': list(misiones_populares),
            'grafico_tendencia': grafico_tendencia,
            'grafico_categorias': grafico_categorias,
            'rachas_activas': rachas_activas,
            'porcentaje_rachas': round(porcentaje_rachas, 1),
            'retencion_semanal': retencion_semanal,
            'porcentaje_retencion': round(porcentaje_retencion, 1),
        }

    @classmethod
    def _generar_grafico_tendencia(cls, datos_puntos):
        """Genera un gráfico de tendencia de puntos"""
        if not datos_puntos:
            return None

        try:
            df = pd.DataFrame(list(datos_puntos))
            df.columns = ['fecha', 'puntos']

            plt.figure(figsize=(10, 5))
            plt.plot(df['fecha'], df['puntos'], marker='o', linestyle='-', color='#4CAF50')
            plt.title('Tendencia de Puntos Diarios')
            plt.xlabel('Fecha')
            plt.ylabel('Puntos')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()

            # Guardar gráfico en memoria
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            imagen_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            plt.close()

            return imagen_base64
        except Exception as e:
            print(f"Error al generar gráfico de tendencia: {e}")
            return None

    @classmethod
    def _generar_grafico_categorias(cls, datos_categorias):
        """Genera un gráfico de distribución de logros por categoría"""
        if not datos_categorias:
            return None

        try:
            df = pd.DataFrame(list(datos_categorias))
            df.columns = ['categoria', 'total']

            plt.figure(figsize=(8, 8))
            plt.pie(df['total'], labels=df['categoria'], autopct='%1.1f%%',
                    shadow=True, startangle=90)
            plt.axis('equal')
            plt.title('Distribución de Logros por Categoría')
            plt.tight_layout()

            # Guardar gráfico en memoria
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            imagen_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            plt.close()

            return imagen_base64
        except Exception as e:
            print(f"Error al generar gráfico de categorías: {e}")
            return None
