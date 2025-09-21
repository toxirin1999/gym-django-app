# planificador_helms_completo.py
"""
Planificador Helms Completo - Implementación del sistema de Eric Helms
Basado en "The Muscle and Strength Pyramid"
"""

import math
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any


class PlanificadorHelms:
    """
    Planificador principal basado en la metodología de Eric Helms
    """
    EJERCICIOS_DATABASE = {
        'pecho': {
            'compuesto_principal': ['Press Banca con Barra', 'Press Inclinado con Barra',
                                    'Fondos en Paralelas (con lastre)'],
            'compuesto_secundario': ['Press Banca con Mancuernas', 'Press Inclinado con Mancuernas'],
            'aislamiento': ['Aperturas con Mancuernas', 'Cruce de Poleas', 'Pec Deck']
        },
        'espalda': {
            'compuesto_principal': ['Dominadas (con lastre)', 'Remo con Barra (Pendlay)', 'Peso Muerto'],
            'compuesto_secundario': ['Remo con Mancuerna a una mano', 'Jalón al Pecho', 'Remo en Polea Baja (Gironda)'],
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
            'compuesto_principal': [],  # Los bíceps no suelen tener compuestos principales
            'compuesto_secundario': ['Curl con Barra Z', 'Curl Araña'],
            'aislamiento': ['Curl de Concentración', 'Curl Martillo con Mancuernas', 'Curl en Polea Alta']
        },
        'triceps': {
            'compuesto_principal': ['Press Francés con Barra Z', 'Press Cerrado en Banca'],
            'compuesto_secundario': ['Extensiones de Tríceps en Polea Alta', 'Fondos entre bancos'],
            'aislamiento': ['Patada de Tríceps con Polea']
        }
        # Puedes seguir añadiendo más grupos y ejercicios
    }

    def __init__(self, perfil_cliente: 'PerfilCliente'):
        self.perfil = perfil_cliente
        # Aseguramos un valor por defecto para evitar errores
        self.dias_disponibles = self.perfil.dias_disponibles if self.perfil.dias_disponibles in [3, 4, 5] else 4
        # ... (el resto de los atributos del __init__ no cambian)
        self.experiencia_años = perfil_cliente.experiencia_años
        self.objetivo_principal = perfil_cliente.objetivo_principal
        self.tiempo_por_sesion = perfil_cliente.tiempo_por_sesion
        self.ejercicios_preferidos = perfil_cliente.ejercicios_preferidos
        self.ejercicios_evitar = perfil_cliente.ejercicios_evitar
        self.nivel_estres = perfil_cliente.nivel_estres
        self.calidad_sueño = perfil_cliente.calidad_sueño
        self.nivel_energia = perfil_cliente.nivel_energia
        self.historial_volumen = perfil_cliente.historial_volumen
        self.maximos_actuales = getattr(perfil_cliente, 'maximos_actuales', {})

    # en analytics/planificador_helms_completo.py -> dentro de la clase PlanificadorHelms

    # En analytics/planificador_helms_completo.py, dentro de la clase PlanificadorHelms

    # En analytics/planificador_helms_completo.py, dentro de la clase PlanificadorHelms

    def _calcular_peso_trabajo(self, nombre_ejercicio: str, repeticiones_str: str, rpe_objetivo: int) -> float:
        nombre_normalizado = nombre_ejercicio.strip().lower()
        one_rm_estimado = self.perfil.maximos_actuales.get(nombre_normalizado, 40.0)

        try:
            reps_planificadas = int(repeticiones_str.split('-')[0].strip())
        except:
            reps_planificadas = 8

        try:
            # ==================================================================
            #           LÓGICA DE CÁLCULO DE PESO REFACTORIZADA (v3)
            # ==================================================================

            # 1. Calcular el peso de trabajo teórico para el RPE y repeticiones objetivo.
            #    Este es el peso que DEBERÍAS levantar si tu 1RM es correcto.
            peso_rpe_10 = one_rm_estimado / (1 + (reps_planificadas / 30))
            reduccion_por_rpe = (10 - rpe_objetivo) * 0.03
            peso_base_calculado = peso_rpe_10 * (1 - reduccion_por_rpe)

            # 2. Determinar el tipo de progresión basado en el 1RM actual.
            #    Si el 1RM es muy bajo (ejercicios de aislamiento/mancuernas), usamos un incremento fijo y pequeño.
            #    Si el 1RM es alto (compuestos), usamos un incremento porcentual.

            FACTOR_PROGRESION_PORCENTUAL = 1.05  # Incremento del 5% para ejercicios pesados
            FACTOR_PROGRESION_FIJO_PEQUENO = 1.25  # Incremento de 1.25kg para ejercicios ligeros
            FACTOR_PROGRESION_FIJO_GRANDE = 2.5  # Incremento de 2.5kg para ejercicios pesados

            if one_rm_estimado > 50:  # Umbral para considerarlo un ejercicio "pesado"
                # Progresión porcentual para los grandes levantamientos
                peso_con_progresion = peso_base_calculado * FACTOR_PROGRESION_PORCENTUAL
                incremento_aplicado = f"{((FACTOR_PROGRESION_PORCENTUAL - 1) * 100):.0f}%"
            else:
                # Progresión fija para ejercicios más ligeros para evitar estancamientos
                peso_con_progresion = peso_base_calculado + FACTOR_PROGRESION_FIJO_PEQUENO
                incremento_aplicado = f"+{FACTOR_PROGRESION_FIJO_PEQUENO}kg"

            # 3. Redondear al múltiplo de 2.5 kg más cercano.
            peso_final = round(peso_con_progresion / 2.5) * 2.5

            # --- DEBUGGING ---
            print(f"\n--- Calculando peso para: '{nombre_normalizado}' ---")
            print(f"1RM encontrado: {one_rm_estimado:.2f} kg")
            print(f"Peso base calculado para RPE {rpe_objetivo}: {peso_base_calculado:.2f} kg")
            print(f"Aplicando incremento ({incremento_aplicado}): {peso_con_progresion:.2f} kg")
            print(f"Peso final redondeado: {peso_final} kg")
            print("--------------------------------------------------")

            return peso_final

        except ZeroDivisionError:
            return 20.0

    def generar_entrenamiento_para_fecha(self, fecha_objetivo: date):
        """
        Genera la rutina específica para una fecha dada, usando la periodización
        y la disponibilidad de días del perfil del cliente.
        """
        try:
            semana_num_total = fecha_objetivo.isocalendar()[1]
            dia_semana_num = fecha_objetivo.weekday()  # Lunes=0
        except Exception:
            return None

        periodizacion = self._generar_periodizacion_anual()
        bloque_actual = None
        numero_bloque_actual = 0
        for i, bloque in enumerate(periodizacion, 1):
            if semana_num_total in bloque.get('semanas', []):
                bloque_actual = bloque
                numero_bloque_actual = i
                break

        if not bloque_actual:
            return None

        mapa_dias = {}
        dias_entreno_keys = [f'dia_{i + 1}' for i in range(self.dias_disponibles)]

        if self.dias_disponibles == 3:
            dias_entreno_indices = [0, 2, 4]
        elif self.dias_disponibles == 5:
            dias_entreno_indices = [0, 1, 2, 3, 4]
        else:
            dias_entreno_indices = [0, 1, 3, 4]

        for i, dia_index in enumerate(dias_entreno_indices):
            if i < len(dias_entreno_keys):
                mapa_dias[dia_index] = dias_entreno_keys[i]

        clave_dia = mapa_dias.get(dia_semana_num)

        if not clave_dia:
            return {"rutina_nombre": "Día de Descanso", "ejercicios": [], "objetivo": "Descanso"}

        nivel_experiencia = self._determinar_nivel_experiencia()
        volumen_base = self._calcular_volumen_base(nivel_experiencia)
        plan_semanal_base = self._crear_plan_semanal_base(volumen_base)

        semana_completa = self._generar_semana_especifica(plan_semanal_base, bloque_actual, numero_bloque_actual)

        ejercicios_del_dia = semana_completa.get(clave_dia)

        if not ejercicios_del_dia:
            return {"rutina_nombre": "Día de Descanso", "ejercicios": [], "objetivo": "Descanso"}

        return {
            "rutina_nombre": f"{clave_dia.replace('_', ' ').title()} - {bloque_actual['fase'].replace('_', ' ').title()}",
            "ejercicios": ejercicios_del_dia,
            "objetivo": bloque_actual['fase'].replace('_', ' ').title(),
            "bloque": bloque_actual.get('nombre', bloque_actual['fase'].title()),
        }

    def generar_plan_anual(self) -> Dict[str, Any]:
        """
        MODIFICADO: Ahora pasa el número de bloque a la generación de la semana.
        """
        # ... (la lógica inicial para nivel, volumen, periodización y plan_semanal_base se mantiene)
        nivel_experiencia = self._determinar_nivel_experiencia()
        volumen_base = self._calcular_volumen_base(nivel_experiencia)
        periodizacion = self._generar_periodizacion_anual()
        plan_semanal_base = self._crear_plan_semanal_base(volumen_base)

        entrenos_por_fecha = {}
        plan_por_bloques = []
        # ... (la lógica para los días de entreno y la fecha de inicio se mantiene)
        if self.dias_disponibles == 3:
            dias_de_entreno_offset = [0, 2, 4]
        elif self.dias_disponibles == 5:
            dias_de_entreno_offset = [0, 1, 2, 3, 4]
        else:
            dias_de_entreno_offset = [0, 1, 3, 4]

        año_actual = datetime.now().year
        primer_dia_del_año = date(año_actual, 1, 1)
        dias_para_lunes = (0 - primer_dia_del_año.weekday() + 7) % 7
        fecha_inicio_plan = primer_dia_del_año + timedelta(days=dias_para_lunes)

        semana_global_actual = 0
        # --- BUCLE PRINCIPAL MODIFICADO ---
        # Usamos enumerate para obtener el índice del bloque (numero_bloque)
        for numero_bloque, bloque in enumerate(periodizacion, 1):
            semanas_del_bloque_para_resumen = []

            for _ in bloque['semanas']:
                semana_global_actual += 1
                if semana_global_actual > 52: break

                semanas_del_bloque_para_resumen.append({'semana_num_total': semana_global_actual})

                # --- PASAMOS EL NÚMERO DE BLOQUE ---
                plan_de_la_semana = self._generar_semana_especifica(plan_semanal_base, bloque, numero_bloque)

                # ... (el resto de la lógica para asignar fechas se mantiene igual)
                dias_entreno_keys = sorted(plan_de_la_semana.keys())
                for i, dia_key in enumerate(dias_entreno_keys):
                    if i >= len(dias_de_entreno_offset): continue
                    offset_dia_semana = dias_de_entreno_offset[i]
                    dias_desde_inicio = ((semana_global_actual - 1) * 7) + offset_dia_semana
                    fecha_entrenamiento = fecha_inicio_plan + timedelta(days=dias_desde_inicio)
                    ejercicios = plan_de_la_semana[dia_key]
                    entrenos_por_fecha[fecha_entrenamiento.isoformat()] = {
                        "nombre_rutina": f"Día {i + 1} - {bloque['fase'].title()}",
                        "ejercicios": ejercicios
                    }

            plan_por_bloques.append({
                'nombre': bloque['fase'].replace('_', ' ').title(),
                'objetivo': bloque['fase'],
                'duracion': len(bloque['semanas']),
                'semanas': semanas_del_bloque_para_resumen
            })
            if semana_global_actual > 52: break

        return {
            'cliente_id': self.perfil.id,
            'plan_por_bloques': plan_por_bloques,
            'entrenos_por_fecha': entrenos_por_fecha,
            'metadata': {'generado_por': 'helms'}
        }

    def _generar_fases_para_template(self, periodizacion: List[Dict]) -> List[Dict]:
        """Crea una lista simplificada de fases para la plantilla."""
        fases_vistas = set()
        fases_unicas = []
        for bloque in periodizacion:
            if bloque['fase'] not in fases_vistas:
                fases_unicas.append({
                    'nombre': bloque['fase'].title(),
                    'rep_range': bloque['rep_range'],
                    'rpe': f"{bloque['intensidad_rpe'][0]}-{bloque['intensidad_rpe'][1]}"
                })
                fases_vistas.add(bloque['fase'])
        return fases_unicas

    def _determinar_nivel_experiencia(self) -> str:
        """Determina el nivel de experiencia según los años de entrenamiento"""
        if self.experiencia_años < 1:
            return 'principiante'
        elif self.experiencia_años < 3:
            return 'intermedio'
        else:
            return 'avanzado'

    def _calcular_volumen_base(self, nivel_experiencia: str) -> Dict[str, int]:
        """Calcula el volumen base por grupo muscular según Helms"""
        volumenes_base = {
            'principiante': {
                'pecho': 10, 'espalda': 12, 'hombros': 8, 'biceps': 6,
                'triceps': 6, 'cuadriceps': 12, 'isquios': 8, 'gluteos': 8, 'gemelos': 6
            },
            'intermedio': {
                'pecho': 14, 'espalda': 16, 'hombros': 12, 'biceps': 8,
                'triceps': 8, 'cuadriceps': 16, 'isquios': 10, 'gluteos': 12, 'gemelos': 8
            },
            'avanzado': {
                'pecho': 18, 'espalda': 20, 'hombros': 16, 'biceps': 12,
                'triceps': 12, 'cuadriceps': 20, 'isquios': 14, 'gluteos': 16, 'gemelos': 12
            }
        }

        return volumenes_base[nivel_experiencia]

    # en analytics/planificador_helms_completo.py

    def _generar_periodizacion_anual(self) -> List[Dict[str, Any]]:
        """
        Genera la periodización anual basada en un enfoque de hipertrofia con bloques
        de fuerza base, hipertrofia específica, mini potencia y extensión hasta 52 semanas.
        """
        plan_base = [
            # Hipertrofia 1 (8 semanas)
            {'fase': 'hipertrofia', 'objetivo': 'hipertrofia',
             'semanas': 8, 'vol_mult': 1.2, 'rpe': (7, 8), 'reps': '8-12'},
            # Fuerza Base (4 semanas)
            {'fase': 'fuerza_base', 'objetivo': 'fuerza',
             'semanas': 4, 'vol_mult': 0.9, 'rpe': (8, 9), 'reps': '4-6'},
            # Hipertrofia 2 (8 semanas)
            {'fase': 'hipertrofia', 'objetivo': 'hipertrofia',
             'semanas': 8, 'vol_mult': 1.2, 'rpe': (7, 8), 'reps': '8-12'},
            # Hipertrofia Específica (6 semanas)
            {'fase': 'hipertrofia_especifica', 'objetivo': 'hipertrofia',
             'semanas': 6, 'vol_mult': 1.25, 'rpe': (7, 8), 'reps': '8-12'},
            # Mini Potencia / Resensibilización (2 semanas)
            {'fase': 'mini_potencia', 'objetivo': 'potencia',
             'semanas': 2, 'vol_mult': 0.7, 'rpe': (8,), 'reps': '3-5'},
            # Hipertrofia Final (10 semanas)
            {'fase': 'hipertrofia_final', 'objetivo': 'hipertrofia',
             'semanas': 10, 'vol_mult': 1.2, 'rpe': (7, 8), 'reps': '8-12'},
            # Bloque adicional para completar hasta 52 semanas:
            # Mini Potencia 2 (2 semanas) + Hipertrofia Estética (7 semanas)
            {'fase': 'mini_potencia_2', 'objetivo': 'potencia',
             'semanas': 2, 'vol_mult': 0.7, 'rpe': (8,), 'reps': '3-5'},
            {'fase': 'hipertrofia_estetica', 'objetivo': 'hipertrofia',
             'semanas': 7, 'vol_mult': 1.2, 'rpe': (7, 8), 'reps': '10-15'}
        ]

        periodizacion_anual = []
        semana_actual = 1
        contador_descarga = 0

        for bloque in plan_base:
            semanas_en_bloque = []
            for _ in range(bloque['semanas']):
                if semana_actual > 52:
                    break
                semanas_en_bloque.append(semana_actual)
                semana_actual += 1
                contador_descarga += 1

                # Cada 7 semanas aproximadamente, insertar descarga
                if contador_descarga >= 7 and semana_actual <= 52:
                    periodizacion_anual.append({
                        'semanas': [semana_actual],
                        'fase': 'descarga',
                        'volumen_multiplicador': 0.5,
                        'intensidad_rpe': (6,),
                        'rep_range': '10-15'
                    })
                    semana_actual += 1
                    contador_descarga = 0

            # Añadir bloque principal al plan
            if semanas_en_bloque:
                periodizacion_anual.append({
                    'semanas': semanas_en_bloque,
                    'fase': bloque['fase'],
                    'volumen_multiplicador': bloque['vol_mult'],
                    'intensidad_rpe': bloque['rpe'],
                    'rep_range': bloque['reps']
                })

            if semana_actual > 52:
                break

        return periodizacion_anual

    def _periodizacion_hipertrofia(self) -> List[Dict[str, Any]]:
        """Periodización específica para hipertrofia"""
        return [
            {
                'semanas': list(range(1, 5)),
                'fase': 'acumulacion',
                'volumen_multiplicador': 1.0,
                'intensidad_rpe': (7, 8),
                'rep_range': '8-12'
            },
            {
                'semanas': list(range(5, 8)),
                'fase': 'intensificacion',
                'volumen_multiplicador': 0.8,
                'intensidad_rpe': (8, 9),
                'rep_range': '6-10'
            },
            {
                'semanas': [8],
                'fase': 'descarga',
                'volumen_multiplicador': 0.6,
                'intensidad_rpe': (6, 7),
                'rep_range': '8-12'
            }
        ] * 6  # Repetir 6 veces para el año

    def _periodizacion_fuerza(self) -> List[Dict[str, Any]]:
        """Periodización específica para fuerza"""
        return [
            {
                'semanas': list(range(1, 4)),
                'fase': 'acumulacion',
                'volumen_multiplicador': 1.0,
                'intensidad_rpe': (7, 8),
                'rep_range': '3-6'
            },
            {
                'semanas': list(range(4, 7)),
                'fase': 'intensificacion',
                'volumen_multiplicador': 0.7,
                'intensidad_rpe': (8, 9),
                'rep_range': '1-5'
            },
            {
                'semanas': [7],
                'fase': 'descarga',
                'volumen_multiplicador': 0.5,
                'intensidad_rpe': (6, 7),
                'rep_range': '3-6'
            }
        ] * 7  # Repetir 7 veces para el año

    def _periodizacion_general(self) -> List[Dict[str, Any]]:
        """Periodización general para objetivos mixtos"""
        return [
            {
                'semanas': list(range(1, 6)),
                'fase': 'acumulacion',
                'volumen_multiplicador': 1.0,
                'intensidad_rpe': (7, 8),
                'rep_range': '6-12'
            },
            {
                'semanas': [6],
                'fase': 'descarga',
                'volumen_multiplicador': 0.7,
                'intensidad_rpe': (6, 7),
                'rep_range': '8-12'
            }
        ] * 8  # Repetir 8 veces para el año

    def _crear_plan_semanal_base(self, volumen_base: Dict[str, int]) -> Dict[str, Any]:
        """
        MODIFICADO: Ahora solo prepara la distribución de volumen y la frecuencia.
        La selección de ejercicios se hará dinámicamente por bloque.
        """
        distribucion_semanal = self._distribuir_volumen_semanal(volumen_base)

        return {
            'distribucion': distribucion_semanal,
            'frecuencia_grupos': self._calcular_frecuencia_grupos()
        }

    def _distribuir_volumen_semanal(self, volumen_base: Dict[str, int]) -> Dict[str, Dict[str, int]]:
        """
        Distribuye el volumen semanal entre los días disponibles.
        VERSIÓN FINAL Y DEFINITIVA que maneja 3, 4 y 5 días.
        """
        dias_entreno = [f'dia_{i + 1}' for i in range(self.dias_disponibles)]
        distribucion = {dia: {} for dia in dias_entreno}

        # --- INICIO DE LA CORRECCIÓN ---
        # Define la estructura de entrenamiento (Push/Pull/Legs, Upper/Lower, etc.)
        if self.dias_disponibles == 3:
            # Push/Pull/Legs
            grupos_por_dia = {
                'dia_1': ['pecho', 'hombros', 'triceps'],
                'dia_2': ['espalda', 'biceps'],
                'dia_3': ['cuadriceps', 'isquios', 'gluteos', 'gemelos']
            }
        elif self.dias_disponibles == 5:
            # Body Part Split para 5 días
            grupos_por_dia = {
                'dia_1': ['pecho', 'triceps'],
                'dia_2': ['espalda', 'biceps'],
                'dia_3': ['cuadriceps', 'gemelos'],
                'dia_4': ['hombros', 'trapecios'],
                'dia_5': ['isquios', 'gluteos', 'core']
            }
        else:  # Default para 4 días (Upper/Lower)
            grupos_por_dia = {
                'dia_1': ['pecho', 'hombros', 'triceps'],
                'dia_2': ['cuadriceps', 'isquios', 'gluteos'],
                'dia_3': ['espalda', 'biceps'],
                'dia_4': ['cuadriceps', 'isquios', 'gluteos', 'gemelos']
            }

        # Asegurarse de que solo usamos los días disponibles
        grupos_por_dia = {k: v for k, v in grupos_por_dia.items() if k in dias_entreno}
        # --- FIN DE LA CORRECCIÓN ---

        # Itera sobre cada grupo muscular para distribuir su volumen total
        for grupo, volumen_total_grupo in volumen_base.items():
            dias_para_este_grupo = [dia for dia, grupos in grupos_por_dia.items() if grupo in grupos]
            if not dias_para_este_grupo:
                continue

            series_base_por_dia = volumen_total_grupo // len(dias_para_este_grupo)
            series_extra = volumen_total_grupo % len(dias_para_este_grupo)

            for i, dia in enumerate(dias_para_este_grupo):
                series_asignadas = series_base_por_dia
                if i < series_extra:
                    series_asignadas += 1

                if series_asignadas > 0:
                    distribucion[dia][grupo] = distribucion[dia].get(grupo, 0) + series_asignadas

        return distribucion

    def _calcular_frecuencia_grupos(self) -> Dict[str, int]:
        """Calcula la frecuencia de entrenamiento por grupo muscular"""
        frecuencias_base = {
            'pecho': 2, 'espalda': 2, 'hombros': 2,
            'biceps': 2, 'triceps': 2, 'cuadriceps': 2,
            'isquios': 2, 'gluteos': 2, 'gemelos': 2
        }

        # Ajustar según días disponibles
        if self.dias_disponibles >= 5:
            # Aumentar frecuencia para grupos pequeños
            frecuencias_base.update({
                'biceps': 3, 'triceps': 3, 'hombros': 3
            })

        return frecuencias_base

    # en analytics/planificador_helms_completo.py

    def _aplicar_periodizacion(self, plan_semanal_base: Dict[str, Any], periodizacion: List[Dict[str, Any]]) -> Dict[
        str, Any]:
        """
        Aplica la periodización al plan semanal base.
        VERSIÓN FINAL Y DEFINITIVA que itera correctamente sobre los bloques.
        """
        plan_anual = {}
        semana_global_contador = 1

        # El número de ciclos completos que haremos en el año (ej: 6 ciclos de 8 semanas)
        num_ciclos_anuales = 52 // sum(len(b['semanas']) for b in periodizacion)

        # Iteramos sobre el número de ciclos
        for ciclo in range(num_ciclos_anuales + 1):
            # Dentro de cada ciclo, iteramos sobre los bloques de la periodización (Acumulación, Intensificación, etc.)
            for bloque in periodizacion:
                # Iteramos sobre las semanas relativas de ese bloque (ej: 1, 2, 3, 4)
                for _ in bloque['semanas']:
                    if semana_global_contador > 52:
                        break

                    # Generamos la semana específica usando los parámetros del bloque actual
                    plan_de_la_semana = self._generar_semana_especifica(
                        plan_semanal_base,
                        bloque,  # Pasamos el bloque correcto (Acumulación, Intensificación, etc.)
                        semana_global_contador
                    )

                    plan_anual[f'semana_{semana_global_contador}'] = plan_de_la_semana
                    semana_global_contador += 1

                if semana_global_contador > 52:
                    break
            if semana_global_contador > 52:
                break

        return plan_anual

    # en analytics/planificador_helms_completo.py

    def _generar_semana_especifica(self, plan_base: Dict[str, Any], bloque: Dict[str, Any], numero_bloque: int) -> Dict[
        str, Any]:
        """
        MODIFICADO: Ahora llama al selector de ejercicios dinámico.
        """
        ejercicios_semana = {}

        # --- LLAMADA DINÁMICA A LA SELECCIÓN DE EJERCICIOS ---
        # Se obtienen ejercicios diferentes para cada bloque
        ejercicios_del_bloque = self._seleccionar_ejercicios_para_bloque(numero_bloque)

        for dia, grupos_del_dia in plan_base['distribucion'].items():
            ejercicios_dia = []
            for grupo, volumen_del_grupo in grupos_del_dia.items():
                # Usamos la lista de ejercicios recién generada para este bloque
                nombres_ejercicios_grupo = ejercicios_del_bloque.get(grupo, [])
                if not nombres_ejercicios_grupo: continue

                volumen_ajustado = int(volumen_del_grupo * bloque['volumen_multiplicador'])
                series_por_ejercicio = max(1, volumen_ajustado // len(nombres_ejercicios_grupo))
                series_por_ejercicio = min(series_por_ejercicio, 6)

                for nombre_ejercicio in nombres_ejercicios_grupo:
                    # ... (el resto de la lógica para calcular peso, tempo, etc., se mantiene igual)
                    rpe_objetivo = bloque['intensidad_rpe'][0]
                    peso_calculado = self._calcular_peso_trabajo(nombre_ejercicio, bloque['rep_range'], rpe_objetivo)
                    tempo_calculado = self._determinar_tempo(bloque['fase'])
                    descanso_calculado = self._calcular_descanso(nombre_ejercicio, rpe_objetivo)

                    ejercicios_dia.append({
                        'nombre': nombre_ejercicio,
                        'grupo_muscular': grupo,
                        'series': series_por_ejercicio,
                        'repeticiones': bloque['rep_range'],
                        'peso_kg': peso_calculado,
                        'rpe_objetivo': rpe_objetivo,
                        'tempo': tempo_calculado,
                        'descanso_minutos': descanso_calculado
                    })
            if ejercicios_dia:
                ejercicios_semana[dia] = ejercicios_dia
        return ejercicios_semana

    def _calcular_descanso(self, ejercicio: str, rpe: int) -> int:
        """Calcula tiempo de descanso según ejercicio y RPE"""
        ejercicios_principales = ['sentadilla', 'peso_muerto', 'press_banca', 'press_militar']

        if any(principal in ejercicio for principal in ejercicios_principales):
            return 4 if rpe >= 8 else 3  # 3-4 minutos para principales
        else:
            return 2 if rpe >= 8 else 1  # 1-2 minutos para auxiliares

    def _seleccionar_ejercicios_para_bloque(self, numero_bloque: int) -> Dict[str, List[str]]:
        """
        Selecciona un conjunto de ejercicios para un bloque específico, introduciendo variación.
        El número del bloque se usa para rotar los ejercicios.
        """
        ejercicios_seleccionados = {}

        for grupo, tipos in self.EJERCICIOS_DATABASE.items():
            seleccion_grupo = []

            # 1. Seleccionar un ejercicio compuesto principal
            compuestos_principales = tipos.get('compuesto_principal', [])
            if compuestos_principales:
                # Rotamos el ejercicio principal usando el número del bloque
                # El operador módulo (%) asegura que el índice siempre sea válido
                indice = (numero_bloque - 1) % len(compuestos_principales)
                seleccion_grupo.append(compuestos_principales[indice])

            # 2. Seleccionar un ejercicio compuesto secundario o de aislamiento
            compuestos_secundarios = tipos.get('compuesto_secundario', [])
            aislamientos = tipos.get('aislamiento', [])

            opciones_adicionales = compuestos_secundarios + aislamientos
            if opciones_adicionales:
                # Rotamos de la misma forma para el segundo ejercicio
                indice = (numero_bloque - 1) % len(opciones_adicionales)
                ejercicio_adicional = opciones_adicionales[indice]
                # Evitar duplicados si un ejercicio está en varias listas
                if ejercicio_adicional not in seleccion_grupo:
                    seleccion_grupo.append(ejercicio_adicional)

            # Filtrar por preferencias del cliente (evitar ejercicios)
            seleccion_final = [ej for ej in seleccion_grupo if ej not in self.perfil.ejercicios_evitar]

            ejercicios_seleccionados[grupo] = seleccion_final[:2]  # Nos aseguramos de tener máximo 2

        return ejercicios_seleccionados

    def _determinar_tempo(self, objetivo: str) -> str:
        """Determina el tempo según el objetivo"""
        tempos = {
            'hipertrofia': '2-0-X-0',
            'fuerza': '1-0-X-0',
            'potencia': '1-0-X-0',
            'resistencia': '1-0-1-0'
        }
        return tempos.get(objetivo, '2-0-X-0')


class CalculadoraVolumen:
    """Calculadora de volumen según principios de Helms"""

    @staticmethod
    def calcular_volumen_mantenimiento(grupo_muscular: str, experiencia: str) -> int:
        """Calcula volumen mínimo de mantenimiento"""
        volumenes_mantenimiento = {
            'principiante': {'pecho': 4, 'espalda': 6, 'piernas': 6},
            'intermedio': {'pecho': 6, 'espalda': 8, 'piernas': 8},
            'avanzado': {'pecho': 8, 'espalda': 10, 'piernas': 10}
        }

        categoria = 'piernas' if grupo_muscular in ['cuadriceps', 'isquios', 'gluteos'] else grupo_muscular
        return volumenes_mantenimiento.get(experiencia, {}).get(categoria, 6)

    @staticmethod
    def calcular_volumen_maximo_adaptativo(grupo_muscular: str, experiencia: str) -> int:
        """Calcula volumen máximo adaptativo según Helms"""
        volumenes_maximos = {
            'principiante': {'pecho': 12, 'espalda': 14, 'piernas': 16},
            'intermedio': {'pecho': 18, 'espalda': 20, 'piernas': 20},
            'avanzado': {'pecho': 22, 'espalda': 25, 'piernas': 25}
        }

        categoria = 'piernas' if grupo_muscular in ['cuadriceps', 'isquios', 'gluteos'] else grupo_muscular
        return volumenes_maximos.get(experiencia, {}).get(categoria, 20)


class OptimizadorRecuperacion:
    """Optimizador de recuperación basado en factores de Helms"""

    def __init__(self, nivel_estres: int, calidad_sueño: int, nivel_energia: int):
        self.nivel_estres = nivel_estres
        self.calidad_sueño = calidad_sueño
        self.nivel_energia = nivel_energia

    def calcular_factor_recuperacion(self) -> float:
        """Calcula factor de recuperación (0.7 - 1.3)"""
        # Normalizar valores a escala 0-1
        estres_norm = (10 - self.nivel_estres) / 10  # Invertir: menos estrés = mejor
        sueño_norm = self.calidad_sueño / 10
        energia_norm = self.nivel_energia / 10

        # Promedio ponderado
        factor_base = (estres_norm * 0.3 + sueño_norm * 0.4 + energia_norm * 0.3)

        # Escalar a rango 0.7 - 1.3
        return 0.7 + (factor_base * 0.6)

    def necesita_descarga(self) -> bool:
        """Determina si se necesita una semana de descarga"""
        factor = self.calcular_factor_recuperacion()
        return factor < 0.85


class SelectorEjercicios:
    """Selector inteligente de ejercicios según principios de Helms"""

    @classmethod
    def seleccionar_ejercicios_optimos(cls, grupo_muscular: str, nivel_experiencia: str,
                                       preferidos: List[str] = None, evitados: List[str] = None) -> List[str]:
        """Selecciona ejercicios óptimos para un grupo muscular"""
        ejercicios_grupo = cls.EJERCICIOS_DATABASE.get(grupo_muscular, {})

        if not ejercicios_grupo:
            return []

        # Filtrar por experiencia
        ejercicios_filtrados = {}
        for ejercicio, datos in ejercicios_grupo.items():
            if nivel_experiencia == 'principiante' and datos['dificultad'] == 'alta':
                continue
            ejercicios_filtrados[ejercicio] = datos

        # Aplicar preferencias
        if preferidos:
            preferidos_disponibles = [e for e in preferidos if e in ejercicios_filtrados]
            if preferidos_disponibles:
                return preferidos_disponibles[:2]

        # Evitar ejercicios no deseados
        if evitados:
            ejercicios_filtrados = {e: d for e, d in ejercicios_filtrados.items() if e not in evitados}

        # Seleccionar por diversidad de patrones
        patrones_usados = set()
        ejercicios_seleccionados = []

        for ejercicio, datos in ejercicios_filtrados.items():
            if datos['patron'] not in patrones_usados and len(ejercicios_seleccionados) < 3:
                ejercicios_seleccionados.append(ejercicio)
                patrones_usados.add(datos['patron'])

        return ejercicios_seleccionados[:2]  # Máximo 2 ejercicios por grupo


# Funciones de utilidad para compatibilidad
def generar_plan_helms(cliente_data: Dict[str, Any]) -> Dict[str, Any]:
    """Función de conveniencia para generar plan Helms"""
    planificador = PlanificadorHelms(cliente_data)
    return planificador.generar_plan_anual()


def calcular_volumen_optimo(grupo_muscular: str, experiencia: str, objetivo: str) -> int:
    """Calcula volumen óptimo para un grupo muscular"""
    calculadora = CalculadoraVolumen()
    volumen_base = calculadora.calcular_volumen_mantenimiento(grupo_muscular, experiencia)
    volumen_maximo = calculadora.calcular_volumen_maximo_adaptativo(grupo_muscular, experiencia)

    # Ajustar según objetivo
    if objetivo == 'hipertrofia':
        return int(volumen_base * 1.5)
    elif objetivo == 'fuerza':
        return int(volumen_base * 1.2)
    else:
        return volumen_base


def optimizar_recuperacion(nivel_estres: int, calidad_sueño: int, nivel_energia: int) -> Dict[str, Any]:
    """Optimiza parámetros de recuperación"""
    optimizador = OptimizadorRecuperacion(nivel_estres, calidad_sueño, nivel_energia)

    return {
        'factor_recuperacion': optimizador.calcular_factor_recuperacion(),
        'necesita_descarga': optimizador.necesita_descarga(),
        'recomendaciones': [
            'Priorizar sueño de calidad' if calidad_sueño < 7 else None,
            'Reducir estrés mediante técnicas de relajación' if nivel_estres > 7 else None,
            'Considerar semana de descarga' if optimizador.necesita_descarga() else None
        ]
    }


def seleccionar_ejercicios_inteligente(grupo_muscular: str, nivel_experiencia: str,
                                       preferidos: List[str] = None, evitados: List[str] = None) -> List[str]:
    """Selección inteligente de ejercicios"""
    return SelectorEjercicios.seleccionar_ejercicios_optimos(
        grupo_muscular, nivel_experiencia, preferidos, evitados
    )


class PerfilCliente:
    """Perfil completo del cliente para el sistema Helms"""

    def __init__(self, cliente_data: Dict[str, Any]):
        # Datos básicos del cliente
        self.id = cliente_data.get('id')
        self.nombre = cliente_data.get('nombre', '')
        self.edad = cliente_data.get('edad', 25)
        self.peso = cliente_data.get('peso', 70.0)
        self.altura = cliente_data.get('altura', 170.0)
        self.genero = cliente_data.get('genero', 'masculino')

        # Experiencia y objetivos
        self.experiencia_años = cliente_data.get('experiencia_años', 0)
        self.objetivo_principal = cliente_data.get('objetivo_principal', 'hipertrofia')
        self.objetivos_secundarios = cliente_data.get('objetivos_secundarios', [])

        # Disponibilidad
        self.dias_disponibles = cliente_data.get('dias_disponibles', 3)
        self.tiempo_por_sesion = cliente_data.get('tiempo_por_sesion', 60)
        self.horarios_preferidos = cliente_data.get('horarios_preferidos', [])

        # Preferencias de ejercicios
        self.ejercicios_preferidos = cliente_data.get('ejercicios_preferidos', [])
        self.ejercicios_evitar = cliente_data.get('ejercicios_evitar', [])
        self.equipamiento_disponible = cliente_data.get('equipamiento_disponible', [])
        self.limitaciones_fisicas = cliente_data.get('limitaciones_fisicas', [])

        # Factores de recuperación (Helms específicos)
        self.nivel_estres = cliente_data.get('nivel_estres', 5)  # 1-10
        self.calidad_sueño = cliente_data.get('calidad_sueño', 7)  # 1-10
        self.nivel_energia = cliente_data.get('nivel_energia', 7)  # 1-10
        self.nutricion_calidad = cliente_data.get('nutricion_calidad', 7)  # 1-10

        # Historial de entrenamiento
        self.historial_volumen = cliente_data.get('historial_volumen', {})
        self.historial_intensidad = cliente_data.get('historial_intensidad', {})
        self.lesiones_previas = cliente_data.get('lesiones_previas', [])

        # Métricas de rendimiento
        self.maximos_actuales = cliente_data.get('maximos_actuales', {})
        self.progreso_historico = cliente_data.get('progreso_historico', {})

        # Preferencias del sistema Helms
        self.precision_rpe = cliente_data.get('precision_rpe', 'principiante')  # principiante, intermedio, avanzado
        self.preferencia_tempo = cliente_data.get('preferencia_tempo', 'moderado')  # lento, moderado, rapido
        self.nivel_educacion_deseado = cliente_data.get('nivel_educacion_deseado', 'medio')  # bajo, medio, alto

        # Estado de migración
        self.migrado_a_helms = cliente_data.get('migrado_a_helms', False)
        self.fecha_migracion_helms = cliente_data.get('fecha_migracion_helms')
        self.version_helms = cliente_data.get('version_helms', '1.0')

    def calcular_nivel_experiencia(self) -> str:
        """Calcula el nivel de experiencia basado en años de entrenamiento"""
        if self.experiencia_años < 1:
            return 'principiante'
        elif self.experiencia_años < 3:
            return 'intermedio'
        else:
            return 'avanzado'

    def calcular_factor_recuperacion(self) -> float:
        """Calcula factor de recuperación global (0.7 - 1.3)"""
        # Normalizar valores a escala 0-1
        estres_norm = (10 - self.nivel_estres) / 10  # Invertir: menos estrés = mejor
        sueño_norm = self.calidad_sueño / 10
        energia_norm = self.nivel_energia / 10
        nutricion_norm = self.nutricion_calidad / 10

        # Promedio ponderado
        factor_base = (estres_norm * 0.25 + sueño_norm * 0.35 +
                       energia_norm * 0.25 + nutricion_norm * 0.15)

        # Escalar a rango 0.7 - 1.3
        return 0.7 + (factor_base * 0.6)

    def necesita_descarga(self) -> bool:
        """Determina si necesita semana de descarga"""
        factor_recuperacion = self.calcular_factor_recuperacion()
        return factor_recuperacion < 0.85

    def obtener_volumen_objetivo(self, grupo_muscular: str) -> int:
        """Obtiene volumen objetivo para un grupo muscular específico"""
        nivel = self.calcular_nivel_experiencia()
        factor_recuperacion = self.calcular_factor_recuperacion()

        # Volúmenes base por nivel
        volumenes_base = {
            'principiante': {
                'pecho': 10, 'espalda': 12, 'hombros': 8, 'biceps': 6,
                'triceps': 6, 'cuadriceps': 12, 'isquios': 8, 'gluteos': 8, 'gemelos': 6
            },
            'intermedio': {
                'pecho': 14, 'espalda': 16, 'hombros': 12, 'biceps': 8,
                'triceps': 8, 'cuadriceps': 16, 'isquios': 10, 'gluteos': 12, 'gemelos': 8
            },
            'avanzado': {
                'pecho': 18, 'espalda': 20, 'hombros': 16, 'biceps': 12,
                'triceps': 12, 'cuadriceps': 20, 'isquios': 14, 'gluteos': 16, 'gemelos': 12
            }
        }

        volumen_base = volumenes_base[nivel].get(grupo_muscular, 10)

        # Ajustar por factor de recuperación
        volumen_ajustado = int(volumen_base * factor_recuperacion)

        # Ajustar por objetivo
        if self.objetivo_principal == 'hipertrofia':
            volumen_ajustado = int(volumen_ajustado * 1.1)
        elif self.objetivo_principal == 'fuerza':
            volumen_ajustado = int(volumen_ajustado * 0.9)
        elif self.objetivo_principal == 'resistencia':
            volumen_ajustado = int(volumen_ajustado * 1.2)

        return max(volumen_ajustado, 4)  # Mínimo 4 series por semana

    def obtener_intensidad_objetivo(self) -> tuple:
        """Obtiene rango de intensidad RPE objetivo"""
        nivel = self.calcular_nivel_experiencia()

        if nivel == 'principiante':
            return (6, 8)  # RPE 6-8
        elif nivel == 'intermedio':
            return (7, 9)  # RPE 7-9
        else:
            return (7, 9)  # RPE 7-9 (avanzados también, pero con mejor precisión)

    def obtener_frecuencia_objetivo(self, grupo_muscular: str) -> int:
        """Obtiene frecuencia de entrenamiento objetivo para un grupo"""
        # Frecuencia base según días disponibles
        if self.dias_disponibles <= 3:
            frecuencia_base = 1
        elif self.dias_disponibles <= 4:
            frecuencia_base = 2
        else:
            frecuencia_base = 2

        # Ajustar por grupo muscular
        grupos_grandes = ['pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos']
        if grupo_muscular in grupos_grandes:
            return frecuencia_base
        else:
            return min(frecuencia_base + 1, 3)  # Grupos pequeños pueden ir más frecuente

    def es_compatible_ejercicio(self, ejercicio: str) -> bool:
        """Verifica si un ejercicio es compatible con el perfil del cliente"""
        # Verificar ejercicios a evitar
        if ejercicio in self.ejercicios_evitar:
            return False

        # Verificar limitaciones físicas
        ejercicios_problematicos = {
            'lesion_hombro': ['press_militar', 'elevaciones_laterales', 'dominadas'],
            'lesion_rodilla': ['sentadilla', 'zancadas', 'extension_cuadriceps'],
            'lesion_espalda_baja': ['peso_muerto', 'sentadilla', 'remo_con_barra']
        }

        for limitacion in self.limitaciones_fisicas:
            if limitacion in ejercicios_problematicos:
                if ejercicio in ejercicios_problematicos[limitacion]:
                    return False

        return True

    def obtener_tempo_preferido(self, tipo_ejercicio: str = 'general') -> str:
        """Obtiene tempo preferido según el tipo de ejercicio y objetivo"""
        if self.objetivo_principal == 'hipertrofia':
            return '3-0-X-1'  # Tempo más lento para hipertrofia
        elif self.objetivo_principal == 'fuerza':
            return '2-0-X-0'  # Tempo moderado para fuerza
        elif self.objetivo_principal == 'potencia':
            return '1-0-X-0'  # Tempo explosivo para potencia
        else:
            return '2-0-X-0'  # Tempo estándar

    def obtener_descanso_preferido(self, tipo_ejercicio: str, rpe_objetivo: int) -> int:
        """Obtiene tiempo de descanso preferido en minutos"""
        # Base según tipo de ejercicio
        ejercicios_principales = ['sentadilla', 'peso_muerto', 'press_banca', 'press_militar']

        if any(principal in tipo_ejercicio for principal in ejercicios_principales):
            descanso_base = 4  # 4 minutos para principales
        else:
            descanso_base = 2  # 2 minutos para auxiliares

        # Ajustar por RPE
        if rpe_objetivo >= 9:
            descanso_base += 1
        elif rpe_objetivo <= 6:
            descanso_base -= 1

        # Ajustar por nivel de experiencia
        if self.calcular_nivel_experiencia() == 'principiante':
            descanso_base += 1  # Principiantes necesitan más descanso

        return max(descanso_base, 1)  # Mínimo 1 minuto

    def generar_resumen_perfil(self) -> Dict[str, Any]:
        """Genera resumen completo del perfil para logging/debugging"""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'nivel_experiencia': self.calcular_nivel_experiencia(),
            'objetivo_principal': self.objetivo_principal,
            'dias_disponibles': self.dias_disponibles,
            'factor_recuperacion': round(self.calcular_factor_recuperacion(), 2),
            'necesita_descarga': self.necesita_descarga(),
            'intensidad_objetivo': self.obtener_intensidad_objetivo(),
            'migrado_a_helms': self.migrado_a_helms,
            'limitaciones': len(self.limitaciones_fisicas),
            'ejercicios_preferidos': len(self.ejercicios_preferidos),
            'ejercicios_evitar': len(self.ejercicios_evitar)
        }

    def actualizar_desde_feedback(self, feedback_data: Dict[str, Any]):
        """Actualiza el perfil basándose en feedback del usuario"""
        # Actualizar factores de recuperación si se proporcionan
        if 'nivel_estres' in feedback_data:
            self.nivel_estres = max(1, min(10, feedback_data['nivel_estres']))

        if 'calidad_sueño' in feedback_data:
            self.calidad_sueño = max(1, min(10, feedback_data['calidad_sueño']))

        if 'nivel_energia' in feedback_data:
            self.nivel_energia = max(1, min(10, feedback_data['nivel_energia']))

        # Actualizar preferencias de ejercicios
        if 'nuevos_ejercicios_preferidos' in feedback_data:
            for ejercicio in feedback_data['nuevos_ejercicios_preferidos']:
                if ejercicio not in self.ejercicios_preferidos:
                    self.ejercicios_preferidos.append(ejercicio)

        if 'nuevos_ejercicios_evitar' in feedback_data:
            for ejercicio in feedback_data['nuevos_ejercicios_evitar']:
                if ejercicio not in self.ejercicios_evitar:
                    self.ejercicios_evitar.append(ejercicio)

        # Actualizar disponibilidad si cambió
        if 'dias_disponibles' in feedback_data:
            self.dias_disponibles = max(1, min(7, feedback_data['dias_disponibles']))

        if 'tiempo_por_sesion' in feedback_data:
            self.tiempo_por_sesion = max(30, min(180, feedback_data['tiempo_por_sesion']))

    def __str__(self):
        return f"PerfilCliente({self.nombre}, {self.calcular_nivel_experiencia()}, {self.objetivo_principal})"

    def __repr__(self):
        return self.__str__()


