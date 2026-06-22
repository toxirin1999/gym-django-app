"""
Phase Gym Peso 2 — Carga dependiente de fase.

Regla madre: el último peso no es la recomendación, es evidencia para
estimar capacidad (e1RM). Estos tests validan que el cálculo dependiente
de fase gobierna en los TRES sitios donde hoy se decide el peso:

  1. analytics/planificador_helms/core.py        (generación del plan)
  2. entrenos/models.py GymDecisionLog.peso_sugerido (pisa downstream)
  3. entrenos/views.py vista_entrenamiento_activo  (lo que ve el usuario)

Caso real que disparó esta fase: 107.5kg x 3 reps (fase potencia) →
hoy Descarga Activa, objetivo 10 reps, RPE bajo. El sistema NO puede
proponer 105kg (= 107.5 - 2.5, incremento fijo de siempre); debe
recalcular desde e1RM con reducción de descarga.
"""

import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymDecisionLog
from rutinas.models import Rutina


class ProgresionDependienteFaseBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_pgp2', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.cliente.dias_disponibles = 4
        self.cliente.save()
        self.rutina = Rutina.objects.create(nombre='Test Rutina PGP2', programa=None)
        self.client = Client()
        self.client.login(username='tester_pgp2', password='x')

    def _crear_entreno_historico(self, nombre_ejercicio, peso_kg, repeticiones, rpe, fecha):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=nombre_ejercicio,
            peso_kg=peso_kg,
            series=3,
            repeticiones=repeticiones,
            rpe=rpe,
            completado=True,
        )
        return entreno

    def _ejercicio_payload(self, nombre, rep_range, rpe_objetivo, peso_kg_plan=0.0):
        return {
            'nombre': nombre,
            'grupo_muscular': 'piernas',
            'tipo_ejercicio': 'compuesto_principal',
            'peso_kg': peso_kg_plan,
            'series': 3,
            'repeticiones': rep_range,
            'rpe_objetivo': rpe_objetivo,
            'tipo_progresion': 'peso_reps',
        }

    def _get_entrenamiento_activo(self, ejercicios, fecha=None):
        fecha = fecha or date.today()
        return self.client.get(
            reverse('entrenos:entrenamiento_activo', kwargs={'cliente_id': self.cliente.id}),
            {
                'fecha': fecha.isoformat(),
                'rutina_nombre': 'Test',
                'ejercicios': json.dumps([ejercicios] if isinstance(ejercicios, dict) else ejercicios),
            },
        )


# ── Test 1: el caso roto — 107.5kg x 3 reps (potencia) → hoy descarga 10 reps ─

class TestCasoRotoDescargaTrasPotencia(ProgresionDependienteFaseBase):
    """
    El resultado NO puede ser 105kg (peso_anterior - incremento fijo de
    siempre). Debe ser un recálculo por e1RM con reducción de descarga,
    sustancialmente menor que el carry-forward roto.
    """

    def test_no_propone_105kg_por_arrastre(self):
        self._crear_entreno_historico(
            'Sentadilla con Barra', peso_kg=107.5, repeticiones=3, rpe=8,
            fecha=date(2026, 6, 1),
        )

        response = self._get_entrenamiento_activo(
            self._ejercicio_payload('Sentadilla con Barra', '10-15', rpe_objetivo=6),
        )
        self.assertEqual(response.status_code, 200)

        ejercicios_ctx = response.context['ejercicios_planificados']
        ej = ejercicios_ctx[0]

        peso_mostrado = float(ej.get('peso_inicial_kg') or 0)

        # El bug roto proponía 105.0 (107.5 - 2.5kg incremento fijo).
        self.assertNotAlmostEqual(peso_mostrado, 105.0, delta=0.01,
            msg="El peso sigue siendo el carry-forward roto (107.5 - 2.5kg fijo)")
        # Debe ser una reducción real, no el peso anterior intacto tampoco.
        self.assertLess(peso_mostrado, 95.0,
            msg=f"Peso {peso_mostrado} no refleja una reducción real de descarga")
        self.assertGreater(peso_mostrado, 0)


# ── Test 2: Client() real, motivo visible debe reflejar el recálculo ────────

class TestMotivoVisibleRecalculoFase(ProgresionDependienteFaseBase):
    """
    El motivo mostrado debe distinguir 'recalculado por fase/descarga' de un
    carry-forward silencioso. No basta con que el número cambie: el usuario
    debe poder ver por qué.
    """

    def test_motivo_no_es_carry_forward_silencioso(self):
        self._crear_entreno_historico(
            'Sentadilla con Barra', peso_kg=107.5, repeticiones=3, rpe=8,
            fecha=date(2026, 6, 1),
        )

        response = self._get_entrenamiento_activo(
            self._ejercicio_payload('Sentadilla con Barra', '10-15', rpe_objetivo=6),
        )
        self.assertEqual(response.status_code, 200)

        ej = response.context['ejercicios_planificados'][0]

        motivo = ej.get('motivo_peso') or {}
        self.assertIn(motivo.get('tipo'), ('recalculado_fase', 'recalculado_descarga'),
            msg=f"motivo_peso={motivo} no refleja un recálculo por fase/descarga")

        peso_mostrado = float(ej.get('peso_inicial_kg') or 0)
        self.assertLess(peso_mostrado, 95.0)


# ── Test 3: no regresión — bucket compatible, RPE bajo → sigue progresando ──

