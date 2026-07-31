from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import IntervencionPlan, SugerenciaPlan
from entrenos.services.contrato_sugerencia_service import (
    construir_contrato_sugerencia,
    revalidar_sugerencia,
    validar_contrato_snapshot,
)
from entrenos.services.sugerencias_service import (
    SugerenciaNoVigente,
    aceptar_sugerencia,
    consultar_sugerencia_activa,
    get_sugerencia_activa,
)


def semanas_que_cumplen():
    return [
        {'lunes': date(2026, 7, 13), 'domingo': date(2026, 7, 19), 'hay_datos': True,
         'sesiones_completadas': 4, 'sesiones_esenciales': 2},
        {'lunes': date(2026, 7, 6), 'domingo': date(2026, 7, 12), 'hay_datos': True,
         'sesiones_completadas': 3, 'sesiones_esenciales': 2},
        {'lunes': date(2026, 6, 29), 'domingo': date(2026, 7, 5), 'hay_datos': True,
         'sesiones_completadas': 3, 'sesiones_esenciales': 0},
    ]


class ContratoSugerenciaV1Tests(TestCase):
    def setUp(self):
        self.hoy = date(2026, 7, 20)
        self.user = User.objects.create_user('contrato-v1', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def crear(self, snapshot=None):
        return SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='esenciales_frecuentes',
            texto='Texto heredado',
            contrato_snapshot=snapshot,
        )

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_constructor_cuantifica_evidencia_y_declara_limites(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        contrato = construir_contrato_sugerencia(
            self.cliente, 'esenciales_frecuentes', self.hoy,
        )
        self.assertTrue(validar_contrato_snapshot(contrato))
        self.assertEqual(contrato['evidencia']['semanas_que_cumplen'], 2)
        self.assertEqual(contrato['cambio']['codigo'], 'freeze_load_increases')
        self.assertEqual(contrato['cambio']['duracion_dias'], 7)
        self.assertIn('volumen', contrato['limites']['no_demuestra'])
        self.assertIn('fatiga', contrato['limites']['no_demuestra'])

    def test_legacy_sin_snapshot_permanece_oculta(self):
        self.crear()
        self.assertIsNone(consultar_sugerencia_activa(self.cliente, self.hoy))

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_snapshot_valido_pero_patron_actual_ausente_se_oculta(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        contrato = construir_contrato_sugerencia(self.cliente, 'esenciales_frecuentes', self.hoy)
        sugerencia = self.crear(contrato)
        recopilar.return_value = [dict(s, sesiones_esenciales=0) for s in semanas_que_cumplen()]
        self.assertIsNone(consultar_sugerencia_activa(self.cliente, self.hoy))
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_aceptacion_revalida_y_dura_siete_dias_inclusivos(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        contrato = construir_contrato_sugerencia(self.cliente, 'esenciales_frecuentes', self.hoy)
        sugerencia = self.crear(contrato)
        aceptar_sugerencia(sugerencia, self.hoy)
        intervencion = IntervencionPlan.objects.get(sugerencia=sugerencia)
        self.assertEqual(intervencion.tipo, IntervencionPlan.TIPO_NO_SUBIR)
        self.assertEqual(intervencion.fecha_inicio, self.hoy)
        self.assertEqual(intervencion.fecha_fin, self.hoy + timedelta(days=6))

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_aceptacion_rechaza_si_la_evidencia_cambio(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        contrato = construir_contrato_sugerencia(self.cliente, 'esenciales_frecuentes', self.hoy)
        sugerencia = self.crear(contrato)
        recopilar.return_value = [dict(s, sesiones_esenciales=0) for s in semanas_que_cumplen()]
        with self.assertRaises(SugerenciaNoVigente):
            aceptar_sugerencia(sugerencia, self.hoy)
        self.assertFalse(IntervencionPlan.objects.exists())

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_cambio_de_cuentas_invalida_aunque_el_patron_siga_cumpliendo(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        contrato = construir_contrato_sugerencia(self.cliente, 'esenciales_frecuentes', self.hoy)
        sugerencia = self.crear(contrato)
        actualizadas = semanas_que_cumplen()
        actualizadas[0] = dict(actualizadas[0], sesiones_esenciales=3)
        recopilar.return_value = actualizadas
        self.assertIsNone(revalidar_sugerencia(sugerencia, self.hoy))
        with self.assertRaises(SugerenciaNoVigente):
            aceptar_sugerencia(sugerencia, self.hoy)
        self.assertFalse(IntervencionPlan.objects.exists())

    def test_patron_desconocido_no_puede_aceptarse(self):
        sugerencia = SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='patron_sin_ejecutor',
            texto='Desconocida',
        )
        with self.assertRaises(ValueError):
            aceptar_sugerencia(sugerencia, self.hoy)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertFalse(IntervencionPlan.objects.exists())

    def test_esenciales_sin_snapshot_no_puede_aceptarse(self):
        sugerencia = self.crear(snapshot=None)
        with self.assertRaises(SugerenciaNoVigente):
            aceptar_sugerencia(sugerencia, self.hoy)
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)
        self.assertFalse(IntervencionPlan.objects.exists())

    @patch('entrenos.services.analisis_semanal_service._detectar_patrones_activos', return_value=['esenciales_frecuentes'])
    @patch('entrenos.services.analisis_semanal_service._recopilar_semanas')
    @patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento')
    def test_patron_sin_consentimiento_no_frena(self, analizar, recopilar, detectar):
        analizar.return_value = {'hay_datos': True, 'estado_semana': 'solida'}
        recopilar.return_value = semanas_que_cumplen()
        from entrenos.services.progresion_contextual_service import evaluar_permiso_progresion
        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertEqual(permiso['accion'], 'progresion_permitida')

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_comando_dry_run_no_muta_y_apply_adjunta_snapshot(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        sugerencia = self.crear()
        out = StringIO()
        call_command('revalidar_sugerencias_plan', cliente_id=self.cliente.pk, stdout=out)
        sugerencia.refresh_from_db()
        self.assertIsNone(sugerencia.contrato_snapshot)
        self.assertIn('eligible=1 applied=0', out.getvalue())
        out = StringIO()
        call_command('revalidar_sugerencias_plan', cliente_id=self.cliente.pk, apply=True, stdout=out)
        sugerencia.refresh_from_db()
        self.assertTrue(validar_contrato_snapshot(sugerencia.contrato_snapshot))
        self.assertIn('eligible=1 applied=1', out.getvalue())

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_cooldown_vencido_crea_episodio_nuevo(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        anterior = self.crear()
        anterior.estado = SugerenciaPlan.ESTADO_IGNORADA
        anterior.cooldown_hasta = self.hoy - timedelta(days=1)
        anterior.save(update_fields=['estado', 'cooldown_hasta'])
        with patch(
            'entrenos.services.analisis_semanal_service.obtener_sugerencia_con_patron',
            return_value={'patron': 'esenciales_frecuentes', 'texto': 'Nueva evidencia'},
        ):
            nueva = get_sugerencia_activa(self.cliente, self.hoy)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, SugerenciaPlan.ESTADO_IGNORADA)
        self.assertNotEqual(nueva.pk, anterior.pk)
        self.assertIsNotNone(nueva.contrato_snapshot)

    @patch('entrenos.services.contrato_sugerencia_service._recopilar_semanas')
    def test_tarjeta_explica_contrato_y_cta_exacto(self, recopilar):
        recopilar.return_value = semanas_que_cumplen()
        contrato = construir_contrato_sugerencia(self.cliente, 'esenciales_frecuentes', self.hoy)
        self.crear(contrato)
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('clientes:plan_decisiones'))
        self.assertContains(response, '2 de las últimas 3 semanas')
        self.assertContains(response, 'No demuestra que tengas demasiado volumen')
        self.assertContains(response, '4 completadas · 2 esenciales (50%)')
        self.assertContains(response, '13/07/2026–19/07/2026')
        self.assertContains(response, 'último peso que realizaste')
        self.assertContains(response, 'Si el plan propone una bajada, la respetaremos')
        self.assertContains(response, 'Mantener cargas 7 días')
        self.assertContains(response, 'No cambiaremos ejercicios, series, repeticiones ni días')
        self.assertNotContains(response, 'Probar este ajuste')
