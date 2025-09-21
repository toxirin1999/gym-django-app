from entrenos.models import EntrenoRealizado, EjercicioRealizado
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from datetime import datetime, timedelta
import json
from clientes.models import Cliente


class AnalisisProgresionAvanzado:
    """
    Análisis avanzado de progresión - VERSIÓN COMPLETA Y MEJORADA
    """

    def __init__(self, cliente):
        self.cliente = cliente

        # 1. FUENTE ÚNICA DE VERDAD: La nueva base de datos de ejercicios.
        self.EJERCICIOS_DATABASE = {
            'pecho': {
                'compuesto_principal': ['Press Banca con Barra', 'Press Inclinado con Barra',
                                        'Fondos en Paralelas (con lastre)'],
                'compuesto_secundario': ['Press Banca con Mancuernas', 'Press Inclinado con Mancuernas'],
                'aislamiento': ['Aperturas con Mancuernas', 'Cruce de Poleas', 'Pec Deck']
            },
            'espalda': {
                'compuesto_principal': ['Dominadas (con lastre)', 'Remo con Barra (Pendlay)', 'Peso Muerto'],
                'compuesto_secundario': ['Remo con Mancuerna a una mano', 'Jalón al Pecho',
                                         'Remo en Polea Baja (Gironda)'],
                'aislamiento': ['Face Pulls', 'Pull-overs con mancuerna']
            },
            'hombros': {
                'compuesto_principal': ['Press Militar con Barra (de pie)', 'Push Press'],
                'compuesto_secundario': ['Press Arnold', 'Press Militar con Mancuernas (sentado)'],
                'aislamiento': ['Elevaciones Laterales con Mancuernas', 'Elevaciones Frontales con Polea',
                                'Pájaros (Bent Over Raises)']
            },
            'cuadriceps': {
                'compuesto_principal': ['Sentadilla Trasera con Barra', 'Sentadilla Frontal con Barra'],
                'compuesto_secundario': ['Prensa de Piernas', 'Zancadas con Mancuernas', 'Sentadilla Búlgara'],
                'aislamiento': ['Extensiones de Cuádriceps en Máquina']
            },
            'isquios': {
                'compuesto_principal': ['Peso Muerto Rumano', 'Buenos Días (Good Mornings)'],
                'compuesto_secundario': ['Curl Femoral Tumbado', 'Curl Femoral Sentado'],
                'aislamiento': ['Hiperextensiones Inversas']
            },
            'gluteos': {
                'compuesto_principal': ['Hip Thrust con Barra', 'Peso Muerto Sumo'],
                'compuesto_secundario': ['Patada de Glúteo en Polea', 'Abducción de Cadera en Máquina'],
                'aislamiento': []
            },
            'biceps': {
                'compuesto_secundario': ['Curl con Barra Z', 'Curl Araña'],
                'aislamiento': ['Curl de Concentración', 'Curl Martillo con Mancuernas', 'Curl en Polea Alta']
            },
            'triceps': {
                'compuesto_principal': ['Press Francés con Barra Z', 'Press Cerrado en Banca'],
                'compuesto_secundario': ['Extensiones de Tríceps en Polea Alta', 'Fondos entre bancos'],
                'aislamiento': ['Patada de Tríceps con Polea']
            }
        }

        # 2. EJERCICIOS PRINCIPALES PARA RATIOS: Los nombres canónicos que usaremos.
        self.ejercicios_principales = [
            'Press banca', 'Press inclinado', 'Sentadilla', 'Peso muerto',
            'Press militar', 'Dominadas', 'Remo', 'Hip thrust'
        ]

        # 3. GENERACIÓN DINÁMICA: Creamos el mapeo a partir de la base de datos.
        self.mapeo_nombres = self._generar_mapeo_desde_db()

    # En la clase AnalisisProgresionAvanzado, reemplaza este método

    def _generar_mapeo_desde_db(self):
        """
        Genera el diccionario `mapeo_nombres` a partir de la base de datos estructurada.
        Define un nombre "canónico" para cada grupo de ejercicios y agrupa todas las variantes.
        """
        mapeo = {}

        # --- INICIO DE LA CORRECCIÓN ---
        # Hemos hecho las reglas más específicas para asegurar que cada ejercicio
        # se asigne a la clave correcta, especialmente para los presses.
        reglas_canonicas = {
            # REGLAS ESPECÍFICAS PRIMERO
            'press banca con barra': 'Press banca',
            'press banca con mancuernas': 'Press banca',
            'press inclinado con barra': 'Press inclinado',
            'press inclinado con mancuernas': 'Press inclinado',
            'press militar con barra': 'Press militar',
            'press militar con mancuernas': 'Press militar',
            'sentadilla trasera': 'Sentadilla',
            'sentadilla frontal': 'Sentadilla',
            'peso muerto rumano': 'Peso muerto',
            'peso muerto sumo': 'Peso muerto',

            # REGLAS GENERALES DESPUÉS
            'press banca': 'Press banca', 'press inclinado': 'Press inclinado', 'sentadilla': 'Sentadilla',
            'peso muerto': 'Peso muerto', 'remo': 'Remo', 'dominadas': 'Dominadas',
            'press militar': 'Press militar', 'push press': 'Press militar', 'hip thrust': 'Hip thrust',
            'fondos': 'Fondos', 'aperturas': 'Aperturas', 'cruce de poleas': 'Aperturas',
            'pec deck': 'Aperturas', 'jalón': 'Jalones', 'face pulls': 'Face pull',
            'pull-overs': 'Pull-over', 'press arnold': 'Press de hombros',
            'elevaciones laterales': 'Elevaciones laterales', 'elevaciones frontales': 'Elevaciones frontales',
            'pájaros': 'Pájaros', 'prensa': 'Prensa', 'zancadas': 'Zancadas',
            'sentadilla búlgara': 'Zancadas', 'extensiones de cuádriceps': 'Extensiones cuadriceps',
            'curl femoral': 'Femoral', 'buenos días': 'Isquios', 'hiperextensiones': 'Isquios',
            'patada de glúteo': 'Gluteos', 'abducción de cadera': 'Gluteos', 'curl': 'Curl',
            'press francés': 'Triceps', 'press cerrado': 'Triceps', 'extensiones de tríceps': 'Triceps',
        }
        # --- FIN DE LA CORRECCIÓN ---

        for grupo_muscular, tipos in self.EJERCICIOS_DATABASE.items():
            for tipo_ejercicio, lista_ejercicios in tipos.items():
                for ejercicio_largo in lista_ejercicios:
                    nombre_canonico_encontrado = None
                    ej_lower = ejercicio_largo.lower()

                    for fragmento, nombre_canonico in reglas_canonicas.items():
                        if fragmento in ej_lower:
                            nombre_canonico_encontrado = nombre_canonico
                            break

                    if not nombre_canonico_encontrado:
                        nombre_canonico_encontrado = grupo_muscular.title()

                    if nombre_canonico_encontrado not in mapeo:
                        mapeo[nombre_canonico_encontrado] = []

                    mapeo[nombre_canonico_encontrado].append(ejercicio_largo)
                    mapeo[nombre_canonico_encontrado].append(ej_lower)

        mapeo.setdefault('Press inclinado', []).append('press incllinado')
        mapeo.setdefault('Sentadilla', []).append('sentadilla libre')

        for clave, valor in mapeo.items():
            mapeo[clave] = sorted(list(set(valor)))

        print("✅ Mapeo de nombres generado dinámicamente.")
        return mapeo

    def calcular_ratios_fuerza(self):
        """
        Calcula ratios de fuerza para balance muscular
        """
        rms = self._obtener_1rm_ejercicios()
        if not rms:
            return {'ratios': [], 'grafico_radar': {'labels': [], 'valores': [], 'optimos': []}, 'puntos_debiles': []}
            # 1. Diccionario para mapear claves internas a nombres visuales

        nombres_ratios = {
            'press_sentadilla': 'Press/Sentadilla',
            'peso_muerto_sentadilla': 'Peso Muerto/Sentadilla',
            'press_militar_banca': 'Press Militar/Press Banca',
            'dominadas_remo': 'Dominadas/Remo'
        }

        ratios = {
            'press_sentadilla': self._calcular_ratio(rms.get('Press banca', 0), rms.get('Sentadilla', 0)),
            'peso_muerto_sentadilla': self._calcular_ratio(rms.get('Peso muerto', 0), rms.get('Sentadilla', 0)),
            'press_militar_banca': self._calcular_ratio(rms.get('Press militar', 0), rms.get('Press banca', 0)),
            'dominadas_remo': self._calcular_ratio(rms.get('Dominadas', 0), rms.get('Remo', 0))
        }
        estandares = {
            'press_sentadilla': {'optimo': 0.75, 'rango': (0.65, 0.85)},
            'peso_muerto_sentadilla': {'optimo': 1.25, 'rango': (1.15, 1.35)},
            'press_militar_banca': {'optimo': 0.65, 'rango': (0.55, 0.75)},
            'dominadas_remo': {'optimo': 1.0, 'rango': (0.85, 1.15)}
        }
        analisis_ratios = []
        for ratio_name, valor in ratios.items():
            if valor > 0:
                estandar = estandares[ratio_name]
                estado = self._evaluar_ratio(valor, estandar)
                analisis_ratios.append({
                    'clave': ratio_name,
                    # --- LÍNEA MODIFICADA ---
                    # Usamos nuestro diccionario para obtener el nombre bonito
                    'nombre': nombres_ratios.get(ratio_name, ratio_name.replace('_', ' ').title()),
                    'valor': valor,
                    'optimo': estandar['optimo'],
                    'estado': estado,
                    'recomendacion': self._generar_recomendacion_ratio(ratio_name, estado)
                })
        ratios_validos = {r['clave']: r['valor'] for r in analisis_ratios}
        estandares_validos = {clave: estandares[clave] for clave in ratios_validos}

        print("🧪 Ratios finales generados:", analisis_ratios)
        print("📊 Ratios para radar:", [nombres_ratios.get(r['clave']) for r in analisis_ratios])

        return {
            'ratios': analisis_ratios,
            # --- LÍNEA MODIFICADA ---
            # Pasamos el diccionario de nombres bonitos como un nuevo argumento
            'grafico_radar': self._generar_datos_radar(ratios_validos, estandares_validos, nombres_ratios),
            'puntos_debiles': self._identificar_puntos_debiles(analisis_ratios)
        }

    def analisis_evolucion_temporal(self, ejercicio=None, periodo_dias=90):
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)
        todos_los_ejercicios_registrados = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente, entreno__fecha__gte=fecha_inicio
        ).values_list('nombre_ejercicio', flat=True).distinct()

        ejercicios_agrupados = {}
        for nombre_original in todos_los_ejercicios_registrados:
            nombre_norm = self._normalizar_nombre(nombre_original)
            if nombre_norm not in ejercicios_agrupados:
                ejercicios_agrupados[nombre_norm] = []
            ejercicios_agrupados[nombre_norm].append(nombre_original)

        ejercicios_a_procesar = ejercicios_agrupados
        if ejercicio:
            ejercicio_norm_seleccionado = self._normalizar_nombre(ejercicio)
            ejercicios_a_procesar = {
                ejercicio_norm_seleccionado: ejercicios_agrupados.get(ejercicio_norm_seleccionado, [])}

        resultados = {}
        for nombre_norm, variantes_originales in ejercicios_a_procesar.items():
            if not variantes_originales: continue
            datos = self._obtener_datos_temporales(nombre_norm, variantes_originales, fecha_inicio)
            if datos:
                tendencia = self._calcular_tendencia_lineal(datos)
                resultados[nombre_norm] = {
                    'datos': datos, 'tendencia': tendencia,
                    'volumen_por_grupo': sum(d['volumen'] for d in datos),
                    'hitos': self._detectar_hitos(datos),
                    'predicciones': self._generar_predicciones_temporales(datos, tendencia)
                }
        return resultados

    def analisis_mesociclos(self, periodo_dias=180):
        """
        Análisis de mesociclos para periodización
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)
        mesociclos = self._dividir_en_mesociclos(fecha_inicio, 28)
        analisis_mesociclos = []
        for i, (inicio, fin) in enumerate(mesociclos):
            datos_mesociclo = self._analizar_mesociclo(inicio, fin)
            if i > 0:
                mesociclo_anterior = analisis_mesociclos[i - 1]
                comparativa = self._comparar_mesociclos(datos_mesociclo, mesociclo_anterior['datos'])
                datos_mesociclo['comparativa'] = comparativa
            analisis_mesociclos.append({
                'numero': i + 1, 'fecha_inicio': inicio, 'fecha_fin': fin,
                'datos': datos_mesociclo,
                'efectividad': self._evaluar_efectividad_mesociclo(datos_mesociclo),
                'recomendaciones': self._generar_recomendaciones_mesociclo(datos_mesociclo)
            })
        return {
            'mesociclos': analisis_mesociclos,
            'periodizacion_optima': self._sugerir_periodizacion_optima(analisis_mesociclos),
            'picos_valles': self._identificar_picos_valles_rendimiento(analisis_mesociclos)
        }

    # ============================================================================
    # MÉTODOS AUXILIARES IMPLEMENTADOS
    # ============================================================================
    # En la clase AnalisisProgresionAvanzado, reemplaza este método temporalmente

    def _obtener_1rm_ejercicios(self, dias=180):
        print("🔥 Calculando 1RM para ratios de fuerza...")
        fecha_limite = datetime.now().date() - timedelta(days=dias)
        registros = EjercicioRealizado.objects.filter(entreno__cliente=self.cliente, entreno__fecha__gte=fecha_limite)
        rms = {}
        print(f"🔍 Analizando {registros.count()} registros de ejercicios de los últimos {dias} días.")

        # --- INICIO DE LA SECCIÓN DE DEPURACIÓN ---
        print("=" * 50)
        print("INICIO DEPURACIÓN: ¿Qué nombres se están normalizando?")
        nombres_encontrados = set()
        # --- FIN DE LA SECCIÓN DE DEPURACIÓN ---

        for r in registros:
            nombre_original = r.nombre_ejercicio.strip()
            nombre_norm = self._normalizar_nombre(nombre_original)

            # --- INICIO DE LA SECCIÓN DE DEPURACIÓN ---
            if nombre_original not in nombres_encontrados:
                print(f"  -> Original: '{nombre_original}'  |  Normalizado como: '{nombre_norm}'")
                nombres_encontrados.add(nombre_original)
            # --- FIN DE LA SECCIÓN DE DEPURACIÓN ---

            if nombre_norm not in self.ejercicios_principales:
                continue
            try:
                peso = float(str(r.peso_kg or '0').replace(',', '.'))
                reps = int(r.repeticiones)
                if 1 <= reps <= 12 and peso >= 0:
                    rm_estimado = peso / (1.0278 - 0.0278 * reps)
                    if nombre_norm not in rms or rm_estimado > rms[nombre_norm]:
                        rms[nombre_norm] = round(rm_estimado, 1)
            except (ValueError, TypeError, AttributeError):
                continue

        # --- INICIO DE LA SECCIÓN DE DEPURACIÓN ---
        print("FIN DEPURACIÓN")
        print("=" * 50)
        # --- FIN DE LA SECCIÓN DE DEPURACIÓN ---

        print(f"✅ Cálculo de 1RM finalizado. Récords encontrados: {rms}")
        return rms

    def _calcular_ratio(self, valor1, valor2):
        return round(valor1 / valor2, 2) if valor2 > 0 else 0

    def _evaluar_ratio(self, valor, estandar):
        rango_min, rango_max = estandar['rango']
        if rango_min <= valor <= rango_max:
            return 'optimo'
        elif valor < rango_min:
            return 'bajo'
        else:
            return 'alto'

    def _generar_recomendacion_ratio(self, ratio_name, estado):
        recomendaciones = {
            'press_sentadilla': {'bajo': 'Enfócate en fortalecer el press de banca.',
                                 'alto': 'Prioriza el entrenamiento de piernas.',
                                 'optimo': 'Mantén el equilibrio actual.'},
            'peso_muerto_sentadilla': {'bajo': 'Trabaja más el peso muerto y cadena posterior.',
                                       'alto': 'Equilibra con más trabajo de cuádriceps.',
                                       'optimo': 'Excelente equilibrio.'},
            'press_militar_banca': {'bajo': 'Incrementa el trabajo de hombros.',
                                    'alto': 'Reduce volumen de press militar.', 'optimo': 'Buen equilibrio.'},
            'dominadas_remo': {'bajo': 'Aumenta trabajo de dominadas.', 'alto': 'Equilibra con más remo horizontal.',
                               'optimo': 'Excelente equilibrio.'}
        }
        return recomendaciones.get(ratio_name, {}).get(estado, 'Mantén el entrenamiento actual.')

    # En la clase AnalisisProgresionAvanzado, reemplaza este método

    def _generar_datos_radar(self, ratios, estandares, nombres_bonitos):
        """
        Genera datos para el gráfico radar, usando los nombres visuales proporcionados.
        """
        labels = []
        valores = []
        optimos = []

        for ratio_name, valor in ratios.items():
            if valor > 0:
                # --- LÍNEA MODIFICADA ---
                # Ahora usamos el diccionario de nombres bonitos que recibimos
                labels.append(nombres_bonitos.get(ratio_name, "Error"))
                valores.append(valor)
                optimos.append(estandares[ratio_name]['optimo'])

        return {
            'labels': labels,
            'valores': valores,
            'optimos': optimos
        }

    def _identificar_puntos_debiles(self, analisis_ratios):
        return [f"{r['nombre']}: {r['recomendacion']}" for r in analisis_ratios if r['estado'] != 'optimo']

    def _obtener_datos_temporales(self, nombre_normalizado, variantes, fecha_inicio):
        qs = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente, nombre_ejercicio__in=variantes, entreno__fecha__gte=fecha_inicio
        ).order_by('entreno__fecha').select_related('entreno')
        datos = []
        for e in qs:
            try:
                peso = float(str(e.peso_kg or '0').replace(',', '.'))
                reps = int(e.repeticiones or 1)
                series = int(e.series or 1)
                volumen = peso * reps * series
                rm_estimado = peso / (1.0278 - 0.0278 * reps) if 1 <= reps <= 12 and peso > 0 else peso
                intensidad = (peso / rm_estimado) * 100 if rm_estimado > 0 else 0
                datos.append({
                    'fecha': e.entreno.fecha.strftime('%Y-%m-%d'), 'peso': peso, 'repeticiones': reps,
                    'series': series, 'volumen': volumen, 'intensidad': round(intensidad, 1)
                })
            except (ValueError, TypeError):
                continue
        return datos

    # En la clase AnalisisProgresionAvanzado, reemplaza tu _calcular_tendencia_lineal

    def _calcular_tendencia_lineal(self, datos):
        """
        Calcula tendencia lineal usando regresión.
        Maneja casos especiales para ejercicios de peso corporal como Dominadas.
        """
        if len(datos) < 2: return self._calcular_tendencia_simple(datos)

        # Detectar si es un ejercicio de peso corporal (basado en si el peso máximo es 0)
        pesos = [d['peso'] for d in datos]
        es_peso_corporal = max(pesos) == 0

        try:
            from scipy import stats
            fechas_num = [
                (datetime.strptime(d['fecha'], '%Y-%m-%d') - datetime.strptime(datos[0]['fecha'], '%Y-%m-%d')).days for
                d in datos]

            if es_peso_corporal:
                # Si es peso corporal, la tendencia se basa en REPETICIONES
                metrica_a_analizar = [d['repeticiones'] for d in datos]
                unidad = "reps"
            else:
                # Para el resto, se basa en PESO
                metrica_a_analizar = pesos
                unidad = "kg"

            slope, intercept, r_value, p_value, std_err = stats.linregress(fechas_num, metrica_a_analizar)

            return {
                'tendencia_semanal': f"{round(slope * 7, 2)} {unidad}",  # Añadimos la unidad
                'confianza': round(abs(r_value) * 100, 1)
            }
        except (ImportError, ValueError):
            return self._calcular_tendencia_simple(datos)  # Fallback

    def _calcular_tendencia_simple(self, datos):
        if len(datos) < 2: return None
        primer, ultimo = datos[0]['peso'], datos[-1]['peso']
        dias = (datetime.strptime(datos[-1]['fecha'], "%Y-%m-%d") - datetime.strptime(datos[0]['fecha'],
                                                                                      "%Y-%m-%d")).days
        cambio = ((ultimo - primer) / primer * 100) if primer > 0 else 0
        tendencia_semanal = cambio / (dias / 7) if dias > 0 else 0
        return {'tendencia_semanal': round(tendencia_semanal, 2), 'confianza': 75.0}

    def _detectar_hitos(self, datos):
        if not datos: return []
        hitos = []
        pesos = [d['peso'] for d in datos]
        peso_max = max(pesos)
        fecha_max = next((d['fecha'] for d in datos if d['peso'] == peso_max), datos[-1]['fecha'])
        hitos.append({'tipo': 'record_personal', 'fecha': fecha_max, 'valor': peso_max,
                      'descripcion': f'Nuevo récord: {peso_max} kg'})
        for i in range(1, len(datos)):
            if datos[i - 1]['peso'] > 0:
                incremento = ((datos[i]['peso'] - datos[i - 1]['peso']) / datos[i - 1]['peso']) * 100
                if incremento >= 5:
                    hitos.append(
                        {'tipo': 'incremento_significativo', 'fecha': datos[i]['fecha'], 'valor': datos[i]['peso'],
                         'descripcion': f'Incremento del {incremento:.1f}%'})
        return hitos

    # En la clase AnalisisProgresionAvanzado, reemplaza tu _generar_predicciones_temporales

    def _generar_predicciones_temporales(self, datos, tendencia):
        """
        Genera predicciones basadas en la progresión actual.
        Ahora es capaz de manejar tendencias basadas en peso (kg) o en repeticiones (reps).
        """
        if not tendencia or len(datos) < 2:
            return []

        predicciones = []
        ultimo_dato = datos[-1]
        fecha_base = datetime.strptime(ultimo_dato['fecha'], '%Y-%m-%d')

        # 1. Extraer el valor numérico y la unidad de la tendencia
        tendencia_str = str(tendencia.get('tendencia_semanal', '0'))
        try:
            # Intentamos separar el número de la unidad (ej. "0.5 reps" -> 0.5, "reps")
            valor_tendencia_semanal = float(tendencia_str.split()[0])
            unidad = tendencia_str.split()[1] if len(tendencia_str.split()) > 1 else 'kg'
        except (ValueError, IndexError):
            # Si falla, asumimos que es un número simple (compatible con versiones anteriores)
            valor_tendencia_semanal = float(tendencia_str)
            unidad = 'kg'

        # 2. Determinar la métrica base para la predicción
        if unidad == 'reps':
            metrica_base = ultimo_dato['repeticiones']
            descripcion_prediccion = "{valor_estimado} reps"
        else:  # Por defecto, la predicción es sobre el peso
            metrica_base = ultimo_dato['peso']
            descripcion_prediccion = "{valor_estimado} kg"

        # 3. Generar las predicciones para las próximas semanas
        for semanas in [4, 8, 12]:
            fecha_prediccion = fecha_base + timedelta(weeks=semanas)

            # El cálculo ahora es genérico: métrica base + (tendencia * número de semanas)
            valor_predicho = metrica_base + (valor_tendencia_semanal * semanas)

            # Ajustar la confianza basada en el tiempo
            confianza = max(tendencia.get('confianza', 75) - (semanas * 4), 30)

            predicciones.append({
                'fecha': fecha_prediccion.strftime('%Y-%m-%d'),
                'semanas': semanas,
                'confianza': round(confianza, 1),
                # Usamos el formato de descripción dinámico
                'descripcion': descripcion_prediccion.format(valor_estimado=round(valor_predicho, 1))
            })

        return predicciones

    def _calcular_volumen_grupo_muscular(self, ejercicio, fecha_inicio):
        registros = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente, nombre_ejercicio__iexact=ejercicio, fecha_creacion__gte=fecha_inicio
        )
        volumen_total = 0
        for r in registros:
            try:
                peso = float(r.peso_kg or 0)
                reps = int(r.repeticiones or 1)
                series = int(r.series or 1)
                volumen_total += peso * reps * series
            except:
                continue
        return volumen_total

    def _dividir_en_mesociclos(self, fecha_inicio, dias_por_ciclo):
        mesociclos = []
        fecha_actual = fecha_inicio
        fecha_fin_total = datetime.now().date()
        while fecha_actual < fecha_fin_total:
            fecha_fin_ciclo = fecha_actual + timedelta(days=dias_por_ciclo)
            if fecha_fin_ciclo > fecha_fin_total:
                fecha_fin_ciclo = fecha_fin_total
            mesociclos.append((fecha_actual, fecha_fin_ciclo))
            fecha_actual = fecha_fin_ciclo + timedelta(days=1)
        return mesociclos

    def _analizar_mesociclo(self, fecha_inicio, fecha_fin):
        registros = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente, entreno__fecha__gte=fecha_inicio, entreno__fecha__lte=fecha_fin
        )
        entrenos_ids = registros.values_list('entreno_id', flat=True).distinct()
        sesiones = len(entrenos_ids)
        carga_total = 0
        for r in registros:
            try:
                peso = float(r.peso_kg or 0)
                reps = int(r.repeticiones or 1)
                series = int(r.series or 1)
                carga_total += peso * reps * series
            except:
                continue
        duracion_total = 0
        return {
            'carga_total': carga_total, 'duracion_total': duracion_total, 'sesiones': sesiones,
            'carga_promedio': carga_total / sesiones if sesiones > 0 else 0,
            'duracion_promedio': duracion_total / sesiones if sesiones > 0 else 0
        }

    def _normalizar_nombre(self, nombre):
        if not nombre or not isinstance(nombre, str):
            return "Desconocido"
        nombre_limpio = nombre.strip().lower()
        if not hasattr(self, '_mapeo_inverso'):
            self._mapeo_inverso = {}
            for clave_principal, alias_lista in self.mapeo_nombres.items():
                for alias in alias_lista:
                    self._mapeo_inverso[alias.strip().lower()] = clave_principal
        return self._mapeo_inverso.get(nombre_limpio, nombre.strip().title())

    def _comparar_mesociclos(self, mesociclo_actual, mesociclo_anterior):
        if not mesociclo_anterior: return None
        cambio_carga = mesociclo_actual['carga_total'] - mesociclo_anterior['carga_total']
        cambio_sesiones = mesociclo_actual['sesiones'] - mesociclo_anterior['sesiones']
        return {
            'cambio_carga': cambio_carga,
            'cambio_carga_pct': (cambio_carga / mesociclo_anterior['carga_total']) * 100 if mesociclo_anterior[
                                                                                                'carga_total'] > 0 else 0,
            'cambio_sesiones': cambio_sesiones,
            'mejora': cambio_carga > 0
        }

    def _evaluar_efectividad_mesociclo(self, datos_mesociclo):
        if datos_mesociclo['sesiones'] >= 12 and datos_mesociclo['carga_promedio'] > 1000:
            return 'alta'
        elif datos_mesociclo['sesiones'] >= 8 and datos_mesociclo['carga_promedio'] > 500:
            return 'media'
        else:
            return 'baja'

    def _generar_recomendaciones_mesociclo(self, datos_mesociclo):
        recomendaciones = []
        if datos_mesociclo['sesiones'] < 8: recomendaciones.append('Aumentar frecuencia de entrenamiento')
        if datos_mesociclo['carga_promedio'] < 500: recomendaciones.append('Incrementar intensidad o volumen')
        if datos_mesociclo['duracion_promedio'] > 90: recomendaciones.append('Considerar reducir duración de sesiones')
        if not recomendaciones: recomendaciones.append('Mantener el enfoque actual')
        return recomendaciones

    def _sugerir_periodizacion_optima(self, analisis_mesociclos):
        if not analisis_mesociclos: return "Datos insuficientes para sugerir periodización"
        efectividades = [m['efectividad'] for m in analisis_mesociclos]
        if efectividades.count('alta') > len(efectividades) / 2:
            return "Continúa con la periodización actual, está funcionando bien"
        else:
            return "Considera alternar mesociclos de alta y baja intensidad para mejor recuperación"

    def _identificar_picos_valles_rendimiento(self, analisis_mesociclos):
        if len(analisis_mesociclos) < 3: return []
        picos_valles = []
        for i in range(1, len(analisis_mesociclos) - 1):
            actual = analisis_mesociclos[i]['datos']['carga_total']
            anterior = analisis_mesociclos[i - 1]['datos']['carga_total']
            siguiente = analisis_mesociclos[i + 1]['datos']['carga_total']
            if actual > anterior and actual > siguiente:
                picos_valles.append({'tipo': 'pico', 'mesociclo': analisis_mesociclos[i]['numero'], 'valor': actual})
            elif actual < anterior and actual < siguiente:
                picos_valles.append({'tipo': 'valle', 'mesociclo': analisis_mesociclos[i]['numero'], 'valor': actual})
        return picos_valles

    def _extraer_repeticiones(self, rep_str):
        try:
            rep_str = str(rep_str).lower().replace('×', 'x').replace(' ', '')
            return int(rep_str.split('x')[1]) if 'x' in rep_str else int(rep_str)
        except:
            return 1

    def _extraer_series(self, rep_str):
        try:
            rep_str = str(rep_str).lower().replace('×', 'x').replace(' ', '')
            return int(rep_str.split('x')[0]) if 'x' in rep_str else 1
        except:
            return 1

    def _obtener_1rm_estimado(self, ejercicio, peso, reps):
        if reps <= 12: return peso / (1.0278 - 0.0278 * reps)
        return peso * 1.3

    # En la clase AnalisisProgresionAvanzado, reemplaza tu obtener_ejercicios_registrados

    def obtener_ejercicios_registrados(self, dias=180):
        """
        Obtiene una lista limpia y normalizada de todos los ejercicios
        que el cliente ha realizado en el período especificado.
        """
        fecha_limite = datetime.now().date() - timedelta(days=dias)

        # Usamos entreno__fecha para ser consistentes con los otros análisis
        ejercicios = (
            EjercicioRealizado.objects
            .filter(entreno__cliente=self.cliente, entreno__fecha__gte=fecha_limite)
            .values_list('nombre_ejercicio', flat=True)
            .distinct()
        )

        # Normalizamos cada nombre y usamos un 'set' para eliminar duplicados automáticamente
        ejercicios_normalizados = sorted(list(set(self._normalizar_nombre(e) for e in ejercicios)))

        return {e: e for e in ejercicios_normalizados}


# Vista para el Dashboard de Progresión Avanzado
# En tu archivo analisis_progresion.py, reemplaza la vista completa

def dashboard_progresion_avanzado(request, cliente_id):
    print("🚨 Se ejecutó la vista dashboard_progresion_avanzado")
    cliente = get_object_or_404(Cliente, id=cliente_id)
    analizador = AnalisisProgresionAvanzado(cliente)

    # 1. OBTENER PARÁMETROS DE LA URL
    ejercicio_seleccionado = request.GET.get('ejercicio')
    periodo = int(request.GET.get('periodo', 90))

    # 2. REALIZAR TODOS LOS ANÁLISIS PRINCIPALES
    # Los ratios y mesociclos son análisis generales del cliente y se calculan siempre.
    ratios_fuerza = analizador.calcular_ratios_fuerza()
    analisis_mesociclos = analizador.analisis_mesociclos(periodo_dias=periodo)

    # La evolución temporal depende de la selección, la función interna lo maneja.
    evolucion_temporal = analizador.analisis_evolucion_temporal(
        ejercicio=ejercicio_seleccionado,
        periodo_dias=periodo
    )

    # La lista de ejercicios para el menú desplegable.
    ejercicios_disponibles = analizador.obtener_ejercicios_registrados(dias=periodo)

    # 3. PREPARAR DATOS ESPECÍFICOS PARA LA PLANTILLA
    # Obtenemos los datos concretos del ejercicio que se ha seleccionado (si hay uno).
    datos_ejercicio = None
    if ejercicio_seleccionado:
        # No es necesario normalizar aquí, la clave del diccionario ya está normalizada.
        datos_ejercicio = evolucion_temporal.get(ejercicio_seleccionado)

        # Imprimir logs de depuración solo si se ha seleccionado un ejercicio
        if datos_ejercicio:
            print(f"🔍 Datos disponibles para '{ejercicio_seleccionado}': {len(datos_ejercicio['datos'])} registros")
            print(f"📈 Tendencia calculada: {datos_ejercicio.get('tendencia')}")
            print(f"🏆 Hitos encontrados: {datos_ejercicio.get('hitos')}")
            print(f"🔮 Predicciones generadas: {datos_ejercicio.get('predicciones')}")
        else:
            print(
                f"⚠️ No se encontraron datos de evolución para '{ejercicio_seleccionado}' en el período seleccionado.")
    else:
        print("ℹ️ No se ha seleccionado un ejercicio. Mostrando resumen general (Ratios y Mesociclos).")

    # 4. CONSTRUIR EL CONTEXTO FINAL PARA LA PLANTILLA
    # Preparamos los datos para los gráficos de JavaScript.
    datos_grafico_evolucion = {
        ejercicio_seleccionado: datos_ejercicio} if ejercicio_seleccionado and datos_ejercicio else {}

    context = {
        'cliente': cliente,
        'ejercicio_seleccionado': ejercicio_seleccionado,
        'periodo': periodo,
        'ejercicios_disponibles': ejercicios_disponibles.items(),
        'ratios_fuerza': ratios_fuerza,
        'analisis_mesociclos': analisis_mesociclos,  # <-- Mesociclos incluidos
        'evolucion_temporal': evolucion_temporal,
        'datos_ejercicio': datos_ejercicio,
        'datos_graficos': json.dumps({
            'evolucion': datos_grafico_evolucion,
            'ratios': ratios_fuerza
        }, indent=4)  # Usar indent para depurar más fácil en el HTML
    }

    print("Ejercicios disponibles para el desplegable:", ejercicios_disponibles)

    return render(request, 'analytics/progresion_avanzado.html', context)
