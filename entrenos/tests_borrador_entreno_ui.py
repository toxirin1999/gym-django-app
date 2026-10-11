from pathlib import Path

from django.test import SimpleTestCase


class BorradorEntrenoUIContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(
            encoding='utf-8'
        )

    def test_el_usuario_puede_descartar_el_borrador_local_con_confirmacion(self):
        self.assertIn('id="btn-descartar-borrador"', self.source)
        self.assertIn('function descartarBorrador()', self.source)
        self.assertIn('¿Descartar el borrador local?', self.source)
        self.assertIn('limpiarCheckpoint();', self.source)
        self.assertIn('localStorage.removeItem(_WK_KEY);', self.source)

    def test_avisa_antes_de_saltar_un_ejercicio_con_series_pendientes(self):
        self.assertIn('id="modal-series-pendientes"', self.source)
        self.assertIn('function navEjercicio(delta, confirmarSalto=false)', self.source)
        self.assertIn('tieneSeriesPendientes(card)', self.source)
        self.assertIn('id="btn-seguir-registrando"', self.source)
        self.assertIn('id="btn-ir-al-siguiente"', self.source)

