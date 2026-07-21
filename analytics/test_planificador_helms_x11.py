# analytics/test_planificador_helms_x11.py
"""
Tests TDD para X.11 — Config (REP_RANGE_TOQUE, ROL_TOQUE) + módulo puro
ejercicios/variacion.py (derivar_rep_rpe_toque, construir_variantes_por_toque).

Funciones puras, sin BD. Se usa unittest.TestCase directamente;
el runner de Django lo descubre igualmente.
"""

import unittest

from analytics.planificador_helms.ejercicios.variacion import (
    derivar_rep_rpe_toque,
    construir_variantes_por_toque,
)
from analytics.planificador_helms.config import (
    REP_RANGE_TOQUE,
    ROL_TOQUE,
    KEYWORDS_VERTICAL,
    KEYWORDS_HORIZONTAL,
)


# ---------------------------------------------------------------------------
# Helpers de construcción de ejercicios sintéticos
# ---------------------------------------------------------------------------

def _ej(nombre: str, perfil: str = 'media', **kwargs) -> dict:
    return {'nombre': nombre, 'perfil': perfil, **kwargs}


def _pool(principal=None, secundario=None, aislamiento=None) -> dict:
    return {
        'compuesto_principal': principal or [],
        'compuesto_secundario': secundario or [],
        'aislamiento': aislamiento or [],
    }


# ===========================================================================
# Tests para derivar_rep_rpe_toque
# ===========================================================================

class TestDerivarRepRpeToque(unittest.TestCase):

    # ── Prueba requerida 1 ──────────────────────────────────────────────────
    def test_toque1_identidad_exacta(self):
        """Toque 1: devuelve exactamente (rep_range_base, rpe_objetivo) sin cambio."""
        self.assertEqual(derivar_rep_rpe_toque('8-12', 8, 1), ('8-12', 8))

    # ── Prueba requerida 2 ──────────────────────────────────────────────────
    def test_toque2_sube_rep_range_y_baja_rpe(self):
        """Toque 2: '8-12' → '12-15', RPE 8 → 7."""
        self.assertEqual(derivar_rep_rpe_toque('8-12', 8, 2), ('12-15', 7))

    # ── Prueba requerida 3 ──────────────────────────────────────────────────
    def test_toque3_sube_mas_que_toque2(self):
        """Toque 3: sube un peldaño más que toque 2 sobre el mismo base."""
        rr_t2 = derivar_rep_rpe_toque('8-12', 8, 2)[0]
        rr_t3 = derivar_rep_rpe_toque('8-12', 8, 3)[0]
        # t2: '8-12'→'12-15';  t3: '8-12'→'15-20'
        self.assertEqual(rr_t2, '12-15')
        self.assertEqual(rr_t3, '15-20')

    # ── Prueba requerida 4 ──────────────────────────────────────────────────
    def test_techo_idempotente_15_20(self):
        """'15-20' en cualquier toque se queda en '15-20'."""
        self.assertEqual(derivar_rep_rpe_toque('15-20', 8, 2)[0], '15-20')
        self.assertEqual(derivar_rep_rpe_toque('15-20', 8, 3)[0], '15-20')

    # ── Prueba requerida 5 ──────────────────────────────────────────────────
    def test_rpe_no_baja_de_6(self):
        """RPE nunca baja de 6 aunque rpe_objetivo sea 6."""
        self.assertEqual(derivar_rep_rpe_toque('8-12', 6, 2)[1], 6)

    # ── Prueba requerida 6 ──────────────────────────────────────────────────
    def test_clave_desconocida_no_lanza_excepcion(self):
        """Rep_range desconocido devuelve el base sin cambio, sin excepción."""
        result = derivar_rep_rpe_toque('20-25', 8, 2)
        self.assertEqual(result[0], '20-25')

    # ── Prueba adicional: toque 1 para varios rangos ─────────────────────────
    def test_toque1_identidad_varios_rangos(self):
        """Toque 1 es identidad para cualquier rep_range y RPE."""
        casos = [('6-8', 7), ('12-15', 8), ('15-20', 9), ('2-4', 10)]
        for rr, rpe in casos:
            with self.subTest(rep_range=rr, rpe=rpe):
                self.assertEqual(derivar_rep_rpe_toque(rr, rpe, 1), (rr, rpe))

    # ── Prueba adicional: cobertura de '6-8' en toque 2 ─────────────────────
    def test_toque2_6_8_sube_a_8_10(self):
        """'6-8' en toque 2 sube a '8-10' según REP_RANGE_TOQUE."""
        self.assertEqual(derivar_rep_rpe_toque('6-8', 8, 2)[0], '8-10')

    def test_rpe_baja_exactamente_1_cuando_hay_margen(self):
        """RPE se reduce en 1 cuando rpe_objetivo > 6."""
        self.assertEqual(derivar_rep_rpe_toque('8-12', 9, 2)[1], 8)
        self.assertEqual(derivar_rep_rpe_toque('8-12', 7, 2)[1], 6)


