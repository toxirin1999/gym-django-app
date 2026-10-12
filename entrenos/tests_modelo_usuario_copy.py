"""Contratos de redacción del modelo progresivo del atleta."""

from pathlib import Path

from django.test import SimpleTestCase


class ModeloUsuarioCopyTests(SimpleTestCase):
    def test_recuperacion_usa_singular_para_un_dia(self):
        """La memoria no debe decir ``1 días`` en el resumen ni en el detalle."""
        servicio = Path(
            "entrenos/services/modelo_usuario_service.py"
        ).read_text(encoding="utf-8")
        plantilla = Path(
            "clientes/templates/clientes/memoria_entrenador.html"
        ).read_text(encoding="utf-8")

        self.assertIn("etiqueta_dia = 'día' if dias_optimo == 1 else 'días'", servicio)
        self.assertIn("día{{ modelo.ventana_recuperacion.dias_optimos|pluralize }}", plantilla)
