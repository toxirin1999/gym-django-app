"""Revisión del 8-nov (adelantada al 7-nov, con el Día 5 guardado).

Ahora:
- El porcentaje dice con qué se compara: «Últimos 7 días: un 33 % por debajo de
  tu media de las 4 semanas anteriores».
- El ACWR pasa a «Tendencia de carga» con su referencia («7 días frente a 42,
  ponderados»); los umbrales no cambian.

Cuerpo:
- «Tus señales no piden descanso extra» frente a «Hoy toca descanso según el plan».
- Sin «pido 10»: cuántas mañanas, en qué periodo y que no hace falta que sean seguidas.

Comprobaciones del paquete del lunes:
- Fútbol: «Sueles jugar…» (inferido del historial), no «Mañana juegas».
- Propuesta de isquios: se evalúa con sesiones comparables (sin descarga, mismo
  tramo de reps); si no las hay, «Sin evidencia suficiente».
- Contador: el grupo de cada ejercicio del plan sale del catálogo, como en lo hecho.
"""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from entrenos.models import SemanaPlanGym
from entrenos.services.estado_carga_service import _texto_ratio
from entrenos.services.evolucion_muscular_service import comparar_ejercicios
from entrenos.tests_evolucion_muscular import _DatosEntrenoMixin

PLANTILLAS = Path(settings.BASE_DIR) / 'clientes' / 'templates' / 'clientes'


def _estado(**extra):
    base = {'respuesta': 'vas_bien', 'carga': {'ratio': 0.67}, 'malos_5': 1, 'dias_5': 5,
            'buenos_14': 7, 'dias_14': 10, 'esfuerzo': {'subiendo': False}, 'molestias': []}
    base.update(extra)
    return base


class Ahora(SimpleTestCase):
    def test_porcentaje_con_su_referencia(self):
        self.assertEqual(_texto_ratio(0.67), 'un 33 % por debajo de tu media de las 4 semanas anteriores')
        self.assertEqual(_texto_ratio(1.02), 'como tu media de las 4 semanas anteriores')

    def test_tendencia_con_su_referencia(self):
        src = (PLANTILLAS / 'dashboard_silencioso_preview.html').read_text(encoding='utf-8')
        self.assertIn('<span>Carga 7 días</span>', src)
        self.assertIn('metric-name">Tendencia de carga</span>', src)
        vista = (Path(settings.BASE_DIR) / 'clientes' / 'views.py').read_text(encoding='utf-8')
        self.assertIn("f'Últimos 7 días: {_texto_ratio(float(ratio))}'", vista)
        self.assertIn("'Bajando' if acwr < 0.8 else ('Estable' if acwr <= 1.3 else 'Subiendo rápido')", vista)
        self.assertIn("f'7 días frente a 42, ponderados · {acwr:.2f}'", vista)


class Cuerpo(SimpleTestCase):
    def test_descanso_dice_que_son_tus_senales(self):
        from entrenos.services.panel_cuerpo_service import tres_preguntas
        descanso, pasas, mas = tres_preguntas(_estado())
        self.assertEqual(descanso['porque'], 'Tus señales no piden descanso extra: 1 de 5 mañanas con dato de los '
                                             'últimos 5 días por debajo de lo normal. Lo pediría con 3, seguidas o no.')
        self.assertEqual(pasas['porque'], 'Últimos 7 días: un 33 % por debajo de tu media de las 4 semanas anteriores.')
        self.assertEqual(mas['porque'], '7 mañanas buenas en los últimos 14 días; hacen falta 10, seguidas o no; '
                                        'el reloj solo pudo comparar 10 de los 14.')
        self.assertNotIn('pido', mas['porque'])

    def test_si_toca_descansar_por_senales(self):
        from entrenos.services.panel_cuerpo_service import tres_preguntas
        descanso = tres_preguntas(_estado(respuesta='descansa', malos_5=3, carga={'ratio': 1.0}))[0]
        self.assertEqual(descanso['porque'], 'Tus señales piden descanso: 3 de 5 mañanas con dato de los '
                                             'últimos 5 días por debajo de lo normal en ti.')

    def test_descanso_del_plan_aparte(self):
        from entrenos.services.panel_cuerpo_service import descanso_del_plan
        hoy = date(2026, 11, 8)
        with patch('entrenos.services.semana_rutina_service.semana_segun_cola',
                   return_value={'dias': {hoy: {'tipo': 'descanso'}}}):
            self.assertTrue(descanso_del_plan(None, hoy))
        with patch('entrenos.services.semana_rutina_service.semana_segun_cola',
                   return_value={'dias': {hoy: {'tipo': 'descanso', 'aplazada': 'Día 4'}}}):
            self.assertFalse(descanso_del_plan(None, hoy))
        src = (PLANTILLAS / 'cuerpo.html').read_text(encoding='utf-8')
        self.assertIn('Hoy toca descanso según el plan: es el día libre de la semana, no una señal de tu cuerpo.', src)
        self.assertIn('seguidas o no; un día sin dato del reloj no cuenta como buena', src)


class EvaluacionComparable(_DatosEntrenoMixin, TestCase):
    def test_distinto_tramo_de_reps_no_se_compara(self):
        self._ej(40, 'Buenos Días (Good Mornings)', 50, 12, 'Isquios')
        self._ej(5, 'Buenos Días (Good Mornings)', 70, 6, 'Isquios')
        normal = comparar_ejercicios(self.cliente, self.HOY, 30)[0]
        estricto = comparar_ejercicios(self.cliente, self.HOY, 30, estricto=True)[0]
        self.assertIsNotNone(normal['pct'])
        self.assertIsNone(estricto['pct'])
        self.assertTrue(estricto['cambio_rango'])

    def test_sin_las_semanas_de_descarga(self):
        self._ej(40, 'Curl Femoral Tumbado', 40, 12, 'Isquios')
        self._ej(5, 'Curl Femoral Tumbado', 30, 12, 'Isquios')
        fecha = self.HOY - timedelta(days=5)
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=fecha - timedelta(days=fecha.weekday()),
                                     semana_plan=44, descarga=True, origen='descarga_programada')
        estricto = comparar_ejercicios(self.cliente, self.HOY, 30, estricto=True)[0]
        self.assertIsNone(estricto['ahora'])
        self.assertIsNone(estricto['pct'])


class ContadorCatalogo(TestCase):
    def test_el_plan_usa_el_grupo_del_catalogo(self):
        from collections import Counter
        from django.contrib.auth.models import User
        from entrenos.services import marcador_semanal_service as m
        from rutinas.models import EjercicioBase
        EjercicioBase.objects.create(nombre='Sentadilla Búlgara', grupo_muscular='Cuádriceps',
                                     tipo_progresion='peso_reps')
        cliente = User.objects.create_user('contador_catalogo', password='x').cliente_perfil
        lunes = date(2026, 11, 2)
        ent = {'rutina_nombre': 'Dia 5', 'ejercicios': [
            {'nombre': 'Sentadilla Búlgara', 'grupo_muscular': 'gluteos', 'series': 3}]}

        class P:
            def generar_entrenamiento_para_fecha(self, fecha):
                return ent if fecha == lunes else None
        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=P()):
            plan, _ = m.series_plan_semana(cliente, lunes)
        self.assertEqual(plan, Counter({'cuádriceps': 3, 'glúteos': 1.5}))
