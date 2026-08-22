from datetime import date, timedelta
from io import StringIO
import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ContratoBloqueGym, ContratoSemanalGym, EvaluacionBloqueGym,
    EvaluacionSemanalGym, SesionProgramada,
)
from entrenos.services.contrato_bloque_gym_service import (
    activar_bloque_gym, proponer_bloque_gym,
)
from entrenos.services.estrategia_semanal_gym_service import aprobar_estrategia_semanal_gym


class CierreBloqueGymTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cierre_bloque', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Cierre bloque'},
        )
        self.inicio = date(2026, 8, 3)
        self.estrategia = aprobar_estrategia_semanal_gym(
            self.cliente, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=self.inicio, aprobado_por=self.user,
        )
        propuesta = proponer_bloque_gym(
            self.cliente, semana_inicio=self.inicio, semanas_previstas=2,
            objetivo_principal='hipertrofia', limites_snapshot={'sin_autoajustes': True},
        )
        self.bloque = activar_bloque_gym(
            propuesta, version_esperada=1, actor=self.user,
        )

    def _semana(self, indice, estado='objetivo', protegidas=0, revision='aceptada'):
        lunes = self.inicio + timedelta(weeks=indice - 1)
        contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia,
            bloque=self.bloque, indice_semana_bloque=indice, semana=lunes,
            objetivo_sesiones=5, minimo_valido=3,
        )
        completadas = {'objetivo': 5, 'minima_valida': 3, 'insuficiente': 2}[estado]
        for offset in range(5):
            if offset < completadas:
                sesion_estado = SesionProgramada.ESTADO_COMPLETADA
            elif offset < completadas + protegidas:
                sesion_estado = SesionProgramada.ESTADO_CANCELADA_LESION
            else:
                sesion_estado = SesionProgramada.ESTADO_SALTADA_USUARIO
            SesionProgramada.objects.create(
                cliente=self.cliente, contrato_semanal=contrato,
                semana_prescrita=lunes, fecha_prevista=lunes + timedelta(days=offset),
                estado=sesion_estado,
            )
        conteos = {codigo: 0 for codigo, _ in SesionProgramada.ESTADOS}
        conteos[SesionProgramada.ESTADO_COMPLETADA] = completadas
        conteos[SesionProgramada.ESTADO_CANCELADA_LESION] = protegidas
        conteos[SesionProgramada.ESTADO_SALTADA_USUARIO] = 5 - completadas - protegidas
        return EvaluacionSemanalGym.objects.create(
            contrato=contrato, estado_cumplimiento=estado,
            sesiones_completadas=completadas, sesiones_reubicadas=0,
            evidencia_snapshot={
                'version_calculo': 1, 'contrato_id': contrato.pk,
                'semana': lunes.isoformat(), 'objetivo_sesiones': 5,
                'minimo_valido': 3, 'estado_cumplimiento': estado,
                'conteos_estado': conteos, 'sesiones_completadas': completadas,
            },
            estado_revision=revision,
            respondida_por=self.user if revision != 'pendiente' else None,
        )

    def test_preview_bloque_abierto_clasifica_sin_persistir(self):
        from entrenos.services.contrato_bloque_gym_service import previsualizar_cierre_bloque_gym
        resultado = previsualizar_cierre_bloque_gym(self.bloque, hoy=date(2026, 8, 10))
        self.assertEqual(resultado['estado_resultado'], 'evidencia_insuficiente')
        self.assertFalse(resultado['cierre_persistible'])
        self.assertIn('bloque_abierto', resultado['impedimentos'])
        self.assertEqual(EvaluacionBloqueGym.objects.count(), 0)

    def test_persistencia_exige_fin_y_todas_las_evaluaciones_aceptadas(self):
        from entrenos.services.contrato_bloque_gym_service import (
            BloqueAbierto, EvidenciaBloqueIncompleta, cerrar_bloque_gym,
        )
        self._semana(1)
        with self.assertRaises(BloqueAbierto):
            cerrar_bloque_gym(self.bloque, hoy=date(2026, 8, 10))
        with self.assertRaises(EvidenciaBloqueIncompleta):
            cerrar_bloque_gym(self.bloque, hoy=date(2026, 8, 17))
        self._semana(2, revision='pendiente')
        with self.assertRaises(EvidenciaBloqueIncompleta):
            cerrar_bloque_gym(self.bloque, hoy=date(2026, 8, 17))

    def test_clasifica_objetivo_minimo_deriva_y_seguridad_sin_recalcular_entrenos(self):
        from entrenos.services.contrato_bloque_gym_service import previsualizar_cierre_bloque_gym
        self._semana(1, 'objetivo')
        self._semana(2, 'objetivo')
        self.assertEqual(
            previsualizar_cierre_bloque_gym(self.bloque, hoy=date(2026, 8, 17))['estado_resultado'],
            'objetivo_sostenido',
        )

        EvaluacionSemanalGym.objects.filter(contrato__indice_semana_bloque=2).update(
            estado_cumplimiento='minima_valida', sesiones_completadas=3,
            evidencia_snapshot={
                'estado_cumplimiento': 'minima_valida', 'sesiones_completadas': 3,
                'conteos_estado': {'completada': 3, 'cancelada_lesion': 0},
            },
        )
        self.assertEqual(
            previsualizar_cierre_bloque_gym(self.bloque, hoy=date(2026, 8, 17))['estado_resultado'],
            'minimo_sostenido',
        )
        EvaluacionSemanalGym.objects.filter(contrato__indice_semana_bloque=2).update(
            estado_cumplimiento='insuficiente', sesiones_completadas=2,
            evidencia_snapshot={
                'estado_cumplimiento': 'insuficiente', 'sesiones_completadas': 2,
                'conteos_estado': {'completada': 2, 'cancelada_lesion': 0},
            },
        )
        self.assertEqual(
            previsualizar_cierre_bloque_gym(self.bloque, hoy=date(2026, 8, 17))['estado_resultado'],
            'deriva_observada',
        )
        EvaluacionSemanalGym.objects.filter(contrato__indice_semana_bloque=2).update(
            evidencia_snapshot={
                'estado_cumplimiento': 'insuficiente', 'sesiones_completadas': 2,
                'conteos_estado': {'completada': 2, 'cancelada_lesion': 3},
            },
        )
        self.assertEqual(
            previsualizar_cierre_bloque_gym(self.bloque, hoy=date(2026, 8, 17))['estado_resultado'],
            'interrumpido_seguridad',
        )

    def test_cierre_append_only_idempotente_y_snapshot_inmutable(self):
        from entrenos.services.contrato_bloque_gym_service import cerrar_bloque_gym
        self._semana(1)
        self._semana(2, 'minima_valida')
        primero = cerrar_bloque_gym(self.bloque, hoy=date(2026, 8, 17))
        segundo = cerrar_bloque_gym(self.bloque, hoy=date(2026, 8, 17))
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(primero.version_calculo, 1)
        self.assertEqual(primero.estado_resultado, 'minimo_sostenido')
        primero.estado_resultado = 'deriva_observada'
        with self.assertRaises(ValidationError):
            primero.save()

    def test_revision_propietario_aceptar_finaliza_y_rechazar_no(self):
        from entrenos.services.contrato_bloque_gym_service import (
            ActorBloqueNoAutorizado, cerrar_bloque_gym,
            responder_evaluacion_bloque_gym,
        )
        self._semana(1)
        self._semana(2)
        evaluacion = cerrar_bloque_gym(self.bloque, hoy=date(2026, 8, 17))
        ajeno = User.objects.create_user(username='ajeno_cierre')
        with self.assertRaises(ActorBloqueNoAutorizado):
            responder_evaluacion_bloque_gym(evaluacion, actor=ajeno, aceptar=True)
        rechazada = responder_evaluacion_bloque_gym(evaluacion, actor=self.user, aceptar=False)
        self.bloque.refresh_from_db()
        self.assertEqual(rechazada.estado_revision, 'rechazada')
        self.assertEqual(self.bloque.estado, 'activo')

        # Una evidencia rechazada no se reescribe; una nueva versión puede
        # publicarse si cambia la evidencia semanal.
        EvaluacionSemanalGym.objects.filter(contrato__indice_semana_bloque=2).update(
            estado_cumplimiento='minima_valida', sesiones_completadas=3,
            evidencia_snapshot={
                'estado_cumplimiento': 'minima_valida', 'sesiones_completadas': 3,
                'conteos_estado': {'completada': 3, 'cancelada_lesion': 0},
            },
        )
        nueva = cerrar_bloque_gym(self.bloque, hoy=date(2026, 8, 17))
        self.assertEqual(nueva.version_calculo, 2)
        aceptada = responder_evaluacion_bloque_gym(nueva, actor=self.user, aceptar=True)
        repetida = responder_evaluacion_bloque_gym(nueva, actor=self.user, aceptar=True)
        self.assertEqual(aceptada.pk, repetida.pk)
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.estado, 'finalizado')
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.dias_disponibles, 5)

    def test_comandos_dry_run_no_escriben_y_apply_mas_respuesta(self):
        self._semana(1)
        self._semana(2)
        salida = StringIO()
        call_command(
            'cerrar_bloque_gym', bloque=self.bloque.pk,
            hoy='2026-08-17', stdout=salida,
        )
        lineas = [json.loads(linea) for linea in salida.getvalue().splitlines()]
        self.assertTrue(lineas[-1]['solo_lectura'])
        self.assertEqual(EvaluacionBloqueGym.objects.count(), 0)
        salida = StringIO()
        call_command(
            'cerrar_bloque_gym', bloque=self.bloque.pk,
            hoy='2026-08-17', apply=True, stdout=salida,
        )
        evaluacion = EvaluacionBloqueGym.objects.get()
        salida = StringIO()
        call_command(
            'responder_evaluacion_bloque_gym', evaluacion=evaluacion.pk,
            respuesta='aceptar', stdout=salida,
        )
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado_revision, 'pendiente')
        call_command(
            'responder_evaluacion_bloque_gym', evaluacion=evaluacion.pk,
            respuesta='aceptar', apply=True, stdout=StringIO(),
        )
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado_revision, 'aceptada')
