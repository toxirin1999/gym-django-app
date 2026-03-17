# planificador_helms/database/ejercicios.py
"""
Base de datos completa de ejercicios del sistema Helms.
Todos los ejercicios organizados por grupo muscular y tipo.
"""

from typing import Dict, List, Optional

# ============================================================
# BASE DE DATOS DE EJERCICIOS
# ============================================================
EJERCICIOS_DATABASE = {

    # =========================
    # PECHO — EMPUJE HORIZONTAL
    # =========================
    'pecho': {
        'compuesto_principal': [
            {'nombre': 'Press Banca con Barra', 'patron': 'empuje_horizontal', 'estabilidad': 'media',
             'perfil': 'media', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Press Inclinado con Barra', 'patron': 'empuje_horizontal', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Press Banca con Mancuernas', 'patron': 'empuje_horizontal', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Convergent Machine Press', 'patron': 'empuje_horizontal', 'estabilidad': 'alta',
             'perfil': 'acortado', 'posicion': 'sentado', 'cadena': 'abierta'},
        ],
        'compuesto_secundario': [
            {'nombre': 'Press Inclinado con Mancuernas', 'patron': 'empuje_horizontal', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Press Cerrado en Banca', 'patron': 'empuje_horizontal', 'estabilidad': 'media',
             'perfil': 'media', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Dips (Fondos en Pecho)', 'patron': 'empuje_horizontal', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada'},
        ],
        'aislamiento': [
            {'nombre': 'Aperturas con Mancuernas', 'patron': 'aislamiento', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Cruce de Poleas', 'patron': 'aislamiento', 'estabilidad': 'media', 'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Low-to-High Cable Fly', 'patron': 'aislamiento', 'estabilidad': 'media', 'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Pec Deck', 'patron': 'aislamiento', 'estabilidad': 'alta', 'perfil': 'acortado', 'posicion': 'sentado', 'cadena': 'abierta'},
        ]
    },

    # =========================
    # ESPALDA — TRACCIONES
    # =========================
    'espalda': {
        'compuesto_principal': [
            {'nombre': 'Dominadas (con lastre)', 'patron': 'traccion_vertical', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada'},
            {'nombre': 'Jalón al Pecho', 'patron': 'traccion_vertical', 'estabilidad': 'alta', 'perfil': 'estirado', 'posicion': 'sentado', 'cadena': 'abierta'},
            {'nombre': 'Jalon unilateral pecho', 'patron': 'traccion_vertical', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'sentado', 'cadena': 'abierta'},
            {'nombre': 'Remo con Barra (Pendlay)', 'patron': 'traccion_horizontal', 'estabilidad': 'baja',
             'perfil': 'media', 'posicion': 'pie', 'cadena': 'cerrada'},
            {'nombre': 'Remo pecho apoyado', 'patron': 'traccion_horizontal', 'estabilidad': 'alta',
             'perfil': 'acortado', 'posicion': 'tumbado', 'cadena': 'abierta'},
        ],
        'compuesto_secundario': [
            {'nombre': 'Remo con Mancuerna a una mano', 'patron': 'traccion_horizontal', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Remo en Polea Baja (Gironda)', 'patron': 'traccion_horizontal', 'estabilidad': 'media',
             'perfil': 'acortado', 'universal_safe': True, 'posicion': 'sentado', 'cadena': 'abierta'},
        ],
        'aislamiento': [
            {'nombre': 'Face Pulls', 'patron': 'traccion_horizontal', 'estabilidad': 'media', 'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Pull-over con Mancuerna', 'patron': 'traccion_vertical', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Jalon brazos rectos', 'patron': 'traccion_vertical', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'abierta'},
        ]
    },

    # =========================
    # HOMBROS — EMPUJE VERTICAL
    # =========================
    'hombros': {
        'compuesto_principal': [
            {'nombre': 'Press Militar con Barra (de pie)', 'patron': 'empuje_vertical', 'estabilidad': 'baja',
             'perfil': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Push Press', 'patron': 'empuje_vertical', 'estabilidad': 'baja', 'perfil': 'media',
             'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Press Militar con Mancuernas (sentado)', 'patron': 'empuje_vertical', 'estabilidad': 'media',
             'perfil': 'estirado', 'universal_safe': True, 'posicion': 'sentado', 'cadena': 'abierta'},
            {'nombre': 'Machine Shoulder Press', 'patron': 'empuje_vertical', 'estabilidad': 'alta',
             'perfil': 'acortado', 'posicion': 'sentado', 'cadena': 'abierta'},
        ],
        'compuesto_secundario': [
            {'nombre': 'Press Arnold', 'patron': 'empuje_vertical', 'estabilidad': 'baja', 'perfil': 'estirado', 'posicion': 'sentado', 'cadena': 'abierta'},
        ],
        'aislamiento': [
            {'nombre': 'Elevaciones Laterales con Mancuernas', 'patron': 'aislamiento', 'estabilidad': 'baja',
             'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Elevaciones Laterales en Polea', 'patron': 'aislamiento', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Y-Raises', 'patron': 'aislamiento', 'estabilidad': 'baja', 'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Elevaciones Frontales con Polea', 'patron': 'aislamiento', 'estabilidad': 'media',
             'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Pájaros (Bent Over Raises)', 'patron': 'aislamiento', 'estabilidad': 'baja',
             'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
        ]
    },

    # =========================
    # CUÁDRICEPS — RODILLA
    # =========================
    'cuadriceps': {
        'compuesto_principal': [
            {'nombre': 'Sentadilla Trasera con Barra', 'patron': 'rodilla', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_rodilla_profunda', 'impacto_vertical', 'carga_axial']},
            {'nombre': 'Sentadilla Frontal con Barra', 'patron': 'rodilla', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_rodilla_profunda', 'impacto_vertical', 'carga_axial']},
            {'nombre': 'Sentadilla Hack', 'patron': 'rodilla', 'estabilidad': 'alta', 'perfil': 'estirado',
             'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_rodilla_profunda', 'empuje_pierna', 'carga_distal_pierna']},
            {'nombre': 'Sentadilla Búlgara', 'patron': 'rodilla', 'estabilidad': 'baja', 'perfil': 'estirado',
             'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_rodilla_profunda', 'estabilidad_tobillo', 'impacto_vertical']},
        ],
        'compuesto_secundario': [
            {'nombre': 'Prensa de Piernas', 'patron': 'rodilla', 'estabilidad': 'alta', 'perfil': 'media',
             'posicion': 'tumbado', 'cadena': 'cerrada',
             'risk_tags': ['empuje_pierna', 'flexion_rodilla_profunda', 'carga_distal_pierna']},
            {'nombre': 'Zancadas con Mancuernas', 'patron': 'rodilla', 'estabilidad': 'baja', 'perfil': 'estirado',
             'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['estabilidad_tobillo', 'impacto_vertical', 'flexion_rodilla_profunda']},
        ],
        'aislamiento': [
            {'nombre': 'Extensiones de Cuádriceps en Máquina', 'patron': 'aislamiento', 'estabilidad': 'alta',
             'perfil': 'acortado', 'posicion': 'sentado', 'cadena': 'abierta',
             'risk_tags': []},
            {'nombre': 'Sissy Squat', 'patron': 'aislamiento', 'estabilidad': 'baja', 'perfil': 'estirado',
             'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_rodilla_profunda', 'estabilidad_tobillo']},
        ]
    },

    # =========================
    # ISQUIOS — BISAGRA
    # =========================
    'isquios': {
        'compuesto_principal': [
            {'nombre': 'Peso Muerto Rumano', 'patron': 'bisagra', 'estabilidad': 'media', 'perfil': 'estirado',
             'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['bisagra_cadera', 'carga_axial']},
            {'nombre': 'Buenos Días (Good Mornings)', 'patron': 'bisagra', 'estabilidad': 'baja', 'perfil': 'estirado',
             'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['bisagra_cadera', 'carga_axial']},
            {'nombre': 'Curl Nórdico (Nordic Hamstring Curl)', 'patron': 'flexion_rodilla', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'cerrada',
             'risk_tags': ['flexion_rodilla_profunda']},
        ],
        'compuesto_secundario': [
            {'nombre': 'Curl Femoral Tumbado', 'patron': 'aislamiento', 'estabilidad': 'alta', 'perfil': 'media',
             'posicion': 'tumbado', 'cadena': 'abierta',
             'risk_tags': []},
            {'nombre': 'Curl Femoral Sentado', 'patron': 'aislamiento', 'estabilidad': 'alta', 'perfil': 'estirado',
             'posicion': 'sentado', 'cadena': 'abierta',
             'risk_tags': []},
        ],
        'aislamiento': [
            {'nombre': 'Hiperextensiones Inversas', 'patron': 'bisagra', 'estabilidad': 'media', 'perfil': 'acortado',
             'risk_tags': []},
        ]
    },

    # =========================
    # GLÚTEOS — BISAGRA
    # =========================
    'gluteos': {
        'compuesto_principal': [
            {'nombre': 'Hip Thrust con Barra', 'patron': 'bisagra', 'estabilidad': 'media', 'perfil': 'acortado',
             'posicion': 'tumbado', 'cadena': 'cerrada',
             'risk_tags': ['bisagra_cadera']},
            {'nombre': 'Peso Muerto Sumo', 'patron': 'bisagra', 'estabilidad': 'media', 'perfil': 'estirado',
             'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['bisagra_cadera', 'carga_axial']},
        ],
        'compuesto_secundario': [
            {'nombre': 'Patada de Glúteo en Polea', 'patron': 'aislamiento', 'estabilidad': 'media',
             'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta',
             'risk_tags': []},
            {'nombre': 'Abducción de Cadera en Máquina', 'patron': 'aislamiento', 'estabilidad': 'alta',
             'perfil': 'acortado', 'posicion': 'sentado', 'cadena': 'abierta',
             'risk_tags': []},
        ],
        'aislamiento': []
    },

    # =========================
    # BÍCEPS
    # =========================
    'biceps': {
        'compuesto_principal': [],
        'compuesto_secundario': [
            {'nombre': 'Curl con Barra Z', 'patron': 'flexion_codo', 'estabilidad': 'media', 'perfil': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Curl Araña', 'patron': 'flexion_codo', 'estabilidad': 'alta', 'perfil': 'acortado', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Curl Inclinado con Mancuernas', 'patron': 'flexion_codo', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'sentado', 'cadena': 'abierta'},
            {'nombre': 'Bayesian Curl', 'patron': 'flexion_codo', 'estabilidad': 'media', 'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'abierta'},
        ],
        'aislamiento': [
            {'nombre': 'Curl de Concentración', 'patron': 'flexion_codo', 'estabilidad': 'baja', 'perfil': 'acortado', 'posicion': 'sentado', 'cadena': 'abierta'},
            {'nombre': 'Curl Martillo con Mancuernas', 'patron': 'flexion_codo', 'estabilidad': 'baja',
             'perfil': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Curl en Polea Alta', 'patron': 'flexion_codo', 'estabilidad': 'media', 'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
        ]
    },

    # =========================
    # TRÍCEPS
    # =========================
    'triceps': {
        'compuesto_principal': [
            {'nombre': 'Press Francés con Barra Z', 'patron': 'extension_codo', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Press Cerrado en Banca', 'patron': 'extension_codo', 'estabilidad': 'media', 'perfil': 'media', 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Fondos en Paralelas (con lastre)', 'patron': 'extension_codo', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada'},
            {'nombre': 'Katana Extensions', 'patron': 'extension_codo', 'estabilidad': 'media', 'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'abierta'},
        ],
        'compuesto_secundario': [
            {'nombre': 'Extensiones de Tríceps con Polea Alta', 'patron': 'extension_codo', 'estabilidad': 'media',
             'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Extensiones sobre la Cabeza con Mancuerna', 'patron': 'extension_codo', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'sentado', 'cadena': 'abierta'},
            {'nombre': 'Fondos entre Bancos', 'patron': 'extension_codo', 'estabilidad': 'media', 'perfil': 'media', 'posicion': 'pie', 'cadena': 'cerrada'},
            {'nombre': 'Patada de Tríceps con Polea', 'patron': 'extension_codo', 'estabilidad': 'media',
             'perfil': 'acortado', 'posicion': 'pie', 'cadena': 'abierta'},
        ],
        'aislamiento': []
    },

    # =========================
    # GEMELOS
    # =========================
    'gemelos': {
        'compuesto_principal': [
            {'nombre': 'Elevación de Gemelos de Pie (Máquina)', 'patron': 'gemelos', 'estabilidad': 'alta',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_plantar', 'carga_distal_pierna', 'estabilidad_gemelo']},
            {'nombre': 'Elevación de Gemelos en Prensa', 'patron': 'gemelos', 'estabilidad': 'alta',
             'perfil': 'estirado', 'posicion': 'tumbado', 'cadena': 'cerrada',
             'risk_tags': ['flexion_plantar', 'carga_distal_pierna', 'estabilidad_gemelo']},
        ],
        'compuesto_secundario': [
            {'nombre': 'Elevación de Gemelos Sentado (Máquina)', 'patron': 'gemelos', 'estabilidad': 'alta',
             'perfil': 'acortado', 'posicion': 'sentado', 'cadena': 'cerrada',
             'risk_tags': ['flexion_plantar', 'estabilidad_gemelo']},
        ],
        'aislamiento': [
            {'nombre': 'Elevación de Gemelos Unilateral (Mancuerna)', 'patron': 'gemelos', 'estabilidad': 'baja',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_plantar', 'estabilidad_tobillo', 'estabilidad_gemelo']},
            {'nombre': 'Elevación de Gemelos en Multipower', 'patron': 'gemelos', 'estabilidad': 'media',
             'perfil': 'estirado', 'posicion': 'pie', 'cadena': 'cerrada',
             'risk_tags': ['flexion_plantar', 'carga_distal_pierna', 'estabilidad_gemelo']},
        ]
    },

    # =========================
    # CORE
    # =========================
    'core': {
        'compuesto_principal': [
            {'nombre': 'Elevaciones de Piernas Colgado', 'patron': 'core', 'estabilidad': 'baja', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Crunch en Polea (Cable Crunch)', 'patron': 'core', 'estabilidad': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
        ],
        'compuesto_secundario': [
            {'nombre': 'Plancha (Plank)', 'patron': 'core', 'estabilidad': 'baja', 'universal_safe': True, 'posicion': 'tumbado', 'cadena': 'cerrada'},
            {'nombre': 'Pallof Press', 'patron': 'core', 'estabilidad': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
        ],
        'aislamiento': [
            {'nombre': 'Dead Bug', 'patron': 'core', 'estabilidad': 'baja', 'universal_safe': True, 'posicion': 'tumbado', 'cadena': 'abierta'},
            {'nombre': 'Ab Wheel (Rueda Abdominal)', 'patron': 'core', 'estabilidad': 'baja', 'posicion': 'tumbado', 'cadena': 'cerrada'},
        ]
    },

    # =========================
    # TRAPECIOS
    # =========================
    'trapecios': {
        'compuesto_principal': [
            {'nombre': 'Encogimientos con Barra', 'patron': 'trapecio', 'estabilidad': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Encogimientos con Mancuernas', 'patron': 'trapecio', 'estabilidad': 'baja', 'posicion': 'pie', 'cadena': 'abierta'},
        ],
        'compuesto_secundario': [
            {'nombre': 'Farmer Walk (Paseo del Granjero)', 'patron': 'agarre', 'estabilidad': 'baja', 'posicion': 'pie', 'cadena': 'cerrada'},
        ],
        'aislamiento': [
            {'nombre': 'Face Pull', 'patron': 'traccion_horizontal', 'estabilidad': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Remo al Mentón con Polea (Upright Row)', 'patron': 'trapecio', 'estabilidad': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
        ]
    },

    # =========================
    # ANTEBRAZOS
    # =========================
    'antebrazos': {
        'compuesto_principal': [],
        'compuesto_secundario': [
            {'nombre': 'Farmer Walk (Paseo del Granjero)', 'patron': 'agarre', 'estabilidad': 'baja', 'posicion': 'pie', 'cadena': 'cerrada'},
            {'nombre': 'Aguante en Barra (Dead Hang)', 'patron': 'agarre', 'estabilidad': 'media', 'posicion': 'pie', 'cadena': 'cerrada'},
        ],
        'aislamiento': [
            {'nombre': 'Curl de Muñeca (Wrist Curl)', 'patron': 'antebrazo', 'estabilidad': 'media', 'posicion': 'sentado', 'cadena': 'abierta'},
            {'nombre': 'Curl Inverso con Barra', 'patron': 'antebrazo', 'estabilidad': 'media', 'posicion': 'pie', 'cadena': 'abierta'},
            {'nombre': 'Extensión de Muñeca (Reverse Wrist Curl)', 'patron': 'antebrazo', 'estabilidad': 'media', 'posicion': 'sentado', 'cadena': 'abierta'},
        ]
    },
    # =========================
    # HYROX STATIONS
    # =========================
    'hyrox': {
        'compuesto_principal': [
            {'nombre': 'SkiErg', 'patron': 'traccion_vertical', 'risk_tags': ['flexion_plantar']},
            {'nombre': 'Sled Push', 'patron': 'rodilla', 'risk_tags': ['empuje_pierna', 'carga_distal_pierna']},
            {'nombre': 'Sled Pull', 'patron': 'bisagra', 'risk_tags': ['bisagra_cadera', 'traccion_horizontal']},
            {'nombre': 'Burpee Broad Jump', 'patron': 'pleometrico', 'risk_tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'triple_extension_explosiva']},
            {'nombre': 'Rowing', 'patron': 'traccion_horizontal', 'risk_tags': ['bisagra_cadera']},
            {'nombre': 'Farmers Carry', 'patron': 'agarre', 'risk_tags': ['carga_axial', 'estabilidad_tobillo']},
            {'nombre': 'Sandbag Lunges', 'patron': 'rodilla', 'risk_tags': ['impacto_vertical', 'flexion_rodilla_profunda', 'estabilidad_tobillo']},
            {'nombre': 'Wall Balls', 'patron': 'rodilla', 'risk_tags': ['impacto_vertical', 'flexion_rodilla_profunda']},
        ],
        'compuesto_secundario': [],
        'aislamiento': []
    },
}


# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def obtener_grupo_muscular(nombre_ejercicio: str) -> str:
    """
    Obtiene el grupo muscular de un ejercicio dado su nombre.
    Busca en toda la base de datos y devuelve el primer grupo que lo contiene.

    Args:
        nombre_ejercicio: Nombre del ejercicio a buscar

    Returns:
        str: Nombre del grupo muscular ('pecho', 'espalda', etc.) o 'otros' si no se encuentra

    Ejemplo:
        >>> obtener_grupo_muscular('Press Banca con Barra')
        'pecho'
        >>> obtener_grupo_muscular('Dominadas (con lastre)')
        'espalda'
    """
    nombre_normalizado = nombre_ejercicio.strip().lower()

    for grupo_muscular, categorias in EJERCICIOS_DATABASE.items():
        for categoria, ejercicios in categorias.items():
            for ejercicio in ejercicios:
                ej_nombre = ejercicio.get('nombre', '').strip().lower() if isinstance(ejercicio, dict) else str(
                    ejercicio).strip().lower()
                if ej_nombre == nombre_normalizado:
                    return grupo_muscular

    return 'otros'


def obtener_todos_ejercicios_por_grupo(grupo_muscular: str) -> List[Dict[str, str]]:
    """
    Devuelve todos los ejercicios de un grupo muscular específico.

    Args:
        grupo_muscular: Nombre del grupo muscular

    Returns:
        List[Dict]: Lista de diccionarios con ejercicios del grupo

    Ejemplo:
        >>> obtener_todos_ejercicios_por_grupo('pecho')
        [{'nombre': 'Press Banca con Barra', 'patron': 'empuje_horizontal'}, ...]
    """
    if grupo_muscular not in EJERCICIOS_DATABASE:
        return []

    todos_los_ejercicios = []
    for categoria, ejercicios in EJERCICIOS_DATABASE[grupo_muscular].items():
        todos_los_ejercicios.extend(ejercicios)

    return todos_los_ejercicios


def crear_mapeo_inverso() -> Dict[str, str]:
    """
    Crea un mapeo inverso: ejercicio -> grupo_muscular.
    Útil para búsquedas rápidas.

    Returns:
        dict: {nombre_ejercicio_normalizado: grupo_muscular}

    Ejemplo:
        >>> mapeo = crear_mapeo_inverso()
        >>> mapeo['press banca con barra']
        'pecho'
    """
    mapeo = {}
    for grupo_muscular, categorias in EJERCICIOS_DATABASE.items():
        for categoria, ejercicios in categorias.items():
            for ejercicio in ejercicios:
                nombre = ejercicio.get('nombre', '').strip().lower() if isinstance(ejercicio, dict) else str(
                    ejercicio).strip().lower()
                if nombre:
                    mapeo[nombre] = grupo_muscular
    return mapeo


# Cache del mapeo inverso para evitar recalcularlo
_MAPEO_INVERSO_CACHE: Optional[Dict[str, str]] = None


def obtener_mapeo_inverso() -> Dict[str, str]:
    """
    Obtiene el mapeo inverso (con cache).
    
    Returns:
        dict: Mapeo de ejercicio -> grupo muscular
    """
    global _MAPEO_INVERSO_CACHE
    if _MAPEO_INVERSO_CACHE is None:
        _MAPEO_INVERSO_CACHE = crear_mapeo_inverso()
    return _MAPEO_INVERSO_CACHE
