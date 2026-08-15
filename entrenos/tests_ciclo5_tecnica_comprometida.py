from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    EntrenoRealizado,
    EjercicioRealizado,
    GymDecisionLog,
    SerieRealizada,
)
from entrenos.services.decision_log_service import cerrar_aprendizaje_gym
from rutinas.models import EjercicioBase, Rutina


class CicloTecnicaComprometidaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='ciclo_tecnica')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Ciclo técnica'},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina técnica')
        self.ejercicio = EjercicioBase.objects.create(nombre='Press banca')

    def sesion(self, fecha, tecnica, peso=50, rpe=7, fallo=False):
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
        if tecnica is not None:
            SerieRealizada.objects.create(
                entreno=entreno,
                ejercicio=self.ejercicio,
                serie_numero=1,
                repeticiones=8,
                peso_kg=peso,
                tecnica_calidad=tecnica,
                completado=True,
            )
        return entreno

    def test_crea_freno_causal_en_lugar_de_progresion(self):
        origen = self.sesion(date(2026, 8, 1), 'comprometida')

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.accion, 'mantener')
        self.assertEqual(decision.motivo_codigo, 'tecnica_comprometida')
        self.assertEqual(decision.peso_anterior, 50)
        self.assertIsNone(decision.resultado)

    def test_tecnica_recuperada_valida_el_freno(self):
        origen = self.sesion(date(2026, 8, 1), 'comprometida')
        cerrar_aprendizaje_gym(origen)
        siguiente = self.sesion(date(2026, 8, 5), 'buena')

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.resultado, 'validada')
        self.assertIn('Técnica recuperada', decision.notas_resultado)
        nueva = GymDecisionLog.objects.get(entreno_origen=siguiente)
        self.assertNotEqual(nueva.motivo_codigo, 'tecnica_comprometida')

    def test_tecnica_comprometida_repetida_falla_y_renueva_el_freno(self):
        origen = self.sesion(date(2026, 8, 1), 'comprometida')
        cerrar_aprendizaje_gym(origen)
        siguiente = self.sesion(date(2026, 8, 5), 'comprometida')

        cerrar_aprendizaje_gym(siguiente)

        anterior = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(anterior.resultado, 'fallida')
        self.assertIn('persiste', anterior.notas_resultado)
        nueva = GymDecisionLog.objects.get(entreno_origen=siguiente)
        self.assertEqual(nueva.motivo_codigo, 'tecnica_comprometida')
        self.assertIsNone(nueva.resultado)

    def test_sin_dato_tecnico_cierra_como_evidencia_insuficiente(self):
        origen = self.sesion(date(2026, 8, 1), 'comprometida')
        cerrar_aprendizaje_gym(origen)
        siguiente = self.sesion(date(2026, 8, 5), None)

        cerrar_aprendizaje_gym(siguiente)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.resultado, 'neutra')
        self.assertIn('Sin dato técnico', decision.notas_resultado)

    def test_fallo_muscular_prevalece_sobre_tecnica(self):
        origen = self.sesion(
            date(2026, 8, 1), 'comprometida', rpe=10, fallo=True,
        )

        cerrar_aprendizaje_gym(origen)

        decision = GymDecisionLog.objects.get(entreno_origen=origen)
        self.assertEqual(decision.accion, 'bajar_peso')
        self.assertNotEqual(decision.motivo_codigo, 'tecnica_comprometida')
