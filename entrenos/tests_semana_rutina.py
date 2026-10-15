"""Rutina y Plan cuentan la semana con la misma cola que Ahora (14-oct-2026).

Caso real del 14-oct: el Día 1 se hizo el martes; el miércoles Ahora proponía
el Día 2 (atrasado) y Rutina decía "HOY Día 3" y "martes: Día 2 programada".
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SemanaPlanGym
from rutinas.models import Rutina

LUNES = date(2026, 10, 12)
MARTES, MIERCOLES = LUNES + timedelta(days=1), LUNES + timedelta(days=2)
GRUPOS = {1: 'cuadriceps', 2: 'espalda', 3: 'pecho', 4: 'isquios', 5: 'hombros'}


class PlanificadorFalso:
    """Lunes a viernes, Día 1..5, cada uno de un grupo distinto."""

    def generar_entrenamiento_para_fecha(self, fecha):
        n = fecha.weekday() + 1
        if n > 5:
            return None
        return {
            'rutina_nombre': f'Dia {n} - Hipertrofia — Metabólica',
            'ejercicios': [{'nombre': f'Ejercicio {n}', 'series': 3, 'repeticiones': '12-15',
                            'peso_kg': 50, 'grupo_muscular': GRUPOS[n]}],
        }


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='semanarutina', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'S'})
        Cliente.objects.filter(pk=self.cliente.pk).update(fecha_registro=date(2025, 8, 1))
        self.cliente.refresh_from_db()
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Hipertrofia — Metabólica')
        self.entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=MARTES)
        EjercicioRealizado.objects.create(entreno=self.entreno, nombre_ejercicio='Sentadilla Hack',
                                          peso_kg=20, series=3, repeticiones=12, completado=True)
        patcher = patch('entrenos.services.sesion_recomendada._build_planificador',
                        return_value=PlanificadorFalso())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(cache.clear)


class SemanaSegunCola(Base):
    def test_el_miercoles_cuenta_lo_que_paso_y_lo_que_toca(self):
        from entrenos.services.semana_rutina_service import nota_semana, semana_segun_cola
        s = semana_segun_cola(self.cliente, MIERCOLES)
        dias = s['dias']
        self.assertEqual(dias[LUNES]['tipo'], 'sin_entreno')
        self.assertEqual(dias[MARTES]['tipo'], 'hecha')
        self.assertEqual(dias[MARTES]['nombre'], 'Dia 1 - Hipertrofia — Metabólica')
        self.assertEqual(dias[MIERCOLES]['nombre'], 'Dia 2 - Hipertrofia — Metabólica')  # lo mismo que Ahora
        self.assertTrue(dias[MIERCOLES]['atrasada'])
        self.assertEqual(dias[LUNES + timedelta(days=3)]['nombre'], 'Dia 3 - Hipertrofia — Metabólica')
        self.assertEqual(dias[LUNES + timedelta(days=4)]['nombre'], 'Dia 4 - Hipertrofia — Metabólica')
        # Como Ahora, la atrasada también toca en fin de semana.
        self.assertEqual(dias[LUNES + timedelta(days=5)]['nombre'], 'Dia 5 - Hipertrofia — Metabólica')
        self.assertEqual(dias[LUNES + timedelta(days=6)]['tipo'], 'descanso')
        self.assertEqual(s['fuera'], [])
        self.assertEqual(nota_semana(s), 'Llevas 1 de 5 sesiones esta semana.')

    def test_lo_que_no_cabe_antes_del_domingo_se_nombra(self):
        from entrenos.services.semana_rutina_service import nota_semana, semana_segun_cola
        s = semana_segun_cola(self.cliente, LUNES + timedelta(days=5))  # sábado sin más entrenos
        self.assertEqual(s['dias'][LUNES + timedelta(days=5)]['nombre'], 'Dia 2 - Hipertrofia — Metabólica')
        self.assertEqual(s['dias'][LUNES + timedelta(days=6)]['nombre'], 'Dia 3 - Hipertrofia — Metabólica')
        self.assertEqual(len(s['fuera']), 2)
        self.assertIn('no entran Día 4 y Día 5', nota_semana(s))

    def test_sin_atrasos_respeta_los_dias_de_descanso_del_plan(self):
        from entrenos.services.semana_rutina_service import semana_segun_cola
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 2 - Hipertrofia — Metabólica')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=MARTES)
        rutina1, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Hipertrofia — Metabólica')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina1, fecha=LUNES)
        s = semana_segun_cola(self.cliente, MIERCOLES)
        self.assertEqual(s['dias'][MIERCOLES]['nombre'], 'Dia 3 - Hipertrofia — Metabólica')
        self.assertFalse(s['dias'][MIERCOLES]['atrasada'])
        self.assertEqual(s['dias'][LUNES + timedelta(days=4)]['nombre'], 'Dia 5 - Hipertrofia — Metabólica')
        self.assertEqual(s['dias'][LUNES + timedelta(days=5)]['tipo'], 'descanso')

    def test_hoy_coincide_con_ahora(self):
        from entrenos.services.semana_rutina_service import semana_segun_cola
        from entrenos.services.sesion_recomendada import _siguiente_de_cola
        self.assertEqual(
            semana_segun_cola(self.cliente, MIERCOLES)['dias'][MIERCOLES]['nombre'],
            _siguiente_de_cola(self.cliente, MIERCOLES)['nombre'],
        )

    def test_si_hoy_ya_entrenaste_hoy_es_hecha(self):
        from entrenos.services.semana_rutina_service import semana_segun_cola
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 2 - Hipertrofia — Metabólica')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=MIERCOLES)
        s = semana_segun_cola(self.cliente, MIERCOLES)
        self.assertEqual(s['dias'][MIERCOLES]['tipo'], 'hecha')
        self.assertEqual(s['dias'][LUNES + timedelta(days=3)]['nombre'], 'Dia 3 - Hipertrofia — Metabólica')
        self.assertEqual(s['hechas'], 2)


class RutinaPreview(Base):
    def contexto(self):
        from entrenos.views import _obtener_contexto_rutina_silenciosa
        with patch('entrenos.views.PlanificadorHelms') as anual, \
                patch('entrenos.views.agregar_educacion_a_plan', side_effect=lambda p: p):
            anual.return_value.generar_plan_anual.return_value = {
                'plan_por_bloques': [{'nombre': 'Hipertrofia', 'duracion': 52}],
                'entrenos_por_fecha': {
                    (LUNES + timedelta(days=i)).isoformat(): {
                        'nombre_rutina': f'Día {i + 1} - del calendario',
                        'ejercicios': [{'nombre': 'X', 'series': 3, 'peso_kg': 40}],
                    } for i in range(5)
                },
            }
            return _obtener_contexto_rutina_silenciosa(self.cliente, hoy=MIERCOLES)

    def test_rutina_dice_lo_mismo_que_ahora(self):
        c = self.contexto()
        por_fecha = {d['fecha']: d for d in c['semana']}
        self.assertEqual(c['hoy']['titulo'], 'Dia 2 - Hipertrofia — Metabólica')
        self.assertIn('atrasada', c['hoy']['detalle'])
        self.assertEqual(por_fecha[MARTES]['tipo'], 'hecha')
        self.assertEqual(por_fecha[MARTES]['preview']['ejercicios'][0]['nombre'], 'Sentadilla Hack')
        self.assertIn(f'/entreno/{self.entreno.id}/cierre/', por_fecha[MARTES]['preview']['url'])
        self.assertEqual(por_fecha[LUNES]['preview']['etiqueta'], 'Sin entreno')
        jueves = por_fecha[LUNES + timedelta(days=3)]['preview']
        self.assertEqual((jueves['etiqueta'], jueves['titulo']), ('Prevista', 'Dia 3 - Hipertrofia — Metabólica'))
        self.assertIsNone(jueves['ejercicios'][0]['peso'])  # el peso lo fija el briefing
        self.assertIn('Llevas 1 de 5', c['insight'])

    def test_semana_pasada_cuenta_lo_que_se_hizo(self):
        from entrenos.views import _obtener_contexto_rutina_silenciosa
        with patch('entrenos.views.PlanificadorHelms') as anual, \
                patch('entrenos.views.agregar_educacion_a_plan', side_effect=lambda p: p):
            anual.return_value.generar_plan_anual.return_value = {
                'plan_por_bloques': [{'nombre': 'Hipertrofia', 'duracion': 52}],
                'entrenos_por_fecha': {(LUNES + timedelta(days=1)).isoformat(): {
                    'nombre_rutina': 'Día 2 - del calendario', 'ejercicios': [{'nombre': 'X', 'series': 3}]}},
            }
            c = _obtener_contexto_rutina_silenciosa(self.cliente, hoy=LUNES + timedelta(days=9),
                                                    semana_inicio=LUNES.isoformat())
        martes = next(d for d in c['semana'] if d['fecha'] == MARTES)
        self.assertEqual(martes['tipo'], 'hecha')
        self.assertIsNone(c['insight'])


class PlanSinAcuerdo(Base):
    def test_plan_lee_la_periodizacion_y_la_cola(self):
        from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES, semana_plan=3,
                                     origen=SemanaPlanGym.ORIGEN_AVANCE)
        t = proyectar_trayectoria_plan(self.cliente, fecha=MIERCOLES)
        self.assertEqual(t['estado'], 'available')
        self.assertEqual(t['semana']['origen'], 'cola')
        nombres = [(s['fecha_efectiva'], s['nombre'], s['realizada']) for s in t['semana']['sesiones']]
        self.assertEqual(nombres[0], (MARTES, 'Dia 1 - Hipertrofia — Metabólica', True))
        self.assertEqual(nombres[1], (MIERCOLES, 'Dia 2 - Hipertrofia — Metabólica', False))
        self.assertTrue(t['semana']['sesiones'][1]['en_cola'])
        self.assertEqual(t['semana']['fuera'], [])

    def test_antes_de_la_periodizacion_dinamica_sigue_sin_configurar(self):
        from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan
        # La periodización dinámica arranca en la semana real de hoy: antes no hay semanas.
        self.assertEqual(proyectar_trayectoria_plan(self.cliente, fecha=date(2026, 8, 26))['estado'], 'unknown')


class PortadaEsAhora(TestCase):
    def test_la_raiz_y_mi_panel_llevan_a_ahora(self):
        user = User.objects.create_user(username='portada', password='x')
        Cliente.objects.get_or_create(user=user, defaults={'nombre': 'P'})
        self.client.force_login(user)
        destino = reverse('clientes:dashboard_silencioso_preview')
        self.assertRedirects(self.client.get('/redirigir/'), destino, fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('clientes:panel_cliente')), destino,
                             fetch_redirect_response=False)
