"""
Servicio de Estadísticas y Análisis
Calcula métricas, tendencias y comparativas para el dashboard
"""

from django.db.models import Sum, Count, Avg, Q, F, Max
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import numpy as np
import logging
from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE, obtener_mapeo_inverso

logger = logging.getLogger(__name__)

# MAPEO DINÁMICO DE EJERCICIOS PARA 1RM Y RATIOS (Principal Lifts)
MAPEO_EJERCICIOS_A_PRINCIPAL = {
    # 🎯 ESPALDA Y TRACCIONES VERTICALES
    'dominadas': 'Dominadas',
    'dominadas asistidas': 'Dominadas',
    'dominadas supinas': 'Dominadas',
    'jalon al pecho': 'Espalda',
    'jalón al pecho': 'Espalda',
    'pull over en polea alta': 'Espalda',
    
    # 🎯 REMOS (Tracciones horizontales) -> Mapeo directo a Rowing Hyrox
    'remo': 'Rowing',
    'remo en máquina': 'Rowing',
    'remo con barra': 'Rowing',
    'remo con mancuerna': 'Rowing',
    'remo con mancuerna a una mano': 'Rowing',
    'remo en polea baja (gironda)': 'Rowing',
    'remo gironda': 'Rowing',
    'remo en polea alta': 'Rowing',
    'remo con barra (pendlay)': 'Rowing',
    'remo pendlay': 'Rowing',
    'remo pecho apoyado': 'Rowing',
    'remo al mentón con polea (upright row)': 'Rowing',
    'remo al menton con polea (upright row)': 'Rowing',
    # 🎯 PRESS BANCA (Bench Press)
    'press banca con barra': 'Press Banca',
    'press banca con mancuernas': 'Press Banca',
    'press inclinado con barra': 'Press Banca',
    'press inclinado con mancuernas': 'Press Banca',

    # 🎯 PRESS MILITAR (Overhead Press)
    'press militar con barra (de pie)': 'Press Militar',
    'press militar con mancuernas (sentado)': 'Press Militar',
    'push press': 'Press Militar',
    # 'machine shoulder press': 'Press Militar', # Eliminado: No transferible directamente

    # 🎯 PESO MUERTO (Deadlift)
    'farmers carry': 'Farmers Carry',
    'paseo del granjero': 'Farmers Carry',
    'paseo granjero': 'Farmers Carry',
    'farmer walk': 'Farmers Carry',
    'peso muerto': 'Peso Muerto',
    'peso muerto rumano': 'Peso Muerto',
    'peso muerto sumo': 'Peso Muerto',

    # 🎯 SENTADILLA (Squat)
    'sentadilla trasera con barra': 'Sentadilla',
    'sentadilla frontal con barra': 'Sentadilla',
    'sentadilla hack': 'Sentadilla',
    'sentadilla goblet': 'Sentadilla',
    # 'prensa de piernas': 'Sentadilla', # Eliminado: Infla artificialmente el 1RM
}

CONFIG_RATIOS = {
    'Press Banca / Sentadilla': ('Press Banca', 'Sentadilla'),
    'Peso Muerto / Sentadilla': ('Peso Muerto', 'Sentadilla'),
    'Press Militar / Press Banca': ('Press Militar', 'Press Banca'),
    'Remo / Press Banca': ('Rowing', 'Press Banca'),  # Rowing = clave usada en MAPEO_EJERCICIOS_A_PRINCIPAL
}

# MAPEO MUSCULAR DINÁMICO
def _get_dynamic_muscle_mapping():
    """Genera el mapeo de ejercicio -> grupo muscular desde la base de datos de Helms"""
    mapping = obtener_mapeo_inverso()
    
    # Nombres visuales con tildes
    nombres_display = {
        'cuadriceps': 'Cuádriceps',
        'biceps': 'Bíceps',
        'triceps': 'Tríceps',
        'gluteos': 'Glúteos',
        'isquios': 'Isquios',
        'pecho': 'Pecho',
        'espalda': 'Espalda',
        'hombros': 'Hombros',
    }

    final_mapping = {}
    for ej_nombre, grupo_db in mapping.items():
        base_name = nombres_display.get(grupo_db, grupo_db.capitalize())
        final_mapping[ej_nombre] = base_name
        
    return final_mapping

