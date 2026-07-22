# entrenos/test_x3_ancla_vista_activa.py
"""
Tests TDD para X.3 — suavizado de ancla histórica en vista_entrenamiento_activo.

Qué hace X.3:
  `obtener_ancla_ejercicio(cliente_id, nombre_ejercicio, fecha_actual, referencia)`
  pondera las N sesiones de EjercicioRealizado del mismo bucket que la referencia
  (ventana 42 días, pesos 0.5/0.3/0.2 renormalizados) y pasa el ancla suavizada a
  `resolver_peso_objetivo` en lugar de la sesión literal más reciente.

Separación cálculo/display (invariante principal):
  - `peso_anterior_kg` (display) sigue siendo la sesión más reciente.
  - `peso_inicial_kg` (cálculo) usa el ancla suavizada si hay suficiente historial.

Tests rojos antes de X.3 (fallan sin implementación):
  - Test 2: 3 sesiones mismo bucket → peso_inicial_kg < resultado con solo la más reciente.

Tests de regresión (pasan antes y después):
  - Test 1: 1 sola sesión → peso_inicial_kg idéntico (propiedad de seguridad N=1).
  - Test 3: display/cálculo separados — peso_anterior_kg = sesión más reciente; peso_inicial_kg = ancla.
  - Test 4: tope de máquina → peso_inicial_kg = peso de la última sesión (ancla nunca interfiere).

Todos los tests usan `Client().get()` para verificar la vista real, no solo la función
auxiliar, cumpliendo el feedback explícito del proyecto: verificar con la app real.
"""
import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client as DjangoClient
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from rutinas.models import Rutina


NOMBRE_EJ = 'Curl X3Test Biceps'   # nombre único, nunca en catálogo real


