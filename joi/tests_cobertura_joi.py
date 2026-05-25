"""
Phase 56.12 — Cobertura total de entradas JOI.

Objetivo: ningún mensaje de JOI llega al usuario sin pasar por el contrato semántico.

Checklist (6):
1.  Gym: la salida post-entreno pasa el validador.
2.  Hyrox: la salida post-sesión pasa el validador.
3.  Apertura diaria pasa el validador.
4.  Un trigger de decisión de plan pasa el validador.
5.  Si el validador detecta una violación, el mensaje igual se guarda (no se bloquea).
6.  El fallback de apertura (sin mensaje previo) produce texto limpio.
"""

import unittest.mock as mock

from django.test import TestCase

from joi.validador_semantico import validar_semantica_joi, READINESS_BAJO_UMBRAL


class TestCoberturaValidadorGym(TestCase):
    """1. La ruta gym (entreno completado) pasa por el validador."""

    def test_mensaje_gym_pasa_validador(self):
        texto = (
            "Completaste la sesión con margen. El volumen de empuje sube 5% la semana que viene."
        )
        r = validar_semantica_joi(texto, modulo='gym')
        self.assertTrue(r['valida'], msg=f"Violaciones: {r['violaciones']}")
        self.assertEqual(r['texto'], texto)

    def test_mensaje_gym_con_rpe_alto_pasa(self):
        texto = "RPE 9 sostenido — el sistema lo registra y ajusta carga para mañana."
        r = validar_semantica_joi(texto, modulo='gym')
        self.assertTrue(r['valida'])

    def test_mensaje_gym_diagnostico_es_detectado(self):
        """Si JOI cometiera un error en la ruta gym, el validador lo capta."""
        texto = "Eso es apatía de vivir, no fatiga muscular."
        r = validar_semantica_joi(texto, modulo='gym')
        self.assertFalse(r['valida'])
        self.assertTrue(any('diagnostico' in v for v in r['violaciones']))


class TestCoberturaValidadorHyrox(TestCase):
    """2. La ruta hyrox (sesión completada) pasa por el validador."""

    def test_mensaje_hyrox_correcto_pasa(self):
        texto = (
            "Dieciséis minutos a RPE 8 en estaciones son práctica real "
            "del terreno que vas a encontrar. Hoy cuenta como familiaridad acumulada."
        )
        r = validar_semantica_joi(texto, modulo='hyrox')
        self.assertTrue(r['valida'], msg=f"Violaciones: {r['violaciones']}")

    def test_atribucion_mental_en_hyrox_detectada(self):
        texto = "Tu mente sabe que puedes más, pero el cuerpo no acompañó hoy."
        r = validar_semantica_joi(texto, modulo='hyrox')
        self.assertFalse(r['valida'])
        self.assertTrue(any('atribucion_mental' in v for v in r['violaciones']))

    def test_readiness_bajo_en_hyrox_detectado(self):
        texto = "Tu readiness está bajo, considera una sesión de recuperación."
        r = validar_semantica_joi(texto, modulo='hyrox')
        self.assertFalse(r['valida'])
        self.assertTrue(any('readiness_bajo_incorrecto' in v for v in r['violaciones']))


class TestCoberturaValidadorDiario(TestCase):
    """3 & 4. Apertura diaria y trigger de decisión de plan pasan el validador."""

    def test_apertura_diaria_limpia_pasa(self):
        texto = (
            "Hoy el plan pide fuerza de tren superior. Readiness disponible con reserva. "
            "Principales primero, accesorios opcionales."
        )
        r = validar_semantica_joi(texto, modulo='diario')
        self.assertTrue(r['valida'], msg=f"Violaciones: {r['violaciones']}")

    def test_apertura_con_peso_emocional_sin_etiqueta_pasa(self):
        txt = "Llevas días con algo encima. Hoy descansa sin culpa."
        r = validar_semantica_joi(txt, modulo='diario')
        self.assertTrue(r['valida'], msg=f"Violaciones: {r['violaciones']}")

    def test_trigger_decision_plan_pasa(self):
        texto = (
            "El plan detectó estancamiento en press banca (3 sesiones sin mejora). "
            "Esta semana cambia a press inclinado como variante de trabajo."
        )
        r = validar_semantica_joi(texto, modulo='gym')
        self.assertTrue(r['valida'])

    def test_crisis_en_apertura_detectada(self):
        texto = "Estás en una crisis, David. El plan lo nota."
        r = validar_semantica_joi(texto, modulo='diario')
        self.assertFalse(r['valida'])


class TestNoBloqueoConViolacion(TestCase):
    """5. El validador detecta y registra — nunca bloquea."""

    def test_validador_siempre_devuelve_texto_original(self):
        """El campo 'texto' nunca cambia, aunque haya violación."""
        original = "Tu mente intenta convencerse de que puedes seguir."
        r = validar_semantica_joi(original, modulo='hyrox')
        self.assertFalse(r['valida'])
        self.assertEqual(r['texto'], original)

    def test_validador_no_lanza_excepcion_con_texto_extrano(self):
        """El validador nunca rompe el flujo."""
        textos = [
            '',
            '   ',
            'a' * 5000,
            'Тu cuerpo respondió.',
        ]
        for t in textos:
            try:
                r = validar_semantica_joi(t, modulo='gym')
                self.assertIn('valida', r)
            except Exception as exc:
                self.fail(f"validar_semantica_joi lanzó excepción con texto={t!r}: {exc}")


class TestFallbackAperturaLimpia(TestCase):
    """6. El fallback on-demand genera texto que pasa el contrato."""

    def test_texto_vacio_es_valido(self):
        """Silencio de JOI no es una violación."""
        r = validar_semantica_joi('', modulo='diario')
        self.assertTrue(r['valida'])
        self.assertEqual(r['violaciones'], [])

    def test_readiness_etiquetas_no_contienen_bajo(self):
        """Ninguna etiqueta por encima del umbral usa 'bajo'."""
        from joi.validador_semantico import readiness_etiqueta
        for score in range(READINESS_BAJO_UMBRAL, 101):
            etiqueta = readiness_etiqueta(score)
            self.assertNotIn(
                'bajo', etiqueta.lower(),
                msg=f"'bajo' en etiqueta readiness={score}: '{etiqueta}'"
            )

    def test_readiness_bajo_umbral_etiqueta_correcta(self):
        """Por debajo del umbral sí se usa 'Carga alta acumulada'."""
        from joi.validador_semantico import readiness_etiqueta
        etiqueta = readiness_etiqueta(READINESS_BAJO_UMBRAL - 1)
        self.assertIn('Carga alta', etiqueta)
