"""17-nov-2026 · Lentitud de Ahora: entrenos, versiones, calendario y análisis.

Producción (20:51, Ahora, 357 consultas): ``entrenos_entrenorealizado`` x66,
``generar_calendario_plan`` x14 (``rutinas_rutina``), ``_entrenos_con_version``
x15. Perfilado en local, las 66 no son una lectura de semana repetida: incluyen
las 15 de versiones (se leen con el entreno), ~18 de ``_ctx_analytics``
(mesociclos, fatiga), 8 de ``analizar_semana_entrenamiento`` y unos 25 sitios
sueltos. Cambios:

A. Ahora no calcula ``_ctx_analytics``: ni su plantilla ni su vista lo usan y
   solo lee. Prueba: el HTML de Ahora es idéntico calculándolo y sin calcularlo.
B. El calendario lee la rutina con cada entreno.
C. La primera búsqueda de ``ultima_sesion`` de la petición carga juntos los
   entrenos más recientes del cliente (como mucho 10) con su versión.
D. ``analizar_semana_entrenamiento`` se memoriza por cliente y lunes.
"""

import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import (
    EjercicioRealizado, EntrenoRealizado, GymDecisionVersion, SerieRealizada, SesionProgramada,
)
from rutinas.models import EjercicioBase, Rutina

NOMBRES = ['Press Banca', 'Remo', 'Sentadilla Hack', 'Curl Martillo', 'Extension Triceps', 'Jalon al pecho',
           'Prensa', 'Gemelos']


class Escenario(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='ahora-lenta', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'A', 'dias_disponibles': 3})
        self.hoy = timezone.localdate()
        bases = {n: EjercicioBase.objects.create(nombre=n, grupo_muscular='otros', tipo_progresion='peso_reps')
                 for n in NOMBRES}
        n = 0
        for k in range(70, 0, -1):
            if k % 7 not in (1, 3, 5):
                continue
            n += 1
            f = self.hoy - timedelta(days=k)
            rutina, _ = Rutina.objects.get_or_create(nombre=f'Dia {k % 7}')
            v = GymDecisionVersion.objects.create(
                cliente=self.cliente, fecha=f, version=1, decision_id=f'd{n}', origen='sistema',
                fingerprint='f', base_fingerprint='b', postura='empujar',
                snapshot={'entrenamiento': {'ejercicios': [{'nombre': x, 'repeticiones': '8-10'} for x in NOMBRES]}})
            e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=f, gym_decision_version=v,
                                                modo_reducido=(k % 7 == 5))
            if k % 7 == 1:   # solo algunos días tienen sesión programada con nombre; el resto lo pone la rutina
                SesionProgramada.objects.create(cliente=self.cliente, fecha_prevista=f, nombre_sesion=rutina.nombre,
                                                estado=SesionProgramada.ESTADO_COMPLETADA, entreno_realizado=e)
            # cada día, sus ejercicios (como en el plan real): las búsquedas de cada uno dan sesiones distintas
            del_dia = {1: NOMBRES[:3], 3: NOMBRES[3:6], 5: NOMBRES[6:]}[k % 7]
            for j, x in enumerate(del_dia):
                peso = 40 + j * 5 + (70 - k) // 7
                EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=x, peso_kg=peso, repeticiones=9, rpe=8,
                                                  completado=True)
                for s in range(3):
                    SerieRealizada.objects.create(entreno=e, ejercicio=bases[x], serie_numero=s + 1,
                                                  repeticiones=9 - s, peso_kg=peso, rpe_real=8, completado=True)

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))


def _sin_variables(html):
    """Quita lo que cambia entre dos cargas iguales (token CSRF)."""
    return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', '', html)


class AhoraSinAnalytics(Escenario):
    def test_el_html_de_ahora_es_identico_calculando_y_sin_calcular_los_analisis(self):
        import clientes.views as v
        original = v._get_dashboard_context_data

        def con_analytics(request, cliente, **kw):
            return original(request, cliente, **{**kw, 'con_analytics': True})

        self.client.force_login(self.user)
        url = reverse('clientes:dashboard_silencioso_preview')
        sin = self.client.get(url)
        cache.clear()
        with patch.object(v, '_get_dashboard_context_data', con_analytics), \
                patch.object(v, '_ctx_analytics', wraps=v._ctx_analytics) as espia:
            con = self.client.get(url)
        self.assertTrue(espia.called, 'la comparación tiene que calcular los análisis en una de las dos cargas')
        self.assertEqual(sin.status_code, 200)
        self.assertEqual(_sin_variables(con.content.decode()), _sin_variables(sin.content.decode()))

    def test_ahora_no_calcula_los_analisis_y_el_panel_completo_si(self):
        import clientes.views as v
        self.client.force_login(self.user)
        with patch.object(v, '_ctx_analytics', wraps=v._ctx_analytics) as espia:
            self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertFalse(espia.called)
        req = RequestFactory().get('/x/')
        req.user = self.user
        with patch.object(v, '_ctx_analytics', return_value={
                'ratios_fuerza': {}, 'fatiga_acumulada': {}, 'analisis_mesociclos': {}}) as espia:
            try:
                v._get_dashboard_context_data(req, self.cliente)
            except Exception:
                pass
        self.assertTrue(espia.called)


