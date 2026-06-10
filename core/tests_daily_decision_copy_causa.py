"""
Phase 59X.D — Copy del semáforo por causa.

No cambia la decisión (estado/causa/tipo_recuperar/datos_raw): solo el
copy (mensaje, recomendaciones, título) según causa y fase_plan.

Disparador: durante una descarga planificada (fase_plan.es_descarga=True),
el semáforo no debe usar lenguaje de abandono/compensación/"volver"/
"recuperar lo perdido" — esa era la incoherencia conceptual de raíz que
detectó David.

Casos:
1. RECUPERAR + descarga (fatiga real durante deload) — copy reasegurador,
   sin lenguaje de abandono.
2. RECUPERAR + descarga (fragilidad) — ídem, también en recomendaciones.
3. EJECUTAR CON MARGEN — causa='fragilidad' usa título propio (no
   "RECUPERAR"), manteniendo estado='recuperar' para no romper routing.
4. Sin descarga: mensajes/títulos originales no cambian (regresión).
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from core.daily_decision import DailyDecisionEngine as DDE


_FORBIDDEN_DESCARGA = (
    'recuperar lo perdido', 'volver con', 'reenganchar',
    'compensar la pausa', 'abandono',
)

_ACT_CTX_BASE = {
    'sesiones_gym_semana': 0,
    'sesiones_hyrox_semana': 0,
    'sesiones_semana_total': 0,
    'actividad_semana': {},
    'ultima_actividad': None,
    'racha_dias': 0,
    'fase_plan': None,
}


def _act_ctx(fase_plan=None):
    ctx = dict(_ACT_CTX_BASE)
    ctx['fase_plan'] = fase_plan
    return ctx


_FASE_DESCARGA = {
    'tipo': 'descarga', 'es_descarga': True,
    'dias_en_fase': 3, 'nombre': 'Descarga',
}


class TestCopyPorCausa(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('tester_59xd', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _estado(self, *, readiness=0.75, acwr=None, energia=None,
                fase_plan=None, es_descanso_plan=None, ausencia=None):
        bio = {
            'has_data': energia is not None, 'hrv_ms': None,
            'energia': energia, 'horas_sueno': None,
        }
        patches = [
            patch('core.daily_decision.BioContextProvider.get_bio_signals', return_value=bio),
            patch('core.daily_decision.BioContextProvider.get_readiness_score',
                  return_value={'score': readiness}),
            patch('core.daily_decision.get_actividad_context', return_value=_act_ctx(fase_plan)),
            patch('entrenos.services.services.EstadisticasService.analizar_acwr_unificado',
                  return_value={'acwr_actual': acwr}),
        ]
        if ausencia is not None:
            patches.append(patch.object(DDE, '_calcular_ausencia_dias', return_value=ausencia))

        with patches[0], patches[1], patches[2], patches[3]:
            if len(patches) == 5:
                with patches[4]:
                    return DDE.get_estado_hoy(self.cliente, es_descanso_plan=es_descanso_plan)
            return DDE.get_estado_hoy(self.cliente, es_descanso_plan=es_descanso_plan)

    # ── Caso 3: fragilidad → título propio, estado interno intacto ──────
    def test_fragilidad_titulo_ejecutar_con_margen(self):
        e = self._estado(readiness=0.88, acwr=0.5, energia=8)
        self.assertEqual(e['causa'], 'fragilidad')
        self.assertEqual(e['estado'], DDE.RECUPERAR,
                         "el estado interno no cambia, solo el título visible")
        self.assertEqual(e['titulo'], 'EJECUTAR CON MARGEN')

    # ── Caso 1: RECUPERAR por fatiga + descarga ──────────────────────────
    def test_recuperar_fatiga_con_descarga_evita_lenguaje_abandono(self):
        e = self._estado(readiness=0.30, fase_plan=_FASE_DESCARGA)
        self.assertEqual(e['causa'], 'fatiga')
        msg = e['mensaje'].lower()
        for frase in _FORBIDDEN_DESCARGA:
            self.assertNotIn(frase, msg, f"mensaje no debe contener '{frase}'")
        self.assertIn('descarga', msg)

    # ── Caso 2: RECUPERAR por fragilidad + descarga ──────────────────────
    def test_recuperar_fragilidad_con_descarga_evita_lenguaje_reenganche(self):
        e = self._estado(readiness=0.88, acwr=0.5, energia=8, fase_plan=_FASE_DESCARGA)
        self.assertEqual(e['causa'], 'fragilidad')
        for campo in ('mensaje', 'recomendacion_gym', 'recomendacion_hyrox'):
            texto = e[campo].lower()
            for frase in _FORBIDDEN_DESCARGA:
                self.assertNotIn(frase, texto, f"{campo} no debe contener '{frase}'")

    # ── Caso 4: regresión sin descarga ───────────────────────────────────
    def test_recuperar_fatiga_sin_descarga_mensaje_original(self):
        e = self._estado(readiness=0.30, fase_plan=None)
        self.assertEqual(e['causa'], 'fatiga')
        self.assertEqual(e['mensaje'], DDE._MENSAJES['recuperar_descanso'])
        self.assertEqual(e['titulo'], 'RECUPERAR')

    def test_volver_sin_descarga_mensaje_y_titulo_original(self):
        e = self._estado(readiness=0.75, fase_plan=None, ausencia=6)
        self.assertEqual(e['estado'], DDE.VOLVER)
        self.assertEqual(e['causa'], 'ausencia')
        self.assertEqual(e['mensaje'], DDE._MENSAJES['volver'])
        self.assertEqual(e['titulo'], 'VOLVER')
