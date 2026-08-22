import hashlib
import json

from django.db import transaction
from django.utils import timezone

from entrenos.models import ContratoBloqueGym
from hyrox.models import ContratoCampanaHyrox, HyroxObjective, HyroxSession


def _permisos(*, explorar=False, ejecutar=False):
    return {
        'aportar_carga': True, 'sincronizar_strava': True, 'seguridad': True,
        'registro_manual': True, 'lecturas_exploracion': explorar,
        'generar_plan': ejecutar, 'programar_sesiones': ejecutar,
        'correctivos': ejecutar, 'autoajuste': ejecutar, 'joi_hyrox': ejecutar,
        'competir_con_gym': False,
    }


PERMISOS = {
    'inactiva': _permisos(),
    'exploracion': _permisos(explorar=True),
    'activa': _permisos(explorar=True, ejecutar=True),
    'finalizada': _permisos(),
}


class CampanaHyroxNoAutoriza(PermissionError):
    """La campaña vigente no autoriza una mutación prescriptiva Hyrox."""

    def __init__(self, *, accion, autoridad):
        self.accion = accion
        self.autoridad = autoridad
        super().__init__(
            f"La campaña Hyrox {autoridad['estado']} no autoriza {accion}."
        )

def _inventario(code, superficie, mutacion, permiso, siempre=False, cubierto=False):
    return {'code': code, 'superficie': superficie, 'mutacion': mutacion,
            'permiso_requerido': permiso, 'siempre_permitido': siempre,
            'cubierto_7a': cubierto}


INVENTARIO_AUTOMATIZACIONES = [
    _inventario('plan_generacion', 'hyrox.views', 'crear sesiones futuras', 'generar_plan', cubierto=True),
    _inventario('plan_regeneracion', 'hyrox.views', 'borrar/regenerar plan', 'generar_plan', cubierto=True),
    _inventario('auto_adjust_override', 'hyrox.views', 'ajustar o sobrescribir sesión', 'autoajuste', cubierto=True),
    _inventario('lesion_regeneracion', 'hyrox.models.UserInjury', 'invalidar/regenerar sesiones', 'generar_plan', cubierto=True),
    _inventario('adaptacion_doble', 'hyrox.training_engine', 'adaptar sesión por dos motores', 'autoajuste', cubierto=True),
    _inventario('rm_pace', 'hyrox.signals', 'actualizar RM o ritmos', 'correctivos', cubierto=True),
    _inventario('correctivos', 'hyrox.services', 'crear sesiones correctivas', 'correctivos', cubierto=True),
    _inventario('deload', 'hyrox.training_engine.DeloadAutoTrigger', 'crear deload', 'autoajuste', cubierto=True),
    _inventario('bitacora_fatiga', 'hyrox.signals', 'actualizar fatiga desde bitácora', 'autoajuste', cubierto=True),
    _inventario('gym_fatiga_rm', 'entrenos.signals', 'actualizar fatiga/RM Hyrox desde Gym', 'autoajuste', cubierto=True),
    _inventario('cinco_k', 'hyrox.signals', 'recalibrar ritmos desde 5K', 'correctivos', cubierto=True),
    _inventario('joi_countdown', 'joi.services', 'generar voz countdown', 'joi_hyrox'),
    _inventario('joi_post', 'joi.services', 'generar voz post sesión', 'joi_hyrox'),
    _inventario('joi_readiness', 'joi.services', 'verbalizar readiness', 'joi_hyrox'),
    _inventario('joi_estancamiento', 'joi.services', 'verbalizar estancamiento', 'joi_hyrox'),
    _inventario('dashboard_gym_no_canonico', 'clientes.views', 'mostrar autoridad Hyrox paralela', 'lecturas_exploracion'),
]

TRANSICIONES = {
    None: {'inactiva', 'exploracion'},
    'inactiva': {'exploracion', 'finalizada'},
    'exploracion': {'activa', 'inactiva', 'finalizada'},
    'activa': {'exploracion', 'inactiva', 'finalizada'},
    'finalizada': set(),
}


def _vigente(cliente):
    return ContratoCampanaHyrox.objects.filter(cliente=cliente).order_by('-version', '-pk').first()


