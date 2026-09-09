from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import AusenciaPlanificadaGym, SesionProgramada
from entrenos.services.ausencia_planificada_service import (
    ampliar_ausencia_planificada,
    cancelar_tramo_restante_ausencia,
    confirmar_ausencia_planificada,
    previsualizar_ampliacion_ausencia,
    previsualizar_ausencia_planificada,
)
from entrenos.services.distribucion_semanal_contractual_service import _clasificar_sesion
from entrenos.services.resumen_semanal_service import get_resumen_semanal_gym


class AusenciaPlanificadaServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ausente', password='x')
        self.otro_user = User.objects.create_user('otro-ausente', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.inicio = date(2026, 9, 10)
        self.fin = date(2026, 9, 14)

    def _sesion(self, fecha, **kwargs):
        return SesionProgramada.objects.create(
            cliente=kwargs.pop('cliente', self.cliente), fecha_prevista=fecha, **kwargs,
        )

    def test_preview_solo_incluye_pendientes_por_fecha_efectiva(self):
        dentro = self._sesion(self.inicio, nombre_sesion='Dentro')
        pospuesta_dentro = self._sesion(
            self.inicio - timedelta(days=3), pospuesta_hasta=self.fin,
            nombre_sesion='Pospuesta dentro',
        )
        fuera_por_posposicion = self._sesion(
            self.inicio - timedelta(days=2), pospuesta_hasta=self.fin + timedelta(days=1),
            nombre_sesion='Fuera efectiva',
        )
        completada = self._sesion(self.inicio + timedelta(days=1), estado='completada')
        lesion = self._sesion(self.inicio + timedelta(days=2), estado='cancelada_lesion')
        ajena = self._sesion(self.inicio, cliente=self.otro)

        preview = previsualizar_ausencia_planificada(self.cliente, self.inicio, self.fin)

        self.assertEqual([item['id'] for item in preview], [dentro.id, pospuesta_dentro.id])
        self.assertEqual(preview[1]['fecha_efectiva'], self.fin)
        self.assertNotIn(fuera_por_posposicion.id, [item['id'] for item in preview])
        self.assertNotIn(completada.id, [item['id'] for item in preview])
        self.assertNotIn(lesion.id, [item['id'] for item in preview])
        self.assertNotIn(ajena.id, [item['id'] for item in preview])

    def test_confirmacion_auditable_preserva_fechas_y_deja_deuda_cero(self):
        sesion = self._sesion(
            self.inicio - timedelta(days=1), pospuesta_hasta=self.inicio,
            nombre_sesion='Fuerza A',
        )
        ausencia = confirmar_ausencia_planificada(
            cliente=self.cliente, inicio=self.inicio, fin=self.fin,
            motivo='viaje', nota='Trabajo fuera',
        )

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, SesionProgramada.ESTADO_OMITIDA_USUARIO)
        self.assertEqual(sesion.fecha_prevista, self.inicio - timedelta(days=1))
        self.assertEqual(sesion.pospuesta_hasta, self.inicio)
        self.assertEqual(sesion.ausencia_planificada, ausencia)
        self.assertEqual(sesion.motivo_estado, 'Ausencia planificada: Viaje.')
        self.assertEqual(ausencia.sesiones_afectadas, 1)
        self.assertEqual(ausencia.sesiones_snapshot[0]['id'], sesion.id)
        self.assertEqual(ausencia.deuda_generada, 0)

    def test_confirmacion_es_atomica_si_falla_la_actualizacion(self):
        self._sesion(self.inicio)
        with patch('entrenos.services.ausencia_planificada_service._omitir_sesiones', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                confirmar_ausencia_planificada(
                    cliente=self.cliente, inicio=self.inicio, fin=self.fin,
                    motivo='vacaciones', nota='',
                )
        self.assertFalse(AusenciaPlanificadaGym.objects.exists())

    def test_ampliacion_solo_admite_extender_fin_y_anexa_sesiones_sin_duplicar(self):
        ya_vinculada = self._sesion(self.fin, nombre_sesion='Ya omitida')
        ausencia = confirmar_ausencia_planificada(
            cliente=self.cliente, inicio=self.inicio, fin=self.fin,
            motivo='viaje', nota='',
        )
        nueva = self._sesion(self.fin + timedelta(days=2), nombre_sesion='Nueva')

        preview = previsualizar_ampliacion_ausencia(
            ausencia, self.fin + timedelta(days=3), cliente=self.cliente,
        )
        self.assertEqual([item['id'] for item in preview], [nueva.id])
        ampliada = ampliar_ausencia_planificada(
            ausencia=ausencia, nuevo_fin=self.fin + timedelta(days=3), cliente=self.cliente,
        )

        ampliada.refresh_from_db()
        nueva.refresh_from_db()
        self.assertEqual(ampliada.inicio, self.inicio)
        self.assertEqual(ampliada.fin, self.fin + timedelta(days=3))
        self.assertEqual(ampliada.sesiones_afectadas, 2)
        self.assertEqual({item['id'] for item in ampliada.sesiones_snapshot}, {ya_vinculada.id, nueva.id})
        self.assertEqual(nueva.ausencia_planificada, ampliada)
        with self.assertRaisesMessage(ValueError, 'posterior'):
            ampliar_ausencia_planificada(
                ausencia=ampliada, nuevo_fin=self.fin, cliente=self.cliente,
            )

    @patch('entrenos.services.ausencia_planificada_service.timezone.localdate', return_value=date(2026, 9, 12))
    def test_cancelar_solo_reabre_tramo_futuro_intacto_y_deja_auditoria(self, _localdate):
        ausencia = AusenciaPlanificadaGym.objects.create(
            cliente=self.cliente, inicio=self.inicio, fin=self.fin,
            motivo='vacaciones', sesiones_afectadas=4,
        )
        pasada = self._sesion(date(2026, 9, 11), estado='omitida_usuario', ausencia_planificada=ausencia,
                              motivo_estado='Ausencia planificada: Vacaciones.')
        futura = self._sesion(date(2026, 9, 12), estado='omitida_usuario', ausencia_planificada=ausencia,
                              motivo_estado='Ausencia planificada: Vacaciones.')
        completada = self._sesion(date(2026, 9, 13), estado='completada', ausencia_planificada=ausencia)
        modificada = self._sesion(date(2026, 9, 14), pospuesta_hasta=date(2026, 9, 15),
                                  estado='omitida_usuario', ausencia_planificada=ausencia,
                                  motivo_estado='Ausencia planificada: Vacaciones.')
        ausencia.sesiones_snapshot = [
            {'id': pasada.id, 'fecha_prevista': '2026-09-11', 'pospuesta_hasta': None},
            {'id': futura.id, 'fecha_prevista': '2026-09-12', 'pospuesta_hasta': None},
            {'id': completada.id, 'fecha_prevista': '2026-09-13', 'pospuesta_hasta': None},
            # Se pospuso después de confirmar la ausencia: ya fue modificada.
            {'id': modificada.id, 'fecha_prevista': '2026-09-14', 'pospuesta_hasta': None},
        ]
        ausencia.save(update_fields=['sesiones_snapshot'])

        restauradas = cancelar_tramo_restante_ausencia(ausencia=ausencia, cliente=self.cliente)

        self.assertEqual(restauradas, 1)
        for sesion in (pasada, futura, completada, modificada):
            sesion.refresh_from_db()
        ausencia.refresh_from_db()
        self.assertEqual(futura.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(futura.ausencia_planificada_id)
        self.assertEqual(pasada.estado, SesionProgramada.ESTADO_OMITIDA_USUARIO)
        self.assertEqual(completada.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(modificada.estado, SesionProgramada.ESTADO_OMITIDA_USUARIO)
        self.assertIsNotNone(ausencia.cancelada_en)
        self.assertEqual(ausencia.fecha_cancelacion_efectiva, date(2026, 9, 12))

    def test_operaciones_rechazan_cliente_ajeno(self):
        ausencia = AusenciaPlanificadaGym.objects.create(
            cliente=self.cliente, inicio=self.inicio, fin=self.fin, motivo='otro',
        )
        with self.assertRaises(PermissionError):
            previsualizar_ampliacion_ausencia(ausencia, self.fin + timedelta(days=1), cliente=self.otro)
        with self.assertRaises(PermissionError):
            cancelar_tramo_restante_ausencia(ausencia=ausencia, cliente=self.otro)


class AusenciaPlanificadaViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('vista-ausencia', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    @patch('clientes.views.timezone.localdate', return_value=date(2026, 9, 9))
    def test_formulario_default_preview_explicito_y_confirmacion(self, _localdate):
        sesion = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 9, 10), nombre_sesion='Pierna',
        )
        url = reverse('clientes:ausencia_planificada_gym')
        respuesta = self.client.get(url)
        self.assertContains(respuesta, 'No estaré disponible unos días')
        self.assertContains(respuesta, 'value="2026-09-09"')

        datos = {'inicio': '2026-09-09', 'fin': '2026-09-11', 'motivo': 'vacaciones', 'nota': ''}
        preview = self.client.post(url, {**datos, 'accion': 'previsualizar'})
        sesion.refresh_from_db()
        self.assertContains(preview, 'Sesiones pendientes afectadas')
        self.assertContains(preview, 'Pierna')
        self.assertEqual(sesion.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertContains(preview, 'Confirmar ausencia')

        confirmacion = self.client.post(url, {**datos, 'accion': 'confirmar'})
        self.assertRedirects(confirmacion, reverse('clientes:mockup_demo'))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, SesionProgramada.ESTADO_OMITIDA_USUARIO)

    def test_fin_anterior_a_inicio_es_invalido(self):
        respuesta = self.client.post(reverse('clientes:ausencia_planificada_gym'), {
            'inicio': '2026-09-12', 'fin': '2026-09-11',
            'motivo': 'otro', 'nota': '', 'accion': 'previsualizar',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'igual o posterior')
        self.assertFalse(AusenciaPlanificadaGym.objects.exists())

    @patch('clientes.views.timezone.localdate', return_value=date(2026, 9, 10))
    def test_portada_durante_ausencia_no_ofrece_entreno_y_muestra_regreso(self, _localdate):
        AusenciaPlanificadaGym.objects.create(
            cliente=self.cliente, inicio=date(2026, 9, 9), fin=date(2026, 9, 12),
            motivo='viaje', nota='', sesiones_afectadas=0, sesiones_snapshot=[],
        )
        respuesta = self.client.get(reverse('clientes:mockup_demo'))
        self.assertContains(respuesta, 'Ausencia planificada')
        self.assertContains(respuesta, 'Regresas el 13/09/2026')
        self.assertContains(respuesta, 'Gestionar ausencia')
        self.assertContains(respuesta, '09/09/2026–12/09/2026')
        self.assertNotContains(respuesta, 'Abrir sesión Gym')

    @patch('clientes.views.timezone.localdate', return_value=date(2026, 9, 10))
    def test_pantalla_gestiona_ampliacion_con_preview_y_cancelacion_explicita(self, _localdate):
        ausencia = AusenciaPlanificadaGym.objects.create(
            cliente=self.cliente, inicio=date(2026, 9, 9), fin=date(2026, 9, 12),
            motivo='viaje', sesiones_afectadas=0,
        )
        nueva = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=date(2026, 9, 14), nombre_sesion='Fuerza B',
        )
        url = reverse('clientes:ausencia_planificada_gym')
        pantalla = self.client.get(url)
        self.assertContains(pantalla, 'Ausencia activa')
        self.assertContains(pantalla, 'Ampliar hasta')
        preview = self.client.post(url, {'accion': 'previsualizar_ampliacion', 'nuevo_fin': '2026-09-15'})
        self.assertContains(preview, 'Fuerza B')
        nueva.refresh_from_db()
        self.assertEqual(nueva.estado, SesionProgramada.ESTADO_PENDIENTE)
        confirmar = self.client.post(url, {'accion': 'confirmar_ampliacion', 'nuevo_fin': '2026-09-15'})
        self.assertRedirects(confirmar, url)
        ausencia.refresh_from_db()
        self.assertEqual(ausencia.fin, date(2026, 9, 15))
        cancelar = self.client.post(url, {'accion': 'cancelar_tramo', 'confirmar_cancelacion': 'si'})
        self.assertRedirects(cancelar, reverse('clientes:mockup_demo'))
        ausencia.refresh_from_db()
        self.assertIsNotNone(ausencia.cancelada_en)

    @patch('clientes.views.timezone.localdate', return_value=date(2026, 9, 10))
    def test_cancelacion_sin_confirmacion_no_cambia_nada(self, _localdate):
        ausencia = AusenciaPlanificadaGym.objects.create(
            cliente=self.cliente, inicio=date(2026, 9, 9), fin=date(2026, 9, 12), motivo='otro',
        )
        respuesta = self.client.post(reverse('clientes:ausencia_planificada_gym'), {'accion': 'cancelar_tramo'})
        self.assertEqual(respuesta.status_code, 200)
        ausencia.refresh_from_db()
        self.assertIsNone(ausencia.cancelada_en)
        self.assertContains(respuesta, 'Confirma explícitamente')


class BalanceAusenciaTests(TestCase):
    def test_distribucion_clasifica_ausencia_como_omision_del_usuario(self):
        user = User.objects.create_user('distribucion-ausencia', password='x')
        cliente = Cliente.objects.get(user=user)
        ausencia = AusenciaPlanificadaGym.objects.create(
            cliente=cliente, inicio=date(2026, 9, 7), fin=date(2026, 9, 13),
            motivo='vacaciones', nota='', sesiones_afectadas=1, sesiones_snapshot=[],
        )
        sesion = SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 9, 9),
            estado=SesionProgramada.ESTADO_OMITIDA_USUARIO,
            ausencia_planificada=ausencia,
        )

        resultado = _clasificar_sesion(sesion)

        self.assertEqual(resultado['resultado'], 'omitida')
        self.assertEqual(resultado['causa'], 'ausencia_planificada')

    def test_balance_distingue_omitidas_por_ausencia_y_motivo_sin_entrenos(self):
        user = User.objects.create_user('balance-ausencia', password='x')
        cliente = Cliente.objects.get(user=user)
        ausencia = AusenciaPlanificadaGym.objects.create(
            cliente=cliente, inicio=date(2026, 9, 7), fin=date(2026, 9, 13),
            motivo='enfermedad', nota='', sesiones_afectadas=1, sesiones_snapshot=[],
        )
        SesionProgramada.objects.create(
            cliente=cliente, fecha_prevista=date(2026, 9, 8),
            estado=SesionProgramada.ESTADO_OMITIDA_USUARIO,
            ausencia_planificada=ausencia,
        )
        items = get_resumen_semanal_gym(cliente, date(2026, 9, 7), date(2026, 9, 13))
        ausencia_item = next(item for item in items if item['tipo'] == 'ausencia_planificada')
        self.assertIn('1 sesión omitida por ausencia planificada', ausencia_item['texto'])
        self.assertIn('Enfermedad', ausencia_item['texto'])