class BaseX3Vista(TestCase):
    """Setup común: usuario, cliente, rutina y cliente Django de test."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_x3_ancla_vista',
            password='testpass_x3',
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestX3Vista', 'dias_disponibles': 4},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_x3_rutina')
        self.http = DjangoClient()
        self.http.force_login(self.user)

    def _crear_entreno(self, delta_dias: int) -> EntrenoRealizado:
        return EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today() - timedelta(days=delta_dias),
        )

    def _crear_ej(self, entreno, peso, reps, rpe, es_tope=False) -> EjercicioRealizado:
        return EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=NOMBRE_EJ,
            peso_kg=peso,
            repeticiones=reps,
            rpe=rpe,
            es_tope_maquina=es_tope,
        )

    def _ejercicio_hoy(self, reps='10-12', rpe_obj=8):
        """Dict mínimo inyectable en la vista via GET param 'ejercicios'."""
        return {
            'nombre': NOMBRE_EJ,
            'repeticiones': reps,
            'rpe_objetivo': rpe_obj,
            'series': 3,
            'peso_recomendado_kg': 0,
            'usa_peso': True,
            'tipo_ejercicio': 'aislamiento',
        }

    def _get_vista(self, reps_hoy='10-12', rpe_obj=8):
        """Llama la vista real via HTTP GET e inyecta un ejercicio en JSON."""
        ejercicios_json = json.dumps([self._ejercicio_hoy(reps=reps_hoy, rpe_obj=rpe_obj)])
        url = reverse('entrenos:entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})
        fecha_hoy = date.today().strftime('%Y-%m-%d')
        return self.http.get(url, {
            'fecha': fecha_hoy,
            'ejercicios': ejercicios_json,
        })

    def _ej_contexto(self, response):
        """Extrae el primer ejercicio del contexto de la respuesta."""
        self.assertEqual(
            response.status_code, 200,
            f"La vista redirigió (¿excepción interna?). status={response.status_code}",
        )
        return response.context['ejercicios_planificados'][0]


# ===========================================================================
# Test 1 — Propiedad de seguridad: N=1 → resultado idéntico antes y después de X.3
# ===========================================================================

class TestX3UnaSesionResultadoIdentico(BaseX3Vista):
    """
    Con una sola sesión (fuerza_potencia: reps=6) y exercise de hoy en bucket
    hipertrofia (reps='10-12'), `resolver_peso_objetivo` dispara el recálculo.

    Pre-X.3:  usa datos_anterior crudo  → mismo resultado que N=1 con ancla.
    Post-X.3: `obtener_ancla_ejercicio` con sesiones=[1 sesión] llama a
              `resolver_ancla_historica([1 sesión])` → round-trip matemáticamente
              exacto (e1RM → peso_suave → e1RM en resolver_peso_objetivo).

    Este test pasa ANTES y DESPUÉS de la implementación.
    Su valor: garantizar que X.3 no degrada el caso base (nunca peor que pre-X.3).
    """

    def setUp(self):
        super().setUp()
        entreno = self._crear_entreno(delta_dias=3)
        self._crear_ej(entreno, peso=80.0, reps=6, rpe=8)

    def test_peso_inicial_kg_calculado_con_una_sesion(self):
        """N=1 no introduce sesgo — el resultado suavizado ≈ resultado crudo."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        peso_inicial = float(ej.get('peso_inicial_kg') or 0)
        # Con N=1, el round-trip e1RM es exacto: el peso calculado es el mismo.
        # Verificamos que hay un valor calculado (>0) y que no difiere mucho del
        # resultado esperado con datos_anterior.peso=80, reps=6, rpe=8, target=10-12.
        self.assertGreater(peso_inicial, 0, "debe calcular un peso inicial > 0")
        # El resultado pre-X.3 con esos parámetros es 75.0 kg (ver cálculo en docstring).
        # Post-X.3, N=1 es matemáticamente idéntico → mismo 75.0 kg.
        self.assertAlmostEqual(peso_inicial, 75.0, delta=2.5,
                               msg=f"N=1: peso_inicial_kg={peso_inicial:.1f}, esperado ≈75.0")

    def test_peso_anterior_kg_es_la_sesion_literal(self):
        """Display: peso_anterior_kg debe mostrar los 80 kg de la sesión real."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        self.assertAlmostEqual(float(ej.get('peso_anterior_kg') or 0), 80.0, delta=0.1)


# ===========================================================================
# Test 2 — 3 sesiones mismo bucket → peso_inicial_kg refleja ancla suavizada (RED)
# ===========================================================================

class TestX3TresSesionesBucketIncompatible(BaseX3Vista):
    """
    Sesiones históricas (todas fuerza_potencia, reps=6):
      A: 2 días,  peso=90 kg, rpe=8  (más reciente)
      B: 9 días,  peso=70 kg, rpe=8
      C: 16 días, peso=50 kg, rpe=8

    Exercise hoy: '10-12' reps (hipertrofia) → bucket incompatible → resolver_peso_objetivo
    dispara el recálculo.

    Pre-X.3: usa datos_anterior.peso=90 → e1RM(90,6,8)=114 → peso_inicial_kg=80.0 kg.
    Post-X.3: ancla suavizada ≈76 kg → e1RM(76,6,8)=96.3 → peso_inicial_kg≈67.5 kg.

    Assertion RED: peso_inicial_kg < 80.0 (falla antes de X.3; pasa después).
    """

    def setUp(self):
        super().setUp()
        for delta, peso in [(2, 90.0), (9, 70.0), (16, 50.0)]:
            self._crear_ej(self._crear_entreno(delta), peso=peso, reps=6, rpe=8)

    def test_peso_inicial_menor_que_solo_sesion_reciente(self):
        """
        Con ancla suavizada el peso_inicial_kg debe ser menor que el calculado
        usando solo la sesión más reciente (A=90 → 80.0 kg).

        Este test es RED antes de X.3 e implementa el invariante principal.
        """
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        peso_inicial = float(ej.get('peso_inicial_kg') or 0)
        self.assertGreater(peso_inicial, 0, "debe calcular un peso inicial > 0")
        self.assertLess(
            peso_inicial, 80.0,
            f"Con ancla suavizada (≈67.5 kg) debe ser < 80.0 kg; se obtuvo {peso_inicial:.1f} kg",
        )

    def test_peso_inicial_cercano_al_ancla_esperada(self):
        """
        El ancla suavizada con sesiones A=90, B=70, C=50 (pesos 0.5/0.3/0.2) da ≈76 kg.
        Aplicado a reps=10-12, rpe=8: peso_inicial_kg≈67.5 (redondeado a múltiplo de 2.5).
        """
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        peso_inicial = float(ej.get('peso_inicial_kg') or 0)
        # El resultado exacto depende de la aritmética de Decimal; damos margen de 5 kg.
        self.assertAlmostEqual(peso_inicial, 67.5, delta=5.0,
                               msg=f"peso_inicial_kg={peso_inicial:.1f}, esperado ≈67.5")


# ===========================================================================
# Test 3 — Invariante de separación cálculo/display
# ===========================================================================

class TestX3SeparacionDisplayCalculo(BaseX3Vista):
    """
    Con 3 sesiones (A=90 kg más reciente, B=70, C=50), la vista debe mostrar:
    - `peso_anterior_kg` = 90.0 (la sesión literal más reciente — display).
    - `fecha_anterior`   = fecha de la sesión A (no del ancla).
    - `peso_inicial_kg`  < 80.0 (ancla suavizada — cálculo).

    Separación cálculo/display: X.3 solo toca la llamada a resolver_peso_objetivo;
    nunca modifica datos_anterior en sí mismo.
    """

    def setUp(self):
        super().setUp()
        self.fecha_sesion_a = date.today() - timedelta(days=2)
        entreno_a = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=self.fecha_sesion_a,
        )
        self._crear_ej(entreno_a, peso=90.0, reps=6, rpe=8)
        for delta, peso in [(9, 70.0), (16, 50.0)]:
            self._crear_ej(self._crear_entreno(delta), peso=peso, reps=6, rpe=8)

    def test_peso_anterior_kg_es_sesion_mas_reciente(self):
        """El display (peso_anterior_kg) sigue siendo la sesión literal A=90 kg."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        self.assertAlmostEqual(
            float(ej.get('peso_anterior_kg') or 0), 90.0, delta=0.1,
            msg="peso_anterior_kg debe ser 90.0 (sesión A), no el ancla suavizada",
        )

    def test_fecha_anterior_es_de_sesion_mas_reciente(self):
        """El display (fecha_anterior) sigue siendo la fecha de la sesión A."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        self.assertEqual(
            ej.get('fecha_anterior'), self.fecha_sesion_a,
            "fecha_anterior debe apuntar a la sesión más reciente (A), no al ancla",
        )

    def test_peso_inicial_kg_usa_ancla_no_peso_anterior(self):
        """El cálculo (peso_inicial_kg) usa el ancla suavizada, no datos_anterior.peso."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        peso_inicial = float(ej.get('peso_inicial_kg') or 0)
        # Si usara solo datos_anterior (90 kg), el resultado sería 80.0 kg.
        # Con ancla suavizada (≈76 kg), el resultado es ≈67.5 kg.
        self.assertLess(
            peso_inicial, 80.0,
            f"peso_inicial_kg={peso_inicial:.1f} debería ser < 80.0 (ancla, no raw data_anterior)",
        )