def crear_perfil_desde_cliente(cliente_django) -> 'PerfilCliente':
    """
    Convierte un modelo Cliente de Django a PerfilCliente para Helms
    """
    # Mapear nivel de experiencia
    experiencia_años = getattr(cliente_django, 'experiencia_años', 1)

    # Mapear objetivo
    objetivo_map = {
        'hipertrofia': ObjetivoEntrenamiento.HIPERTROFIA,
        'fuerza': ObjetivoEntrenamiento.FUERZA,
        'potencia': ObjetivoEntrenamiento.POTENCIA,
        'resistencia': ObjetivoEntrenamiento.RESISTENCIA,
        'perdida_grasa': ObjetivoEntrenamiento.PERDIDA_GRASA,
        'salud_general': ObjetivoEntrenamiento.SALUD_GENERAL,
        'rehabilitacion': ObjetivoEntrenamiento.REHABILITACION,
        'rendimiento_deportivo': ObjetivoEntrenamiento.RENDIMIENTO_DEPORTIVO
    }
    objetivo_str = getattr(cliente_django, 'objetivo_principal', 'hipertrofia')
    if hasattr(objetivo_str, 'lower'):
        objetivo_str = objetivo_str.lower()
    objetivo = objetivo_map.get(objetivo_str, ObjetivoEntrenamiento.HIPERTROFIA)

    # Crear el diccionario de datos para el PerfilCliente
    cliente_data = {
        'id': cliente_django.id,
        'nombre': getattr(cliente_django, 'nombre', ''),
        'experiencia_años': experiencia_años,
        'objetivo_principal': objetivo,
        'dias_disponibles': getattr(cliente_django, 'dias_disponibles', 4),
        'tiempo_por_sesion': getattr(cliente_django, 'tiempo_por_sesion', 90),
        'ejercicios_preferidos': getattr(cliente_django, 'ejercicios_preferidos', []),
        'ejercicios_evitar': getattr(cliente_django, 'ejercicios_evitar', []),
        'nivel_estres': getattr(cliente_django, 'nivel_estres', 5),
        'calidad_sueño': getattr(cliente_django, 'calidad_sueño', 7),
        'nivel_energia': getattr(cliente_django, 'nivel_energia', 7),
        'historial_volumen': getattr(cliente_django, 'historial_volumen', {}),
        'limitaciones_fisicas': getattr(cliente_django, 'limitaciones_fisicas', []),
        'lesiones_previas': getattr(cliente_django, 'lesiones_previas', []),
        'maximos_actuales': getattr(cliente_django, 'one_rm_data', {})
    }

    # La clase PerfilCliente espera un único diccionario llamado 'cliente_data'
    return PerfilCliente(cliente_data)


