from datetime import date, timedelta
from unittest.mock import MagicMock, patch

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
    SesionProgramada,
)
from entrenos.services.proyeccion_bloque_gym_service import proyectar_bloque_gym


class ProyeccionBloqueGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('portada_bloque', password='x')
        self.otro_user = User.objects.create_user('portada_bloque_otro', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.inicio = date(2026, 8, 3)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5,
            minimo_valido=3, vigente_desde=self.inicio, aprobado_por=self.user,
        )

    def _bloque(self, estado=ContratoBloqueGym.ESTADO_ACTIVO):
        return ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=1, estado=estado,
            semana_inicio=self.inicio, semanas_previstas=4,
            semana_fin_prevista=self.inicio + timedelta(days=27),
            estrategia=self.estrategia, objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='Construir fuerza útil',
            objetivos_secundarios=['Mejorar sentadilla', 'Sostener técnica'],
            limites_snapshot={'dolor_maximo': 2}, motor_nombre='Helms',
            motor_version='11A', fingerprint=f'fp-{estado}', aprobado_por=self.user,
        )

    def _contrato(self, bloque, indice=3):
        semana = self.inicio + timedelta(weeks=indice - 1)
        return ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia, bloque=bloque,
            indice_semana_bloque=indice, semana=semana,
            objetivo_sesiones=5, minimo_valido=3,
        )

    def test_sin_bloque_devuelve_evidencia_no_disponible_sin_inventar_cero(self):
        resultado = proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 17))
        self.assertEqual(resultado['estado_evidencia'], 'evidencia_no_disponible')
        self.assertFalse(resultado['disponible'])
        self.assertNotIn('sesiones_completadas', resultado)

    def test_bloque_activo_proyecta_snapshot_rango_y_semana_actual(self):
        bloque = self._bloque()
        resultado = proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 18))
        self.assertEqual(resultado['bloque_id'], bloque.pk)
        self.assertEqual(resultado['version'], 1)
        self.assertEqual(resultado['estado'], 'activo')
        self.assertEqual(resultado['semana_actual'], 3)
        self.assertEqual(resultado['semanas_previstas'], 4)
        self.assertEqual(resultado['objetivo_principal'], 'Construir fuerza útil')
        self.assertEqual(resultado['objetivos_secundarios'], ['Mejorar sentadilla', 'Sostener técnica'])
        self.assertEqual(resultado['rango'], {'inicio': self.inicio, 'fin': date(2026, 8, 30)})
        self.assertEqual(resultado['estado_evidencia'], 'evidencia_no_disponible')

    def test_bloque_pausado_se_identifica_sin_materializar_semana(self):
        self._bloque(ContratoBloqueGym.ESTADO_PAUSADO)
        resultado = proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 11))
        self.assertEqual(resultado['estado'], 'pausado')
        self.assertEqual(resultado['semana_actual'], 2)
        self.assertFalse(resultado['progreso_disponible'])
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)

    def test_progreso_cuenta_solo_completadas_vinculadas_y_usa_snapshot_semanal(self):
        bloque = self._bloque()
        contrato = self._contrato(bloque)
        for indice, estado in enumerate([
            SesionProgramada.ESTADO_COMPLETADA,
            SesionProgramada.ESTADO_COMPLETADA,
            SesionProgramada.ESTADO_COMPLETADA,
            SesionProgramada.ESTADO_PENDIENTE,
        ]):
            SesionProgramada.objects.create(
                cliente=self.cliente, contrato_semanal=contrato,
                fecha_prevista=contrato.semana + timedelta(days=indice), estado=estado,
            )
        SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=contrato.semana + timedelta(days=6),
            estado=SesionProgramada.ESTADO_COMPLETADA,
        )
        resultado = proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 18))
        self.assertEqual(resultado['sesiones_completadas'], 3)
        self.assertEqual(resultado['objetivo_sesiones'], 5)
        self.assertEqual(resultado['minimo_valido'], 3)
        self.assertEqual(resultado['estado_cumplimiento'], 'minimo_valido')

    def test_estados_objetivo_e_insuficiente(self):
        for completadas, esperado in ((5, 'objetivo'), (2, 'insuficiente')):
            bloque = self._bloque()
            contrato = self._contrato(bloque)
            for indice in range(completadas):
                SesionProgramada.objects.create(
                    cliente=self.cliente, contrato_semanal=contrato,
                    fecha_prevista=contrato.semana + timedelta(days=indice),
                    estado=SesionProgramada.ESTADO_COMPLETADA,
                )
            self.assertEqual(
                proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 18))['estado_cumplimiento'],
                esperado,
            )
            SesionProgramada.objects.all().delete()
            contrato.delete()
            bloque.delete()

    def test_revision_y_cierre_solo_aparecen_si_estan_persistidos_y_pendientes(self):
        bloque = self._bloque()
        contrato = self._contrato(bloque)
        semanal = EvaluacionSemanalGym.objects.create(
            contrato=contrato, estado_cumplimiento='minima_valida', sesiones_completadas=3,
            estado_revision=EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )
        cierre = EvaluacionBloqueGym.objects.create(
            bloque=bloque, version_calculo=1, fingerprint_evidencia='cierre-fp',
            estado_resultado=EvaluacionBloqueGym.RESULTADO_MINIMO,
            estado_revision=EvaluacionBloqueGym.REVISION_PENDIENTE,
        )
        resultado = proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 18))
        self.assertEqual(resultado['evaluacion_semanal']['id'], semanal.pk)
        self.assertTrue(resultado['requiere_decision'])
        self.assertEqual(resultado['cierre_bloque']['id'], cierre.pk)
        self.assertEqual(resultado['url_decision'], reverse('clientes:plan_decisiones'))
        semanal.estado_revision = EvaluacionSemanalGym.ESTADO_ACEPTADA
        semanal.save(update_fields=['estado_revision'])
        cierre.estado_revision = EvaluacionBloqueGym.REVISION_ACEPTADA
        cierre.save(update_fields=['estado_revision'])
        resultado = proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 18))
        self.assertFalse(resultado['requiere_decision'])
        self.assertNotIn('url_decision', resultado)
        self.assertNotIn('cierre_bloque', resultado)

    def test_privacidad_no_mezcla_bloques_ajenos(self):
        self._bloque()
        resultado = proyectar_bloque_gym(self.otro, fecha=date(2026, 8, 18))
        self.assertFalse(resultado['disponible'])

    def test_multiples_bloques_abiertos_declaran_autoridad_ambigua(self):
        primero = self._bloque()
        segundo = ContratoBloqueGym(
            cliente=self.cliente, version=2, estado=ContratoBloqueGym.ESTADO_PAUSADO,
        )
        consulta = MagicMock()
        consulta.select_related.return_value.__iter__.return_value = iter([primero, segundo])
        consulta.select_related.return_value.__getitem__.return_value = [primero, segundo]
        consulta.select_related.return_value.first.return_value = primero
        with patch.object(ContratoBloqueGym.objects, 'filter', return_value=consulta):
            resultado = proyectar_bloque_gym(self.cliente, fecha=date(2026, 8, 18))
        self.assertFalse(resultado['disponible'])
        self.assertEqual(resultado['estado_evidencia'], 'autoridad_ambigua')
        self.assertFalse(resultado['requiere_decision'])


