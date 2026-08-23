from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    ContratoBloqueGym,
    ContratoSemanalGym,
    EstrategiaSemanalGym,
    EvaluacionBloqueGym,
    EvaluacionSemanalGym,
)


class CierreBloqueCentroTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre_bloque_ui', password='x')
        self.otro_user = User.objects.create_user('cierre_bloque_ui_otro', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.inicio = date(2026, 7, 6)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=3, objetivo_sesiones=5,
            minimo_valido=3, vigente_desde=self.inicio, aprobado_por=self.user,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=2, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            semana_inicio=self.inicio, semanas_previstas=4,
            semana_fin_prevista=self.inicio + timedelta(days=27),
            estrategia=self.estrategia, objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='Sostener fuerza útil',
            objetivos_secundarios=['Privado: no renderizar'],
            limites_snapshot={'nota_privada': 'SECRETO-LIMITE'},
            motor_nombre='Helms', motor_version='11B', fingerprint='bloque-ui',
            aprobado_por=self.user,
        )

    def _evaluacion(self, *, version=1, estado=EvaluacionBloqueGym.REVISION_PENDIENTE):
        return EvaluacionBloqueGym.objects.create(
            bloque=self.bloque, version_calculo=version,
            fingerprint_evidencia=f'evidencia-{version}',
            estado_resultado=EvaluacionBloqueGym.RESULTADO_MINIMO,
            estado_revision=estado,
            evidencia_snapshot={
                'schema_version': 1,
                'bloque_id': self.bloque.pk,
                'bloque_version': 2,
                'semana_inicio': self.inicio.isoformat(),
                'semana_fin_prevista': (self.inicio + timedelta(days=27)).isoformat(),
                'semanas_previstas': 4,
                'objetivo_sesiones': 5,
                'minimo_valido': 3,
                'semanas': [
                    {'indice': 1, 'cumplimiento': 'objetivo', 'sesiones_completadas': 5,
                     'protegidas_seguridad': 0, 'nota_privada': 'SECRETO-EVIDENCIA'},
                    {'indice': 2, 'cumplimiento': 'minima_valida', 'sesiones_completadas': 3,
                     'protegidas_seguridad': 1},
                ],
                'texto_libre': 'SECRETO-TEXTO-LIBRE',
            },
        )

    def _get(self, user=None):
        self.client.force_login(user or self.user)
        return self.client.get(reverse('clientes:plan_decisiones'))

    def test_get_solo_consulta_ultima_pendiente_propia_sin_generar_ni_mutar(self):
        anterior = self._evaluacion(version=1)
        ultima = self._evaluacion(version=2)
        conteos = (ContratoBloqueGym.objects.count(), EvaluacionBloqueGym.objects.count())
        with patch('entrenos.services.contrato_bloque_gym_service.cerrar_bloque_gym') as cerrar, \
             patch('entrenos.services.contrato_bloque_gym_service.previsualizar_cierre_bloque_gym') as preview:
            response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cierre_bloque'].pk, ultima.pk)
        self.assertNotEqual(response.context['cierre_bloque'].pk, anterior.pk)
        cerrar.assert_not_called()
        preview.assert_not_called()
        self.assertEqual(conteos, (ContratoBloqueGym.objects.count(), EvaluacionBloqueGym.objects.count()))
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.estado, ContratoBloqueGym.ESTADO_ACTIVO)

    def test_card_unica_coexiste_con_cierre_semanal_y_muestra_solo_evidencia_factual(self):
        evaluacion = self._evaluacion()
        contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia, bloque=self.bloque,
            indice_semana_bloque=1, semana=self.inicio,
            objetivo_sesiones=5, minimo_valido=3,
        )
        EvaluacionSemanalGym.objects.create(
            contrato=contrato, estado_cumplimiento=EvaluacionSemanalGym.CUMPLIMIENTO_OBJETIVO,
            sesiones_completadas=5, estado_revision=EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )
        response = self._get()
        self.assertContains(response, 'Cierre del bloque', count=1)
        self.assertContains(response, 'Cierre semanal', count=1)
        self.assertContains(response, 'Sostener fuerza útil')
        self.assertContains(response, '06/07/2026–02/08/2026')
        self.assertContains(response, 'Versión 2')
        self.assertContains(response, 'Mínimo sostenido')
        self.assertContains(response, 'Objetivo semanal: 5 · mínimo válido: 3')
        self.assertContains(response, 'Semana 1:')
        self.assertContains(response, '· 5 sesiones · 0 protegidas')
        self.assertContains(response, 'Semana 2:')
        self.assertContains(response, '· 3 sesiones · 1 protegida')
        self.assertNotContains(response, 'SECRETO-EVIDENCIA')
        self.assertNotContains(response, 'SECRETO-TEXTO-LIBRE')
        self.assertNotContains(response, 'SECRETO-LIMITE')
        self.assertNotContains(response, 'Privado: no renderizar')
        self.assertContains(response, reverse('clientes:aceptar_cierre_bloque', args=[evaluacion.pk]))
        self.assertContains(response, reverse('clientes:rechazar_cierre_bloque', args=[evaluacion.pk]))

    def test_sin_pendiente_propia_no_renderiza_card_ni_filtra_la_ajena(self):
        self._evaluacion(estado=EvaluacionBloqueGym.REVISION_ACEPTADA)
        estrategia_ajena = EstrategiaSemanalGym.objects.create(
            cliente=self.otro, version=1, objetivo_sesiones=4, minimo_valido=2,
            vigente_desde=self.inicio, aprobado_por=self.otro_user,
        )
        bloque_ajeno = ContratoBloqueGym.objects.create(
            cliente=self.otro, version=1, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            semana_inicio=self.inicio, semanas_previstas=4,
            semana_fin_prevista=self.inicio + timedelta(days=27), estrategia=estrategia_ajena,
            objetivo_sesiones=4, minimo_valido=2, objetivo_principal='OBJETIVO-AJENO',
            fingerprint='ajeno', aprobado_por=self.otro_user,
        )
        EvaluacionBloqueGym.objects.create(
            bloque=bloque_ajeno, version_calculo=1, fingerprint_evidencia='eval-ajena',
            estado_resultado=EvaluacionBloqueGym.RESULTADO_OBJETIVO,
        )
        response = self._get()
        self.assertIsNone(response.context['cierre_bloque'])
        self.assertNotContains(response, 'Cierre del bloque')
        self.assertNotContains(response, 'OBJETIVO-AJENO')

    def test_post_aceptar_y_rechazar_delegan_al_servicio_y_hacen_prg(self):
        for aceptar, nombre in ((True, 'aceptar_cierre_bloque'), (False, 'rechazar_cierre_bloque')):
            evaluacion = self._evaluacion()
            self.client.force_login(self.user)
            with patch(
                'entrenos.services.contrato_bloque_gym_service.responder_evaluacion_bloque_gym'
            ) as responder:
                response = self.client.post(reverse(f'clientes:{nombre}', args=[evaluacion.pk]))
            self.assertRedirects(response, reverse('clientes:plan_decisiones'))
            responder.assert_called_once_with(evaluacion, actor=self.user, aceptar=aceptar)
            evaluacion.delete()

    def test_endpoints_exigen_post_login_ownership_y_pendiente_sin_mutacion(self):
        evaluacion = self._evaluacion()
        url = reverse('clientes:aceptar_cierre_bloque', args=[evaluacion.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.otro_user)
        self.assertEqual(self.client.post(url).status_code, 404)
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado_revision, EvaluacionBloqueGym.REVISION_PENDIENTE)
        self.client.force_login(self.user)
        evaluacion.estado_revision = EvaluacionBloqueGym.REVISION_RECHAZADA
        evaluacion.save(update_fields=['estado_revision'])
        self.assertEqual(self.client.post(url).status_code, 404)
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado_revision, EvaluacionBloqueGym.REVISION_RECHAZADA)
