# analytics/planificador.py

import random
from datetime import date, timedelta
import calendar


class PlanificadorAvanzadoHelms:
    """
    Genera un plan de entrenamiento anual para atletas AVANZADOS.
    VERSIÓN FINAL Y FUNCIONAL que incluye cálculo de peso y descanso.
    """

    def __init__(self, cliente_data):
        self.cliente_data = cliente_data
        self.one_rm = self.cliente_data.get("one_rm_estimados", {})
        self.ejercicios_a_evitar = self.cliente_data.get("ejercicios_a_evitar", [])

        # 1. PERIODIZACIÓN ANUAL COMPLETA
        self.estructura_anual = [
            {'nombre': 'Mesociclo 1: Acumulación de Volumen', 'duracion_semanas': 4, 'foco': 'hipertrofia'},
            {'nombre': 'Mesociclo 2: Intensificación de Fuerza', 'duracion_semanas': 4, 'foco': 'fuerza'},
            {'nombre': 'Mesociclo 3: Pico de Potencia', 'duracion_semanas': 3, 'foco': 'potencia'},
            {'nombre': 'Semana de Deload Activo', 'duracion_semanas': 1, 'foco': 'deload'},
            {'nombre': 'Mesociclo 4: Acumulación con Variaciones', 'duracion_semanas': 4, 'foco': 'hipertrofia',
             'rotar': True},
            {'nombre': 'Mesociclo 5: Fuerza con Variaciones', 'duracion_semanas': 4, 'foco': 'fuerza', 'rotar': True},
            {'nombre': 'Semana de Deload Activo', 'duracion_semanas': 1, 'foco': 'deload'},
            {'nombre': 'Mesociclo 6: Hipertrofia Funcional', 'duracion_semanas': 4, 'foco': 'hipertrofia'},
            {'nombre': 'Mesociclo 7: Mantenimiento de Fuerza', 'duracion_semanas': 4, 'foco': 'fuerza'},
            {'nombre': 'Semana de Deload Activo', 'duracion_semanas': 1, 'foco': 'deload'},
            {'nombre': 'Mesociclo 8: Acumulación Final', 'duracion_semanas': 4, 'foco': 'hipertrofia', 'rotar': True},
            {'nombre': 'Mesociclo 9: Fuerza Final', 'duracion_semanas': 4, 'foco': 'fuerza', 'rotar': True},
            {'nombre': 'Semana de Transición', 'duracion_semanas': 1, 'foco': 'deload'},
        ]

        # 2. CONFIGURACIÓN COMPLETA CON TODAS LAS CLAVES NECESARIAS
        self.config_objetivos = {
            'hipertrofia': {
                'reps': (8, 12), 'rpe_objetivo': (7, 9), 'descanso_min': (2, 3),
                'porcentaje_1rm': (0.65, 0.80),  # <-- CLAVE RESTAURADA
                'volumen_semanal': {'Empuje': 16, 'Tracción': 16, 'Pierna': 18, 'Core': 8}
            },
            'fuerza': {
                'reps': (3, 5), 'rpe_objetivo': (8, 9), 'descanso_min': (3, 5),
                'porcentaje_1rm': (0.80, 0.90),  # <-- CLAVE RESTAURADA
                'volumen_semanal': {'Empuje': 12, 'Tracción': 12, 'Pierna': 14, 'Core': 6}
            },
            'potencia': {
                'reps': (2, 4), 'rpe_objetivo': (7, 8), 'descanso_min': (3, 4),
                'porcentaje_1rm': (0.85, 0.95),  # <-- CLAVE RESTAURADA
                'volumen_semanal': {'Empuje': 10, 'Tracción': 10, 'Pierna': 10, 'Core': 4}
            },
            'deload': {
                'reps': (10, 15), 'rpe_objetivo': (5, 6), 'descanso_min': (1, 2),
                'porcentaje_1rm': (0.50, 0.60),  # <-- CLAVE RESTAURADA
                'volumen_semanal': {'Empuje': 8, 'Tracción': 8, 'Pierna': 8, 'Core': 4}
            }
        }

        # 3. CATÁLOGO DE EJERCICIOS (sin cambios)
        self.catalogo_ejercicios = {
            'Empuje Horizontal': {'principal': ['Press de Banca con Barra', 'Press de Banca con Mancuernas'],
                                  'secundario': ['Fondos en Paralelas'], 'aislamiento': ['Aperturas en Polea']},
            'Empuje Vertical': {'principal': ['Press Militar con Barra'], 'secundario': ['Press Arnold'],
                                'aislamiento': ['Elevaciones Laterales']},
            'Tracción Horizontal': {'principal': ['Remo con Barra (Pendlay)'], 'secundario': ['Remo en Polea'],
                                    'aislamiento': ['Face Pulls']},
            'Tracción Vertical': {'principal': ['Dominadas con Lastre'], 'secundario': ['Jalón al Pecho'],
                                  'aislamiento': ['Pullover en Polea']},
            'Dominante de Rodilla': {'principal': ['Sentadilla Trasera con Barra'], 'secundario': ['Prensa de Piernas'],
                                     'aislamiento': ['Extensiones de Cuádriceps']},
            'Dominante de Cadera': {'principal': ['Peso Muerto Convencional'], 'secundario': ['Peso Muerto Rumano'],
                                    'aislamiento': ['Curl Femoral']},
            'Core': {'aislamiento': ['Plancha con Peso', 'Rueda Abdominal']},
            'Bíceps': {'aislamiento': ['Curl con Barra Z', 'Curl Martillo']},
            'Tríceps': {'aislamiento': ['Press Francés', 'Extensiones en Polea']}
        }

        # 4. DISTRIBUCIÓN SEMANAL (con la estructura de diccionario que funcionaba)
        self.distribucion_semanal = {
            'Día 1 (Upper - Fuerza)': {'tipo': 'fuerza',
                                       'patrones': {'Empuje': ['Empuje Horizontal', 'Empuje Vertical'],
                                                    'Tracción': ['Tracción Vertical', 'Tracción Horizontal'],
                                                    'Brazos': ['Bíceps', 'Tríceps']}},
            'Día 2 (Lower - Fuerza)': {'tipo': 'fuerza',
                                       'patrones': {'Pierna': ['Dominante de Rodilla', 'Dominante de Cadera'],
                                                    'Core': ['Core']}},
            'Día 3 (Upper - Hipertrofia)': {'tipo': 'hipertrofia',
                                            'patrones': {'Empuje': ['Empuje Vertical', 'Empuje Horizontal'],
                                                         'Tracción': ['Tracción Horizontal', 'Tracción Vertical'],
                                                         'Brazos': ['Bíceps', 'Tríceps']}},
            'Día 4 (Lower - Hipertrofia)': {'tipo': 'hipertrofia',
                                            'patrones': {'Pierna': ['Dominante de Cadera', 'Dominante de Rodilla'],
                                                         'Core': ['Core']}},
        }

    def _seleccionar_ejercicios_para_mesociclo(self, rotar=False):
        # ... (esta función no necesita cambios)
        seleccion = {}
        for patron, tipos in self.catalogo_ejercicios.items():
            principales = [e for e in tipos.get('principal', []) if e not in self.ejercicios_a_evitar]
            secundarios = [e for e in tipos.get('secundario', []) if e not in self.ejercicios_a_evitar]
            aislamiento = [e for e in tipos.get('aislamiento', []) if e not in self.ejercicios_a_evitar]
            if not principales and not secundarios and not aislamiento: continue
            ej_principal = (principales[1 % len(principales)] if rotar and len(principales) > 1 else (
                principales[0] if principales else None))
            ej_secundario = random.choice(secundarios) if secundarios else None
            ej_aislamiento = random.choice(aislamiento) if aislamiento else None
            seleccion[patron] = {'principal': ej_principal, 'secundario': ej_secundario, 'aislamiento': ej_aislamiento}
        return seleccion

    def _calcular_peso_progresion(self, nombre_ejercicio, porcentaje_1rm, semana_total):
        """Calcula el peso aplicando una progresión lineal simple a lo largo del año."""
        rm_base = self.one_rm.get(nombre_ejercicio, 50)
        rm_progresivo = rm_base * (1 + (semana_total * 0.005))
        peso = rm_progresivo * random.uniform(porcentaje_1rm[0], porcentaje_1rm[1])
        return round(peso / 2.5) * 2.5

    def _generar_rutina_dia(self, config_dia, ejercicios_mesociclo, config_bloque, semana_num_total):
        """Genera la rutina para un día específico, AÑADIENDO PESO Y DESCANSO."""
        rutina = []
        config_dup = self.config_objetivos[config_dia['tipo']]

        for grupo_general, patrones_especificos in config_dia['patrones'].items():
            volumen_total_semanal = config_bloque['volumen_semanal'].get(grupo_general, 12)
            volumen_dia = volumen_total_semanal // 2
            series_por_ejercicio = max(1, volumen_dia // len(patrones_especificos))

            for patron in patrones_especificos:
                ejercicios_disponibles = ejercicios_mesociclo.get(patron)
                if not ejercicios_disponibles: continue

                ejercicio_elegido = ejercicios_disponibles.get('principal') or ejercicios_disponibles.get(
                    'secundario') or ejercicios_disponibles.get('aislamiento')
                if not ejercicio_elegido: continue

                # Obtener el %1RM del día para calcular el peso
                porcentaje_1rm_dia = config_dup.get('porcentaje_1rm', (0.6, 0.7))  # Fallback seguro

                rutina.append({
                    "nombre": ejercicio_elegido,
                    "series": series_por_ejercicio,
                    "repeticiones": f"{config_dup['reps'][0]}-{config_dup['reps'][1]}",
                    "rpe": f"{config_dup['rpe_objetivo'][0]}-{config_dup['rpe_objetivo'][1]}",
                    "descanso": f"{config_dup['descanso_min'][0]}-{config_dup['descanso_min'][1]} min",
                    # Clave 'descanso'
                    "peso_kg": self._calcular_peso_progresion(  # Cálculo del peso
                        ejercicio_elegido, porcentaje_1rm_dia, semana_num_total
                    ),
                    "notas": f"Objetivo del día: {config_dia['tipo'].capitalize()}"
                })
        return rutina

    def generar_plan_completo(self):
        """Genera la estructura completa del plan de entrenamiento anual."""
        plan_anual_semanal = []
        plan_por_bloques = []
        semana_num_total = 1

        for mesociclo_info in self.estructura_anual:
            ejercicios_del_mesociclo = self._seleccionar_ejercicios_para_mesociclo(mesociclo_info.get('rotar', False))
            bloque_actual = {'nombre': mesociclo_info['nombre'], 'objetivo': mesociclo_info['foco'],
                             'duracion': mesociclo_info['duracion_semanas'], 'semanas': []}

            for semana_num_mesociclo in range(1, mesociclo_info['duracion_semanas'] + 1):
                es_deload = mesociclo_info['foco'] == 'deload'
                semana_actual = {"semana_num_total": semana_num_total, "semana_num_bloque": semana_num_mesociclo,
                                 "bloque": mesociclo_info['nombre'],
                                 "objetivo": "Deload" if es_deload else mesociclo_info['foco'].capitalize(),
                                 "rutinas": {}}

                for nombre_dia, config_dia in self.distribucion_semanal.items():
                    tipo_dia_actual = 'deload' if es_deload else config_dia['tipo']
                    config_bloque_actual = self.config_objetivos[tipo_dia_actual]

                    # Llamada corregida con los 4 argumentos necesarios
                    rutina_generada = self._generar_rutina_dia(
                        config_dia,
                        ejercicios_del_mesociclo,
                        config_bloque_actual,
                        semana_num_total  # El argumento que faltaba
                    )
                    semana_actual["rutinas"][nombre_dia] = rutina_generada

                plan_anual_semanal.append(semana_actual)
                bloque_actual['semanas'].append(semana_actual)
                semana_num_total += 1

            plan_por_bloques.append(bloque_actual)

        return plan_anual_semanal, plan_por_bloques


# La función generar_contexto_calendario no necesita cambios
def generar_contexto_calendario(plan_semanal_completo, año, mes):
    # ... (código sin cambios)
    cal = calendar.Calendar()
    dias_del_mes_con_fecha_completa = cal.monthdatescalendar(año, mes)
    hoy = date.today()
    primer_dia_del_año = date(hoy.year, 1, 1)
    dias_para_lunes = (0 - primer_dia_del_año.weekday() + 7) % 7
    fecha_inicio_plan = primer_dia_del_año + timedelta(days=dias_para_lunes)
    plan_por_fecha = {}
    dias_de_entreno_offset = [0, 1, 3, 4]
    nombres_rutinas_semana = list(PlanificadorAvanzadoHelms({}).distribucion_semanal.keys())
    for num_semana, semana_data in enumerate(plan_semanal_completo):
        for i, nombre_rutina in enumerate(nombres_rutinas_semana):
            if i >= len(dias_de_entreno_offset): continue
            offset_dia = dias_de_entreno_offset[i]
            dias_totales_desde_inicio = (num_semana * 7) + offset_dia
            fecha_entrenamiento = fecha_inicio_plan + timedelta(days=dias_totales_desde_inicio)
            plan_por_fecha[fecha_entrenamiento] = {
                "rutina_nombre": nombre_rutina,
                "ejercicios": semana_data['rutinas'][nombre_rutina],
                "objetivo": semana_data.get('objetivo', 'N/A').capitalize(),
                "bloque": semana_data.get('bloque', 'N/A'),
            }
    contexto_calendario_final = []
    for semana_de_fechas in dias_del_mes_con_fecha_completa:
        semana_para_template = []
        for fecha_del_dia in semana_de_fechas:
            plan_del_dia = plan_por_fecha.get(fecha_del_dia, {"objetivo": "Descanso"})
            semana_para_template.append({
                'num': fecha_del_dia.day if fecha_del_dia.month == mes else 0,
                'fecha_str': fecha_del_dia.strftime('%Y-%m-%d'),
                'plan': plan_del_dia
            })
        contexto_calendario_final.append(semana_para_template)
    return contexto_calendario_final


class PlanificadorAnualIA:
    def __init__(self, cliente_id):
        self.cliente_id = cliente_id
        self.cliente = Cliente.objects.get(id=cliente_id)

        # Crear perfil para Helms
        self.perfil_helms = self._crear_perfil_helms()
        self.planificador_helms = PlanificadorHelms(self.perfil_helms)

    def _crear_perfil_helms(self):
        return PerfilCliente(
            cliente_id=self.cliente.id,
            experiencia_años=self.cliente.experiencia_años,
            objetivo_principal=self._mapear_objetivo(),
            dias_disponibles=self.cliente.dias_disponibles,
            tiempo_por_sesion=self.cliente.tiempo_por_sesion,
            # ... mapear resto de campos
        )

    def generar_plan_anual(self):
        # Usar el planificador de Helms
        plan_helms = self.planificador_helms.generar_plan_completo()

        if plan_helms['status'] == 'success':
            return self._convertir_a_formato_actual(plan_helms)
        else:
            # Fallback a tu planificador actual
            return self._generar_plan_fallback()
