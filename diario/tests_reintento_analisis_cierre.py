import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import CierreNocturnoOperacion, ProsocheDiario
from diario.services.analisis_cierre_service import (
    AnalisisNoDisponible,
    hash_texto,
    verificar_artefacto,
)
from diario.services.cierre_service import ejecutar_cierre_nocturno


class ReintentoAnalisisCierreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('retry-cierre', password='x')
        self.client.force_login(self.user)
        self.fecha = timezone.localdate()
        self.url = reverse('diario:reintentar_analisis_cierre')
        self.operacion = ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=self.fecha,
            payload={
                'reflexion_libre': 'Texto conservado en servidor',
                'friccion_no': 3,
                'cuerpo_cierre': 'cansado',
                'estado_animo_noche': 4,
                'habitos_completados': [],
                'simbiosis_respuesta': '',
                'simbiosis_pregunta': '',
            },
            idempotency_key=uuid.uuid4(),
            expected_version=0,
        ).operacion
        self.operacion.estado = 'failed'
        self.operacion.error = 'IA caída'
        self.operacion.save(update_fields=['estado', 'error', 'updated_at'])

    def post(self, operacion=None, version=1, **extra):
        return self.client.post(
            self.url,
            json.dumps({
                'operacion': str((operacion or self.operacion).idempotency_key),
                'version': version,
                **extra,
            }),
            content_type='application/json',
        )

    def test_exige_autenticacion(self):
        self.client.logout()
        response = self.post()
        self.assertEqual(response.status_code, 302)

    def test_rechaza_json_invalido_y_no_acepta_texto_del_cliente(self):
        invalido = self.client.post(self.url, '{', content_type='application/json')
        manipulado = self.post(texto='Texto inyectado', analisis={'estado': 'ok'})
        self.assertEqual(invalido.status_code, 400)
        self.assertEqual(manipulado.status_code, 400)

    def test_rechaza_ajena_obsoleta_hash_distinto_y_estados_no_reintentables(self):
        otro = User.objects.create_user('otro-retry')
        ajena = ejecutar_cierre_nocturno(
            usuario=otro, fecha=self.fecha,
            payload={
                'reflexion_libre': 'Ajeno', 'friccion_no': 1, 'cuerpo_cierre': '',
                'estado_animo_noche': 3, 'habitos_completados': [],
                'simbiosis_respuesta': '', 'simbiosis_pregunta': '',
            }, idempotency_key=uuid.uuid4(), expected_version=0,
        ).operacion
        ajena.estado = 'failed'
        ajena.save(update_fields=['estado', 'updated_at'])
        self.assertEqual(self.post(ajena).status_code, 404)
        self.assertEqual(self.post(version=2).status_code, 409)

        self.operacion.payload_hash = '0' * 64
        self.operacion.save(update_fields=['payload_hash', 'updated_at'])
        self.assertEqual(self.post().status_code, 409)
        self.operacion.payload_hash = self.operacion.entrada.cierre_payload_hash
        self.operacion.save(update_fields=['payload_hash', 'updated_at'])

        for estado in ('noop', 'completed', 'processing', 'superseded', 'pending'):
            self.operacion.estado = estado
            self.operacion.save(update_fields=['estado', 'updated_at'])
            self.assertEqual(self.post().status_code, 409, estado)

    @patch(
        'diario.services.analisis_cierre_service.analizar_texto',
        side_effect=AnalisisNoDisponible('sigue caída'),
    )
    def test_no_disponible_preserva_failed_y_version_y_devuelve_503_retryable(self, _analizar):
        payload_antes = dict(self.operacion.enrichment_payload)
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json()['retryable'])
        self.operacion.refresh_from_db()
        self.operacion.entrada.refresh_from_db()
        self.assertEqual(self.operacion.estado, 'failed')
        self.assertEqual(self.operacion.error, 'IA caída')
        self.assertEqual(self.operacion.enrichment_payload, payload_antes)
        self.assertEqual(self.operacion.entrada.cierre_version, 1)

    @patch('diario.services.cierre_service.ejecutar_enriquecimiento_cierre')
    @patch('diario.services.analisis_cierre_service.analizar_texto')
    def test_exito_regenera_desde_payload_servidor_y_no_duplica(self, analizar, enriquecer):
        analizar.return_value = {
            'estado': 'ok',
            'parseo': {'personas': [], 'impulsos': [], 'etiquetas': []},
            'enriquecido': {'interacciones': [], 'micro_verdad': 'Nueva'},
        }

        def completar(pk):
            CierreNocturnoOperacion.objects.filter(pk=pk).update(estado='completed')
            return {'respuesta_joi': 'Lectura recuperada'}

        enriquecer.side_effect = completar
        primero = self.post()
        segundo = self.post()
        self.assertEqual(primero.status_code, 200)
        self.assertEqual(segundo.status_code, 200)
        self.assertEqual(primero.json()['result_url'], segundo.json()['result_url'])
        analizar.assert_called_once_with('Texto conservado en servidor')
        enriquecer.assert_called_once_with(self.operacion.pk)
        self.assertEqual(CierreNocturnoOperacion.objects.count(), 1)
        self.assertEqual(ProsocheDiario.objects.get().cierre_version, 1)
        self.operacion.refresh_from_db()
        artefacto = self.operacion.enrichment_payload['analisis_cierre']
        self.assertEqual(artefacto['texto_hash'], hash_texto('Texto conservado en servidor'))
        self.assertEqual(artefacto['enriquecido']['micro_verdad'], 'Nueva')

    @patch('diario.services.cierre_service.ejecutar_enriquecimiento_cierre')
    @patch('diario.services.analisis_cierre_service.analizar_texto')
    def test_si_la_version_cambia_durante_el_reintento_no_responde_exito(
        self, analizar, enriquecer,
    ):
        analizar.return_value = {
            'estado': 'ok',
            'parseo': {'personas': [], 'impulsos': [], 'etiquetas': []},
            'enriquecido': {},
        }

        def quedar_obsoleta(pk):
            CierreNocturnoOperacion.objects.filter(pk=pk).update(estado='superseded')
            return {'active_version': 2}

        enriquecer.side_effect = quedar_obsoleta

        response = self.post()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'superseded_during_retry')

    def test_ui_solo_ofrece_reintento_en_failed_y_maneja_503(self):
        result_url = reverse('diario:presencia_cierre') + f'?cierre_operacion={self.operacion.idempotency_key}'
        html = self.client.get(result_url).content.decode()
        self.assertIn('id="reintentar-analisis"', html)
        self.assertIn(self.url, html)
        self.assertIn('boton.disabled = true', html)
        self.assertIn('window.location.assign(data.result_url)', html)
        self.assertIn('respuesta.status === 503', html)
        self.operacion.estado = 'completed'
        self.operacion.save(update_fields=['estado', 'updated_at'])
        self.assertNotIn('id="reintentar-analisis"', self.client.get(result_url).content.decode())


class CheckSimbiosisFallbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('precheck-fallback')
        self.client.force_login(self.user)
        self.url = reverse('diario:check_simbiosis_api')

    def test_json_invalido_es_400_estable(self):
        response = self.client.post(self.url, '{', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_json')

    @patch('diario.services.analisis_cierre_service.analizar_texto', side_effect=RuntimeError('boom'))
    def test_fallo_exterior_con_json_valido_devuelve_contrato_no_disponible_firmado(self, _analizar):
        response = self.client.post(
            self.url, json.dumps({'texto': 'Texto válido'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['estado_analisis'], 'no_disponible')
        self.assertFalse(data['bloqueo'])
        self.assertIn('analisis_cierre_token', data)
        artefacto = verificar_artefacto(
            data['analisis_cierre_token'], usuario=self.user,
            fecha=timezone.localdate(), texto='Texto válido',
        )
        self.assertEqual(artefacto['estado'], 'no_disponible')
