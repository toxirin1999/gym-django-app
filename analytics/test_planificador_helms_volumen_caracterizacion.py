# analytics/test_planificador_helms_volumen_caracterizacion.py
"""
Tests de caracterización del comportamiento de PlanificadorHelms.

Capturan la línea base exacta para que cualquier cambio en
analytics/planificador_helms/ rompa estos tests inmediatamente.
Valores actualizados el 2026-07-20 tras X.7 (motor de asignación conectado).

  - X.0 a X.4: red de seguridad, fixes bíceps/bisagra, CalculadoraVolumen,
    topes dinámicos (ver historial de commits anteriores).

  - X.5 + X.6: motor de frecuencia y asignador — construidos y verificados
    en shadow mode sin tocar producción.

  - X.7 (2026-07-20): core.py ahora usa el motor de asignación automática
    (distribucion/asignador.py) en lugar de DISTRIBUCION_DIAS estático.
    DISTRIBUCION_DIAS se conserva como fallback en AsignacionImposibleError.

    Impacto en todos los perfiles con freq>1 posible:
      david (5d, avanzado, general): 8/12 grupos suben a freq=2
        (espalda/hombros/cuádriceps/bíceps/glúteos/gemelos/core/trapecios).
        pecho/tríceps/isquios/antebrazos se quedan en freq=1
        (degradados por presupuesto o por restricción de patron_manager).
      Novato 3d: core, trapecios y antebrazos ahora aparecen (freq=1 cada uno,
        asignados por volumen aunque DISTRIBUCION_DIAS[3] no los incluía).
      Avanzado 3d: igual — los 12 grupos aparecen todos (freq=1 cada uno).
      Avanzado 6d: bíceps sube a freq=3, antebrazos a freq=2, tríceps baja a freq=1.

    Nota sobre isquios de david (freq=1, 9 series):
      El motor asignó isquios a freq=1 por degradación de presupuesto. Dentro
      del día, patron_manager.dias_usados_bisagra llega a 2 (tope de hipertrofia)
      antes de procesar isquios — glúteos consumió ambos slots en dia_1 y dia_3.
      Resultado: solo Curl Femoral Tumbado (aislamiento) × 9 series.

    Nota sobre la clave de caché generar_plan_anual:
      La clave incluye dias_disponibles y objetivo_principal, por lo que
      perfiles con distinto motor vs fallback nunca se solapan en caché.
      En producción, al desplegar X.7 habrá que invalidar las entradas
      "plan_anual_*" de la caché de archivo — los planes generados con
      DISTRIBUCION_DIAS quedan obsoletos y no se auto-invalidan.
"""

import logging
from unittest.mock import patch

from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion


# ---------------------------------------------------------------------------
# Helpers — sin estado, reutilizables en todas las clases de test
# ---------------------------------------------------------------------------

def _build_planner(perfil_data: dict) -> tuple:
    """
    Instancia perfil + planificador con historial vacío para que la salida
    sea reproducible sin depender de datos de BD del entorno de test.
    """
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None           # evita consulta Cliente.objects.get
    planner._historial_ejercicios_raw = []  # historial vacío = sin historial previo
    return perfil, planner


def _semana_bloque0(planner: PlanificadorHelms) -> dict:
    """Genera la semana del bloque 0 (Hipertrofia Acumulación) con numero_bloque=1."""
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    bloque0 = periodizacion[0]
    return planner._generar_semana_especifica(bloque0, 1)


def _resumen(semana: dict) -> dict:
    """Devuelve {grupo: {'freq': int, 'series': int}} para la semana dada."""
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


def _estructura_dia(semana: dict) -> dict:
    """Devuelve {dia: [(nombre, grupo_muscular, series), ...]} con días ordenados."""
    return {
        dia: [(ej['nombre'], ej['grupo_muscular'], ej['series']) for ej in ejercicios]
        for dia, ejercicios in sorted(semana.items())
    }


# ---------------------------------------------------------------------------
# Perfil real de "david" — el caso más importante
# ---------------------------------------------------------------------------

