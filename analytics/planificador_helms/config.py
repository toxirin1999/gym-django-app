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
    'maquina': 2.5,
    'cable': 2.5,
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
    # Mancuernas: peso por mancuerna (no total)
    'press mancuerna': 28.0,    # ~28kg/hand press
    'curl mancuerna': 18.0,     # ~18kg/hand curl
    'remo mancuerna': 30.0,     # ~30kg/hand row
    'mancuerna': 22.0,          # Fallback genérico por mancuerna
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
# UMBRALES DE EJERCICIO "PESADO" POR TIPO DE CARGA (kg 1RM)
# ============================================================
UMBRALES_PESADO = {
    'barra': 70,        # Barbell: pesado desde 70kg 1RM
    'mancuerna': 25,    # Dumbbell: pesado desde 25kg/hand
    'cable': 35,        # Cable: pesado desde 35kg
    'maquina': 50,      # Machine: pesado desde 50kg
    'general': 50,      # Fallback
}

# ============================================================
# TEMPOS POR OBJETIVO
# ============================================================
TEMPOS = {
    'hipertrofia': '2-0-X-0',
    'hipertrofia_especifica': '3-0-X-0',   # más TUT para especialización
    'hipertrofia_metabolica': '2-0-2-0',   # énfasis en fase concéntrica y excéntrica
    'fuerza': '1-0-X-0',
    'fuerza_hipertrofia': '2-0-X-0',
    'potencia': '1-0-X-0',
    'resistencia': '1-0-1-0',
    'descarga': '2-0-2-0',                 # movimiento controlado, sin explosividad
}

