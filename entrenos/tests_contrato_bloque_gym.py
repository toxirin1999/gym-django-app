from datetime import date, timedelta
from io import StringIO
import json

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ContratoBloqueGym, ContratoSemanalGym
from entrenos.services.estrategia_semanal_gym_service import (
    abrir_contrato_semanal_gym,
    aprobar_estrategia_semanal_gym,
)


class ContratoBloqueGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bloque_gym', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Bloque Gym'},
        )
        self.inicio = date(2026, 8, 24)
        self.estrategia = aprobar_estrategia_semanal_gym(
            self.cliente, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=self.inicio, aprobado_por=self.user,
        )

    def _proponer(self, **extra):
        from entrenos.services.contrato_bloque_gym_service import proponer_bloque_gym
        datos = {
            'semana_inicio': self.inicio,
            'semanas_previstas': 4,
            'objetivo_principal': 'hipertrofia',
            'objetivos_secundarios': ['gemelos'],
            'limites_snapshot': {'sin_autoajustes': True},
            'motor_nombre': 'Helms',
            'motor_version': 'actual',
            'motivo': 'Bloque confirmado',
        }
        datos.update(extra)
        return proponer_bloque_gym(self.cliente, **datos)

    def test_propuesta_snapshot_versionada_y_fingerprint_idempotente(self):
        primero = self._proponer()
        segundo = self._proponer()

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(primero.version, 1)
        self.assertEqual(primero.estado, ContratoBloqueGym.ESTADO_PROPUESTO)
        self.assertEqual(primero.objetivo_sesiones, 5)
        self.assertEqual(primero.minimo_valido, 3)
        self.assertEqual(primero.semana_fin_prevista, date(2026, 9, 20))
        self.assertTrue(primero.fingerprint)

    def test_activar_exige_version_optimista_y_no_solapa(self):
        from entrenos.services.contrato_bloque_gym_service import (
            ConflictoVersionBloque,
            SolapeBloqueGym,
            activar_bloque_gym,
        )
        propuesta = self._proponer()
        with self.assertRaises(ConflictoVersionBloque):
            activar_bloque_gym(propuesta, version_esperada=2, actor=self.user)
        activo = activar_bloque_gym(propuesta, version_esperada=1, actor=self.user)
        self.assertEqual(activo.estado, ContratoBloqueGym.ESTADO_ACTIVO)
        self.assertIsNotNone(activo.aprobado_en)

        otro = self._proponer(
            semana_inicio=self.inicio + timedelta(weeks=1), motivo='Solapado',
        )
        with self.assertRaises(SolapeBloqueGym):
            activar_bloque_gym(otro, version_esperada=2, actor=self.user)

    def test_activar_exige_propietario(self):
        from entrenos.services.contrato_bloque_gym_service import (
            ActorBloqueNoAutorizado, activar_bloque_gym,
        )
        ajeno = User.objects.create_user(username='actor_bloque_ajeno')
        with self.assertRaises(ActorBloqueNoAutorizado):
            activar_bloque_gym(self._proponer(), version_esperada=1, actor=ajeno)
        self.assertEqual(ContratoBloqueGym.objects.get().estado, 'propuesto')

    def test_semana_se_vincula_con_indice_y_pausa_impide_nuevos_vinculos(self):
        from entrenos.services.contrato_bloque_gym_service import (
            activar_bloque_gym, pausar_bloque_gym,
        )
        activo = activar_bloque_gym(self._proponer(), version_esperada=1, actor=self.user)
        semana_1 = abrir_contrato_semanal_gym(self.cliente, self.inicio)
        semana_2 = abrir_contrato_semanal_gym(self.cliente, self.inicio + timedelta(weeks=1))
        self.assertEqual(semana_1.bloque, activo)
        self.assertEqual(semana_1.indice_semana_bloque, 1)
        self.assertEqual(semana_2.indice_semana_bloque, 2)

        pausar_bloque_gym(activo, version_esperada=1)
        semana_3 = abrir_contrato_semanal_gym(self.cliente, self.inicio + timedelta(weeks=2))
        self.assertIsNone(semana_3.bloque_id)
        self.assertIsNone(semana_3.indice_semana_bloque)

    def test_snapshot_aprobado_es_inmutable_y_correccion_exige_sucesor(self):
        from entrenos.services.contrato_bloque_gym_service import activar_bloque_gym
        activo = activar_bloque_gym(self._proponer(), version_esperada=1, actor=self.user)
        activo.objetivo_sesiones = 4
        with self.assertRaises(ValidationError):
            activo.save()

        sucesor = self._proponer(
            semana_inicio=activo.semana_fin_prevista + timedelta(days=1),
            predecesor=activo,
            motivo='Corrección prospectiva',
        )
        self.assertEqual(sucesor.predecesor, activo)
        self.assertEqual(sucesor.version, 2)
        activo.refresh_from_db()
        self.assertEqual(activo.objetivo_sesiones, 5)

    def test_divergencia_de_estrategia_aborta_vinculo(self):
        from entrenos.services.contrato_bloque_gym_service import activar_bloque_gym
        from entrenos.services.estrategia_semanal_gym_service import DivergenciaBloqueSemanal
        activar_bloque_gym(self._proponer(), version_esperada=1, actor=self.user)
        aprobar_estrategia_semanal_gym(
            self.cliente, objetivo_sesiones=4, minimo_valido=3,
            vigente_desde=self.inicio + timedelta(weeks=1), aprobado_por=self.user,
        )
        with self.assertRaises(DivergenciaBloqueSemanal):
            abrir_contrato_semanal_gym(self.cliente, self.inicio + timedelta(weeks=1))
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)

    def test_auditoria_deriva_es_solo_lectura_y_no_genera_deuda(self):
        from entrenos.models import SesionProgramada
        from entrenos.services.contrato_bloque_gym_service import (
            activar_bloque_gym, auditar_deriva_bloque_gym,
        )
        activo = activar_bloque_gym(self._proponer(), version_esperada=1, actor=self.user)
        semana = abrir_contrato_semanal_gym(self.cliente, self.inicio)
        for i in range(5):
            SesionProgramada.objects.create(
                cliente=self.cliente, contrato_semanal=semana,
                semana_prescrita=self.inicio,
                fecha_prevista=self.inicio + timedelta(days=i),
                estado=(SesionProgramada.ESTADO_COMPLETADA if i < 3 else SesionProgramada.ESTADO_PENDIENTE),
            )
        antes = (ContratoBloqueGym.objects.count(), ContratoSemanalGym.objects.count())
        audit = auditar_deriva_bloque_gym(activo)
        despues = (ContratoBloqueGym.objects.count(), ContratoSemanalGym.objects.count())
        self.assertEqual(antes, despues)
        self.assertTrue(audit['solo_lectura'])
        self.assertEqual(audit['semanas'][0]['cumplimiento'], 'minima_valida')
        self.assertEqual(audit['semanas'][0]['deuda_generada'], 0)
        self.assertEqual(audit['resumen']['semanas_sin_materializar'], 3)

    def test_comandos_configurar_activar_y_auditar_son_dry_run_por_defecto(self):
        salida = StringIO()
        call_command(
            'configurar_bloque_gym', cliente=self.cliente.pk,
            semana_inicio=self.inicio.isoformat(), semanas=4,
            objetivo_principal='hipertrofia', stdout=salida,
        )
        self.assertTrue(json.loads(salida.getvalue())['solo_lectura'])
        self.assertEqual(ContratoBloqueGym.objects.count(), 0)

        salida = StringIO()
        call_command(
            'configurar_bloque_gym', cliente=self.cliente.pk,
            semana_inicio=self.inicio.isoformat(), semanas=4,
            objetivo_principal='hipertrofia', apply=True, stdout=salida,
        )
        propuesta = ContratoBloqueGym.objects.get()
        salida = StringIO()
        call_command('activar_bloque_gym', bloque=propuesta.pk, version_esperada=1, stdout=salida)
        self.assertEqual(propuesta.estado, ContratoBloqueGym.ESTADO_PROPUESTO)
        salida = StringIO()
        call_command('activar_bloque_gym', bloque=propuesta.pk, version_esperada=1, apply=True, stdout=salida)
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, ContratoBloqueGym.ESTADO_ACTIVO)

        salida = StringIO()
        call_command('auditar_bloque_gym', bloque=propuesta.pk, stdout=salida)
        lineas = [json.loads(linea) for linea in salida.getvalue().splitlines()]
        self.assertTrue(lineas[-1]['solo_lectura'])

    def test_dry_run_configuracion_exige_estrategia_real_vigente(self):
        self.estrategia.delete()
        with self.assertRaisesMessage(
            CommandError,
            'No existe estrategia semanal aprobada al inicio del bloque.',
        ):
            call_command(
                'configurar_bloque_gym', cliente=self.cliente.pk,
                semana_inicio=self.inicio.isoformat(), semanas=4,
                objetivo_principal='hipertrofia', stdout=StringIO(),
            )

    def test_dry_run_comparte_snapshot_y_fingerprint_exacto_con_apply(self):
        salida = StringIO()
        call_command(
            'configurar_bloque_gym', cliente=self.cliente.pk,
            semana_inicio=self.inicio.isoformat(), semanas=4,
            objetivo_principal='hipertrofia',
            objetivo_secundario=['gemelos'], motor_version='v-helms',
            stdout=salida,
        )
        previo = json.loads(salida.getvalue())
        self.assertEqual(ContratoBloqueGym.objects.count(), 0)
        self.assertEqual(previo['semana_fin_prevista'], '2026-09-20')
        self.assertEqual(previo['objetivo_sesiones'], 5)
        self.assertEqual(previo['minimo_valido'], 3)
        self.assertEqual(previo['estrategia_id'], self.estrategia.pk)
        self.assertEqual(previo['estrategia_version'], 1)
        self.assertEqual(previo['objetivos_secundarios'], ['gemelos'])
        self.assertEqual(previo['limites_snapshot'], {'sin_autoajustes': True})
        self.assertEqual(previo['motor'], {'nombre': 'Helms', 'version': 'v-helms'})
        self.assertEqual(len(previo['fingerprint']), 64)
        self.assertFalse(previo['propuesta_existente'])

        salida = StringIO()
        call_command(
            'configurar_bloque_gym', cliente=self.cliente.pk,
            semana_inicio=self.inicio.isoformat(), semanas=4,
            objetivo_principal='hipertrofia',
            objetivo_secundario=['gemelos'], motor_version='v-helms',
            apply=True, stdout=salida,
        )
        aplicado = json.loads(salida.getvalue())
        bloque = ContratoBloqueGym.objects.get()
        self.assertEqual(aplicado['fingerprint'], previo['fingerprint'])
        self.assertEqual(bloque.fingerprint, previo['fingerprint'])

        salida = StringIO()
        call_command(
            'configurar_bloque_gym', cliente=self.cliente.pk,
            semana_inicio=self.inicio.isoformat(), semanas=4,
            objetivo_principal='hipertrofia',
            objetivo_secundario=['gemelos'], motor_version='v-helms',
            stdout=salida,
        )
        self.assertTrue(json.loads(salida.getvalue())['propuesta_existente'])
        self.assertEqual(ContratoBloqueGym.objects.count(), 1)
