# 🎯 VISTAS COMPLETAS DEL CENTRO DE ANÁLISIS - ADAPTADAS PARA TABLA EXISTENTE
# Archivo: analytics/views.py (VERSIÓN COMPLETA)
from django.shortcuts import render, get_object_or_404
import json
from decimal import Decimal
from analytics.planificador_helms_completo import PlanificadorHelms, PerfilCliente
from .calculators import CalculadoraEjerciciosTabla
from .analisis_progresion import AnalisisProgresionAvanzado
from .analisis_intensidad import AnalisisIntensidadAvanzado
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Avg, Max, Min, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
import json
from analytics.planificador import PlanificadorAvanzadoHelms
from decimal import Decimal
from entrenos.utils.utils import parse_reps_and_series
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado
from .models import (
    MetricaRendimiento, AnalisisEjercicio, TendenciaProgresion,
    PrediccionRendimiento, RecomendacionEntrenamiento, ComparativaRendimiento, MetaRendimiento, AnotacionEntrenamiento
)

from entrenos.models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente
import logging

logger = logging.getLogger(__name__)


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
    # Reemplaza la función calcular_1rm_estimado_por_ejercicio con esta versión CORREGIDA

    # Archivo: analytics/views.py
    # Reemplaza la función calcular_1rm_estimado_por_ejercicio con esta versión DEFINITIVA

    def calcular_1rm_estimado_por_ejercicio(self):
        """
        Calcula el 1RM estimado para cada movimiento principal.

        VERSIÓN DEFINITIVA:
        - Mapeo directo de ejercicios específicos a movimientos principales
        - Basado en la clasificación exacta de patrones de movimiento
        - Agrupa automáticamente variaciones de ejercicios
        - Devuelve el 1RM máximo para cada movimiento principal
        """

        # 1. MAPEO DIRECTO: Ejercicio específico -> Movimiento Principal
        # Este mapeo es la FUENTE DE VERDAD para clasificar ejercicios
        mapeo_ejercicios_a_principal = {
            # 🎯 REMO (Row) - Tracción Horizontal
            'remo con barra (pendlay)': 'Remo',
            'remo con mancuerna a una mano': 'Remo',
            'remo en polea baja (gironda)': 'Remo',

            # 🎯 PRESS BANCA (Bench Press) - Empuje Horizontal
            'press banca con barra': 'Press Banca',
            'press banca con mancuernas': 'Press Banca',
            'press inclinado con barra': 'Press Banca',
            'press inclinado con mancuernas': 'Press Banca',
            'press cerrado en banca': 'Press Banca',
            'fondos en paralelas (con lastre)': 'Press Banca',

            # 🎯 PRESS MILITAR (Overhead Press) - Empuje Vertical
            'press militar con barra (de pie)': 'Press Militar',
            'press militar con mancuernas (sentado)': 'Press Militar',
            'push press': 'Press Militar',
            'press arnold': 'Press Militar',

            # 🎯 PESO MUERTO (Deadlift) - Bisagra de Cadera
            'peso muerto': 'Peso Muerto',
            'peso muerto rumano': 'Peso Muerto',
            'peso muerto sumo': 'Peso Muerto',
            # 'buenos días (good mornings)': 'Peso Muerto', # Eliminado por ser accesorio
            # 'hip thrust con barra': 'Peso Muerto', # Eliminado: No es equivalente a peso muerto

            # 🎯 SENTADILLA (Squat) - Flexión de Rodilla
            'sentadilla trasera con barra': 'Sentadilla',
            'sentadilla frontal con barra': 'Sentadilla',
            'sentadilla búlgara': 'Sentadilla',
            # 'prensa de piernas': 'Sentadilla', # Eliminado: Sobrestima masivamente el 1RM
            # 'zancadas con mancuernas': 'Sentadilla', # Eliminado: Accesorio unilateral
        }

        # 2. Obtenemos todos los ejercicios realizados por el cliente
        todos_los_ejercicios = self.obtener_ejercicios_tabla()
        if not todos_los_ejercicios:
            return {}

        # 3. Calculamos el 1RM para cada levantamiento individual
        levantamientos_con_rm = []
        for e in todos_los_ejercicios:
            try:
                peso = float(e.get('peso', 0))
                reps = int(e.get('repeticiones', 0))

                if peso > 0 and reps > 0:
                    # Fórmula de Epley para estimar 1RM
                    rm_estimado = peso * (1 + (reps / 30))

                    # Normalizamos el nombre del ejercicio para la búsqueda
                    nombre_normalizado = e['nombre'].strip().lower()

                    # Buscamos el movimiento principal usando el mapeo directo
                    ejercicio_principal = mapeo_ejercicios_a_principal.get(nombre_normalizado, None)

                    # Si no encontramos mapeo directo, lo saltamos
                    if not ejercicio_principal:
                        print(f"⚠️ Ejercicio no mapeado: '{e['nombre']}'")
                        continue

                    levantamientos_con_rm.append({
                        'ejercicio_principal': ejercicio_principal,
                        'rm': rm_estimado,
                        'nombre_original': e['nombre'],
                    })
            except (ValueError, TypeError) as err:
                print(f"❌ Error procesando ejercicio: {e.get('nombre', 'desconocido')} - {err}")
                continue

        # 4. Agrupamos por ejercicio principal y encontramos el RM máximo
        one_rm_finales = {}
        for levantamiento in levantamientos_con_rm:
            principal = levantamiento['ejercicio_principal']
            rm = levantamiento['rm']

            if principal not in one_rm_finales or rm > one_rm_finales[principal]:
                one_rm_finales[principal] = rm

        # 5. Redondeamos los resultados finales
        for ejercicio, rm in one_rm_finales.items():
            one_rm_finales[ejercicio] = round(rm, 2)

        # 6. DEBUG: Imprimimos los resultados para verificar
        print("\n" + "=" * 60)
        print("🔍 1RMs CALCULADOS (VERSIÓN DEFINITIVA)")
        print("=" * 60)
        print(f"Total de ejercicios en mapeo: {len(mapeo_ejercicios_a_principal)}")
        print(f"Total de levantamientos procesados: {len(levantamientos_con_rm)}")
        print(f"\n1RMs finales calculados:")
        for principal, rm in sorted(one_rm_finales.items()):
            print(f"  ✅ {principal}: {rm} kg")
        print("=" * 60 + "\n")

        return one_rm_finales

    def calcular_volumen_por_grupo_muscular(self):
        """
        Calcula el volumen total por grupo muscular usando mapeo explícito de ejercicios.

        VERSIÓN CORREGIDA:
        - No depende del campo 'grupo_muscular' de la BD (que está vacío)
        - Usa un mapeo explícito de ejercicios a grupos musculares
        - Agrupa ejercicios relacionados correctamente
        """

        # MAPEO EXPLÍCITO: Ejercicio -> Grupo Muscular
        mapeo_ejercicio_a_grupo = {
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

            # ESPALDA
            'remo con barra (pendlay)': 'Espalda',
            'remo con mancuerna a una mano': 'Espalda',
            'remo en polea baja (gironda)': 'Espalda',
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
        }

        # Obtener todos los ejercicios
        todos_los_ejercicios = self.obtener_ejercicios_tabla()
        if not todos_los_ejercicios:
            return {}

        # Calcular volumen por grupo
        volumen_por_grupo = {}
        ejercicios_no_mapeados = set()

        for e in todos_los_ejercicios:
            try:
                # Normalizar nombre del ejercicio
                nombre_normalizado = e['nombre'].strip().lower()

                # Buscar el grupo muscular
                grupo = mapeo_ejercicio_a_grupo.get(nombre_normalizado, None)

                if not grupo:
                    ejercicios_no_mapeados.add(e['nombre'])
                    continue

                # Calcular volumen del ejercicio
                peso = float(e.get('peso', 0))
                series = int(e.get('series', 1))
                reps = int(e.get('repeticiones', 1))

                if peso > 0 and series > 0 and reps > 0:
                    volumen_ejercicio = peso * series * reps
                    volumen_por_grupo[grupo] = volumen_por_grupo.get(grupo, 0) + volumen_ejercicio

            except (ValueError, TypeError):
                continue

        # Debug
        if ejercicios_no_mapeados:
            print(f"\n⚠️ Ejercicios no mapeados a grupo muscular:")
            for ej in sorted(ejercicios_no_mapeados):
                print(f"  - {ej}")

        print(f"\n✅ Volumen por grupo muscular calculado:")
        for grupo, volumen in sorted(volumen_por_grupo.items(), key=lambda x: x[1], reverse=True):
            print(f"  {grupo}: {volumen:.2f} kg")

        return volumen_por_grupo

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

        # Archivo: analytics/views.py
        # Reemplaza el método obtener_progresion_completa_ejercicios con esta versión CORREGIDA

    def obtener_progresion_completa_ejercicios(self):
        """
        Calcula la progresión de TODOS los ejercicios del cliente desde el inicio.
        Devuelve una lista ordenada por progresión (de mayor a menor).

        VERSIÓN CORREGIDA: Maneja correctamente valores None en nombres de ejercicios.

        Cada elemento contiene:
        - nombre_ejercicio: Nombre del ejercicio
        - progresion_peso: Porcentaje de cambio de peso (positivo = mejora, negativo = empeora)
        - peso_inicial: Peso con el que empezó
        - peso_final: Peso actual
        - sesiones: Número de sesiones realizadas
        - 1rm_inicial: 1RM estimado al inicio
        - 1rm_final: 1RM estimado al final
        - cambio_1rm: Cambio en el 1RM estimado
        """
        # Obtener todos los ejercicios sin filtro de fecha
        ejercicios = self.obtener_ejercicios_tabla()

        if not ejercicios:
            return []

        # Agrupar ejercicios por nombre normalizado
        ejercicios_por_nombre = {}
        for e in ejercicios:
            # CORRECCIÓN: Verificar que el nombre no sea None antes de llamar a .strip()
            nombre_raw = e.get('nombre')

            # Si el nombre es None o está vacío, lo saltamos
            if not nombre_raw:
                continue

            nombre_normalizado = nombre_raw.strip().lower()
            nombre_mostrado = nombre_raw.strip().title()

            # Saltamos si después de limpiar queda vacío
            if not nombre_normalizado:
                continue

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

            # Ordenar las sesiones por fecha
            lista_ejercicios.sort(key=lambda x: x['fecha'])

            primero = lista_ejercicios[0]
            ultimo = lista_ejercicios[-1]

            try:
                # Obtener pesos - con manejo de None
                peso_inicial_raw = primero.get('peso')
                peso_final_raw = ultimo.get('peso')

                # Convertir a float, tratando None y 'PC' como 0
                if peso_inicial_raw is None or peso_inicial_raw == 'PC':
                    peso_inicial = 0
                else:
                    peso_inicial = float(peso_inicial_raw)

                if peso_final_raw is None or peso_final_raw == 'PC':
                    peso_final = 0
                else:
                    peso_final = float(peso_final_raw)

                # Calcular progresión de peso
                if peso_inicial > 0:
                    progresion_peso = ((peso_final - peso_inicial) / peso_inicial) * 100
                else:
                    progresion_peso = 100.0 if peso_final > 0 else 0.0

                # Calcular 1RM estimado (usando la fórmula de Epley)
                reps_inicial_raw = primero.get('repeticiones')
                reps_final_raw = ultimo.get('repeticiones')

                # Manejo de None para repeticiones
                reps_inicial = int(reps_inicial_raw) if reps_inicial_raw is not None else 1
                reps_final = int(reps_final_raw) if reps_final_raw is not None else 1

                rm_inicial = peso_inicial * (1 + (reps_inicial / 30)) if peso_inicial > 0 else 0
                rm_final = peso_final * (1 + (reps_final / 30)) if peso_final > 0 else 0

                cambio_rm = rm_final - rm_inicial

                # Determinar el color/estado basado en la progresión
                if progresion_peso > 0:
                    estado = 'mejora'
                elif progresion_peso < 0:
                    estado = 'empeora'
                else:
                    estado = 'estancado'

                progresiones.append({
                    'nombre_ejercicio': nombre_mostrado,
                    'progresion_peso': round(progresion_peso, 2),
                    'peso_inicial': round(peso_inicial, 2),
                    'peso_final': round(peso_final, 2),
                    'cambio_peso': round(peso_final - peso_inicial, 2),
                    'sesiones': len(lista_ejercicios),
                    '1rm_inicial': round(rm_inicial, 2),
                    '1rm_final': round(rm_final, 2),
                    'cambio_1rm': round(cambio_rm, 2),
                    'estado': estado,
                    'fecha_inicio': primero['fecha'],
                    'fecha_fin': ultimo['fecha']
                })

            except (ValueError, TypeError) as e:
                # Si hay algún error en la conversión de datos, lo registramos y continuamos
                print(f"⚠️ Error procesando ejercicio '{nombre_mostrado}': {str(e)}")
                continue

        # Ordenar por progresión de peso (de mayor a menor)
        progresiones.sort(key=lambda x: x['progresion_peso'], reverse=True)

        return progresiones

    def calcular_metricas_principales(self, fecha_inicio=None, fecha_fin=None):
        """
        Calcula todas las métricas principales.
        VERSIÓN CORREGIDA: Maneja correctamente los filtros de fecha opcionales.
        """
        # 1. Empezamos con la consulta base, filtrando solo por cliente.
        entrenamientos_qs = EntrenoRealizado.objects.filter(cliente=self.cliente)

        # 2. Aplicamos los filtros de fecha SOLO SI no son None.
        if fecha_inicio:
            entrenamientos_qs = entrenamientos_qs.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            entrenamientos_qs = entrenamientos_qs.filter(fecha__lte=fecha_fin)

        if not entrenamientos_qs.exists():
            return self._metricas_vacias()  # Usamos el método que ya tenías para devolver ceros.

        # 3. Usar funciones de agregación de Django para obtener los totales.
        agregados = entrenamientos_qs.aggregate(
            volumen_total_agregado=Sum('volumen_total_kg'),
            duracion_total_agregada=Sum('duracion_minutos'),
            calorias_totales_agregadas=Sum('calorias_quemadas'),
            num_entrenamientos=Count('id')
        )

        # Obtenemos la primera y última fecha del queryset para el cálculo de frecuencia
        # Hacemos esto DESPUÉS de aplicar los filtros.
        if not fecha_inicio:
            fecha_inicio = entrenamientos_qs.earliest('fecha').fecha
        if not fecha_fin:
            fecha_fin = entrenamientos_qs.latest('fecha').fecha

        volumen_total = agregados['volumen_total_agregado'] or 0
        duracion_total = agregados['duracion_total_agregada'] or 0
        calorias_totales = agregados['calorias_totales_agregadas'] or 0
        entrenamientos_unicos = agregados['num_entrenamientos']

        # 4. Calcular métricas derivadas.
        intensidad_promedio = (volumen_total / duracion_total) if duracion_total > 0 else 0
        duracion_promedio = (duracion_total / entrenamientos_unicos) if entrenamientos_unicos > 0 else 0

        dias_periodo = (fecha_fin - fecha_inicio).days + 1
        frecuencia_semanal = (entrenamientos_unicos * 7) / dias_periodo if dias_periodo > 0 else 0

        # 5. Para métricas a nivel de ejercicio, llamamos a obtener_ejercicios_tabla
        # pasando las mismas fechas (o None)
        ejercicios = self.obtener_ejercicios_tabla(fecha_inicio, fecha_fin)
        total_ejercicios = len(ejercicios)
        ejercicios_completados = len([e for e in ejercicios if e.get('completado', False)])
        consistencia = (ejercicios_completados / total_ejercicios * 100) if total_ejercicios > 0 else 0

        pesos = [float(e['peso']) for e in ejercicios if
                 isinstance(e.get('peso'), (int, float, Decimal)) and e.get('peso') > 0]
        peso_maximo = max(pesos) if pesos else 0
        peso_promedio = sum(pesos) / len(pesos) if pesos else 0

        # 6. Devolver el diccionario completo.
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

        # Archivo: analytics/views.py
        # ... dentro de la clase CalculadoraEjerciciosTabla ...

    def analizar_acwr(self, periodo_dias=90, periodo_agudo=7, periodo_cronico=28):
        """
        Calcula la Carga Aguda, Carga Crónica y el ratio ACWR.
        Utiliza pandas para un cálculo eficiente.
        VERSIÓN CORREGIDA: Convierte Decimal a float para ser serializable en JSON.
        """
        try:
            import pandas as pd
        except ImportError:
            return {'dataframe': [], 'acwr_actual': 0, 'zona_riesgo': 'desconocida',
                    'recomendacion': 'Pandas no está instalado.'}
        # Buscamos la fecha del último entrenamiento registrado para este cliente
        ultimo_entreno = EntrenoRealizado.objects.filter(cliente=self.cliente).order_by('-fecha').first()
        fecha_fin = ultimo_entreno.fecha if ultimo_entreno else timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=periodo_dias)

        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        ).order_by('fecha').values('fecha', 'volumen_total_kg')

        if not entrenamientos:
            return {'dataframe': [], 'acwr_actual': 0, 'zona_riesgo': 'muy_baja',
                    'recomendacion': 'No hay datos suficientes.'}

        df = pd.DataFrame(list(entrenamientos))
        df['fecha'] = pd.to_datetime(df['fecha'])

        # Convertir Decimal a float aquí
        df['volumen_total_kg'] = df['volumen_total_kg'].astype(float)

        df = df.groupby('fecha')['volumen_total_kg'].sum().reset_index()
        df['carga_diaria'] = df['volumen_total_kg'] / 1000

        idx = pd.date_range(start=fecha_inicio, end=fecha_fin)
        df = df.set_index('fecha').reindex(idx, fill_value=0)

        df['carga_aguda'] = df['carga_diaria'].rolling(window=periodo_agudo, min_periods=1).mean()
        df['carga_cronica'] = df['carga_diaria'].rolling(window=periodo_cronico, min_periods=1).mean()
        df['acwr'] = (df['carga_aguda'] / df['carga_cronica']).fillna(0).replace([np.inf, -np.inf], 0)

        acwr_actual = round(df['acwr'].iloc[-1], 2) if not df.empty else 0

        if 0.8 <= acwr_actual <= 1.3:
            zona_riesgo = 'optima'
            recomendacion = "Estás en la 'zona dulce'. La carga es ideal para progresar de forma segura."
        elif 1.3 < acwr_actual < 1.5:
            zona_riesgo = 'cuidado'
            recomendacion = "Estás aumentando la carga. Procede con cuidado y vigila la recuperación."
        elif acwr_actual >= 1.5:
            zona_riesgo = 'riesgo_alto'
            recomendacion = "¡Peligro! El riesgo de lesión es elevado. Considera reducir la intensidad o el volumen."
        else:
            zona_riesgo = 'baja_carga'
            recomendacion = "La carga es baja. Ideal para una semana de descarga, pero riesgosa para perder adaptaciones si se mantiene."

        df_json = df.reset_index().rename(columns={'index': 'fecha'})
        df_json['fecha'] = df_json['fecha'].dt.strftime('%Y-%m-%d')

        return {
            'dataframe': df_json.to_dict('records'),
            'acwr_actual': acwr_actual,
            'zona_riesgo': zona_riesgo,
            'recomendacion': recomendacion
        }

    def analizar_equilibrio_muscular(self):
        """
        Calcula ratios de fuerza. Ahora usa los nombres de los ejercicios principales del mapeo.
        """
        one_rm_estimados = self.calcular_1rm_estimado_por_ejercicio()

        # Usamos los nombres de los ejercicios PRINCIPALES (las claves del mapeo)
        config_ratios = {
            'Press Banca / Sentadilla': ('Press Banca', 'Sentadilla'),
            'Peso Muerto / Sentadilla': ('Peso Muerto', 'Sentadilla'),
            'Press Militar / Press Banca': ('Press Militar', 'Press Banca'),
            'Remo / Press Banca': ('Remo', 'Press Banca')
        }

        resultados = []
        datos_radar = {'labels': [], 'valores': []}

        for nombre_ratio, (ej_num, ej_den) in config_ratios.items():
            valor_num = one_rm_estimados.get(ej_num, 0)
            valor_den = one_rm_estimados.get(ej_den, 0)

            ratio = 0
            if valor_num > 0 and valor_den > 0:
                ratio = round(valor_num / valor_den, 2)

            resultados.append({
                'nombre': nombre_ratio,
                'ratio': ratio,
                'ejercicio_numerador': ej_num,
                'valor_numerador': valor_num,
                'ejercicio_denominador': ej_den,
                'valor_denominador': valor_den
            })
            datos_radar['labels'].append(nombre_ratio)
            datos_radar['valores'].append(ratio)

        return {'tabla_ratios': resultados, 'datos_radar': datos_radar}


