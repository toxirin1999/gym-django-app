"""
Phase 29.1 — Tests for injury-safe alternatives service.

Rule: The system does not substitute automatically; it offers reviewable options.
Language: "a valorar", "si molesta" — never "haz esto" or "sustitución segura".

Checklist:
1.  Alternatives exclude exercises with restricted tags.
2.  Alternatives are from the same muscle group.
3.  Original exercise is excluded from alternatives.
4.  No alternatives when all same-group exercises have restricted tags.
5.  Result is limited to 'limite' parameter.
6.  lesion_activa phase generates prudent 'activa' note.
7.  lesion_retorno phase generates 'retorno' note.
8.  Note does NOT use forbidden language.
9.  API endpoint returns 200 with alternatives list.
10. API endpoint without required fields returns 400.
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from rutinas.models import EjercicioBase
from entrenos.services.alternativas_lesion_service import (
    buscar_alternativas_lesion,
    nota_prudente_lesion,
)


class AlternativasLesionBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_alt29', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestAlt29', 'dias_disponibles': 4},
        )
        cache.clear()
        # Create test exercises
        self.ej_principal = EjercicioBase.objects.create(
            nombre='Sentadilla Test', grupo_muscular='Cuadriceps',
            risk_tags=['flexion_rodilla_profunda', 'triple_extension_explosiva'],
        )
        self.ej_sin_riesgo = EjercicioBase.objects.create(
            nombre='Extensión Cuád Test', grupo_muscular='Cuadriceps',
            risk_tags=[],
        )
        self.ej_con_riesgo = EjercicioBase.objects.create(
            nombre='Hack Squat Test', grupo_muscular='Cuadriceps',
            risk_tags=['flexion_rodilla_profunda'],
        )
        self.ej_otro_grupo = EjercicioBase.objects.create(
            nombre='Press Banca Test', grupo_muscular='Pecho',
            risk_tags=['hombro_inestable'],
        )

    def tearDown(self):
        cache.clear()
        EjercicioBase.objects.filter(nombre__endswith=' Test').delete()


# ── Cases 1-5: service logic ──────────────────────────────────────────────────

class TestCase1_ExcluyeEjerciciosRiesgosos(AlternativasLesionBase):
    def test_alternativas_excluyen_ejercicios_con_tags_restringidos(self):
        alternativas = buscar_alternativas_lesion(
            'Sentadilla Test', 'Cuadriceps',
            ['flexion_rodilla_profunda'],
        )
        nombres = [a['nombre'] for a in alternativas]
        self.assertNotIn('Hack Squat Test', nombres)  # has restricted tag
        self.assertNotIn('Sentadilla Test', nombres)   # original


class TestCase2_MismoGrupoMuscular(AlternativasLesionBase):
    def test_alternativas_del_mismo_grupo(self):
        alternativas = buscar_alternativas_lesion(
            'Sentadilla Test', 'Cuadriceps',
            ['flexion_rodilla_profunda'],
        )
        for alt in alternativas:
            self.assertIn('Cuadriceps', alt['grupo_muscular'],
                          msg=f"{alt['nombre']} no es de Cuadriceps")


class TestCase3_OriginalExcluido(AlternativasLesionBase):
    def test_ejercicio_original_no_aparece(self):
        alternativas = buscar_alternativas_lesion(
            'Sentadilla Test', 'Cuadriceps',
            ['flexion_rodilla_profunda'],
        )
        nombres = [a['nombre'] for a in alternativas]
        self.assertNotIn('Sentadilla Test', nombres)


class TestCase4_SinAlternativasSeguras(AlternativasLesionBase):
    def test_vacio_si_todos_tienen_tags_restringidos(self):
        # Temporarily give all cuad exercises the restricted tag
        EjercicioBase.objects.filter(nombre='Extensión Cuád Test').update(
            risk_tags=['flexion_rodilla_profunda'],
        )
        alternativas = buscar_alternativas_lesion(
            'Sentadilla Test', 'Cuadriceps',
            ['flexion_rodilla_profunda'],
        )
        # Only 'Extensión Cuád Test' was the safe one, now it's also blocked
        # (Hack Squat also had it, original excluded)
        self.assertEqual(alternativas, [])
        # Restore
        EjercicioBase.objects.filter(nombre='Extensión Cuád Test').update(risk_tags=[])


class TestCase5_Limite(AlternativasLesionBase):
    def test_resultado_limitado_por_parametro(self):
        # Create extra safe exercises
        extras = [
            EjercicioBase.objects.create(
                nombre=f'Extra Cuád {i} Test', grupo_muscular='Cuadriceps', risk_tags=[],
            )
            for i in range(5)
        ]
        try:
            alternativas = buscar_alternativas_lesion(
                'Sentadilla Test', 'Cuadriceps', ['flexion_rodilla_profunda'], limite=2,
            )
            self.assertLessEqual(len(alternativas), 2)
        finally:
            for e in extras:
                e.delete()


# ── Cases 6-8: notas de lenguaje ─────────────────────────────────────────────

class TestCase6_NotaActiva(AlternativasLesionBase):
    def test_nota_lesion_activa_es_prudente(self):
        nota = nota_prudente_lesion('AGUDA')
        self.assertIn('aguda', nota.lower())
        self.assertGreater(len(nota), 20)

    def test_nota_sub_aguda_es_prudente(self):
        nota = nota_prudente_lesion('SUB_AGUDA')
        self.assertGreater(len(nota), 20)


class TestCase7_NotaRetorno(AlternativasLesionBase):
    def test_nota_retorno_menciona_tono_revisable(self):
        nota = nota_prudente_lesion('RETORNO').lower()
        palabras = ['valorar', 'si molesta', 'prueba', 'alternativa']
        usa_tono = any(k in nota for k in palabras)
        self.assertTrue(usa_tono, f"Nota no usa tono revisable: {nota}")


class TestCase8_NotaSinAbsolutos(AlternativasLesionBase):
    def test_notas_no_tienen_absolutos(self):
        forbidden = ['nunca', 'prohibido', 'debes', 'haz esto', 'sustitución segura']
        for fase in ['AGUDA', 'SUB_AGUDA', 'RETORNO']:
            nota = nota_prudente_lesion(fase).lower()
            for palabra in forbidden:
                self.assertNotIn(palabra, nota, msg=f"Fase {fase}: nota usa '{palabra}'")


# ── Cases 9-10: API endpoint ──────────────────────────────────────────────────

class TestCase9_APIEndpoint(AlternativasLesionBase):
    def test_api_returns_200_with_alternatives(self):
        c = Client()
        c.login(username='tester_alt29', password='x')
        resp = c.post(
            reverse('entrenos:api_alternativas_lesion', args=[self.cliente.id]),
            data='{"ejercicio_nombre":"Sentadilla Test","grupo_muscular":"Cuadriceps","tags_restringidos":["flexion_rodilla_profunda"],"fase_lesion":"RETORNO"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('alternativas', data)
        self.assertIn('nota_general', data)

    def test_api_alternativas_excluyen_ejercicios_riesgosos(self):
        c = Client()
        c.login(username='tester_alt29', password='x')
        resp = c.post(
            reverse('entrenos:api_alternativas_lesion', args=[self.cliente.id]),
            data='{"ejercicio_nombre":"Sentadilla Test","grupo_muscular":"Cuadriceps","tags_restringidos":["flexion_rodilla_profunda"],"fase_lesion":"RETORNO"}',
            content_type='application/json',
        )
        data = resp.json()
        nombres = [a['nombre'] for a in data.get('alternativas', [])]
        self.assertNotIn('Hack Squat Test', nombres)


class TestCase10_APISinCampos(AlternativasLesionBase):
    def test_api_returns_400_without_required_fields(self):
        c = Client()
        c.login(username='tester_alt29', password='x')
        resp = c.post(
            reverse('entrenos:api_alternativas_lesion', args=[self.cliente.id]),
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
