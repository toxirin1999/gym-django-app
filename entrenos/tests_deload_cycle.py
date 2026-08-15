from datetime import timedelta
from unittest.mock import patch
import inspect

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import CicloDeload
from entrenos.services.deload_cycle_service import (
    aplicar_overlay_gym,
    aplicar_overlay_hyrox,
    cerrar_ciclos_vencidos,
    obtener_ciclo_activo,
    abrir_ciclo_deload,
)


class CicloDeloadServiceTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('deload-user')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user,
            defaults={'nombre': 'Deload', 'email': 'd@example.com', 'telefono': '1'},
        )
        self.hoy = timezone.localdate()

    def test_apertura_es_idempotente_y_gym_define_ventana_de_7_dias(self):
        primero, creado = abrir_ciclo_deload(
            self.cliente, CicloDeload.CAUSA_FATIGA_GYM,
            metrica='rpe_medio', umbral=8.5, valor=9.1,
            evidencia={'sesiones': 5}, hoy=self.hoy,
        )
        segundo, creado_dos = abrir_ciclo_deload(
            self.cliente, CicloDeload.CAUSA_FATIGA_GYM,
            metrica='rpe_medio', umbral=8.5, valor=9.1, hoy=self.hoy,
        )
        self.assertTrue(creado)
        self.assertFalse(creado_dos)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(primero.fecha_fin_prevista, self.hoy + timedelta(days=6))
        self.assertEqual(CicloDeload.objects.filter(cliente=self.cliente, estado='activo').count(), 1)

    def test_hyrox_define_ventana_de_9_dias_y_guarda_snapshot_versionado(self):
        ciclo, _ = abrir_ciclo_deload(
            self.cliente, CicloDeload.CAUSA_TSB_HYROX,
            metrica='tsb', umbral=-25, valor=-31, hoy=self.hoy,
        )
        self.assertEqual(ciclo.fecha_fin_prevista, self.hoy + timedelta(days=8))
        self.assertEqual(ciclo.politica_snapshot['version'], 1)
        self.assertEqual(ciclo.politica_snapshot['hyrox']['factor'], 0.55)

    def test_overlay_gym_resta_una_serie_minimo_dos_y_limita_rpe_sin_mutar_input(self):
        abrir_ciclo_deload(self.cliente, CicloDeload.CAUSA_FATIGA_GYM, hoy=self.hoy)
        original = [{'nombre': 'Sentadilla', 'series': 4, 'rpe_objetivo': 9},
                    {'nombre': 'Remo', 'series': 2, 'rpe_objetivo': 6}]
        una = aplicar_overlay_gym(self.cliente, original, self.hoy)
        dos = aplicar_overlay_gym(self.cliente, una, self.hoy)
        self.assertEqual(original[0]['series'], 4)
        self.assertEqual(una[0]['series'], 3)
        self.assertEqual(una[0]['rpe_objetivo'], 7)
        self.assertEqual(una[1]['series'], 2)
        self.assertEqual(dos, una)

    def test_overlay_hyrox_aplica_factor_una_vez_y_no_muta_metricas(self):
        abrir_ciclo_deload(self.cliente, CicloDeload.CAUSA_TSB_HYROX, hoy=self.hoy)
        metricas = {'distancia_m': 1000, 'series': [{'reps': 10, 'peso_kg': 20}]}
        una = aplicar_overlay_hyrox(self.cliente, metricas, self.hoy)
        dos = aplicar_overlay_hyrox(self.cliente, una, self.hoy)
        self.assertEqual(metricas['distancia_m'], 1000)
        self.assertEqual(una['distancia_m'], 550)
        self.assertEqual(una['series'][0], {'reps': 6, 'peso_kg': 20})
        self.assertEqual(dos, una)

    def test_cierre_por_expiracion_clasifica_resultado_y_revierte_overlay(self):
        ciclo, _ = abrir_ciclo_deload(
            self.cliente, CicloDeload.CAUSA_TSB_HYROX,
            metrica='tsb', umbral=-25, valor=-31, hoy=self.hoy - timedelta(days=10),
        )
        with patch('entrenos.services.deload_cycle_service._evaluar_resultado', return_value=('favorable', {'tsb': -8})):
            cerrados = cerrar_ciclos_vencidos(self.hoy)
        ciclo.refresh_from_db()
        self.assertEqual(cerrados, [ciclo])
        self.assertEqual(ciclo.estado, 'cerrado')
        self.assertEqual(ciclo.resultado, 'favorable')
        self.assertIsNone(obtener_ciclo_activo(self.cliente, self.hoy))
        self.assertEqual(aplicar_overlay_gym(self.cliente, [{'series': 4}], self.hoy), [{'series': 4}])

    def test_detector_hyrox_abre_ciclo_sin_mutar_sesion_futura(self):
        from hyrox.models import HyroxObjective, HyroxSession
        from hyrox.training_engine import DeloadAutoTrigger, HyroxLoadManager
        objetivo = HyroxObjective.objects.create(
            cliente=self.cliente, fecha_evento=self.hoy + timedelta(days=90)
        )
        completada = HyroxSession.objects.create(
            objective=objetivo, fecha=self.hoy, estado='completado', titulo='Carga'
        )
        futura = HyroxSession.objects.create(
            objective=objetivo, fecha=self.hoy + timedelta(days=2), titulo='Taper intacto'
        )
        with patch.object(HyroxLoadManager, 'calcular_ctl_atl_tsb', return_value={'tsb': -31}):
            mensajes = DeloadAutoTrigger.check_and_apply(completada)
        futura.refresh_from_db()
        self.assertTrue(mensajes)
        self.assertEqual(futura.titulo, 'Taper intacto')
        self.assertEqual(obtener_ciclo_activo(self.cliente, self.hoy).causa, 'tsb_hyrox')

    def test_fachada_cierra_ciclo_vencido_al_consultarlo(self):
        ciclo, _ = abrir_ciclo_deload(
            self.cliente, CicloDeload.CAUSA_FATIGA_GYM,
            hoy=self.hoy - timedelta(days=8),
        )
        self.assertIsNone(obtener_ciclo_activo(self.cliente, self.hoy))
        ciclo.refresh_from_db()
        self.assertEqual(ciclo.estado, CicloDeload.ESTADO_CERRADO)
        self.assertEqual(ciclo.resultado, 'insuficiente')

    def test_vista_activa_no_conserva_segunda_autoridad_ni_escape_forzar_plan(self):
        from entrenos import views
        fuente = inspect.getsource(views.vista_entrenamiento_activo)
        self.assertNotIn("request.GET.get('forzar_plan')", fuente)
        self.assertNotIn("GymDecisionLog.objects.create", fuente)

    def test_plan_y_consumidor_aplican_una_vez_y_crean_un_solo_log(self):
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        abrir_ciclo_deload(self.cliente, CicloDeload.CAUSA_FATIGA_GYM, hoy=self.hoy)
        plan, _ = aplicar_plan_dinamico(
            self.cliente, [{'nombre': 'Sentadilla', 'series': 4, 'rpe_objetivo': 9}], self.hoy
        )
        consumido = aplicar_overlay_gym(self.cliente, plan, self.hoy)
        self.assertEqual(consumido[0]['series'], 3)
        self.assertEqual(
            self.cliente.gym_decision_logs.filter(accion='deload').count(), 1
        )

    def test_helper_hyrox_obtiene_ciclo_y_respeta_lesion_y_descanso(self):
        from hyrox.views import _crear_hyrox_decision
        abrir_ciclo_deload(self.cliente, CicloDeload.CAUSA_TSB_HYROX, hoy=self.hoy)
        base = {'current_score': 80, 'resumen_semanal': {'tsb': 0, 'acwr': 1}}
        self.assertEqual(_crear_hyrox_decision(**base, cliente=self.cliente)['causa'], 'deload_seguridad')
        self.assertEqual(
            _crear_hyrox_decision(**base, cliente=self.cliente, es_descanso_plan=True)['causa'],
            'descanso_plan',
        )
        lesion = type('Lesion', (), {
            'tags_restringidos': [], 'zona_afectada': 'rodilla'
        })()
        self.assertEqual(
            _crear_hyrox_decision(**base, cliente=self.cliente, lesion_activa=lesion)['causa'],
            'lesion',
        )