from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import timedelta
import json
from .models import RecomendacionEntrenamiento
from entrenos.models import EntrenoRealizado
from clientes.models import Cliente
from .analisis_intensidad import AnalisisIntensidadAvanzado
from datetime import datetime  # Asegúrate de que datetime esté importado


# -------------------------------------------------------------------------
# VISTA: EXPLICACIÓN DEL PLAN ACTUAL (HELMS)
# -------------------------------------------------------------------------
@login_required
def explicacion_plan_helms(request):
    """
    Vista que explica al usuario en qué fase del plan se encuentra,
    por qué está haciendo lo que hace (RPE, rangos) y ejemplos visuales.
    """
    cliente = get_object_or_404(Cliente, user=request.user)
    
    # 1. Instanciar Planificador y Perfil
    # Necesitamos los máximos actuales para ejemplos precisos
    calc = CalculadoraEjerciciosTabla(cliente)
    maximos = calc.calcular_1rm_estimado_por_ejercicio()
    
    # Convertir a formato compatible con PerfilCliente si es necesario
    # PerfilCliente espera diccionario o objeto, aquí pasamos un dict enriquecido
    perfil_data = {
        'id': cliente.id,
        'nombre': cliente.nombre,
        'experiencia_años': cliente.experiencia_años, # Asumiendo campo en modelo
        'objetivo_principal': cliente.objetivo_principal,
        'dias_disponibles': cliente.dias_disponibles,
        'maximos_actuales': maximos,
        # Otros campos requeridos por PerfilCliente con defaults
        'nivel_estres': 5,
        'calidad_sueño': 7,
        'nivel_energia': 7,
    }
    
    perfil = PerfilCliente(perfil_data)
    planificador = PlanificadorHelms(perfil)
    
    # 2. Obtener el plan anual completo
    plan_anual = planificador.generar_plan_anual()
    
    # 3. Determinar dónde estamos HOY
    hoy = timezone.now().date()
    # Para testing/demo podemos forzar una fecha si el plan empieza en otro momento
    # hoy = date(2024, 1, 15) 
    
    bloque_actual_info = None
    semana_actual_display = 0
    total_semanas_bloque = 0
    fase_actual = "Desconocida"
    descripcion_fase = "No se ha encontrado un plan activo para hoy."
    parametros_fase = {}
    
    # Buscar en entrenos_por_fecha primero para exactitud diaria
    fecha_iso = hoy.isoformat()
    entreno_hoy_data = plan_anual['entrenos_por_fecha'].get(fecha_iso)
    
    # Si no hay entreno justo hoy, buscar el bloque por rango de fechas (aproximación)
    # Como PlanificadorHelms devuelve estructura plana, iteramos bloques y sus semanas
    
    # Lógica simplificada basada en la estructura de plan_por_bloques
    # plan_por_bloques es una lista de dicts
    
    # Recorremos para encontrar el bloque actual
    # Esto es complejo porque plan_por_bloques no tiene fechas absolutas explícitas en el nivel superior,
    # pero las semanas sí tienen numeración global.
    
    fechas_ordenadas = sorted(plan_anual['entrenos_por_fecha'].keys())
    if fechas_ordenadas:
        primera_fecha = datetime.fromisoformat(fechas_ordenadas[0]).date()
        ultima_fecha = datetime.fromisoformat(fechas_ordenadas[-1]).date()
        
        bloques_disponibles = plan_anual.get('plan_por_bloques', [])
        if hoy < primera_fecha:
            estado_plan = "El plan aún no ha comenzado"
            bloque_target = bloques_disponibles[0] if bloques_disponibles else None
        elif hoy > ultima_fecha:
            estado_plan = "El plan anual ha finalizado"
            bloque_target = bloques_disponibles[-1] if bloques_disponibles else None
        else:
            estado_plan = "Activo"
            # Determinar semana actual relativa al inicio
            delta_days = (hoy - primera_fecha).days
            semana_global_actual = (delta_days // 7) + 1
            
            # Buscar qué bloque contiene esta semana global
            acumulado_semanas = 0
            bloque_target = None
            for bloque in plan_anual['plan_por_bloques']:
                duracion = bloque['duracion'] # num semanas
                if acumulado_semanas < semana_global_actual <= (acumulado_semanas + duracion):
                    bloque_target = bloque
                    semana_actual_display = semana_global_actual - acumulado_semanas
                    break
                acumulado_semanas += duracion
                
    else:
        # Fallback si no hay fechas
        estado_plan = "Sin plan generado"
        bloque_target = None

    if bloque_target:
        fase_actual = bloque_target.get('nombre', 'Fase General')
        objetivo_fase = bloque_target.get('objetivo', 'Hipertrofia')
        descripcion_fase = bloque_target.get('descripcion', 'Fase enfocada en el desarrollo muscular y mejora de la capacidad de trabajo.')
        total_semanas_bloque = bloque_target.get('duracion', 4)
        semana_actual_display = semana_actual_display if semana_actual_display > 0 else 1
        
        # Extraer parámetros de una semana típica del bloque (la primera)
        # Nota: La estructura legacy vs refactored puede variar.
        # Asumimos que bloque_target tiene la info cruda o necesitamos inferirla
        
        # Mapeo de objetivos a descripción user-friendly paramétrica
        parametros_fase = {
            'rpe_target': "7-8",
            'rango_reps': "8-12",
            'enfoque': objetivo_fase.title()
        }

        if 'fuerza' in objetivo_fase.lower():
            parametros_fase['rpe_target'] = "8-9"
            parametros_fase['rango_reps'] = "3-6"
        elif 'metabolico' in objetivo_fase.lower() or 'resistencia' in objetivo_fase.lower():
            parametros_fase['rpe_target'] = "6-8"
            parametros_fase['rango_reps'] = "12-15"

        # Descripción legible del RIR (Reps In Reserve) a partir del RPE objetivo
        _rpe_max = int(parametros_fase['rpe_target'].split('-')[-1])
        _rir = 10 - _rpe_max
        if _rir == 0:
            parametros_fase['rpe_target_desc'] = "ninguna"
        elif _rir == 1:
            parametros_fase['rpe_target_desc'] = "1"
        else:
            parametros_fase['rpe_target_desc'] = f"{_rir}-{_rir + 1}"
            
    # 4. Generar Ejemplos Calculados (Big 3 + Militar)
    ejemplos_calculados = []
    ejercicios_clave = [
        ('Sentadilla', 'Sentadilla'),
        ('Press Banca', 'Press Banca'),
        ('Peso Muerto', 'Peso Muerto'),
        ('Press Militar', 'Press Militar')
    ]
    
    # Usar CalculadorPeso para obtener números reales
    from analytics.planificador_helms.calculo.peso import CalculadorPeso
    
    rpe_obj = 8 # Promedio para el ejemplo
    reps_obj = "8" # Promedio
    
    # Intentar parsear del bloque si existe
    if 'rpe_target' in parametros_fase:
        try:
            rpe_obj = int(parametros_fase['rpe_target'].split('-')[-1])
        except: pass
        
    if 'rango_reps' in parametros_fase:
        try:
            reps_obj = parametros_fase['rango_reps'].split('-')[0]
        except: pass

    for nombre_mostrar, nombre_clave in ejercicios_clave:
        rm_est = maximos.get(nombre_clave, 0)
        
        # Solo mostrar si tiene 1RM
        if rm_est > 0:
            peso_sugerido = CalculadorPeso.calcular_peso_trabajo(
                nombre_ejercicio=nombre_clave,
                repeticiones_str=reps_obj,
                rpe_objetivo=rpe_obj,
                maximos_actuales=maximos
            )
            
            porcentaje_uso = (peso_sugerido / rm_est * 100) if rm_est > 0 else 0
            
            ejemplos_calculados.append({
                'ejercicio': nombre_mostrar,
                'rm_actual': rm_est,
                'peso_target': peso_sugerido,
                'porcentaje': round(porcentaje_uso),
                'schema_reps': f"{reps_obj} reps @ RPE {rpe_obj}"
            })
            
    # 5. Construir datos de timeline para el template
    bloques_plan = []
    if fechas_ordenadas:
        acum_semanas = 0
        total_semanas_plan = sum(b['duracion'] for b in plan_anual['plan_por_bloques'])
        for bloque in plan_anual['plan_por_bloques']:
            dur = bloque['duracion']
            fecha_inicio_bloque = primera_fecha + timedelta(weeks=acum_semanas)
            fecha_fin_bloque = primera_fecha + timedelta(weeks=acum_semanas + dur) - timedelta(days=1)
            
            # Determinar tipo de fase para color
            objetivo = bloque.get('objetivo', '').lower()
            if objetivo == 'descarga':
                tipo_color = 'descarga'
            elif 'fuerza' in objetivo:
                tipo_color = 'fuerza'
            elif 'potencia' in objetivo:
                tipo_color = 'potencia'
            else:
                tipo_color = 'hipertrofia'
            
            # Obtener rep_range y rpe de la periodización original
            rep_range = ''
            rpe_display = ''
            for bloque_orig in plan_anual.get('metadata', {}).get('periodizacion_completa', []):
                if bloque_orig['nombre'] == bloque['nombre']:
                    rep_range = bloque_orig.get('rep_range', '')
                    rpe_i = bloque_orig.get('rpe_inicio', '')
                    rpe_f = bloque_orig.get('rpe_fin', '')
                    rpe_display = f"{rpe_i}-{rpe_f}" if rpe_i != rpe_f else str(rpe_i)
                    break
            
            bloques_plan.append({
                'nombre': bloque['nombre'],
                'objetivo': bloque.get('objetivo', ''),
                'descripcion': bloque.get('descripcion', ''),
                'duracion': dur,
                'fecha_inicio': fecha_inicio_bloque,
                'fecha_fin': fecha_fin_bloque,
                'es_actual': (bloque_target is not None and bloque['nombre'] == bloque_target.get('nombre', '')),
                'es_descarga': objetivo == 'descarga',
                'tipo_color': tipo_color,
                'porcentaje_anual': round((dur / total_semanas_plan) * 100, 1),
                'rep_range': rep_range,
                'rpe': rpe_display,
            })
            acum_semanas += dur

    # 6. Detectar transiciones de fase y guardar snapshots de 1RM
    # Solo se ejecuta cuando el plan está activo; escribe a BD únicamente si hay un cambio real.
    from analytics.models import HistorialFase

    if bloque_target and estado_plan == "Activo":
        fase_activa_bd = HistorialFase.obtener_fase_activa(cliente)
        nombre_fase_actual = bloque_target.get('nombre', '')
        objetivo_actual = bloque_target.get('objetivo', '').lower()

        if objetivo_actual == 'descarga':
            tipo_fase_actual = 'descarga'
        elif 'fuerza' in objetivo_actual:
            tipo_fase_actual = 'fuerza'
        elif 'potencia' in objetivo_actual:
            tipo_fase_actual = 'potencia'
        elif 'metabolico' in objetivo_actual or 'metabólica' in objetivo_actual:
            tipo_fase_actual = 'hipertrofia_metabolica'
        elif 'específica' in objetivo_actual:
            tipo_fase_actual = 'hipertrofia_especifica'
        else:
            tipo_fase_actual = 'hipertrofia'

        bloque_actual_info = next((b for b in bloques_plan if b['es_actual']), None)

        if bloque_actual_info:
            def _rpe_int(bloque_info, idx):
                raw = bloque_info.get('rpe', '')
                try:
                    return int(raw.split('-')[idx])
                except (ValueError, IndexError):
                    return None

            if not fase_activa_bd:
                # Caso 1: Primera vez — crear registro inicial
                HistorialFase.objects.create(
                    cliente=cliente,
                    nombre_fase=nombre_fase_actual,
                    tipo_fase=tipo_fase_actual,
                    fecha_inicio=bloque_actual_info['fecha_inicio'],
                    semanas_planificadas=bloque_actual_info['duracion'],
                    rm_inicio=maximos,
                    activa=True,
                    rpe_inicio=_rpe_int(bloque_actual_info, 0),
                    rpe_fin=_rpe_int(bloque_actual_info, -1),
                    rango_reps=bloque_actual_info.get('rep_range', ''),
                )

            elif fase_activa_bd.nombre_fase != nombre_fase_actual:
                # Caso 2: Cambio de fase — cerrar la anterior y abrir la nueva
                fase_activa_bd.marcar_como_completada(maximos)
                fase_activa_bd.fecha_fin = hoy - timedelta(days=1)
                fase_activa_bd.semanas_completadas = (hoy - fase_activa_bd.fecha_inicio).days // 7
                fase_activa_bd.save()

                HistorialFase.objects.create(
                    cliente=cliente,
                    nombre_fase=nombre_fase_actual,
                    tipo_fase=tipo_fase_actual,
                    fecha_inicio=bloque_actual_info['fecha_inicio'],
                    semanas_planificadas=bloque_actual_info['duracion'],
                    rm_inicio=maximos,
                    activa=True,
                    rpe_inicio=_rpe_int(bloque_actual_info, 0),
                    rpe_fin=_rpe_int(bloque_actual_info, -1),
                    rango_reps=bloque_actual_info.get('rep_range', ''),
                )

            else:
                # Caso 3: Misma fase — solo escribe si el contador de semanas cambió
                semanas_transcurridas = (hoy - fase_activa_bd.fecha_inicio).days // 7
                if semanas_transcurridas != fase_activa_bd.semanas_completadas:
                    fase_activa_bd.semanas_completadas = semanas_transcurridas
                    fase_activa_bd.save()
    
    # 7. Obtener historial de fases completadas para mostrar en el template
    fases_completadas = HistorialFase.obtener_fases_completadas(cliente)[:5]  # Últimas 5

    # 8. Calcular predicciones de 1RM basadas en tendencias históricas
    predicciones_1rm = {}
    
    if fases_completadas.count() >= 2 and bloque_target:
        # Necesitamos al menos 2 fases completadas para calcular tendencia
        ejercicios_principales = ['Sentadilla', 'Press Banca', 'Peso Muerto', 'Press Militar']
        
        for ejercicio in ejercicios_principales:
            rm_actual = maximos.get(ejercicio, 0)
            
            if rm_actual > 0:
                # Calcular tasa de ganancia promedio de las últimas fases
                ganancias = []
                
                for fase in fases_completadas[:3]:  # Últimas 3 fases
                    if fase.rm_inicio and fase.rm_fin:
                        rm_ini = fase.rm_inicio.get(ejercicio)
                        rm_fin = fase.rm_fin.get(ejercicio)
                        
                        if rm_ini and rm_fin and rm_ini > 0:
                            ganancia_pct = ((rm_fin - rm_ini) / rm_ini) * 100
                            ganancias.append(ganancia_pct)
                
                if ganancias:
                    # Promedio de ganancia por fase
                    ganancia_promedio_pct = sum(ganancias) / len(ganancias)
                    
                    # Proyectar ganancia para la fase actual
                    # Ajustar según el tipo de fase (fuerza gana más en 1RM que hipertrofia)
                    objetivo_actual = bloque_target.get('objetivo', '').lower()
                    multiplicador = 1.0
                    
                    if 'fuerza' in objetivo_actual:
                        multiplicador = 1.2  # Fases de fuerza suelen ganar más en 1RM
                    elif 'potencia' in objetivo_actual:
                        multiplicador = 1.15
                    elif 'hipertrofia' in objetivo_actual:
                        multiplicador = 0.8  # Hipertrofia gana menos en 1RM directo
                    elif 'descarga' in objetivo_actual:
                        multiplicador = 0.0  # Descarga mantiene
                    
                    ganancia_proyectada_pct = ganancia_promedio_pct * multiplicador
                    ganancia_proyectada_kg = rm_actual * (ganancia_proyectada_pct / 100)
                    rm_proyectado = rm_actual + ganancia_proyectada_kg
                    
                    # Confianza basada en cantidad de datos históricos
                    confianza = min(len(ganancias) * 30, 90)  # Max 90%
                    
                    predicciones_1rm[ejercicio] = {
                        'actual': round(rm_actual, 1),
                        'proyectado': round(rm_proyectado, 1),
                        'ganancia_kg': round(ganancia_proyectada_kg, 1),
                        'ganancia_pct': round(ganancia_proyectada_pct, 1),
                        'confianza': confianza,
                        'tendencia': 'positiva' if ganancia_proyectada_pct > 0 else 'neutral'
                    }

    # 9. Comparativa de fases: Agrupar por tipo y calcular estadísticas
    comparativa_fases = {}
    
    if fases_completadas.count() >= 2:
        # Agrupar fases por tipo
        from collections import defaultdict
        fases_por_tipo = defaultdict(list)
        
        for fase in fases_completadas:
            fases_por_tipo[fase.tipo_fase].append(fase)
        
        # Calcular estadísticas por tipo de fase
        for tipo_fase, fases in fases_por_tipo.items():
            if not fases:
                continue
                
            # Calcular ganancia promedio
            ganancias_totales = [f.ganancia_promedio for f in fases if f.ganancia_promedio]
            ganancia_prom = sum(ganancias_totales) / len(ganancias_totales) if ganancias_totales else 0
            
            # Encontrar mejor ejercicio (mayor ganancia absoluta promedio)
            ejercicios_ganancias = defaultdict(list)
            
            for fase in fases:
                if fase.rm_inicio and fase.rm_fin:
                    for ejercicio in fase.rm_fin.keys():
                        rm_ini = fase.rm_inicio.get(ejercicio, 0)
                        rm_fin = fase.rm_fin.get(ejercicio, 0)
                        if rm_ini > 0:
                            ganancia_kg = rm_fin - rm_ini
                            ejercicios_ganancias[ejercicio].append(ganancia_kg)
            
            mejor_ejercicio = None
            mejor_ganancia = 0
            
            for ejercicio, ganancias in ejercicios_ganancias.items():
                ganancia_prom_ej = sum(ganancias) / len(ganancias)
                if ganancia_prom_ej > mejor_ganancia:
                    mejor_ganancia = ganancia_prom_ej
                    mejor_ejercicio = ejercicio
            
            # Calcular duración total en este tipo de fase
            semanas_totales = sum(f.semanas_completadas for f in fases)
            
            comparativa_fases[tipo_fase] = {
                'nombre_display': dict(HistorialFase._meta.get_field('tipo_fase').choices).get(tipo_fase, tipo_fase),
                'cantidad_fases': len(fases),
                'ganancia_promedio': round(ganancia_prom, 1),
                'mejor_ejercicio': mejor_ejercicio,
                'mejor_ganancia_kg': round(mejor_ganancia, 1) if mejor_ejercicio else 0,
                'semanas_totales': semanas_totales,
                'efectividad': 'alta' if ganancia_prom > 3 else ('media' if ganancia_prom > 1.5 else 'baja')
            }


    # Etiquetas de mes dinámicas para el timeline (basadas en la fecha real de inicio del plan)
    MESES_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    if fechas_ordenadas:
        mes_inicio = datetime.fromisoformat(fechas_ordenadas[0]).month  # 1-12
        timeline_meses = [MESES_ES[(mes_inicio - 1 + i) % 12] for i in range(12)]
    else:
        timeline_meses = MESES_ES[:]

    context = {
        'cliente': cliente,
        'fase_actual': fase_actual,
        'descripcion': descripcion_fase,
        'semana_actual': semana_actual_display,
        'total_semanas': total_semanas_bloque,
        'progreso_bloque': (semana_actual_display / total_semanas_bloque * 100) if total_semanas_bloque > 0 else 0,
        'parametros': parametros_fase,
        'ejemplos': ejemplos_calculados,
        'hoy': hoy,
        'bloques_plan': bloques_plan,
        'año_plan': plan_anual.get('metadata', {}).get('año_planificacion', hoy.year),
        'fases_completadas': fases_completadas,
        'predicciones_1rm': predicciones_1rm,
        'comparativa_fases': comparativa_fases,
        'timeline_meses': timeline_meses,
    }
    
    return render(request, 'analytics/explicacion_helms.html', context)


# ... (tus imports)
from .analisis_intensidad import AnalisisIntensidadAvanzado  # Asegúrate de que esté importado


@login_required
def dashboard(request, cliente_id=None):
    """
    Dashboard principal del centro de análisis con todas las mejoras implementadas.
    """
    if cliente_id:
        cliente = get_object_or_404(Cliente, id=cliente_id)
    else:
        cliente = Cliente.objects.first()
        if not cliente:
            return render(request, 'analytics/no_data.html')

    # --- 1. GESTIÓN DE FECHAS ---
    try:
        fecha_inicio_str = request.GET.get('fecha_inicio')
        fecha_fin_str = request.GET.get('fecha_fin')
        fecha_inicio_actual = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin_actual = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        fecha_fin_actual = timezone.now().date()
        fecha_inicio_actual = fecha_fin_actual - timedelta(days=30)

    duracion_periodo_dias = (fecha_fin_actual - fecha_inicio_actual).days
    fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
    fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=duracion_periodo_dias)

    # --- 2. CÁLCULO DE MÉTRICAS Y COMPARATIVAS ---
    calculadora = CalculadoraEjerciciosTabla(cliente)
    metricas_actuales = calculadora.calcular_metricas_principales(fecha_inicio_actual, fecha_fin_actual)
    metricas_anteriores = calculadora.calcular_metricas_principales(fecha_inicio_anterior, fecha_fin_anterior)

    comparativas = {}
    metricas_a_comparar = ['volumen_total', 'intensidad_promedio', 'calorias_totales', 'frecuencia_semanal',
                           'duracion_promedio', 'consistencia']
    for metrica in metricas_a_comparar:
        actual = metricas_actuales.get(metrica, 0)
        anterior = metricas_anteriores.get(metrica, 0)
        diferencia_pct = ((actual - anterior) / anterior * 100) if anterior > 0 else (100.0 if actual > 0 else 0.0)
        comparativas[metrica] = {'actual': actual, 'anterior': anterior, 'diferencia_pct': diferencia_pct}

    # --- 3. OBTENCIÓN DE DATOS PARA EL DASHBOARD ---

    # Datos generales
    entrenamientos_recientes = EntrenoRealizado.objects.filter(cliente=cliente, fecha__gte=fecha_inicio_actual,
                                                               fecha__lte=fecha_fin_actual).order_by('-fecha')[:10]
    recomendaciones = RecomendacionEntrenamiento.objects.filter(cliente=cliente, expires_at__gt=timezone.now(),
                                                                aplicada=False).order_by('prioridad')[:5]
    datos_graficos = calculadora.obtener_datos_graficos(fecha_inicio_actual, fecha_fin_actual)

    # Análisis de Estado del Atleta
    try:
        analizador_intensidad = AnalisisIntensidadAvanzado(cliente)
        estado_atleta = analizador_intensidad.calcular_fatiga_acumulada(periodo_dias=14)
    except Exception as e:
        print(f"Error al calcular el estado del atleta: {e}")
        estado_atleta = None

    # Análisis detallado de Ejercicios
    ejercicios_del_periodo = calculadora.obtener_ejercicios_tabla(fecha_inicio_actual, fecha_fin_actual)
    todos_los_ejercicios = calculadora.obtener_ejercicios_tabla()  # Para una progresión más completa

    progresiones = calculadora.obtener_ejercicios_progresion(limite=None, datos_ejercicios=todos_los_ejercicios)
    ejercicios_mejor_progresion = sorted([p for p in progresiones if p['progresion_peso'] > 0],
                                         key=lambda x: x['progresion_peso'], reverse=True)[:5]
    ejercicios_estancados = sorted([p for p in progresiones if p['progresion_peso'] <= 5],
                                   key=lambda x: x['progresion_peso'])[:5]

    # Cálculo de Frecuencia de Ejercicios con porcentaje para la barra visual
    frecuencia = {}
    for ej in ejercicios_del_periodo:
        nombre = ej['nombre'].strip().title()
        frecuencia[nombre] = frecuencia.get(nombre, 0) + 1

    ejercicios_mas_frecuentes_raw = sorted(frecuencia.items(), key=lambda x: x[1], reverse=True)[:5]
    max_frecuencia = ejercicios_mas_frecuentes_raw[0][1] if ejercicios_mas_frecuentes_raw else 0

    ejercicios_mas_frecuentes = []
    for nombre, count in ejercicios_mas_frecuentes_raw:
        porcentaje = (count / max_frecuencia * 100) if max_frecuencia > 0 else 0
        ejercicios_mas_frecuentes.append(
            {'nombre_ejercicio': nombre, 'sesiones': count, 'porcentaje_frecuencia': porcentaje})

    # --- 4. CONSTRUCCIÓN DEL CONTEXTO FINAL ---
    context = {
        'cliente': cliente,
        'metricas_principales': metricas_actuales,
        'comparativas': comparativas,
        'entrenamientos_recientes': entrenamientos_recientes,
        'recomendaciones': recomendaciones,
        'datos_volumen': json.dumps(datos_graficos['volumen_diario'], default=str),
        'datos_intensidad': json.dumps(datos_graficos['intensidad_diaria'], default=str),
        'fecha_inicio': fecha_inicio_actual.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin_actual.strftime('%Y-%m-%d'),
        'volumen_vacio': not datos_graficos['volumen_diario'],
        'intensidad_vacia': not datos_graficos['intensidad_diaria'],
        'estado_atleta': estado_atleta,
        'ejercicios_mejor_progresion': ejercicios_mejor_progresion,
        'ejercicios_estancados': ejercicios_estancados,
        'ejercicios_mas_frecuentes': ejercicios_mas_frecuentes,
        'ejercicios': ejercicios_del_periodo[:20],  # Para la tabla inferior, si aún la usas
    }

    return render(request, 'analytics/dashboard.html', context)


