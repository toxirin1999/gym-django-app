# analytics/test_planificador_helms_x5.py
"""
Tests TDD para X.5 — motor de frecuencia aislado.

Función pura `frecuencia_desde_volumen` que invierte la relación
volumen→frecuencia: en lugar de que la frecuencia sea un subproducto fijo
del split estático (DISTRIBUCION_DIAS), la frecuencia se deriva del volumen
objetivo y del techo de series por sesión.

Esta pieza vive aislada: NO está conectada a core.py ni a DISTRIBUCION_DIAS.
La integración con producción es X.7, gated por revisión del usuario.

Grupos de tests:
  TestFrecuenciaDesdeVolumen       — casos básicos (tope 3, tope días)
  TestVolumenCero                  — volumen_objetivo=0 → freq=0
  TestCapSesionGrupo               — diferenciación grandes vs pequeños
  TestCaracterizacionDavid         — tabla informativa: qué pediría el motor
                                     para el perfil real de david (avanzado,
                                     5 días, objetivo='general')
  TestDeterminismo                 — función pura: mismo input → mismo output
"""

import math

from django.test import TestCase

from analytics.planificador_helms.distribucion.frecuencia import (
    calcular_frecuencia,
    cap_sesion_para_grupo,
    frecuencia_desde_volumen,
)
from analytics.planificador_helms.config import GRUPOS_GRANDES, LIMITES_SERIES_SESION
from analytics.planificador_helms.volumen.calculadora import calcular_volumen_optimo
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente


# ---------------------------------------------------------------------------
# Constantes de test
# ---------------------------------------------------------------------------

_CAP_GRANDE = LIMITES_SERIES_SESION['grupos_grandes']['max']    # 10
_CAP_PEQUENO = LIMITES_SERIES_SESION['grupos_pequenos']['max']  # 8

# Perfil real del desarrollador — el mismo que usan los tests de caracterización
_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}

# Los 12 grupos del plan, en el mismo orden que la tabla de config
_GRUPOS = [
    'pecho', 'espalda', 'hombros', 'biceps', 'triceps',
    'cuadriceps', 'isquios', 'gluteos',
    'gemelos', 'core', 'trapecios', 'antebrazos',
]


# ---------------------------------------------------------------------------
# TestFrecuenciaDesdeVolumen
# ---------------------------------------------------------------------------

class TestFrecuenciaDesdeVolumen(TestCase):
    """Casos básicos de frecuencia_desde_volumen."""

    # ── Caso 1: volumen bajo → freq 1 ────────────────────────────────────────

    def test_volumen_bajo_da_freq_1(self):
        # ceil(6 / 10) = 1
        self.assertEqual(frecuencia_desde_volumen(6, _CAP_GRANDE, 5), 1)

    def test_volumen_minimo_igual_cap_da_freq_1(self):
        # ceil(10 / 10) = 1; el grupo cabe entero en una sesión
        self.assertEqual(frecuencia_desde_volumen(10, _CAP_GRANDE, 5), 1)

    # ── Caso 1: volumen supera 1×cap pero no 2×cap → freq 2 ─────────────────

    def test_volumen_supera_un_cap_da_freq_2(self):
        # ceil(12 / 10) = 2
        self.assertEqual(frecuencia_desde_volumen(12, _CAP_GRANDE, 5), 2)

    def test_exactamente_dos_caps_da_freq_2(self):
        # ceil(20 / 10) = 2
        self.assertEqual(frecuencia_desde_volumen(20, _CAP_GRANDE, 5), 2)

    # ── Caso 1: tope duro en 3, aunque el volumen pida más ──────────────────

    def test_volumen_supera_dos_caps_da_freq_3(self):
        # ceil(21 / 10) = 3
        self.assertEqual(frecuencia_desde_volumen(21, _CAP_GRANDE, 5), 3)

    def test_tope_duro_3_con_volumen_absurdo(self):
        # ceil(100 / 10) = 10, pero min(3, 10, 5) = 3
        self.assertEqual(frecuencia_desde_volumen(100, _CAP_GRANDE, 5), 3)

    def test_tope_duro_3_no_superable_ningun_volumen(self):
        for vol in [25, 40, 80, 200, 1000]:
            with self.subTest(vol=vol):
                self.assertLessEqual(
                    frecuencia_desde_volumen(vol, _CAP_GRANDE, 5),
                    3,
                    msg=f'Freq con volumen={vol} supera el tope duro de 3',
                )

    # ── Caso 2: dias_disponibles como techo adicional ────────────────────────

    def test_dias_disponibles_limita_cuando_es_menor_que_freq_deseada(self):
        # ceil(25 / 10) = 3, min(3, 3, 2) = 2 — dias gana
        self.assertEqual(frecuencia_desde_volumen(25, _CAP_GRANDE, 2), 2)

    def test_dias_disponibles_limita_con_volumen_absurdo(self):
        # ceil(100 / 8) = 13, min(3, 13, 2) = 2 — dias gana sobre el tope duro
        self.assertEqual(frecuencia_desde_volumen(100, _CAP_PEQUENO, 2), 2)

    def test_los_tres_terminos_del_min_en_juego(self):
        # Tres roles distintos para los tres términos:
        # A) freq_deseada < cap_duro < dias → freq_deseada manda
        self.assertEqual(frecuencia_desde_volumen(8, _CAP_GRANDE, 5), 1)
        # B) cap_duro < freq_deseada, dias >= cap_duro → cap_duro manda
        self.assertEqual(frecuencia_desde_volumen(100, _CAP_GRANDE, 5), 3)
        # C) dias < freq_deseada y dias < cap_duro → dias manda
        self.assertEqual(frecuencia_desde_volumen(100, _CAP_PEQUENO, 2), 2)

    def test_dias_1_impone_freq_1_sin_importar_volumen(self):
        self.assertEqual(frecuencia_desde_volumen(100, _CAP_GRANDE, 1), 1)


