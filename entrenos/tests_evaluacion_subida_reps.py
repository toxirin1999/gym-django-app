"""Una subida de peso solo "funcionó" si además se hicieron las reps mínimas."""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog
from entrenos.services.decision_log_service import evaluar_decisiones_para_entreno
from rutinas.models import EjercicioBase, Rutina


class EvaluacionSubidaRepsTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='subida_reps')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'Subida'})
        self.rutina = Rutina.objects.create(nombre='Rutina subida')
        EjercicioBase.objects.create(nombre='Curl femoral tumbado', tipo_progresion='peso_reps')

    def _sesion(self, peso, reps, rpe=8):
        entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 10, 10))
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Curl femoral tumbado', peso_kg=peso,
            series=3, repeticiones=reps, rpe=rpe, completado=True,
        )
        return entreno

    def _decision(self, motivo_codigo):
        return GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='curl femoral tumbado',
            ejercicio_normalizado='curl femoral tumbado', accion='subir_peso',
            motivo_codigo=motivo_codigo, peso_anterior=42.5, reps_anteriores=12,
            rpe_anterior=7, valor_cambio=5, motivo='x', estado_aplicacion='aplicada',
        )

    def test_progresion_con_pocas_reps_no_funciona_todavia(self):
        decision = self._decision('progresion_peso')
        evaluar_decisiones_para_entreno(self._sesion(45, 6))
        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'neutra')
        self.assertEqual(decision.notas_resultado, 'Peso alcanzado, pero con 6 reps frente a 10 de objetivo')

    def test_progresion_con_reps_suficientes_funciona(self):
        decision = self._decision('progresion_peso')
        evaluar_decisiones_para_entreno(self._sesion(45, 11))
        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'validada')

    def test_subida_generica_tambien_exige_reps(self):
        decision = self._decision('')
        evaluar_decisiones_para_entreno(self._sesion(45, 6))
        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'neutra')
        self.assertIn('6 reps', decision.notas_resultado)
