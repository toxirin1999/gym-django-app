"""Contrato del mapa corporal de evolución en "Lo que sé de ti"."""

from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from rutinas.models import Rutina

PLANTILLA = Path('clientes/templates/clientes/memoria_entrenador.html')
PARCIAL = Path('clientes/templates/clientes/partials/_mapa_evolucion_muscular.html')


class MemoriaMapaCorporalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='mapa', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse('clientes:memoria_entrenador', args=[self.cliente.id])
        self.client.force_login(self.user)

    def _sesion(self, dias_atras, nombre, peso, grupo):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre=f'r{dias_atras}{nombre}'),
            fecha=timezone.localdate() - timedelta(days=dias_atras),
        )
        EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
            entreno=entreno, nombre_ejercicio=nombre, grupo_muscular=grupo,
            peso_kg=peso, repeticiones=10, series=3,
        )])

    def test_sin_datos_muestra_el_mapa_en_gris_y_lo_explica(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'clientes/partials/_mapa_evolucion_muscular.html')
        self.assertContains(response, 'id="evolucion"')
        self.assertContains(response, 'Aún sin datos para comparar')
        self.assertEqual(response.context['evolucion_muscular']['n_con_datos'], 0)
        self.assertNotContains(response, 'mm-progresa_mucho"')

    def test_colorea_la_zona_segun_su_evolucion(self):
        self._sesion(120, 'Press francés', 20, 'Tríceps')
        self._sesion(10, 'Press francés', 32, 'Triceps')
        response = self.client.get(self.url)
        evo = response.context['evolucion_muscular']
        self.assertEqual(evo['estado_por_zona']['triceps'], 'progresa_mucho')
        self.assertContains(response, 'data-zona="triceps"')
        self.assertContains(response, 'mm-z mm-progresa_mucho')
        self.assertContains(response, '+60')
        self.assertContains(response, 'Tríceps')

    def test_dato_dudoso_se_muestra_aparte_y_no_colorea(self):
        self._sesion(120, 'Hiperextensiones inversas', 5, 'Isquios')
        self._sesion(10, 'Hiperextensiones inversas', 15, 'Isquios')
        response = self.client.get(self.url)
        evo = response.context['evolucion_muscular']
        self.assertEqual(evo['estado_por_zona']['isquios'], 'sin_datos')
        self.assertEqual(evo['n_dudosos'], 1)
        self.assertContains(response, 'Dato a revisar')
        self.assertContains(response, '1 a revisar')
        self.assertContains(response, 'Hiperextensiones inversas')

    def test_periodo_seleccionable_y_validado(self):
        r30 = self.client.get(self.url, {'periodo': '30'})
        self.assertEqual(r30.context['evolucion_muscular']['periodo_dias'], 30)
        self.assertContains(r30, 'aria-current="true"', count=1)
        rx = self.client.get(self.url, {'periodo': 'abc'})
        self.assertEqual(rx.context['evolucion_muscular']['periodo_dias'], 90)
        r999 = self.client.get(self.url, {'periodo': '999'})
        self.assertEqual(r999.context['evolucion_muscular']['periodo_dias'], 90)

    def test_el_mapa_sustituye_a_la_lista_de_tendencia_de_cargas(self):
        plantilla = PLANTILLA.read_text()
        self.assertIn("{% include 'clientes/partials/_mapa_evolucion_muscular.html'", plantilla)
        self.assertNotIn('Tendencia de cargas por grupo', plantilla)
        # El mapa va antes del expediente completo.
        self.assertLess(plantilla.index('_mapa_evolucion_muscular'),
                        plantilla.index('Expediente completo'))

    def test_parcial_accesible(self):
        parcial = PARCIAL.read_text()
        self.assertIn('role="img"', parcial)
        self.assertIn('aria-label', parcial)
        self.assertIn('<details', parcial)
        self.assertNotIn('onclick', parcial.lower())
