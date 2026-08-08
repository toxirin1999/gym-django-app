import json
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from diario.models import (
    CierreNocturnoOperacion,
    InteraccionSombra,
    PersonaImportante,
    PersonaInterina,
    ProsocheDiario,
    ProsocheMes,
)
from diario.services.cierre_service import ejecutar_enriquecimiento_cierre
from diario.services.lectura_semanal import agregar_semana
from joi.models import ManualDavid


class NoPersonaContratoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('no-persona', password='x')
        self.client.force_login(self.user)
        self.interina = PersonaInterina.objects.create(
            usuario=self.user, nombre='Padres', estado='sombra', veces_mencionada=3,
        )
        self.sombra = InteraccionSombra.objects.create(
            persona_interina=self.interina, descripcion='Registro histórico.',
            fecha=date(2026, 8, 2),
        )
        self.url = reverse('diario:promover_persona_interina')

    def _accion(self, accion):
        return self.client.post(
            self.url,
            json.dumps({'id': self.interina.pk, 'accion': accion}),
            content_type='application/json',
        )

    def test_marcar_no_persona_es_atomico_idempotente_y_conserva_historial(self):
        primera = self._accion('no_persona')
        segunda = self._accion('no_persona')

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'no_persona')
        self.assertTrue(InteraccionSombra.objects.filter(pk=self.sombra.pk).exists())

    @patch(
        'diario.services.cierre_service.desactivar_manuales_tecnicos_de_interina',
        side_effect=RuntimeError('fallo simulado'),
    )
    def test_fallo_al_desactivar_metadata_revierte_el_estado(self, _desactivar):
        respuesta = self._accion('no_persona')

        self.assertEqual(respuesta.status_code, 400)
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'sombra')

    def test_no_persona_desactiva_solo_manual_tecnico_atribuido_por_ledger(self):
        tecnico = ManualDavid.objects.create(
            user=self.user, entrada="Entidad nueva detectada: 'Padres'. Pendiente.",
            origen='patron_detectado',
        )
        manual_real = ManualDavid.objects.create(
            user=self.user, entrada='Dato manual real', origen='feedback_error',
        )
        mes = ProsocheMes.objects.create(usuario=self.user, mes='agosto', año=2026)
        entrada = ProsocheDiario.objects.create(prosoche_mes=mes, fecha=date(2026, 8, 2))
        CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=uuid.uuid4(), payload_hash='x',
            expected_version=0, enrichment_payload={}, result_version=1, estado='completed',
            resultado={'schema_version': 2, 'ledger': {'manual': [{
                'id': tecnico.pk, 'created': True,
                'persona_interina_id': self.interina.pk,
                'after': {
                    'entrada': tecnico.entrada, 'origen': tecnico.origen,
                    'tipo': tecnico.tipo, 'confianza': tecnico.confianza,
                    'estado': tecnico.estado, 'activa': tecnico.activa,
                    'fuente_mensaje_id': None, 'ultima_evidencia': None,
                    'notas_revision': None, 'hipotesis_contraria': None,
                },
            }] }},
        )

        self._accion('no_persona')

        tecnico.refresh_from_db()
        manual_real.refresh_from_db()
        self.assertFalse(tecnico.activa)
        self.assertEqual(tecnico.estado, 'descartada')
        self.assertTrue(manual_real.activa)

    def test_restaurar_devuelve_a_sombra_sin_reactivar_historial(self):
        self._accion('no_persona')
        respuesta = self._accion('restaurar')

        self.assertEqual(respuesta.status_code, 200)
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'sombra')
        self.assertEqual(self.interina.veces_mencionada, 0)
        self.assertEqual(self.interina.menciones_desde_descarte, 0)
        self.assertEqual(InteraccionSombra.objects.filter(persona_interina=self.interina).count(), 1)

    def test_dashboard_ofrece_excluir_en_sombra_y_restaurar_desde_lista(self):
        respuesta = self.client.get(reverse('diario:simbiosis_dashboard'))
        self.assertContains(respuesta, 'No es una persona')
        self._accion('no_persona')

        respuesta = self.client.get(reverse('diario:simbiosis_dashboard'))
        self.assertNotContains(respuesta, 'id="sombra-%s"' % self.interina.pk)
        self.assertContains(respuesta, 'Detecciones excluidas')
        self.assertContains(respuesta, 'Restaurar')

    def test_lectura_semanal_excluye_sombras_de_no_persona(self):
        self.interina.estado = 'no_persona'
        self.interina.save(update_fields=['estado'])
        agregado = agregar_semana(
            self.user, inicio=date(2026, 8, 1), fin=date(2026, 8, 7),
        )
        self.assertEqual(agregado['simbiosis']['interacciones'], 0)
        self.assertNotIn('Padres', agregado['simbiosis']['personas_mencionadas'])

    @patch('joi.services.enriquecer_cierre', return_value={'interacciones': [{
        'persona': 'Padres', 'descripcion': 'No debe proyectarse', 'tipo': 'neutra',
    }]})
    @patch('joi.services.parsear_cierre_diario', return_value={'personas': ['Padres']})
    def test_reprocesado_tambien_respeta_no_persona(self, _parsear, _enriquecer):
        self.interina.estado = 'no_persona'
        self.interina.save(update_fields=['estado'])

        respuesta = self.client.post(reverse('diario:reprocesar_cierres'), {
            'texto_manual': 'Hablé de padres', 'fecha_manual': '2026-08-08',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'no_persona')
        self.assertEqual(self.interina.veces_mencionada, 3)
        self.assertEqual(InteraccionSombra.objects.filter(persona_interina=self.interina).count(), 1)

    @patch('joi.services.generar_respuesta_cierre', return_value='')
    def test_cierre_canonico_no_reactiva_ni_proyecta_no_persona(self, _respuesta):
        mes = ProsocheMes.objects.create(usuario=self.user, mes='agosto', año=2026)
        entrada = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=date(2026, 8, 8), cierre_version=1,
        )
        self.interina.estado = 'no_persona'
        self.interina.save(update_fields=['estado'])
        op = CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=uuid.uuid4(), payload_hash='h',
            expected_version=0, result_version=1, estado='pending', enrichment_payload={
                'reflexion_libre': 'Hablé de padres', 'estado_animo_noche': 3,
                'friccion_no': 2, 'simbiosis_respuesta': '',
                'analisis_cierre': {
                    'estado': 'ok',
                    'parseo': {'personas': ['Padres'], 'etiquetas': []},
                    'enriquecido': {'interacciones': [{
                        'persona': 'Padres', 'descripcion': 'Otra mención', 'tipo': 'neutra',
                    }]},
                },
            },
        )

        resultado = ejecutar_enriquecimiento_cierre(op.pk)

        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'no_persona')
        self.assertEqual(self.interina.veces_mencionada, 3)
        self.assertEqual(resultado['sombras'], [])
        self.assertFalse(ManualDavid.objects.filter(entrada__startswith='Entidad nueva detectada').exists())

    def test_creacion_manual_homonima_prevalece_y_reconcilia_marcador(self):
        self.interina.estado = 'no_persona'
        self.interina.save(update_fields=['estado'])
        respuesta = self.client.post(reverse('diario:persona_crear'), {
            'nombre': 'padres', 'tipo_relacion': 'familia', 'salud_relacion': '',
            'notas': '',
        })
        self.assertEqual(respuesta.status_code, 302)
        persona = PersonaImportante.objects.get(usuario=self.user)
        self.interina.refresh_from_db()
        self.assertEqual(self.interina.estado, 'promovida')
        self.assertEqual(self.interina.persona_importante, persona)
