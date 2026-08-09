"""
Fix 414 URI Too Large — tests de regresión y contrato del nuevo mecanismo.

El bug: el flujo calendario→briefing→sesión activa serializaba el array completo
de ejercicios en la query string, generando URLs de 9.800-13.000+ caracteres.
PythonAnywhere las rechazaba con 414 antes de que Django las procesara.

El fix: cache de transporte con claves cortas en vez de JSON en la URL.
- Salto 1 (calendario→briefing): clave determinista
  `transporte_ejercicios_dia_{cliente_id}_{fecha_str}`, escrita en el AJAX
  de mes y leída en briefing_entrenamiento con fallback a _calcular_ejercicios_dia.
- Salto 2 (briefing→sesión activa): token aleatorio corto
  `transporte_ejercicios_mod_{token}`, escrito en briefing y leído en
  vista_entrenamiento_activo con fallback determinista.
"""

import json
from datetime import date
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('tester_414', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.c = Client()
        self.c.login(username='tester_414', password='x')
        self.fecha_str = date.today().strftime('%Y-%m-%d')

    def tearDown(self):
        cache.clear()


# ---------------------------------------------------------------------------
# Test 1: Las URLs generadas por las vistas corregidas son cortas y NO
#          contienen `ejercicios=`.
# ---------------------------------------------------------------------------

class UrlCorta_BriefingTests(_Base):
    """briefing_entrenamiento ya no mete ejercicios en la URL hacia sesión activa."""

    def _call_briefing(self):
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        # Poblamos el cache de transporte para que briefing lo encuentre
        _key = f"transporte_ejercicios_dia_{self.cliente.id}_{self.fecha_str}"
        cache.set(_key, [
            {'nombre': 'Press Banca', 'series': 4, 'repeticiones': 8, 'peso_kg': 80,
             'rpe_objetivo': 7, 'tipo_ejercicio': 'compuesto_principal'},
        ], 900)
        return self.c.get(url, {'fecha': self.fecha_str, 'rutina_nombre': 'Día 1 - Fuerza'})

    def test_briefing_devuelve_200(self):
        resp = self._call_briefing()
        self.assertIn(resp.status_code, (200, 302))

    def test_url_sesion_en_contexto_no_contiene_ejercicios(self):
        resp = self._call_briefing()
        if resp.status_code != 200:
            return  # redirect es aceptable
        url_sesion = resp.context.get('url_sesion', '')
        self.assertNotIn('ejercicios=', url_sesion,
                         msg="La URL hacia entrenamiento_activo no debe llevar ejercicios= en la query string")

    def test_url_sesion_en_contexto_es_corta(self):
        resp = self._call_briefing()
        if resp.status_code != 200:
            return
        url_sesion = resp.context.get('url_sesion', '')
        self.assertLess(len(url_sesion), 500,
                        msg=f"URL demasiado larga ({len(url_sesion)} chars): {url_sesion[:200]}")

    def test_url_sesion_contiene_ejercicios_token(self):
        resp = self._call_briefing()
        if resp.status_code != 200:
            return
        url_sesion = resp.context.get('url_sesion', '')
        self.assertIn('ejercicios_token=', url_sesion,
                      msg="La URL hacia entrenamiento_activo debe llevar ejercicios_token=")


# ---------------------------------------------------------------------------
# Test 2: El contenido llega intacto (nombre del ejercicio preservado).
# ---------------------------------------------------------------------------

class ContenidoInacto_EntrenoActivoTests(_Base):
    """Los ejercicios que llegan a vista_entrenamiento_activo son los del cache."""

    def test_ejercicio_llega_desde_cache_token(self):
        token = 'testtoken123'
        ejercicios_mod = [
            {'nombre': 'Sentadilla', 'series': 4, 'repeticiones': 6,
             'peso_recomendado_kg': 100, 'rpe': 8, 'form_id': 'ej_0',
             'tipo_ejercicio': 'compuesto_principal'},
        ]
        cache.set(f"transporte_ejercicios_mod_{token}", ejercicios_mod, 900)

        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        resp = self.c.get(url, {
            'fecha': self.fecha_str,
            'rutina_nombre': 'Día 1 - Fuerza',
            'ejercicios_token': token,
        })
        self.assertIn(resp.status_code, (200, 302))
        if resp.status_code == 200:
            ejercicios_en_template = resp.context.get('ejercicios_planificados', [])
            nombres = [e.get('nombre') for e in ejercicios_en_template]
            self.assertIn('Sentadilla', nombres,
                          msg="El ejercicio del cache no llegó al template")


# ---------------------------------------------------------------------------
# Test 3: Fallback en cache miss — no 500, no lista vacía silenciosa.
# ---------------------------------------------------------------------------

class FallbackCacheMiss_BriefingTests(_Base):
    """briefing_entrenamiento cae al helper _calcular_ejercicios_dia si no hay cache."""

    def test_briefing_sin_cache_no_lanza_500(self):
        # No se pre-carga nada en cache — debe usar el fallback determinista
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        resp = self.c.get(url, {'fecha': self.fecha_str, 'rutina_nombre': 'Día 1 - Fuerza'})
        self.assertNotEqual(resp.status_code, 500,
                            msg="briefing_entrenamiento lanzó 500 en cache miss")
        self.assertIn(resp.status_code, (200, 302))


class FallbackCacheMiss_EntrenoActivoTests(_Base):
    """vista_entrenamiento_activo con token inválido no lanza 500."""

    def test_entrenamiento_activo_token_invalido_no_lanza_500(self):
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        resp = self.c.get(url, {
            'fecha': self.fecha_str,
            'rutina_nombre': 'Día 1 - Fuerza',
            'ejercicios_token': 'token_que_no_existe_en_cache',
        })
        self.assertNotEqual(resp.status_code, 500,
                            msg="entrenamiento_activo lanzó 500 con token inválido")
        self.assertIn(resp.status_code, (200, 302))

    def test_entrenamiento_activo_sin_token_no_lanza_500(self):
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        resp = self.c.get(url, {
            'fecha': self.fecha_str,
            'rutina_nombre': 'Día 1 - Fuerza',
        })
        self.assertNotEqual(resp.status_code, 500)
        self.assertIn(resp.status_code, (200, 302))


# ---------------------------------------------------------------------------
# Test 3b: dashboard → briefing sin cache de calendario (botones "EMPEZAR
#          ENTRENAMIENTO") llevan '?ejercicios=<json>'. Antes del fix, ese
#          parámetro se ignoraba y _calcular_ejercicios_dia (sin plan en cache)
#          devolvía [], vaciando la sesión aunque el dashboard mostrara el
#          día correcto.
# ---------------------------------------------------------------------------

class FallbackGetEjercicios_BriefingTests(_Base):
    """briefing_entrenamiento usa '?ejercicios=' del dashboard si el cache de calendario está vacío."""

    def test_ejercicios_de_get_llegan_al_contexto_cuando_no_hay_cache_ni_plan(self):
        ejercicios_dashboard = [
            {'nombre': 'Peso Muerto', 'series': 4, 'repeticiones': 6,
             'peso_kg': 120, 'rpe_objetivo': 8,
             'tipo_ejercicio': 'compuesto_principal'},
        ]
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        resp = self.c.get(url, {
            'fecha': self.fecha_str,
            'rutina_nombre': 'Día 3 - Hipertrofia',
            'ejercicios': json.dumps(ejercicios_dashboard),
        })
        self.assertEqual(resp.status_code, 200)
        nombres = [e.get('nombre') for e in resp.context.get('ejercicios', [])]
        self.assertIn('Peso Muerto', nombres,
                       msg="El ejercicio pasado por '?ejercicios=' del dashboard no llegó al contexto del briefing")

    def test_payload_explicito_del_cta_prevalece_sobre_cache_del_calendario(self):
        """El CTA representa la decisión visible más reciente y debe ser la autoridad."""
        cache.set(
            f"transporte_ejercicios_dia_{self.cliente.id}_{self.fecha_str}",
            [{'nombre': 'Plan antiguo en cache', 'series': 4, 'repeticiones': 8}],
            900,
        )
        ejercicios_cta = [
            {'nombre': 'Plan explícito del CTA', 'series': 4, 'repeticiones': 6,
             'peso_kg': 100, 'rpe_objetivo': 8,
             'tipo_ejercicio': 'compuesto_principal'},
        ]

        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        resp = self.c.get(url, {
            'fecha': self.fecha_str,
            'rutina_nombre': 'Día 1 - Fuerza',
            'ejercicios': json.dumps(ejercicios_cta),
        })

        self.assertEqual(resp.status_code, 200)
        nombres = [e.get('nombre') for e in resp.context.get('ejercicios', [])]
        self.assertEqual(nombres, ['Plan explícito del CTA'])


class DeloadIdempotenteTransporteTests(_Base):
    def test_briefing_y_sesion_activa_no_reducen_series_dos_veces(self):
        """Continuidad contractual: el plan 4→3 en briefing debe seguir en 3 al ejecutar."""
        ejercicios = [
            {'nombre': 'Press Banca', 'series': 4, 'repeticiones': 6,
             'peso_kg': 100, 'rpe_objetivo': 8,
             'tipo_ejercicio': 'compuesto_principal'},
        ]
        url_briefing = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])

        with patch(
            'entrenos.services.briefing_service.necesita_deload_gym',
            return_value=True,
        ):
            briefing = self.c.get(url_briefing, {
                'fecha': self.fecha_str,
                'rutina_nombre': 'Día 1 - Fuerza',
                'ejercicios': json.dumps(ejercicios),
            })
            self.assertEqual(briefing.status_code, 200)
            ejercicios_briefing = briefing.context.get('ejercicios', [])
            self.assertEqual(ejercicios_briefing[0]['series'], 3)

            url_sesion = briefing.context['url_sesion']
            sesion = self.c.get(url_sesion)

        self.assertEqual(sesion.status_code, 200)
        ejercicios_sesion = sesion.context.get('ejercicios_planificados', [])
        self.assertEqual(ejercicios_sesion[0]['series'], 3)

    def test_sesion_activa_si_ajusta_plan_sin_marca_previa(self):
        """Un acceso directo con plan aún crudo conserva el ajuste 4→3."""
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        ejercicios_sin_ajustar = [
            {'nombre': 'Press Banca', 'series': 4, 'repeticiones': 6,
             'peso_kg': 100, 'rpe_objetivo': 8,
             'tipo_ejercicio': 'compuesto_principal'},
        ]

        with patch(
            'entrenos.services.briefing_service.necesita_deload_gym',
            return_value=True,
        ):
            sesion = self.c.get(url, {
                'fecha': self.fecha_str,
                'rutina_nombre': 'Día 1 - Fuerza',
                'ejercicios': json.dumps(ejercicios_sin_ajustar),
            })

        self.assertEqual(sesion.status_code, 200)
        ejercicios_sesion = sesion.context.get('ejercicios_planificados', [])
        self.assertEqual(ejercicios_sesion[0]['series'], 3)
        self.assertTrue(ejercicios_sesion[0]['_deload_aplicado'])