# ============================================================
# DESCANSOS POR TIPO DE EJERCICIO Y RPE
# ============================================================
DESCANSOS = {
    'principal': {
        'rpe_alto': 4,  # RPE >= 8
        'rpe_bajo': 3  # RPE < 8
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

LIMITE_DURO_SERIES = 4  # Código muerto — no se usa. El tope real es TOPE_SERIES_POR_EJERCICIO.

# ============================================================
# TOPE DE SERIES POR EJERCICIO SEGÚN FASE
# ============================================================
# Defensa en profundidad — un límite que casi nunca se activa.
# El techo real lo pone GestorFatiga (LIMITES_SERIES_SESION: grandes≤10,
# pequeños≤8). Para que GestorFatiga diferencie correctamente entre grupos
# grandes y pequeños, este tope debe quedar en o por encima del máximo de
# LIMITES_SERIES_SESION para grandes (10). Potencia y descarga son excepciones:
# ahí el volumen intencionalmente bajo sí necesita un tope restrictivo.
TOPE_SERIES_POR_EJERCICIO = {
    'hipertrofia':            10,
    'hipertrofia_especifica': 10,
    'hipertrofia_metabolica':  8,
    'fuerza':                  8,
    'potencia':                5,
    'descarga':                4,
}

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
# CAPACIDAD DE SERIES POR SESIÓN (presupuesto del asignador)
# ============================================================
# Máximo de series de trabajo que una sesión puede acumular sumando
# cap_sesion_para_grupo de los grupos asignados a ese día.
# Con 12 grupos y 5 días, 24 es insuficiente para lograr freq>1 en ningún
# grupo (5×24=120; min first-touches=106; quedan 14 series de slack que no
# alcanzan ni 2 grupos con cap=8). 36 da 5×36=180; slack=74 para 2ºs toques.
# Ajustable: subir para sesiones más largas, bajar para menos tiempo disponible.
CAPACIDAD_SERIES_DIA = 36

# ============================================================
# UMBRAL DE FUSIÓN DE SESIONES CORTAS
# ============================================================
# Si un día tiene menos de este número de series, el asignador
# intenta moverlo al día adyacente con más hueco.
UMBRAL_FUSION_SESION = 10

# ============================================================
# GRUPOS SINÉRGICOS — derivado de DISTRIBUCION_DIAS[5]
# ============================================================
# Preferencia BLANDA del asignador: un grupo prefiere estar en el
# mismo día que sus sinérgicos. No es una restricción dura.
# Estructura: lista de frozensets. Un grupo puede pertenecer solo
# a un conjunto (aislado de la tabla 5 días del split actual).
GRUPOS_SINERGICOS = [
    frozenset(['pecho', 'triceps']),
    frozenset(['espalda', 'biceps', 'antebrazos']),
    frozenset(['cuadriceps', 'gemelos']),
    frozenset(['hombros', 'trapecios']),
    frozenset(['isquios', 'gluteos', 'core']),
]

# ============================================================
# AJUSTE DE REPETICIONES PARA MÚSCULOS PEQUEÑOS
# La evidencia muestra que bíceps, tríceps, deltoides lateral,
# gemelos, core y antebrazos responden mejor a rangos de rep
# más altos que los músculos grandes (Schoenfeld et al., 2017).
# Este mapa traduce el rep_range del bloque al rango óptimo
# para músculos pequeños.
# ============================================================
REP_RANGE_AJUSTE_PEQUENOS = {
    '2-4':  '6-8',    # potencia → rango funcional para pequeños
    '3-5':  '8-12',   # fuerza → rango híbrido para pequeños
    '4-6':  '8-12',   # fuerza → mismo
    '8-10': '12-15',  # intensificación → bump clásico
    '8-12': '12-15',  # hipertrofia principal → óptimo para pequeños
    '10-12': '12-15', # acumulación → leve subida
    '12-15': '15-20', # metabólico → máximo pump para pequeños
}

GRUPOS_PEQUENOS = {
    'biceps', 'triceps', 'hombros', 'gemelos', 'core', 'trapecios', 'antebrazos'
}

# ============================================================
# ESCALERA DE REP_RANGE POR TOQUE INTRA-SEMANAL
# Toque 1 = identidad (dict vacío, sin remapeo).
# Toque 2 = un peldaño más ligero (más reps) sobre el rango base.
# Toque 3 = un peldaño más sobre toque 2, con techo idempotente en '15-20'.
# Claves: unión de salidas de REP_RANGE_AJUSTE_PEQUENOS + rangos directos
# de bloques grandes ('8-10', '10-12') — cubre todos los valores posibles
# que pueden llegar a derivar_rep_rpe_toque tanto de grupos pequeños
# (post-AJUSTE_PEQUENOS) como grandes (directo del bloque).
# Clave ausente = fallback seguro: el llamador devuelve el base sin cambio.
# ============================================================
REP_RANGE_TOQUE = {
    1: {},  # identidad — no se aplica ningún remapeo en toque 1
    2: {
        '6-8':   '8-10',
        '8-10':  '10-12',
        '8-12':  '12-15',
        '10-12': '12-15',
        '12-15': '15-20',
        '15-20': '15-20',  # techo idempotente
    },
    3: {
        '6-8':   '10-12',
        '8-10':  '12-15',
        '8-12':  '15-20',
        '10-12': '15-20',
        '12-15': '15-20',
        '15-20': '15-20',
    },
}

# ============================================================
# ROL DE CADA TOQUE INTRA-SEMANAL
# Define qué perfil biomecánico priorizar y en qué orden recorrer
# las categorías al construir candidatos para el toque.
# Toque 1: sin preferencia de perfil; prioriza compuestos principales
#          (comportamiento idéntico al sistema actual — invariante duro).
# Toque 2: perfil estirado (posición de máximo estiramiento bajo carga);
#          prioriza secundarios/aislamiento para no repetir el compuesto.
# Toque 3: perfil acortado (bombeo/contracción máxima);
#          prioriza aislamiento para máxima especificidad metabólica.
# ============================================================
ROL_TOQUE = {
    1: {
        'perfil_preferido': None,
        'orden_categoria': ('compuesto_principal', 'compuesto_secundario', 'aislamiento'),
    },
    2: {
        'perfil_preferido': 'estirado',
        'orden_categoria': ('variantes_compartidas', 'compuesto_secundario', 'aislamiento', 'compuesto_principal'),
    },
    3: {
        'perfil_preferido': 'acortado',
        'orden_categoria': ('aislamiento', 'compuesto_secundario', 'compuesto_principal'),
    },
}

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
    },
    6: {  # PPL × 2
        'dia_1': ['pecho', 'hombros', 'triceps'],
        'dia_2': ['espalda', 'biceps', 'antebrazos'],
        'dia_3': ['cuadriceps', 'isquios', 'gluteos', 'gemelos'],
        'dia_4': ['pecho', 'hombros', 'triceps'],
        'dia_5': ['espalda', 'biceps'],
        'dia_6': ['cuadriceps', 'isquios', 'gluteos', 'gemelos']
    }
}

# ============================================================
# PATRONES OBJETIVO POR GRUPO MUSCULAR
# ============================================================
# ============================================================
# EJERCICIOS COMODÍN SEGUROS (fallback bio-seguro universal)
# ============================================================
UNIVERSAL_SAFE_EXERCISE_NAMES = {'plancha (plank)', 'dead bug'}

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
