"""27-oct-2026 · Panel «Cómo responde tu cuerpo»: dudas de David.

1. Sin media no hay «Fresco» (el 27 salía en verde con la variabilidad en 32 ms).
2. «Sin dato» y «Sin media aún» se distinguen y están en la leyenda.
3. La variabilidad enseña los valores de las últimas mañanas.
4. Pulso en reposo con su gráfica.
5. Botón «i» que explica cada apartado.
"""

from django.urls import reverse

from entrenos.services import recuperacion_service as rec
from entrenos.services.panel_cuerpo_service import pulso, variabilidad
from entrenos.tests_estado_carga_20261025 import HOY, Base


class PanelCuerpo(Base):
    def test_sin_media_no_hay_fresco(self):
        self.reloj(2, hrv=55, fc=59, sueno=7.8)
        self.reloj(1, hrv=81, fc=58, sueno=6.6)
        self.reloj(0, hrv=32, fc=58, sueno=7.9)
        self.assertEqual(rec.lectura_recuperacion(self.cliente, HOY)['nivel'], 'sin_referencia')

    def test_con_media_y_buen_dia_si_es_fresco(self):
        self.base(dias=10)
        self.reloj(0, hrv=60, fc=50, sueno=7.5)
        self.assertEqual(rec.lectura_recuperacion(self.cliente, HOY)['nivel'], 'verde')

    def test_variabilidad_y_pulso_con_ultimos_valores(self):
        self.reloj(2, hrv=55, fc=59, sueno=7.8)
        self.reloj(1, hrv=81, fc=58, sueno=6.6)
        self.reloj(0, hrv=32, fc=58, sueno=7.9)
        v = variabilidad(self.cliente, HOY)
        self.assertEqual(v['ultimos'], '55 · 81 · 32')
        self.assertEqual(v['dias_con_dato'], 3)
        self.assertIsNone(v['media'])
        p = pulso(self.cliente, HOY)
        self.assertEqual(p['ultimos'], '59 · 58 · 58')

    def test_pulso_alto_sale_en_rojo(self):
        self.base(dias=10, fc=52)
        self.reloj(0, hrv=50, fc=58, sueno=7.5)
        p = pulso(self.cliente, HOY)
        self.assertIn(p['media'], (52, 53))  # la media de la gráfica incluye hoy
        self.assertTrue(p['puntos'][-1]['bajo'])
        self.assertFalse(p['puntos'][0]['bajo'])

    def test_pagina(self):
        self.reloj(1, hrv=81, fc=58, sueno=6.6)
        self.reloj(0, hrv=32, fc=58, sueno=7.9)
        self.client.force_login(self.user)
        r = self.client.get(reverse('clientes:cuerpo'))
        self.assertContains(r, 'Sin media aún')
        self.assertContains(r, 'Últimas mañanas: <strong>81 · 32</strong> ms', html=False)
        self.assertContains(r, 'Pulso en reposo cada mañana')
        self.assertContains(r, 'la franja de lo normal sale cuando haya 5 mañanas (llevo 2)')
        self.assertGreaterEqual(r.content.decode().count('class="info"'), 5)
        self.assertContains(r, 'aria-label="Cómo funciona"')