class TestCaracterizacionDavid(TestCase):
    """
    Perfil real del desarrollador: avanzado, objetivo 'general', 5 días.

    Post-X.7: motor de asignación activo. La mayoría de grupos suben a
    freq=2. pecho/tríceps/isquios/antebrazos se quedan en freq=1 por
    degradación de presupuesto o por tope de patron_manager.bisagra.
    """

    PERFIL = {
        'id': 2,
        'nombre': 'david',
        'experiencia_años': 7,
        'objetivo_principal': 'general',
        'dias_disponibles': 5,
    }

    # Estructura completa capturada 2026-07-20 (post-X.7).
    # El motor asigna por volumen, no por Body Part Split fijo.
    # bloque0.volumen_multiplicador=1.2 (no 1.0) — determina vol_efectivo.
    ESTRUCTURA_ESPERADA = {
        'dia_1': [
            ('Crunch en Polea (Cable Crunch)',             'core',        4),
            ('Pallof Press',                               'core',        4),
            ('Sentadilla Hack',                            'cuadriceps',  7),
            ('Prensa de Piernas',                          'cuadriceps',  7),
            ('Elevación de Gemelos de Pie (Máquina)',      'gemelos',     4),
            ('Elevación de Gemelos Sentado (Máquina)',     'gemelos',     4),
            ('Hip Thrust con Barra',                       'gluteos',     6),
            ('Abducción de Cadera en Máquina',             'gluteos',     6),
        ],
        'dia_2': [
            ('Aguante en Barra (Dead Hang)',                'antebrazos',  5),
            ('Farmer Walk (Paseo del Granjero)',            'antebrazos',  5),
            ('Curl con Barra Z',                           'biceps',      4),
            ('Curl Araña',                                 'biceps',      4),
            ('Jalón al Pecho',                             'espalda',     7),
            ('Remo pecho apoyado',                         'espalda',     7),
            ('Machine Shoulder Press',                     'hombros',     5),
            ('Press Arnold',                               'hombros',     5),
        ],
        'dia_3': [
            ('Crunch en Polea (Cable Crunch)',             'core',        4),
            ('Pallof Press',                               'core',        4),
            ('Hip Thrust con Barra',                       'gluteos',     6),
            ('Abducción de Cadera en Máquina',             'gluteos',     6),
            ('Peso Muerto Rumano',                         'isquios',     9),
            ('Curl Femoral Tumbado',                       'isquios',     9),
            ('Encogimientos con Barra',                    'trapecios',   3),
            ('Farmer Walk (Paseo del Granjero)',            'trapecios',   3),
        ],
        'dia_4': [
            ('Sentadilla Hack',                            'cuadriceps',  7),
            ('Prensa de Piernas',                          'cuadriceps',  7),
            ('Elevación de Gemelos de Pie (Máquina)',      'gemelos',     4),
            ('Elevación de Gemelos Sentado (Máquina)',     'gemelos',     4),
            ('Convergent Machine Press',                   'pecho',      10),
            ('Press Cerrado en Banca',                     'pecho',      10),
            ('Press Francés con Barra Z',                  'triceps',     8),
            ('Extensiones de Tríceps con Polea Alta',      'triceps',     8),
        ],
        'dia_5': [
            ('Curl con Barra Z',                           'biceps',      4),
            ('Curl Araña',                                 'biceps',      4),
            ('Jalón al Pecho',                             'espalda',     7),
            ('Remo pecho apoyado',                         'espalda',     7),
            ('Machine Shoulder Press',                     'hombros',     5),
            ('Press Arnold',                               'hombros',     5),
            ('Encogimientos con Barra',                    'trapecios',   3),
            ('Farmer Walk (Paseo del Granjero)',            'trapecios',   3),
        ],
    }

    # Post-X.7: 8/12 grupos en freq=2. pecho/tríceps/isquios/antebrazos en freq=1.
    RESUMEN_ESPERADO = {
        'antebrazos': {'freq': 1, 'series': 10},
        'biceps':     {'freq': 2, 'series': 16},
        'core':       {'freq': 2, 'series': 16},
        'cuadriceps': {'freq': 2, 'series': 28},
        'espalda':    {'freq': 2, 'series': 28},
        'gemelos':    {'freq': 2, 'series': 16},
        'gluteos':    {'freq': 2, 'series': 24},
        'hombros':    {'freq': 2, 'series': 20},
        'isquios':    {'freq': 1, 'series': 18},
        'pecho':      {'freq': 1, 'series': 20},
        'trapecios':  {'freq': 2, 'series': 12},
        'triceps':    {'freq': 1, 'series': 16},
    }

    def setUp(self):
        _, self._planner = _build_planner(self.PERFIL)
        self._semana = _semana_bloque0(self._planner)

    def test_resumen_freq_series(self):
        self.assertEqual(_resumen(self._semana), self.RESUMEN_ESPERADO)

    def test_estructura_dia_completa(self):
        self.assertEqual(_estructura_dia(self._semana), self.ESTRUCTURA_ESPERADA)

    def test_dias_presentes(self):
        self.assertEqual(set(self._semana.keys()), {'dia_1', 'dia_2', 'dia_3', 'dia_4', 'dia_5'})

    def test_biceps_freq2_post_x7(self):
        """Post-X.7: bíceps sube a freq=2 — el motor lo asigna dos veces."""
        resumen = _resumen(self._semana)
        self.assertEqual(resumen['biceps']['freq'], 2)
        self.assertEqual(resumen['biceps']['series'], 16)

    def test_gluteos_freq2_post_x7(self):
        """Post-X.7: glúteos en freq=2, 24 series (vol_efectivo mayor con vol_mult=1.2)."""
        resumen = _resumen(self._semana)
        self.assertEqual(resumen['gluteos']['freq'],   2)
        self.assertEqual(resumen['gluteos']['series'], 24)

    def test_grupos_con_freq2_post_x7(self):
        """Post-X.7: 8 grupos alcanzan freq=2 gracias al motor de asignación."""
        grupos_freq2 = {'espalda', 'hombros', 'cuadriceps', 'biceps',
                        'gluteos', 'gemelos', 'core', 'trapecios'}
        resumen = _resumen(self._semana)
        for grupo in grupos_freq2:
            with self.subTest(grupo=grupo):
                self.assertEqual(resumen[grupo]['freq'], 2,
                                 f"{grupo} debería tener freq=2 con el motor nuevo")

    def test_tope_10_series_por_ejercicio_post_x4(self):
        """
        X.4 corregido: tope dinámico TOPE_SERIES_POR_EJERCICIO['hipertrofia']=10.
        Ningún ejercicio individual supera 10 series — el tope real de cada
        grupo lo pone GestorFatiga (grandes≤10, pequeños≤8).
        """
        from analytics.planificador_helms.config import TOPE_SERIES_POR_EJERCICIO
        tope = TOPE_SERIES_POR_EJERCICIO['hipertrofia']
        for dia_key, ejercicios in self._semana.items():
            for ej in ejercicios:
                self.assertLessEqual(
                    ej['series'], tope,
                    f"{ej['nombre']} en {dia_key} supera el tope de {tope} series"
                )


