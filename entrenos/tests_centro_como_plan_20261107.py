"""7-nov-2026 · Centro de decisiones con el mismo estado que Plan.

Prueba que cierra el paquete: en la semana de descarga, Centro y Plan dicen
lo mismo (5 de 5, Día 5 hecho, isquios en pausa hasta el lunes y revisión el 17/11).

- C1: la propuesta en pausa por la descarga sale en pausa, no «semana 4 de 4».
- C2/C3: bloque y semana salen de proyectar_trayectoria_plan, el mismo estado que Plan.
- C4: sin formularios de bloque ni de prioridad.
- C5: «Hoy: Día 5 hecho» sale de la sesión de gym registrada, aunque haya un
  descanso guardado; un partido importado no da por hecho el Día.
- C6: carga por ejercicio separada en vigente e historial.
- C7: sin «JOI: lectura mínima».
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from entrenos.models import (
    ActividadRealizada, EjercicioRealizado, EntrenoRealizado, GymDecisionLog, SemanaPlanGym,
)
from rutinas.models import Rutina

LUNES = date(2026, 11, 2)
SABADO = LUNES + timedelta(days=5)
PLANTILLA = Path(settings.BASE_DIR) / 'clientes' / 'templates' / 'clientes' / 'plan_decisiones.html'


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user('centro_como_plan_20261107', password='x')
        self.cliente = self.user.cliente_perfil
        self.cliente.dias_disponibles = 5
        self.cliente.save(update_fields=['dias_disponibles'])

    def semana_de_descarga(self):
        for i, n in enumerate((39, 40, 41, 42, 43, 44)):
            SemanaPlanGym.objects.create(
                cliente=self.cliente, lunes=LUNES - timedelta(weeks=5 - i), semana_plan=n,
                descarga=(n == 44), origen=SemanaPlanGym.ORIGEN_AVANCE,
            )

    def entreno(self, dia, nombre):
        rutina, _ = Rutina.objects.get_or_create(nombre=nombre)
        return EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=dia)


class MismoEstadoQuePlan(Base):
    def test_descarga_bloque_y_semana_como_plan(self):
        from entrenos.services.centro_decisiones_service import construir_resumen_operativo_centro
        from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan
        self.semana_de_descarga()
        for i, d in enumerate((0, 1, 2, 4, 5)):  # como David: el jueves libre, el Día 5 el sábado
            self.entreno(LUNES + timedelta(days=d), f'Día {i + 1} - Descarga Activa')

        r = construir_resumen_operativo_centro(self.cliente, {'bloque': None}, None, SABADO)
        plan = proyectar_trayectoria_plan(self.cliente, fecha=SABADO)

        self.assertEqual(r['bloque']['estado'], 'periodizacion')
        self.assertTrue(r['bloque']['descarga'])
        self.assertEqual(r['bloque']['nombre'], plan['periodizacion']['nombre'])
        self.assertEqual((r['bloque']['semana_actual'], r['bloque']['semanas_total']),
                         (plan['periodizacion']['semana_actual'], plan['periodizacion']['semanas']))
        self.assertEqual(r['bloque']['siguiente_nombre'], 'Fuerza — Hipertrofia')
        self.assertEqual(r['bloque']['siguiente_inicio'], LUNES + timedelta(days=7))
        hechas = sum(1 for s in plan['semana']['sesiones'] if s['realizada'])
        self.assertEqual((r['semana']['completadas'], r['semana']['objetivo']),
                         (hechas, plan['semana']['objetivo_sesiones']))
        self.assertEqual(r['semana']['completadas'], 5)
        self.assertEqual(r['semana']['hecha_hoy'], {'nombre': 'Día 5', 'completa': True})

    def test_pantalla_dice_descarga_5_de_5_y_lo_que_viene(self):
        from django.urls import reverse
        self.semana_de_descarga()
        for i, d in enumerate((0, 1, 2, 4, 5)):  # como David: el jueves libre, el Día 5 el sábado
            self.entreno(LUNES + timedelta(days=d), f'Día {i + 1} - Descarga Activa')
        self.client.force_login(self.user)
        with patch('django.utils.timezone.localdate', return_value=SABADO):
            html = self.client.get(reverse('clientes:plan_decisiones')).content.decode()
        self.assertNotIn('Bloque sin semana actual', html)
        self.assertNotIn('Semana pendiente de programar', html)
        self.assertIn('Descarga · Semana 1 de 1', html)
        self.assertIn('5 de 5 hechas', html)
        self.assertIn('El lunes 09/11 empieza Fuerza — Hipertrofia', html)
        self.assertIn('Hoy: Día 5 hecho', html)
        self.assertNotIn('Preparar bloque Gym', html)
        self.assertNotIn('Priorizar un grupo muscular', html)


class HoySegunLaSesion(Base):
    def _hoy(self, cambios):
        from clientes.views import _hoy_segun_sesion
        return _hoy_segun_sesion(self.cliente, SABADO, cambios, {'semana': {}})

    def test_sesion_registrada_gana_al_descanso_guardado(self):
        from clientes.views import _hoy_segun_sesion
        cambios = [{'titulo': 'Hoy: descanso', 'porque': 'x'}, {'titulo': '+2 series por semana de isquios'}]
        res = _hoy_segun_sesion(self.cliente, SABADO, cambios,
                                {'semana': {'hecha_hoy': {'nombre': 'Día 5', 'completa': True}}})
        self.assertEqual([c['titulo'] for c in res], ['Hoy: Día 5 hecho', '+2 series por semana de isquios'])

    def test_un_partido_importado_no_da_por_hecho_el_dia(self):
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Fútbol',
                                          fecha=SABADO, duracion_minutos=60)
        cambios = [{'titulo': 'Hoy: descanso', 'porque': None}]
        self.assertEqual(self._hoy(cambios), cambios)

    def test_sin_semana_del_plan_basta_la_sesion_de_gym(self):
        self.entreno(SABADO, 'Dia 1')
        self.assertEqual(self._hoy([{'titulo': 'Hoy: descanso'}])[0]['titulo'], 'Hoy: sesión de gym hecha')


class PropuestaEnPausa(Base):
    def test_en_pausa_hasta_el_lunes_y_revision(self):
        from clientes.views import _cambios_plan_ahora
        visible = {
            'tipo': 'en_curso', 'semana': 4, 'pausa': True,
            'propuesta': SimpleNamespace(fin=date(2026, 11, 17)),
            'presentacion': {'zona': 'Isquios', 'variacion_texto': '17,1', 'variacion_pct': -17.1,
                             'ejercicios': ['Curl Femoral Tumbado', 'Buenos Días (Good Mornings)'],
                             'semanas': 4, 'ajuste_texto': '+2'},
        }
        with patch('clientes.views._propuesta_zona_visible', return_value=visible):
            cambios = _cambios_plan_ahora(self.cliente, SABADO)
        isquios = next(c for c in cambios if 'isquios' in c['titulo'])
        self.assertEqual(isquios['titulo'], '+2 series por semana de isquios · en pausa esta semana por la descarga')
        self.assertIn('Se reanuda el lunes 09/11 y lo compruebo el 17/11.', isquios['detalle'])
        self.assertNotIn('semana 4 de 4', isquios['titulo'])


class CargaPorVigencia(Base):
    def log(self, ejercicio, accion, dia, motivo='m', resultado=None, estado='pendiente'):
        e = self.entreno(dia, f'Sesión {dia}')
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=ejercicio, peso_kg=10, series=3, repeticiones=10)
        log = GymDecisionLog.objects.create(cliente=self.cliente, ejercicio=ejercicio.lower(),
                                            ejercicio_normalizado=ejercicio.lower(), entreno_origen=e,
                                            accion=accion, motivo=motivo, resultado=resultado,
                                            estado_aplicacion=estado)
        return log

    def test_vigente_e_historial(self):
        from entrenos.services.centro_decisiones_service import decisiones_por_vigencia
        desde = LUNES
        self.log('Bayesian Curl', 'cambiar_variante', LUNES - timedelta(days=10))      # anterior y vigente
        self.log('Encogimientos', 'bajar_peso', LUNES - timedelta(days=7))             # sustituida
        self.log('Encogimientos', 'mantener', LUNES + timedelta(days=1))
        self.log('Jalon Brazos Rectos', 'subir_peso', LUNES + timedelta(days=1), estado='pospuesta')
        self.log('Pallof Press', 'mantener', LUNES + timedelta(days=1))
        self.log('Remo', 'mantener', LUNES - timedelta(days=12))                       # fuera del bloque
        logs = GymDecisionLog.objects.filter(cliente=self.cliente).select_related('entreno_origen').order_by('-fecha_creacion')
        r = decisiones_por_vigencia(self.cliente, logs, desde, SABADO)
        vigentes = {(d['ejercicio'], d['accion'], d['estado']) for d in r['vigentes']}
        self.assertEqual(vigentes, {('Bayesian Curl', 'cambiar_variante', 'para la próxima sesión'),
                                    ('Jalon Brazos Rectos', 'subir_peso', 'pospuesta')})
        historial = {(d['ejercicio'], d['accion']) for d in r['historial']}
        self.assertEqual(historial, {('Encogimientos', 'mantener'), ('Pallof Press', 'mantener')})
        self.assertTrue(all(d['fecha'] for d in r['historial']))

    def test_ya_evaluada_no_es_vigente(self):
        from entrenos.services.centro_decisiones_service import decisiones_por_vigencia
        self.log('Curl', 'subir_peso', LUNES + timedelta(days=1), resultado='validada')
        logs = GymDecisionLog.objects.filter(cliente=self.cliente).select_related('entreno_origen')
        r = decisiones_por_vigencia(self.cliente, logs, LUNES, SABADO)
        self.assertEqual(r['vigentes'], [])
        self.assertEqual(len(r['historial']), 1)


class Plantilla(SimpleTestCase):
    def test_sin_formularios_ni_joi_minima(self):
        src = PLANTILLA.read_text(encoding='utf-8')
        self.assertNotIn('id="preparar-bloque-gym"', src)
        self.assertNotIn('Priorizar un grupo muscular', src)
        self.assertIn("lectura_semanal_joi.estado != 'minima'", src)
        self.assertIn('carga_vigencia.vigentes', src)
        self.assertNotIn('Ver decisiones por ejercicio', src)