# ===========================================================================
# Test 4 — Tope de máquina: X.3 no interfiere
# ===========================================================================

class TestX3TopeMaquinaSinInterferencia(BaseX3Vista):
    """
    Cuando la última sesión tiene `es_tope_maquina=True`, la vista establece
    `sugerencia_tope=True` y omite el bloque de resolver_peso_objetivo.

    X.3 no debe interferir: `obtener_ancla_ejercicio` solo se llama dentro de
    ese bloque, así que el tope de máquina sigue ganando igual que antes.

    El peso_inicial_kg debe ser el peso de la última sesión (carry-forward).
    """

    def setUp(self):
        super().setUp()
        # Sesión con tope de máquina
        entreno = self._crear_entreno(delta_dias=3)
        self._crear_ej(entreno, peso=60.0, reps=10, rpe=8, es_tope=True)
        # Segunda sesión del mismo bucket para que haya suavizado disponible
        entreno2 = self._crear_entreno(delta_dias=10)
        self._crear_ej(entreno2, peso=50.0, reps=10, rpe=8)

    def test_sugerencia_tope_activa(self):
        """La vista debe detectar el tope y activar sugerencia_tope=True."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        self.assertTrue(
            ej.get('sugerencia_tope'),
            "sugerencia_tope debe ser True cuando la última sesión tiene es_tope_maquina=True",
        )

    def test_peso_inicial_es_el_del_tope_no_el_ancla(self):
        """Con tope de máquina, el peso_inicial_kg = peso de la última sesión (60 kg)."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        self.assertAlmostEqual(
            float(ej.get('peso_inicial_kg') or 0), 60.0, delta=0.1,
            msg="Con tope de máquina, peso_inicial_kg debe ser 60.0 (no recalculado por ancla)",
        )

    def test_no_motivo_recalculado_con_tope(self):
        """Con tope de máquina, no debe aparecer motivo_peso de tipo 'recalculado_*'."""
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        motivo = ej.get('motivo_peso') or {}
        tipo = motivo.get('tipo', '')
        self.assertFalse(
            tipo.startswith('recalculado'),
            f"Con tope de máquina no debe haber motivo_peso recalculado; se obtuvo: '{tipo}'",
        )