# Archivo: analytics/views.py
# Reemplaza la vista dashboard_global completa con esta versión
# Archivo: analytics/views.py
# Reemplaza la vista dashboard_global completa con esta versión CORREGIDA

@login_required
def dashboard_global(request, cliente_id):
    """
    Dashboard de Rendimiento Global.
    VERSIÓN FINAL CORREGIDA: Maneja correctamente valores None en grupos musculares.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    # --- 1. CÁLCULO DE MÉTRICAS GLOBALES ---

    # A. Métricas para KPIs (tarjetas superiores) - GLOBALES (sin filtro de fecha)
    metricas_principales = calculadora.calcular_metricas_principales()

    # B. Análisis de Carga y Fatiga (ACWR) - Usa un período largo para ser robusto
    analisis_acwr = calculadora.analizar_acwr(periodo_dias=365)

    # C. Análisis de Equilibrio Muscular - Usa el historial COMPLETO
    equilibrio_muscular = calculadora.analizar_equilibrio_muscular()

    # D. Distribución de volumen por grupo muscular - Usa el historial COMPLETO
    volumen_por_grupo = calculadora.calcular_volumen_por_grupo_muscular()
    volumen_por_grupo_ordenado = sorted(volumen_por_grupo.items(), key=lambda x: x[1], reverse=True)

    # E. Progresión de todos los ejercicios
    progresion_ejercicios = calculadora.obtener_progresion_completa_ejercicios()

    # --- 2. CONSTRUCCIÓN DEL CONTEXTO FINAL ---
    # Preparar datos JSON para gráficos
    volumen_grupo_data = {
        'labels': [item[0] for item in volumen_por_grupo_ordenado],
        'valores': [item[1] for item in volumen_por_grupo_ordenado]
    }

    context = {
        'cliente': cliente,
        'metricas_principales': metricas_principales,
        'analisis_acwr': analisis_acwr,
        'equilibrio_muscular': equilibrio_muscular,
        'progresion_ejercicios': progresion_ejercicios,
        'volumen_por_grupo_labels': json.dumps([item[0] for item in volumen_por_grupo_ordenado]),
        'volumen_por_grupo_valores': json.dumps([item[1] for item in volumen_por_grupo_ordenado]),
        'volumen_grupo_json': json.dumps(volumen_grupo_data),
    }

    context['acwr_data_json'] = json.dumps(analisis_acwr.get('dataframe', []))
    context['equilibrio_radar_json'] = json.dumps(equilibrio_muscular.get('datos_radar', {}))

    # --- 3. DATOS PARA EL HEATMAP DE ACTIVIDAD ANUAL ---
    # Obtener entrenamientos del año actual
    current_year = datetime.now().year
    entrenamientos_anio = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__year=current_year
    ).values('fecha').annotate(
        intensidad=Count('id')  # Contar entrenamientos por día
    )

    # Crear diccionario con formato {"YYYY-MM-DD": intensidad}
    heatmap_data = {}
    for e in entrenamientos_anio:
        fecha_str = e['fecha'].strftime('%Y-%m-%d')
        # Normalizar intensidad: 1-4 según número de entrenamientos
        intensidad = min(e['intensidad'], 4)  # Máximo 4 niveles
        heatmap_data[fecha_str] = intensidad

    context['heatmap_data_json'] = json.dumps(heatmap_data)

    return render(request, 'analytics/dashboard_global.html', context)


from django.shortcuts import render, get_object_or_404
from .models import TendenciaProgresion, PrediccionRendimiento
# Asumiendo que tienes esta función en analytics/vendor.py
import json


@login_required
def analisis_progresion(request, cliente_id):
    """
    Análisis detallado de progresión por ejercicio.
    Muestra gráfico, estadísticas, 1RM estimado, predicciones e historial de sesiones.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)
    todos_ejercicios = calculadora.obtener_ejercicios_tabla()

    # 1. Agrupar todos los ejercicios por nombre para el selector y el análisis
    ejercicios_dict = {}
    for e in todos_ejercicios:
        clave = e['nombre'].strip().lower()
        if clave not in ejercicios_dict:
            ejercicios_dict[clave] = {
                'nombre_mostrado': e['nombre'].strip().title(),
                'ejercicios': []
            }
        ejercicios_dict[clave]['ejercicios'].append(e)

    ejercicios_unicos = sorted([v['nombre_mostrado'] for v in ejercicios_dict.values()])

    # 2. Determinar el ejercicio seleccionado desde la URL o tomar el primero
    raw_nombre = request.GET.get('ejercicio')
    ejercicio_seleccionado = raw_nombre.strip().title() if raw_nombre else (
        ejercicios_unicos[0] if ejercicios_unicos else None)

    # 3. Inicializar todas las variables que se pasarán al contexto
    datos_progresion = []
    historial_ejercicio = []
    tendencia = None
    predicciones = []
    fila_1rm = None

    if ejercicio_seleccionado:
        # 4. Filtrar datos para el ejercicio seleccionado
        clave_seleccionada = ejercicio_seleccionado.lower()
        ejercicios_filtrados = ejercicios_dict.get(clave_seleccionada, {}).get('ejercicios', [])

        if ejercicios_filtrados:
            # Ordenar por fecha para el gráfico
            ejercicios_filtrados.sort(key=lambda x: x['fecha'])

            # Preparar el historial para la tabla (ordenado de más reciente a más antiguo)
            historial_ejercicio = sorted(ejercicios_filtrados, key=lambda x: x['fecha'], reverse=True)

            # Preparar datos para el gráfico
            # Variables para rastrear PRs
            max_peso = 0
            max_volumen = 0

            # Primera pasada: Calcular datos y encontrar máximos
            temp_datos = []
            for e in ejercicios_filtrados:
                try:
                    peso = float(e.get('peso', 0)) if e.get('peso') != 'PC' else 0
                    series, reps = parse_reps_and_series(str(e.get('repeticiones', '1x1')))
                    
                    if peso > 0 and reps > 0:
                        volumen = peso * series * reps
                        # Fórmula Epley para 1RM
                        rm_estimado = round(peso * (1 + reps / 30), 2)
                        
                        # Actualizar máximos
                        if peso > max_peso: max_peso = peso
                        if volumen > max_volumen: max_volumen = volumen
                        
                        e['volumen_calculado'] = volumen
                        e['rm_estimado'] = rm_estimado
                        
                        temp_datos.append({
                            'fecha_obj': e['fecha'], # Guardamos objeto fecha para ordenamiento si fuera necesario
                            'fecha': e['fecha'].strftime('%Y-%m-%d'),
                            'peso': peso,
                            'volumen': volumen,
                            'rm': rm_estimado,
                            'is_pr_peso': False, # Se calculará en la segunda pasada o aquí mismo si es secuencial histórico?
                            'is_pr_volumen': False
                        })
                except (ValueError, TypeError):
                    continue

            # Segunda pasada: Marcar PRs (Récords Históricos hasta la fecha)
            # Si queremos marcar el "Récord Actual" (el mejor de todos), usamos max_peso.
            # Si queremos "Récord hasta ese momento", necesitamos iterar cronológicamente.
            # El usuario pidió "Highlight PRs", asumo el mejor histórico absoluto para la tabla.
            
            # Para el gráfico es útil saber cuáles son PRs.
            # Vamos a marcar el PR absoluto en la lista de datos para el JS si se quiere usar,
            # y actualizar el historial_ejercicio para la tabla.

            for e in ejercicios_filtrados:
                if 'volumen_calculado' in e:
                    e['is_pr_peso'] = e.get('peso') == max_peso and max_peso > 0
                    e['is_pr_volumen'] = e.get('volumen_calculado') == max_volumen and max_volumen > 0
            
            # Actualizamos datos_progresion con la info de PRs
            datos_progresion = temp_datos

            # 5. Obtener datos de modelos de análisis relacionados
            tendencia = TendenciaProgresion.objects.filter(cliente=cliente,
                                                           nombre_ejercicio__iexact=ejercicio_seleccionado).order_by(
                '-fecha_fin').first()
            predicciones = PrediccionRendimiento.objects.filter(cliente=cliente,
                                                                nombre_ejercicio__iexact=ejercicio_seleccionado,
                                                                activa=True).order_by('-fecha_prediccion')[:3]

    # 6. Calcular la tabla de 1RM para todos los ejercicios y luego filtrar
    tabla_1rm_completa = []
    for datos in ejercicios_dict.values():
        lista = datos['ejercicios']
        nombre = datos['nombre_mostrado']
        entrenos_validos = []
        for e in lista:
            try:
                peso = float(e['peso']) if e.get('peso') != 'PC' else 0
                series, reps = parse_reps_and_series(str(e.get('repeticiones', '1x1')))
                if peso > 0 and reps > 0:
                    # Fórmula de Epley para 1RM: peso * (1 + reps / 30)
                    rm = round(peso * (1 + reps / 30), 2)
                    entrenos_validos.append({'fecha': e['fecha'], '1rm': rm})
            except (ValueError, TypeError):
                continue

        if len(entrenos_validos) >= 2:
            entrenos_validos.sort(key=lambda x: x['fecha'])
            rm_actual = entrenos_validos[-1]['1rm']
            rm_anterior = entrenos_validos[-2]['1rm']
            progreso = round(((rm_actual - rm_anterior) / rm_anterior) * 100, 2) if rm_anterior > 0 else 100.0
            tabla_1rm_completa.append(
                {'nombre': nombre, 'rm_actual': rm_actual, 'rm_anterior': rm_anterior, 'progreso': progreso})

    # Filtrar la fila del 1RM para el ejercicio seleccionado
    if ejercicio_seleccionado and tabla_1rm_completa:
        fila_1rm = next(
            (fila for fila in tabla_1rm_completa if fila['nombre'].lower() == ejercicio_seleccionado.lower()), None)
    metas = []
    anotaciones = []
    if ejercicio_seleccionado:
        # Obtenemos las metas y anotaciones para el ejercicio seleccionado
        metas = MetaRendimiento.objects.filter(cliente=cliente, nombre_ejercicio__iexact=ejercicio_seleccionado)
        anotaciones = AnotacionEntrenamiento.objects.filter(cliente=cliente,
                                                            ejercicio_asociado__iexact=ejercicio_seleccionado)

    # 7. Construir el contexto final para la plantilla
    context = {
        'cliente': cliente,
        'ejercicios': ejercicios_unicos,
        'ejercicio_seleccionado': ejercicio_seleccionado,
        'datos_progresion': json.dumps(datos_progresion, default=str),
        'tendencia': tendencia,
        'predicciones': predicciones,
        'tabla_1rm': fila_1rm,
        'historial_ejercicio': historial_ejercicio,
        'metas_json': json.dumps(list(metas.values('fecha_objetivo', 'valor_objetivo')), default=str),
        'anotaciones_json': json.dumps(list(anotaciones.values('fecha', 'descripcion', 'tipo')), default=str),
        'tipos_anotacion': AnotacionEntrenamiento.TIPO_ANOTACION,  # Para el formulario
    }

    return render(request, 'analytics/progresion.html', context)


