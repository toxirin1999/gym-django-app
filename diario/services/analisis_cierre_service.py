import hashlib
import json
import unicodedata

from django.core import signing


SALT = 'diario.analisis-cierre.v1'
SCHEMA_VERSION = 1
TTL_SECONDS = 15 * 60
MAX_TOKEN_BYTES = 24 * 1024


class AnalisisTokenInvalido(Exception):
    pass


class AnalisisNoDisponible(Exception):
    pass


def normalizar_texto(texto):
    return ' '.join(unicodedata.normalize('NFKC', texto or '').split())


def hash_texto(texto):
    return hashlib.sha256(normalizar_texto(texto).encode('utf-8')).hexdigest()


def analizar_texto(texto):
    texto = normalizar_texto(texto)
    if not texto:
        return {
            'estado': 'ok_sin_senales',
            'parseo': {'estado_animo': 3, 'impulsos': [], 'personas': [], 'etiquetas': []},
            'enriquecido': {
                'titulo_logos': None, 'categoria_estoica': None, 'micro_verdad': None,
                'interacciones': [], 'propuesta_habito': None,
            },
        }
    from joi.services import enriquecer_cierre, parsear_cierre_diario
    try:
        parseo = parsear_cierre_diario(texto, strict=True)
        enriquecido = enriquecer_cierre(texto, parseo.get('personas') or [], strict=True)
    except Exception as exc:
        raise AnalisisNoDisponible(str(exc)) from exc
    hay_senales = bool(
        parseo.get('personas') or parseo.get('impulsos') or parseo.get('etiquetas')
        or enriquecido.get('micro_verdad') or enriquecido.get('interacciones')
        or enriquecido.get('propuesta_habito')
    )
    return {
        'estado': 'ok' if hay_senales else 'ok_sin_senales',
        'parseo': parseo, 'enriquecido': enriquecido,
    }


def crear_artefacto(*, usuario, fecha, texto, analisis, persona='', pregunta=''):
    return {
        'schema_version': SCHEMA_VERSION,
        'user_id': usuario.pk,
        'fecha': fecha.isoformat(),
        'texto_hash': hash_texto(texto),
        'estado': analisis['estado'],
        'parseo': analisis['parseo'],
        'enriquecido': analisis['enriquecido'],
        'persona_simbiosis': persona or '',
        'pregunta_simbiosis': pregunta or '',
    }


def firmar_artefacto(artefacto):
    token = signing.dumps(artefacto, salt=SALT, compress=True)
    if len(token.encode('utf-8')) > MAX_TOKEN_BYTES:
        raise AnalisisTokenInvalido('El análisis excede el tamaño permitido.')
    return token


def verificar_artefacto(token, *, usuario, fecha, texto):
    if not token or len(token.encode('utf-8')) > MAX_TOKEN_BYTES:
        raise AnalisisTokenInvalido('Token ausente o demasiado grande.')
    try:
        artefacto = signing.loads(token, salt=SALT, max_age=TTL_SECONDS)
    except signing.BadSignature as exc:
        raise AnalisisTokenInvalido('Firma o vigencia inválida.') from exc
    esperado = (SCHEMA_VERSION, usuario.pk, fecha.isoformat(), hash_texto(texto))
    actual = (
        artefacto.get('schema_version'), artefacto.get('user_id'),
        artefacto.get('fecha'), artefacto.get('texto_hash'),
    )
    if actual != esperado:
        raise AnalisisTokenInvalido('El token no corresponde a este cierre.')
    return artefacto
