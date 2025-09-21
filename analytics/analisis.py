from datetime import datetime, timedelta
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente
from entrenos.utils.utils import parse_reps_and_series
from django.db.models import Sum, Avg, Max, Min, Count


class CalculadoraEjerciciosTabla:
    """
    Calculadora que usa los datos de la tabla estructurada EjercicioRealizado
    """

    def __init__(self, cliente):
        self.cliente = cliente

    # Archivo: analytics/views.py

    # ... (dentro de la clase CalculadoraEjerciciosTabla)
    def _metricas_vacias(self):
        """Retorna un diccionario de métricas con valores en cero."""
        return {
            'volumen_total': 0,
            'intensidad_promedio': 0,
            'calorias_totales': 0,
            'frecuencia_semanal': 0,
            'duracion_promedio': 0,
            'consistencia': 0,
            'total_ejercicios': 0,
            'ejercicios_unicos': 0,
            'peso_promedio': 0,
            'peso_maximo': 0,
            'series_totales': 0,
            'repeticiones_totales': 0,
            'entrenamientos_unicos': 0
        }

    # Archivo: analytics/views.py
    # Clase: CalculadoraEjerciciosTabla

    def calcular_1rm_estimado_por_ejercicio(self):
        """
        Calcula el 1RM estimado. VERSIÓN FINAL CORREGIDA.
        """
        todos_los_ejercicios = self.obtener_ejercicios_tabla()
        if not todos_los_ejercicios:
            return {}

        ejercicios_agrupados = {}
        for e in todos_los_ejercicios:
            nombre = e['nombre'].strip().title()
            if nombre not in ejercicios_agrupados:
                ejercicios_agrupados[nombre] = []

            try:
                peso = float(e.get('peso', 0))

                # --- INICIO DE LA CORRECCIÓN FINAL ---
                # La depuración nos mostró que 'repeticiones' ya es un número.
                # No necesitamos la función de parseo. Usamos el valor directamente.
                reps = int(e.get('repeticiones', 0))
                # --- FIN DE LA CORRECCIÓN FINAL ---

                if peso > 0 and reps > 0:
                    ejercicios_agrupados[nombre].append({'peso': peso, 'repeticiones': reps})
            except (ValueError, TypeError):
                continue

        one_rm_finales = {}
        for nombre_ejercicio, levantamientos in ejercicios_agrupados.items():
            rm_maximo = 0
            for levantamiento in levantamientos:
                peso = levantamiento['peso']
                reps = levantamiento['repeticiones']
                rm_estimado = peso * (1 + (reps / 30))
                if rm_estimado > rm_maximo:
                    rm_maximo = rm_estimado
            if rm_maximo > 0:
                one_rm_finales[nombre_ejercicio] = round(rm_maximo, 2)

        return one_rm_finales

    def obtener_ejercicios_tabla(self, fecha_inicio=None, fecha_fin=None):
        """
        Obtiene todos los ejercicios realizados por el cliente con una consulta
        única y optimizada, asegurando que los filtros de fecha se apliquen correctamente.
        VERSIÓN DE DEPURACIÓN
        """
        print("\n--- INICIANDO DEPURACIÓN DE obtener_ejercicios_tabla ---")

        # 1. Verificamos el cliente
        print(f"1. Buscando ejercicios para el cliente: {self.cliente.nombre} (ID: {self.cliente.id})")

        # 2. Construimos la consulta base
        query = EjercicioRealizado.objects.filter(entreno__cliente=self.cliente)
        print(f"2. Consulta inicial encontró: {query.count()} registros de EjercicioRealizado para este cliente.")

        # 3. Aplicamos filtros de fecha (si existen)
        if fecha_inicio:
            query = query.filter(entreno__fecha__gte=fecha_inicio)
            print(f"3. Después de filtro de fecha de inicio ({fecha_inicio}), quedan: {query.count()} registros.")
        if fecha_fin:
            query = query.filter(entreno__fecha__lte=fecha_fin)
            print(f"3. Después de filtro de fecha de fin ({fecha_fin}), quedan: {query.count()} registros.")

        # 4. Seleccionamos los campos
        ejercicios_qs = query.select_related('entreno').values(
            'nombre_ejercicio', 'grupo_muscular', 'peso_kg', 'series', 'repeticiones',
            'completado', 'entreno__fecha', 'entreno__id'
        )
        print(f"4. La consulta final con .values() tiene {len(ejercicios_qs)} elementos.")

        # 5. Mostramos los primeros 3 registros crudos que se obtuvieron
        if ejercicios_qs:
            print("5. Primeros 3 registros crudos de la base de datos:")
            for e_raw in list(ejercicios_qs)[:3]:
                print(f"   - {e_raw}")

        # 6. Construimos la lista final
        ejercicios = [
            {
                'nombre': e['nombre_ejercicio'], 'grupo': e['grupo_muscular'],
                'peso': e['peso_kg'] or 0, 'series': e['series'] or 1,
                'repeticiones': e['repeticiones'] or 1, 'completado': bool(e['completado']),
                'fecha': e['entreno__fecha'], 'cliente': self.cliente.nombre,
                'entreno_id': e['entreno__id']
            }
            for e in ejercicios_qs
        ]
        print(f"6. Se ha construido la lista final 'ejercicios' con {len(ejercicios)} diccionarios.")
        print("--- FIN DE DEPURACIÓN ---\n")

        return ejercicios

    def calcular_metricas_principales(self, fecha_inicio=None, fecha_fin=None):
        """
        Calcula todas las métricas principales de forma consistente y eficiente,
        priorizando los datos pre-calculados del modelo EntrenoRealizado.
        """
        # 1. Obtener los entrenamientos del período con una única consulta.
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )

        if not entrenamientos.exists():
            return self._metricas_vacias()

        # 2. Usar funciones de agregación de Django para obtener los totales.
        # Esto es mucho más eficiente que iterar en Python.
        agregados = entrenamientos.aggregate(
            volumen_total_agregado=Sum('volumen_total_kg'),
            duracion_total_agregada=Sum('duracion_minutos'),
            calorias_totales_agregadas=Sum('calorias_quemadas'),
            num_entrenamientos=Count('id')
        )

        # Asignar valores, manejando el caso de que no haya datos (None).
        volumen_total = agregados['volumen_total_agregado'] or 0
        duracion_total = agregados['duracion_total_agregada'] or 0
        calorias_totales = agregados['calorias_totales_agregadas'] or 0
        entrenamientos_unicos = agregados['num_entrenamientos']

        # 3. Calcular métricas derivadas.
        intensidad_promedio = (volumen_total / duracion_total) if duracion_total > 0 else 0
        duracion_promedio = (duracion_total / entrenamientos_unicos) if entrenamientos_unicos > 0 else 0

        dias_periodo = (fecha_fin - fecha_inicio).days + 1
        frecuencia_semanal = (entrenamientos_unicos * 7) / dias_periodo if dias_periodo > 0 else 0

        # 4. Para métricas a nivel de ejercicio (consistencia, peso máx, etc.),
        # necesitamos consultar la tabla de ejercicios.
        ejercicios = self.obtener_ejercicios_tabla(fecha_inicio, fecha_fin)
        total_ejercicios = len(ejercicios)
        ejercicios_completados = len([e for e in ejercicios if e.get('completado', False)])
        consistencia = (ejercicios_completados / total_ejercicios * 100) if total_ejercicios > 0 else 0

        pesos = [float(e['peso']) for e in ejercicios if isinstance(e.get('peso'), (int, float)) and e.get('peso') > 0]
        peso_maximo = max(pesos) if pesos else 0
        peso_promedio = sum(pesos) / len(pesos) if pesos else 0

        # 5. Devolver el diccionario completo con valores consistentes.
        return {
            'volumen_total': volumen_total,
            'intensidad_promedio': intensidad_promedio,
            'calorias_totales': calorias_totales,
            'frecuencia_semanal': frecuencia_semanal,
            'duracion_promedio': duracion_promedio,
            'consistencia': consistencia,
            'total_ejercicios': total_ejercicios,
            'ejercicios_unicos': len(set(e['nombre'] for e in ejercicios)),
            'peso_promedio': peso_promedio,
            'peso_maximo': peso_maximo,
            'series_totales': sum(e.get('series', 1) for e in ejercicios),
            'repeticiones_totales': sum(e.get('series', 1) * e.get('repeticiones', 1) for e in ejercicios),
            'entrenamientos_unicos': entrenamientos_unicos
        }

    # Archivo: analytics/views.py
    # Dentro de la clase CalculadoraEjerciciosTabla

    def obtener_ejercicios_progresion(self, limite=5, datos_ejercicios=None):
        """
        Calcula la progresión de peso para cada ejercicio.
        - Acepta una lista de ejercicios pre-cargada para evitar consultas extra.
        - Puede devolver todos los resultados si limite es None.
        - Calcula tanto progresiones positivas como negativas/estancadas.
        """
        # Si no se proporciona una lista de ejercicios, la obtiene de la base de datos.
        # Esto mantiene la compatibilidad con otras partes de tu código que puedan llamarla sin parámetros.
        ejercicios = datos_ejercicios if datos_ejercicios is not None else self.obtener_ejercicios_tabla()

        # Agrupar todos los registros de ejercicio por su nombre normalizado (insensible a mayúsculas)
        ejercicios_por_nombre = {}
        for e in ejercicios:
            nombre_normalizado = e['nombre'].strip().lower()
            nombre_mostrado = e['nombre'].strip().title()

            if nombre_normalizado not in ejercicios_por_nombre:
                ejercicios_por_nombre[nombre_normalizado] = {
                    'nombre_mostrado': nombre_mostrado,
                    'ejercicios': []
                }
            ejercicios_por_nombre[nombre_normalizado]['ejercicios'].append(e)

        progresiones = []
        for datos in ejercicios_por_nombre.values():
            lista_ejercicios = datos['ejercicios']
            nombre_mostrado = datos['nombre_mostrado']

            # Se necesitan al menos dos sesiones para calcular una progresión
            if len(lista_ejercicios) < 2:
                continue

            # Ordenar las sesiones por fecha para encontrar la primera y la última
            lista_ejercicios.sort(key=lambda x: x['fecha'])

            primero = lista_ejercicios[0]
            ultimo = lista_ejercicios[-1]

            try:
                # Obtener pesos, tratando 'PC' (Peso Corporal) como 0 para el cálculo de progresión
                peso_inicial = float(primero.get('peso', 0)) if primero.get('peso') != 'PC' else 0
                peso_final = float(ultimo.get('peso', 0)) if ultimo.get('peso') != 'PC' else 0

                # Solo calculamos el porcentaje si el peso inicial era mayor que cero
                if peso_inicial > 0:
                    progresion_peso = ((peso_final - peso_inicial) / peso_inicial) * 100
                else:
                    # Si empezamos en 0 y subimos, es un progreso, pero no podemos dividir por cero.
                    # Podríamos asignarle un valor simbólico o simplemente 0.
                    progresion_peso = 100.0 if peso_final > 0 else 0.0

                # ✅ CAMBIO: Ya no filtramos por progresion_peso > 0. Guardamos todos los resultados.
                progresiones.append({
                    'nombre_ejercicio': nombre_mostrado,
                    'progresion_peso': progresion_peso,
                    'peso_inicial': peso_inicial,
                    'peso_final': peso_final,
                    'sesiones': len(lista_ejercicios)
                })

            except (ValueError, TypeError):
                # Si hay algún error en la conversión de datos, se omite ese ejercicio.
                continue

        # El print de depuración se ha eliminado para no ensuciar la consola.
        # Puedes volver a añadirlo si necesitas depurar algo específico.

        # ✅ CAMBIO: La lógica del límite se aplica al final.
        if limite is not None:
            # Ordenar por el valor de la progresión para devolver los "mejores"
            progresiones.sort(key=lambda x: x['progresion_peso'], reverse=True)
            return progresiones[:limite]
        else:
            # Si no hay límite, devuelve todos los resultados sin un orden específico
            return progresiones

    def obtener_datos_graficos(self, fecha_inicio=None, fecha_fin=None):
        """
        Obtiene datos para gráficos usando el campo de volumen pre-calculado
        del modelo EntrenoRealizado para garantizar la consistencia.
        """
        # 1. Construir la consulta base sobre EntrenoRealizado.
        query = EntrenoRealizado.objects.filter(cliente=self.cliente)

        # 2. Aplicar los filtros de fecha.
        if fecha_inicio:
            query = query.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            query = query.filter(fecha__lte=fecha_fin)

        # 3. Seleccionar solo los campos necesarios y ordenar por fecha.
        # Nos interesa la fecha y el volumen total que ya está guardado.
        entrenos_con_volumen = query.order_by('fecha').values('fecha', 'volumen_total_kg')

        # 4. Formatear los datos para el gráfico.
        # No hay necesidad de calcular nada, solo formatear.
        datos_volumen = [
            {
                'fecha': entreno['fecha'].strftime('%Y-%m-%d'),
                'volumen_total': entreno['volumen_total_kg'] or 0
            }
            for entreno in entrenos_con_volumen if entreno['volumen_total_kg'] is not None
        ]

        # El cálculo de intensidad ahora también usará el volumen correcto.
        datos_intensidad = []
        for item in datos_volumen:
            # Asume una duración de 60 min por sesión si no hay datos más precisos.
            intensidad = item['volumen_total'] / 60
            datos_intensidad.append({
                'fecha': item['fecha'],
                'intensidad_promedio': intensidad
            })

        return {
            'volumen_diario': datos_volumen,
            'intensidad_diaria': datos_intensidad
        }