# Archivo: analytics/views.py

@login_required
def comparativas(request, cliente_id):
    """
    Análisis comparativo con TRES opciones:
    1. Temporal (vs período anterior)
    2. Por Grupo Muscular (agregado)
    3. Por Ejercicio (individual)
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    # --- 1. OBTENER PARÁMETROS Y CALCULAR FECHAS ---
    tipo_comparativa = request.GET.get('tipo', 'temporal')
    periodo_dias = int(request.GET.get('periodo', 30))

    fecha_fin_actual = timezone.now().date()
    fecha_inicio_actual = fecha_fin_actual - timedelta(days=periodo_dias)
    fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
    fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=periodo_dias)

    # --- 2. LÓGICA DE COMPARACIÓN ---
    comparativas_data = {}  # Usaremos un diccionario para los tipos 'temporal' y 'ejercicio'

    if tipo_comparativa == 'temporal':
        # ... (esta lógica no cambia) ...
        metricas_actuales = calculadora.calcular_metricas_principales(fecha_inicio_actual, fecha_fin_actual)
        metricas_anteriores = calculadora.calcular_metricas_principales(fecha_inicio_anterior, fecha_fin_anterior)

        temp_data_list = []
        metricas_a_comparar = [
            ('volumen_total', 'Volumen Total'), ('intensidad_promedio', 'Intensidad Promedio'),
            ('calorias_totales', 'Calorías Totales'), ('consistencia', 'Consistencia')
        ]
        for clave, etiqueta in metricas_a_comparar:
            actual = metricas_actuales.get(clave, 0)
            anterior = metricas_anteriores.get(clave, 0)
            diferencia_pct = ((actual - anterior) / anterior * 100) if anterior > 0 else (100.0 if actual > 0 else 0.0)
            temp_data_list.append({
                'etiqueta': etiqueta, 'actual': actual, 'anterior': anterior,
                'diferencia_pct': diferencia_pct, 'diferencia_abs': actual - anterior,
            })
        comparativas_data = temp_data_list

    elif tipo_comparativa == 'grupo_muscular':
        # ... (esta lógica no cambia) ...
        ejercicios = calculadora.obtener_ejercicios_tabla(fecha_inicio_actual, fecha_fin_actual)
        volumen_por_grupo = {}
        for e in ejercicios:
            grupo = e.get('grupo', 'Otro').strip().title()
            if not grupo: continue
            try:
                peso = float(e.get('peso', 0));
                series = int(e.get('series', 1));
                reps = int(e.get('repeticiones', 1))
                volumen_por_grupo[grupo] = volumen_por_grupo.get(grupo, 0) + (peso * series * reps)
            except (ValueError, TypeError):
                continue

        volumen_ordenado = sorted(volumen_por_grupo.items(), key=lambda x: x[1], reverse=True)
        comparativas_data = [{'grupo': grupo, 'volumen': volumen} for grupo, volumen in volumen_ordenado]

    elif tipo_comparativa == 'ejercicio':
        # ✅ REINTRODUCIMOS LA LÓGICA ORIGINAL DE COMPARATIVA POR EJERCICIO
        ejercicios = calculadora.obtener_ejercicios_tabla(fecha_inicio_actual, fecha_fin_actual)

        ejercicios_metricas = {}
        for e in ejercicios:
            nombre_mostrado = e['nombre'].strip().title()
            if nombre_mostrado not in ejercicios_metricas:
                ejercicios_metricas[nombre_mostrado] = {'total_sesiones': 0, 'volumen_total': 0, 'peso_maximo': 0,
                                                        'pesos': []}

            try:
                peso = float(e.get('peso', 0))
                series = int(e.get('series', 1))
                reps = int(e.get('repeticiones', 1))

                ejercicios_metricas[nombre_mostrado]['total_sesiones'] += 1
                ejercicios_metricas[nombre_mostrado]['volumen_total'] += peso * series * reps
                ejercicios_metricas[nombre_mostrado]['peso_maximo'] = max(
                    ejercicios_metricas[nombre_mostrado]['peso_maximo'], peso)
                if peso > 0:
                    ejercicios_metricas[nombre_mostrado]['pesos'].append(peso)
            except (ValueError, TypeError):
                continue

        # Calcular promedios y ordenar
        for nombre, datos in ejercicios_metricas.items():
            pesos = datos['pesos']
            datos['peso_promedio'] = sum(pesos) / len(pesos) if pesos else 0
            del datos['pesos']  # Limpiamos la lista de pesos que ya no necesitamos

        # Ordenamos el diccionario por volumen total descendente
        comparativas_data = dict(
            sorted(ejercicios_metricas.items(), key=lambda item: item[1]['volumen_total'], reverse=True))

    # --- 3. CONSTRUCCIÓN DEL CONTEXTO ---
    context = {
        'cliente': cliente,
        'tipo_comparativa': tipo_comparativa,
        'periodo_seleccionado': periodo_dias,
        'comparativas_data': comparativas_data,
        'fecha_inicio_actual': fecha_inicio_actual.strftime('%d/%m/%Y'),
        'fecha_fin_actual': fecha_fin_actual.strftime('%d/%m/%Y'),
        'fecha_inicio_anterior': fecha_inicio_anterior.strftime('%d/%m/%Y'),
        'fecha_fin_anterior': fecha_fin_anterior.strftime('%d/%m/%Y'),
    }

    return render(request, 'analytics/comparativas.html', context)


@login_required
def recomendaciones(request, cliente_id):
    """
    Sistema de recomendaciones personalizadas con prevención de duplicados.
    VERSIÓN ROBUSTA para evitar MultipleObjectsReturned.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    PRIORIDADES = {'alta': 1, 'media': 2, 'baja': 3}

    if request.method == 'POST' and 'generar' in request.POST:
        calculadora = CalculadoraEjerciciosTabla(cliente)
        creadas = 0
        actualizadas = 0

        # --- Lógica de Consistencia ---
        ejercicios = calculadora.obtener_ejercicios_tabla(fecha_inicio=timezone.now().date() - timedelta(days=30))
        if ejercicios:
            completados = len([e for e in ejercicios if e.get('completado', False)])
            consistencia = (completados / len(ejercicios)) * 100 if len(ejercicios) > 0 else 0

            if consistencia < 70:
                titulo_rec = 'Mejorar Consistencia'
                desc_rec = f'Tu consistencia actual es del {consistencia:.1f}%. Intenta completar todos los ejercicios de tus rutinas.'

                # Búsqueda más específica: incluimos la descripción
                obj, created = RecomendacionEntrenamiento.objects.update_or_create(
                    cliente=cliente,
                    tipo='consistencia',
                    titulo=titulo_rec,
                    descripcion=desc_rec,  # <-- CRITERIO ADICIONAL
                    defaults={
                        'prioridad': PRIORIDADES['alta'],
                        'expires_at': timezone.now() + timedelta(days=14),
                        'aplicada': False,
                    }
                )
                if created:
                    creadas += 1
                else:
                    actualizadas += 1

        # --- Lógica de Ejercicios Estancados ---
        progresiones = calculadora.obtener_ejercicios_progresion(limite=None)
        estancados = [p['nombre_ejercicio'] for p in progresiones if p['progresion_peso'] < 5]

        if estancados:
            titulo_rec = 'Ejercicios Estancados Detectados'
            desc_rec = f'Los siguientes ejercicios muestran poca progresión: {", ".join(sorted(estancados)[:3])}. Considera variar la rutina o la intensidad.'

            # Búsqueda más específica: incluimos la descripción
            obj, created = RecomendacionEntrenamiento.objects.update_or_create(
                cliente=cliente,
                tipo='progresion',
                titulo=titulo_rec,
                descripcion=desc_rec,  # <-- CRITERIO ADICIONAL
                defaults={
                    'prioridad': PRIORIDADES['media'],
                    'expires_at': timezone.now() + timedelta(days=30),
                    'aplicada': False,
                }
            )
            if created:
                creadas += 1
            else:
                actualizadas += 1

        # Mensajes de feedback
        if creadas > 0 or actualizadas > 0:
            msg_parts = []
            if creadas > 0: msg_parts.append(
                f"{creadas} {'nueva recomendación generada' if creadas == 1 else 'nuevas recomendaciones generadas'}")
            if actualizadas > 0: msg_parts.append(
                f"{actualizadas} {'existente actualizada' if actualizadas == 1 else 'existentes actualizadas'}")
            messages.success(request, f"Análisis completado: {', '.join(msg_parts)}.")
        else:
            messages.info(request, "No se encontraron nuevas oportunidades de recomendación en este momento.")

        return redirect('analytics:recomendaciones', cliente_id=cliente.id)

    # --- Lógica para mostrar la página (GET request) ---
    recomendaciones_activas = RecomendacionEntrenamiento.objects.filter(
        cliente=cliente,
        expires_at__gt=timezone.now(),
        aplicada=False
    ).order_by('prioridad', '-created_at')

    recomendaciones_aplicadas = RecomendacionEntrenamiento.objects.filter(
        cliente=cliente,
        aplicada=True,
        fecha_aplicacion__gte=timezone.now() - timedelta(days=30)
    ).order_by('-fecha_aplicacion')

    context = {
        'cliente': cliente,
        'recomendaciones_activas': recomendaciones_activas,
        'recomendaciones_aplicadas': recomendaciones_aplicadas,
    }
    return render(request, 'analytics/recomendaciones.html', context)