# ---------------------------------------------------------------------------
# TestVolumenCero
# ---------------------------------------------------------------------------

class TestVolumenCero(TestCase):
    """volumen_objetivo=0 (o negativo) → freq=0."""

    def test_volumen_cero_da_freq_0(self):
        self.assertEqual(frecuencia_desde_volumen(0, _CAP_GRANDE, 5), 0)

    def test_volumen_negativo_da_freq_0(self):
        # Dato corrupto o descarga extrema — no debe explotar ni dar negativo
        self.assertEqual(frecuencia_desde_volumen(-5, _CAP_GRANDE, 5), 0)

    def test_calcular_frecuencia_con_vol_cero(self):
        self.assertEqual(calcular_frecuencia('pecho', 0, 5), 0)


# ---------------------------------------------------------------------------
# TestCapSesionGrupo
# ---------------------------------------------------------------------------

class TestCapSesionGrupo(TestCase):
    """cap_sesion_para_grupo diferencia correctamente grandes de pequeños."""

    def test_grupos_grandes_usan_cap_10(self):
        for g in ['pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos']:
            with self.subTest(grupo=g):
                self.assertEqual(cap_sesion_para_grupo(g), _CAP_GRANDE)

    def test_grupos_pequenos_usan_cap_8(self):
        for g in ['biceps', 'triceps', 'hombros', 'gemelos', 'core', 'trapecios', 'antebrazos']:
            with self.subTest(grupo=g):
                self.assertEqual(cap_sesion_para_grupo(g), _CAP_PEQUENO)

    def test_mismo_volumen_da_distinta_frecuencia_segun_grupo(self):
        # volumen=9:
        #   grande  (cap=10): ceil(9/10)=1
        #   pequeño (cap=8):  ceil(9/8) =2
        # El mismo volumen objetivo produce frecuencias distintas según el grupo.
        self.assertEqual(calcular_frecuencia('pecho', 9, 5), 1)    # grande
        self.assertEqual(calcular_frecuencia('biceps', 9, 5), 2)   # pequeño

    def test_diferenciacion_visible_en_resultado_final(self):
        # volumen=17:
        #   grande  (cap=10): ceil(17/10)=2 → 2
        #   pequeño (cap=8):  ceil(17/8) =3 → 3 (topado en cap duro = 3)
        self.assertEqual(calcular_frecuencia('pecho', 17, 5), 2)
        self.assertEqual(calcular_frecuencia('hombros', 17, 5), 3)


# ---------------------------------------------------------------------------
# TestCaracterizacionDavid
# ---------------------------------------------------------------------------

