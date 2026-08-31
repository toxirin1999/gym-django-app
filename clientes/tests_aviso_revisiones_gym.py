from datetime import date, timedelta

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


class AvisoRevisionesGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('revisiones_portada', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.inicio = date(2026, 7, 6)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=4,
            minimo_valido=2,
            vigente_desde=self.inicio,
            aprobado_por=self.user,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente,
            version=1,
            estado=ContratoBloqueGym.ESTADO_FINALIZADO,
            semana_inicio=self.inicio,
            semanas_previstas=4,
            semana_fin_prevista=self.inicio + timedelta(days=27),
            estrategia=self.estrategia,
            objetivo_sesiones=4,
            minimo_valido=2,
            objetivo_principal='Consolidar fuerza',
            objetivos_secundarios=[],
            limites_snapshot={},
            motor_nombre='Helms',
            motor_version='test',
            fingerprint='aviso-revisiones',
            aprobado_por=self.user,
        )
        self.client.force_login(self.user)

    def _evaluacion_semanal(self, semana, estado):
        contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente,
            estrategia=self.estrategia,
            bloque=self.bloque,
            indice_semana_bloque=((semana - self.inicio).days // 7) + 1,
            semana=semana,
            objetivo_sesiones=4,
            minimo_valido=2,
        )
        return EvaluacionSemanalGym.objects.create(
            contrato=contrato,
            estado_cumplimiento=EvaluacionSemanalGym.CUMPLIMIENTO_MINIMA_VALIDA,
            sesiones_completadas=2,
            estado_revision=estado,
        )

    def _evaluacion_bloque(self, version, estado):
        return EvaluacionBloqueGym.objects.create(
            bloque=self.bloque,
            version_calculo=version,
            fingerprint_evidencia=f'aviso-{version}',
            estado_resultado=EvaluacionBloqueGym.RESULTADO_MINIMO,
            estado_revision=estado,
        )

    def test_portada_cuenta_todas_y_avisa_en_ahora_con_contexto_y_enlace(self):
        self._evaluacion_semanal(self.inicio, EvaluacionSemanalGym.ESTADO_PENDIENTE)
        self._evaluacion_semanal(
            self.inicio + timedelta(weeks=1),
            EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )
        self._evaluacion_bloque(1, EvaluacionBloqueGym.REVISION_PENDIENTE)
        self._evaluacion_bloque(2, EvaluacionBloqueGym.REVISION_ACEPTADA)

        response = self.client.get(reverse('clientes:mockup_demo'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['revisiones_gym_pendientes']['total'], 3)
        self.assertEqual(response.context['revisiones_gym_pendientes']['semanales'], 2)
        self.assertEqual(response.context['revisiones_gym_pendientes']['bloques'], 1)
        contenido = response.content.decode()
        ahora = contenido.index('id="chapter-ahora"')
        entreno = contenido.index('id="chapter-entrenamiento"')
        aviso = contenido.index('data-revisiones-gym-pendientes')
        self.assertLess(ahora, aviso)
        self.assertLess(aviso, entreno)
        self.assertContains(response, '3 revisiones Gym pendientes')
        self.assertContains(response, '2 semanas')
        self.assertContains(response, '1 bloque')
        self.assertContains(response, reverse('clientes:plan_decisiones'))

    def test_aviso_singular_persiste_con_pendiente_antigua_y_no_bloquea_la_portada(self):
        pendiente = self._evaluacion_semanal(
            self.inicio,
            EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )
        self._evaluacion_semanal(
            self.inicio + timedelta(weeks=1),
            EvaluacionSemanalGym.ESTADO_ACEPTADA,
        )

        response = self.client.get(reverse('clientes:mockup_demo'))

        self.assertContains(response, '1 revisión Gym pendiente')
        self.assertContains(response, f'Semana del {pendiente.contrato.semana:%d/%m/%Y}')
        self.assertContains(response, 'Revisar en el Centro')
        self.assertNotContains(response, 'Entrenamiento bloqueado')

    def test_centro_prioriza_la_pendiente_mas_antigua_aunque_haya_una_posterior_respondida(self):
        pendiente = self._evaluacion_semanal(
            self.inicio,
            EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )
        respondida = self._evaluacion_semanal(
            self.inicio + timedelta(weeks=1),
            EvaluacionSemanalGym.ESTADO_ACEPTADA,
        )

        response = self.client.get(reverse('clientes:plan_decisiones'))

        self.assertEqual(response.context['cierre_semanal'].pk, pendiente.pk)
        self.assertContains(
            response,
            reverse('clientes:aceptar_cierre_semanal', args=[pendiente.pk]),
        )
        self.assertNotContains(
            response,
            reverse('clientes:aceptar_cierre_semanal', args=[respondida.pk]),
        )
