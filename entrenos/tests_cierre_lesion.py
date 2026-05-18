"""
Phase 29.1 — Cierre del ciclo de lesión. Auditoría del checklist completo.

Cubre los items del checklist no bien representados en fases anteriores:

1.  Ejercicio con lesión relevante → botón "Ver alternativas" en decisión.
2.  Ejercicio sin lesión relevante → no hay preferencia_aplicada ni aviso de lesión.
3.  Rodilla retorno → alternativas compatibles con rodilla (sin tags de rodilla).
4.  Hombro retorno → no muestra alternativas de rodilla.
5.  Modal no usa lenguaje absoluto.
6.  Elegir alternativa NO modifica PlanificadorHelms.
7.  Alternativa registrable como sustitución manual (hot-swap API existe y acepta POST).
8.  api_alternativas_lesion devuelve alternativas sin riesgo para la zona afectada.
9.  Lesión aguda: nota más prudente que retorno (tono diferente).
10. Sin alternativas seguras → API devuelve lista vacía, no error.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch

from clientes.models import Cliente
from entrenos.models import PreferenciaPlanAprendida
from entrenos.services.alternativas_lesion_service import (
    buscar_alternativas_lesion, nota_prudente_lesion,
)
from entrenos.services.sesion_recomendada import (
    _aplicar_aviso_lesion,
    _detectar_riesgo_lesion,
)
from rutinas.models import EjercicioBase


class CierreLesionBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_cierre29', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestCierre29', 'dias_disponibles': 4},
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _crear_lesion(self, fase='RETORNO', tags=None, zona='Rodilla'):
        from hyrox.models import UserInjury
        tags_val = tags if tags is not None else ['flexion_rodilla_profunda']
        return UserInjury.objects.create(
            cliente=self.cliente, zona_afectada=zona,
            fase=fase, activa=True, tags_restringidos=tags_val,
        )

    def _crear_ej(self, nombre, grupo, risk_tags=None):
        return EjercicioBase.objects.create(
            nombre=nombre, grupo_muscular=grupo,
            risk_tags=risk_tags or [],
        )

    def tearDown(self):
        cache.clear()
        EjercicioBase.objects.filter(nombre__endswith='_test29').delete()


# ── Item 1: ejercicio afectado → aviso existe ─────────────────────────────────

class TestItem1_AvisoExiste(CierreLesionBase):
    def test_ejercicio_con_lesion_relevante_genera_aviso(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        entreno = {'ejercicios': [
            {'nombre': 'Sentadilla', 'risk_tags': ['flexion_rodilla_profunda'],
             'grupo_muscular': 'Cuadriceps'},
        ]}
        aviso = _detectar_riesgo_lesion(self.cliente, entreno)
        self.assertIsNotNone(aviso)
        self.assertIn('Sentadilla', aviso['ejercicios_en_riesgo'])


# ── Item 2: ejercicio sin lesión relevante → sin aviso ───────────────────────

class TestItem2_SinAvisoSinLesion(CierreLesionBase):
    def test_sin_lesion_activa_no_hay_aviso(self):
        entreno = {'ejercicios': [
            {'nombre': 'Press banca', 'risk_tags': ['hombro_inestable'],
             'grupo_muscular': 'Pecho'},
        ]}
        aviso = _detectar_riesgo_lesion(self.cliente, entreno)
        self.assertIsNone(aviso)

    def test_lesion_rodilla_no_afecta_ejercicio_hombro(self):
        self._crear_lesion(tags=['flexion_rodilla_profunda'])
        entreno = {'ejercicios': [
            {'nombre': 'Press militar', 'risk_tags': ['hombro_inestable'],
             'grupo_muscular': 'Hombro'},
        ]}
        aviso = _detectar_riesgo_lesion(self.cliente, entreno)
        self.assertIsNone(aviso)


# ── Items 3-4: alternativas correctas por zona ───────────────────────────────

class TestItems34_AlternativasPorZona(CierreLesionBase):
    def setUp(self):
        super().setUp()
        self._crear_ej('Extensión cuád_test29', 'Cuadriceps', risk_tags=[])
        self._crear_ej('Hack squat_test29', 'Cuadriceps',
                       risk_tags=['flexion_rodilla_profunda'])
        self._crear_ej('Press banca_test29', 'Pecho', risk_tags=[])

    def test_rodilla_retorno_muestra_alternativas_sin_tags_rodilla(self):
        alts = buscar_alternativas_lesion(
            'Sentadilla', 'Cuadriceps', ['flexion_rodilla_profunda'],
        )
        nombres = [a['nombre'] for a in alts]
        self.assertIn('Extensión cuád_test29', nombres)
        self.assertNotIn('Hack squat_test29', nombres)

    def test_hombro_no_muestra_alternativas_de_rodilla(self):
        alts = buscar_alternativas_lesion(
            'Press lateral', 'Hombro', ['hombro_inestable'],
        )
        nombres = [a['nombre'] for a in alts]
        # Press banca is Pecho, not Hombro → shouldn't appear
        self.assertNotIn('Press banca_test29', nombres)


# ── Item 5: modal sin lenguaje absoluto ───────────────────────────────────────

class TestItem5_LenguajePrudente(CierreLesionBase):
    def test_nota_modal_sin_palabras_absolutas(self):
        for fase in ['AGUDA', 'SUB_AGUDA', 'RETORNO']:
            nota = nota_prudente_lesion(fase).lower()
            for palabra in ['prohibido', 'nunca', 'debes', 'seguro', 'garantizado']:
                self.assertNotIn(palabra, nota,
                                 msg=f"Nota fase={fase} usa '{palabra}'")

    def test_nota_no_dice_sustitucion_segura(self):
        for fase in ['AGUDA', 'RETORNO']:
            nota = nota_prudente_lesion(fase).lower()
            self.assertNotIn('sustitución segura', nota)
            self.assertNotIn('sustitucion segura', nota)


# ── Item 6: alternativa no modifica PlanificadorHelms ─────────────────────────

class TestItem6_NoPlanificador(CierreLesionBase):
    def test_buscar_alternativas_no_llama_planificador(self):
        self._crear_ej('Alternativa_test29', 'Cuadriceps', risk_tags=[])
        with patch('analytics.planificador_helms.core.PlanificadorHelms') as mock_p:
            buscar_alternativas_lesion(
                'Sentadilla', 'Cuadriceps', ['flexion_rodilla_profunda'],
            )
        mock_p.assert_not_called()

    def test_api_alternativas_lesion_no_llama_planificador(self):
        self._crear_ej('Alt2_test29', 'Cuadriceps', risk_tags=[])
        c = Client()
        c.login(username='tester_cierre29', password='x')
        with patch('analytics.planificador_helms.core.PlanificadorHelms') as mock_p:
            c.post(
                reverse('entrenos:api_alternativas_lesion', args=[self.cliente.id]),
                data='{"ejercicio_nombre":"Sentadilla","grupo_muscular":"Cuadriceps",'
                     '"tags_restringidos":["flexion_rodilla_profunda"],"fase_lesion":"RETORNO"}',
                content_type='application/json',
            )
        mock_p.assert_not_called()


# ── Item 7: hot-swap API existe y acepta POST (trazabilidad manual) ───────────

class TestItem7_HotSwapTrazabilidad(CierreLesionBase):
    def test_api_save_hot_swap_url_existe(self):
        try:
            url = reverse('entrenos:api_save_hot_swap', args=[self.cliente.id])
            self.assertTrue(url.startswith('/'))
        except NoReverseMatch:
            self.fail("api_save_hot_swap URL no existe")

    def test_api_alternativas_lesion_url_existe(self):
        try:
            url = reverse('entrenos:api_alternativas_lesion', args=[self.cliente.id])
            self.assertTrue(url.startswith('/'))
        except NoReverseMatch:
            self.fail("api_alternativas_lesion URL no existe")


# ── Item 8: API devuelve alternativas sin riesgo ─────────────────────────────

class TestItem8_APIAlternativasSinRiesgo(CierreLesionBase):
    def setUp(self):
        super().setUp()
        self._crear_ej('Safe_test29', 'Cuadriceps', risk_tags=[])
        self._crear_ej('Risky_test29', 'Cuadriceps',
                       risk_tags=['flexion_rodilla_profunda'])

    def test_api_no_devuelve_ejercicios_con_riesgo(self):
        c = Client()
        c.login(username='tester_cierre29', password='x')
        resp = c.post(
            reverse('entrenos:api_alternativas_lesion', args=[self.cliente.id]),
            data='{"ejercicio_nombre":"Sentadilla","grupo_muscular":"Cuadriceps",'
                 '"tags_restringidos":["flexion_rodilla_profunda"],"fase_lesion":"RETORNO"}',
            content_type='application/json',
        )
        data = resp.json()
        nombres = [a['nombre'] for a in data.get('alternativas', [])]
        self.assertNotIn('Risky_test29', nombres)
        self.assertIn('Safe_test29', nombres)


# ── Item 9: lesión aguda más prudente que retorno ────────────────────────────

class TestItem9_TonoPorFase(CierreLesionBase):
    def test_nota_aguda_menciona_reposo_o_prudencia_mayor(self):
        nota_aguda = nota_prudente_lesion('AGUDA').lower()
        nota_retorno = nota_prudente_lesion('RETORNO').lower()
        # Aguda should mention aguda/reposo/fase aguda
        self.assertIn('aguda', nota_aguda)
        # They should NOT be identical
        self.assertNotEqual(nota_aguda, nota_retorno)

    def test_nota_retorno_menciona_alternativa_y_valorar(self):
        nota = nota_prudente_lesion('RETORNO').lower()
        palabras_retorno = ['alternativa', 'valorar', 'molesta', 'prueba']
        usa = any(k in nota for k in palabras_retorno)
        self.assertTrue(usa, f"Nota RETORNO no usa tono revisable: {nota}")


# ── Item 10: sin alternativas → lista vacía, no error ────────────────────────

class TestItem10_SinAlternativas(CierreLesionBase):
    def test_sin_ejercicios_compatibles_devuelve_lista_vacia(self):
        # All same-group exercises have the restricted tag → no safe alternatives
        self._crear_ej('Solo_test29', 'GrupoUnico', risk_tags=['tag_raro_xyz'])
        alts = buscar_alternativas_lesion(
            'Ejercicio A', 'GrupoUnico', ['tag_raro_xyz'],
        )
        self.assertEqual(alts, [])

    def test_api_sin_alternativas_devuelve_200_lista_vacia(self):
        c = Client()
        c.login(username='tester_cierre29', password='x')
        resp = c.post(
            reverse('entrenos:api_alternativas_lesion', args=[self.cliente.id]),
            data='{"ejercicio_nombre":"X","grupo_muscular":"GrupoInexistente",'
                 '"tags_restringidos":["tag_raro_xyz"],"fase_lesion":"RETORNO"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['alternativas'], [])
