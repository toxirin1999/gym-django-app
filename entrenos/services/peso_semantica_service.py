"""Semántica canónica del peso mostrado en las superficies de entrenamiento."""


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