class CalendarioConRutina(Escenario):
    def test_el_calendario_no_lee_la_rutina_de_cada_entreno(self):
        from entrenos.services.calendario_plan_service import generar_calendario_plan
        antes = generar_calendario_plan(self.cliente, num_semanas=4, fecha_ref=self.hoy)
        with CaptureQueriesContext(connection) as ctx:
            despues = generar_calendario_plan(self.cliente, num_semanas=4, fecha_ref=self.hoy)
        self.assertEqual(despues, antes)
        rutinas = [q for q in ctx.captured_queries if q['sql'].lstrip().startswith('SELECT')
                   and 'FROM "rutinas_rutina"' in q['sql']]
        self.assertEqual(len(rutinas), 0, '\n'.join(q['sql'][:120] for q in rutinas))
        # «carga mantenida» se consulta una vez por entreno, no dos
        mantenida = [q for q in ctx.captured_queries if 'FROM "entrenos_ejerciciorealizado"' in q['sql']]
        con_entreno = sum(1 for s in antes for d in s['dias'] if d['entreno_realizado'])
        self.assertLessEqual(len(mantenida), con_entreno)
        nombres = [d['detalle']['nombre_sesion'] for s in antes for d in s['dias'] if d['entreno_realizado']]
        self.assertTrue(nombres and all(nombres), nombres)


class UltimaSesionConEntrenosRecientes(Escenario):
    def test_las_busquedas_de_varios_ejercicios_cargan_los_entrenos_juntos(self):
        from entrenos.services.ultima_sesion_service import ultima_sesion
        fuera = [ultima_sesion(self.cliente, n, self.hoy) for n in NOMBRES]

        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                self.dentro = [ultima_sesion(self.cliente, n, self.hoy) for n in NOMBRES]
            self.entrenos = [q['sql'][:100] for q in ctx.captured_queries
                             if q['sql'].lstrip().startswith('SELECT "entrenos_entrenorealizado"')]
        self.en_peticion(vista)
        resumen = lambda ls: [(l['entreno'].pk, l['fecha'], l['referencia']['peso'], l['series']) for l in ls]  # noqa: E731
        self.assertEqual(resumen(self.dentro), resumen(fuera))
        # antes: una lectura de entrenos por ejercicio (8)
        self.assertLessEqual(len(self.entrenos), 1, '\n'.join(self.entrenos))

    def test_un_ejercicio_con_la_ultima_sesion_antigua_tambien_la_encuentra(self):
        """La precarga es solo de los 10 entrenos más recientes; los demás se siguen leyendo."""
        from entrenos.services.ultima_sesion_service import ultima_sesion
        rutina, _ = Rutina.objects.get_or_create(nombre='Antigua')
        base = EjercicioBase.objects.create(nombre='Hip Thrust', grupo_muscular='otros', tipo_progresion='peso_reps')
        viejo = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=self.hoy - timedelta(days=30))
        EjercicioRealizado.objects.create(entreno=viejo, nombre_ejercicio='Hip Thrust', peso_kg=100, repeticiones=8,
                                          completado=True)
        SerieRealizada.objects.create(entreno=viejo, ejercicio=base, serie_numero=1, repeticiones=8, peso_kg=100,
                                      completado=True)

        def vista(request):
            ultima_sesion(self.cliente, 'Press Banca', self.hoy)
            self.hip = ultima_sesion(self.cliente, 'Hip Thrust', self.hoy)
        self.en_peticion(vista)
        self.assertEqual((self.hip['entreno'].pk, self.hip['referencia']['peso']), (viejo.pk, 100.0))


class SemanaMemorizada(Escenario):
    def test_la_misma_semana_desde_cualquier_dia_se_lee_una_vez_y_da_lo_mismo(self):
        from entrenos.services.analisis_semanal_service import analizar_semana_entrenamiento
        lunes = self.hoy - timedelta(days=self.hoy.weekday() + 7)
        fuera = [analizar_semana_entrenamiento(self.cliente, lunes + timedelta(days=d)) for d in range(7)]

        def vista(request):
            analizar_semana_entrenamiento(self.cliente, lunes)
            with CaptureQueriesContext(connection) as ctx:
                self.dentro = [analizar_semana_entrenamiento(self.cliente, lunes + timedelta(days=d)) for d in range(7)]
            self.n = len(ctx.captured_queries)
        self.en_peticion(vista)
        self.assertEqual(self.dentro, fuera)
        self.assertTrue(fuera[0]['hay_datos'])
        self.assertEqual(self.n, 0)

    def test_un_entreno_guardado_en_la_peticion_cuenta_en_la_semana(self):
        from entrenos.services.analisis_semanal_service import analizar_semana_entrenamiento
        lunes = self.hoy - timedelta(days=self.hoy.weekday() + 7)

        def vista(request):
            self.antes = analizar_semana_entrenamiento(self.cliente, lunes)['sesiones_completadas']
            rutina, _ = Rutina.objects.get_or_create(nombre='Extra')
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=lunes + timedelta(days=6))
            self.despues = analizar_semana_entrenamiento(self.cliente, lunes)['sesiones_completadas']
        self.en_peticion(vista)
        self.assertEqual(self.despues, self.antes + 1)
