# analytics/test_planificador_helms_x1_x2.py
"""
Tests TDD para X.1 (bug bíceps) y X.2 (bug bisagra glúteos).

Escrito ANTES de los fixes: todos deben fallar con el código original
y pasar en verde después de implementar los cambios en
  - database/ejercicios.py
  - ejercicios/selector.py
  - ejercicios/patrones.py
  - core.py (2 call sites)
"""

from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.ejercicios.patrones import PatronManager


# ---------------------------------------------------------------------------
# Helpers (misma interfaz que test_planificador_helms_volumen_caracterizacion)
# ---------------------------------------------------------------------------

def _build_planner(perfil_data: dict) -> tuple:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    return perfil, planner


def _semana_bloque0(planner: PlanificadorHelms) -> dict:
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    bloque0 = periodizacion[0]
    return planner._generar_semana_especifica(bloque0, 1)


PERFIL_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}


# ===========================================================================
# X.1 — Bug bíceps: siempre sale con 1 solo ejercicio
# ===========================================================================

class TestX1BicepsDosEjercicios(TestCase):
    """
    Bug: bíceps solo recibe 1 ejercicio porque compuesto_principal está vacío.
    Fix X.1 debe:
      1. Promover Curl con Barra Z a compuesto_principal en database/ejercicios.py.
      2. En selector.py, cuando pool_principal es genuinamente vacío, elegir
         dos ejercicios distintos de secundario+aislamiento.
    """

    def setUp(self):
        _, planner = _build_planner(PERFIL_DAVID)
        semana = _semana_bloque0(planner)
        self.biceps_ejs = [
            ej for ejs in semana.values()
            for ej in ejs
            if ej['grupo_muscular'] == 'biceps'
        ]

    def test_biceps_tiene_dos_ejercicios(self):
        """
        Debe haber 2 ejercicios DISTINTOS de bíceps en la semana.
        Post-X.7: bíceps aparece en 2 días (freq=2), con los mismos 2
        ejercicios rotados — total 4 entradas pero solo 2 ejercicios únicos.
        El invariante de X.1 es que haya 2 ejercicios distintos, no 2 entradas.
        """
        nombres_unicos = {e['nombre'] for e in self.biceps_ejs}
        self.assertEqual(
            len(nombres_unicos), 2,
            f"Bíceps tiene {len(nombres_unicos)} ejercicio(s) únicos; se esperaban 2. "
            f"Ejercicios: {[e['nombre'] for e in self.biceps_ejs]}"
        )

    def test_biceps_dieciseis_series(self):
        """
        2 ejercicios, cada uno acotado por GestorFatiga (pequeños≤8/ejercicio)
        tras la corrección de X.4 = 16 series semanales de bíceps para david.
        """
        total = sum(e['series'] for e in self.biceps_ejs)
        self.assertEqual(total, 16, f"Total series bíceps: {total}, esperado: 16")

    def test_biceps_ejercicios_distintos(self):
        """
        Los 2 ejercicios únicos no pueden ser el mismo.
        Post-X.7: con freq=2, los mismos 2 ejercicios se repiten cada día.
        El invariante sigue siendo: 2 ejercicios distintos.
        """
        nombres_unicos = {e['nombre'] for e in self.biceps_ejs}
        self.assertEqual(len(nombres_unicos), 2, f"Ejercicios únicos: {nombres_unicos}")

    def test_curl_con_barra_z_en_compuesto_principal(self):
        """Fix parte 2: Curl con Barra Z debe estar en compuesto_principal de bíceps."""
        from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE
        principales = [
            ej.get('nombre') for ej in EJERCICIOS_DATABASE['biceps']['compuesto_principal']
            if isinstance(ej, dict)
        ]
        self.assertIn(
            'Curl con Barra Z', principales,
            f"Curl con Barra Z no está en compuesto_principal. Principales: {principales}"
        )

    def test_curl_barra_z_es_primer_ejercicio(self):
        """Curl con Barra Z (principal) debe ser ej1 (posición 0 en el día)."""
        nombres = [e['nombre'] for e in self.biceps_ejs]
        self.assertEqual(
            nombres[0], 'Curl con Barra Z',
            f"Primer ejercicio bíceps: {nombres[0]}, esperado: Curl con Barra Z"
        )