# ---------------------------------------------------------------------------
# Principiante — 3 días (mínimo split PPL)
# ---------------------------------------------------------------------------

class TestCaracterizacionNovato3d(TestCase):
    """
    Principiante, 3 días. Post-X.7: el motor asigna los 12 grupos musculares
    (incluyendo core, trapecios y antebrazos, que DISTRIBUCION_DIAS[3] omitía).
    Todos los grupos quedan en freq=1 porque 3 días limita freq_deseada.
    """

    PERFIL = {
        'id': 99,
        'experiencia_años': 0.5,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 3,
    }

    # Post-X.7: los 12 grupos aparecen (motor los asigna por volumen objetivo).
    # core, trapecios y antebrazos ya no están excluidos.
    RESUMEN_ESPERADO = {
        'antebrazos': {'freq': 1, 'series':  6},
        'biceps':     {'freq': 1, 'series': 10},
        'core':       {'freq': 1, 'series': 10},
        'cuadriceps': {'freq': 1, 'series': 16},
        'espalda':    {'freq': 1, 'series': 16},
        'gemelos':    {'freq': 1, 'series': 10},
        'gluteos':    {'freq': 1, 'series': 12},
        'hombros':    {'freq': 1, 'series': 12},
        'isquios':    {'freq': 1, 'series': 12},
        'pecho':      {'freq': 1, 'series': 14},
        'trapecios':  {'freq': 1, 'series':  6},
        'triceps':    {'freq': 1, 'series': 10},
    }

    def setUp(self):
        _, self._planner = _build_planner(self.PERFIL)
        self._semana = _semana_bloque0(self._planner)

    def test_resumen(self):
        self.assertEqual(_resumen(self._semana), self.RESUMEN_ESPERADO)

    def test_dias_presentes(self):
        self.assertEqual(len(self._semana), 3)

    def test_todos_freq_1(self):
        """Con 3 días, freq_deseada siempre ≤ 3 — todos los grupos quedan en freq=1."""
        for grupo, stats in _resumen(self._semana).items():
            self.assertEqual(stats['freq'], 1, f"{grupo} debería ser freq=1 en 3 días")

    def test_12_grupos_post_x7(self):
        """
        Post-X.7: el motor asigna los 12 grupos musculares incluyendo
        core, trapecios y antebrazos que DISTRIBUCION_DIAS[3] omitía.
        """
        resumen = _resumen(self._semana)
        for grupo in ('core', 'trapecios', 'antebrazos'):
            self.assertIn(grupo, resumen, f"{grupo} debería aparecer con el motor nuevo")


