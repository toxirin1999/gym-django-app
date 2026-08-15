from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymAdaptationProfile, GymDecisionLog
from entrenos.services.decision_log_service import _actualizar_perfil


class Ciclo10PerfilAdaptacionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='ciclo10')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Ciclo 10'},
        )
        self.ejercicio = 'press banca'

    def decision(self, *, resultado, motivo_codigo='progresion_peso',
                 estado='aplicada', accion='subir_peso'):
        return GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio=self.ejercicio,
            ejercicio_normalizado=self.ejercicio,
            accion=accion,
            valor_cambio=5,
            motivo='Evidencia de prueba',
            motivo_codigo=motivo_codigo,
            estado_aplicacion=estado,
            resultado=resultado,
        )

    def perfil(self):
        return GymAdaptationProfile.objects.get(
            cliente=self.cliente, ejercicio=self.ejercicio,
        )

    def test_solo_aprende_de_progresiones_de_peso_aplicadas_y_concluyentes(self):
        self.decision(resultado='validada')
        self.decision(resultado='fallida')
        self.decision(resultado='neutra')
        self.decision(resultado='validada', estado='pospuesta')
        self.decision(resultado='fallida', motivo_codigo='rpe_alto_sostenido', accion='bajar_peso')
        self.decision(resultado='validada', motivo_codigo='progresion_reps', accion='subir_reps')

        _actualizar_perfil(self.cliente, self.ejercicio)

        perfil = self.perfil()
        self.assertEqual(perfil.decisiones_totales, 2)
        self.assertEqual(perfil.decisiones_validadas, 1)
        self.assertEqual(perfil.decisiones_fallidas, 1)
        self.assertEqual(perfil.confianza, 'baja')

    def test_dos_validaciones_calibran_desde_la_base_explicita(self):
        self.decision(resultado='validada')
        self.decision(resultado='validada')

        _actualizar_perfil(self.cliente, self.ejercicio)

        self.assertEqual(self.perfil().incremento_peso_pct, 5.5)

    def test_dos_fallos_calibran_desde_la_base_explicita(self):
        self.decision(resultado='fallida')
        self.decision(resultado='fallida')

        _actualizar_perfil(self.cliente, self.ejercicio)

        self.assertEqual(self.perfil().incremento_peso_pct, 4.0)

    def test_recalcular_con_la_misma_evidencia_es_idempotente(self):
        self.decision(resultado='validada')
        self.decision(resultado='validada')

        _actualizar_perfil(self.cliente, self.ejercicio)
        primero = self.perfil().incremento_peso_pct
        _actualizar_perfil(self.cliente, self.ejercicio)

        self.assertEqual(primero, 5.5)
        self.assertEqual(self.perfil().incremento_peso_pct, primero)

    def test_la_confianza_solo_usa_evidencia_pertinente(self):
        for _ in range(6):
            self.decision(resultado='validada', motivo_codigo='tecnica_comprometida', accion='mantener')
        for _ in range(3):
            self.decision(resultado='validada')

        _actualizar_perfil(self.cliente, self.ejercicio)

        perfil = self.perfil()
        self.assertEqual(perfil.decisiones_totales, 3)
        self.assertEqual(perfil.confianza, 'media')

    def test_preserva_la_reduccion_existente(self):
        GymAdaptationProfile.objects.create(
            cliente=self.cliente,
            ejercicio=self.ejercicio,
            incremento_peso_pct=6.5,
            reduccion_peso_pct=13.0,
        )
        self.decision(resultado='fallida')
        self.decision(resultado='fallida')
        self.decision(resultado='fallida', motivo_codigo='rpe_alto_sostenido', accion='bajar_peso')

        _actualizar_perfil(self.cliente, self.ejercicio)

        perfil = self.perfil()
        self.assertEqual(perfil.incremento_peso_pct, 4.0)
        self.assertEqual(perfil.reduccion_peso_pct, 13.0)
