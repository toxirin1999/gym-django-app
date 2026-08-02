def validar_estado_animo_post(valor):
    """Devuelve (es_valido, mood) para el valor opcional recibido por POST."""
    if valor in (None, ""):
        return True, None

    try:
        estado_animo = int(valor)
    except (TypeError, ValueError):
        return False, None

    if estado_animo not in range(1, 6):
        return False, None

    return True, estado_animo
