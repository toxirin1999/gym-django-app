"""Contrato longitudinal Gym: gobierno del bloque, no planificación paralela."""

from datetime import date, timedelta
import hashlib
import json

from django.db import transaction
from django.db.models import Max, Q
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import (
    ContratoBloqueGym, EvaluacionBloqueGym, EstrategiaSemanalGym,
    SesionProgramada,
)


class ConflictoVersionBloque(RuntimeError):
    pass


class SolapeBloqueGym(RuntimeError):
    pass


class TransicionBloqueInvalida(RuntimeError):
    pass


class ActorBloqueNoAutorizado(PermissionError):
    pass


class BloqueAbierto(RuntimeError):
    pass


class EvidenciaBloqueIncompleta(RuntimeError):
    pass


class EvaluacionBloqueCongelada(RuntimeError):
    pass


class CierreBloquePendiente(RuntimeError):
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


def _exigir_propietario(cliente, actor):
    if actor is None or actor.pk != cliente.user_id:
        raise ActorBloqueNoAutorizado('Solo el propietario puede gestionar su bloque.')


def _exigir_sin_cierre_pendiente(cliente):
    if EvaluacionBloqueGym.objects.filter(
        bloque__cliente=cliente,
        estado_revision=EvaluacionBloqueGym.REVISION_PENDIENTE,
    ).exists():
        raise CierreBloquePendiente(
            'Hay un cierre del bloque pendiente de revisión antes de continuar.'
        )


def _resolver_estrategia_colaborativa(cliente, semana_inicio, actor):
    estrategia = _estrategia_vigente(cliente, semana_inicio)
    if estrategia and (
        estrategia.objetivo_sesiones == 5 and estrategia.minimo_valido == 3
    ):
        return estrategia
    from entrenos.services.estrategia_semanal_gym_service import aprobar_estrategia_semanal_gym
    return aprobar_estrategia_semanal_gym(
        cliente,
        objetivo_sesiones=5,
        minimo_valido=3,
        vigente_desde=semana_inicio,
        aprobado_por=actor,
        motivo='Estrategia canónica del bloque colaborativo Gym.',
    )


def consultar_bloque_gym_colaborativo(cliente):
    """Proyección de lectura para el Centro; nunca materializa ni modifica."""
    cierre_pendiente = EvaluacionBloqueGym.objects.filter(
        bloque__cliente=cliente,
        estado_revision=EvaluacionBloqueGym.REVISION_PENDIENTE,
    ).exists()
    bloque = (
        ContratoBloqueGym.objects.filter(
            cliente=cliente,
            estado__in=[
                ContratoBloqueGym.ESTADO_PROPUESTO,
                ContratoBloqueGym.ESTADO_ACTIVO,
                ContratoBloqueGym.ESTADO_PAUSADO,
            ],
        )
        .order_by('-version')
        .first()
    )
    if bloque is None:
        return {'cierre_pendiente': cierre_pendiente, 'bloque': None}
    objetivos = dict(Cliente.OBJETIVO_CHOICES)
    secundarios = {
        'gemelos': 'Gemelos', 'hombros': 'Hombros', 'brazos': 'Brazos',
        'espalda': 'Espalda', 'pecho': 'Pecho', 'gluteos': 'Glúteos',
        'cuadriceps': 'Cuádriceps',
    }
    return {
        'cierre_pendiente': cierre_pendiente,
        'bloque': bloque,
        'card': {
            'estado': bloque.estado,
            'estado_label': dict(ContratoBloqueGym.ESTADOS).get(bloque.estado, bloque.estado),
            'semana_inicio': bloque.semana_inicio,
            'semana_fin': bloque.semana_fin_prevista,
            'semanas': bloque.semanas_previstas,
            'objetivo_label': objetivos.get(bloque.objetivo_principal, 'Objetivo del bloque'),
            'secundarios': [
                secundarios[item]
                for item in bloque.objetivos_secundarios
                if item in secundarios
            ],
            'objetivo_sesiones': bloque.objetivo_sesiones,
            'minimo_valido': bloque.minimo_valido,
            'version': bloque.version,
        },
    }


@transaction.atomic
def preparar_bloque_gym_colaborativo(
    cliente, *, semana_inicio, semanas_previstas, objetivo_principal,
    objetivos_secundarios=None, motivo='', actor,
):
    _exigir_propietario(cliente, actor)
    Cliente.objects.select_for_update().get(pk=cliente.pk)
    _exigir_sin_cierre_pendiente(cliente)
    if ContratoBloqueGym.objects.select_for_update().filter(
        cliente=cliente,
        estado__in=[
            ContratoBloqueGym.ESTADO_PROPUESTO,
            ContratoBloqueGym.ESTADO_ACTIVO,
            ContratoBloqueGym.ESTADO_PAUSADO,
        ],
    ).exists():
        raise TransicionBloqueInvalida(
            'Ya existe un bloque o una propuesta; usa su acción de revisión.'
        )
    _resolver_estrategia_colaborativa(cliente, semana_inicio, actor)
    return proponer_bloque_gym(
        cliente,
        semana_inicio=semana_inicio,
        semanas_previstas=semanas_previstas,
        objetivo_principal=objetivo_principal,
        objetivos_secundarios=objetivos_secundarios or [],
        limites_snapshot={'sin_autoajustes': True},
        motor_nombre='Helms',
        motor_version='actual',
        motivo=motivo,
    )