def resolver_autoridad_campana(cliente, fecha):
    contrato = _vigente(cliente)
    if contrato is None:
        return {'estado': 'inactiva', 'origen': 'inactiva_legacy', 'contrato_id': None, 'permisos': dict(PERMISOS['inactiva']), 'hallazgos': []}
    estado, hallazgos = contrato.estado, []
    if estado == 'activa':
        if not contrato.objetivo_id or contrato.objetivo.cliente_id != cliente.pk:
            hallazgos.append('objetivo_invalido')
        elif contrato.objetivo.fecha_evento <= fecha:
            hallazgos.append('objetivo_vencido')
        if not contrato.bloque_gym_id or contrato.bloque_gym.cliente_id != cliente.pk or contrato.bloque_gym.estado not in ('activo', 'pausado'):
            hallazgos.append('bloque_gym_no_abierto')
        if hallazgos:
            estado = 'inactiva'
    return {'estado': estado, 'origen': 'contrato', 'contrato_id': contrato.pk,
            'objetivo_id': contrato.objetivo_id, 'version': contrato.version,
            'permisos': dict(PERMISOS[estado]), 'hallazgos': hallazgos}


def exigir_prescripcion(cliente, *, accion='generar_plan', fecha=None, objective=None):
    """Gate único para cualquier escritura que prescriba el futuro Hyrox."""
    autoridad = resolver_autoridad_campana(
        cliente,
        fecha or timezone.localdate(),
    )
    if not autoridad['permisos'].get(accion, False):
        raise CampanaHyroxNoAutoriza(accion=accion, autoridad=autoridad)
    if accion in {'generar_plan', 'programar_sesiones', 'autoajuste', 'correctivos'}:
        contrato = ContratoCampanaHyrox.objects.filter(
            pk=autoridad.get('contrato_id')
        ).first()
        if objective is None or contrato is None or contrato.objetivo_id != objective.pk:
            autoridad['hallazgos'] = [*autoridad.get('hallazgos', []), 'objetivo_fuera_campana']
            raise CampanaHyroxNoAutoriza(accion=accion, autoridad=autoridad)
        snapshot = contrato.objetivo_snapshot or {}
        snapshot_coherente = (
            snapshot.get('id') == objective.pk
            and snapshot.get('fecha_evento') == str(objective.fecha_evento)
            and isinstance(contrato.fingerprint, str)
            and len(contrato.fingerprint) == 64
        )
        if not snapshot_coherente:
            autoridad['hallazgos'] = [
                *autoridad.get('hallazgos', []),
                'objetivo_snapshot_incoherente',
            ]
            raise CampanaHyroxNoAutoriza(accion=accion, autoridad=autoridad)
    return autoridad


def autoriza_efectos_campana(objective, *, accion='autoajuste', fecha=None):
    """Booleano seguro para signals: una denegación equivale a no-op factual."""
    if objective is None:
        return False
    try:
        exigir_prescripcion(
            objective.cliente,
            accion=accion,
            fecha=fecha,
            objective=objective,
        )
    except CampanaHyroxNoAutoriza:
        return False
    return True


def previsualizar(cliente, estado, objetivo=None, bloque=None, limites=None, fecha=None):
    fecha = fecha or timezone.localdate()
    if estado == 'activa' and (objetivo is None or bloque is None):
        raise ValueError('Una campaña activa exige objetivo y bloque Gym.')
    if objetivo and objetivo.cliente_id != cliente.pk:
        raise ValueError('El objetivo pertenece a otro cliente.')
    if bloque and bloque.cliente_id != cliente.pk:
        raise ValueError('El bloque Gym pertenece a otro cliente.')
    if estado == 'activa' and objetivo.fecha_evento <= fecha:
        raise ValueError('Una campaña activa exige un objetivo futuro.')
    if estado == 'activa' and bloque.estado not in ('activo', 'pausado'):
        raise ValueError('Una campaña activa exige un bloque Gym activo o pausado.')
    actual = _vigente(cliente)
    version = (actual.version + 1) if actual else 1
    osnap = ({'id': objetivo.pk, 'fecha_evento': str(objetivo.fecha_evento), 'estado': objetivo.estado} if objetivo else {})
    bsnap = ({'id': bloque.pk, 'estado': bloque.estado, 'version': bloque.version} if bloque else {})
    semantica = {'cliente_id': cliente.pk, 'estado': estado, 'objetivo_id': objetivo.pk if objetivo else None,
            'bloque_gym_id': bloque.pk if bloque else None, 'objetivo_snapshot': osnap,
            'bloque_gym_snapshot': bsnap, 'limites_snapshot': limites or {'autoridad_gym_soberana': True}}
    vigente_identica = bool(actual and all((
        actual.estado == semantica['estado'],
        actual.objetivo_id == semantica['objetivo_id'],
        actual.bloque_gym_id == semantica['bloque_gym_id'],
        actual.objetivo_snapshot == semantica['objetivo_snapshot'],
        actual.bloque_gym_snapshot == semantica['bloque_gym_snapshot'],
        actual.limites_snapshot == semantica['limites_snapshot'],
    )))
    if vigente_identica:
        return {
            'version': actual.version, 'predecesor_id': actual.predecesor_id,
            **semantica, 'fingerprint': actual.fingerprint,
            'contrato_existente_id': actual.pk, 'propuesta_existente': True,
        }
    base = {'version': version, 'predecesor_id': actual.pk if actual else None, **semantica}
    identidad_transicion = {'predecesor_id': base['predecesor_id'], **semantica}
    base['fingerprint'] = hashlib.sha256(
        json.dumps(identidad_transicion, sort_keys=True).encode()
    ).hexdigest()
    base['contrato_existente_id'] = None
    base['propuesta_existente'] = False
    return base


