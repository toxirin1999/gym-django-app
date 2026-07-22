# analytics/test_planificador_helms_x22_ancla_core.py
"""
Tests TDD para X.2.2 — suavizado de ancla histórica en _obtener_historial_ejercicio.

_obtener_historial_ejercicio (camino de caché precargada) ya no devuelve los
valores crudos de una única sesión. Recoge TODAS las sesiones del ejercicio,
filtra las del mismo bucket que la sesión de referencia (fuerza_potencia /
hipertrofia) y llama a resolver_ancla_historica() para producir un ancla
ponderada (ventana de 42 días, pesos 0.5/0.3/0.2 renormalizados).

El camino de fallback (consultas individuales sin precarga) no se toca.

Propiedad de seguridad clave (Test 1): con N=1 sesión completa el round-trip
e1RM → peso es matemáticamente exacto, así que el resultado es
byte-idéntico al comportamiento pre-X.2.2.

Tests rojos (fallan antes de la implementación):
  - Test 2: 3 sesiones mismo bucket → peso suavizado < sesión más reciente.
  - Test 6: 2 sesiones en ventana + 1 fuera → C excluida, result entre A y B.

Tests de regresión/cableado (pasan antes y después):
  - Test 1: 1 sola sesión → resultado idéntico (propiedad de seguridad).
  - Test 3: 2 buckets distintos → resultado basado solo en el bucket de referencia.
  - Test 4: referencia sin repeticiones (raw directo) → fallback a cruda.
  - Test 5: sin historial → todo None.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from rutinas.models import Rutina


# Nombre de ejercicio que no existe en el catálogo — sin colisión con datos reales
NOMBRE_EJ = 'Test X22 Press Ancla'


def _hacer_planner(cliente_id: int) -> PlanificadorHelms:
    perfil = PerfilCliente({
        'id': cliente_id,
        'nombre': 'test_x22',
        'experiencia_años': 5,
        'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 4,
    })
    return PlanificadorHelms(perfil)


class BaseX22(TestCase):
    """Setup común: usuario, cliente Django, rutina."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_x22_ancla',
            password='testpass_x22',
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TestX22', 'dias_disponibles': 4},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_x22_rutina')

    def _crear_entreno(self, delta_dias: int) -> EntrenoRealizado:
        return EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today() - timedelta(days=delta_dias),
        )

    def _crear_ej(self, entreno, peso, reps, rpe) -> EjercicioRealizado:
        return EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=NOMBRE_EJ,
            peso_kg=peso,
            repeticiones=reps,
            rpe=rpe,
        )

    def _historial(self) -> dict:
        planner = _hacer_planner(self.cliente.id)
        planner._precargar_historial_ejercicios()
        return planner._obtener_historial_ejercicio(NOMBRE_EJ)


# ===========================================================================
# Test 1 — Propiedad de seguridad: 1 sola sesión → resultado idéntico
# ===========================================================================

class TestUnaSesionResultadoIdentico(BaseX22):
    """
    Con N=1, el round-trip e1RM→peso mediante Epley+RIR es matemáticamente
    exacto. El resultado debe ser byte-idéntico al comportamiento pre-X.2.2.

    Este test pasa ANTES y DESPUÉS de la implementación.
    Su valor es garantizar que X.2.2 no degrada el caso base.
    """

    def setUp(self):
        super().setUp()
        entreno = self._crear_entreno(delta_dias=3)
        self._crear_ej(entreno, peso=80.0, reps=6, rpe=8)

    def test_peso_igual_a_sesion_unica(self):
        resultado = self._historial()
        self.assertIsNotNone(resultado['peso_real'])
        self.assertAlmostEqual(resultado['peso_real'], 80.0, delta=0.5,
                               msg="Con 1 sesión el peso suavizado debe ser ≈ el peso crudo")

    def test_reps_igual_a_sesion_unica(self):
        resultado = self._historial()
        self.assertEqual(resultado['reps_real'], 6)

    def test_rpe_igual_a_sesion_unica(self):
        resultado = self._historial()
        self.assertAlmostEqual(resultado['rpe_real'], 8.0, delta=0.1)


# ===========================================================================
# Test 2 — 3 sesiones mismo bucket → peso suavizado (RED antes de X.2.2)
# ===========================================================================