@login_required
def predicciones(request, cliente_id):
    """
    Sistema de predicciones de rendimiento
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    # Obtener y agrupar ejercicios insensibles a mayúsculas
    todos_ejercicios = calculadora.obtener_ejercicios_tabla()
    ejercicios_dict = {}

    for e in todos_ejercicios:
        clave = e['nombre'].strip().lower()
        if clave not in ejercicios_dict:
            ejercicios_dict[clave] = {
                'nombre_mostrado': e['nombre'].strip().title(),
                'ejercicios': []
            }
        ejercicios_dict[clave]['ejercicios'].append(e)

    ejercicios_unicos = [v['nombre_mostrado'] for v in ejercicios_dict.values()]
    ejercicios_unicos.sort()

    raw_nombre = request.GET.get('ejercicio', None)
    ejercicio_seleccionado = raw_nombre.strip().title() if raw_nombre else (
        ejercicios_unicos[0] if ejercicios_unicos else None)

    predicciones_data = []

    if ejercicio_seleccionado:
        clave = ejercicio_seleccionado.lower()
        ejercicios_filtrados = ejercicios_dict.get(clave, {}).get('ejercicios', [])
        ejercicios_filtrados.sort(key=lambda x: x['fecha'])

        if len(ejercicios_filtrados) >= 3:
            pesos = []
            fechas = []

            for e in ejercicios_filtrados:
                try:
                    peso = float(e.get('peso', 0)) if e.get('peso') != 'PC' else 0
                    if peso > 0:
                        pesos.append(peso)
                        fechas.append(e['fecha'])
                except (ValueError, TypeError):
                    continue

            if len(pesos) >= 3:
                incrementos = [pesos[i] - pesos[i - 1] for i in range(1, len(pesos))]
                incremento_promedio = sum(incrementos) / len(incrementos) if incrementos else 0
                peso_actual = pesos[-1]

                for meses in [1, 3, 6]:
                    peso_predicho = peso_actual + (incremento_promedio * meses * 4)
                    fecha_prediccion = timezone.now().date() + timedelta(days=30 * meses)

                    predicciones_data.append({
                        'ejercicio': ejercicio_seleccionado,
                        'fecha_prediccion': fecha_prediccion.strftime('%Y-%m-%d'),  # ⬅️ aquí el cambio
                        'peso_predicho': max(peso_predicho, peso_actual),
                        'peso_actual': peso_actual,
                        'incremento_esperado': peso_predicho - peso_actual,
                        'meses': meses,
                        'confianza': max(70 - (meses * 10), 30)
                    })

    # Predicciones históricas (no necesitan cambio)
    predicciones_bd = PrediccionRendimiento.objects.filter(
        cliente=cliente,
        activa=True
    ).order_by('-fecha_prediccion')[:10]

    context = {
        'cliente': cliente,
        'ejercicios': ejercicios_unicos,
        'ejercicio_seleccionado': ejercicio_seleccionado,
        'predicciones_data': predicciones_data,
        'predicciones_bd': predicciones_bd,
    }

    return render(request, 'analytics/predicciones.html', context)


# ============================================================================
# APIs PARA DATOS DINÁMICOS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def api_ejercicios_tabla(request, cliente_id):
    """
    API para obtener ejercicios usando la misma lógica que la tabla
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    # Parámetros
    limite = int(request.GET.get('limite', 20))
    ejercicio_filtro = request.GET.get('ejercicio', '')

    ejercicios = calculadora.obtener_ejercicios_tabla()

    # Filtrar por ejercicio si se especifica
    if ejercicio_filtro:
        ejercicios = [e for e in ejercicios if ejercicio_filtro.lower() in e['nombre'].lower()]

    # Limitar resultados
    ejercicios = ejercicios[:limite]

    # Convertir fechas a string para JSON
    for e in ejercicios:
        e['fecha'] = e['fecha'].strftime('%Y-%m-%d')

    return JsonResponse({
        'success': True,
        'ejercicios': ejercicios,
        'total': len(ejercicios)
    })


