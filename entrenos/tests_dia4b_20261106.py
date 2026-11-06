"""6-nov-2026 · Repaso del Día 4 de la descarga (aplazado al viernes).

1. Rutina: «La pasaste de ayer a hoy» si la aplazaste tú.
2. La etiqueta OPCIONAL de la sesión usa la misma regla que el briefing.
3. Descarga con el mismo peso: la tarjeta «Última vez» lo explica.
4. El botón «Guardar · …» se refresca al tocar el picker.
5. En descarga no se suben reps entre series.
6. «Lo que viene»: «Mañana, sábado: Día 5… Pasa del viernes al sábado».
7. La duración que se revisa es la que se guarda.
"""

from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.tests_semana_rutina import LUNES, Base
from rutinas.models import Rutina

ACTIVO = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos' / 'entrenamiento_activo.html'
JUEVES, VIERNES = LUNES + timedelta(days=3), LUNES + timedelta(days=4)


class Plantilla(SimpleTestCase):
    def setUp(self):
        self.src = ACTIVO.read_text(encoding='utf-8')

    def test_nota2_opcional_con_la_regla_nueva(self):
        self.assertIn("{% if not ejercicio.es_principal %}", self.src)
        self.assertNotIn("{% if ejercicio.tipo_ejercicio != 'compuesto_principal' %}\n        {% if modo_reducido", self.src)

    def test_nota3_mismo_peso_explicado(self):
        self.assertIn('mismo peso · {{ ejercicio.reps_objetivo|subtract:ejercicio.repeticiones_anterior', self.src)

    def test_nota4_boton_al_tocar_el_picker(self):
        i = self.src.index('function cambiarPicker(')
        self.assertIn('refrescarBotonesGuardar', self.src[i:i + 900])

    def test_nota5_descarga_sin_subir_entre_series(self):
        i = self.src.index('function aplicarSugerenciaSiguienteSerie(')
        bloque = self.src[i:i + 2000]
        self.assertIn("dataset.descarga === '1'", bloque)

    def test_nota7_duracion_congelada(self):
        self.assertIn('return _minRevision!==null?_minRevision:_duracionCruda();', self.src)
        self.assertIn('_minRevision=mins;', self.src)


class AplazadaAHoy(Base):
    def test_nota1(self):
        from entrenos.services.semana_rutina_service import aplazada_a_hoy
        SesionProgramada.objects.create(cliente=self.cliente, fecha_prevista=JUEVES,
                                        nombre_sesion='Dia 4 - Hipertrofia — Metabólica', pospuesta_hasta=VIERNES)
        self.assertEqual(aplazada_a_hoy(self.cliente, VIERNES), JUEVES)
        self.assertIsNone(aplazada_a_hoy(self.cliente, JUEVES))


class LoQueViene(Base):
    def test_nota6_manana_sabado(self):
        from entrenos.services.cierre_porque_service import lo_que_viene
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 4 - Descarga Activa')
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=VIERNES)
        siguiente = {'nombre': 'Dia 5 - Descarga Activa', 'fecha': VIERNES, 'entrenamiento': {}}
        with patch('entrenos.services.sesion_recomendada._siguiente_de_cola', return_value=siguiente), \
                patch('entrenos.services.sesion_recomendada._marcar_completadas'):
            lineas = lo_que_viene(self.cliente, e)
        self.assertEqual(lineas[0], 'Mañana, sábado: Día 5. Pasa del viernes al sábado porque hoy hiciste el Día 4.')
