"""
Phase 59D — Tests del marco narrativo inicial.

Objetivo: verificar que _bloque_marco_narrativo() genera contenido correcto
y que el prompt de generar_mensaje_joi sitúa el marco ANTES del trigger.

Casos cubiertos:
1. Sin NarrativaActiva → devuelve cadena vacía.
2. NarrativaActiva solo con capa_corta → marco incluye solo esa capa.
3. NarrativaActiva con las tres capas → todas aparecen en el orden correcto.
4. El marco indica explícitamente que el evento no es protagonista.
5. El marco indica que no se fuerce lectura profunda en eventos menores.
6. En el prompt ensamblado, [MARCO NARRATIVO ACTIVO] aparece antes del builder.
7. Sin NarrativaActiva, [MARCO NARRATIVO ACTIVO] no aparece en el prompt.
"""

from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase

from joi.services import _bloque_marco_narrativo
from joi.models import NarrativaActiva


class TestBloqueMarcoNarrativo(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='tester_marco', password='x')

    def test_sin_narrativa_devuelve_vacio(self):
        resultado = _bloque_marco_narrativo(self.user)
        self.assertEqual(resultado, '')

    def test_narrativa_descartada_devuelve_vacio(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='descartada',
            capa_corta='Algo',
        )
        resultado = _bloque_marco_narrativo(self.user)
        self.assertEqual(resultado, '')

    def test_narrativa_sin_capas_devuelve_vacio(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
        )
        resultado = _bloque_marco_narrativo(self.user)
        self.assertEqual(resultado, '')

    def test_solo_capa_corta_aparece_en_marco(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='RPE bajando y energía subiendo.',
        )
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('[Ahora mismo]', resultado)
        self.assertIn('RPE bajando y energía subiendo.', resultado)
        self.assertNotIn('[Esta fase]', resultado)
        self.assertNotIn('[Patrón profundo]', resultado)

    def test_tres_capas_aparecen_en_orden(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='Ahora mismo texto.',
            capa_media='Esta fase texto.',
            capa_larga='Patrón profundo texto.',
        )
        resultado = _bloque_marco_narrativo(self.user)

        idx_larga = resultado.index('[Patrón profundo]')
        idx_media = resultado.index('[Esta fase]')
        idx_corta = resultado.index('[Ahora mismo]')

        self.assertLess(idx_larga, idx_media)
        self.assertLess(idx_media, idx_corta)

    def test_marco_incluye_instruccion_de_encuadre(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='Algo.',
        )
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('[MARCO NARRATIVO ACTIVO]', resultado)
        self.assertIn('encuadre inicial', resultado)
        self.assertIn('evidencia posible', resultado)

    def test_marco_advierte_no_forzar_lectura_profunda(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='Algo.',
        )
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('no fuerces una lectura profunda', resultado.lower())

    def test_marco_funciona_con_estado_borrador(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='borrador',
            capa_corta='En construcción.',
        )
        resultado = _bloque_marco_narrativo(self.user)
        self.assertNotEqual(resultado, '')
        self.assertIn('En construcción.', resultado)


