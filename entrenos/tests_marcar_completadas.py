"""
Tests for _marcar_completadas — extended logic for sessions done on a later date.

Strategy 1 (existing): exact date match — session pending for May 15, done May 15.
Strategy 2 (new): same rutina within 7 days after pending date — session pending for
May 15, done May 18 with the same routine name.

Cases:
1.  Exact date: pending May 15, EntrenoRealizado May 15 → closed, fecha_realizada=15.
2.  Later date: pending May 15, EntrenoRealizado May 18 (same rutina) → closed, fecha_realizada=18.
3.  No match: pending May 15, no EntrenoRealizado in window → stays PENDIENTE.
4.  Ambiguous: two EntrenoRealizado with same rutina in window → NOT closed (safety).
5.  Different rutina: EntrenoRealizado in window but different routine → NOT closed.
6.  Beyond 7-day window: EntrenoRealizado 8 days after → NOT closed.
7.  Already COMPLETADA: not touched.
8.  Strategy 2 sets entreno_realizado FK on the SesionProgramada.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import SesionProgramada, EntrenoRealizado
from entrenos.services.sesion_recomendada import _marcar_completadas
from rutinas.models import Rutina, Programa


class MarcarCompletadasBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_mc', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestMC', 'dias_disponibles': 4},
        )
        self.programa = Programa.objects.create(nombre='Prog Test')
        self.rutina = Rutina.objects.create(
            programa=self.programa,
            nombre='Dia 5 - Hipertrofia — Intensificación',
        )
        self.hoy = date(2026, 5, 18)

    def _sp(self, fecha, nombre='Dia 5 - Hipertrofia — Intensificación',
             estado=SesionProgramada.ESTADO_PENDIENTE):
        return SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=fecha,
            nombre_sesion=nombre, estado=estado,
        )

    def _er(self, fecha, rutina=None):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, fecha=fecha,
            rutina=rutina or self.rutina,
        )


class TestStrategy1_FechaExacta(MarcarCompletadasBase):
    def test_pendiente_con_entreno_misma_fecha_se_cierra(self):
        sp = self._sp(self.hoy - timedelta(days=3))
        self._er(self.hoy - timedelta(days=3))
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_COMPLETADA)

    def test_fecha_realizada_igual_a_fecha_prevista(self):
        fecha = self.hoy - timedelta(days=3)
        sp = self._sp(fecha)
        self._er(fecha)
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.fecha_realizada, fecha)


class TestStrategy2_FechaPosterior(MarcarCompletadasBase):
    def test_pendiente_mayo_15_hecho_mayo_18_misma_rutina(self):
        sp = self._sp(self.hoy - timedelta(days=3))  # May 15
        er = self._er(self.hoy)                        # May 18
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(sp.fecha_realizada, self.hoy)

    def test_entreno_realizado_enlazado_en_sesion(self):
        sp = self._sp(self.hoy - timedelta(days=3))
        er = self._er(self.hoy)
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.entreno_realizado_id, er.id)


class TestStrategy2_NoMatch(MarcarCompletadasBase):
    def test_sin_entreno_en_ventana_queda_pendiente(self):
        sp = self._sp(self.hoy - timedelta(days=3))
        # No EntrenoRealizado created
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_ambiguo_dos_entrenos_misma_rutina_no_cierra(self):
        sp = self._sp(self.hoy - timedelta(days=5))
        self._er(self.hoy - timedelta(days=3))
        self._er(self.hoy - timedelta(days=1))  # two matches → ambiguous
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_diferente_rutina_no_cierra(self):
        otra_rutina = Rutina.objects.create(
            programa=self.programa, nombre='Dia 1 - Pecho', orden=2,
        )
        sp = self._sp(self.hoy - timedelta(days=3))
        self._er(self.hoy, rutina=otra_rutina)
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_mas_de_7_dias_no_cierra(self):
        sp = self._sp(self.hoy - timedelta(days=10))
        # EntrenoRealizado 8 days after sp.fecha_prevista = 2 days ago
        self._er(self.hoy - timedelta(days=2))  # > 7 days from May 8
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        # May 8 + 7 = May 15 max; May 16 (hoy-2) is outside window
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_PENDIENTE)


class TestStrategy2_AlreadyCompleta(MarcarCompletadasBase):
    def test_ya_completada_no_se_toca(self):
        sp = self._sp(self.hoy - timedelta(days=3),
                       estado=SesionProgramada.ESTADO_COMPLETADA)
        sp.fecha_realizada = self.hoy - timedelta(days=3)
        sp.save()
        _marcar_completadas(self.cliente, self.hoy)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_COMPLETADA)
