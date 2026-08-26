from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from diario.models import SeguimientoVires
from entrenos.models import IntervencionPlan, SenalEntrenamientoAutorizada, SugerenciaPlan
from entrenos.services.senales_autorizadas_service import (
    obtener_proyeccion_senal_autorizada,
    revocar_senal_autorizada,
)
from entrenos.services.sugerencias_service import aceptar_sugerencia
from entrenos.services.decision_trace_service import registrar_decision_trace


class PuenteDiario9ABase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('propietario9a', password='x')
        self.otro = User.objects.create_user('otro9a', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.cliente_otro = Cliente.objects.get(user=self.otro)
        self.hoy = timezone.localdate()
        for offset in (0, 1):
            SeguimientoVires.objects.create(
                usuario=self.user,
                fecha=self.hoy - timedelta(days=offset),
                cuerpo_cierre='dolorido',
                molestia_zona='espalda',
                molestia_nota='texto íntimo que nunca debe salir',
                notas='otra nota privada',
                descripcion_entrenamiento='descripción privada',
            )
        self.sugerencia = SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='Propuesta privada',
        )


class TestPublicacionAutorizada(PuenteDiario9ABase):
    def test_sin_autorizacion_no_sale_del_diario(self):
        self.assertEqual(
            obtener_proyeccion_senal_autorizada(self.cliente, self.hoy),
            {'hay_senal': False, 'schema_version': 1},
        )

    def test_aceptacion_publica_idempotente_por_14_dias_y_conecta_intervencion(self):
        aceptar_sugerencia(self.sugerencia, fecha_ref=self.hoy)
        aceptar_sugerencia(self.sugerencia, fecha_ref=self.hoy)

        self.assertEqual(SenalEntrenamientoAutorizada.objects.count(), 1)
        senal = SenalEntrenamientoAutorizada.objects.get()
        self.assertEqual(senal.estado, SenalEntrenamientoAutorizada.ESTADO_AUTORIZADA)
        self.assertEqual(senal.vigente_desde, self.hoy)
        self.assertEqual(senal.vigente_hasta, self.hoy + timedelta(days=13))
        intervencion = IntervencionPlan.objects.get(sugerencia=self.sugerencia)
        self.assertEqual(intervencion.tipo, IntervencionPlan.TIPO_VIGILAR_SENAL)
        self.assertEqual(senal.intervencion_id, intervencion.id)

    def test_payload_publico_es_minimo_y_sin_texto_privado(self):
        aceptar_sugerencia(self.sugerencia, fecha_ref=self.hoy)
        payload = obtener_proyeccion_senal_autorizada(self.cliente, self.hoy)

        self.assertEqual(set(payload), {
            'hay_senal', 'schema_version', 'senal_id', 'categoria', 'intensidad',
            'alcance', 'vigente_desde', 'vigente_hasta', 'sugerencia_id',
            'intervencion_id', 'origen',
        })
        self.assertEqual(payload['alcance'], 'observacion')
        self.assertEqual(payload['origen'], {'sistema': 'diario', 'tipo': 'tendencia_corporal'})
        serializado = repr(payload).lower()
        for prohibido in ('nota', 'texto', 'descripcion', 'molestia'):
            self.assertNotIn(prohibido, serializado)

    def test_expiracion_corta_consumo(self):
        aceptar_sugerencia(self.sugerencia, fecha_ref=self.hoy)
        self.assertFalse(
            obtener_proyeccion_senal_autorizada(
                self.cliente, self.hoy + timedelta(days=14)
            )['hay_senal']
        )

    def test_aceptacion_revalida_y_hace_rollback_si_la_senal_ya_no_existe(self):
        from entrenos.services.sugerencias_service import SugerenciaNoVigente

        SeguimientoVires.objects.filter(usuario=self.user).delete()
        with self.assertRaises(SugerenciaNoVigente):
            aceptar_sugerencia(self.sugerencia, fecha_ref=self.hoy)
        self.sugerencia.refresh_from_db()
        self.assertEqual(self.sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertFalse(IntervencionPlan.objects.filter(sugerencia=self.sugerencia).exists())
        self.assertFalse(SenalEntrenamientoAutorizada.objects.exists())


class TestRevocacion(PuenteDiario9ABase):
    def setUp(self):
        super().setUp()
        aceptar_sugerencia(self.sugerencia, fecha_ref=self.hoy)
        self.senal = SenalEntrenamientoAutorizada.objects.get()

    def test_revocacion_es_inmediata_idempotente_y_no_borra_historia(self):
        primera = revocar_senal_autorizada(self.senal, fecha_ref=self.hoy)
        segunda = revocar_senal_autorizada(self.senal, fecha_ref=self.hoy)
        self.assertEqual(primera.pk, segunda.pk)
        self.senal.refresh_from_db()
        self.assertEqual(self.senal.estado, SenalEntrenamientoAutorizada.ESTADO_REVOCADA)
        self.assertIsNotNone(self.senal.revocada_en)
        self.assertFalse(obtener_proyeccion_senal_autorizada(self.cliente, self.hoy)['hay_senal'])
        self.assertTrue(SugerenciaPlan.objects.filter(pk=self.sugerencia.pk).exists())
        self.assertEqual(
            IntervencionPlan.objects.get(pk=self.senal.intervencion_id).estado,
            IntervencionPlan.ESTADO_CANCELADA,
        )

    def test_endpoint_es_post_y_solo_propietario(self):
        url = reverse('clientes:revocar_senal_diario', args=[self.senal.pk])
        self.client.force_login(self.otro)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.senal.refresh_from_db()
        self.assertEqual(self.senal.estado, SenalEntrenamientoAutorizada.ESTADO_REVOCADA)

    def test_centro_ofrece_retirar_la_observacion_autorizada(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('clientes:plan_decisiones'))

        self.assertContains(
            response,
            reverse('clientes:revocar_senal_diario', args=[self.senal.pk]),
        )
        self.assertContains(response, 'Dejar de compartir')


class TestDashboardNoFiltraPrivado(PuenteDiario9ABase):
    def test_contexto_y_explicacion_no_reciben_senal_sin_autorizacion(self):
        from clientes.views import _ctx_explicacion_decision, _ctx_senal_corporal_diario

        payload = _ctx_senal_corporal_diario(self.cliente)
        self.assertEqual(payload, {'hay_senal': False, 'schema_version': 1})
        explicacion = _ctx_explicacion_decision({'estado': 'entrenar'}, payload)
        self.assertNotIn('diario', repr(explicacion).lower())

    def test_trace_guarda_solo_id_y_version_cuando_senal_fue_visible(self):
        aceptar_sugerencia(self.sugerencia, fecha_ref=self.hoy)
        senal = SenalEntrenamientoAutorizada.objects.get()
        registrar_decision_trace(
            self.cliente,
            {
                'estado': 'entrenar',
                'causa_principal': 'plan',
                'distribucion_aviso': {'tipo': 'vigilar_senal'},
            },
            fecha=self.hoy,
        )
        trace = self.cliente.decision_traces.get(fecha=self.hoy)
        self.assertEqual(
            trace.senales_autorizadas,
            [{'id': senal.id, 'schema_version': senal.schema_version}],
        )
        self.assertNotIn('texto', repr(trace.senales_autorizadas).lower())
