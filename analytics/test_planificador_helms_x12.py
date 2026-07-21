# analytics/test_planificador_helms_x12.py
"""
Tests TDD para X.12 — SelectorEjercicios.construir_pool_seguro_por_grupo().

Módulo puro con un toque de Django (usa unittest.TestCase: sin BD, sin fixtures).
Todos deben fallar antes de la implementación y pasar en verde después.
"""

import unittest
from unittest.mock import patch, MagicMock

from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
from analytics.planificador_helms.ejercicios.variacion import construir_variantes_por_toque
from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE


# ===========================================================================
# Test 1 — Sin truncar: el pool devuelto tiene TODOS los candidatos
# ===========================================================================

class TestPoolSinTruncar(unittest.TestCase):
    """
    seleccionar_ejercicios_para_bloque trunca a max_ej=2.
    construir_pool_seguro_por_grupo NO debe truncar: devuelve el pool completo.
    cuadriceps.compuesto_principal tiene 4 entradas en el catálogo real.
    """

    def test_compuesto_principal_devuelve_todos_sin_truncar(self):
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('cuadriceps', 'hipertrofia')
        # El catálogo real tiene 4 ejercicios en cuadriceps.compuesto_principal
        raw_count = len(EJERCICIOS_DATABASE['cuadriceps']['compuesto_principal'])
        self.assertGreaterEqual(
            len(pool['compuesto_principal']),
            raw_count,
            f"Se esperaban al menos {raw_count} ejercicios en compuesto_principal; "
            f"se obtuvieron {len(pool['compuesto_principal'])}",
        )
        self.assertGreater(
            len(pool['compuesto_principal']), 2,
            "El pool no debe estar truncado a 2 — debe retornar todos los candidatos",
        )


# ===========================================================================
# Test 2 — Estructura del resultado: siempre 4 claves exactas
# ===========================================================================

class TestEstructuraResultado(unittest.TestCase):

    CLAVES_ESPERADAS = {
        'compuesto_principal',
        'compuesto_secundario',
        'aislamiento',
        'variantes_compartidas',
    }

    def test_resultado_tiene_exactamente_4_claves(self):
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('biceps', 'hipertrofia')
        self.assertEqual(
            set(pool.keys()), self.CLAVES_ESPERADAS,
            f"Claves del resultado: {set(pool.keys())}; "
            f"esperadas: {self.CLAVES_ESPERADAS}",
        )

    def test_todas_las_claves_son_listas(self):
        for grupo in ['biceps', 'gluteos', 'cuadriceps', 'espalda']:
            with self.subTest(grupo=grupo):
                pool = SelectorEjercicios.construir_pool_seguro_por_grupo(grupo, 'hipertrofia')
                for clave in self.CLAVES_ESPERADAS:
                    self.assertIsInstance(
                        pool[clave], list,
                        f"pool['{clave}'] no es una lista en grupo '{grupo}'",
                    )

    def test_grupos_sin_variantes_compartidas_devuelven_lista_vacia(self):
        # La mayoría de grupos no tienen variantes_compartidas en el catálogo
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('biceps', 'hipertrofia')
        self.assertEqual(
            pool['variantes_compartidas'], [],
            "biceps no tiene variantes_compartidas — debe ser lista vacía",
        )


# ===========================================================================
# Test 3 — Búlgara aparece en variantes_compartidas para glúteos
# ===========================================================================

class TestBulgaraAparaceParaGluteos(unittest.TestCase):
    """
    El catálogo tiene Sentadilla Búlgara en gluteos.variantes_compartidas (X.10).
    construir_pool_seguro_por_grupo debe incluirla en esa clave del resultado.
    """

    def test_bulgara_en_variantes_compartidas_gluteos(self):
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('gluteos', 'hipertrofia')
        nombres = [e['nombre'] for e in pool['variantes_compartidas']]
        self.assertIn(
            'Sentadilla Búlgara', nombres,
            f"'Sentadilla Búlgara' no aparece en variantes_compartidas de glúteos. "
            f"Contenido: {nombres}",
        )

    def test_bulgara_en_variantes_compartidas_fase_fuerza(self):
        # La búlgara no está restringida por la fase fuerza (evitar_contiene=[])
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('gluteos', 'fuerza')
        nombres = [e['nombre'] for e in pool['variantes_compartidas']]
        self.assertIn('Sentadilla Búlgara', nombres)


