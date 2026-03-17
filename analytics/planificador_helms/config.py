# planificador_helms/config.py
"""
Configuración centralizada del Planificador Helms.
Todas las constantes y parámetros configurables del sistema.
"""

# ============================================================
# FACTORES DE PROGRESIÓN
# ============================================================
PROGRESION = {
    'porcentual': 1.05,  # Incremento del 5% para ejercicios pesados
    'fijo_pequeno': 1.25,  # Incremento de 1.25kg para ejercicios ligeros
    'fijo_grande': 2.5,  # Incremento de 2.5kg para ejercicios pesados
    'umbral_ejercicio_pesado': 50  # kg - umbral para considerar un ejercicio "pesado"
}

# ============================================================
# REDONDEO DE PESOS POR TIPO DE CARGA
# ============================================================
REDONDEO = {
    'barra': 2.5,
    'mancuerna': 2.5,
    'maquina': 5.0,
    'cable': 5.0,
    'general': 2.5
}

# ============================================================
# LÍMITES DE FATIGA POR FASE
# ============================================================
LIMITES_FATIGA = {
    'hipertrofia': {
        'series_pesadas_max': 10,
        'bisagra_pesada_max': 3,
        'rodilla_pesada_max': 5
    },
    'hipertrofia_especifica': {
        'series_pesadas_max': 10,
        'bisagra_pesada_max': 3,
        'rodilla_pesada_max': 5
    },
    'hipertrofia_metabolica': {
        'series_pesadas_max': 10,
        'bisagra_pesada_max': 3,
        'rodilla_pesada_max': 5
    },
    'fuerza': {
        'series_pesadas_max': 16,
        'bisagra_pesada_max': 8,
        'rodilla_pesada_max': 10
    },
    'potencia': {
        'series_pesadas_max': 8,
        'bisagra_pesada_max': 3,
        'rodilla_pesada_max': 4
    },
    'descarga': {
        'series_pesadas_max': 6,
        'bisagra_pesada_max': 2,
        'rodilla_pesada_max': 3
    }
}

# ============================================================
# VOLÚMENES BASE POR NIVEL DE EXPERIENCIA
# ============================================================
VOLUMENES_BASE = {
    'principiante': {
        'pecho': 10, 'espalda': 12, 'hombros': 8, 'biceps': 6,
        'triceps': 6, 'cuadriceps': 12, 'isquios': 8, 'gluteos': 8,
        'gemelos': 6, 'core': 6, 'trapecios': 4, 'antebrazos': 2
    },
    'intermedio': {
        'pecho': 14, 'espalda': 16, 'hombros': 12, 'biceps': 8,
        'triceps': 8, 'cuadriceps': 16, 'isquios': 10, 'gluteos': 12,
        'gemelos': 8, 'core': 8, 'trapecios': 6, 'antebrazos': 4
    },
    'avanzado': {
        'pecho': 18, 'espalda': 20, 'hombros': 16, 'biceps': 12,
        'triceps': 12, 'cuadriceps': 20, 'isquios': 14, 'gluteos': 16,
        'gemelos': 12, 'core': 10, 'trapecios': 8, 'antebrazos': 6
    }
}

# ============================================================
# DEFAULTS DE 1RM POR EJERCICIO (kg)
# ============================================================
DEFAULTS_1RM = {
    'sentadilla': 120.0,
    'press banca': 90.0,
    'press militar': 55.0,
    'peso muerto': 140.0,
    'rumano': 125.0,
    'hip thrust': 160.0,
    'mancuerna': 60.0,  # Total para 2 mancuernas
    # Fallbacks por patrón
    'rodilla': 110.0,
    'bisagra': 120.0,
    'empuje_horizontal': 85.0,
    'empuje_vertical': 50.0,
    'traccion_horizontal': 80.0,
    'traccion_vertical': 80.0,
    'aislamiento': 45.0
}

# ============================================================
# TEMPOS POR OBJETIVO
# ============================================================
TEMPOS = {
    'hipertrofia': '2-0-X-0',
    'fuerza': '1-0-X-0',
    'potencia': '1-0-X-0',
    'resistencia': '1-0-1-0'
}