@transaction.atomic
def revisar_bloque_gym_colaborativo(
    bloque, *, version_esperada, semana_inicio, semanas_previstas,
    objetivo_principal, objetivos_secundarios=None, motivo='', actor,
):
    cliente = Cliente.objects.select_for_update().get(pk=bloque.cliente_id)
    _exigir_propietario(cliente, actor)
    _exigir_sin_cierre_pendiente(cliente)
    anterior = ContratoBloqueGym.objects.select_for_update().get(pk=bloque.pk)
    if anterior.version != version_esperada:
        raise ConflictoVersionBloque('La propuesta visible ya no es la versión actual.')
    if anterior.estado != ContratoBloqueGym.ESTADO_PROPUESTO:
        raise TransicionBloqueInvalida('Solo una propuesta puede revisarse.')
    _resolver_estrategia_colaborativa(cliente, semana_inicio, actor)
    anterior.estado = ContratoBloqueGym.ESTADO_RETIRADO
    anterior.save(update_fields=['estado', 'actualizado_en'])
    return proponer_bloque_gym(
        cliente,
        semana_inicio=semana_inicio,
        semanas_previstas=semanas_previstas,
        objetivo_principal=objetivo_principal,
        objetivos_secundarios=objetivos_secundarios or [],
        limites_snapshot={'sin_autoajustes': True},
        motor_nombre='Helms',
        motor_version='actual',
        motivo=motivo,
        predecesor=anterior,
    )


@transaction.atomic
def retirar_propuesta_bloque_gym(bloque, *, version_esperada, actor):
    cliente = Cliente.objects.select_for_update().get(pk=bloque.cliente_id)
    _exigir_propietario(cliente, actor)
    _exigir_sin_cierre_pendiente(cliente)
    propuesta = ContratoBloqueGym.objects.select_for_update().get(pk=bloque.pk)
    if propuesta.version != version_esperada:
        raise ConflictoVersionBloque('La propuesta visible ya no es la versión actual.')
    if propuesta.estado != ContratoBloqueGym.ESTADO_PROPUESTO:
        raise TransicionBloqueInvalida('Solo una propuesta puede retirarse.')
    propuesta.estado = ContratoBloqueGym.ESTADO_RETIRADO
    propuesta.save(update_fields=['estado', 'actualizado_en'])
    return propuesta


def previsualizar_propuesta_bloque_gym(
    cliente, *, semana_inicio, semanas_previstas, objetivo_principal,
    objetivos_secundarios=None, limites_snapshot=None, motor_nombre='Helms',
    motor_version='actual', predecesor=None,
):
    """Calcula el contrato candidato completo sin adquirir locks ni escribir."""
    if semana_inicio.weekday() != 0:
        raise ValueError('El bloque debe comenzar en lunes.')
    if semanas_previstas < 1:
        raise ValueError('El bloque debe contener al menos una semana.')
    estrategia = _estrategia_vigente(cliente, semana_inicio)
    if estrategia is None:
        raise EstrategiaSemanalGym.DoesNotExist(
            'No existe estrategia semanal aprobada al inicio del bloque.'
        )
    if predecesor is not None and predecesor.cliente_id != cliente.pk:
        raise ValueError('El predecesor debe pertenecer al mismo cliente.')
    fin = semana_inicio + timedelta(weeks=semanas_previstas) - timedelta(days=1)
    snapshot = {
        'semana_inicio': semana_inicio.isoformat(),
        'semanas_previstas': semanas_previstas,
        'semana_fin_prevista': fin.isoformat(),
        'estrategia_id': estrategia.pk,
        'estrategia_version': estrategia.version,
        'objetivo_sesiones': estrategia.objetivo_sesiones,
        'minimo_valido': estrategia.minimo_valido,
        'objetivo_principal': objetivo_principal,
        'objetivos_secundarios': objetivos_secundarios or [],
        'limites_snapshot': limites_snapshot or {},
        'motor': {'nombre': motor_nombre, 'version': motor_version},
        'predecesor_id': predecesor.pk if predecesor else None,
    }
    # La versión de la estrategia está presente para auditoría, pero la
    # identidad relacional ya queda fijada por estrategia_id.
    identidad = {
        clave: valor for clave, valor in snapshot.items()
        if clave != 'estrategia_version'
    }
    identidad['motor_nombre'] = identidad.pop('motor')['nombre']
    identidad['motor_version'] = snapshot['motor']['version']
    fingerprint = _fingerprint(identidad)
    existente = ContratoBloqueGym.objects.filter(
        cliente=cliente, fingerprint=fingerprint,
    ).only('id').first()
    return {
        **snapshot,
        'fingerprint': fingerprint,
        'propuesta_existente': bool(existente),
        'propuesta_existente_id': existente.pk if existente else None,
    }


