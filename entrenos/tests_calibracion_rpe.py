"""Calibración del RPE en fuerza con el propio rendimiento (14-oct-2026)."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SerieRealizada
from entrenos.services.calibracion_rpe_service import calibracion_rpe_gym
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 10, 14)


class CalibracionRPE(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='calibra', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'C'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')

    def ejercicio(self, nombre):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='otros', tipo_progresion='peso_reps')

    def sesion(self, dias_atras, base, series):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=HOY - timedelta(days=dias_atras))
        for i, (peso, reps, rpe) in enumerate(series, start=1):
            SerieRealizada.objects.create(
                entreno=e, ejercicio=base, serie_numero=i, repeticiones=reps, peso_kg=peso,
                rpe_real=rpe, completado=True,
            )

    def test_detecta_un_rpe_alto(self):
        prensa = self.ejercicio('Prensa de Piernas')
        self.sesion(9, prensa, [(140, 12, 9)])          # RPE 9: quedaba ~1 → máximo 13
        self.sesion(0, prensa, [(140, 15, 8)])          # 15 ≥ 13 + 2
        res = calibracion_rpe_gym(self.cliente, hoy=HOY)
        self.assertEqual((res['casos'], res['altos']), (1, 1))
        self.assertEqual(res['lectura'], 'insuficiente')
        self.assertEqual(
            res['ejemplo'], 'Prensa de Piernas: dijiste RPE 9 con 140 kg × 12 y 9 días después hiciste 140 kg × 15.',
        )

    def test_rpe_que_cuadra(self):
        for i in range(5):
            base = self.ejercicio(f'Ejercicio {i}')
            self.sesion(7, base, [(50, 10, 9)])
            self.sesion(0, base, [(50, 11, 9)])         # dentro de lo posible
        res = calibracion_rpe_gym(self.cliente, hoy=HOY)
        self.assertEqual((res['casos'], res['altos'], res['lectura']), (5, 0, 'fiable'))

    def test_marca_alto_con_casos_suficientes(self):
        for i in range(5):
            base = self.ejercicio(f'Ejercicio {i}')
            self.sesion(7, base, [(50, 10, 9)])
            self.sesion(0, base, [(50, 14 if i < 3 else 10, 8)])
        res = calibracion_rpe_gym(self.cliente, hoy=HOY)
        self.assertEqual((res['altos'], res['pct'], res['lectura']), (3, 60, 'alto'))

    def test_no_compara_sesiones_lejanas_ni_pesos_distintos(self):
        a = self.ejercicio('A')
        self.sesion(30, a, [(50, 10, 9)])
        self.sesion(0, a, [(50, 15, 8)])                # 30 días: puede ser progreso real
        b = self.ejercicio('B')
        self.sesion(5, b, [(50, 10, 9)])
        self.sesion(0, b, [(45, 15, 8)])                # otro peso
        self.assertIsNone(calibracion_rpe_gym(self.cliente, hoy=HOY))

    def test_rpe_bajo_no_cuenta(self):
        a = self.ejercicio('A')
        self.sesion(5, a, [(50, 10, 6)])
        self.sesion(0, a, [(50, 15, 8)])
        self.assertIsNone(calibracion_rpe_gym(self.cliente, hoy=HOY))


class MemoriaLoMuestra(TestCase):
    def test_tarjeta_en_memoria(self):
        user = User.objects.create_user(username='calibra_mem', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'C'})
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        base = EjercicioBase.objects.create(nombre='Prensa de Piernas', grupo_muscular='otros', tipo_progresion='peso_reps')
        from django.utils import timezone
        hoy = timezone.localdate()
        for dias, reps, rpe in ((9, 12, 9), (0, 15, 8)):
            e = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=hoy - timedelta(days=dias))
            SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=1, repeticiones=reps,
                                          peso_kg=140, rpe_real=rpe, completado=True)
        self.client.force_login(user)
        from django.urls import reverse
        r = self.client.get(reverse('clientes:memoria_entrenador', args=[cliente.id]))
        self.assertContains(r, 'Tu RPE en fuerza')
        self.assertContains(r, '1 de 1')
