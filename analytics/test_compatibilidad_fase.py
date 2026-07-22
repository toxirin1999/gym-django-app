"""
Phase Gym Peso 2 — Tests unitarios del módulo central de compatibilidad de fase.

resolver_peso_objetivo() es la única función que decide si el peso de hoy
debe recalcularse desde e1RM (bucket incompatible o descarga) o si el
caller debe seguir su propio camino de incremento fijo (bucket compatible).

Phase Gym Peso 2.2 — X.0: resolver_ancla_historica()
Helper puro que suaviza la ancla de e1RM ponderando las sesiones recientes
dentro de una ventana de 42 días. Sin acceso a BD; el caller filtra por bucket.
"""

from datetime import date, timedelta

from django.test import SimpleTestCase

from analytics.planificador_helms.calculo.compatibilidad_fase import (
    resolver_ancla_historica, resolver_peso_objetivo, son_rangos_compatibles,
)


class TestSonRangosCompatibles(SimpleTestCase):

    def test_sin_reps_anteriores_no_es_compatible(self):
        self.assertFalse(son_rangos_compatibles(None, '8-12'))

    def test_potencia_3_reps_vs_descarga_10_reps_incompatible(self):
        self.assertFalse(son_rangos_compatibles(3, '10-15'))

    def test_potencia_3_reps_vs_fuerza_5_reps_compatible(self):
        self.assertTrue(son_rangos_compatibles(3, '4-6'))

    def test_hipertrofia_12_reps_vs_potencia_3_reps_incompatible(self):
        self.assertFalse(son_rangos_compatibles(12, '2-4'))

    def test_hipertrofia_10_reps_vs_hipertrofia_metabolica_12_reps_compatible(self):
        self.assertTrue(son_rangos_compatibles(10, '12-15'))


