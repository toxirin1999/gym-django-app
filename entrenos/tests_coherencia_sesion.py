"""Coherencia entre pantallas (14-oct-2026).

El 13-oct el briefing decía "conserva 99,2 kg" y el entrenamiento activo
proponía 102,5 kg para el mismo ejercicio; cada pantalla tenía además su
propia "última vez". Este test monta una sesión con historial real y exige
que el briefing y el entrenamiento activo (por los dos caminos que usa en
producción: el token del briefing y el snapshot de la decisión, cuando el
token se pierde entre procesos) digan el mismo peso y la misma "última vez".
"""

from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado, EntrenoRealizado, GymDecisionVersion, SerieRealizada,
)
from entrenos.services.ultima_sesion_service import ultima_sesion
from rutinas.models import EjercicioBase, Rutina

EJERCICIOS = [
    # nombre, rango, rpe, peso que propondría el plan anual, series de ayer (peso, reps, rpe), tope
    ('Sentadilla Hack', '12-15', 8, 25.0, [(22, 8, 8), (22, 8, 8)], False),
    ('Prensa de Piernas', '12-15', 8, 147.5, [(145, 12, 7), (140, 12, 7), (140, 12, 7)], False),
    ('Elevación de Gemelos de Pie (Máquina)', '15-20', 9, 102.5, [(100, 15, 7), (100, 15, 8)], True),
    ('Elevación de Gemelos Sentado (Máquina)', '15-20', 9, 79.0, [(79, 8, 10), (60, 15, 7)], False),
    ('Low-to-High Cable Fly', '12-15', 9, 25.0, [(15.5, 12, 7), (18, 12, 7), (20, 12, 7)], False),
]


def peso_briefing(ej):
    """El número grande que enseña la tarjeta del briefing (misma lógica que la plantilla)."""
    if ej.get('progresion_aplicada') or ej.get('progresion_pospuesta'):
        return float(ej['peso_kg'])
    return float(ej.get('peso_recomendado_kg') or ej.get('peso_kg') or 0)


class CoherenciaEntrePantallas(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='coherencia', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'C'})
        self.client.force_login(self.user)
        self.hoy = timezone.localdate()
        ayer = self.hoy - timedelta(days=1)
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Hipertrofia')
        entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=ayer)
        entreno.gym_decision_version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=ayer, version=1, decision_id='ayer',
            origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64,
            base_fingerprint='b' * 64, postura='empujar',
            snapshot={'entrenamiento': {'ejercicios': [
                {'nombre': n, 'repeticiones': r} for n, r, *_ in EJERCICIOS
            ]}},
        )
        entreno.save(update_fields=['gym_decision_version'])
        for nombre, _, _, _, series, tope in EJERCICIOS:
            base = EjercicioBase.objects.create(nombre=nombre, grupo_muscular='otros', tipo_progresion='peso_reps')
            EjercicioRealizado.objects.create(
                entreno=entreno, nombre_ejercicio=nombre, peso_kg=sum(p for p, _, _ in series) / len(series),
                series=len(series), repeticiones=series[0][1], rpe=8, completado=True, es_tope_maquina=tope,
            )
            for i, (peso, reps, rpe) in enumerate(series, start=1):
                SerieRealizada.objects.create(
                    entreno=entreno, ejercicio=base, serie_numero=i, repeticiones=reps,
                    peso_kg=peso, rpe_real=rpe, completado=True,
                )
        self.addCleanup(cache.clear)

    def decision_de_hoy(self, *args, **kwargs):
        return {
            'estado': 'entrenar', 'tipo': 'programada_hoy', 'contexto_fisico': {},
            'entrenamiento': {
                'rutina_nombre': 'Dia 2 - Hipertrofia',
                'ejercicios': [
                    {'nombre': n, 'series': 3, 'repeticiones': r, 'rpe_objetivo': rpe,
                     'peso_kg': propuesto, 'tipo_progresion': 'peso_reps', 'grupo_muscular': 'otros'}
                    for n, r, rpe, propuesto, *_ in EJERCICIOS
                ],
            },
        }

    def pantallas(self):
        from entrenos.services.autoridad_diaria_gym_service import resolver_autoridad_diaria_gym
        with patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy',
                   side_effect=self.decision_de_hoy):
            autoridad = resolver_autoridad_diaria_gym(self.cliente, self.hoy)
            decision_id = autoridad['decision_id']
            fecha = self.hoy.strftime('%Y-%m-%d')
            briefing = self.client.get(
                reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id]),
                {'fecha': fecha, 'decision_id': decision_id},
            )
            self.assertEqual(briefing.status_code, 200)
            qs = {k: v[0] for k, v in parse_qs(urlparse(briefing.context['url_sesion']).query).items()}
            activo_token = self.client.get(
                reverse('entrenos:entrenamiento_activo', args=[self.cliente.id]), qs,
            )
            qs_sin_token = {k: v for k, v in qs.items() if k != 'ejercicios_token'}
            activo_snapshot = self.client.get(
                reverse('entrenos:entrenamiento_activo', args=[self.cliente.id]), qs_sin_token,
            )
        self.assertEqual(activo_token.status_code, 200)
        self.assertEqual(activo_snapshot.status_code, 200)
        por_nombre = lambda lista: {e['nombre']: e for e in lista}
        return (
            por_nombre(briefing.context['ejercicios']),
            por_nombre(activo_token.context['ejercicios_planificados']),
            por_nombre(activo_snapshot.context['ejercicios_planificados']),
        )

    def test_briefing_y_entrenamiento_proponen_el_mismo_peso(self):
        briefing, token, snapshot = self.pantallas()
        for nombre, *_ in EJERCICIOS:
            with self.subTest(nombre):
                esperado = peso_briefing(briefing[nombre])
                self.assertAlmostEqual(float(token[nombre]['peso_inicial_kg']), esperado, places=2,
                                       msg=f'{nombre}: activo (token) ≠ briefing')
                self.assertAlmostEqual(float(snapshot[nombre]['peso_inicial_kg']), esperado, places=2,
                                       msg=f'{nombre}: activo (snapshot) ≠ briefing')

    def test_la_ultima_vez_es_la_misma_en_todas(self):
        _, token, snapshot = self.pantallas()
        for nombre, rango, *_ in EJERCICIOS:
            with self.subTest(nombre):
                ref = ultima_sesion(self.cliente, nombre, self.hoy + timedelta(days=1),
                                    reps_min=int(rango.split('-')[0]))['referencia']
                for pantalla in (token, snapshot):
                    self.assertAlmostEqual(float(pantalla[nombre]['peso_anterior_kg']), ref['peso'], places=2)
                    self.assertEqual(int(pantalla[nombre]['repeticiones_anterior']), round(float(ref['reps'])))

    def test_las_reglas_de_peso_se_respetan_en_lo_que_se_ve(self):
        briefing, *_ = self.pantallas()
        self.assertEqual(peso_briefing(briefing['Sentadilla Hack']), 20.0)          # 22 × 8 → baja
        self.assertEqual(peso_briefing(briefing['Elevación de Gemelos Sentado (Máquina)']), 60.0)
        self.assertEqual(peso_briefing(briefing['Elevación de Gemelos de Pie (Máquina)']), 100.0)  # tope
        self.assertLessEqual(peso_briefing(briefing['Low-to-High Cable Fly']), 22.5)   # un salto como mucho