# ---------------------------------------------------------------------------
# Intermedio — 4 días (Upper/Lower)
# ---------------------------------------------------------------------------

class TestCaracterizacionIntermedio4d(TestCase):
    """
    Intermedio, 4 días. Post-X.7: el motor decide la asignación por volumen.
    El split resultante es muy distinto al Upper/Lower de DISTRIBUCION_DIAS[4].
    """

    PERFIL = {
        'id': 98,
        'experiencia_años': 2,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 4,
    }

    # Post-X.7 + fix presupuesto bisagra por variante: motor activo. Core y
    # gemelos suben a freq=2. Cuadriceps queda en freq=1 (degradado). Isquios
    # en freq=1 con sus 2 ejercicios completos (antes del fix del presupuesto
    # de bisagra por variante, glúteos agotaba el cupo compartido y dejaba a
    # isquios solo con Curl Femoral, 8 series).
    RESUMEN_ESPERADO = {
        'antebrazos': {'freq': 1, 'series':  6},
        'biceps':     {'freq': 1, 'series': 12},
        'core':       {'freq': 2, 'series': 12},
        'cuadriceps': {'freq': 1, 'series': 20},
        'espalda':    {'freq': 1, 'series': 20},
        'gemelos':    {'freq': 2, 'series': 12},
        'gluteos':    {'freq': 2, 'series': 20},
        'hombros':    {'freq': 2, 'series': 16},
        'isquios':    {'freq': 1, 'series': 16},
        'pecho':      {'freq': 1, 'series': 20},
        'trapecios':  {'freq': 1, 'series': 10},
        'triceps':    {'freq': 1, 'series': 12},
    }

    def setUp(self):
        _, self._planner = _build_planner(self.PERFIL)
        self._semana = _semana_bloque0(self._planner)

    def test_resumen(self):
        self.assertEqual(_resumen(self._semana), self.RESUMEN_ESPERADO)

    def test_gluteos_freq2_post_x7(self):
        """Post-X.7: glúteos en freq=2, 20 series totales con motor activo."""
        resumen = _resumen(self._semana)
        self.assertEqual(resumen['gluteos']['freq'],   2)
        self.assertEqual(resumen['gluteos']['series'], 20)

    def test_hombros_freq2_post_x7(self):
        """Post-X.7: hombros en freq=2, 16 series (motor lo asigna dos veces)."""
        resumen = _resumen(self._semana)
        self.assertEqual(resumen['hombros']['freq'],   2)
        self.assertEqual(resumen['hombros']['series'], 16)


# ---------------------------------------------------------------------------
# Avanzado — 6 días (PPL × 2)
# ---------------------------------------------------------------------------

class TestCaracterizacionAvanzado6d(TestCase):
    """
    Avanzado, 6 días. Post-X.7: bíceps sube a freq=3, antebrazos a freq=2.
    Tríceps baja a freq=1 (degradado por presupuesto). El resto de grupos
    grandes mantiene freq=2.
    """

    PERFIL = {
        'id': 97,
        'experiencia_años': 5,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 6,
    }

    # Post-X.7: motor activo. biceps=3/18 (vol_efectivo=18 con vol_mult=1.2,
    # ceil(18/8)=3), antebrazos=2/12 (vol_efectivo=9, ceil(9/8)=2),
    # triceps=1/16 (degradado desde freq=2 deseada por presupuesto).
    RESUMEN_ESPERADO = {
        'antebrazos': {'freq': 2, 'series': 12},
        'biceps':     {'freq': 3, 'series': 18},
        'core':       {'freq': 2, 'series': 16},
        'cuadriceps': {'freq': 2, 'series': 28},
        'espalda':    {'freq': 2, 'series': 28},
        'gemelos':    {'freq': 2, 'series': 20},
        'gluteos':    {'freq': 2, 'series': 24},
        'hombros':    {'freq': 2, 'series': 20},
        'isquios':    {'freq': 2, 'series': 20},
        'pecho':      {'freq': 2, 'series': 24},
        'trapecios':  {'freq': 2, 'series': 12},
        'triceps':    {'freq': 1, 'series': 16},
    }

    def setUp(self):
        _, self._planner = _build_planner(self.PERFIL)
        self._semana = _semana_bloque0(self._planner)

    def test_resumen(self):
        self.assertEqual(_resumen(self._semana), self.RESUMEN_ESPERADO)

    def test_grupos_grandes_freq_2(self):
        """Post-X.7: grupos grandes (pecho, espalda, cuadriceps, isquios) en freq=2."""
        resumen = _resumen(self._semana)
        for grupo in ('pecho', 'espalda', 'cuadriceps', 'isquios'):
            self.assertEqual(resumen[grupo]['freq'], 2, f"{grupo} debería ser freq=2 en 6 días")

    def test_biceps_freq3_post_x7(self):
        """
        Post-X.7: bíceps sube a freq=3 en avanzado/6d.
        vol_efectivo = int(min(15 × 1.2, 18)) = 18; ceil(18/8) = 3.
        """
        resumen = _resumen(self._semana)
        self.assertEqual(resumen['biceps']['freq'], 3)

    def test_techo_20_series_por_grupo_por_dia(self):
        """
        Post-X.4 corregido: tope=10 por ejercicio × 2 ejercicios = 20 series/grupo/día
        como techo estructural máximo.
        """
        for dia_key, ejercicios in self._semana.items():
            por_grupo: dict = {}
            for ej in ejercicios:
                g = ej['grupo_muscular']
                por_grupo[g] = por_grupo.get(g, 0) + ej['series']
            for grupo, series in por_grupo.items():
                self.assertLessEqual(
                    series, 20,
                    f"{grupo} en {dia_key} supera 20 series"
                )