@login_required
@require_http_methods(["GET"])
def api_metricas_tabla(request, cliente_id):
    """
    API para obtener métricas usando datos de la tabla
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    # Parámetros
    dias = int(request.GET.get('dias', 30))
    fecha_fin = timezone.now().date()
    fecha_inicio = fecha_fin - timedelta(days=dias)

    metricas = calculadora.calcular_metricas_principales(fecha_inicio, fecha_fin)
    datos_graficos = calculadora.obtener_datos_graficos(fecha_inicio, fecha_fin)

    return JsonResponse({
        'success': True,
        'metricas': metricas,
        'graficos': datos_graficos,
        'periodo': f"{fecha_inicio} - {fecha_fin}"
    })


@login_required
@require_http_methods(["POST"])
def marcar_recomendacion_aplicada(request, recomendacion_id):
    """
    Marcar una recomendación como aplicada
    """
    recomendacion = get_object_or_404(RecomendacionEntrenamiento, id=recomendacion_id)

    recomendacion.aplicada = True
    recomendacion.fecha_aplicacion = timezone.now()
    recomendacion.save()

    return JsonResponse({
        'success': True,
        'message': 'Recomendación marcada como aplicada'
    })


@login_required
@require_http_methods(["GET"])
def api_progresion(request, cliente_id, ejercicio):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    dias = int(request.GET.get('dias', 90))
    fecha_fin = timezone.now().date()
    fecha_inicio = fecha_fin - timedelta(days=dias)

    datos_progresion = []

    ejercicios = calculadora.obtener_ejercicios_tabla(fecha_inicio, fecha_fin)
    ejercicios_filtrados = [e for e in ejercicios if e['nombre'] == ejercicio]
    ejercicios_filtrados.sort(key=lambda x: x['fecha'])

    for e in ejercicios_filtrados:
        try:
            peso = float(e.get('peso', 0)) if e.get('peso') != 'PC' else 0
            if peso > 0:
                datos_progresion.append({
                    'fecha': e['fecha'].strftime('%Y-%m-%d'),
                    'peso': peso,
                    'series': int(e.get('series', 1)),
                    'repeticiones': int(e.get('repeticiones', 1)),
                    'volumen': peso * int(e.get('series', 1)) * int(e.get('repeticiones', 1))
                })
        except Exception:
            continue

    return JsonResponse({
        'success': True,
        'datos': datos_progresion,
        'ejercicio': ejercicio,
        'periodo': f"{fecha_inicio} - {fecha_fin}"
    })


@login_required
@require_http_methods(["POST"])
def calcular_metricas(request, cliente_id):
    """
    Forzar recálculo de métricas desde la tabla de ejercicios
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    fecha_fin = timezone.now().date()
    fecha_inicio = fecha_fin - timedelta(days=30)

    try:
        metricas = calculadora.calcular_metricas_principales(fecha_inicio, fecha_fin)
        return JsonResponse({
            'success': True,
            'mensaje': 'Métricas recalculadas correctamente',
            'metricas': metricas
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def generar_recomendaciones(request, cliente_id):
    """
    Genera recomendaciones automáticamente para un cliente usando la calculadora
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)

    # Mapeo claro para prioridad
    PRIORIDADES = {'alta': 1, 'media': 2, 'baja': 3}

    recomendaciones_generadas = []

    progresiones = calculadora.obtener_ejercicios_progresion()
    for prog in progresiones:
        if prog['progresion_peso'] < 5:
            recomendaciones_generadas.append({
                'titulo': f'Estancamiento en {prog["nombre_ejercicio"]}',
                'descripcion': f'El progreso ha sido bajo ({prog["progresion_peso"]:.1f}%)',
                'tipo': 'progresion',
                'prioridad': PRIORIDADES['media']
            })

    for rec in recomendaciones_generadas:
        RecomendacionEntrenamiento.objects.create(
            cliente=cliente,
            titulo=rec['titulo'],
            descripcion=rec['descripcion'],
            tipo=rec['tipo'],
            prioridad=rec['prioridad'],
            expires_at=timezone.now() + timedelta(days=30)
        )

    return JsonResponse({
        'success': True,
        'mensaje': f'{len(recomendaciones_generadas)} recomendaciones creadas.'
    })


from analytics.models import TendenciaProgresion
from datetime import timedelta

from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from urllib.parse import urlencode
import pandas as pd


# (y el resto de tus imports: Cliente, CalculadoraEjerciciosTabla, etc.)

@login_required
def actualizar_tendencias(request, cliente_id):
    """
    Calcula y guarda tendencias para todos los ejercicios del cliente.
    Ahora mantiene el ejercicio seleccionado al redirigir.
    """
    # 2. La vista ahora debe aceptar POST para recibir el campo oculto del formulario
    if request.method != 'POST':
        # Si alguien intenta acceder a esta URL directamente (GET), lo redirigimos
        return redirect('analytics:progresion', cliente_id=cliente_id)

    # Imports locales para mantener la función organizada
    from .progression import ProgressionAnalyzer  # Asumiendo que está en analytics.progression

    cliente = get_object_or_404(Cliente, id=cliente_id)
    calculadora = CalculadoraEjerciciosTabla(cliente)
    ejercicios = calculadora.obtener_ejercicios_tabla()

    ejercicios_por_nombre = {}
    for e in ejercicios:
        nombre = e['nombre'].strip().lower()
        if nombre not in ejercicios_por_nombre:
            ejercicios_por_nombre[nombre] = []
        ejercicios_por_nombre[nombre].append(e)

    resultados_guardados = 0
    resumen_tendencias = []

    for nombre_normalizado, lista in ejercicios_por_nombre.items():
        if len(lista) < 3:
            continue

        # ✅ SOLUCIÓN 1: Inicializar las listas ANTES de usarlas en el bucle
        entrenos_validos = []
        datos_validos = []

        for e in lista:
            try:
                peso = float(e['peso']) if e['peso'] != 'PC' else 0
                repeticiones_valor = e.get('repeticiones')
                series, reps = parse_reps_and_series(repeticiones_valor)

                # Este print ahora no dará error, pero la variable 'nombre' no está definida aquí.
                # Usamos 'nombre_normalizado' que sí existe en este scope.
                print(f"🎯 {nombre_normalizado} → peso: {peso}, reps: {reps}")
                if peso > 0 and reps > 0:
                    rm = round(peso * (1 + reps / 30), 2)
                    entrenos_validos.append({
                        'fecha': e['fecha'],
                        '1rm': rm
                    })
            except Exception as error:
                # Usamos 'nombre_normalizado' para un mensaje de error correcto
                print(f"❌ ERROR en {nombre_normalizado}: {error}")

            if 'peso' in e and e.get('peso') not in [None, 'PC']:
                try:
                    datos_validos.append({
                        'fecha': e['fecha'],
                        'peso': float(e.get('peso'))
                    })
                except (ValueError, TypeError):
                    continue

        if len(datos_validos) < 3:
            continue

        df = pd.DataFrame(datos_validos)
        df = df[df['peso'] > 0]
        if len(df) < 3:
            continue

        df = df.sort_values('fecha')
        nombre_mostrado = lista[0]['nombre'].strip().title()

        try:
            analizador = ProgressionAnalyzer(cliente)
            resultado = analizador.analizar_progresion_ejercicio(nombre_mostrado,
                                                                 periodo_dias=365)  # Usar un período largo

            if resultado and resultado.get('tendencia'):
                nombre_estandarizado = nombre_mostrado.strip().title()
                tendencia_valor = round(resultado['tendencia'].get('pendiente', 0), 1)
                simbolo = "↗️" if tendencia_valor > 0 else "↘️"
                resumen_tendencias.append(f"{nombre_mostrado} {simbolo} {tendencia_valor}%")

                peso_maximo = df['peso'].max()
                sesiones = len(df)
                fecha_inicio = df['fecha'].min()
                fecha_fin = df['fecha'].max()
                tendencia_valor = round(resultado['tendencia'].get('pendiente', 0), 1)

                # Determinar el tipo de tendencia
                if tendencia_valor > 1:
                    tipo = 'creciente'
                elif tendencia_valor < -1:
                    tipo = 'decreciente'
                else:
                    tipo = 'estable'
                TendenciaProgresion.objects.update_or_create(
                    cliente=cliente,
                    nombre_ejercicio__iexact=nombre_estandarizado,
                    defaults={
                        'nombre_ejercicio': nombre_estandarizado,
                        'fecha_inicio': fecha_inicio,
                        'fecha_fin': fecha_fin,
                        'tendencia_general': tendencia_valor,
                        'peso_maximo': peso_maximo,
                        'sesiones_totales': sesiones,
                        'tipo_tendencia': tipo,
                    }
                )
                resultados_guardados += 1
        except Exception as e:
            print(f"Error al analizar con ProgressionAnalyzer para {nombre_mostrado}: {e}")

    if resultados_guardados > 0:
        texto = ", ".join(resumen_tendencias[:5])
        if len(resumen_tendencias) > 5:
            texto += "..."
        messages.success(request, f"📈 Se guardaron {resultados_guardados} tendencias: {texto}")
    else:
        messages.info(request, "No se detectaron ejercicios con datos suficientes para calcular tendencias.")

    # ✅ SOLUCIÓN 2: Redirección inteligente que mantiene el ejercicio seleccionado
    ejercicio_seleccionado = request.POST.get('ejercicio_actual', None)

    # Construimos la URL base para la redirección
    redirect_url = reverse('analytics:progresion', args=[cliente.id])

    # Si había un ejercicio seleccionado, lo añadimos como parámetro a la URL
    if ejercicio_seleccionado:
        # Usamos urlencode para manejar correctamente los espacios y caracteres especiales
        redirect_url += f'?{urlencode({"ejercicio": ejercicio_seleccionado})}'

    return redirect(redirect_url)


# 📈 DASHBOARD DE PROGRESIÓN AVANZADO - VERSIÓN COMPLETA CORREGIDA
# Todos los métodos implementados para evitar errores

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Avg, Max, Min, Count
from datetime import datetime, timedelta
import json
import numpy as np
from entrenos.utils.utils import parse_reps_and_series
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado


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

        ratios = {
            'press_sentadilla': self._calcular_ratio(rms.get('Press banca', 0), rms.get('Sentadilla', 0)),
            'peso_muerto_sentadilla': self._calcular_ratio(rms.get('Peso muerto', 0), rms.get('Sentadilla', 0)),
            'press_militar_banca': self._calcular_ratio(rms.get('Press militar', 0), rms.get('Press banca', 0)),
            'dominadas_remo': self._calcular_ratio(rms.get('Dominadas', 0), rms.get('Remo', 0))
        }

        # Comparar con estándares
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
                    'nombre': ratio_name.replace('_', ' ').title(),
                    'valor': valor,
                    'optimo': estandar['optimo'],
                    'estado': estado,
                    'recomendacion': self._generar_recomendacion_ratio(ratio_name, estado)
                })

        return {
            'ratios': analisis_ratios,
            'grafico_radar': self._generar_datos_radar(ratios, estandares),
            'puntos_debiles': self._identificar_puntos_debiles(analisis_ratios)
        }

    def analisis_evolucion_temporal(self, ejercicio=None, periodo_dias=90):
        """
        Análisis de evolución temporal con gráficos de línea
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        if ejercicio:
            ejercicios = [ejercicio]
        else:
            ejercicios = self.ejercicios_principales

        datos_evolucion = {}

        for ej in ejercicios:
            datos_ejercicio = self._obtener_datos_temporales(ej, fecha_inicio)
            if datos_ejercicio:
                # Calcular tendencias
                try:
                    from scipy import stats
                    tendencia = self._calcular_tendencia_lineal(datos_ejercicio)
                except ImportError:
                    tendencia = self._calcular_tendencia_simple(datos_ejercicio)

                # Detectar hitos y objetivos
                hitos = self._detectar_hitos(datos_ejercicio)

                # Predicciones basadas en progresión actual
                predicciones = self._generar_predicciones_temporales(datos_ejercicio, tendencia)

                datos_evolucion[ej] = {
                    'datos': datos_ejercicio,
                    'tendencia': tendencia,
                    'hitos': hitos,
                    'predicciones': predicciones,
                    'volumen_por_grupo': self._calcular_volumen_grupo_muscular(ej, fecha_inicio)
                }

        return datos_evolucion

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

    def _obtener_1rm_ejercicios(self):
        """
        Calcula 1RM estimado usando fórmula de Brzycki
        """
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=datetime.now().date() - timedelta(days=30)
        ).exclude(notas_liftin__isnull=True).exclude(notas_liftin='')

        rms = {}

        for entreno in entrenamientos:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)

            for ejercicio in ejercicios:
                nombre = ejercicio['nombre']
                if nombre in self.ejercicios_principales:
                    try:
                        peso = float(ejercicio.get('peso', 0)) if ejercicio.get('peso') != 'PC' else 0
                        reps = self._extraer_repeticiones(ejercicio.get('repeticiones', '1'))

                        if peso > 0 and reps > 0 and reps <= 12:
                            # Fórmula de Brzycki: 1RM = peso / (1.0278 - 0.0278 * reps)
                            rm_estimado = peso / (1.0278 - 0.0278 * reps)

                            if nombre not in rms or rm_estimado > rms[nombre]:
                                rms[nombre] = round(rm_estimado, 1)

                    except (ValueError, TypeError):
                        continue

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
        """
        Obtiene datos temporales de un ejercicio específico
        """
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio
        ).exclude(notas_liftin__isnull=True).exclude(notas_liftin='').order_by('fecha')

        datos = []

        for entreno in entrenamientos:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)

            for ej in ejercicios:
                if ej['nombre'] == ejercicio:
                    try:
                        peso = float(ej.get('peso', 0)) if ej.get('peso') != 'PC' else 0
                        reps = self._extraer_repeticiones(ej.get('repeticiones', '1'))
                        series = self._extraer_series(ej.get('repeticiones', '1'))

                        if peso > 0:
                            volumen = peso * series * reps
                            intensidad = (peso / self._obtener_1rm_estimado(ejercicio, peso,
                                                                            reps)) * 100 if reps <= 12 else 70

                            datos.append({
                                'fecha': entreno.fecha.strftime('%Y-%m-%d'),
                                'peso': peso,
                                'repeticiones': reps,
                                'series': series,
                                'volumen': volumen,
                                'intensidad': round(intensidad, 1)
                            })

                    except (ValueError, TypeError):
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
        """
        Calcula tendencia simple sin scipy
        """
        if len(datos) < 3:
            return None

        primer_peso = datos[0]['peso']
        ultimo_peso = datos[-1]['peso']

        if primer_peso > 0:
            cambio_porcentual = ((ultimo_peso - primer_peso) / primer_peso) * 100
            dias_transcurridos = (datetime.strptime(datos[-1]['fecha'], '%Y-%m-%d') -
                                  datetime.strptime(datos[0]['fecha'], '%Y-%m-%d')).days

            tendencia_semanal = (cambio_porcentual / dias_transcurridos) * 7 if dias_transcurridos > 0 else 0

            return {
                'pendiente': round((ultimo_peso - primer_peso) / len(datos), 3),
                'intercepto': primer_peso,
                'correlacion': 0.8,  # Valor estimado
                'p_value': 0.05,
                'tendencia_semanal': round(tendencia_semanal, 2),
                'confianza': 75.0
            }

        return None

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
        Calcula volumen total por grupo muscular
        """
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio
        ).exclude(notas_liftin__isnull=True).exclude(notas_liftin='')

        volumen_total = 0

        for entreno in entrenamientos:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)

            for ej in ejercicios:
                if ej['nombre'] == ejercicio:
                    try:
                        peso = float(ej.get('peso', 0)) if ej.get('peso') != 'PC' else 0
                        reps = self._extraer_repeticiones(ej.get('repeticiones', '1'))
                        series = self._extraer_series(ej.get('repeticiones', '1'))

                        volumen_total += peso * series * reps
                    except (ValueError, TypeError):
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
        Analiza un mesociclo específico
        """
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )

        carga_total = 0
        duracion_total = 0
        sesiones = entrenamientos.count()

        for entreno in entrenamientos:
            duracion_total += entreno.duracion_minutos or 0

            if entreno.notas_liftin:
                ejercicios = parsear_ejercicios(entreno.notas_liftin)
                for ej in ejercicios:
                    try:
                        peso = float(ej.get('peso', 0)) if ej.get('peso') != 'PC' else 0
                        reps = self._extraer_repeticiones(ej.get('repeticiones', '1'))
                        series = self._extraer_series(ej.get('repeticiones', '1'))
                        carga_total += peso * series * reps
                    except (ValueError, TypeError):
                        continue

        return {
            'carga_total': carga_total,
            'duracion_total': duracion_total,
            'sesiones': sesiones,
            'carga_promedio': carga_total / sesiones if sesiones > 0 else 0,
            'duracion_promedio': duracion_total / sesiones if sesiones > 0 else 0
        }

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


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Avg, Max, Min, Count
from datetime import datetime, timedelta
import json
import numpy as np

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado


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
        Analiza distribución de zonas de entrenamiento
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio
        )

        distribucion = {
            'recuperacion': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0},
            'aerobica': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0},
            'umbral': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0},
            'anaerobica': {'tiempo': 0, 'porcentaje': 0, 'calorias': 0}
        }

        tiempo_total = 0

        for entreno in entrenamientos:
            duracion = entreno.duracion_minutos or 60  # Default 60 min
            tiempo_total += duracion

            # Estimar zona basada en tipo de entrenamiento
            zona = self._estimar_zona_entrenamiento(entreno)

            distribucion[zona]['tiempo'] += duracion
            distribucion[zona]['calorias'] += self._calcular_calorias_zona(zona, duracion)

        # Calcular porcentajes
        if tiempo_total > 0:
            for zona in distribucion:
                distribucion[zona]['porcentaje'] = round(
                    (distribucion[zona]['tiempo'] / tiempo_total) * 100, 1
                )

        # Generar recomendaciones
        recomendaciones = self._generar_recomendaciones_zonas(distribucion)

        return {
            'distribucion': distribucion,
            'tiempo_total': tiempo_total,
            'recomendaciones_zonas': recomendaciones
        }

    def analizar_carga_entrenamiento(self, periodo_dias=90):
        """
        Analiza carga de entrenamiento semanal/mensual
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        # Obtener datos por semana
        carga_semanal = {}
        semana_actual = fecha_inicio

        while semana_actual <= datetime.now().date():
            fin_semana = semana_actual + timedelta(days=6)

            entrenamientos_semana = EntrenoRealizado.objects.filter(
                cliente=self.cliente,
                fecha__gte=semana_actual,
                fecha__lte=fin_semana
            )

            carga_total = 0
            sesiones = entrenamientos_semana.count()
            duracion_total = 0

            for entreno in entrenamientos_semana:
                duracion = entreno.duracion_minutos or 60
                duracion_total += duracion

                # Calcular carga basada en volumen y duración
                if entreno.notas_liftin:
                    ejercicios = parsear_ejercicios(entreno.notas_liftin)
                    volumen_entreno = self._calcular_volumen_entreno(ejercicios)
                    intensidad_estimada = self._estimar_intensidad_entreno(ejercicios)

                    # Fórmula de carga: Volumen × Intensidad × Factor tiempo
                    carga_entreno = (volumen_entreno * intensidad_estimada * duracion) / 1000
                    carga_total += carga_entreno

            semana_str = semana_actual.strftime('%Y-W%U')
            carga_semanal[semana_str] = {
                'carga_total': round(carga_total, 1),
                'sesiones': sesiones,
                'duracion_total': duracion_total,
                'carga_promedio': round(carga_total / sesiones, 1) if sesiones > 0 else 0
            }

            semana_actual += timedelta(days=7)

        # Calcular tendencias
        cargas = [data['carga_total'] for data in carga_semanal.values()]
        tendencia = self._calcular_tendencia_carga(cargas)

        # Estadísticas generales
        carga_promedio = sum(cargas) / len(cargas) if cargas else 0
        sesiones_promedio = sum(data['sesiones'] for data in carga_semanal.values()) / len(
            carga_semanal) if carga_semanal else 0
        duracion_promedio = sum(data['duracion_total'] for data in carga_semanal.values()) / len(
            carga_semanal) if carga_semanal else 0

        # Recomendaciones de carga
        recomendaciones = self._generar_recomendaciones_carga(carga_promedio, tendencia)

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
        Analiza distribución de intensidades por % 1RM
        """
        fecha_inicio = datetime.now().date() - timedelta(days=periodo_dias)

        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=fecha_inicio
        ).exclude(notas_liftin__isnull=True).exclude(notas_liftin='')

        distribucion = {
            'recuperacion': 0,  # 40-60% 1RM
            'hipertrofia': 0,  # 60-80% 1RM
            'fuerza': 0,  # 80-90% 1RM
            'potencia': 0  # 90-100% 1RM
        }

        total_series = 0

        for entreno in entrenamientos:
            ejercicios = parsear_ejercicios(entreno.notas_liftin)

            for ejercicio in ejercicios:
                try:
                    peso = float(ejercicio.get('peso', 0)) if ejercicio.get('peso') != 'PC' else 0
                    reps = self._extraer_repeticiones(ejercicio.get('repeticiones', '1'))
                    series = self._extraer_series(ejercicio.get('repeticiones', '1'))

                    if peso > 0 and reps > 0:
                        # Estimar 1RM
                        rm_estimado = self._calcular_1rm(peso, reps)
                        intensidad_pct = (peso / rm_estimado) * 100 if rm_estimado > 0 else 50

                        # Clasificar por zona de intensidad
                        zona = self._clasificar_intensidad(intensidad_pct)
                        distribucion[zona] += series
                        total_series += series

                except (ValueError, TypeError):
                    continue

        # Convertir a porcentajes
        if total_series > 0:
            for zona in distribucion:
                distribucion[zona] = round((distribucion[zona] / total_series) * 100, 1)

        # Evaluar efectividad de rutina
        efectividad = self._evaluar_efectividad_rutina(distribucion)

        # Recomendaciones de intensidad
        recomendaciones = self._generar_recomendaciones_intensidad(distribucion)

        return {
            'distribucion': distribucion,
            'total_series': total_series,
            'efectividad_rutina': efectividad,
            'recomendaciones_intensidad': recomendaciones
        }

    # Dentro de la clase AnalisisIntensidadAvanzado
    # Dentro de la clase AnalisisIntensidadAvanzado
    # Dentro de la clase AnalisisIntensidadAvanzado
    from django.utils import timezone  # <-- ¡ASEGÚRATE DE TENER ESTA IMPORTACIÓN!

    def calcular_fatiga_acumulada(self, periodo_dias=14):
        """
        Calcula fatiga acumulada - VERSIÓN FINAL CON MANEJO DE ZONA HORARIA.
        """
        logger.info("--- INICIANDO CÁLCULO DE FATIGA (VERSIÓN TIMEZONE) ---")

        # Usamos timezone.now() para obtener la fecha actual de forma segura en Django
        hoy = timezone.now().date()

        ultimo_entreno = EntrenoRealizado.objects.filter(cliente=self.cliente).order_by('-fecha').first()

        if not ultimo_entreno:
            logger.info("No se encontraron entrenamientos. Fatiga es 0.")
            return {'fatiga_actual': 0, 'nivel': 'baja', 'recomendacion_descanso': "Estás completamente recuperado.",
                    'dias_recuperacion': 0}

        logger.info(f"Último entreno encontrado en fecha: {ultimo_entreno.fecha}")

        # Asumimos que la fatiga justo después del último entreno es la carga de ese día.
        carga_ultimo_entreno = self._calcular_carga_dia(ultimo_entreno)
        logger.info(f"Carga calculada para el último entreno: {carga_ultimo_entreno}")

        fatiga_post_entreno = carga_ultimo_entreno

        # --- Aplicar decaimiento desde el último entreno hasta HOY ---
        dias_de_recuperacion = (hoy - ultimo_entreno.fecha).days

        logger.info(f"Fecha de hoy (consciente de timezone): {hoy}. Días de recuperación: {dias_de_recuperacion}")

        if dias_de_recuperacion < 0:
            logger.warning("La fecha del último entreno es en el futuro. Se tratará como 0 días de recuperación.")
            dias_de_recuperacion = 0

        decay_factor = 0.85
        fatiga_actual = fatiga_post_entreno * (decay_factor ** dias_de_recuperacion)

        logger.info(
            f"Cálculo final: {fatiga_post_entreno:.2f} * ({decay_factor} ** {dias_de_recuperacion}) = {fatiga_actual:.2f}")

        # El resto de la lógica...
        nivel_fatiga = self._evaluar_nivel_fatiga(fatiga_actual)
        dias_rec_recomendados = self._calcular_dias_recuperacion(fatiga_actual)
        recomendacion = self._generar_recomendacion_descanso(nivel_fatiga, dias_rec_recomendados)

        resultado = {
            'fatiga_actual': round(fatiga_actual, 1),
            'nivel': nivel_fatiga,
            'dias_recuperacion': dias_rec_recomendados,
            'recomendacion_descanso': recomendacion
        }
        logger.info(f"--- CÁLCULO DE FATIGA FINALIZADO: {resultado} ---")
        return resultado

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

    def _generar_recomendaciones_carga(self, carga_promedio, tendencia):
        """
        Genera recomendaciones de carga
        """
        recomendaciones = []

        if carga_promedio < 300:
            recomendaciones.append('Carga muy baja. Considera aumentar volumen o intensidad')
        elif carga_promedio > 1000:
            recomendaciones.append('Carga muy alta. Monitorea signos de sobreentrenamiento')

        if tendencia['direccion'] == 'subiendo' and tendencia['porcentaje'] > 20:
            recomendaciones.append('Incremento de carga muy rápido. Considera progresión más gradual')
        elif tendencia['direccion'] == 'bajando' and tendencia['porcentaje'] > 15:
            recomendaciones.append('Reducción significativa de carga. Evalúa si es intencional')

        if not recomendaciones:
            recomendaciones.append('Carga de entrenamiento en rango óptimo')

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
        if fatiga_actual < 50:
            return 'baja'
        elif fatiga_actual < 100:
            return 'moderada'
        elif fatiga_actual < 150:
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


# Vista para el Dashboard de Intensidad Avanzado - VERSIÓN DE DEPURACIÓN

