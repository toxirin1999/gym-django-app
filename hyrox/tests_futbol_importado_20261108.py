"""8-nov-2026 · Al importar un partido de Strava, la app dice qué hace el plan con él."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from entrenos.models import ActividadRealizada, EntrenoRealizado
from hyrox.views import _msg_futbol_importado
from rutinas.models import Rutina


class MensajeFutbolImportado(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('futbol_importado_20261108', password='x').cliente_perfil
        self.hoy = timezone.localdate()

    def _partido(self, fecha, **extra):
        datos = {'duracion_minutos': 60, 'rpe_medio': 7.5, 'fuente': 'strava'}
        datos.update(extra)
        return ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Fútbol', fecha=fecha,
                                                 **datos)

    def test_jugado_ayer(self):
        msg = _msg_futbol_importado(self.cliente, self._partido(self.hoy - timedelta(days=1)),
                                    'RPE estimado desde FC')
        self.assertEqual(msg, 'Fútbol registrado (60 min, RPE 7,5 estimado del pulso): cuenta como partido jugado. '
                              'La carga de la semana y la pierna de los dos días siguientes ya lo tienen en cuenta; '
                              'el briefing de tu próxima sesión dirá si cambia algo.')

    def test_hoy_antes_del_gimnasio(self):
        msg = _msg_futbol_importado(self.cliente, self._partido(self.hoy, rpe_medio=8), 'RPE manual')
        self.assertIn('(60 min, RPE 8)', msg)
        self.assertTrue(msg.endswith('Si entrenas hoy después, la pierna se ajusta a este esfuerzo.'))

    def test_hoy_con_el_gimnasio_ya_hecho(self):
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=self.hoy)
        msg = _msg_futbol_importado(self.cliente, self._partido(self.hoy), 'RPE manual')
        self.assertNotIn('Si entrenas hoy', msg)
