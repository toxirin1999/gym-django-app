"""7-nov-2026 · Módulos archivados y Hyrox congelado.

- Vida/diario, logros, estoico, nutrición y la habitación de JOI: archivados.
- Hyrox: congelado (fuera de Memoria).
- Strava y lesiones se mantienen.
"""

import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.modulos import archivado, hyrox_congelado

NAV = Path(settings.BASE_DIR) / 'templates' / 'includes' / 'bottom_nav.html'
AHORA = Path(settings.BASE_DIR) / 'clientes' / 'templates' / 'clientes' / 'dashboard_silencioso_preview.html'
BRIEFING = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos' / 'briefing_entrenamiento.html'


class Ajustes(SimpleTestCase):
    def test_modulos_archivados_y_hyrox_congelado(self):
        for nombre in ('diario', 'logros', 'estoico', 'nutricion', 'joi_habitacion'):
            self.assertTrue(archivado(nombre), nombre)
        self.assertFalse(archivado('entrenos'))
        self.assertTrue(hyrox_congelado())


class Navegacion(SimpleTestCase):
    def test_sin_vida_en_la_barra(self):
        src = NAV.read_text(encoding='utf-8')
        self.assertNotIn('diario:dashboard_diario', src)
        self.assertNotIn('<strong>Vida</strong>', src)
        self.assertIn('grid-template-columns:repeat(4,1fr)', src)

    def test_strava_se_mantiene(self):
        self.assertIn("hyrox:strava_reconciliacion", AHORA.read_text(encoding='utf-8'))
        self.assertIn('Activa Strava antes de empezar', BRIEFING.read_text(encoding='utf-8'))
        self.assertEqual(reverse('hyrox:strava_webhook'), '/hyrox/strava/webhook/')


class AhoraNoMandaAModulosArchivados(TestCase):
    def setUp(self):
        from diario.models import ProsocheDiario, ProsocheMes
        self.user = User.objects.create_user('archivo_20261107', password='x')
        hoy = timezone.localdate()
        mes = ProsocheMes.objects.create(usuario=self.user, mes=str(hoy.month), año=hoy.year)
        ProsocheDiario.objects.create(prosoche_mes=mes, fecha=hoy, persona_quiero_ser='x',
                                      apertura_confirmada_en=timezone.now())

    def test_sin_aviso_de_cierre_del_diario(self):
        from core.organismo import _check_observando
        self.assertIsNone(_check_observando(self.user))

    @override_settings(MODULOS_ARCHIVADOS=())
    def test_sin_archivar_sigue_avisando(self):
        from core.organismo import _check_observando
        estado = _check_observando(self.user)
        self.assertIsNotNone(estado)
        self.assertEqual(estado['motivo'], 'diario_manana_hecha')


class MemoriaSinHyrox(TestCase):
    def setUp(self):
        from hyrox.models import HyroxObjective
        self.user = User.objects.create_user('archivo_hyrox_20261107', password='x')
        self.cliente = self.user.cliente_perfil
        HyroxObjective.objects.create(cliente=self.cliente,
                                      fecha_evento=timezone.localdate() + datetime.timedelta(days=60))
        self.client.force_login(self.user)

    def _contexto(self):
        r = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertEqual(r.status_code, 200)
        return r.context

    def test_congelado_no_aparece(self):
        r = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertIsNone(r.context['hyrox_obj'])
        self.assertNotContains(r, 'Hyrox · Perfil base')

    @override_settings(HYROX_CONGELADO=False)
    def test_descongelado_vuelve(self):
        self.assertIsNotNone(self._contexto()['hyrox_obj'])
