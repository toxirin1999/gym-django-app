"""Proyección de presentación para la supervisión manual de Gym."""

from entrenos.models import GymDecisionVersion


_TITULOS = {
    GymDecisionVersion.ORIGEN_CORRECCION: "Ajuste supervisado",
    GymDecisionVersion.ORIGEN_REVERSION: "Propuesta restaurada",
}


def construir_recibo_supervision_gym(
    *, cliente, fecha, portada_hoy, autoridad_gym=None
):
    """Describe la versión manual vigente sin reinterpretar su autoridad."""
    vigente = (
        GymDecisionVersion.objects
        .select_related("reemplaza")
        .filter(cliente=cliente, fecha=fecha, vigente=True)
        .order_by("-version")
        .first()
    )
    if not vigente or vigente.origen not in _TITULOS:
        return None

    sesion = (portada_hoy or {}).get("sesion_dominante") or {}
    if sesion.get("modulo") == "gym":
        ejecutable = sesion.get("ejecutable") is True
    else:
        ejecutable = (autoridad_gym or {}).get("ejecutable") is True
    anterior = vigente.reemplaza.postura if vigente.reemplaza_id else ""
    return {
        "titulo": _TITULOS[vigente.origen],
        "version": vigente.version,
        "postura_anterior": anterior,
        "postura_actual": vigente.postura,
        "motivo": vigente.motivo_correccion,
        "conservacion": (
            "Se conservan los ejercicios, los cambios dinámicos y la "
            "evidencia física de la propuesta motor."
        ),
        "ejecutable": ejecutable,
        "origen": vigente.origen,
    }
