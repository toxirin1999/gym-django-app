# analytics/ia_analizador_programas.py

from rutinas.models import Programa, Rutina, RutinaEjercicio


class AnalizadorProgramaIA:
    def __init__(self, programa, objetivo_cliente):
        self.programa_original = programa
        self.objetivo = objetivo_cliente

        # =================================================================
        # ### CORRECCIÓN: AÑADIMOS LA CLAVE 'general' AL DICCIONARIO ###
        # =================================================================
        self.configuracion = {
            'fuerza': {
                'reps_objetivo': (1, 5), 'series_objetivo': (3, 6),
                'frecuencia_objetivo': 3, 'descanso_objetivo': (180, 300)
            },
            'hipertrofia': {
                'reps_objetivo': (6, 12), 'series_objetivo': (3, 5),
                'frecuencia_objetivo': 4, 'descanso_objetivo': (60, 120)
            },
            'resistencia': {
                'reps_objetivo': (12, 20), 'series_objetivo': (2, 4),
                'frecuencia_objetivo': 5, 'descanso_objetivo': (30, 60)
            },
            # --- AÑADE ESTE BLOQUE COMPLETO ---
            'general': {
                'reps_objetivo': (8, 15), 'series_objetivo': (2, 4),
                'frecuencia_objetivo': 3, 'descanso_objetivo': (60, 90)
            }
            # ------------------------------------
        }
        # =================================================================

        self.sugerencias = []
        self.programa_modificado = self._clonar_programa_a_diccionario()

    # ... (El resto de la clase se mantiene exactamente igual) ...
    def _clonar_programa_a_diccionario(self):
        """
        Convierte el programa de Django a una estructura de diccionario en memoria.
        VERSIÓN CON DEPURACIÓN.
        """
        print(f"\n--- Depurando _clonar_programa_a_diccionario para programa: {self.programa_original.nombre} ---")

        programa_dict = {'nombre': self.programa_original.nombre, 'rutinas': []}

        rutinas_del_programa = self.programa_original.rutina_set.all()
        print(f"🔍 Encontradas {rutinas_del_programa.count()} rutinas para este programa.")

        for rutina in rutinas_del_programa.order_by('orden'):
            print(f"  -> Procesando rutina: {rutina.nombre}")
            rutina_dict = {'nombre': rutina.nombre, 'ejercicios': []}

            ejercicios_de_la_rutina = rutina.rutinaejercicio_set.all()
            print(f"    🔍 Encontrados {ejercicios_de_la_rutina.count()} ejercicios para la rutina '{rutina.nombre}'.")

            for re in ejercicios_de_la_rutina.order_by('id'):
                print(f"      -> Añadiendo ejercicio: {re.ejercicio.nombre}")
                ejercicio_dict = {
                    'nombre': re.ejercicio.nombre,
                    'grupo_muscular': re.ejercicio.grupo_muscular,
                    'series': re.series,
                    'repeticiones': re.repeticiones
                }
                rutina_dict['ejercicios'].append(ejercicio_dict)
            programa_dict['rutinas'].append(rutina_dict)

        print("--- Fin de la depuración ---")
        return programa_dict

    def analizar_y_generar_contexto(self):
        # Primero, verificamos si el programa tiene contenido
        if not self.programa_modificado or not self.programa_modificado['rutinas']:
            # Si no hay rutinas, devolvemos un contexto vacío para evitar errores
            return {
                'rutina_optimizada': None, 'sesion_individual': None,
                'periodizacion': None, 'recuperacion': None,
                'focus_message': "El programa asignado no contiene rutinas para analizar.",
                'mejora_estimada': 0, 'sugerencias_raw': []
            }

        self._analizar_frecuencia()
        self._analizar_volumen_por_rutina()
        self._analizar_intensidad_y_series()
        self._analizar_equilibrio_muscular()

        mejora_estimada = len(self.sugerencias) * 7
        return {
            'rutina_optimizada': self._construir_rutina_optimizada(),
            'sesion_individual': self._construir_sesion_ejemplo(),
            'periodizacion': self._construir_periodizacion(),
            'recuperacion': self._construir_recuperacion(),
            'focus_message': self._generar_focus_message(),
            'mejora_estimada': min(95, mejora_estimada),
            'sugerencias_raw': self.sugerencias
        }

    def _analizar_frecuencia(self):
        frecuencia_programa = self.programa_original.rutina_set.count()
        frecuencia_ideal = self.configuracion[self.objetivo]['frecuencia_objetivo']
        if frecuencia_programa < frecuencia_ideal:
            self.sugerencias.append({'tipo': 'Frecuencia Semanal',
                                     'descripcion': f"El programa tiene {frecuencia_programa} días, pero para {self.objetivo} se recomiendan {frecuencia_ideal}."})
        elif frecuencia_programa > frecuencia_ideal + 1:
            self.sugerencias.append({'tipo': 'Frecuencia Semanal',
                                     'descripcion': f"El programa tiene {frecuencia_programa} días. Asegúrate de que haya suficiente recuperación."})

    def _analizar_volumen_por_rutina(self):
        for rutina in self.programa_modificado['rutinas']:
            series_totales = sum(ej['series'] for ej in rutina['ejercicios'])
            if series_totales > 25 and self.objetivo != 'resistencia':
                self.sugerencias.append({'tipo': 'Volumen Excesivo',
                                         'descripcion': f"La rutina '{rutina['nombre']}' tiene un volumen muy alto ({series_totales} series). Podría causar sobreentrenamiento."})
            elif series_totales < 12:
                self.sugerencias.append({'tipo': 'Volumen Insuficiente',
                                         'descripcion': f"La rutina '{rutina['nombre']}' tiene un volumen bajo ({series_totales} series). Podría no ser suficiente estímulo."})

    def _analizar_intensidad_y_series(self):
        reps_ideales = self.configuracion[self.objetivo]['reps_objetivo']
        series_ideales = self.configuracion[self.objetivo]['series_objetivo']
        for i, rutina in enumerate(self.programa_modificado['rutinas']):
            for j, ejercicio in enumerate(rutina['ejercicios']):
                if not (reps_ideales[0] <= ejercicio['repeticiones'] <= reps_ideales[1]):
                    reps_originales = ejercicio['repeticiones']
                    reps_nuevas = max(reps_ideales[0], min(ejercicio['repeticiones'], reps_ideales[1]))
                    self.sugerencias.append({'tipo': 'Rango de Repeticiones',
                                             'descripcion': f"En '{ejercicio['nombre']}', las {reps_originales} reps no son óptimas para {self.objetivo}. Se ajustan a {reps_nuevas}."})
                    self.programa_modificado['rutinas'][i]['ejercicios'][j]['repeticiones'] = reps_nuevas
                if not (series_ideales[0] <= ejercicio['series'] <= series_ideales[1]):
                    series_originales = ejercicio['series']
                    series_nuevas = max(series_ideales[0], min(ejercicio['series'], series_ideales[1]))
                    self.sugerencias.append({'tipo': 'Número de Series',
                                             'descripcion': f"En '{ejercicio['nombre']}', las {series_originales} series no son óptimas para {self.objetivo}. Se ajustan a {series_nuevas}."})
                    self.programa_modificado['rutinas'][i]['ejercicios'][j]['series'] = series_nuevas

    def _analizar_equilibrio_muscular(self):
        grupos_contados = {}
        for rutina in self.programa_modificado['rutinas']:
            for ejercicio in rutina['ejercicios']:
                grupo = ejercicio['grupo_muscular']
                grupos_contados[grupo] = grupos_contados.get(grupo, 0) + ejercicio['series']
        if not grupos_contados: return
        max_grupo = max(grupos_contados, key=grupos_contados.get)
        min_grupo = min(grupos_contados, key=grupos_contados.get)
        if len(grupos_contados) > 2 and grupos_contados[max_grupo] > 2 * grupos_contados.get(min_grupo, 0):
            self.sugerencias.append({'tipo': 'Equilibrio Muscular',
                                     'descripcion': f"Posible desequilibrio: El grupo '{max_grupo}' tiene mucho más volumen que '{min_grupo}'."})

    def _construir_rutina_optimizada(self):
        rutinas = self.programa_modificado['rutinas']
        if not rutinas: return None
        total_ejercicios = sum(len(r['ejercicios']) for r in rutinas)
        avg_ejercicios_por_dia = total_ejercicios / len(rutinas) if rutinas else 0
        descanso_ideal = self.configuracion[self.objetivo]['descanso_objetivo']
        return {
            'frecuencia_semanal': len(rutinas),
            'ejercicios_por_dia': f"{avg_ejercicios_por_dia:.1f}",
            'repeticiones': f"{self.configuracion[self.objetivo]['reps_objetivo'][0]}-{self.configuracion[self.objetivo]['reps_objetivo'][1]}",
            'descanso_series': f"{descanso_ideal[0]}-{descanso_ideal[1]} seg"
        }

    def _construir_sesion_ejemplo(self):
        if not self.programa_modificado['rutinas']: return None
        return {'ejercicios_recomendados': self.programa_modificado['rutinas'][0]['ejercicios']}

    def _construir_periodizacion(self):
        fase_actual = self.objetivo.capitalize()
        plan = {'Hipertrofia': {'nombre': 'Fuerza', 'duracion': '4 sem.'},
                'Fuerza': {'nombre': 'Hipertrofia', 'duracion': '6 sem.'},
                'Resistencia': {'nombre': 'Hipertrofia', 'duracion': '5 sem.'}}
        proxima_fase = plan.get(fase_actual, {'nombre': 'Descarga', 'duracion': '1 sem.'})
        return {'fase_actual': fase_actual, 'duracion_fase': 'Fase Actual', 'fases_planificadas': [proxima_fase]}

    def _construir_recuperacion(self):
        frecuencia = len(self.programa_modificado['rutinas'])
        descanso_ideal = self.configuracion[self.objetivo]['descanso_objetivo']
        return {'descanso_entre_entrenamientos': f"{descanso_ideal[0]}-{descanso_ideal[1]} seg entre series",
                'dias_descanso_semanal': 7 - frecuencia}

    def _generar_focus_message(self):
        if not self.sugerencias: return "¡El programa asignado está muy bien alineado con tu objetivo! Sigue así."
        return self.sugerencias[0]['descripcion']
