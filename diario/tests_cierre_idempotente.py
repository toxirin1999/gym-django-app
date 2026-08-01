import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.forms import CierreDiarioForm
from diario.models import (
    CierreNocturnoOperacion,
    Gesto,
    ProsocheDiario,
    ProsocheMes,
    ReflexionLibre,
    RegistroGesto,
    SeguimientoVires,
)
from diario.services.cierre_service import ConflictoVersionCierre, ejecutar_cierre_nocturno


class CierreDiarioFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-form')
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', estado='activo')

    def form(self, **overrides):
        data = {
            'reflexion_libre': 'Un día consciente',
            'friccion_no': '3',
            'cuerpo_cierre': 'ligero',
            'estado_animo_noche': '4',
            'habitos_completados': json.dumps([self.gesto.pk]),
            'idempotency_key': str(uuid.uuid4()),
            'expected_version': '0',
            **overrides,
        }
        return CierreDiarioForm(data=data, usuario=self.user)

    def test_post_vacio_no_es_confirmacion_valida(self):
        self.assertFalse(CierreDiarioForm(data={}, usuario=self.user).is_valid())

    def test_friccion_es_eleccion_consciente_y_animo_pm_restringido(self):
        self.assertFalse(self.form(friccion_no='').is_valid())
        self.assertFalse(self.form(estado_animo_noche='3').is_valid())

    def test_habitos_deben_ser_lista_de_ids_activos_del_usuario(self):
        ajeno = User.objects.create_user('ajeno')
        gesto_ajeno = Gesto.objects.create(usuario=ajeno, nombre='Ajeno', estado='activo')
        self.assertFalse(self.form(habitos_completados=json.dumps([gesto_ajeno.pk])).is_valid())
        self.assertFalse(self.form(habitos_completados='{"id": 1}').is_valid())

    def test_reflexion_tiene_maximo_validado(self):
        self.assertFalse(self.form(reflexion_libre='x' * 5001).is_valid())


class CierreNocturnoCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-command')
        self.hoy = timezone.localdate()
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', estado='activo')

    def payload(self, **overrides):
        return {
            'reflexion_libre': 'Hoy sostuve el límite.',
            'friccion_no': 4,
            'cuerpo_cierre': 'cargado',
            'estado_animo_noche': 2,
            'habitos_completados': [self.gesto.pk],
            'simbiosis_respuesta': '',
            **overrides,
        }

    def ejecutar(self, token=None, expected=0, **payload):
        return ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=self.hoy,
            payload=self.payload(**payload),
            idempotency_key=token or uuid.uuid4(),
            expected_version=expected,
        )

    def test_crea_padres_solo_al_ejecutar_y_no_pisa_animo_am(self):
        resultado = self.ejecutar()
        entrada = resultado.entrada
        entrada.estado_animo = 5
        entrada.save(update_fields=['estado_animo'])
        self.ejecutar(expected=1, reflexion_libre='Texto cambiado')
        entrada.refresh_from_db()
        self.assertEqual(entrada.estado_animo, 5)
        self.assertEqual(entrada.estado_animo_noche, 2)
        self.assertEqual(entrada.cierre_version, 2)
        self.assertIsNotNone(entrada.cierre_confirmado_en)

    def test_replay_mismo_token_y_hash_con_token_distinto_son_noop(self):
        token = uuid.uuid4()
        primero = self.ejecutar(token=token)
        replay = self.ejecutar(token=token, expected=0)
        mismo_hash = self.ejecutar(expected=1)
        self.assertEqual(replay.operacion.pk, primero.operacion.pk)
        self.assertEqual(mismo_hash.entrada.cierre_version, 1)
        self.assertEqual(CierreNocturnoOperacion.objects.count(), 2)
        self.assertEqual(CierreNocturnoOperacion.objects.filter(result_version=1).count(), 1)

    def test_expected_version_obsoleta_da_conflicto(self):
        self.ejecutar()
        with self.assertRaises(ConflictoVersionCierre):
            self.ejecutar(expected=0, reflexion_libre='Cambio real')

    def test_sincronizacion_gestos_es_determinista(self):
        self.ejecutar()
        self.assertTrue(RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy).exists())
        self.ejecutar(expected=1, reflexion_libre='Cambio', habitos_completados=[])
        self.assertFalse(RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy).exists())


class PresenciaCierreViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-view', password='x')
        self.client.force_login(self.user)
        self.url = reverse('diario:presencia_cierre')
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', estado='activo')

    def data(self, **overrides):
        return {
            'reflexion_libre': 'Cierre real',
            'friccion_no': '3',
            'cuerpo_cierre': '',
            'estado_animo_noche': '4',
            'habitos_completados': json.dumps([self.gesto.pk]),
            'idempotency_key': str(uuid.uuid4()),
            'expected_version': '0',
            **overrides,
        }

    def test_get_es_puro(self):
        response = self.client.get(self.url)
        self.assertFalse(ProsocheMes.objects.exists())
        self.assertFalse(ProsocheDiario.objects.exists())
        self.assertFalse(SeguimientoVires.objects.exists())
        self.assertFalse(RegistroGesto.objects.exists())
        html = response.content.decode()
        self.assertIn('<option value="" selected>Elige conscientemente</option>', html)
        self.assertNotIn('<option value="1" selected>', html)
        self.assertNotIn('<option value="2" selected>', html)
        self.assertNotIn('<option value="4" selected>', html)
        self.assertNotIn('<option value="5" selected>', html)

    def test_post_invalido_ajax_no_escribe(self):
        response = self.client.post(self.url, {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIn(response.status_code, (400, 422))
        self.assertFalse(ProsocheDiario.objects.exists())

    @patch('diario.services.cierre_service.ejecutar_enriquecimiento_cierre', side_effect=RuntimeError('IA caída'))
    def test_fallo_ia_conserva_confirmacion_y_es_retryable(self, _enriquecer):
        response = self.client.post(self.url, self.data(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['confirmacion'], 'Cierre guardado.')
        entrada = ProsocheDiario.objects.get()
        self.assertIsNotNone(entrada.cierre_confirmado_en)
        self.assertEqual(CierreNocturnoOperacion.objects.get().estado, 'failed')

    @patch('diario.services.cierre_service.ejecutar_enriquecimiento_cierre')
    def test_post_tradicional_siempre_prg(self, enriquecer):
        enriquecer.return_value = {'respuesta_joi': 'Lectura visible'}
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302)
        self.assertIn('cierre_operacion=', response.url)

    def test_template_tiene_un_solo_listener_y_no_submit_nativo(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertEqual(html.count("addEventListener('submit'"), 1)
        self.assertNotIn(".submit();", html)
        self.assertIn('idempotency_key', html)
        self.assertIn('expected_version', html)

    def test_lectura_ofrece_edicion_explicita_y_editar_precarga_version(self):
        mes = ProsocheMes.objects.create(usuario=self.user, mes=timezone.localdate().strftime('%B'), año=timezone.localdate().year)
        entrada = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=timezone.localdate(), cierre_confirmado_en=timezone.now(),
            cierre_version=3, reflexiones_dia='Texto anterior', estado_animo_noche=5,
            respuesta_joi_cierre='Lectura anterior',
        )
        SeguimientoVires.objects.create(usuario=self.user, fecha=timezone.localdate(), nivel_estres=4, cuerpo_cierre='cargado')
        lectura = self.client.get(self.url).content.decode()
        self.assertIn('id="editar-cierre"', lectura)
        self.assertIn('id="cierre-form" style="display:none"', lectura)
        edicion = self.client.get(f'{self.url}?editar=1').content.decode()
        self.assertNotIn('id="cierre-form" style="display:none"', edicion)
        self.assertIn('value="3"', edicion)
        self.assertIn('<option value="5" selected>Pleno</option>', edicion)

    @patch('joi.services.enriquecer_cierre', return_value={'interacciones': [], 'micro_verdad': None})
    @patch('joi.services.parsear_cierre_diario', return_value={'personas': [], 'etiquetas': []})
    @patch('joi.services.generar_respuesta_cierre', side_effect=[RuntimeError('cae'), 'Lectura recuperada'])
    def test_token_nuevo_mismo_hash_reintenta_operacion_canonica_sin_duplicar(self, _respuesta, _parseo, _enriq):
        primero = self.client.post(self.url, self.data(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(primero.status_code, 200)
        canonical = CierreNocturnoOperacion.objects.get(result_version=1)
        self.assertEqual(canonical.estado, 'failed')
        segundo = self.client.post(
            self.url, self.data(expected_version='1'), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(segundo.status_code, 200)
        canonical.refresh_from_db()
        self.assertEqual(canonical.estado, 'completed')
        self.assertEqual(ProsocheDiario.objects.get().cierre_version, 1)
        self.assertEqual(ReflexionLibre.objects.count(), 1)
        self.assertEqual(CierreNocturnoOperacion.objects.count(), 2)


class EstadoDiarioCierreTests(TestCase):
    def test_solo_cierre_confirmado_cuenta_como_noche(self):
        from diario.services.estado_diario import calcular_estado_diario_hoy
        falso = ProsocheDiario(reflexiones_dia='texto sin confirmar')
        self.assertEqual(calcular_estado_diario_hoy(falso)['estado'], 'sin_entrada')
        falso.cierre_confirmado_en = timezone.now()
        self.assertEqual(calcular_estado_diario_hoy(falso)['estado'], 'solo_noche')


class PromptCierreJOITests(TestCase):
    @patch('joi.services._llamar_haiku', return_value='Respuesta')
    @patch('joi.services._bloque_manual', return_value='MANUAL')
    @patch('joi.services._bloque_narrativa', return_value='NARRATIVA')
    def test_orden_narrativa_manual_trigger_sin_narrativa_duplicada(self, narrativa, manual, llamar):
        from joi.services import generar_respuesta_cierre
        user = User.objects.create_user('prompt-cierre')
        self.assertEqual(generar_respuesta_cierre('Mi cierre', {}, user), 'Respuesta')
        manual.assert_called_once_with(user, incluir_narrativa=False)
        prompt = llamar.call_args.args[0]
        self.assertLess(prompt.index('NARRATIVA'), prompt.index('MANUAL'))
        self.assertLess(prompt.index('MANUAL'), prompt.index('TRIGGER — CIERRE DE HOY'))
        self.assertEqual(prompt.count('NARRATIVA'), 1)

    @patch('joi.services._llamar_haiku', side_effect=RuntimeError('sin red'))
    def test_fallback_de_voz_es_vacio(self, _llamar):
        from joi.services import generar_respuesta_cierre
        user = User.objects.create_user('prompt-fallback')
        self.assertEqual(generar_respuesta_cierre('Mi cierre', {}, user), '')