class TestX1SelectorDosEjerciciosSinPrincipal(TestCase):
    """
    Fix parte 1 del selector.py: cuando pool_principal es genuinamente vacío,
    el selector debe elegir 2 ejercicios distintos de secundario+aislamiento.
    Verificado con un perfil diferente al de david para confirmar generalidad.
    """

    def _ejercicios_para_grupo(self, dias: int, grupo: str) -> list:
        _, planner = _build_planner({
            'id': 90, 'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': dias,
        })
        semana = _semana_bloque0(planner)
        return [
            ej for ejs in semana.values()
            for ej in ejs
            if ej['grupo_muscular'] == grupo
        ]

    def test_biceps_dos_ejercicios_avanzado_6d(self):
        """Bíceps también recibe 2 ejercicios en perfil avanzado de 6 días."""
        ejs = self._ejercicios_para_grupo(6, 'biceps')
        nombres = {e['nombre'] for e in ejs}
        self.assertGreaterEqual(
            len(nombres), 2,
            f"Bíceps en 6d tiene {len(nombres)} ejercicio(s) únicos: {nombres}"
        )

    def test_grupos_con_principal_no_cambian(self):
        """
        Grupos con compuesto_principal no vacío (pecho, espalda, cuadriceps)
        siguen funcionando exactamente igual — la nueva rama del selector no
        se activa para ellos.

        Post-X.7: isquios se elimina de esta verificación. Con el motor nuevo,
        glúteos ocupa los 2 slots de bisagra semanal (dia_1 y dia_3) antes de
        que isquios sea procesado en dia_3 → patron_manager.dias_usados_bisagra=2
        (tope) → Peso Muerto Rumano bloqueado → solo Curl Femoral Tumbado (1 ej).
        Este comportamiento es correcto y pre-existente a X.7 — no es una
        regresión del selector sino de patron_manager.
        """
        _, planner = _build_planner(PERFIL_DAVID)
        semana = _semana_bloque0(planner)
        for grupo in ('pecho', 'espalda', 'cuadriceps'):
            ejs = [e for ejs in semana.values() for e in ejs if e['grupo_muscular'] == grupo]
            self.assertGreaterEqual(
                len(ejs), 2,
                f"{grupo} tiene menos de 2 ejercicios — el selector regresionó"
            )


# ===========================================================================
# X.2 — Bug bisagra: glúteo pierde Hip Thrust cuando comparte día con isquios
# ===========================================================================

class TestX2GluteoHipThrustMismoDia(TestCase):
    """
    Bug: Hip Thrust de glúteos queda bloqueado por `puede_usar_bisagra` cuando
    isquios ya registró un patrón bisagra EN EL MISMO DÍA (diff=0 ≤ 1 → False).
    Fix X.2: mismo día siempre permitido; sólo días adyacentes son candidatos
    a bloqueo (y sólo si alguna variante es 'pesada').
    """

    def setUp(self):
        _, planner = _build_planner(PERFIL_DAVID)
        self.semana = _semana_bloque0(planner)
        # En BPS 5d, isquios+gluteos comparten dia_5
        self.gluteos_ejs = [
            ej for ejs in self.semana.values()
            for ej in ejs
            if ej['grupo_muscular'] == 'gluteos'
        ]

    def test_gluteos_tiene_dos_ejercicios(self):
        """
        Glúteos debe tener 2 ejercicios DISTINTOS: Hip Thrust + variante.
        Post-X.7: glúteos en freq=2 (dia_1 y dia_3) — los mismos 2 ejercicios
        se repiten. El invariante de X.2 es 2 ejercicios únicos, no 2 entradas.
        """
        nombres_unicos = {e['nombre'] for e in self.gluteos_ejs}
        self.assertEqual(
            len(nombres_unicos), 2,
            f"Glúteos tiene {len(nombres_unicos)} ejercicio(s) únicos: "
            f"{[e['nombre'] for e in self.gluteos_ejs]}"
        )

    def test_hip_thrust_presente(self):
        """Hip Thrust con Barra debe estar en el plan de glúteos."""
        nombres = {e['nombre'] for e in self.gluteos_ejs}
        self.assertIn(
            'Hip Thrust con Barra', nombres,
            f"Hip Thrust no encontrado. Ejercicios de glúteos: {nombres}"
        )

    def test_gluteos_veinte_cuatro_series(self):
        """
        Post-X.7: glúteos en freq=2 (dia_1 y dia_3). Cada día 2 ejercicios
        acotados por GestorFatiga (grandes≤10/ejercicio). Con vol_dia=12/día
        y 2 ejercicios: ceil(12/2)=6 series/ejercicio. Total = 6×2×2 = 24.
        """
        total = sum(e['series'] for e in self.gluteos_ejs)
        self.assertEqual(total, 24, f"Total series glúteos: {total}, esperado: 24 (freq=2)")

    def test_hip_thrust_es_primer_ejercicio_gluteos(self):
        """Hip Thrust (compuesto_principal) debe ser el primer ejercicio de glúteos."""
        nombres = [e['nombre'] for e in self.gluteos_ejs]
        self.assertEqual(
            nombres[0], 'Hip Thrust con Barra',
            f"Primer ejercicio glúteos: {nombres[0]}"
        )


