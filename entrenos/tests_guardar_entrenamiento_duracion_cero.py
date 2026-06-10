"""
Bug post-62F — guardar_entrenamiento_activo con duracion_minutos_real='0'.

Si el usuario pulsa "confirmar guardar" sin abrir el modal de resumen (los
campos hid-* del resumen viajan vacíos), pero hid-duracion sí llega como '0'
(sesión de duración ~0 minutos), EntrenoRealizado.objects.create() guardaba
duracion_minutos="0" (string, valor crudo del POST). Ese string se propagaba
a SesionEntrenamiento.duracion_minutos (logros/services.py) y de ahí a
sincronizar_hub_actividad (entrenos/signals.py), donde
`duracion is not None and duracion > 0` comparaba un str con un int y
lanzaba TypeError, abortando el guardado con el mensaje
"Hubo un error crítico al guardar: '>' not supported between instances of
'str' and 'int'".
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class TestGuardarEntrenamientoDuracionCero(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_dur0', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestDur0', 'dias_disponibles': 4},
        )
        Rutina.objects.get_or_create(nombre='Push Day Test')
        self.client.force_login(self.user)

    def _post_data(self, duracion):
        data = {
            'fecha': '2026-06-10',
            'rutina_nombre': 'Push Day Test',
            'sesion_programada_id': '',
            'modo_reducido': '0',
            'duracion_minutos_real': duracion,
            # Modal de resumen nunca abierto: estos campos viajan vacíos.
            'series_completadas': '',
            'series_totales': '',
            'ejercicios_completados': '',
            'ejercicios_totales': '',
            'volumen_total_sesion': '',
            'rpe_medio_sesion': '',
            'rpe_global_sesion': '',
            'energia_pre_sesion': '',
            'ej1_nombre': 'Press banca',
            'ej1_tipo_progresion': 'peso_reps',
            'ej1_es_principal': '',
            'ej1_es_tope_maquina': 'false',
            'ej1_molestia_reportada': 'false',
        }
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '60'
            data[f'ej1_reps_{i}'] = '8'
            data[f'ej1_rpe_{i}'] = '7'
        return data

    def test_guardar_con_duracion_cero_no_lanza_typeerror(self):
        url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})
        resp = self.client.post(url, self._post_data('0'))

        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertRedirects(
            resp,
            reverse('entrenos:post_entreno_resumen',
                    kwargs={'cliente_id': self.cliente.id, 'entreno_id': entreno.id}),
            fetch_redirect_response=False,
        )

    def test_duracion_cero_se_guarda_como_entero(self):
        url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})
        self.client.post(url, self._post_data('0'))

        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertEqual(entreno.duracion_minutos, 0)
        self.assertIsInstance(entreno.duracion_minutos, int)