@transaction.atomic
def proponer_bloque_gym(
    cliente, *, semana_inicio, semanas_previstas, objetivo_principal,
    objetivos_secundarios=None, limites_snapshot=None, motor_nombre='Helms',
    motor_version='actual', motivo='', predecesor=None,
):
    Cliente.objects.select_for_update().get(pk=cliente.pk)
    previo = previsualizar_propuesta_bloque_gym(
        cliente, semana_inicio=semana_inicio,
        semanas_previstas=semanas_previstas,
        objetivo_principal=objetivo_principal,
        objetivos_secundarios=objetivos_secundarios,
        limites_snapshot=limites_snapshot,
        motor_nombre=motor_nombre, motor_version=motor_version,
        predecesor=predecesor,
    )
    estrategia = EstrategiaSemanalGym.objects.get(pk=previo['estrategia_id'])
    fin = date.fromisoformat(previo['semana_fin_prevista'])
    fingerprint = previo['fingerprint']
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
    _exigir_sin_cierre_pendiente(bloque.cliente)
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


def previsualizar_cierre_bloque_gym(bloque, *, hoy=None):
    """Construye evidencia solo desde contratos y evaluaciones semanales."""
    hoy = hoy or timezone.localdate()
    contratos = {
        contrato.indice_semana_bloque: contrato
        for contrato in bloque.contratos_semanales.select_related('evaluacion').prefetch_related('sesiones')
    }
    semanas = []
    impedimentos = []
    if hoy <= bloque.semana_fin_prevista:
        impedimentos.append('bloque_abierto')

    estados = []
    seguridad_dominante = False
    for indice in range(1, bloque.semanas_previstas + 1):
        contrato = contratos.get(indice)
        if contrato is None or contrato.sesiones.count() != bloque.objetivo_sesiones:
            impedimentos.append(f'semana_no_materializada:{indice}')
            semanas.append({
                'indice': indice, 'contrato_semanal_id': contrato.pk if contrato else None,
                'evaluacion_semanal_id': None, 'revision': None,
                'cumplimiento': 'sin_evidencia', 'protegidas_seguridad': 0,
            })
            continue
        try:
            evaluacion = contrato.evaluacion
        except ObjectDoesNotExist:
            # No se importa ninguna fuente alternativa ni se recalcula la semana.
            evaluacion = None
        if evaluacion is None:
            impedimentos.append(f'evaluacion_ausente:{indice}')
            semanas.append({
                'indice': indice, 'contrato_semanal_id': contrato.pk,
                'evaluacion_semanal_id': None, 'revision': None,
                'cumplimiento': 'sin_evidencia', 'protegidas_seguridad': 0,
            })
            continue
        if evaluacion.estado_revision != evaluacion.ESTADO_ACEPTADA:
            impedimentos.append(f'evaluacion_no_aceptada:{indice}')
        snapshot = evaluacion.evidencia_snapshot or {}
        conteos = snapshot.get('conteos_estado') or {}
        protegidas = int(conteos.get(SesionProgramada.ESTADO_CANCELADA_LESION, 0) or 0)
        completadas = int(evaluacion.sesiones_completadas or 0)
        estado = evaluacion.estado_cumplimiento
        if (
            estado == evaluacion.CUMPLIMIENTO_INSUFICIENTE
            and protegidas > 0
            and completadas + protegidas >= bloque.minimo_valido
        ):
            seguridad_dominante = True
        estados.append(estado)
        semanas.append({
            'indice': indice, 'contrato_semanal_id': contrato.pk,
            'evaluacion_semanal_id': evaluacion.pk,
            'revision': evaluacion.estado_revision,
            'cumplimiento': estado,
            'sesiones_completadas': completadas,
            'protegidas_seguridad': protegidas,
            'evidencia_semanal': snapshot,
        })

    faltantes = any(
        codigo.startswith(('semana_no_materializada:', 'evaluacion_ausente:', 'evaluacion_no_aceptada:'))
        for codigo in impedimentos
    )
    if faltantes:
        resultado = EvaluacionBloqueGym.RESULTADO_EVIDENCIA_INSUFICIENTE
    elif seguridad_dominante:
        resultado = EvaluacionBloqueGym.RESULTADO_SEGURIDAD
    elif estados and all(estado == 'objetivo' for estado in estados):
        resultado = EvaluacionBloqueGym.RESULTADO_OBJETIVO
    elif estados and all(estado in ('objetivo', 'minima_valida') for estado in estados):
        resultado = EvaluacionBloqueGym.RESULTADO_MINIMO
    else:
        resultado = EvaluacionBloqueGym.RESULTADO_DERIVA

    evidencia = {
        'schema_version': 1,
        'bloque_id': bloque.pk,
        'bloque_version': bloque.version,
        'bloque_fingerprint': bloque.fingerprint,
        'semana_inicio': bloque.semana_inicio.isoformat(),
        'semana_fin_prevista': bloque.semana_fin_prevista.isoformat(),
        'semanas_previstas': bloque.semanas_previstas,
        'objetivo_sesiones': bloque.objetivo_sesiones,
        'minimo_valido': bloque.minimo_valido,
        'semanas': semanas,
    }
    return {
        'schema_version': 1,
        'solo_lectura': True,
        'bloque_id': bloque.pk,
        'estado_resultado': resultado,
        'fingerprint_evidencia': _fingerprint(evidencia),
        'evidencia_snapshot': evidencia,
        'impedimentos': impedimentos,
        'cierre_persistible': not impedimentos,
    }


