"""
Base de equivalencias de alimentos en Bloques Zone.
─────────────────────────────────────────────────────
1 Bloque Proteína (P) = 7g proteína neta
1 Bloque Carbos    (C) = 9g carbos netos
1 Bloque Grasa     (G) = 3g grasa

Formato de cada alimento:
{
    "id":            str   — identificador único
    "nombre":        str   — nombre mostrado al usuario
    "categoria":     str   — "proteina" | "carbo" | "grasa" | "verdura"
    "cantidad_g":    float — gramos para 1 bloque de la categoría principal
    "medida_casa":   str   — medida casera equivalente
    "P": int   — bloques de proteína que aporta (sistema original)
    "C": int   — bloques de carbos que aporta
    "G": int   — bloques de grasa que aporta
    "nota": str    — aviso al usuario

    — Campos ACN (Algoritmo de Conversión Nutricional) ─────────────
    "macros_100g":   dict  — {p, h, g, fibra} por 100g en estado_ref
    "estado_ref":    str   — "crudo" | "cocinado" | "directo"
    "factor_coccion": float|None — ratio cocinado/crudo (si aplica)
    "cooking_modes": list|None — ["crudo","cocinado"] si hay conversión
    "tags":          list  — ["fuel"] | ["repair"] | ["rest"]
    "calidad":       str   — "verde" (natural) | "gris" (procesado)
}

Tags de momento:
  [fuel]   → carbos de alto IG, energía rápida — antes de Hyrox/HIIT
  [repair] → proteínas de absorción rápida — después del gym
  [rest]   → grasas saludables, fibra, bajo IG — días de descanso

Calidad de bloque:
  verde → fuente natural, mínimamente procesada
  gris  → fuente procesada (impacto inflamatorio mayor)

Reglas ACN:
  A. Descuento grasa oculta — los bloques G del alimento se restan del cupo G del plato
  B. Factor de cocción     — si cooking_modes existe, ajusta el peso antes de calcular
  C. Cap de fibra          — si fibra/h > 0.5 (por 100g), los carbos no cuentan como bloques C
"""