@transaction.atomic
def configurar(cliente, estado, objetivo=None, bloque=None, limites=None, motivo='',
               version_esperada=None, actor=None):
    list(type(cliente).objects.select_for_update().filter(pk=cliente.pk))
    actual = _vigente(cliente)
    actual_version = actual.version if actual else 0
    if version_esperada is not None and actual_version != version_esperada:
        raise ValueError(f'Versión esperada {version_esperada}; actual {actual_version}.')
    if actor is None or actor.pk != cliente.user_id:
        raise ValueError('El actor no es propietario del cliente.')
    data = previsualizar(cliente, estado, objetivo, bloque, limites)
    previo = actual.estado if actual else None
    if data['contrato_existente_id']:
        return actual
    if previo == 'finalizada':
        raise ValueError('Una campaña finalizada es terminal.')
    if estado not in TRANSICIONES[previo]:
        raise ValueError(f'Transición inválida: {previo or "ausencia"} → {estado}.')
    return ContratoCampanaHyrox.objects.create(
        cliente=cliente, version=data['version'], predecesor=actual, estado=estado,
        objetivo=objetivo, bloque_gym=bloque, objetivo_snapshot=data['objetivo_snapshot'],
        bloque_gym_snapshot=data['bloque_gym_snapshot'], limites_snapshot=data['limites_snapshot'],
        fingerprint=data['fingerprint'], motivo=motivo, aprobado_en=timezone.now(),
        aprobado_por=actor,
    )


def auditar_campana(cliente, fecha):
    autoridad = resolver_autoridad_campana(cliente, fecha)
    hallazgos = []
    objetivos = HyroxObjective.objects.filter(cliente=cliente, estado='activo')
    if autoridad['origen'] == 'inactiva_legacy' and objetivos.exists():
        hallazgos.append({'code': 'objetivo_activo_sin_campana', 'count': objetivos.count()})
    if objetivos.count() > 1:
        hallazgos.append({'code': 'objetivos_activos_multiples', 'count': objetivos.count()})
    vencidos = objetivos.filter(fecha_evento__lte=fecha).count()
    if vencidos:
        hallazgos.append({'code': 'objetivo_activo_vencido', 'count': vencidos})
    futuras = HyroxSession.objects.filter(objective__cliente=cliente, fecha__gt=fecha, estado='planificado').count()
    if futuras and autoridad['estado'] != 'activa':
        hallazgos.append({'code': 'sesion_futura_sin_campana_activa', 'count': futuras})
    contrato = _vigente(cliente)
    if contrato and contrato.objetivo_id and contrato.objetivo_snapshot.get('fecha_evento') != str(contrato.objetivo.fecha_evento):
        hallazgos.append({'code': 'snapshot_objetivo_divergente', 'contrato_id': contrato.pk})
    riesgos_estaticos = [x for x in INVENTARIO_AUTOMATIZACIONES if not x['cubierto_7a']]
    return {'autoridad': autoridad, 'inventario': INVENTARIO_AUTOMATIZACIONES,
            'riesgos_estaticos': riesgos_estaticos, 'hallazgos': hallazgos}
