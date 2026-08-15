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
from entrenos.services.decision_log_service import (
    evaluar_decisiones_para_entreno,
    generar_decisiones_para_entreno,
)
from rutinas.models import EjercicioBase, Rutina


class CicloProgresionPositivaTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='ciclo_progresion')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Ciclo progresión'},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina progresión')
        self.base = EjercicioBase.objects.create(
            nombre='Press banca', tipo_progresion='peso_reps',
        )

    def sesion(self, fecha, *, peso=80, reps=8, rpe=7, fallo=False):
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
            completado=True,
        )
        return entreno

    def decision_peso(self, *, estado='aplicada'):
        return GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio='press banca',
            ejercicio_normalizado='press banca',
            accion='subir_peso',
            motivo_codigo='progresion_peso',
            peso_anterior=80,
            reps_anteriores=8,
            rpe_anterior=7,
            valor_cambio=5,
            motivo='Dos ejecuciones controladas',
            estado_aplicacion=estado,
        )

    def test_generacion_clasifica_la_progresion_de_peso(self):
        anterior = self.sesion(date(2026, 8, 1), rpe=7)
        actual = self.sesion(date(2026, 8, 5), rpe=7)

        generar_decisiones_para_entreno(actual)

        decision = GymDecisionLog.objects.get(entreno_origen=actual)
        self.assertEqual(decision.accion, 'subir_peso')
        self.assertEqual(decision.motivo_codigo, 'progresion_peso')

    def test_progresion_pospuesta_no_se_evalua(self):
        decision = self.decision_peso(estado='pospuesta')
        siguiente = self.sesion(date(2026, 8, 5), peso=85, rpe=7)

        evaluar_decisiones_para_entreno(siguiente)

        decision.refresh_from_db()
        self.assertIsNone(decision.resultado)
        self.assertIsNone(decision.fecha_evaluacion)

    def test_progresion_pendiente_no_se_evalua(self):
        decision = self.decision_peso(estado='pendiente')
        siguiente = self.sesion(date(2026, 8, 5), peso=85, rpe=7)

        evaluar_decisiones_para_entreno(siguiente)

        decision.refresh_from_db()
        self.assertIsNone(decision.resultado)
        self.assertIsNone(decision.fecha_evaluacion)

    def test_objetivo_aplicado_con_margen_valida(self):
        decision = self.decision_peso()
        siguiente = self.sesion(date(2026, 8, 5), peso=85, rpe=8)

        evaluar_decisiones_para_entreno(siguiente)

        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'validada')
        self.assertIn('sostenible', decision.notas_resultado.lower())

    def test_subida_parcial_no_valida_el_objetivo(self):
        decision = self.decision_peso()
        siguiente = self.sesion(date(2026, 8, 5), peso=82.5, rpe=7)

        evaluar_decisiones_para_entreno(siguiente)

        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'neutra')
        self.assertIn('objetivo', decision.notas_resultado.lower())

    def test_objetivo_con_rpe_nueve_falla(self):
        decision = self.decision_peso()
        siguiente = self.sesion(date(2026, 8, 5), peso=85, rpe=9)

        evaluar_decisiones_para_entreno(siguiente)

        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'fallida')
        self.assertIn('rpe', decision.notas_resultado.lower())

    def test_objetivo_con_tecnica_comprometida_falla(self):
        decision = self.decision_peso()
        siguiente = self.sesion(date(2026, 8, 5), peso=85, rpe=8)
        SerieRealizada.objects.create(
            entreno=siguiente,
            ejercicio=self.base,
            serie_numero=1,
            repeticiones=8,
            peso_kg=85,
            rpe_real=8,
            tecnica_calidad='comprometida',
            completado=True,
        )

        evaluar_decisiones_para_entreno(siguiente)

        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'fallida')
        self.assertIn('técnica', decision.notas_resultado.lower())

    def test_progresion_por_distancia_exige_el_incremento_completo(self):
        EjercicioBase.objects.create(
            nombre='Farmer walk', tipo_progresion='progresion_distancia',
        )
        decision = GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio='farmer walk',
            ejercicio_normalizado='farmer walk',
            accion='subir_reps',
            motivo_codigo='progresion_reps',
            peso_anterior=32,
            reps_anteriores=20,
            rpe_anterior=7,
            valor_cambio=5,
            motivo='Progresión de distancia',
            estado_aplicacion='aplicada',
        )
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 8, 5),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Farmer walk',
            peso_kg=32,
            series=3,
            repeticiones=22,
            rpe=7,
            completado=True,
        )

        evaluar_decisiones_para_entreno(entreno)

        decision.refresh_from_db()
        self.assertEqual(decision.resultado, 'neutra')
        self.assertIn('objetivo', decision.notas_resultado.lower())
