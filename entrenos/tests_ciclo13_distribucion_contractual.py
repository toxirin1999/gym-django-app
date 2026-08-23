import json
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ContratoSemanalGym,
    EstrategiaSemanalGym,
    EvaluacionSemanalGym,
    SesionProgramada,
)


class DistribucionSemanalContractualTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ciclo13')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Ciclo 13'},
        )
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=2,
            minimo_valido=1,
            vigente_desde=date(2026, 1, 1),
            motivo='Contrato de prueba',
        )

    def _semana(self, lunes, estados, *, revision='aceptada'):
        contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente,
            estrategia=self.estrategia,
            semana=lunes,
            objetivo_sesiones=len(estados),
            minimo_valido=1,
        )
        sesiones = []
        conteos = {codigo: 0 for codigo, _ in SesionProgramada.ESTADOS}
        reubicadas = 0
        for indice, dato in enumerate(estados):
            estado, desplazamiento = dato
            prevista = lunes + timedelta(days=indice * 2)
            realizada = None
            if estado == SesionProgramada.ESTADO_COMPLETADA:
                realizada = prevista + timedelta(days=desplazamiento)
                reubicadas += desplazamiento != 0
            sesiones.append(SesionProgramada.objects.create(
                cliente=self.cliente,
                contrato_semanal=contrato,
                semana_prescrita=lunes,
                fecha_prevista=prevista,
                fecha_realizada=realizada,
                estado=estado,
                nombre_sesion=f'Sesión {indice + 1}',
            ))
            conteos[estado] += 1
        EvaluacionSemanalGym.objects.create(
            contrato=contrato,
            estado_cumplimiento=EvaluacionSemanalGym.CUMPLIMIENTO_OBJETIVO,
            sesiones_completadas=conteos[SesionProgramada.ESTADO_COMPLETADA],
            sesiones_reubicadas=reubicadas,
            estado_revision=revision,
            evidencia_snapshot={'conteos_estado': conteos},
        )
        return contrato, sesiones

    def test_exige_tres_semanas_cerradas_y_aceptadas(self):
        from entrenos.services.distribucion_semanal_contractual_service import (
            analizar_distribucion_semanal_contractual,
        )

        self._semana(date(2026, 7, 6), [(SesionProgramada.ESTADO_COMPLETADA, 0)])
        self._semana(date(2026, 7, 13), [(SesionProgramada.ESTADO_COMPLETADA, 0)])
        self._semana(
            date(2026, 7, 20),
            [(SesionProgramada.ESTADO_COMPLETADA, 0)],
            revision=EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )

        resultado = analizar_distribucion_semanal_contractual(
            self.cliente, hasta=date(2026, 8, 1),
        )

        self.assertEqual(resultado['estado'], 'evidencia_insuficiente')
        self.assertEqual(resultado['semanas_aceptadas'], 2)
        self.assertEqual(resultado['minimo_semanas'], 3)
        self.assertEqual(resultado['semanas'], [])

    def test_clasifica_identidades_sin_reinterpretar_proteccion(self):
        from entrenos.services.distribucion_semanal_contractual_service import (
            analizar_distribucion_semanal_contractual,
        )

        combinaciones = [
            [(SesionProgramada.ESTADO_COMPLETADA, 0), (SesionProgramada.ESTADO_COMPLETADA, 1)],
            [(SesionProgramada.ESTADO_SALTADA_USUARIO, 0), (SesionProgramada.ESTADO_OMITIDA_SISTEMA, 0)],
            [(SesionProgramada.ESTADO_CANCELADA_LESION, 0), (SesionProgramada.ESTADO_COMPLETADA, -1)],
        ]
        for semana, estados in zip((date(2026, 7, 6), date(2026, 7, 13), date(2026, 7, 20)), combinaciones):
            _, sesiones = self._semana(semana, estados)
        # El cierre semanal real solo llama reubicada a una fecha efectiva
        # presente y distinta; un dato legacy sin fecha sigue siendo completada.
        sesiones[-1].fecha_realizada = None
        sesiones[-1].save(update_fields=['fecha_realizada'])

        resultado = analizar_distribucion_semanal_contractual(
            self.cliente, hasta=date(2026, 8, 1),
        )

        self.assertEqual(resultado['estado'], 'evaluada')
        self.assertEqual(resultado['conteos'], {
            'completada': 2,
            'reubicada': 1,
            'omitida': 2,
            'protegida': 1,
        })
        omisiones = [
            sesion for semana in resultado['semanas'] for sesion in semana['sesiones']
            if sesion['resultado'] == 'omitida'
        ]
        self.assertEqual(
            [sesion['causa'] for sesion in omisiones],
            ['usuario', 'sistema'],
        )
        protegida = next(
            sesion for semana in resultado['semanas'] for sesion in semana['sesiones']
            if sesion['resultado'] == 'protegida'
        )
        self.assertEqual(protegida['causa'], 'lesion')

    def test_es_cliente_scoped_determinista_read_only_e_idempotente(self):
        from entrenos.services.distribucion_semanal_contractual_service import (
            analizar_distribucion_semanal_contractual,
        )

        for lunes in (date(2026, 7, 6), date(2026, 7, 13), date(2026, 7, 20)):
            self._semana(lunes, [(SesionProgramada.ESTADO_COMPLETADA, 0)])
        otro_user = User.objects.create_user(username='otro-ciclo13')
        otro, _ = Cliente.objects.get_or_create(user=otro_user, defaults={'nombre': 'Otro'})
        EstrategiaSemanalGym.objects.create(
            cliente=otro, version=1, objetivo_sesiones=1, minimo_valido=1,
            vigente_desde=date(2026, 1, 1), motivo='Ajena',
        )
        antes = (
            ContratoSemanalGym.objects.count(), EvaluacionSemanalGym.objects.count(),
            SesionProgramada.objects.count(),
        )

        primero = analizar_distribucion_semanal_contractual(self.cliente, hasta=date(2026, 8, 1))
        segundo = analizar_distribucion_semanal_contractual(self.cliente, hasta=date(2026, 8, 1))

        self.assertEqual(primero, segundo)
        self.assertEqual(antes, (
            ContratoSemanalGym.objects.count(), EvaluacionSemanalGym.objects.count(),
            SesionProgramada.objects.count(),
        ))
        self.assertTrue(all(s['contrato_id'] in {
            c.pk for c in ContratoSemanalGym.objects.filter(cliente=self.cliente)
        } for s in primero['semanas']))

    def test_command_emite_json_estable_y_no_ofrece_apply(self):
        for lunes in (date(2026, 7, 6), date(2026, 7, 13), date(2026, 7, 20)):
            self._semana(lunes, [(SesionProgramada.ESTADO_COMPLETADA, 0)])
        salida = StringIO()

        call_command(
            'auditar_distribucion_semanal_contractual',
            cliente=self.cliente.pk,
            hasta='2026-08-01',
            stdout=salida,
        )

        documento = json.loads(salida.getvalue())
        self.assertEqual(documento['cliente_id'], self.cliente.pk)
        self.assertEqual(documento['estado'], 'evaluada')
        self.assertNotIn('apply', documento)
