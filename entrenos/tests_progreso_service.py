"""
Phase 64D — Memoria compacta de progreso en el portal.

`entrenos/services/progreso_service.py` centraliza:
- calcular_sugerencia_tope: detección de tope de máquina (mismo peso, +1 rep)
- detectar_estancamiento: GymDecisionLog activo de "Sin progresión"
- calcular_comparacion_peso: comparación peso recomendado vs última vez

Estos tests cubren las funciones puras del servicio, su uso en
`vista_entrenamiento_activo` (no debe cambiar valores previos) y la
renderización compacta "Última vez" + chips en `portal_sesion.html`.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymDecisionLog
from rutinas.models import Rutina
from entrenos.services.progreso_service import (
    calcular_sugerencia_tope,
    detectar_estancamiento,
    calcular_comparacion_peso,
)

HOY = date(2026, 6, 14)


# ---------------------------------------------------------------------------
# 1. calcular_sugerencia_tope
# ---------------------------------------------------------------------------
class TestCalcularSugerenciaTope(TestCase):
    def test_tope_maquina_sugiere_mas_una_rep(self):
        datos_anterior = {'peso': 50.0, 'repeticiones': 10, 'es_tope_maquina': True}
        sugerencia, reps = calcular_sugerencia_tope(datos_anterior)
        self.assertTrue(sugerencia)
        self.assertEqual(reps, 11)

    def test_sin_tope_no_sugiere(self):
        datos_anterior = {'peso': 50.0, 'repeticiones': 10, 'es_tope_maquina': False}
        sugerencia, reps = calcular_sugerencia_tope(datos_anterior)
        self.assertFalse(sugerencia)
        self.assertIsNone(reps)

    def test_sin_datos_anterior_no_sugiere(self):
        sugerencia, reps = calcular_sugerencia_tope(None)
        self.assertFalse(sugerencia)
        self.assertIsNone(reps)


# ---------------------------------------------------------------------------
# 2. detectar_estancamiento
# ---------------------------------------------------------------------------
class TestDetectarEstancamiento(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_progreso_estanc', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def test_con_decision_log_activo_detecta_estancamiento(self):
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Peso Muerto', accion='cambiar_variante',
            motivo='Sin progresión en 3 sesiones — cambio de estímulo recomendado.',
        )
        self.assertTrue(detectar_estancamiento(self.cliente, 'Peso Muerto', HOY))

    def test_sin_decision_log_no_detecta_estancamiento(self):
        self.assertFalse(detectar_estancamiento(self.cliente, 'Peso Muerto', HOY))


# ---------------------------------------------------------------------------
# 3. calcular_comparacion_peso
# ---------------------------------------------------------------------------
class TestCalcularComparacionPeso(TestCase):
    def test_subida(self):
        comparacion = calcular_comparacion_peso(82.5, 80.0)
        self.assertEqual(comparacion['direccion'], 'subida')
        self.assertEqual(comparacion['delta'], 2.5)

    def test_bajada(self):
        comparacion = calcular_comparacion_peso(77.5, 80.0)
        self.assertEqual(comparacion['direccion'], 'bajada')
        self.assertEqual(comparacion['delta'], -2.5)

    def test_igual(self):
        comparacion = calcular_comparacion_peso(80.0, 80.0)
        self.assertEqual(comparacion['direccion'], 'igual')
        self.assertEqual(comparacion['delta'], 0.0)

    def test_sin_historico_devuelve_none(self):
        self.assertIsNone(calcular_comparacion_peso(80.0, None))
        self.assertIsNone(calcular_comparacion_peso(80.0, 0))


# ---------------------------------------------------------------------------
# 4-7. Render en portal_sesion.html
# ---------------------------------------------------------------------------
_OBTENER_PROXIMO_PATH = 'clientes.views.obtener_proximo_entrenamiento'


class PortalSesionProgresoBase(TestCase):
    """portal_sesion.html (clientes:portal_sesion) solo construye
    rutina_ajustada si hay un check-in (BitacoraDiaria) de hoy."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_progreso_portal', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = date.today()
        BitacoraDiaria.objects.create(
            cliente=self.cliente, energia_subjetiva=10, dolor_articular=0, horas_sueno=10,
        )

    def _get(self, ejercicio):
        plan = {'fecha': self.hoy, 'ejercicios': [ejercicio]}
        c = Client()
        c.login(username='tester_progreso_portal', password='x')
        url = reverse('clientes:portal_sesion', args=[self.cliente.id])
        with patch(_OBTENER_PROXIMO_PATH, return_value=plan):
            return c.get(url)

    def _ejercicio_base(self, nombre='Peso Muerto', peso_kg=82.5):
        return {
            'nombre': nombre, 'grupo_muscular': 'pierna',
            'tipo_ejercicio': 'compuesto_principal', 'peso_kg': peso_kg,
            'series': 4, 'repeticiones': '5', 'rpe_objetivo': 7,
        }


