"""
HyroxStationIntelligence — capa de inteligencia técnica por estación HYROX.

Complementa al motor TSB/readiness/interferencia: explica el *por qué*
de cada debilidad y qué corregir, sin reemplazar las decisiones de carga.
"""


class HyroxStationIntelligence:

    STATIONS = {
        "skierg": {
            "display_name": "SkiErg",
            "icon": "fa-skiing",
            "technical_focus": [
                "Cadera atrás (bisagra), no sentadilla",
                "Dorsales activos desde el inicio",
                "Core firme todo el recorrido",
                "Brazos cerca del cuerpo",
            ],
            "common_mistakes": [
                "Tirar solo con brazos",
                "Bajar demasiado el torso",
                "Abrir los brazos en Y",
                "Perder tensión en core",
            ],
            "strategy": [
                "Primeros 200m controla pulsaciones",
                "Mantén 32–38 SPM",
                "Últimos 100m reduce ligeramente",
            ],
            "corrective_work": [
                "3×15 reps solo cadera (sin brazos)",
                "2×500m a 32–34 SPM",
                "Respiración: exhala al tirar",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "skierg",
                    "nombre_ejercicio": "SkiErg técnico · Patrón cadera",
                    "data_metricas": {
                        "override": True,
                        "series": [{"reps": 15}, {"reps": 15}, {"reps": 15}],
                        "rpe_objetivo": "4-5",
                        "notas": "Sin brazos o con cuerda. Foco total en bisagra de cadera. Dorsales activos.",
                    },
                },
                {
                    "tipo_actividad": "skierg",
                    "nombre_ejercicio": "SkiErg 2×500m técnico",
                    "data_metricas": {
                        "override": True,
                        "series": [{"distancia_m": 500}, {"distancia_m": 500}],
                        "rpe_objetivo": "5-6",
                        "notas": "32–34 SPM. Prioriza eficiencia técnica sobre velocidad.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "Sales muy fatigado del SkiErg. Posible exceso de brazos o mala bisagra de cadera.",
                "high_rpe": "El esfuerzo es alto. Revisa core y patrón de cadera.",
                "slow_time": "Tiempo bajo. Prioriza eficiencia antes de intensidad.",
                "general": "Trabaja patrón de cadera y dorsales para mejorar eficiencia en SkiErg.",
            },
        },

        "sled_push": {
            "display_name": "Sled Push",
            "icon": "fa-truck-loading",
            "description": (
                "Estación 02 — 4 × 12,5 m (25 m totales). Llega tras el 2.º km de carrera. "
                "Si el trineo se detiene, necesitas el doble de energía para arrancar de nuevo. "
                "Sin fase excéntrica: puedes entrenarlo con frecuencia sin coste de recuperación elevado."
            ),
            "weights": {
                "women_open": "102 kg",
                "men_open": "152 kg",
                "pro_men": "202 kg",
                "pro_women": "152 kg",
                "doubles_mixed_f": "102 kg",
                "doubles_mixed_m": "152 kg",
            },
            "technical_focus": [
                "Posición de abrazo: antebrazos apoyados en postes, codos cerrados, manos como ganchos",
                "Centro de masa bajo: cabeza y torso alineados con el centro del trineo",
                "Pasos cortos y potentes, empujando con las puntas",
                "Core firme transmitiendo fuerza de piernas al trineo",
                "Salida explosiva: inclínate sobre el trineo y arranca como un sprint",
                "Respiración continua: inhala y exhala por completo, no contengas el aliento",
            ],
            "positions": [
                "Brazos extendidos: manos por encima del centro, muñeca-codo-hombro alineados. Mejor para atletas altos.",
                "Abrazo (más común): antebrazos en postes, codos cerrados. Activa más cadena posterior. Mejor para atletas bajos.",
            ],
            "common_mistakes": [
                "Fuerza dirigida arriba o abajo — baja las manos, la presión va hacia adelante",
                "Pasos demasiado largos — pierdes tracción y desperdicias energía",
                "Codos abiertos y empuje con hombros — dispersa la fuerza y aumenta la fatiga",
                "Contener la respiración — acelera la fatiga muscular",
                "Dejar que el trineo se detenga — cuesta el doble volver a arrancarlo",
            ],
            "strategy": [
                "Divide mentalmente en dos tramos de 12,5 m; usa la mitad como referencia",
                "Cuenta tus pasos en entrenamiento para saber cuántos necesitas por tramo",
                "Si el trineo se para: detente, reajusta postura y reinicia explosivo",
                "Objetivo: trineo en movimiento constante — inercia > velocidad punta",
            ],
            "rules": [
                "El trineo debe cruzar completamente la línea antes de cambiar dirección",
                "No puedes soltar el trineo y descansar — movimiento continuo",
                "Permanece dentro de tu carril asignado durante toda la estación",
                "Entra por IN y sal por OUT de la Roxzone — error = penalización 2 min",
            ],
            "corrective_work": [
                "Entrena con más carga que en competición (ej. +20%) para que el peso oficial se sienta manejable",
                "Combina siempre trineo con carrera: 1 km antes + estación + 1 km después",
                "Practica respiración bajo carga hasta que sea automática",
                "Core antiextensión: plancha, dead bugs, pallof press",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "hyrox_station",
                    "nombre_ejercicio": "Sled Push técnico · 4×25m",
                    "data_metricas": {
                        "override": True,
                        "series": [{"distancia_m": 25}, {"distancia_m": 25}, {"distancia_m": 25}, {"distancia_m": 25}],
                        "rpe_objetivo": "6-7",
                        "notas": "Peso competición +20%. Posición de abrazo. Pasos cortos. Trineo en movimiento constante.",
                    },
                },
                {
                    "tipo_actividad": "carrera",
                    "nombre_ejercicio": "Transición Sled Push → carrera Z2",
                    "data_metricas": {
                        "override": True,
                        "distancia_km": 2,
                        "rpe_objetivo": "5",
                        "notas": "Recupera el patrón de carrera después del esfuerzo de empuje. Frecuencia antes que velocidad.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "El trineo te destruye para la carrera. Revisa posición (¿codos abiertos?, ¿pasos largos?) o reduce intensidad de salida.",
                "high_rpe": "Esfuerzo alto. Prueba posición de abrazo y cuenta pasos para mantener cadencia constante.",
                "slow_time": "Falta eficiencia de empuje. No es solo fuerza — trabaja la mecánica de salida y respiración bajo carga.",
                "general": "Combina trineo con carrera en cada sesión. La transferencia aeróbica es clave para rendir después de la estación.",
            },
        },

        "sled_pull": {
            "display_name": "Sled Pull",
            "icon": "fa-anchor",
            "technical_focus": [
                "Apoyo firme de pies",
                "Tirón desde cadera y core",
                "Brazos como guía, no motor",
                "Ritmo continuo",
            ],
            "common_mistakes": [
                "Tirar solo con brazos",
                "Falta de estabilidad en pies",
                "Tirones desordenados",
                "Parones largos",
            ],
            "strategy": [
                "Tirones constantes, no máximos",
                "Mantener ritmo uniforme",
                "Evitar pausas largas",
            ],
            "corrective_work": [
                "Tirones técnicos con carga ligera",
                "Trabajo de agarre",
                "Core anti-rotacional",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "hyrox_station",
                    "nombre_ejercicio": "Sled Pull técnico · 4×20m",
                    "data_metricas": {
                        "override": True,
                        "series": [{"distancia_m": 20}, {"distancia_m": 20}, {"distancia_m": 20}, {"distancia_m": 20}],
                        "rpe_objetivo": "5-6",
                        "notas": "Pies firmes, tirón con cadera. No con la espalda. Mantén tensión en la cuerda.",
                    },
                },
                {
                    "tipo_actividad": "carrera",
                    "nombre_ejercicio": "Transición Sled Pull → carrera suave",
                    "data_metricas": {
                        "override": True,
                        "distancia_km": 2.5,
                        "rpe_objetivo": "5",
                        "notas": "Volver a correr sin hundirte, no buscar marca.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "Pierdes mucho después del tirón. Posible falta de coordinación o exceso de brazos.",
                "high_rpe": "Fatiga alta. Revisa apoyo y ritmo.",
                "slow_time": "No es solo fuerza. Mejora técnica de tracción.",
                "general": "Refuerza cadena posterior y trabaja tirón con cadera en Sled Pull.",
            },
        },

        "burpees": {
            "display_name": "Burpee Broad Jump",
            "icon": "fa-person-falling",
            "technical_focus": [
                "Movimiento fluido continuo",
                "Salto controlado, no máximo",
                "Respiración constante",
                "Aterrizaje estable",
            ],
            "common_mistakes": [
                "Saltar demasiado lejos",
                "Pararse entre repeticiones",
                "Perder ritmo",
                "Fatiga descontrolada",
            ],
            "strategy": [
                "Ritmo constante tipo metrónomo",
                "No buscar distancia máxima",
                "Mantener respiración estable",
            ],
            "corrective_work": [
                "Series de burpees a ritmo fijo",
                "Trabajo de pacing",
                "Entrenamiento de respiración",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "hyrox_station",
                    "nombre_ejercicio": "Burpee Broad Jump técnico",
                    "data_metricas": {
                        "override": True,
                        "series": [{"reps": 10}, {"reps": 10}, {"reps": 10}],
                        "rpe_objetivo": "5-6",
                        "notas": "Foco en caída controlada y salto simétrico. No buscar velocidad.",
                    },
                },
                {
                    "tipo_actividad": "fuerza",
                    "nombre_ejercicio": "Box Jump · Aterrizaje suave",
                    "data_metricas": {
                        "override": True,
                        "series": [{"reps": 5}, {"reps": 5}, {"reps": 5}],
                        "rpe_objetivo": "5",
                        "notas": "Aterrizaje silencioso. Potencia de salto sin impacto excesivo.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "Te vacían demasiado. Probable mal pacing.",
                "high_rpe": "Fatiga excesiva. Ajusta ritmo.",
                "slow_time": "Pierdes ritmo. Busca continuidad.",
                "general": "Trabaja ritmo constante y técnica de salto en Burpee Broad Jump.",
            },
        },

        "rowing": {
            "display_name": "Rowing",
            "icon": "fa-water",
            "technical_focus": [
                "Piernas → cadera → brazos",
                "Secuencia correcta siempre",
                "Core estable",
                "Recuperación controlada",
            ],
            "common_mistakes": [
                "Tirar con brazos primero",
                "Ritmo desordenado",
                "Recuperación demasiado rápida",
                "Falta de control",
            ],
            "strategy": [
                "Ritmo estable",
                "Controlar recuperación",
                "No salir fuerte",
            ],
            "corrective_work": [
                "Drills de secuencia",
                "Series a ritmo controlado",
                "Trabajo técnico lento",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "remo",
                    "nombre_ejercicio": "Remo técnico 3×500m",
                    "data_metricas": {
                        "override": True,
                        "series": [{"distancia_m": 500}, {"distancia_m": 500}, {"distancia_m": 500}],
                        "rpe_objetivo": "4-5",
                        "notas": "24 SPM. Secuencia: piernas → cadera → brazos. No tirar con brazos primero.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "Mala transferencia de fuerza. Problema de secuencia.",
                "high_rpe": "Fatiga alta. Ajusta ritmo.",
                "slow_time": "Ineficiencia técnica.",
                "general": "Refuerza secuencia técnica y potencia de piernas en el remo.",
            },
        },

        "farmers_carry": {
            "display_name": "Farmer's Carry",
            "icon": "fa-dumbbell",
            "technical_focus": [
                "Postura erguida",
                "Core firme",
                "Pasos cortos",
                "Agarre constante",
            ],
            "common_mistakes": [
                "Encogerse",
                "Pasos largos",
                "Perder agarre",
                "Paradas frecuentes",
            ],
            "strategy": [
                "Caminar continuo",
                "Evitar pausas largas",
                "Controlar respiración",
            ],
            "corrective_work": [
                "Carries ligeros largos",
                "Trabajo de agarre",
                "Core isométrico",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "hyrox_station",
                    "nombre_ejercicio": "Farmer's Carry técnico 4×40m",
                    "data_metricas": {
                        "override": True,
                        "series": [{"distancia_m": 40}, {"distancia_m": 40}, {"distancia_m": 40}, {"distancia_m": 40}],
                        "rpe_objetivo": "5-6",
                        "notas": "Hombros abajo, core activo, pasos cortos. Foco en postura vertical.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "Te rompe el agarre o postura.",
                "high_rpe": "Fatiga elevada. Ajusta ritmo.",
                "slow_time": "Pierdes continuidad.",
                "general": "Refuerza estabilidad de tronco y posición de hombros en Farmer's Carry.",
            },
        },

        "sandbag_lunges": {
            "display_name": "Sandbag Lunges",
            "icon": "fa-walking",
            "technical_focus": [
                "Paso estable",
                "Rodilla controlada",
                "Core firme",
                "Ritmo constante",
            ],
            "common_mistakes": [
                "Perder equilibrio",
                "Paso irregular",
                "Colapso de rodilla",
                "Paradas frecuentes",
            ],
            "strategy": [
                "Ritmo constante",
                "Evitar fallo muscular",
                "Controlar respiración",
            ],
            "corrective_work": [
                "Lunges técnicos ligeros",
                "Trabajo de estabilidad",
                "Core",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "hyrox_station",
                    "nombre_ejercicio": "Sandbag Lunges técnico 3×30m",
                    "data_metricas": {
                        "override": True,
                        "series": [{"distancia_m": 30}, {"distancia_m": 30}, {"distancia_m": 30}],
                        "rpe_objetivo": "5-6",
                        "notas": "Tronco vertical, rodilla sin colapsar, saco firme. Ritmo constante.",
                    },
                },
                {
                    "tipo_actividad": "fuerza",
                    "nombre_ejercicio": "Goblet Squat · Verticalidad de tronco",
                    "data_metricas": {
                        "override": True,
                        "series": [{"reps": 12}, {"reps": 12}, {"reps": 12}],
                        "rpe_objetivo": "4-5",
                        "notas": "Tronco erguido durante todo el movimiento.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "Fatiga excesiva en piernas.",
                "high_rpe": "Demasiado desgaste.",
                "slow_time": "Falta control y estabilidad.",
                "general": "Refuerza estabilidad de tronco y rodilla en Sandbag Lunges.",
            },
        },

        "wall_balls": {
            "display_name": "Wall Balls",
            "icon": "fa-circle",
            "technical_focus": [
                "Sentadilla profunda controlada",
                "Lanzamiento eficiente",
                "Respiración sincronizada",
                "Ritmo constante",
            ],
            "common_mistakes": [
                "Romper ritmo",
                "Lanzar demasiado fuerte",
                "Fallo técnico en sentadilla",
                "Ir al fallo",
            ],
            "strategy": [
                "Series cortas",
                "Evitar fallo",
                "Mantener ritmo",
            ],
            "corrective_work": [
                "Series de 10–15 reps",
                "Trabajo técnico de sentadilla",
                "Respiración",
            ],
            "corrective_activities": [
                {
                    "tipo_actividad": "hyrox_station",
                    "nombre_ejercicio": "Wall Balls técnicos 3×15",
                    "data_metricas": {
                        "override": True,
                        "series": [{"reps": 15}, {"reps": 15}, {"reps": 15}],
                        "rpe_objetivo": "4-5",
                        "notas": "Sentadilla profunda completa. Foco en coordinación piernas → lanzamiento. No velocidad.",
                    },
                },
                {
                    "tipo_actividad": "fuerza",
                    "nombre_ejercicio": "Thruster · Patrón completo",
                    "data_metricas": {
                        "override": True,
                        "series": [{"reps": 10}, {"reps": 10}, {"reps": 10}],
                        "rpe_objetivo": "5",
                        "notas": "Explosión de piernas al subir. Mismo patrón que wall ball.",
                    },
                },
            ],
            "diagnosis": {
                "high_if": "Llegas muy fatigado. Problema acumulado.",
                "high_rpe": "Fallo muscular cercano.",
                "slow_time": "Gestión incorrecta de series.",
                "general": "Trabaja profundidad de sentadilla y coordinación en Wall Balls.",
            },
        },
    }

    # ── RESOLUCIÓN DE NOMBRE ──────────────────────────────────────────────────

    _NAME_MAP = [
        ("skierg", "skierg"),
        ("ski erg", "skierg"),
        ("sled push", "sled_push"),
        ("sled pull", "sled_pull"),
        ("burpee", "burpees"),
        ("rowing", "rowing"),
        ("remo", "rowing"),
        ("farmer", "farmers_carry"),
        ("carry", "farmers_carry"),
        ("sandbag", "sandbag_lunges"),
        ("lunge", "sandbag_lunges"),
        ("wall ball", "wall_balls"),
    ]

    @classmethod
    def _resolve(cls, name):
        if not name:
            return None
        name_lower = name.lower()
        for keyword, key in cls._NAME_MAP:
            if keyword in name_lower:
                return key
        return None

    # ── API PÚBLICA ───────────────────────────────────────────────────────────

    @classmethod
    def get_station_tip(cls, station_name):
        """Devuelve foco técnico y estrategia para mostrar antes de ejecutar."""
        key = cls._resolve(station_name)
        if not key:
            return None
        data = cls.STATIONS[key]
        return {
            "display_name": data["display_name"],
            "technical_focus": data["technical_focus"],
            "strategy": data["strategy"],
            "common_mistakes": data["common_mistakes"],
            "description": data.get("description", ""),
            "positions": data.get("positions", []),
            "rules": data.get("rules", []),
            "weights": data.get("weights", {}),
        }

    @classmethod
    def get_diagnosis(cls, station_name, context=None):
        """Devuelve diagnóstico textual según el contexto (interferencia, rpe, tiempo)."""
        key = cls._resolve(station_name)
        if not key:
            return None
        diagnosis = cls.STATIONS[key]["diagnosis"]
        if context is None:
            return diagnosis.get("general")
        if context.get("is_interference"):
            return diagnosis.get("high_if")
        if context.get("rpe", 0) >= 8:
            return diagnosis.get("high_rpe")
        return diagnosis.get("slow_time", diagnosis.get("general"))

    @classmethod
    def get_corrective_session(cls, station_name):
        """Devuelve lista de actividades para el override engine."""
        key = cls._resolve(station_name)
        if not key:
            return None
        return cls.STATIONS[key].get("corrective_activities")

    @classmethod
    def get_common_mistakes(cls, station_name):
        key = cls._resolve(station_name)
        if not key:
            return []
        return cls.STATIONS[key].get("common_mistakes", [])

    @classmethod
    def is_hyrox_station(cls, station_name):
        return cls._resolve(station_name) is not None

    @classmethod
    def get_feedback_diagnosis(cls, station_name, pausas=None, fallos=None, sensacion=None):
        """
        Genera diagnóstico accionable basado en el feedback post-entreno del usuario.
        Devuelve dict con 'resumen' (frase) y 'proxima_vez' (corrección concreta).
        """
        key = cls._resolve(station_name)
        if not key:
            return None
        data = cls.STATIONS[key]
        display = data['display_name']
        diag = data['diagnosis']
        corrective = data['corrective_work']

        # Determinar causa principal
        if sensacion == 'muy mala' or (pausas == '3+'):
            causa = diag.get('high_rpe') or diag.get('high_if')
        elif sensacion == 'torpe' or (pausas == '1-2') or (fallos and len(fallos) >= 2):
            causa = diag.get('high_if') or diag.get('slow_time')
        else:
            causa = diag.get('slow_time') or diag.get('general')

        # Construir resumen de problemas detectados
        problemas = []
        if pausas and pausas != '0':
            problemas.append(f"{'muchas' if pausas == '3+' else 'algunas'} pausas")
        if fallos:
            _labels = {'respiracion': 'respiración', 'brazos': 'brazos', 'piernas': 'piernas',
                       'tecnica': 'técnica', 'ritmo': 'ritmo', 'no_se': 'causa incierta'}
            problemas.append(' y '.join(_labels.get(f, f) for f in fallos[:2]))
        if sensacion and sensacion != 'fluida':
            problemas.append(f"sensación {sensacion}")

        resumen = f"{display} salió pesado" + (f" por {', '.join(problemas)}" if problemas else "") + "."
        proxima_vez = corrective[0] if corrective else f"Trabaja técnica básica de {display}."

        return {
            'display_name': display,
            'resumen': resumen,
            'proxima_vez': f"Próxima vez: {proxima_vez}",
            'causa': causa,
        }
