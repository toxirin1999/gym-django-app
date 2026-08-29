"""Inventario canónico y read-only de la transición al entrenador Gym."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy


SCHEMA_VERSION = 1
STATES = (
    'archived',
    'campaign_optional',
    'contextual_active',
    'core_active',
    'legacy_compat',
    'postponed',
)
AUTHORITIES = ('contextual', 'none', 'signal_source', 'sovereign', 'supervised')
FORBIDDEN_AUTHORITY_STATES = {'archived', 'legacy_compat', 'postponed'}


def _route(name, *args):
    item = {'name': name}
    if args:
        item['args'] = list(args)
    return item


_SURFACES = (
    {
        'id': 'analytics_legacy',
        'titulo': 'Analytics y paneles históricos',
        'modulos': ['analytics'],
        'estado': 'legacy_compat',
        'autoridad': 'none',
        'dependencias': ['gym_execution'],
        'rutas': [_route('analytics:dashboard_cliente', 1)],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'availability_context',
        'titulo': 'Disponibilidad contextual',
        'modulos': ['disponibilidad'],
        'estado': 'contextual_active',
        'autoridad': 'signal_source',
        'dependencias': ['gym_authority'],
        'rutas': [],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'diary_bridge',
        'titulo': 'Diario y señal deportiva autorizada',
        'modulos': ['diario'],
        'estado': 'contextual_active',
        'autoridad': 'signal_source',
        'dependencias': ['gym_authority'],
        'rutas': [
            _route('diario:dashboard_diario'),
            _route('diario:presencia_apertura'),
            _route('diario:presencia_cierre'),
        ],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'gamification',
        'titulo': 'Gamificación histórica',
        'modulos': ['logros'],
        'estado': 'postponed',
        'autoridad': 'none',
        'dependencias': ['gym_execution'],
        'rutas': [_route('logros:perfil_gamificacion')],
        'comandos': ['auditar_integridad_gamificacion'],
        'procesos': [],
    },
    {
        'id': 'gym_authority',
        'titulo': 'Autoridad diaria Gym',
        'modulos': ['clientes', 'entrenos'],
        'estado': 'core_active',
        'autoridad': 'sovereign',
        'dependencias': ['gym_week', 'physical_evidence'],
        'rutas': [_route('clientes:mockup_demo')],
        'comandos': ['auditar_snapshot_fisico_gym'],
        'procesos': [],
    },
    {
        'id': 'gym_decision_center',
        'titulo': 'Centro de decisiones Gym',
        'modulos': ['clientes', 'entrenos'],
        'estado': 'core_active',
        'autoridad': 'supervised',
        'dependencias': ['gym_authority', 'gym_week'],
        'rutas': [_route('clientes:plan_decisiones')],
        'comandos': ['reconciliar_gobernanza_centro'],
        'procesos': [],
    },
    {
        'id': 'gym_execution',
        'titulo': 'Briefing, sesión activa y cierre causal',
        'modulos': ['entrenos'],
        'estado': 'core_active',
        'autoridad': 'supervised',
        'dependencias': ['gym_authority', 'routine_library'],
        'rutas': [
            _route('entrenos:briefing_entrenamiento', 1),
            _route('entrenos:entrenamiento_activo', 1),
        ],
        'comandos': ['cerrar_supervision_gym'],
        'procesos': [],
    },
    {
        'id': 'gym_week',
        'titulo': 'Estrategia, bloque y semana Gym',
        'modulos': ['entrenos'],
        'estado': 'core_active',
        'autoridad': 'supervised',
        'dependencias': ['routine_library'],
        'rutas': [],
        'comandos': [
            'auditar_bloque_gym',
            'cerrar_semana_gym',
            'materializar_contrato_semanal_gym',
            'preparar_semana_gym',
        ],
        'procesos': [],
    },
    {
        'id': 'hyrox_campaign',
        'titulo': 'Campaña Hyrox subordinada',
        'modulos': ['hyrox'],
        'estado': 'campaign_optional',
        'autoridad': 'supervised',
        'dependencias': ['gym_authority', 'physical_evidence', 'strava'],
        'rutas': [
            _route('hyrox:dashboard'),
            _route('hyrox:solicitar_extra'),
        ],
        'comandos': ['auditar_campana_hyrox', 'configurar_campana_hyrox'],
        'procesos': [],
    },
    {
        'id': 'joi_presence',
        'titulo': 'Presencia y outbox JOI',
        'modulos': ['joi'],
        'estado': 'contextual_active',
        'autoridad': 'contextual',
        'dependencias': ['gym_authority', 'memory_review'],
        'rutas': [_route('joi:joi_habitacion')],
        'comandos': ['auditar_outbox_entrenador_joi'],
        'procesos': [
            'joi.tasks.ciclo_sintesis_joi',
            'joi.tasks.generar_apertura_manana',
        ],
    },
    {
        'id': 'liftin',
        'titulo': 'Liftin histórico',
        'modulos': ['entrenos'],
        'estado': 'archived',
        'autoridad': 'none',
        'dependencias': ['gym_execution'],
        'rutas': [_route('entrenos:dashboard_liftin_cliente', 1)],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'memory_review',
        'titulo': 'Memoria epistemológica revisable',
        'modulos': ['core', 'joi'],
        'estado': 'contextual_active',
        'autoridad': 'supervised',
        'dependencias': [],
        'rutas': [_route('joi:joi_manual')],
        'comandos': [
            'auditar_memoria_epistemica',
            'auditar_revision_memoria',
            'planificar_revision_memoria',
        ],
        'procesos': [],
    },
    {
        'id': 'multi_client_management',
        'titulo': 'Gestión multi-cliente protegida',
        'modulos': ['clientes'],
        'estado': 'legacy_compat',
        'autoridad': 'none',
        'dependencias': [],
        'rutas': [
            _route('clientes:lista_clientes'),
            _route('clientes:panel_entrenador'),
        ],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'nutrition',
        'titulo': 'Nutrición fuera de uso',
        'modulos': ['nutricion_app_django'],
        'estado': 'postponed',
        'autoridad': 'none',
        'dependencias': [],
        'rutas': [],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'physical_evidence',
        'titulo': 'Check-in y snapshot físico',
        'modulos': ['clientes', 'core', 'entrenos'],
        'estado': 'contextual_active',
        'autoridad': 'signal_source',
        'dependencias': ['strava'],
        'rutas': [_route('clientes:checkin_matutino')],
        'comandos': ['auditar_snapshot_fisico_gym', 'materializar_snapshot_fisico_gym'],
        'procesos': [],
    },
    {
        'id': 'rehab',
        'titulo': 'Rehab y contrato de riesgo Gym',
        'modulos': ['rehab'],
        'estado': 'postponed',
        'autoridad': 'none',
        'dependencias': ['physical_evidence'],
        'rutas': [_route('rehab:hoy')],
        'comandos': ['auditar_autoridad_lesion_gym', 'previsualizar_freno_rehab_gym'],
        'procesos': [],
    },
    {
        'id': 'routine_library',
        'titulo': 'Programas, rutinas y ejercicios',
        'modulos': ['rutinas'],
        'estado': 'core_active',
        'autoridad': 'supervised',
        'dependencias': [],
        'rutas': [_route('lista_programas')],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'stoic_legacy',
        'titulo': 'Contenido estoico histórico',
        'modulos': ['estoico'],
        'estado': 'legacy_compat',
        'autoridad': 'none',
        'dependencias': [],
        'rutas': [],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'strava',
        'titulo': 'Strava y evento físico canónico',
        'modulos': ['hyrox'],
        'estado': 'contextual_active',
        'autoridad': 'signal_source',
        'dependencias': [],
        'rutas': [
            _route('hyrox:strava_connect'),
            _route('hyrox:strava_reconciliacion'),
        ],
        'comandos': [
            'auditar_metricas_strava_gym',
            'clasificar_identidad_strava_gym',
            'reconciliar_fechas_strava_gym',
        ],
        'procesos': [],
    },
    {
        'id': 'stretching_tool',
        'titulo': 'Biblioteca de estiramientos',
        'modulos': ['estiramientos'],
        'estado': 'contextual_active',
        'autoridad': 'contextual',
        'dependencias': [],
        'rutas': [_route('estiramientos:panel')],
        'comandos': [],
        'procesos': [],
    },
    {
        'id': 'weekly_evaluation',
        'titulo': 'Evaluación semanal y de bloque',
        'modulos': ['entrenos'],
        'estado': 'core_active',
        'autoridad': 'supervised',
        'dependencias': ['gym_execution', 'gym_week'],
        'rutas': [_route('clientes:plan_decisiones')],
        'comandos': [
            'auditar_distribucion_semanal_contractual',
            'cerrar_bloque_gym',
            'cerrar_semana_gym',
        ],
        'procesos': ['entrenos.tasks.evaluar_intervenciones_esenciales_diarias'],
    },
)


def _validate_surfaces(surfaces):
    ids = [surface['id'] for surface in surfaces]
    if len(surfaces) < 15:
        raise ValueError('El inventario debe contener al menos 15 superficies.')
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise ValueError('Los IDs deben ser únicos y estar ordenados.')

    known_ids = set(ids)
    for surface in surfaces:
        if surface['estado'] not in STATES:
            raise ValueError(f"Estado inválido: {surface['estado']}")
        if surface['autoridad'] not in AUTHORITIES:
            raise ValueError(f"Autoridad inválida: {surface['autoridad']}")
        if (
            surface['estado'] in FORBIDDEN_AUTHORITY_STATES
            and surface['autoridad'] != 'none'
        ):
            raise ValueError(f"{surface['id']} no puede conservar autoridad.")
        dependencies = surface['dependencias']
        if dependencies != sorted(set(dependencies)):
            raise ValueError(f"Dependencias no canónicas: {surface['id']}")
        if not set(dependencies).issubset(known_ids):
            raise ValueError(f"Dependencia desconocida: {surface['id']}")
        for field in ('comandos', 'modulos', 'procesos'):
            if surface[field] != sorted(set(surface[field])):
                raise ValueError(f"{field} no canónico: {surface['id']}")
        route_names = [route['name'] for route in surface['rutas']]
        if route_names != sorted(set(route_names)):
            raise ValueError(f"Rutas no canónicas: {surface['id']}")


def build_transition_inventory():
    """Devuelve el inventario versionado sin consultar ni mutar datos de usuario."""
    surfaces = sorted(deepcopy(_SURFACES), key=lambda item: item['id'])
    _validate_surfaces(surfaces)
    unsigned = {
        'schema_version': SCHEMA_VERSION,
        'solo_lectura': True,
        'contrato': {
            'estados': list(STATES),
            'autoridades': list(AUTHORITIES),
            'estados_sin_autoridad': sorted(FORBIDDEN_AUTHORITY_STATES),
        },
        'superficies': surfaces,
        'resumen': {
            'total_superficies': len(surfaces),
            'total_rutas': sum(len(item['rutas']) for item in surfaces),
            'total_comandos': sum(len(item['comandos']) for item in surfaces),
            'total_procesos': sum(len(item['procesos']) for item in surfaces),
        },
    }
    canonical = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return {**unsigned, 'fingerprint': hashlib.sha256(canonical).hexdigest()}
