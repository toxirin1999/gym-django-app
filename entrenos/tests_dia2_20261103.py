"""3-nov-2026 · Repaso del Día 2 de la descarga.

1. «Hoy vas justo»: los accesorios, solo si te ves bien (no «para otro día»).
2. La píldora del calentamiento dice los pasos que hay (2 en descarga).
3. En descarga, el selector arranca en las reps de la descarga (el Crunch salía a 13).
4. Principales para la versión suave: multiarticulares menos el core.
5. Descanso de 2 minutos como mucho en descarga.
6. Al continuar se avisa del ejercicio que dejaste atrás.
8. Pallof y remo a una mano: reps por lado, kilos de los dos lados.
9. «Cómo llegabas hoy» en descarga no compara con tu media.
"""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from entrenos.models import SemanaPlanGym
from entrenos.services import recuperacion_service as rec
from entrenos.tests_recuperacion_20261024 import HOY, ComprobacionCierre
from entrenos.views import _es_principal_hoy, _fijar_reps_descarga

ACTIVO = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos' / 'entrenamiento_activo.html'
RESUMEN = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos' / 'post_entreno_resumen.html'


class Textos(SimpleTestCase):
    def test_nota1_accesorios_solo_si_te_ves_bien(self):
        frase = rec._frase_recuperacion('rojo', [{'tipo': 'hrv', 'texto': 'x'}], [], {})
        self.assertIn('los accesorios, solo si te ves bien', frase)
        self.assertNotIn('para otro día', frase)

    def test_nota2_y_5_y_6_en_la_sesion(self):
        src = ACTIVO.read_text(encoding='utf-8')
        self.assertIn('{% if ejercicio.aproximaciones.peso3 %}3{% else %}2{% endif %} pasos', src)
        self.assertIn("if(card?.dataset.descarga==='1')descansoSeg=Math.min(descansoSeg,120);", src)
        self.assertIn(", al final'", src)

    def test_nota8_por_lado_en_el_resumen(self):
        src = RESUMEN.read_text(encoding='utf-8')
        self.assertIn('reps{% if trabajo.por_lado %} por lado{% endif %}', src)
        self.assertIn('(los dos lados)', src)


class RepsDescargaEnElSelector(SimpleTestCase):
    def test_manda_la_descarga(self):
        ej = {'deload': True, 'reps_objetivo_hoy': 12, 'reps_objetivo': 13, 'reps_min': 13, 'reps_max': 13,
              'sugerencia_tope': True, 'reps_sugeridas_tope': 13}
        _fijar_reps_descarga(ej)
        self.assertEqual((ej['reps_objetivo'], ej['reps_min'], ej['sugerencia_tope']), (12, 12, False))
        self.assertNotIn('reps_sugeridas_tope', ej)

    def test_fuera_de_descarga_no_toca(self):
        ej = {'reps_objetivo_hoy': 12, 'reps_objetivo': 13}
        _fijar_reps_descarga(ej)
        self.assertEqual(ej['reps_objetivo'], 13)


class Principales(SimpleTestCase):
    def test_core_no_y_remo_si(self):
        self.assertFalse(_es_principal_hoy({'grupo_muscular': 'core', 'tipo_ejercicio': 'compuesto_principal'}))
        self.assertTrue(_es_principal_hoy({'grupo_muscular': 'espalda', 'tipo_ejercicio': 'compuesto_secundario'}))
        self.assertTrue(_es_principal_hoy({'grupo_muscular': 'espalda', 'tipo_ejercicio': 'compuesto_principal'}))
        self.assertFalse(_es_principal_hoy({'grupo_muscular': 'hombros', 'tipo_ejercicio': 'aislamiento'}))
        self.assertFalse(_es_principal_hoy({'grupo_muscular': 'cuadriceps', 'tipo_ejercicio': 'compuesto_principal',
                                            'pierna_suave': True}))


class CierreEnDescarga(ComprobacionCierre):
    def test_nota9_descarga_no_compara_con_tu_media(self):
        lunes = HOY - timedelta(days=HOY.weekday())
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=lunes, semana_plan=44, descarga=True,
                                     origen='descarga_programada')
        self._entreno(9, None, 8)
        e = self._entreno(0, 'recuperacion_baja', 6)
        frase = rec.comprobacion_cierre(self.cliente, e)
        self.assertIn('Era semana de descarga', frase)
        self.assertIn('justo lo que tocaba', frase)
        self.assertNotIn('como tus', frase)

    def test_fuera_de_descarga_menos_de_lo_normal(self):
        self._entreno(5, None, 8)
        e = self._entreno(0, 'recuperacion_baja', 6)
        frase = rec.comprobacion_cierre(self.cliente, e)
        self.assertIn('Te costó menos de lo normal', frase)


from entrenos.tests_ultima_sesion import Base as BaseUltima  # noqa: E402


class DeadHangEnDescarga(BaseUltima):
    """3-nov-2026: el briefing del Día 3 decía «Hoy a por 37 s» en la descarga."""

    def test_menos_tiempo_y_sin_marca(self):
        from rutinas.models import EjercicioBase
        from entrenos.services.sesion_descarga_service import ajustar_a_descarga
        hang = EjercicioBase.objects.create(nombre='Aguante en Barra (Dead Hang)', grupo_muscular='antebrazos',
                                            tipo_progresion='progresion_tiempo')
        e = self.entreno(HOY - timedelta(days=5), {hang.nombre: '30-60'})
        self.hacer(e, hang, [(0, 36, 7), (0, 36, 7)])
        ej = {'nombre': hang.nombre, 'tipo_progresion': 'progresion_tiempo', 'repeticiones': '30-60',
              'reps_objetivo': 37, 'usa_tiempo': True}
        frase = ajustar_a_descarga(self.cliente, ej, HOY)
        self.assertEqual(ej['reps_objetivo'], 30)
        self.assertEqual(ej['reps_objetivo_hoy'], 30)
        self.assertEqual(ej['repeticiones'], 30)  # «2 series × 30 s» en el briefing
        self.assertTrue(ej['deload'])
        self.assertIn('30 s (la última vez 36 s)', frase)
        self.assertIn('No se busca marca', frase)
        _fijar_reps_descarga(dict(ej, reps_objetivo=37))
