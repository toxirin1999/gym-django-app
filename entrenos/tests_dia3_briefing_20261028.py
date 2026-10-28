"""28-oct-2026 · Briefing del Día 3 y panel del cuerpo (antes de entrenar)."""

from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from entrenos.models import ActividadRealizada, SerieRealizada
from entrenos.services.porque_decision_service import construir_porque
from entrenos.services.ultima_sesion_service import reps_txt, texto_doble_progresion
from entrenos.tests_cola_semanal import LUNES, ColaSemanalBase, PLAN, _sesion
from entrenos.tests_estado_carga_20261025 import HOY, Base
from entrenos.tests_ultima_sesion import Base as BaseSesion
from rutinas.models import EjercicioBase


class Textos(SimpleTestCase):
    def test_nota3_sin_reps_con_decimales(self):
        self.assertEqual(reps_txt(17.5), '17-18')
        self.assertEqual(reps_txt(16), '16')
        self.assertIn('la última vez 17-18', texto_doble_progresion(17.5, (15, 20)))

    def test_nota1_una_sola_cifra_de_carga(self):
        d = {'estado': 'entrenar', 'contexto_fisico': {'acwr_valor': 1.18, 'carga_ratio': 1.31}}
        self.assertEqual(construir_porque(d), 'Esta semana llevas un 31 % más de carga que en tus semanas normales.')


class PlanDinamico(BaseSesion):
    def test_nota5_sin_carga_tiene_objetivo(self):
        from entrenos.services.plan_dinamico_service import _objetivo_sin_carga
        b = EjercicioBase.objects.create(nombre='Sissy Squat', grupo_muscular='Cuádriceps', tipo_progresion='progresion_reps')
        e = self.entreno(timezone.localdate() - timedelta(days=5), {b.nombre: '15-20'})
        self.hacer(e, b, [(0, 9, 8)] * 3)
        ej = {'nombre': b.nombre, 'repeticiones': '15-20', 'tipo_progresion': 'progresion_reps'}
        _objetivo_sin_carga(self.cliente, ej, timezone.localdate())
        self.assertEqual(ej['reps_objetivo_hoy'], 10)
        self.assertEqual(ej['progresion_motivo'], 'Hoy a por 10 (la última vez 9, 9 y 9).')

    def test_nota4_tachado_y_fecha(self):
        from entrenos.services.cerebro_carga_service import aplicar_decision_carga, decidir_carga
        b = EjercicioBase.objects.create(nombre='Curl con Barra Z', grupo_muscular='Bíceps', tipo_progresion='peso_reps')
        e = self.entreno(timezone.localdate() - timedelta(days=22), {b.nombre: '15-20'})
        self.hacer(e, b, [(30, 15, 7), (30, 15, 7), (30, 12, 8), (30, 9, 8), (30, 10, 7)])
        ej = {'nombre': b.nombre, 'repeticiones': '15-20', 'rpe_objetivo': 9, 'tipo_progresion': 'peso_reps',
              'peso_kg': 32.5, 'peso_kg_anterior': 32.5}
        d = decidir_carga(self.cliente, ej, timezone.localdate())
        self.assertEqual(d['peso_antes'], 30)
        self.assertIn('(hace 22 días)', d['frase'])
        aplicar_decision_carga(ej, d)
        self.assertEqual(ej['peso_kg_anterior'], 30)

    def test_nota6_tope_de_reps_20(self):
        from entrenos.services.progreso_service import MAX_REPS_TOPE
        self.assertEqual(MAX_REPS_TOPE, 20)


class Panel(Base):
    def test_nota8_sin_comparar_sigue_conociendote(self):
        from entrenos.services.estado_carga_service import estado_carga
        for d in range(5):
            self.reloj(d, hrv=60, fc=58, sueno=7.5)
        e = estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'conociendote')
        self.assertIn('ya tengo 5 mañanas del reloj', e['frase'])


class DiaDespuesDelFutbol(ColaSemanalBase):
    def test_nota7_el_que_menos_repite(self):
        # Martes: quedan Día 2 (espalda, glúteos), Día 3 (bíceps, cuádriceps),
        # Día 4 (isquios, pecho)... con fútbol el lunes todos llevan pierna menos
        # el 5; sin el 5 en la semana, se elige el que menos repite.
        plan = dict(PLAN)
        plan[LUNES + timedelta(days=1)] = _sesion(2, ['cuadriceps', 'gluteos', 'gemelos'])
        plan[LUNES + timedelta(days=2)] = _sesion(3, ['isquios', 'pecho'])
        plan[LUNES + timedelta(days=3)] = _sesion(4, ['cuadriceps', 'gemelos'])
        plan[LUNES + timedelta(days=4)] = _sesion(5, ['gluteos', 'triceps', 'cuadriceps'])
        from unittest.mock import MagicMock, patch
        p = MagicMock()
        p.generar_entrenamiento_para_fecha.side_effect = lambda f: dict(plan.get(f) or {'rutina_nombre': 'Día de Descanso', 'ejercicios': []})
        self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Partido',
                                          fecha=LUNES, duracion_minutos=90)
        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=p):
            d = self.hoy(LUNES + timedelta(days=1))
        self.assertEqual(self.nombre(d), 'Dia 3 - Hipertrofia')
        self.assertIn('solo repite isquios', d['mensaje'])
