from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch

from clientes.models import Cliente
from entrenos.models import (
    ContratoSemanalGym, EjercicioRealizado, EntrenoRealizado, SesionEntrenamiento,
    EstrategiaSemanalGym, IntervencionPlan, SesionProgramada, SugerenciaPlan,
)
from rutinas.models import Rutina


def snapshot_legacy():
    return {
        'version': 1, 'patron': 'esenciales_frecuentes', 'fecha_referencia': '2026-07-01',
        'vigente': True,
        'evidencia': {'ventana_semanas': 3, 'semanas_observadas': [
            {'completadas': 2, 'esenciales': 1, 'cumple_umbral': True},
            {'completadas': 2, 'esenciales': 1, 'cumple_umbral': True}],
            'semanas_que_cumplen': 2},
        'cambio': {'codigo': 'freeze_load_increases', 'tipo_intervencion': 'no_subir_cargas', 'duracion_dias': 7},
        'unchanged': ['series'], 'evaluacion': {'criterio': 'comparar'},
    }


class EvaluacionEsencialV1Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ciclo4', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Ciclo 4')
        self.inicio = date(2026, 7, 8)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=date(2026, 1, 1), estado='aprobada',
        )

    def sugerencia(self, snapshot=None):
        return SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='esenciales_frecuentes', texto='x',
            contrato_snapshot=snapshot if snapshot is not None else snapshot_legacy(),
        )

    def contrato(self, lunes):
        return ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia, semana=lunes,
            objetivo_sesiones=5, minimo_valido=3,
        )

    def programada(self, fecha, estado='pendiente', entreno=None, contrato=None, pospuesta=None):
        return SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=contrato, semana_prescrita=contrato.semana if contrato else None,
            fecha_prevista=fecha, pospuesta_hasta=pospuesta, estado=estado,
            fecha_realizada=entreno.fecha_ejecucion if entreno else None, entreno_realizado=entreno,
        )

    def entreno(self, fecha_plan, fecha_real, esencial=False, rpes=(), energia=None, principales=2, completados=2):
        e = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha_plan, fecha_ejecucion=fecha_real,
            modo_reducido=esencial, energia_pre_sesion=energia,
            principales_planificados=principales, numero_ejercicios=max(completados, 1), volumen_total_kg=100,
        )
        for i in range(completados):
            EjercicioRealizado.objects.create(
                entreno=e, nombre_ejercicio=f'P{i}', es_bloque_principal=True,
                completado=True, rpe=(rpes[i] if i < len(rpes) else None),
            )
        return e

    @patch('entrenos.services.contrato_sugerencia_service.revalidar_sugerencia')
    def test_aceptar_congela_baseline_21_dias_fechas_y_no_promocion(self, revalidar):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        sug = self.sugerencia()
        revalidar.return_value = sug.contrato_snapshot
        aceptada = aceptar_sugerencia(sug, self.inicio)
        snap = aceptada.contrato_snapshot
        self.assertEqual(snap['evaluacion_v1']['baseline']['ventana'], {
            'desde': '2026-06-17', 'hasta': '2026-07-07'})
        self.assertEqual(snap['evaluacion_v1']['intervencion']['ventana'], {
            'desde': '2026-07-08', 'hasta': '2026-07-14'})
        self.assertEqual(snap['evaluacion_v1']['decision']['no_promocion'], True)
        self.assertEqual(snap['evaluacion_v1']['decision']['estrategia_modificada'], False)

    def test_snapshot_antiguo_sigue_validando(self):
        from entrenos.services.contrato_sugerencia_service import validar_contrato_snapshot
        self.assertTrue(validar_contrato_snapshot(snapshot_legacy()))

    def test_medicion_usa_fecha_efectiva_limites_exclusiones_y_reubicada_una_vez(self):
        from entrenos.services.ciclo_intervencion_esenciales_service import medir_ventana
        contrato = self.contrato(self.inicio - timedelta(days=2))
        a = self.entreno(self.inicio - timedelta(days=2), self.inicio, True, (5, 9), 4)
        self.programada(self.inicio - timedelta(days=2), 'completada', a, contrato, self.inicio)
        b = self.entreno(self.inicio + timedelta(days=6), self.inicio + timedelta(days=6), False, (7,), 8, 2, 1)
        self.programada(self.inicio + timedelta(days=6), 'completada', b, contrato)
        self.programada(self.inicio + timedelta(days=2), 'omitida_sistema', contrato=contrato)
        self.programada(self.inicio + timedelta(days=3), 'cancelada_lesion', contrato=contrato)
        m = medir_ventana(self.cliente, self.inicio, self.inicio + timedelta(days=6))
        self.assertEqual((m['sesiones_elegibles'], m['sesiones_completadas'], m['sesiones_esenciales']), (2, 2, 1))
        self.assertEqual(m['principales'], {'planificados': 4, 'completados': 3, 'porcentaje': 75})
        SesionEntrenamiento.objects.update_or_create(entreno=a, defaults={'duracion_minutos': 45, 'rpe_medio': 5})
        SesionEntrenamiento.objects.update_or_create(entreno=b, defaults={'duracion_minutos': 45, 'rpe_medio': 9})
        m = medir_ventana(self.cliente, self.inicio, self.inicio + timedelta(days=6))
        self.assertEqual(m['rpe'], {'mediana': 7.0, 'n': 2})
        self.assertEqual(m['energia_pre'], {'mediana': 6.0, 'n': 2})
        self.assertEqual(m['continuidad']['objetivo_sesiones'], 5)
        self.assertEqual(m['continuidad']['minimo_valido'], 3)
        self.assertEqual(m['continuidad']['estado'], 'no_evaluable')

    def test_sin_sesiones_porcentaje_esenciales_none_y_continuidad_no_evaluable(self):
        from entrenos.services.ciclo_intervencion_esenciales_service import medir_ventana
        m = medir_ventana(self.cliente, self.inicio, self.inicio + timedelta(days=6))
        self.assertIsNone(m['porcentaje_esenciales'])
        self.assertEqual(m['continuidad']['estado'], 'no_evaluable')

    def test_continuidad_categorica_y_atribucion_contractual(self):
        from entrenos.services.ciclo_intervencion_esenciales_service import _atribucion, medir_ventana
        contrato = self.contrato(self.inicio - timedelta(days=2))
        for i in range(5):
            e = self.entreno(self.inicio + timedelta(days=i), self.inicio + timedelta(days=i)) if i < 3 else None
            self.programada(
                self.inicio + timedelta(days=i), 'completada' if e else 'pendiente', e, contrato,
            )
        m = medir_ventana(self.cliente, self.inicio, self.inicio + timedelta(days=6))
        self.assertEqual(m['continuidad']['estado'], 'minima_valida')
        baseline = {'sesiones_completadas': 3, 'porcentaje_esenciales': 80,
                    'principales': {'porcentaje': 50}}
        actual = {'sesiones_completadas': 3, 'porcentaje_esenciales': 20,
                  'principales': {'porcentaje': 75}}
        self.assertEqual(_atribucion(baseline, actual), 'compatible_con_freeze')

    def test_denominador_principales_ausente_da_null_y_evaluacion_es_idempotente(self):
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        sug = self.sugerencia()
        iv = IntervencionPlan.objects.create(
            cliente=self.cliente, sugerencia=sug, tipo='no_subir_cargas', origen_patron='esenciales_frecuentes',
            fecha_inicio=self.inicio, fecha_fin=self.inicio + timedelta(days=6), estado='activa')
        e = self.entreno(self.inicio, self.inicio, True, (), None, 0, 0)
        self.programada(self.inicio, 'completada', e)
        a = evaluar_intervencion(iv, self.inicio + timedelta(days=7), aplicar=True)
        b = evaluar_intervencion(iv, self.inicio + timedelta(days=8), aplicar=True)
        self.assertEqual(a, b)
        self.assertIsNone(a['evaluacion_v1']['medicion']['principales']['porcentaje'])
        self.assertEqual(a['resultado'], 'datos_insuficientes')
        self.assertEqual(a['evaluacion_v1']['atribucion'], 'no_evaluable')
        self.assertEqual(a['evaluacion_v1']['abandono_evitado'], 'no_demostrable')
        self.assertEqual(a['evaluacion_v1']['decision']['reversion'], 'automatica')
        self.assertTrue(a['evaluacion_v1']['decision']['no_promocion'])

    def test_prompt_joi_expone_cobertura_sin_causalidad_ni_promocion(self):
        from joi.services import _prompt_resultado_intervencion
        prompt = _prompt_resultado_intervencion({}, {
            'resultado': 'senal_reducida', 'sesiones_completadas': 3, 'sesiones_esenciales': 1,
            'evaluacion_v1': {'medicion': {
                'rpe': {'mediana': 7.0, 'n': 2}, 'energia_pre': {'mediana': 6.0, 'n': 1},
                'principales': {'planificados': 4, 'completados': 3},
            }},
        })
        self.assertIn('RPE mediana 7.0 (n=2)', prompt)
        self.assertIn('sin atribuir causalidad', prompt)
        self.assertIn('ni promociones una preferencia o estrategia', prompt)

    def test_centro_muestra_sin_clasificacion_si_no_hay_denominador(self):
        snap = snapshot_legacy()
        snap['evaluacion'].update({'resultado': 'datos_insuficientes', 'sesiones_completadas': 1,
                                   'sesiones_esenciales': 1})
        snap['evaluacion_v1'] = {'medicion': {
            'sesiones_completadas': 1, 'sesiones_elegibles': 1,
            'principales': {'planificados': 0, 'completados': 0, 'porcentaje': None},
            'rpe': {'mediana': None, 'n': 0}, 'energia_pre': {'mediana': None, 'n': 0},
        }}
        sug = self.sugerencia(snap)
        sug.estado = SugerenciaPlan.ESTADO_ACEPTADA
        sug.save(update_fields=['estado'])
        IntervencionPlan.objects.create(
            cliente=self.cliente, sugerencia=sug, tipo='no_subir_cargas',
            origen_patron='esenciales_frecuentes', fecha_inicio=self.inicio,
            fecha_fin=self.inicio + timedelta(days=6), estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        web = Client(); web.login(username='ciclo4', password='x')
        response = web.get(reverse('clientes:plan_decisiones'))
        self.assertContains(response, 'principales sin clasificación')
        self.assertNotContains(response, 'principales 0/0')
