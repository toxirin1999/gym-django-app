import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import CierreNocturnoOperacion, Gesto, PersonaInterina, ReflexionLibre


class AnalisisCierreUnicoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('analisis-unico')
        self.client.force_login(self.user)
        self.precheck = reverse('diario:check_simbiosis_api')
        self.cierre = reverse('diario:presencia_cierre')

    def _post(self, texto, token='', **extra):
        return self.client.post(self.cierre, {
            'reflexion_libre': texto, 'friccion_no': '3', 'cuerpo_cierre': '',
            'estado_animo_noche': '4', 'habitos_completados': '[]',
            'simbiosis_respuesta': '', 'simbiosis_pregunta': 'falsificada',
            'analisis_cierre_token': token, 'idempotency_key': str(uuid.uuid4()),
            'expected_version': '0', **extra,
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    @patch('joi.services.generar_respuesta_cierre', return_value='JOI')
    @patch('joi.services.enriquecer_cierre')
    @patch('joi.services.parsear_cierre_diario')
    def test_precheck_y_post_reutilizan_una_interpretacion(self, parsear, enriquecer, _respuesta):
        parsear.return_value = {'personas': ['Ana'], 'impulsos': [], 'etiquetas': []}
        enriquecer.return_value = {'interacciones': [], 'micro_verdad': None}
        pre = self.client.post(
            self.precheck, json.dumps({'texto': 'Vi a Ana'}), content_type='application/json',
        ).json()
        response = self._post('Vi a Ana', pre['analisis_cierre_token'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parsear.call_count, 1)
        self.assertEqual(enriquecer.call_count, 1)

    @patch('joi.services.generar_respuesta_cierre', return_value='')
    @patch('joi.services.enriquecer_cierre', return_value={'interacciones': []})
    @patch('joi.services.parsear_cierre_diario', return_value={'personas': [], 'impulsos': [], 'etiquetas': []})
    def test_token_manipulado_regenera_exactamente_una_vez(self, parsear, enriquecer, _respuesta):
        pre = self.client.post(
            self.precheck, json.dumps({'texto': 'Texto'}), content_type='application/json',
        ).json()
        response = self._post('Texto', pre['analisis_cierre_token'] + 'x')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parsear.call_count, 2)
        self.assertEqual(enriquecer.call_count, 2)

    @patch('joi.services.enriquecer_cierre')
    @patch('joi.services.parsear_cierre_diario')
    def test_texto_vacio_es_determinista_sin_ia(self, parsear, enriquecer):
        pre = self.client.post(
            self.precheck, json.dumps({'texto': ''}), content_type='application/json',
        ).json()
        self.assertEqual(pre['estado_analisis'], 'ok_sin_senales')
        self.assertTrue(pre['analisis_cierre_token'])
        parsear.assert_not_called()
        enriquecer.assert_not_called()

    @patch('joi.services.parsear_cierre_diario', side_effect=RuntimeError('IA caída'))
    def test_fallo_es_no_disponible_no_sin_senales(self, _parsear):
        pre = self.client.post(
            self.precheck, json.dumps({'texto': 'Texto'}), content_type='application/json',
        ).json()
        self.assertEqual(pre['estado_analisis'], 'no_disponible')
        self.assertFalse(pre['bloqueo'])

    @patch('joi.services.generar_respuesta_cierre', return_value='Lectura recuperada')
    @patch('joi.services.enriquecer_cierre', return_value={'interacciones': [], 'micro_verdad': None})
    @patch('joi.services.parsear_cierre_diario')
    def test_token_nuevo_valido_reemplaza_artefacto_fallido_canonico(
        self, parsear, _enriquecer, _respuesta,
    ):
        parsear.side_effect = [RuntimeError('IA caída'), {
            'personas': [], 'impulsos': [], 'etiquetas': [],
        }]
        primer_precheck = self.client.post(
            self.precheck, json.dumps({'texto': 'Texto estable'}),
            content_type='application/json',
        ).json()
        primero = self._post('Texto estable', primer_precheck['analisis_cierre_token'])
        self.assertEqual(primero.status_code, 200)
        canonica = CierreNocturnoOperacion.objects.get(result_version=1)
        self.assertEqual(canonica.estado, 'failed')

        segundo_precheck = self.client.post(
            self.precheck, json.dumps({'texto': 'Texto estable'}),
            content_type='application/json',
        ).json()
        segundo = self._post(
            'Texto estable', segundo_precheck['analisis_cierre_token'],
            expected_version='1',
        )
        self.assertEqual(segundo.status_code, 200)
        canonica.refresh_from_db()
        self.assertEqual(canonica.estado, 'completed')
        self.assertEqual(canonica.resultado['respuesta_joi'], 'Lectura recuperada')

    @patch('joi.services.generar_respuesta_cierre', return_value='Lectura')
    @patch('joi.services.enriquecer_cierre', return_value={
        'interacciones': [{
            'persona': 'Bea', 'tipo': 'neutra', 'descripcion': 'No fue detectada',
        }],
        'micro_verdad': None,
    })
    @patch('joi.services.parsear_cierre_diario', return_value={
        'personas': ['Ana'], 'impulsos': [], 'etiquetas': [],
    })
    def test_proyecciones_no_introducen_personas_ajenas_al_analisis_firmado(
        self, _parsear, _enriquecer, _respuesta,
    ):
        pre = self.client.post(
            self.precheck, json.dumps({'texto': 'Vi a Ana'}),
            content_type='application/json',
        ).json()
        response = self._post('Vi a Ana', pre['analisis_cierre_token'])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PersonaInterina.objects.filter(nombre='Bea').exists())
        operacion = CierreNocturnoOperacion.objects.get(result_version=1)
        self.assertEqual(operacion.resultado['simbiosis']['personas'], ['Ana'])

    @patch('joi.services.generar_pregunta_simbiosis', return_value='¿Qué esperas todavía de Ana?')
    @patch('diario.services.analisis_cierre_service.analizar_texto')
    def test_precheck_usa_la_voz_joi_y_firma_su_pregunta(self, analizar, generar):
        from diario.services.analisis_cierre_service import verificar_artefacto

        analizar.return_value = {
            'estado': 'ok',
            'parseo': {'personas': ['Ana'], 'impulsos': [], 'etiquetas': []},
            'enriquecido': {},
        }
        hoy = timezone.localdate()
        for dias in (1, 2):
            reflexion = ReflexionLibre.objects.create(
                usuario=self.user, contenido='Ana', etiquetas='ana',
            )
            ReflexionLibre.objects.filter(pk=reflexion.pk).update(
                fecha=timezone.now() - timedelta(days=dias)
            )

        datos = self.client.post(
            self.precheck, json.dumps({'texto': 'Hoy pensé en Ana'}),
            content_type='application/json',
        ).json()

        self.assertTrue(datos['bloqueo'])
        self.assertEqual(datos['pregunta'], '¿Qué esperas todavía de Ana?')
        generar.assert_called_once_with(self.user, 'Ana')
        artefacto = verificar_artefacto(
            datos['analisis_cierre_token'], usuario=self.user, fecha=hoy,
            texto='Hoy pensé en Ana',
        )
        self.assertEqual(artefacto['pregunta_simbiosis'], datos['pregunta'])

    @patch('joi.services.generar_pregunta_simbiosis', return_value='')
    @patch('diario.services.analisis_cierre_service.analizar_texto')
    def test_sin_pregunta_autentica_el_precheck_no_bloquea(self, analizar, _generar):
        analizar.return_value = {
            'estado': 'ok',
            'parseo': {'personas': ['Ana'], 'impulsos': [], 'etiquetas': []},
            'enriquecido': {},
        }
        for dias in (1, 2):
            reflexion = ReflexionLibre.objects.create(
                usuario=self.user, contenido='Ana', etiquetas='ana',
            )
            ReflexionLibre.objects.filter(pk=reflexion.pk).update(
                fecha=timezone.now() - timedelta(days=dias)
            )

        datos = self.client.post(
            self.precheck, json.dumps({'texto': 'Hoy pensé en Ana'}),
            content_type='application/json',
        ).json()
        self.assertFalse(datos['bloqueo'])
        self.assertEqual(datos['persona'], '')
        self.assertEqual(datos['pregunta'], '')

    def test_diario_no_conserva_el_fallback_que_fingia_ser_joi(self):
        from pathlib import Path
        import diario.views

        fuente = Path(diario.views.__file__).read_text()
        self.assertNotIn('que aún no te das a ti mismo', fuente)
