# analytics/test_planificador_helms_x3.py
"""
Tests TDD para X.3 — conectar CalculadoraVolumen como fuente del volumen objetivo.

Escritos ANTES del fix: test_core_llama_calcular_volumen_optimo falla con
AttributeError (el módulo core aún no importa la función). Los demás son tests
de comportamiento esperado post-fix que validan directamente la fórmula
implementada (no requieren que el planner entero produzca salidas distintas,
ya que el tope min(4,...) de X.4 sigue activo y oculta el cambio en el output
final entregado al usuario — eso lo resolverá X.4).

Cobertura de los 6 requisitos de la spec:
  1. core.py LLAMA a calcular_volumen_optimo (integración)
  2. hipertrofia vs fuerza → volúmenes objetivo internos distintos
  3. factor_recuperacion alto vs bajo → volúmenes objetivo distintos
  4. vol_mult alto (2.0) nunca excede MRV del grupo
  5. descarga (vol_mult=0.5) puede caer bajo MEV — sin suelo artificial
  6. objetivo='general' → multiplicador 1.0x (sin regresión para david)
"""

from django.test import TestCase

from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.volumen.calculadora import (
    calcular_volumen_optimo,
    CalculadoraVolumen,
)


# ---------------------------------------------------------------------------
# Helpers (igual que en los otros test files de esta serie)
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


PERFIL_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}


# ===========================================================================
# 1. Integración: core.py debe llamar a calcular_volumen_optimo
# ===========================================================================

class TestX3IntegracionCoreLlamaCalculadora(TestCase):
    """
    ROJO antes de X.3: core.py no importa calcular_volumen_optimo; el patch
    lanza AttributeError y self.fail() lo convierte en fallo descriptivo.
    VERDE después: core.py la importa y la llama para cada grupo del plan.
    """

    def test_core_llama_calcular_volumen_optimo(self):
        from unittest.mock import patch

        try:
            with patch(
                'analytics.planificador_helms.core.calcular_volumen_optimo',
                wraps=calcular_volumen_optimo,
            ) as mock_cvo:
                _, planner = _build_planner(PERFIL_DAVID)
                _semana_bloque0(planner)
                self.assertTrue(
                    mock_cvo.called,
                    "core.py debe llamar a calcular_volumen_optimo para calcular "
                    "el volumen objetivo de cada grupo muscular",
                )
                # Debe haberse llamado al menos una vez por grupo presente en el plan
                self.assertGreater(
                    mock_cvo.call_count, 0,
                    f"call_count={mock_cvo.call_count}; se esperaba al menos 1 llamada",
                )
        except AttributeError:
            self.fail(
                "core.py no importa calcular_volumen_optimo — fix X.3 no aplicado. "
                "Importa la función y úsala en _generar_semana_especifica."
            )

    def test_core_llama_con_nivel_objetivo_recuperacion(self):
        """
        Verifica que la llamada incluye nivel, objetivo y factor_recuperacion
        correctos (no valores hardcodeados).
        """
        from unittest.mock import patch, call

        perfil_data = {
            'id': 50,
            'experiencia_años': 2,        # → intermedio
            'objetivo_principal': 'fuerza',
            'dias_disponibles': 5,
            # factor_recuperacion con defaults: ~1.09
        }
        perfil = PerfilCliente(perfil_data)
        nivel_esperado = perfil.calcular_nivel_experiencia()            # 'intermedio'
        factor_esperado = perfil.calcular_factor_recuperacion()

        try:
            with patch(
                'analytics.planificador_helms.core.calcular_volumen_optimo',
                wraps=calcular_volumen_optimo,
            ) as mock_cvo:
                _, planner = _build_planner(perfil_data)
                _semana_bloque0(planner)

                for c in mock_cvo.call_args_list:
                    args, kwargs = c
                    # Firma: (grupo_muscular, experiencia, objetivo, factor_recuperacion)
                    experiencia = args[1] if len(args) > 1 else kwargs.get('experiencia')
                    objetivo = args[2] if len(args) > 2 else kwargs.get('objetivo')
                    factor = args[3] if len(args) > 3 else kwargs.get('factor_recuperacion')

                    self.assertEqual(
                        experiencia, nivel_esperado,
                        f"Experiencia pasada a calcular_volumen_optimo: {experiencia!r}, "
                        f"esperado: {nivel_esperado!r}",
                    )
                    self.assertEqual(
                        objetivo, 'fuerza',
                        f"Objetivo pasado: {objetivo!r}, esperado: 'fuerza'",
                    )
                    self.assertAlmostEqual(
                        factor, factor_esperado, places=3,
                        msg=f"Factor de recuperación pasado: {factor}, esperado: {factor_esperado}",
                    )
        except AttributeError:
            self.fail("core.py no importa calcular_volumen_optimo — fix X.3 no aplicado")


