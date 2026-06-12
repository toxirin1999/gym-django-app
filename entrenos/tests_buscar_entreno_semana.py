"""
Tests for buscar_entreno_realizado_esta_semana — Phase 62J.

Bug: el "Nivel 2: hecho esta semana" del dashboard (clientes/views.py) marcaba
como "ya realizado" la sesión de HOY cuando, en realidad, lo que se encontró
fue un catch-up tardío de la MISMA rutina (por nombre) pero de la SEMANA
ANTERIOR de periodización. "Día 5 - Potencia — Resensibilización" se repite
con el mismo nombre en cada semana del bloque, sin distinguir semana 1 de
semana 2 (pesos progresados).

buscar_entreno_realizado_esta_semana(cliente, hoy, rutina_nombre) reproduce la
búsqueda por nombre dentro de esta semana, pero descarta candidatos cuya
SesionProgramada vinculada (fecha_prevista) pertenece a una semana de bloque
distinta a la de `hoy`.

Cases:
1.  Catch-up de la semana anterior con el mismo nombre de rutina → NO se
    considera "hecho esta semana" (el bug original).
2.  Sesión hecha hoy con el mismo nombre, sin SesionProgramada vinculada →
    SÍ se considera "hecho esta semana".
3.  Sin candidatos → None.
4.  rutina_nombre vacío → None.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.sesion_recomendada import buscar_entreno_realizado_esta_semana
from rutinas.models import Programa, Rutina

_RUTINA_DIA5 = 'Dia 5 - Potencia — Resensibilización'


class BuscarEntrenoSemanaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_bes', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestBES', 'dias_disponibles': 5},
        )
        self.programa = Programa.objects.create(nombre='Prog BES')
        self.rutina = Rutina.objects.create(
            programa=self.programa, nombre=_RUTINA_DIA5,
        )
        # Viernes, "Día 5" semana 2 del bloque "Potencia — Resensibilización"
        self.hoy = date(2026, 6, 12)


class TestCase1_CatchUpSemanaAnterior(BuscarEntrenoSemanaBase):
    """El catch-up del viernes pasado (semana 1) no debe contar como 'hoy hecho'."""

    def test_catchup_no_se_considera_hecho_esta_semana(self):
        sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 6, 5),  # viernes semana 1, "Día 5"
            nombre_sesion=_RUTINA_DIA5,
            dia_numero=5,
            estado=SesionProgramada.ESTADO_COMPLETADA,
            fecha_realizada=date(2026, 6, 8),
        )
        er = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            fecha=date(2026, 6, 8),  # lunes semana 2 (catch-up tardío)
            rutina=self.rutina,
        )
        sp.entreno_realizado = er
        sp.save()

        resultado = buscar_entreno_realizado_esta_semana(self.cliente, self.hoy, _RUTINA_DIA5)
        self.assertIsNone(resultado)


class TestCase2_HechoEstaSemana(BuscarEntrenoSemanaBase):
    """Una sesión hecha hoy, mismo nombre, sin catch-up de otra semana, sí cuenta."""

    def test_hecho_hoy_se_considera_hecho_esta_semana(self):
        er = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            fecha=self.hoy,
            rutina=self.rutina,
        )
        resultado = buscar_entreno_realizado_esta_semana(self.cliente, self.hoy, _RUTINA_DIA5)
        self.assertEqual(resultado, er)


class TestCase3_SinCandidatos(BuscarEntrenoSemanaBase):
    def test_sin_entrenos_devuelve_none(self):
        resultado = buscar_entreno_realizado_esta_semana(self.cliente, self.hoy, _RUTINA_DIA5)
        self.assertIsNone(resultado)


class TestCase4_RutinaVacia(BuscarEntrenoSemanaBase):
    def test_rutina_nombre_vacio_devuelve_none(self):
        EntrenoRealizado.objects.create(
            cliente=self.cliente, fecha=self.hoy, rutina=self.rutina,
        )
        resultado = buscar_entreno_realizado_esta_semana(self.cliente, self.hoy, '')
        self.assertIsNone(resultado)
