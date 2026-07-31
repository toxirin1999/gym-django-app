from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import IntervencionPlan, SugerenciaPlan
from entrenos.services.hipotesis_service import (
    aceptar_sugerencia_hipotesis,
    ignorar_sugerencia_hipotesis,
)
from entrenos.services.sugerencias_service import (
    aceptar_sugerencia,
    ignorar_sugerencia,
)


class CentroDecisionesEtapa3B1Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('centro_3b1', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.login(username='centro_3b1', password='x')
        self.hoy = timezone.localdate()

    def sugerencia(self, patron, texto='Propuesta concreta.'):
        return SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron=patron,
            texto=texto,
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )


class TestSeparacionDeEndpoints(CentroDecisionesEtapa3B1Base):
    def test_endpoint_generico_no_acepta_hipotesis(self):
        sugerencia = self.sugerencia('hipotesis_senal_entrenar')

        response = self.client.post(
            reverse('clientes:aceptar_sugerencia', args=[sugerencia.pk])
        )

        self.assertEqual(response.status_code, 404)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertFalse(IntervencionPlan.objects.filter(sugerencia=sugerencia).exists())

    def test_endpoint_generico_no_ignora_hipotesis(self):
        sugerencia = self.sugerencia('hipotesis_senal_entrenar')

        response = self.client.post(
            reverse('clientes:ignorar_sugerencia', args=[sugerencia.pk])
        )

        self.assertEqual(response.status_code, 404)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)

    def test_endpoints_hipotesis_no_mutan_sugerencia_ordinaria(self):
        sugerencia = self.sugerencia('esenciales_frecuentes')

        aceptar = self.client.post(
            reverse('clientes:aceptar_hipotesis', args=[sugerencia.pk])
        )
        ignorar = self.client.post(
            reverse('clientes:ignorar_hipotesis', args=[sugerencia.pk])
        )

        self.assertEqual(aceptar.status_code, 404)
        self.assertEqual(ignorar.status_code, 404)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertFalse(IntervencionPlan.objects.filter(sugerencia=sugerencia).exists())


class TestSeparacionEnServicios(CentroDecisionesEtapa3B1Base):
    def test_servicio_generico_rechaza_hipotesis(self):
        sugerencia = self.sugerencia('hipotesis_senal_entrenar')

        with self.assertRaises(ValueError):
            aceptar_sugerencia(sugerencia, fecha_ref=self.hoy)
        with self.assertRaises(ValueError):
            ignorar_sugerencia(sugerencia)

        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)

    def test_servicio_hipotesis_rechaza_sugerencia_ordinaria(self):
        sugerencia = self.sugerencia('esenciales_frecuentes')

        with self.assertRaises(ValueError):
            aceptar_sugerencia_hipotesis(sugerencia, fecha_ref=self.hoy)
        with self.assertRaises(ValueError):
            ignorar_sugerencia_hipotesis(sugerencia, fecha_ref=self.hoy)

        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)


class TestAceptacionHipotesisIdempotente(CentroDecisionesEtapa3B1Base):
    def test_post_repetido_devuelve_misma_intervencion_y_no_duplica(self):
        sugerencia = self.sugerencia('hipotesis_senal_entrenar')

        primera = aceptar_sugerencia_hipotesis(sugerencia, fecha_ref=self.hoy)
        segunda = aceptar_sugerencia_hipotesis(sugerencia, fecha_ref=self.hoy)

        self.assertEqual(segunda.pk, primera.pk)
        self.assertEqual(
            IntervencionPlan.objects.filter(sugerencia=sugerencia).count(),
            1,
        )


class TestSugerenciaOrdinariaPrioritaria(CentroDecisionesEtapa3B1Base):
    def test_centro_oculta_ordinarias_legacy_y_mantiene_hipotesis_separada(self):
        antigua = self.sugerencia('distribucion_dias_reales_menores', 'Propuesta antigua.')
        reciente = self.sugerencia('esenciales_frecuentes', 'Revisar volumen real.')
        hipotesis = self.sugerencia('hipotesis_senal_entrenar', 'Observar una señal.')
        SugerenciaPlan.objects.filter(pk=antigua.pk).update(
            fecha_generada=timezone.now() - timedelta(days=2)
        )
        SugerenciaPlan.objects.filter(pk=reciente.pk).update(
            fecha_generada=timezone.now() - timedelta(days=1)
        )

        response = self.client.get(reverse('clientes:plan_decisiones'))

        self.assertIsNone(response.context['sugerencia_prioritaria'])
        self.assertEqual(response.context['sugerencia_hipotesis'].pk, hipotesis.pk)
        self.assertNotContains(response, 'Revisar volumen real.')
        self.assertNotContains(response, 'esenciales_frecuentes')
        self.assertNotContains(response, 'Propuesta antigua.')

    def test_get_no_reactiva_ni_genera_sugerencias(self):
        ignorada = self.sugerencia('esenciales_frecuentes')
        ignorada.estado = SugerenciaPlan.ESTADO_IGNORADA
        ignorada.cooldown_hasta = self.hoy - timedelta(days=1)
        ignorada.save(update_fields=['estado', 'cooldown_hasta'])

        self.client.get(reverse('clientes:plan_decisiones'))

        ignorada.refresh_from_db()
        self.assertEqual(ignorada.estado, SugerenciaPlan.ESTADO_IGNORADA)
        self.assertEqual(SugerenciaPlan.objects.count(), 1)
