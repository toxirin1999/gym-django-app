"""Contrato longitudinal Gym: gobierno del bloque, no planificación paralela."""

from datetime import timedelta
import hashlib
import json

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym


class ConflictoVersionBloque(RuntimeError):
    pass


class SolapeBloqueGym(RuntimeError):
    pass


class TransicionBloqueInvalida(RuntimeError):
    pass


class ActorBloqueNoAutorizado(PermissionError):
    pass


def _fingerprint(payload):
    serializado = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(serializado.encode('utf-8')).hexdigest()


def _estrategia_vigente(cliente, semana):
    return (
        EstrategiaSemanalGym.objects.filter(
            cliente=cliente,
            estado=EstrategiaSemanalGym.ESTADO_APROBADA,
            vigente_desde__lte=semana,
        )
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=semana))
        .order_by('-version')
        .first()
    )


@transaction.atomic
def proponer_bloque_gym(
    cliente, *, semana_inicio, semanas_previstas, objetivo_principal,
    objetivos_secundarios=None, limites_snapshot=None, motor_nombre='Helms',
    motor_version='actual', motivo='', predecesor=None,
):
    if semana_inicio.weekday() != 0:
        raise ValueError('El bloque debe comenzar en lunes.')
    if semanas_previstas < 1:
        raise ValueError('El bloque debe contener al menos una semana.')
    Cliente.objects.select_for_update().get(pk=cliente.pk)
    estrategia = _estrategia_vigente(cliente, semana_inicio)
    if estrategia is None:
        raise EstrategiaSemanalGym.DoesNotExist(
            'No existe estrategia semanal aprobada al inicio del bloque.'
        )
    fin = semana_inicio + timedelta(weeks=semanas_previstas) - timedelta(days=1)
    payload = {
        'semana_inicio': semana_inicio.isoformat(),
        'semanas_previstas': semanas_previstas,
        'semana_fin_prevista': fin.isoformat(),
        'estrategia_id': estrategia.pk,
        'objetivo_sesiones': estrategia.objetivo_sesiones,
        'minimo_valido': estrategia.minimo_valido,
        'objetivo_principal': objetivo_principal,
        'objetivos_secundarios': objetivos_secundarios or [],
        'limites_snapshot': limites_snapshot or {},
        'motor_nombre': motor_nombre,
        'motor_version': motor_version,
        'predecesor_id': predecesor.pk if predecesor else None,
    }
    fingerprint = _fingerprint(payload)
    existente = ContratoBloqueGym.objects.filter(
        cliente=cliente, fingerprint=fingerprint,
    ).first()
    if existente:
        return existente
    version = (
        ContratoBloqueGym.objects.filter(cliente=cliente).aggregate(maxima=Max('version'))['maxima']
        or 0
    ) + 1
    return ContratoBloqueGym.objects.create(
        cliente=cliente, version=version, predecesor=predecesor,
        estado=ContratoBloqueGym.ESTADO_PROPUESTO,
        semana_inicio=semana_inicio, semanas_previstas=semanas_previstas,
        semana_fin_prevista=fin, estrategia=estrategia,
        objetivo_sesiones=estrategia.objetivo_sesiones,
        minimo_valido=estrategia.minimo_valido,
        objetivo_principal=objetivo_principal,
        objetivos_secundarios=objetivos_secundarios or [],
        limites_snapshot=limites_snapshot or {}, motor_nombre=motor_nombre,
        motor_version=motor_version, fingerprint=fingerprint, motivo=motivo,
    )


