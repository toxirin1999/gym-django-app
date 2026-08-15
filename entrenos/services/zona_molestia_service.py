import re
import unicodedata


ZONA_TAGS_MAP = {
    'hombro': ['empuje_horizontal', 'empuje_vertical', 'rotacion_interna_hombro'],
    'rodilla': ['flexion_rodilla_profunda', 'impacto_vertical', 'triple_extension_explosiva'],
    'cadera': ['flexion_cadera_profunda', 'triple_extension_explosiva', 'bisagra_cadera_cargada'],
    'lumbar': ['flexion_lumbar', 'carga_axial', 'bisagra_cadera_cargada'],
    'muñeca': ['agarre_pesado', 'apoyo_muñeca'], 'cuello': ['carga_cervical'],
    'tobillo': ['impacto_vertical', 'dorsiflexion_tobillo'],
    'pecho': ['empuje_horizontal'], 'codo': ['traccion_codo', 'empuje_codo'], 'otro': [],
}


def normalizar_zona(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode()
    limpio = re.sub(r'[^a-z]+', ' ', texto.lower()).strip()
    return {'muneca': 'muñeca'}.get(limpio, limpio if limpio in ZONA_TAGS_MAP else 'otro')


def risk_tags_zona(zona):
    return list(ZONA_TAGS_MAP.get(normalizar_zona(zona), []))
