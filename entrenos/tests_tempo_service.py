"""
Phase 64A — Tempo: fuente única para sugerencias de tempo.

`entrenos/services/tempo_service.py` centraliza la sugerencia de tempo por
ejercicio para que voz_entrenador, briefing y la sesión activa hablen desde
el mismo criterio.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from rutinas.models import Rutina
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymDecisionLog
from entrenos.services.tempo_service import (
    get_tempo_sugerido,
    get_mensaje_tempo,
    resolver_tempo_sesion,
)
from entrenos.services.voz_entrenador_service import get_instrucciones
from entrenos.services.briefing_service import get_briefing_gym
from entrenos.views import obtener_ultimo_peso_ejercicio

HOY = date(2026, 6, 13)


class TestGetTempoSugerido(TestCase):
    def test_ejercicio_conocido_devuelve_tempo_especifico(self):
        self.assertEqual(get_tempo_sugerido('Sentadilla con Barra'), '3-1-2')
        self.assertEqual(get_tempo_sugerido('Peso Muerto Rumano'), '2-1-3')

    def test_ejercicio_desconocido_devuelve_generico(self):
        self.assertEqual(get_tempo_sugerido('Ejercicio Desconocido'), '3-1-2')


class TestResolverTempoSesion(TestCase):
    def test_con_tempo_registrado(self):
        self.assertEqual(
            resolver_tempo_sesion('Peso Muerto', tempo_registrado='2-0-X-0'),
            ('2-0-X-0', 'registrado'),
        )

    def test_sin_tempo_registrado(self):
        self.assertEqual(
            resolver_tempo_sesion('Peso Muerto', tempo_registrado=None),
            ('2-1-3', 'sugerido'),
        )

    def test_tempo_registrado_vacio_cae_a_sugerido(self):
        self.assertEqual(
            resolver_tempo_sesion('Peso Muerto', tempo_registrado=''),
            ('2-1-3', 'sugerido'),
        )


class TempoEstancamientoBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_tempo64a', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Rutina test')
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Peso Muerto', accion='cambiar_variante',
            motivo='Sin progresión en 3 sesiones — cambio de estímulo recomendado.',
        )


class TestVozEntrenadorUsaTempoService(TempoEstancamientoBase):
    def test_instruccion_usa_tempo_de_tempo_service(self):
        instrucciones = get_instrucciones(self.cliente, ['Peso Muerto'], HOY)

        instr_estancamiento = next(
            (i for i in instrucciones if i['ejercicio'] == 'Peso Muerto'), None
        )
        self.assertIsNotNone(instr_estancamiento)
        self.assertIn('2-1-3', instr_estancamiento['instruccion'])


class TestBriefingUsaTempoService(TempoEstancamientoBase):
    def test_mensaje_estancamiento_usa_tempo_de_tempo_service(self):
        briefing = get_briefing_gym(
            self.cliente,
            [{'nombre': 'Peso Muerto', 'tipo_ejercicio': 'compuesto_principal'}],
            HOY,
        )

        msg = next((m for m in briefing['mensajes'] if m['tipo'] == 'estancamiento'), None)
        self.assertIsNotNone(msg)
        self.assertIn('2-1-3', msg['texto'])
        self.assertNotIn('(3-1-2)', msg['texto'])


class TestObtenerUltimoPesoEjercicioIncluyeTempo(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_tempo64a_b', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Rutina test')

    def test_devuelve_tempo_registrado(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 6, 1),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Peso Muerto',
            peso_kg=100, series=4, repeticiones=5, tempo='2-0-X-0',
        )

        datos = obtener_ultimo_peso_ejercicio(
            cliente_id=self.cliente.id, nombre_ejercicio='Peso Muerto', fecha_actual=HOY,
        )

        self.assertIsNotNone(datos)
        self.assertEqual(datos['tempo'], '2-0-X-0')
