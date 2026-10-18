"""18-oct-2026: cada toque de espalda lleva un remo.

En el plan de David el Día 4 salía con Jalón brazos rectos + Pull-over: el
pull-over contaba como "horizontal" por llevar "mancuerna" en el nombre y la
semana se quedaba con 3 series de remo frente a ~13 de empuje horizontal.
"""

from django.test import SimpleTestCase

from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE
from analytics.planificador_helms.ejercicios.variacion import (
    _asegurar_oposicion_espalda, _traccion, construir_variantes_por_toque,
)


def ej(nombre):
    for tipos in EJERCICIOS_DATABASE['espalda'].values():
        for e in tipos:
            if e['nombre'] == nombre:
                return e
    raise KeyError(nombre)


def pool():
    return {k: list(v) for k, v in EJERCICIOS_DATABASE['espalda'].items()}


class Traccion(SimpleTestCase):
    def test_patron_del_catalogo_manda(self):
        self.assertEqual(_traccion(ej('Pull-over con Mancuerna')), 'vertical')
        self.assertEqual(_traccion(ej('Jalon brazos rectos')), 'vertical')
        self.assertEqual(_traccion(ej('Remo con Mancuerna a una mano')), 'horizontal')
        self.assertEqual(_traccion(ej('Remo en Polea Baja (Gironda)')), 'horizontal')
        self.assertIsNone(_traccion(ej('Face Pulls')))


class OposicionEspalda(SimpleTestCase):
    def test_brazos_rectos_y_pullover_cambia_el_pullover_por_un_remo(self):
        seleccion = [ej('Jalon brazos rectos'), ej('Pull-over con Mancuerna')]
        disponibles = [e for cat in pool().values() for e in cat
                       if e['nombre'] not in ('Jalón al Pecho', 'Remo con Mancuerna a una mano')]
        nueva = _asegurar_oposicion_espalda(seleccion, disponibles)
        self.assertEqual(nueva[0]['nombre'], 'Jalon brazos rectos')
        self.assertEqual(_traccion(nueva[1]), 'horizontal')
        self.assertNotEqual(nueva[1]['nombre'], 'Face Pulls')

    def test_si_ya_hay_remo_no_se_toca(self):
        seleccion = [ej('Jalón al Pecho'), ej('Remo con Mancuerna a una mano')]
        self.assertIs(_asegurar_oposicion_espalda(seleccion, []), seleccion)

    def test_todos_los_toques_llevan_remo(self):
        toque1 = [ej('Jalón al Pecho'), ej('Remo con Mancuerna a una mano')]
        variantes = construir_variantes_por_toque('espalda', 3, True, pool(), toque1)
        for toque, ejercicios in variantes.items():
            tipos = {_traccion(e) for e in ejercicios}
            self.assertIn('horizontal', tipos, f'toque {toque}: {[e["nombre"] for e in ejercicios]}')
            self.assertIn('vertical', tipos, f'toque {toque}: {[e["nombre"] for e in ejercicios]}')