class TestReglaDePresicion(TestCase):
    """Phase 59D.0.1 — Bisturí, no martillo.
    Verifica que el marco contiene la regla explícita contra absolutismo."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_precision', password='x')

    def _crear_narrativa(self):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='Algo concreto.',
        )

    def test_marco_exige_evidencia_concreta(self):
        self._crear_narrativa()
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('evidencia concreta', resultado)

    def test_marco_prohíbe_absolutos_sin_evidencia(self):
        self._crear_narrativa()
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('no agrupes en absolutos', resultado.lower())

    def test_marco_exige_nombrar_habito_concreto(self):
        self._crear_narrativa()
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('hábito concreto', resultado)

    def test_marco_contiene_regla_bisturi(self):
        self._crear_narrativa()
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('bisturí', resultado)
        self.assertIn('martillo', resultado)

    def test_marco_lista_absolutos_prohibidos(self):
        self._crear_narrativa()
        resultado = _bloque_marco_narrativo(self.user)
        for absoluto in ("'cero'", "'nunca'", "'todo'", "'nada'"):
            self.assertIn(absoluto, resultado,
                          f"El marco debe mencionar '{absoluto}' como absoluto a evitar")

    def test_marco_exige_formulacion_temporal_no_absoluta(self):
        self._crear_narrativa()
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('N días sin', resultado)
        self.assertIn('observación', resultado.lower())

    def test_marco_exige_presencia_no_informe(self):
        self._crear_narrativa()
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('card de analytics', resultado)
        self.assertIn('informe', resultado.lower())
        self.assertIn('narrativa viva', resultado)


class TestOrdenPromptConMarco(TestCase):
    """Verifica que el marco aparece ANTES del builder en el prompt ensamblado."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_orden', password='x')
        from clientes.models import Cliente
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user)

    def _mock_haiku(self, texto='Mensaje generado.'):
        mock = MagicMock()
        mock.content = [MagicMock(text=texto)]
        return mock

    @patch('joi.services._llamar_haiku')
    @patch('joi.services.construir_contexto', return_value={})
    @patch('joi.services.build_continuidad_context', return_value={})
    @patch('joi.services._bloque_continuidad', return_value='')
    @patch('joi.services.resolver_contexto_temporal', return_value={})
    @patch('joi.services._bloque_temporal', return_value='')
    @patch('joi.services._bloque_memoria', return_value='')
    @patch('joi.services.validar_semantica_joi')
    def test_marco_aparece_antes_del_builder(
        self,
        mock_validar, mock_memoria, mock_temporal,
        mock_resolver, mock_bloque_cont, mock_build_cont,
        mock_ctx, mock_haiku,
    ):
        NarrativaActiva.objects.create(
            user=self.user,
            estado='activa',
            capa_corta='Capa corta de prueba.',
        )
        mock_haiku.return_value = self._mock_haiku('Respuesta JOI.')
        captured_prompts = []

        def capture_prompt(prompt, **kwargs):
            captured_prompts.append(prompt)
            return self._mock_haiku('Respuesta JOI.')

        mock_haiku.side_effect = capture_prompt

        from joi.services import generar_mensaje_joi
        # apertura_manana requiere contexto mínimo — usamos un builder que existe
        with patch.dict('joi.services._PROMPT_BUILDERS', {
            'apertura_manana': lambda ctx, extra: '[TRIGGER apertura]'
        }):
            generar_mensaje_joi(self.cliente, 'apertura_manana', {})

        self.assertTrue(len(captured_prompts) > 0, 'No se capturó ningún prompt')
        prompt = captured_prompts[0]

        self.assertIn('[MARCO NARRATIVO ACTIVO]', prompt)
        self.assertIn('[TRIGGER apertura]', prompt)

        idx_marco = prompt.index('[MARCO NARRATIVO ACTIVO]')
        idx_trigger = prompt.index('[TRIGGER apertura]')
        self.assertLess(idx_marco, idx_trigger,
                        'El marco debe aparecer antes del builder en el prompt')

    @patch('joi.services._llamar_haiku')
    @patch('joi.services.construir_contexto', return_value={})
    @patch('joi.services.build_continuidad_context', return_value={})
    @patch('joi.services._bloque_continuidad', return_value='')
    @patch('joi.services.resolver_contexto_temporal', return_value={})
    @patch('joi.services._bloque_temporal', return_value='')
    @patch('joi.services._bloque_memoria', return_value='')
    @patch('joi.services.validar_semantica_joi')
    def test_sin_narrativa_no_inyecta_marco(
        self,
        mock_validar, mock_memoria, mock_temporal,
        mock_resolver, mock_bloque_cont, mock_build_cont,
        mock_ctx, mock_haiku,
    ):
        captured_prompts = []

        def capture_prompt(prompt, **kwargs):
            captured_prompts.append(prompt)
            return self._mock_haiku('Respuesta.')

        mock_haiku.side_effect = capture_prompt

        from joi.services import generar_mensaje_joi
        with patch.dict('joi.services._PROMPT_BUILDERS', {
            'apertura_manana': lambda ctx, extra: '[TRIGGER sin narrativa]'
        }):
            generar_mensaje_joi(self.cliente, 'apertura_manana', {})

        if captured_prompts:
            self.assertNotIn('[MARCO NARRATIVO ACTIVO]', captured_prompts[0])