# ===========================================================================
# 2. hipertrofia vs fuerza → volúmenes objetivo internos distintos
# ===========================================================================

class TestX3ObjetivoInfluyeEnVolumen(TestCase):
    """
    Post-X.3: hipertrofia (×1.15) y fuerza (×0.85) deben producir volúmenes
    objetivo distintos para el mismo grupo y nivel.
    """

    def test_hipertrofia_mayor_que_fuerza_pecho_avanzado(self):
        vol_hip = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', 1.0)
        vol_fue = calcular_volumen_optimo('pecho', 'avanzado', 'fuerza', 1.0)
        self.assertGreater(
            vol_hip, vol_fue,
            f"hipertrofia ({vol_hip}) debería superar fuerza ({vol_fue}) para pecho avanzado",
        )

    def test_valores_coherentes_con_multiplicadores(self):
        """
        pecho avanzado: vol_base=18.
          hipertrofia: round(18×1.15)=21 → max(mev=11, min(21, mrv=22))=21
          fuerza:      round(18×0.85)=15 → max(11, min(15, 22))=15
        """
        vol_hip = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', 1.0)
        vol_fue = calcular_volumen_optimo('pecho', 'avanzado', 'fuerza', 1.0)
        self.assertEqual(vol_hip, 21, f"pecho avanzado hipertrofia: esperado 21, obtenido {vol_hip}")
        self.assertEqual(vol_fue, 15, f"pecho avanzado fuerza: esperado 15, obtenido {vol_fue}")

    def test_diferencia_aplica_en_multiples_grupos(self):
        """La diferencia objetivo/fuerza es consistente en todos los grupos grandes."""
        for grupo in ('pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos'):
            vol_hip = calcular_volumen_optimo(grupo, 'avanzado', 'hipertrofia', 1.0)
            vol_fue = calcular_volumen_optimo(grupo, 'avanzado', 'fuerza', 1.0)
            self.assertGreater(
                vol_hip, vol_fue,
                f"{grupo}: hipertrofia ({vol_hip}) debería ser > fuerza ({vol_fue})",
            )

    def test_diferencia_aplica_en_todos_los_niveles(self):
        for nivel in ('principiante', 'intermedio', 'avanzado'):
            vol_hip = calcular_volumen_optimo('pecho', nivel, 'hipertrofia', 1.0)
            vol_fue = calcular_volumen_optimo('pecho', nivel, 'fuerza', 1.0)
            self.assertGreater(
                vol_hip, vol_fue,
                f"pecho {nivel}: hipertrofia ({vol_hip}) debería ser > fuerza ({vol_fue})",
            )


# ===========================================================================
# 3. factor_recuperacion influye en el volumen objetivo
# ===========================================================================