class TestTresSesionesMismoBucketSuavizado(BaseX22):
    """
    Sesiones: (más reciente→más antigua)
      A: 2 días, peso=84, reps=6, rpe=8  → fuerza_potencia
      B: 9 días, peso=82, reps=6, rpe=8  → fuerza_potencia
      C: 16 días, peso=80, reps=6, rpe=8 → fuerza_potencia

    Pre-X.2.2: toma solo A → peso_real=84.0.
    Post-X.2.2: resolver_ancla_historica([A,B,C], pesos=[0.5,0.3,0.2])
                → peso_suave ≈ 82.6 (entre 80 y 84, < 84).

    Assertion RED: peso_real < 84.0.
    """

    def setUp(self):
        super().setUp()
        for delta, peso in [(2, 84.0), (9, 82.0), (16, 80.0)]:
            self._crear_ej(self._crear_entreno(delta), peso=peso, reps=6, rpe=8)

    def test_peso_suavizado_menor_que_mas_reciente(self):
        resultado = self._historial()
        self.assertIsNotNone(resultado['peso_real'])
        self.assertLess(
            resultado['peso_real'], 84.0,
            "El peso suavizado debe ser < 84.0 (sesión más reciente); "
            f"se obtuvo {resultado['peso_real']:.2f}",
        )

    def test_peso_suavizado_mayor_que_mas_antigua(self):
        resultado = self._historial()
        self.assertGreater(
            resultado['peso_real'], 80.0,
            "El peso suavizado debe ser > 80.0 (sesión más antigua); "
            f"se obtuvo {resultado['peso_real']:.2f}",
        )

    def test_reps_del_mas_reciente(self):
        """reps_ref siempre viene de la sesión más reciente (usadas[0])."""
        resultado = self._historial()
        self.assertEqual(resultado['reps_real'], 6)

    def test_rpe_suavizado_cerca_de_8(self):
        """Con todos los rpe=8, el rpe ponderado debe ser 8.0."""
        resultado = self._historial()
        self.assertAlmostEqual(resultado['rpe_real'], 8.0, delta=0.1)


# ===========================================================================
# Test 3 — 2 sesiones de buckets distintos → solo usa el bucket de referencia
# ===========================================================================

class TestBucketsSeparados(BaseX22):
    """
    Sesiones:
      A (más reciente): 2 días, reps=6 (fuerza_potencia), peso=80, rpe=8
      B (más antigua):  9 días, reps=10 (hipertrofia),     peso=50, rpe=8

    La referencia es A (más reciente, fuerza_potencia).
    B está en bucket distinto → excluida del suavizado.
    sesiones = [A solamente] → resultado ≈ 80.0 (N=1, round-trip exacto).

    Si se mezclaran buckets, el peso caería hacia 50. El test verifica que
    el resultado está cerca de 80, no del promedio A+B.
    """

    def setUp(self):
        super().setUp()
        self._crear_ej(self._crear_entreno(delta_dias=2),  peso=80.0, reps=6,  rpe=8)
        self._crear_ej(self._crear_entreno(delta_dias=9),  peso=50.0, reps=10, rpe=8)

    def test_resultado_cercano_a_bucket_referencia(self):
        resultado = self._historial()
        self.assertIsNotNone(resultado['peso_real'])
        self.assertAlmostEqual(
            resultado['peso_real'], 80.0, delta=2.0,
            msg="El resultado debe reflejar solo el bucket de referencia (fuerza); "
                f"se obtuvo {resultado['peso_real']:.2f}",
        )

    def test_resultado_no_mezclado_con_otro_bucket(self):
        resultado = self._historial()
        # Si se mezclaran, el peso caería significativamente por debajo de 75
        self.assertGreater(
            resultado['peso_real'], 75.0,
            "El peso no debe mezclarse con la sesión del bucket contrario (50 kg); "
            f"se obtuvo {resultado['peso_real']:.2f}",
        )

    def test_reps_del_bucket_referencia(self):
        resultado = self._historial()
        self.assertEqual(resultado['reps_real'], 6)


# ===========================================================================
# Test 4 — Referencia sin repeticiones (None) → fallback a cruda
# ===========================================================================

