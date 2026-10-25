"""Semántica canónica de carga: presentación y snapshots de persistencia."""

from decimal import Decimal, InvalidOperation


TIPOS_CARGA = {"total", "por_mano", "por_lado"}
ALIASES_TIPO_CARGA = {
    "total_ambas": "total",
    "por_mancuerna": "por_mano",
}


def resolver_semantica_carga(tipo_carga, peso_kg, multiplicador_solicitado=None):
    """Calcula snapshots confiables; nunca acepta el multiplicador del cliente."""
    tipo = ALIASES_TIPO_CARGA.get(str(tipo_carga or "").strip(), str(tipo_carga or "").strip())
    if tipo not in TIPOS_CARGA:
        tipo = "total"
    multiplicador = 2 if tipo in {"por_mano", "por_lado"} else 1
    try:
        peso = Decimal(str(peso_kg or 0))
    except (InvalidOperation, TypeError, ValueError):
        peso = Decimal("0")
    return {
        "tipo_carga": tipo,
        "multiplicador_carga": multiplicador,
        "peso_total_kg": peso * multiplicador,
    }


_MANCUERNA = ("mancuerna", "mancuernas", "dumbbell", "db ", "db-")
_UNILATERAL = ("unilateral", "una mano", "un brazo", "por lado", "alterno")
_POR_LADO_SIN_MANCUERNA = ("pallof", "unilateral", "una mano", "un brazo")


def _normalizar_base(ejercicio):
    """Añade metadatos de presentación sin alterar nombre ni peso contractual."""
    out = dict(ejercicio or {})
    nombre = str(out.get("nombre") or "")
    nombre_normalizado = nombre.casefold()

    tipo_explicito = out.get("tipo_carga_default") or out.get("tipo_carga")
    if tipo_explicito in {"por_mano", "por_lado"}:
        out["peso_formato"] = tipo_explicito
        return out

    if not any(token in nombre_normalizado for token in _MANCUERNA):
        # 17-oct-2026: el Pallof se hace con cada lado (15 reps por lado).
        if any(token in nombre_normalizado for token in _POR_LADO_SIN_MANCUERNA):
            out["peso_formato"] = "por_lado"
            return out
        out.setdefault("peso_formato", "total")
        return out

    if any(token in nombre_normalizado for token in _UNILATERAL):
        out["peso_formato"] = "por_lado"
        out.pop("peso_por_mancuerna_kg", None)
        return out

    # 25-oct-2026: "con Mancuerna" (una sola): el peso es esa mancuerna, no "total de ambas".
    from entrenos.services.maquina_service import es_una_mancuerna
    if es_una_mancuerna(nombre):
        out["peso_formato"] = "una_mancuerna"
        out.pop("peso_por_mancuerna_kg", None)
        return out

    out["peso_formato"] = "total_ambas"
    if "peso_por_mancuerna_kg" not in out:
        peso_total = out.get("peso_kg", out.get("peso_recomendado_kg"))
        if isinstance(peso_total, (int, float)):
            out["peso_por_mancuerna_kg"] = round(peso_total / 2.0, 1)
    return out


_POR_PIERNA = ("zancada", "lunge", "búlgara", "bulgara", "step up", "step-up", "subida al cajón", "a una pierna",
               # 25-oct-2026: la patada de glúteo en polea se hace pierna a pierna.
               "patada de glúteo", "patada de gluteo", "kickback")
# 25-oct-2026: curls en polea a un brazo (Bayesian: 15 reps por brazo).
_POR_BRAZO_SIN_MANCUERNA = ("bayesian",)


# 18-oct-2026: zancadas, búlgaras y subidas al cajón se cuentan por pierna y
# su rango no pasa de 12. Con cargas que permiten más de 12 por pierna, la
# serie la corta el equilibrio y el ahogo antes que el músculo; la hipertrofia
# es similar en rangos amplios cerca del fallo (Schoenfeld et al., 2021).
_UNILATERAL_PIERNA_COMPUESTO = ("zancada", "lunge", "búlgara", "bulgara", "step up", "step-up", "subida al cajón")
RANGO_UNILATERAL_PIERNA = "8-12"


def rango_unilateral_pierna(nombre, rango):
    """'15-20' → '8-12' para zancadas y similares; el resto, sin tocar."""
    nombre = str(nombre or "").casefold()
    if not any(t in nombre for t in _UNILATERAL_PIERNA_COMPUESTO):
        return rango
    try:
        bajo, alto = (int(x) for x in str(rango).split("-"))
    except (TypeError, ValueError):
        return rango
    return RANGO_UNILATERAL_PIERNA if alto > 12 else rango


def normalizar_semantica_carga(ejercicio):
    """Añade metadatos de presentación (peso y reps) sin alterar nombre ni peso.

    18-oct-2026: ``reps_unidad`` dice cómo se cuentan las reps: "por pierna"
    (zancadas), "por brazo" (curl con dos mancuernas) o "por lado" (Pallof,
    a una mano). Antes 15-20 reps se leía como el total (8 por brazo).
    """
    out = _normalizar_base(ejercicio)
    nombre = str(out.get("nombre") or "").casefold()
    if any(t in nombre for t in _POR_PIERNA):
        out["reps_unidad"] = "por pierna"
    elif out.get("peso_formato") in {"por_lado", "por_mano"}:
        out["reps_unidad"] = "por lado"
    elif ("curl" in nombre and any(t in nombre for t in _MANCUERNA)) or any(t in nombre for t in _POR_BRAZO_SIN_MANCUERNA):
        out["reps_unidad"] = "por brazo"
    return out
