"""
Phase 30.1 — Tests de no duplicación y explicación unificada.

Valida que el panel no muestra mensajes duplicados ni líneas vacías,
y que el lenguaje no usa culpa ni absolutos.

Checklist:
1. [Ya cubierto] PRF y distribucion sobre mismo patrón → solo PRF visible.
2.  PRF existe → aparece bloque teal en HTML del panel.
3.  lesion_aviso existe → aparece en card Y en ¿Por qué hoy?
4.  Sin lesión → senales_activas no tiene línea de lesión.
5.  Sin preferencia → senales_activas no tiene línea de preferencia.
6. [Ya cubierto] Sin nada especial → todo_limpio=True, colapsable no aparece.
7.  Lenguaje en senales_activas sin culpa ni absolutos.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.services.explicacion_decision_service import construir_explicacion_decision


def _decision(**kwargs):
    base = {
        'tipo': 'programada_hoy', 'estado': 'entrenar',
        'sesion_programada': None, 'entrenamiento': {},
        'mensaje': 'Sesión prevista.', 'causa_principal': 'sesion_hoy',
        'modo_reducido': False, 'distribucion_aviso': None,
        'preferencia_aplicada': None, 'lesion_aviso': None,
    }
    base.update(kwargs)
    return base


# ── Items 4-5: sin señal → lista limpia ─────────────────────────────────────

class TestSinSenal_ListaLimpia(TestCase):
    def test_sin_lesion_no_hay_linea_de_lesion(self):
        result = construir_explicacion_decision(_decision())
        for senal in result['senales_activas']:
            self.assertNotIn('lesión', senal.lower())
            self.assertNotIn('rodilla', senal.lower())

    def test_sin_preferencia_no_hay_linea_de_preferencia(self):
        result = construir_explicacion_decision(_decision())
        for senal in result['senales_activas']:
            self.assertNotIn('preferencia', senal.lower())
            self.assertNotIn('recuerda', senal.lower())

    def test_sin_distribucion_no_hay_linea_de_distribucion(self):
        result = construir_explicacion_decision(_decision())
        for senal in result['senales_activas']:
            self.assertNotIn('prueba activa', senal.lower())

    def test_lista_vacia_cuando_nada_especial(self):
        result = construir_explicacion_decision(_decision())
        self.assertEqual(result['senales_activas'], [])


# ── Item 7: lenguaje sin culpa ni absolutos ──────────────────────────────────

class TestLenguajeSinCulpa(TestCase):
    PALABRAS_CULPA = [
        'no has', 'fallaste', 'debiste', 'deberías', 'no cumpliste',
        'incumplimiento', 'culpa', 'fracaso',
    ]
    PALABRAS_ABSOLUTAS = ['nunca', 'siempre', 'prohibido', 'imposible', 'jamás']

    def _senales_para(self, **kwargs):
        return construir_explicacion_decision(_decision(**kwargs))['senales_activas']

    def test_lesion_sin_culpa_ni_absolutos(self):
        senales = self._senales_para(lesion_aviso={
            'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
            'ejercicios_en_riesgo': ['Sentadilla'],
            'mensaje': 'En fase de retorno la articulación necesita carga gradual.',
        })
        for senal in senales:
            texto = senal.lower()
            for palabra in self.PALABRAS_CULPA + self.PALABRAS_ABSOLUTAS:
                self.assertNotIn(palabra, texto,
                                 msg=f"Senal usa '{palabra}': {senal}")

    def test_preferencia_sin_culpa_ni_absolutos(self):
        senales = self._senales_para(preferencia_aplicada={
            'tipo': 'evitar_pierna_tras_futbol',
            'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
            'accion_sugerida': 'posponer_recomendado',
        })
        for senal in senales:
            texto = senal.lower()
            for palabra in self.PALABRAS_CULPA + self.PALABRAS_ABSOLUTAS:
                self.assertNotIn(palabra, texto)

    def test_modo_reducido_sin_culpa(self):
        senales = self._senales_para(modo_reducido=True)
        for senal in senales:
            texto = senal.lower()
            for palabra in self.PALABRAS_CULPA:
                self.assertNotIn(palabra, texto)

    def test_freno_sin_culpa(self):
        senales = self._senales_para(entrenamiento={
            'ejercicios': [],
            'permiso_progresion': {
                'accion': 'mantener_carga',
                'mensaje': 'El plan frena la subida de cargas esta semana.',
            },
        })
        for senal in senales:
            texto = senal.lower()
            for palabra in self.PALABRAS_CULPA:
                self.assertNotIn(palabra, texto)


# ── Items 2-3: template — señales aparecen en HTML ───────────────────────────

class TestTemplateIntegracion(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester_nodup30', password='x',
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestNoDup30', 'dias_disponibles': 4},
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _get(self, decision_mock):
        with patch(
            'entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy',
            return_value=decision_mock,
        ):
            c = Client()
            c.login(username='tester_nodup30', password='x')
            return c.get(reverse('clientes:mockup_demo'))

    def _decision_con_sesion(self, **kwargs):
        base = {
            'tipo': 'programada_hoy', 'estado': 'entrenar',
            'sesion_programada': None,
            'entrenamiento': {
                'rutina_nombre': 'Push A', 'nombre_rutina': 'Push A', 'nombre': 'Push A',
                'ejercicios': [
                    {'nombre': 'Press banca', 'series': 4, 'repeticiones': '4-6',
                     'grupo_muscular': 'Pecho', 'tipo_ejercicio': 'compuesto_principal'},
                ],
            },
            'mensaje': 'Sesión prevista.', 'causa_principal': 'sesion_hoy',
            'modo_reducido': False, 'distribucion_aviso': None,
            'preferencia_aplicada': None, 'lesion_aviso': None,
        }
        base.update(kwargs)
        return base

    def test_item2_prf_visible_en_html_cuando_preferencia_activa(self):
        decision = self._decision_con_sesion(preferencia_aplicada={
            'tipo': 'evitar_pierna_tras_futbol',
            'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
            'accion_sugerida': 'posponer_recomendado',
        })
        response = self._get(decision)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preferencia del plan')

    def test_item3_lesion_visible_en_card_y_en_por_que_hoy(self):
        decision = self._decision_con_sesion(lesion_aviso={
            'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
            'ejercicios_en_riesgo': ['Press banca'],
            'mensaje': 'En fase de retorno, la Rodilla puede tolerar carga progresiva.',
        })
        response = self._get(decision)
        self.assertEqual(response.status_code, 200)
        # Lesion aviso in card
        self.assertContains(response, 'Revisar · Rodilla')
        # Also summarized in ¿Por qué hoy?
        self.assertContains(response, '¿Por qué hoy?')

    def test_item6_sin_senales_por_que_hoy_no_aparece(self):
        """todo_limpio=True → colapsable '¿Por qué hoy?' no se renderiza."""
        decision = self._decision_con_sesion()
        response = self._get(decision)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '¿Por qué hoy?')

    def test_distribucion_suprimida_no_aparece_en_html(self):
        """Si PRF suplanta distribucion_aviso, el aviso naranja no aparece."""
        decision = self._decision_con_sesion(
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_pierna_futbol',
                'texto': 'Prueba activa: separar pierna del fútbol.',
                'accion_sugerida': 'posponer_opcional',
            },
        )
        response = self._get(decision)
        self.assertEqual(response.status_code, 200)
        # Preference is visible
        self.assertContains(response, 'Preferencia del plan')
        # But distribution aviso text is NOT shown (suppressed)
        self.assertNotContains(response, 'Prueba activa: separar pierna del fútbol')