# ============================================================
# DESCANSOS POR TIPO DE EJERCICIO Y RPE
# ============================================================
DESCANSOS = {
    'principal': {
        'rpe_alto': 4,  # RPE >= 8
        'rpe_bajo': 3   # RPE < 8
    },
    'secundario': {
        'rpe_alto': 2,
        'rpe_bajo': 1
    }
}

# ============================================================
# TOPES DE SERIES POR TIPO DE EJERCICIO
# ============================================================
TOPES_SERIES = {
    'compuesto_principal': (3, 4),
    'compuesto_secundario': (2, 3),
    'aislamiento': (2, 3)
}

LIMITE_DURO_SERIES = 4  # Nunca más de 4 series por ejercicio en hipertrofia

# ============================================================
# LÍMITES DE SERIES POR SESIÓN
# ============================================================
LIMITES_SERIES_SESION = {
    'grupos_grandes': {  # pecho, espalda, cuadriceps, isquios, gluteos
        'min': 6,
        'max': 10
    },
    'grupos_pequenos': {  # bíceps, tríceps, hombros, gemelos, etc.
        'min': 4,
        'max': 8
    }
}

GRUPOS_GRANDES = {'pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos'}

# ============================================================
# KEYWORDS DE EJERCICIOS
# ============================================================
KEYWORDS_MANCUERNA = ['mancuerna', 'mancuernas', 'db ']
KEYWORDS_CABLE = ['polea', 'cable', 'jalón', 'jalon', 'pulley']
KEYWORDS_MAQUINA = ['máquina', 'maquina', 'smith', 'prensa', 'hack', 'multipower']
KEYWORDS_BARRA = ['barra', 'barbell']

KEYWORDS_VERTICAL = ['dominad', 'jalón', 'jalon']
KEYWORDS_HORIZONTAL = ['remo', 'polea baja', 'gironda', 'pendlay', 'mancuerna']

KEYWORDS_PRINCIPALES = [
    'sentadilla', 'peso muerto', 'press banca',
    'press militar', 'hip thrust', 'dominadas'
]

# ============================================================
# REGLAS DE BISAGRA
# ============================================================
BISAGRA_PESADAS = ['peso muerto', 'sumo', 'convencional']
BISAGRA_LIGERAS = ['rumano', 'buenos', 'good morning', 'hip thrust', 'hiperext']

MAX_DIAS_BISAGRA = {
    'descarga': 1,
    'potencia': 1,
    'hipertrofia': 2,
    'hipertrofia_especifica': 2,
    'hipertrofia_metabolica': 2,
    'fuerza': 2
}

# ============================================================
# DISTRIBUCIÓN DE DÍAS POR FRECUENCIA
# ============================================================
DISTRIBUCION_DIAS = {
    3: {  # Push/Pull/Legs
        'dia_1': ['pecho', 'hombros', 'triceps'],
        'dia_2': ['espalda', 'biceps'],
        'dia_3': ['cuadriceps', 'isquios', 'gluteos', 'gemelos']
    },
    4: {  # Upper/Lower
        'dia_1': ['pecho', 'hombros', 'triceps'],
        'dia_2': ['cuadriceps', 'isquios', 'gluteos'],
        'dia_3': ['espalda', 'biceps'],
        'dia_4': ['cuadriceps', 'isquios', 'gluteos', 'gemelos']
    },
    5: {  # Body Part Split
        'dia_1': ['pecho', 'triceps'],
        'dia_2': ['espalda', 'biceps', 'antebrazos'],
        'dia_3': ['cuadriceps', 'gemelos'],
        'dia_4': ['hombros', 'trapecios'],
        'dia_5': ['isquios', 'gluteos', 'core']
    }
}

# ============================================================
# PATRONES OBJETIVO POR GRUPO MUSCULAR
# ============================================================
PATRONES_OBJETIVO = {
    'espalda': {'traccion_vertical', 'traccion_horizontal'},
    'pecho': {'empuje_horizontal'},
    'hombros': {'empuje_vertical'},
    'cuadriceps': {'rodilla'},
    'isquios': {'bisagra'},
    'gluteos': {'bisagra'}
}
