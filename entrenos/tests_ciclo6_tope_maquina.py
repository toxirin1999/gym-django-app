from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymDecisionLog
from entrenos.services.decision_log_service import cerrar_aprendizaje_gym
from rutinas.models import EjercicioBase, Rutina


class CicloTopeMaquinaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='ciclo_tope')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Ciclo tope'},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina tope')
        EjercicioBase.objects.create(
            nombre='Press de pierna', tipo_progresion='peso_reps',
        )

    def sesion(self, fecha, *, peso=120, reps=10, tope=True, rpe=7, fallo=False):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Press de pierna',
            peso_kg=peso,
            series=4,
            repeticiones=reps,
            rpe=rpe,
            fallo_muscular=fallo,
            es_tope_maquina=tope,
            completado=True,
        )
        return entreno

    def test_tope_genera_decision_causal_mismo_peso_mas_una_rep(self):
        origen = self.sesion(date(2026, 8, 1))

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.accion, 'subir_reps')
        self.assertEqual(decision.motivo_codigo, 'tope_maquina')
        self.assertEqual(decision.peso_anterior, 120)
        self.assertEqual(decision.reps_sugeridas, 11)

    def test_alcanzar_objetivo_con_mismo_peso_valida(self):
        origen = self.sesion(date(2026, 8, 1), reps=10)
        cerrar_aprendizaje_gym(origen)
        siguiente = self.sesion(date(2026, 8, 5), reps=11)

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.resultado, 'validada')
        self.assertIn('Tope consolidado', decision.notas_resultado)

    def test_subir_reps_cambiando_peso_no_valida_el_ajuste(self):
        origen = self.sesion(date(2026, 8, 1), peso=120, reps=10)
        cerrar_aprendizaje_gym(origen)
        siguiente = self.sesion(date(2026, 8, 5), peso=110, reps=11)

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.resultado, 'neutra')
        self.assertIn('cambió', decision.notas_resultado)

    def test_tres_topes_sin_avance_proponen_cambio_de_estimulo(self):
        for fecha in (date(2026, 8, 1), date(2026, 8, 5), date(2026, 8, 9)):
            cerrar_aprendizaje_gym(self.sesion(fecha, peso=120, reps=10))

        ultima = GymDecisionLog.objects.get(
            entreno_origen__fecha=date(2026, 8, 9),
        )
        self.assertEqual(ultima.accion, 'cambiar_variante')
        self.assertEqual(ultima.motivo_codigo, 'tope_maquina_sin_margen')
        self.assertIn('Sin progresión', ultima.motivo)

    def test_ganar_una_repeticion_reinicia_el_conteo_de_sin_margen(self):
        cerrar_aprendizaje_gym(self.sesion(date(2026, 8, 1), reps=10))
        cerrar_aprendizaje_gym(self.sesion(date(2026, 8, 5), reps=10))
        tercera = self.sesion(date(2026, 8, 9), reps=11)

        cerrar_aprendizaje_gym(tercera)

        ultima = GymDecisionLog.objects.get(entreno_origen=tercera)
        self.assertEqual(ultima.accion, 'subir_reps')
        self.assertEqual(ultima.motivo_codigo, 'tope_maquina')
        self.assertEqual(ultima.reps_sugeridas, 12)

    def test_una_sesion_sin_tope_interrumpe_la_consecutividad(self):
        cerrar_aprendizaje_gym(self.sesion(date(2026, 8, 1), reps=10, tope=True))
        cerrar_aprendizaje_gym(self.sesion(date(2026, 8, 5), reps=10, tope=False))
        tercera = self.sesion(date(2026, 8, 9), reps=10, tope=True)

        cerrar_aprendizaje_gym(tercera)

        ultima = GymDecisionLog.objects.get(entreno_origen=tercera)
        self.assertEqual(ultima.accion, 'subir_reps')
        self.assertEqual(ultima.motivo_codigo, 'tope_maquina')

    def test_rpe_extremo_prevalece_y_ordena_bajar_peso(self):
        origen = self.sesion(date(2026, 8, 1), rpe=10)

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.accion, 'bajar_peso')
        self.assertNotIn(
            decision.motivo_codigo,
            ('tope_maquina', 'tope_maquina_sin_margen'),
        )
