"""26-oct-2026 · Semana adaptativa, paso 1: elegir el día que toca.

Fija la semana (los cinco días), adapta el día: si lo que toca repite músculo
de ayer, se hace otro de los días que quedan, y se dice por qué.
"""

from datetime import timedelta

from entrenos.models import ActividadRealizada, SerieRealizada
from entrenos.services.porque_decision_service import construir_porque
from entrenos.tests_cola_semanal import LUNES, ColaSemanalBase
from rutinas.models import EjercicioBase


class EligeElDia(ColaSemanalBase):
    def series(self, entreno, grupo, n=4):
        base, _ = EjercicioBase.objects.get_or_create(
            nombre=f'Ejercicio real {grupo}', defaults={'grupo_muscular': grupo, 'tipo_progresion': 'peso_reps'},
        )
        for i in range(1, n + 1):
            SerieRealizada.objects.create(entreno=entreno, ejercicio=base, serie_numero=i,
                                          repeticiones=12, peso_kg=50, rpe_real=8, completado=True)

    def test_el_lunes_tras_pecho_del_domingo_adelanta_otro_dia(self):
        domingo = LUNES - timedelta(days=1)
        self.series(self.entrenar(domingo, 'Dia 5 - Hipertrofia'), 'Pecho')
        d = self.hoy(LUNES)
        self.assertEqual(self.nombre(d), 'Dia 2 - Hipertrofia')
        self.assertEqual(d['tipo'], 'pendiente')
        self.assertIn('Hoy el Día 2 en vez del Día 1: ayer hiciste pecho', d['mensaje'])
        self.assertEqual(construir_porque(d), d['mensaje'])

    def test_al_dia_siguiente_vuelve_el_que_se_aplazo(self):
        domingo = LUNES - timedelta(days=1)
        self.series(self.entrenar(domingo, 'Dia 5 - Hipertrofia'), 'Pecho')
        self.hoy(LUNES)
        self.series(self.entrenar(LUNES, 'Dia 2 - Hipertrofia'), 'Espalda')
        d = self.hoy(LUNES + timedelta(days=1))
        self.assertEqual(self.nombre(d), 'Dia 1 - Hipertrofia')

    def test_sin_choque_sigue_el_orden(self):
        domingo = LUNES - timedelta(days=1)
        self.series(self.entrenar(domingo, 'Dia 5 - Hipertrofia'), 'Hombros')
        d = self.hoy(LUNES)
        self.assertEqual(self.nombre(d), 'Dia 1 - Hipertrofia')
        self.assertNotIn('en vez del', d.get('mensaje') or '')

    def test_el_futbol_cuenta_como_pierna(self):
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Partido',
                                          fecha=LUNES - timedelta(days=1), duracion_minutos=90)
        d = self.hoy(LUNES)
        # Día 1 lleva cuádriceps; el Día 2 (espalda, glúteos) también es pierna;
        # el primero sin pierna es el Día 5 (hombros, tríceps).
        self.assertEqual(self.nombre(d), 'Dia 5 - Hipertrofia')
        self.assertIn('fútbol (pierna)', d['mensaje'])

    def test_si_ninguno_encaja_se_queda_el_previsto(self):
        domingo = LUNES - timedelta(days=1)
        e = self.entrenar(domingo, 'Dia 5 - Hipertrofia')
        for g in ('Pecho', 'Espalda', 'Bíceps', 'Isquiotibiales', 'Hombros'):
            self.series(e, g)
        d = self.hoy(LUNES)
        self.assertEqual(self.nombre(d), 'Dia 1 - Hipertrofia')