class CoherenciaConTopeGuardadoYDecisionesPendientes(CoherenciaEntrePantallas):
    """Lo mismo, con un tope guardado (100) distinto del último peso (100,5)
    y decisiones pendientes del cierre anterior (subir la prensa y el fly)."""

    def setUp(self):
        super().setUp()
        from entrenos.models import GymDecisionLog, TopeMaquinaGym
        TopeMaquinaGym.objects.create(
            cliente=self.cliente, ejercicio_normalizado='elevación de gemelos de pie (máquina)',
            ejercicio='Elevación de Gemelos de Pie (Máquina)', peso_max_kg=100,
        )
        SerieRealizada.objects.filter(ejercicio__nombre='Elevación de Gemelos de Pie (Máquina)').update(peso_kg=100.5)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        for nombre, peso in (('prensa de piernas', 145), ('low-to-high cable fly', 20)):
            GymDecisionLog.objects.create(
                cliente=self.cliente, ejercicio=nombre, ejercicio_normalizado=nombre,
                entreno_origen=entreno, accion='subir_peso', valor_cambio=5,
                peso_anterior=peso, reps_anteriores=12, rpe_anterior=7, motivo='x',
            )

    def test_el_tope_guardado_manda_en_todas(self):
        briefing, token, snapshot = self.pantallas()
        nombre = 'Elevación de Gemelos de Pie (Máquina)'
        self.assertEqual(peso_briefing(briefing[nombre]), 100.0)
        self.assertEqual(float(token[nombre]['peso_inicial_kg']), 100.0)
        self.assertEqual(float(snapshot[nombre]['peso_inicial_kg']), 100.0)
        self.assertTrue(token[nombre]['sugerencia_tope'])
        self.assertTrue(snapshot[nombre]['sugerencia_tope'])

    def test_las_reglas_de_peso_se_respetan_en_lo_que_se_ve(self):
        briefing, *_ = self.pantallas()
        self.assertEqual(peso_briefing(briefing['Prensa de Piernas']), 145.0)  # doble progresión: 12 de 15
        self.assertEqual(peso_briefing(briefing['Low-to-High Cable Fly']), 20.0)
