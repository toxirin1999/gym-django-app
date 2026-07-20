# Script de comparación — no es un test formal.
# Vuelca la tabla grupo→frecuencia→series/semana para la matriz de perfiles del
# sistema de caracterización. Útil para diffs manuales entre sub-fases X.0-X.9.
#
# Uso:
#   python3 manage.py comparar_volumen_planificador --settings=gymproject.settings_local
#   python3 manage.py comparar_volumen_planificador --bloque 2 --settings=gymproject.settings_local

from django.core.management.base import BaseCommand

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion


# Matriz de perfiles a evaluar. Editar aquí para ampliar cobertura.
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

TODOS_LOS_GRUPOS = [
    'pecho', 'espalda', 'hombros', 'biceps', 'triceps',
    'cuadriceps', 'isquios', 'gluteos', 'gemelos',
    'core', 'trapecios', 'antebrazos',
]


def _build_semana(perfil_data: dict, bloque_idx: int) -> dict:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    bloque = periodizacion[bloque_idx]
    return planner._generar_semana_especifica(bloque, bloque_idx + 1), bloque


def _resumen(semana: dict) -> dict:
    grupos_series: dict = {}
    grupos_dias: dict = {}
    for dia_key, ejercicios in semana.items():
        for ej in ejercicios:
            g = ej['grupo_muscular']
            grupos_series[g] = grupos_series.get(g, 0) + ej['series']
            grupos_dias.setdefault(g, set()).add(dia_key)
    return {g: {'freq': len(grupos_dias[g]), 'series': grupos_series[g]} for g in grupos_series}


class Command(BaseCommand):
    help = (
        'Vuelca la tabla grupo→frecuencia→series/semana para la matriz de perfiles '
        'del planificador Helms. Útil para diffs entre sub-fases X.0-X.9.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--bloque',
            type=int,
            default=0,
            help='Índice del bloque de periodización a evaluar (0=Hipertrofia Acumulación)',
        )
        parser.add_argument(
            '--detalle',
            action='store_true',
            default=False,
            help='Mostrar también el desglose día a día por grupo',
        )

    def handle(self, *args, **options):
        bloque_idx = options['bloque']
        mostrar_detalle = options['detalle']

        # Obtener el nombre del bloque para el encabezado
        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        if bloque_idx >= len(periodizacion):
            self.stderr.write(
                self.style.ERROR(
                    f"Bloque {bloque_idx} no existe. "
                    f"Hay {len(periodizacion)} bloques (0-{len(periodizacion)-1})."
                )
            )
            return
        bloque_nombre = periodizacion[bloque_idx].get('nombre', f'Bloque {bloque_idx}')
        bloque_fase   = periodizacion[bloque_idx].get('fase', '')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'=== COMPARACION VOLUMEN PLANIFICADOR HELMS ==='
        ))
        self.stdout.write(
            f'Bloque {bloque_idx}: {bloque_nombre} ({bloque_fase})'
        )
        self.stdout.write('')

        col_perfil = 42
        col_grupo  = 13
        col_freq   = 6
        col_series = 8

        encabezado = (
            f"{'PERFIL':<{col_perfil}} "
            f"{'GRUPO':<{col_grupo}} "
            f"{'FREQ':>{col_freq}} "
            f"{'SERIES':>{col_series}}"
        )
        separador = '-' * len(encabezado)

        self.stdout.write(encabezado)
        self.stdout.write(separador)

        for entry in PERFILES_MATRIZ:
            label = entry['label']
            pdata = entry['data']

            try:
                semana, _ = _build_semana(pdata, bloque_idx)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'{label}: ERROR — {exc}'))
                continue

            resumen = _resumen(semana)

            primera_fila = True
            for grupo in TODOS_LOS_GRUPOS:
                if grupo not in resumen:
                    continue
                stats = resumen[grupo]
                prefijo = label if primera_fila else ' ' * col_perfil
                self.stdout.write(
                    f"{prefijo:<{col_perfil}} "
                    f"{grupo:<{col_grupo}} "
                    f"{stats['freq']:>{col_freq}} "
                    f"{stats['series']:>{col_series}}"
                )
                primera_fila = False

            # Grupos presentes en la semana pero no en TODOS_LOS_GRUPOS (casos raros)
            for grupo in sorted(set(resumen.keys()) - set(TODOS_LOS_GRUPOS)):
                stats = resumen[grupo]
                prefijo = label if primera_fila else ' ' * col_perfil
                self.stdout.write(
                    f"{prefijo:<{col_perfil}} "
                    f"{grupo:<{col_grupo}} "
                    f"{stats['freq']:>{col_freq}} "
                    f"{stats['series']:>{col_series}}"
                )
                primera_fila = False

            if mostrar_detalle:
                self.stdout.write('')
                for dia_key, ejercicios in sorted(semana.items()):
                    self.stdout.write(f"  {dia_key}:")
                    for ej in ejercicios:
                        self.stdout.write(
                            f"    {ej['nombre']} ({ej['grupo_muscular']}): "
                            f"{ej['series']} series"
                        )

            self.stdout.write(separador)

        self.stdout.write('')
        self.stdout.write(
            'FIXES APLICADOS (X.1 + X.2 — 2026-07-19):'
        )
        self.stdout.write(
            '  X.1: biceps 4→8 series — Curl con Barra Z promovido a compuesto_principal;'
            ' selector generalizado para grupos con compuesto_principal vacio.'
            ' Antebrazos tambien se beneficia del mismo fix.'
        )
        self.stdout.write(
            '  X.2: gluteos Hip Thrust desbloqueado — puede_usar_bisagra corregido:'
            ' mismo dia siempre permitido; adyacente bloqueado solo si variante pesada.'
            ' Efecto colateral: contador bisagra compartido puede reducir series de isquios'
            ' en splits con freq=2 para ambos grupos (limitacion conocida, pendiente X.5-X.6).'
        )
        self.stdout.write('')
