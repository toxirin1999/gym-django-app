from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog
from entrenos.services.estadisticas_service import EstadisticasService
from rutinas.models import EjercicioBase, Rutina


class FarmerWalkEstancamientoDashboardTest(TestCase):
    def setUp(self):
        user = User.objects.create_user('farmer_estadisticas')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Farmer estadísticas'},
        )
        self.rutina = Rutina.objects.create(nombre='Farmer estadísticas')

    def _sesion(self, dias_atras, reps, *, nombre='Farmer Walk', tope=True):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today() - timedelta(days=dias_atras),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=nombre,
            peso_kg=75,
            series=1,
            repeticiones=reps,
            es_tope_maquina=tope,
            completado=True,
        )
        return entreno

    def test_distancia_40_a_41_no_es_estancamiento_aunque_el_promedio_historico_sea_mayor(self):
        EjercicioBase.objects.create(
            nombre='Farmer Walk',
            grupo_muscular='Full body',
            tipo_progresion='progresion_distancia',
        )
        self._sesion(21, 45)
        self._sesion(14, 45)
        self._sesion(7, 40)
        self._sesion(0, 41)

        nombres = {item['nombre'] for item in EstadisticasService.detectar_estancamientos(self.cliente)}

        self.assertNotIn('Farmer Walk', nombres)

    def test_decision_causal_de_subir_reps_rescata_nombre_legacy_sin_catalogo(self):
        nombre = 'Farmer Walk Legacy'
        self._sesion(21, 45, nombre=nombre)
        self._sesion(14, 45, nombre=nombre)
        self._sesion(7, 40, nombre=nombre)
        ultimo = self._sesion(0, 41, nombre=nombre)
        GymDecisionLog.objects.create(
            cliente=self.cliente,
            entreno_origen=ultimo,
            ejercicio=nombre,
            ejercicio_normalizado='farmer walk legacy',
            accion='subir_reps',
            motivo='Progresión real de distancia: 40 a 41 metros.',
            motivo_codigo='progresion_reps',
        )

        nombres = {item['nombre'] for item in EstadisticasService.detectar_estancamientos(self.cliente)}

        self.assertNotIn(nombre, nombres)

    def test_tope_sin_avance_real_sigue_clasificado_como_estancado(self):
        EjercicioBase.objects.create(
            nombre='Farmer Walk',
            grupo_muscular='Full body',
            tipo_progresion='progresion_distancia',
        )
        for dias in (21, 14, 7, 0):
            self._sesion(dias, 40)

        nombres = {item['nombre'] for item in EstadisticasService.detectar_estancamientos(self.cliente)}

        self.assertIn('Farmer Walk', nombres)
