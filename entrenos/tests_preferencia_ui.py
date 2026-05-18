"""
Phase 25.1 — Tests for preferencia_aplicada UI integration.

Verifies that the template block PRF:
1.  Appears in context when preferencia_aplicada exists.
2.  Is None when no preference fires.
3.  Does NOT appear when estado_entreno == 'recuperar' (template guard).
4.  Text does not contain 'debes', 'siempre', 'nunca'.
5.  Shows accion_sugerida hint when present.
6.  Saltar/posponer URLs exist independently.
7.  Workout card still renders with PRF present.
8.  preferencia_aplicada does not change estado_entreno or causa_entreno in ctx.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch

from clientes.models import Cliente
from entrenos.models import PreferenciaPlanAprendida
from entrenos.services.sesion_recomendada import _PREF_MENSAJES


class UIPreferenciaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester_ui25', password='testpass', first_name='Test',
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestUI25', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 22)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _pref_data(self, tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                   accion='posponer_recomendado'):
        return {
            'tipo': tipo,
            'descripcion': 'El plan intentará no colocar pierna tras el fútbol.',
            'mensaje': _PREF_MENSAJES.get(tipo, 'El plan lo toma como referencia.'),
            'accion_sugerida': accion,
        }

    def _decision(self, pref=None, estado='entrenar', causa='sesion_hoy'):
        return {
            'tipo': 'programada_hoy',
            'estado': estado,
            'sesion_programada': None,
            'entrenamiento': {
                'rutina_nombre': 'Push A',
                'nombre_rutina': 'Push A',
                'nombre': 'Push A',
                'ejercicios': [
                    {'nombre': 'Press banca', 'series': 4, 'repeticiones': '4-6',
                     'grupo_muscular': 'Pecho', 'tipo_ejercicio': 'compuesto_principal'},
                ],
            },
            'mensaje': 'Sesión prevista.',
            'causa_principal': causa,
            'modo_reducido': False,
            'distribucion_aviso': None,
            'preferencia_aplicada': pref,
        }

    def _get(self, decision_mock):
        with patch(
            'entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy',
            return_value=decision_mock,
        ):
            c = Client()
            c.login(username='tester_ui25', password='testpass')
            return c.get(reverse('clientes:mockup_demo'))


# ── Case 1 & 2: context contains preferencia_aplicada ────────────────────────

class TestCase1_PreferenciaEnContexto(UIPreferenciaBase):
    def test_preferencia_aplicada_llega_al_contexto_cuando_existe(self):
        pref = self._pref_data()
        response = self._get(self._decision(pref=pref))
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertIsNotNone(ctx.get('preferencia_aplicada'))
        self.assertEqual(ctx['preferencia_aplicada']['tipo'],
                         PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL)

    def test_preferencia_aplicada_es_none_sin_preferencias(self):
        response = self._get(self._decision(pref=None))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get('preferencia_aplicada'))


# ── Case 3: template guard — recuperar oculta PRF ────────────────────────────

class TestCase3_RecuperarOcultaPRF(UIPreferenciaBase):
    def test_prf_no_visible_cuando_estado_recuperar(self):
        pref = self._pref_data()
        decision = self._decision(pref=pref, estado='recuperar', causa='lesion')
        decision['mensaje'] = 'La sesión sigue en el mapa, pero hoy no debe pasar por encima de tu lesión.'
        response = self._get(decision)
        self.assertEqual(response.status_code, 200)
        # Template guard: {% if preferencia_aplicada and estado_entreno != 'recuperar' %}
        self.assertNotContains(response, 'Preferencia del plan')


# ── Case 4: texto sin absolutos ──────────────────────────────────────────────

class TestCase4_MensajesSinAbsolutos(UIPreferenciaBase):
    def test_mensajes_prf_no_contienen_absolutos(self):
        forbidden = ['debes', 'siempre', 'nunca', 'tienes que', 'no puedes']
        for tipo, msg in _PREF_MENSAJES.items():
            texto = msg.lower()
            for palabra in forbidden:
                self.assertNotIn(palabra, texto,
                                 msg=f"Mensaje '{tipo}' contiene '{palabra}'")

    def test_subtextos_ui_son_blandos(self):
        hints = [
            'El plan lo toma como referencia. Puedes entrenar o posponer igualmente.',
            'Los accesorios de hoy son opcionales como referencia, no como regla.',
            'Puedes hacer la versión esencial si tienes menos margen hoy.',
        ]
        forbidden = ['debes', 'tienes que', 'nunca', 'siempre debes']
        for hint in hints:
            texto = hint.lower()
            for palabra in forbidden:
                self.assertNotIn(palabra, texto)


# ── Case 5: accion_sugerida hint visible en HTML ──────────────────────────────

class TestCase5_AccionSugeridaVisible(UIPreferenciaBase):
    def test_posponer_recomendado_muestra_hint_posponer(self):
        pref = self._pref_data(accion='posponer_recomendado')
        response = self._get(self._decision(pref=pref))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preferencia del plan')
        self.assertContains(response, 'Puedes entrenar o posponer igualmente')

    def test_accesorios_opcionales_muestra_hint_accesorios(self):
        pref = self._pref_data(
            tipo=PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA,
            accion='accesorios_opcionales',
        )
        response = self._get(self._decision(pref=pref))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'opcionales como referencia')

    def test_version_esencial_muestra_hint_esencial(self):
        pref = self._pref_data(
            tipo=PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
            accion='version_esencial_sugerida',
        )
        response = self._get(self._decision(pref=pref))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'versión esencial')


# ── Cases 6-7: CTAs existentes siguen funcionando ─────────────────────────────

class TestCase6_PosponerAccesible(UIPreferenciaBase):
    def test_saltar_sesion_url_existe(self):
        try:
            url = reverse('clientes:saltar_sesion', args=[1])
            self.assertTrue(url.startswith('/'))
        except NoReverseMatch:
            self.fail("URL 'clientes:saltar_sesion' no existe")

    def test_posponer_sesion_url_existe(self):
        try:
            url = reverse('clientes:posponer_sesion', args=[1])
            self.assertTrue(url.startswith('/'))
        except NoReverseMatch:
            self.fail("URL 'clientes:posponer_sesion' no existe")


class TestCase7_EntrenarIgualAccesible(UIPreferenciaBase):
    def test_workout_card_sigue_mostrando_ejercicios_con_prf(self):
        decision = {
            'tipo': 'programada_hoy', 'estado': 'entrenar',
            'sesion_programada': None,
            'entrenamiento': {
                'rutina_nombre': 'Pierna A',
                'nombre_rutina': 'Pierna A',
                'nombre': 'Pierna A',
                'ejercicios': [
                    {'nombre': 'Sentadilla', 'series': 4, 'repeticiones': '4-6',
                     'grupo_muscular': 'Cuadriceps', 'tipo_ejercicio': 'compuesto_principal'},
                ],
            },
            'mensaje': 'Sesión prevista.',
            'causa_principal': 'sesion_hoy',
            'modo_reducido': False,
            'distribucion_aviso': None,
            'preferencia_aplicada': self._pref_data(),
        }
        response = self._get(decision)
        self.assertEqual(response.status_code, 200)
        # PRF block is there
        self.assertContains(response, 'Preferencia del plan')
        # But the session name still shows (session is still accessible)
        self.assertContains(response, 'Pierna A')

    def test_sin_prf_workout_card_muestra_normal(self):
        response = self._get(self._decision(pref=None))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Push A')
        self.assertNotContains(response, 'Preferencia del plan')


# ── Case 8: ctx no altera estado_entreno / causa_entreno ──────────────────────

class TestCase8_ContextoNoAlteraEstado(UIPreferenciaBase):
    def test_preferencia_aplicada_no_cambia_estado_ni_causa_en_ctx(self):
        pref = self._pref_data()
        response = self._get(self._decision(pref=pref))
        ctx = response.context
        self.assertEqual(ctx['estado_entreno'], 'entrenar')
        self.assertEqual(ctx['causa_entreno'], 'sesion_hoy')
        self.assertIsNotNone(ctx.get('preferencia_aplicada'))

    def test_preferencia_y_causa_son_campos_independientes(self):
        pref = self._pref_data()
        # causa 'futbol_reciente' + preferencia al mismo tiempo
        decision = self._decision(pref=pref, estado='posponer', causa='futbol_reciente')
        response = self._get(decision)
        ctx = response.context
        self.assertEqual(ctx['causa_entreno'], 'futbol_reciente')
        self.assertEqual(ctx['estado_entreno'], 'posponer')
        # preference still present as secondary layer
        self.assertIsNotNone(ctx.get('preferencia_aplicada'))
