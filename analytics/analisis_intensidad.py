# 🔥 DASHBOARD DE INTENSIDAD AVANZADO - VERSIÓN COMPLETA CORREGIDA
# Todos los métodos implementados para evitar errores
from entrenos.models import EjercicioRealizado
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Avg, Max, Min, Count
from datetime import datetime, timedelta, date
import json
import numpy as np
from entrenos.utils.utils import parse_reps_and_series
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from entrenos.models import EjercicioRealizado
from django.shortcuts import render, get_object_or_404
# ... (tus otras importaciones)
from django.utils import timezone  # <-- Asegúrate de que esta esté
import logging  # <-- Asegúrate de que esta esté

# --- DEFINICIÓN DEL LOGGER (¡ESTA ES LA LÍNEA CLAVE!) ---
# Coloca esto justo después de tus importaciones y antes de la clase.
logger = logging.getLogger(__name__)


class AnalisisIntensidadAvanzado:
    """
    Análisis avanzado de intensidad - VERSIÓN COMPLETA
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.zonas_fc = {
            'recuperacion': {'min': 50, 'max': 60},
            'aerobica': {'min': 60, 'max': 70},
            'umbral': {'min': 70, 'max': 80},
            'anaerobica': {'min': 80, 'max': 90}
        }

    def analizar_zonas_entrenamiento(self, periodo_dias=30):
        """
        Analiza distribución de zonas de entrenamiento usando EjercicioRealizado
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        entrenos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio
        ).prefetch_related('ejercicios_realizados')

        distribucion = {
            'recuperacion': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0},
            'aerobica': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0},
            'umbral': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0},
            'anaerobica': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0}
        }

        tiempo_total = 0

        for entreno in entrenos:
            duracion = entreno.duracion_minutos or 60
            tiempo_total += duracion

            intensidades = []
            for ej in entreno.ejercicios_realizados.all():
                reps = ej.repeticiones or 1
                # Estimar intensidad según repeticiones
                if reps <= 3:
                    intensidad = 90
                elif reps <= 6:
                    intensidad = 85
                elif reps <= 12:
                    intensidad = 75
                else:
                    intensidad = 60
                intensidades.append(intensidad)

            intensidad_prom = sum(intensidades) / len(intensidades) if intensidades else 70

            # Clasificar zona según intensidad promedio
            if intensidad_prom >= 85:
                zona = 'anaerobica'
            elif intensidad_prom >= 75:
                zona = 'umbral'
            elif intensidad_prom >= 65:
                zona = 'aerobica'
            else:
                zona = 'recuperacion'

            distribucion[zona]['tiempo'] += duracion
            distribucion[zona]['calorias'] += self._calcular_calorias_zona(zona, duracion)

        if tiempo_total > 0:
            for zona in distribucion:
                distribucion[zona]['porcentaje'] = round(
                    (distribucion[zona]['tiempo'] / tiempo_total) * 100, 1
                )

        recomendaciones = self._generar_recomendaciones_zonas(distribucion)

        return {
            'distribucion': distribucion,
            'tiempo_total': tiempo_total,
            'recomendaciones_zonas': recomendaciones
        }

    def analizar_carga_entrenamiento(self, periodo_dias=90):
        """
        Analiza carga semanal usando EjercicioRealizado
        Escalado calibrado para generar valores semanales realistas
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)
        entrenos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio
        ).prefetch_related('ejercicios_realizados')

        carga_semanal = {}
        semana_actual = fecha_inicio

        while semana_actual <= datetime.now().date():
            fin_semana = semana_actual + timedelta(days=6)

            entrenos_semana = [
                e for e in entrenos
                if semana_actual <= e.fecha <= fin_semana
            ]

            carga_total = 0
            sesiones = len(entrenos_semana)
            duracion_total = 0

            for entreno in entrenos_semana:
                duracion = entreno.duracion_minutos or 60
                duracion_total += duracion

                volumen = 0
                intensidades = []

                for ej in entreno.ejercicios_realizados.all():
                    peso = ej.peso_kg or 0
                    reps = ej.repeticiones or 1
                    series = ej.series or 1

                    volumen += peso * reps * series

                    # Estimar intensidad
                    if reps <= 3:
                        intensidad = 90
                    elif reps <= 6:
                        intensidad = 85
                    elif reps <= 12:
                        intensidad = 75
                    else:
                        intensidad = 60
                    intensidades.append(intensidad)

                intensidad_prom = sum(intensidades) / len(intensidades) if intensidades else 70

                # 🔧 ESCALADO AJUSTADO AQUÍ
                carga_entreno = (volumen * intensidad_prom * duracion) / 150000
                carga_total += carga_entreno

            semana_str = semana_actual.strftime('%Y-W%U')
            carga_semanal[semana_str] = {
                'carga_total': round(carga_total, 1),
                'sesiones': sesiones,
                'duracion_total': duracion_total,
                'carga_promedio': round(carga_total / sesiones, 1) if sesiones > 0 else 0
            }

            semana_actual += timedelta(days=7)

        cargas = [data['carga_total'] for data in carga_semanal.values()]
        tendencia = self._calcular_tendencia_carga(cargas)

        carga_promedio = sum(cargas) / len(cargas) if cargas else 0
        sesiones_promedio = sum(d['sesiones'] for d in carga_semanal.values()) / len(
            carga_semanal) if carga_semanal else 0
        duracion_promedio = sum(d['duracion_total'] for d in carga_semanal.values()) / len(
            carga_semanal) if carga_semanal else 0

        # 🔧 Recomendaciones calibradas
        recomendaciones = []
        if carga_promedio < 400:
            recomendaciones.append('Carga muy baja. Considera aumentar volumen o intensidad.')
        elif carga_promedio > 1400:
            recomendaciones.append('Carga muy alta. Monitorea signos de sobreentrenamiento.')

        if tendencia['direccion'] == 'subiendo' and tendencia['porcentaje'] > 20:
            recomendaciones.append('Incremento de carga muy rápido. Considera progresión más gradual.')
        elif tendencia['direccion'] == 'bajando' and tendencia['porcentaje'] > 15:
            recomendaciones.append('Reducción significativa de carga. Evalúa si es intencional.')

        if not recomendaciones:
            recomendaciones.append('Carga de entrenamiento en rango óptimo.')

        carga_semanal = {k: v for k, v in carga_semanal.items() if v['carga_total'] > 0}

        return {
            'carga_semanal': carga_semanal,
            'carga_promedio': round(carga_promedio, 1),
            'sesiones_promedio': round(sesiones_promedio, 1),
            'duracion_promedio': round(duracion_promedio, 1),
            'tendencia': tendencia,
            'recomendaciones_carga': recomendaciones
        }

    def analizar_distribucion_intensidades(self, periodo_dias=60):
        """
        Analiza distribución de intensidades por % 1RM usando EjercicioRealizado
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        ejercicios = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente,
            entreno__fecha__gte=fecha_inicio
        )

        distribucion = {
            'recuperacion': 0,  # 40-60% 1RM
            'hipertrofia': 0,  # 60-80% 1RM
            'fuerza': 0,  # 80-90% 1RM
            'potencia': 0  # 90-100% 1RM
        }

        total_series = 0

        for ej in ejercicios:
            try:
                peso = ej.peso_kg or 0
                reps = ej.repeticiones or 1
                series = ej.series or 1

                if peso > 0 and reps > 0:
                    rm_estimado = self._calcular_1rm(peso, reps)
                    intensidad_pct = (peso / rm_estimado) * 100 if rm_estimado > 0 else 50

                    zona = self._clasificar_intensidad(intensidad_pct)
                    distribucion[zona] += series
                    total_series += series

            except Exception as e:
                continue  # Si algún dato está mal, simplemente lo salta

        if total_series > 0:
            for zona in distribucion:
                distribucion[zona] = round((distribucion[zona] / total_series) * 100, 1)

        efectividad = self._evaluar_efectividad_rutina(distribucion)
        recomendaciones = self._generar_recomendaciones_intensidad(distribucion)

        return {
            'distribucion': distribucion,
            'total_series': total_series,
            'efectividad_rutina': efectividad,
            'recomendaciones_intensidad': recomendaciones
        }

    # Dentro de la clase AnalisisIntensidadAvanzado en el archivo analisis_intensidad.py

    # --- MÉTODO DE FATIGA CORREGIDO (reemplaza el existente) ---
    def calcular_fatiga_acumulada(self, periodo_dias=14):
        """
        Modelo definitivo: fatiga acumulada normalizada y estable,
        CON CÁLCULO DE RECUPERACIÓN HASTA EL DÍA DE HOY.
        """
        logger.info("--- INICIANDO CÁLCULO DE FATIGA (desde analisis_intensidad.py) ---")

        hoy = timezone.now().date()
        fecha_inicio_calculo = hoy - timedelta(days=periodo_dias)

        entrenos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio_calculo
        ).order_by('fecha').prefetch_related('ejercicios_realizados')

        fatiga_acumulada = 0.0
        ultimo_dia_entreno = None
        decay_factor = 0.75  # Recuperación diaria del 25%

        if entrenos.exists():
            # Iterar sobre los entrenamientos para calcular la fatiga acumulada
            dia_actual_loop = entrenos.first().fecha
            ultimo_dia_entreno = entrenos.last().fecha
            entrenos_por_dia = {e.fecha: e for e in entrenos}

            while dia_actual_loop <= ultimo_dia_entreno:
                # Aplicar decaimiento diario
                fatiga_acumulada *= decay_factor

                # Si hubo entreno este día, añadir la carga
                if dia_actual_loop in entrenos_por_dia:
                    entreno_del_dia = entrenos_por_dia[dia_actual_loop]

                    # Reutilizamos la lógica de cálculo de carga del entreno
                    volumen = 0
                    intensidades = []
                    for ej in entreno_del_dia.ejercicios_realizados.all():
                        peso = ej.peso_kg or 0
                        reps = ej.repeticiones or 1
                        series = ej.series or 1
                        volumen += peso * reps * series
                        if reps <= 3:
                            intensidad = 90
                        elif reps <= 6:
                            intensidad = 85
                        elif reps <= 12:
                            intensidad = 75
                        else:
                            intensidad = 60
                        intensidades.append(intensidad)

                    intensidad_prom = sum(intensidades) / len(intensidades) if intensidades else 70
                    duracion = entreno_del_dia.duracion_minutos or 60

                    carga_dia = (volumen * intensidad_prom * duracion) / 2500000
                    carga_dia = max(carga_dia, 10)

                    fatiga_acumulada += carga_dia

                dia_actual_loop += timedelta(days=1)

        # --- BLOQUE CLAVE CORREGIDO ---
        # Aplicar el decaimiento desde el último día de entreno hasta HOY
        if ultimo_dia_entreno and hoy > ultimo_dia_entreno:
            dias_de_recuperacion_adicional = (hoy - ultimo_dia_entreno).days
            logger.info(
                f"Último entreno fue el {ultimo_dia_entreno}. Aplicando {dias_de_recuperacion_adicional} días de recuperación adicional.")
            fatiga_acumulada *= (decay_factor ** dias_de_recuperacion_adicional)
        elif not ultimo_dia_entreno:
            fatiga_acumulada = 0  # Si no hay entrenos, la fatiga es cero.

        logger.info(f"Fatiga calculada final: {fatiga_acumulada:.2f}")

        nivel_fatiga = self._evaluar_nivel_fatiga(fatiga_acumulada)
        dias_recuperacion = self._calcular_dias_recuperacion(fatiga_acumulada)
        recomendacion = self._generar_recomendacion_descanso(nivel_fatiga, dias_recuperacion)

        return {
            'fatiga_diaria': [],  # Ya no es necesario para el display
            'fatiga_actual': round(fatiga_acumulada, 1),
            'nivel': nivel_fatiga,
            'dias_recuperacion': dias_recuperacion,
            'recomendacion_descanso': recomendacion
        }

    # ============================================================================
    # MÉTODOS AUXILIARES IMPLEMENTADOS
    # ============================================================================

    def _estimar_zona_entrenamiento(self, entreno):
        """
        Estima zona de entrenamiento basada en características del entreno
        """
        duracion = entreno.duracion_minutos or 60

        if entreno.notas_liftin:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)
            intensidad_promedio = self._calcular_intensidad_promedio(ejercicios)

            if intensidad_promedio >= 85:
                return 'anaerobica'
            elif intensidad_promedio >= 75:
                return 'umbral'
            elif intensidad_promedio >= 65:
                return 'aerobica'
            else:
                return 'recuperacion'

        # Estimación basada en duración si no hay datos
        if duracion <= 30:
            return 'anaerobica'
        elif duracion <= 60:
            return 'umbral'
        elif duracion <= 90:
            return 'aerobica'
        else:
            return 'recuperacion'

    def _calcular_calorias_zona(self, zona, duracion_minutos):
        """
        Calcula calorías quemadas por zona
        """
        calorias_por_minuto = {
            'recuperacion': 4,  # 4 cal/min
            'aerobica': 5,  # 5 cal/min
            'umbral': 6,  # 6 cal/min
            'anaerobica': 8  # 8 cal/min
        }

        return duracion_minutos * calorias_por_minuto.get(zona, 5)

    def _generar_recomendaciones_zonas(self, distribucion):
        """
        Genera recomendaciones basadas en distribución de zonas
        """
        recomendaciones = []

        # Verificar distribución óptima
        if distribucion['recuperacion']['porcentaje'] < 10:
            recomendaciones.append('Aumenta el tiempo en zona de recuperación para mejor adaptación')

        if distribucion['aerobica']['porcentaje'] < 30:
            recomendaciones.append('Incrementa el trabajo aeróbico para mejorar la base cardiovascular')

        if distribucion['anaerobica']['porcentaje'] > 25:
            recomendaciones.append('Reduce el tiempo en zona anaeróbica para evitar sobreentrenamiento')

        if not recomendaciones:
            recomendaciones.append('Distribución de zonas óptima, mantén el enfoque actual')

        return recomendaciones

    def _calcular_volumen_entreno(self, ejercicios):
        """
        Calcula volumen total de un entrenamiento
        """
        volumen_total = 0

        for ejercicio in ejercicios:
            try:
                peso = float(ejercicio.get('peso', 0)) if ejercicio.get('peso') != 'PC' else 0
                reps = self._extraer_repeticiones(ejercicio.get('repeticiones', '1'))
                series = self._extraer_series(ejercicio.get('repeticiones', '1'))

                volumen_total += peso * series * reps
            except (ValueError, TypeError):
                continue

        return volumen_total

    def _estimar_intensidad_entreno(self, ejercicios):
        """
        Estima intensidad promedio de un entrenamiento
        """
        intensidades = []

        for ejercicio in ejercicios:
            try:
                peso = float(ejercicio.get('peso', 0)) if ejercicio.get('peso') != 'PC' else 0
                reps = self._extraer_repeticiones(ejercicio.get('repeticiones', '1'))

                if peso > 0 and reps > 0:
                    # Estimar intensidad basada en repeticiones
                    if reps <= 3:
                        intensidad = 90  # Fuerza máxima
                    elif reps <= 6:
                        intensidad = 85  # Fuerza
                    elif reps <= 12:
                        intensidad = 75  # Hipertrofia
                    else:
                        intensidad = 60  # Resistencia

                    intensidades.append(intensidad)
            except (ValueError, TypeError):
                continue

        return sum(intensidades) / len(intensidades) if intensidades else 70

    def _calcular_tendencia_carga(self, cargas):
        """
        Calcula tendencia de carga
        """
        if len(cargas) < 2:
            return {'direccion': 'estable', 'porcentaje': 0}

        primera_mitad = cargas[:len(cargas) // 2]
        segunda_mitad = cargas[len(cargas) // 2:]

        promedio_inicial = sum(primera_mitad) / len(primera_mitad)
        promedio_final = sum(segunda_mitad) / len(segunda_mitad)

        if promedio_inicial > 0:
            cambio_porcentual = ((promedio_final - promedio_inicial) / promedio_inicial) * 100

            if cambio_porcentual > 5:
                direccion = 'subiendo'
            elif cambio_porcentual < -5:
                direccion = 'bajando'
            else:
                direccion = 'estable'

            return {
                'direccion': direccion,
                'porcentaje': round(abs(cambio_porcentual), 1)
            }

        return {'direccion': 'estable', 'porcentaje': 0}

    # En analisis_intensidad.py, dentro de la clase AnalisisIntensidadAvanzado

    def _generar_recomendaciones_carga(self, carga_promedio, tendencia):
        """
        Genera recomendaciones de carga - VERSIÓN CON UMBRALES CALIBRADOS.
        """
        recomendaciones = []

        UMBRAL_BAJO = 200
        UMBRAL_ALTO = 1200

        if carga_promedio < UMBRAL_BAJO:
            recomendaciones.append(
                f'Tu carga promedio ({int(carga_promedio)}) es baja. Para progresar, considera aumentar gradualmente el volumen o la intensidad.')
        elif carga_promedio > UMBRAL_ALTO:
            recomendaciones.append(
                f'Tu carga promedio ({int(carga_promedio)}) es muy alta. Asegúrate de priorizar la recuperación y monitorear signos de sobreentrenamiento.')

        if tendencia['direccion'] == 'subiendo' and tendencia['porcentaje'] > 25:
            recomendaciones.append(
                'Tu carga está aumentando muy rápido. Una progresión más gradual puede ser más sostenible y segura.')
        elif tendencia['direccion'] == 'bajando' and tendencia['porcentaje'] > 20:
            recomendaciones.append(
                'Hemos detectado una reducción significativa en tu carga. Asegúrate de que sea una descarga planificada y no una falta de consistencia.')

        if not recomendaciones:
            if tendencia['direccion'] == 'subiendo':
                recomendaciones.append(
                    '¡Excelente! Tu carga de entrenamiento muestra una tendencia progresiva y sostenible. Sigue así.')
            else:
                recomendaciones.append(
                    'Tu carga de entrenamiento se mantiene en un rango estable y óptimo. Buen trabajo de mantenimiento.')

        return recomendaciones

    def _calcular_1rm(self, peso, reps):
        """
        Calcula 1RM usando fórmula de Brzycki
        """
        if reps <= 12:
            return peso / (1.0278 - 0.0278 * reps)
        return peso * 1.3  # Estimación para altas repeticiones

    def _clasificar_intensidad(self, intensidad_pct):
        """
        Clasifica intensidad por % 1RM
        """
        if intensidad_pct >= 90:
            return 'potencia'
        elif intensidad_pct >= 80:
            return 'fuerza'
        elif intensidad_pct >= 60:
            return 'hipertrofia'
        else:
            return 'recuperacion'

    def _evaluar_efectividad_rutina(self, distribucion):
        """
        Evalúa efectividad de la rutina basada en distribución
        """
        # Distribución óptima para hipertrofia/fuerza general
        if (distribucion['hipertrofia'] >= 50 and
                distribucion['fuerza'] >= 20 and
                distribucion['recuperacion'] >= 10):
            return 'Rutina muy efectiva para hipertrofia y fuerza'
        elif distribucion['hipertrofia'] >= 40:
            return 'Rutina efectiva, considera agregar más trabajo de fuerza'
        else:
            return 'Rutina necesita ajustes en distribución de intensidades'

    def _generar_recomendaciones_intensidad(self, distribucion):
        """
        Genera recomendaciones de intensidad
        """
        recomendaciones = []

        if distribucion['hipertrofia'] < 40:
            recomendaciones.append('Aumenta el trabajo en rango de hipertrofia (60-80% 1RM)')

        if distribucion['fuerza'] < 15:
            recomendaciones.append('Incluye más trabajo de fuerza (80-90% 1RM)')

        if distribucion['recuperacion'] < 5:
            recomendaciones.append('Agrega series de recuperación activa (40-60% 1RM)')

        if distribucion['potencia'] > 10:
            recomendaciones.append('Reduce el trabajo de potencia para evitar fatiga excesiva')

        if not recomendaciones:
            recomendaciones.append('Distribución de intensidades óptima')

        return recomendaciones

    def _calcular_carga_dia(self, entreno):
        """
        Calcula carga de entrenamiento de un día
        """
        if not entreno.notas_liftin:
            return 50  # Carga base estimada

        ejercicios = parsear_ejercicios(entreno.notas_liftin)
        volumen = self._calcular_volumen_entreno(ejercicios)
        intensidad = self._estimar_intensidad_entreno(ejercicios)
        duracion = entreno.duracion_minutos or 60

        # Fórmula de carga: (Volumen × Intensidad × Duración) / 1000
        carga = (volumen * intensidad * duracion) / 10000

        return max(carga, 10)  # Mínimo 10 puntos de carga

    def _evaluar_nivel_fatiga(self, fatiga_actual):
        """
        Evalúa nivel de fatiga actual
        """
        if fatiga_actual < 40:
            return 'baja'
        elif fatiga_actual < 90:
            return 'moderada'
        elif fatiga_actual < 190:
            return 'alta'
        else:
            return 'critica'

    def _calcular_dias_recuperacion(self, fatiga_actual):
        """
        Calcula días de recuperación necesarios
        """
        if fatiga_actual < 50:
            return 1
        elif fatiga_actual < 100:
            return 2
        elif fatiga_actual < 150:
            return 3
        else:
            return 5

    def _generar_recomendacion_descanso(self, nivel_fatiga, dias_recuperacion):
        """
        Genera recomendación de descanso
        """
        recomendaciones = {
            'baja': 'Fatiga baja. Puedes continuar con el entrenamiento normal.',
            'moderada': f'Fatiga moderada. Considera {dias_recuperacion} días de entrenamiento ligero.',
            'alta': f'Fatiga alta. Toma {dias_recuperacion} días de descanso activo o completo.',
            'critica': f'Fatiga crítica. Descanso obligatorio de {dias_recuperacion} días mínimo.'
        }

        return recomendaciones.get(nivel_fatiga, 'Evalúa tu estado de recuperación.')

    def _calcular_intensidad_promedio(self, ejercicios):
        """
        Calcula intensidad promedio de una lista de ejercicios
        """
        intensidades = []

        for ejercicio in ejercicios:
            try:
                reps = self._extraer_repeticiones(ejercicio.get('repeticiones', '1'))

                # Estimar intensidad basada en repeticiones
                if reps <= 3:
                    intensidad = 90
                elif reps <= 6:
                    intensidad = 85
                elif reps <= 12:
                    intensidad = 75
                else:
                    intensidad = 60

                intensidades.append(intensidad)
            except (ValueError, TypeError):
                continue

        return sum(intensidades) / len(intensidades) if intensidades else 70

    def _extraer_repeticiones(self, rep_str):
        """
        Extrae número de repeticiones de string como "3x8"
        """
        try:
            rep_str = str(rep_str).lower().replace('×', 'x').replace(' ', '')
            if 'x' in rep_str:
                return int(rep_str.split('x')[1])
            return int(rep_str)
        except:
            return 1

    def _extraer_series(self, rep_str):
        """
        Extrae número de series de string como "3x8"
        """
        try:
            rep_str = str(rep_str).lower().replace('×', 'x').replace(' ', '')
            if 'x' in rep_str:
                return int(rep_str.split('x')[0])
            return 1
        except:
            return 1


def convertir_fechas(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convertir_fechas(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convertir_fechas(i) for i in obj]
    return obj


# Vista para el Dashboard de Intensidad Avanzado
# En tu archivo: analisis_intensidad.py

# ... (tus importaciones y la clase AnalisisIntensidadAvanzado deben estar antes) ...

def dashboard_intensidad_avanzado(request, cliente_id):
    """
    Vista principal del Dashboard de Intensidad Avanzado
    - VERSIÓN COMPLETA CON DEPURACIÓN VISUAL INTEGRADA -
    """
    # 1. Obtener objetos principales
    cliente = get_object_or_404(Cliente, id=cliente_id)
    analizador = AnalisisIntensidadAvanzado(cliente)

    # 2. Obtener parámetros de la URL
    periodo = int(request.GET.get('periodo', 30))

    # 3. Realizar todos los análisis llamando a los métodos de la clase
    zonas_entrenamiento = analizador.analizar_zonas_entrenamiento(periodo)
    analisis_carga = analizador.analizar_carga_entrenamiento(90)
    distribucion_intensidades = analizador.analizar_distribucion_intensidades(60)
    fatiga_acumulada = analizador.calcular_fatiga_acumulada(14)

    # 4. Preparar datos para los gráficos de JavaScript
    # (Esta sección es para Chart.js y parece correcta)
    zonas_distribucion = zonas_entrenamiento['distribucion']
    zonas_labels = [zona.capitalize() for zona in zonas_distribucion.keys()]
    zonas_valores = [zonas_distribucion[z]['porcentaje'] for z in zonas_distribucion]
    zonas_colores = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']

    zonas_chart_data = {
        'labels': zonas_labels,
        'valores': zonas_valores,
        'colores': zonas_colores
    }

    # ==================================================================
    # INICIO DEL BLOQUE DE DEPURACIÓN
    # ==================================================================

    # Extraemos los valores clave que queremos depurar
    carga_promedio_debug = analisis_carga.get('carga_promedio', 'NO ENCONTRADO')
    tendencia_debug = analisis_carga.get('tendencia', 'NO ENCONTRADA')

    # Volvemos a llamar al método de recomendaciones para estar 100% seguros
    # de que estamos viendo lo que genera la lógica más reciente.
    recomendaciones_generadas_debug = analizador._generar_recomendaciones_carga(carga_promedio_debug, tendencia_debug)

    # Creamos el diccionario de depuración que pasaremos al template
    debug_info = {
        'carga_promedio': carga_promedio_debug,
        'tendencia': tendencia_debug,
        'recomendaciones_generadas': recomendaciones_generadas_debug
    }

    # ==================================================================
    # FIN DEL BLOQUE DE DEPURACIÓN
    # ==================================================================

    # 5. Construir el contexto final para el template
    context = {
        'cliente': cliente,
        'periodo': periodo,
        'zonas_entrenamiento': zonas_entrenamiento,
        'analisis_carga': analisis_carga,
        'distribucion_intensidades': distribucion_intensidades,
        'fatiga_acumulada': fatiga_acumulada,

        # Pasamos los datos para los gráficos
        'datos_graficos': json.dumps(convertir_fechas({
            'zonas': zonas_chart_data,
            'carga': analisis_carga,
            'intensidades': distribucion_intensidades
        })),

        # ¡Añadimos nuestro diccionario de depuración al contexto!
        'debug_info': debug_info
    }

    # 6. Renderizar la página
    return render(request, 'analytics/intensidad_avanzado.html', context)