MAPEO_MUSCULAR_DYNAMIC = _get_dynamic_muscle_mapping()


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
    def analizar_estado_coach(cliente, acwr_data=None, stats_globales=None, estancados=None, equilibrio_data=None, volumen_optimo_data=None):
        """
        Analiza el estado del cliente basado en 5 pilares: ACWR, RPE, Estancamiento, Equilibrio y Volumen.
        Acepta datos pre-calculados para evitar consultas duplicadas.
        """
        # 1. Usar datos pre-calculados si están disponibles, o calcular si no
        if acwr_data is None:
            acwr_data = EstadisticasService.analizar_acwr(cliente)
        acwr = acwr_data.get('acwr_actual', 1.0)
        zona_riesgo = acwr_data.get('zona_riesgo', 'desconocida')

        if stats_globales is None:
            stats_globales = EstadisticasService.calcular_estadisticas_globales(cliente, rango='30d')
        rpe_medio = stats_globales.get('rpe_promedio', 0)

        if estancados is None:
            estancados = EstadisticasService.detectar_estancamientos(cliente)

        if equilibrio_data is None:
            equilibrio_data = EstadisticasService.analizar_equilibrio_muscular(cliente)
        ratios = equilibrio_data.get('tabla_ratios', [])

        if volumen_optimo_data is None:
            volumen_optimo_data = EstadisticasService.analizar_volumen_optimo(cliente, rango='30d')
        series_reales = volumen_optimo_data.get('series_reales', [])
        grupos = volumen_optimo_data.get('labels', [])
        min_series = volumen_optimo_data.get('min_recomendado', 10)
        max_series = volumen_optimo_data.get('max_recomendado', 20)

        # --- LÓGICA DE DECISIÓN HOLÍSTICA ---
        diagnosticos = []

        # A. Carga (ACWR)
        if zona_riesgo == 'riesgo_alto':
            diagnosticos.append(
                f"⚠️ <b>FATIGA CRÍTICA:</b> Tu ACWR ({acwr}) indica riesgo alto. ¡Prioriza el descanso!")
            estado, color, icono = 'riesgo', '#FF2D92', 'fas fa-skull-crossbones'
        elif zona_riesgo == 'cuidado':
            diagnosticos.append(f"⚠️ <b>PRECAUCIÓN:</b> Carga elevada ({acwr}). Vigila tu recuperación.")
            estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'
        else:
            diagnosticos.append(f"✅ <b>CARGA ÓPTIMA:</b> Ratio ACWR ({acwr}) en zona ideal.")
            estado, color, icono = 'optimo', '#00FF88', 'fas fa-check-circle'

        # B. Intensidad (RPE)
        if rpe_medio > 8.5:
            diagnosticos.append(f"🔥 <b>INTENSIDAD ALTA:</b> RPE medio de {rpe_medio}. Estás al límite.")
            if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'
        elif rpe_medio < 7.0:
            diagnosticos.append(f"📉 <b>INTENSIDAD BAJA:</b> RPE de {rpe_medio}. Tienes margen para subir carga.")
            if estado == 'optimo': estado, color, icono = 'baja', '#00D4FF', 'fas fa-arrow-up'

        # C. Estancamiento
        if estancados:
            diagnosticos.append(
                f"🛑 <b>ESTANCAMIENTO:</b> {len(estancados)} ejercicios sin progreso (ej: {estancados[0]['nombre']}).")
            if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'

        # D. Equilibrio Muscular
        for ratio in ratios:
            if ratio['nombre'] == 'Press Banca / Sentadilla' and (ratio['ratio'] < 0.5 or ratio['ratio'] > 0.7):
                diagnosticos.append(
                    f"⚖️ <b>DESEQUILIBRIO:</b> Ratio Banca/Sentadilla ({ratio['ratio']}) fuera de rango.")
                if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'
            elif ratio['nombre'] == 'Remo / Press Banca' and ratio['ratio'] < 1.0:
                diagnosticos.append(
                    f"⚖️ <b>DESEQUILIBRIO:</b> Tracción débil frente al empuje (Ratio: {ratio['ratio']}).")
                if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'

        # E. Volumen Óptimo
        for i, series in enumerate(series_reales):
            grupo = grupos[i]
            if series < min_series and series > 0:
                diagnosticos.append(f"📦 <b>VOLUMEN BAJO:</b> {grupo} necesita más series (actual: {series}).")
                if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'
            elif series > max_series:
                diagnosticos.append(f"📦 <b>SOBRECARGA:</b> Demasiado volumen en {grupo} ({series} series).")
                if estado == 'optimo': estado, color, icono = 'cuidado', '#FFB800', 'fas fa-exclamation-triangle'

        # Unir todos los diagnósticos con saltos de línea
        mensaje = "<br>".join(diagnosticos)

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
            'desequilibrios': len([d for d in diagnosticos if "⚖️" in d]),
            'volumen_problema': len([d for d in diagnosticos if "📦" in d])
        }

    @staticmethod
    def calcular_progresion_ejercicios(cliente, rango='30d'):
        """
        Calcula la progresión de peso/volumen por ejercicio
        """
        from entrenos.models import EjercicioRealizado
        from entrenos.utils.utils import normalizar_nombre_ejercicio

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        # Obtener ejercicios únicos de todas las fuentes
        nombres_manuales = list(EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values_list('nombre_ejercicio', flat=True).distinct())

        from entrenos.models import EjercicioLiftinDetallado
        nombres_liftin = list(EjercicioLiftinDetallado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values_list('nombre_ejercicio', flat=True).distinct())

        # 3. Series Nuevo Modelo
        from entrenos.models import SerieRealizada
        nombres_nuevos = list(SerieRealizada.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values_list('ejercicio__nombre', flat=True).distinct())

        # Normalizamos los nombres para agrupar correctamente
        ejercicios_nombres = list(set([normalizar_nombre_ejercicio(n).lower() for n in nombres_manuales + nombres_liftin + nombres_nuevos if n]))

        progresiones = []

        for nombre_ejercicio in ejercicios_nombres:
            # Buscar en todas las tablas por aproximación de nombre (case-insensitive) y unir resultados
            query_manual = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio__icontains=nombre_ejercicio,
                completado=True,
                entreno__fecha__gte=fecha_inicio
            ).values('entreno__fecha', 'peso_kg')

            query_liftin = EjercicioLiftinDetallado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio__icontains=nombre_ejercicio,
                completado=True,
                entreno__fecha__gte=fecha_inicio
            ).values('entreno__fecha', 'peso_kg')

            # Para el nuevo modelo, buscamos el peso máximo levantado de ese ejercicio en ese entreno
            query_nuevo = SerieRealizada.objects.filter(
                entreno__cliente=cliente,
                ejercicio__nombre__icontains=nombre_ejercicio,
                completado=True,
                entreno__fecha__gte=fecha_inicio
            ).values('entreno__fecha').annotate(
                peso_kg_max=Max('peso_kg')
            ).values('entreno__fecha', 'peso_kg_max')

            # Combinar y ordenar
            todos_registros = []
            todos_registros.extend([{'fecha': r['entreno__fecha'], 'peso_kg': r['peso_kg']} for r in query_manual])
            todos_registros.extend([{'fecha': r['entreno__fecha'], 'peso_kg': r['peso_kg']} for r in query_liftin])
            todos_registros.extend([{'fecha': r['entreno__fecha'], 'peso_kg': r['peso_kg_max']} for r in query_nuevo])

            # Filtramos nulos, ordenamos por fecha y nos quedamos con el máximo por día (para evitar duplicados por error)
            registros_validos = [r for r in todos_registros if r['peso_kg'] is not None and r['peso_kg'] > 0]
            if not registros_validos:
                continue
                
            registros_validos.sort(key=lambda x: x['fecha'])
            
            # Agrupar por fecha (quedándonos con el máximo de cada día)
            registros_por_fecha = {}
            for r in registros_validos:
                fecha = r['fecha']
                peso = Decimal(str(r['peso_kg']))
                if fecha not in registros_por_fecha or peso > registros_por_fecha[fecha]:
                     registros_por_fecha[fecha] = peso
                     
            registros_finales = [{'fecha': f, 'peso_kg': p} for f, p in sorted(registros_por_fecha.items())]

            if len(registros_finales) < 2:
                continue

            primer_ejercicio = registros_finales[0]
            ultimo_ejercicio = registros_finales[-1]

            peso_inicial = primer_ejercicio['peso_kg']
            peso_actual = ultimo_ejercicio['peso_kg']
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
                'nombre_ejercicio': nombre_ejercicio.title(),
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
        from entrenos.utils.utils import normalizar_nombre_ejercicio

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        # 1. Obtener ejercicios manuales
        ejs_manuales = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('nombre_ejercicio', 'grupo_muscular', 'peso_kg', 'series', 'repeticiones')

        # 2. Obtener ejercicios Liftin detallados
        from entrenos.models import EjercicioLiftinDetallado
        ejs_liftin = EjercicioLiftinDetallado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('nombre_ejercicio', 'peso_kg', 'series_realizadas', 'repeticiones_min', 'repeticiones_max')

        # 3. Series Nuevo Modelo
        from entrenos.models import SerieRealizada
        series_nuevas = SerieRealizada.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('ejercicio__nombre', 'peso_kg', 'repeticiones')

        # Procesar en Python para aplicar el mapeo
        volumen_por_grupo = {}

        def _obtener_grupo_robusto(nombre_crudo, grupo_db=None):
            nombre = normalizar_nombre_ejercicio(nombre_crudo).lower()
            if grupo_db:
                return grupo_db
            grupo = MAPEO_MUSCULAR_DYNAMIC.get(nombre)
            if not grupo:
                for ej_db, gr_db in MAPEO_MUSCULAR_DYNAMIC.items():
                    if ej_db in nombre or nombre in ej_db:
                        return gr_db
            return grupo or 'Otros'

        # Procesar Manuales
        for ej in ejs_manuales:
            grupo = _obtener_grupo_robusto(ej['nombre_ejercicio'], ej['grupo_muscular'])
            try:
                v = float(ej['peso_kg'] or 0) * int(ej['series'] or 1) * int(ej['repeticiones'] or 1)
                if v > 0: volumen_por_grupo[grupo] = volumen_por_grupo.get(grupo, 0) + v
            except: continue

        # Procesar Liftin
        for ej in ejs_liftin:
            grupo = _obtener_grupo_robusto(ej['nombre_ejercicio'])
            try:
                reps = (int(ej['repeticiones_min'] or 0) + int(ej['repeticiones_max'] or 0)) / 2 or int(ej['repeticiones_min'] or 1)
                v = float(ej['peso_kg'] or 0) * int(ej['series_realizadas'] or 1) * reps
                if v > 0: volumen_por_grupo[grupo] = volumen_por_grupo.get(grupo, 0) + v
            except: continue

        # Procesar Series Automáticas
        for serie in series_nuevas:
            grupo = _obtener_grupo_robusto(serie['ejercicio__nombre'])
            try:
                v = float(serie['peso_kg'] or 0) * int(serie['repeticiones'] or 1)
                if v > 0: volumen_por_grupo[grupo] = volumen_por_grupo.get(grupo, 0) + v
            except: continue

        datos_ordenados = sorted(volumen_por_grupo.items(), key=lambda x: x[1], reverse=True)

        return {
            'labels': [x[0] for x in datos_ordenados],
            'data': [float(round(x[1], 1)) for x in datos_ordenados]
        }

    @staticmethod
    def calcular_volumen_semanal(cliente, rango='30d'):
        """
        Calcula el volumen total por semana sumando todas las fuentes de datos
        """
        from entrenos.models import EntrenoRealizado, EjercicioRealizado, EjercicioLiftinDetallado
        
        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)
        hoy = timezone.now().date()
        
        # Estructura para agrupar por semana
        # Clave: Inicio de semana (Lunes), Valor: Volumen acumulado
        volumen_semanal = {}
        
        # Generar todas las semanas del rango para que no queden huecos
        semana_actual = fecha_inicio - timedelta(days=fecha_inicio.weekday())
        while semana_actual <= hoy:
            semana_str = semana_actual.strftime('%d %b')
            volumen_semanal[semana_str] = 0
            semana_actual += timedelta(days=7)

        # 1. Volumen de Entrenos (si tienen el campo calculado)
        entrenos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio
        )
        
        for e in entrenos:
            lunes = e.fecha - timedelta(days=e.fecha.weekday())
            semana_str = lunes.strftime('%d %b')
            if semana_str in volumen_semanal:
                volumen_semanal[semana_str] += float(e.volumen_total_kg or 0)

        # Si vol_total es 0, intentar sumar desde ejercicios individuales (fallback)
        # Esto es costoso, así que idealmente confiamos en EntrenoRealizado.volumen_total_kg
        # que se actualiza al guardar.

        return {
            'labels': list(volumen_semanal.keys()),
            'data': [round(v, 1) for v in volumen_semanal.values()]
        }

    @staticmethod
    def calcular_rpe_semanal(cliente, rango='30d'):
        """
        Calcula el RPE promedio semanal basado en sesiones y series
        """
        from entrenos.models import SesionEntrenamiento, SerieRealizada, EntrenoRealizado
        
        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)
        hoy = timezone.now().date()
        
        rpe_semanal = {}
        conteo_semanal = {}
        
        # Inicializar semanas
        semana_actual = fecha_inicio - timedelta(days=fecha_inicio.weekday())
        while semana_actual <= hoy:
            semana_str = semana_actual.strftime('%d %b')
            rpe_semanal[semana_str] = 0
            conteo_semanal[semana_str] = 0
            semana_actual += timedelta(days=7)
            
        # 1. RPE de Sesiones (Mejor fuente)
        sesiones = SesionEntrenamiento.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            rpe_medio__isnull=False
        ).select_related('entreno')

        entrenos_con_rpe_sesion = set()
        for s in sesiones:
            e = s.entreno
            lunes = e.fecha - timedelta(days=e.fecha.weekday())
            semana_str = lunes.strftime('%d %b')

            if semana_str in rpe_semanal:
                rpe_semanal[semana_str] += s.rpe_medio
                conteo_semanal[semana_str] += 1
                entrenos_con_rpe_sesion.add(e.id)

        # 2. RPE de Series individuales (Fallback: solo para entrenos sin SesionEntrenamiento con RPE)
        series = SerieRealizada.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            rpe_real__isnull=False
        ).exclude(
            entreno_id__in=entrenos_con_rpe_sesion
        ).select_related('entreno').values('entreno_id', 'entreno__fecha', 'rpe_real')

        # Agrupar por entreno para evitar que N series de un mismo entreno inflen el conteo
        rpe_por_entreno = {}
        fechas_por_entreno = {}
        for s in series:
            eid = s['entreno_id']
            rpe_por_entreno.setdefault(eid, []).append(s['rpe_real'])
            fechas_por_entreno[eid] = s['entreno__fecha']

        for eid, rpelist in rpe_por_entreno.items():
            fecha = fechas_por_entreno[eid]
            lunes = fecha - timedelta(days=fecha.weekday())
            semana_str = lunes.strftime('%d %b')
            if semana_str in rpe_semanal:
                rpe_semanal[semana_str] += sum(rpelist) / len(rpelist)
                conteo_semanal[semana_str] += 1
        
        # Calcular promedios
        data = []
        for semana_str in rpe_semanal.keys():
            total_rpe = rpe_semanal[semana_str]
            count = conteo_semanal[semana_str]
            if count > 0:
                data.append(round(total_rpe / count, 1))
            else:
                data.append(0) # O None para que no pinte
                
        return {
            'labels': list(rpe_semanal.keys()),
            'data': data
        }

    @staticmethod
    def obtener_fases_historicas(cliente, rango='30d'):
        """
        Devuelve la lista de fases correspondientes a cada semana del rango
        """
        from clientes.models import FaseCliente
        
        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)
        hoy = timezone.now().date()
        
        fases_semanales = []
        
        # Obtener todas las fases del cliente ordenadas por fecha
        fases_db = list(FaseCliente.objects.filter(cliente=cliente).order_by('fecha_inicio'))
        
        # Iterar por semanas
        semana_actual = fecha_inicio - timedelta(days=fecha_inicio.weekday())
        while semana_actual <= hoy:
            # Determinar fase activa en 'semana_actual'
            fase_encontrada = 'Mantenimiento' # Default
            
            # Buscar la fase más reciente que haya iniciado antes o en esta semana
            fase_obj = None
            for f in fases_db:
                if f.fecha_inicio <= semana_actual:
                    fase_obj = f
                else:
                    break
            
            if fase_obj:
                fase_encontrada = fase_obj.get_fase_display()
                
            fases_semanales.append(fase_encontrada)
            semana_actual += timedelta(days=7)
            
        return fases_semanales

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
        # NULL → 0 explícito antes de convertir a float para evitar NaN silenciosos
        df['volumen_total_kg'] = df['volumen_total_kg'].fillna(0).astype(float)

        df = df.groupby('fecha')['volumen_total_kg'].sum().reset_index()
        df['carga_diaria'] = df['volumen_total_kg'] / 1000

        idx = pd.date_range(start=fecha_inicio, end=fecha_fin)
        df = df.set_index('fecha').reindex(idx, fill_value=0)

        # min_periods=7 en la crónica: no mostramos ACWR hasta tener al menos 7 días
        # de historia crónica (evita valores disparados en las primeras semanas)
        df['carga_aguda'] = df['carga_diaria'].rolling(window=7, min_periods=1).mean()
        df['carga_cronica'] = df['carga_diaria'].rolling(window=28, min_periods=7).mean()
        df['acwr'] = (df['carga_aguda'] / df['carga_cronica']).fillna(0).replace([np.inf, -np.inf], 0)

        acwr_actual = round(df['acwr'].iloc[-1], 2) if not df.empty else 0

        # Detectar parón: si no hay carga en la ventana crónica excepto los últimos 7 días,
        # el ACWR sería artificialmente alto y no representativo de la fitness real del atleta.
        carga_cronica_sin_aguda = df['carga_diaria'].iloc[-28:-7].sum() if len(df) >= 28 else 0
        paron_activo = carga_cronica_sin_aguda == 0 and df['carga_diaria'].iloc[-7:].sum() > 0

        if paron_activo:
            zona_riesgo = 'reanudacion'
            acwr_actual = 0  # No mostramos un ratio inválido
        elif 0.8 <= acwr_actual <= 1.3:
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
            'paron_detectado': paron_activo,
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
    def analizar_volumen_optimo(cliente, rango='30d'):
        """
        Analiza si el volumen por grupo muscular está en el rango óptimo (10-20 series/semana)
        """
        from entrenos.models import EjercicioRealizado
        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        dias = (timezone.now().date() - fecha_inicio).days
        semanas_divisor = max(1, dias / 7.0)

        # 1. Series manuales (modelo antiguo)
        ejs_manuales = EjercicioRealizado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('nombre_ejercicio', 'series')

        # 2. Series Liftin
        from entrenos.models import EjercicioLiftinDetallado
        ejs_liftin = EjercicioLiftinDetallado.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('nombre_ejercicio', 'series_realizadas')

        # 3. Series Nuevo Modelo
        from entrenos.models import SerieRealizada
        series_nuevas = SerieRealizada.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio,
            completado=True
        ).values('ejercicio__nombre').annotate(
            total_series=Count('id')
        )

        series_por_grupo = {}
        ejercicios_no_mapeados = []  # Para tracking
        ejercicios_mapeados_detalle = []  # Para debugging detallado

        from entrenos.utils.utils import normalizar_nombre_ejercicio
        
        def _procesar_ejercicio(nombre_crudo, series_count, origen):
            nombre = normalizar_nombre_ejercicio(nombre_crudo).lower()
            grupo = MAPEO_MUSCULAR_DYNAMIC.get(nombre)
            
            # Intento secundario: buscar subcadenas si no hay coincidencia exacta
            if not grupo:
                for ej_db, gr_db in MAPEO_MUSCULAR_DYNAMIC.items():
                    if ej_db in nombre or nombre in ej_db:
                        grupo = gr_db
                        break
            
            grupo = grupo or 'Otros'
            
            if grupo == 'Otros':
                ejercicios_no_mapeados.append(nombre)
                logger.warning(f"[Cliente {cliente.id}] Ejercicio {origen} no mapeado: '{nombre}' (original: '{nombre_crudo}') - {series_count} series")
            else:
                ejercicios_mapeados_detalle.append(f"[{origen}] {nombre} -> {grupo} ({series_count} series)")
                
            series_por_grupo[grupo] = series_por_grupo.get(grupo, 0) + series_count

        for ej in ejs_manuales:
            _procesar_ejercicio(ej['nombre_ejercicio'], int(ej['series'] or 0), 'manual')

        for ej in ejs_liftin:
            _procesar_ejercicio(ej['nombre_ejercicio'], int(ej['series_realizadas'] or 0), 'liftin')

        for serie_agrupada in series_nuevas:
            _procesar_ejercicio(serie_agrupada['ejercicio__nombre'], serie_agrupada['total_series'], 'app_movil')

        # Log del resumen
        logger.info(f"[Cliente {cliente.id}] Rango: {rango}, Semanas: {semanas_divisor:.1f}")
        logger.info(f"[Cliente {cliente.id}] Series totales por grupo: {series_por_grupo}")
        logger.info(f"[Cliente {cliente.id}] Total ejercicios no mapeados: {len(set(ejercicios_no_mapeados))}")
        if ejercicios_no_mapeados:
            logger.info(f"[Cliente {cliente.id}] Ejercicios no mapeados únicos: {list(set(ejercicios_no_mapeados))}")
        
        # Log de primeros ejercicios mapeados para verificación
        if ejercicios_mapeados_detalle:
            logger.info(f"[Cliente {cliente.id}] Primeros 5 ejercicios mapeados: {ejercicios_mapeados_detalle[:5]}")

        grupos_principales = ['Pecho', 'Espalda', 'Cuádriceps', 'Isquios', 'Hombros', 'Glúteos', 'Bíceps', 'Tríceps']
        labels = []
        data_actual = []

        for grupo in grupos_principales:
            labels.append(grupo)
            total_series = series_por_grupo.get(grupo, 0)
            promedio_semanal = round(total_series / semanas_divisor, 1)
            data_actual.append(promedio_semanal)
            logger.debug(f"[Cliente {cliente.id}] {grupo}: {total_series} series totales / {semanas_divisor:.1f} semanas = {promedio_semanal} series/semana")

        return {
            'labels': labels,
            'series_reales': data_actual,
            'min_recomendado': 10,
            'max_recomendado': 20,
            'ejercicios_no_mapeados': list(set(ejercicios_no_mapeados))  # Para debugging
        }


    @staticmethod
    def analizar_intensidad_historica(cliente, rango='30d'):
        from entrenos.models import SesionEntrenamiento, EntrenoRealizado, EjercicioRealizado
        from django.db.models import Avg

        fecha_inicio = EstadisticasService._calcular_fecha_inicio(rango)

        intensidad = {'Baja (1-5)': 0, 'Moderada (6-7)': 0, 'Alta (8-9)': 0, 'Máxima (10)': 0}

        def _clasificar(val):
            if val is None:
                return
            if val <= 5:
                intensidad['Baja (1-5)'] += 1
            elif val <= 7.9:
                intensidad['Moderada (6-7)'] += 1
            elif val <= 9.5:
                intensidad['Alta (8-9)'] += 1
            else:
                intensidad['Máxima (10)'] += 1

        # 1. SesionEntrenamiento con rpe_medio (flujo antiguo)
        sesiones = SesionEntrenamiento.objects.filter(
            entreno__cliente=cliente,
            entreno__fecha__gte=fecha_inicio
        ).select_related('entreno')
        # Solo marcamos como "cubiertos" los entrenos con RPE real, no los que tienen rpe_medio=None
        entrenos_con_rpe_sesion = set()
        for s in sesiones:
            if s.rpe_medio is not None:
                entrenos_con_rpe_sesion.add(s.entreno_id)
                _clasificar(s.rpe_medio)

        # 2. EjercicioRealizado.rpe como fallback para entrenos sin RPE en SesionEntrenamiento
        # (flujo nuevo: guardar_entrenamiento_activo guarda RPE por ejercicio)
        entrenos_sin_sesion = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__gte=fecha_inicio
        ).exclude(id__in=entrenos_con_rpe_sesion).values_list('id', flat=True)

        rpe_por_entreno = (
            EjercicioRealizado.objects
            .filter(entreno_id__in=entrenos_sin_sesion, rpe__isnull=False)
            .values('entreno_id')
            .annotate(rpe_medio=Avg('rpe'))
        )
        for row in rpe_por_entreno:
            _clasificar(row['rpe_medio'])

        return {'labels': list(intensidad.keys()), 'data': list(intensidad.values())}

    @staticmethod
    def generar_predicciones_ia(cliente):
        from entrenos.models import EjercicioRealizado
        ejercicios_objetivo = ['Press Banca', 'Sentadilla', 'Peso Muerto']
        proyecciones = []
        for ej_nombre in ejercicios_objetivo:
            nombres_variaciones = [k for k, v in MAPEO_EJERCICIOS_A_PRINCIPAL.items() if v == ej_nombre]
            nombres_variaciones_extendidos = list(
                set(nombres_variaciones + [n.strip().title() for n in nombres_variaciones]))
            registros = EjercicioRealizado.objects.filter(entreno__cliente=cliente,
                                                          nombre_ejercicio__in=nombres_variaciones_extendidos,
                                                          peso_kg__gt=0, completado=True).order_by('entreno__fecha')
            if registros.count() < 3: continue
            marcas_diarias = {}
            for r in registros:
                fecha = r.entreno.fecha
                rm = float(r.peso_kg) * (1 + (r.repeticiones / 30))
                if fecha not in marcas_diarias or rm > marcas_diarias[fecha]: marcas_diarias[fecha] = rm
            fechas_ordenadas = sorted(marcas_diarias.keys())
            marcas = [marcas_diarias[f] for f in fechas_ordenadas]
            if len(marcas) < 3: continue
            actual, inicial = marcas[-1], marcas[0]
            dias = (fechas_ordenadas[-1] - fechas_ordenadas[0]).days or 1
            tasa_diaria = (actual - inicial) / dias
            proyecciones.append(
                {'nombre': ej_nombre, 'actual': round(actual, 1), 'p4_semanas': round(actual + (tasa_diaria * 28), 1),
                 'p8_semanas': round(actual + (tasa_diaria * 56), 1), 'confianza': min(95, 50 + (len(marcas) * 5))})
        return proyecciones

    @staticmethod
    def detectar_estancamientos(cliente):
        from entrenos.models import EjercicioRealizado
        nombres = EjercicioRealizado.objects.filter(entreno__cliente=cliente).values_list('nombre_ejercicio',
                                                                                          flat=True).distinct()
        estancados = []
        for nombre in nombres:
            registros = EjercicioRealizado.objects.filter(entreno__cliente=cliente, nombre_ejercicio=nombre,
                                                          completado=True).order_by('-entreno__fecha')[:4]
            if registros.count() < 3: continue
            volumenes = [float(r.peso_kg) * r.repeticiones * r.series for r in registros]
            ultimo, anteriores = volumenes[0], volumenes[1:]
            promedio_anterior = sum(anteriores) / len(anteriores)
            if ultimo <= promedio_anterior * 1.02:
                estancados.append({'nombre': nombre, 'ultimo_volumen': round(ultimo, 1), 'sesiones_estancado': 3})
        return sorted(estancados, key=lambda x: x['ultimo_volumen'], reverse=True)[:5]

    @staticmethod
    def calcular_1rm_estimado_por_ejercicio(cliente):
        from entrenos.models import EjercicioRealizado
        ejercicios = EjercicioRealizado.objects.filter(entreno__cliente=cliente, completado=True)
        one_rm_finales = {}
        for e in ejercicios:
            try:
                peso, reps = float(e.peso_kg or 0), int(e.repeticiones or 1)
                if peso > 0:
                    rm_estimado = peso * (1 + (reps / 30))
                    nombre_norm = e.nombre_ejercicio.lower().strip()
                    # Mapeo de variantes a ejercicio principal
                    ej_principal = MAPEO_EJERCICIOS_A_PRINCIPAL.get(nombre_norm) # Assuming MAPEO_EJERCICIOS_A_PRINCIPAL is the correct mapping
                    if not ej_principal:
                        try:
                            from entrenos.utils.auto_aprendizaje import clasificar_ejercicio_dinamico
                            ej_principal = clasificar_ejercicio_dinamico(e.nombre_ejercicio, default_return=nombre_norm.title())
                        except ImportError:
                            ej_principal = nombre_norm.title() # Fallback if dynamic classification is not available
                    
                    if ej_principal and (ej_principal not in one_rm_finales or rm_estimado > one_rm_finales[ej_principal]):
                        one_rm_finales[ej_principal] = rm_estimado
            except (ValueError, TypeError):
                continue
        return one_rm_finales

    @staticmethod
    def _calcular_fecha_inicio(rango):
        hoy = timezone.now().date()
        if rango == '30d':
            return hoy - timedelta(days=30)
        elif rango == '90d':
            return hoy - timedelta(days=90)
        elif rango == '180d':
            return hoy - timedelta(days=180)
        elif rango == 'todo':
            return datetime(2000, 1, 1).date()
        return hoy - timedelta(days=30)

    @staticmethod
    def obtener_mapeo_muscular_completo():
        """
        Retorna el glosario completo de ejercicios organizados por grupo muscular.
        """
        glosario = {}
        for ej, grupo in MAPEO_MUSCULAR_DYNAMIC.items():
            if grupo not in glosario:
                glosario[grupo] = []
            glosario[grupo].append(ej.title())

        # Ordenar grupos y ejercicios
        glosario_ordenado = {k: sorted(v) for k, v in sorted(glosario.items())}
        return glosario_ordenado