# ===========================================================================
# Tests para construir_variantes_por_toque
# ===========================================================================

class TestConstruirVariantesPorToque(unittest.TestCase):

    # ── Prueba requerida 7 ──────────────────────────────────────────────────
    def test_toque1_en_resultado_es_exactamente_ejercicios_toque1(self):
        """Toque 1 en el resultado es el mismo objeto que ejercicios_toque1."""
        toque1 = [_ej('Curl Barra'), _ej('Curl Martillo')]
        pool = _pool(
            principal=[_ej('Curl Barra')],
            secundario=[_ej('Curl Martillo')],
            aislamiento=[_ej('Curl Predicador', 'acortado')],
        )
        resultado = construir_variantes_por_toque('biceps', 2, False, pool, toque1)
        self.assertIs(resultado[1], toque1)

    # ── Prueba requerida 8 ──────────────────────────────────────────────────
    def test_toque2_excluye_nombres_toque1_y_prioriza_estirado(self):
        """Toque 2: excluye toque 1 por nombre y pone estirado primero."""
        toque1 = [_ej('Curl Barra', 'media')]
        pool = _pool(
            principal=[_ej('Curl Barra', 'media')],
            secundario=[
                _ej('Curl Mancuerna Inclinado', 'estirado'),
                _ej('Curl Predicador', 'acortado'),
            ],
            aislamiento=[_ej('Curl Concentrado', 'acortado')],
        )
        resultado = construir_variantes_por_toque('biceps', 2, False, pool, toque1)
        toque2 = resultado[2]

        nombres_t2 = [e['nombre'] for e in toque2]
        self.assertNotIn('Curl Barra', nombres_t2)
        self.assertEqual(toque2[0]['nombre'], 'Curl Mancuerna Inclinado')

    # ── Prueba requerida 9 ──────────────────────────────────────────────────
    def test_toque3_excluye_toque1_y_toque2_prioriza_acortado(self):
        """Freq=3: toque 3 excluye toque1+toque2 y prioriza perfil='acortado'."""
        toque1 = [_ej('Curl Barra', 'media')]
        pool = _pool(
            principal=[_ej('Curl Barra', 'media')],
            secundario=[_ej('Curl Mancuerna Inclinado', 'estirado')],
            aislamiento=[
                _ej('Curl Concentrado', 'acortado'),
                _ej('Curl Cable', 'media'),
            ],
        )
        resultado = construir_variantes_por_toque('biceps', 3, False, pool, toque1)

        nombres_t1 = {e['nombre'] for e in resultado[1]}
        nombres_t2 = {e['nombre'] for e in resultado[2]}
        nombres_t3 = {e['nombre'] for e in resultado[3]}

        # Toque 3 no repite ningún nombre de toque 1 ni toque 2
        self.assertFalse(nombres_t3 & (nombres_t1 | nombres_t2))
        # El primero en toque 3 tiene perfil acortado
        self.assertEqual(resultado[3][0]['perfil'], 'acortado')

    # ── Prueba requerida 10 ─────────────────────────────────────────────────
    def test_espalda_oposicion_vertical_horizontal_en_toque2(self):
        """Espalda freq=2: toque 2 contiene 1 vertical y 1 horizontal."""
        toque1 = [
            _ej('Dominadas', 'estirado'),
            _ej('Remo con Barra', 'media'),
        ]
        pool = _pool(
            principal=[
                _ej('Dominadas', 'estirado'),
                _ej('Remo con Barra', 'media'),
            ],
            secundario=[
                _ej('Jalón al Pecho', 'estirado'),   # vertical: 'jalón'
                _ej('Remo Mancuerna', 'media'),       # horizontal: 'remo' + 'mancuerna'
            ],
            aislamiento=[_ej('Pull-over Polea', 'acortado')],
        )
        resultado = construir_variantes_por_toque('espalda', 2, True, pool, toque1)
        toque2 = resultado[2]

        nombres_t2 = [e['nombre'].lower() for e in toque2]
        tiene_vertical = any(any(k in n for k in KEYWORDS_VERTICAL) for n in nombres_t2)
        tiene_horizontal = any(any(k in n for k in KEYWORDS_HORIZONTAL) for n in nombres_t2)

        self.assertTrue(tiene_vertical, f"Sin vertical en toque2 espalda: {nombres_t2}")
        self.assertTrue(tiene_horizontal, f"Sin horizontal en toque2 espalda: {nombres_t2}")
        # Además, no deben repetirse nombres del toque 1
        nombres_t1 = {e['nombre'].lower() for e in toque1}
        for n in nombres_t2:
            self.assertNotIn(n, nombres_t1, f"'{n}' repetido del toque 1")

    # ── Prueba requerida 11 ─────────────────────────────────────────────────
    def test_fallback_pool_insuficiente_devuelve_toque1(self):
        """Pool con solo el ejercicio de toque1: toque2 = toque1 (fallback)."""
        toque1 = [_ej('Curl Barra', 'media')]
        # El único candidato del pool es el mismo de toque1 — queda excluido.
        pool = _pool(principal=[_ej('Curl Barra', 'media')])
        resultado = construir_variantes_por_toque('biceps', 2, False, pool, toque1)
        toque2 = resultado[2]

        self.assertEqual(len(toque2), len(toque1))
        self.assertEqual(toque2[0]['nombre'], 'Curl Barra')

    # ── Prueba requerida 12 ─────────────────────────────────────────────────
    def test_determinismo(self):
        """Misma entrada produce el mismo resultado en llamadas repetidas."""
        toque1 = [_ej('Curl Barra', 'media')]
        pool = _pool(
            principal=[_ej('Curl Barra', 'media')],
            secundario=[_ej('Curl Mancuerna Inclinado', 'estirado')],
            aislamiento=[_ej('Curl Predicador', 'acortado')],
        )
        r1 = construir_variantes_por_toque('biceps', 2, False, pool, toque1)
        r2 = construir_variantes_por_toque('biceps', 2, False, pool, toque1)
        self.assertEqual(
            [e['nombre'] for e in r1[2]],
            [e['nombre'] for e in r2[2]],
        )

    # ── Pruebas adicionales ─────────────────────────────────────────────────

    def test_frecuencia_1_solo_contiene_toque1(self):
        """Con frecuencia=1, el resultado tiene exactamente el toque 1."""
        toque1 = [_ej('Sentadilla', 'media')]
        pool = _pool(principal=[_ej('Sentadilla', 'media')])
        resultado = construir_variantes_por_toque('cuadriceps', 1, True, pool, toque1)
        self.assertEqual(list(resultado.keys()), [1])

    def test_toque2_mismo_numero_ejercicios_que_toque1(self):
        """Toque 2 siempre tiene el mismo número de ejercicios que toque 1."""
        toque1 = [_ej('Dominadas', 'estirado'), _ej('Remo Barra', 'media')]
        # Pool solo tiene los mismos — el fallback debe cubrir 2 posiciones.
        pool = _pool(
            principal=[_ej('Dominadas', 'estirado'), _ej('Remo Barra', 'media')],
        )
        resultado = construir_variantes_por_toque('espalda', 2, True, pool, toque1)
        self.assertEqual(len(resultado[2]), len(toque1))

    def test_toque2_usa_orden_categoria_secundario_primero(self):
        """Toque 2 recorre secundario antes que principal en el orden de categoría."""
        toque1 = [_ej('Sentadilla', 'media')]
        # El secundario (no excluido) debe aparecer antes que principal en el resultado.
        pool = _pool(
            principal=[_ej('Sentadilla', 'media'), _ej('Prensa', 'media')],
            secundario=[_ej('Hack Squat', 'media')],
        )
        resultado = construir_variantes_por_toque('cuadriceps', 2, True, pool, toque1)
        # Hack Squat (secundario) debe ser el primero en toque 2 al no tener
        # competencia de perfil preferido y recorrerse primero en el orden.
        self.assertEqual(resultado[2][0]['nombre'], 'Hack Squat')

    def test_espalda_fallback_si_pool_no_permite_oposicion(self):
        """Si el pool de espalda solo tiene verticales, no lanza excepción."""
        toque1 = [_ej('Dominadas', 'estirado'), _ej('Jalón Cerrado', 'estirado')]
        pool = _pool(
            principal=[_ej('Dominadas', 'estirado'), _ej('Jalón Cerrado', 'estirado')],
            secundario=[_ej('Jalón al Pecho', 'estirado')],  # otro vertical
        )
        try:
            resultado = construir_variantes_por_toque('espalda', 2, True, pool, toque1)
        except Exception as exc:
            self.fail(f"construir_variantes_por_toque levantó excepción inesperada: {exc}")
        # El toque 2 debe tener el mismo número de ejercicios que toque 1
        self.assertEqual(len(resultado[2]), len(toque1))