def dashboard_intensidad_avanzado(request, cliente_id):
    """
    Vista principal del Dashboard de Intensidad Avanzado.
    - CON LIMPIEZA DE CACHE FORZADA PARA DEPURACIÓN.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    analizador = AnalisisIntensidadAvanzado(cliente)

    # --- LÓGICA DE DEPURACIÓN ---
    # Forzamos la eliminación del cache en cada carga para asegurarnos
    # de que todos los cálculos se hacen desde cero.
    cache_key = f'dashboard_intensidad_{cliente.id}'
    cache.delete(cache_key)
    logger.info(f"¡CACHE FORZADO A LIMPIAR PARA '{cache_key}'!")
    # --- FIN DE LÓGICA DE DEPURACIÓN ---

    # El resto de la vista ahora se ejecutará siempre con datos frescos.

    periodo = int(request.GET.get('periodo', 30))

    # Como el cache está limpio, estas líneas siempre se ejecutarán
    logger.info(f"Calculando todos los datos para el cliente {cliente.id} (sin cache).")
    zonas_entrenamiento = analizador.analizar_zonas_entrenamiento(periodo_dias=30)
    analisis_carga = analizador.analizar_carga_entrenamiento(periodo_dias=90)
    distribucion_intensidades = analizador.analizar_distribucion_intensidades(periodo_dias=60)

    # El cálculo de fatiga también se ejecuta
    fatiga_acumulada = analizador.calcular_fatiga_acumulada(periodo_dias=14)
    logger.info(f"FATIGA CALCULADA: {fatiga_acumulada}")  # <-- Log para ver el resultado

    # Construcción del contexto
    context = {
        'cliente': cliente,
        'periodo': periodo,
        'zonas_entrenamiento': zonas_entrenamiento,
        'analisis_carga': analisis_carga,
        'distribucion_intensidades': distribucion_intensidades,
        'fatiga_acumulada': fatiga_acumulada,
    }

    # Preparar datos para JS
    datos_graficos = {
        'zonas': {
            'labels': list(context['zonas_entrenamiento']['distribucion'].keys()),
            'valores': [d['porcentaje'] for d in context['zonas_entrenamiento']['distribucion'].values()],
            'colores': ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
        },
        'carga': {
            'carga_semanal': context['analisis_carga']['carga_semanal']
        },
        'intensidades': {
            'distribucion': context['distribucion_intensidades']['distribucion']
        }
    }
    context['datos_graficos'] = json.dumps(datos_graficos)

    return render(request, 'analytics/intensidad_avanzado.html', context)


from django.shortcuts import redirect
from django.contrib import messages
from rutinas.models import Programa, Rutina, RutinaEjercicio, Asignacion
from django.shortcuts import render, get_object_or_404
from clientes.models import Cliente
from entrenos.models import EjercicioBase
from .ia_analizador_programas import AnalizadorProgramaIA
import json
from django.shortcuts import render, get_object_or_404, redirect
from clientes.models import Cliente
from rutinas.models import Asignacion, Programa  # ... y otros modelos que necesites
from django.utils.html import escape


def vista_optimizacion_programa(request, cliente_id):
    """
    Analiza el PROGRAMA ASIGNADO a un cliente y lo muestra en el
    template de optimización.
    """
    print("✅✅✅ ¡ÉXITO! La URL está llamando a 'vista_optimizacion_programa' correctamente. ✅✅✅")
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # =================================================================
    # ### CORRECCIÓN CLAVE ###
    # Nos aseguramos de que 'programa_asignado' se define correctamente
    # antes de ser usada.
    # =================================================================
    try:
        # Buscamos la asignación para este cliente
        asignacion = Asignacion.objects.get(cliente=cliente)
        # Obtenemos el programa a través de la asignación
        programa_asignado = asignacion.programa
        print(f"✅ Asignación encontrada. Analizando programa: '{programa_asignado.nombre}'")

    except Asignacion.DoesNotExist:
        # Si no hay asignación, mostramos un error claro y terminamos.
        print("❌ No se encontró asignación para este cliente.")
        return render(request, 'error.html',
                      {'message': 'Este cliente no tiene un programa de entrenamiento asignado.'})

    # A partir de aquí, la variable 'programa_asignado' SIEMPRE existe.
    objetivo_actual = request.GET.get('objetivo', cliente.objetivo_principal)
    if objetivo_actual not in ['hipertrofia', 'fuerza', 'resistencia', 'general']:
        objetivo_actual = cliente.objetivo_principal

    # Usamos la variable que hemos definido
    analizador = AnalizadorProgramaIA(programa_asignado, objetivo_actual)
    contexto_ia = analizador.analizar_y_generar_contexto()
    # Convertimos el diccionario a una cadena JSON aquí mismo
    programa_modificado_json_string = json.dumps(analizador.programa_modificado)
    json_string = json.dumps(analizador.programa_modificado)
    programa_original_dict = analizador._clonar_programa_a_diccionario(programa_asignado)
    programa_original_json_string = json.dumps(programa_original_dict)
    # 2. Escapamos las comillas dobles de la cadena para que sea segura
    #    dentro de un atributo value="..." del HTML.
    json_string_escaped = escape(json_string)
    context = {
        'cliente': cliente,
        'objetivo_actual': objetivo_actual,
        'programa_modificado_json': programa_modificado_json_string,
        'programa_modificado': analizador.programa_modificado,
        'programa_modificado_json_escaped': json_string_escaped,
        'programa_original_json_escaped': escape(programa_original_json_string),
        **contexto_ia
    }

    return render(request, 'analytics/optimizacion_entrenamientos.html', context)


from django.utils.safestring import mark_safe
from .vendor.diff_match_patch import diff_match_patch  # Necesitaremos esto

# ... (tus otras vistas) ...
# analytics/views_ia.py

# ... (tus otras importaciones) ...
from django.utils.html import escape  # <-- Asegúrate de que esta importación existe


# ... (tus otras vistas) ...

def vista_optimizacion_programa(request, cliente_id):
    """
    Analiza el PROGRAMA ASIGNADO a un cliente y lo muestra en el
    template de optimización.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        asignacion = Asignacion.objects.get(cliente=cliente)
        programa_asignado = asignacion.programa
    except Asignacion.DoesNotExist:
        return render(request, 'error.html',
                      {'message': 'Este cliente no tiene un programa de entrenamiento asignado.'})

    objetivo_actual = request.GET.get('objetivo', cliente.objetivo_principal)
    if objetivo_actual not in ['hipertrofia', 'fuerza', 'resistencia', 'general']:
        objetivo_actual = cliente.objetivo_principal

    analizador = AnalizadorProgramaIA(programa_asignado, objetivo_actual)
    contexto_ia = analizador.analizar_y_generar_contexto()

    # =================================================================
    # ### CORRECCIÓN FINAL Y DEFINITIVA ###
    # Aquí preparamos los datos JSON que el formulario necesita para
    # enviarlos a la siguiente vista (la de comparación).
    # =================================================================

    # 1. Clonamos el programa original a un diccionario
    programa_original_dict = analizador._clonar_programa_a_diccionario(programa_asignado)

    # 2. Convertimos ambos diccionarios (original y modificado) a cadenas JSON
    programa_original_json_string = json.dumps(programa_original_dict)
    programa_modificado_json_string = json.dumps(analizador.programa_modificado)

    # 3. Construimos el contexto final, añadiendo las versiones "escapadas"
    #    de los JSON para que sean seguras en el HTML.
    context = {
        'cliente': cliente,
        'objetivo_actual': objetivo_actual,

        # Datos para el formulario
        'programa_original_json_escaped': escape(programa_original_json_string),
        'programa_modificado_json_escaped': escape(programa_modificado_json_string),

        # Desempaquetamos el resto de datos de la IA (rutina_optimizada, etc.)
        **contexto_ia
    }
    # =================================================================

    return render(request, 'analytics/optimizacion_entrenamientos.html', context)


# analytics/views.py

# ... (otros imports) ...

def vista_resumen_anual(request, cliente_id):
    """
    Muestra una vista de alto nivel de todo el plan anual,
    organizado por mesociclos o bloques.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Generamos el plan (la lógica es la misma que en la vista del calendario)
    calculadora = CalculadoraEjerciciosTabla(cliente)
    one_rm_reales = calculadora.calcular_1rm_estimado_por_ejercicio()
    if not one_rm_reales:
        one_rm_reales = {'Press de Banca': 80, 'Sentadilla': 100}

    cliente_data = {"id": cliente.id, "nombre": cliente.nombre, "one_rm_estimados": one_rm_reales}
    planificador = inicializar_planificador_helms(cliente)

    # El método ahora devuelve un diccionario
    plan_semanal, plan_por_bloques = planificador.generar_plan_completo()

    context = {
        'cliente': cliente,
        'plan_por_bloques': plan_por_bloques,  # Usamos la variable directamente
        'total_semanas': len(plan_semanal)  # Usamos la otra variable para el conteo
    }

    return render(request, 'analytics/vista_resumen_anual.html', context)


# analytics/views.py

# ... (asegúrate de tener estos imports al principio del archivo)
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from datetime import datetime

import json

# analytics/views.py

# ... (imports) ...
import re  # Asegúrate de tener este import para las expresiones regulares


@login_required
@require_http_methods(["POST"])
def api_marcar_entreno_completado(request, cliente_id):
    """
    API para marcar una rutina del plan como completada.
    VERSIÓN CORREGIDA que procesa los datos de repeticiones.
    """
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        data = json.loads(request.body)

        fecha_str = data.get('fecha')
        rutina_nombre = data.get('rutina_nombre')
        ejercicios = data.get('ejercicios')

        if not all([fecha_str, rutina_nombre, ejercicios]):
            return JsonResponse({'error': 'Faltan datos en la solicitud.'}, status=400)

        fecha_entreno = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        entreno = EntrenoRealizado.objects.create(
            cliente=cliente,
            fecha=fecha_entreno,
            nombre=rutina_nombre,
        )

        for ejercicio_data in ejercicios:

            # --- INICIO DE LA CORRECCIÓN ---
            reps_str = str(ejercicio_data.get('repeticiones', '0'))

            # Usamos una expresión regular para encontrar todos los números en el string
            numeros = re.findall(r'\d+', reps_str)

            repeticiones_a_guardar = 0
            if len(numeros) > 0:
                # Si hay números, los convertimos a entero y calculamos el promedio
                numeros_int = [int(n) for n in numeros]
                repeticiones_a_guardar = int(sum(numeros_int) / len(numeros_int))
            # --- FIN DE LA CORRECCIÓN ---

            EjercicioRealizado.objects.create(
                entreno=entreno,
                nombre_ejercicio=ejercicio_data.get('nombre'),
                series=int(ejercicio_data.get('series', 0)),  # Aseguramos que sea entero
                repeticiones=repeticiones_a_guardar,  # Usamos el valor procesado
                peso_kg=float(ejercicio_data.get('peso_recomendado_kg', 0)),  # Aseguramos que sea float
                completado=True
            )

        return JsonResponse({
            'success': True,
            'message': f'Entrenamiento "{rutina_nombre}" del {fecha_str} guardado correctamente.'
        })

    except Exception as e:
        # Devolvemos el error específico para facilitar la depuración
        return JsonResponse({'error': f'Error interno del servidor: {str(e)}'}, status=500)


# analytics/views.py

# ... (Asegúrate de tener los imports: json, datetime, timedelta, etc.)
import pandas as pd  # Usaremos pandas para calcular medias móviles fácilmente. ¡Es muy eficiente!


# Si no tienes pandas, instálalo con: pip install pandas

class AnalizadorCargaYFatiga:
    def __init__(self, cliente, periodo_dias=90):
        self.cliente = cliente
        self.fecha_fin = timezone.now().date()
        self.fecha_inicio = self.fecha_fin - timedelta(days=periodo_dias)
        self.entrenamientos = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha__gte=self.fecha_inicio,
            fecha__lte=self.fecha_fin
        ).order_by('fecha')

    def _calcular_carga_entrenamiento(self, entreno):
        """
        Calcula la Carga de Entrenamiento (Training Load) multi-métrica.
        Combina Volumen (GYM) con Duración x RPE (Cardio/Intensidad).
        """
        carga = 0.0
        # 1. Carga por Volumen (Fuerza)
        if entreno.volumen_total_kg and entreno.volumen_total_kg > 0:
            carga += float(entreno.volumen_total_kg) / 1000.0
        
        # 2. Carga por Duración y RPE (Cardio/HIIT/Metabólico)
        duracion = entreno.duracion_minutos or 0
        rpe = 0
        
        # Intentar obtener RPE y duración de la sesión detallada si existe
        if hasattr(entreno, 'sesion_detalle'):
            rpe = entreno.sesion_detalle.rpe_medio or 0
            if not duracion:
                duracion = entreno.sesion_detalle.duracion_minutos or 0
        
        if duracion > 0:
            # Si no hay RPE registrado, asumimos un esfuerzo base de 5.0 (moderado)
            rpe_val = rpe if rpe > 0 else 5.0
            # Normalización: (Minutos * RPE) / 100
            carga += (duracion * float(rpe_val)) / 100.0
             
        return round(float(carga), 2)

    def _generar_narrativa_dinamica(self, df, acwr_actual, zona_riesgo, monotonia=0):
        """
        Analiza el DataFrame de carga y genera un resumen textual dinámico.
        """
        if df.empty or df['carga_diaria'].sum() == 0:
            return {
                'titulo': "Esperando Datos",
                'resumen': "Aún no hay suficientes datos de entrenamiento en este período para generar un análisis. ¡Es hora de empezar a entrenar!",
                'puntos_clave': []
            }

        # 1. Analizar la tendencia general del Fitness (Carga Crónica)
        # Comparamos el fitness del último tercio del período con el primero
        tercio = len(df) // 3
        fitness_inicial = df['carga_cronica'].iloc[:tercio].mean()
        fitness_final = df['carga_cronica'].iloc[-tercio:].mean()

        tendencia_fitness = "estable."
        if fitness_final > fitness_inicial * 1.1:  # Si ha aumentado más de un 10%
            tendencia_fitness = "ascendente, lo cual es excelente."
        elif fitness_final < fitness_inicial * 0.9:  # Si ha disminuido más de un 10%
            tendencia_fitness = "descendente, indicando una posible pérdida de forma."

        resumen = f"Durante el último período, tu nivel de fitness (Carga Crónica) ha mostrado una tendencia general {tendencia_fitness}"

        # 2. Identificar puntos clave
        puntos_clave = []

        # Análisis de Monotonía
        if monotonia > 2.0:
            puntos_clave.append({
                'emoji': '🥱',
                'texto': f"Tu entrenamiento es muy monótono (índice <strong>{monotonia}</strong>). Variar la intensidad (días duros vs suaves) ayuda a evitar el estancamiento."
            })
        elif monotonia < 1.2:
             puntos_clave.append({
                'emoji': '⚡',
                'texto': f"¡Gran variedad! Tu índice de monotonía es bajo (<strong>{monotonia}</strong>), lo que indica una buena alternancia entre cargas altas y bajas."
            })

        # Punto de mayor riesgo
        riesgo_max = df['acwr'].max()
        if riesgo_max >= 1.5:
            fecha_riesgo_max = df['acwr'].idxmax().strftime('%d de %B')
            puntos_clave.append({
                'emoji': '🚨',
                'texto': f"Se detectó un pico de riesgo el <strong>{fecha_riesgo_max}</strong> con un ratio de {riesgo_max:.2f}. Estos son los momentos donde hay que priorizar la recuperación."
            })

        # Períodos de descarga o baja carga
        periodos_baja_carga = (df['acwr'] < 0.8).sum()
        if periodos_baja_carga > 5:  # Si hubo más de 5 días en baja carga
            puntos_clave.append({
                'emoji': '🔋',
                'texto': "Has tenido períodos de baja carga, ideales para la recuperación y supercompensación, o indicativos de una pausa en el entrenamiento."
            })

        # Estado actual
        if zona_riesgo == 'optima':
            puntos_clave.append({
                'emoji': '✅',
                'texto': f"Actualmente, con un ratio de <strong>{acwr_actual:.2f}</strong>, te encuentras en la zona óptima para seguir progresando de forma segura."
            })
        else:
            puntos_clave.append({
                'emoji': '⚠️',
                'texto': f"Tu estado actual (ratio de <strong>{acwr_actual:.2f}</strong>) sugiere que debes prestar atención a la recomendación para ajustar tu próxima semana."
            })

        return {
            'titulo': "Análisis del Período",
            'resumen': resumen,
            'puntos_clave': puntos_clave
        }

    def analizar_acwr(self, periodo_agudo=7, periodo_cronico=28):
        """
        Calcula el ratio ACWR y genera narrativa dinámica.
        Si no hay carga en los últimos 7 días, retrocede al último entreno para dar feedback útil.
        """
        if not self.entrenamientos.exists():
            return {
                'dataframe_json': pd.DataFrame().to_json(orient='split'),
                'acwr_actual': 0,
                'zona_riesgo': 'muy_baja',
                'recomendacion': 'No hay datos suficientes. ¡A entrenar!',
                'narrativa': self._generar_narrativa_dinamica(pd.DataFrame(), 0, 'muy_baja')
            }

        # --- Lógica de Ventana Activa ---
        # Si el último entreno es previo a hoy, pero reciente (< 30 días), 
        # centramos el análisis ahí para no mostrar un dashboard vacío de 0.00.
        ultimo_entreno_fecha = self.entrenamientos.latest('fecha').fecha
        hoy = timezone.now().date()
        referencia = hoy
        
        # Si David no ha entrenado esta semana, pero sí en el último mes
        if (hoy - ultimo_entreno_fecha).days > 7 and (hoy - ultimo_entreno_fecha).days < 30:
            referencia = ultimo_entreno_fecha

        idx = pd.date_range(start=referencia - timedelta(days=90), end=referencia)
        cargas_diarias = {entreno.fecha: self._calcular_carga_entrenamiento(entreno) for entreno in self.entrenamientos}
        df = pd.DataFrame(cargas_diarias.items(), columns=['fecha', 'carga_diaria'])
        df['fecha'] = pd.to_datetime(df['fecha'])
        df = df.set_index('fecha').reindex(idx, fill_value=0)
        
        df['carga_aguda'] = df['carga_diaria'].rolling(window=periodo_agudo, min_periods=1).mean()
        df['carga_cronica'] = df['carga_diaria'].rolling(window=periodo_cronico, min_periods=1).mean()
        df['acwr'] = (df['carga_aguda'] / df['carga_cronica']).fillna(0)

        acwr_actual = round(df['acwr'].iloc[-1], 2) if not df.empty else 0
        # ... (lógica para determinar zona_riesgo y recomendacion se mantiene igual)
        # ... (lógica para determinar zona_riesgo y recomendacion se mantiene igual)
        if 0.8 <= acwr_actual <= 1.3:
            zona_riesgo = 'optima'
            recomendacion = "Estás en la 'zona dulce'. La carga es ideal para progresar de forma segura."
        elif 1.3 < acwr_actual < 1.5:
            zona_riesgo = 'cuidado'
            recomendacion = "Estás aumentando la carga. Procede con cuidado y vigila la recuperación."
        elif acwr_actual >= 1.5:
            zona_riesgo = 'riesgo_alto'
            recomendacion = "¡Peligro! El riesgo de lesión es elevado. Considera reducir la intensidad o el volumen."
        else:  # Cubre acwr < 0.8 y el caso inicial de 0
            zona_riesgo = 'baja_carga'
            recomendacion = "La carga es baja, lo que puede llevar a una pérdida de adaptaciones. Ideal para una semana de descarga."

        # CÁLCULO DE MONOTONÍA Y STRAIN (Añadido)
        # Monotonía = Carga Media Diaria / Desviación Estándar
        # Strain = Carga Total Semanal * Monotonía
        if not df.empty and len(df) >= 7:
            last_7_days = df.iloc[-7:]
            mean_load = last_7_days['carga_diaria'].mean()
            std_dev = last_7_days['carga_diaria'].std()

            if std_dev > 0:
                monotonia = round(mean_load / std_dev, 2)
            else:
                monotonia = 0 # Evitar división por cero si todos los días son iguales (std=0)

            carga_semanal = last_7_days['carga_diaria'].sum()
            strain_raw = carga_semanal * monotonia
            
            # Normalización del Strain (0-100) para mejor comprensión
            # Usamos un valor de referencia basado en el histórico o un estimado 'alto'
            # Si no hay histórico suficiente, usamos un valor base razonable.
            max_strain_historico = 1.0
            if len(df) > 30:
                 # Calculamos el strain histórico para normalizar
                 # Esto es aproximado pero sirve para la escala
                 df['rolling_std'] = df['carga_diaria'].rolling(7).std()
                 df['rolling_mean'] = df['carga_diaria'].rolling(7).mean()
                 df['rolling_load'] = df['carga_diaria'].rolling(7).sum()
                 df['rolling_strain'] = df['rolling_load'] * (df['rolling_mean'] / df['rolling_std'].replace(0, 1))
                 max_strain_historico = df['rolling_strain'].max()
            
            if max_strain_historico == 0: max_strain_historico = 1 # Evitar div/0
            
            # Si el strain actual es mayor, será 100 (o más, pero lo capamos visualmente)
            # Si es muy bajo, será cercano a 0.
            # Convertimos a escala 0-10.
            # Ajuste heurístico: Si strain_raw es > max_historico, es un 10.
            
            # Simplificación: Devolvemos el valor raw y un porcentaje relativo
            strain = round(strain_raw, 1)
            strain_percent = min(round((strain_raw / max_strain_historico) * 100), 100) if max_strain_historico > 1 else 0

        else:
            monotonia = 0
            strain = 0
            strain_percent = 0

        es_monotono = monotonia > 2.0

        # --- CÁLCULO DE MONOTONÍA Y STRAIN (NUEVO) ---
        # Monotonía = Carga Promedio / Desviación Estándar
        # Strain = Carga Total * Monotonía
        # Ya calculado arriba.
        
        # Preparar datos para el gráfico (Lista de dicts, no string JSON)
        df_reset = df.reset_index()
        # Aseguramos que la columna de fecha tenga el nombre correcto
        if 'index' in df_reset.columns:
            df_reset = df_reset.rename(columns={'index': 'fecha'})
        
        # Convertimos fechas a string ISO para evitar problemas de serialización
        df_reset['fecha'] = df_reset['fecha'].dt.strftime('%Y-%m-%d')
        
        # Convertimos a lista de diccionarios
        chart_data = df_reset.to_dict(orient='records')
        
        # Limpieza manual asegurada de NaN/Infinitos
        for record in chart_data:
            for key, value in record.items():
                # Verificamos si es float y si es nulo (NaN) o infinito
                if isinstance(value, float) and pd.isna(value):
                    record[key] = None
                # También limpiar strings 'NaN' si hubieran quedado
                elif value == 'NaN':
                    record[key] = None

        return {
            'dataframe_json': chart_data, # Ahora es una lista, no un string JSON
            'acwr_actual': acwr_actual,
            'zona_riesgo': zona_riesgo,
            'recomendacion': recomendacion,
            'narrativa': self._generar_narrativa_dinamica(df, acwr_actual, zona_riesgo, monotonia),
            'monotonia': monotonia,
            'es_monotono': es_monotono,
            'strain': strain,
            'strain_percent': strain_percent # Nuevo campo para la barra de progreso
        }




# --- AÑADE ESTA NUEVA VISTA ---
@login_required
def dashboard_fatiga(request, cliente_id):
    """
    Vista para el nuevo Dashboard de Gestión de Fatiga y Recuperación.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    analizador = AnalizadorCargaYFatiga(cliente)

    # Obtenemos el análisis ACWR
    analisis_acwr = analizador.analizar_acwr()

    context = {
        'cliente': cliente,
        'analisis_acwr': analisis_acwr,
    }
    return render(request, 'analytics/dashboard_fatiga.html', context)


