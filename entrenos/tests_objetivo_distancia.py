"""Objetivo de distancia sin reps_objetivo: lo de la última vez, no el mínimo del rango (15-oct-2026)."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SerieRealizada
from entrenos.services.decision_log_service import (
    _distancia_cumple_evidencia, _objetivo_distancia_snapshot, normalizar_ejercicio,
)
from rutinas.models import EjercicioBase, Rutina

FARMER = 'Farmer Walk'


class ObjetivoDistancia(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='farmer', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'F'})
        self.base = EjercicioBase.objects.create(nombre=FARMER, grupo_muscular='otros',
                                                 tipo_progresion='progresion_distancia')
        self.rutina = Rutina.objects.create(nombre='Dia 5')

    def sesion(self, fecha, metros, rpe=7):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        for i, m in enumerate(metros, start=1):
            SerieRealizada.objects.create(entreno=e, ejercicio=self.base, serie_numero=i, repeticiones=1,
                                          peso_kg=36, distancia_metros=m, rpe_real=rpe, completado=True)
        return e

    def test_exige_lo_de_la_ultima_vez(self):
        self.sesion(date(2026, 10, 9), [50, 51])
        hoy = self.sesion(date(2026, 10, 16), [45, 46])
        clave = normalizar_ejercicio(FARMER)
        self.assertEqual(_objetivo_distancia_snapshot(hoy, clave), Decimal('51'))
        self.assertFalse(_distancia_cumple_evidencia(hoy, clave, Decimal('51')))

    def test_igualar_la_ultima_vez_cumple(self):
        self.sesion(date(2026, 10, 9), [50, 51])
        hoy = self.sesion(date(2026, 10, 16), [51, 52])
        clave = normalizar_ejercicio(FARMER)
        objetivo = _objetivo_distancia_snapshot(hoy, clave)
        self.assertTrue(_distancia_cumple_evidencia(hoy, clave, objetivo))

    def test_primera_vez_sin_snapshot_no_hay_objetivo(self):
        hoy = self.sesion(date(2026, 10, 16), [40])
        self.assertIsNone(_objetivo_distancia_snapshot(hoy, normalizar_ejercicio(FARMER)))