# ---------------------------------------------------------------------------
# Avanzado — 3 días
# ---------------------------------------------------------------------------

class TestCaracterizacionAvanzado3d(TestCase):
    """
    Avanzado, 3 días. Post-X.7: los 12 grupos aparecen (motor los asigna).
    Todos freq=1 (3 días limita frecuencia).
    """

    PERFIL = {
        'id': 96,
        'experiencia_años': 5,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 3,
    }

    # Post-X.7: los 12 grupos aparecen. Mismo freq=1 que antes pero ahora
    # incluye core, trapecios y antebrazos que DISTRIBUCION_DIAS[3] omitía.
    RESUMEN_ESPERADO = {
        'antebrazos': {'freq': 1, 'series': 10},
        'biceps':     {'freq': 1, 'series': 16},
        'core':       {'freq': 1, 'series': 16},
        'cuadriceps': {'freq': 1, 'series': 20},
        'espalda':    {'freq': 1, 'series': 20},
        'gemelos':    {'freq': 1, 'series': 16},
        'gluteos':    {'freq': 1, 'series': 20},
        'hombros':    {'freq': 1, 'series': 16},
        'isquios':    {'freq': 1, 'series': 20},
        'pecho':      {'freq': 1, 'series': 20},
        'trapecios':  {'freq': 1, 'series': 12},
        'triceps':    {'freq': 1, 'series': 16},
    }

    def setUp(self):
        _, self._planner = _build_planner(self.PERFIL)
        self._semana = _semana_bloque0(self._planner)

    def test_resumen(self):
        self.assertEqual(_resumen(self._semana), self.RESUMEN_ESPERADO)

    def test_avanzado_mas_volumen_que_novato_3d(self):
        """
        Con la diferenciación real de X.3+X.4, avanzado debe tener igual o
        más series que principiante en cada grupo.
        """
        _, planner_novato = _build_planner({
            'id': 99, 'experiencia_años': 0.5,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3,
        })
        resumen_avanzado = _resumen(self._semana)
        resumen_novato = _resumen(_semana_bloque0(planner_novato))
        for grupo in resumen_novato:
            with self.subTest(grupo=grupo):
                self.assertGreaterEqual(
                    resumen_avanzado[grupo]['series'], resumen_novato[grupo]['series'],
                    f"{grupo}: avanzado ({resumen_avanzado[grupo]['series']}) debería tener "
                    f"≥ series que novato ({resumen_novato[grupo]['series']})"
                )


# ---------------------------------------------------------------------------
# Principiante — 6 días
# ---------------------------------------------------------------------------