@transaction.atomic
def activar_bloque_gym(bloque, *, version_esperada, actor):
    Cliente.objects.select_for_update().get(pk=bloque.cliente_id)
    bloque = ContratoBloqueGym.objects.select_for_update().select_related('cliente').get(pk=bloque.pk)
    if bloque.version != version_esperada:
        raise ConflictoVersionBloque('La propuesta visible ya no es la versión actual.')
    if actor is None or actor.pk != bloque.cliente.user_id:
        raise ActorBloqueNoAutorizado('Solo el propietario puede aprobar el bloque.')
    if bloque.estado == ContratoBloqueGym.ESTADO_ACTIVO:
        return bloque
    if bloque.estado != ContratoBloqueGym.ESTADO_PROPUESTO:
        raise TransicionBloqueInvalida('Solo una propuesta puede activarse.')
    solape = ContratoBloqueGym.objects.filter(
        cliente=bloque.cliente,
        estado__in=[ContratoBloqueGym.ESTADO_ACTIVO, ContratoBloqueGym.ESTADO_PAUSADO],
        semana_inicio__lte=bloque.semana_fin_prevista,
        semana_fin_prevista__gte=bloque.semana_inicio,
    ).exclude(pk=bloque.pk).exists()
    if solape:
        raise SolapeBloqueGym('Existe otro bloque abierto en el mismo rango.')
    bloque.estado = ContratoBloqueGym.ESTADO_ACTIVO
    bloque.aprobado_por = actor
    bloque.aprobado_en = timezone.now()
    bloque.save(update_fields=['estado', 'aprobado_por', 'aprobado_en', 'actualizado_en'])
    return bloque


@transaction.atomic
def pausar_bloque_gym(bloque, *, version_esperada):
    Cliente.objects.select_for_update().get(pk=bloque.cliente_id)
    bloque = ContratoBloqueGym.objects.select_for_update().get(pk=bloque.pk)
    if bloque.version != version_esperada:
        raise ConflictoVersionBloque('El bloque ya no coincide con la versión visible.')
    if bloque.estado == ContratoBloqueGym.ESTADO_PAUSADO:
        return bloque
    if bloque.estado != ContratoBloqueGym.ESTADO_ACTIVO:
        raise TransicionBloqueInvalida('Solo un bloque activo puede pausarse.')
    bloque.estado = ContratoBloqueGym.ESTADO_PAUSADO
    bloque.save(update_fields=['estado', 'actualizado_en'])
    return bloque


def auditar_deriva_bloque_gym(bloque):
    """Lectura factual. No evalúa causalidad ni modifica el plan."""
    from entrenos.services.estrategia_semanal_gym_service import evaluar_contrato_semanal_gym

    contratos = {
        contrato.indice_semana_bloque: contrato
        for contrato in bloque.contratos_semanales.prefetch_related('sesiones').all()
    }
    semanas = []
    conteos = {'objetivo': 0, 'minima_valida': 0, 'insuficiente': 0, 'sin_materializar': 0}
    for indice in range(1, bloque.semanas_previstas + 1):
        inicio = bloque.semana_inicio + timedelta(weeks=indice - 1)
        contrato = contratos.get(indice)
        if contrato is None:
            conteos['sin_materializar'] += 1
            semanas.append({
                'indice': indice, 'semana': inicio.isoformat(),
                'contrato_semanal_id': None, 'cumplimiento': 'sin_materializar',
                'sesiones_completadas': 0, 'deuda_generada': 0,
            })
            continue
        resultado = evaluar_contrato_semanal_gym(contrato)
        conteos[resultado['estado_cumplimiento']] += 1
        semanas.append({
            'indice': indice, 'semana': inicio.isoformat(),
            'contrato_semanal_id': contrato.pk,
            'cumplimiento': resultado['estado_cumplimiento'],
            'sesiones_completadas': resultado['sesiones_completadas'],
            'sesiones_reubicadas': resultado['sesiones_reubicadas'],
            'deuda_generada': 0,
        })
    return {
        'schema_version': 1, 'solo_lectura': True,
        'bloque_id': bloque.pk, 'bloque_version': bloque.version,
        'estado': bloque.estado, 'fingerprint': bloque.fingerprint,
        'semanas': semanas,
        'resumen': {
            'semanas_objetivo': conteos['objetivo'],
            'semanas_minimas_validas': conteos['minima_valida'],
            'semanas_insuficientes': conteos['insuficiente'],
            'semanas_sin_materializar': conteos['sin_materializar'],
            'deuda_generada': 0,
        },
    }