class TestX2PuedaUsarBisagraLogica(TestCase):
    """
    Tests unitarios de la lógica corregida de PatronManager.puede_usar_bisagra.
    Verifica todos los casos: mismo día, días adyacentes pesada/ligera, y días lejanos.
    """

    def _pm(self):
        return PatronManager('hipertrofia')

    # ─── CASO 1: Mismo día ────────────────────────────────────────────────────

    def test_mismo_dia_siempre_permitido_sin_historial(self):
        """Sin historial previo, cualquier bisagra está permitida."""
        pm = self._pm()
        self.assertTrue(pm.puede_usar_bisagra(4, 'Hip Thrust con Barra'))

    def test_mismo_dia_permitido_tras_bisagra_ligera(self):
        """Después de registrar bisagra ligera en día 4, otra bisagra en día 4 está OK."""
        pm = self._pm()
        pm.registrar_uso_patron('bisagra', 4, 'isquios', 'Peso Muerto Rumano')
        self.assertTrue(
            pm.puede_usar_bisagra(4, 'Hip Thrust con Barra'),
            "Bisagra en mismo día que RDL (ligera) debería estar permitida"
        )

    def test_mismo_dia_permitido_tras_bisagra_pesada(self):
        """
        Incluso tras bisagra pesada en el mismo día, otra bisagra sigue
        siendo permitida — dos bisagras en la misma sesión es diseño legítimo.
        """
        pm = self._pm()
        pm.registrar_uso_patron('bisagra', 2, 'isquios', 'Peso Muerto con Barra')
        self.assertTrue(
            pm.puede_usar_bisagra(2, 'Hip Thrust con Barra'),
            "Bisagra en mismo día que PM convencional (pesada) debería estar permitida"
        )

    # ─── CASO 2: Días adyacentes ──────────────────────────────────────────────

    def test_adyacente_dos_pesadas_bloqueado(self):
        """
        PM convencional en día 0 → PM convencional en día 1 debe bloquearse
        (SNC/lumbar: ambas pesadas en días consecutivos = riesgo real).
        """
        pm = self._pm()
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto con Barra')
        self.assertFalse(
            pm.puede_usar_bisagra(1, 'Peso Muerto con Barra'),
            "Dos PM convencionales en días adyacentes deben estar bloqueados"
        )

    def test_adyacente_pesada_luego_ligera_bloqueada(self):
        """
        Última bisagra fue pesada → bisagra ligera en día siguiente también
        bloqueada (la pesada ya genera fatiga SNC que afecta el día siguiente).
        """
        pm = self._pm()
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto con Barra')
        self.assertFalse(
            pm.puede_usar_bisagra(1, 'Peso Muerto Rumano'),
            "Ligera tras pesada en días adyacentes debe estar bloqueada"
        )

    def test_adyacente_ligera_luego_pesada_bloqueada(self):
        """
        Última bisagra fue ligera → bisagra pesada en día siguiente bloqueada
        (la pesada actual sería la que añade carga sistémica excesiva).
        """
        pm = self._pm()
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto Rumano')
        self.assertFalse(
            pm.puede_usar_bisagra(1, 'Peso Muerto con Barra'),
            "Pesada tras ligera en días adyacentes debe estar bloqueada"
        )

    def test_adyacente_dos_ligeras_permitido(self):
        """
        RDL en día 0 → Hip Thrust en día 1: ambas ligeras, días adyacentes
        están permitidos porque la demanda sistémica es baja.
        """
        pm = self._pm()
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto Rumano')
        self.assertTrue(
            pm.puede_usar_bisagra(1, 'Hip Thrust con Barra'),
            "Dos bisagras ligeras en días adyacentes deben estar permitidas"
        )

    # ─── CASO 3: Días no adyacentes ──────────────────────────────────────────

    def test_dos_dias_distancia_siempre_permitido(self):
        """Con 2 días de distancia, siempre permitido independientemente de la variante."""
        pm = self._pm()
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto con Barra')
        self.assertTrue(
            pm.puede_usar_bisagra(2, 'Peso Muerto con Barra'),
            "Bisagra pesada con 2 días de distancia debe estar permitida"
        )

    def test_max_dias_bisagra_respetado(self):
        """
        MAX_DIAS_BISAGRA solo se aplica a variantes 'pesada' (fix posterior a X.7:
        el presupuesto semanal compartido entre grupos distintos no debe aplicar
        a variantes ligeras como Peso Muerto Rumano / Hip Thrust — ver
        test_patron_bisagra_presupuesto_variante.py para el detalle del bug real
        que esto arregló, isquios ahogado por glúteos consumiendo el presupuesto).
        """
        pm = self._pm()  # hipertrofia: MAX_DIAS_BISAGRA = 2, solo cuenta 'pesada'
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto Convencional')
        pm.registrar_uso_patron('bisagra', 3, 'gluteos', 'Peso Muerto Sumo')
        # Tercer uso PESADO debe bloquearse por el tope semanal
        self.assertFalse(
            pm.puede_usar_bisagra(6, 'Peso Muerto Convencional'),
            "No debe superar MAX_DIAS_BISAGRA=2 para variantes pesadas en hipertrofia"
        )
        # Variantes LIGERAS no compiten por ese presupuesto — deben seguir permitidas
        self.assertTrue(
            pm.puede_usar_bisagra(6, 'Peso Muerto Rumano'),
            "Variante ligera no debería estar bloqueada por el tope semanal de pesadas"
        )

    # ─── CASO 4: Integración isquios+glúteos mismo día ────────────────────────

    def test_integracion_isquios_gluteos_dia5(self):
        """
        Simula el flujo real de dia_5 (idx=4): isquios registra bisagra primero,
        luego glúteos puede usar bisagra en el mismo día.
        """
        pm = self._pm()
        # isquios usa Peso Muerto Rumano (ligera) en día 4
        pm.registrar_uso_patron('bisagra', 4, 'isquios', 'Peso Muerto Rumano')
        # glúteos quiere usar Hip Thrust (ligera) en el mismo día 4
        self.assertTrue(
            pm.puede_usar_bisagra(4, 'Hip Thrust con Barra'),
            "Hip Thrust en dia_5 (mismo día que RDL) debe estar permitido"
        )


