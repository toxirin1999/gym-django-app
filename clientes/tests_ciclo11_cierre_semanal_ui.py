import json
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    ContratoSemanalGym,
    EstrategiaSemanalGym,
    EvaluacionSemanalGym,
    SesionProgramada,
)


class CierreSemanalCentroTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre_ui', password='x')
        self.otro = User.objects.create_user('cierre_ui_otro', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.cliente.dias_disponibles = 5
        self.cliente.save(update_fields=['dias_disponibles'])
        self.lunes = date(2026, 8, 3)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5,
            minimo_valido=3, vigente_desde=self.lunes, aprobado_por=self.user,
        )
        self.contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia,
            semana=self.lunes, objetivo_sesiones=5, minimo_valido=3,
        )
        for indice in range(5):
            SesionProgramada.objects.create(
                cliente=self.cliente, contrato_semanal=self.contrato,
                semana_prescrita=self.lunes,
                fecha_prevista=self.lunes + timedelta(days=indice),
                estado=SesionProgramada.ESTADO_PENDIENTE,
                nombre_sesion=f'Día {indice + 1}', dia_numero=indice + 1,
            )

    def _evaluacion(self, estado=EvaluacionSemanalGym.ESTADO_PENDIENTE):
        return EvaluacionSemanalGym.objects.create(
            contrato=self.contrato,
            estado_cumplimiento=EvaluacionSemanalGym.CUMPLIMIENTO_MINIMA_VALIDA,
            sesiones_completadas=3,
            sesiones_reubicadas=1,
            estado_revision=estado,
            evidencia_snapshot={
                'objetivo_sesiones': 5,
                'minimo_valido': 3,
                'metricas': {
                    'volumen_total_kg': '3450.50',
                    'duracion_total_minutos': 145,
                    'energia_pre_sesion_media': 7.5,
                    'rpe_medio': None,
                    'cobertura': {
                        'volumen': {'disponibles': 3, 'total': 3},
                        'duracion': {'disponibles': 2, 'total': 3},
                        'energia_pre_sesion': {'disponibles': 2, 'total': 3},
                        'rpe': {'disponibles': 0, 'total': 3},
                    },
                },
            },
        )

    def _get(self, user=None):
        self.client.force_login(user or self.user)
        return self.client.get(reverse('clientes:plan_decisiones'))

    def test_get_es_read_only_y_sin_evaluacion_no_muestra_bloque_vacio(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EvaluacionSemanalGym.objects.count(), 0)
        self.assertNotContains(response, 'Cierre semanal')

    def test_card_pendiente_explica_acuerdo_realidad_y_solo_metricas_con_cobertura(self):
        evaluacion = self._evaluacion()
        response = self._get()
        self.assertContains(response, 'Cierre semanal', count=1)
        self.assertContains(response, 'Requiere tu revisión')
        self.assertContains(response, 'Mínima válida')
        self.assertContains(response, '3 de 5')
        self.assertContains(response, 'Mínimo acordado: 3')
        self.assertContains(response, '1 reubicada')
        self.assertContains(response, '3450,50')
        self.assertContains(response, '145 min')
        self.assertContains(response, '7,5')
        self.assertNotContains(response, 'RPE medio')
        self.assertContains(response, '2 de 3 sesiones con duración')
        self.assertContains(response, reverse('clientes:aceptar_cierre_semanal', args=[evaluacion.pk]))
        self.assertContains(response, reverse('clientes:rechazar_cierre_semanal', args=[evaluacion.pk]))

    def test_aceptar_y_rechazar_hacen_prg_sin_mutar_estrategia_ni_dias(self):
        for aceptar, nombre_url, estado in (
            (True, 'aceptar_cierre_semanal', EvaluacionSemanalGym.ESTADO_ACEPTADA),
            (False, 'rechazar_cierre_semanal', EvaluacionSemanalGym.ESTADO_RECHAZADA),
        ):
            evaluacion = self._evaluacion()
            self.client.force_login(self.user)
            response = self.client.post(reverse(f'clientes:{nombre_url}', args=[evaluacion.pk]))
            self.assertRedirects(response, reverse('clientes:plan_decisiones'))
            evaluacion.refresh_from_db()
            self.assertEqual(evaluacion.estado_revision, estado)
            self.estrategia.refresh_from_db()
            self.cliente.refresh_from_db()
            self.assertEqual((self.estrategia.objetivo_sesiones, self.estrategia.minimo_valido), (5, 3))
            self.assertEqual(self.cliente.dias_disponibles, 5)
            evaluacion.delete()

    def test_otro_usuario_recibe_404_y_get_en_endpoint_recibe_405(self):
        evaluacion = self._evaluacion()
        self.client.force_login(self.otro)
        url = reverse('clientes:aceptar_cierre_semanal', args=[evaluacion.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_revisada_se_muestra_compacta_sin_formularios(self):
        evaluacion = self._evaluacion(EvaluacionSemanalGym.ESTADO_ACEPTADA)
        response = self._get()
        self.assertContains(response, 'Lectura confirmada')
        self.assertNotContains(response, reverse('clientes:aceptar_cierre_semanal', args=[evaluacion.pk]))
        self.assertNotContains(response, reverse('clientes:rechazar_cierre_semanal', args=[evaluacion.pk]))


class CerrarSemanaGymCommandTests(CierreSemanalCentroTests):
    def test_dry_run_no_persiste_y_apply_si_persiste_json_determinista(self):
        salida = StringIO()
        call_command(
            'cerrar_semana_gym', '--cliente', str(self.cliente.pk),
            '--semana', self.lunes.isoformat(), stdout=salida,
        )
        self.assertEqual(EvaluacionSemanalGym.objects.count(), 0)
        preview = json.loads(salida.getvalue())
        self.assertEqual(preview['modo'], 'dry-run')
        self.assertEqual(preview['semana'], self.lunes.isoformat())

        salida = StringIO()
        call_command(
            'cerrar_semana_gym', '--cliente', str(self.cliente.pk),
            '--semana', self.lunes.isoformat(), '--apply', stdout=salida,
        )
        self.assertEqual(EvaluacionSemanalGym.objects.count(), 1)
        aplicado = json.loads(salida.getvalue())
        self.assertEqual(aplicado['modo'], 'apply')
        self.assertEqual(aplicado['evaluacion_id'], EvaluacionSemanalGym.objects.get().pk)

    def test_command_rechaza_cliente_contrato_y_semana_invalidos(self):
        with self.assertRaises(CommandError):
            call_command('cerrar_semana_gym', '--cliente', '999999', '--semana', self.lunes.isoformat())
        self.contrato.sesiones.last().delete()
        with self.assertRaises(CommandError):
            call_command('cerrar_semana_gym', '--cliente', str(self.cliente.pk), '--semana', self.lunes.isoformat())
        with self.assertRaises(CommandError):
            call_command('cerrar_semana_gym', '--cliente', str(self.cliente.pk), '--semana', '2026-08-10')
