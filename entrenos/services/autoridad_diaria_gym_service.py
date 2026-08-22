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
from django.db import transaction
from django.utils import timezone


SCHEMA_VERSION = 2
_CACHE_TTL_SECONDS = 15 * 60


class AutoridadGymCorreccionInvalida(ValueError):
    pass


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


def _fingerprint_snapshot_fisico(snapshot: dict) -> str:
    """Huella observacional; nunca participa en la identidad ejecutiva Gym."""
    payload = {
        clave: valor
        for clave, valor in snapshot.items()
        if clave not in {'captured_at', 'fingerprint'}
    }
    crudo = json.dumps(
        _serializable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(crudo.encode('utf-8')).hexdigest()


def _snapshot_fisico_no_disponible(cliente, fecha) -> dict:
    return {
        'schema_version': 1,
        'cliente_id': cliente.pk,
        'as_of_date': fecha.isoformat(),
        'status': 'unavailable',
        'error_code': 'physical_snapshot_unavailable',
    }


def _construir_snapshot_fisico(cliente, fecha):
    try:
        from core.services.physical_snapshot import build_physical_snapshot

        snapshot = build_physical_snapshot(cliente, fecha)
    except Exception:
        snapshot = _snapshot_fisico_no_disponible(cliente, fecha)
    return deepcopy(snapshot), snapshot.get('fingerprint') or _fingerprint_snapshot_fisico(snapshot)


def _snapshot_fisico_valido(snapshot, cliente, fecha) -> bool:
    """Contrato mínimo V1 materializable; `unavailable` nunca se promociona."""
    return bool(
        isinstance(snapshot, dict)
        and snapshot.get('status') != 'unavailable'
        and snapshot.get('schema_version') == 1
        and snapshot.get('cliente_id') == cliente.pk
        and snapshot.get('as_of_date') == fecha.isoformat()
        and isinstance(snapshot.get('signals'), dict)
    )


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


def _aplicar_version_manual(autoridad: dict, version) -> dict:
    resultado = deepcopy(autoridad)
    resultado.update(version.ajustes or {})
    snapshot_version = version.snapshot or {}
    if 'physical_snapshot' in snapshot_version:
        resultado['physical_snapshot'] = deepcopy(snapshot_version['physical_snapshot'])
        resultado['physical_snapshot_fingerprint'] = snapshot_version.get(
            'physical_snapshot_fingerprint'
        ) or _fingerprint_snapshot_fisico(snapshot_version['physical_snapshot'])
    resultado.update({
        'decision_id': version.decision_id,
        'origen_decision': version.origen,
        'version_persistida': version.version,
        'motivo_correccion': version.motivo_correccion,
    })
    return resultado


def _persistir_version_motor(cliente, fecha, autoridad: dict, huella: str) -> dict:
    from clientes.models import Cliente
    from entrenos.models import GymDecisionVersion

    with transaction.atomic():
        Cliente.objects.select_for_update().get(pk=cliente.pk)
        versiones = GymDecisionVersion.objects.select_for_update().filter(
            cliente=cliente,
            fecha=fecha,
        )
        vigente = versiones.filter(vigente=True).order_by('-version').first()

        if (
            vigente
            and vigente.origen in {
                GymDecisionVersion.ORIGEN_CORRECCION,
                GymDecisionVersion.ORIGEN_REVERSION,
            }
            and vigente.base_fingerprint == huella
        ):
            return _aplicar_version_manual(autoridad, vigente)

        if (
            vigente
            and vigente.origen == GymDecisionVersion.ORIGEN_MOTOR
            and vigente.fingerprint == huella
        ):
            snapshot_vigente = vigente.snapshot or {}
            physical_vigente = snapshot_vigente.get('physical_snapshot')
            if _snapshot_fisico_valido(physical_vigente, cliente, fecha):
                autoridad['physical_snapshot'] = deepcopy(snapshot_vigente['physical_snapshot'])
                autoridad['physical_snapshot_fingerprint'] = snapshot_vigente.get(
                    'physical_snapshot_fingerprint'
                ) or _fingerprint_snapshot_fisico(snapshot_vigente['physical_snapshot'])
                autoridad['origen_decision'] = vigente.origen
                autoridad['version_persistida'] = vigente.version
                return autoridad

            physical_nuevo = autoridad.get('physical_snapshot')
            if _snapshot_fisico_valido(physical_nuevo, cliente, fecha):
                # Upgrade contractual inmutable: la fila legacy se conserva y
                # la sucesora mantiene la misma identidad ejecutiva.
                versiones.filter(pk=vigente.pk, vigente=True).update(vigente=False)
                ultima = versiones.order_by('-version').first()
                numero = (ultima.version if ultima else 0) + 1
                snapshot_upgrade = _serializable(autoridad)
                snapshot_upgrade['contract_upgrade'] = 'physical_snapshot_v1'
                creada = GymDecisionVersion.objects.create(
                    cliente=cliente,
                    fecha=fecha,
                    version=numero,
                    decision_id=vigente.decision_id,
                    schema_version=vigente.schema_version,
                    origen=GymDecisionVersion.ORIGEN_MOTOR,
                    vigente=True,
                    fingerprint=vigente.fingerprint,
                    base_fingerprint=vigente.base_fingerprint,
                    postura=vigente.postura,
                    causa_principal=vigente.causa_principal,
                    snapshot=snapshot_upgrade,
                    reemplaza=vigente,
                )
                autoridad['origen_decision'] = creada.origen
                autoridad['version_persistida'] = creada.version
                return autoridad

            # La captura nueva también falló: conservar la autoridad legacy,
            # sin presentar el intento como una materialización correcta.
            autoridad['origen_decision'] = vigente.origen
            autoridad['version_persistida'] = vigente.version
            return autoridad

        if vigente:
            versiones.filter(vigente=True).update(vigente=False)
        ultima = versiones.order_by('-version').first()
        numero = (ultima.version if ultima else 0) + 1
        creada = GymDecisionVersion.objects.create(
            cliente=cliente,
            fecha=fecha,
            version=numero,
            decision_id=autoridad['decision_id'],
            schema_version=SCHEMA_VERSION,
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=True,
            fingerprint=huella,
            base_fingerprint=huella,
            postura=autoridad['postura'],
            causa_principal=autoridad.get('causa_principal') or '',
            snapshot=_serializable(autoridad),
            reemplaza=vigente,
        )
        autoridad['origen_decision'] = creada.origen
        autoridad['version_persistida'] = creada.version
        return autoridad


def resolver_autoridad_diaria_gym(
    cliente,
    fecha=None,
    *,
    physical_snapshot=None,
    force_refresh=False,
) -> dict:
    """Devuelve la única decisión Gym preparada para presentar y ejecutar."""
    from entrenos.services.sesion_recomendada import obtener_sesion_recomendada_hoy

    fecha = fecha or timezone.localdate()
    if physical_snapshot is None:
        # Se recaptura en cada resolución para que un check-in/readiness recién
        # guardado pueda cambiar la decisión y, por tanto, su cache key ejecutiva.
        physical_snapshot, huella_fisica = _construir_snapshot_fisico(cliente, fecha)
    else:
        physical_snapshot = deepcopy(physical_snapshot)
        huella_fisica = physical_snapshot.get('fingerprint') or _fingerprint_snapshot_fisico(
            physical_snapshot
        )
    decision_base = obtener_sesion_recomendada_hoy(
        cliente,
        fecha,
        physical_snapshot=physical_snapshot,
    )
    huella = _fingerprint(decision_base, fecha)
    cache_key = f'autoridad_diaria_gym_v{SCHEMA_VERSION}_{cliente.pk}_{fecha.isoformat()}_{huella}'
    cached = cache.get(cache_key)
    if cached is not None and not force_refresh:
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
    autoridad['physical_snapshot'] = physical_snapshot
    autoridad['physical_snapshot_fingerprint'] = huella_fisica
    deload_materializado = any(cambio.get('tipo') == 'deload' for cambio in cambios)
    for ejercicio in (autoridad.get('entrenamiento') or {}).get('ejercicios', []):
        ejercicio['_autoridad_gym_materializada'] = True
        ejercicio['_autoridad_gym_decision_id'] = autoridad['decision_id']
        if deload_materializado:
            ejercicio['_deload_aplicado'] = True
    autoridad = _persistir_version_motor(cliente, fecha, autoridad, huella)
    cache.set(cache_key, autoridad, _CACHE_TTL_SECONDS)
    return deepcopy(autoridad)


def corregir_autoridad_diaria_gym(
    cliente,
    fecha,
    *,
    decision_id_esperada: str,
    ajustes: dict,
    motivo: str,
) -> dict:
    """Crea una nueva versión manual, sin sobrescribir ni relajar seguridad."""
    from clientes.models import Cliente
    from entrenos.models import GymDecisionVersion

    permitidos = {'postura', 'modo_reducido', 'mensaje'}
    if not ajustes or set(ajustes) - permitidos:
        raise AutoridadGymCorreccionInvalida('La corrección contiene campos no permitidos.')
    if not str(motivo or '').strip():
        raise AutoridadGymCorreccionInvalida('La corrección necesita un motivo.')

    vigente_previa = (
        GymDecisionVersion.objects.filter(cliente=cliente, fecha=fecha, vigente=True)
        .order_by('-version')
        .first()
    )
    snapshot_previo = (
        (vigente_previa.snapshot or {}).get('physical_snapshot')
        if vigente_previa else None
    )
    actual = resolver_autoridad_diaria_gym(
        cliente,
        fecha,
        physical_snapshot=snapshot_previo,
    )
    if actual.get('decision_id') != decision_id_esperada:
        raise AutoridadGymCorreccionInvalida('La decisión cambió; revisa la versión vigente.')

    with transaction.atomic():
        Cliente.objects.select_for_update().get(pk=cliente.pk)
        versiones = GymDecisionVersion.objects.select_for_update().filter(
            cliente=cliente,
            fecha=fecha,
        )
        vigente = versiones.filter(vigente=True).order_by('-version').first()
        if not vigente or vigente.decision_id != decision_id_esperada:
            raise AutoridadGymCorreccionInvalida('La decisión cambió; revisa la versión vigente.')

        postura_actual = vigente.postura or 'empujar'
        postura_nueva = ajustes.get('postura', postura_actual)
        rango = {'proteger': 0, 'sostener': 1, 'empujar': 2}
        if postura_nueva not in rango or rango[postura_nueva] > rango[postura_actual]:
            raise AutoridadGymCorreccionInvalida('Una corrección no puede relajar la seguridad.')

        motor = versiones.filter(
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            base_fingerprint=vigente.base_fingerprint,
        ).order_by('-version').first()
        if not motor:
            raise AutoridadGymCorreccionInvalida('No existe una propuesta motora compatible.')

        numero = vigente.version + 1
        corregida = deepcopy(motor.snapshot)
        corregida.update(ajustes)
        corregida['postura'] = postura_nueva
        if postura_nueva == 'sostener':
            corregida['estado'] = 'version_reducida'
            corregida['modo_reducido'] = True
        elif postura_nueva == 'proteger':
            corregida['estado'] = 'recuperar'
            corregida['postura'] = 'proteger'
            corregida['modo_reducido'] = False
        digest = hashlib.sha256(
            json.dumps(_serializable(ajustes), sort_keys=True).encode('utf-8')
        ).hexdigest()[:12]
        corregida['decision_id'] = f'gym-{fecha.isoformat()}-v{numero}-manual-{digest}'
        corregida['origen_decision'] = GymDecisionVersion.ORIGEN_CORRECCION
        corregida['version_persistida'] = numero
        corregida['motivo_correccion'] = motivo.strip()

        versiones.filter(vigente=True).update(vigente=False)
        GymDecisionVersion.objects.create(
            cliente=cliente,
            fecha=fecha,
            version=numero,
            decision_id=corregida['decision_id'],
            schema_version=SCHEMA_VERSION,
            origen=GymDecisionVersion.ORIGEN_CORRECCION,
            vigente=True,
            fingerprint=digest,
            base_fingerprint=vigente.base_fingerprint,
            postura=postura_nueva,
            causa_principal=corregida.get('causa_principal') or '',
            snapshot=_serializable(corregida),
            ajustes=ajustes,
            motivo_correccion=motivo.strip(),
            reemplaza=vigente,
        )

    cache_key = (
        f'autoridad_diaria_gym_v{SCHEMA_VERSION}_{cliente.pk}_'
        f'{fecha.isoformat()}_{vigente.base_fingerprint}'
    )
    cache.set(cache_key, corregida, _CACHE_TTL_SECONDS)
    return deepcopy(corregida)


def revertir_correccion_autoridad_diaria_gym(
    cliente,
    fecha,
    *,
    decision_id_esperada: str,
    motivo: str,
) -> dict:
    """Restaura la propuesta motora como una versión nueva y auditable."""
    from clientes.models import Cliente
    from entrenos.models import GymDecisionVersion

    if not str(motivo or '').strip():
        raise AutoridadGymCorreccionInvalida('La reversión necesita un motivo.')
    vigente_previa = (
        GymDecisionVersion.objects.filter(cliente=cliente, fecha=fecha, vigente=True)
        .order_by('-version')
        .first()
    )
    snapshot_previo = (
        (vigente_previa.snapshot or {}).get('physical_snapshot')
        if vigente_previa else None
    )
    actual = resolver_autoridad_diaria_gym(
        cliente,
        fecha,
        physical_snapshot=snapshot_previo,
    )
    if actual.get('decision_id') != decision_id_esperada:
        raise AutoridadGymCorreccionInvalida('La decisión cambió; revisa la versión vigente.')

    with transaction.atomic():
        Cliente.objects.select_for_update().get(pk=cliente.pk)
        versiones = GymDecisionVersion.objects.select_for_update().filter(
            cliente=cliente,
            fecha=fecha,
        )
        vigente = versiones.filter(vigente=True).order_by('-version').first()
        if (
            not vigente
            or vigente.decision_id != decision_id_esperada
            or vigente.origen != GymDecisionVersion.ORIGEN_CORRECCION
        ):
            raise AutoridadGymCorreccionInvalida('Solo se puede revertir una corrección vigente.')

        motor = versiones.filter(
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            base_fingerprint=vigente.base_fingerprint,
        ).order_by('-version').first()
        if not motor:
            raise AutoridadGymCorreccionInvalida('No existe una propuesta motora compatible.')

        numero = vigente.version + 1
        restaurada = deepcopy(motor.snapshot)
        ajustes = {}
        digest = hashlib.sha256(
            f'{vigente.decision_id}:{numero}:reversion'.encode('utf-8')
        ).hexdigest()[:12]
        restaurada.update({
            'decision_id': f'gym-{fecha.isoformat()}-v{numero}-reversion-{digest}',
            'origen_decision': GymDecisionVersion.ORIGEN_REVERSION,
            'version_persistida': numero,
            'motivo_correccion': motivo.strip(),
        })

        versiones.filter(vigente=True).update(vigente=False)
        GymDecisionVersion.objects.create(
            cliente=cliente,
            fecha=fecha,
            version=numero,
            decision_id=restaurada['decision_id'],
            schema_version=SCHEMA_VERSION,
            origen=GymDecisionVersion.ORIGEN_REVERSION,
            vigente=True,
            fingerprint=digest,
            base_fingerprint=vigente.base_fingerprint,
            postura=restaurada['postura'],
            causa_principal=restaurada.get('causa_principal') or '',
            snapshot=_serializable(restaurada),
            ajustes=ajustes,
            motivo_correccion=motivo.strip(),
            reemplaza=vigente,
        )

    cache_key = (
        f'autoridad_diaria_gym_v{SCHEMA_VERSION}_{cliente.pk}_'
        f'{fecha.isoformat()}_{vigente.base_fingerprint}'
    )
    cache.set(cache_key, restaurada, _CACHE_TTL_SECONDS)
    return deepcopy(restaurada)
