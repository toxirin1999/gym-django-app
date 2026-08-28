import json
from datetime import date, datetime, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.centro_decisiones_service import agrupar_traces_recientes
from entrenos.services.sesion_recomendada import (
    CierreSesionProgramadaInvalido,
    cerrar_sesion_programada,
)
from rutinas.models import Rutina


class CierreSesionProgramadaContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-explicito')
        self.otro_user = User.objects.create_user('cierre-explicito-otro')
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.rutina = Rutina.objects.create(nombre='Día causal')
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 8, 27),
            fecha_ejecucion=date(2026, 8, 28),
        )

    def test_resultado_observable_y_fecha_real_efectiva(self):
        sp = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 8, 27),
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='Día causal',
        )
        resultado = cerrar_sesion_programada(sp.pk, self.entreno)
        sp.refresh_from_db()
        self.assertEqual(resultado['estado'], 'cerrada')
        self.assertEqual(sp.fecha_realizada, date(2026, 8, 28))
        self.assertEqual(sp.entreno_realizado, self.entreno)

    def test_rechaza_cliente_ajeno_y_estado_no_pendiente(self):
        ajena = SesionProgramada.objects.create(
            cliente=self.otro, fecha_prevista=date(2026, 8, 27),
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )
        with self.assertRaises(CierreSesionProgramadaInvalido):
            cerrar_sesion_programada(ajena.pk, self.entreno)
        cerrada = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 8, 28),
            estado=SesionProgramada.ESTADO_COMPLETADA,
        )
        with self.assertRaises(CierreSesionProgramadaInvalido):
            cerrar_sesion_programada(cerrada.pk, self.entreno)


class PortalSesionProgramadaCausalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('portal-sp', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.hoy = date.today()

    @patch('clientes.views.obtener_proximo_entrenamiento')
    def test_get_transporta_id_y_post_cierra_misma_sesion(self, proximo):
        proximo.return_value = {'fecha': self.hoy, 'rutina_nombre': 'Push causal', 'ejercicios': []}
        BitacoraDiaria.objects.create(
            cliente=self.cliente, energia_subjetiva=8, dolor_articular=0, horas_sueno=8,
        )
        sp = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=self.hoy,
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='Push causal',
        )
        response = self.client.get(reverse('clientes:portal_sesion', args=[self.cliente.pk]))
        self.assertContains(response, f'name="sesion_programada_id" value="{sp.pk}"')

        response = self.client.post(reverse('clientes:guardar_entrenamiento_activo', args=[self.cliente.pk]), {
            'fecha': self.hoy.isoformat(), 'rutina_nombre': 'Push causal',
            'sesion_programada_id': str(sp.pk), 'ej1_nombre': 'Press banca',
            'ej1_peso_1': '60', 'ej1_reps_1': '8', 'ej1_completado_1': '1',
        })
        self.assertEqual(response.status_code, 302)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertIsNotNone(sp.entreno_realizado_id)

    def test_post_id_ajeno_revierte_entrenamiento(self):
        otro_user = User.objects.create_user('portal-sp-otro')
        otro = Cliente.objects.get(user=otro_user)
        sp = SesionProgramada.objects.create(
            cliente=otro, fecha_prevista=self.hoy,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )
        self.client.post(reverse('clientes:guardar_entrenamiento_activo', args=[self.cliente.pk]), {
            'fecha': self.hoy.isoformat(), 'rutina_nombre': 'Ajena',
            'sesion_programada_id': str(sp.pk),
        })
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=self.cliente).count(), 0)


class AnalyticsSesionProgramadaCausalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('analytics-sp', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    def test_api_solo_cierra_id_explicito(self):
        sp = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 8, 27),
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='API causal',
        )
        url = reverse('analytics:api_marcar_completado', args=[self.cliente.pk])
        payload = {'fecha': '2026-08-27', 'rutina_nombre': 'API causal', 'ejercicios': [
            {'nombre': 'Press', 'series': 1, 'repeticiones': '8', 'peso_recomendado_kg': 10},
        ]}
        self.client.post(url, data=json.dumps(payload), content_type='application/json')
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PENDIENTE)
        payload['sesion_programada_id'] = sp.pk
        self.client.post(url, data=json.dumps(payload), content_type='application/json')
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_COMPLETADA)


