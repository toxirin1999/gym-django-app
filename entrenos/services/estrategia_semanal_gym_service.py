"""Gestión transaccional del contrato semanal de entrenamiento Gym."""

from datetime import timedelta

from django.db import transaction
from django.db.models import F, Max, Q

from clientes.models import Cliente
from entrenos.models import ContratoSemanalGym, EstrategiaSemanalGym, SesionProgramada


@transaction.atomic
def aprobar_estrategia_semanal_gym(
    cliente,
    *,
    objetivo_sesiones,
    minimo_valido,
    vigente_desde,
    aprobado_por=None,
    motivo='',
):
    """Aprueba una versión y retira atómicamente cualquier versión vigente."""
    if minimo_valido < 1 or objetivo_sesiones < minimo_valido or objetivo_sesiones > 7:
        raise ValueError('El mínimo válido debe ser positivo y no superar el objetivo.')

    # Serializa aprobaciones concurrentes incluso cuando aún no existe ninguna
    # estrategia para el cliente.
    cliente_bloqueado = Cliente.objects.select_for_update().get(pk=cliente.pk)
    estrategias = EstrategiaSemanalGym.objects.select_for_update().filter(cliente=cliente)
    ultima_version = estrategias.aggregate(maxima=Max('version'))['maxima'] or 0
    estrategias.filter(estado=EstrategiaSemanalGym.ESTADO_APROBADA).update(
        estado=EstrategiaSemanalGym.ESTADO_RETIRADA,
        vigente_hasta=vigente_desde - timedelta(days=1),
    )
    estrategia = EstrategiaSemanalGym.objects.create(
        cliente=cliente,
        version=ultima_version + 1,
        objetivo_sesiones=objetivo_sesiones,
        minimo_valido=minimo_valido,
        vigente_desde=vigente_desde,
        estado=EstrategiaSemanalGym.ESTADO_APROBADA,
        aprobado_por=aprobado_por,
        motivo=motivo,
    )
    # Proyección transitoria para el planificador Helms existente. La estrategia
    # es la autoridad versionada; dias_disponibles sigue siendo su entrada legacy.
    if cliente_bloqueado.dias_disponibles != objetivo_sesiones:
        cliente_bloqueado.dias_disponibles = objetivo_sesiones
        cliente_bloqueado.save(update_fields=['dias_disponibles'])
    return estrategia


@transaction.atomic
def abrir_contrato_semanal_gym(cliente, semana):
    """Abre una semana con una copia inmutable de los umbrales aplicables."""
    if semana.weekday() != 0:
        raise ValueError('La semana del contrato debe comenzar en lunes.')
    Cliente.objects.select_for_update().get(pk=cliente.pk)
    existente = ContratoSemanalGym.objects.select_for_update().filter(
        cliente=cliente, semana=semana,
    ).first()
    if existente:
        return existente

    estrategia = (
        EstrategiaSemanalGym.objects.filter(
            cliente=cliente,
            estado=EstrategiaSemanalGym.ESTADO_APROBADA,
            vigente_desde__lte=semana,
        )
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=semana))
        .order_by('-version')
        .first()
    )
    if estrategia is None:
        raise EstrategiaSemanalGym.DoesNotExist(
            'No existe una estrategia Gym aprobada y vigente para esta semana.'
        )
    return ContratoSemanalGym.objects.create(
        cliente=cliente,
        estrategia=estrategia,
        semana=semana,
        objetivo_sesiones=estrategia.objetivo_sesiones,
        minimo_valido=estrategia.minimo_valido,
    )


def evaluar_contrato_semanal_gym(contrato):
    """Evalúa adherencia sin trasladar sesiones pendientes como deuda futura."""
    sesiones = contrato.sesiones.all()
    completadas = sesiones.filter(estado=SesionProgramada.ESTADO_COMPLETADA)
    numero_completadas = completadas.count()
    if numero_completadas >= contrato.objetivo_sesiones:
        estado = 'objetivo'
    elif numero_completadas >= contrato.minimo_valido:
        estado = 'minima_valida'
    else:
        estado = 'insuficiente'

    return {
        'estado_cumplimiento': estado,
        'sesiones_completadas': numero_completadas,
        'sesiones_reubicadas': completadas.filter(fecha_realizada__isnull=False).exclude(fecha_realizada=F('fecha_prevista')).count(),
        'sesiones_pendientes': sesiones.filter(estado=SesionProgramada.ESTADO_PENDIENTE).count(),
        'deuda_generada': 0,
    }
