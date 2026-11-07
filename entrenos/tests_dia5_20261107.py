"""7-nov-2026 · Briefing del Día 5 de la descarga.

1. En la semana de descarga no se cambia de variante por estancamiento (el
   curl martillo entraba sin descarga, «a por 15 reps»); una variante por
   molestia sí, pero también en descarga.
2. Descarga con la referencia fuera de rango: la estimación más prudente de
   todas las series (extensiones 15 × 4 @10 y 10 × 7 @9 → no 12,5 × 10).
"""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from entrenos.tests_descarga_semana_20261102 import LUNES
from entrenos.tests_ultima_sesion import Base


class ExtensionesTrasUnFallo(Base):
    def test_nota2_no_parte_del_fallo(self):
        from rutinas.models import EjercicioBase
        from entrenos.services.sesion_descarga_service import ajustar_a_descarga
        ext = EjercicioBase.objects.create(nombre='Extensiones sobre la Cabeza con Mancuerna',
                                           grupo_muscular='triceps', tipo_progresion='peso_reps', equipo='Mancuerna')
        e = self.entreno(LUNES - timedelta(days=8), {ext.nombre: '10-15'})
        self.hacer(e, ext, [(15, 4, 10), (10, 7, 9)])
        ej = {'nombre': ext.nombre, 'repeticiones': '10-15', 'tipo_progresion': 'peso_reps',
              'rpe_objetivo': 6, 'peso_kg': 999}
        ajustar_a_descarga(self.cliente, ej, LUNES)
        self.assertLessEqual(ej['peso_kg'], 10.0)
        self.assertEqual(ej['reps_objetivo_hoy'], 10)


class SinCambioDeVarianteEnDescarga(SimpleTestCase):
    def test_nota1_codigo(self):
        src = (Path(settings.BASE_DIR) / 'entrenos' / 'services' / 'plan_dinamico_service.py').read_text(encoding='utf-8')
        self.assertIn('if es_estancado and not es_molestia and _semana_descarga(cliente, hoy):', src)
        self.assertEqual(src.count('_variante_en_descarga(cliente, ej, hoy)'), 3)  # la definición y las dos molestias