from enum import Enum


class NivelExperiencia(Enum):
    """Enumeración para niveles de experiencia en entrenamiento"""
    PRINCIPIANTE = "principiante"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"
    ELITE = "elite"

    @classmethod
    def desde_años(cls, años: int):
        """Determina nivel de experiencia basado en años de entrenamiento"""
        if años < 1:
            return cls.PRINCIPIANTE
        elif años < 3:
            return cls.INTERMEDIO
        elif años < 6:
            return cls.AVANZADO
        else:
            return cls.ELITE

    def obtener_volumen_multiplicador(self) -> float:
        """Obtiene multiplicador de volumen según nivel"""
        multiplicadores = {
            self.PRINCIPIANTE: 0.8,
            self.INTERMEDIO: 1.0,
            self.AVANZADO: 1.2,
            self.ELITE: 1.4
        }
        return multiplicadores[self]

    def obtener_complejidad_maxima(self) -> int:
        """Obtiene complejidad máxima de ejercicios (1-5)"""
        complejidades = {
            self.PRINCIPIANTE: 2,
            self.INTERMEDIO: 3,
            self.AVANZADO: 4,
            self.ELITE: 5
        }
        return complejidades[self]

    def obtener_rpe_rango(self) -> tuple:
        """Obtiene rango de RPE recomendado"""
        rangos = {
            self.PRINCIPIANTE: (6, 8),
            self.INTERMEDIO: (7, 9),
            self.AVANZADO: (7, 9),
            self.ELITE: (8, 10)
        }
        return rangos[self]

    def __str__(self):
        return self.value.title()


