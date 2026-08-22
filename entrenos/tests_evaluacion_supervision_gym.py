"""Fase 6.4B: cierre factual e idempotente de la supervisión diaria Gym."""

import json
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    EntrenoRealizado,
    EvaluacionSupervisionGym,
    GymDecisionVersion,
)
from entrenos.services.evaluacion_supervision_gym_service import (
    cerrar_supervisiones_gym,
    evaluar_supervision_gym,
)
from rutinas.models import Rutina


class EvaluacionSupervisionGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cierre-supervision", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro_user = User.objects.create_user("cierre-ajeno", password="x")
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.fecha = date(2026, 8, 20)
        self.hoy = date(2026, 8, 22)
        self.rutina = Rutina.objects.create(nombre="Sesión evaluable")

    def _version(
        self,
        *,
        cliente=None,
        fecha=None,
        version=2,
        origen=GymDecisionVersion.ORIGEN_CORRECCION,
        postura="sostener",
        vigente=True,
        reemplaza=None,
        modo_reducido=True,
    ):
        estado = {
            "proteger": "recuperar",
            "sostener": "version_reducida",
            "empujar": "entrenar",
        }[postura]
        return GymDecisionVersion.objects.create(
            cliente=cliente or self.cliente,
            fecha=fecha or self.fecha,
            version=version,
            decision_id=f"gym-{(fecha or self.fecha).isoformat()}-v{version}-{origen}",
            origen=origen,
            vigente=vigente,
            fingerprint=f"fp-{version}-{origen}",
            base_fingerprint="base",
            postura=postura,
            snapshot={
                "estado": estado,
                "postura": postura,
                "modo_reducido": modo_reducido,
            },
            ajustes={"postura": postura, "modo_reducido": modo_reducido},
            reemplaza=reemplaza,
        )

    def _entreno(
        self,
        *,
        cliente=None,
        fecha=None,
        version=None,
        modo_reducido=False,
        causal="exacta",
        emitida_en=None,
    ):
        return EntrenoRealizado.objects.create(
            cliente=cliente or self.cliente,
            rutina=self.rutina,
            fecha=fecha or self.fecha,
            fecha_ejecucion=fecha or self.fecha,
            gym_decision_version=version,
            gym_decision_estado_causal=causal if version else None,
            gym_decision_emitida_en=emitida_en if version else None,
            modo_reducido=modo_reducido,
            volumen_total_kg=100,
        )

    def test_sostener_exacto_y_reducido_es_ejecucion_conforme(self):
        version = self._version()
        entreno = self._entreno(version=version, modo_reducido=True)

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "ejecutada_conforme")
        self.assertEqual(resultado["evidencia_snapshot"]["entrenos_exactos"], [entreno.pk])

    def test_sostener_exacto_normal_es_desviacion_si_exigia_reduccion(self):
        version = self._version(modo_reducido=True)
        self._entreno(version=version, modo_reducido=False)

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "desviada")

    def test_empujar_manual_exacto_es_conforme_y_rpe_ausente_no_importa(self):
        version = self._version(postura="empujar", modo_reducido=False)
        self._entreno(version=version, modo_reducido=False)

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "ejecutada_conforme")

    def test_superada_durante_ejecucion_no_puede_ser_favorable(self):
        version = self._version()
        self._entreno(
            version=version,
            modo_reducido=True,
            causal="superada_durante_ejecucion",
        )

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "inconclusa")

    def test_sostener_sin_vinculo_explicito_es_inconclusa(self):
        version = self._version()
        self._entreno(version=None, modo_reducido=True)

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "inconclusa")

    def test_proteger_sin_entreno_cumple_proteccion_tras_cerrar_el_dia(self):
        version = self._version(postura="proteger", modo_reducido=False)

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "proteccion_cumplida")

    def test_proteger_con_ejecucion_exacta_posterior_es_desviada(self):
        version = self._version(postura="proteger", modo_reducido=False)
        posterior = version.creado_en + timedelta(minutes=2)
        self._entreno(version=version, emitida_en=posterior)

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "desviada")

    def test_proteger_no_juzga_retroactivamente_entreno_anterior(self):
        motor = self._version(
            version=1,
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            postura="empujar",
            vigente=False,
            modo_reducido=False,
        )
        version = self._version(
            version=2,
            postura="proteger",
            reemplaza=motor,
            modo_reducido=False,
        )
        anterior = version.creado_en - timedelta(hours=1)
        self._entreno(version=motor, emitida_en=anterior)

        resultado = evaluar_supervision_gym(version, hoy=self.hoy)

        self.assertEqual(resultado["resultado"], "inconclusa")

    def test_no_evalua_motor_reemplazada_no_vigente_ni_dia_abierto(self):
        motor = self._version(
            version=1,
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            postura="empujar",
            vigente=False,
            modo_reducido=False,
        )
        reemplazada = self._version(version=2, vigente=False, reemplaza=motor)
        final = self._version(
            version=3,
            origen=GymDecisionVersion.ORIGEN_REVERSION,
            postura="empujar",
            reemplaza=reemplazada,
            modo_reducido=False,
        )
        abierta = self._version(fecha=self.hoy, version=4)

        self.assertIsNone(evaluar_supervision_gym(motor, hoy=self.hoy))
        self.assertIsNone(evaluar_supervision_gym(reemplazada, hoy=self.hoy))
        self.assertIsNone(evaluar_supervision_gym(abierta, hoy=self.hoy))
        self.assertEqual(
            evaluar_supervision_gym(final, hoy=self.hoy)["resultado"],
            "inconclusa",
        )

    def test_no_evalua_version_que_no_es_la_final_aunque_legacy_marque_dos_vigentes(self):
        anterior = self._version(version=2, vigente=True)
        self._version(
            version=3,
            origen=GymDecisionVersion.ORIGEN_REVERSION,
            postura="empujar",
            vigente=True,
            reemplaza=anterior,
            modo_reducido=False,
        )

        self.assertIsNone(evaluar_supervision_gym(anterior, hoy=self.hoy))

    def test_apply_es_idempotente_y_aisla_cliente_y_rango(self):
        incluida = self._version()
        ajena = self._version(cliente=self.otro, version=2)
        fuera = self._version(fecha=date(2026, 8, 18), version=2)

        primera = cerrar_supervisiones_gym(
            cliente_id=self.cliente.pk,
            desde=self.fecha,
            hasta=self.fecha,
            limite=50,
            aplicar=True,
            hoy=self.hoy,
        )
        segunda = cerrar_supervisiones_gym(
            cliente_id=self.cliente.pk,
            desde=self.fecha,
            hasta=self.fecha,
            limite=50,
            aplicar=True,
            hoy=self.hoy,
        )

        self.assertEqual(primera["aplicados"], 1)
        self.assertEqual(segunda["aplicados"], 0)
        self.assertEqual(EvaluacionSupervisionGym.objects.count(), 1)
        self.assertTrue(
            EvaluacionSupervisionGym.objects.filter(version_decision=incluida).exists()
        )
        self.assertFalse(
            EvaluacionSupervisionGym.objects.filter(version_decision=ajena).exists()
        )
        self.assertFalse(
            EvaluacionSupervisionGym.objects.filter(version_decision=fuera).exists()
        )

    def test_dry_run_y_evaluacion_no_mutan_fuentes_ni_autoridad(self):
        version = self._version()
        entreno = self._entreno(version=version, modo_reducido=True)
        snapshot_version = {
            "vigente": version.vigente,
            "snapshot": version.snapshot.copy(),
            "ajustes": version.ajustes.copy(),
        }
        snapshot_entreno = {
            "modo_reducido": entreno.modo_reducido,
            "gym_decision_estado_causal": entreno.gym_decision_estado_causal,
        }

        resumen = cerrar_supervisiones_gym(
            cliente_id=self.cliente.pk,
            desde=self.fecha,
            hasta=self.fecha,
            aplicar=False,
            hoy=self.hoy,
        )

        self.assertEqual(resumen["candidatos"], 1)
        self.assertEqual(resumen["aplicados"], 0)
        self.assertFalse(EvaluacionSupervisionGym.objects.exists())
        version.refresh_from_db()
        entreno.refresh_from_db()
        self.assertEqual(snapshot_version, {
            "vigente": version.vigente,
            "snapshot": version.snapshot,
            "ajustes": version.ajustes,
        })
        self.assertEqual(snapshot_entreno, {
            "modo_reducido": entreno.modo_reducido,
            "gym_decision_estado_causal": entreno.gym_decision_estado_causal,
        })

    def test_comando_dry_run_por_defecto_y_apply_emite_resumen_jsonl(self):
        self._version()
        salida = StringIO()

        call_command(
            "cerrar_supervision_gym",
            cliente=self.cliente.pk,
            desde=self.fecha.isoformat(),
            hasta=self.fecha.isoformat(),
            stdout=salida,
        )

        payload = json.loads(salida.getvalue().strip().splitlines()[-1])
        self.assertTrue(payload["solo_lectura"])
        self.assertEqual(payload["candidatos"], 1)
        self.assertFalse(EvaluacionSupervisionGym.objects.exists())