class TestResolverPesoObjetivo(SimpleTestCase):

    def test_caso_a_sin_historial_no_aplica(self):
        r = resolver_peso_objetivo(
            peso_anterior=None, reps_anteriores=None, rpe_anterior=None,
            rep_range_hoy='8-12', rpe_objetivo_hoy=8,
        )
        self.assertFalse(r['aplica'])
        self.assertIsNone(r['peso'])

    def test_caso_b_bucket_compatible_no_aplica(self):
        """Fuerza 5 reps RPE8 → hoy potencia 3-5 reps: misma familia, no recalcula."""
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8,
            rep_range_hoy='3-5', rpe_objetivo_hoy=8,
        )
        self.assertFalse(r['aplica'])

    def test_caso_c_bucket_incompatible_recalcula(self):
        """107.5kg x 3 reps RPE8 (potencia) → hoy 10-15 reps (descarga/hipertrofia)."""
        r = resolver_peso_objetivo(
            peso_anterior=107.5, reps_anteriores=3, rpe_anterior=8,
            rep_range_hoy='10-15', rpe_objetivo_hoy=6, es_descarga_hoy=True,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_descarga')
        # Debe ser sustancialmente menor que peso_anterior - incremento_fijo (105kg)
        self.assertLess(r['peso'], 90.0)
        self.assertGreater(r['peso'], 0)

    def test_caso_d_descarga_reduce_peso_incluso_con_bucket_compatible(self):
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=12, rpe_anterior=8,
            rep_range_hoy='10-15', rpe_objetivo_hoy=6, es_descarga_hoy=True,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_descarga')
        self.assertLess(r['peso'], 100.0)


# ── Phase Gym Peso 2.2 — X.0 ─────────────────────────────────────────────────

class TestResolverAnclaHistorica(SimpleTestCase):
    """
    Helper puro: promedios ponderados de e1RM sobre sesiones recientes.
    Invariante de seguridad: con N=1 el resultado es idéntico a la sesión
    de entrada (sin suavizado efectivo).

    Inputs: dicts con claves peso, reps, rpe, fecha (date). Lista ordenada
    más reciente primero. Ya filtrada por bucket por el caller.
    """

    _AHORA = date(2026, 7, 21)

    def _s(self, peso, reps=5, rpe=8.0, dias_atras=10):
        return {
            'peso': peso,
            'reps': reps,
            'rpe': rpe,
            'fecha': self._AHORA - timedelta(days=dias_atras),
        }

    def test_lista_vacia_devuelve_none(self):
        self.assertIsNone(resolver_ancla_historica([]))

    def test_n1_propiedad_de_seguridad_peso_identico(self):
        # Con N=1 la inversa de Epley+RIR debe recuperar el peso original.
        # peso=90, reps=5, rpe=8 → e1RM=90*(1+7/30)=111.0 (exacto); inversa=90.0
        r = resolver_ancla_historica([self._s(90.0)], ahora=self._AHORA)
        self.assertAlmostEqual(r['peso'], 90.0, delta=0.01)
        self.assertEqual(r['reps'], 5)
        self.assertAlmostEqual(r['rpe'], 8.0, delta=0.01)

    def test_n2_pesos_renormalizados_625_375(self):
        # [0.5, 0.3] → renormalizados [0.625, 0.375]
        # mismo reps/rpe → peso_suave = media ponderada de pesos
        # 0.625*90 + 0.375*60 = 56.25 + 22.5 = 78.75
        s1 = self._s(90.0, dias_atras=5)
        s2 = self._s(60.0, dias_atras=15)
        r = resolver_ancla_historica([s1, s2], ahora=self._AHORA)
        self.assertAlmostEqual(r['peso'], 78.75, delta=0.5)

    def test_n3_pesos_050_030_020_sin_renormalizar(self):
        # [0.5, 0.3, 0.2] suman 1.0; no se renormalizan
        # 0.5*90 + 0.3*60 + 0.2*30 = 45 + 18 + 6 = 69.0
        s1 = self._s(90.0, dias_atras=5)
        s2 = self._s(60.0, dias_atras=15)
        s3 = self._s(30.0, dias_atras=25)
        r = resolver_ancla_historica([s1, s2, s3], ahora=self._AHORA)
        self.assertAlmostEqual(r['peso'], 69.0, delta=0.5)

    def test_n4_solo_usa_tres_primeras_ignora_resto(self):
        # La 4ª sesión (peso=1.0) no debe influir en el resultado
        s1 = self._s(90.0, dias_atras=5)
        s2 = self._s(60.0, dias_atras=15)
        s3 = self._s(30.0, dias_atras=25)
        s4 = self._s(1.0, dias_atras=35)
        r = resolver_ancla_historica([s1, s2, s3, s4], ahora=self._AHORA)
        self.assertAlmostEqual(r['peso'], 69.0, delta=0.5)

    def test_ventana_excluye_sesion_antigua(self):
        # Sesión a 50 días queda fuera de VENTANA_ANCLA_DIAS=42
        dentro = self._s(90.0, dias_atras=30)
        fuera = self._s(20.0, dias_atras=50)
        r = resolver_ancla_historica([dentro, fuera], ahora=self._AHORA)
        # Solo "dentro" contribuye; resultado ~ N=1 con peso=90
        self.assertAlmostEqual(r['peso'], 90.0, delta=0.5)

    def test_ventana_fallback_todas_excluidas_usa_mas_reciente(self):
        # Si todas superan 42 días, se usa la primera (más reciente)
        s1 = self._s(90.0, dias_atras=50)
        s2 = self._s(20.0, dias_atras=60)
        r = resolver_ancla_historica([s1, s2], ahora=self._AHORA)
        # Fallback a s1 (más reciente); resultado ~ N=1 con peso=90
        self.assertAlmostEqual(r['peso'], 90.0, delta=0.5)

    def test_no_crashea_con_enteros_devuelve_float(self):
        # El helper acepta ints en peso/rpe y devuelve float en 'peso'
        s = {'peso': 80, 'reps': 5, 'rpe': 8, 'fecha': self._AHORA - timedelta(days=5)}
        r = resolver_ancla_historica([s], ahora=self._AHORA)
        self.assertIsNotNone(r)
        self.assertIsInstance(r['peso'], float)


# ── Phase Gym Peso 2.2 — X.1 ─────────────────────────────────────────────────

class TestResolverPesoObjetivoX1GuardAlto(SimpleTestCase):
    """
    Guard de reps altas (>= UMBRAL_REPS_ALTO = 15).

    Cuando el rango OBJETIVO tiene >= 15 reps, Brzycki directo es poco fiable
    (tiende a infraestimar la carga real en ese tramo). En su lugar se proyecta
    a un equivalente-10RM fiable y se aplica un step-down plano del 17.5%.
    El derate por RPE objetivo NO se aplica en este camino: el step-down es
    la prescripción completa.
    """

    def test_guard_activo_ancla_fuerza_calculo_exacto(self):
        """
        Ancla FUERZA (100 kg x5 RPE8), objetivo '15-20' RPE8.

        e1RM = 100 * (1 + 7/30) = 123.33
        factor_10rm = 1.0278 - 0.0278*10 = 0.7498
        peso_10rm = 123.33 * 0.7498 = 92.48
        peso_calc = 92.48 * 0.825 = 76.29 → 77.5 (múltiplo de 2.5)
        """
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0,
            rep_range_hoy='15-20', rpe_objetivo_hoy=8,
        )
        self.assertTrue(r['aplica'])
        self.assertAlmostEqual(r['peso'], 77.5, delta=0.1)
        self.assertEqual(r['motivo_tipo'], 'recalculado_alto')

    def test_guard_da_mayor_que_brzycki_directo_18_reps(self):
        """
        El guard corrige la infraestimación de Brzycki en reps altas.

        Brzycki directo a 18 reps con RPE8 sobre la misma ancla:
            e1RM=123.33, factor=0.5274, peso_rpe10=65.04, derate=0.06 → ≈60.0

        El guard da ≈77.5, que es MAYOR. Esto muestra que el camino normal
        sub-prescribiría en este tramo y el guard corrige hacia arriba.
        """
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0,
            rep_range_hoy='15-20', rpe_objetivo_hoy=8,
        )
        brzycki_18_directo = 60.0  # calculado a mano (ver docstring)
        self.assertGreater(r['peso'], brzycki_18_directo)

    def test_guard_activo_ancla_hipertrofia_ortogonal_al_bucket_origen(self):
        """
        El guard solo mira el rango OBJETIVO, no el bucket de origen.

        Ancla HIPERTROFIA (60 kg x10 RPE7) + es_descarga_hoy=True → objetivo '15-20' RPE6.
        Los buckets son compatibles (hipertrofia→hipertrofia) pero es_descarga=True
        fuerza el recálculo (Caso D). Una vez dentro del cálculo, reps_obj=15 >= 15 →
        el guard actúa igual que con ancla fuerza.

        e1RM = 60*(1+13/30) = 86.0
        peso_10rm = 86.0 * 0.7498 = 64.48
        peso_calc = 64.48 * 0.825 = 53.20 → 52.5
        (El guard NO aplica derate por RPE objetivo; el step-down plano es la prescripción.)
        """
        r = resolver_peso_objetivo(
            peso_anterior=60.0, reps_anteriores=10, rpe_anterior=7.0,
            rep_range_hoy='15-20', rpe_objetivo_hoy=6,
            es_descarga_hoy=True,
        )
        self.assertTrue(r['aplica'])
        self.assertAlmostEqual(r['peso'], 52.5, delta=0.1)
        self.assertEqual(r['motivo_tipo'], 'recalculado_alto')

    def test_frontera_12_reps_no_activa_guard_usa_brzycki_normal(self):
        """
        '12-15' → primer_numero=12 < UMBRAL_REPS_ALTO=15 → camino normal.

        Ancla FUERZA (100, 5, 8) vs objetivo '12-15' (bucket HIPERTROFIA):
        incompatible → recalcula, pero por el camino Brzycki directo.
        motivo_tipo debe ser 'recalculado_fase', no 'recalculado_alto'.
        """
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0,
            rep_range_hoy='12-15', rpe_objetivo_hoy=8,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_fase')
        # El peso por Brzycki a 12 reps RPE8 es ≈80.0 (muy diferente de 77.5 del guard)
        self.assertAlmostEqual(r['peso'], 80.0, delta=0.1)

    def test_frontera_15_reps_activa_guard_limite_inclusivo(self):
        """
        '15-20' → primer_numero=15, ==UMBRAL_REPS_ALTO → entra al guard (>=, no >).
        """
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0,
            rep_range_hoy='15-20', rpe_objetivo_hoy=8,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_alto')

    def test_caso_b_bucket_compatible_range_alto_aplica_false(self):
        """
        Bucket compatible (hipertrofia → hipertrofia 15-20), sin descarga:
        aplica=False aunque el rango de hoy sea >= 15. La rama temprana de
        compatibilidad actúa antes de que se llegue a calcular reps_objetivo_hoy.
        """
        r = resolver_peso_objetivo(
            peso_anterior=60.0, reps_anteriores=12, rpe_anterior=8.0,
            rep_range_hoy='15-20', rpe_objetivo_hoy=8,
        )
        self.assertFalse(r['aplica'])
        self.assertIsNone(r['peso'])
        self.assertIsNone(r['motivo_tipo'])

    def test_descarga_y_rango_alto_motivo_es_recalculado_alto(self):
        """
        Cuando es_descarga_hoy=True Y reps >= UMBRAL_REPS_ALTO, el rango alto
        tiene prioridad sobre el motivo normal de descarga: motivo='recalculado_alto'.
        El rango es la razón de que se use una fórmula especial; la descarga
        ya estaba cubierta por el camino normal de todas formas.
        """
        r = resolver_peso_objetivo(
            peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0,
            rep_range_hoy='15-20', rpe_objetivo_hoy=6,
            es_descarga_hoy=True,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_alto')