class ObjetivoEntrenamiento(Enum):
    """Enumeración para objetivos de entrenamiento"""
    HIPERTROFIA = "hipertrofia"
    FUERZA = "fuerza"
    POTENCIA = "potencia"
    RESISTENCIA = "resistencia"
    PERDIDA_GRASA = "perdida_grasa"
    SALUD_GENERAL = "salud_general"
    REHABILITACION = "rehabilitacion"
    RENDIMIENTO_DEPORTIVO = "rendimiento_deportivo"

    def obtener_rango_repeticiones(self) -> str:
        """Obtiene rango de repeticiones típico para el objetivo"""
        rangos = {
            self.HIPERTROFIA: "8-12",
            self.FUERZA: "1-5",
            self.POTENCIA: "3-6",
            self.RESISTENCIA: "15-25",
            self.PERDIDA_GRASA: "10-15",
            self.SALUD_GENERAL: "8-15",
            self.REHABILITACION: "12-20",
            self.RENDIMIENTO_DEPORTIVO: "6-10"
        }
        return rangos[self]

    def obtener_intensidad_promedio(self) -> float:
        """Obtiene intensidad promedio (%1RM) para el objetivo"""
        intensidades = {
            self.HIPERTROFIA: 75.0,
            self.FUERZA: 85.0,
            self.POTENCIA: 80.0,
            self.RESISTENCIA: 60.0,
            self.PERDIDA_GRASA: 70.0,
            self.SALUD_GENERAL: 65.0,
            self.REHABILITACION: 50.0,
            self.RENDIMIENTO_DEPORTIVO: 80.0
        }
        return intensidades[self]

    def obtener_descanso_recomendado(self) -> int:
        """Obtiene tiempo de descanso recomendado en minutos"""
        descansos = {
            self.HIPERTROFIA: 2,
            self.FUERZA: 4,
            self.POTENCIA: 3,
            self.RESISTENCIA: 1,
            self.PERDIDA_GRASA: 1,
            self.SALUD_GENERAL: 2,
            self.REHABILITACION: 2,
            self.RENDIMIENTO_DEPORTIVO: 3
        }
        return descansos[self]

    def obtener_volumen_multiplicador(self) -> float:
        """Obtiene multiplicador de volumen según objetivo"""
        multiplicadores = {
            self.HIPERTROFIA: 1.2,
            self.FUERZA: 0.8,
            self.POTENCIA: 0.9,
            self.RESISTENCIA: 1.4,
            self.PERDIDA_GRASA: 1.1,
            self.SALUD_GENERAL: 1.0,
            self.REHABILITACION: 0.7,
            self.RENDIMIENTO_DEPORTIVO: 1.0
        }
        return multiplicadores[self]

    def obtener_frecuencia_recomendada(self) -> int:
        """Obtiene frecuencia semanal recomendada por grupo muscular"""
        frecuencias = {
            self.HIPERTROFIA: 2,
            self.FUERZA: 3,
            self.POTENCIA: 3,
            self.RESISTENCIA: 2,
            self.PERDIDA_GRASA: 2,
            self.SALUD_GENERAL: 2,
            self.REHABILITACION: 3,
            self.RENDIMIENTO_DEPORTIVO: 2
        }
        return frecuencias[self]

    def obtener_tempo_recomendado(self) -> str:
        """Obtiene tempo recomendado para el objetivo"""
        tempos = {
            self.HIPERTROFIA: "3-0-X-1",
            self.FUERZA: "2-0-X-0",
            self.POTENCIA: "1-0-X-0",
            self.RESISTENCIA: "2-0-2-0",
            self.PERDIDA_GRASA: "2-0-X-0",
            self.SALUD_GENERAL: "2-0-X-0",
            self.REHABILITACION: "3-1-3-1",
            self.RENDIMIENTO_DEPORTIVO: "2-0-X-0"
        }
        return tempos[self]

    def es_compatible_con_nivel(self, nivel: NivelExperiencia) -> bool:
        """Verifica si el objetivo es apropiado para el nivel de experiencia"""
        compatibilidades = {
            self.HIPERTROFIA: [NivelExperiencia.PRINCIPIANTE, NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO,
                               NivelExperiencia.ELITE],
            self.FUERZA: [NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO, NivelExperiencia.ELITE],
            self.POTENCIA: [NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO, NivelExperiencia.ELITE],
            self.RESISTENCIA: [NivelExperiencia.PRINCIPIANTE, NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO,
                               NivelExperiencia.ELITE],
            self.PERDIDA_GRASA: [NivelExperiencia.PRINCIPIANTE, NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO,
                                 NivelExperiencia.ELITE],
            self.SALUD_GENERAL: [NivelExperiencia.PRINCIPIANTE, NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO,
                                 NivelExperiencia.ELITE],
            self.REHABILITACION: [NivelExperiencia.PRINCIPIANTE, NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO,
                                  NivelExperiencia.ELITE],
            self.RENDIMIENTO_DEPORTIVO: [NivelExperiencia.INTERMEDIO, NivelExperiencia.AVANZADO, NivelExperiencia.ELITE]
        }
        return nivel in compatibilidades[self]

    def __str__(self):
        return self.value.replace('_', ' ').title()


