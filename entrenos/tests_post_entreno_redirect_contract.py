"""
Phase 62F — contrato del redirect tras guardar un entrenamiento.

guardar_entrenamiento_activo no tiene cobertura de tests propia (vista POST
extensa con muchas dependencias). Este test de contrato (precedente:
tests_continuidad_narracion.py) verifica que el redirect de éxito apunta a
la nueva pantalla de cierre, no directamente al dashboard de evolución.
"""

from django.test import TestCase


def _leer(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


class TestRedirectPostEntreno(TestCase):
    def test_guardar_entrenamiento_redirige_a_cierre(self):
        src = _leer('entrenos/views.py')
        self.assertIn(
            "return redirect('entrenos:post_entreno_resumen', cliente_id=cliente.id, entreno_id=entreno.id)",
            src,
        )

    def test_no_redirige_directo_a_dashboard_evolucion(self):
        src = _leer('entrenos/views.py')
        self.assertNotIn(
            "return redirect('entrenos:dashboard_evolucion', cliente_id=cliente.id)",
            src,
        )
