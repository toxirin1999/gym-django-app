"""Salida canónica, explicable e idempotente de la decisión diaria Gym.

Este servicio no introduce un motor nuevo. Ordena la decisión ya resuelta por
``sesion_recomendada`` y materializa una sola vez las decisiones ejecutivas por
ejercicio. Los consumidores deben leer este contrato, no volver a decidir.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date

from django.core.cache import cache
from django.utils import timezone


SCHEMA_VERSION = 1
_CACHE_TTL_SECONDS = 15 * 60


def _serializable(valor):
    if isinstance(valor, dict):
        return {
            str(clave): _serializable(contenido)
            for clave, contenido in sorted(valor.items(), key=lambda item: str(item[0]))
            if not str(clave).startswith('_')
        }
    if isinstance(valor, (list, tuple)):
        return [_serializable(item) for item in valor]
    if isinstance(valor, date):
        return valor.isoformat()
    if hasattr(valor, 'pk'):
        return {'modelo': valor._meta.label_lower, 'pk': valor.pk}
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def _fingerprint(decision: dict, fecha) -> str:
    payload = {
        'schema_version': SCHEMA_VERSION,
        'fecha': fecha.isoformat(),
        'decision': _serializable(decision),
    }
    crudo = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(crudo.encode('utf-8')).hexdigest()[:20]


def _postura(estado: str) -> str:
    if estado in {'recuperar', 'posponer'}:
        return 'proteger'
    if estado in {'version_reducida', 'descanso'}:
        return 'sostener'
    return 'empujar'


def _causas_secundarias(decision: dict) -> list[str]:
    contexto = decision.get('contexto_fisico') or {}
    mapa = (
        ('lesion_activa', 'lesion'),
        ('readiness_bajo', 'readiness_bajo'),
        ('energia_baja', 'energia_baja'),
        ('futbol_reciente', 'futbol_reciente'),
        ('hyrox_reciente', 'hyrox_reciente'),
    )
    principal = decision.get('causa_principal')
    return [causa for campo, causa in mapa if contexto.get(campo) and causa != principal]


def _capas_suprimidas(decision: dict) -> list[str]:
    declaradas = list(decision.get('capas_suprimidas') or [])
    if (
        decision.get('distribucion_aviso')
        and decision.get('preferencia_aplicada')
        and 'distribucion_aviso' not in declaradas
    ):
        declaradas.append('distribucion_aviso')
    return declaradas


def resolver_autoridad_diaria_gym(cliente, fecha=None) -> dict:
    """Devuelve la única decisión Gym preparada para presentar y ejecutar."""
    from entrenos.services.sesion_recomendada import obtener_sesion_recomendada_hoy

    fecha = fecha or timezone.localdate()
    decision_base = obtener_sesion_recomendada_hoy(cliente, fecha)
    huella = _fingerprint(decision_base, fecha)
    cache_key = f'autoridad_diaria_gym_v{SCHEMA_VERSION}_{cliente.pk}_{fecha.isoformat()}_{huella}'
    cached = cache.get(cache_key)
    if cached is not None:
        return deepcopy(cached)

    autoridad = deepcopy(decision_base)
    estado = autoridad.get('estado') or 'entrenar'
    cambios = []

    entrenamiento = autoridad.get('entrenamiento')
    if estado not in {'recuperar', 'descanso', 'posponer'} and entrenamiento:
        ejercicios = deepcopy(entrenamiento.get('ejercicios') or [])
        if ejercicios:
            from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico

            ejercicios, cambios = aplicar_plan_dinamico(cliente, ejercicios, fecha)
            entrenamiento = deepcopy(entrenamiento)
            entrenamiento['ejercicios'] = ejercicios
            autoridad['entrenamiento'] = entrenamiento

    autoridad.update({
        'schema_version': SCHEMA_VERSION,
        'decision_id': f'gym-{fecha.isoformat()}-{huella}',
        'fingerprint': huella,
        'fecha': fecha.isoformat(),
        'vigente_hasta': fecha.isoformat(),
        'postura': _postura(estado),
        'causas_secundarias': _causas_secundarias(autoridad),
        'capas_suprimidas': _capas_suprimidas(autoridad),
        'cambios_materializados': cambios,
        'sesion_materializada': bool(entrenamiento and entrenamiento.get('ejercicios')),
    })
    deload_materializado = any(cambio.get('tipo') == 'deload' for cambio in cambios)
    for ejercicio in (autoridad.get('entrenamiento') or {}).get('ejercicios', []):
        ejercicio['_autoridad_gym_materializada'] = True
        ejercicio['_autoridad_gym_decision_id'] = autoridad['decision_id']
        if deload_materializado:
            ejercicio['_deload_aplicado'] = True
    cache.set(cache_key, autoridad, _CACHE_TTL_SECONDS)
    return deepcopy(autoridad)
