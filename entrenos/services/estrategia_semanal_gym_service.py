"""Gestión transaccional del contrato semanal de entrenamiento Gym."""

from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.db.models import F, Max, Q

from clientes.models import Cliente
from entrenos.models import (
    ContratoSemanalGym,
    EntrenoRealizado,
    EstrategiaSemanalGym,
    SesionProgramada,
)


class ContratoSemanalIncompleto(ValueError):
    pass


def _build_planificador(cliente, contrato):
    """Construye Helms desde el snapshot, no desde configuración mutable."""
    from analytics.planificador_helms.core import PlanificadorHelms
    from analytics.planificador_helms.models.perfil_cliente import PerfilCliente

    perfil = PerfilCliente({
        'id': cliente.id,
        'nombre': getattr(cliente, 'nombre', ''),
        'experiencia_años': getattr(cliente, 'experiencia_años', 0),
        'objetivo_principal': getattr(cliente, 'objetivo_principal', 'hipertrofia'),
        'dias_disponibles': contrato.objetivo_sesiones,
        'año_planificacion': contrato.semana.year,
        'nivel_estres': getattr(cliente, 'nivel_estres', 5),
        'calidad_sueño': getattr(cliente, 'calidad_sueño', 7),
        'nivel_energia': getattr(cliente, 'nivel_energia', 7),
        'ejercicios_evitar': getattr(cliente, 'ejercicios_evitar', []) or [],
        'maximos_actuales': getattr(cliente, 'one_rm_data', {}) or {},
    })
    return PlanificadorHelms(perfil)


def _generar_propuestas(cliente, contrato):
    planificador = _build_planificador(cliente, contrato)
    propuestas = []
    for offset in range(7):
        fecha = contrato.semana + timedelta(days=offset)
        entrenamiento = planificador.generar_entrenamiento_para_fecha(fecha)
        if entrenamiento and entrenamiento.get('ejercicios'):
            propuestas.append((fecha, entrenamiento))
    if len(propuestas) != contrato.objetivo_sesiones:
        raise ContratoSemanalIncompleto(
            f'El motor produjo {len(propuestas)} sesiones y el contrato exige '
            f'{contrato.objetivo_sesiones}.'
        )
    return propuestas


def previsualizar_contrato_semanal_gym(cliente, semana):
    """Calcula las identidades prescritas sin crear contrato ni sesiones."""
    if semana.weekday() != 0:
        raise ValueError('La semana del contrato debe comenzar en lunes.')
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
    contrato_virtual = SimpleNamespace(
        semana=semana,
        objetivo_sesiones=estrategia.objetivo_sesiones,
    )
    return _generar_propuestas(cliente, contrato_virtual)


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


@transaction.atomic
def materializar_contrato_semanal_gym(cliente, semana):
    """Persiste todas las identidades prescritas por el contrato, sin duplicar."""
    from entrenos.services.sesion_recomendada import inferir_prioridad_sesion

    Cliente.objects.select_for_update().get(pk=cliente.pk)
    contrato = abrir_contrato_semanal_gym(cliente, semana)
    contrato = ContratoSemanalGym.objects.select_for_update().get(pk=contrato.pk)
    propuestas = _generar_propuestas(cliente, contrato)

    fechas = [fecha for fecha, _ in propuestas]
    existentes = {
        sesion.fecha_prevista: sesion
        for sesion in SesionProgramada.objects.select_for_update().filter(
            cliente=cliente,
            fecha_prevista__in=fechas,
        )
    }
    for fecha, entrenamiento in propuestas:
        sesion = existentes.get(fecha)
        if sesion is not None:
            if sesion.contrato_semanal_id not in (None, contrato.pk):
                raise ContratoSemanalIncompleto(
                    f'La sesión de {fecha.isoformat()} pertenece a otro contrato.'
                )
            campos = []
            if sesion.contrato_semanal_id is None:
                sesion.contrato_semanal = contrato
                campos.append('contrato_semanal')
            if sesion.semana_prescrita is None:
                sesion.semana_prescrita = semana
                campos.append('semana_prescrita')
            if not sesion.nombre_sesion:
                sesion.nombre_sesion = entrenamiento.get('rutina_nombre', '')
                campos.append('nombre_sesion')
            if not sesion.bloque_nombre:
                sesion.bloque_nombre = entrenamiento.get('bloque', '')
                campos.append('bloque_nombre')
            if sesion.dia_numero is None:
                sesion.dia_numero = entrenamiento.get('dia')
                campos.append('dia_numero')
            if campos:
                campos.append('actualizada_en')
                sesion.save(update_fields=campos)
            continue

        # `fecha` conserva la identidad del día prescrito. `fecha_ejecucion`
        # solo expresa cuándo se realizó y permite reconocer reubicaciones.
        candidatos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha=fecha,
        ).order_by('id')
        if candidatos.count() > 1:
            raise ContratoSemanalIncompleto(
                f'Hay más de un entrenamiento real para {fecha.isoformat()}.'
            )
        entreno = candidatos.first()
        sesion = SesionProgramada.objects.create(
            cliente=cliente,
            contrato_semanal=contrato,
            semana_prescrita=semana,
            fecha_prevista=fecha,
            fecha_realizada=(entreno.fecha_ejecucion or entreno.fecha) if entreno else None,
            estado=(
                SesionProgramada.ESTADO_COMPLETADA
                if entreno else SesionProgramada.ESTADO_PENDIENTE
            ),
            prioridad=(
                inferir_prioridad_sesion(entrenamiento)
                or SesionProgramada.PRIORIDAD_ALTA
            ),
            nombre_sesion=entrenamiento.get('rutina_nombre', ''),
            bloque_nombre=entrenamiento.get('bloque', ''),
            dia_numero=entrenamiento.get('dia'),
            entreno_realizado=entreno,
            motivo_estado=(
                'Sesión ya completada al abrir el contrato.'
                if entreno else 'Sesión prescrita por el contrato semanal.'
            ),
        )
    return contrato
