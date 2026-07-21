# Script de inspección de variación intra-semanal — NO es un test formal.
# Simula cómo quedarán los toques 2 y 3 de cada grupo con freq≥2 DESPUÉS
# de que X.14 conecte variacion.py a core.py. El comportamiento REAL
# actual sigue siendo toque 1 repetido en todas las apariciones.
#
# Diferencia con el golden master de X.13 (test_estructura_dia_completa):
#   - El golden master captura el comportamiento HOY (toque 1 repetido).
#   - Este comando muestra la SIMULACIÓN de lo que X.14 producirá.
#   - Usar este comando para detectar combinaciones raras antes de aprobar X.14.
#
# Uso:
#   python3 manage.py comparar_variacion_toque --settings=gymproject.settings_local
#   python3 manage.py comparar_variacion_toque --perfil david --settings=gymproject.settings_local

from django.core.management.base import BaseCommand

from analytics.planificador_helms.config import (
    GRUPOS_GRANDES,
    REP_RANGE_AJUSTE_PEQUENOS,
)
from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
from analytics.planificador_helms.ejercicios.variacion import (
    construir_variantes_por_toque,
    derivar_rep_rpe_toque,
)
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.utils.helpers import extraer_nombre_ejercicio

PERFILES_MATRIZ = [
    {
        'label': 'david (avanzado, 5d, general) [PERFIL REAL]',
        'data': {
            'id': 2, 'nombre': 'david', 'experiencia_años': 7,
            'objetivo_principal': 'general', 'dias_disponibles': 5,
        },
    },
    {
        'label': 'principiante / 3d / hipertrofia',
        'data': {
            'id': 99, 'experiencia_años': 0.5,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3,
        },
    },
    {
        'label': 'principiante / 6d / hipertrofia',
        'data': {
            'id': 95, 'experiencia_años': 0.5,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6,
        },
    },
    {
        'label': 'intermedio / 4d / hipertrofia',
        'data': {
            'id': 98, 'experiencia_años': 2,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 4,
        },
    },
    {
        'label': 'intermedio / 5d / hipertrofia',
        'data': {
            'id': 94, 'experiencia_años': 2,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 5,
        },
    },
    {
        'label': 'avanzado / 3d / hipertrofia',
        'data': {
            'id': 96, 'experiencia_años': 5,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3,
        },
    },
    {
        'label': 'avanzado / 6d / hipertrofia',
        'data': {
            'id': 97, 'experiencia_años': 5,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6,
        },
    },
]


def _build_planner(perfil_data: dict) -> PlanificadorHelms:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    return planner


def _semana_bloque0(planner: PlanificadorHelms) -> dict:
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    bloque0 = periodizacion[0]
    return planner._generar_semana_especifica(bloque0, 1)


def _resumen(semana: dict) -> dict:
    grupos_series: dict = {}
    grupos_dias: dict = {}
    for dia_key, ejercicios in semana.items():
        for ej in ejercicios:
            grupo = ej['grupo_muscular']
            grupos_series[grupo] = grupos_series.get(grupo, 0) + ej['series']
            grupos_dias.setdefault(grupo, set()).add(dia_key)
    return {
        g: {'freq': len(grupos_dias[g]), 'series': grupos_series[g]}
        for g in grupos_series
    }


def _ejercicios_toque1_por_grupo(semana: dict) -> dict:
    """
    Extrae los ejercicios de la PRIMERA aparición semanal de cada grupo.
    Devuelve {grupo: [lista de ej-dicts]}, con el orden real de core.py.
    """
    dia_primera_vez: dict = {}   # grupo → dia_key de la primera vez
    resultado: dict = {}
    for dia_key in sorted(semana.keys()):
        for ej in semana[dia_key]:
            grupo = ej['grupo_muscular']
            if grupo not in dia_primera_vez:
                dia_primera_vez[grupo] = dia_key
                resultado[grupo] = []
            if dia_primera_vez[grupo] == dia_key:
                resultado[grupo].append(ej)
    return resultado