# ===========================================================================
# Test 5 — Bucket diferente de las sesiones históricas: fallback a referencia
# ===========================================================================

class TestX3SesionesBucketDistinto(BaseX3Vista):
    """
    Si todas las sesiones de EjercicioRealizado del ejercicio pertenecen a un
    bucket distinto al de la referencia (datos_anterior), `obtener_ancla_ejercicio`
    devuelve `referencia` tal cual — el resultado es idéntico al pre-X.3.

    Referencia: reps=6 (fuerza_potencia).
    Historial en BD: reps=10 (hipertrofia) — bucket distinto.
    Exercise hoy: '10-12' (hipertrofia, bucket incompatible con referencia).

    `obtener_ancla_ejercicio` no encuentra sesiones en el mismo bucket que referencia
    (fuerza_potencia) → devuelve referencia → resolver_peso_objetivo usa datos_anterior.
    """

    def setUp(self):
        super().setUp()
        # La sesión más reciente tiene reps=6 (fuerza_potencia) — será datos_anterior
        entreno_reciente = self._crear_entreno(delta_dias=2)
        self._crear_ej(entreno_reciente, peso=80.0, reps=6, rpe=8)
        # Sesiones más antiguas tienen reps=10 (hipertrofia) — bucket distinto
        for delta, peso in [(9, 70.0), (16, 60.0)]:
            self._crear_ej(self._crear_entreno(delta), peso=peso, reps=10, rpe=8)

    def test_fallback_cuando_historial_bucket_incompatible(self):
        """
        Con solo la sesión reciente en el bucket de referencia (fuerza_potencia),
        el resultado debe ser idéntico al pre-X.3 (datos_anterior crudo).

        peso=80, reps=6, rpe=8, target='10-12' → peso_inicial_kg ≈ 75.0 kg.
        """
        resp = self._get_vista(reps_hoy='10-12')
        ej = self._ej_contexto(resp)
        peso_inicial = float(ej.get('peso_inicial_kg') or 0)
        # Con N=1 en fuerza_potencia, el ancla = datos_anterior → resultado ≈ 75.0 kg
        self.assertAlmostEqual(
            peso_inicial, 75.0, delta=2.5,
            msg=f"Con solo N=1 en bucket referencia, peso_inicial_kg={peso_inicial:.1f} esperado ≈75.0",
        )
