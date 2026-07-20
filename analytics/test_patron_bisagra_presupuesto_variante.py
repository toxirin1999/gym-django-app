# analytics/test_patron_bisagra_presupuesto_variante.py
"""
Bugfix: el presupuesto semanal de patrón 'bisagra' (MAX_DIAS_BISAGRA) contaba
TODAS las variantes por igual, compartido entre grupos distintos (isquios,
gluteos). Antes de X.6/X.7 cada grupo bisagra aparecía como máximo 1x/semana,
así que el presupuesto (2 en hipertrofia) siempre alcanzaba. Con frecuencia
dinámica, gluteos con freq=2 consume él solo los 2 cupos semanales (Hip
Thrust, variante 'ligera'), dejando a isquios sin cupo para su propio
ejercicio bisagra (Peso Muerto Rumano) aunque comparta día con gluteos.
Verificado: isquios pasaba de 18 a 9 series/semana para david.

Fix: el presupuesto semanal solo se aplica a variantes 'pesada' (peso
muerto convencional/sumo — fatiga SNC/lumbar real). Las variantes 'ligera'
(RDL, Hip Thrust, buenos días, hiperextensión) no cargan ese riesgo
sistémico y no deben competir por un presupuesto compartido con otro grupo
distinto — solo quedan sujetas a la restricción de días adyacentes ya
existente (X.2).
"""

from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.ejercicios.patrones import PatronManager


def _build_planner(perfil_data: dict) -> tuple:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    return perfil, planner


def _semana_bloque0(planner: PlanificadorHelms) -> dict:
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    return planner._generar_semana_especifica(periodizacion[0], 1)


PERFIL_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}


class TestIsquiosNoAhogadoPorPresupuestoBisagra(TestCase):
    """El bug reproducido con el perfil real de david."""

    def setUp(self):
        _, self._planner = _build_planner(PERFIL_DAVID)
        self._semana = _semana_bloque0(self._planner)
        self._isquios_ejs = [
            ej for ejs in self._semana.values()
            for ej in ejs
            if ej['grupo_muscular'] == 'isquios'
        ]

    def test_isquios_tiene_dos_ejercicios(self):
        nombres_unicos = {e['nombre'] for e in self._isquios_ejs}
        self.assertEqual(
            len(nombres_unicos), 2,
            f"Isquios tiene {len(nombres_unicos)} ejercicio(s) único(s): {nombres_unicos}. "
            f"Se esperaban 2 (Peso Muerto Rumano + Curl Femoral)."
        )

    def test_isquios_no_capado_a_la_mitad(self):
        total = sum(e['series'] for e in self._isquios_ejs)
        self.assertGreater(
            total, 15,
            f"Isquios: {total} series — sigue ahogado por el presupuesto compartido "
            f"de bisagra (antes del fix: 9)."
        )

    def test_gluteos_mantiene_dos_sesiones_hip_thrust(self):
        gluteos_ejs = [
            ej for ejs in self._semana.values()
            for ej in ejs
            if ej['grupo_muscular'] == 'gluteos' and ej['nombre'] == 'Hip Thrust con Barra'
        ]
        self.assertEqual(
            len(gluteos_ejs), 2,
            "Glúteos debería conservar Hip Thrust en sus 2 sesiones — sin regresión."
        )


class TestPresupuestoSemanalSoloAplicaAVariantePesada(TestCase):
    """La protección real (variante pesada) debe seguir intacta."""

    def test_variante_pesada_respeta_tope_semanal(self):
        pm = PatronManager(fase='hipertrofia')
        # MAX_DIAS_BISAGRA['hipertrofia'] = 2. Simular 2 usos pesados ya registrados
        # en días no adyacentes entre sí.
        self.assertTrue(pm.puede_usar_bisagra(1, 'Peso Muerto Convencional'))
        pm.registrar_uso_patron('bisagra', 1, grupo='isquios', nombre_ejercicio='Peso Muerto Convencional')

        self.assertTrue(pm.puede_usar_bisagra(3, 'Peso Muerto Convencional'))
        pm.registrar_uso_patron('bisagra', 3, grupo='gluteos', nombre_ejercicio='Peso Muerto Convencional')

        # Tercer uso pesado: presupuesto semanal (2) ya agotado → debe bloquearse
        self.assertFalse(
            pm.puede_usar_bisagra(5, 'Peso Muerto Convencional'),
            "Un tercer uso de variante PESADA debería bloquearse por el tope semanal."
        )

    def test_variante_ligera_sin_tope_semanal(self):
        pm = PatronManager(fase='hipertrofia')
        # 3 usos ligeros en días separados (no adyacentes) — no deben bloquearse
        # aunque MAX_DIAS_BISAGRA=2, porque la variante ligera no compite por ese cupo.
        for dia in (1, 3, 5):
            self.assertTrue(
                pm.puede_usar_bisagra(dia, 'Hip Thrust con Barra'),
                f"Variante ligera en día {dia} no debería estar bloqueada por el tope semanal."
            )
            pm.registrar_uso_patron('bisagra', dia, grupo='gluteos', nombre_ejercicio='Hip Thrust con Barra')

    def test_dias_adyacentes_pesada_sigue_bloqueado(self):
        """La restricción de días adyacentes (X.2) para variantes pesadas no debe cambiar."""
        pm = PatronManager(fase='hipertrofia')
        pm.registrar_uso_patron('bisagra', 2, grupo='isquios', nombre_ejercicio='Peso Muerto Convencional')
        self.assertFalse(
            pm.puede_usar_bisagra(3, 'Peso Muerto Sumo'),
            "Dos variantes pesadas en días adyacentes deben seguir bloqueadas."
        )

    def test_dias_adyacentes_ligera_sigue_permitido(self):
        """Dos variantes ligeras en días adyacentes siguen permitidas (X.2, sin cambios)."""
        pm = PatronManager(fase='hipertrofia')
        pm.registrar_uso_patron('bisagra', 2, grupo='isquios', nombre_ejercicio='Peso Muerto Rumano')
        self.assertTrue(
            pm.puede_usar_bisagra(3, 'Hip Thrust con Barra'),
            "Dos variantes ligeras en días adyacentes deberían seguir permitidas."
        )


class TestOtrosPatronesSinCambios(TestCase):
    """Los demás patrones (no bisagra) no deben verse afectados por este fix."""

    def test_empuje_horizontal_dias_usados_sigue_funcionando(self):
        pm = PatronManager(fase='hipertrofia')
        pm.registrar_uso_patron('empuje_horizontal', 1, grupo='pecho')
        pm.registrar_uso_patron('empuje_horizontal', 2, grupo='pecho')
        self.assertEqual(pm.estado_semana['empuje_horizontal']['dias_usados'], 2)