class TestNoRegresionProgresionCompatible(ProgresionDependienteFaseBase):
    """
    Misma familia de fase (p.ej. hipertrofia 10 reps → hipertrofia 8-10
    reps hoy), RPE bajo: debe poder seguir subiendo +1.25/+2.5kg como hoy,
    sin que el recálculo por e1RM lo sustituya.
    """

    def test_bucket_compatible_sigue_subiendo_incremento_fijo(self):
        self._crear_entreno_historico(
            'Press Banca con Barra', peso_kg=80.0, repeticiones=10, rpe=6,
            fecha=date(2026, 6, 1),
        )

        response = self._get_entrenamiento_activo(
            self._ejercicio_payload('Press Banca con Barra', '8-10', rpe_objetivo=8),
        )
        self.assertEqual(response.status_code, 200)

        ej = response.context['ejercicios_planificados'][0]
        peso_mostrado = float(ej.get('peso_inicial_kg') or 0)

        # El carry-forward (80kg, sin progresión ejecutiva en core.py vía
        # querystring) debe mantenerse cerca del peso anterior, no caer a un
        # valor muy distinto por un recálculo de fase que no debería activarse.
        self.assertGreaterEqual(peso_mostrado, 75.0)
        self.assertLessEqual(peso_mostrado, 90.0)


# ── Test 4: doble vía — el comportamiento depende de TODO el camino e2e ─────

class TestDobleViaGymDecisionLogYPlan(ProgresionDependienteFaseBase):
    """
    Si GymDecisionLog.peso_sugerido sigue ciego a fase/reps (o si el plan
    sigue ciego pero el log no), el resultado final que ve el usuario en
    vista_entrenamiento_activo debe seguir siendo incorrecto y este test
    debe fallar. Se prueba el camino GymDecisionLog → plan_dinamico_service
    → vista_entrenamiento_activo con un log 'subir_peso' pendiente que
    arrastra reps/RPE de un bucket de potencia, sobre un ejercicio cuya
    sesión de HOY es claramente de bucket distinto (descarga/hipertrofia).
    """

    def test_log_pendiente_con_bucket_incompatible_no_aplica_incremento_fijo(self):
        from unittest.mock import patch

        self._crear_entreno_historico(
            'Sentadilla con Barra', peso_kg=107.5, repeticiones=3, rpe=8,
            fecha=date(2026, 6, 1),
        )
        log = GymDecisionLog.objects.create(
            cliente=self.cliente,
            ejercicio='sentadilla con barra',
            peso_anterior=107.5,
            reps_anteriores=3,
            rpe_anterior=8,
            accion='subir_peso',
            valor_cambio=5.0,  # incremento porcentual legacy — NO debe gobernar aquí
            motivo='RPE bajo en la última sesión de potencia.',
            resultado=None,
        )

        permiso_ok = {
            'accion': 'progresion_permitida', 'motivo': 'ok',
            'mensaje': 'Semana con margen.',
            'aplica_a_principales': False, 'aplica_a_accesorios': False,
            'hay_datos_semana': True,
        }
        permiso_local_ok = {'puede_subir': True, 'motivo': None, 'mensaje': None}

        with patch(
            'entrenos.services.progresion_contextual_service.evaluar_permiso_progresion',
            return_value=permiso_ok,
        ), patch(
            'entrenos.services.progresion_contextual_service.evaluar_permiso_local_ejercicio',
            return_value=permiso_local_ok,
        ), patch(
            'entrenos.services.briefing_service.necesita_deload_gym',
            return_value=False,
        ):
            response = self._get_entrenamiento_activo(
                self._ejercicio_payload('Sentadilla con Barra', '10-15', rpe_objetivo=6),
            )

        self.assertEqual(response.status_code, 200)
        ej = response.context['ejercicios_planificados'][0]
        peso_mostrado = float(ej.get('peso_inicial_kg') or ej.get('peso_recomendado_kg') or 0)

        # GymDecisionLog.peso_sugerido "ciego" hubiera dado 107.5 * 1.05 = 112.5kg.
        # Ese resultado es absurdo para una sesión de descarga a 10-15 reps.
        self.assertNotAlmostEqual(peso_mostrado, 112.5, delta=0.01,
            msg="GymDecisionLog.peso_sugerido sigue ciego a fase/reps (incremento legacy aplicado)")
        self.assertLess(peso_mostrado, 95.0,
            msg=f"Peso final {peso_mostrado} no refleja recálculo por fase/descarga end-to-end")

        log.refresh_from_db()


# ── Test 5: transición potencia → fuerza (bucket compatible, no recalcula) ──

class TestTransicionPotenciaFuerzaCompatible(ProgresionDependienteFaseBase):
    """
    Potencia (2-5 reps) y Fuerza (3-6 reps) comparten la misma familia de
    estímulo de cara a la pregunta "¿el mismo peso sigue teniendo sentido?".
    La regla de compatibilidad no es "todo cambio de reps = incompatible":
    se basa en los buckets reales confirmados en config.py /
    periodizacion/generador.py.
    """

    def test_potencia_a_fuerza_no_dispara_recalculo_por_fase(self):
        self._crear_entreno_historico(
            'Peso Muerto con Barra', peso_kg=140.0, repeticiones=3, rpe=7,
            fecha=date(2026, 6, 1),
        )

        response = self._get_entrenamiento_activo(
            self._ejercicio_payload('Peso Muerto con Barra', '4-6', rpe_objetivo=8),
        )
        self.assertEqual(response.status_code, 200)

        ej = response.context['ejercicios_planificados'][0]
        motivo = ej.get('motivo_peso') or {}

        self.assertNotIn(motivo.get('tipo'), ('recalculado_fase', 'recalculado_descarga'),
            msg="Potencia→Fuerza no debería disparar recálculo por fase: mismo bucket")
