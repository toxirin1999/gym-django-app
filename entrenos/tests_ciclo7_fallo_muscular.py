from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymDecisionLog
from entrenos.services.decision_log_service import cerrar_aprendizaje_gym
from rutinas.models import EjercicioBase, Rutina


class CicloFalloMuscularBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ciclo_fallo', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Ciclo fallo'},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina fallo')
        EjercicioBase.objects.create(nombre='Press banca', tipo_progresion='peso_reps')

    def sesion(
        self, fecha, *, fallo=False, intencional=None, peso=80, reps=8, rpe=8,
    ):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Press banca',
            peso_kg=peso,
            series=3,
            repeticiones=reps,
            rpe=rpe,
            fallo_muscular=fallo,
            fallo_intencional=intencional,
            completado=True,
        )
        return entreno


class CicloFalloMuscularDecisionTests(CicloFalloMuscularBase):
    def test_fallo_previsto_se_clasifica_sin_inferirlo_de_rir(self):
        origen = self.sesion(
            date(2026, 8, 1), fallo=True, intencional=True, rpe=9,
        )

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.accion, 'mantener')
        self.assertEqual(decision.motivo_codigo, 'fallo_intencional')

    def test_primer_fallo_no_previsto_consolida(self):
        origen = self.sesion(
            date(2026, 8, 1), fallo=True, intencional=False, rpe=9,
        )

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.accion, 'mantener')
        self.assertEqual(decision.motivo_codigo, 'fallo_no_controlado')

    def test_dos_fallos_no_previstos_consecutivos_reducen_peso(self):
        primera = self.sesion(
            date(2026, 8, 1), fallo=True, intencional=False, rpe=9,
        )
        cerrar_aprendizaje_gym(primera)
        segunda = self.sesion(
            date(2026, 8, 5), fallo=True, intencional=False, rpe=9,
        )

        cerrar_aprendizaje_gym(segunda)

        decision = GymDecisionLog.objects.get(entreno_origen=segunda)
        self.assertEqual(decision.accion, 'bajar_peso')
        self.assertEqual(decision.motivo_codigo, 'fallo_repetido_no_controlado')

    def test_un_fallo_previsto_interrumpe_la_repeticion_no_controlada(self):
        primera = self.sesion(
            date(2026, 8, 1), fallo=True, intencional=False, rpe=9,
        )
        cerrar_aprendizaje_gym(primera)
        segunda = self.sesion(
            date(2026, 8, 5), fallo=True, intencional=True, rpe=9,
        )

        cerrar_aprendizaje_gym(segunda)

        decision = GymDecisionLog.objects.get(entreno_origen=segunda)
        self.assertEqual(decision.accion, 'mantener')
        self.assertEqual(decision.motivo_codigo, 'fallo_intencional')

    def test_siguiente_ejecucion_segura_valida_recuperacion_de_margen(self):
        origen = self.sesion(
            date(2026, 8, 1), fallo=True, intencional=False, rpe=9,
        )
        cerrar_aprendizaje_gym(origen)
        siguiente = self.sesion(
            date(2026, 8, 5), fallo=False, intencional=None, rpe=7,
        )

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.resultado, 'validada')
        self.assertIn('margen recuperado', decision.notas_resultado.lower())


class GuardarFalloMuscularActivoTests(CicloFalloMuscularBase):
    def _payload(self, tipo):
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
            'ej1_fallo_tipo': tipo,
        }
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '80'
            data[f'ej1_reps_{i}'] = '8'
            data[f'ej1_rpe_{i}'] = '9'
            data[f'ej1_completado_{i}'] = '1'
        return data

    def test_post_guarda_fallo_no_previsto_explicito(self):
        self.client.force_login(self.user)
        url = reverse(
            'entrenos:guardar_entrenamiento_activo',
            kwargs={'cliente_id': self.cliente.pk},
        )

        response = self.client.post(url, self._payload('no_previsto'))

        self.assertEqual(response.status_code, 302)
        ejercicio = EjercicioRealizado.objects.get(entreno__cliente=self.cliente)
        self.assertTrue(ejercicio.fallo_muscular)
        self.assertIs(ejercicio.fallo_intencional, False)

    def test_post_guarda_fallo_previsto_explicito(self):
        self.client.force_login(self.user)
        url = reverse(
            'entrenos:guardar_entrenamiento_activo',
            kwargs={'cliente_id': self.cliente.pk},
        )

        response = self.client.post(url, self._payload('previsto'))

        self.assertEqual(response.status_code, 302)
        ejercicio = EjercicioRealizado.objects.get(entreno__cliente=self.cliente)
        self.assertTrue(ejercicio.fallo_muscular)
        self.assertIs(ejercicio.fallo_intencional, True)
