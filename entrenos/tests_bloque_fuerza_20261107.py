"""7-nov-2026 · El bloque del lunes pasa de «Potencia — Peaking» a «Fuerza — Hipertrofia».

Decisión de David: ganar músculo de forma equilibrada y seguir progresando en
fuerza sin quedarse sin piernas para el fútbol.

- 4 semanas (45-48), los mismos ejercicios y días del bloque Metabólica.
- 4-6 reps en los multiarticulares de músculo grande; 8-12 en aislamientos,
  zancadas y búlgaras; pequeños, a su rango.
- Curl femoral tumbado y buenos días siguen (propuesta de isquios hasta el 17/11).
- Sin nórdico.
- Víspera de fútbol: pierna con una serie menos y RPE 7 como mucho.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion


def _bloques():
    return GeneradorPeriodizacion.generar_periodizacion_anual()


def _semana(numero_bloque, semana_plan):
    from analytics.planificador_helms.core import PlanificadorHelms
    from analytics.planificador_helms.models.perfil_cliente import PerfilCliente

    perfil = PerfilCliente({
        'id': 999999, 'nombre': 'x', 'experiencia_años': 2, 'objetivo_principal': 'hipertrofia',
        'dias_disponibles': 5, 'nivel_estres': 5, 'calidad_sueño': 7, 'nivel_energia': 7,
        'ejercicios_evitar': [], 'maximos_actuales': {},
    })
    bloque = dict(_bloques()[numero_bloque - 1])
    detalle = {d['num']: d for d in bloque['semanas_detalle']}[semana_plan]
    bloque['volumen_multiplicador'] = detalle['vol_mult']
    bloque['intensidad_rpe'] = (detalle['rpe'],)
    semana = PlanificadorHelms(perfil)._generar_semana_especifica(bloque, numero_bloque)
    return [ej for dia in sorted(semana) for ej in semana[dia]]


class Periodizacion(SimpleTestCase):
    def test_sin_peaking_y_52_semanas(self):
        bloques = _bloques()
        self.assertEqual(sum(len(b['semanas']) for b in bloques), 52)
        nombres = [b['nombre'] for b in bloques]
        self.assertNotIn('Potencia — Peaking', nombres)
        fuerza = next(b for b in bloques if b['nombre'] == 'Fuerza — Hipertrofia')
        self.assertEqual(fuerza['semanas'], [45, 46, 47, 48])
        self.assertEqual((fuerza['fase'], fuerza['rep_range'], fuerza['reps_secundarios']), ('fuerza', '4-6', '8-12'))
        self.assertTrue(fuerza['ejercicios_del_bloque_anterior'])
        self.assertEqual((fuerza['vol_inicio'], fuerza['vol_fin']), (0.85, 0.95))
        self.assertEqual(bloques[bloques.index(fuerza) + 1]['fase'], 'descarga')


class Plan(TestCase):
    """Bloques: 13 Metabólica (39-43), 15 Fuerza — Hipertrofia (45-48), 16 descarga (49), 17 Puente (50-51)."""

    def test_mismos_ejercicios_que_la_metabolica(self):
        metabolica = {e['nombre'] for e in _semana(13, 43)}
        fuerza = _semana(15, 45)
        self.assertEqual({e['nombre'] for e in fuerza}, metabolica)
        self.assertEqual({e['nombre'] for e in _semana(17, 50)}, metabolica)
        self.assertLessEqual({e['nombre'] for e in _semana(16, 49)}, metabolica)

    def test_isquios_de_la_propuesta_y_sin_nordico(self):
        nombres = {e['nombre'] for e in _semana(15, 45)}
        self.assertIn('Curl Femoral Tumbado', nombres)
        self.assertIn('Buenos Días (Good Mornings)', nombres)
        self.assertFalse(any('nórdico' in n.casefold() for n in nombres))

    def test_rangos(self):
        por_nombre = {}
        for e in _semana(15, 45):
            por_nombre.setdefault(e['nombre'], e['repeticiones'])
        self.assertEqual(por_nombre['Sentadilla Hack'], '4-6')
        self.assertEqual(por_nombre['Peso Muerto Rumano'], '4-6')
        self.assertEqual(por_nombre['Convergent Machine Press'], '4-6')
        self.assertEqual(por_nombre['Low-to-High Cable Fly'], '8-12')
        self.assertEqual(por_nombre['Curl Femoral Tumbado'], '8-12')
        self.assertEqual(por_nombre['Abducción de Cadera en Máquina'], '8-12')
        self.assertEqual(por_nombre['Zancadas con Kettlebell'], '8-12')
        self.assertEqual(por_nombre['Curl con Barra Z'], '8-12')

    def test_ningun_ejercicio_a_una_serie_y_series_por_debajo_de_la_metabolica(self):
        fuerza = _semana(15, 45)
        self.assertTrue(all(int(e['series']) >= 2 for e in fuerza))
        total = sum(int(e['series']) for e in fuerza)
        metabolica = sum(int(e['series']) for e in _semana(13, 43))
        self.assertLess(total, metabolica)
        self.assertGreater(total, metabolica * 0.8)


class VisperaFutbol(TestCase):
    def setUp(self):
        from entrenos.models import ActividadRealizada
        self.user = User.objects.create_user('vispera_futbol_20261107', password='x')
        self.cliente = self.user.cliente_perfil
        self.martes = date(2026, 11, 10)
        for semanas in (1, 2, 3):
            ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Fútbol',
                                              fecha=self.martes + timedelta(days=1 - 7 * semanas),
                                              duracion_minutos=60, carga_ua=480)

    def test_patron_de_los_miercoles(self):
        from entrenos.services.criterios_entrenador_service import futbol_manana
        self.assertEqual(futbol_manana(self.cliente, self.martes),
                         'Sueles jugar al fútbol los miércoles (3 de las últimas 4 semanas) y mañana es miércoles')
        self.assertIsNone(futbol_manana(self.cliente, self.martes + timedelta(days=1)))

    def test_pierna_con_una_serie_menos_y_rpe_7(self):
        from entrenos.services.criterios_entrenador_service import aplicar_vispera_futbol
        ejercicios = [
            {'nombre': 'Peso Muerto Rumano', 'grupo_muscular': 'isquios', 'series': 4, 'rpe_objetivo': 8},
            {'nombre': 'Jalón al Pecho', 'grupo_muscular': 'espalda', 'series': 4, 'rpe_objetivo': 8},
            {'nombre': 'Curl Femoral Tumbado', 'grupo_muscular': 'isquios', 'series': 2, 'rpe_objetivo': 7},
        ]
        frases = aplicar_vispera_futbol(self.cliente, ejercicios, self.martes)
        rumano, jalon, curl = ejercicios
        self.assertEqual((rumano['series'], rumano['rpe_objetivo']), (3, 7))
        self.assertEqual((jalon['series'], jalon['rpe_objetivo']), (4, 8))
        self.assertEqual((curl['series'], curl['rpe_objetivo']), (2, 7))
        self.assertEqual(len(frases), 1)
        self.assertEqual(rumano['criterio_entrenador'],
                         'Sueles jugar al fútbol los miércoles (3 de las últimas 4 semanas) y mañana es miércoles: '
                         'hoy 3 series en vez de 4 y RPE 7 en vez de 8 en pierna, para llegar con piernas.')

    def test_sin_patron_no_toca_nada(self):
        from entrenos.services.criterios_entrenador_service import aplicar_vispera_futbol
        ej = [{'nombre': 'Peso Muerto Rumano', 'grupo_muscular': 'isquios', 'series': 4, 'rpe_objetivo': 8}]
        self.assertEqual(aplicar_vispera_futbol(self.cliente, ej, self.martes + timedelta(days=2)), [])
        self.assertEqual(ej[0]['series'], 4)
