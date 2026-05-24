import re
from django.test import TestCase
from joi.services import _prompt_apertura_manana


PALABRAS_PROHIBIDAS_GESTOS = [
    'racha', 'cumplimiento', 'cumpliste', 'cumplido',
    'fallaste', 'fallado', 'fallo',
    'recaída', 'recaida', 'cediste',
    '%',
]

# Patrón: [GESTO ...]: <dato real>
# El dato real es lo que queda después de ']: ' hasta el próximo '[' o fin de sección.
_RE_DATO_GESTO = re.compile(r'\[GESTO[^\]]+\]:\s*(El gesto [^.]+\.)')


def _extraer_datos_gesto(prompt: str) -> list:
    """Extrae solo los textos de datos (lo que va después del label [GESTO...]:).
    Los labels en sí pueden mencionar palabras prohibidas como contraejemplos; aquí
    solo chequeamos el contenido real que JOI recibirá como hecho."""
    return [m.group(1).strip() for m in _RE_DATO_GESTO.finditer(prompt)]


class TestGestosVocabularioJOI(TestCase):
    """Auditoría: el dato de gesto en el prompt nunca usa vocabulario prohibido."""

    def _prompt_con_gestos(self, señales):
        ctx = {'gestos_señales': señales}
        return _prompt_apertura_manana(ctx, {})

    def test_aparecio_varias_sin_palabras_prohibidas(self):
        prompt = self._prompt_con_gestos([
            {'nombre': 'Lectura', 'señal': 'aparecio_varias', 'presencias': 5}
        ])
        datos = _extraer_datos_gesto(prompt)
        self.assertTrue(datos, "El gesto debería aparecer en el prompt")
        for palabra in PALABRAS_PROHIBIDAS_GESTOS:
            for dato in datos:
                self.assertNotIn(
                    palabra, dato.lower(),
                    f"Palabra prohibida '{palabra}' en dato de gesto: {dato}"
                )

    def test_ausente_sin_palabras_prohibidas(self):
        prompt = self._prompt_con_gestos([
            {'nombre': 'Meditación', 'señal': 'ausente', 'dias_sin': 4}
        ])
        datos = _extraer_datos_gesto(prompt)
        self.assertTrue(datos)
        for palabra in PALABRAS_PROHIBIDAS_GESTOS:
            for dato in datos:
                self.assertNotIn(
                    palabra, dato.lower(),
                    f"Palabra prohibida '{palabra}' en dato de gesto: {dato}"
                )

    def test_reaparecio_sin_palabras_prohibidas(self):
        prompt = self._prompt_con_gestos([
            {'nombre': 'Móvil al levantarse', 'señal': 'reaparecio', 'veces': 2}
        ])
        datos = _extraer_datos_gesto(prompt)
        self.assertTrue(datos)
        for palabra in PALABRAS_PROHIBIDAS_GESTOS:
            for dato in datos:
                self.assertNotIn(
                    palabra, dato.lower(),
                    f"Palabra prohibida '{palabra}' en dato de gesto: {dato}"
                )

    def test_sin_gestos_no_genera_seccion(self):
        prompt = self._prompt_con_gestos([])
        datos = _extraer_datos_gesto(prompt)
        self.assertEqual(datos, [], "Sin señales no debería haber datos de gesto")

    def test_maximo_dos_gestos_en_prompt(self):
        señales = [
            {'nombre': 'Lectura', 'señal': 'aparecio_varias', 'presencias': 5},
            {'nombre': 'Meditación', 'señal': 'ausente', 'dias_sin': 4},
            {'nombre': 'Móvil', 'señal': 'reaparecio', 'veces': 1},
        ]
        prompt = self._prompt_con_gestos(señales)
        datos = _extraer_datos_gesto(prompt)
        self.assertLessEqual(
            len(datos), 2,
            f"El prompt no debería incluir más de 2 gestos, encontró {len(datos)}"
        )