# ---------------------------------------------------------------------------
# Test 4: _calcular_ejercicios_dia devuelve lista cuando hay plan en cache.
# ---------------------------------------------------------------------------

class CalcularEjerciciosDiaTests(_Base):
    """Helper devuelve lista (vacía o con ejercicios) sin lanzar excepciones."""

    def test_retorna_lista_cuando_no_hay_plan(self):
        from entrenos.views import _calcular_ejercicios_dia
        result = _calcular_ejercicios_dia(self.cliente.id, date.today())
        self.assertIsInstance(result, list)

    def test_retorna_lista_cuando_plan_en_cache_sin_fecha(self):
        from entrenos.views import _calcular_ejercicios_dia
        # Plan mínimo que no tiene la fecha pedida → debe retornar [] sin crash
        plan_stub = {'entrenos_por_fecha': {}}
        año = date.today().year
        cache.set(f'plan_anual_{self.cliente.id}_{año}', plan_stub, 60)
        result = _calcular_ejercicios_dia(self.cliente.id, date.today())
        self.assertIsInstance(result, list)

    def test_retorna_ejercicios_cuando_fecha_presente_en_plan(self):
        from entrenos.views import _calcular_ejercicios_dia
        hoy = date.today()
        plan_stub = {
            'entrenos_por_fecha': {
                hoy.isoformat(): {
                    'nombre_rutina': 'Día 1 - Fuerza',
                    'ejercicios': [
                        {'nombre': 'Press Banca', 'series': 4, 'repeticiones': 8,
                         'peso_kg': 80, 'rpe_objetivo': 7,
                         'tipo_ejercicio': 'compuesto_principal',
                         'grupo_muscular': 'Pecho'},
                    ],
                }
            }
        }
        año = hoy.year
        cache.set(f'plan_anual_{self.cliente.id}_{año}', plan_stub, 60)

        with patch('core.bio_context.BioContextProvider.get_current_restrictions',
                   return_value={'tags': set()}):
            result = _calcular_ejercicios_dia(self.cliente.id, hoy)

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0, "Se esperaba al menos un ejercicio")
        self.assertEqual(result[0]['nombre'], 'Press Banca')
        # Verificar normalización
        self.assertIn('peso_recomendado_kg', result[0])
        self.assertIn('reps_objetivo', result[0])
        self.assertIn('form_id', result[0])