# ===========================================================================
# Test 4 — Búlgara NO aparece para grupos sin esa categoría en el catálogo
# ===========================================================================

class TestBulgaraNoAparaceEnOtrosGrupos(unittest.TestCase):

    def test_biceps_variantes_compartidas_vacio(self):
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('biceps', 'hipertrofia')
        self.assertEqual(pool['variantes_compartidas'], [])

    def test_cuadriceps_variantes_compartidas_vacio(self):
        # La búlgara VIVE en cuadriceps.compuesto_principal, no en variantes_compartidas
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('cuadriceps', 'hipertrofia')
        self.assertEqual(
            pool['variantes_compartidas'], [],
            "cuadriceps no tiene variantes_compartidas definidas en el catálogo",
        )

    def test_espalda_variantes_compartidas_vacio(self):
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('espalda', 'hipertrofia')
        self.assertEqual(pool['variantes_compartidas'], [])


# ===========================================================================
# Test 5 — Seguridad biológica intacta en las 4 categorías
# ===========================================================================

class TestSeguridadBiologica(unittest.TestCase):
    """
    Cuando el cliente tiene restricted_tags, ningún ejercicio con esos tags
    debe aparecer en ninguna de las 4 categorías del pool devuelto.
    """

    def _pool_con_restriccion(self, grupo, fase, tags):
        mock_cliente = MagicMock()
        with patch(
            'core.bio_context.BioContextProvider.get_current_restrictions',
            return_value={'tags': tags, 'injuries': []},
        ):
            return SelectorEjercicios.construir_pool_seguro_por_grupo(
                grupo, fase, cliente=mock_cliente
            )

    def test_tag_restringido_excluye_ejercicio_de_variantes_compartidas(self):
        """
        Búlgara tiene risk_tags=['flexion_rodilla_profunda', ...].
        Con ese tag activo, no debe aparecer en variantes_compartidas.
        """
        pool = self._pool_con_restriccion('gluteos', 'hipertrofia', {'flexion_rodilla_profunda'})
        nombres = [e['nombre'] for e in pool['variantes_compartidas']]
        self.assertNotIn(
            'Sentadilla Búlgara', nombres,
            f"La Búlgara tiene 'flexion_rodilla_profunda' en risk_tags — no debe aparecer. "
            f"Pool variantes_compartidas: {nombres}",
        )

    def test_tag_restringido_excluye_ejercicio_de_compuesto_principal(self):
        """
        cuadriceps.compuesto_principal: todos los ejercicios tienen 'flexion_rodilla_profunda'.
        Con ese tag activo, el pool principal de cuadriceps debe quedar vacío.
        """
        pool = self._pool_con_restriccion('cuadriceps', 'hipertrofia', {'flexion_rodilla_profunda'})
        # Todos los compuestos principales de cuadriceps tienen flexion_rodilla_profunda
        self.assertEqual(
            pool['compuesto_principal'], [],
            f"Se esperaba pool principal vacío con tag 'flexion_rodilla_profunda'. "
            f"Resultado: {[e['nombre'] for e in pool['compuesto_principal']]}",
        )

    def test_sin_cliente_no_aplica_filtro_bio(self):
        """Sin cliente, el pool devuelve todos (sin restricciones biológicas)."""
        pool_sin_cliente = SelectorEjercicios.construir_pool_seguro_por_grupo(
            'gluteos', 'hipertrofia', cliente=None
        )
        self.assertIn(
            'Sentadilla Búlgara',
            [e['nombre'] for e in pool_sin_cliente['variantes_compartidas']],
        )

    def test_excepcion_en_biocontext_no_rompe_el_metodo(self):
        """Si BioContextProvider lanza excepción, el método devuelve el pool sin filtro bio."""
        mock_cliente = MagicMock()
        with patch(
            'core.bio_context.BioContextProvider.get_current_restrictions',
            side_effect=Exception("BioContext no disponible"),
        ):
            # No debe lanzar excepción
            try:
                pool = SelectorEjercicios.construir_pool_seguro_por_grupo(
                    'gluteos', 'hipertrofia', cliente=mock_cliente
                )
            except Exception as exc:
                self.fail(f"construir_pool_seguro_por_grupo lanzó excepción inesperada: {exc}")
        # Pool devuelto sin filtro bio → Búlgara presente
        nombres = [e['nombre'] for e in pool['variantes_compartidas']]
        self.assertIn('Sentadilla Búlgara', nombres)


