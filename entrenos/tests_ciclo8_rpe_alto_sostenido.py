from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymDecisionLog
from entrenos.services.decision_log_service import cerrar_aprendizaje_gym
from rutinas.models import EjercicioBase, Rutina


class CicloRpeAltoSostenidoTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='ciclo_rpe')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Ciclo RPE'},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina RPE')
        EjercicioBase.objects.create(nombre='Press banca', tipo_progresion='peso_reps')

    def sesion(self, fecha, *, rpe, peso=80, fallo=False):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Press banca',
            peso_kg=peso,
            series=3,
            repeticiones=8,
            rpe=rpe,
            fallo_muscular=fallo,
            completado=True,
        )
        return entreno

    def cerrar_tres(self, rpes):
        sesiones = []
        for dia, rpe in zip((1, 5, 9), rpes):
            sesion = self.sesion(date(2026, 8, dia), rpe=rpe)
            cerrar_aprendizaje_gym(sesion)
            sesiones.append(sesion)
        return sesiones

    def test_un_rpe_alto_aislado_no_reduce_la_carga(self):
        origen = self.sesion(date(2026, 8, 1), rpe=9)

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertNotEqual(decision.accion, 'bajar_peso')
        self.assertNotEqual(decision.motivo_codigo, 'rpe_alto_sostenido')

    def test_tres_rpe_altos_consecutivos_reducen_la_carga(self):
        sesiones = self.cerrar_tres([9, 9, 9])

        decision = GymDecisionLog.objects.get(entreno_origen=sesiones[-1])
        self.assertEqual(decision.accion, 'bajar_peso')
        self.assertEqual(decision.motivo_codigo, 'rpe_alto_sostenido')

    def test_una_sesion_controlada_interrumpe_la_consecutividad(self):
        sesiones = self.cerrar_tres([9, 7.5, 9])

        decision = GymDecisionLog.objects.get(entreno_origen=sesiones[-1])
        self.assertNotEqual(decision.accion, 'bajar_peso')
        self.assertNotEqual(decision.motivo_codigo, 'rpe_alto_sostenido')

    def test_rpe_extremo_reduce_sin_esperar_tres_sesiones(self):
        origen = self.sesion(date(2026, 8, 1), rpe=10)

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.accion, 'bajar_peso')
        self.assertEqual(decision.motivo_codigo, 'rpe_extremo')

    def test_reduccion_aplicada_y_rpe_controlado_valida(self):
        sesiones = self.cerrar_tres([9, 9, 9])
        siguiente = self.sesion(date(2026, 8, 13), rpe=8, peso=72)

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=sesiones[-1])
        self.assertEqual(decision.resultado, 'validada')
        self.assertIn('margen recuperado', decision.notas_resultado.lower())

    def test_si_no_reduce_el_peso_la_evaluacion_es_neutra(self):
        sesiones = self.cerrar_tres([9, 9, 9])
        siguiente = self.sesion(date(2026, 8, 13), rpe=8, peso=80)

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=sesiones[-1])
        self.assertEqual(decision.resultado, 'neutra')
        self.assertIn('no se aplicó', decision.notas_resultado.lower())

    def test_reduccion_aplicada_con_rpe_aun_alto_falla(self):
        sesiones = self.cerrar_tres([9, 9, 9])
        siguiente = self.sesion(date(2026, 8, 13), rpe=9, peso=72)

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=sesiones[-1])
        self.assertEqual(decision.resultado, 'fallida')
        self.assertIn('sigue alto', decision.notas_resultado.lower())