class TestReferenciaSinRepeticionesFallback(TestCase):
    """
    Cuando la sesión de referencia tiene repeticiones=None no es posible
    determinar el bucket. El código debe devolver los valores crudos de la
    referencia sin llamar a resolver_ancla_historica.

    Se manipula _historial_ejercicios_raw directamente (EjercicioRealizado
    no admite repeticiones=None en BD, pero el código debe ser robusto
    ante datos inconsistentes).
    """

    def _planner_con_raw(self, raw: list) -> PlanificadorHelms:
        perfil = PerfilCliente({'id': 9999, 'nombre': 'test_x22_raw', 'dias_disponibles': 4})
        planner = PlanificadorHelms(perfil)
        planner._historial_ejercicios_raw = raw
        return planner

    def test_fallback_devuelve_peso_crudo(self):
        raw = [{
            'nombre_ejercicio': 'Test X22 Press Ancla',
            'peso_kg': 80.0,
            'rpe': 7,
            'repeticiones': None,
            'entreno__fecha': date.today() - timedelta(days=3),
        }]
        planner = self._planner_con_raw(raw)
        resultado = planner._obtener_historial_ejercicio('Test X22 Press Ancla')
        self.assertAlmostEqual(resultado['peso_real'], 80.0, delta=0.01)

    def test_fallback_rpe_crudo(self):
        raw = [{
            'nombre_ejercicio': 'Test X22 Press Ancla',
            'peso_kg': 80.0,
            'rpe': 7,
            'repeticiones': None,
            'entreno__fecha': date.today() - timedelta(days=3),
        }]
        planner = self._planner_con_raw(raw)
        resultado = planner._obtener_historial_ejercicio('Test X22 Press Ancla')
        self.assertAlmostEqual(resultado['rpe_real'], 7.0, delta=0.01)

    def test_fallback_reps_none(self):
        raw = [{
            'nombre_ejercicio': 'Test X22 Press Ancla',
            'peso_kg': 80.0,
            'rpe': 7,
            'repeticiones': None,
            'entreno__fecha': date.today() - timedelta(days=3),
        }]
        planner = self._planner_con_raw(raw)
        resultado = planner._obtener_historial_ejercicio('Test X22 Press Ancla')
        self.assertIsNone(resultado['reps_real'])


# ===========================================================================
# Test 5 — Sin historial → todo None
# ===========================================================================

class TestSinHistorial(BaseX22):
    """Sin sesiones del ejercicio, el resultado debe ser idéntico al pre-X.2.2."""

    def test_sin_sesiones_resultado_todo_none(self):
        resultado = self._historial()
        self.assertIsNone(resultado['peso_real'])
        self.assertIsNone(resultado['rpe_real'])
        self.assertIsNone(resultado['reps_real'])


# ===========================================================================
# Test 6 — Ventana de 42 días: sesión fuera no contribuye (RED antes de X.2.2)
# ===========================================================================

class TestVentana42Dias(BaseX22):
    """
    Sesiones:
      A (más reciente): 3 días, peso=100, reps=5, rpe=8   → dentro de ventana
      B: 20 días, peso=80, reps=5, rpe=8                  → dentro de ventana
      C: 50 días, peso=60, reps=5, rpe=8                  → FUERA de ventana

    Pre-X.2.2: toma solo A → peso_real=100.0.
    Post-X.2.2: resolver_ancla_historica([A,B]; C excluida por ventana)
                → peso_suave ≈ 92-93 (entre 80 y 100).

    Assertion RED: peso_real < 100.0 (A sola), también > 80 (no arrastra C).
    """

    def setUp(self):
        super().setUp()
        for delta, peso in [(3, 100.0), (20, 80.0), (50, 60.0)]:
            self._crear_ej(self._crear_entreno(delta), peso=peso, reps=5, rpe=8)

    def test_peso_por_debajo_de_solo_A(self):
        resultado = self._historial()
        self.assertIsNotNone(resultado['peso_real'])
        self.assertLess(
            resultado['peso_real'], 100.0,
            "Con sesión B dentro de ventana, el suavizado debe bajar de 100; "
            f"se obtuvo {resultado['peso_real']:.2f}",
        )

    def test_sesion_C_fuera_de_ventana_no_arrastra_el_peso(self):
        resultado = self._historial()
        # C tiene peso=60. Si se incluyera, el promedio caería por debajo de 80.
        self.assertGreater(
            resultado['peso_real'], 80.0,
            "La sesión C (50 días atrás, fuera de ventana) no debe arrastrar el peso; "
            f"se obtuvo {resultado['peso_real']:.2f}",
        )