@transaction.atomic
def cerrar_bloque_gym(bloque, *, hoy=None):
    hoy = hoy or timezone.localdate()
    Cliente.objects.select_for_update().get(pk=bloque.cliente_id)
    bloque = ContratoBloqueGym.objects.select_for_update().get(pk=bloque.pk)
    previo = previsualizar_cierre_bloque_gym(bloque, hoy=hoy)
    if hoy <= bloque.semana_fin_prevista:
        raise BloqueAbierto('El bloque todavía no ha alcanzado su fecha de fin.')
    if previo['impedimentos']:
        raise EvidenciaBloqueIncompleta(
            'El cierre exige todas las semanas materializadas y sus evaluaciones aceptadas.'
        )
    existente = EvaluacionBloqueGym.objects.select_for_update().filter(
        bloque=bloque, fingerprint_evidencia=previo['fingerprint_evidencia'],
    ).first()
    if existente:
        return existente
    ultima = EvaluacionBloqueGym.objects.select_for_update().filter(
        bloque=bloque,
    ).order_by('-version_calculo').first()
    if ultima and ultima.estado_revision == EvaluacionBloqueGym.REVISION_ACEPTADA:
        raise EvaluacionBloqueCongelada('El bloque ya tiene un cierre aceptado e inmutable.')
    version = (ultima.version_calculo if ultima else 0) + 1
    return EvaluacionBloqueGym.objects.create(
        bloque=bloque, version_calculo=version,
        fingerprint_evidencia=previo['fingerprint_evidencia'],
        estado_resultado=previo['estado_resultado'],
        evidencia_snapshot=previo['evidencia_snapshot'],
    )


@transaction.atomic
def responder_evaluacion_bloque_gym(evaluacion, *, actor, aceptar):
    evaluacion = EvaluacionBloqueGym.objects.select_for_update().select_related(
        'bloque__cliente',
    ).get(pk=evaluacion.pk)
    if actor is None or actor.pk != evaluacion.bloque.cliente.user_id:
        raise ActorBloqueNoAutorizado('Solo el propietario puede revisar el cierre.')
    nuevo = (
        EvaluacionBloqueGym.REVISION_ACEPTADA
        if aceptar else EvaluacionBloqueGym.REVISION_RECHAZADA
    )
    if evaluacion.estado_revision == nuevo:
        return evaluacion
    if evaluacion.estado_revision != EvaluacionBloqueGym.REVISION_PENDIENTE:
        raise EvaluacionBloqueCongelada('La evaluación ya tiene una respuesta distinta.')
    evaluacion.estado_revision = nuevo
    evaluacion.revisado_por = actor
    evaluacion.revisado_en = timezone.now()
    evaluacion.save(update_fields=[
        'estado_revision', 'revisado_por', 'revisado_en', 'actualizado_en',
    ])
    if aceptar:
        bloque = ContratoBloqueGym.objects.select_for_update().get(pk=evaluacion.bloque_id)
        if bloque.estado not in (
            ContratoBloqueGym.ESTADO_ACTIVO, ContratoBloqueGym.ESTADO_PAUSADO,
            ContratoBloqueGym.ESTADO_FINALIZADO,
        ):
            raise TransicionBloqueInvalida('El bloque no admite un cierre aceptado.')
        if bloque.estado != ContratoBloqueGym.ESTADO_FINALIZADO:
            bloque.estado = ContratoBloqueGym.ESTADO_FINALIZADO
            bloque.save(update_fields=['estado', 'actualizado_en'])
    return evaluacion