class GrupoMuscular(Enum):
    """Enumeración para grupos musculares"""
    PECHO = "pecho"
    ESPALDA = "espalda"
    HOMBROS = "hombros"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    CUADRICEPS = "cuadriceps"
    ISQUIOS = "isquios"
    GLUTEOS = "gluteos"
    GEMELOS = "gemelos"
    CORE = "core"
    ANTEBRAZOS = "antebrazos"
    TRAPECIOS = "trapecios"

    def obtener_volumen_base(self, nivel: NivelExperiencia) -> int:
        """Obtiene volumen base semanal según nivel de experiencia"""
        volumenes = {
            NivelExperiencia.PRINCIPIANTE: {
                self.PECHO: 8, self.ESPALDA: 10, self.HOMBROS: 6, self.BICEPS: 4,
                self.TRICEPS: 4, self.CUADRICEPS: 10, self.ISQUIOS: 6, self.GLUTEOS: 6,
                self.GEMELOS: 4, self.CORE: 6, self.ANTEBRAZOS: 2, self.TRAPECIOS: 2
            },
            NivelExperiencia.INTERMEDIO: {
                self.PECHO: 12, self.ESPALDA: 14, self.HOMBROS: 10, self.BICEPS: 6,
                self.TRICEPS: 6, self.CUADRICEPS: 14, self.ISQUIOS: 8, self.GLUTEOS: 10,
                self.GEMELOS: 6, self.CORE: 8, self.ANTEBRAZOS: 4, self.TRAPECIOS: 4
            },
            NivelExperiencia.AVANZADO: {
                self.PECHO: 16, self.ESPALDA: 18, self.HOMBROS: 14, self.BICEPS: 8,
                self.TRICEPS: 8, self.CUADRICEPS: 18, self.ISQUIOS: 12, self.GLUTEOS: 14,
                self.GEMELOS: 8, self.CORE: 10, self.ANTEBRAZOS: 6, self.TRAPECIOS: 6
            },
            NivelExperiencia.ELITE: {
                self.PECHO: 20, self.ESPALDA: 22, self.HOMBROS: 18, self.BICEPS: 12,
                self.TRICEPS: 12, self.CUADRICEPS: 22, self.ISQUIOS: 16, self.GLUTEOS: 18,
                self.GEMELOS: 12, self.CORE: 14, self.ANTEBRAZOS: 8, self.TRAPECIOS: 8
            }
        }
        return volumenes[nivel][self]

    def obtener_volumen_minimo_mantenimiento(self) -> int:
        """Obtiene volumen mínimo para mantener masa muscular"""
        volumenes_minimos = {
            self.PECHO: 4, self.ESPALDA: 6, self.HOMBROS: 4, self.BICEPS: 2,
            self.TRICEPS: 2, self.CUADRICEPS: 6, self.ISQUIOS: 4, self.GLUTEOS: 4,
            self.GEMELOS: 2, self.CORE: 3, self.ANTEBRAZOS: 1, self.TRAPECIOS: 1
        }
        return volumenes_minimos[self]

    def obtener_volumen_maximo_adaptativo(self, nivel: NivelExperiencia) -> int:
        """Obtiene volumen máximo antes de rendimientos decrecientes"""
        base = self.obtener_volumen_base(nivel)
        multiplicadores = {
            NivelExperiencia.PRINCIPIANTE: 1.5,
            NivelExperiencia.INTERMEDIO: 1.8,
            NivelExperiencia.AVANZADO: 2.2,
            NivelExperiencia.ELITE: 2.5
        }
        return int(base * multiplicadores[nivel])

    def obtener_frecuencia_optima(self, volumen_semanal: int) -> int:
        """Obtiene frecuencia óptima basada en volumen semanal"""
        if volumen_semanal <= 8:
            return 1
        elif volumen_semanal <= 16:
            return 2
        else:
            return 3

    def obtener_ejercicios_principales(self) -> List[str]:
        """Obtiene lista de ejercicios principales para el grupo muscular"""
        ejercicios = {
            self.PECHO: ["press_banca", "press_inclinado", "aperturas", "fondos"],
            self.ESPALDA: ["dominadas", "remo_con_barra", "remo_con_mancuerna", "jalones"],
            self.HOMBROS: ["press_militar", "elevaciones_laterales", "elevaciones_posteriores", "press_arnold"],
            self.BICEPS: ["curl_con_barra", "curl_con_mancuerna", "curl_martillo", "curl_concentrado"],
            self.TRICEPS: ["press_frances", "fondos_triceps", "extension_polea", "patadas_triceps"],
            self.CUADRICEPS: ["sentadilla", "prensa", "zancadas", "extension_cuadriceps"],
            self.ISQUIOS: ["peso_muerto_rumano", "curl_femoral", "peso_muerto_piernas_rigidas", "buenos_dias"],
            self.GLUTEOS: ["hip_thrust", "sentadilla_bulgara", "peso_muerto_sumo", "patadas_gluteo"],
            self.GEMELOS: ["elevaciones_gemelos_parado", "elevaciones_gemelos_sentado", "prensa_gemelos"],
            self.CORE: ["plancha", "crunches", "elevaciones_piernas", "russian_twists"],
            self.ANTEBRAZOS: ["curl_muñecas", "farmer_walks", "grip_squeeze"],
            self.TRAPECIOS: ["encogimientos", "upright_rows", "face_pulls"]
        }
        return ejercicios[self]

    def es_grupo_grande(self) -> bool:
        """Determina si es un grupo muscular grande"""
        grupos_grandes = [self.PECHO, self.ESPALDA, self.CUADRICEPS, self.ISQUIOS, self.GLUTEOS]
        return self in grupos_grandes

    def obtener_grupos_sinergistas(self) -> List['GrupoMuscular']:
        """Obtiene grupos musculares que trabajan sinérgicamente"""
        sinergias = {
            self.PECHO: [self.TRICEPS, self.HOMBROS],
            self.ESPALDA: [self.BICEPS, self.TRAPECIOS],
            self.HOMBROS: [self.TRICEPS, self.TRAPECIOS],
            self.BICEPS: [self.ANTEBRAZOS],
            self.TRICEPS: [self.HOMBROS],
            self.CUADRICEPS: [self.GLUTEOS, self.CORE],
            self.ISQUIOS: [self.GLUTEOS, self.CORE],
            self.GLUTEOS: [self.CUADRICEPS, self.ISQUIOS],
            self.GEMELOS: [],
            self.CORE: [self.CUADRICEPS, self.ISQUIOS, self.GLUTEOS],
            self.ANTEBRAZOS: [self.BICEPS],
            self.TRAPECIOS: [self.ESPALDA, self.HOMBROS]
        }
        return sinergias[self]

    def obtener_grupos_antagonistas(self) -> List['GrupoMuscular']:
        """Obtiene grupos musculares antagonistas"""
        antagonismos = {
            self.PECHO: [self.ESPALDA],
            self.ESPALDA: [self.PECHO],
            self.BICEPS: [self.TRICEPS],
            self.TRICEPS: [self.BICEPS],
            self.CUADRICEPS: [self.ISQUIOS],
            self.ISQUIOS: [self.CUADRICEPS],
            self.HOMBROS: [],
            self.GLUTEOS: [],
            self.GEMELOS: [],
            self.CORE: [],
            self.ANTEBRAZOS: [],
            self.TRAPECIOS: []
        }
        return antagonismos[self]

    def requiere_calentamiento_especifico(self) -> bool:
        """Determina si requiere calentamiento específico"""
        grupos_sensibles = [self.HOMBROS, self.CORE, self.CUADRICEPS, self.ISQUIOS]
        return self in grupos_sensibles

    def obtener_tiempo_recuperacion_horas(self) -> int:
        """Obtiene tiempo de recuperación típico en horas"""
        tiempos = {
            self.PECHO: 48, self.ESPALDA: 48, self.HOMBROS: 36, self.BICEPS: 36,
            self.TRICEPS: 36, self.CUADRICEPS: 72, self.ISQUIOS: 72, self.GLUTEOS: 48,
            self.GEMELOS: 24, self.CORE: 24, self.ANTEBRAZOS: 24, self.TRAPECIOS: 36
        }
        return tiempos[self]

    @classmethod
    def obtener_todos_grupos(cls) -> List['GrupoMuscular']:
        """Obtiene lista de todos los grupos musculares"""
        return list(cls)

    @classmethod
    def obtener_grupos_principales(cls) -> List['GrupoMuscular']:
        """Obtiene solo los grupos musculares principales"""
        return [cls.PECHO, cls.ESPALDA, cls.HOMBROS, cls.BICEPS, cls.TRICEPS,
                cls.CUADRICEPS, cls.ISQUIOS, cls.GLUTEOS]

    def __str__(self):
        return self.value.title()