# ===========================================================================
# Test 6 — Reglas de fase aplicadas (evitar_contiene/permitir_variantes)
# ===========================================================================

class TestReglasFaseAplicadas(unittest.TestCase):
    """
    En hipertrofia, evitar_contiene=["peso muerto"], permitir_variantes=["rumano"].
    gluteos.compuesto_principal incluye "Peso Muerto Sumo" (contiene "peso muerto"
    pero no "rumano") → debe ser filtrado del pool en hipertrofia.
    """

    def test_peso_muerto_sumo_excluido_de_gluteos_en_hipertrofia(self):
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('gluteos', 'hipertrofia')
        nombres_principal = [e['nombre'] for e in pool['compuesto_principal']]
        self.assertNotIn(
            'Peso Muerto Sumo', nombres_principal,
            "'Peso Muerto Sumo' contiene 'peso muerto' y no es variante 'rumano' "
            "— no debe aparecer en compuesto_principal de glúteos en hipertrofia.",
        )
        # Hip Thrust sí debe aparecer (no contiene "peso muerto")
        self.assertIn(
            'Hip Thrust con Barra', nombres_principal,
            "'Hip Thrust con Barra' debe permanecer en el pool de hipertrofia.",
        )

    def test_peso_muerto_sumo_presente_en_gluteos_en_fuerza(self):
        """En fuerza, evitar_contiene=[] → Peso Muerto Sumo no debe filtrarse."""
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('gluteos', 'fuerza')
        nombres_principal = [e['nombre'] for e in pool['compuesto_principal']]
        self.assertIn(
            'Peso Muerto Sumo', nombres_principal,
            "'Peso Muerto Sumo' debe estar disponible en fase de fuerza.",
        )

    def test_rumano_permitido_en_hipertrofia(self):
        """
        isquios tiene "Peso Muerto Rumano" (contiene "peso muerto" y "rumano").
        Con permitir_variantes=["rumano"], debe aparecer en el pool de hipertrofia.
        """
        pool = SelectorEjercicios.construir_pool_seguro_por_grupo('isquios', 'hipertrofia')
        todos_nombres = (
            [e['nombre'] for e in pool['compuesto_principal']]
            + [e['nombre'] for e in pool['compuesto_secundario']]
        )
        self.assertIn(
            'Peso Muerto Rumano', todos_nombres,
            "'Peso Muerto Rumano' tiene 'rumano' en el nombre — debe ser permitido en hipertrofia.",
        )


# ===========================================================================
# Test 7 — Integración real X.11 + X.12: la Búlgara puede aparecer en toque 2
# ===========================================================================

