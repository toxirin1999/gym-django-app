"""Compositor puro de la portada "Hoy".

No calcula readiness, lesiones ni decisiones: solo ordena autoridades ya
resueltas y garantiza que exista, como máximo, una acción principal.
"""

import unicodedata


_GYM_NO_EJECUTABLE = {"recuperar", "descanso", "posponer", "realizado"}


def _texto_normalizado(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(char for char in texto if not unicodedata.combining(char)).strip().lower()


def _es_descanso_gym(estado_sistema, sesion_gym):
    textos = [
        estado_sistema.get("estado_label"),
        estado_sistema.get("accion_label"),
    ]
    if isinstance(sesion_gym, dict):
        textos.extend(sesion_gym.get(campo) for campo in ("nombre", "titulo", "label"))
    return any("descanso" in _texto_normalizado(texto) for texto in textos)


def _sesion(modulo, datos, *, ejecutable):
    return {
        "modulo": modulo,
        "datos": datos,
        "ejecutable": bool(ejecutable),
    } if datos else None


def _limitar_textos(items):
    textos = []
    for item in items or ():
        if isinstance(item, dict):
            item = next((item.get(key) for key in (
                "texto", "label", "titulo", "mensaje", "descripcion"
            ) if item.get(key)), "")
        texto = str(item or "").strip()
        if texto:
            textos.append(texto)
        if len(textos) == 3:
            break
    return textos


def construir_portada_hoy(
    *,
    estado_sistema,
    decision_gym,
    sesion_gym,
    hyrox_decision,
    sesion_hyrox,
    hyrox_relevante,
    hyrox_url,
    recuperacion_url,
    checkin_pendiente,
    diario_pendiente,
    diario_url,
    diario_label="Abrir Diario",
    senales=(),
    aprendizajes=(),
):
    """Traduce decisiones existentes al contrato visual de la portada."""
    estado_sistema = estado_sistema or {}
    decision_gym = decision_gym or {}
    hyrox_decision = hyrox_decision or {}

    estado_gym = str(
        decision_gym.get("estado") or decision_gym.get("tipo") or ""
    ).strip().lower()
    gym_viable = (
        bool(sesion_gym)
        and estado_gym not in _GYM_NO_EJECUTABLE
        and estado_sistema.get("modulo_operativo") is not False
        and not _es_descanso_gym(estado_sistema, sesion_gym)
    )
    hyrox_viable = (
        bool(hyrox_relevante)
        and bool(sesion_hyrox)
        and hyrox_decision.get("puede_ejecutar_plan") is True
    )

    gym = _sesion("gym", sesion_gym, ejecutable=gym_viable)
    hyrox = (
        _sesion("hyrox", sesion_hyrox, ejecutable=hyrox_viable)
        if hyrox_relevante else None
    )
    dominante = gym if gym_viable else hyrox if hyrox_viable else gym or hyrox
    alternativa = None
    if dominante and dominante["modulo"] == "gym" and hyrox:
        alternativa = hyrox
    elif dominante and dominante["modulo"] == "hyrox" and gym:
        alternativa = gym

    protegiendo = estado_sistema.get("estado") == "PROTEGIENDO"
    hyrox_bloqueado = (
        bool(hyrox_relevante)
        and bool(sesion_hyrox)
        and hyrox_decision.get("puede_ejecutar_plan") is False
        and (
            not gym_viable
            or estado_sistema.get("modulo_principal") == "hyrox"
        )
    )
    accion = None
    if protegiendo:
        accion = {
            "prioridad": "P0",
            "tipo": "enlace",
            "label": estado_sistema.get("accion_label") or "Revisar recuperación",
            "url": estado_sistema.get("accion_url") or recuperacion_url,
        }
    elif hyrox_bloqueado:
        accion = {
            "prioridad": "P0", "tipo": "enlace",
            "label": hyrox_decision.get("accion_label") or "Revisar recuperación Hyrox",
            "url": recuperacion_url,
        }
    elif checkin_pendiente and (gym_viable or hyrox_viable):
        accion = {
            "prioridad": "P1", "tipo": "modal_checkin",
            "label": "Completar check-in", "url": None,
        }
    elif (
        gym_viable
        and estado_sistema.get("estado") == "EN_MARGEN"
        and estado_sistema.get("accion_url")
    ):
        accion = {
            "prioridad": "P2", "tipo": "enlace",
            "label": estado_sistema.get("accion_label") or "Abrir sesión Gym",
            "url": estado_sistema.get("accion_url"),
        }
    elif hyrox_viable and not gym_viable:
        accion = {
            "prioridad": "P3", "tipo": "enlace",
            "label": hyrox_decision.get("accion_label") or "Abrir sesión Hyrox",
            "url": hyrox_url,
        }
    # Diario ya dispone de una acción contextual en su propio bloque. En un
    # día de descanso promoverla aquí convertiría un estado informativo en
    # una falsa urgencia y duplicaría el acceso inferior.

    return {
        "decision": {
            "estado": estado_sistema.get("estado_label") or estado_sistema.get("estado") or "Hoy",
            "frase": estado_sistema.get("texto") or "El sistema no necesita forzar nada ahora.",
        },
        "accion_principal": accion,
        "sesion_dominante": dominante,
        "sesion_alternativa": alternativa,
        "senales": _limitar_textos(senales),
        "aprendizajes": _limitar_textos(aprendizajes),
    }
