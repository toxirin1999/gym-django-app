"""
Servicio de Estadísticas y Análisis
Calcula métricas, tendencias y comparativas para el dashboard
"""

from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import numpy as np
import logging

logger = logging.getLogger(__name__)

# MAPEO DE EJERCICIOS PARA 1RM Y RATIOS
MAPEO_EJERCICIOS_A_PRINCIPAL = {
    # 🎯 REMO (Row)
    'remo con barra (pendlay)': 'Remo',
    'remo con mancuerna a una mano': 'Remo',
    'remo en polea baja (gironda)': 'Remo',
    'remo con barra': 'Remo',
    'remo en polea alta': 'Remo',

    # 🎯 PRESS BANCA (Bench Press)
    'press banca con barra': 'Press Banca',
    'press banca con mancuernas': 'Press Banca',
    'press inclinado con barra': 'Press Banca',
    # Eliminados: Press Cerrado, Fondos (perfiles de fuerza muy diferentes)

    # 🎯 PRESS MILITAR (Overhead Press)
    'press militar con barra (de pie)': 'Press Militar',
    'press militar con mancuernas (sentado)': 'Press Militar',
    'push press': 'Press Militar',

    # 🎯 PESO MUERTO (Deadlift)
    'peso muerto': 'Peso Muerto',
    'peso muerto rumano': 'Peso Muerto',
    'peso muerto sumo': 'Peso Muerto',
    # Eliminados: Hip Thrust, Buenos Días

    # 🎯 SENTADILLA (Squat)
    'sentadilla trasera con barra': 'Sentadilla',
    'sentadilla frontal con barra': 'Sentadilla',
    'sentadilla goblet': 'Sentadilla',
    # Eliminados: Prensa, Búlgara, Zancadas (máquinas y unilaterales)
}

CONFIG_RATIOS = {
    'Press Banca / Sentadilla': ('Press Banca', 'Sentadilla'),
    'Peso Muerto / Sentadilla': ('Peso Muerto', 'Sentadilla'),
    'Press Militar / Press Banca': ('Press Militar', 'Press Banca'),
    'Remo / Press Banca': ('Remo', 'Press Banca')
}

MAPEO_MUSCULAR = {
    # PECHO
    'press banca con barra': 'Pecho',
    'press banca con mancuernas': 'Pecho',
    'press inclinado con barra': 'Pecho',
    'press inclinado con mancuernas': 'Pecho',
    'press cerrado en banca': 'Pecho',
    'fondos en paralelas (con lastre)': 'Pecho',
    'aperturas con mancuernas': 'Pecho',
    'cruce de poleas': 'Pecho',
    'pec deck': 'Pecho',

    # 🎯 ESPALDA Y TRACCIONES VERTICALES
    'dominadas': 'Dominadas',
    'dominadas asistidas': 'Dominadas',
    'dominadas supinas': 'Dominadas',
    'jalon al pecho': 'Espalda',
    'jalón al pecho': 'Espalda',
    'pull over en polea alta': 'Espalda',
    'peso muerto rumano': 'Espalda',
    'peso muerto sumo': 'Espalda',
    'face pulls': 'Espalda',
    'pull-overs con mancuerna': 'Espalda',
    
    # 🎯 REMOS (Tracciones horizontales) -> Mapeo directo a Rowing Hyrox
    'remo': 'Rowing',
    'remo en máquina': 'Rowing',
    'remo con barra': 'Rowing',
    'remo con mancuerna': 'Rowing',
    'remo con mancuerna a una mano': 'Rowing',
    'remo en polea baja (gironda)': 'Rowing',
    'remo gironda': 'Rowing',
    'remo en polea alta': 'Rowing',
    'farmers carry': 'Farmers Carry',
    'paseo del granjero': 'Farmers Carry',
    'paseo granjero': 'Farmers Carry',
    'farmer walk': 'Farmers Carry',
    'peso muerto': 'Espalda',
    'peso muerto rumano': 'Espalda',
    'peso muerto sumo': 'Espalda',
    'dominadas (con lastre)': 'Espalda',
    'jalón al pecho': 'Espalda',
    'face pulls': 'Espalda',
    'pull-overs con mancuerna': 'Espalda',

    # HOMBROS
    'press militar con barra (de pie)': 'Hombros',
    'press militar con mancuernas (sentado)': 'Hombros',
    'push press': 'Hombros',
    'press arnold': 'Hombros',
    'elevaciones laterales con mancuernas': 'Hombros',
    'elevaciones frontales con polea': 'Hombros',
    'pájaros (bent over raises)': 'Hombros',

    # CUÁDRICEPS
    'sentadilla trasera con barra': 'Cuádriceps',
    'sentadilla frontal con barra': 'Cuádriceps',
    'sentadilla búlgara': 'Cuádriceps',
    'prensa de piernas': 'Cuádriceps',
    'zancadas con mancuernas': 'Cuádriceps',
    'extensiones de cuádriceps en máquina': 'Cuádriceps',

    # ISQUIOS
    'buenos días (good mornings)': 'Isquios',
    'curl femoral tumbado': 'Isquios',
    'curl femoral sentado': 'Isquios',
    'hiperextensiones inversas': 'Isquios',

    # GLÚTEOS
    'hip thrust con barra': 'Glúteos',
    'patada de glúteo en polea': 'Glúteos',
    'abducción de cadera en máquina': 'Glúteos',

    # BÍCEPS
    'curl con barra z': 'Bíceps',
    'curl araña': 'Bíceps',
    'curl de concentración': 'Bíceps',
    'curl martillo con mancuernas': 'Bíceps',
    'curl en polea alta': 'Bíceps',

    # TRÍCEPS
    'press francés con barra z': 'Tríceps',
    'press cerrado en banca': 'Tríceps',
    'extensiones de tríceps con polea alta': 'Tríceps',
    'fondos entre bancos': 'Tríceps',
    'patada de tríceps con polea': 'Tríceps',

    # CORE
    'plancha (plank)': 'Core',
    'crunch abdominal': 'Core',
    'elevación de piernas': 'Core',
    'mountain climbers': 'Core',
}


