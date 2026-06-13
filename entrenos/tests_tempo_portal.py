"""
Phase 64A.1 — Tempo: conectar tempo_fuente en portal_sesion_unificado.

64A centralizó la sugerencia/registro de tempo en `tempo_service.py` y la
usó en `vista_entrenamiento_activo`, pero `portal_sesion_unificado` (la vista
que realmente renderiza `portal_sesion.html`) seguía con el fallback fijo
'2-0-X-0' y nunca asignaba `tempo_fuente`. Estos tests cierran ese loop.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from rutinas.models import Rutina

_OBTENER_PROXIMO_PATH = 'clientes.views.obtener_proximo_entrenamiento'


class PortalSesionTempoBase(TestCase):
    """portal_sesion.html (clientes:portal_sesion) solo construye
    rutina_ajustada si hay un check-in (BitacoraDiaria) de hoy."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_tempo_portal', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = date.today()
        BitacoraDiaria.objects.create(
            cliente=self.cliente, energia_subjetiva=10, dolor_articular=0, horas_sueno=10,
        )

    def _get(self, ejercicio):
        plan = {'fecha': self.hoy, 'ejercicios': [ejercicio]}
        c = Client()
        c.login(username='tester_tempo_portal', password='x')
        url = reverse('clientes:portal_sesion', args=[self.cliente.id])
        with patch(_OBTENER_PROXIMO_PATH, return_value=plan):
            return c.get(url)


class TestTempoSugeridoSinHistorial(PortalSesionTempoBase):
    def test_sin_tempo_previo_usa_sugerido(self):
        ejercicio = {
            'nombre': 'Peso Muerto', 'grupo_muscular': 'pierna',
            'tipo_ejercicio': 'compuesto_principal', 'peso_kg': 100.0,
            'series': 4, 'repeticiones': '5', 'rpe_objetivo': 7,
        }

        response = self._get(ejercicio)
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertEqual(ej['tempo_fuente'], 'sugerido')
        self.assertEqual(ej['tempo'], '2-1-3')

        html = response.content.decode()
        self.assertIn('Tempo sugerido', html)
        self.assertIn('2-1-3', html)


class TestTempoRegistradoConHistorial(PortalSesionTempoBase):
    def test_con_tempo_previo_usa_registrado(self):
        rutina = Rutina.objects.create(nombre='Rutina test')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina, fecha=self.hoy - timedelta(days=7),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Peso Muerto',
            peso_kg=100, series=4, repeticiones=5, tempo='2-0-X-0',
        )

        ejercicio = {
            'nombre': 'Peso Muerto', 'grupo_muscular': 'pierna',
            'tipo_ejercicio': 'compuesto_principal', 'peso_kg': 100.0,
            'series': 4, 'repeticiones': '5', 'rpe_objetivo': 7,
        }

        response = self._get(ejercicio)
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertEqual(ej['tempo_fuente'], 'registrado')
        self.assertEqual(ej['tempo'], '2-0-X-0')

        html = response.content.decode()
        self.assertIn('Tempo registrado', html)
        self.assertIn('2-0-X-0', html)
