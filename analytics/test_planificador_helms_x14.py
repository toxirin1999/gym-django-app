# analytics/test_planificador_helms_x14.py
"""
Tests de X.14 — cableado de variación intra-semanal en core.py.

Contrato duro:
  - Toque 1 (primera aparición semanal de cada grupo): byte-idéntico al
    comportamiento previo a X.14, capturado en ESTRUCTURA_ESPERADA de
    TestCaracterizacionDavid.
  - Toque ≥2: ejercicios distintos del toque 1 cuando el pool lo permite;
    rep_range un peldaño más alto; RPE baja 1 (suelo 6).
  - Fallback (frecuencia_map=None): construir_variantes_por_toque no se llama,
    todos los días usan toque=1 (sin variación).
  - Determinismo: misma entrada → misma salida tras el cambio.

Perfiles de cobertura:
  - David (id=2, 5d, avanzado, general): caso principal — 7 grupos en freq=2.
  - Avanzado 6d (id=97): biceps/core/trapecios en freq=2.
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion


# ---------------------------------------------------------------------------
# Helpers — mismos que en el archivo de caracterización, duplicados aquí para
# mantener este módulo autónomo sin importar desde el otro test.
# ---------------------------------------------------------------------------

def _build_planner(perfil_data: dict) -> tuple:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    return perfil, planner


def _semana_bloque0(planner: PlanificadorHelms) -> dict:
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    bloque0 = periodizacion[0]
    return planner._generar_semana_especifica(bloque0, 1)


def _estructura_dia(semana: dict) -> dict:
    return {
        dia: [(ej['nombre'], ej['grupo_muscular'], ej['series']) for ej in ejercicios]
        for dia, ejercicios in sorted(semana.items())
    }


def _rep_ranges_por_grupo_y_dia(semana: dict) -> dict:
    """Devuelve {dia: {grupo: [rep_range, ...]}} para inspeccionar toque 2."""
    resultado = {}
    for dia, ejercicios in sorted(semana.items()):
        resultado[dia] = {}
        for ej in ejercicios:
            g = ej['grupo_muscular']
            resultado[dia].setdefault(g, []).append(ej['repeticiones'])
    return resultado


def _nombres_por_grupo_y_dia(semana: dict) -> dict:
    """Devuelve {dia: {grupo: [nombre, ...]}} para comparar ejercicios entre toques."""
    resultado = {}
    for dia, ejercicios in sorted(semana.items()):
        resultado[dia] = {}
        for ej in ejercicios:
            g = ej['grupo_muscular']
            resultado[dia].setdefault(g, []).append(ej['nombre'])
    return resultado


# ---------------------------------------------------------------------------
# Datos de referencia de X.13 (toque 1 — invariante duro)
# Copiados de TestCaracterizacionDavid.ESTRUCTURA_ESPERADA.
# Para X.14 son inmutables: dia_1 y dia_2 son 100% toque-1 para David.
# ---------------------------------------------------------------------------

DAVID_TOQUE1_DIA1 = [
    ('Sentadilla Hack',                            'cuadriceps',  4),
    ('Prensa de Piernas',                          'cuadriceps',  4),
    ('Elevación de Gemelos de Pie (Máquina)',      'gemelos',     3),
    ('Elevación de Gemelos Sentado (Máquina)',     'gemelos',     3),
    ('Hip Thrust con Barra',                       'gluteos',     3),
    ('Abducción de Cadera en Máquina',             'gluteos',     3),
    ('Press Francés con Barra Z',                  'triceps',     3),
    ('Extensiones de Tríceps con Polea Alta',      'triceps',     3),
]

DAVID_TOQUE1_DIA2 = [
    ('Aguante en Barra (Dead Hang)',                'antebrazos',  3),
    ('Farmer Walk (Paseo del Granjero)',            'antebrazos',  3),
    ('Curl con Barra Z',                           'biceps',      3),
    ('Curl Araña',                                 'biceps',      3),
    ('Jalón al Pecho',                             'espalda',     4),
    ('Remo pecho apoyado',                         'espalda',     4),
    ('Machine Shoulder Press',                     'hombros',     3),
    ('Press Arnold',                               'hombros',     3),
]

# En dia_3 solo core e isquios son toque-1 para David.
DAVID_TOQUE1_DIA3_GRUPOS_SOLO_TOQUE1 = {'core', 'isquios'}

# En dia_4 solo pecho es toque-1 para David.
DAVID_TOQUE1_DIA4_GRUPOS_SOLO_TOQUE1 = {'pecho'}

# En dia_5 solo trapecios es toque-1 para David.
DAVID_TOQUE1_DIA5_GRUPOS_SOLO_TOQUE1 = {'trapecios'}


# ---------------------------------------------------------------------------
# Perfil de David
# ---------------------------------------------------------------------------

PERFIL_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}

PERFIL_AVANZADO_6D = {
    'id': 97,
    'experiencia_años': 5,
    'objetivo_principal': 'hipertrofia',
    'dias_disponibles': 6,
}


# ---------------------------------------------------------------------------
# Test 1 — Invariante toque-1
# DEBE pasar tanto ANTES como DESPUÉS de X.14.
# ---------------------------------------------------------------------------

class TestX14InvarianteToque1(TestCase):
    """
    Verifica que el toque 1 (primera aparición de cada grupo en orden cronológico)
    es byte-idéntico al comportamiento pre-X.14 capturado en el golden master de X.13.

    dia_1 y dia_2 de David son 100% toque-1 → se verifican exhaustivamente.
    Para dia_3/4/5, se verifican solo los grupos freq=1 (que nunca cambian).
    """

    def setUp(self):
        _, self._planner = _build_planner(PERFIL_DAVID)
        self._semana = _semana_bloque0(self._planner)

    def test_dia1_byte_identico_al_golden_master_x13(self):
        """dia_1 es 100% toque-1 — ningún grupo con freq≥2 aparece por 2ª vez."""
        estructura = _estructura_dia(self._semana)
        self.assertEqual(
            estructura['dia_1'],
            DAVID_TOQUE1_DIA1,
            "dia_1 cambió respecto al golden master X.13 — invariante toque-1 roto",
        )

    def test_dia2_byte_identico_al_golden_master_x13(self):
        """dia_2 es 100% toque-1 — primera aparición de biceps/espalda/hombros."""
        estructura = _estructura_dia(self._semana)
        self.assertEqual(
            estructura['dia_2'],
            DAVID_TOQUE1_DIA2,
            "dia_2 cambió respecto al golden master X.13 — invariante toque-1 roto",
        )

    def test_dia3_grupos_toque1_no_cambian(self):
        """En dia_3, core e isquios son toque-1 y no deben cambiar."""
        estructura = _estructura_dia(self._semana)
        nombres = _nombres_por_grupo_y_dia(self._semana)

        # core toque-1: Crunch en Polea + Pallof Press
        core_nombres = nombres.get('dia_3', {}).get('core', [])
        self.assertIn('Crunch en Polea (Cable Crunch)', core_nombres,
                      "core toque-1 cambió — invariante roto")
        self.assertIn('Pallof Press', core_nombres,
                      "core toque-1 cambió — invariante roto")

        # isquios toque-1: Peso Muerto Rumano + Curl Femoral
        isquios_nombres = nombres.get('dia_3', {}).get('isquios', [])
        self.assertIn('Peso Muerto Rumano', isquios_nombres,
                      "isquios toque-1 cambió — invariante roto")
        self.assertIn('Curl Femoral Tumbado', isquios_nombres,
                      "isquios toque-1 cambió — invariante roto")

    def test_dia4_pecho_toque1_no_cambia(self):
        """En dia_4, pecho es toque-1 (freq=1) y no debe cambiar."""
        nombres = _nombres_por_grupo_y_dia(self._semana)
        pecho_nombres = nombres.get('dia_4', {}).get('pecho', [])
        self.assertIn('Convergent Machine Press', pecho_nombres,
                      "pecho toque-1 cambió — invariante roto")
        self.assertIn('Press Cerrado en Banca', pecho_nombres,
                      "pecho toque-1 cambió — invariante roto")

    def test_dia5_trapecios_toque1_no_cambia(self):
        """En dia_5, trapecios es toque-1 (freq=1) y no debe cambiar."""
        nombres = _nombres_por_grupo_y_dia(self._semana)
        trapecios_nombres = nombres.get('dia_5', {}).get('trapecios', [])
        self.assertIn('Encogimientos con Barra', trapecios_nombres,
                      "trapecios toque-1 cambió — invariante roto")
        self.assertIn('Farmer Walk (Paseo del Granjero)', trapecios_nombres,
                      "trapecios toque-1 cambió — invariante roto")

    def test_resumen_freq_series_no_cambia(self):
        """
        X.14 solo cambia qué ejercicio se usa, no cuántas series ni cuántas frecuencias.
        El resumen (grupos × freq × series) debe ser idéntico al de X.13.
        """
        from analytics.test_planificador_helms_volumen_caracterizacion import (
            _resumen, TestCaracterizacionDavid,
        )
        resumen = _resumen(self._semana)
        self.assertEqual(resumen, TestCaracterizacionDavid.RESUMEN_ESPERADO)


# ---------------------------------------------------------------------------
# Test 2 — Variación real en toque 2
# DEBE fallar ANTES de X.14, pasar DESPUÉS.
# ---------------------------------------------------------------------------

class TestX14VariacionToque2David(TestCase):
    """
    Verifica que el toque 2 de cada grupo de David usa ejercicios distintos
    al toque 1, y que el rep_range es un peldaño más alto.
    """

    def setUp(self):
        _, self._planner = _build_planner(PERFIL_DAVID)
        self._semana = _semana_bloque0(self._planner)
        self._nombres = _nombres_por_grupo_y_dia(self._semana)
        self._rep_ranges = _rep_ranges_por_grupo_y_dia(self._semana)

    def _toque1_nombres(self, grupo: str, dia_toque1: str) -> set:
        return set(self._nombres.get(dia_toque1, {}).get(grupo, []))

    def _toque2_nombres(self, grupo: str, dia_toque2: str) -> set:
        return set(self._nombres.get(dia_toque2, {}).get(grupo, []))

    def test_biceps_toque2_ejercicio_diferente(self):
        """
        bíceps aparece en dia_2 (toque 1) y dia_5 (toque 2).
        Toque 2 debe usar al menos un ejercicio distinto.
        """
        t1 = self._toque1_nombres('biceps', 'dia_2')
        t2 = self._toque2_nombres('biceps', 'dia_5')
        self.assertTrue(
            bool(t2 - t1),
            f"bíceps toque-2 {t2} no tiene ningún ejercicio nuevo respecto a toque-1 {t1}",
        )

    def test_biceps_toque2_rep_range_mayor(self):
        """
        bíceps es músculo pequeño: toque-1 usa '12-15' (post AJUSTE_PEQUENOS),
        toque-2 debe usar '15-20'.
        """
        t2_ranges = self._rep_ranges.get('dia_5', {}).get('biceps', [])
        self.assertTrue(
            all(r in ('15-20',) for r in t2_ranges),
            f"bíceps toque-2 debería tener rep_range '15-20', got {t2_ranges}",
        )

    def test_espalda_toque2_ejercicio_diferente(self):
        """espalda: toque-1 en dia_2, toque-2 en dia_5."""
        t1 = self._toque1_nombres('espalda', 'dia_2')
        t2 = self._toque2_nombres('espalda', 'dia_5')
        self.assertTrue(
            bool(t2 - t1),
            f"espalda toque-2 {t2} no tiene ejercicio nuevo respecto a toque-1 {t1}",
        )

    def test_hombros_toque2_ejercicio_diferente(self):
        """hombros: toque-1 en dia_2, toque-2 en dia_5."""
        t1 = self._toque1_nombres('hombros', 'dia_2')
        t2 = self._toque2_nombres('hombros', 'dia_5')
        self.assertTrue(
            bool(t2 - t1),
            f"hombros toque-2 {t2} no tiene ejercicio nuevo respecto a toque-1 {t1}",
        )

    def test_gluteos_toque2_ejercicio_diferente(self):
        """
        glúteos: toque-1 en dia_1 (Hip Thrust + Abducción), toque-2 en dia_3.
        Toque 2 prioriza 'variantes_compartidas' (búlgara) → debería diferir.
        """
        t1 = self._toque1_nombres('gluteos', 'dia_1')
        t2 = self._toque2_nombres('gluteos', 'dia_3')
        self.assertTrue(
            bool(t2 - t1),
            f"glúteos toque-2 {t2} no tiene ejercicio nuevo respecto a toque-1 {t1}",
        )

    def test_cuadriceps_toque2_rep_range_mayor(self):
        """
        cuádriceps es grande: toque-1 usa '10-12', toque-2 debe usar '12-15'.
        dia_1=toque1, dia_4=toque2.
        """
        t2_ranges = self._rep_ranges.get('dia_4', {}).get('cuadriceps', [])
        self.assertTrue(
            all(r in ('12-15', '15-20') for r in t2_ranges),
            f"cuádriceps toque-2 debería tener rep_range '12-15' o '15-20', got {t2_ranges}",
        )

    def test_triceps_toque2_rep_range_mayor(self):
        """tríceps pequeño: toque-1 '12-15', toque-2 '15-20'. dia_1=toque1, dia_4=toque2."""
        t2_ranges = self._rep_ranges.get('dia_4', {}).get('triceps', [])
        self.assertTrue(
            all(r in ('15-20',) for r in t2_ranges),
            f"tríceps toque-2 debería tener rep_range '15-20', got {t2_ranges}",
        )

    def test_gemelos_toque2_rep_range_mayor(self):
        """gemelos pequeño: toque-1 '12-15', toque-2 '15-20'. dia_1=toque1, dia_4=toque2."""
        t2_ranges = self._rep_ranges.get('dia_4', {}).get('gemelos', [])
        self.assertTrue(
            all(r in ('15-20',) for r in t2_ranges),
            f"gemelos toque-2 debería tener rep_range '15-20', got {t2_ranges}",
        )

    def test_rpe_toque2_igual_o_menor_que_toque1(self):
        """
        El RPE de toque-2 debe ser ≤ RPE de toque-1 (suelo en 6).
        Bloque 0 rpe_objetivo=6; max(6, 6-1)=6. RPE no sube nunca.
        Verificamos con espalda (gran grupo, sin ajuste de músculo pequeño).
        """
        semana = self._semana
        rpe_dia2_espalda = [ej['rpe_objetivo'] for ej in semana.get('dia_2', [])
                             if ej['grupo_muscular'] == 'espalda']
        rpe_dia5_espalda = [ej['rpe_objetivo'] for ej in semana.get('dia_5', [])
                             if ej['grupo_muscular'] == 'espalda']
        for rpe_t1, rpe_t2 in zip(rpe_dia2_espalda, rpe_dia5_espalda):
            self.assertLessEqual(
                rpe_t2, rpe_t1,
                f"RPE toque-2 ({rpe_t2}) > RPE toque-1 ({rpe_t1}) — contraste roto",
            )

    def test_grupos_freq1_sin_variacion(self):
        """
        antebrazos, core, isquios, pecho, trapecios son freq=1 para David.
        Sus ejercicios NO deben cambiar (solo aparecen una vez → siempre toque-1).
        """
        nombres = self._nombres
        # antebrazos toque-1: dia_2
        self.assertIn('Aguante en Barra (Dead Hang)',
                      nombres.get('dia_2', {}).get('antebrazos', []))
        # core toque-1: dia_3
        self.assertIn('Crunch en Polea (Cable Crunch)',
                      nombres.get('dia_3', {}).get('core', []))
        # pecho toque-1: dia_4
        self.assertIn('Convergent Machine Press',
                      nombres.get('dia_4', {}).get('pecho', []))


# ---------------------------------------------------------------------------
# Test 3 — Glúteos + Búlgara (búsqueda de variante compartida)
# ---------------------------------------------------------------------------

class TestX14GluteosVarianteCompartida(TestCase):
    """
    glúteos tiene 'variantes_compartidas' con Sentadilla Búlgara (perfil='estirado').
    ROL_TOQUE[2]['orden_categoria'] prioriza variantes_compartidas para toque-2.
    Verifica que el toque 2 de glúteos incluye un ejercicio distinto al toque-1.
    """

    def setUp(self):
        _, self._planner = _build_planner(PERFIL_DAVID)
        self._semana = _semana_bloque0(self._planner)

    def test_gluteos_toque2_no_repite_toque1_completo(self):
        """
        dia_1 = toque-1 de glúteos: Hip Thrust + Abducción.
        dia_3 = toque-2 de glúteos: debe diferir en al menos un ejercicio.
        """
        nombres = _nombres_por_grupo_y_dia(self._semana)
        t1 = set(nombres.get('dia_1', {}).get('gluteos', []))
        t2 = set(nombres.get('dia_3', {}).get('gluteos', []))
        self.assertNotEqual(
            t1, t2,
            f"glúteos toque-2 {sorted(t2)} es idéntico al toque-1 {sorted(t1)} — variación intra-semanal no activada",
        )

    def test_gluteos_toque2_tiene_ejercicio_estiramiento(self):
        """
        El toque-2 prioriza perfil='estirado'. Al menos un ejercicio del pool
        con ese perfil debería aparecer (o el pool de variantes_compartidas).
        No forzamos el nombre exacto — verificamos que hay diferencia.
        """
        nombres = _nombres_por_grupo_y_dia(self._semana)
        t1 = set(nombres.get('dia_1', {}).get('gluteos', []))
        t2 = set(nombres.get('dia_3', {}).get('gluteos', []))
        nuevos = t2 - t1
        self.assertGreater(len(nuevos), 0,
                           f"glúteos toque-2 no tiene ningún ejercicio nuevo. t2={t2}, t1={t1}")


# ---------------------------------------------------------------------------
# Test 4 — Fallback frecuencia_map=None no activa variación
# ---------------------------------------------------------------------------

class TestX14FallbackSinVariacion(TestCase):
    """
    Cuando AsignacionImposibleError fuerza el fallback (DISTRIBUCION_DIAS),
    frecuencia_map=None y plan_variantes queda vacío — sin variación de toque.
    construir_variantes_por_toque NO debe ser llamado en ese path.
    """

    def test_construir_variantes_no_llamado_en_fallback(self):
        from analytics.planificador_helms.distribucion.asignador import AsignacionImposibleError

        _, planner = _build_planner(PERFIL_DAVID)

        with patch('analytics.planificador_helms.core.asignar_semana',
                   side_effect=AsignacionImposibleError("Test fallback X.14")):
            with patch('analytics.planificador_helms.core.construir_variantes_por_toque') as mock_cvt:
                semana = _semana_bloque0(planner)

        self.assertEqual(
            mock_cvt.call_count, 0,
            "construir_variantes_por_toque fue llamado a pesar de estar en fallback — bug en check frecuencia_map",
        )
        # El plan sigue siendo válido (no vacío)
        self.assertGreater(
            sum(len(ejs) for ejs in semana.values()), 0,
            "La semana está vacía en el fallback — algo más roto",
        )

    def test_fallback_genera_semana_valida_con_estructura_estatica(self):
        """Verifica que el plan resultante del fallback tiene el formato esperado."""
        from analytics.planificador_helms.distribucion.asignador import AsignacionImposibleError
        from analytics.planificador_helms.config import DISTRIBUCION_DIAS

        _, planner = _build_planner(PERFIL_DAVID)

        with patch('analytics.planificador_helms.core.asignar_semana',
                   side_effect=AsignacionImposibleError("Test fallback X.14")):
            semana = _semana_bloque0(planner)

        grupos_resultado = {
            dia: sorted({ej['grupo_muscular'] for ej in ejs})
            for dia, ejs in semana.items()
        }
        grupos_fallback = {
            dia: sorted(grupos)
            for dia, grupos in DISTRIBUCION_DIAS[5].items()
        }
        self.assertEqual(grupos_resultado, grupos_fallback)


# ---------------------------------------------------------------------------
# Test 5 — Determinismo tras X.14
# ---------------------------------------------------------------------------

class TestX14Determinismo(TestCase):
    """
    Misma entrada → misma salida, incluyendo los nuevos candidatos de toque-2.
    El pool de variantes es determinista porque el catálogo es estático.
    """

    def test_david_determinista_dos_ejecuciones(self):
        _, p1 = _build_planner(PERFIL_DAVID)
        _, p2 = _build_planner(PERFIL_DAVID)
        s1 = _semana_bloque0(p1)
        s2 = _semana_bloque0(p2)
        self.assertEqual(
            _estructura_dia(s1), _estructura_dia(s2),
            "Motor no determinista para David tras X.14",
        )

    def test_avanzado6d_determinista(self):
        _, p1 = _build_planner(PERFIL_AVANZADO_6D)
        _, p2 = _build_planner(PERFIL_AVANZADO_6D)
        s1 = _semana_bloque0(p1)
        s2 = _semana_bloque0(p2)
        self.assertEqual(
            _estructura_dia(s1), _estructura_dia(s2),
            "Motor no determinista para Avanzado 6d tras X.14",
        )

    def test_todos_los_perfiles_deterministas(self):
        perfiles = [
            {'id':  2, 'experiencia_años': 7,   'objetivo_principal': 'general',     'dias_disponibles': 5},
            {'id': 99, 'experiencia_años': 0.5, 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3},
            {'id': 97, 'experiencia_años': 5,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6},
        ]
        for pdata in perfiles:
            with self.subTest(id=pdata['id'], dias=pdata['dias_disponibles']):
                _, p1 = _build_planner(pdata)
                _, p2 = _build_planner(pdata)
                s1 = _semana_bloque0(p1)
                s2 = _semana_bloque0(p2)
                self.assertEqual(_estructura_dia(s1), _estructura_dia(s2))


# ---------------------------------------------------------------------------
# Test 6 — Avanzado 6d: biceps/core/trapecios toque-2
# ---------------------------------------------------------------------------

class TestX14Avanzado6dToque2(TestCase):
    """
    Avanzado 6d (id=97): biceps/core/trapecios en freq=2.
    Verifica que toque-2 difiere del toque-1 en al menos un ejercicio.
    """

    def setUp(self):
        _, self._planner = _build_planner(PERFIL_AVANZADO_6D)
        self._semana = _semana_bloque0(self._planner)
        self._nombres = _nombres_por_grupo_y_dia(self._semana)

    def test_biceps_toque2_diferente(self):
        """
        biceps toque-1 en dia_2, toque-2 en dia_6.
        """
        t1 = set(self._nombres.get('dia_2', {}).get('biceps', []))
        t2 = set(self._nombres.get('dia_6', {}).get('biceps', []))
        self.assertTrue(
            bool(t2) and t1 != t2,
            f"bíceps toque-2 {t2} es idéntico al toque-1 {t1} para Avanzado 6d",
        )

    def test_trapecios_toque2_diferente(self):
        """
        trapecios toque-1 en dia_3, toque-2 en dia_5.
        """
        t1 = set(self._nombres.get('dia_3', {}).get('trapecios', []))
        t2 = set(self._nombres.get('dia_5', {}).get('trapecios', []))
        self.assertTrue(
            bool(t2) and t1 != t2,
            f"trapecios toque-2 {t2} es idéntico al toque-1 {t1} para Avanzado 6d",
        )

    def test_core_toque2_diferente_o_rep_range_diferente(self):
        """
        core toque-1 en dia_3, toque-2 en dia_6.
        Si el pool de core tiene pocos ejercicios únicos, puede repetir el nombre
        pero el rep_range debería ser distinto (más alto en toque-2).
        Verificamos que al menos uno de los dos difiere.
        """
        t1_nombres = set(self._nombres.get('dia_3', {}).get('core', []))
        t2_nombres = set(self._nombres.get('dia_6', {}).get('core', []))

        rep_t1 = _rep_ranges_por_grupo_y_dia(self._semana).get('dia_3', {}).get('core', [])
        rep_t2 = _rep_ranges_por_grupo_y_dia(self._semana).get('dia_6', {}).get('core', [])

        ejercicios_difieren = t1_nombres != t2_nombres
        reps_difieren = rep_t1 != rep_t2
        self.assertTrue(
            ejercicios_difieren or reps_difieren,
            f"core toque-2 es byte-idéntico al toque-1 — nombres: {t2_nombres}, reps: {rep_t2}",
        )

    def test_grupos_freq1_sin_variacion_avanzado6d(self):
        """
        Los grupos freq=1 en avanzado 6d (cuadriceps, espalda, gemelos, etc.)
        no deben cambiar — solo tienen toque-1.
        """
        nombres = self._nombres
        # cuadriceps en dia_5 (toque-1, freq=1)
        cuad = nombres.get('dia_5', {}).get('cuadriceps', [])
        self.assertIn('Sentadilla Hack', cuad,
                      "cuádriceps (freq=1) cambió en avanzado 6d — invariante roto")
        # isquios en dia_3 (toque-1, freq=1)
        isq = nombres.get('dia_3', {}).get('isquios', [])
        self.assertIn('Peso Muerto Rumano', isq,
                      "isquios (freq=1) cambió en avanzado 6d — invariante roto")
