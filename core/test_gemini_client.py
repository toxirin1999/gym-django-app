from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from core.ai import gemini_client


class GeminiClientTests(SimpleTestCase):
    def setUp(self):
        self.original_genai = gemini_client._genai
        self.original_types = gemini_client._types
        self.original_client = gemini_client._client
        gemini_client._client = None

    def tearDown(self):
        gemini_client._genai = self.original_genai
        gemini_client._types = self.original_types
        gemini_client._client = self.original_client

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_usa_el_cliente_del_sdk_actual_y_devuelve_texto(self):
        response = SimpleNamespace(text=' respuesta ')
        client = MagicMock()
        client.models.generate_content.return_value = response
        sdk = MagicMock()
        sdk.Client.return_value = client
        gemini_client._genai = sdk
        gemini_client._types = MagicMock()

        result = gemini_client.generate_text('hola', model='gemini-test')

        self.assertEqual(result, 'respuesta')
        sdk.Client.assert_called_once_with(api_key='clave-de-prueba')
        client.models.generate_content.assert_called_once_with(
            model='gemini-test', contents='hola', config=None,
        )

    def test_sin_sdk_o_clave_retorna_el_fallback(self):
        gemini_client._genai = None

        self.assertEqual(
            gemini_client.generate_text('hola', fallback='sin IA'),
            'sin IA',
        )
