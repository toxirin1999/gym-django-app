# Script de comparación en modo sombra — NO es un test formal.
# Para cada perfil conocido, imprime lado a lado:
#   ACTUAL  = split estático (DISTRIBUCION_DIAS vía core.py)
#   NUEVO   = asignar_semana() (motor X.6 aislado)
#
# Uso:
#   python3 manage.py comparar_asignador_shadow --settings=gymproject.settings_local
#   python3 manage.py comparar_asignador_shadow --perfil david --settings=gymproject.settings_local

from django.core.management.base import BaseCommand

from analytics.planificador_helms.config import (
    DISTRIBUCION_DIAS,
    GRUPOS_GRANDES,
    CAPACIDAD_SERIES_DIA,
)
from analytics.planificador_helms.distribucion.asignador import (
    GrupoParaAsignar,
    AsignacionImposibleError,
    asignar_semana,
)
from analytics.planificador_helms.distribucion.frecuencia import calcular_frecuencia
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.volumen.calculadora import calcular_volumen_optimo

# Patrón dominante por grupo (heurística sin ejercicio específico)
_PATRON_DOMINANTE = {
    'pecho': 'empuje_horizontal',
    'espalda': 'traccion_vertical',
    'hombros': 'empuje_vertical',
    'biceps': 'aislamiento',
    'triceps': 'aislamiento',
    'cuadriceps': 'rodilla',
    'isquios': 'bisagra',
    'gluteos': 'bisagra',
    'gemelos': 'aislamiento',
    'core': 'aislamiento',
    'trapecios': 'aislamiento',
    'antebrazos': 'aislamiento',
}

TODOS_LOS_GRUPOS = [
    'pecho', 'espalda', 'hombros', 'biceps', 'triceps',
    'cuadriceps', 'isquios', 'gluteos',
    'gemelos', 'core', 'trapecios', 'antebrazos',
]

PERFILES_MATRIZ = [
    {
        'label': 'david (avanzado, 5d, general) [PERFIL REAL]',
        'data': {'id': 2, 'nombre': 'david', 'experiencia_años': 7,
                 'objetivo_principal': 'general', 'dias_disponibles': 5},
    },
    {
        'label': 'principiante / 3d / hipertrofia',
        'data': {'id': 99, 'experiencia_años': 0.5,
                 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3},
    },
    {
        'label': 'principiante / 6d / hipertrofia',
        'data': {'id': 95, 'experiencia_años': 0.5,
                 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6},
    },
    {
        'label': 'intermedio / 4d / hipertrofia',
        'data': {'id': 98, 'experiencia_años': 2,
                 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 4},
    },
    {
        'label': 'intermedio / 5d / hipertrofia',
        'data': {'id': 94, 'experiencia_años': 2,
                 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 5},
    },
    {
        'label': 'avanzado / 3d / hipertrofia',
        'data': {'id': 96, 'experiencia_años': 5,
                 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3},
    },
    {
        'label': 'avanzado / 6d / hipertrofia',
        'data': {'id': 97, 'experiencia_años': 5,
                 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6},
    },
]


def _frecuencia_actual(dias_disponibles: int) -> dict:
    """
    Extrae frecuencia efectiva del split estático DISTRIBUCION_DIAS.
    Todos los grupos tienen freq=1 (cada grupo aparece en exactamente 1 día).
    """
    split = DISTRIBUCION_DIAS.get(dias_disponibles, {})
    freq = {}
    for dia_grupos in split.values():
        for g in dia_grupos:
            freq[g] = freq.get(g, 0) + 1
    return freq


