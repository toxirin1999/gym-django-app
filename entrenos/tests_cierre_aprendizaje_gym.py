from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from clientes.models import Cliente
from entrenos.models import ActividadRealizada, EntrenoRealizado, EjercicioRealizado, GymDecisionLog
from entrenos.services.decision_log_service import cerrar_aprendizaje_gym
from rutinas.models import Rutina


class CierreAprendizajeGymTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='cierre_causal')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'Causal'})
        self.rutina = Rutina.objects.create(nombre='Causal')

    def sesion(self, fecha, nombre='Press Banca', rpe=7):
        entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=nombre, peso_kg=50,
            series=3, repeticiones=10, rpe=rpe, completado=True,
        )
        return entreno

    def test_reintentos_y_triple_save_generan_una_decision(self):
        entreno = self.sesion(date(2026, 8, 1))
        entreno.save(); entreno.save(); entreno.save()
        cerrar_aprendizaje_gym(entreno)
        cerrar_aprendizaje_gym(entreno)
        self.assertEqual(GymDecisionLog.objects.filter(entreno_origen=entreno).count(), 1)
        self.assertIsNone(GymDecisionLog.objects.get(entreno_origen=entreno).resultado)
        self.assertEqual(ActividadRealizada.objects.filter(entreno_gym=entreno).count(), 1)


class GuardarEntrenamientoActivoCierreE2ETests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cierre_e2e', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Cierre E2E', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Push Causal E2E')
        self.client.force_login(self.user)

    def sesion(self, fecha, nombre='Press Banca', rpe=7):
        entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=nombre, peso_kg=50,
            series=3, repeticiones=10, rpe=rpe, completado=True,
        )
        return entreno

    def _payload_reducido(self):
        data = {
            'fecha': '2026-08-09',
            'rutina_nombre': self.rutina.nombre,
            'sesion_programada_id': '',
            'modo_reducido': '1',
            'duracion_minutos_real': '40',
            'series_completadas': '', 'series_totales': '',
            'ejercicios_completados': '', 'ejercicios_totales': '',
            'volumen_total_sesion': '', 'rpe_medio_sesion': '',
            'rpe_global_sesion': '', 'energia_pre_sesion': '',
            'ej1_nombre': 'Press banca',
            'ej1_tipo_progresion': 'peso_reps',
            'ej1_es_principal': '1',
            'ej1_es_tope_maquina': 'false',
            'ej1_molestia_reportada': 'false',
        }
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '60'
            data[f'ej1_reps_{i}'] = '8'
            data[f'ej1_rpe_{i}'] = '7'
        return data

    def test_post_reducido_evalua_previa_y_deja_una_nueva_pendiente(self):
        previa = GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio='Press banca',
            ejercicio_normalizado='press banca',
            accion='mantener',
            motivo='Decisión pendiente anterior',
            resultado=None,
        )
        url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.pk})

        # El wrapper prueba que el cierre efectivo vive una sola vez en la vista;
        # los post_save intermedios quedan diferidos.
        with patch(
            'entrenos.services.decision_log_service.cerrar_aprendizaje_gym',
            wraps=cerrar_aprendizaje_gym,
        ) as cierre:
            response = self.client.post(url, self._payload_reducido())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=self.cliente).count(), 1)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        self.assertTrue(entreno.modo_reducido)
        self.assertEqual(ActividadRealizada.objects.filter(entreno_gym=entreno).count(), 1)
        previa.refresh_from_db()
        self.assertIsNotNone(previa.resultado)
        nuevas = GymDecisionLog.objects.filter(entreno_origen=entreno)
        self.assertEqual(nuevas.count(), 1)
        self.assertIsNone(nuevas.get().resultado)
        self.assertEqual(cierre.call_count, 1)

    def test_siguiente_sesion_evalua_anterior_y_genera_otra(self):
        anterior = self.sesion(date(2026, 8, 1))
        cerrar_aprendizaje_gym(anterior)
        actual = self.sesion(date(2026, 8, 4))
        cerrar_aprendizaje_gym(actual)
        self.assertIsNotNone(GymDecisionLog.objects.get(entreno_origen=anterior).resultado)
        self.assertIsNone(GymDecisionLog.objects.get(entreno_origen=actual).resultado)

    def test_dos_entrenos_del_mismo_dia_permiten_dos_decisiones(self):
        a = self.sesion(date(2026, 8, 1))
        b = self.sesion(date(2026, 8, 1))
        cerrar_aprendizaje_gym(a); cerrar_aprendizaje_gym(b)
        self.assertEqual(GymDecisionLog.objects.count(), 2)

    def test_nombre_casefold_espacios_no_duplica_en_mismo_origen(self):
        entreno = self.sesion(date(2026, 8, 1), '  PRESS   BANCA ')
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='press banca', peso_kg=50,
            series=3, repeticiones=10, rpe=7, completado=True,
        )
        cerrar_aprendizaje_gym(entreno)
        self.assertEqual(GymDecisionLog.objects.filter(entreno_origen=entreno).count(), 1)
        self.assertEqual(GymDecisionLog.objects.get(entreno_origen=entreno).ejercicio_normalizado, 'press banca')

    def test_modo_reducido_no_autoevalua_decision_nueva(self):
        entreno = self.sesion(date(2026, 8, 1))
        entreno.modo_reducido = True
        entreno.save(update_fields=['modo_reducido'])
        cerrar_aprendizaje_gym(entreno)
        cerrar_aprendizaje_gym(entreno)
        self.assertIsNone(GymDecisionLog.objects.get(entreno_origen=entreno).resultado)
