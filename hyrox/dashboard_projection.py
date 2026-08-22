"""Proyección Hyrox pura sobre la única autoridad diaria Gym."""

from copy import deepcopy

from hyrox.decision_service import (
    estaciones_bloqueadas_por_tags,
    normalizar_tags_restringidos,
)


_RANGO = {'proteger': 0, 'sostener': 1, 'empujar': 2}


def leer_autoridad_gym_vigente(cliente, fecha):
    """Lectura sin escrituras de la versión Gym ya materializada para el día."""
    from entrenos.models import GymDecisionVersion

    version = GymDecisionVersion.objects.filter(
        cliente=cliente, fecha=fecha, vigente=True
    ).order_by('-version').first()
    if version is None:
        return {
            'decision_id': None,
            'version_persistida': None,
            'postura': 'proteger',
            'estado': 'recuperar',
            'causa_principal': 'autoridad_gym_no_materializada',
        }
    autoridad = deepcopy(version.snapshot or {})
    autoridad.update({
        'decision_id': version.decision_id,
        'version_persistida': version.version,
        'postura': version.postura,
        'estado': autoridad.get('estado') or (
            'recuperar' if version.postura == 'proteger'
            else 'version_reducida' if version.postura == 'sostener'
            else 'entrenar'
        ),
        'causa_principal': version.causa_principal,
    })
    return autoridad


def _valor(resumen, campo):
    if isinstance(resumen, dict):
        return resumen.get(campo)
    return getattr(resumen, campo, None) if resumen is not None else None


def _payload_base(autoridad_gym):
    autoridad_gym = autoridad_gym or {}
    decision_id = autoridad_gym.get('decision_id')
    version = autoridad_gym.get(
        'version_persistida', autoridad_gym.get('version')
    )
    return {
        'source': 'gym_decision_version',
        'hyrox_es_proyeccion': True,
        'decision_id': decision_id,
        'version': version,
        'gym_decision_id': decision_id,
        'gym_decision_version': version,
        'permitido': deepcopy(autoridad_gym.get('permitido') or []),
        'evitar': deepcopy(autoridad_gym.get('evitar') or []),
        'tags_restringidos': [],
        'estaciones_bloqueadas': [],
    }


def proyectar_decision_hyrox(
    autoridad_gym,
    *,
    campana_activa,
    readiness=None,
    resumen_carga=None,
    lesion_activa=None,
):
    """Modula hacia protección; nunca crea una postura superior a Gym."""
    payload = _payload_base(autoridad_gym)
    if not campana_activa:
        payload.update({
            'estado': 'inactivo',
            'causa': 'campana_inactiva',
            'titulo': 'Explorar Hyrox',
            'subtitulo': 'Sin campaña activa',
            'mensaje': 'Puedes explorar Hyrox sin alterar el plan Gym.',
            'accion_label': 'Explorar Hyrox',
            'puede_ejecutar_plan': False,
        })
        return payload

    postura_gym = (autoridad_gym or {}).get('postura')
    if postura_gym not in _RANGO:
        postura_gym = 'proteger'
    postura = postura_gym
    causa = (autoridad_gym or {}).get('causa_principal') or 'gym'

    tags = normalizar_tags_restringidos(lesion_activa)
    if lesion_activa:
        postura, causa = 'proteger', 'lesion'
        payload['tags_restringidos'] = tags
        payload['estaciones_bloqueadas'] = estaciones_bloqueadas_por_tags(tags)
        payload['evitar'] = list(dict.fromkeys([
            *payload['evitar'], *payload['estaciones_bloqueadas']
        ]))
    else:
        tsb = _valor(resumen_carga, 'tsb')
        acwr = _valor(resumen_carga, 'acwr')
        if (tsb is not None and tsb <= -20) or (acwr is not None and acwr > 1.7):
            postura, causa = 'proteger', 'carga_hyrox'
        elif (
            _RANGO[postura] > _RANGO['sostener']
            and (
                (acwr is not None and acwr >= 1.5)
                or (readiness is not None and readiness < 45)
            )
        ):
            postura, causa = 'sostener', (
                'carga_hyrox' if acwr is not None and acwr >= 1.5
                else 'readiness_hyrox'
            )

    # El mínimo ordinal gana: Hyrox solo puede proteger más.
    if _RANGO[postura] > _RANGO[postura_gym]:
        postura = postura_gym

    estado_gym = (autoridad_gym or {}).get('estado')
    configuracion = {
        'proteger': {
            'estado': 'recuperar', 'titulo': 'Proteger',
            'subtitulo': 'La autoridad Gym limita la ejecución',
            'mensaje': 'Hyrox acompaña la protección indicada por el plan Gym.',
            'accion_label': 'Recuperación activa',
            'puede_ejecutar_plan': False,
        },
        'sostener': {
            'estado': 'sostener', 'titulo': 'Sostener',
            'subtitulo': 'Ejecutar con margen',
            'mensaje': 'Hyrox conserva el margen definido por el plan Gym.',
            'accion_label': 'Sesión con margen',
            'puede_ejecutar_plan': estado_gym not in {
                'descanso', 'recuperar', 'posponer'
            },
        },
        'empujar': {
            'estado': 'empujar', 'titulo': 'Empujar',
            'subtitulo': 'Señales compatibles con el plan Gym',
            'mensaje': 'Hyrox puede ejecutarse dentro de la autoridad Gym vigente.',
            'accion_label': 'Ejecutar plan',
            'puede_ejecutar_plan': True,
        },
    }[postura]
    payload.update(configuracion)
    payload['causa'] = causa
    return payload
