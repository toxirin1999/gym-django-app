# Archivo: analytics/calculators.py

from entrenos.models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente
from django.db.models import Sum, Count


# (Si la clase usa otras importaciones, asegúrate de moverlas aquí también)

class CalculadoraEjerciciosTabla:
    """
    Calculadora que usa los datos de la tabla estructurada EjercicioRealizado.
    Ahora vive en su propio archivo para evitar dependencias circulares.
    """

    def __init__(self, cliente):
        self.cliente = cliente

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

    def calcular_1rm_estimado_por_ejercicio(self):
        # ... (el código de este método no cambia)
        todos_los_ejercicios = self.obtener_ejercicios_tabla()
        if not todos_los_ejercicios:
            return {}

        ejercicios_agrupados = {}
        for e in todos_los_ejercicios:
            nombre = e['nombre'].strip().title()
            if "Prensa" in nombre:
                print(f"DEBUG MAPPING: Original: {e['nombre']} -> Mapped: {nombre} | Weight: {e.get('peso')}")
            if "Hip Thrust" in nombre:
                print(f"DEBUG MAPPING: Original: {e['nombre']} -> Mapped: {nombre} | Weight: {e.get('peso')}")
            if nombre not in ejercicios_agrupados:
                ejercicios_agrupados[nombre] = []

            try:
                peso = float(e.get('peso', 0))
                reps = int(e.get('repeticiones', 0))
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

        pesos = [float(e['peso']) for e in ejercicios if
                 isinstance(e.get('peso'), (int, float)) and e.get('peso') > 0]
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