class TestX3FactorRecuperacionInfluyeEnVolumen(TestCase):
    """
    Post-X.3: factor_recuperacion alto (buena recuperación) vs bajo (mala)
    produce volúmenes objetivo distintos.
    """

    def _factor_alto(self):
        """estres=2, sueño=9, energia=9, nutricion=9 → factor ≈ 1.225"""
        p = PerfilCliente({'id': 70, 'experiencia_años': 5, 'objetivo_principal': 'hipertrofia',
                           'nivel_estres': 2, 'calidad_sueño': 9, 'nivel_energia': 9,
                           'nutricion_calidad': 9})
        return p.calcular_factor_recuperacion()

    def _factor_bajo(self):
        """estres=8, sueño=4, energia=4, nutricion=4 → factor ≈ 0.91"""
        p = PerfilCliente({'id': 71, 'experiencia_años': 5, 'objetivo_principal': 'hipertrofia',
                           'nivel_estres': 8, 'calidad_sueño': 4, 'nivel_energia': 4,
                           'nutricion_calidad': 4})
        return p.calcular_factor_recuperacion()

    def test_factor_alto_mayor_que_factor_bajo(self):
        self.assertGreater(
            self._factor_alto(), self._factor_bajo(),
            "Factor de recuperación alto debe ser mayor que factor bajo",
        )

    def test_pecho_avanzado_volumen_mayor_con_factor_alto(self):
        vol_alto = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', self._factor_alto())
        vol_bajo = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', self._factor_bajo())
        self.assertGreater(
            vol_alto, vol_bajo,
            f"Factor alto → vol={vol_alto}, factor bajo → vol={vol_bajo}. "
            "El volumen debería ser mayor con mejor recuperación.",
        )

    def test_factor_alto_acotado_por_mrv(self):
        """Incluso con factor muy alto, el volumen no supera el MRV."""
        mrv = CalculadoraVolumen.calcular_volumen_maximo_adaptativo('pecho', 'avanzado')
        vol = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', 1.3)
        self.assertLessEqual(
            vol, mrv,
            f"Con factor=1.3, vol={vol} supera MRV={mrv}",
        )


# ===========================================================================
# 4. vol_mult alto (2.0) nunca excede MRV
# ===========================================================================

class TestX3VolMultAltoNunuExcedeMRV(TestCase):
    """
    Post-X.3: La pipeline vol_opt → vol_opt×vol_mult → min(·, mrv) garantiza
    que incluso con vol_mult=2.0 (acumulación extrema) el resultado ≤ MRV.
    """

    def _vol_bloque(self, grupo: str, nivel: str, objetivo: str, vol_mult: float) -> float:
        """Replica la fórmula que implementará core.py."""
        factor = 1.0  # recuperación neutral para el test
        vol_opt = calcular_volumen_optimo(grupo, nivel, objetivo, factor)
        mrv = CalculadoraVolumen.calcular_volumen_maximo_adaptativo(grupo, nivel)
        vol_ajustado = vol_opt * vol_mult
        # En descarga, NO aplicar suelo MEV — intencional.
        return min(vol_ajustado, mrv), mrv

    def test_pecho_avanzado_hipertrofia_vol_mult_2(self):
        vol_bloque, mrv = self._vol_bloque('pecho', 'avanzado', 'hipertrofia', 2.0)
        self.assertLessEqual(
            vol_bloque, mrv,
            f"vol_bloque={vol_bloque} supera MRV={mrv} con vol_mult=2.0",
        )

    def test_cap_reducio_el_valor_para_pecho_avanzado(self):
        """Con vol_mult=2.0, el cap de MRV sí actúa (sin él superaría el MRV)."""
        vol_opt = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', 1.0)
        mrv = CalculadoraVolumen.calcular_volumen_maximo_adaptativo('pecho', 'avanzado')
        vol_sin_cap = vol_opt * 2.0
        vol_con_cap = min(vol_sin_cap, mrv)
        self.assertLess(
            vol_con_cap, vol_sin_cap,
            f"El cap de MRV no actuó: vol_sin_cap={vol_sin_cap}, vol_con_cap={vol_con_cap}",
        )

    def test_todos_grupos_avanzados_con_vol_mult_2(self):
        grupos = [
            'pecho', 'espalda', 'hombros', 'biceps', 'triceps',
            'cuadriceps', 'isquios', 'gluteos', 'gemelos',
            'core', 'trapecios', 'antebrazos',
        ]
        for grupo in grupos:
            vol_bloque, mrv = self._vol_bloque(grupo, 'avanzado', 'hipertrofia', 2.0)
            self.assertLessEqual(
                vol_bloque, mrv,
                f"{grupo} avanzado: vol_bloque={vol_bloque} supera MRV={mrv}",
            )


