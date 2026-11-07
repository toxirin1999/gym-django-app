"""7-nov-2026 · Repaso del Día 5 de la descarga (sábado).

1. Sin ⚡ Estancado ni aviso de estancamiento en descarga.
2/5. La frase de descarga cita la serie de la que sale el peso y «Vuelve a» parte
     de la que más se acercó al rango (extensiones 15 × 4 @10 y 10 × 7 @9 → 10 × 7).
3. Dips a por 12 (no 13): es el tope de la descarga (máximo del rango − 3). Sin cambio.
4. En descarga, la ejecución de hoy se compara con la última vez de verdad.
6. «Vuelve a…» avisa si el bloque nuevo le cambia el rango.
7. «Lo que viene» anuncia el bloque nuevo.
"""

from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from entrenos.models import SemanaPlanGym
from entrenos.services.sesion_descarga_service import reps_descarga

ENTRENOS = Path(settings.BASE_DIR) / 'entrenos'


class Nota1SinEstancadoEnDescarga(SimpleTestCase):
    def test_briefing_y_sesion(self):
        briefing = (ENTRENOS / 'services' / 'briefing_service.py').read_text(encoding='utf-8')
        self.assertIn('estancados_hoy = [n for n in nombres_hoy if n not in en_descarga and any(', briefing)
        vistas = (ENTRENOS / 'views.py').read_text(encoding='utf-8')
        self.assertEqual(vistas.count("or _es_semana_descarga(cliente, fecha_obj):"), 2)


class Notas2y5Referencia(SimpleTestCase):
    def test_vuelve_a_la_serie_que_mas_se_acerco(self):
        from types import SimpleNamespace
        from entrenos.services.cerebro_carga_service import _referencia_mas_cercana
        lectura = {'referencia': {'peso': 15, 'reps': 4, 'reps_mediana': 4, 'en_rango': True},
                   'series': [{'peso': 15, 'reps': 4, 'rpe': 10}, {'peso': 10, 'reps': 7, 'rpe': 9}],
                   'entreno': SimpleNamespace()}
        with patch('entrenos.services.ultima_sesion_service.rango_de_sesion', return_value=(10, 15)):
            ref = _referencia_mas_cercana(lectura, 'Extensiones sobre la Cabeza con Mancuerna')
        self.assertEqual((ref['peso'], ref['reps_mediana']), (10, 7))
        with patch('entrenos.services.ultima_sesion_service.rango_de_sesion', return_value=(4, 6)):
            self.assertEqual(_referencia_mas_cercana(lectura, 'x')['peso'], 15)

    def test_la_frase_de_descarga_cita_la_serie_del_peso(self):
        src = (ENTRENOS / 'services' / 'sesion_descarga_service.py').read_text(encoding='utf-8')
        self.assertIn("({cuando} {kg(cita_peso)} kg × {cita_reps})", src)


class Nota3DipsTope(SimpleTestCase):
    def test_tope_de_la_descarga(self):
        self.assertEqual(reps_descarga(16, 10, 15), 12)


class Nota4ComparaConLaUltimaDeVerdad(SimpleTestCase):
    def test_en_descarga_no_busca_reps_compatibles(self):
        src = (ENTRENOS / 'services' / 'cierre_entrenamiento_service.py').read_text(encoding='utf-8')
        self.assertIn('if es_descarga_hoy or reps_compatibles_con_objetivo(reps_candidato, reps_hoy):', src)


class Notas6y7BloqueNuevo(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('dia5_cierre_20261107', password='x').cliente_perfil
        hoy = timezone.localdate()
        self.hoy = hoy
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=hoy - timedelta(days=hoy.weekday()),
                                     semana_plan=44, descarga=True, origen='descarga_programada')

    def test_bloque_nuevo_tras_la_descarga(self):
        from entrenos.services.bloque_siguiente_service import bloque_nuevo
        nuevo = bloque_nuevo(self.cliente, self.hoy)
        lunes = self.hoy - timedelta(days=self.hoy.weekday()) + timedelta(days=7)
        self.assertEqual(nuevo['nombre'], 'Fuerza — Hipertrofia')
        self.assertEqual(nuevo['frase'], f'El lunes {lunes:%d/%m} empieza Fuerza — Hipertrofia: 4-6 reps en '
                                         f'los básicos y 8-12 en el resto, con los mismos ejercicios.')

    def test_aviso_de_rango_nuevo(self):
        from entrenos.services.cerebro_carga_service import _aviso_rango_nuevo
        with patch('entrenos.services.bloque_siguiente_service.rango_proximo', return_value='6-8'):
            texto = _aviso_rango_nuevo(self.cliente, 'Dips (Fondos en Pecho)', self.hoy, (15, 20))
        self.assertEqual(texto, ' Con Fuerza — Hipertrofia va a 6-8 reps: el peso sale para ese rango.')
        with patch('entrenos.services.bloque_siguiente_service.rango_proximo', return_value='8-12'):
            self.assertEqual(_aviso_rango_nuevo(self.cliente, 'Sentadilla Búlgara', self.hoy, (8, 12)), '')

    def test_lo_que_viene_lo_anuncia(self):
        src = (ENTRENOS / 'services' / 'cierre_porque_service.py').read_text(encoding='utf-8')
        self.assertIn("nuevo = bloque_nuevo(cliente, fecha)", src)
