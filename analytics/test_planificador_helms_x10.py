# analytics/test_planificador_helms_x10.py
"""
Tests TDD para X.10 — Catálogo: backfill de 'perfil' + búlgara compartida
vía variantes_compartidas + whitelist de mapeo en las 3 funciones de utilidad.

Todos deben fallar con el código original (antes de X.10) y pasar en verde
después de implementar los cambios en database/ejercicios.py.

Tests 2 y 3 son la red de seguridad real: si la whitelist se implementa MAL,
esos tests fallan; si se implementa bien, pasan tanto antes como después.
"""

import importlib
from django.test import TestCase

import analytics.planificador_helms.database.ejercicios as ej_module
from analytics.planificador_helms.database.ejercicios import (
    EJERCICIOS_DATABASE,
    obtener_grupo_muscular,
    obtener_todos_ejercicios_por_grupo,
    obtener_mapeo_inverso,
    CATEGORIAS_CANONICAS,
)


def _reset_cache():
    """Resetea la caché de módulo entre assertions para evitar resultados obsoletos."""
    ej_module._MAPEO_INVERSO_CACHE = None


# ===========================================================================
# 1. Cobertura de `perfil`: todo ejercicio en categorías canónicas (no hyrox)
#    debe tener 'perfil' en {'estirado', 'acortado', 'media'}.
# ===========================================================================

class TestBackfillPerfilCompleto(TestCase):
    """
    Falla ANTES de X.10 (core/trapecios/antebrazos carecen de 'perfil').
    Pasa DESPUÉS de añadir el campo a todas las entradas listadas en el diseño.
    """

    VALORES_VALIDOS = {'estirado', 'acortado', 'media'}

    def test_todos_los_ejercicios_no_hyrox_tienen_perfil(self):
        grupos_sin_perfil = []
        for grupo, categorias in EJERCICIOS_DATABASE.items():
            if grupo == 'hyrox':
                continue
            for categoria in CATEGORIAS_CANONICAS:
                ejercicios = categorias.get(categoria, [])
                for ej in ejercicios:
                    if ej.get('perfil') not in self.VALORES_VALIDOS:
                        grupos_sin_perfil.append(
                            f"{grupo}/{categoria}: '{ej.get('nombre')}' perfil={ej.get('perfil')!r}"
                        )
        self.assertEqual(
            grupos_sin_perfil, [],
            "Ejercicios con 'perfil' ausente o inválido:\n" + "\n".join(grupos_sin_perfil),
        )


# ===========================================================================
# 2. obtener_grupo_muscular — la búlgara sigue siendo 'cuadriceps'
#    (red de seguridad real: si el whitelist falla, este test también falla)
# ===========================================================================

class TestObtenerGrupoMuscularBulgara(TestCase):
    """
    Pasa ANTES de X.10 (cuadriceps es el único propietario de la búlgara).
    Debe seguir pasando DESPUÉS: añadir variantes_compartidas a glúteos
    no debe cambiar el retorno de obtener_grupo_muscular.
    """

    def test_bulgara_es_cuadriceps(self):
        _reset_cache()
        resultado = obtener_grupo_muscular('Sentadilla Búlgara')
        self.assertEqual(
            resultado, 'cuadriceps',
            f"obtener_grupo_muscular('Sentadilla Búlgara') devolvió '{resultado}' en vez de 'cuadriceps'",
        )

    def test_bulgara_no_es_gluteos(self):
        _reset_cache()
        resultado = obtener_grupo_muscular('Sentadilla Búlgara')
        self.assertNotEqual(
            resultado, 'gluteos',
            "obtener_grupo_muscular devolvió 'gluteos' — la whitelist no está funcionando",
        )


# ===========================================================================
# 3. obtener_mapeo_inverso — la búlgara sigue mapeando a 'cuadriceps'
# ===========================================================================

class TestMapeoInversoBulgara(TestCase):
    """
    Pasa ANTES de X.10.
    Debe seguir pasando DESPUÉS: variantes_compartidas NO debe entrar
    en el mapeo inverso gracias a la whitelist en crear_mapeo_inverso.
    """

    def test_mapeo_inverso_bulgara_es_cuadriceps(self):
        _reset_cache()
        mapeo = obtener_mapeo_inverso()
        self.assertEqual(
            mapeo.get('sentadilla búlgara'), 'cuadriceps',
            f"mapeo['sentadilla búlgara'] = {mapeo.get('sentadilla búlgara')!r}; se esperaba 'cuadriceps'",
        )

    def test_mapeo_inverso_no_registra_bulgara_como_gluteos_tras_cache_reset(self):
        """
        Verifica que incluso tras resetear la caché (forzando recalcular)
        el resultado sigue siendo cuadriceps. Este test falla si el whitelist
        no está en crear_mapeo_inverso.
        """
        _reset_cache()
        mapeo = obtener_mapeo_inverso()
        for nombre, grupo in mapeo.items():
            if 'búlgara' in nombre or 'bulgara' in nombre:
                self.assertEqual(
                    grupo, 'cuadriceps',
                    f"La búlgara aparece en el mapeo con grupo '{grupo}' — "
                    "variantes_compartidas está filtrándose al mapeo inverso",
                )


# ===========================================================================
# 4. variantes_compartidas existe en gluteos con la entrada correcta
# ===========================================================================