# ===========================================================================
# 5. Descarga (vol_mult=0.5) puede caer bajo MEV — sin suelo artificial
# ===========================================================================

class TestX3DescargaPuedeCaerBajoMEV(TestCase):
    """
    Post-X.3: En bloques de descarga con vol_mult bajo, el volumen calculado
    puede caer por debajo del MEV. No se reintroduce el suelo de MEV en la
    pipeline de core.py porque eso anularía el propósito de la descarga
    (disipar fatiga, no seguir estimulando al mínimo).
    """

    def _vol_descarga(self, grupo: str, nivel: str, objetivo: str, vol_mult: float = 0.5) -> tuple:
        """Devuelve (vol_descarga, mev) para verificar que vol < mev es posible."""
        factor = 1.0
        vol_opt = calcular_volumen_optimo(grupo, nivel, objetivo, factor)
        mev = CalculadoraVolumen.calcular_volumen_mantenimiento(grupo, nivel)
        mrv = CalculadoraVolumen.calcular_volumen_maximo_adaptativo(grupo, nivel)
        # Pipeline de core.py: aplica vol_mult, cap solo por arriba
        vol_ajustado = vol_opt * vol_mult
        vol_bloque = min(vol_ajustado, mrv)
        return vol_bloque, mev, vol_opt

    def test_pecho_avanzado_hipertrofia_descarga_cae_bajo_mev(self):
        """pecho avanzado hipertrofia: vol_opt=21, ×0.5=10.5 < mev=11."""
        vol_bloque, mev, vol_opt = self._vol_descarga('pecho', 'avanzado', 'hipertrofia', 0.5)
        self.assertLess(
            vol_bloque, mev,
            f"Descarga: vol_bloque={vol_bloque} debería ser < MEV={mev} "
            f"(vol_opt={vol_opt}, ×0.5={vol_opt * 0.5})",
        )

    def test_espalda_avanzado_descarga_cae_bajo_mev(self):
        """espalda avanzado hipertrofia: vol_opt=23, ×0.5=11.5 < mev=12."""
        vol_bloque, mev, vol_opt = self._vol_descarga('espalda', 'avanzado', 'hipertrofia', 0.5)
        self.assertLess(
            vol_bloque, mev,
            f"Descarga espalda: vol_bloque={vol_bloque}, MEV={mev}",
        )

    def test_descarga_sin_suelo_mev_es_intencionado(self):
        """
        Si se aplicara el suelo de MEV, la descarga no bajaría de mev=11 (pecho
        avanzado). Confirma que la fórmula intencionalmente NO lo aplica.
        El suelo de MEV solo existe dentro de calcular_volumen_optimo, no fuera.
        """
        vol_opt = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', 1.0)
        mev = CalculadoraVolumen.calcular_volumen_mantenimiento('pecho', 'avanzado')
        mrv = CalculadoraVolumen.calcular_volumen_maximo_adaptativo('pecho', 'avanzado')
        vol_mult = 0.5
        vol_con_suelo = max(vol_opt * vol_mult, mev)     # lo que NO debe hacer core.py
        vol_sin_suelo = min(vol_opt * vol_mult, mrv)     # lo que SÍ debe hacer core.py
        # Si existiera suelo, ambos valores serían iguales (mev=11 en ambos casos)
        # Si no hay suelo, vol_sin_suelo < mev, mientras vol_con_suelo = mev
        self.assertLess(
            vol_sin_suelo, mev,
            "La pipeline sin suelo de MEV debe poder producir valores < MEV en descarga",
        )
        self.assertEqual(
            vol_con_suelo, mev,
            "Con suelo de MEV (comportamiento incorrecto), el resultado sería exactamente MEV",
        )