# analytics/views.py
# ... (asegúrate de tener los imports de json, JsonResponse, require_http_methods, etc. )
from .models import MetaRendimiento, AnotacionEntrenamiento  # Importa los nuevos modelos


@login_required
@require_http_methods(["POST"])
def api_guardar_meta(request, cliente_id):
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        data = json.loads(request.body)

        MetaRendimiento.objects.create(
            cliente=cliente,
            nombre_ejercicio=data['ejercicio'],
            fecha_objetivo=data['fecha'],
            valor_objetivo=data['valor']
        )
        return JsonResponse({'success': True, 'message': '¡Meta guardada correctamente!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_guardar_anotacion(request, cliente_id):
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        data = json.loads(request.body)

        AnotacionEntrenamiento.objects.create(
            cliente=cliente,
            fecha=data['fecha'],
            tipo=data['tipo'],
            descripcion=data['descripcion'],
            ejercicio_asociado=data.get('ejercicio')  # .get() para que sea opcional
        )
        return JsonResponse({'success': True, 'message': '¡Anotación guardada correctamente!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# analytics/views.py

# ... (Asegúrate de tener todos los imports necesarios: render, get_object_or_404, Cliente, etc.)
import json  # Necesario para pasar datos a la plantilla


# Puedes colocar esta clase junto a tus otras clases de análisis
class AnalizadorEquilibrioMuscular:
    def __init__(self, cliente):
        self.cliente = cliente
        # Usaremos la calculadora que ya tienes para obtener los 1RM
        self.calculadora = CalculadoraEjerciciosTabla(cliente)

    def _calcular_ratio(self, valor1, valor2):
        """Calcula un ratio de forma segura, evitando divisiones por cero."""
        if valor1 > 0 and valor2 > 0:
            return round(valor1 / valor2, 2)
        return 0

    def analizar_ratios_fuerza(self):
        """
        Calcula los ratios de fuerza clave y los compara con estándares óptimos.
        """
        # 1. Obtenemos los 1RM estimados de la calculadora que ya existe
        one_rm_estimados = self.calculadora.calcular_1rm_estimado_por_ejercicio()
        print("=" * 50)
        print("🔍 1RMs CALCULADOS POR EL SISTEMA:")
        # 2. Definimos los ratios y los estándares de referencia
        # (Estos son valores comúnmente aceptados en la ciencia del deporte)
        config_ratios = {
            'Press Banca / Sentadilla': {
                'numerador': 'Press Banca', 'denominador': 'Sentadilla', 'optimo': 0.75,
                'descripcion': 'Equilibrio entre empuje de torso y fuerza de piernas.'
            },
            'Peso Muerto / Sentadilla': {
                'numerador': 'Peso Muerto', 'denominador': 'Sentadilla', 'optimo': 1.20,
                'descripcion': 'Equilibrio entre cadena posterior y anterior.'
            },
            'Press Militar / Press Banca': {
                'numerador': 'Press Militar', 'denominador': 'Press Banca', 'optimo': 0.65,
                'descripcion': 'Equilibrio entre empuje vertical y horizontal.'
            },
            'Remo con Barra / Press Banca': {
                'numerador': 'Remo Con Barra', 'denominador': 'Press Banca', 'optimo': 1.0,
                'descripcion': 'Equilibrio entre músculos de empuje y tracción del torso.'
            }
        }

        resultados_ratios = []
        datos_radar = {'labels': [], 'valores_actuales': [], 'valores_optimos': []}

        for nombre_ratio, config in config_ratios.items():
            # Obtenemos los valores de 1RM para el cálculo
            # Usamos .get(key, 0) para manejar casos donde un ejercicio no tiene 1RM
            valor_num = one_rm_estimados.get(config['numerador'], 0)
            valor_den = one_rm_estimados.get(config['denominador'], 0)

            # Calculamos el ratio actual
            ratio_actual = self._calcular_ratio(valor_num, valor_den)

            # Determinamos el estado (óptimo, bajo, alto)
            if ratio_actual == 0:
                estado = 'incompleto'
            elif abs(ratio_actual - config['optimo']) < 0.1:  # Margen de +/- 0.1
                estado = 'optimo'
            elif ratio_actual < config['optimo']:
                estado = 'bajo'
            else:
                estado = 'alto'

            # Añadimos los datos a nuestras listas
            resultados_ratios.append({
                'nombre': nombre_ratio,
                'valor_actual': ratio_actual,
                'valor_optimo': config['optimo'],
                'estado': estado,
                'descripcion': config['descripcion']
            })

            datos_radar['labels'].append(nombre_ratio)
            datos_radar['valores_actuales'].append(ratio_actual)
            datos_radar['valores_optimos'].append(config['optimo'])

        return resultados_ratios, datos_radar


# --- AÑADE ESTA NUEVA VISTA ---
# Archivo: analytics/views.py

# Archivo: analytics/views.py

# Archivo: analytics/views.py

@login_required
def dashboard_equilibrio(request, cliente_id):
    """
    Vista para el nuevo Dashboard de Equilibrio Muscular.
    VERSIÓN FINAL Y FUNCIONAL
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # --- INICIO DE LA SOLUCIÓN ---
    # En lugar de usar la clase AnalizadorEquilibrioMuscular, que era la
    # que causaba el problema, replicamos su lógica directamente aquí,
    # usando la CalculadoraEjerciciosTabla que ya hemos verificado que funciona.

    # 1. Obtenemos los 1RM estimados directamente.
    calculadora = CalculadoraEjerciciosTabla(cliente)
    one_rm_estimados = calculadora.calcular_1rm_estimado_por_ejercicio()

    # 2. Definimos los ratios y los estándares de referencia.
    # ¡¡IMPORTANTE!! Ahora debes corregir los nombres aquí para que coincidan
    # con la lista que vimos en la consola.
    config_ratios = {
        'Press Banca / Sentadilla': {
            'numerador': 'Press Banca',  # <-- Revisa si este es el nombre correcto
            'denominador': 'Sentadilla Trasera Con Barra',  # <-- Ejemplo de corrección
            'optimo': 0.75,
            'descripcion': 'Equilibrio entre empuje de torso y fuerza de piernas.'
        },
        'Peso Muerto / Sentadilla': {
            'numerador': 'Peso Muerto',  # <-- Revisa este nombre
            'denominador': 'Sentadilla Trasera Con Barra',  # <-- Ejemplo de corrección
            'optimo': 1.20,
            'descripcion': 'Equilibrio entre cadena posterior y anterior.'
        },
        'Press Militar / Press Banca': {
            'numerador': 'Press Militar Con Barra (De Pie)',  # <-- Ejemplo de corrección
            'denominador': 'Press Banca',  # <-- Revisa este nombre
            'optimo': 0.65,
            'descripcion': 'Equilibrio entre empuje vertical y horizontal.'
        },
        'Remo / Press Banca': {
            'numerador': 'Remo En Máquina Hammer',  # <-- Ejemplo de corrección
            'denominador': 'Press Banca',  # <-- Revisa este nombre
            'optimo': 1.0,
            'descripcion': 'Equilibrio entre músculos de empuje y tracción del torso.'
        }
    }

    # 3. Calculamos los ratios (esta lógica es segura).
    resultados_ratios = []
    datos_radar = {'labels': [], 'valores_actuales': [], 'valores_optimos': []}

    for nombre_ratio, config in config_ratios.items():
        valor_num = one_rm_estimados.get(config['numerador'], 0)
        valor_den = one_rm_estimados.get(config['denominador'], 0)

        ratio_actual = 0
        if valor_num > 0 and valor_den > 0:
            ratio_actual = round(valor_num / valor_den, 2)

        if ratio_actual == 0:
            estado = 'incompleto'
        elif abs(ratio_actual - config['optimo']) < 0.1:
            estado = 'optimo'
        elif ratio_actual < config['optimo']:
            estado = 'bajo'
        else:
            estado = 'alto'

        resultados_ratios.append({
            'nombre': nombre_ratio, 'valor_actual': ratio_actual,
            'valor_optimo': config['optimo'], 'estado': estado,
            'descripcion': config['descripcion']
        })
        datos_radar['labels'].append(nombre_ratio)
        datos_radar['valores_actuales'].append(ratio_actual)
        datos_radar['valores_optimos'].append(config['optimo'])

    # --- FIN DE LA SOLUCIÓN ---

    context = {
        'cliente': cliente,
        'ratios': resultados_ratios,
        'datos_radar_json': json.dumps(datos_radar)
    }
    return render(request, 'analytics/dashboard_equilibrio.html', context)
