"""7-nov-2026 · Plan anual: el calendario dice qué toca y cuándo.

- P1: «RPE 6», no «RPE 6–6».
- P2: en vez del porqué genérico («añade progresión gradual»), lo que cambia
  esta semana, como Plan, y que es la pauta general (el objetivo exacto, en la sesión).
- P3/P4: sin «Máximos registrados» ni objetivos teóricos Helms (+7,5 %).
  Los máximos siguen para el cálculo de respaldo cuando falta historial.
- P5: en descarga, el rango de cada ejercicio; en Fuerza — Hipertrofia,
  «Básicos: 4–6 reps» y «Resto: según ejercicio» (brazos, hombros y gemelos
  tienen sus rangos; el exacto, en la sesión).
- P6: el resumen semanal dice «Sesiones previstas» (no «Entrenos»), cuenta las
  hechas aparte y las marca en su día; sin minutos estimados; «…»/«–» mientras
  carga, no un cero.
"""

from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from entrenos.models import SemanaPlanGym

PLANTILLA = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos' / 'vista_plan_calendario.html'


class Plantilla(SimpleTestCase):
    def setUp(self):
        self.src = PLANTILLA.read_text(encoding='utf-8')

    def test_sin_maximos_ni_objetivos_teoricos(self):
        self.assertNotIn('Lo que el plan sabe de ti', self.src)
        self.assertNotIn('incremento teórico Helms', self.src)
        self.assertNotIn('id="projections-container"', self.src)

    def test_sin_porque_generico(self):
        self.assertNotIn('añade progresión gradual', self.src)
        self.assertNotIn('¿Por qué esta fase?', self.src)
        self.assertIn('{% for linea in cambios_semana.lineas %}', self.src)
        self.assertIn('Es la pauta general de la semana; el objetivo exacto de cada ejercicio está en su sesión.',
                      self.src)

    def test_rpe_y_reps(self):
        self.assertIn('{% if parametros_fase.rpe_min == parametros_fase.rpe_max %}{{ parametros_fase.rpe_min }}',
                      self.src)
        self.assertIn('<div class="cp-stat-val">El de cada ejercicio</div>', self.src)
        self.assertIn('Básicos: {{ parametros_fase.reps_min }}–{{ parametros_fase.reps_max }} reps', self.src)
        self.assertIn('Resto: según ejercicio; el rango exacto, en la sesión', self.src)

    def test_resumen_semanal_previstas_y_hechas(self):
        self.assertIn('<div class="summary-label">Sesiones previstas</div>', self.src)
        self.assertIn('<div class="summary-label">Hechas</div>', self.src)
        self.assertNotIn('Minutos', self.src)
        self.assertNotIn('summaryMinutes', self.src)
        self.assertNotIn('<div class="summary-label">Entrenos</div>', self.src)
        self.assertIn('<div class="summary-value" id="summaryWorkouts">…</div>', self.src)
        self.assertIn("fechasHechas = new Set(data.hechas || []);", self.src)


class Parametros(SimpleTestCase):
    def test_reps_secundarios_del_bloque(self):
        from entrenos.views import _parametros_fase_plan
        p = _parametros_fase_plan({'nombre': 'Fuerza — Hipertrofia', 'rep_range': '4-6',
                                   'reps_secundarios': '8-12'}, {})
        self.assertEqual((p['reps_min'], p['reps_max'], p['reps_secundarios']), (4, 6, '8-12'))
        self.assertIsNone(_parametros_fase_plan({'rep_range': '10-15'}, {})['reps_secundarios'])


class FechasHechas(TestCase):
    def test_solo_sesiones_de_gym_del_mes(self):
        from entrenos.models import ActividadRealizada, EntrenoRealizado
        from entrenos.views import _fechas_hechas_mes
        from rutinas.models import Rutina
        cliente = User.objects.create_user('plan_anual_hechas_20261107', password='x').cliente_perfil
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=date(2026, 11, 2))
        EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=date(2026, 10, 31))
        ActividadRealizada.objects.create(cliente=cliente, tipo='futbol', titulo='Fútbol',
                                          fecha=date(2026, 11, 4), duracion_minutos=60)
        self.assertEqual(_fechas_hechas_mes(cliente, 2026, 11), ['2026-11-02'])


class Descarga(TestCase):
    def test_semana_de_descarga(self):
        from entrenos.views import _semana_de_descarga_plan_anual
        cliente = User.objects.create_user('plan_anual_20261107', password='x').cliente_perfil
        sabado = date(2026, 11, 7)
        self.assertFalse(_semana_de_descarga_plan_anual(cliente, sabado, {'nombre': 'Fuerza — Hipertrofia'}))
        self.assertTrue(_semana_de_descarga_plan_anual(cliente, sabado, {'nombre': 'Descarga Activa'}))
        SemanaPlanGym.objects.create(cliente=cliente, lunes=date(2026, 11, 2), semana_plan=44, descarga=True,
                                     origen='descarga_programada')
        self.assertTrue(_semana_de_descarga_plan_anual(cliente, sabado, {'nombre': 'x'}))

    def test_la_pagina_renderiza(self):
        from django.urls import reverse
        user = User.objects.create_user('plan_anual_pagina_20261107', password='x')
        self.client.force_login(user)
        r = self.client.get(reverse('entrenos:vista_plan_anual', args=[user.cliente_perfil.id]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Máximos registrados')
