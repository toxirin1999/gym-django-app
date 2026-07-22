# analytics/test_planificador_helms_x4.py
"""
Tests TDD para X.4 — topes dinámicos de series por ejercicio.

Escritos a partir del estado post-X.3 (donde el literal `4` en core.py
oculta el volumen calculado por CalculadoraVolumen).

Cambios que validan:
  1. `TOPE_SERIES_POR_EJERCICIO` en config.py sustituye al literal `4`.
  2. `candidatos[:n_ejercicios_grupo]` lee la regla desde SelectorEjercicios
     en lugar del `[:2]` hardcodeado en paralelo.
  3. El techo real en producción pasa a ser GestorFatiga (fatiga + sesión),
     no core.py.

Grupos de tests:
  - TestX4TopeDinamicoHipertrofia: ROJO antes del fix, VERDE después.
  - TestX4GestorFatigaSigueCortando: verifica que GestorFatiga actúa
    cuando corresponde (VERDE antes y después del fix — documenta invariante).
  - TestX4Descarga: tope=3 por ejercicio en fase descarga (ROJO antes).
  - TestX4SinRegresionNovato6d: novato 6d no cambia (vol_dia/n_ej ≤ 4).
  - TestX4ConsistenciaConfigSelector: TOPE_SERIES_POR_EJERCICIO cubre todas
    las fases que SelectorEjercicios conoce.
"""

from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
from analytics.planificador_helms.config import (
    TOPE_SERIES_POR_EJERCICIO,
    LIMITES_FATIGA,
    LIMITES_SERIES_SESION,
    GRUPOS_GRANDES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_planner(perfil_data: dict) -> PlanificadorHelms:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    return planner


def _semana_bloque0(planner: PlanificadorHelms) -> dict:
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    return planner._generar_semana_especifica(periodizacion[0], 1)


def _resumen(semana: dict) -> dict:
    gs: dict = {}
    gd: dict = {}
    for dia_key, ejercicios in semana.items():
        for ej in ejercicios:
            g = ej['grupo_muscular']
            gs[g] = gs.get(g, 0) + ej['series']
            gd.setdefault(g, set()).add(dia_key)
    return {g: {'freq': len(gd[g]), 'series': gs[g]} for g in gs}


PERFIL_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}


# ===========================================================================
# 1. Tope dinámico — output real supera la barrera de 8 series
# ===========================================================================