class EstadisticasService:
    """
    Servicio para cálculos estadísticos y análisis de progreso
    """

    @staticmethod
    def calcular_estadisticas_globales(cliente, rango='30d'):
        """
        Calcula estadísticas globales para un cliente en un rango de tiempo
        """
        from entrenos.models import EntrenoRealizado, SesionEntrenamiento

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        # Filtrar entrenamientos en el rango
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio
        )

        # Estadísticas básicas
        total_entrenamientos = entrenamientos.count()
        volumen_total = entrenamientos.aggregate(
            total=Sum('volumen_total_kg')
        )['total'] or 0

        # Estadísticas de sesiones
        sesiones = SesionEntrenamiento.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio
        )

        duracion_promedio = sesiones.aggregate(
            promedio=Avg('duracion_minutos')
        )['promedio'] or 0

        rpe_promedio = sesiones.aggregate(
            promedio=Avg('rpe_medio')
        )['promedio'] or 0

        sesiones_perfectas = sesiones.filter(
            series_completadas=F('series_totales')
        ).count()

        return {
            'total_entrenamientos': total_entrenamientos,
            'volumen_total_global': volumen_total or 0,
            'duracion_promedio': round(duracion_promedio, 1) if duracion_promedio else 0,
            'rpe_promedio': round(rpe_promedio, 1) if rpe_promedio else 0,
            'sesiones_perfectas': sesiones_perfectas,
            'porcentaje_perfeccion': round((sesiones_perfectas / total_entrenamientos * 100),
                                           1) if total_entrenamientos > 0 else 0
        }

    @staticmethod
    def calcular_progresion_ejercicios(cliente, rango='30d'):
        """
        Calcula la progresión de peso/volumen por ejercicio
        """
        from entrenos.models import EjercicioRealizado

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        # Obtener ejercicios únicos
        ejercicios_nombres = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values_list('nombre_ejercicio', flat=True).distinct()

        progresiones = []

        for nombre_ejercicio in ejercicios_nombres:
            ejercicios = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio=nombre_ejercicio,
                completado=True,
                entreno__fecha__gte=fecha_inicio
            ).order_by('entreno__fecha')

            if ejercicios.count() < 2:
                continue

            primer_ejercicio = ejercicios.first()
            ultimo_ejercicio = ejercicios.last()

            peso_inicial = Decimal(str(primer_ejercicio.peso_kg))
            peso_actual = Decimal(str(ultimo_ejercicio.peso_kg))
            progresion_kg = peso_actual - peso_inicial

            progresion_porcentaje = 0
            if peso_inicial > 0:
                progresion_porcentaje = float((progresion_kg / peso_inicial) * 100)

            # Determinar tendencia
            if progresion_kg > 0:
                tendencia = 'subiendo'
            elif progresion_kg < 0:
                tendencia = 'bajando'
            else:
                tendencia = 'estable'

            progresiones.append({
                'nombre_ejercicio': nombre_ejercicio,
                'peso_inicial': float(round(peso_inicial, 1)),
                'peso_actual': float(round(peso_actual, 1)),
                'progresion_kg': float(round(progresion_kg, 1)),
                'progresion_porcentaje': round(progresion_porcentaje, 1),
                'tendencia': tendencia
            })

        return sorted(progresiones, key=lambda x: abs(x['progresion_porcentaje']), reverse=True)

    @staticmethod
    def calcular_distribucion_muscular(cliente, rango='30d'):
        """
        Calcula la distribución de volumen por grupo muscular usando mapeo explícito
        """
        from entrenos.models import EjercicioRealizado

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        # Obtener todos los ejercicios en el rango
        ejercicios = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('nombre_ejercicio', 'grupo_muscular', 'peso_kg', 'series', 'repeticiones')

        # Procesar en Python para aplicar el mapeo
        volumen_por_grupo = {}

        for ej in ejercicios:
            nombre = ej['nombre_ejercicio'].lower().strip()
            # 1. Intentar usar el grupo_muscular de la BD si existe
            grupo = ej['grupo_muscular']

            # 2. Si no, usar el mapeo explícito
            if not grupo:
                grupo = MAPEO_MUSCULAR.get(nombre)

            # 3. Si aún no hay grupo, marcar como 'Otros'
            if not grupo:
                grupo = 'Otros'

            # Calcular volumen
            try:
                volumen = float(ej['peso_kg'] or 0) * int(ej['series'] or 1) * int(ej['repeticiones'] or 1)
                if volumen > 0:
                    volumen_por_grupo[grupo] = volumen_por_grupo.get(grupo, 0) + volumen
            except (ValueError, TypeError):
                continue

        # Ordenar y formatear para el gráfico
        datos_ordenados = sorted(volumen_por_grupo.items(), key=lambda x: x[1], reverse=True)

        return {
            'labels': [x[0] for x in datos_ordenados],
            'data': [float(round(x[1], 1)) for x in datos_ordenados]
        }

    @staticmethod
    def calcular_volumen_semanal(cliente, rango='30d'):
        """
        Calcula el volumen total por semana
        """
        from entrenos.models import EntrenoRealizado
        from django.db.models.functions import TruncWeek

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        # Agrupar por semana
        volumen_semanal = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio
        ).annotate(
            semana=TruncWeek('fecha')
        ).values('semana').annotate(
            volumen=Sum('volumen_total_kg')
        ).order_by('semana')

        labels = []
        data = []

        for item in volumen_semanal:
            if item['semana']:
                labels.append(item['semana'].strftime('%d/%m'))
                data.append(float(item['volumen'] or 0))

        return {
            'labels': labels,
            'data': data
        }

    @staticmethod
    def generar_heatmap_actividad(cliente):
        """
        Genera datos para el heatmap de actividad anual
        """
        from entrenos.models import EntrenoRealizado

        # Obtener entrenamientos del último año
        hace_un_ano = timezone.now().date() - timedelta(days=365)

        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=hace_un_ano
        ).values('fecha').annotate(
            count=Count('id')
        )

        # Crear diccionario con fechas y conteos
        actividad = {}
        for entreno in entrenamientos:
            fecha_str = entreno['fecha'].strftime('%Y-%m-%d')
            actividad[fecha_str] = entreno['count']

        return actividad

    @staticmethod
    def analizar_acwr(cliente, periodo_dias=90):
        """
        Calcula la Carga Aguda, Carga Crónica y el ratio ACWR.
        """
        from entrenos.models import EntrenoRealizado
        try:
            import pandas as pd
        except ImportError:
            return {'dataframe': [], 'acwr_actual': 0, 'zona_riesgo': 'desconocida'}

        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=periodo_dias)

        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        ).order_by('fecha').values('fecha', 'volumen_total_kg')

        if not entrenamientos:
            return {'dataframe': [], 'acwr_actual': 0, 'zona_riesgo': 'baja_carga'}

        df = pd.DataFrame(list(entrenamientos))
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['volumen_total_kg'] = df['volumen_total_kg'].astype(float)

        df = df.groupby('fecha')['volumen_total_kg'].sum().reset_index()
        df['carga_diaria'] = df['volumen_total_kg'] / 1000

        idx = pd.date_range(start=fecha_inicio, end=fecha_fin)
        df = df.set_index('fecha').reindex(idx, fill_value=0)

        df['carga_aguda'] = df['carga_diaria'].rolling(window=7, min_periods=1).mean()
        df['carga_cronica'] = df['carga_diaria'].rolling(window=28, min_periods=1).mean()
        df['acwr'] = (df['carga_aguda'] / df['carga_cronica']).fillna(0).replace([np.inf, -np.inf], 0)

        acwr_actual = round(df['acwr'].iloc[-1], 2) if not df.empty else 0

        if 0.8 <= acwr_actual <= 1.3:
            zona_riesgo = 'optima'
        elif 1.3 < acwr_actual < 1.5:
            zona_riesgo = 'cuidado'
        elif acwr_actual >= 1.5:
            zona_riesgo = 'riesgo_alto'
        else:
            zona_riesgo = 'baja_carga'

        df_json = df.reset_index().rename(columns={'index': 'fecha'})
        df_json['fecha'] = df_json['fecha'].dt.strftime('%Y-%m-%d')

        return {
            'dataframe': df_json.to_dict('records'),
            'acwr_actual': acwr_actual,
            'zona_riesgo': zona_riesgo
        }

    @staticmethod
    def analizar_equilibrio_muscular(cliente):
        """
        Calcula ratios de fuerza para el gráfico de radar.
        """
        one_rm_estimados = EstadisticasService.calcular_1rm_estimado_por_ejercicio(cliente)

        resultados = []
        datos_radar = {'labels': [], 'valores': []}

        for nombre_ratio, (ej_num, ej_den) in CONFIG_RATIOS.items():
            valor_num = one_rm_estimados.get(ej_num, 0)
            valor_den = one_rm_estimados.get(ej_den, 0)

            ratio = 0
            if valor_num > 0 and valor_den > 0:
                ratio = round(valor_num / valor_den, 2)

            resultados.append({
                'nombre': nombre_ratio,
                'ratio': ratio,
            })
            datos_radar['labels'].append(nombre_ratio)
            datos_radar['valores'].append(ratio)

        return {'tabla_ratios': resultados, 'datos_radar': datos_radar}

    @staticmethod
    def analizar_estado_coach(cliente):
        """
        Analiza el estado del cliente basado en los 3 pilares: ACWR, RPE y Volumen.
        Retorna un mensaje, un estado (color) y un icono para el AI Coach.
        """
        # 1. ACWR (Acute:Chronic Workload Ratio)
        acwr_data = EstadisticasService.analizar_acwr(cliente)
        acwr = acwr_data.get('acwr_actual', 1.0)
        zona_riesgo = acwr_data.get('zona_riesgo', 'desconocida')

        # 2. RPE (Ratio de Esfuerzo Percibido)
        stats_globales = EstadisticasService.calcular_estadisticas_globales(cliente, rango='30d')
        rpe_medio = stats_globales.get('rpe_promedio', 0)

        # 3. Volumen (Tendencia)
        # Usaremos la detección de estancamientos como proxy de la tendencia de volumen/fuerza
        estancados = EstadisticasService.detectar_estancamientos(cliente)

        # 4. Equilibrio Muscular (Ratios de Fuerza)
        equilibrio_data = EstadisticasService.analizar_equilibrio_muscular(cliente)
        ratios = equilibrio_data.get('tabla_ratios', [])

        # 5. Volumen Óptimo (Series por Grupo)
        volumen_optimo_data = EstadisticasService.analizar_volumen_optimo(cliente, rango='30d')
        series_reales = volumen_optimo_data.get('series_reales', [])
        grupos = volumen_optimo_data.get('labels', [])
        min_series = volumen_optimo_data.get('min_recomendado', 10)
        max_series = volumen_optimo_data.get('max_recomendado', 20)

        # --- LÓGICA DE DECISIÓN DEL COACH (HOLÍSTICA) ---
        diagnosticos = []

        # 1. Análisis de Carga (ACWR)
        if zona_riesgo == 'riesgo_alto':
            diagnosticos.append(
                f"⚠️ <b>FATIGA CRÍTICA:</b> Tu ACWR ({acwr}) indica riesgo alto. ¡Prioriza el descanso!")
            estado = 'riesgo'
            color = '#FF2D92'
            icono = 'fas fa-skull-crossbones'
        elif zona_riesgo == 'cuidado':
            diagnosticos.append(f"⚠️ <b>PRECAUCIÓN:</b> Carga elevada ({acwr}). Vigila tu recuperación.")
            estado = 'cuidado'
            color = '#FFB800'
            icono = 'fas fa-exclamation-triangle'
        else:
            diagnosticos.append(f"✅ <b>CARGA ÓPTIMA:</b> Ratio ACWR ({acwr}) en zona ideal.")
            estado = 'optimo'
            color = '#00FF88'
            icono = 'fas fa-check-circle'

        # 2. Análisis de Intensidad (RPE)
        if rpe_medio > 8.5:
            diagnosticos.append(f"🔥 <b>INTENSIDAD ALTA:</b> RPE medio de {rpe_medio}. Estás al límite.")
            if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'
        elif rpe_medio < 7.0:
            diagnosticos.append(f"📉 <b>INTENSIDAD BAJA:</b> RPE de {rpe_medio}. Tienes margen para subir carga.")
            if estado == 'optimo': estado, color, icono = 'baja', '#00D4FF', 'fas fa-arrow-up'

        # 3. Análisis de Estancamiento
        if estancados:
            diagnosticos.append(
                f"🛑 <b>ESTANCAMIENTO:</b> {len(estancados)} ejercicios sin progreso (ej: {estancados[0]['nombre']}).")
            if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'

        # 4. Análisis de Equilibrio Muscular
        desequilibrios = []
        for ratio in ratios:
            if ratio['nombre'] == 'Press Banca / Sentadilla' and (ratio['ratio'] < 0.5 or ratio['ratio'] > 0.7):
                desequilibrios.append(
                    f"⚖️ <b>DESEQUILIBRIO:</b> Ratio Banca/Sentadilla ({ratio['ratio']}) fuera de rango.")
            elif ratio['nombre'] == 'Remo / Press Banca' and ratio['ratio'] < 1.0:
                desequilibrios.append(
                    f"⚖️ <b>DESEQUILIBRIO:</b> Tu tracción es débil frente al empuje (Ratio: {ratio['ratio']}).")

        if desequilibrios:
            diagnosticos.extend(desequilibrios)
            if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'

        # 5. Análisis de Volumen Óptimo
        volumen_problema = []
        for i, series in enumerate(series_reales):
            grupo = grupos[i]
            if series < min_series and series > 0:
                volumen_problema.append(f"📦 <b>VOLUMEN BAJO:</b> {grupo} necesita más series (actual: {series}).")
            elif series > max_series:
                volumen_problema.append(f"📦 <b>SOBRECARGA:</b> Demasiado volumen en {grupo} ({series} series).")

        if volumen_problema:
            diagnosticos.extend(volumen_problema[:2])  # Mostrar max 2
            if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'

        # Unir todos los diagnósticos con saltos de línea
        mensaje = "<br>".join(diagnosticos)

        # Función auxiliar para convertir HEX a RGBA

        # Función auxiliar para convertir HEX a RGBA
        def hex_to_rgba(hex_color, alpha):
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"rgba({r}, {g}, {b}, {alpha})"

        return {
            'mensaje': mensaje,
            'estado': estado,
            'color': color,
            'color_rgba_01': hex_to_rgba(color, 0.1),
            'color_rgba_02': hex_to_rgba(color, 0.2),
            'color_rgba_05': hex_to_rgba(color, 0.5),
            'icono': icono,
            'acwr': acwr,
            'rpe_medio': rpe_medio,
            'ejercicios_estancados': len(estancados),
            'desequilibrios': desequilibrios,
            'volumen_problema': volumen_problema
        }

    @staticmethod
    def calcular_1rm_estimado_por_ejercicio(cliente):
        """
        Calcula el 1RM máximo para cada patrón de movimiento.
        """
        from entrenos.models import EjercicioRealizado
        ejercicios = EjercicioRealizado.objects.filter(entreno__cliente=cliente, completado=True)

        one_rm_finales = {}
        for e in ejercicios:
            try:
                peso = float(e.peso_kg or 0)
                reps = int(e.repeticiones or 1)

                if peso > 0:
                    rm_estimado = peso * (1 + (reps / 30))
                    nombre_norm = e.nombre_ejercicio.lower().strip()
                    principal = MAPEO_EJERCICIOS_A_PRINCIPAL.get(nombre_norm)

                    if principal:
                        if principal not in one_rm_finales or rm_estimado > one_rm_finales[principal]:
                            one_rm_finales[principal] = rm_estimado
            except (ValueError, TypeError):
                continue

        return {k: round(v, 2) for k, v in one_rm_finales.items()}

    @staticmethod
    def analizar_volumen_optimo(cliente, rango='30d'):
        """
        Calcula las series efectivas semanales por grupo muscular.
        Se adapta al rango seleccionado para mostrar el promedio semanal en ese periodo.
        """
        from entrenos.models import EjercicioRealizado
        from django.utils import timezone
        from datetime import timedelta

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)
        hoy = timezone.now().date()

        # Ajuste especial para 'Todo': usar la fecha del primer entrenamiento real
        if rango == 'todo':
            primer_entreno = EjercicioRealizado.objects.filter(entreno__cliente=cliente).order_by(
                'entreno__fecha').first()
            if primer_entreno:
                fecha_inicio = primer_entreno.entreno.fecha

        # Calcular cuántas semanas han pasado en este rango para promediar
        dias_pasados = (hoy - fecha_inicio).days
        # Mínimo 7 días para promediar (evitar divisiones por 0 o infladas)
        semanas_divisor = max(1.0, dias_pasados / 7.0)

        # Agrupar series por grupo muscular en el rango seleccionado
        ejercicios = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('nombre_ejercicio', 'grupo_muscular', 'series')

        series_por_grupo = {}
        for ej in ejercicios:
            nombre = ej['nombre_ejercicio'].lower().strip()
            # Limpiar grupo_muscular de la BD
            grupo_db = ej['grupo_muscular']
            if not grupo_db or grupo_db in ['-', 'None', 'null', 'Null']:
                grupo_db = None

            grupo = grupo_db or MAPEO_MUSCULAR.get(nombre) or 'Otros'
            series_por_grupo[grupo] = series_por_grupo.get(grupo, 0) + (ej['series'] or 0)

        # Formatear para el gráfico de barras
        grupos_principales = ['Pecho', 'Espalda', 'Cuádriceps', 'Isquios', 'Hombros', 'Glúteos', 'Bíceps', 'Tríceps']
        labels = []
        data_actual = []

        for grupo in grupos_principales:
            labels.append(grupo)
            # Calculamos el promedio semanal basado en el rango
            total_ejercicio = series_por_grupo.get(grupo, 0)
            promedio_semanal = round(total_ejercicio / semanas_divisor, 1)
            data_actual.append(promedio_semanal)

        return {
            'labels': labels,
            'series_reales': data_actual,
            'series_recomendadas': [15.0] * len(grupos_principales),
            'min_recomendado': 10,
            'max_recomendado': 20
        }

    @staticmethod
    def analizar_intensidad_historica(cliente):
        """
        Analiza la distribución de RPE de las sesiones
        """
        from entrenos.models import SesionEntrenamiento

        sesiones = SesionEntrenamiento.objects.filter(entreno__cliente=cliente, rpe_medio__isnull=False)

        # Clasificar RPE
        intensidad = {'Baja (1-5)': 0, 'Moderada (6-7)': 0, 'Alta (8-9)': 0, 'Máxima (10)': 0}

        for s in sesiones:
            val = s.rpe_medio
            if val <= 5:
                intensidad['Baja (1-5)'] += 1
            elif val <= 7:
                intensidad['Moderada (6-7)'] += 1
            elif val <= 9:
                intensidad['Alta (8-9)'] += 1
            else:
                intensidad['Máxima (10)'] += 1

        return {
            'labels': list(intensidad.keys()),
            'data': list(intensidad.values())
        }

    @staticmethod
    def generar_predicciones_ia(cliente):
        """
        Proyecta el 1RM a futuro basado en la tendencia actual
        """
        from entrenos.models import EjercicioRealizado

        # Solo para los 3 grandes por ahora (mejor data)
        ejercicios_objetivo = ['Press Banca', 'Sentadilla', 'Peso Muerto']
        proyecciones = []

        for ej_nombre in ejercicios_objetivo:
            # Buscar variaciones mapeadas a este ejercicio principal
            nombres_variaciones = [k for k, v in MAPEO_EJERCICIOS_A_PRINCIPAL.items() if v == ej_nombre]
            # Asegurar que incluimos versiones en Título (común en la base de datos)
            nombres_variaciones_extendidos = list(
                set(nombres_variaciones + [n.strip().title() for n in nombres_variaciones]))

            registros = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio__in=nombres_variaciones_extendidos,
                peso_kg__gt=0,
                completado=True
            ).order_by('entreno__fecha')

            if registros.count() < 3: continue

            # Cálculo de tendencia por sesión (Max 1RM per day)
            marcas_diarias = {}
            for r in registros:
                fecha = r.entreno.fecha
                rm = float(r.peso_kg) * (1 + (r.repeticiones / 30))
                if fecha not in marcas_diarias or rm > marcas_diarias[fecha]:
                    marcas_diarias[fecha] = rm

            # Ordenar por fecha para obtener la serie temporal
            fechas_ordenadas = sorted(marcas_diarias.keys())
            marcas = [marcas_diarias[f] for f in fechas_ordenadas]

            if len(marcas) < 3: continue

            actual = marcas[-1]
            inicial = marcas[0]
            dias = (fechas_ordenadas[-1] - fechas_ordenadas[0]).days or 1

            tasa_diaria = (actual - inicial) / dias

            # Proyectar a 4 y 8 semanas
            proyecciones.append({
                'nombre': ej_nombre,
                'actual': round(actual, 1),
                'p4_semanas': round(actual + (tasa_diaria * 28), 1),
                'p8_semanas': round(actual + (tasa_diaria * 56), 1),
                'confianza': min(95, 50 + (len(marcas) * 5))
            })

        return proyecciones

    @staticmethod
    def obtener_mapeo_muscular_completo():
        """
        Retorna el glosario completo de ejercicios organizados por grupo muscular.
        """
        glosario = {}
        for ej, grupo in MAPEO_MUSCULAR.items():
            if grupo not in glosario:
                glosario[grupo] = []
            glosario[grupo].append(ej.title())

        # Ordenar grupos y ejercicios
        glosario_ordenado = {k: sorted(v) for k, v in sorted(glosario.items())}
        return glosario_ordenado

    @staticmethod
    def detectar_estancamientos(cliente):
        """
        Detecta ejercicios que llevan 3+ sesiones sin mejora
        """
        from entrenos.models import EjercicioRealizado

        # Obtener nombres de todos los ejercicios realizados
        nombres = EjercicioRealizado.objects.filter(entreno__cliente=cliente).values_list('nombre_ejercicio',
                                                                                          flat=True).distinct()
        estancados = []

        for nombre in nombres:
            registros = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio=nombre,
                completado=True
            ).order_by('-entreno__fecha')[:4]

            if registros.count() < 3: continue

            # Calcular volumen total por sesión (peso * reps * series)
            volumenes = [float(r.peso_kg) * r.repeticiones * r.series for r in registros]

            # Si el volumen del último es menor o igual al promedio de los 3 anteriores (con margen del 2%)
            ultimo = volumenes[0]
            anteriores = volumenes[1:]
            promedio_anterior = sum(anteriores) / len(anteriores)

            if ultimo <= promedio_anterior * 1.02:
                estancados.append({
                    'nombre': nombre,
                    'ultimo_volumen': round(ultimo, 1),
                    'sesiones_estancado': 3,
                    'recomendacion': "Considera un 'Deload' o variar el rango de repeticiones."
                })

        return sorted(estancados, key=lambda x: x['ultimo_volumen'], reverse=True)[:5]

    @staticmethod
    def _calcular_fecha_inicio(rango):
        """
        Calcula la fecha de inicio basándose en el rango
        """
        hoy = timezone.now().date()

        if rango == '30d':
            return hoy - timedelta(days=30)
        elif rango == '90d':
            return hoy - timedelta(days=90)
        elif rango == '180d':
            return hoy - timedelta(days=180)
        elif rango == 'todo':
            return datetime(2000, 1, 1).date()
        else:
            return hoy - timedelta(days=30)