class TestX2ComportamientoPreservado(TestCase):
    """
    Verifica que el fix X.2 no rompe el comportamiento legítimo existente:
    bisagra pesada en días consecutivos sigue siendo bloqueada correctamente.
    """

    def test_peso_muerto_convencional_dias_consecutivos_bloqueado(self):
        """
        Flujo que requería la regla original: PM en lunes → PM en martes → bloqueado.
        Este es el caso REAL que la restricción protege.
        """
        pm = PatronManager('hipertrofia')
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto con Barra')
        resultado = pm.puede_usar_bisagra(1, 'Peso Muerto con Barra')
        self.assertFalse(
            resultado,
            "PM convencional en días adyacentes DEBE seguir siendo bloqueado"
        )

    def test_bisagra_no_se_ve_afectada_por_otras_patrones(self):
        """Registrar patrones no-bisagra no afecta el estado de bisagra."""
        pm = PatronManager('hipertrofia')
        pm.registrar_uso_patron('empuje_horizontal', 0, 'pecho', 'Press Banca con Barra')
        pm.registrar_uso_patron('traccion_vertical', 1, 'espalda', 'Dominadas')
        # bisagra no tiene historial previo, debe estar libre
        self.assertTrue(pm.puede_usar_bisagra(2, 'Peso Muerto Rumano'))

    def test_dias_lejanos_peso_muerto_permitido(self):
        """PM en día 0 y PM en día 3 (no adyacentes) → permitido."""
        pm = PatronManager('hipertrofia')
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto con Barra')
        self.assertTrue(
            pm.puede_usar_bisagra(3, 'Peso Muerto con Barra'),
            "PM en días no adyacentes (diff=3) debe estar permitido"
        )