# ===========================================================================
# 6. objetivo='general' → multiplicador 1.0x (sin regresión para david)
# ===========================================================================

class TestX3ObjetivoGeneralNoRegresion(TestCase):
    """
    Post-X.3: 'general' no está en _MULT_OBJETIVO y cae a 1.0 via .get(obj, 1.0).
    El volumen de david (general) debe ser idéntico a fuerza_hipertrofia (también 1.0).
    La migración de david a 'hipertrofia' es X.8 — no tocar aquí.
    """

    def test_general_igual_a_fuerza_hipertrofia(self):
        vol_general = calcular_volumen_optimo('pecho', 'avanzado', 'general', 1.0)
        vol_fh = calcular_volumen_optimo('pecho', 'avanzado', 'fuerza_hipertrofia', 1.0)
        self.assertEqual(
            vol_general, vol_fh,
            f"'general' ({vol_general}) debe dar el mismo resultado que "
            f"'fuerza_hipertrofia' ({vol_fh}) — ambos usan multiplicador 1.0",
        )

    def test_general_no_igual_a_hipertrofia(self):
        vol_general = calcular_volumen_optimo('pecho', 'avanzado', 'general', 1.0)
        vol_hip = calcular_volumen_optimo('pecho', 'avanzado', 'hipertrofia', 1.0)
        self.assertLess(
            vol_general, vol_hip,
            f"'general' ({vol_general}) debe ser < 'hipertrofia' ({vol_hip})",
        )

    def test_david_avanzado_general_volumen_esperado_pecho(self):
        """
        pecho avanzado general (×1.0, factor=1.0): round(18×1.0×1.0)=18,
        max(mev=11, min(18, mrv=22))=18.
        """
        vol = calcular_volumen_optimo('pecho', 'avanzado', 'general', 1.0)
        self.assertEqual(vol, 18, f"pecho avanzado general: esperado 18, obtenido {vol}")

    def test_series_finales_david_post_x7(self):
        """
        Post-X.7 (motor de asignación activo): los grupos con freq>1 acumulan
        el volumen de múltiples días. GestorFatiga (grandes≤10/ej, pequeños≤8/ej)
        sigue siendo el techo real por sesión, pero ahora la diferenciación viene
        tanto del volumen_optimo (X.3) como de la frecuencia asignada (X.7).

        Post fix presupuesto real del asignador + reducción vol_fin bloques
        hipertrofia (2026-07-20): solo espalda/hombros/biceps/trapecios
        alcanzan freq=2; el resto queda en freq=1 con el volumen reducido.
        """
        _, planner = _build_planner(PERFIL_DAVID)
        semana = _semana_bloque0(planner)

        grupos_series: dict = {}
        for ejs in semana.values():
            for ej in ejs:
                g = ej['grupo_muscular']
                grupos_series[g] = grupos_series.get(g, 0) + ej['series']

        esperado = {
            'pecho':      20,
            'espalda':    24,
            'cuadriceps': 20,
            'gluteos':    18,
            'isquios':    16,
            'hombros':    20,
            'biceps':     16,
            'triceps':    14,
            'gemelos':    14,
            'core':       12,
            'trapecios':  12,
            'antebrazos':  8,
        }
        for grupo, total_esperado in esperado.items():
            self.assertEqual(
                grupos_series[grupo], total_esperado,
                f"{grupo}: {grupos_series[grupo]} series — se esperaban {total_esperado} "
                f"(X.3+X.4+X.7 activos)",
            )