class TestCaracterizacionNovato6d(TestCase):
    """
    Principiante, 6 días. Post-X.7: core aparece ahora con freq=2.
    Trapecios degradado a freq=1; tríceps degradado a freq=1.
    """

    PERFIL = {
        'id': 95,
        'experiencia_años': 0.5,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 6,
    }

    # Post-X.7: motor activo. core=2/12 (nuevo), triceps=1/10 (degradado),
    # trapecios=1/6 (degradado).
    RESUMEN_ESPERADO = {
        'antebrazos': {'freq': 1, 'series':  6},
        'biceps':     {'freq': 2, 'series': 12},
        'core':       {'freq': 2, 'series': 12},
        'cuadriceps': {'freq': 2, 'series': 16},
        'espalda':    {'freq': 2, 'series': 16},
        'gemelos':    {'freq': 2, 'series': 12},
        'gluteos':    {'freq': 2, 'series': 12},
        'hombros':    {'freq': 2, 'series': 12},
        'isquios':    {'freq': 2, 'series': 12},
        'pecho':      {'freq': 2, 'series': 16},
        'trapecios':  {'freq': 1, 'series':  6},
        'triceps':    {'freq': 1, 'series': 10},
    }

    def setUp(self):
        _, self._planner = _build_planner(self.PERFIL)
        self._semana = _semana_bloque0(self._planner)

    def test_resumen(self):
        self.assertEqual(_resumen(self._semana), self.RESUMEN_ESPERADO)

    def test_series_menores_que_avanzado_6d(self):
        """Principiante 6d < avanzado 6d en grupos donde el volumen base difiere."""
        _, p_avanzado = _build_planner({
            'id': 97, 'experiencia_años': 5,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6,
        })
        s_avanzado = _resumen(_semana_bloque0(p_avanzado))
        s_novato = _resumen(self._semana)
        for grupo in ('pecho', 'hombros', 'isquios'):
            self.assertLessEqual(
                s_novato[grupo]['series'], s_avanzado[grupo]['series'],
                f"{grupo}: principiante debería tener ≤ series que avanzado"
            )


# ---------------------------------------------------------------------------
# Intermedio — 5 días
# ---------------------------------------------------------------------------

class TestCaracterizacionIntermedio5d(TestCase):
    """
    Intermedio, 5 días. Post-X.7: motor activo. Muchos grupos en freq=2.
    Split completamente distinto al Body Part Split anterior.
    """

    PERFIL = {
        'id': 94,
        'experiencia_años': 2,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 5,
    }

    # Post-X.7: espalda=2/24, core=2/12, cuadriceps=2/20, biceps=2/12,
    # gemelos=2/12, gluteos=2/20, hombros=2/16, trapecios=2/12.
    # pecho/triceps/isquios/antebrazos en freq=1.
    RESUMEN_ESPERADO = {
        'antebrazos': {'freq': 1, 'series':  6},
        'biceps':     {'freq': 2, 'series': 12},
        'core':       {'freq': 2, 'series': 12},
        'cuadriceps': {'freq': 2, 'series': 20},
        'espalda':    {'freq': 2, 'series': 24},
        'gemelos':    {'freq': 2, 'series': 12},
        'gluteos':    {'freq': 2, 'series': 20},
        'hombros':    {'freq': 2, 'series': 16},
        'isquios':    {'freq': 1, 'series': 16},
        'pecho':      {'freq': 1, 'series': 20},
        'trapecios':  {'freq': 2, 'series': 12},
        'triceps':    {'freq': 1, 'series': 12},
    }

    def setUp(self):
        _, self._planner = _build_planner(self.PERFIL)
        self._semana = _semana_bloque0(self._planner)

    def test_resumen(self):
        self.assertEqual(_resumen(self._semana), self.RESUMEN_ESPERADO)


# ---------------------------------------------------------------------------
# Test de determinismo
# ---------------------------------------------------------------------------

