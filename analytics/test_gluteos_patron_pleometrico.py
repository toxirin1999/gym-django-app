# analytics/test_gluteos_patron_pleometrico.py
"""
Cierre de gap: glúteo cubría bisagra/acortado/abducción/estiramiento parcial
pero no tenía ningún ejercicio del patrón explosivo/pliométrico (saltos,
swings) asignable como objetivo — el único ejercicio 'pleometrico' del
catálogo (Burpee Broad Jump) vivía en 'hyrox', nunca en 'gluteos'.

Estos tests verifican:
  1. El catálogo tiene ejercicios 'pleometrico' propios de glúteos.
  2. PATRONES_OBJETIVO['gluteos'] amplía el set (no reemplaza 'bisagra').
  3. El motor real (SelectorEjercicios, vía rotación por numero_bloque) puede
     asignar de verdad ese patrón como ejercicio de glúteos — no solo como
     variante de relleno en toques 2/3.
"""

import unittest

from analytics.planificador_helms.config import PATRONES_OBJETIVO
from analytics.planificador_helms.database.ejercicios import (
    EJERCICIOS_DATABASE,
    CATEGORIAS_CANONICAS,
)
from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
from analytics.planificador_helms.ejercicios.patrones import PatronManager


def _ejercicios_gluteos_pleometrico():
    gluteos = EJERCICIOS_DATABASE.get('gluteos', {})
    encontrados = []
    for categoria in CATEGORIAS_CANONICAS:
        for ej in gluteos.get(categoria, []):
            if ej.get('patron') == 'pleometrico':
                encontrados.append(ej)
    return encontrados


class TestCatalogoGluteosPleometrico(unittest.TestCase):

    def test_gluteos_tiene_al_menos_un_ejercicio_pleometrico(self):
        encontrados = _ejercicios_gluteos_pleometrico()
        self.assertGreater(
            len(encontrados), 0,
            "No hay ningún ejercicio con patron='pleometrico' en gluteos — "
            "el gap del patrón explosivo/potencia sigue sin catálogo propio.",
        )

    def test_ejercicios_pleometrico_tienen_perfil_valido(self):
        # Contrato de X.10 (test_planificador_helms_x10.py): todo ejercicio en
        # categorías canónicas no-hyrox debe tener 'perfil' válido.
        valores_validos = {'estirado', 'acortado', 'media'}
        for ej in _ejercicios_gluteos_pleometrico():
            self.assertIn(
                ej.get('perfil'), valores_validos,
                f"'{ej['nombre']}' tiene perfil={ej.get('perfil')!r} inválido",
            )

    def test_ejercicios_pleometrico_tienen_risk_tags_para_filtro_lesion(self):
        for ej in _ejercicios_gluteos_pleometrico():
            self.assertTrue(
                ej.get('risk_tags'),
                f"'{ej['nombre']}' (pleometrico) no tiene risk_tags — no podría "
                f"filtrarse ante una lesión activa de cadera/rodilla/tobillo",
            )


class TestPatronesObjetivoGluteosAmpliado(unittest.TestCase):

    def test_bisagra_se_conserva(self):
        self.assertIn('bisagra', PATRONES_OBJETIVO['gluteos'])

    def test_pleometrico_anadido(self):
        self.assertIn('pleometrico', PATRONES_OBJETIVO['gluteos'])

    def test_obtener_faltantes_grupo_soporta_multiples_patrones(self):
        """
        PatronManager.obtener_faltantes_grupo ya opera sobre sets (diferencia
        de conjuntos), igual que lo hace hoy para 'espalda' con 2 patrones —
        ampliar gluteos a 2 patrones no requiere ningún cambio de motor.
        """
        pm = PatronManager('hipertrofia')
        faltantes_iniciales = pm.obtener_faltantes_grupo('gluteos')
        self.assertEqual(faltantes_iniciales, {'bisagra', 'pleometrico'})

        pm.registrar_uso_patron('bisagra', dia_index=0, grupo='gluteos', nombre_ejercicio='Hip Thrust con Barra')
        self.assertEqual(pm.obtener_faltantes_grupo('gluteos'), {'pleometrico'})

        pm.registrar_uso_patron('pleometrico', dia_index=0, grupo='gluteos', nombre_ejercicio='Kettlebell Swing')
        self.assertEqual(pm.obtener_faltantes_grupo('gluteos'), set())


class TestMotorAsignaPleometricoDeVerdad(unittest.TestCase):
    """
    El catálogo por sí solo no basta: si nunca entra en la rotación real de
    SelectorEjercicios, seguiría siendo papel muerto. Se recorre un rango de
    bloques (como lo haría generar_plan_anual a lo largo del año) y se
    confirma que el patrón 'pleometrico' aparece como ejercicio real
    seleccionado para glúteos en al menos un bloque — no solo como variante
    de relleno de toques 2/3.
    """

    def test_pleometrico_aparece_en_rotacion_real_de_bloques(self):
        bloques_con_pleometrico = []
        for numero_bloque in range(1, 13):
            seleccion = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
                numero_bloque=numero_bloque,
                fase='hipertrofia',
            )
            gluteos = seleccion.get('gluteos', [])
            if any(ej.get('patron') == 'pleometrico' for ej in gluteos):
                bloques_con_pleometrico.append(numero_bloque)

        self.assertGreater(
            len(bloques_con_pleometrico), 0,
            "El patrón 'pleometrico' nunca fue seleccionado para gluteos en "
            "ningún bloque (1-12) — sigue sin ser un objetivo real del motor.",
        )


if __name__ == '__main__':
    unittest.main()
