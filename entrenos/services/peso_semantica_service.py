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


def normalizar_semantica_carga(ejercicio):
    """Añade metadatos de presentación sin alterar nombre ni peso contractual."""
    out = dict(ejercicio or {})
    nombre = str(out.get("nombre") or "")
    nombre_normalizado = nombre.casefold()

    if not any(token in nombre_normalizado for token in _MANCUERNA):
        out.setdefault("peso_formato", "total")
        return out

    if any(token in nombre_normalizado for token in _UNILATERAL):
        out["peso_formato"] = "por_lado"
        out.pop("peso_por_mancuerna_kg", None)
        return out

    out["peso_formato"] = "total_ambas"
    if "peso_por_mancuerna_kg" not in out:
        peso_total = out.get("peso_kg", out.get("peso_recomendado_kg"))
        if isinstance(peso_total, (int, float)):
            out["peso_por_mancuerna_kg"] = round(peso_total / 2.0, 1)
    return out
