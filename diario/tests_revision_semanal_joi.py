from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import ProsocheDiario, ProsocheMes
from diario.services.lectura_semanal import (
    agregar_semana,
    generar_revision_semanal,
    periodo_semana_completa,
)
from joi.models import MensajeJOI


class RevisionSemanalJOITests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('semana', password='pass123')
        self.cliente = self.user.cliente_perfil
        self.url = reverse('diario:lectura_semanal')
        self.client.force_login(self.user)

    @patch('diario.services.lectura_semanal.timezone.localdate', return_value=date(2026, 7, 29))
    def test_periodo_es_ultima_semana_completa_lunes_domingo(self, _localdate):
        inicio, fin, clave = periodo_semana_completa()
        self.assertEqual((inicio, fin), (date(2026, 7, 20), date(2026, 7, 26)))
        self.assertEqual(clave, '2026-07-20_2026-07-26')

    @patch('diario.services.lectura_semanal.timezone.localdate', return_value=date(2026, 7, 29))
    def test_get_es_puro_y_recupera_solo_el_mensaje_del_periodo(self, _localdate):
        MensajeJOI.objects.create(
            user=self.user, trigger='resumen_semanal', mensaje='Lectura real de JOI',
            contexto={'version_contrato': 1, 'periodo': {'inicio': '2026-07-20', 'fin': '2026-07-26', 'clave': '2026-07-20_2026-07-26'}},
        )
        with patch('diario.services.lectura_semanal.generar_mensaje_joi') as generar:
            response = self.client.get(self.url)
        generar.assert_not_called()
        self.assertEqual(MensajeJOI.objects.count(), 1)
        self.assertContains(response, 'Lectura real de JOI')
        self.assertContains(response, reverse('diario:dashboard_diario'))
        self.assertNotContains(response, 'Lo que JOI ve')

    @patch('diario.services.lectura_semanal.timezone.localdate', return_value=date(2026, 7, 29))
    def test_agregar_semana_acepta_inicio_fin_y_detecta_diario_sin_gym(self, _localdate):
        mes = ProsocheMes.objects.create(usuario=self.user, mes='7', año=2026)
        ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=date(2026, 7, 22),
            persona_quiero_ser='Ser paciente', que_ha_ido_bien='Escuché con calma',
        )
        datos = agregar_semana(self.user, inicio=date(2026, 7, 20), fin=date(2026, 7, 26))
        self.assertTrue(datos['hay_senales'])
        self.assertEqual(datos['presencia']['cierres'], 1)
        self.assertEqual(datos['periodo']['clave'], '2026-07-20_2026-07-26')
        self.assertIn('gestos', datos)
        self.assertIn('simbiosis', datos)
        self.assertIn('logos', datos)
        self.assertIn('gym', datos)

    @patch('diario.services.lectura_semanal.generar_mensaje_joi')
    def test_generacion_deduplica_por_clave_y_guarda_contrato(self, generar):
        inicio, fin = date(2026, 7, 20), date(2026, 7, 26)
        existente = MensajeJOI.objects.create(
            user=self.user, trigger='resumen_semanal', mensaje='Ya existe',
            contexto={'periodo': {'clave': '2026-07-20_2026-07-26'}},
        )
        resultado = generar_revision_semanal(self.cliente, inicio=inicio, fin=fin)
        self.assertEqual(resultado, existente)
        generar.assert_not_called()

    @patch('diario.services.lectura_semanal.generar_mensaje_joi')
    def test_fallo_no_finge_exito_y_permite_reintento(self, generar):
        inicio, fin = date(2026, 7, 20), date(2026, 7, 26)
        mes = ProsocheMes.objects.create(usuario=self.user, mes='7', año=2026)
        ProsocheDiario.objects.create(prosoche_mes=mes, fecha=date(2026, 7, 22), que_ha_ido_bien='Algo')
        generar.side_effect = [None, MensajeJOI.objects.create(
            user=self.user, trigger='resumen_semanal', mensaje='Segundo intento', contexto={}
        )]

        primero = generar_revision_semanal(self.cliente, inicio=inicio, fin=fin)
        segundo = generar_revision_semanal(self.cliente, inicio=inicio, fin=fin)

        self.assertIsNone(primero)
        self.assertEqual(segundo.mensaje, 'Segundo intento')
        self.assertEqual(generar.call_count, 2)
        contexto = generar.call_args.args[2]
        self.assertEqual(contexto['version_contrato'], 1)
        self.assertEqual(contexto['periodo']['clave'], '2026-07-20_2026-07-26')

    @patch('diario.services.lectura_semanal.generar_revision_semanal')
    def test_post_usa_prg_y_muestra_error_si_generacion_falla(self, generar):
        generar.return_value = None
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, self.url)
        self.assertContains(response, 'No se pudo generar')

    def test_vacio_tiene_copy_honesto_y_boton_post(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Todavía no hay una lectura de JOI')
        self.assertContains(response, 'method="post"')
        self.assertNotContains(response, 'Esta semana no dice quién eres')


class TareaRevisionSemanalTests(TestCase):
    @patch('joi.tasks.timezone.localdate', return_value=date(2026, 7, 27))
    @patch('diario.services.lectura_semanal.generar_revision_semanal')
    def test_task_usa_servicio_comun_y_cuenta_solo_mensajes(self, generar, _localdate):
        user = User.objects.create_user('task-semana')
        generar.return_value = MensajeJOI.objects.create(
            user=user, trigger='resumen_semanal', mensaje='Hecho', contexto={}
        )
        from joi.tasks import generar_resumen_semanal_joi
        resultado = generar_resumen_semanal_joi.run()
        self.assertEqual(resultado['generados'], 1)
        args = generar.call_args
        self.assertEqual(args.kwargs['inicio'], date(2026, 7, 20))
        self.assertEqual(args.kwargs['fin'], date(2026, 7, 26))

    @patch('joi.tasks.timezone.localdate', return_value=date(2026, 7, 28))
    def test_task_solo_corre_lunes(self, _localdate):
        from joi.tasks import generar_resumen_semanal_joi
        self.assertEqual(generar_resumen_semanal_joi.run()['omitido'], 'no es lunes')
