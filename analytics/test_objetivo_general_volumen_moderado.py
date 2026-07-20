# analytics/test_objetivo_general_volumen_moderado.py
"""
Objetivo 'general' pasa a representar una filosofía de volumen MODERADO
(anclado cerca del MEV — el mínimo científico efectivo, ni más ni menos),
en vez de caer en el multiplicador neutro 1.0x por defecto que empujaba
el volumen hacia el rango alto igual que 'fuerza_hipertrofia'.

Motivo (2026-07-20, sesión con el usuario): inspirado en una filosofía de
entrenamiento de "entrenar para la vida, no maximizar cada gramo de
músculo" — el usuario pidió volumen moderado para TODOS los grupos, sin
priorizar ninguno. La tentación era usar un número plano (6-9 series para
todos), pero eso haría caer a los grupos grandes por debajo de su propio
MEV (mínimo efectivo real, ~11-12 series/semana en avanzado) — el mismo
problema de infra-dosificación que arrancó toda esta fase con el glúteo.
En su lugar, 'general' ancla el volumen justo al MEV de cada grupo (con un
pequeño margen), dando números moderados pero nunca por debajo del suelo
científico.
"""

from django.test import TestCase

from analytics.planificador_helms.volumen.calculadora import (
    calcular_volumen_optimo,
    CalculadoraVolumen,
)


class TestObjetivoGeneralAncladoAMEV(TestCase):
    def test_general_no_cae_bajo_mev(self):
        """Para ningún grupo/nivel el resultado con objetivo='general' debe caer bajo su MEV."""
        grupos = [
            'pecho', 'espalda', 'hombros', 'biceps', 'triceps', 'cuadriceps',
            'isquios', 'gluteos', 'gemelos', 'core', 'trapecios', 'antebrazos',
        ]
        for nivel in ('principiante', 'intermedio', 'avanzado'):
            for grupo in grupos:
                with self.subTest(nivel=nivel, grupo=grupo):
                    vol = calcular_volumen_optimo(grupo, nivel, 'general', 1.0)
                    mev = CalculadoraVolumen.calcular_volumen_mantenimiento(grupo, nivel)
                    self.assertGreaterEqual(
                        vol, mev,
                        f"{grupo}/{nivel}: general dio {vol}, por debajo de su MEV={mev}"
                    )

    def test_general_da_volumen_moderado_no_maximo(self):
        """
        'general' debe dar bastante menos que 'hipertrofia' para el mismo
        grupo/nivel — es una filosofía de mantenimiento/moderación, no de
        maximizar crecimiento.
        """
        for grupo in ('pecho', 'espalda', 'cuadriceps', 'biceps'):
            with self.subTest(grupo=grupo):
                vol_general = calcular_volumen_optimo(grupo, 'avanzado', 'general', 1.0)
                vol_hipertrofia = calcular_volumen_optimo(grupo, 'avanzado', 'hipertrofia', 1.0)
                self.assertLess(
                    vol_general, vol_hipertrofia,
                    f"{grupo}: general ({vol_general}) debería ser menor que hipertrofia ({vol_hipertrofia})"
                )

    def test_pecho_avanzado_general_valor_esperado(self):
        """Caso concreto: pecho avanzado, general → cerca del MEV (11), con margen pequeño."""
        vol = calcular_volumen_optimo('pecho', 'avanzado', 'general', 1.0)
        mev = CalculadoraVolumen.calcular_volumen_mantenimiento('pecho', 'avanzado')
        self.assertEqual(mev, 11)
        self.assertEqual(vol, 12)

    def test_grupos_pequenos_general_en_rango_moderado(self):
        """
        Grupos pequeños con objetivo='general' deben caer en un rango
        moderado (~4-9 series), consistente con la filosofía de volumen
        conservador para músculos secundarios.
        """
        for grupo in ('biceps', 'triceps', 'trapecios', 'antebrazos'):
            with self.subTest(grupo=grupo):
                vol = calcular_volumen_optimo(grupo, 'avanzado', 'general', 1.0)
                self.assertLessEqual(vol, 9, f"{grupo}: {vol} series, se esperaba ≤9")
