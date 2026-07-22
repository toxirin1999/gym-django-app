# entrenos/test_x4_peso_sugerido_snapshot_crudo.py
"""
Phase Gym Peso 2.2 — X.4: contrato de GymDecisionLog.peso_sugerido_para_fase.

A diferencia de core.py (X.2) y vista_entrenamiento_activo (X.3), esta función
NO debe pasar por el ancla suavizada de resolver_ancla_historica(). Sus campos
peso_anterior/reps_anteriores/rpe_anterior son un snapshot fijo de la sesión
concreta que disparó el log (técnica comprometida, tope de máquina, etc.) —
promediarlos con otras sesiones rompería el significado de "por qué se generó
este log". Ver diseño Phase Gym Peso 2.2 (opus-architect): "GymDecisionLog
sigue sobre el snapshot crudo... suavizar sería semánticamente incorrecto".

Este test fija ese contrato: si en el futuro alguien intenta cablear el ancla
aquí, este test debe fallar y recordar por qué no se hizo.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionLog


class TestPesoSugeridoParaFaseUsaSnapshotCrudo(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_x4_snapshot', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestX4', 'dias_disponibles': 4}
        )

    def _log(self, **kwargs):
        defaults = dict(
            cliente=self.cliente,
            ejercicio='Test X4 Press Snapshot',
            accion='subir_peso',
            valor_cambio=5.0,
            peso_anterior=100.0,
            reps_anteriores=5,
            rpe_anterior=8.0,
            motivo='test',
        )
        defaults.update(kwargs)
        return GymDecisionLog.objects.create(**defaults)

    def test_usa_exactamente_los_campos_propios_no_historial_externo(self):
        """
        Con bucket incompatible (fuerza 5 reps -> hipertrofia 12 reps), dispara
        el recálculo de resolver_peso_objetivo. El resultado debe depender SOLO
        de peso_anterior/reps_anteriores/rpe_anterior del propio log — no debe
        existir ninguna consulta a EjercicioRealizado ni a resolver_ancla_historica
        dentro de peso_sugerido_para_fase.
        """
        log = self._log()
        peso, motivo = log.peso_sugerido_para_fase(
            rep_range_hoy='10-12', rpe_objetivo_hoy=7, es_descarga_hoy=False
        )
        self.assertIsNotNone(peso)
        self.assertEqual(motivo, 'recalculado_fase')

    def test_dos_logs_con_mismo_snapshot_dan_el_mismo_resultado(self):
        """
        Propiedad de aislamiento: dos GymDecisionLog con idéntico snapshot pero
        de fechas distintas (simulando que uno tiene 'más historial detrás' si
        se hubiera promediado) deben dar el MISMO peso sugerido — prueba de que
        no hay suavizado entre sesiones distintas.
        """
        log_a = self._log(peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0)
        log_b = self._log(peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0)

        peso_a, _ = log_a.peso_sugerido_para_fase('10-12', 7, False)
        peso_b, _ = log_b.peso_sugerido_para_fase('10-12', 7, False)

        self.assertEqual(peso_a, peso_b)

    def test_no_importa_el_historial_real_de_ejercicio_realizado(self):
        """
        Crea EjercicioRealizado reales con pesos muy distintos al snapshot del
        log, en el mismo bucket. Si peso_sugerido_para_fase promediara con ese
        historial (como hacen core.py/X.2 y vista_entrenamiento_activo/X.3),
        el resultado cambiaría. Debe seguir siendo idéntico al snapshot puro.
        """
        from datetime import date, timedelta
        from entrenos.models import EntrenoRealizado, EjercicioRealizado
        from rutinas.models import Rutina

        rutina, _ = Rutina.objects.get_or_create(nombre='_test_x4_rutina')
        for delta, peso in [(2, 40.0), (9, 35.0), (16, 30.0)]:
            entreno = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=rutina,
                fecha=date.today() - timedelta(days=delta),
            )
            EjercicioRealizado.objects.create(
                entreno=entreno, nombre_ejercicio='Test X4 Press Snapshot',
                peso_kg=peso, repeticiones=5, rpe=8,
            )

        log = self._log(peso_anterior=100.0, reps_anteriores=5, rpe_anterior=8.0)
        peso_sin_historial_externo, _ = log.peso_sugerido_para_fase('10-12', 7, False)

        # Si hubiera leído el historial real (peso ~30-40kg) en vez del snapshot
        # propio (100kg), el resultado sería drásticamente menor.
        self.assertGreater(
            peso_sin_historial_externo, 50.0,
            "peso_sugerido_para_fase no debe verse afectado por EjercicioRealizado "
            "externo — solo por su propio snapshot (peso_anterior=100kg)",
        )
