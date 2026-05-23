"""
Phase Diario 1.3 — Tests de intensidad contextual de la pregunta JOI.
"""
from django.test import TestCase
from diario.services.intensidad_apertura import calcular_intensidad_pregunta_apertura
from joi.services import _PREGUNTAS_SUAVES


class TestIntensidadApertura(TestCase):

    def _ctx(self, **kwargs) -> dict:
        base = {
            'hay_datos_suficientes': True,
            'energia_baja': False,
            'sueno_bajo': False,
            'molestia_zona': False,
            'patron_reciente_detectado': False,
            'modo_joi': 'sostener',
            'senal_suficiente': False,
        }
        base.update(kwargs)
        return base

    def test_sin_datos_devuelve_suave(self):
        ctx = self._ctx(hay_datos_suficientes=False)
        self.assertEqual(calcular_intensidad_pregunta_apertura(ctx), 'suave')

    def test_energia_baja_fuerza_suave(self):
        ctx = self._ctx(energia_baja=True)
        self.assertEqual(calcular_intensidad_pregunta_apertura(ctx), 'suave')

    def test_sueno_bajo_fuerza_suave(self):
        ctx = self._ctx(sueno_bajo=True)
        self.assertEqual(calcular_intensidad_pregunta_apertura(ctx), 'suave')

    def test_molestia_fuerza_suave(self):
        ctx = self._ctx(molestia_zona=True)
        self.assertEqual(calcular_intensidad_pregunta_apertura(ctx), 'suave')

    def test_empujar_sin_senal_suficiente_no_produce_afilada(self):
        ctx = self._ctx(modo_joi='empujar', senal_suficiente=False)
        self.assertNotEqual(calcular_intensidad_pregunta_apertura(ctx), 'afilada')

    def test_con_senal_suficiente_produce_afilada(self):
        ctx = self._ctx(modo_joi='empujar', senal_suficiente=True)
        self.assertEqual(calcular_intensidad_pregunta_apertura(ctx), 'afilada')

    def test_patron_reciente_produce_media(self):
        ctx = self._ctx(patron_reciente_detectado=True)
        self.assertEqual(calcular_intensidad_pregunta_apertura(ctx), 'media')

    def test_default_sin_patron_ni_empujar_produce_media(self):
        ctx = self._ctx()
        self.assertEqual(calcular_intensidad_pregunta_apertura(ctx), 'media')


class TestBancoPreguntas(TestCase):
    _PALABRAS_PRESION = ['demostrar', 'deberías', 'suficiente', 'debes', 'tienes que', 'obligatorio']

    def test_preguntas_suaves_no_tienen_lenguaje_de_presion(self):
        for pregunta in _PREGUNTAS_SUAVES:
            normalizada = pregunta.lower()
            for palabra in self._PALABRAS_PRESION:
                self.assertNotIn(
                    palabra,
                    normalizada,
                    msg=f"Pregunta suave contiene lenguaje de presión '{palabra}': {pregunta}",
                )

    def test_banco_suave_tiene_al_menos_cinco_preguntas(self):
        self.assertGreaterEqual(len(_PREGUNTAS_SUAVES), 5)