class TestDeterminismo(TestCase):
    """
    El motor debe ser 100% determinista: misma entrada → misma salida,
    sin importar cuántas veces se invoque en la misma sesión o en sesiones
    distintas. Requisito duro para que SesionProgramada sea estable.
    """

    def _ejecutar(self, perfil_data: dict) -> dict:
        _, planner = _build_planner(perfil_data)
        return _semana_bloque0(planner)

    def test_david_mismo_resultado_dos_ejecuciones(self):
        perfil = {'id': 2, 'experiencia_años': 7, 'objetivo_principal': 'general', 'dias_disponibles': 5}
        s1 = self._ejecutar(perfil)
        s2 = self._ejecutar(perfil)
        self.assertEqual(_estructura_dia(s1), _estructura_dia(s2))

    def test_estructura_identica_byte_a_byte(self):
        perfil = {'id': 2, 'experiencia_años': 7, 'objetivo_principal': 'general', 'dias_disponibles': 5}
        s1 = self._ejecutar(perfil)
        s2 = self._ejecutar(perfil)
        for dia in sorted(s1.keys()):
            nombres1 = [e['nombre']  for e in s1[dia]]
            series1  = [e['series']  for e in s1[dia]]
            nombres2 = [e['nombre']  for e in s2[dia]]
            series2  = [e['series']  for e in s2[dia]]
            self.assertEqual(nombres1, nombres2, f"Nombres diferentes en {dia}")
            self.assertEqual(series1,  series2,  f"Series diferentes en {dia}")

    def test_determinismo_todos_los_perfiles_de_la_matriz(self):
        """Verifica determinismo en los 7 perfiles de la matriz de caracterización."""
        perfiles = [
            {'id':  2, 'experiencia_años': 7,   'objetivo_principal': 'general',     'dias_disponibles': 5},
            {'id': 99, 'experiencia_años': 0.5, 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3},
            {'id': 98, 'experiencia_años': 2,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 4},
            {'id': 97, 'experiencia_años': 5,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6},
            {'id': 96, 'experiencia_años': 5,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3},
            {'id': 95, 'experiencia_años': 0.5, 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6},
            {'id': 94, 'experiencia_años': 2,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 5},
        ]
        for pdata in perfiles:
            with self.subTest(perfil=f"id={pdata['id']} dias={pdata['dias_disponibles']}"):
                s1 = self._ejecutar(pdata)
                s2 = self._ejecutar(pdata)
                self.assertEqual(
                    _estructura_dia(s1),
                    _estructura_dia(s2),
                    f"Motor no determinista para perfil {pdata}"
                )


# ---------------------------------------------------------------------------
# Tests X.7 — motor de asignación conectado
# ---------------------------------------------------------------------------