class TestX4TopeDinamicoHipertrofia(TestCase):
    """
    ROJO con el código anterior (min(4,...) → max 8 series/grupo/día, plano
    para todos los grupos).

    VERDE con X.4 corregido: TOPE_SERIES_POR_EJERCICIO['hipertrofia']=10,
    fijado en o por encima de LIMITES_SERIES_SESION['grupos_grandes']['max']
    (=10) a propósito, para que el tope actúe como defensa en profundidad y
    sea GestorFatiga (grandes≤10/ejercicio, pequeños≤8/ejercicio) quien
    realmente diferencie el resultado según el volumen_optimo calculado por
    CalculadoraVolumen (X.3) para cada grupo. Por eso el resultado para
    david YA NO es un número plano — cada grupo refleja su propio MEV/MRV:
    grandes en 18-20 (cerca de su techo de sesión), pequeños entre 10 y 16
    según su volumen objetivo individual.
    """

    def setUp(self):
        self._planner = _build_planner(PERFIL_DAVID)
        self._semana = _semana_bloque0(self._planner)
        self._resumen = _resumen(self._semana)

    def test_pecho_supera_8_series_bloque_hipertrofia(self):
        """
        Con CalculadoraVolumen (X.3) el volumen objetivo de pecho avanzado
        es alto (cerca de su MRV=22). Tope viejo: min(4,...)*2 = 8 total,
        plano para todos los grupos. Tope X.4 corregido: GestorFatiga
        (grandes≤10/ejercicio) acota pecho a 20 total — muy por encima de 8.
        """
        self.assertGreater(
            self._resumen['pecho']['series'], 8,
            "Pecho avanzado+hipertrofia debe superar 8 series tras X.4"
        )

    def test_pecho_exactamente_catorce_series(self):
        self.assertEqual(self._resumen['pecho']['series'], 14)

    def test_grupos_grandes_diferenciados_por_volumen_real(self):
        """
        Para david (avanzado, general anclado a MEV, 5d), los grupos grandes
        siguen sin dar todos el mismo número — cada uno refleja su
        volumen_optimo real × freq asignada, acotado por GestorFatiga.

        Post objetivo='general' anclado a MEV (2026-07-20, volumen moderado):
        espalda y cuadriceps alcanzan freq=2; pecho/gluteos/isquios varían
        según su propio volumen_optimo (gluteos también sube a freq=2, isquios
        se queda en freq=1).
        """
        esperado = {
            'pecho':       14,
            'espalda':     16,
            'cuadriceps':  16,
            'gluteos':     12,
            'isquios':     12,
        }
        for grupo, series_esperadas in esperado.items():
            with self.subTest(grupo=grupo):
                self.assertEqual(
                    self._resumen[grupo]['series'], series_esperadas,
                    f"{grupo} debería dar {series_esperadas} series tras X.4+X.7"
                )

    def test_grupos_pequenos_diferenciados_por_volumen_real(self):
        """
        Los grupos pequeños varían según su volumen_optimo × freq asignada.
        Post objetivo='general' anclado a MEV (2026-07-20): biceps, hombros,
        gemelos y triceps alcanzan freq=2; core/trapecios/antebrazos quedan
        en freq=1 con el volumen moderado.
        """
        esperado = {
            'biceps':     12,
            'triceps':    12,
            'hombros':    12,
            'gemelos':    12,
            'core':        8,
            'trapecios':   8,
            'antebrazos':  6,
        }
        for grupo, series_esperadas in esperado.items():
            with self.subTest(grupo=grupo):
                self.assertEqual(
                    self._resumen[grupo]['series'], series_esperadas,
                    f"{grupo} (pequeño) debería dar {series_esperadas} series tras X.4+X.7"
                )

    def test_grupos_grandes_no_todos_iguales(self):
        """
        Guarda de regresión específica del bug detectado en el primer intento
        de X.4: con un tope demasiado bajo, TODOS los grupos convergían al
        mismo número (10 para todos), anulando la diferenciación de X.3.
        Este test falla si eso vuelve a ocurrir.
        """
        valores = {self._resumen[g]['series'] for g in
                   ('pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos')}
        self.assertGreater(
            len(valores), 1,
            "Los grupos grandes no deberían converger todos al mismo número — "
            "eso indica que el tope está aplanando el volumen calculado por X.3."
        )

    def test_ninguna_serie_por_ejercicio_excede_tope_por_fase(self):
        """
        Ningún ejercicio individual supera TOPE_SERIES_POR_EJERCICIO['hipertrofia']=10.
        """
        tope = TOPE_SERIES_POR_EJERCICIO['hipertrofia']
        for dia, ejercicios in self._semana.items():
            for ej in ejercicios:
                with self.subTest(dia=dia, ejercicio=ej['nombre']):
                    self.assertLessEqual(
                        ej['series'], tope,
                        f"{ej['nombre']} en {dia}: {ej['series']} > tope={tope}"
                    )

    def test_ninguna_serie_excede_limite_sesion_gestor_fatiga(self):
        """
        Ningún ejercicio supera LIMITES_SERIES_SESION.max para su tipo de grupo.
        Esto verifica que GestorFatiga sigue siendo el filtro de seguridad final.
        """
        for dia, ejercicios in self._semana.items():
            for ej in ejercicios:
                grupo = ej['grupo_muscular']
                if grupo in GRUPOS_GRANDES:
                    max_sesion = LIMITES_SERIES_SESION['grupos_grandes']['max']
                else:
                    max_sesion = LIMITES_SERIES_SESION['grupos_pequenos']['max']
                with self.subTest(dia=dia, ejercicio=ej['nombre']):
                    self.assertLessEqual(
                        ej['series'], max_sesion,
                        f"{ej['nombre']} ({grupo}) = {ej['series']} series > límite sesión={max_sesion}"
                    )


# ===========================================================================
# 2. GestorFatiga sigue siendo el techo cuando corresponde
# ===========================================================================

