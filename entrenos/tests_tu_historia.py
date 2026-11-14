"""14-nov-2026 · Tu historia en el gym (panel provisional tipo resumen anual)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from entrenos.services.tu_historia_service import calcular_historia, sesiones_limpias
from rutinas.models import Rutina

HOY = date(2026, 11, 14)


class TuHistoriaBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='historia', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'H'})
        self.rutina = Rutina.objects.create(nombre='Dia 1 - Hipertrofia')

    def entreno(self, fecha, kg, minutos=60, nombre=None):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            volumen_total_kg=Decimal(kg), duracion_minutos=minutos,
            nombre_rutina_liftin=nombre,
        )


class LimpiezaTests(TuHistoriaBase):
    def test_descarta_dias_de_prueba_duplicados_y_sin_volumen(self):
        for _ in range(3):  # día de pruebas de la app
            self.entreno(date(2025, 8, 7), 1530)
        self.entreno(date(2025, 8, 25), 5420, 50)
        self.entreno(date(2025, 9, 1), 6000)
        self.entreno(date(2025, 9, 1), 6000)  # duplicado
        self.entreno(date(2025, 9, 2), 0)     # sin volumen
        sesiones = sesiones_limpias(self.cliente, HOY)
        self.assertEqual([s.fecha for s in sesiones], [date(2025, 8, 25), date(2025, 9, 1)])

    def test_duracion_absurda_cuenta_como_desconocida(self):
        self.entreno(date(2026, 8, 10), 27875, 1478)
        self.assertIsNone(sesiones_limpias(self.cliente, HOY)[0].minutos)


class CalculoTests(TuHistoriaBase):
    def setUp(self):
        super().setUp()
        self.entreno(date(2025, 10, 6), 50000, 50, 'Dia 1 - Hipertrofia_Final')
        self.entreno(date(2025, 10, 8), 64000, 40)
        self.entreno(date(2025, 11, 3), 30000, None)  # sin duración
        self.entreno(date(2026, 10, 5), 150000, 70)
        self.grande = self.entreno(date(2026, 10, 7), 130000, 80)
        self.entreno(date(2026, 11, 9), 13950, 60)
        EjercicioRealizado.objects.create(entreno=self.grande, nombre_ejercicio='Jalón al Pecho', series=4)
        e = EntrenoRealizado.objects.filter(fecha=date(2026, 10, 5)).first()
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio='jalón al pecho ', series=3)
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio='Curl Martillo', series=3)

    def test_totales(self):
        h = calcular_historia(self.cliente, HOY)
        self.assertEqual(h['primera']['fecha'], '6 de octubre de 2025')
        self.assertEqual(h['primera']['nombre'], 'Dia 1 - Hipertrofia_Final')
        self.assertEqual(h['sesiones'], 6)
        self.assertEqual(h['dias'], 6)
        self.assertEqual(h['toneladas'], '438')
        # 300 min conocidos + 1 sesión estimada con la media (60) = 6 h
        self.assertEqual(h['horas'], 6)
        self.assertEqual(h['horas_estimadas'], 1)

    def test_meses_y_constancia(self):
        h = calcular_historia(self.cliente, HOY)
        self.assertEqual(h['meses_total'], 14)
        self.assertEqual(h['meses_con_entreno'], 4)
        self.assertEqual(h['barras'][0]['alto'], 100)
        self.assertEqual(h['racha_semanas'], 1)

    def test_compara_el_ultimo_mes_completo_con_el_de_hace_un_anio(self):
        c = calcular_historia(self.cliente, HOY)['comparacion']
        self.assertEqual((c['antes_mes'], c['ahora_mes']), ('Octubre 2025', 'Octubre 2026'))
        self.assertEqual((c['antes_t'], c['ahora_t']), ('114', '280'))
        self.assertEqual(c['factor'], '2,5')
        self.assertTrue(c['sube'])

    def test_dia_mas_grande_y_ejercicio_mas_repetido(self):
        h = calcular_historia(self.cliente, HOY)
        self.assertEqual(h['mayor']['t'], '150,0')
        self.assertEqual(h['ejercicio']['nombre'], 'Jalón al Pecho')
        self.assertEqual(h['ejercicio']['entrenos'], 2)
        self.assertEqual(h['ejercicio']['series'], 7)

    def test_sin_mes_anterior_no_hay_comparacion(self):
        EntrenoRealizado.objects.filter(fecha__year=2025).delete()
        self.assertIsNone(calcular_historia(self.cliente, HOY)['comparacion'])

    def test_sin_entrenos_no_hay_historia(self):
        EntrenoRealizado.objects.all().delete()
        self.assertIsNone(calcular_historia(self.cliente, HOY))


class VistaTests(TuHistoriaBase):
    def test_pagina_y_acceso_desde_memoria(self):
        self.entreno(date(2025, 10, 6), 50000, 50)
        self.client.force_login(self.user)
        url = reverse('entrenos:tu_historia', args=[self.cliente.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Tu historia')
        self.assertContains(r, '6 de octubre de 2025')
        memoria = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertContains(memoria, url)

    def test_otro_usuario_no_ve_la_historia(self):
        otro = User.objects.create_user(username='otro', password='x')
        self.client.force_login(otro)
        r = self.client.get(reverse('entrenos:tu_historia', args=[self.cliente.id]))
        self.assertEqual(r.status_code, 404)

    def test_sin_entrenos_la_pagina_no_falla(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('entrenos:tu_historia', args=[self.cliente.id]))
        self.assertContains(r, 'Todavía no hay entrenos registrados')
