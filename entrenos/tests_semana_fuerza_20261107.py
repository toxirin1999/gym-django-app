"""7-nov-2026 · Antes del primer día de Fuerza — Hipertrofia.

Fútbol:
- Víspera: distingue «Mañana tienes fútbol (lo tienes apuntado)» de «Sueles jugar…».
- El mismo día: por costumbre, la pierna al final y opcional (reversible); con el
  partido apuntado, además una serie menos y RPE 7.

Primera prescripción del lunes (briefing en producción frente a la sesión):
- La lista «El plan ha cambiado» y la etiqueta siguen a la regla única (prensa
  «→ 182,5» con 180 en la tarjeta; aperturas «→ 20 kg» y «↓ BAJAR» con 30 kg).
- La sesión arranca en el peso del briefing (convergent 72,5 frente a 70;
  gemelos de pie 90, el de la descarga, frente a 100).
- Farmer: «Hoy a por 62 m (la última vez 57)», no «Hoy a por 5 m».
"""

from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from entrenos.models import ActividadRealizada

MIERCOLES = date(2026, 11, 11)


class Futbol(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('futbol_mismo_dia_20261107', password='x').cliente_perfil
        for k in (1, 2, 3):
            self._partido(MIERCOLES - timedelta(days=7 * k))

    def _partido(self, fecha):
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Fútbol', fecha=fecha,
                                          duracion_minutos=60, carga_ua=480)

    def _ejercicios(self):
        return [
            {'nombre': 'Zancadas con Kettlebell', 'grupo_muscular': 'cuadriceps', 'series': 3, 'rpe_objetivo': 8},
            {'nombre': 'Curl con Barra Z', 'grupo_muscular': 'biceps', 'series': 2, 'rpe_objetivo': 8},
        ]

    def test_mismo_dia_por_costumbre_solo_opcional(self):
        from entrenos.services.criterios_entrenador_service import aplicar_futbol_hoy
        ejs = self._ejercicios()
        aplicar_futbol_hoy(self.cliente, ejs, MIERCOLES)
        curl, zancadas = ejs
        self.assertEqual(curl['nombre'], 'Curl con Barra Z')
        self.assertTrue(zancadas['opcional_futbol'])
        self.assertEqual((zancadas['series'], zancadas['rpe_objetivo']), (3, 8))
        self.assertEqual(zancadas['criterio_entrenador'],
                         'Sueles jugar al fútbol los miércoles (3 de las últimas 4 semanas): la pierna de hoy va '
                         'al final y es opcional. Si hoy no juegas, hazla como siempre.')
        self.assertNotIn('opcional_futbol', curl)

    def test_mismo_dia_apuntado_tambien_rebaja(self):
        from entrenos.services.criterios_entrenador_service import aplicar_futbol_hoy
        self._partido(MIERCOLES)
        ejs = self._ejercicios()
        aplicar_futbol_hoy(self.cliente, ejs, MIERCOLES)
        zancadas = ejs[1]
        self.assertEqual((zancadas['series'], zancadas['rpe_objetivo']), (2, 7))
        self.assertEqual(zancadas['criterio_entrenador'],
                         'Hoy tienes fútbol (lo tienes apuntado): la pierna va al final y es opcional, '
                         'con 2 series en vez de 3 y RPE 7 en vez de 8.')

    def test_vispera_apuntado_o_por_costumbre(self):
        from entrenos.services.criterios_entrenador_service import futbol_manana
        martes = MIERCOLES - timedelta(days=1)
        self.assertEqual(futbol_manana(self.cliente, martes),
                         'Sueles jugar al fútbol los miércoles (3 de las últimas 4 semanas) y mañana es miércoles')
        self._partido(MIERCOLES)
        self.assertEqual(futbol_manana(self.cliente, martes), 'Mañana tienes fútbol (lo tienes apuntado)')

    def test_sin_futbol_nada(self):
        from entrenos.services.criterios_entrenador_service import aplicar_futbol_hoy
        ejs = self._ejercicios()
        self.assertEqual(aplicar_futbol_hoy(self.cliente, ejs, MIERCOLES + timedelta(days=1)), [])
        self.assertNotIn('opcional_futbol', ejs[0])