class ReconciliarSesionProgramadaCommandTests(TestCase):
    def test_dry_run_apply_e_idempotencia_match_unico(self):
        user = User.objects.create_user('reconciliar-sp')
        cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre='Rutina única')
        sp = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 8, 27),
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='Rutina única',
        )
        entreno = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=rutina, fecha=date(2026, 8, 27),
            fecha_ejecucion=date(2026, 8, 27),
        )
        out = StringIO()
        call_command('reconciliar_sesiones_programadas_gym', cliente=cliente.pk, stdout=out)
        self.assertIn('unique_safe_match', out.getvalue())
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PENDIENTE)
        call_command('reconciliar_sesiones_programadas_gym', cliente=cliente.pk, apply=True, stdout=StringIO())
        sp.refresh_from_db()
        self.assertEqual(sp.entreno_realizado, entreno)
        out = StringIO()
        call_command('reconciliar_sesiones_programadas_gym', cliente=cliente.pk, stdout=out)
        self.assertIn('already_linked', out.getvalue())

    def test_completada_sin_fk_con_match_unico_se_clasifica_y_repara(self):
        user = User.objects.create_user('reconciliar-completada')
        cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre='Rutina completada')
        sp = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 8, 27),
            fecha_realizada=date(2026, 8, 27),
            estado=SesionProgramada.ESTADO_COMPLETADA,
            nombre_sesion='Rutina completada',
        )
        entreno = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=rutina, fecha=date(2026, 8, 27),
            fecha_ejecucion=date(2026, 8, 27),
        )
        out = StringIO()
        call_command('reconciliar_sesiones_programadas_gym', cliente=cliente.pk, stdout=out)
        registro = json.loads(out.getvalue().splitlines()[0])
        self.assertEqual(registro['classification'], 'completed_missing_fk')
        self.assertEqual(registro['match_status'], 'unique_safe_match')

        call_command(
            'reconciliar_sesiones_programadas_gym', cliente=cliente.pk,
            apply=True, stdout=StringIO(),
        )
        sp.refresh_from_db()
        self.assertEqual(sp.entreno_realizado, entreno)

    def test_omision_anticipada_se_diagnostica_y_restaura_sin_completar(self):
        user = User.objects.create_user('reconciliar-omision-anticipada')
        cliente = Cliente.objects.get(user=user)
        motivo = 'Sesión omitida por reconciliación semanal para evitar acumulación de deuda.'
        sp = SesionProgramada.objects.create(
            cliente=cliente,
            fecha_prevista=date(2026, 8, 28),
            estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
            prioridad=SesionProgramada.PRIORIDAD_NORMAL,
            nombre_sesion='Día 5 - Fuerza — Avanzada',
            motivo_estado=motivo,
        )
        SesionProgramada.objects.filter(pk=sp.pk).update(
            actualizada_en=datetime(2026, 8, 23, 12, tzinfo=dt_timezone.utc),
        )

        out = StringIO()
        call_command(
            'reconciliar_sesiones_programadas_gym', cliente=cliente.pk,
            desde='2026-08-20', hasta='2026-08-30', stdout=out,
        )
        registro = json.loads(out.getvalue().splitlines()[0])
        self.assertEqual(registro['classification'], 'omitted_before_due')
        self.assertEqual(registro['estado_previo'], SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertEqual(registro['fecha_prevista'], '2026-08-28')
        self.assertIsNone(registro['pospuesta_hasta'])
        self.assertEqual(registro['motivo'], motivo)
        self.assertEqual(registro['motivo_estado'], motivo)

        call_command(
            'reconciliar_sesiones_programadas_gym', cliente=cliente.pk,
            desde='2026-08-20', hasta='2026-08-30', apply=True, stdout=StringIO(),
        )
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(sp.motivo_estado, '')
        self.assertIsNone(sp.entreno_realizado_id)
        self.assertIsNone(sp.fecha_realizada)

        out = StringIO()
        call_command(
            'reconciliar_sesiones_programadas_gym', cliente=cliente.pk,
            desde='2026-08-20', hasta='2026-08-30', stdout=out,
        )
        self.assertNotIn('omitted_before_due', out.getvalue())

    def test_no_restaura_omisiones_legitimas_ni_ambiguas(self):
        user = User.objects.create_user('reconciliar-omisiones-legitimas')
        cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre='Rutina ambigua')
        motivo = 'Sesión omitida por reconciliación semanal para evitar acumulación de deuda.'
        vencida = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 8, 20),
            estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
            nombre_sesion='Vencida', motivo_estado=motivo,
        )
        otro_motivo = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 8, 27),
            estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
            nombre_sesion='Otra causa', motivo_estado='Omisión manual auditada.',
        )
        ambigua = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 8, 28),
            estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
            nombre_sesion='Rutina ambigua', motivo_estado=motivo,
        )
        saltada = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 8, 25),
            estado=SesionProgramada.ESTADO_SALTADA_USUARIO,
            nombre_sesion='Saltada', motivo_estado=motivo,
        )
        cancelada = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 8, 26),
            estado=SesionProgramada.ESTADO_CANCELADA_LESION,
            nombre_sesion='Cancelada', motivo_estado=motivo,
        )
        SesionProgramada.objects.filter(
            pk__in=[otro_motivo.pk, ambigua.pk, saltada.pk, cancelada.pk],
        ).update(
            actualizada_en=datetime(2026, 8, 23, 12, tzinfo=dt_timezone.utc),
        )
        for _ in range(2):
            EntrenoRealizado.objects.create(
                cliente=cliente, rutina=rutina, fecha=date(2026, 8, 28),
                fecha_ejecucion=date(2026, 8, 28),
            )

        call_command(
            'reconciliar_sesiones_programadas_gym', cliente=cliente.pk,
            desde='2026-08-20', hasta='2026-08-30', apply=True, stdout=StringIO(),
        )
        vencida.refresh_from_db()
        otro_motivo.refresh_from_db()
        ambigua.refresh_from_db()
        saltada.refresh_from_db()
        cancelada.refresh_from_db()
        self.assertEqual(vencida.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertEqual(otro_motivo.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertEqual(ambigua.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertEqual(saltada.estado, SesionProgramada.ESTADO_SALTADA_USUARIO)
        self.assertEqual(cancelada.estado, SesionProgramada.ESTADO_CANCELADA_LESION)


class AgrupacionTraceSemanticaTests(TestCase):
    def test_mismo_estado_agrupa_aunque_cambie_explicacion(self):
        traces = [
            {'decision_estado': 'entrenar', 'decision_label': 'Entrenar', 'explicacion': 'A', 'lesion_label': '', 'fecha_label': 'hoy'},
            {'decision_estado': 'entrenar', 'decision_label': 'Entrenar', 'explicacion': 'B', 'lesion_label': '', 'fecha_label': 'ayer'},
        ]
        grupos = agrupar_traces_recientes(traces)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]['count'], 2)
        self.assertEqual([item['explicacion'] for item in grupos[0]['items']], ['A', 'B'])