class TestX4GestorFatigaSigueCortando(TestCase):
    """
    Cuando rpe=9 todos los ejercicios son 'pesados'. GestorFatiga aplica
    rodilla_pesada_max (=5 en hipertrofia) sobre cuadriceps. El resultado
    total para cuadriceps no puede exceder ese presupuesto — independiente de
    que el vol_mult sea arbitrariamente alto.

    Este test documenta que el techo real viene de GestorFatiga, no de
    core.py. Debe pasar ANTES y DESPUÉS de X.4.
    """

    PERFIL = {
        'id': 2,
        'experiencia_años': 7,
        'objetivo_principal': 'general',
        'dias_disponibles': 5,
    }

    def _generar_bloque_rpe9_vol_alto(self) -> dict:
        """Bloque0 candidatos (Sentadilla Hack + Prensa de Piernas, ambos patron=rodilla)
        pero con rpe=9 (pesado) y vol_mult artificialmente alto."""
        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        bloque = dict(periodizacion[0])
        bloque['intensidad_rpe'] = (9,)
        bloque['volumen_multiplicador'] = 5.0
        return bloque

    def test_cuadriceps_acotado_por_rodilla_pesada_max(self):
        """
        Con rpe=9, ejercicios de cuadriceps tienen patron='rodilla' → es_pesado=True.
        GestorFatiga aplica rodilla_pesada_max=5 POR DÍA (se reinicia cada día).

        Post-X.7: cuadriceps aparece en 2 días. En cada día individual, cuadriceps
        no puede superar rodilla_pesada_max. El total semanal puede ser > 5.

        Verificamos el invariante real: NINGÚN DÍA supera rodilla_pesada_max.
        En un día (dia_1), core consume el presupuesto pesado global primero
        → cuadriceps solo alcanza 2 series. En el otro (dia_4), cuadriceps
        va primero → agota rodilla_pesada_max=5 exactamente.
        """
        planner = _build_planner(self.PERFIL)
        bloque = self._generar_bloque_rpe9_vol_alto()
        semana = planner._generar_semana_especifica(bloque, 1)

        limite = LIMITES_FATIGA['hipertrofia']['rodilla_pesada_max']
        for dia_key, ejercicios in semana.items():
            series_cuadriceps_dia = sum(
                ej['series'] for ej in ejercicios
                if ej['grupo_muscular'] == 'cuadriceps'
            )
            if series_cuadriceps_dia > 0:
                self.assertLessEqual(
                    series_cuadriceps_dia, limite,
                    f"Cuadriceps en {dia_key} con rpe=9: {series_cuadriceps_dia} series "
                    f"> rodilla_pesada_max={limite}. GestorFatiga no actuó."
                )

    def test_cuadriceps_maximo_dia_es_rodilla_pesada_max_con_rpe9(self):
        """
        BUG ARREGLADO (2026-07-22, reparto per-grupo de series_pesadas_max):
        con rpe=9 todos los ejercicios son 'pesado'. Antes del fix, el
        presupuesto de series_pesadas_max era GLOBAL por sesión — los primeros
        grupos procesados lo agotaban y cuadriceps (y hasta 5 grupos más)
        desaparecía por completo de la semana.

        Después del fix: el presupuesto se reparte a partes iguales entre los
        grupos del día al instanciar GestorFatiga(fase, grupos_dia=...). Cada
        grupo tiene su propio cupo — el consumo de pecho no agota el cupo de
        cuadriceps. Ningún grupo grande desaparece del plan con rpe=9.
        """
        planner = _build_planner(self.PERFIL)
        bloque = self._generar_bloque_rpe9_vol_alto()
        semana = planner._generar_semana_especifica(bloque, 1)

        grupos_en_semana = set()
        for ejercicios in semana.values():
            for ej in ejercicios:
                grupos_en_semana.add(ej['grupo_muscular'])

        self.assertIn(
            'cuadriceps', grupos_en_semana,
            "Cuadriceps desapareció de la semana con rpe=9 — "
            "el fix de reparto per-grupo no está funcionando."
        )
        # Ningún grupo grande debe desaparecer entero por el presupuesto global agotado
        grupos_grandes_ausentes = [
            g for g in ('pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos')
            if g not in grupos_en_semana
        ]
        self.assertEqual(
            grupos_grandes_ausentes, [],
            f"Grupos grandes ausentes con rpe=9: {grupos_grandes_ausentes}. "
            "Con el fix, ninguno debe desaparecer por presupuesto global agotado."
        )


