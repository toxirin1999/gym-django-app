import json
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ContratoSemanalGym, EstrategiaSemanalGym, EvaluacionSemanalGym,
    SesionProgramada,
)


class OperarSemanaGymTests(TestCase):
    lunes = date(2026, 8, 31)
    semana_anterior = date(2026, 8, 24)

    def _contrato(self, sufijo):
        user = User.objects.create_user(username=f'operar_{sufijo}')
        cliente = Cliente.objects.get(user=user)
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=cliente, version=1, objetivo_sesiones=1, minimo_valido=1,
            vigente_desde=self.semana_anterior, estado='aprobada',
        )
        contrato = ContratoSemanalGym.objects.create(
            cliente=cliente, estrategia=estrategia, semana=self.semana_anterior,
            objetivo_sesiones=1, minimo_valido=1,
        )
        SesionProgramada.objects.create(
            cliente=cliente, contrato_semanal=contrato,
            semana_prescrita=self.semana_anterior,
            fecha_prevista=self.semana_anterior, estado='pendiente',
            nombre_sesion='A', dia_numero=1,
        )
        return contrato

    @patch('entrenos.services.ciclo_semanal_gym_service.preparar_semana_gym')
    def test_domingo_dry_run_y_apply_reutilizan_apertura(self, preparar):
        preparar.return_value = {
            'resultados': [{'estado': 'previsualizada'}],
            'semana': '2026-08-31',
        }
        from entrenos.services.ciclo_semanal_gym_service import operar_semana_gym

        dry = operar_semana_gym(fecha_referencia=date(2026, 8, 30))
        apply = operar_semana_gym(fecha_referencia=date(2026, 8, 30), aplicar=True)

        self.assertEqual(dry['operacion'], 'apertura_semanal')
        self.assertEqual(dry['semana'], '2026-08-31')
        self.assertTrue(dry['solo_lectura'])
        self.assertFalse(apply['solo_lectura'])
        self.assertEqual(preparar.call_args_list[0].kwargs, {
            'fecha_referencia': date(2026, 8, 30), 'aplicar': False,
            'solo_domingo': True,
        })
        self.assertTrue(preparar.call_args_list[1].kwargs['aplicar'])

    def test_lunes_dry_run_no_crea_y_apply_crea_pendiente(self):
        contrato = self._contrato('uno')
        from entrenos.services.ciclo_semanal_gym_service import operar_semana_gym

        dry = operar_semana_gym(fecha_referencia=self.lunes)
        self.assertEqual(dry['operacion'], 'cierre_semanal')
        self.assertEqual(dry['semana'], '2026-08-24')
        self.assertTrue(dry['solo_lectura'])
        self.assertEqual(EvaluacionSemanalGym.objects.count(), 0)
        self.assertEqual(dry['resultados'][0]['estado'], 'previsualizada')

        aplicado = operar_semana_gym(fecha_referencia=self.lunes, aplicar=True)
        evaluacion = EvaluacionSemanalGym.objects.get(contrato=contrato)
        self.assertEqual(evaluacion.estado_revision, 'pendiente')
        self.assertEqual(aplicado['resultados'][0]['estado'], 'evaluada')

    def test_repeticion_y_evaluacion_respondida_preservan_identidad_y_timestamps(self):
        contrato = self._contrato('dos')
        from entrenos.services.ciclo_semanal_gym_service import operar_semana_gym
        operar_semana_gym(fecha_referencia=self.lunes, aplicar=True)
        evaluacion = EvaluacionSemanalGym.objects.get(contrato=contrato)
        EvaluacionSemanalGym.objects.filter(pk=evaluacion.pk).update(estado_revision='aceptada')
        evaluacion.refresh_from_db()
        antes = (evaluacion.pk, evaluacion.actualizada_en, evaluacion.estado_revision)

        repetido = operar_semana_gym(fecha_referencia=self.lunes, aplicar=True)
        evaluacion.refresh_from_db()
        self.assertEqual((evaluacion.pk, evaluacion.actualizada_en, evaluacion.estado_revision), antes)
        self.assertEqual(repetido['resultados'][0]['estado'], 'ya_evaluada')

    def test_dia_neutro_es_noop_sin_consultas_operativas(self):
        from entrenos.services.ciclo_semanal_gym_service import operar_semana_gym
        with self.assertNumQueries(0):
            resultado = operar_semana_gym(fecha_referencia=date(2026, 9, 1), aplicar=True)
        self.assertEqual(resultado['operacion'], 'sin_operacion')
        self.assertIsNone(resultado['semana'])
        self.assertEqual(resultado['resultados'], [])
        self.assertTrue(resultado['solo_lectura'])

    @patch('entrenos.services.ciclo_semanal_gym_service._snapshot')
    def test_error_de_un_cliente_no_detiene_al_siguiente(self, snapshot):
        malo = self._contrato('a')
        bueno = self._contrato('b')
        snapshot.side_effect = lambda contrato: (
            (_ for _ in ()).throw(ValueError('dato inválido'))
            if contrato.pk == malo.pk else {
                'estado_cumplimiento': 'insuficiente', 'sesiones_completadas': 0,
            }
        )
        from entrenos.services.ciclo_semanal_gym_service import operar_semana_gym
        resultado = operar_semana_gym(fecha_referencia=self.lunes)
        por_id = {fila['contrato_id']: fila for fila in resultado['resultados']}
        self.assertEqual(por_id[malo.pk]['estado'], 'error')
        self.assertEqual(por_id[bueno.pk]['estado'], 'previsualizada')

    def test_comando_emite_json_determinista_y_dry_run_por_defecto(self):
        salida = StringIO()
        call_command('operar_semana_gym', fecha_referencia='2026-09-01', stdout=salida)
        payload = json.loads(salida.getvalue())
        self.assertEqual(payload['modo'], 'dry-run')
        self.assertEqual(payload['fecha'], '2026-09-01')
        self.assertIn('"modo":"dry-run"', salida.getvalue())