def _construir_grupos(perfil: PerfilCliente) -> dict:
    nivel = perfil.calcular_nivel_experiencia()
    objetivo = perfil.objetivo_principal
    factor = perfil.calcular_factor_recuperacion()
    grupos = {}
    for nombre in TODOS_LOS_GRUPOS:
        vol = calcular_volumen_optimo(nombre, nivel, objetivo, factor)
        patron = _PATRON_DOMINANTE.get(nombre, 'aislamiento')
        vp = 'ligera' if patron == 'bisagra' else None
        grupos[nombre] = GrupoParaAsignar(
            nombre=nombre,
            volumen_objetivo=vol,
            mev=max(round(vol * 0.60), 4),
            es_grande=(nombre in GRUPOS_GRANDES),
            patron_dominante=patron,
            variante_peso=vp,
        )
    return grupos


class Command(BaseCommand):
    help = (
        'Compara split actual (DISTRIBUCION_DIAS) vs asignador nuevo (X.6) '
        'para la matriz de perfiles conocidos. Herramienta de inspección manual '
        'antes de conectar el motor a producción (X.7).'
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
        self.stdout.write(self.style.SUCCESS('=== SHADOW COMPARISON: Split Actual vs Asignador X.6 ==='))
        self.stdout.write(f'CAPACIDAD_SERIES_DIA = {CAPACIDAD_SERIES_DIA}')
        self.stdout.write('')

        col_grupo = 13
        col_actual = 10
        col_nuevo_freq = 10
        col_nuevo_dias = 30

        hdr = (
            f"{'GRUPO':<{col_grupo}} "
            f"{'ACTUAL-F':>{col_actual}} "
            f"{'NUEVO-F':>{col_nuevo_freq}} "
            f"{'NUEVO-DIAS':<{col_nuevo_dias}}"
        )
        separador = '-' * len(hdr)

        for entry in PERFILES_MATRIZ:
            label = entry['label']
            if filtro and filtro.lower() not in label.lower():
                continue

            pdata = entry['data']
            dias = pdata['dias_disponibles']

            self.stdout.write(self.style.SUCCESS(f'--- {label} ---'))

            # Split actual
            freq_actual = _frecuencia_actual(dias)

            # Motor nuevo
            perfil = PerfilCliente(pdata)
            grupos = _construir_grupos(perfil)
            try:
                resultado = asignar_semana(grupos, dias)
            except AsignacionImposibleError as e:
                self.stdout.write(self.style.ERROR(f'  ERROR asignador: {e}'))
                self.stdout.write('')
                continue

            freq_nueva = resultado.frecuencia_efectiva
            asig_nueva = resultado.asignacion
            degradados = resultado.grupos_degradados

            # Construir mapa grupo→días asignados
            grupo_dias_nuevo: dict = {g: [] for g in TODOS_LOS_GRUPOS}
            for dia_key, glist in asig_nueva.items():
                for g in glist:
                    if g in grupo_dias_nuevo:
                        grupo_dias_nuevo[g].append(dia_key)

            self.stdout.write(hdr)
            self.stdout.write(separador)

            for grupo in TODOS_LOS_GRUPOS:
                fa = freq_actual.get(grupo, 0)
                fn = freq_nueva.get(grupo, 0)
                dias_str = ', '.join(sorted(grupo_dias_nuevo.get(grupo, [])))
                degradado = '*' if grupo in degradados else ' '
                self.stdout.write(
                    f"{grupo:<{col_grupo}} "
                    f"{fa:>{col_actual}} "
                    f"{fn:>{col_nuevo_freq}}{degradado} "
                    f"{dias_str:<{col_nuevo_dias}}"
                )

            freq_total_actual = sum(freq_actual.get(g, 0) for g in TODOS_LOS_GRUPOS)
            freq_total_nueva = sum(freq_nueva.values())
            self.stdout.write(separador)
            self.stdout.write(
                f"{'TOTAL':<{col_grupo}} "
                f"{freq_total_actual:>{col_actual}} "
                f"{freq_total_nueva:>{col_nuevo_freq}}  "
            )
            if degradados:
                self.stdout.write(
                    f"  * degradados (freq reducida): {', '.join(sorted(degradados))}"
                )
            self.stdout.write('')
