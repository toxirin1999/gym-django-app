"""Check-in automático desde la app Salud (Health Auto Export, 14-oct-2026)."""

import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import BitacoraDiaria, Cliente
from clientes.salud_iphone_service import leer_metricas


def payload(hoy):
    ayer = hoy - timedelta(days=1)
    return {'data': {'metrics': [
        {'name': 'sleep_analysis', 'units': 'hr', 'data': [
            {'date': hoy.isoformat(), 'totalSleep': 7.25, 'asleep': 7.25, 'inBed': 8.0,
             'sleepStart': f'{ayer} 23:40:00 +0200', 'sleepEnd': f'{hoy} 07:01:00 +0200'},
        ]},
        {'name': 'resting_heart_rate', 'units': 'count/min', 'data': [
            {'date': f'{hoy} 00:00:00 +0200', 'qty': 51.6},
        ]},
        {'name': 'heart_rate_variability', 'units': 'ms', 'data': [
            {'date': f'{hoy} 06:50:00 +0200', 'qty': 44},
            {'date': f'{hoy} 08:10:00 +0200', 'qty': 52},
        ]},
        {'name': 'step_count', 'units': 'count', 'data': [{'date': f'{hoy} 00:00:00 +0200', 'qty': 900}]},
    ], 'workouts': []}}


class LeerMetricas(TestCase):
    def test_agregado(self):
        hoy = date(2026, 10, 15)
        self.assertEqual(leer_metricas(payload(hoy)), {hoy: {'horas_sueno': 7.25, 'fc_reposo': 52, 'hrv_ms': 48}})

    def test_sueno_por_tramos_cuenta_el_dia_de_despertar_y_no_lo_despierto(self):
        datos = {'data': {'metrics': [{'name': 'sleep_analysis', 'units': 'min', 'data': [
            {'startDate': '2026-10-14 23:30:00 +0200', 'endDate': '2026-10-15 02:30:00 +0200', 'qty': 180, 'value': 'Core'},
            {'startDate': '2026-10-15 02:30:00 +0200', 'endDate': '2026-10-15 02:45:00 +0200', 'qty': 15, 'value': 'Awake'},
            {'startDate': '2026-10-15 02:45:00 +0200', 'endDate': '2026-10-15 06:45:00 +0200', 'qty': 240, 'value': 'Deep'},
        ]}]}}
        self.assertEqual(leer_metricas(datos), {date(2026, 10, 15): {'horas_sueno': 7.0}})

    def test_json_raro_no_rompe(self):
        for raro in (None, {}, {'data': []}, {'data': {'metrics': 'x'}}, {'data': {'metrics': [1, {'name': 'sleep_analysis', 'data': [{'date': 'nope'}]}]}}):
            self.assertEqual(leer_metricas(raro), {})


class Endpoint(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='salud', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'S'})
        self.token = self.cliente.get_or_create_api_token()
        self.url = reverse('clientes:api_salud_iphone')
        self.hoy = timezone.localdate()
        self.addCleanup(cache.clear)

    def post(self, cuerpo, token=None):
        cabeceras = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
        return self.client.post(self.url, data=json.dumps(cuerpo), content_type='application/json', **cabeceras)

    def test_sin_token_o_token_malo(self):
        self.assertEqual(self.post(payload(self.hoy)).status_code, 401)
        self.assertEqual(self.post(payload(self.hoy), token='otro').status_code, 401)
        self.assertFalse(BitacoraDiaria.objects.exists())

    def test_rellena_el_checkin_de_hoy_sin_tocar_la_energia(self):
        BitacoraDiaria.objects.create(cliente=self.cliente, energia_subjetiva=7)
        r = self.post(payload(self.hoy), token=self.token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['dias'], {self.hoy.isoformat(): {'horas_sueno': 7.25, 'fc_reposo': 52, 'hrv_ms': 48}})
        b = BitacoraDiaria.objects.get(cliente=self.cliente, fecha=self.hoy)
        self.assertEqual((float(b.horas_sueno), b.fc_reposo, b.hrv_ms, b.energia_subjetiva), (7.25, 52, 48, 7))

    def test_crea_el_dia_de_ayer_con_su_fecha_e_ignora_lo_antiguo(self):
        ayer = self.hoy - timedelta(days=1)
        viejo = self.hoy - timedelta(days=30)
        cuerpo = payload(ayer)
        cuerpo['data']['metrics'][0]['data'].append({'date': viejo.isoformat(), 'totalSleep': 6})
        self.post(cuerpo, token=self.token)
        self.assertEqual(list(BitacoraDiaria.objects.values_list('fecha', flat=True)), [ayer])

    def test_el_sueno_cierra_el_checkin_de_ahora(self):
        self.client.force_login(self.user)
        antes = self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertTrue(antes.context['quiet_week']['checkin_pendiente'])
        self.post(payload(self.hoy), token=self.token)
        despues = self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertFalse(despues.context['quiet_week']['checkin_pendiente'])

    def test_pagina_de_configuracion(self):
        self.client.force_login(self.user)
        self.post(payload(self.hoy), token=self.token)
        r = self.client.get(reverse('clientes:salud_iphone'))
        self.assertContains(r, f'Bearer {self.token}')
        self.assertContains(r, '/clientes/api/salud-iphone/')
        self.assertContains(r, 'sueño 7 h 15')

    def test_sin_energia_en_el_checkin_se_ve_la_del_ultimo_entreno(self):
        from entrenos.models import EntrenoRealizado
        from rutinas.models import Rutina
        ayer = self.hoy - timedelta(days=1)
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=Rutina.objects.create(nombre='Dia 1'),
                                        fecha=ayer, energia_pre_sesion=7)
        self.post(payload(self.hoy), token=self.token)
        self.client.force_login(self.user)
        r = self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertEqual(r.context['quiet_week']['energia_entreno'], {'valor': 7, 'fecha': ayer})
        self.assertContains(r, 'Al empezar el entreno · ' + ayer.strftime('%d/%m'))


class PesoDesdeSalud(TestCase):
    def test_el_peso_va_a_peso_diario(self):
        from clientes.models import PesoDiario
        from clientes.salud_iphone_service import guardar_checkin_iphone
        user = User.objects.create_user(username='peso-salud', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'P'})
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)
        guardado = guardar_checkin_iphone(cliente, {'data': {'metrics': [
            {'name': 'weight_body_mass', 'units': 'kg', 'data': [
                {'date': f'{ayer} 07:10:00 +0200', 'qty': 84.9},
                {'date': f'{hoy} 07:05:00 +0200', 'qty': 85.3},
                {'date': f'{hoy} 21:00:00 +0200', 'qty': 84.6},
            ]},
        ]}}, hoy=hoy)
        self.assertEqual(guardado[hoy.isoformat()], {'peso_kg': 84.6})
        pesos = {p.fecha: float(p.peso_kg) for p in PesoDiario.objects.filter(cliente=cliente)}
        self.assertEqual(pesos, {ayer: 84.9, hoy: 84.6})
        self.assertFalse(BitacoraDiaria.objects.filter(cliente=cliente).exists())
