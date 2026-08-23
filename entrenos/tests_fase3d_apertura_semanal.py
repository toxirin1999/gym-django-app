from datetime import date, timedelta
from io import StringIO
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ContratoBloqueGym, ContratoSemanalGym, EstrategiaSemanalGym


class AperturaSemanalGymTests(TestCase):
    lunes = date(2026, 8, 24)

    def _cliente(self, sufijo, *, estado=ContratoBloqueGym.ESTADO_ACTIVO,
                 inicio=None, fin=None, con_bloque=True):
        user = User.objects.create_user(username=f'apertura_{sufijo}')
        cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': f'Cliente {sufijo}'},
        )
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=cliente, version=1, objetivo_sesiones=1, minimo_valido=1,
            vigente_desde=self.lunes - timedelta(weeks=4), estado='aprobada',
        )
        bloque = None
        if con_bloque:
            inicio = inicio or self.lunes
            fin = fin or self.lunes + timedelta(weeks=3, days=6)
            bloque = ContratoBloqueGym.objects.create(
                cliente=cliente, version=1, estado=estado,
                semana_inicio=inicio, semanas_previstas=4,
                semana_fin_prevista=fin, estrategia=estrategia,
                objetivo_sesiones=1, minimo_valido=1,
                objetivo_principal='hipertrofia', objetivos_secundarios=[],
                limites_snapshot={}, motor_nombre='Helms', motor_version='v1',
                fingerprint=(sufijo * 64)[:64],
            )
        return cliente, estrategia, bloque

    def test_semana_objetivo_lunes_inclusivo_y_domingo_siguiente(self):
        from entrenos.services.apertura_semanal_gym_service import semana_objetivo

        self.assertEqual(semana_objetivo(date(2026, 8, 24)), date(2026, 8, 24))
        self.assertEqual(semana_objetivo(date(2026, 8, 23)), date(2026, 8, 24))

    @patch('entrenos.services.apertura_semanal_gym_service.previsualizar_contrato_semanal_gym')
    def test_dry_run_previsualiza_sin_escribir(self, preview):
        cliente, _, _ = self._cliente('a')
        preview.return_value = [(self.lunes, {'dia': 1, 'rutina_nombre': 'A'})]

        from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym
        resultado = preparar_semana_gym(fecha_referencia=date(2026, 8, 23))

        self.assertTrue(resultado['solo_lectura'])
        self.assertEqual(resultado['resultados'][0]['estado'], 'previsualizada')
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)
        preview.assert_called_once_with(cliente, self.lunes)

    @patch('entrenos.services.apertura_semanal_gym_service.materializar_contrato_semanal_gym')
    def test_apply_materializa(self, materializar):
        cliente, estrategia, bloque = self._cliente('b')
        def crear(*_args):
            return ContratoSemanalGym.objects.create(
                cliente=cliente, estrategia=estrategia, bloque=bloque,
                indice_semana_bloque=1, semana=self.lunes,
                objetivo_sesiones=1, minimo_valido=1,
            )
        materializar.side_effect = crear

        from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym
        resultado = preparar_semana_gym(
            fecha_referencia=self.lunes, aplicar=True,
        )

        self.assertEqual(resultado['resultados'][0]['estado'], 'materializada')
        materializar.assert_called_once_with(cliente, self.lunes)

    @patch('entrenos.services.apertura_semanal_gym_service.materializar_contrato_semanal_gym')
    @patch('entrenos.services.apertura_semanal_gym_service.previsualizar_contrato_semanal_gym')
    def test_rerun_no_invoca_motor_ni_modifica_timestamp(self, preview, materializar):
        cliente, estrategia, bloque = self._cliente('c')
        contrato = ContratoSemanalGym.objects.create(
            cliente=cliente, estrategia=estrategia, bloque=bloque,
            indice_semana_bloque=1, semana=self.lunes,
            objetivo_sesiones=1, minimo_valido=1,
        )
        creado = contrato.creado_en

        from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym
        resultado = preparar_semana_gym(fecha_referencia=self.lunes, aplicar=True)

        contrato.refresh_from_db()
        self.assertEqual(resultado['resultados'][0]['estado'], 'ya_materializada')
        self.assertEqual(contrato.creado_en, creado)
        preview.assert_not_called()
        materializar.assert_not_called()

    @patch('entrenos.services.apertura_semanal_gym_service.previsualizar_contrato_semanal_gym')
    def test_excluye_estados_fuera_de_rango_y_cliente_sin_bloque(self, preview):
        self._cliente('d', estado=ContratoBloqueGym.ESTADO_PAUSADO)
        self._cliente('e', estado=ContratoBloqueGym.ESTADO_PROPUESTO)
        self._cliente('f', estado=ContratoBloqueGym.ESTADO_FINALIZADO)
        self._cliente('g', inicio=self.lunes + timedelta(weeks=1),
                      fin=self.lunes + timedelta(weeks=4))
        self._cliente('h', con_bloque=False)

        from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym
        resultado = preparar_semana_gym(fecha_referencia=self.lunes)

        self.assertEqual(resultado['resultados'], [])
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)
        preview.assert_not_called()

    @patch('entrenos.services.apertura_semanal_gym_service.previsualizar_contrato_semanal_gym')
    def test_divergencia_se_reporta_sin_escritura(self, preview):
        cliente, _, bloque = self._cliente('i')
        bloque.objetivo_sesiones = 2
        ContratoBloqueGym.objects.filter(pk=bloque.pk).update(objetivo_sesiones=2)

        from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym
        resultado = preparar_semana_gym(fecha_referencia=self.lunes, aplicar=True)

        self.assertEqual(resultado['resultados'][0]['estado'], 'error')
        self.assertEqual(resultado['resultados'][0]['codigo'], 'divergencia_bloque')
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)
        preview.assert_not_called()

    @patch('entrenos.services.apertura_semanal_gym_service.previsualizar_contrato_semanal_gym')
    def test_un_error_no_bloquea_otro_cliente(self, preview):
        malo, _, _ = self._cliente('j')
        bueno, _, _ = self._cliente('k')
        preview.side_effect = lambda cliente, semana: (
            (_ for _ in ()).throw(ValueError('motor inválido'))
            if cliente.pk == malo.pk else [(semana, {'dia': 1, 'rutina_nombre': 'OK'})]
        )

        from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym
        resultado = preparar_semana_gym(fecha_referencia=self.lunes)

        por_cliente = {fila['cliente_id']: fila for fila in resultado['resultados']}
        self.assertEqual(por_cliente[malo.pk]['estado'], 'error')
        self.assertEqual(por_cliente[bueno.pk]['estado'], 'previsualizada')

    @patch('entrenos.services.apertura_semanal_gym_service.materializar_contrato_semanal_gym',
           side_effect=IntegrityError('unique race'))
    def test_integrity_error_de_carrera_es_controlado(self, _materializar):
        self._cliente('l')
        from entrenos.services.apertura_semanal_gym_service import preparar_semana_gym

        resultado = preparar_semana_gym(fecha_referencia=self.lunes, aplicar=True)

        fila = resultado['resultados'][0]
        self.assertEqual(fila['estado'], 'error')
        self.assertEqual(fila['codigo'], 'carrera_integridad')
        self.assertNotIn('traceback', fila)

    @patch('entrenos.services.apertura_semanal_gym_service.previsualizar_contrato_semanal_gym',
           return_value=[])
    def test_comando_json_determinista_y_fecha_iso_validada(self, _preview):
        self._cliente('m')
        salida = StringIO()
        call_command('preparar_semana_gym', fecha_referencia='2026-08-23', stdout=salida)
        payload = json.loads(salida.getvalue())
        self.assertEqual(payload['semana'], '2026-08-24')
        self.assertEqual(payload['modo'], 'dry-run')
        self.assertIn('"modo":"dry-run"', salida.getvalue())