# Funciones de utilidad para trabajar con las enumeraciones
def obtener_nivel_desde_string(nivel_str: str) -> NivelExperiencia:
    """Convierte string a NivelExperiencia"""
    mapeo = {
        'principiante': NivelExperiencia.PRINCIPIANTE,
        'intermedio': NivelExperiencia.INTERMEDIO,
        'avanzado': NivelExperiencia.AVANZADO,
        'elite': NivelExperiencia.ELITE
    }
    return mapeo.get(nivel_str.lower(), NivelExperiencia.PRINCIPIANTE)


def obtener_objetivo_desde_string(objetivo_str: str) -> ObjetivoEntrenamiento:
    """Convierte string a ObjetivoEntrenamiento"""
    mapeo = {
        'hipertrofia': ObjetivoEntrenamiento.HIPERTROFIA,
        'fuerza': ObjetivoEntrenamiento.FUERZA,
        'potencia': ObjetivoEntrenamiento.POTENCIA,
        'resistencia': ObjetivoEntrenamiento.RESISTENCIA,
        'perdida_grasa': ObjetivoEntrenamiento.PERDIDA_GRASA,
        'perdida grasa': ObjetivoEntrenamiento.PERDIDA_GRASA,
        'salud_general': ObjetivoEntrenamiento.SALUD_GENERAL,
        'salud general': ObjetivoEntrenamiento.SALUD_GENERAL,
        'rehabilitacion': ObjetivoEntrenamiento.REHABILITACION,
        'rehabilitación': ObjetivoEntrenamiento.REHABILITACION,
        'rendimiento_deportivo': ObjetivoEntrenamiento.RENDIMIENTO_DEPORTIVO,
        'rendimiento deportivo': ObjetivoEntrenamiento.RENDIMIENTO_DEPORTIVO
    }
    return mapeo.get(objetivo_str.lower(), ObjetivoEntrenamiento.HIPERTROFIA)


