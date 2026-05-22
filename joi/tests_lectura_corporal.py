"""
Phase 56.8 — Tests de lectura corporal JOI post-entreno.

Contrato: Datos crudos → lectura corporal → orientación práctica → voz JOI.
JOI no debe narrar métricas. Debe traducirlas a sensación corporal y dirección práctica.

Regla de cierre: 'Si JOI no puede responder ¿qué hago?, falla.'
"""

from django.test import TestCase
from joi.services import _construir_lectura_corporal, _prompt_entreno_completado


class TestLecturaCorporal(TestCase):
    """Unit tests for _construir_lectura_corporal — structure before voice."""

    # ── 1. Estado corporal comprensible ──────────────────────────────────────

    def test_rpe_moderado_readiness_medio_da_disponible_con_reserva(self):
        """RPE 7 + readiness 67 → disponible_con_reserva, nunca 'fatigado' ni 'fresco'."""
        lectura = _construir_lectura_corporal(
            rpe=7, readiness=67, acwr=None, en_retorno=False, prs=[]
        )
        self.assertEqual(lectura['estado'], 'disponible_con_reserva',
            msg='RPE 7 + readiness medio = disponible_con_reserva, no porcentaje literal.')

    def test_readiness_no_se_interpreta_como_porcentaje_de_capacidad(self):
        """Readiness 67 NO genera estado 'fatigado' ni un porcentaje de capacidad."""
        lectura = _construir_lectura_corporal(
            rpe=7, readiness=67, acwr=None, en_retorno=False, prs=[]
        )
        self.assertNotIn(lectura['estado'], ('fatigado', 'cargado'),
            msg='Readiness 67 no debe leerse como fatiga — es disponibilidad media.')

    def test_retorno_lesion_da_en_recuperacion(self):
        """En fase de retorno → estado siempre en_recuperacion."""
        lectura = _construir_lectura_corporal(
            rpe=7, readiness=80, acwr=None, en_retorno=True, prs=[]
        )
        self.assertEqual(lectura['estado'], 'en_recuperacion')

    # ── 2. Dirección práctica siempre presente ───────────────────────────────

    def test_rpe_7_readiness_medio_da_mantener_sin_forzar_en_retorno(self):
        """RPE moderado + en retorno → dirección = mantener_sin_forzar."""
        lectura = _construir_lectura_corporal(
            rpe=7, readiness=67, acwr=None, en_retorno=True, prs=[]
        )
        self.assertEqual(lectura['direccion'], 'mantener_sin_forzar')

    def test_toda_lectura_tiene_direccion_definida(self):
        """Toda combinación de inputs produce una dirección del vocabulario controlado."""
        _DIRECCIONES_VALIDAS = {
            'apretar_un_poco', 'mantener', 'mantener_sin_forzar',
            'reducir', 'recuperar', 'observar'
        }
        casos = [
            dict(rpe=5, readiness=90, acwr=0.9, en_retorno=False, prs=[]),
            dict(rpe=9, readiness=45, acwr=1.5, en_retorno=False, prs=[]),
            dict(rpe=7, readiness=67, acwr=None, en_retorno=True, prs=[]),
            dict(rpe=None, readiness=None, acwr=None, en_retorno=False, prs=[]),
            dict(rpe=8, readiness=80, acwr=None, en_retorno=False, prs=['Sentadilla']),
        ]
        for caso in casos:
            lectura = _construir_lectura_corporal(**caso)
            self.assertIn(lectura['direccion'], _DIRECCIONES_VALIDAS,
                msg=f'Caso {caso} produjo dirección no válida: {lectura["direccion"]}')

    # ── 3. RPE 7 no genera épica ni alarma ───────────────────────────────────

    def test_rpe_7_no_genera_estado_fatigado_ni_cargado(self):
        """RPE 7 = moderado. No debe generar alarma."""
        lectura = _construir_lectura_corporal(
            rpe=7, readiness=75, acwr=1.0, en_retorno=False, prs=[]
        )
        self.assertNotIn(lectura['estado'], ('fatigado', 'cargado', 'alerta'))
        self.assertEqual(lectura['intensidad'], 'moderada')

    # ── 4. Lesión en retorno ≠ descanso obligatorio ───────────────────────────

    def test_retorno_lesion_no_da_recuperar_si_rpe_moderado(self):
        """Lesión en retorno + RPE moderado → mantener_sin_forzar, no 'recuperar'."""
        lectura = _construir_lectura_corporal(
            rpe=7, readiness=70, acwr=None, en_retorno=True, prs=[],
            lesion_zona='rodilla'
        )
        self.assertNotEqual(lectura['direccion'], 'recuperar',
            msg='Retorno de lesión con RPE moderado no equivale a descanso obligatorio.')
        self.assertEqual(lectura['direccion'], 'mantener_sin_forzar')

    def test_retorno_lesion_incluye_zona_en_vigilar(self):
        """Zona de lesión aparece en qué vigilar."""
        lectura = _construir_lectura_corporal(
            rpe=7, readiness=70, acwr=None, en_retorno=True, prs=[],
            lesion_zona='rodilla'
        )
        vigilar_texto = ' '.join(lectura['vigilar'])
        self.assertIn('rodilla', vigilar_texto)

    # ── 5. Sin datos suficientes → no inventa sensación ──────────────────────

    def test_sin_rpe_ni_readiness_no_genera_estado_especifico(self):
        """Sin datos → estado genérico, no invención."""
        lectura = _construir_lectura_corporal(
            rpe=None, readiness=None, acwr=None, en_retorno=False, prs=[]
        )
        self.assertEqual(lectura['intensidad'], 'desconocida')
        self.assertEqual(lectura['recuperacion'], 'sin_datos')

    # ── 6. Prompt post-entreno no contiene números crudos ────────────────────

    def test_prompt_no_contiene_numeros_de_rpe_ni_readiness(self):
        """El prompt que va al AI no debe incluir '67', '7', etc. como métricas crudas."""
        prompt = _prompt_entreno_completado(
            ctx={'readiness_hyrox': 67, 'acwr': 1.0, 'is_in_transition': True},
            datos_extra={'rpe': 7, 'prs': [], 'lesion_zona': 'rodilla'}
        )
        # Los números deben estar en la estructura interna (estados), no como métricas crudas
        self.assertNotIn('RPE 7', prompt)
        self.assertNotIn('readiness 67', prompt)
        self.assertNotIn('67%', prompt)

    def test_prompt_contiene_direccion_practica(self):
        """El prompt siempre incluye una de las 6 direcciones en lenguaje natural."""
        _TEXTOS_DIRECCION = [
            'forzar', 'ritmo', 'intensidad', 'volumen', 'recuper', 'observa'
        ]
        prompt = _prompt_entreno_completado(
            ctx={'readiness_hyrox': 67, 'acwr': None, 'is_in_transition': True},
            datos_extra={'rpe': 7, 'prs': [], 'lesion_zona': 'rodilla'}
        )
        tiene_direccion = any(kw in prompt.lower() for kw in _TEXTOS_DIRECCION)
        self.assertTrue(tiene_direccion,
            msg='El prompt debe contener una dirección práctica para el usuario.')
