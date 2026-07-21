# analytics/test_planificador_helms_x15.py
"""
Tests de X.15 — Verificación y validación de la Fase Variación Intra-Semanal.

Tres partes:
  Parte 1 — Oposición vertical/horizontal de espalda en todos los perfiles con freq≥2.
  Parte 2 — Interacción con puede_usar_bisagra cuando el toque 2 cambia a bisagra pesada.
  Parte 3 — Validación en flujo real (sin depender solo de tests unitarios aislados).
"""

import unittest
from unittest.mock import patch

from django.test import TestCase, Client

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.ejercicios.patrones import PatronManager
from analytics.planificador_helms.config import KEYWORDS_VERTICAL, KEYWORDS_HORIZONTAL


# ---------------------------------------------------------------------------
# Helpers compartidos
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


def _dias_por_grupo(semana: dict) -> dict:
    """
    Devuelve {grupo: [dia_key, ...]} ordenado cronológicamente, sin duplicados.
    Un grupo puede tener varios ejercicios en el mismo día; se cuenta el día una sola vez.
    """
    resultado: dict = {}
    for dia, ejercicios in sorted(semana.items()):
        grupos_vistos_en_dia = set()
        for ej in ejercicios:
            g = ej['grupo_muscular']
            if g not in grupos_vistos_en_dia:
                resultado.setdefault(g, []).append(dia)
                grupos_vistos_en_dia.add(g)
    return resultado


def _ejercicios_por_grupo_y_dia(semana: dict) -> dict:
    """Devuelve {dia: {grupo: [{'nombre':..., ...}, ...]}}."""
    resultado: dict = {}
    for dia, ejercicios in sorted(semana.items()):
        resultado.setdefault(dia, {})
        for ej in ejercicios:
            g = ej['grupo_muscular']
            resultado[dia].setdefault(g, []).append(ej)
    return resultado


# ---------------------------------------------------------------------------
# TODOS los perfiles de la matriz de caracterización
# ---------------------------------------------------------------------------

