from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.models import BitacoraDiaria, Cliente
from entrenos.services.sesion_recomendada import (
    _aplicar_contexto,
    _obtener_contexto_fisico,
)
from hyrox.models import HyroxObjective, HyroxReadinessLog


class EvidenciaFisicaGymTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        user = User.objects.create_user(username='evidencia-gym')
        self.cliente = Cliente.objects.get(user=user)
        Cliente.objects.filter(pk=self.cliente.pk).update(
            nombre='David', email='david@example.com', telefono='000'
        )
        self.cliente.refresh_from_db()

    def _decision_base(self):
        return {
            'tipo': 'programada_hoy',
            'estado': 'entrenar',
            'sesion_programada': None,
            'entrenamiento': {
                'rutina_nombre': 'Torso',
                'ejercicios': [{'nombre': 'Press banca', 'grupo_muscular': 'pecho'}],
            },
            'mensaje': 'base',
            'causa_principal': None,
            'modo_reducido': False,
        }

    def _objetivo(self, *, dias=30, estado='activo'):
        return HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + timedelta(days=dias),
            estado=estado,
        )

    def _readiness(self, objetivo, score):
        log = HyroxReadinessLog.objects.create(objective=objetivo, score=score)
        HyroxReadinessLog.objects.filter(pk=log.pk).update(fecha=self.hoy)
        return log

    def test_expone_evidencia_observacional_exacta_del_dia(self):
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            energia_subjetiva=6,
            horas_sueno=7.25,
            fc_reposo=54,
            hrv_ms=61,
            calidad_sueno=82,
            dolor_articular=2,
        )

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)

        self.assertEqual(contexto['evidencia_fecha'], self.hoy)
        self.assertTrue(contexto['evidencia_presente'])
        self.assertEqual(contexto['energia_valor'], 6)
        self.assertEqual(contexto['horas_sueno'], 7.25)
        self.assertEqual(contexto['frecuencia_cardiaca_reposo'], 54)
        self.assertEqual(contexto['hrv_ms'], 61)
        self.assertEqual(contexto['calidad_sueno'], 82)
        self.assertEqual(contexto['dolor'], 2)

    def test_no_reutiliza_la_bitacora_de_ayer(self):
        registro = BitacoraDiaria.objects.create(
            cliente=self.cliente,
            energia_subjetiva=2,
            horas_sueno=4,
            fc_reposo=75,
            hrv_ms=20,
            calidad_sueno=25,
            dolor_articular=7,
        )
        BitacoraDiaria.objects.filter(pk=registro.pk).update(
            fecha=self.hoy - timedelta(days=1)
        )

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)

        self.assertFalse(contexto['evidencia_presente'])
        self.assertIsNone(contexto['evidencia_fecha'])
        for campo in (
            'energia_valor', 'horas_sueno', 'frecuencia_cardiaca_reposo',
            'hrv_ms', 'calidad_sueno', 'dolor',
        ):
            self.assertIsNone(contexto[campo])
        self.assertFalse(contexto['energia_baja'])

    def test_biometria_aislada_es_observacional_y_no_cambia_la_sesion(self):
        BitacoraDiaria.objects.create(
            cliente=self.cliente,
            energia_subjetiva=None,
            horas_sueno=3,
            fc_reposo=92,
            hrv_ms=12,
            calidad_sueno=10,
            dolor_articular=8,
        )

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)
        decision = _aplicar_contexto(self._decision_base(), contexto, self.hoy)

        self.assertEqual(decision['estado'], 'entrenar')
        self.assertEqual(decision['causa_principal'], 'sesion_hoy')

    def test_sin_biometria_no_penaliza(self):
        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)
        decision = _aplicar_contexto(self._decision_base(), contexto, self.hoy)

        self.assertFalse(contexto['evidencia_presente'])
        self.assertFalse(contexto['readiness_bajo'])
        self.assertEqual(decision['estado'], 'entrenar')

    def test_objetivo_hyrox_activo_vencido_no_gobierna_gym(self):
        objetivo = self._objetivo(dias=-1)
        self._readiness(objetivo, 20)

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)

        self.assertFalse(contexto['readiness_bajo'])
        self.assertIsNone(contexto['readiness_valor'])

    def test_campana_vigente_con_readiness_bajo_activa_recuperacion(self):
        objetivo = self._objetivo(dias=30)
        self._readiness(objetivo, 44)

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)
        decision = _aplicar_contexto(self._decision_base(), contexto, self.hoy)

        self.assertTrue(contexto['readiness_bajo'])
        self.assertEqual(contexto['readiness_valor'], 44)
        self.assertEqual(decision['estado'], 'recuperar')
        self.assertEqual(decision['causa_principal'], 'fatiga_alta')

    def test_selecciona_la_campana_vigente_mas_proxima(self):
        cercana = self._objetivo(dias=10)
        lejana = self._objetivo(dias=90)
        self._readiness(cercana, 80)
        self._readiness(lejana, 20)

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)

        self.assertEqual(contexto['readiness_valor'], 80)
        self.assertFalse(contexto['readiness_bajo'])

    def test_desempata_campanas_por_pk(self):
        primera = self._objetivo(dias=20)
        segunda = self._objetivo(dias=20)
        self._readiness(primera, 80)
        self._readiness(segunda, 20)

        contexto = _obtener_contexto_fisico(self.cliente, self.hoy)

        self.assertEqual(contexto['readiness_valor'], 80)
        self.assertFalse(contexto['readiness_bajo'])
