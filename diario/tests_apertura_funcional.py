from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import ProsocheDiario, ProsocheMes, SeguimientoVires
from diario.services.estado_diario import calcular_estado_diario_hoy, tiene_apertura_manana
from joi.services import _sintetizador_contexto_vital, generar_respuesta_breve_apertura


class AperturaFuncionalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('apertura', password='clave')
        from clientes.models import Cliente
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'Apertura', 'email': 'apertura@test.local', 'telefono': ''},
        )
        self.client.force_login(self.user)
        self.hoy = timezone.localdate()
        self.url = reverse('diario:presencia_apertura')

    def _mes(self):
        return ProsocheMes.objects.create(
            usuario=self.user, mes=self.hoy.strftime('%B'), año=self.hoy.year
        )

    def _entrada(self, **kwargs):
        return ProsocheDiario.objects.create(
            prosoche_mes=self._mes(), fecha=self.hoy, **kwargs
        )

    def _post(self, **overrides):
        data = {
            'estado_animo': '4',
            'intencion': 'Cuidar el ritmo',
            'gratitud_1': 'Tengo tiempo',
            'soberania': 'Caminar sin móvil',
            'molestia_zona': 'rodilla',
            'molestia_nota': 'Ligera tensión',
        }
        data.update(overrides)
        return self.client.post(
            self.url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

    def test_get_es_estrictamente_de_lectura(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="respuesta-joi-apertura"')
        self.assertContains(response, "d.respuesta_joi")
        self.assertFalse(ProsocheMes.objects.exists())
        self.assertFalse(ProsocheDiario.objects.exists())
        self.assertFalse(SeguimientoVires.objects.exists())

    def test_animo_exige_seleccion_consciente_y_ajax_devuelve_errores(self):
        for valor in ('', '3', '6', 'texto'):
            with self.subTest(valor=valor):
                response = self._post(estado_animo=valor)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()['success'])
                self.assertIn('estado_animo', response.json()['errors'])
                self.assertFalse(ProsocheDiario.objects.exists())

    def test_html_invalido_renderiza_errores_sin_500(self):
        response = self.client.post(self.url, {
            'estado_animo': '4', 'gratitud_1': 'x' * 201,
            'molestia_zona': 'zona_inventada',
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Corrige', status_code=400)
        self.assertFalse(ProsocheDiario.objects.exists())

    @patch('joi.services.generar_respuesta_breve_apertura', return_value='Te leo: protege ese ritmo hoy.')
    def test_guardado_marca_apertura_y_devuelve_voz_joi_contextual(self, generar):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        entrada = ProsocheDiario.objects.get()
        self.assertIsNotNone(entrada.apertura_confirmada_en)
        self.assertEqual(entrada.respuesta_joi_apertura, 'Te leo: protege ese ritmo hoy.')
        self.assertEqual(response.json()['respuesta_joi'], entrada.respuesta_joi_apertura)
        generar.assert_called_once()
        contexto = generar.call_args.kwargs
        self.assertEqual(contexto['cliente'], self.cliente)
        self.assertEqual(contexto['estado_animo'], 4)
        self.assertEqual(contexto['direccion'], 'Cuidar el ritmo')
        self.assertEqual(contexto['apoyo'], 'Tengo tiempo')
        self.assertEqual(contexto['molestia_zona'], 'rodilla')
        self.assertEqual(contexto['soberania'], 'Caminar sin móvil')

    @patch('joi.services._llamar_haiku', return_value='Una frase real.')
    @patch('joi.services._bloque_manual', return_value='[MANUAL]')
    @patch('joi.services._bloque_narrativa', return_value='[NARRATIVA]')
    def test_generador_joi_respeta_orden_narrativa_manual_trigger(
        self, _narrativa, _manual, llamar
    ):
        respuesta = generar_respuesta_breve_apertura(
            cliente=self.cliente,
            estado_animo=4,
            direccion='Cuidar el ritmo',
            apoyo='Tengo tiempo',
            molestia_zona='rodilla',
            molestia_nota='Tensión',
            soberania='Caminar',
        )
        self.assertEqual(respuesta, 'Una frase real.')
        prompt = llamar.call_args.args[0]
        self.assertLess(prompt.index('[NARRATIVA]'), prompt.index('[MANUAL]'))
        self.assertLess(prompt.index('[MANUAL]'), prompt.index('Ánimo: bien'))
        _manual.assert_called_once_with(self.user, incluir_narrativa=False)

    @patch('joi.services._llamar_haiku', side_effect=RuntimeError('IA caída'))
    def test_fallo_ia_no_fabrica_voz_joi(self, _llamar):
        respuesta = generar_respuesta_breve_apertura(
            cliente=self.cliente, estado_animo=2, direccion='Ir despacio'
        )
        self.assertEqual(respuesta, '')

    def test_fallo_joi_no_revierte_apertura_y_llamada_ocurre_fuera_de_atomic(self):
        from django.db import connection
        nivel_atomic_test = len(connection.atomic_blocks)

        def comprobar_fuera_de_atomic(**kwargs):
            self.assertEqual(len(connection.atomic_blocks), nivel_atomic_test)
            raise RuntimeError('servicio JOI no disponible')

        with patch(
            'joi.services.generar_respuesta_breve_apertura',
            side_effect=comprobar_fuera_de_atomic,
        ):
            response = self._post()

        self.assertEqual(response.status_code, 200)
        entrada = ProsocheDiario.objects.get()
        self.assertIsNotNone(entrada.apertura_confirmada_en)
        self.assertEqual(entrada.respuesta_joi_apertura, '')
        self.assertEqual(response.json()['respuesta_joi'], '')
        self.assertEqual(response.json()['confirmacion'], 'Apertura guardada.')

    @patch('joi.services.generar_respuesta_breve_apertura', return_value='Actualizado.')
    def test_reabrir_preserva_tareas_y_actualiza_solo_soberania(self, _generar):
        entrada = self._entrada(
            tareas_dia=[
                {'texto': 'Comprar pan', 'completada': True},
                {'texto': 'Soberanía anterior', 'completada': False, 'es_soberania': True},
            ]
        )
        response = self.client.get(self.url)
        self.assertContains(response, 'value="Soberanía anterior"')

        self._post(soberania='Leer veinte minutos')
        entrada.refresh_from_db()
        self.assertIn({'texto': 'Comprar pan', 'completada': True}, entrada.tareas_dia)
        soberanias = [t for t in entrada.tareas_dia if t.get('es_soberania')]
        self.assertEqual(soberanias, [{
            'texto': 'Leer veinte minutos', 'completada': False, 'es_soberania': True
        }])

        self._post(soberania='')
        entrada.refresh_from_db()
        self.assertEqual(entrada.tareas_dia, [{'texto': 'Comprar pan', 'completada': True}])

    @patch('joi.services.generar_respuesta_breve_apertura', return_value='Sin dolor hoy.')
    def test_seleccionar_ninguna_limpia_zona_y_nota_anteriores(self, _generar):
        SeguimientoVires.objects.create(
            usuario=self.user, fecha=self.hoy,
            molestia_zona='espalda', molestia_nota='Dato antiguo',
        )
        self._post(molestia_zona='ninguna', molestia_nota='Texto que no debe persistir')
        vires = SeguimientoVires.objects.get()
        self.assertEqual(vires.molestia_zona, 'ninguna')
        self.assertEqual(vires.molestia_nota, '')

    def test_default_vacio_no_es_apertura_para_estado_ni_contexto_joi(self):
        entrada = self._entrada()
        self.assertFalse(tiene_apertura_manana(entrada))
        self.assertEqual(calcular_estado_diario_hoy(entrada)['estado'], 'sin_entrada')
        self.assertEqual(_sintetizador_contexto_vital(self.user)['intencion_am'], [])

    def test_marcador_explicito_es_la_unica_autoridad_de_apertura(self):
        entrada = self._entrada(persona_quiero_ser='texto histórico sin confirmación')
        self.assertFalse(tiene_apertura_manana(entrada))
        entrada.apertura_confirmada_en = timezone.now()
        entrada.save(update_fields=['apertura_confirmada_en'])
        self.assertTrue(tiene_apertura_manana(entrada))