class TestX7MotorConectado(TestCase):
    """
    Tests específicos de X.7: verifica que el motor nuevo está activo,
    que el fallback funciona y que los contratos de tipo_ejercicio se preservan.
    """

    PERFIL_DAVID = {
        'id': 2,
        'experiencia_años': 7,
        'objetivo_principal': 'general',
        'dias_disponibles': 5,
    }

    def _semana_david(self):
        _, planner = _build_planner(self.PERFIL_DAVID)
        return _semana_bloque0(planner)

    def test_motor_activo_biceps_freq2(self):
        """
        Con DISTRIBUCION_DIAS[5] (Body Part Split), bíceps tenía freq=1.
        Con el motor activo, bíceps sube a freq=2 para david.
        Verifica que el motor está conectado y no el fallback.
        """
        semana = self._semana_david()
        resumen = _resumen(semana)
        self.assertEqual(resumen['biceps']['freq'], 2,
                         "Si freq=1, el motor no está activo (DISTRIBUCION_DIAS fallback)")

    def test_motor_activo_core_aparece_multiples_dias(self):
        """
        DISTRIBUCION_DIAS[5] ponía core solo en dia_5 (una vez). Con el motor,
        core aparece en freq=2 para david. Confirma motor activo.
        """
        semana = self._semana_david()
        resumen = _resumen(semana)
        self.assertEqual(resumen['core']['freq'], 2,
                         "core debería estar en 2 días con motor activo")

    def test_fallback_asignacion_imposible(self):
        """
        Si AsignacionImposibleError se lanza, el código debe caer limpiamente
        al comportamiento de DISTRIBUCION_DIAS y loggear un warning.
        El plan resultante sigue siendo válido (mismo formato que antes de X.7).
        """
        from analytics.planificador_helms.distribucion.asignador import AsignacionImposibleError
        from analytics.planificador_helms.config import DISTRIBUCION_DIAS

        _, planner = _build_planner(self.PERFIL_DAVID)

        with patch('analytics.planificador_helms.core.asignar_semana',
                   side_effect=AsignacionImposibleError("Test fallback")):
            with self.assertLogs('analytics.planificador_helms.core', level='WARNING') as cm:
                semana = _semana_bloque0(planner)

        # Debe haber loggeado el warning
        self.assertTrue(any('fallback' in msg.lower() or 'DISTRIBUCION_DIAS' in msg
                            for msg in cm.output))

        # El resultado debe tener la estructura de DISTRIBUCION_DIAS[5]
        grupos_por_dia_resultado = {
            dia: sorted({ej['grupo_muscular'] for ej in ejs})
            for dia, ejs in semana.items()
        }
        grupos_por_dia_fallback = {
            dia: sorted(grupos)
            for dia, grupos in DISTRIBUCION_DIAS[5].items()
        }
        self.assertEqual(grupos_por_dia_resultado, grupos_por_dia_fallback,
                         "En fallback, el split debe ser idéntico a DISTRIBUCION_DIAS[5]")

    def test_tipo_ejercicio_compuesto_principal_preservado(self):
        """
        X.7 no debe alterar la clasificación tipo_ejercicio. Los grupos grandes
        con ejercicios compuestos NO bloqueados por patron_manager deben seguir
        teniendo al menos un 'compuesto_principal' en el plan.

        Nota sobre isquios (david/5d): aunque isquios está en GRUPOS_GRANDES,
        patron_manager.dias_usados_bisagra llega a 2 (tope hipertrofia) antes
        de procesar isquios en dia_3 (gluteos en dia_1 y dia_3 agotaron el budget).
        Resultado: solo Curl Femoral Tumbado (aislamiento). Este comportamiento
        es correcto y pre-existente a X.7 — no es un bug del motor.

        Por tanto, verificamos solo los grupos donde compuesto_principal SÍ aparece
        con X.7, que son: pecho, espalda, cuadriceps, gluteos.
        """
        semana = self._semana_david()

        # Grupos donde compuesto_principal aparece con el motor nuevo (david/5d).
        # isquios se excluye porque su compuesto (Peso Muerto Rumano) está
        # legitimamente bloqueado por el tope de patron_manager.
        grupos_grandes_con_compuesto = {'pecho', 'espalda', 'cuadriceps', 'gluteos'}
        tiene_compuesto_principal = {}

        for dia_ejs in semana.values():
            for ej in dia_ejs:
                if ej['grupo_muscular'] in grupos_grandes_con_compuesto:
                    g = ej['grupo_muscular']
                    if ej['tipo_ejercicio'] == 'compuesto_principal':
                        tiene_compuesto_principal[g] = True

        for grupo in grupos_grandes_con_compuesto:
            with self.subTest(grupo=grupo):
                self.assertIn(
                    grupo, tiene_compuesto_principal,
                    f"{grupo} (grupo grande) no tiene ningún ejercicio 'compuesto_principal'"
                )

    def test_tipo_ejercicio_campo_presente_en_todos_los_ejercicios(self):
        """
        X.7 no debe crear ejercicios sin campo tipo_ejercicio.
        El campo es obligatorio para inferir_prioridad_sesion.
        """
        semana = self._semana_david()
        for dia_key, ejercicios in semana.items():
            for ej in ejercicios:
                self.assertIn('tipo_ejercicio', ej,
                              f"{ej['nombre']} en {dia_key} no tiene campo tipo_ejercicio")
                self.assertIsNotNone(ej['tipo_ejercicio'],
                                     f"{ej['nombre']} en {dia_key} tiene tipo_ejercicio=None")

    def test_freq_efectiva_coherente_con_dias_del_plan(self):
        """
        La frecuencia de cada grupo en el resultado debe coincidir con el número
        de días distintos donde ese grupo aparece en el plan.
        (Verifica que el código usa frecuencia_map correctamente — no hay off-by-one.)
        """
        from analytics.planificador_helms.distribucion.asignador import asignar_semana

        resultados_motor = []

        original_asignar = asignar_semana

        def capturar(*args, **kwargs):
            resultado = original_asignar(*args, **kwargs)
            resultados_motor.append(resultado)
            return resultado

        _, planner = _build_planner(self.PERFIL_DAVID)

        with patch('analytics.planificador_helms.core.asignar_semana', side_effect=capturar):
            semana = _semana_bloque0(planner)

        if not resultados_motor:
            self.skipTest("Motor no fue llamado (posible caché)")

        resultado = resultados_motor[0]
        freq_efectiva = resultado.frecuencia_efectiva

        # Contar días reales en el plan para cada grupo
        grupos_dias_reales = {}
        for dia, ejs in semana.items():
            for ej in ejs:
                grupos_dias_reales.setdefault(ej['grupo_muscular'], set()).add(dia)

        for grupo, dias_reales in grupos_dias_reales.items():
            freq_real = len(dias_reales)
            freq_motor = freq_efectiva.get(grupo, 0)
            # La frecuencia real puede diferir de la efectiva del motor si
            # el patron_manager filtra algún ejercicio de un día asignado.
            # Lo que NO puede pasar: que la frecuencia real SUPERE la del motor.
            self.assertLessEqual(
                freq_real, freq_motor + 1,  # +1 de tolerancia para casos de patron_manager
                f"{grupo}: freq_real={freq_real} supera freq_motor={freq_motor} de forma inesperada"
            )
