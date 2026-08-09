import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import (
    CierreNocturnoOperacion, Gesto, Interaccion, InteraccionSombra,
    PersonaImportante, PersonaInterina, ProsocheDiario, ProsocheMes,
    ReflexionLibre,
)
from diario.services.cierre_service import (
    ejecutar_cierre_nocturno, ejecutar_enriquecimiento_cierre,
)


class RecurrenciaSimbiosisMaterializadaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('recurrencia-materializada')
        self.client.force_login(self.user)
        self.url = reverse('diario:check_simbiosis_api')
        self.hoy = timezone.localdate()

    def _analisis(self):
        return {
            'estado': 'ok',
            'parseo': {'personas': ['Ana'], 'impulsos': [], 'etiquetas': ['foco'], 'estado_animo': 3},
            'enriquecido': {},
        }

    @patch('joi.services.generar_pregunta_simbiosis', return_value='¿Qué está cambiando con Ana?')
    @patch('diario.services.analisis_cierre_service.analizar_texto')
    def test_bloquea_por_persona_materializada_en_sombra_e_interaccion(self, analizar, _pregunta):
        analizar.return_value = self._analisis()
        interina = PersonaInterina.objects.create(usuario=self.user, nombre='Ana')
        InteraccionSombra.objects.create(
            persona_interina=interina, fecha=self.hoy - timedelta(days=1), descripcion='Hablamos',
        )
        confirmada = PersonaImportante.objects.create(usuario=self.user, nombre='Ana')
        interaccion = Interaccion.objects.create(
            usuario=self.user, titulo='Encuentro', descripcion='Hablamos otra vez',
            fecha=self.hoy - timedelta(days=2),
        )
        interaccion.personas.add(confirmada)

        respuesta = self.client.post(
            self.url, json.dumps({'texto': 'Hoy apareció Ana otra vez'}),
            content_type='application/json',
        )

        self.assertTrue(respuesta.json()['bloqueo'])
        self.assertEqual(respuesta.json()['persona'], 'Ana')

    @patch('joi.services.generar_pregunta_simbiosis', return_value='No debe llamarse')
    @patch('diario.services.analisis_cierre_service.analizar_texto')
    def test_etiquetas_tematicas_no_cuentan_como_personas(self, analizar, pregunta):
        analizar.return_value = self._analisis()
        for delta in (1, 2):
            ReflexionLibre.objects.create(
                usuario=self.user, contenido='Tema abstracto', etiquetas='ana,foco',
                fecha=timezone.now() - timedelta(days=delta),
            )

        respuesta = self.client.post(
            self.url, json.dumps({'texto': 'Hoy apareció Ana'}), content_type='application/json',
        )

        self.assertFalse(respuesta.json()['bloqueo'])
        pregunta.assert_not_called()


class PersistenciaSimbiosisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('respuesta-durable')
        self.hoy = timezone.localdate()

    @patch('joi.services.generar_respuesta_cierre', return_value='')
    def test_respuesta_conserva_persona_y_pregunta_y_entra_en_historial_joi(self, _respuesta):
        payload = {
            'reflexion_libre': 'Hoy hablé con Ana.', 'friccion_no': 2,
            'cuerpo_cierre': 'ligero', 'estado_animo_noche': 4,
            'habitos_completados': [], 'simbiosis_respuesta': 'Dejar de anticipar.',
            'simbiosis_pregunta': '¿Qué anticipas de Ana?',
            'simbiosis_persona': 'Ana',
            'analisis_cierre': {
                'estado': 'ok',
                'parseo': {'personas': ['Ana'], 'etiquetas': [], 'impulsos': []},
                'enriquecido': {'interacciones': []},
                'persona_simbiosis': 'Ana',
                'pregunta_simbiosis': '¿Qué anticipas de Ana?',
            },
        }
        op = ejecutar_cierre_nocturno(
            usuario=self.user, fecha=self.hoy, payload=payload,
            idempotency_key=uuid.uuid4(), expected_version=0,
        ).operacion

        ejecutar_enriquecimiento_cierre(op.pk)

        reflexion = ReflexionLibre.objects.get(etiquetas__contains='simbiosis_respuesta')
        self.assertTrue(reflexion.titulo.startswith('Simbiosis: Ana'))
        self.assertIn('¿Qué anticipas de Ana?', reflexion.titulo)
        from joi.services import _historial_simbiosis
        historial = _historial_simbiosis(self.user, 'Ana')
        self.assertIn('¿Qué anticipas de Ana?', historial)
        self.assertIn('Dejar de anticipar.', historial)

    @patch('joi.services.generar_respuesta_cierre', return_value='')
    def test_nombre_ia_se_normaliza_y_recorta_antes_de_persona_interina(self, _respuesta):
        nombre_largo = '   ' + ('Ana muy larga ' * 20) + '   '
        normalizado = ' '.join(nombre_largo.split())[:100].rstrip()
        payload = {
            'reflexion_libre': 'Encuentro.', 'friccion_no': 2, 'cuerpo_cierre': 'ligero',
            'estado_animo_noche': 4, 'habitos_completados': [], 'simbiosis_respuesta': '',
            'simbiosis_pregunta': '', 'simbiosis_persona': '',
            'analisis_cierre': {
                'estado': 'ok', 'parseo': {'personas': [nombre_largo], 'etiquetas': [], 'impulsos': []},
                'enriquecido': {'interacciones': [{
                    'persona': nombre_largo, 'descripcion': 'Encuentro', 'tipo': 'neutra',
                }]},
            },
        }
        op = ejecutar_cierre_nocturno(
            usuario=self.user, fecha=self.hoy, payload=payload,
            idempotency_key=uuid.uuid4(), expected_version=0,
        ).operacion

        ejecutar_enriquecimiento_cierre(op.pk)

        persona = PersonaInterina.objects.get(usuario=self.user)
        self.assertEqual(persona.nombre, normalizado)
        self.assertLessEqual(len(persona.nombre), 100)


class InvitacionGestoYUIAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('gesto-reactivable')
        self.client.force_login(self.user)
        hoy = timezone.localdate()
        mes = ProsocheMes.objects.create(usuario=self.user, mes=hoy.strftime('%B'), año=hoy.year)
        self.entrada = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=hoy, cierre_version=1, cierre_confirmado_en=timezone.now(),
        )
        self.propuesta = {'nombre': 'Preparar mañana', 'descripcion': 'Dejar ropa lista', 'tipo': 'positivo'}
        self.op = CierreNocturnoOperacion.objects.create(
            entrada=self.entrada, idempotency_key=uuid.uuid4(), expected_version=0,
            result_version=1, payload_hash='a' * 64, estado='completed',
            resultado={'propuesta_habito': self.propuesta},
        )

    def test_aceptar_propuesta_reactiva_gesto_cerrado(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre=self.propuesta['nombre'], estado='cerrado',
            fecha_cierre=timezone.localdate() - timedelta(days=2),
        )
        respuesta = self.client.post(
            reverse('diario:aceptar_habito_invitacion'),
            json.dumps({**self.propuesta, 'operacion': str(self.op.idempotency_key)}),
            content_type='application/json',
        )
        gesto.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(gesto.estado, 'activo')
        self.assertIsNone(gesto.fecha_cierre)
        self.assertTrue(respuesta.json()['reactivado'])

    def test_aceptar_propuesta_reactiva_gesto_pausado(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre=self.propuesta['nombre'], estado='pausado',
        )
        respuesta = self.client.post(
            reverse('diario:aceptar_habito_invitacion'),
            json.dumps({**self.propuesta, 'operacion': str(self.op.idempotency_key)}),
            content_type='application/json',
        )
        gesto.refresh_from_db()
        self.assertEqual(gesto.estado, 'activo')
        self.assertTrue(respuesta.json()['reactivado'])

    def test_formulario_explica_proyecciones_y_controles_tienen_44px(self):
        html = self.client.get(reverse('diario:presencia_cierre')).content.decode()
        self.assertIn('Gestos, Simbiosis y Logos', html)
        self.assertIn('min-height: 44px', html)
        self.assertIn('.cuerpo-chip { min-height: 44px; }', html)