PROTEINAS = [
    # ── Carnes magras ─────────────────────────────────────────────────────
    {
        "id": "pollo_pechuga", "nombre": "Pechuga de pollo (cocida)",
        "categoria": "proteina", "cantidad_g": 30, "medida_casa": "tamaño de la palma",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 23, "h": 0, "g": 1.5, "fibra": 0},
        "estado_ref": "cocinado", "factor_coccion": 0.8,
        "cooking_modes": ["cocinado", "crudo"],
        "tags": ["repair"], "calidad": "verde",
    },
    {
        "id": "pavo_pechuga", "nombre": "Pechuga de pavo (cocida)",
        "categoria": "proteina", "cantidad_g": 30, "medida_casa": "tamaño de la palma",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 24, "h": 0, "g": 1, "fibra": 0},
        "estado_ref": "cocinado", "factor_coccion": 0.8,
        "cooking_modes": ["cocinado", "crudo"],
        "tags": ["repair"], "calidad": "verde",
    },
    {
        "id": "ternera_magra", "nombre": "Ternera magra (solomillo)",
        "categoria": "proteina", "cantidad_g": 30, "medida_casa": "tamaño de la palma",
        "P": 1, "C": 0, "G": 1, "nota": "⚠ Contiene grasa — descuenta 1 bloque G",
        "macros_100g": {"p": 22, "h": 0, "g": 5, "fibra": 0},
        "estado_ref": "crudo", "factor_coccion": 0.75,
        "cooking_modes": ["crudo", "cocinado"],
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    # ── Pescados ──────────────────────────────────────────────────────────
    {
        "id": "atun_natural", "nombre": "Atún al natural (lata)",
        "categoria": "proteina", "cantidad_g": 30, "medida_casa": "½ lata pequeña",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 25, "h": 0, "g": 1, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    {
        "id": "salmon", "nombre": "Salmón (fresco)",
        "categoria": "proteina", "cantidad_g": 30, "medida_casa": "tamaño de la palma",
        "P": 1, "C": 0, "G": 1, "nota": "⚠ Rico en omega-3 — descuenta 1 bloque G",
        "macros_100g": {"p": 20, "h": 0, "g": 12, "fibra": 0},
        "estado_ref": "crudo", "factor_coccion": 0.8,
        "cooking_modes": ["crudo", "cocinado"],
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    {
        "id": "merluza", "nombre": "Merluza / Bacalao",
        "categoria": "proteina", "cantidad_g": 40, "medida_casa": "tamaño de la palma",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 17, "h": 0, "g": 1.5, "fibra": 0},
        "estado_ref": "crudo", "factor_coccion": 0.8,
        "cooking_modes": ["crudo", "cocinado"],
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    {
        "id": "sardinas_lata", "nombre": "Sardinas en aceite de oliva",
        "categoria": "proteina", "cantidad_g": 35, "medida_casa": "3 sardinas",
        "P": 1, "C": 0, "G": 1, "nota": "⚠ Contiene grasa — descuenta 1 bloque G",
        "macros_100g": {"p": 20, "h": 0, "g": 9, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    # ── Huevos y lácteos ──────────────────────────────────────────────────
    {
        "id": "huevo_entero", "nombre": "Huevo entero (L)",
        "categoria": "proteina", "cantidad_g": 75, "medida_casa": "1 huevo grande",
        "P": 1, "C": 0, "G": 1, "nota": "⚠ Yema = 1 bloque G — descuenta automáticamente",
        "macros_100g": {"p": 13, "h": 1, "g": 11, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    {
        "id": "clara_huevo", "nombre": "Clara de huevo",
        "categoria": "proteina", "cantidad_g": 50, "medida_casa": "2 claras",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 11, "h": 0.7, "g": 0.2, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair"], "calidad": "verde",
    },
    {
        "id": "queso_cottage", "nombre": "Queso cottage 0%",
        "categoria": "proteina", "cantidad_g": 55, "medida_casa": "3 cucharadas",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 11, "h": 3, "g": 4, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    {
        "id": "griego_0", "nombre": "Yogur griego 0% proteína",
        "categoria": "proteina", "cantidad_g": 90, "medida_casa": "½ tarrina",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 10, "h": 4, "g": 0.5, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    # ── Proteína vegetal ──────────────────────────────────────────────────
    {
        "id": "tofu_firme", "nombre": "Tofu firme",
        "categoria": "proteina", "cantidad_g": 80, "medida_casa": "cubo 5x5cm",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 8, "h": 2, "g": 4, "fibra": 0.3},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair", "rest"], "calidad": "verde",
    },
    {
        "id": "lentejas_cocidas", "nombre": "Lentejas cocidas",
        "categoria": "proteina", "cantidad_g": 75, "medida_casa": "½ taza",
        "P": 1, "C": 1, "G": 0, "nota": "⚠ Legumbre: contiene 1 bloque C — descuenta automáticamente",
        "macros_100g": {"p": 9, "h": 14, "g": 0.5, "fibra": 8},
        "estado_ref": "cocinado", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "garbanzos_cocidos", "nombre": "Garbanzos cocidos",
        "categoria": "proteina", "cantidad_g": 70, "medida_casa": "½ taza",
        "P": 1, "C": 1, "G": 0, "nota": "⚠ Legumbre: contiene 1 bloque C — descuenta automáticamente",
        "macros_100g": {"p": 9, "h": 16, "g": 2, "fibra": 6},
        "estado_ref": "cocinado", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    # ── Suplementos ───────────────────────────────────────────────────────
    {
        "id": "whey_protein", "nombre": "Proteína whey en polvo",
        "categoria": "proteina", "cantidad_g": 10, "medida_casa": "1/3 cacito",
        "P": 1, "C": 0, "G": 0, "nota": "",
        "macros_100g": {"p": 80, "h": 5, "g": 3, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["repair"], "calidad": "gris",
    },
]

CARBOS = [
    # ── Cereales y almidones ──────────────────────────────────────────────
    {
        "id": "arroz_blanco_seco", "nombre": "Arroz blanco (crudo)",
        "categoria": "carbo", "cantidad_g": 15, "medida_casa": "1 cucharada rasa",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 7, "h": 77, "g": 0.7, "fibra": 0.5},
        "estado_ref": "crudo", "factor_coccion": 3.0,
        "cooking_modes": ["crudo", "cocinado"],
        "tags": ["fuel"], "calidad": "verde",
    },
    {
        "id": "arroz_cocido", "nombre": "Arroz blanco (cocido)",
        "categoria": "carbo", "cantidad_g": 45, "medida_casa": "3 cucharadas",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 2.5, "h": 28, "g": 0.3, "fibra": 0.4},
        "estado_ref": "cocinado", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel"], "calidad": "verde",
    },
    {
        "id": "avena_cruda", "nombre": "Avena (copos, cruda)",
        "categoria": "carbo", "cantidad_g": 27, "medida_casa": "3 cucharadas",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 14, "h": 58, "g": 7, "fibra": 11},
        "estado_ref": "crudo", "factor_coccion": 2.0,
        "cooking_modes": ["crudo", "cocinado"],
        "tags": ["fuel", "rest"], "calidad": "verde",
    },
    {
        "id": "pasta_seca", "nombre": "Pasta (seca, cualquier tipo)",
        "categoria": "carbo", "cantidad_g": 15, "medida_casa": "1 cucharada",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 13, "h": 68, "g": 1.5, "fibra": 2.5},
        "estado_ref": "crudo", "factor_coccion": 2.5,
        "cooking_modes": ["crudo", "cocinado"],
        "tags": ["fuel"], "calidad": "verde",
    },
    {
        "id": "pasta_cocida", "nombre": "Pasta (cocida)",
        "categoria": "carbo", "cantidad_g": 45, "medida_casa": "3 cucharadas",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 5, "h": 25, "g": 1, "fibra": 1.5},
        "estado_ref": "cocinado", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel"], "calidad": "verde",
    },
    {
        "id": "boniato_cocido", "nombre": "Boniato / Batata (cocido)",
        "categoria": "carbo", "cantidad_g": 75, "medida_casa": "½ boniato mediano",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 1.5, "h": 18, "g": 0.1, "fibra": 2.5},
        "estado_ref": "cocinado", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel", "rest"], "calidad": "verde",
    },
    {
        "id": "patata_cocida", "nombre": "Patata (cocida)",
        "categoria": "carbo", "cantidad_g": 75, "medida_casa": "1 patata pequeña",
        "P": 0, "C": 1, "G": 0, "nota": "Potasio anti-calambres",
        "macros_100g": {"p": 2, "h": 17, "g": 0.1, "fibra": 2},
        "estado_ref": "cocinado", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel"], "calidad": "verde",
    },
    {
        "id": "pan_integral", "nombre": "Pan integral",
        "categoria": "carbo", "cantidad_g": 20, "medida_casa": "1 rebanada fina",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 9, "h": 41, "g": 3, "fibra": 6},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel"], "calidad": "gris",
    },
    # ── Frutas ────────────────────────────────────────────────────────────
    {
        "id": "manzana", "nombre": "Manzana",
        "categoria": "carbo", "cantidad_g": 100, "medida_casa": "½ manzana mediana",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 0.3, "h": 12, "g": 0.2, "fibra": 2.4},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest", "fuel"], "calidad": "verde",
    },
    {
        "id": "platano", "nombre": "Plátano",
        "categoria": "carbo", "cantidad_g": 70, "medida_casa": "½ plátano",
        "P": 0, "C": 1, "G": 0, "nota": "Ideal pre-Hyrox por índice glucémico",
        "macros_100g": {"p": 1.1, "h": 23, "g": 0.3, "fibra": 2.6},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel"], "calidad": "verde",
    },
    {
        "id": "naranja", "nombre": "Naranja",
        "categoria": "carbo", "cantidad_g": 120, "medida_casa": "1 naranja pequeña",
        "P": 0, "C": 1, "G": 0, "nota": "",
        "macros_100g": {"p": 0.9, "h": 9, "g": 0.2, "fibra": 2.4},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "fresas", "nombre": "Fresas / Arándanos",
        "categoria": "carbo", "cantidad_g": 150, "medida_casa": "1 taza",
        "P": 0, "C": 1, "G": 0, "nota": "Bajo índice glucémico — buena opción días descanso",
        "macros_100g": {"p": 0.7, "h": 7, "g": 0.3, "fibra": 2},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    # ── Bebidas deportivas ────────────────────────────────────────────────
    {
        "id": "maltodextrina", "nombre": "Maltodextrina / Dextrina",
        "categoria": "carbo", "cantidad_g": 10, "medida_casa": "1 cucharadita",
        "P": 0, "C": 1, "G": 0, "nota": "Solo pre/intra-Hyrox. Absorción rápida.",
        "macros_100g": {"p": 0, "h": 95, "g": 0, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel"], "calidad": "gris",
    },
    {
        "id": "isotonica", "nombre": "Bebida isotónica",
        "categoria": "carbo", "cantidad_g": 0, "medida_casa": "200 ml",
        "P": 0, "C": 1, "G": 0, "nota": "Solo intra-entrenamiento Hyrox",
        "macros_100g": {"p": 0, "h": 7, "g": 0, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["fuel"], "calidad": "gris",
    },
]

GRASAS = [
    {
        "id": "aceite_oliva", "nombre": "Aceite de oliva virgen extra",
        "categoria": "grasa", "cantidad_g": 3, "medida_casa": "1 cucharadita rasa",
        "P": 0, "C": 0, "G": 1, "nota": "",
        "macros_100g": {"p": 0, "h": 0, "g": 100, "fibra": 0},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "aguacate", "nombre": "Aguacate",
        "categoria": "grasa", "cantidad_g": 15, "medida_casa": "1 cucharada / 3 rodajas",
        "P": 0, "C": 0, "G": 1, "nota": "",
        "macros_100g": {"p": 2, "h": 2, "g": 15, "fibra": 7},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "almendras", "nombre": "Almendras",
        "categoria": "grasa", "cantidad_g": 6, "medida_casa": "5-6 unidades",
        "P": 0, "C": 0, "G": 1, "nota": "",
        "macros_100g": {"p": 21, "h": 6, "g": 52, "fibra": 12},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "nueces", "nombre": "Nueces",
        "categoria": "grasa", "cantidad_g": 5, "medida_casa": "2 mitades",
        "P": 0, "C": 0, "G": 1, "nota": "Ricas en omega-3 — soporte nervioso",
        "macros_100g": {"p": 15, "h": 4, "g": 65, "fibra": 6.7},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "mantequilla_cacahuete", "nombre": "Mantequilla de cacahuete (natural)",
        "categoria": "grasa", "cantidad_g": 5, "medida_casa": "1 cucharadita rasa",
        "P": 0, "C": 0, "G": 1, "nota": "",
        "macros_100g": {"p": 25, "h": 20, "g": 50, "fibra": 5},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "gris",
    },
    {
        "id": "aceitunas", "nombre": "Aceitunas",
        "categoria": "grasa", "cantidad_g": 9, "medida_casa": "3 aceitunas grandes",
        "P": 0, "C": 0, "G": 1, "nota": "",
        "macros_100g": {"p": 0.8, "h": 1, "g": 11, "fibra": 3.2},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "semillas_chia", "nombre": "Semillas de chía / lino",
        "categoria": "grasa", "cantidad_g": 5, "medida_casa": "1 cucharadita",
        "P": 0, "C": 0, "G": 1, "nota": "Aportan omega-3 y fibra",
        "macros_100g": {"p": 17, "h": 2, "g": 31, "fibra": 34},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
]

VERDURAS = [
    # Las verduras no tienen bloques estrictos — siempre son libres (hasta 3 puños)
    # Regla C ACN: fibra/h > 0.5 → hidratos ignorados en conteo de bloques
    {
        "id": "brocoli", "nombre": "Brócoli",
        "categoria": "verdura", "cantidad_g": 200, "medida_casa": "1 puño grande",
        "P": 0, "C": 0, "G": 0, "nota": "Libre — sin límite de bloques",
        "macros_100g": {"p": 2.8, "h": 4, "g": 0.4, "fibra": 2.6},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "espinacas", "nombre": "Espinacas / Rúcula",
        "categoria": "verdura", "cantidad_g": 200, "medida_casa": "2 puños",
        "P": 0, "C": 0, "G": 0, "nota": "Libre — sin límite de bloques",
        "macros_100g": {"p": 2.9, "h": 1.4, "g": 0.4, "fibra": 2.2},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "pimiento", "nombre": "Pimiento / Pepino / Tomate",
        "categoria": "verdura", "cantidad_g": 150, "medida_casa": "1 pieza mediana",
        "P": 0, "C": 0, "G": 0, "nota": "Libre — sin límite de bloques",
        "macros_100g": {"p": 1, "h": 6, "g": 0.3, "fibra": 2},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
    {
        "id": "zanahoria", "nombre": "Zanahoria",
        "categoria": "verdura", "cantidad_g": 100, "medida_casa": "1 zanahoria",
        "P": 0, "C": 0, "G": 0, "nota": "Libre — sin límite de bloques",
        "macros_100g": {"p": 0.9, "h": 9, "g": 0.2, "fibra": 2.8},
        "estado_ref": "directo", "factor_coccion": None,
        "cooking_modes": None,
        "tags": ["rest"], "calidad": "verde",
    },
]

# ─── Índice por id ────────────────────────────────────────────────────────────
TODOS_LOS_ALIMENTOS = {
    a["id"]: a
    for a in (PROTEINAS + CARBOS + GRASAS + VERDURAS)
}

# ─── Constantes del sistema de bloques ────────────────────────────────────────
GRAMOS_POR_BLOQUE = {
    "P": 7,   # gramos de proteína por bloque
    "C": 9,   # gramos de carbos netos por bloque
    "G": 3,   # gramos de grasa por bloque
}

# Ratio bloques C y G respecto a P según tipo de sesión
RATIO_SESION = {
    # tipo_sesion: {"C": multiplicador, "G": multiplicador}
    "hyrox":    {"C": 2.0, "G": 0.5},
    "gym":      {"C": 1.0, "G": 1.0},
    "descanso": {"C": 0.5, "G": 1.2},
}

# Ratio proteína (g / kg masa magra) según fase
PROTEINA_RATIO_FASE = {
    "definicion":    2.2,
    "volumen":       2.0,
    "peak_week":     2.4,
    "mantenimiento": 1.8,
}

# Bonus de doble sesión (actividad física x2 en el mismo día)
DOBLE_SESION_BONUS = {"C": 2, "P": 1, "G": 0}


def calcular_bloques_dia(lean_mass_kg: float, fase: str, tipo_sesion: str) -> dict:
    """
    Devuelve el número de bloques P/C/G para un día dado.

    Args:
        lean_mass_kg: masa magra en kg
        fase:         'definicion' | 'volumen' | 'peak_week' | 'mantenimiento'
        tipo_sesion:  'gym' | 'hyrox' | 'descanso'

    Returns:
        {'P': int, 'C': int, 'G': int, 'P_g': int, 'C_g': int, 'G_g': int}
    """
    ratio_p = PROTEINA_RATIO_FASE.get(fase, 1.8)
    proteina_g = lean_mass_kg * ratio_p
    bloques_p = max(1, round(proteina_g / GRAMOS_POR_BLOQUE["P"]))

    ratio = RATIO_SESION.get(tipo_sesion, RATIO_SESION["descanso"])
    bloques_c = max(1, round(bloques_p * ratio["C"]))
    bloques_g = max(1, round(bloques_p * ratio["G"]))

    return {
        "P": bloques_p,
        "C": bloques_c,
        "G": bloques_g,
        "P_g": bloques_p * GRAMOS_POR_BLOQUE["P"],
        "C_g": bloques_c * GRAMOS_POR_BLOQUE["C"],
        "G_g": bloques_g * GRAMOS_POR_BLOQUE["G"],
    }


def calcular_bloques_acn(alimento_id: str, peso_g: float, estado: str = None) -> dict:
    """
    Algoritmo de Conversión Nutricional (ACN).
    Convierte peso en gramos → bloques P/C/G con reglas científicas.

    Regla A: El descuento de grasa oculta ya queda implícito en los bloques G calculados.
    Regla B: Factor de cocción — ajusta el peso al estado de referencia.
    Regla C: Cap de fibra — si fibra/h > 0.5, los carbos no cuentan como bloques.

    Args:
        alimento_id: id del alimento (clave en TODOS_LOS_ALIMENTOS)
        peso_g:      gramos introducidos por el usuario
        estado:      'crudo' | 'cocinado' | None (usa estado_ref del alimento)

    Returns:
        {
            'P': float, 'C': float, 'G': float,
            'fiber_capped': bool,
            'cooking_adjusted': bool,
            'nota': str,
        }
    """
    alimento = TODOS_LOS_ALIMENTOS.get(alimento_id)
    if not alimento or not alimento.get("macros_100g"):
        return {"P": 0, "C": 0, "G": 0, "fiber_capped": False, "cooking_adjusted": False, "nota": ""}

    m = alimento["macros_100g"]
    estado_ref = alimento.get("estado_ref", "directo")
    factor = alimento.get("factor_coccion")
    cooking_adjusted = False

    # ── Regla B: Factor de cocción ──────────────────────────────────────
    peso_efectivo = peso_g
    if factor and estado and estado != estado_ref:
        if estado_ref == "crudo" and estado == "cocinado":
            # Macros son para crudo; usuario pesó cocinado → crudo = cocinado / factor
            peso_efectivo = peso_g / factor
            cooking_adjusted = True
        elif estado_ref == "cocinado" and estado == "crudo":
            # Macros son para cocinado; usuario pesó crudo → cocinado = crudo * factor
            peso_efectivo = peso_g * factor
            cooking_adjusted = True

    # ── Cálculo de bloques crudos ───────────────────────────────────────
    raw_p = (peso_efectivo * m["p"]) / (100 * GRAMOS_POR_BLOQUE["P"])
    raw_h = (peso_efectivo * m["h"]) / (100 * GRAMOS_POR_BLOQUE["C"])
    raw_g = (peso_efectivo * m["g"]) / (100 * GRAMOS_POR_BLOQUE["G"])

    # ── Regla C: Cap de fibra ───────────────────────────────────────────
    fiber_ratio = (m["fibra"] / m["h"]) if m["h"] > 0 else 0
    fiber_capped = fiber_ratio > 0.5

    # ── Redondeo inteligente ────────────────────────────────────────────
    bloques_p = _redondeo_inteligente(raw_p)
    bloques_c = 0.0 if fiber_capped else _redondeo_inteligente(raw_h)
    bloques_g = _redondeo_inteligente(raw_g)

    nota = ""
    if fiber_capped:
        nota = "Fibra alta — carbos no cuentan como bloques C"
    if cooking_adjusted:
        nota = (nota + " | " if nota else "") + "Peso ajustado por cocción"

    return {
        "P": bloques_p,
        "C": bloques_c,
        "G": bloques_g,
        "fiber_capped": fiber_capped,
        "cooking_adjusted": cooking_adjusted,
        "nota": nota,
    }


def _redondeo_inteligente(valor: float) -> float:
    """
    Redondeo en pasos de 0.5.
    decimal < 0.25  → baja al entero
    decimal 0.25-0.74 → sube a X.5
    decimal ≥ 0.75  → sube al entero superior
    """
    if valor <= 0:
        return 0.0
    floor_val = int(valor)
    decimal = valor - floor_val
    if decimal < 0.25:
        return float(floor_val)
    elif decimal < 0.75:
        return float(floor_val) + 0.5
    else:
        return float(floor_val + 1)


def distribuir_bloques_comidas(bloques: dict, tipo_sesion: str) -> dict:
    """
    Distribuye los bloques totales del día entre las comidas.
    Prioriza la comida pre-entreno para carbos en días de training.

    Returns dict: {'desayuno': {'P':x,'C':x,'G':x}, 'almuerzo': ..., 'cena': ...}
    """
    P, C, G = bloques["P"], bloques["C"], bloques["G"]

    if tipo_sesion == "hyrox":
        return {
            "desayuno": {"P": round(P * 0.25), "C": round(C * 0.20), "G": round(G * 0.25)},
            "pre":      {"P": round(P * 0.15), "C": round(C * 0.35), "G": round(G * 0.10)},
            "post":     {"P": round(P * 0.30), "C": round(C * 0.25), "G": round(G * 0.15)},
            "cena":     {"P": round(P * 0.30), "C": round(C * 0.20), "G": round(G * 0.50)},
        }
    elif tipo_sesion == "gym":
        return {
            "desayuno": {"P": round(P * 0.25), "C": round(C * 0.25), "G": round(G * 0.25)},
            "pre":      {"P": round(P * 0.20), "C": round(C * 0.30), "G": round(G * 0.15)},
            "post":     {"P": round(P * 0.30), "C": round(C * 0.25), "G": round(G * 0.10)},
            "cena":     {"P": round(P * 0.25), "C": round(C * 0.20), "G": round(G * 0.50)},
        }
    else:  # descanso
        return {
            "desayuno": {"P": round(P * 0.30), "C": round(C * 0.30), "G": round(G * 0.25)},
            "almuerzo": {"P": round(P * 0.35), "C": round(C * 0.40), "G": round(G * 0.25)},
            "cena":     {"P": round(P * 0.35), "C": round(C * 0.30), "G": round(G * 0.50)},
        }