class TestIntegracionX11X12(unittest.TestCase):
    """
    Prueba de integración: construir_pool_seguro_por_grupo (X.12) +
    construir_variantes_por_toque (X.11) + ROL_TOQUE[2] actualizado (X.12 Parte 2).

    Para que la Búlgara sea candidata en toque 2 de glúteos:
    1. construir_pool_seguro_por_grupo debe incluirla en pool_seguro['variantes_compartidas'].
    2. ROL_TOQUE[2]['orden_categoria'] debe incluir 'variantes_compartidas'.
    3. construir_variantes_por_toque debe poder seleccionarla al excluir los ejercicios de toque 1.
    """

    def _toque1_real_gluteos(self):
        """Obtiene el toque 1 real de glúteos desde seleccionar_ejercicios_para_bloque."""
        seleccion = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
            numero_bloque=1,
            fase='hipertrofia',
        )
        return seleccion.get('gluteos', [])

    def test_bulgara_puede_aparecer_en_toque2_gluteos(self):
        """
        Con pool_seguro completo (incluyendo variantes_compartidas con la Búlgara)
        y ROL_TOQUE[2] actualizado, toque 2 de glúteos debe poder incluir la Búlgara.
        """
        pool_seguro = SelectorEjercicios.construir_pool_seguro_por_grupo('gluteos', 'hipertrofia')
        toque1 = self._toque1_real_gluteos()

        # Verificación precondición: pool tiene la Búlgara
        nombres_variantes = [e['nombre'] for e in pool_seguro['variantes_compartidas']]
        self.assertIn(
            'Sentadilla Búlgara', nombres_variantes,
            "Precondición fallida: Búlgara no está en pool_seguro['variantes_compartidas']",
        )

        resultado = construir_variantes_por_toque(
            grupo='gluteos',
            frecuencia=2,
            es_grande=True,
            pool_seguro=pool_seguro,
            ejercicios_toque1=toque1,
        )

        self.assertIn(2, resultado, "El resultado debe contener el toque 2")
        toque2 = resultado[2]

        # Toque 2 no debe repetir nombres del toque 1
        nombres_t1 = {e['nombre'].lower() for e in toque1}
        for ej in toque2:
            self.assertNotIn(
                ej['nombre'].lower(), nombres_t1,
                f"'{ej['nombre']}' del toque 2 repite nombre del toque 1",
            )

        # La Búlgara debe ser candidata viable y estar en toque 2
        # (perfil='estirado' = perfil_preferido de toque 2)
        nombres_t2 = [e['nombre'] for e in toque2]
        self.assertIn(
            'Sentadilla Búlgara', nombres_t2,
            f"La Búlgara (perfil='estirado', variantes_compartidas) debería "
            f"aparecer en toque 2 de glúteos. toque2={nombres_t2}, toque1={[e['nombre'] for e in toque1]}",
        )

    def test_toque2_tiene_mismo_numero_ejercicios_que_toque1(self):
        """La longitud del toque 2 debe coincidir con la del toque 1 (fallback garantiza esto)."""
        pool_seguro = SelectorEjercicios.construir_pool_seguro_por_grupo('gluteos', 'hipertrofia')
        toque1 = self._toque1_real_gluteos()

        resultado = construir_variantes_por_toque('gluteos', 2, True, pool_seguro, toque1)
        self.assertEqual(len(resultado[2]), len(toque1))

    def test_toque1_en_resultado_es_identico_al_selector_original(self):
        """El toque 1 en el resultado de construir_variantes_por_toque es byte-idéntico al entrada."""
        pool_seguro = SelectorEjercicios.construir_pool_seguro_por_grupo('gluteos', 'hipertrofia')
        toque1 = self._toque1_real_gluteos()

        resultado = construir_variantes_por_toque('gluteos', 2, True, pool_seguro, toque1)
        self.assertIs(resultado[1], toque1, "El toque 1 debe ser el mismo objeto, sin copiar")

    def test_rol_toque2_incluye_variantes_compartidas(self):
        """ROL_TOQUE[2]['orden_categoria'] debe incluir 'variantes_compartidas'."""
        from analytics.planificador_helms.config import ROL_TOQUE
        self.assertIn(
            'variantes_compartidas',
            ROL_TOQUE[2]['orden_categoria'],
            "ROL_TOQUE[2]['orden_categoria'] debe incluir 'variantes_compartidas' para X.12",
        )

    def test_rol_toque1_no_incluye_variantes_compartidas(self):
        """
        ROL_TOQUE[1] NO debe incluir 'variantes_compartidas' — invariante duro:
        el toque 1 es byte-idéntico al sistema actual (usa seleccionar_ejercicios_para_bloque).
        """
        from analytics.planificador_helms.config import ROL_TOQUE
        self.assertNotIn(
            'variantes_compartidas',
            ROL_TOQUE[1]['orden_categoria'],
            "ROL_TOQUE[1] NO debe incluir 'variantes_compartidas'",
        )


if __name__ == '__main__':
    unittest.main()
