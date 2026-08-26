import datetime

from django.contrib.auth.models import User
from django.test import TestCase

from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym
from hyrox.campaign_authority import (
    CampanaHyroxNoAutoriza,
    PERMISOS,
    exigir_registro_manual,
    resolver_autoridad_campana,
)
from hyrox.models import ContratoCampanaHyrox, HyroxObjective


class GateRegistroManualCampanaTests(TestCase):
    def setUp(self):
        self.hoy = datetime.date(2026, 8, 26)
        self.user = User.objects.create_user('registro-manual')
        self.cliente = self.user.cliente_perfil
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=60),
        )
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=4,
            minimo_valido=2,
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
            objetivo_sesiones=4,
            minimo_valido=2,
            objetivo_principal='resistencia',
            objetivos_secundarios=[],
            limites_snapshot={},
            motor_nombre='Helms',
            motor_version='actual',
            fingerprint='m' * 64,
        )

    def _contrato(self, estado):
        return ContratoCampanaHyrox.objects.create(
            cliente=self.cliente,
            version=1,
            estado=estado,
            objetivo=self.objetivo if estado == 'activa' else None,
            bloque_gym=self.bloque if estado == 'activa' else None,
            objetivo_snapshot=(
                {
                    'id': self.objetivo.pk,
                    'fecha_evento': str(self.objetivo.fecha_evento),
                }
                if estado == 'activa' else {}
            ),
            bloque_gym_snapshot=(
                {'id': self.bloque.pk, 'estado': self.bloque.estado}
                if estado == 'activa' else {}
            ),
            limites_snapshot={},
            fingerprint=estado[0] * 64,
        )

    def test_autoriza_registro_manual_en_los_cuatro_estados(self):
        for estado in ('inactiva', 'exploracion', 'activa', 'finalizada'):
            with self.subTest(estado=estado):
                ContratoCampanaHyrox.objects.all().delete()
                self._contrato(estado)

                autoridad = exigir_registro_manual(
                    self.cliente,
                    fecha=self.hoy,
                )

                self.assertEqual(autoridad['estado'], estado)
                self.assertTrue(autoridad['permisos']['registro_manual'])

    def test_acepta_objetivo_persistido_del_cliente_sin_elevar_permisos(self):
        self._contrato('exploracion')
        permisos_antes = {estado: dict(permisos) for estado, permisos in PERMISOS.items()}

        autoridad = exigir_registro_manual(
            self.cliente,
            fecha=self.hoy,
            objective=self.objetivo,
        )

        self.assertEqual(autoridad, resolver_autoridad_campana(self.cliente, self.hoy))
        self.assertFalse(autoridad['permisos']['generar_plan'])
        self.assertFalse(autoridad['permisos']['programar_sesiones'])
        self.assertEqual(PERMISOS, permisos_antes)

    def test_rechaza_objetivo_ajeno(self):
        otro_user = User.objects.create_user('registro-manual-ajeno')
        objetivo_ajeno = HyroxObjective.objects.create(
            cliente=otro_user.cliente_perfil,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )

        with self.assertRaises(CampanaHyroxNoAutoriza) as error:
            exigir_registro_manual(
                self.cliente,
                fecha=self.hoy,
                objective=objetivo_ajeno,
            )

        self.assertEqual(error.exception.accion, 'registro_manual')
        self.assertIn('objetivo_invalido', error.exception.autoridad['hallazgos'])

    def test_rechaza_objetivo_no_persistido(self):
        objetivo_sin_guardar = HyroxObjective(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )

        with self.assertRaises(CampanaHyroxNoAutoriza):
            exigir_registro_manual(
                self.cliente,
                fecha=self.hoy,
                objective=objetivo_sin_guardar,
            )

    def test_rechaza_un_valor_que_no_es_objetivo(self):
        with self.assertRaises(CampanaHyroxNoAutoriza):
            exigir_registro_manual(
                self.cliente,
                fecha=self.hoy,
                objective=self.cliente,
            )

    def test_rechaza_instancia_de_objetivo_eliminada(self):
        objetivo_eliminado = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=self.hoy + datetime.timedelta(days=90),
        )
        objetivo_eliminado.delete()

        with self.assertRaises(CampanaHyroxNoAutoriza):
            exigir_registro_manual(
                self.cliente,
                fecha=self.hoy,
                objective=objetivo_eliminado,
            )

    def test_gate_es_solo_lectura_y_devuelve_snapshot_factual_independiente(self):
        contrato = self._contrato('inactiva')
        conteos_antes = (
            ContratoCampanaHyrox.objects.count(),
            HyroxObjective.objects.count(),
        )

        autoridad = exigir_registro_manual(
            self.cliente,
            fecha=self.hoy,
            objective=self.objetivo,
        )
        autoridad['permisos']['generar_plan'] = True
        autoridad['hallazgos'].append('mutacion_local')

        contrato.refresh_from_db()
        self.objetivo.refresh_from_db()
        self.assertEqual(
            conteos_antes,
            (ContratoCampanaHyrox.objects.count(), HyroxObjective.objects.count()),
        )
        self.assertEqual(contrato.estado, 'inactiva')
        self.assertEqual(self.objetivo.cliente_id, self.cliente.pk)
        autoridad_fresca = resolver_autoridad_campana(self.cliente, self.hoy)
        self.assertFalse(autoridad_fresca['permisos']['generar_plan'])
        self.assertNotIn('mutacion_local', autoridad_fresca['hallazgos'])
