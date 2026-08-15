from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
import json

from clientes.models import Cliente
from entrenos.models import (
    EntrenoRealizado, EjercicioRealizado, GymDecisionLog,
    IntervencionMolestiaGym,
)
from entrenos.services.decision_log_service import generar_decisiones_para_entreno, evaluar_decisiones_para_entreno
from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
from rutinas.models import Rutina


class Ciclo12MolestiaRecienteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ciclo12')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'Ciclo 12'})
        self.rutina = Rutina.objects.create(nombre='Ciclo 12')

    def sesion(self, fecha, *, molestia=False, severidad=None, zona='', peso=80, reps=8, rpe=7, fallo=False):
        entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press banca', peso_kg=peso,
            repeticiones=reps, rpe=rpe, fallo_muscular=fallo, completado=True,
            molestia_reportada=molestia, molestia_severidad=severidad, molestia_zona=zona,
        )
        return entreno

    def test_genera_decision_causal_idempotente_para_severidad_uno(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1, zona='hombro')
        generar_decisiones_para_entreno(origen)
        generar_decisiones_para_entreno(origen)
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(GymDecisionLog.objects.count(), 1)
        self.assertEqual((log.accion, log.motivo_codigo), ('mantener', 'molestia_reciente'))
        self.assertEqual(log.molestia_zona_snapshot, 'hombro')
        self.assertEqual((log.peso_anterior, log.reps_anteriores, log.rpe_anterior), (80, 8, 7))

    def test_severidad_dos_no_abre_ciclo_local(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=2)
        generar_decisiones_para_entreno(origen)
        self.assertFalse(GymDecisionLog.objects.filter(motivo_codigo='molestia_reciente').exists())

    def test_fallo_protector_gana_a_molestia(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1, fallo=True, rpe=10)
        generar_decisiones_para_entreno(origen)
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(log.accion, 'bajar_peso')
        self.assertNotEqual(log.motivo_codigo, 'molestia_reciente')

    def test_overlay_acota_solo_el_mismo_ejercicio(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1, zona='hombro')
        generar_decisiones_para_entreno(origen)
        plan = [
            {'nombre': 'Press banca', 'grupo_muscular': 'pecho', 'peso_kg': 90, 'repeticiones': '10-12'},
            {'nombre': 'Remo', 'grupo_muscular': 'espalda', 'peso_kg': 100, 'repeticiones': '10'},
        ]
        mod, cambios = aplicar_plan_dinamico(self.cliente, plan, hoy=date(2026, 8, 10))
        self.assertEqual(mod[0]['peso_kg'], 80)
        self.assertEqual(mod[0]['repeticiones'], '8')
        self.assertEqual(mod[1], plan[1])
        self.assertTrue(any(c['tipo'] == 'molestia_reciente' for c in cambios))
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(log.estado_aplicacion, 'aplicada')

    def test_caducidad_cierra_neutra_sin_overlay(self):
        origen = self.sesion(date(2026, 7, 1), molestia=True, severidad=1)
        generar_decisiones_para_entreno(origen)
        mod, _ = aplicar_plan_dinamico(self.cliente, [{'nombre': 'Press banca', 'grupo_muscular': 'pecho', 'peso_kg': 90, 'repeticiones': '10'}], hoy=date(2026, 7, 20))
        self.assertEqual(mod[0]['peso_kg'], 90)
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(log.resultado, 'neutra')
        self.assertIn('caduc', log.notas_resultado.lower())

    def test_primera_reexposicion_valida_y_cierra(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1, zona='hombro')
        generar_decisiones_para_entreno(origen)
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        log.estado_aplicacion = 'aplicada'; log.save(update_fields=['estado_aplicacion'])
        siguiente = self.sesion(date(2026, 8, 8), peso=80, reps=8, rpe=8)
        evaluar_decisiones_para_entreno(siguiente)
        log.refresh_from_db()
        self.assertEqual(log.resultado, 'validada')

    def test_no_evalua_hasta_que_el_overlay_fue_aplicado(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1)
        generar_decisiones_para_entreno(origen)
        siguiente = self.sesion(date(2026, 8, 8), rpe=7)
        evaluar_decisiones_para_entreno(siguiente)
        self.assertIsNone(GymDecisionLog.objects.get(entreno_origen=origen).resultado)

    def test_reexposicion_sin_rpe_es_neutra(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1)
        generar_decisiones_para_entreno(origen)
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        log.estado_aplicacion = 'aplicada'; log.save(update_fields=['estado_aplicacion'])
        siguiente = self.sesion(date(2026, 8, 8), rpe=None)
        evaluar_decisiones_para_entreno(siguiente)
        log.refresh_from_db()
        self.assertEqual(log.resultado, 'neutra')

    def test_reexposicion_con_misma_zona_falla(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1, zona='hombro')
        generar_decisiones_para_entreno(origen)
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        log.estado_aplicacion = 'aplicada'; log.save(update_fields=['estado_aplicacion'])
        siguiente = self.sesion(date(2026, 8, 8), molestia=True, severidad=1, zona='hombro')
        evaluar_decisiones_para_entreno(siguiente)
        log.refresh_from_db()
        self.assertEqual(log.resultado, 'fallida')

    def test_ventana_usa_fechas_reales_en_sesiones_reubicadas(self):
        origen = self.sesion(date(2026, 8, 1), molestia=True, severidad=1, zona='hombro')
        origen.fecha_ejecucion = date(2026, 8, 5)
        origen.save(update_fields=['fecha_ejecucion'])
        generar_decisiones_para_entreno(origen)
        log = GymDecisionLog.objects.get(entreno_origen=origen)
        log.estado_aplicacion = 'aplicada'
        log.save(update_fields=['estado_aplicacion'])
        siguiente = self.sesion(date(2026, 8, 20), peso=80, reps=8, rpe=8)
        siguiente.fecha_ejecucion = date(2026, 8, 10)
        siguiente.save(update_fields=['fecha_ejecucion'])

        evaluar_decisiones_para_entreno(siguiente)

        log.refresh_from_db()
        self.assertEqual(log.resultado, 'validada')

    def test_tercera_molestia_promueve_sin_duplicar_la_decision_local(self):
        from entrenos.services.intervencion_molestia_gym_service import (
            procesar_molestias_recurrentes,
        )

        self.sesion(date(2026, 8, 1), molestia=True, severidad=1, zona='hombro')
        self.sesion(date(2026, 8, 5), molestia=True, severidad=1, zona='hombro')
        tercera = self.sesion(date(2026, 8, 9), molestia=True, severidad=1, zona='hombro')
        generar_decisiones_para_entreno(tercera)

        intervencion = procesar_molestias_recurrentes(tercera)[0]

        self.assertEqual(IntervencionMolestiaGym.objects.count(), 1)
        self.assertEqual(GymDecisionLog.objects.filter(entreno_origen=tercera).count(), 1)
        self.assertEqual(intervencion.decision_origen.accion, 'cambiar_variante')

    def test_api_preview_severidad_tres_no_muta_lesion(self):
        from hyrox.models import UserInjury
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('entrenos:api_reportar_molestia', args=[self.cliente.pk]),
            data=json.dumps({'ejercicio_nombre': 'Press banca', 'zona': 'hombro',
                             'severidad': 3, 'solo_alternativas': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['lesion_creada'])
        self.assertFalse(UserInjury.objects.filter(cliente=self.cliente).exists())

    def test_api_no_permite_reportar_para_otro_cliente(self):
        otro_user = User.objects.create_user(username='otro_ciclo12')
        otro, _ = Cliente.objects.get_or_create(user=otro_user, defaults={'nombre': 'Otro'})
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('entrenos:api_reportar_molestia', args=[otro.pk]),
            data=json.dumps({'ejercicio_nombre': 'Press banca', 'zona': 'hombro', 'severidad': 1}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
