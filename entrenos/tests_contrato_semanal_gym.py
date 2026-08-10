from datetime import date
import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from rutinas.models import Rutina


class ContratoSemanalGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='contrato_semana_gym', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'Contrato semanal Gym'},
        )
        self.lunes = date(2026, 8, 10)

    def _aprobar(self, objetivo=5, minimo=3):
        from entrenos.services.estrategia_semanal_gym_service import (
            aprobar_estrategia_semanal_gym,
        )

        return aprobar_estrategia_semanal_gym(
            self.cliente,
            objetivo_sesiones=objetivo,
            minimo_valido=minimo,
            vigente_desde=self.lunes,
            aprobado_por=self.user,
            motivo='Objetivo personal confirmado',
        )

    @staticmethod
    def _planificador_cinco():
        class Planificador:
            def generar_entrenamiento_para_fecha(self, fecha):
                if fecha.weekday() >= 5:
                    return {'rutina_nombre': 'Descanso', 'ejercicios': []}
                numero = fecha.weekday() + 1
                return {
                    'rutina_nombre': f'Día {numero} - Hipertrofia',
                    'ejercicios': [{'nombre': f'Ejercicio {numero}'}],
                    'bloque': 'Hipertrofia',
                    'dia': numero,
                }

        return Planificador()

    def test_aprueba_estrategia_versionada_cinco_tres(self):
        estrategia = self._aprobar()

        self.assertEqual(estrategia.version, 1)
        self.assertEqual(estrategia.objetivo_sesiones, 5)
        self.assertEqual(estrategia.minimo_valido, 3)
        self.assertEqual(estrategia.estado, 'aprobada')
        self.assertEqual(estrategia.vigente_desde, self.lunes)
        self.assertEqual(estrategia.aprobado_por, self.user)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.dias_disponibles, 5)

    def test_nueva_aprobacion_cierra_anterior_y_crea_version(self):
        anterior = self._aprobar()

        nueva = self._aprobar(objetivo=5, minimo=4)

        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, 'retirada')
        self.assertEqual(anterior.vigente_hasta, date(2026, 8, 9))
        self.assertEqual(nueva.version, 2)
        self.assertEqual(nueva.minimo_valido, 4)

    def test_base_de_datos_rechaza_minimo_superior_al_objetivo(self):
        from entrenos.models import EstrategiaSemanalGym

        with self.assertRaises(IntegrityError), transaction.atomic():
            EstrategiaSemanalGym.objects.create(
                cliente=self.cliente,
                version=1,
                objetivo_sesiones=3,
                minimo_valido=4,
                vigente_desde=self.lunes,
                estado='aprobada',
            )

    def test_base_de_datos_rechaza_objetivo_superior_a_siete(self):
        from entrenos.models import EstrategiaSemanalGym

        with self.assertRaises(IntegrityError), transaction.atomic():
            EstrategiaSemanalGym.objects.create(
                cliente=self.cliente,
                version=1,
                objetivo_sesiones=8,
                minimo_valido=3,
                vigente_desde=self.lunes,
                estado='aprobada',
            )

    def test_contrato_conserva_snapshot_y_ancla_sesiones_a_la_semana(self):
        from entrenos.services.estrategia_semanal_gym_service import (
            abrir_contrato_semanal_gym,
        )

        estrategia = self._aprobar()
        contrato = abrir_contrato_semanal_gym(self.cliente, self.lunes)
        sesiones = []
        for offset in range(5):
            sesiones.append(SesionProgramada.objects.create(
                cliente=self.cliente,
                contrato_semanal=contrato,
                semana_prescrita=self.lunes,
                fecha_prevista=date(2026, 8, 10 + offset),
                nombre_sesion=f'Día {offset + 1}',
                dia_numero=offset + 1,
            ))

        self.assertEqual(contrato.estrategia, estrategia)
        self.assertEqual(contrato.objetivo_sesiones, 5)
        self.assertEqual(contrato.minimo_valido, 3)
        self.assertEqual(contrato.sesiones.count(), 5)
        self.assertTrue(all(s.semana_prescrita == self.lunes for s in sesiones))

    def test_tres_sesiones_es_semana_minima_valida_y_reubicada_no_crea_deuda(self):
        from entrenos.services.estrategia_semanal_gym_service import (
            abrir_contrato_semanal_gym,
            evaluar_contrato_semanal_gym,
        )

        self._aprobar()
        contrato = abrir_contrato_semanal_gym(self.cliente, self.lunes)
        for offset in range(5):
            completada = offset < 3
            SesionProgramada.objects.create(
                cliente=self.cliente,
                contrato_semanal=contrato,
                semana_prescrita=self.lunes,
                fecha_prevista=date(2026, 8, 10 + offset),
                fecha_realizada=(date(2026, 8, 11 + offset) if completada else None),
                estado=(
                    SesionProgramada.ESTADO_COMPLETADA
                    if completada else SesionProgramada.ESTADO_PENDIENTE
                ),
                nombre_sesion=f'Día {offset + 1}',
                dia_numero=offset + 1,
            )

        resultado = evaluar_contrato_semanal_gym(contrato)

        self.assertEqual(resultado['estado_cumplimiento'], 'minima_valida')
        self.assertEqual(resultado['sesiones_completadas'], 3)
        self.assertEqual(resultado['sesiones_reubicadas'], 3)
        self.assertEqual(resultado['deuda_generada'], 0)
        self.assertEqual(resultado['sesiones_pendientes'], 2)

    def test_cinco_sesiones_alcanza_objetivo_y_dos_es_insuficiente(self):
        from entrenos.services.estrategia_semanal_gym_service import (
            abrir_contrato_semanal_gym,
            evaluar_contrato_semanal_gym,
        )

        self._aprobar()
        contrato = abrir_contrato_semanal_gym(self.cliente, self.lunes)
        sesiones = [SesionProgramada.objects.create(
            cliente=self.cliente,
            contrato_semanal=contrato,
            semana_prescrita=self.lunes,
            fecha_prevista=date(2026, 8, 10 + offset),
            estado=SesionProgramada.ESTADO_COMPLETADA,
            nombre_sesion=f'Día {offset + 1}',
        ) for offset in range(5)]

        self.assertEqual(
            evaluar_contrato_semanal_gym(contrato)['estado_cumplimiento'],
            'objetivo',
        )
        for sesion in sesiones[2:]:
            sesion.estado = SesionProgramada.ESTADO_PENDIENTE
            sesion.save(update_fields=['estado'])
        self.assertEqual(
            evaluar_contrato_semanal_gym(contrato)['estado_cumplimiento'],
            'insuficiente',
        )

    def test_contrato_exige_lunes_y_completada_sin_fecha_no_es_reubicada(self):
        from entrenos.services.estrategia_semanal_gym_service import (
            abrir_contrato_semanal_gym,
            evaluar_contrato_semanal_gym,
        )

        self._aprobar()
        with self.assertRaises(ValueError):
            abrir_contrato_semanal_gym(self.cliente, date(2026, 8, 11))

        contrato = abrir_contrato_semanal_gym(self.cliente, self.lunes)
        SesionProgramada.objects.create(
            cliente=self.cliente,
            contrato_semanal=contrato,
            semana_prescrita=self.lunes,
            fecha_prevista=self.lunes,
            fecha_realizada=None,
            estado=SesionProgramada.ESTADO_COMPLETADA,
        )
        self.assertEqual(
            evaluar_contrato_semanal_gym(contrato)['sesiones_reubicadas'],
            0,
        )

    def test_comando_previsualiza_y_solo_aplica_con_apply(self):
        from entrenos.models import EstrategiaSemanalGym

        salida = StringIO()
        call_command(
            'configurar_estrategia_semanal_gym',
            cliente=self.cliente.pk,
            objetivo=5,
            minimo=3,
            desde=self.lunes.isoformat(),
            stdout=salida,
        )
        previo = json.loads(salida.getvalue())
        self.assertTrue(previo['solo_lectura'])
        self.assertEqual(EstrategiaSemanalGym.objects.count(), 0)

        salida = StringIO()
        call_command(
            'configurar_estrategia_semanal_gym',
            cliente=self.cliente.pk,
            objetivo=5,
            minimo=3,
            desde=self.lunes.isoformat(),
            apply=True,
            stdout=salida,
        )
        aplicado = json.loads(salida.getvalue())
        self.assertEqual(aplicado['modo'], 'apply')
        self.assertEqual(aplicado['version'], 1)
        self.assertEqual(EstrategiaSemanalGym.objects.get().minimo_valido, 3)

    @patch('entrenos.services.estrategia_semanal_gym_service._build_planificador')
    def test_materializa_exactamente_cinco_sesiones_y_es_idempotente(self, build):
        from entrenos.services.estrategia_semanal_gym_service import (
            materializar_contrato_semanal_gym,
        )

        build.return_value = self._planificador_cinco()
        self._aprobar()

        primera = materializar_contrato_semanal_gym(self.cliente, self.lunes)
        segunda = materializar_contrato_semanal_gym(self.cliente, self.lunes)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(primera.sesiones.count(), 5)
        self.assertEqual(SesionProgramada.objects.count(), 5)
        self.assertEqual(
            list(primera.sesiones.order_by('fecha_prevista').values_list('dia_numero', flat=True)),
            [1, 2, 3, 4, 5],
        )
        self.assertTrue(all(
            sesion.semana_prescrita == self.lunes
            for sesion in primera.sesiones.all()
        ))

    @patch('entrenos.services.estrategia_semanal_gym_service._build_planificador')
    def test_materializacion_adopta_sesion_existente_sin_duplicarla(self, build):
        from entrenos.services.estrategia_semanal_gym_service import (
            materializar_contrato_semanal_gym,
        )

        build.return_value = self._planificador_cinco()
        self._aprobar()
        existente = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.lunes,
            nombre_sesion='Sesión ya visible',
            estado=SesionProgramada.ESTADO_COMPLETADA,
            fecha_realizada=self.lunes,
        )

        contrato = materializar_contrato_semanal_gym(self.cliente, self.lunes)

        existente.refresh_from_db()
        self.assertEqual(SesionProgramada.objects.count(), 5)
        self.assertEqual(existente.contrato_semanal, contrato)
        self.assertEqual(existente.semana_prescrita, self.lunes)
        self.assertEqual(existente.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(existente.nombre_sesion, 'Sesión ya visible')

    @patch('entrenos.services.estrategia_semanal_gym_service._build_planificador')
    def test_concilia_por_fecha_planificada_y_conserva_fecha_real_reubicada(self, build):
        from entrenos.services.estrategia_semanal_gym_service import (
            materializar_contrato_semanal_gym,
        )

        build.return_value = self._planificador_cinco()
        self._aprobar()
        rutina = Rutina.objects.create(nombre='Día 2 - Hipertrofia')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=date(2026, 8, 11),
            fecha_ejecucion=date(2026, 8, 10),
        )

        contrato = materializar_contrato_semanal_gym(self.cliente, self.lunes)

        sesion_lunes = contrato.sesiones.get(fecha_prevista=date(2026, 8, 10))
        sesion_martes = contrato.sesiones.get(fecha_prevista=date(2026, 8, 11))
        self.assertEqual(sesion_lunes.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertIsNone(sesion_lunes.entreno_realizado_id)
        self.assertEqual(sesion_martes.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(sesion_martes.entreno_realizado, entreno)
        self.assertEqual(sesion_martes.fecha_realizada, date(2026, 8, 10))

    @patch('entrenos.services.estrategia_semanal_gym_service._build_planificador')
    def test_plan_incompleto_no_deja_contrato_ni_sesiones_parciales(self, build):
        from entrenos.models import ContratoSemanalGym
        from entrenos.services.estrategia_semanal_gym_service import (
            ContratoSemanalIncompleto,
            materializar_contrato_semanal_gym,
        )

        planificador = self._planificador_cinco()
        original = planificador.generar_entrenamiento_para_fecha
        planificador.generar_entrenamiento_para_fecha = lambda fecha: (
            {'rutina_nombre': 'Descanso', 'ejercicios': []}
            if fecha.weekday() == 4 else original(fecha)
        )
        build.return_value = planificador
        self._aprobar()

        with self.assertRaises(ContratoSemanalIncompleto):
            materializar_contrato_semanal_gym(self.cliente, self.lunes)

        self.assertEqual(ContratoSemanalGym.objects.count(), 0)
        self.assertEqual(SesionProgramada.objects.count(), 0)

    @patch('entrenos.services.estrategia_semanal_gym_service._build_planificador')
    def test_comando_materializacion_es_dry_run_por_defecto_y_apply_crea_cinco(self, build):
        from entrenos.models import ContratoSemanalGym

        build.return_value = self._planificador_cinco()
        self._aprobar()
        salida = StringIO()
        call_command(
            'materializar_contrato_semanal_gym',
            cliente=self.cliente.pk,
            semana=self.lunes.isoformat(),
            stdout=salida,
        )
        previo = json.loads(salida.getvalue())
        self.assertTrue(previo['solo_lectura'])
        self.assertEqual(previo['sesiones_previstas'], 5)
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)

        salida = StringIO()
        call_command(
            'materializar_contrato_semanal_gym',
            cliente=self.cliente.pk,
            semana=self.lunes.isoformat(),
            apply=True,
            stdout=salida,
        )
        aplicado = json.loads(salida.getvalue())
        self.assertEqual(aplicado['modo'], 'apply')
        self.assertEqual(aplicado['sesiones_materializadas'], 5)
        self.assertEqual(ContratoSemanalGym.objects.count(), 1)
        self.assertEqual(SesionProgramada.objects.count(), 5)