class Reconciliar(SimpleTestCase):
    def test_una_linea_por_ejercicio_y_etiqueta_a_juego(self):
        from entrenos.services.plan_dinamico_service import _reconciliar_con_regla_unica
        fly = {'nombre': 'Low-to-High Cable Fly', 'regla_carga': 'subir', 'peso_kg': 30, 'peso_kg_anterior': 25,
               'progresion_aplicada': True, 'progresion_accion': 'bajar_peso',
               'progresion_motivo': '14 reps con 25 kg, arriba del rango: hoy 30 kg y vuelta a 8.'}
        encog = {'nombre': 'Encogimientos con Barra', 'regla_carga': 'mantener', 'peso_kg': 120,
                 'peso_kg_anterior': 120, 'progresion_aplicada': True, 'progresion_accion': 'bajar_peso',
                 'reps_objetivo_hoy': 11,
                 'progresion_motivo': 'Mismo peso: hoy a por 11 reps (la última vez 10); con 12 en todas las series, sube la carga.'}
        prensa = {'nombre': 'Prensa de Piernas', 'regla_carga': 'recalcular', 'peso_kg': 180,
                  'peso_kg_anterior': 145, 'progresion_aplicada': True, 'progresion_accion': 'subir_peso'}
        cambios = [
            {'tipo': 'progresion_aplicada', 'ejercicio_original': 'Low-to-High Cable Fly', 'accion': 'bajar_peso',
             'peso_sugerido': 20, 'razon': 'RPE extremo (10) detectado — reducir carga'},
            {'tipo': 'progresion_aplicada', 'ejercicio_original': 'Encogimientos con Barra', 'accion': 'bajar_peso',
             'peso_sugerido': 100, 'razon': '120 kg × 10: lejos de 15-20 reps'},
            {'tipo': 'progresion_aplicada', 'ejercicio_original': 'Prensa de Piernas', 'accion': 'subir_peso',
             'peso_sugerido': 182.5, 'razon': 'Completado con éxito'},
            {'tipo': 'deload', 'razon': 'otra cosa'},
        ]
        _reconciliar_con_regla_unica([fly, encog, prensa], cambios)
        self.assertEqual((fly['progresion_accion'], fly['progresion_aplicada']), ('subir_peso', True))
        self.assertFalse(encog['progresion_aplicada'])
        self.assertTrue(encog['progresion_pospuesta'])
        self.assertFalse(prensa['progresion_aplicada'])
        por_ej = {c.get('ejercicio_original'): c for c in cambios}
        self.assertEqual(por_ej['Low-to-High Cable Fly']['peso_sugerido'], 30)
        self.assertEqual(por_ej['Encogimientos con Barra']['tipo'], 'progresion_pospuesta')
        self.assertNotIn('Prensa de Piernas', por_ej)
        self.assertEqual(len(cambios), 3)


class SesionComoElBriefing(SimpleTestCase):
    def test_arranca_en_el_peso_de_la_regla(self):
        from entrenos.views import _alinear_con_briefing
        ej = {'regla_carga': 'recalcular', 'peso_kg': 70, 'peso_inicial_kg': 72.5}
        _alinear_con_briefing(ej)
        self.assertEqual(ej['peso_inicial_kg'], 70)
        ej = {'regla_carga': 'tope', 'peso_kg': 100, 'peso_inicial_kg': 90, 'tope_maquina_kg': 100}
        _alinear_con_briefing(ej)
        self.assertEqual(ej['peso_inicial_kg'], 100)
        ej = {'peso_kg': 70, 'peso_inicial_kg': 72.5}
        _alinear_con_briefing(ej)
        self.assertEqual(ej['peso_inicial_kg'], 72.5)

    def test_plantilla_opcional_por_futbol(self):
        src = (Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos' / 'entrenamiento_activo.html').read_text(
            encoding='utf-8')
        self.assertIn("or ejercicio.opcional_futbol %}", src)
