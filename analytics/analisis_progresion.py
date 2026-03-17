# Archivo: analytics/analisis_progresion.py (VERSIÓN COMPLETA Y FUNCIONAL)

from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from datetime import datetime, timedelta
import json
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from .calculators import CalculadoraEjerciciosTabla
import numpy as np  # Necesario para la compatibilidad de tipos en la tendencia


class AnalisisProgresionAvanzado:
    """
    Análisis avanzado de progresión - VERSIÓN FINAL, COMPLETA Y FUNCIONAL
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.calculadora = CalculadoraEjerciciosTabla(cliente)

        self.mapeo_nombres_canonicos = {
            'Press banca': ['press banca con barra', 'press banca con mancuernas'],
            'Sentadilla': ['sentadilla trasera con barra', 'sentadilla frontal con barra', 'sentadilla',
                           'sentadilla libre'],
            'Peso muerto': ['peso muerto', 'peso muerto rumano', 'peso muerto sumo'],
            'Press militar': ['press militar con barra (de pie)', 'press militar con mancuernas (sentado)',
                              'push press'],
            'Remo': ['remo con barra (pendlay)', 'remo con mancuerna a una mano', 'remo en polea baja (gironda)'],
            'Dominadas': ['dominadas (con lastre)', 'jalón al pecho'],
            'Press inclinado': ['press inclinado con barra', 'press inclinado con mancuernas', 'press inclinado']
        }

        self._mapeo_inverso = {}
        for nombre_canonico, variantes in self.mapeo_nombres_canonicos.items():
            for variante in variantes:
                self._mapeo_inverso[variante.lower()] = nombre_canonico

    def _normalizar_nombre(self, nombre_ejercicio):
        if not nombre_ejercicio: return "Desconocido"
        return self._mapeo_inverso.get(nombre_ejercicio.lower().strip(), nombre_ejercicio.title())

    def _obtener_1rm_canonicos(self):
        rms_originales = self.calculadora.calcular_1rm_estimado_por_ejercicio()
        rms_canonicos = {}
        for nombre_original, rm_valor in rms_originales.items():
            nombre_canonico = self._normalizar_nombre(nombre_original)
            if nombre_canonico not in rms_canonicos or rm_valor > rms_canonicos[nombre_canonico]:
                rms_canonicos[nombre_canonico] = rm_valor
        return rms_canonicos

    # En la clase AnalisisProgresionAvanzado

    def calcular_ratios_fuerza(self):
        """Calcula los ratios usando los 1RM canónicos agrupados y con lógica de respaldo."""
        rms = self._obtener_1rm_canonicos()

        banca_rm = rms.get('Press banca', 0)
        if banca_rm == 0:
            banca_rm = rms.get('Press inclinado', 0)

        sentadilla_rm = rms.get('Sentadilla', 0)
        muerto_rm = rms.get('Peso muerto', 0)
        militar_rm = rms.get('Press militar', 0)
        dominadas_rm = rms.get('Dominadas', 0)
        remo_rm = rms.get('Remo', 0)

        ratios = {
            'Press Banca / Sentadilla': self._calcular_ratio(banca_rm, sentadilla_rm),
            'Peso Muerto / Sentadilla': self._calcular_ratio(muerto_rm, sentadilla_rm),
            'Press Militar / Press Banca': self._calcular_ratio(militar_rm, banca_rm),
            'Dominadas / Remo': self._calcular_ratio(dominadas_rm, remo_rm)
        }

        estandares = {
            'Press Banca / Sentadilla': {'optimo': 0.75, 'rango': (0.65, 0.85)},
            'Peso Muerto / Sentadilla': {'optimo': 1.25, 'rango': (1.15, 1.35)},
            'Press Militar / Press Banca': {'optimo': 0.65, 'rango': (0.55, 0.75)},
            'Dominadas / Remo': {'optimo': 1.0, 'rango': (0.85, 1.15)}
        }

        analisis_ratios = []
        for nombre_ratio, valor in ratios.items():
            if valor > 0:
                estandar = estandares[nombre_ratio]
                estado = self._evaluar_ratio(valor, estandar)

                # ======================================================================
                # ### CORRECCIÓN FINAL ###
                # Generamos una clave simple y robusta, sin barras.
                # ======================================================================
                clave_recomendacion = nombre_ratio.lower().replace(' / ', '_')

                analisis_ratios.append({
                    'nombre': nombre_ratio, 'valor': f"{valor:.2f}", 'optimo': estandar['optimo'],
                    'estado': estado, 'recomendacion': self._generar_recomendacion_ratio(clave_recomendacion, estado)
                })

        return {
            'ratios': analisis_ratios,
            'grafico_radar': self._generar_datos_radar(analisis_ratios),
            'puntos_debiles': self._identificar_puntos_debiles(analisis_ratios)
        }

    def analisis_evolucion_temporal(self, ejercicio=None, periodo_dias=90):
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        # Obtenemos todos los ejercicios del periodo y los agrupamos por nombre canónico
        ejercicios_del_periodo = self.calculadora.obtener_ejercicios_tabla(fecha_inicio=fecha_inicio)
        ejercicios_agrupados = {}
        for ej in ejercicios_del_periodo:
            nombre_norm = self._normalizar_nombre(ej['nombre'])
            if nombre_norm not in ejercicios_agrupados:
                ejercicios_agrupados[nombre_norm] = []
            ejercicios_agrupados[nombre_norm].append(ej)

        # Si se selecciona un ejercicio, filtramos, si no, los procesamos todos
        ejercicios_a_procesar = ejercicios_agrupados
        if ejercicio:
            ejercicios_a_procesar = {ejercicio: ejercicios_agrupados.get(ejercicio, [])}

        resultados = {}
        for nombre_norm, lista_ejercicios in ejercicios_a_procesar.items():
            if not lista_ejercicios: continue

            # Ordenamos los ejercicios por fecha para el análisis temporal
            lista_ejercicios.sort(key=lambda x: x['fecha'])

            datos_temporales = []
            for e in lista_ejercicios:
                try:
                    peso = float(e.get('peso', 0))
                    reps = int(e.get('repeticiones', 1))
                    series = int(e.get('series', 1))
                    volumen = peso * reps * series
                    datos_temporales.append({
                        'fecha': e['fecha'].strftime('%Y-%m-%d'), 'peso': peso,
                        'repeticiones': reps, 'series': series, 'volumen': volumen
                    })
                except (ValueError, TypeError):
                    continue

            if datos_temporales:
                tendencia = self._calcular_tendencia_lineal(datos_temporales)
                resultados[nombre_norm] = {
                    'datos': datos_temporales,
                    'tendencia': tendencia,
                    'volumen_por_grupo': sum(d['volumen'] for d in datos_temporales),
                    'hitos': self._detectar_hitos(datos_temporales),
                    'predicciones': self._generar_predicciones_temporales(datos_temporales, tendencia)
                }
        return resultados

    def analisis_mesociclos(self, periodo_dias=180):
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)
        mesociclos = self._dividir_en_mesociclos(fecha_inicio, 28)
        analisis_mesociclos = []
        for i, (inicio, fin) in enumerate(mesociclos):
            datos_mesociclo = self._analizar_mesociclo(inicio, fin)
            if i > 0:
                mesociclo_anterior = analisis_mesociclos[i - 1]['datos']
                datos_mesociclo['comparativa'] = self._comparar_mesociclos(datos_mesociclo, mesociclo_anterior)
            analisis_mesociclos.append({
                'numero': i + 1, 'fecha_inicio': inicio, 'fecha_fin': fin,
                'datos': datos_mesociclo,
                'efectividad': self._evaluar_efectividad_mesociclo(datos_mesociclo),
                'recomendaciones': self._generar_recomendaciones_mesociclo(datos_mesociclo)
            })
        return {
            'mesociclos': analisis_mesociclos,
            'periodizacion_optima': self._sugerir_periodizacion_optima(analisis_mesociclos)
        }

    def obtener_ejercicios_registrados(self, dias=180):
        fecha_limite = datetime.now().date() - timedelta(days=dias)
        ejercicios = (
            EjercicioRealizado.objects
            .filter(entreno__cliente=self.cliente, entreno__fecha__gte=fecha_limite)
            .values_list('nombre_ejercicio', flat=True)
            .distinct()
        )
        ejercicios_normalizados = sorted(list(set(self._normalizar_nombre(e) for e in ejercicios)))
        return {e: e for e in ejercicios_normalizados}

    # --- MÉTODOS AUXILIARES ---
    def _calcular_ratio(self, v1, v2):
        return round(v1 / v2, 2) if v1 > 0 and v2 > 0 else 0

    def _evaluar_ratio(self, v, std):
        return 'optimo' if std['rango'][0] <= v <= std['rango'][1] else ('bajo' if v < std['rango'][0] else 'alto')

    def _generar_datos_radar(self, ratios):
        return {'labels': [r['nombre'] for r in ratios], 'valores': [float(r['valor']) for r in ratios],
                'optimos': [r['optimo'] for r in ratios]}

    def _identificar_puntos_debiles(self, ratios):
        return [f"**{r['nombre']} (ratio: {r['valor']})**: {r['recomendacion']}" for r in ratios if
                r['estado'] != 'optimo']

    # En la clase AnalisisProgresionAvanzado

    def _generar_recomendacion_ratio(self, ratio_name, estado):
        # ======================================================================
        # ### CORRECCIÓN FINAL ###
        # El diccionario ahora usa las claves simples y robustas.
        # ======================================================================
        recomendaciones_map = {
            'press_banca_sentadilla': {
                'bajo': 'Tu empuje de torso está descompensado. Prioriza el volumen en Press Banca.',
                'alto': 'Tu tren inferior necesita más atención. Aumenta el volumen en Sentadillas.',
                'optimo': 'Excelente equilibrio torso/pierna.'
            },
            'peso_muerto_sentadilla': {
                'bajo': 'Tu cadena posterior es débil. Enfócate en mejorar tu Peso Muerto.',
                'alto': 'Fuerza de tracción dominante. No descuides las Sentadillas.',
                'optimo': 'Balance ideal cadena posterior/anterior.'
            },
            'press_militar_press_banca': {
                'bajo': 'La fuerza de tus hombros está por detrás. Incrementa el volumen en Press Militar.',
                'alto': 'Hombros dominantes. Asegúrate de progresar también en Press Banca.',
                'optimo': 'Buen equilibrio de empuje horizontal/vertical.'
            },
            'dominadas_remo': {
                'bajo': 'Tu tracción vertical necesita mejorar. Prioriza las Dominadas.',
                'alto': 'Tracción horizontal dominante. No descuides las Dominadas.',
                'optimo': 'Excelente balance en la espalda.'
            }
        }
        return recomendaciones_map.get(ratio_name, {}).get(estado, 'Analiza este ratio.')

    def _calcular_tendencia_lineal(self, datos):
        if len(datos) < 2: return None
        try:
            from scipy import stats
            fechas_num = [
                (datetime.strptime(d['fecha'], '%Y-%m-%d') - datetime.strptime(datos[0]['fecha'], '%Y-%m-%d')).days for
                d in datos]
            pesos = [d['peso'] for d in datos]
            slope, intercept, r_value, p_value, std_err = stats.linregress(fechas_num, pesos)
            return {'tendencia_semanal': round(slope * 7, 2), 'confianza': round(abs(r_value) * 100, 1)}
        except (ImportError, ValueError):
            return None

    def _detectar_hitos(self, datos):
        if not datos: return []
        hitos, peso_max = [], 0
        for d in datos:
            if d['peso'] > peso_max:
                peso_max = d['peso']
                hitos.append(
                    {'tipo': 'record_personal', 'fecha': d['fecha'], 'descripcion': f'Nuevo récord: {peso_max} kg'})
        return hitos

    def _generar_predicciones_temporales(self, datos, tendencia):
        if not tendencia or len(datos) < 2: return []
        predicciones, ultimo_dato = [], datos[-1]
        fecha_base = datetime.strptime(ultimo_dato['fecha'], '%Y-%m-%d')
        for semanas in [4, 8, 12]:
            peso_predicho = ultimo_dato['peso'] + (tendencia['tendencia_semanal'] * semanas)
            confianza = max(tendencia.get('confianza', 75) - (semanas * 4), 30)
            predicciones.append({
                'fecha': (fecha_base + timedelta(weeks=semanas)).strftime('%Y-%m-%d'),
                'semanas': semanas, 'confianza': round(confianza, 1),
                'peso_estimado': round(peso_predicho, 1)
            })
        return predicciones

    def _dividir_en_mesociclos(self, fecha_inicio, dias_por_ciclo):
        mesociclos, fecha_actual = [], fecha_inicio
        fecha_fin_total = datetime.now().date()
        while fecha_actual < fecha_fin_total:
            fecha_fin_ciclo = fecha_actual + timedelta(days=dias_por_ciclo)
            mesociclos.append((fecha_actual, min(fecha_fin_ciclo, fecha_fin_total)))
            fecha_actual = fecha_fin_ciclo + timedelta(days=1)
        return mesociclos

    def _analizar_mesociclo(self, fecha_inicio, fecha_fin):
        entrenos = EntrenoRealizado.objects.filter(cliente=self.cliente, fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
        sesiones = entrenos.count()
        carga_total = entrenos.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0
        return {
            'carga_total': carga_total, 'sesiones': sesiones,
            'carga_promedio': carga_total / sesiones if sesiones > 0 else 0
        }

    def _comparar_mesociclos(self, actual, anterior):
        if not anterior: return None
        cambio_carga = actual['carga_total'] - anterior['carga_total']
        return {'cambio_carga': cambio_carga, 'mejora': cambio_carga > 0}

    def _evaluar_efectividad_mesociclo(self, datos):
        if datos['sesiones'] >= 12 and datos['carga_promedio'] > 1000: return 'alta'
        if datos['sesiones'] >= 8 and datos['carga_promedio'] > 500: return 'media'
        return 'baja'

    def _generar_recomendaciones_mesociclo(self, datos):
        recs = []
        if datos['sesiones'] < 8: recs.append('Aumentar frecuencia de entrenamiento')
        if datos['carga_promedio'] < 500: recs.append('Incrementar intensidad o volumen')
        return recs if recs else ['Mantener el enfoque actual']

    def _sugerir_periodizacion_optima(self, analisis_mesociclos):
        if not analisis_mesociclos: return "Datos insuficientes."
        efectividades = [m['efectividad'] for m in analisis_mesociclos]
        if efectividades.count('alta') > len(efectividades) / 2:
            return "La periodización actual está funcionando bien."
        return "Considera alternar mesociclos de alta y baja intensidad."


# VISTA DEL DASHBOARD
def dashboard_progresion_avanzado(request, cliente_id):
    """
    Vista principal del Dashboard de Progresión Avanzado - VERSIÓN FINAL
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    analizador = AnalisisProgresionAvanzado(cliente)

    ejercicio_seleccionado = request.GET.get('ejercicio')
    periodo = int(request.GET.get('periodo', 90))

    ratios_fuerza = analizador.calcular_ratios_fuerza()
    evolucion_temporal = analizador.analisis_evolucion_temporal(ejercicio=ejercicio_seleccionado, periodo_dias=periodo)
    analisis_mesociclos = analizador.analisis_mesociclos(periodo_dias=periodo)
    ejercicios_disponibles = analizador.obtener_ejercicios_registrados(dias=periodo)

    datos_ejercicio = None
    if ejercicio_seleccionado and evolucion_temporal:
        datos_ejercicio = evolucion_temporal.get(ejercicio_seleccionado)

    context = {
        'cliente': cliente,
        'ejercicio_seleccionado': ejercicio_seleccionado,
        'periodo': periodo,
        'ejercicios_disponibles': ejercicios_disponibles.items(),
        'ratios_fuerza': ratios_fuerza,
        'evolucion_temporal': evolucion_temporal,
        'analisis_mesociclos': analisis_mesociclos,
        'datos_ejercicio': datos_ejercicio,
    }

    datos_para_js = {
        'ratios': ratios_fuerza.get('grafico_radar', {}),
        'evolucion': {}
    }
    if datos_ejercicio:
        datos_para_js['evolucion'][ejercicio_seleccionado] = datos_ejercicio.get('datos', [])

    context['datos_graficos_json'] = json.dumps(datos_para_js, default=str)

    return render(request, 'analytics/progresion_avanzado.html', context)