def obtener_grupo_desde_string(grupo_str: str) -> GrupoMuscular:
    """Convierte string a GrupoMuscular"""
    mapeo = {
        'pecho': GrupoMuscular.PECHO,
        'espalda': GrupoMuscular.ESPALDA,
        'hombros': GrupoMuscular.HOMBROS,
        'biceps': GrupoMuscular.BICEPS,
        'bíceps': GrupoMuscular.BICEPS,
        'triceps': GrupoMuscular.TRICEPS,
        'tríceps': GrupoMuscular.TRICEPS,
        'cuadriceps': GrupoMuscular.CUADRICEPS,
        'cuádriceps': GrupoMuscular.CUADRICEPS,
        'isquios': GrupoMuscular.ISQUIOS,
        'isquiotibiales': GrupoMuscular.ISQUIOS,
        'gluteos': GrupoMuscular.GLUTEOS,
        'glúteos': GrupoMuscular.GLUTEOS,
        'gemelos': GrupoMuscular.GEMELOS,
        'pantorrillas': GrupoMuscular.GEMELOS,
        'core': GrupoMuscular.CORE,
        'abdomen': GrupoMuscular.CORE,
        'antebrazos': GrupoMuscular.ANTEBRAZOS,
        'trapecios': GrupoMuscular.TRAPECIOS
    }
    return mapeo.get(grupo_str.lower(), GrupoMuscular.PECHO)