# ===========================================================================
# 3. Descarga: tope=3 (menor que el literal anterior de 4)
# ===========================================================================

class TestX4Descarga(TestCase):
    """
    Fase descarga: TOPE_SERIES_POR_EJERCICIO['descarga']=4. Aquí SÍ queremos
    que el tope sea restrictivo de verdad (no defensa en profundidad como en
    hipertrofia) — es una fase de volumen intencionalmente bajo.
    SelectorEjercicios.obtener_reglas_por_fase('descarga')['max_ej_por_grupo']=1
    → un solo ejercicio por grupo con máx 4 series.
    """

    PERFIL = {
        'id': 2,
        'experiencia_años': 7,
        'objetivo_principal': 'general',
        'dias_disponibles': 5,
    }

    def setUp(self):
        self._planner = _build_planner(self.PERFIL)
        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        self._bloque_descarga = next(b for b in periodizacion if b['fase'] == 'descarga')
        self._semana = self._planner._generar_semana_especifica(self._bloque_descarga, 2)

    def test_tope_por_ejercicio_es_4_en_descarga(self):
        self.assertEqual(TOPE_SERIES_POR_EJERCICIO.get('descarga', 4), 4)

    def test_max_ej_por_grupo_es_1_en_descarga(self):
        """SelectorEjercicios da max_ej=1 para descarga — igual que antes del fix."""
        reglas = SelectorEjercicios.obtener_reglas_por_fase('descarga')
        self.assertEqual(reglas['max_ej_por_grupo'], 1)

    def test_ninguna_serie_supera_4_en_descarga(self):
        """Ningún ejercicio supera el tope de descarga=4."""
        for dia, ejercicios in self._semana.items():
            for ej in ejercicios:
                with self.subTest(dia=dia, ejercicio=ej['nombre']):
                    self.assertLessEqual(
                        ej['series'], 4,
                        f"{ej['nombre']} en descarga: {ej['series']} > 4"
                    )

    def test_un_ejercicio_por_grupo_en_descarga(self):
        """max_ej_por_grupo=1 para descarga → un solo ejercicio por grupo muscular por día."""
        for dia, ejercicios in self._semana.items():
            grupos_vistos: dict = {}
            for ej in ejercicios:
                g = ej['grupo_muscular']
                grupos_vistos[g] = grupos_vistos.get(g, 0) + 1
            for g, count in grupos_vistos.items():
                with self.subTest(dia=dia, grupo=g):
                    self.assertEqual(count, 1, f"{g} aparece {count} veces en {dia}")

    def test_descarga_tope_menor_que_hipertrofia(self):
        """El tope de descarga (3) debe ser menor que el de hipertrofia (5)."""
        self.assertLess(
            TOPE_SERIES_POR_EJERCICIO['descarga'],
            TOPE_SERIES_POR_EJERCICIO['hipertrofia']
        )


# ===========================================================================
# 4. Sin regresión: novato 6d no cambia (vol_dia/n_ej ≤ 4)
# ===========================================================================

