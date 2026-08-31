from pathlib import Path
from unittest import TestCase


TEMPLATE = (
    Path(__file__).resolve().parent
    / "templates"
    / "entrenos"
    / "entrenamiento_activo.html"
)


class ProximaSerieTopeUIRegressionTests(TestCase):
    def test_resumen_se_calcula_despues_de_congelar_el_peso_del_tope(self):
        source = TEMPLATE.read_text(encoding="utf-8")
        guardar_serie = source.split("function guardarSeriePanel", 1)[1].split(
            "function editarSeriePanel", 1
        )[0]

        aplicar = guardar_serie.index("aplicarSugerenciaSiguienteSerie(")
        leer_peso = guardar_serie.index("const recPeso =")

        self.assertLess(
            aplicar,
            leer_peso,
            "El tope debe congelar el input antes de construir 'Próxima serie'.",
        )
        self.assertIn(
            ".value || peso",
            guardar_serie[leer_peso : leer_peso + 180],
            "El resumen debe mostrar el valor efectivo del input, no data-rec-weight.",
        )