class PortadaBloqueGymViewTests(TestCase):
    setUp = ProyeccionBloqueGymTests.setUp
    _bloque = ProyeccionBloqueGymTests._bloque
    _contrato = ProyeccionBloqueGymTests._contrato

    def test_get_es_read_only_no_invoca_generadores_y_renderiza_una_vez(self):
        bloque = self._bloque()
        contrato = self._contrato(bloque, indice=3)
        SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=contrato,
            fecha_prevista=date(2026, 8, 17), estado=SesionProgramada.ESTADO_COMPLETADA,
        )
        self.client.force_login(self.user)
        conteos = (
            ContratoBloqueGym.objects.count(), ContratoSemanalGym.objects.count(),
            EvaluacionSemanalGym.objects.count(), EvaluacionBloqueGym.objects.count(),
        )
        with patch('django.utils.timezone.localdate', return_value=date(2026, 8, 18)), \
             patch('entrenos.services.estrategia_semanal_gym_service.abrir_contrato_semanal_gym') as abrir, \
             patch('entrenos.services.contrato_bloque_gym_service.previsualizar_cierre_bloque_gym') as cerrar:
            response = self.client.get(reverse('clientes:mockup_demo'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['proyeccion_bloque_gym']['disponible'], response.context['proyeccion_bloque_gym'])
        abrir.assert_not_called()
        cerrar.assert_not_called()
        self.assertEqual(conteos, (
            ContratoBloqueGym.objects.count(), ContratoSemanalGym.objects.count(),
            EvaluacionSemanalGym.objects.count(), EvaluacionBloqueGym.objects.count(),
        ))
        self.assertContains(response, 'Bloque Gym', count=1)
        self.assertContains(response, 'Semana 3 de 4')
        self.assertContains(response, '1 / 5')
        self.assertContains(response, 'Mejorar sentadilla · Sostener técnica')
        self.assertContains(response, '03/08/2026—30/08/2026')
        self.assertNotContains(response, 'Abrir Centro →')

    def test_autoridad_ambigua_no_renderiza_tarjeta(self):
        self.client.force_login(self.user)
        ambiguo = {
            'disponible': False, 'estado_evidencia': 'autoridad_ambigua',
            'progreso_disponible': False, 'requiere_decision': False,
        }
        with patch(
            'entrenos.services.proyeccion_bloque_gym_service.proyectar_bloque_gym',
            return_value=ambiguo,
        ):
            response = self.client.get(reverse('clientes:mockup_demo'))
        self.assertNotContains(response, 'Bloque Gym')

    def test_sin_bloque_no_renderiza_y_pausado_muestra_etiqueta(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('clientes:mockup_demo'))
        self.assertNotContains(response, 'Bloque Gym')
        self._bloque(ContratoBloqueGym.ESTADO_PAUSADO)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 8, 11)):
            response = self.client.get(reverse('clientes:mockup_demo'))
        self.assertContains(response, 'Bloque Gym', count=1)
        self.assertContains(response, 'Pausado')

    def test_enlace_al_centro_solo_con_revision_pendiente(self):
        bloque = self._bloque()
        contrato = self._contrato(bloque)
        EvaluacionSemanalGym.objects.create(
            contrato=contrato, estado_cumplimiento='insuficiente', sesiones_completadas=1,
            estado_revision=EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )
        self.client.force_login(self.user)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 8, 18)):
            response = self.client.get(reverse('clientes:mockup_demo'))
        self.assertContains(response, reverse('clientes:plan_decisiones'))
        self.assertContains(response, 'Requiere revisión')