def validar_combinacion_objetivo_nivel(objetivo: ObjetivoEntrenamiento, nivel: NivelExperiencia) -> bool:
    """Valida si la combinación de objetivo y nivel es apropiada"""
    return objetivo.es_compatible_con_nivel(nivel)


def calcular_volumen_total_semanal(grupos_seleccionados: List[GrupoMuscular], nivel: NivelExperiencia) -> int:
    """Calcula volumen total semanal para una lista de grupos musculares"""
    return sum(grupo.obtener_volumen_base(nivel) for grupo in grupos_seleccionados)


def distribuir_volumen_por_frecuencia(grupo: GrupoMuscular, volumen_semanal: int, frecuencia: int) -> List[int]:
    """Distribuye el volumen semanal entre las sesiones según frecuencia"""
    if frecuencia <= 0:
        return [volumen_semanal]

    volumen_base = volumen_semanal // frecuencia
    volumen_extra = volumen_semanal % frecuencia

    distribucion = [volumen_base] * frecuencia

    # Distribuir el volumen extra en las primeras sesiones
    for i in range(volumen_extra):
        distribucion[i] += 1

    return distribucion


# en analytics/planificador_helms_completo.py
import calendar
from datetime import date, timedelta


def generar_contexto_calendario(plan_anual: Dict, año: int, mes: int) -> Dict:
    """
    Procesa un plan anual y genera los datos para un calendario mensual.
    VERSIÓN FINAL que mapea correctamente cada semana a su fase.
    """
    matriz_mes = calendar.monthcalendar(año, mes)
    hoy = date.today()
    primer_dia_del_año = date(año, 1, 1)
    dias_para_lunes = (0 - primer_dia_del_año.weekday() + 7) % 7
    fecha_inicio_plan = primer_dia_del_año + timedelta(days=dias_para_lunes)

    # --- INICIO DE LA CORRECCIÓN ---

    # 1. Crear un mapa que asocie cada número de semana con su fase
    mapa_semana_a_fase = {}
    periodizacion = plan_anual.get('metadata', {}).get('periodizacion_completa', [])

    # Itera sobre la lista de bloques de periodización
    for bloque in periodizacion:
        # Itera sobre los números de semana reales dentro de cada bloque
        # ej: para el primer bloque, itera sobre [1, 2, 3, 4]
        # ej: para el segundo bloque, itera sobre [5, 6, 7, 8]
        for numero_semana in bloque['semanas']:
            mapa_semana_a_fase[numero_semana] = bloque['fase'].title()

    # 2. Procesar el plan usando el mapa corregido
    entrenos_por_fecha = {}
    dias_de_entreno_offset = [0, 1, 3, 4]  # L, M, J, V

    for num_semana_str, dias_de_la_semana in plan_anual.get('ejercicios_por_semana', {}).items():
        num_semana_int = int(num_semana_str.split('_')[1])
        # Usa el mapa para obtener la fase correcta para esta semana específica
        fase_actual = mapa_semana_a_fase.get(num_semana_int, "Fase")

        dias_entreno_keys = sorted(dias_de_la_semana.keys())

        for i, dia_key in enumerate(dias_entreno_keys):
            if i >= len(dias_de_entreno_offset): continue

            offset_dia_semana = dias_de_entreno_offset[i]
            dias_desde_inicio = ((num_semana_int - 1) * 7) + offset_dia_semana
            fecha_entrenamiento = fecha_inicio_plan + timedelta(days=dias_desde_inicio)

            ejercicios = dias_de_la_semana[dia_key]
            entrenos_por_fecha[fecha_entrenamiento] = {
                "nombre_rutina": f"Día {i + 1} - {fase_actual}",
                "ejercicios": ejercicios
            }

    # --- FIN DE LA CORRECCIÓN ---

    # 3. Construir la estructura final del calendario (sin cambios)
    semanas_calendario = []
    for semana_matriz in matriz_mes:
        dias_semana = []
        for dia_num in semana_matriz:
            if dia_num == 0:
                dias_semana.append(None)
            else:
                fecha_actual = date(año, mes, dia_num)
                entreno_del_dia = entrenos_por_fecha.get(fecha_actual)
                dias_semana.append({
                    "numero": dia_num,
                    "es_hoy": fecha_actual == hoy,
                    "entrenamiento": entreno_del_dia
                })
        semanas_calendario.append(dias_semana)

    return {
        "semanas": semanas_calendario,
        "nombre_mes": calendar.month_name[mes],
        "año": año
    }