class TestVariantesCompartidasGluteos(TestCase):
    """
    Falla ANTES de X.10 (la clave no existe).
    Pasa DESPUÉS.
    """

    def setUp(self):
        self.gluteos = EJERCICIOS_DATABASE.get('gluteos', {})
        self.bulgara_cuad = next(
            (e for e in EJERCICIOS_DATABASE['cuadriceps']['compuesto_principal']
             if e.get('nombre') == 'Sentadilla Búlgara'),
            None,
        )

    def test_variantes_compartidas_existe(self):
        self.assertIn(
            'variantes_compartidas', self.gluteos,
            "EJERCICIOS_DATABASE['gluteos'] no tiene la clave 'variantes_compartidas'",
        )

    def test_variantes_compartidas_contiene_exactamente_una_entrada(self):
        variantes = self.gluteos.get('variantes_compartidas', [])
        self.assertEqual(
            len(variantes), 1,
            f"variantes_compartidas tiene {len(variantes)} entradas; se esperaba exactamente 1",
        )

    def test_variante_bulgara_nombre_correcto(self):
        variantes = self.gluteos.get('variantes_compartidas', [])
        if not variantes:
            self.skipTest("variantes_compartidas vacía — ya cubierta por test anterior")
        self.assertEqual(variantes[0].get('nombre'), 'Sentadilla Búlgara')

    def test_variante_bulgara_perfil_estirado(self):
        variantes = self.gluteos.get('variantes_compartidas', [])
        if not variantes:
            self.skipTest("variantes_compartidas vacía")
        self.assertEqual(variantes[0].get('perfil'), 'estirado')

    def test_variante_bulgara_grupo_canonico_marcado(self):
        variantes = self.gluteos.get('variantes_compartidas', [])
        if not variantes:
            self.skipTest("variantes_compartidas vacía")
        self.assertEqual(variantes[0].get('grupo_canonico'), 'cuadriceps')

    def test_variante_bulgara_mismos_risk_tags_que_cuadriceps(self):
        """
        Verifica que los risk_tags de la variante compartida son idénticos
        a los de la entrada canónica en cuadriceps — nunca hardcodea los tags.
        """
        if self.bulgara_cuad is None:
            self.fail("No se encontró 'Sentadilla Búlgara' en cuadriceps/compuesto_principal")
        variantes = self.gluteos.get('variantes_compartidas', [])
        if not variantes:
            self.skipTest("variantes_compartidas vacía")
        self.assertEqual(
            variantes[0].get('risk_tags'), self.bulgara_cuad.get('risk_tags'),
            "risk_tags de variante_compartida difiere de los de cuadriceps/compuesto_principal",
        )


# ===========================================================================
# 5. obtener_todos_ejercicios_por_grupo — la búlgara NO aparece en gluteos
# ===========================================================================

class TestObtenerTodosEjerciciosPorGrupo(TestCase):
    """
    La whitelist debe excluir variantes_compartidas también de esta función.
    Falla ANTES de X.10 si variantes_compartidas se añade sin whitelist.
    Pasa DESPUÉS con la whitelist correcta.
    """

    def test_bulgara_no_en_lista_gluteos(self):
        todos_gluteos = obtener_todos_ejercicios_por_grupo('gluteos')
        nombres = [e.get('nombre') for e in todos_gluteos]
        self.assertNotIn(
            'Sentadilla Búlgara', nombres,
            "Sentadilla Búlgara aparece en obtener_todos_ejercicios_por_grupo('gluteos') — "
            "variantes_compartidas está siendo incluida",
        )

    def test_lista_gluteos_contiene_hip_thrust(self):
        """Regresión: el hip thrust sigue estando en la lista canónica de glúteos."""
        todos_gluteos = obtener_todos_ejercicios_por_grupo('gluteos')
        nombres = [e.get('nombre') for e in todos_gluteos]
        self.assertIn('Hip Thrust con Barra', nombres)


# ===========================================================================
# 6. Regresión de estadísticas reales (via mapeo inverso, sin levantar service)
#    Verifica que incluso con variantes_compartidas en el módulo cargado,
#    el mapeo inverso sigue siendo correcto después de un reset de caché.
# ===========================================================================

class TestRegresionEstadisticasMapeoInverso(TestCase):
    """
    Cubre el riesgo real de estadisticas_service.py:
    MAPEO_MUSCULAR_DYNAMIC se construye desde obtener_mapeo_inverso() al importar.
    Si el whitelist funciona, un reset+recálculo devuelve el mismo resultado.

    Para validar con datos de BD se requeriría un usuario de prueba;
    aquí verificamos el mapeo que el servicio consumiría, que es el riesgo real.
    """

    def test_reset_cache_y_recalculo_mantiene_bulgara_en_cuadriceps(self):
        # Simula que el módulo se recarga después de que variantes_compartidas existe
        _reset_cache()
        mapeo = obtener_mapeo_inverso()
        self.assertEqual(
            mapeo.get('sentadilla búlgara'), 'cuadriceps',
            "Tras reset de caché, la búlgara no sigue en cuadriceps en el mapeo inverso",
        )

    def test_mapeo_no_contiene_duplicado_bulgara_gluteos(self):
        """
        El mapeo inverso es {nombre → grupo}, no admite duplicados.
        Verifica que no exista ninguna entrada que mapee búlgara a gluteos.
        """
        _reset_cache()
        mapeo = obtener_mapeo_inverso()
        # Buscamos cualquier variante de nombre que contenga 'búlgara' o 'bulgara'
        entradas_bulgara = {k: v for k, v in mapeo.items() if 'bulgar' in k.lower()}
        for nombre, grupo in entradas_bulgara.items():
            self.assertEqual(
                grupo, 'cuadriceps',
                f"'{nombre}' mapea a '{grupo}' en vez de 'cuadriceps'",
            )