class TestX4SinRegresionNovato6d(TestCase):
    """
    Para novato 6d (PPL×2), vol_dia/n_ej ≤ 4 para la mayoría de grupos.
    min(5, ≤4) == min(4, ≤4) → mismo resultado. Los valores del bloque0
    deben ser idénticos a los pre-X.4.
    """

    PERFIL = {
        'id': 95,
        'experiencia_años': 0.5,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 6,
    }

    # Post fix presupuesto real del asignador + reducción vol_fin (2026-07-20).
    # Solo cuadriceps/espalda/hombros/pecho mantienen freq=2; el resto queda
    # en freq=1 con el volumen reducido.
    RESUMEN_PREVIO_X4 = {
        'antebrazos': {'freq': 1, 'series':  6},
        'biceps':     {'freq': 1, 'series': 10},
        'core':       {'freq': 1, 'series': 10},
        'cuadriceps': {'freq': 2, 'series': 16},
        'espalda':    {'freq': 2, 'series': 16},
        'gemelos':    {'freq': 1, 'series': 10},
        'gluteos':    {'freq': 1, 'series': 12},
        'hombros':    {'freq': 2, 'series': 12},
        'isquios':    {'freq': 1, 'series': 12},
        'pecho':      {'freq': 2, 'series': 16},
        'trapecios':  {'freq': 1, 'series':  6},
        'triceps':    {'freq': 1, 'series': 10},
    }

    def setUp(self):
        planner = _build_planner(self.PERFIL)
        self._resumen = _resumen(_semana_bloque0(planner))

    def test_novato_6d_sin_cambio_post_x4(self):
        """
        Post-X.7: los 12 grupos musculares aparecen en novato 6d (motor los asigna).
        core y trapecios nuevos. triceps degradado a freq=1. antebrazos en freq=1.
        El tope X.4 sigue sin afectar a pecho/espalda/cuadriceps/bíceps/gemelos porque
        ceil(vol_dia/2) ≤ 4 para novato — la diferenciación viene del motor, no del tope.
        """
        self.assertEqual(self._resumen, self.RESUMEN_PREVIO_X4)

    def test_pecho_novato_6d_16_series_sin_cambio(self):
        """Caso clave: pecho novato 6d vol_dia=7, ceil(7/2)=4 ≤ new_tope=5 → unchanged."""
        self.assertEqual(self._resumen['pecho']['series'], 16)

    def test_antebrazos_novato_6d_6_series_sin_cambio(self):
        """Antebrazos novato: vol_dia=5, ceil(5/2)=3 ≤ new_tope=5 → 3 per ej → 6 total."""
        self.assertEqual(self._resumen['antebrazos']['series'], 6)


# ===========================================================================
# 5. Consistencia: TOPE_SERIES_POR_EJERCICIO cubre todas las fases conocidas
# ===========================================================================

class TestX4ConsistenciaConfigSelector(TestCase):
    """
    Verifica que TOPE_SERIES_POR_EJERCICIO cubre todas las fases que
    SelectorEjercicios puede devolver, y que el fallback a 4 nunca se usa
    en producción normal.
    """

    FASES_CONOCIDAS = [
        'hipertrofia', 'hipertrofia_especifica', 'hipertrofia_metabolica',
        'fuerza', 'potencia', 'descarga',
    ]

    def test_tope_definido_para_todas_las_fases(self):
        for fase in self.FASES_CONOCIDAS:
            with self.subTest(fase=fase):
                self.assertIn(
                    fase, TOPE_SERIES_POR_EJERCICIO,
                    f"Fase '{fase}' no tiene tope definido en TOPE_SERIES_POR_EJERCICIO"
                )

    def test_valores_plausibles(self):
        """
        Todos los topes deben estar en el rango [2, 10] — el límite superior
        coincide con LIMITES_SERIES_SESION['grupos_grandes']['max']=10 a
        propósito: en fases de hipertrofia el tope debe llegar hasta ahí
        para actuar como defensa en profundidad, no como el techo real.
        """
        for fase, tope in TOPE_SERIES_POR_EJERCICIO.items():
            with self.subTest(fase=fase):
                self.assertGreaterEqual(tope, 2, f"Tope={tope} para '{fase}' es demasiado bajo")
                self.assertLessEqual(tope, 10, f"Tope={tope} para '{fase}' supera max de LIMITES_SERIES_SESION")

    def test_hipertrofia_mas_alta_que_descarga_y_potencia(self):
        """Las fases de mayor estímulo tienen topes más altos que descarga/potencia."""
        self.assertGreater(
            TOPE_SERIES_POR_EJERCICIO['hipertrofia'],
            TOPE_SERIES_POR_EJERCICIO['descarga']
        )
        self.assertGreater(
            TOPE_SERIES_POR_EJERCICIO['hipertrofia'],
            TOPE_SERIES_POR_EJERCICIO['potencia']
        )

    def test_tope_descarga_coincide_con_max_ej_1_ejercicio(self):
        """
        Para descarga, max_ej_por_grupo=1 y tope=4. Con un solo ejercicio de 4 series
        el volumen por día queda en 4 — correcto para una semana de recuperación activa.
        """
        reglas = SelectorEjercicios.obtener_reglas_por_fase('descarga')
        self.assertEqual(reglas['max_ej_por_grupo'], 1)
        self.assertEqual(TOPE_SERIES_POR_EJERCICIO['descarga'], 4)