class AnalisisProgresionAvanzado:
    """
    Análisis avanzado de progresión - VERSIÓN COMPLETA
    """

    def __init__(self, cliente):
        self.cliente = cliente
        self.ejercicios_principales = [
            'Press banca', 'Press inclinado', 'Sentadilla', 'Peso muerto',
            'Press militar', 'Dominadas', 'Remo', 'Hip thrust'
        ]
        self.mapeo_nombres = {
            # FUERZA PRINCIPALES
            'Press banca': ['press banca', 'press inclinado', 'press inclinado con barra', 'press en máquina',
                            'press declinado'],
            'Press inclinado': ['press inclinado', 'press inclinado con barra', 'press inclinado con mancuernas'],
            'Sentadilla': ['sentadilla', ',Sentadilla libre', 'sentadilla libre', 'sentadilla en multipower'],
            'Peso muerto': ['peso muerto', 'peso muerto rumano', 'peso muerto sumo'],
            'Remo': ['remo', 'remo en máquina hammer', 'remo con barra', 'remo en polea baja', 'remo con mancuernas'],
            'Dominadas': ['dominadas'],

            # HOMBROS
            'Press militar': ['press militar', 'press militar con maquina', 'press militar con barra',
                              'press militar sentado'],
            'Elevaciones laterales': ['elevaciones laterales'],
            'Elevaciones frontales': ['elevaciones frontales'],
            'Pájaros': ['pájaros', 'elevaciones posteriores', 'pájaro invertido'],
            'Face pull': ['face pull'],
            'Encogimientos trapecio': ['encogimientos con mancuernas', 'elevaciones trapecio'],

            # BÍCEPS
            'Curl': [
                'curl en polea baja', 'curl en banco scott', 'curl concentración', 'curl martillo',
                'curl alterno con mancuernas', 'curl con barra'
            ],

            # TRÍCEPS
            'Tríceps': [
                'extensión con mancuerna sobre cabeza', 'patada de tríceps', 'press francés',
                'extensión en polea alta', 'fondos en paralelas (tríceps)'
            ],

            # CORE
            'Core': [
                'twist ruso', 'rueda abdominal', 'tijeras abdominales', 'plancha', 'crunch en máquina',
                'crunch abdominal', 'elevaciones de piernas colgado'
            ],

            # GLÚTEOS
            'Glúteos': [
                'hip thrust', 'step up con mancuernas', 'abducción de cadera', 'patada de glúteo'
            ],

            # PIERNAS
            'Prensa': ['prensa', 'prensa inclinada'],
            'Extensiones cuadriceps': ['extensiones de cuádriceps'],
            'Femoral': ['curl femoral sentado', 'curl femoral tumbado'],
            'Gemelos': ['elevación de talones de pie', 'elevación de talones sentado'],
            'Zancadas': ['zancadas búlgaras', 'zancadas caminando'],

            # ESPALDA
            'Jalones': ['jalón tras nuca', 'jalón al pecho'],
            'Pull-over': ['pull-over en polea'],

            # PECHO
            'Aperturas': ['aperturas en contractor', 'aperturas con mancuernas'],
            'Fondos pecho': ['fondos en paralelas (pecho)'],

            # CARDIO
            'Cardio': [
                'battle ropes', 'mountain climbers', 'burpees', 'cuerda para saltar',
                'remo ergómetro', 'elíptica', 'bicicleta estática', 'cinta de correr'
            ]
            # Puedes seguir añadiendo más según tu base de datos
        }

    def calcular_ratios_fuerza(self):
        """
        Calcula ratios de fuerza para balance muscular
        """
        # Obtener 1RM estimados de ejercicios principales
        rms = self._obtener_1rm_ejercicios()

        if not rms:
            return {
                'ratios': [],
                'grafico_radar': {'labels': [], 'valores': [], 'optimos': []},
                'puntos_debiles': []
            }

        # Ratios internos (clave: identificador técnico)
        ratios = {
            'press_sentadilla': self._calcular_ratio(rms.get('Press banca', 0), rms.get('Sentadilla', 0)),
            'peso_muerto_sentadilla': self._calcular_ratio(rms.get('Peso muerto', 0), rms.get('Sentadilla', 0)),
            'press_militar_banca': self._calcular_ratio(rms.get('Press militar', 0), rms.get('Press banca', 0)),
            'dominadas_remo': self._calcular_ratio(rms.get('Dominadas', 0), rms.get('Remo', 0))
        }

        # Estándares definidos por clave interna
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
                    'clave': ratio_name,  # <- clave interna técnica
                    'nombre': ratio_name.replace('_', ' ').title(),  # <- nombre visual
                    'valor': valor,
                    'optimo': estandar['optimo'],
                    'estado': estado,
                    'recomendacion': self._generar_recomendacion_ratio(ratio_name, estado)
                })

        # Preparar solo los ratios válidos
        ratios_validos = {r['clave']: r['valor'] for r in analisis_ratios}
        estandares_validos = {clave: estandares[clave] for clave in ratios_validos}
        print("🧪 Ratios finales generados:", analisis_ratios)
        print("📊 Ratios para radar:", [r['nombre'] for r in analisis_ratios])

        return {
            'ratios': analisis_ratios,
            'grafico_radar': self._generar_datos_radar(ratios_validos, estandares_validos),
            'puntos_debiles': self._identificar_puntos_debiles(analisis_ratios)
        }

    def analisis_evolucion_temporal(self, ejercicio=None, periodo_dias=90):
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)
        ejercicios = [ejercicio] if ejercicio else list(self.obtener_ejercicios_registrados(periodo_dias).keys())
        resultados = {}
        for ej in ejercicios:
            datos = self._obtener_datos_temporales(ej, fecha_inicio)
            if datos:
                tendencia = self._calcular_tendencia_simple(datos)
                resultados[ej] = {
                    'datos': datos,
                    'tendencia': tendencia,
                    'volumen_por_grupo': sum(d['volumen'] for d in datos),
                    'hitos': [],
                    'predicciones': []
                }
        return resultados

    def analisis_mesociclos(self, periodo_dias=180):
        """
        Análisis de mesociclos para periodización
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        # Dividir en mesociclos de 4 semanas
        mesociclos = self._dividir_en_mesociclos(fecha_inicio, 28)

        analisis_mesociclos = []

        for i, (inicio, fin) in enumerate(mesociclos):
            datos_mesociclo = self._analizar_mesociclo(inicio, fin)

            # Comparar con mesociclo anterior
            if i > 0:
                mesociclo_anterior = analisis_mesociclos[i - 1]
                comparativa = self._comparar_mesociclos(datos_mesociclo, mesociclo_anterior['datos'])
                datos_mesociclo['comparativa'] = comparativa

            analisis_mesociclos.append({
                'numero': i + 1,
                'fecha_inicio': inicio,
                'fecha_fin': fin,
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

    def _obtener_1rm_ejercicios(self, dias=180):
        print("🔥 SE LLAMÓ A _obtener_1rm_ejercicios")
        """
        Calcula 1RM estimado usando fórmula de Brzycki, normalizando nombres y pesos.
        Acepta pesos con coma y maneja dominadas con peso 0 correctamente.
        """
        from entrenos.models import EjercicioRealizado
        fecha_limite = datetime.now().date() - timedelta(days=dias)

        registros = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente,
            entreno__fecha__gte=fecha_limite
        )

        rms = {}
        print("🧠 Nombres normalizados detectados en 1RM:")
        print("📂 Total ejercicios encontrados:", registros.count())

        for r in registros:
            nombre_raw = r.nombre_ejercicio.strip()
            nombre_norm = self._normalizar_nombre(nombre_raw)

            try:
                peso = float(r.peso_kg or 0)
                reps = int(r.repeticiones or 1)

                # ✅ Aceptamos Dominadas con peso 0 si el nombre contiene "dominadas"
                es_dominadas = 'dominadas' in nombre_norm.lower()

                if reps > 0 and reps <= 12 and (peso > 0 or es_dominadas):
                    rm_estimado = peso / (1.0278 - 0.0278 * reps)
                    if nombre_norm not in rms or rm_estimado > rms[nombre_norm]:
                        rms[nombre_norm] = round(rm_estimado, 1)

            except (ValueError, TypeError) as e:
                print(
                    f"⚠️ Error en '{nombre_raw}' → normalizado como {nombre_norm} | peso: {r.peso_kg}, reps: {r.repeticiones} | error: {e}")
                continue

        print("📦 1RM finales generados:", rms)
        return rms

    def _calcular_ratio(self, valor1, valor2):
        """
        Calcula ratio entre dos valores
        """
        if valor2 > 0:
            return round(valor1 / valor2, 2)
        return 0

    def _evaluar_ratio(self, valor, estandar):
        """
        Evalúa si un ratio está en rango óptimo
        """
        rango_min, rango_max = estandar['rango']

        if rango_min <= valor <= rango_max:
            return 'optimo'
        elif valor < rango_min:
            return 'bajo'
        else:
            return 'alto'

    def _generar_recomendacion_ratio(self, ratio_name, estado):
        """
        Genera recomendaciones basadas en ratios
        """
        recomendaciones = {
            'press_sentadilla': {
                'bajo': 'Enfócate en fortalecer el press de banca. Agrega más volumen de empuje horizontal.',
                'alto': 'Prioriza el entrenamiento de piernas. Aumenta frecuencia de sentadillas.',
                'optimo': 'Mantén el equilibrio actual entre empuje y piernas.'
            },
            'peso_muerto_sentadilla': {
                'bajo': 'Trabaja más el peso muerto y cadena posterior. Agrega RDL y hip thrust.',
                'alto': 'Equilibra con más trabajo de cuádriceps. Aumenta volumen de sentadillas.',
                'optimo': 'Excelente equilibrio entre cadena anterior y posterior.'
            },
            'press_militar_banca': {
                'bajo': 'Incrementa el trabajo de hombros. Agrega press militar y elevaciones.',
                'alto': 'Reduce volumen de press militar, mantén press banca.',
                'optimo': 'Buen equilibrio entre empuje horizontal y vertical.'
            },
            'dominadas_remo': {
                'bajo': 'Aumenta trabajo de dominadas y tracción vertical.',
                'alto': 'Equilibra con más remo horizontal.',
                'optimo': 'Excelente equilibrio en el trabajo de espalda.'
            }
        }

        return recomendaciones.get(ratio_name, {}).get(estado, 'Mantén el entrenamiento actual.')

    def _generar_datos_radar(self, ratios, estandares):
        """
        Genera datos para el gráfico radar
        """
        labels = []
        valores = []
        optimos = []

        for ratio_name, valor in ratios.items():
            if valor > 0:
                labels.append(ratio_name.replace('_', ' ').title())
                valores.append(valor)
                optimos.append(estandares[ratio_name]['optimo'])

        return {
            'labels': labels,
            'valores': valores,
            'optimos': optimos
        }

    def _identificar_puntos_debiles(self, analisis_ratios):
        """
        Identifica puntos débiles basados en ratios
        """
        puntos_debiles = []

        for ratio in analisis_ratios:
            if ratio['estado'] != 'optimo':
                puntos_debiles.append(f"{ratio['nombre']}: {ratio['recomendacion']}")

        return puntos_debiles

    def _obtener_datos_temporales(self, ejercicio, fecha_inicio):
        # 1. Normalizar el nombre del ejercicio
        nombre_norm = self._normalizar_nombre(ejercicio)

        # 2. Obtener todas las variantes desde el mapeo
        variantes = self.mapeo_nombres.get(nombre_norm, [nombre_norm])

        # 3. Buscar ejercicios equivalentes
        qs = (
            EjercicioRealizado.objects
            .filter(entreno__cliente=self.cliente,
                    nombre_ejercicio__in=variantes,
                    entreno__fecha__gte=fecha_inicio)
            .order_by('entreno__fecha')
        )

        datos = []
        for e in qs:
            try:
                peso = float(e.peso_kg or 0)
                reps = int(e.repeticiones or 1)
                series = int(e.series or 1)
                volumen = peso * reps * series
                rm_estimado = peso / (1.0278 - 0.0278 * reps) if reps <= 12 else peso
                intensidad = (peso / rm_estimado) * 100 if rm_estimado > 0 else 0
                datos.append({
                    'fecha': e.entreno.fecha.strftime('%Y-%m-%d'),
                    'peso': peso,
                    'repeticiones': reps,
                    'series': series,
                    'volumen': volumen,
                    'intensidad': round(intensidad, 1)
                })
            except:
                continue
        return datos

    def _calcular_tendencia_lineal(self, datos):
        """
        Calcula tendencia lineal usando regresión
        """
        if len(datos) < 3:
            return None

        try:
            from scipy import stats
            # Convertir fechas a números para regresión
            fechas_num = [
                (datetime.strptime(d['fecha'], '%Y-%m-%d') - datetime.strptime(datos[0]['fecha'], '%Y-%m-%d')).days for
                d in datos]
            pesos = [d['peso'] for d in datos]

            # Regresión lineal
            slope, intercept, r_value, p_value, std_err = stats.linregress(fechas_num, pesos)

            return {
                'pendiente': round(slope, 3),
                'intercepto': round(intercept, 2),
                'correlacion': round(r_value, 3),
                'p_value': round(p_value, 3),
                'tendencia_semanal': round(slope * 7, 2),
                'confianza': round(abs(r_value) * 100, 1)
            }

        except ImportError:
            return self._calcular_tendencia_simple(datos)

    def _calcular_tendencia_simple(self, datos):
        if len(datos) < 2:
            return None
        primer = datos[0]['peso']
        ultimo = datos[-1]['peso']
        dias = (datetime.strptime(datos[-1]['fecha'], "%Y-%m-%d") -
                datetime.strptime(datos[0]['fecha'], "%Y-%m-%d")).days
        cambio = ((ultimo - primer) / primer * 100) if primer > 0 else 0
        tendencia_semanal = cambio / dias * 7 if dias > 0 else 0
        return {
            'tendencia_semanal': round(tendencia_semanal, 2),
            'confianza': 75.0,
        }

    def _detectar_hitos(self, datos):
        """
        Detecta hitos importantes en la progresión
        """
        if not datos:
            return []

        hitos = []
        pesos = [d['peso'] for d in datos]

        # Peso máximo
        peso_max = max(pesos)
        fecha_max = next(d['fecha'] for d in datos if d['peso'] == peso_max)
        hitos.append({
            'tipo': 'record_personal',
            'fecha': fecha_max,
            'valor': peso_max,
            'descripcion': f'Nuevo récord personal: {peso_max} kg'
        })

        # Incrementos significativos (>5%)
        for i in range(1, len(datos)):
            if datos[i - 1]['peso'] > 0:
                incremento = ((datos[i]['peso'] - datos[i - 1]['peso']) / datos[i - 1]['peso']) * 100
                if incremento >= 5:
                    hitos.append({
                        'tipo': 'incremento_significativo',
                        'fecha': datos[i]['fecha'],
                        'valor': datos[i]['peso'],
                        'descripcion': f'Incremento del {incremento:.1f}%'
                    })

        return hitos

    def _generar_predicciones_temporales(self, datos, tendencia):
        """
        Genera predicciones basadas en progresión actual
        """
        if not tendencia or len(datos) < 3:
            return []

        ultimo_dato = datos[-1]
        fecha_base = datetime.strptime(ultimo_dato['fecha'], '%Y-%m-%d')

        predicciones = []

        # Predicciones a 4, 8 y 12 semanas
        for semanas in [4, 8, 12]:
            fecha_prediccion = fecha_base + timedelta(weeks=semanas)
            peso_predicho = ultimo_dato['peso'] + (tendencia['tendencia_semanal'] * semanas)

            # Ajustar confianza según tiempo
            confianza = max(tendencia['confianza'] - (semanas * 5), 30)

            predicciones.append({
                'fecha': fecha_prediccion.strftime('%Y-%m-%d'),
                'peso_estimado': round(peso_predicho, 1),
                'confianza': round(confianza, 1),
                'semanas': semanas
            })

        return predicciones

    def _calcular_volumen_grupo_muscular(self, ejercicio, fecha_inicio):
        """
        Calcula volumen total acumulado para un ejercicio específico desde EjercicioRealizado
        """
        from entrenos.models import EjercicioRealizado

        registros = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente,
            nombre_ejercicio__iexact=ejercicio,
            fecha_creacion__gte=fecha_inicio
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
        """
        Divide el período en mesociclos
        """
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
        """
        Analiza un mesociclo específico usando la fecha real del EntrenoRealizado
        """
        from entrenos.models import EjercicioRealizado

        registros = EjercicioRealizado.objects.filter(
            entreno__cliente=self.cliente,
            entreno__fecha__gte=fecha_inicio,
            entreno__fecha__lte=fecha_fin
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

        # Duración opcional: si deseas integrar en el futuro desde EntrenoRealizado
        duracion_total = 0

        return {
            'carga_total': carga_total,
            'duracion_total': duracion_total,
            'sesiones': sesiones,
            'carga_promedio': carga_total / sesiones if sesiones > 0 else 0,
            'duracion_promedio': duracion_total / sesiones if sesiones > 0 else 0
        }

    def _normalizar_nombre(self, nombre):
        nombre = nombre.strip().lower()
        for clave, alias in self.mapeo_nombres.items():
            if nombre in [a.lower() for a in alias]:
                return clave
        return nombre.title()

    def _comparar_mesociclos(self, mesociclo_actual, mesociclo_anterior):
        """
        Compara dos mesociclos
        """
        if not mesociclo_anterior:
            return None

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
        """
        Evalúa la efectividad de un mesociclo
        """
        if datos_mesociclo['sesiones'] >= 12 and datos_mesociclo['carga_promedio'] > 1000:
            return 'alta'
        elif datos_mesociclo['sesiones'] >= 8 and datos_mesociclo['carga_promedio'] > 500:
            return 'media'
        else:
            return 'baja'

    def _generar_recomendaciones_mesociclo(self, datos_mesociclo):
        """
        Genera recomendaciones para el mesociclo
        """
        recomendaciones = []

        if datos_mesociclo['sesiones'] < 8:
            recomendaciones.append('Aumentar frecuencia de entrenamiento')

        if datos_mesociclo['carga_promedio'] < 500:
            recomendaciones.append('Incrementar intensidad o volumen')

        if datos_mesociclo['duracion_promedio'] > 90:
            recomendaciones.append('Considerar reducir duración de sesiones')

        if not recomendaciones:
            recomendaciones.append('Mantener el enfoque actual')

        return recomendaciones

    def _sugerir_periodizacion_optima(self, analisis_mesociclos):
        """
        Sugiere periodización óptima
        """
        if not analisis_mesociclos:
            return "Datos insuficientes para sugerir periodización"

        efectividades = [m['efectividad'] for m in analisis_mesociclos]

        if efectividades.count('alta') > len(efectividades) / 2:
            return "Continúa con la periodización actual, está funcionando bien"
        else:
            return "Considera alternar mesociclos de alta y baja intensidad para mejor recuperación"

    def _identificar_picos_valles_rendimiento(self, analisis_mesociclos):
        """
        Identifica picos y valles de rendimiento
        """
        if len(analisis_mesociclos) < 3:
            return []

        picos_valles = []

        for i in range(1, len(analisis_mesociclos) - 1):
            actual = analisis_mesociclos[i]['datos']['carga_total']
            anterior = analisis_mesociclos[i - 1]['datos']['carga_total']
            siguiente = analisis_mesociclos[i + 1]['datos']['carga_total']

            if actual > anterior and actual > siguiente:
                picos_valles.append({
                    'tipo': 'pico',
                    'mesociclo': analisis_mesociclos[i]['numero'],
                    'valor': actual
                })
            elif actual < anterior and actual < siguiente:
                picos_valles.append({
                    'tipo': 'valle',
                    'mesociclo': analisis_mesociclos[i]['numero'],
                    'valor': actual
                })

        return picos_valles

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

    def _obtener_1rm_estimado(self, ejercicio, peso, reps):
        """
        Obtiene 1RM estimado para un ejercicio
        """
        if reps <= 12:
            return peso / (1.0278 - 0.0278 * reps)
        return peso * 1.3  # Estimación conservadora para altas repeticiones

    def obtener_ejercicios_registrados(self, dias=180):
        ejercicios = (
            EjercicioRealizado.objects
            .filter(entreno__cliente=self.cliente, fecha_creacion__gte=datetime.now().date() - timedelta(days=dias))
            .values_list('nombre_ejercicio', flat=True)
            .distinct()
        )
        ejercicios = sorted(set(self._normalizar_nombre(e) for e in ejercicios))
        return {e: e for e in ejercicios}
