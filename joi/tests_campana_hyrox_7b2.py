import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym
from hyrox.models import ContratoCampanaHyrox, HyroxObjective
from joi.models import MensajeJOI


class JoiCampanaHyrox7B2Tests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.user = User.objects.create_user('joi_campana_7b2', password='test')
        self.cliente = self.user.cliente_perfil
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=30),
        )
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=5,
            minimo_valido=3,
            vigente_desde=self.hoy,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente,
            version=1,
            estado='activo',
            semana_inicio=self.hoy,
            semanas_previstas=4,
            semana_fin_prevista=self.hoy + datetime.timedelta(days=27),
            estrategia=estrategia,
            objetivo_sesiones=5,
            minimo_valido=3,
            objetivo_principal='hipertrofia',
            objetivos_secundarios=[],
            limites_snapshot={},
            motor_nombre='Helms',
            motor_version='actual',
            fingerprint='b' * 64,
        )

    def _contrato(self, estado):
        return ContratoCampanaHyrox.objects.create(
            cliente=self.cliente,
            version=1,
            estado=estado,
            objetivo=self.objetivo if estado == 'activa' else None,
            bloque_gym=self.bloque if estado == 'activa' else None,
            objetivo_snapshot={
                'id': self.objetivo.pk,
                'fecha_evento': str(self.objetivo.fecha_evento),
            } if estado == 'activa' else {},
            fingerprint='c' * 64,
            aprobado_por=self.user,
        )

    def test_trigger_hyrox_inactivo_no_llama_ia_ni_crea_mensaje(self):
        from joi.services import generar_mensaje_joi

        self._contrato('inactiva')
        with patch('joi.services._llamar_haiku') as ia:
            mensaje = generar_mensaje_joi(
                self.cliente, 'hyrox_sesion_completada', {'rpe': 8}
            )
        self.assertIsNone(mensaje)
        ia.assert_not_called()
        self.assertFalse(MensajeJOI.objects.filter(user=self.user).exists())

    def test_trigger_hyrox_activo_conserva_generacion(self):
        from joi.services import generar_mensaje_joi

        self._contrato('activa')
        with (
            patch('joi.services.construir_contexto', return_value={}),
            patch('joi.services._llamar_haiku', return_value='Mensaje Hyrox autorizado') as ia,
        ):
            mensaje = generar_mensaje_joi(
                self.cliente, 'hyrox_sesion_completada', {'rpe': 8}
            )
        self.assertIsNotNone(mensaje)
        self.assertEqual(mensaje.trigger, 'hyrox_sesion_completada')
        ia.assert_called_once()

    def test_trigger_general_sigue_activo_sin_campana_hyrox(self):
        from joi.services import generar_mensaje_joi

        self._contrato('inactiva')
        with (
            patch('joi.services.construir_contexto', return_value={}),
            patch('joi.services._llamar_haiku', return_value='Apertura general') as ia,
        ):
            mensaje = generar_mensaje_joi(self.cliente, 'apertura_manana', {})
        self.assertIsNotNone(mensaje)
        ia.assert_called_once()

    def test_builder_hyrox_vacio_inactivo_y_disponible_activo(self):
        from joi.context_builders.hyrox_context import build_hyrox_context

        self._contrato('inactiva')
        self.assertEqual(build_hyrox_context(self.cliente, self.hoy, self.hoy), {})

    def test_builder_y_context_processor_conservan_hyrox_activo(self):
        from joi.context_builders.hyrox_context import build_hyrox_context
        from joi.context_processors import _get_mensaje_hyrox

        self._contrato('activa')
        contexto = build_hyrox_context(self.cliente, self.hoy, self.hoy)
        mensaje = MensajeJOI.objects.create(
            user=self.user,
            trigger='hyrox_readiness_bajo',
            mensaje='Mensaje vigente',
        )
        self.assertEqual(contexto['dias_hasta_carrera'], 30)
        self.assertEqual(_get_mensaje_hyrox(self.user), mensaje)

    def test_context_processor_oculta_legacy_sin_borrarlo(self):
        from joi.context_processors import _get_mensaje_hyrox

        self._contrato('inactiva')
        legacy = MensajeJOI.objects.create(
            user=self.user,
            trigger='hyrox_readiness_bajo',
            mensaje='Mensaje histórico',
        )
        self.assertIsNone(_get_mensaje_hyrox(self.user))
        self.assertTrue(MensajeJOI.objects.filter(pk=legacy.pk).exists())

    def test_tareas_hyrox_inactivas_no_intentan_generar(self):
        from joi.tasks import verificar_ausencia_hyrox, verificar_cuenta_regresiva_hyrox

        self._contrato('inactiva')
        HyroxObjective.objects.filter(pk=self.objetivo.pk).update(
            fecha_creacion=timezone.now() - datetime.timedelta(days=10)
        )
        with patch('joi.services.generar_mensaje_joi') as generar:
            cuenta = verificar_cuenta_regresiva_hyrox.run()
            ausencia = verificar_ausencia_hyrox.run()
        self.assertEqual(cuenta['generados'], 0)
        self.assertEqual(ausencia['generados'], 0)
        generar.assert_not_called()

    def test_tarea_countdown_activa_conserva_generacion(self):
        from joi.tasks import verificar_cuenta_regresiva_hyrox

        self._contrato('activa')
        with patch('joi.services.generar_mensaje_joi') as generar:
            resultado = verificar_cuenta_regresiva_hyrox.run()
        self.assertEqual(resultado['generados'], 1)
        generar.assert_called_once_with(
            self.cliente, 'hyrox_cuenta_regresiva', {'dias': 30}
        )