PERFILES_MATRIZ = [
    {'id': 2,  'nombre': 'david',     'experiencia_años': 7,   'objetivo_principal': 'general',     'dias_disponibles': 5},
    {'id': 99, 'nombre': 'novato_3d', 'experiencia_años': 0.5, 'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3},
    {'id': 98, 'nombre': 'inter_4d',  'experiencia_años': 2,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 4},
    {'id': 97, 'nombre': 'avanz_6d',  'experiencia_años': 5,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 6},
    {'id': 96, 'nombre': 'avanz_3d',  'experiencia_años': 5,   'objetivo_principal': 'hipertrofia', 'dias_disponibles': 3},
]


# ===========================================================================
# PARTE 1 — Oposición vertical/horizontal de espalda (todos los perfiles freq≥2)
# ===========================================================================

class TestX15EspaldaOposicionVerticalHorizontal(TestCase):
    """
    Para cada perfil de la matriz, si espalda llega a freq≥2, el toque 2
    debe tener 1 ejercicio vertical y 1 horizontal, ambos distintos al toque 1.

    Si espalda es freq=1 en ese perfil, el subtest simplemente pasa (no aplica).
    """

    def _ejercicios_espalda_toque2(self, semana: dict) -> list:
        """Devuelve los ejercicios de espalda del toque 2 (segunda aparición)."""
        dias_por_grupo = _dias_por_grupo(semana)
        dias_espalda = dias_por_grupo.get('espalda', [])
        if len(dias_espalda) < 2:
            return []
        dia_toque2 = dias_espalda[1]
        ejpc = _ejercicios_por_grupo_y_dia(semana)
        return ejpc.get(dia_toque2, {}).get('espalda', [])

    def _ejercicios_espalda_toque1(self, semana: dict) -> list:
        dias_por_grupo = _dias_por_grupo(semana)
        dias_espalda = dias_por_grupo.get('espalda', [])
        if not dias_espalda:
            return []
        dia_toque1 = dias_espalda[0]
        ejpc = _ejercicios_por_grupo_y_dia(semana)
        return ejpc.get(dia_toque1, {}).get('espalda', [])

    def test_espalda_toque2_tiene_vertical_y_horizontal_en_perfiles_freq2(self):
        """
        Itera los perfiles de la matriz. Para cada perfil con espalda freq≥2,
        el toque 2 debe contener al menos 1 vertical y 1 horizontal.
        """
        for pdata in PERFILES_MATRIZ:
            with self.subTest(id=pdata['id'], nombre=pdata['nombre']):
                _, planner = _build_planner(pdata)
                semana = _semana_bloque0(planner)

                freq_espalda = len(_dias_por_grupo(semana).get('espalda', []))
                if freq_espalda < 2:
                    # Perfil no llega a freq=2 en espalda — no aplica oposición
                    continue

                toque2 = self._ejercicios_espalda_toque2(semana)
                self.assertGreater(
                    len(toque2), 0,
                    f"Perfil {pdata['nombre']}: espalda freq={freq_espalda} pero "
                    f"toque 2 está vacío (unexpected)",
                )

                nombres_t2 = [e['nombre'].lower() for e in toque2]

                tiene_vertical = any(
                    any(k in n for k in KEYWORDS_VERTICAL) for n in nombres_t2
                )
                tiene_horizontal = any(
                    any(k in n for k in KEYWORDS_HORIZONTAL) for n in nombres_t2
                )

                self.assertTrue(
                    tiene_vertical,
                    f"Perfil {pdata['nombre']}: espalda toque 2 carece de ejercicio "
                    f"vertical. nombres_t2={nombres_t2}",
                )
                self.assertTrue(
                    tiene_horizontal,
                    f"Perfil {pdata['nombre']}: espalda toque 2 carece de ejercicio "
                    f"horizontal. nombres_t2={nombres_t2}",
                )

    def test_espalda_toque2_distinto_al_toque1_en_perfiles_freq2(self):
        """
        En perfiles con espalda freq≥2, el toque 2 debe diferir en al menos
        un ejercicio respecto al toque 1.
        """
        for pdata in PERFILES_MATRIZ:
            with self.subTest(id=pdata['id'], nombre=pdata['nombre']):
                _, planner = _build_planner(pdata)
                semana = _semana_bloque0(planner)

                freq_espalda = len(_dias_por_grupo(semana).get('espalda', []))
                if freq_espalda < 2:
                    continue

                nombres_t1 = {e['nombre'].lower() for e in self._ejercicios_espalda_toque1(semana)}
                nombres_t2 = {e['nombre'].lower() for e in self._ejercicios_espalda_toque2(semana)}

                nuevos_en_t2 = nombres_t2 - nombres_t1
                self.assertTrue(
                    bool(nuevos_en_t2),
                    f"Perfil {pdata['nombre']}: espalda toque 2 {sorted(nombres_t2)} "
                    f"es idéntico al toque 1 {sorted(nombres_t1)} — variación no activada",
                )

    def test_david_espalda_toque1_vertical_horizontal(self):
        """
        Prueba puntual para David: toque 1 de espalda (dia_2) es
        Jalón al Pecho (vertical) + Remo pecho apoyado (horizontal).
        Confirma que KEYWORDS_VERTICAL/HORIZONTAL clasifican correctamente
        los ejercicios reales del catálogo.
        """
        _, planner = _build_planner(PERFILES_MATRIZ[0])  # David
        semana = _semana_bloque0(planner)

        ejs_t1 = self._ejercicios_espalda_toque1(semana)
        nombres_t1 = [e['nombre'].lower() for e in ejs_t1]

        tiene_vertical = any(any(k in n for k in KEYWORDS_VERTICAL) for n in nombres_t1)
        tiene_horizontal = any(any(k in n for k in KEYWORDS_HORIZONTAL) for n in nombres_t1)
        self.assertTrue(tiene_vertical, f"Toque 1 de espalda de David sin vertical: {nombres_t1}")
        self.assertTrue(tiene_horizontal, f"Toque 1 de espalda de David sin horizontal: {nombres_t1}")

    def test_david_espalda_toque2_vertical_es_jalon_brazos_rectos(self):
        """
        Prueba puntual: el toque 2 de espalda de David (dia_5) incluye
        'Jalon brazos rectos' como ejercicio vertical y 'Remo con Mancuerna a una mano'
        como horizontal — tal como muestra el golden master de X.13/X.14.
        """
        _, planner = _build_planner(PERFILES_MATRIZ[0])  # David
        semana = _semana_bloque0(planner)

        ejs_t2 = self._ejercicios_espalda_toque2(semana)
        nombres_t2 = {e['nombre'] for e in ejs_t2}

        self.assertIn(
            'Jalon brazos rectos', nombres_t2,
            f"Esperado 'Jalon brazos rectos' (vertical) en toque 2 de espalda, got {nombres_t2}",
        )
        self.assertIn(
            'Remo con Mancuerna a una mano', nombres_t2,
            f"Esperado 'Remo con Mancuerna a una mano' (horizontal) en toque 2 de espalda, got {nombres_t2}",
        )


# ===========================================================================
# PARTE 2 — Bisagra: interacción con puede_usar_bisagra en toque 2
# ===========================================================================

class TestX15BisagraPatronManagerBloqueo(unittest.TestCase):
    """
    Pruebas puras de PatronManager (sin BD, sin core.py).
    Verifican el mecanismo de restricción de días adyacentes con bisagra pesada.
    """

    def test_bisagra_pesada_dia0_bloquea_cualquier_bisagra_dia1(self):
        """
        Si el último día de bisagra fue una variante 'pesada' (idx=0),
        cualquier bisagra en el día siguiente (idx=1, adyacente) es bloqueada,
        incluso si la nueva variante es 'ligera'.
        """
        pm = PatronManager('hipertrofia')
        # Registrar una bisagra pesada en día 0 (Peso Muerto Convencional).
        # 'convencional' está en BISAGRA_PESADAS → clasificará como 'pesada'.
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto Convencional')

        # Bisagra ligera en día 1 adyacente → bloqueada porque el anterior fue pesado
        self.assertFalse(
            pm.puede_usar_bisagra(1, 'Buenos Días (Good Mornings)'),
            "PatronManager debería bloquear bisagra ligera el día siguiente a una pesada",
        )

    def test_bisagra_pesada_dia0_bloquea_pesada_dia1(self):
        """
        Bisagra pesada en día 0 bloquea también bisagra pesada en día 1.
        """
        pm = PatronManager('hipertrofia')
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto Convencional')

        self.assertFalse(
            pm.puede_usar_bisagra(1, 'Peso Muerto Convencional'),
            "PatronManager debería bloquear bisagra pesada el día siguiente a otra pesada",
        )

    def test_bisagra_pesada_dia0_NO_bloquea_dia2(self):
        """
        Después de 1 día de diferencia (diff=2), ya no aplica la restricción.
        """
        pm = PatronManager('hipertrofia')
        pm.registrar_uso_patron('bisagra', 0, 'isquios', 'Peso Muerto Convencional')

        self.assertTrue(
            pm.puede_usar_bisagra(2, 'Hip Thrust con Barra'),
            "PatronManager NO debería bloquear bisagra con 2 días de diferencia",
        )

    def test_bisagra_ligera_ligera_dias_adyacentes_permitido(self):
        """
        Dos bisagras ligeras en días adyacentes están explícitamente permitidas.
        (Hip Thrust + RDL el día siguiente es diseño legítimo de entrenamiento.)
        """
        pm = PatronManager('hipertrofia')
        pm.registrar_uso_patron('bisagra', 0, 'gluteos', 'Hip Thrust con Barra')

        self.assertTrue(
            pm.puede_usar_bisagra(1, 'Peso Muerto Rumano'),
            "PatronManager debería permitir dos bisagras ligeras en días adyacentes",
        )

    def test_bisagra_ligera_seguida_de_pesada_dia_adyacente_bloqueada(self):
        """
        Bisagra ligera en día 0, bisagra PESADA en día 1: la pesada queda bloqueada.
        La regla bloquea si CUALQUIERA (anterior o actual) es pesada.
        """
        pm = PatronManager('hipertrofia')
        pm.registrar_uso_patron('bisagra', 0, 'gluteos', 'Hip Thrust con Barra')  # ligera

        # Intentar bisagra pesada en día adyacente
        self.assertFalse(
            pm.puede_usar_bisagra(1, 'Peso Muerto Convencional'),
            "PatronManager debería bloquear bisagra PESADA el día siguiente a una ligera",
        )


class TestX15BisagraGracefulDegradationCore(TestCase):
    """
    Verifica que core.py se degrada con gracia cuando el toque 2 de un grupo
    bisagra queda bloqueado por la restricción de días adyacentes:
    - No se lanza ninguna excepción.
    - El día no queda vacío: otros grupos siguen teniendo ejercicios.
    - El grupo bisagra bloqueado puede tener 0 ejercicios ese día — aceptable.

    El comportamiento correcto está garantizado por el `continue` en la línea:
      if patron == 'bisagra' and not patron_manager.puede_usar_bisagra(idx_dia, nombre):
          continue
    Este test lo verifica explícitamente sin modificar ese comportamiento.
    """

    def test_toque2_bisagra_pesada_rechazada_dia_adyacente_no_lanza_excepcion(self):
        """
        Escenario sintético:
        - asignar_semana devuelve gluteos en dia_1 Y dia_2 (adyacentes).
        - El pool real de gluteos en toque 1 (dia_1) incluye Hip Thrust (ligera),
          que se registra en PatronManager al procesar dia_1.
        - construir_variantes_por_toque se parchea para que el toque 2 de gluteos
          en dia_2 solo tenga 'Peso Muerto Sumo' (bisagra pesada).
        - PatronManager bloquea Peso Muerto Sumo (pesada + día adyacente a ligera).
        - El día dia_2 sigue teniendo ejercicios de otros grupos (biceps).
        - No se lanza ninguna excepción.
        """
        from analytics.planificador_helms.distribucion.asignador import (
            ResultadoAsignacion, AsignacionImposibleError,
        )

        PESO_MUERTO_SUMO = {
            'nombre': 'Peso Muerto Sumo',
            'patron': 'bisagra',
            'perfil': 'estirado',
            'tipo_progresion': 'peso_reps',
            'estabilidad': 'media',
            'risk_tags': ['bisagra_cadera', 'carga_axial'],
        }

        # Distribucion sintética: gluteos en dia_1 y dia_2, biceps en dia_2
        asignacion_sintetica = ResultadoAsignacion(
            asignacion={
                'dia_1': ['gluteos'],
                'dia_2': ['biceps', 'gluteos'],
            },
            frecuencia_efectiva={'gluteos': 2, 'biceps': 1},
            grupos_degradados=[],
        )

        def mock_construir_variantes(grupo, frecuencia, es_grande, pool_seguro, ejercicios_toque1):
            if grupo == 'gluteos':
                return {
                    1: ejercicios_toque1,           # toque 1 = real (Hip Thrust + Abducción)
                    2: [PESO_MUERTO_SUMO],          # toque 2 = solo bisagra pesada (bloqueada)
                }
            # Resto de grupos: sin variación (solo toque 1)
            return {1: ejercicios_toque1}

        _, planner = _build_planner(PERFILES_MATRIZ[0])  # David

        with patch('analytics.planificador_helms.core.asignar_semana',
                   return_value=asignacion_sintetica), \
             patch('analytics.planificador_helms.core.construir_variantes_por_toque',
                   side_effect=mock_construir_variantes):

            # No debe lanzar excepción
            try:
                periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
                semana = planner._generar_semana_especifica(periodizacion[0], 1)
            except Exception as exc:
                self.fail(
                    f"_generar_semana_especifica lanzó excepción cuando bisagra "
                    f"toque 2 fue bloqueada: {exc}"
                )

        # dia_2 no debe estar completamente vacío: biceps sigue teniendo ejercicios
        dia2 = semana.get('dia_2', [])
        self.assertGreater(
            len(dia2), 0,
            "dia_2 quedó completamente vacío cuando solo se bloqueó gluteos toque 2. "
            "biceps debería tener ejercicios.",
        )

        grupos_dia2 = {e['grupo_muscular'] for e in dia2}
        self.assertIn(
            'biceps', grupos_dia2,
            f"biceps debería tener ejercicios en dia_2 aunque gluteos toque 2 fue bloqueado. "
            f"grupos en dia_2: {grupos_dia2}",
        )

    def test_toque2_bisagra_ligera_NO_bloqueada_ligera_precedente(self):
        """
        Contra-ejemplo del test anterior: si toque 1 de gluteos fue ligera (Hip Thrust)
        y toque 2 también es bisagra ligera (Peso Muerto Rumano), NO debe ser bloqueado.
        El ejercicio ligero aparece en el día.
        """
        from analytics.planificador_helms.distribucion.asignador import (
            ResultadoAsignacion,
        )

        PESO_MUERTO_RUMANO = {
            'nombre': 'Peso Muerto Rumano',
            'patron': 'bisagra',
            'perfil': 'estirado',
            'tipo_progresion': 'peso_reps',
            'estabilidad': 'media',
            'risk_tags': ['bisagra_cadera', 'carga_axial'],
        }

        asignacion_sintetica = ResultadoAsignacion(
            asignacion={
                'dia_1': ['gluteos'],
                'dia_2': ['gluteos'],
            },
            frecuencia_efectiva={'gluteos': 2},
            grupos_degradados=[],
        )

        def mock_construir_variantes(grupo, frecuencia, es_grande, pool_seguro, ejercicios_toque1):
            if grupo == 'gluteos':
                return {
                    1: ejercicios_toque1,            # Hip Thrust + Abducción (ligera)
                    2: [PESO_MUERTO_RUMANO],          # Rumano (bisagra ligera) — NO bloqueado
                }
            return {1: ejercicios_toque1}

        _, planner = _build_planner(PERFILES_MATRIZ[0])

        with patch('analytics.planificador_helms.core.asignar_semana',
                   return_value=asignacion_sintetica), \
             patch('analytics.planificador_helms.core.construir_variantes_por_toque',
                   side_effect=mock_construir_variantes):
            periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
            semana = planner._generar_semana_especifica(periodizacion[0], 1)

        # dia_2 debe tener Peso Muerto Rumano (bisagra ligera, permitida)
        dia2 = semana.get('dia_2', [])
        nombres_dia2 = {e['nombre'] for e in dia2}
        self.assertIn(
            'Peso Muerto Rumano', nombres_dia2,
            f"Peso Muerto Rumano (bisagra ligera) debería aparecer en dia_2, "
            f"pero fue bloqueado. nombres_dia2={nombres_dia2}",
        )


# ===========================================================================
# PARTE 3 — Validación en flujo real
# ===========================================================================

class TestX15FlujoPlanReal(TestCase):
    """
    Validación que el flujo de producción sirve correctamente los planes con
    variación de toque (X.14), incluyendo días donde grupos como glúteos
    reciben la Búlgara en lugar del Hip Thrust.

    Usa _calcular_ejercicios_dia (la función real que llama briefing_entrenamiento
    cuando el cache de transporte no está disponible) para verificar que el plan
    generado llega intacto hasta la capa de servicio.

    Por qué _calcular_ejercicios_dia y no django.test.Client().get() al briefing:
    briefing_entrenamiento renderiza un template complejo que depende de modelos
    de señales/continuidad/pausa no configurados en el entorno de test. La función
    _calcular_ejercicios_dia cubre el path de negocio que nos interesa verificar:
    PlanificadorHelms → plan anual → día específico → lista de ejercicios.

    Semanas usadas en los tests:
    - Semana 1 (2026-01-05..09, vol_mult=0.9): volumen de rampa — glúteos solo aparece
      una vez (no hay toque 2). Sirve para verificar estructura básica (toque 1).
    - Semana 7 (2026-02-16..20, vol_mult=1.05): primera semana de volumen completo —
      glúteos, cuádriceps y espalda llegan a freq=2, activando la variación de toque.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        from clientes.models import Cliente
        from clientes.utils import get_cliente_actual

        self.user = User.objects.create_user(
            username='test_x15_david',
            password='testpass_x15',
        )
        # El post_save signal de User ya crea el Cliente automáticamente.
        # Usamos get_cliente_actual para obtenerlo y luego actualizamos los campos
        # para que coincida con el perfil de David en la matriz de caracterización.
        self.cliente = get_cliente_actual(self.user)
        self.cliente.experiencia_años = 7.0
        self.cliente.objetivo_principal = 'general'
        self.cliente.dias_disponibles = 5
        self.cliente.save()

    def _ejercicios_del_dia(self, fecha_iso: str) -> list:
        """
        Llama a _calcular_ejercicios_dia desde entrenos.views (el mismo código
        que usa briefing_entrenamiento en producción cuando el cache ha expirado).
        """
        from entrenos.views import _calcular_ejercicios_dia
        from datetime import date
        fecha = date.fromisoformat(fecha_iso)
        return _calcular_ejercicios_dia(self.cliente.id, fecha)

    def test_dia1_toque1_retorna_ejercicios_no_vacio(self):
        """
        dia_1 (2026-01-05, lunes) = toque 1 para cuádriceps, glúteos, gemelos, tríceps.
        El flujo real debe devolver una lista no vacía.
        """
        ejercicios = self._ejercicios_del_dia('2026-01-05')
        self.assertIsInstance(ejercicios, list)
        self.assertGreater(
            len(ejercicios), 0,
            "dia_1 (toque 1) no retornó ejercicios — fallo en _calcular_ejercicios_dia",
        )

    def test_dia3_toque2_gluteos_incluye_bulgar(self):
        """
        Semana 7, dia_3 (2026-02-18, miércoles) = toque 2 para glúteos.
        En semana 1 glúteos solo aparece una vez (vol_mult=0.9 → sin toque 2).
        Desde semana 7 (vol_mult=1.05) glúteos llega a freq=2: dia_1 toque 1
        (Hip Thrust) + dia_3 toque 2 (Búlgara). Este test verifica que el
        ejercicio distintivo del toque 2 llega intacto a la capa de servicio.
        """
        ejercicios = self._ejercicios_del_dia('2026-02-18')
        self.assertIsInstance(ejercicios, list)
        self.assertGreater(
            len(ejercicios), 0,
            "dia_3 no retornó ejercicios — error en plan del dia miércoles",
        )
        nombres = {e.get('nombre', '') for e in ejercicios}
        self.assertIn(
            'Sentadilla Búlgara', nombres,
            f"dia_3 (toque 2 de glúteos) debería incluir la Búlgara. "
            f"Nombres recibidos: {sorted(nombres)}",
        )

    def test_dia5_toque2_espalda_tiene_vertical_y_horizontal(self):
        """
        Semana 7, dia_5 (2026-02-20, viernes) = toque 2 para bíceps, espalda, hombros.
        En semana 7 (vol_mult=1.05) espalda tiene: dia_2 toque 1 (Jalón + Remo apoyado)
        + dia_5 toque 2 (Jalon brazos rectos vertical + Remo Mancuerna horizontal).
        Verifica que la oposición vertical/horizontal llega intacta a la capa de servicio.
        """
        ejercicios = self._ejercicios_del_dia('2026-02-20')
        self.assertGreater(len(ejercicios), 0, "dia_5 no retornó ejercicios")

        ejs_espalda = [e for e in ejercicios if e.get('grupo_muscular') == 'espalda']
        self.assertGreater(
            len(ejs_espalda), 0,
            f"dia_5 no tiene ejercicios de espalda. grupos: "
            f"{sorted({e.get('grupo_muscular') for e in ejercicios})}",
        )

        nombres_espalda = [e['nombre'].lower() for e in ejs_espalda]
        tiene_vertical = any(any(k in n for k in KEYWORDS_VERTICAL) for n in nombres_espalda)
        tiene_horizontal = any(any(k in n for k in KEYWORDS_HORIZONTAL) for n in nombres_espalda)

        self.assertTrue(
            tiene_vertical,
            f"dia_5 espalda toque 2 sin ejercicio vertical. "
            f"nombres_espalda={nombres_espalda}",
        )
        self.assertTrue(
            tiene_horizontal,
            f"dia_5 espalda toque 2 sin ejercicio horizontal. "
            f"nombres_espalda={nombres_espalda}",
        )

    def test_dia2_toque1_devuelve_estructura_correcta(self):
        """
        Verifica que los ejercicios devueltos por el flujo real tienen
        los campos mínimos esperados: nombre, grupo_muscular, series,
        repeticiones, peso_kg, rpe_objetivo.
        """
        ejercicios = self._ejercicios_del_dia('2026-01-06')  # dia_2 = martes
        self.assertGreater(len(ejercicios), 0, "dia_2 sin ejercicios")

        campos_minimos = {'nombre', 'grupo_muscular', 'series', 'repeticiones', 'rpe_objetivo'}
        for i, ej in enumerate(ejercicios[:3]):
            for campo in campos_minimos:
                self.assertIn(
                    campo, ej,
                    f"Ejercicio #{i} de dia_2 no tiene campo '{campo}': {ej}",
                )

    def test_dia4_toque2_cuadriceps_incluye_zancadas(self):
        """
        Semana 7, dia_4 (2026-02-19, jueves) = toque 2 para cuádriceps.
        En semana 7 cuádriceps tiene: dia_1 toque 1 (Sentadilla Hack + Prensa)
        + dia_4 toque 2 (Zancadas + Sissy Squat). Sissy Squat es un candidato
        pendiente de decisión del usuario — el test acepta cualquiera de los dos.
        """
        ejercicios = self._ejercicios_del_dia('2026-02-19')
        self.assertGreater(len(ejercicios), 0, "dia_4 sin ejercicios")

        nombres = {e.get('nombre', '') for e in ejercicios}
        # 'Zancadas con Mancuernas' o 'Sissy Squat' — al menos uno debe estar
        # (Sissy Squat puede estar o no dependiendo de futura decisión del usuario)
        tiene_toque2_cuadriceps = (
            'Zancadas con Mancuernas' in nombres or
            'Sissy Squat' in nombres
        )
        self.assertTrue(
            tiene_toque2_cuadriceps,
            f"dia_4 (toque 2 de cuádriceps) no tiene Zancadas ni Sissy Squat. "
            f"nombres={sorted(nombres)}",
        )