class TestCaracterizacionDavid(TestCase):
    """
    Test informativo/de caracterización.

    Documenta qué frecuencia 'querría' el nuevo motor para cada grupo muscular
    del plan de david (avanzado, objetivo='general', 5 días) si no estuviera
    atado a DISTRIBUCION_DIAS. Sirve como línea base para X.6/X.7.

    Frecuencias actuales: todas = 1 (split estático).
    Frecuencias que pediría el nuevo motor (calculadas con volumen real):

      espalda, hombros, cuadriceps → 3
      pecho, biceps, triceps, isquios, gluteos, gemelos, core, trapecios → 2
      antebrazos → 1

    Este test falla si calcular_volumen_optimo o los caps de sesión cambian,
    lo que indicaría que la tabla de la memoria del proyecto necesita revisión.
    """

    # Frecuencias esperadas calculadas con:
    #   nivel='avanzado', objetivo='general', factor=1.09
    #   cap_sesion_para_grupo(grupo), dias_disponibles=5
    # Verificado el 2026-07-20 tras anclar objetivo='general' al MEV (volumen
    # moderado, decisión explícita del usuario). Con volumen más bajo, ningún
    # grupo pide ya freq=3 — el máximo deseado es freq=2.
    FREQ_ESPERADA = {
        'pecho':       2,
        'espalda':     2,
        'hombros':     2,
        'biceps':      2,
        'triceps':     2,
        'cuadriceps':  2,
        'isquios':     1,
        'gluteos':     2,
        'gemelos':     2,
        'core':        1,
        'trapecios':   1,
        'antebrazos':  1,
    }

    def setUp(self):
        perfil = PerfilCliente(_DAVID)
        self._nivel = perfil.calcular_nivel_experiencia()
        self._objetivo = perfil.objetivo_principal
        self._factor = perfil.calcular_factor_recuperacion()
        self._dias = _DAVID['dias_disponibles']

    def test_factor_recuperacion_david_es_1_09(self):
        # Documenta el factor exacto para que sea visible si PerfilCliente cambia
        self.assertAlmostEqual(self._factor, 1.09, places=2)

    def test_nivel_david_es_avanzado(self):
        self.assertEqual(self._nivel, 'avanzado')

    def test_frecuencias_deseadas_por_grupo(self):
        for grupo in _GRUPOS:
            with self.subTest(grupo=grupo):
                vol = calcular_volumen_optimo(grupo, self._nivel, self._objetivo, self._factor)
                freq = calcular_frecuencia(grupo, vol, self._dias)
                self.assertEqual(
                    freq,
                    self.FREQ_ESPERADA[grupo],
                    msg=(
                        f'{grupo}: vol_objetivo={vol}, '
                        f'cap={cap_sesion_para_grupo(grupo)}, '
                        f'freq_calculada={freq}, '
                        f'freq_esperada={self.FREQ_ESPERADA[grupo]}'
                    ),
                )

    def test_ningun_grupo_pide_ya_freq_3(self):
        """
        Con objetivo='general' anclado al MEV (2026-07-20, volumen moderado),
        ningún grupo supera 2×cap — antes (volumen alto) espalda/hombros/
        cuadriceps pedían freq=3, ahora el máximo deseado es freq=2.
        """
        for grupo in ['espalda', 'hombros', 'cuadriceps']:
            with self.subTest(grupo=grupo):
                vol = calcular_volumen_optimo(grupo, self._nivel, self._objetivo, self._factor)
                self.assertEqual(calcular_frecuencia(grupo, vol, self._dias), 2)

    def test_antebrazos_conserva_freq_1(self):
        # Único grupo cuyo volumen cabe en una sola sesión con el cap de pequeños
        vol = calcular_volumen_optimo('antebrazos', self._nivel, self._objetivo, self._factor)
        self.assertEqual(calcular_frecuencia('antebrazos', vol, self._dias), 1)

    def test_ningun_grupo_supera_freq_3(self):
        for grupo in _GRUPOS:
            with self.subTest(grupo=grupo):
                vol = calcular_volumen_optimo(grupo, self._nivel, self._objetivo, self._factor)
                freq = calcular_frecuencia(grupo, vol, self._dias)
                self.assertLessEqual(freq, 3)

    def test_ningun_grupo_cae_a_freq_0(self):
        for grupo in _GRUPOS:
            with self.subTest(grupo=grupo):
                vol = calcular_volumen_optimo(grupo, self._nivel, self._objetivo, self._factor)
                freq = calcular_frecuencia(grupo, vol, self._dias)
                self.assertGreater(freq, 0)


# ---------------------------------------------------------------------------
# TestDeterminismo
# ---------------------------------------------------------------------------

class TestDeterminismo(TestCase):
    """
    Las tres funciones son puras: el mismo input produce siempre el mismo output.

    Requisito duro del diseño completo — SesionProgramada persiste y casa
    sesiones por rutina_nombre, así que el motor no puede producir asignaciones
    distintas entre recargas.
    """

    def test_frecuencia_desde_volumen_es_determinista(self):
        args = (20, _CAP_GRANDE, 5)
        resultado_1 = frecuencia_desde_volumen(*args)
        resultado_2 = frecuencia_desde_volumen(*args)
        self.assertEqual(resultado_1, resultado_2)

    def test_cap_sesion_para_grupo_es_determinista(self):
        self.assertEqual(cap_sesion_para_grupo('pecho'), cap_sesion_para_grupo('pecho'))
        self.assertEqual(cap_sesion_para_grupo('biceps'), cap_sesion_para_grupo('biceps'))

    def test_calcular_frecuencia_es_determinista(self):
        args = ('espalda', 22, 5)
        self.assertEqual(calcular_frecuencia(*args), calcular_frecuencia(*args))

    def test_multiples_llamadas_producen_mismo_resultado(self):
        casos = [
            ('pecho', 20, 5),
            ('biceps', 13, 3),
            ('cuadriceps', 22, 5),
            ('antebrazos', 7, 5),
        ]
        for grupo, vol, dias in casos:
            with self.subTest(grupo=grupo):
                resultados = [calcular_frecuencia(grupo, vol, dias) for _ in range(5)]
                self.assertEqual(len(set(resultados)), 1, msg=f'Resultados no deterministas: {resultados}')