class TestPortalConHistoricoMuestraUltimaVez(PortalSesionProgresoBase):
    def test_con_historico_muestra_ultima_vez(self):
        rutina = Rutina.objects.create(nombre='Rutina test')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina, fecha=self.hoy - timedelta(days=7),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Peso Muerto',
            peso_kg=80.0, series=4, repeticiones=5,
        )

        response = self._get(self._ejercicio_base(peso_kg=82.5))
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertEqual(ej['peso_anterior_kg'], 80.0)
        self.assertEqual(ej['comparacion_peso']['direccion'], 'subida')

        html = response.content.decode()
        self.assertIn('Última vez', html)
        self.assertIn('80.0 kg', html)
        self.assertIn('+2.5 kg', html)


class TestPortalSinHistoricoNoMuestraUltimaVez(PortalSesionProgresoBase):
    def test_sin_historico_no_muestra_ultima_vez(self):
        response = self._get(self._ejercicio_base())
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertIsNone(ej['peso_anterior_kg'])
        self.assertIsNone(ej['comparacion_peso'])

        html = response.content.decode()
        self.assertNotIn('Última vez', html)


class TestPortalChipTope(PortalSesionProgresoBase):
    def test_chip_tope_aparece_cuando_hay_tope_de_maquina(self):
        rutina = Rutina.objects.create(nombre='Rutina test')
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina, fecha=self.hoy - timedelta(days=7),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press de Pierna',
            peso_kg=120.0, series=4, repeticiones=10, es_tope_maquina=True,
        )

        response = self._get(self._ejercicio_base(nombre='Press de Pierna', peso_kg=120.0))
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertTrue(ej['sugerencia_tope'])
        self.assertEqual(ej['reps_sugeridas_tope'], 11)

        html = response.content.decode()
        self.assertIn('🔝', html)
        self.assertIn('+1 rep', html)


class TestPortalChipEstancado(PortalSesionProgresoBase):
    def test_chip_estancado_aparece_cuando_hay_decision_log_activo(self):
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Peso Muerto', accion='cambiar_variante',
            motivo='Sin progresión en 3 sesiones — cambio de estímulo recomendado.',
        )

        response = self._get(self._ejercicio_base())
        self.assertEqual(response.status_code, 200)

        ej = response.context['rutina_ajustada']['ejercicios'][0]
        self.assertTrue(ej['estancado'])

        html = response.content.decode()
        self.assertIn('⚡', html)
        self.assertIn('Estancado', html)


# ---------------------------------------------------------------------------
# 8. vista_entrenamiento_activo mantiene valores previos tras delegar
# ---------------------------------------------------------------------------
class TestVistaEntrenamientoActivoMantieneValores(TestCase):
    """Tras delegar tope/estancamiento a progreso_service, el comportamiento
    de vista_entrenamiento_activo no debe cambiar."""

    def setUp(self):
        self.user = User.objects.create_user('tester_progreso_activo', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Rutina test')

    def test_tope_de_maquina_se_mantiene_en_vista_activa(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 6, 1),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press de Pierna',
            peso_kg=120.0, series=4, repeticiones=10, es_tope_maquina=True,
        )

        from entrenos.views import obtener_ultimo_peso_ejercicio
        datos_anterior = obtener_ultimo_peso_ejercicio(
            cliente_id=self.cliente.id, nombre_ejercicio='Press de Pierna', fecha_actual=HOY,
        )

        sugerencia, reps = calcular_sugerencia_tope(datos_anterior)
        self.assertTrue(sugerencia)
        self.assertEqual(reps, 11)

    def test_estancamiento_se_mantiene_en_vista_activa(self):
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Peso Muerto', accion='cambiar_variante',
            motivo='Sin progresión en 3 sesiones — cambio de estímulo recomendado.',
        )

        self.assertTrue(detectar_estancamiento(self.cliente, 'Peso Muerto', HOY))
