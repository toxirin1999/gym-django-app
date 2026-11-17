"""16-nov-2026 · Repaso del Día 1: notas 5, 10, 12, 23, 24, 25 y 26."""

import logging
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from entrenos.tests_serie_testigo_20261108 import Base as BaseTestigo
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

LUNES = date(2026, 11, 16)
HOY = timezone.localdate()


class SerieTestigoEnElMovil(BaseTestigo):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.jalon(date(2026, 10, 20), 60, 12)
        self.client.force_login(self.user)

    def abrir(self):
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        return self.client.get(url, {'fecha': LUNES.isoformat(), 'rutina_nombre': 'Día 1 - Fuerza'})

    def test_nota5_las_casillas_tienen_borde_visible(self):
        r = self.abrir()
        self.assertContains(r, 'class="st-campo"', count=2)
        self.assertContains(r, '#serie-testigo .st-campo{')
        self.assertContains(r, 'border:2px solid')

    def test_nota10_al_guardar_se_pliega_el_bloque_y_queda_la_frase(self):
        r = self.abrir()
        self.assertContains(r, "classList.add('st-hecha')")
        self.assertContains(r, '#serie-testigo.st-hecha .st-oculto{display:none !important;}')
        # la frase del resultado no lleva la clase que se oculta
        self.assertContains(r, 'id="st-resultado"')
        self.assertNotContains(r, 'id="st-resultado" class="st-oculto"')


class TopeDeMaquinaAlCerrar(Base):
    def test_nota12_el_resumen_del_ejercicio_no_promete_ajustar_el_peso_en_el_tope(self):
        from django.template.loader import get_template
        fuente = get_template('entrenos/entrenamiento_activo.html').template.source
        self.assertIn('En el máximo de la máquina', fuente)
        self.assertIn('no hay más peso, así que la próxima vez repetimos', fuente)
        # el aviso del tope se evalúa antes que el «ajusto el peso» de por debajo del rango
        self.assertLess(fuente.index('En el máximo de la máquina'),
                        fuente.index("t:'Alguna serie por debajo del rango'"))


class PeticionesLentas(SimpleTestCase):
    def _pasar(self, espera):
        from core.lentitud_middleware import PeticionesLentasMiddleware
        reloj = iter([0.0, espera])
        mw = PeticionesLentasMiddleware(lambda request: SimpleNamespace(status_code=200))
        peticion = RequestFactory().get('/clientes/cuerpo/?token=secreto')
        with override_settings(LENTITUD_UMBRAL_S=2.0), \
                mock.patch('core.lentitud_middleware.time.monotonic', side_effect=lambda: next(reloj)):
            mw(peticion)

    def test_nota23_una_peticion_lenta_deja_una_linea_sin_cadena_de_consulta(self):
        with self.assertLogs('lentitud', level=logging.WARNING) as capturado:
            self._pasar(47.0)
        linea = capturado.output[0]
        self.assertIn('/clientes/cuerpo/', linea)
        self.assertIn('total=47.0s', linea)
        self.assertIn('consultas=0', linea)
        self.assertNotIn('secreto', linea)

    def test_nota23_una_rapida_no_deja_nada(self):
        with mock.patch('core.lentitud_middleware.logger') as registro:
            self._pasar(0.4)
        registro.warning.assert_not_called()


class VeredictosConContexto(SimpleTestCase):
    def _evaluar(self, motivo, rpe, contexto, **extra):
        from entrenos.services import decision_log_service as d
        guardado = {}
        log = SimpleNamespace(
            motivo_codigo=motivo, accion='mantener', peso_anterior=45, reps_anteriores=extra.get('antes', 8), reps_sugeridas=extra.get('objetivo', 9),
            peso_sugerido=None, cliente=None,
        )
        sesion = SimpleNamespace(
            rpe=rpe, fallo_muscular=False, nombre_ejercicio='Press Francés', peso_kg=45, repeticiones=8,
            entreno=SimpleNamespace(), molestia_reportada=False,
        )
        with mock.patch.object(d, '_rendimiento_representativo_desde_series', return_value=(45, extra.get('reps', 8))), \
                mock.patch.object(d, '_rpe_pedido', return_value=8.0), \
                mock.patch.object(d, '_tecnicas_sesion', return_value=set()), \
                mock.patch.object(d, '_contexto_de_ese_dia', return_value=contexto), \
                mock.patch('entrenos.services.ultima_sesion_service.dia_de_fatiga', return_value=None), \
                mock.patch.object(d, '_persistir_evaluacion_final',
                                  side_effect=lambda lg, res, notas: guardado.update(res=res, notas=notas)):
            d._evaluar_log(log, sesion)
        return guardado

    def test_nota24_rpe_alto_con_contexto_no_se_da_por_fallido(self):
        g = self._evaluar('progresion_reps', 10, 'lo hiciste al final, fuera de su orden')
        self.assertEqual(g['res'], 'neutra')
        self.assertIn('fuera de su orden', g['notas'])
        self.assertIn('El resultado de hoy queda sin evaluar', g['notas'])

    def test_nota24_rpe_alto_sin_contexto_sigue_siendo_fallido(self):
        g = self._evaluar('progresion_reps', 10, None)
        self.assertEqual(g['res'], 'fallida')

    def test_nota25_menos_reps_en_el_tope_con_contexto_se_vuelve_a_comprobar(self):
        g = self._evaluar('tope_maquina', 7, 'llegabas con energía 6 frente a tu 8 habitual', reps=14, antes=19, objetivo=20)
        self.assertEqual(g['res'], 'neutra')
        self.assertIn('energía 6', g['notas'])


class TextoDeMantener(Base):
    def test_nota26_el_cierre_dice_las_reps_de_hoy_cuando_fueron_desiguales(self):
        from entrenos.models import GymDecisionLog
        from entrenos.services.cierre_porque_service import _doble_progresion
        b = EjercicioBase.objects.create(nombre='Press Pecho Convergente', grupo_muscular='x',
                                         tipo_progresion='peso_reps')
        e = self.entreno(HOY, {b.nombre: '6-12'})
        self.hacer(e, b, [(85, 10, 8), (85, 9, 8), (85, 8, 9)])
        log = mock.Mock(spec=GymDecisionLog)
        log.accion = 'mantener'
        log.peso_anterior = 85
        log.reps_anteriores = 10
        log.entreno_origen = e
        log.entreno_origen_id = e.id
        log.ejercicio = b.nombre
        texto = _doble_progresion(log, 'peso_reps')
        self.assertIn('(hoy: 10, 9 y 8)', texto)
        self.assertIn('Con 12 en todas las series, subo el peso.', texto)