def _rep_range_ej(rep_range_bloque: str, grupo: str) -> str:
    """Replica el ajuste de rep_range que hace core.py según tamaño del grupo."""
    if grupo in GRUPOS_GRANDES:
        return rep_range_bloque
    return REP_RANGE_AJUSTE_PEQUENOS.get(rep_range_bloque, rep_range_bloque)


class Command(BaseCommand):
    help = (
        'SIMULACIÓN de variación intra-semanal por toque (X.14 pendiente). '
        'Muestra cómo quedarían los ejercicios de toques 2 y 3 para cada '
        'grupo con freq≥2. NO refleja el comportamiento actual de producción.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--perfil',
            type=str,
            default=None,
            help='Filtrar por etiqueta de perfil (ej: "david")',
        )

    def handle(self, *args, **options):
        filtro = options.get('perfil')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            '=== SIMULACIÓN X.14: Variación Intra-Semanal por Toque ==='
        ))
        self.stdout.write(
            'ATENCIÓN: esto muestra lo que X.14 producirá, NO el '
            'comportamiento actual (hoy todos los toques repiten toque 1).'
        )
        self.stdout.write('')

        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        bloque0 = periodizacion[0]
        fase = bloque0.get('fase', 'hipertrofia')
        rep_range_bloque = bloque0.get('rep_range', '8-12')
        rpe_objetivo = (bloque0.get('intensidad_rpe') or (7,))[0]

        self.stdout.write(
            f'Bloque base: {bloque0["nombre"]} | fase={fase} | '
            f'rep_range={rep_range_bloque} | rpe_objetivo={rpe_objetivo}'
        )
        self.stdout.write('')

        for entry in PERFILES_MATRIZ:
            label = entry['label']
            if filtro and filtro.lower() not in label.lower():
                continue

            pdata = entry['data']
            planner = _build_planner(pdata)
            semana = _semana_bloque0(planner)
            resumen = _resumen(semana)

            grupos_freq2 = sorted(
                g for g, stats in resumen.items() if stats['freq'] >= 2
            )

            self.stdout.write(self.style.SUCCESS(f'--- {label} ---'))

            if not grupos_freq2:
                self.stdout.write('  (ningún grupo alcanza freq≥2 — sin variación de toque)')
                self.stdout.write('')
                continue

            toque1_por_grupo = _ejercicios_toque1_por_grupo(semana)

            for grupo in grupos_freq2:
                freq = resumen[grupo]['freq']
                es_grande = grupo in GRUPOS_GRANDES
                rep_range_g = _rep_range_ej(rep_range_bloque, grupo)

                ejercicios_t1 = toque1_por_grupo.get(grupo, [])
                pool_seguro = SelectorEjercicios.construir_pool_seguro_por_grupo(
                    grupo, fase, cliente=None
                )

                variantes = construir_variantes_por_toque(
                    grupo=grupo,
                    frecuencia=freq,
                    es_grande=es_grande,
                    pool_seguro=pool_seguro,
                    ejercicios_toque1=ejercicios_t1,
                )

                self.stdout.write(f'  GRUPO: {grupo.upper()}  (freq={freq})')

                _ROL_NOMBRE = {
                    1: 'pesado / compuesto',
                    2: 'estiramiento / ligero',
                    3: 'acortamiento / bombeo',
                }

                for toque_num in range(1, freq + 1):
                    rr, rpe = derivar_rep_rpe_toque(rep_range_g, rpe_objetivo, toque_num)
                    ejercicios_toque = variantes.get(toque_num, [])
                    nombres = [extraer_nombre_ejercicio(e) for e in ejercicios_toque]
                    perfiles = [
                        e.get('perfil', '—')
                        if isinstance(e, dict) else '—'
                        for e in ejercicios_toque
                    ]
                    rol = _ROL_NOMBRE.get(toque_num, f'toque {toque_num}')
                    ejs_str = '  |  '.join(
                        f'{n} [perfil={p}]'
                        for n, p in zip(nombres, perfiles)
                    ) or '(sin ejercicios)'
                    self.stdout.write(
                        f'    Toque {toque_num} ({rol}):  rep_range={rr}  RPE={rpe}'
                    )
                    self.stdout.write(f'      {ejs_str}')

                self.stdout.write('')
