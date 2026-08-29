from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ContratoSemanalGym,
    EntrenoRealizado,
    EstrategiaSemanalGym,
    EvaluacionSemanalGym,
    SesionProgramada,
)
from entrenos.services.evaluacion_semanal_gym_service import (
    ActorNoAutorizado,
    ContratoNoMaterializado,
    EvaluacionSemanalRevisada,
    SemanaAbierta,
    evaluar_y_persistir_contrato_semanal_gym,
    responder_evaluacion_semanal_gym,
)
from rutinas.models import Rutina


class EvaluacionSemanalGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ciclo11', password='x')
        self.otro = User.objects.create_user('ciclo11_otro', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.cliente.nombre = 'Ciclo 11'
        self.cliente.dias_disponibles = 5
        self.cliente.save(update_fields=['nombre', 'dias_disponibles'])
        self.lunes = date(2026, 8, 10)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=5,
            minimo_valido=3,
            vigente_desde=self.lunes,
            aprobado_por=self.user,
        )
        self.contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente,
            estrategia=self.estrategia,
            semana=self.lunes,
            objetivo_sesiones=5,
            minimo_valido=3,
        )
        self.rutina = Rutina.objects.create(nombre='Rutina ciclo 11')

    def _entreno(self, offset, *, volumen='1000.00', duracion=60, energia=7):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=self.lunes + timedelta(days=offset),
            fecha_ejecucion=self.lunes + timedelta(days=offset),
            volumen_total_kg=Decimal(volumen),
            duracion_minutos=duracion,
            energia_pre_sesion=energia,
        )
        # El save legacy recalcula volumen desde ejercicios; aquí necesitamos
        # representar una métrica ya consolidada por la fuente de la sesión.
        EntrenoRealizado.objects.filter(pk=entreno.pk).update(volumen_total_kg=Decimal(volumen))
        entreno.refresh_from_db()
        return entreno

    def _materializar(self, completadas, *, reubicadas=0, enlazar=True):
        sesiones = []
        for offset in range(5):
            completa = offset < completadas
            entreno = self._entreno(offset) if completa and enlazar else None
            fecha_realizada = self.lunes + timedelta(days=offset)
            if completa and offset < reubicadas:
                fecha_realizada += timedelta(days=1)
            sesiones.append(SesionProgramada.objects.create(
                cliente=self.cliente,
                contrato_semanal=self.contrato,
                semana_prescrita=self.lunes,
                fecha_prevista=self.lunes + timedelta(days=offset),
                fecha_realizada=fecha_realizada if completa else None,
                estado=(SesionProgramada.ESTADO_COMPLETADA if completa else SesionProgramada.ESTADO_PENDIENTE),
                entreno_realizado=entreno,
                nombre_sesion=f'Día {offset + 1}',
                dia_numero=offset + 1,
            ))
        return sesiones

    def _evaluar(self, **kwargs):
        return evaluar_y_persistir_contrato_semanal_gym(
            self.contrato,
            hoy=date(2026, 8, 17),
            **kwargs,
        )

    def test_clasifica_cinco_tres_y_dos_sin_generar_deuda(self):
        for completadas, esperado in ((5, 'objetivo'), (3, 'minima_valida'), (2, 'insuficiente')):
            self.contrato.sesiones.all().delete()
            EntrenoRealizado.objects.all().delete()
            self._materializar(completadas)
            evaluacion = self._evaluar(force=True)
            self.assertEqual(evaluacion.estado_cumplimiento, esperado)
            self.assertEqual(evaluacion.sesiones_completadas, completadas)
            self.assertNotIn('deuda', evaluacion.evidencia_snapshot)

    def test_estados_permanecen_separados_y_reubicacion_se_cuenta_una_vez(self):
        sesiones = self._materializar(3, reubicadas=1)
        sesiones[3].estado = SesionProgramada.ESTADO_SALTADA_USUARIO
        sesiones[3].save(update_fields=['estado'])
        sesiones[4].estado = SesionProgramada.ESTADO_CANCELADA_LESION
        sesiones[4].save(update_fields=['estado'])

        evaluacion = self._evaluar()

        self.assertEqual(evaluacion.sesiones_completadas, 3)
        self.assertEqual(evaluacion.sesiones_reubicadas, 1)
        self.assertEqual(evaluacion.evidencia_snapshot['conteos_estado'], {
            'cancelada_lesion': 1,
            'completada': 3,
            'omitida_sistema': 0,
            'pendiente': 0,
            'saltada_usuario': 1,
        })
        self.assertEqual(len(evaluacion.evidencia_snapshot['sesiones']), 5)

    def test_pospuesta_completada_en_fecha_efectiva_es_reubicada(self):
        sesiones = self._materializar(5)
        sesion = sesiones[-1]
        sesion.pospuesta_hasta = sesion.fecha_prevista + timedelta(days=1)
        sesion.fecha_realizada = sesion.pospuesta_hasta
        sesion.save(update_fields=['pospuesta_hasta', 'fecha_realizada'])

        evaluacion = self._evaluar()
        evidencia = next(
            item for item in evaluacion.evidencia_snapshot['sesiones']
            if item['id'] == sesion.id
        )

        self.assertEqual(evaluacion.estado_cumplimiento, 'objetivo')
        self.assertEqual(evaluacion.sesiones_completadas, 5)
        self.assertEqual(evaluacion.sesiones_reubicadas, 1)
        self.assertEqual(evidencia['fecha_prevista'], '2026-08-14')
        self.assertEqual(evidencia['pospuesta_hasta'], '2026-08-15')
        self.assertEqual(evidencia['fecha_realizada'], '2026-08-15')

    def test_metricas_proceden_solo_de_entrenos_enlazados_y_exponen_cobertura(self):
        sesiones = self._materializar(2)
        sesiones[1].entreno_realizado = None
        sesiones[1].save(update_fields=['entreno_realizado'])
        # Mismo día y cliente, pero sin enlace causal: debe ser invisible.
        self._entreno(1, volumen='9000.00', duracion=200, energia=1)

        evaluacion = self._evaluar()
        metricas = evaluacion.evidencia_snapshot['metricas']

        self.assertEqual(metricas['volumen_total_kg'], '1000.00')
        self.assertEqual(metricas['duracion_total_minutos'], 60)
        self.assertEqual(metricas['energia_pre_sesion_media'], 7.0)
        self.assertIsNone(metricas['rpe_medio'])
        self.assertEqual(metricas['cobertura']['entrenos_enlazados'], {'disponibles': 1, 'total': 2})
        self.assertEqual(metricas['cobertura']['rpe'], {'disponibles': 0, 'total': 1})

    def test_misma_evidencia_es_idempotente(self):
        self._materializar(3)
        primera = self._evaluar()
        snapshot = primera.evidencia_snapshot
        segunda = self._evaluar()

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(segunda.evidencia_snapshot, snapshot)
        self.assertEqual(EvaluacionSemanalGym.objects.count(), 1)

    def test_rechaza_semana_abierta_y_materializacion_incompleta(self):
        self._materializar(3)
        with self.assertRaises(SemanaAbierta):
            evaluar_y_persistir_contrato_semanal_gym(self.contrato, hoy=date(2026, 8, 16))

        self.contrato.sesiones.last().delete()
        with self.assertRaises(ContratoNoMaterializado):
            self._evaluar(force=True)

    def test_evaluacion_revisada_no_se_sobrescribe_si_cambia_la_evidencia(self):
        sesiones = self._materializar(3)
        evaluacion = self._evaluar()
        responder_evaluacion_semanal_gym(evaluacion, actor=self.user, aceptar=True)
        sesiones[3].estado = SesionProgramada.ESTADO_COMPLETADA
        sesiones[3].fecha_realizada = sesiones[3].fecha_prevista
        sesiones[3].save(update_fields=['estado', 'fecha_realizada'])

        with self.assertRaises(EvaluacionSemanalRevisada):
            self._evaluar()
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado_revision, EvaluacionSemanalGym.ESTADO_ACEPTADA)
        self.assertEqual(evaluacion.sesiones_completadas, 3)

    def test_respuesta_es_atomica_idempotente_y_no_muta_el_plan(self):
        self._materializar(3)
        evaluacion = self._evaluar()
        estrategia_antes = (self.estrategia.estado, self.estrategia.objetivo_sesiones, self.estrategia.minimo_valido)
        dias_antes = self.cliente.dias_disponibles

        primera = responder_evaluacion_semanal_gym(evaluacion, actor=self.user, aceptar=False)
        segunda = responder_evaluacion_semanal_gym(primera, actor=self.user, aceptar=False)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(segunda.estado_revision, EvaluacionSemanalGym.ESTADO_RECHAZADA)
        self.assertEqual(segunda.respondida_por, self.user)
        self.assertIsNotNone(segunda.respondida_en)
        self.estrategia.refresh_from_db()
        self.cliente.refresh_from_db()
        self.assertEqual(
            (self.estrategia.estado, self.estrategia.objetivo_sesiones, self.estrategia.minimo_valido),
            estrategia_antes,
        )
        self.assertEqual(self.cliente.dias_disponibles, dias_antes)

    def test_solo_el_usuario_del_cliente_puede_responder(self):
        self._materializar(3)
        evaluacion = self._evaluar()

        with self.assertRaises(ActorNoAutorizado):
            responder_evaluacion_semanal_gym(evaluacion, actor=self.otro, aceptar=True)
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado_revision, EvaluacionSemanalGym.ESTADO_PENDIENTE)
