"""17-nov-2026 · Lentitud: series de un entreno compartidas entre funciones.

Producción (21:54): cierre 407 145 consultas, Ahora 289. Cuatro funciones leían
las series del mismo entreno por separado, cada una con su filtro:
- ``cierre_porque_service._series_trabajo`` (x8): completadas, sin
  aproximaciones, orden ``serie_numero, id``;
- ``decision_log_service._rendimiento_representativo_desde_series`` (x8):
  completadas, con peso, sin aproximaciones;
- ``cierre_entrenamiento_service._series_completadas``: completadas;
- ``ultima_sesion_service._series_del_entreno``: completadas, sin aproximaciones,
  orden ``serie_numero, id``.
Ahora, dentro de una petición, las series completadas de cada entreno se leen
una vez (con su ejercicio, en ``serie_numero, id``) y cada función aplica su
filtro. Y ``aprendizaje_decisiones_service._sesion_evaluadora`` (x8) sale del
historial del ejercicio ya leído en la petición.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog, SerieRealizada
from entrenos.services.aprendizaje_decisiones_service import _sesion_evaluadora
from entrenos.services.cierre_entrenamiento_service import _metricas_comparables_por_unidad, _rendimiento_representativo
from entrenos.services.cierre_porque_service import _series_trabajo, texto_series
from entrenos.services.decision_log_service import _rendimiento_representativo_desde_series
from entrenos.services.ultima_sesion_service import series_de_trabajo
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 11, 17)


class SeriesCompartidas(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='series-compartidas', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'S'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        self.banca = EjercicioBase.objects.create(nombre='Press Banca', grupo_muscular='otros', tipo_progresion='peso_reps')
        self.farmer = EjercicioBase.objects.create(nombre='Farmer', grupo_muscular='otros',
                                                   tipo_progresion='progresion_distancia')
        self.plancha = EjercicioBase.objects.create(nombre='Plancha', grupo_muscular='otros',
                                                    tipo_progresion='progresion_tiempo')
        self.entreno = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=HOY)
        filas = [
            # (base, serie_numero, peso, reps, completado, aproximación, metros, rpe) — creadas fuera de orden
            (self.banca, 3, Decimal('80'), 6, True, False, None, 9),
            (self.banca, 1, Decimal('40'), 12, True, True, None, None),     # aproximación
            (self.banca, 2, Decimal('80'), 8, True, False, None, 8),
            (self.banca, 4, Decimal('85'), 3, False, False, None, 10),      # no completada
            (self.banca, 5, Decimal('70'), 10, True, False, None, 8),
            (self.banca, 6, None, 12, True, False, None, None),             # sin peso
            (self.farmer, 1, Decimal('24'), 1, True, False, Decimal('40'), None),
            (self.farmer, 2, Decimal('24'), 1, True, False, Decimal('30'), None),
            (self.plancha, 1, None, 45, True, False, None, None),
            (self.plancha, 2, None, 40, True, False, None, None),
        ]
        for base, num, peso, reps, comp, aprox, metros, rpe in filas:
            SerieRealizada.objects.create(entreno=self.entreno, ejercicio=base, serie_numero=num, repeticiones=reps,
                                          peso_kg=peso, completado=comp, es_aproximacion=aprox,
                                          distancia_metros=metros, rpe_real=rpe)

    def copia(self):
        return EntrenoRealizado.objects.get(pk=self.entreno.pk)

    def lecturas(self):
        e = self.copia
        return [
            [(s.serie_numero, s.peso_kg, s.repeticiones) for s in _series_trabajo(e(), 'Press Banca')],
            [(s.serie_numero, s.distancia_metros) for s in _series_trabajo(e(), 'farmer')],
            texto_series(e(), 'Press Banca', 'peso_reps'),
            texto_series(e(), 'Farmer', 'progresion_distancia'),
            _rendimiento_representativo_desde_series(e(), 'press banca'),
            _rendimiento_representativo_desde_series(e(), 'plancha'),
            _rendimiento_representativo_desde_series(e(), 'sin series'),
            _rendimiento_representativo(e(), 'Press Banca', 1, 1),
            _metricas_comparables_por_unidad(e(), 'Plancha', 'progresion_tiempo'),
            _metricas_comparables_por_unidad(e(), 'Farmer', 'progresion_distancia'),
            series_de_trabajo(e(), 'Press Banca'),
            series_de_trabajo(e(), 'Farmer'),
        ]

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))

    def test_cada_funcion_conserva_su_seleccion(self):
        lecturas = self.lecturas()
        # sin aproximaciones ni no completadas, en orden de serie
        self.assertEqual(lecturas[0], [(2, Decimal('80.00'), 8), (3, Decimal('80.00'), 6), (5, Decimal('70.00'), 10),
                                       (6, None, 12)])
        self.assertEqual(lecturas[1], [(1, Decimal('40.00')), (2, Decimal('30.00'))])
        # con peso y sin aproximaciones: 80 kg, media de 8 y 6
        self.assertEqual(lecturas[4], (Decimal('80.00'), Decimal('7')))
        self.assertIsNone(lecturas[5])   # plancha sin peso
        self.assertIsNone(lecturas[6])
        self.assertEqual(lecturas[8], {'tipo': 'tiempo', 'segundos': 85})
        self.assertEqual([s['peso'] for s in lecturas[10]], [80.0, 80.0, 70.0, 0.0])

    def test_dentro_de_una_peticion_da_lo_mismo(self):
        fuera = self.lecturas()
        dentro = []
        self.en_peticion(lambda r: dentro.extend(self.lecturas()))
        self.assertEqual(dentro, fuera)

    def test_una_lectura_de_series_por_entreno(self):
        def vista(request):
            copias = [self.copia() for _ in range(3)]
            with CaptureQueriesContext(connection) as ctx:
                for e in copias:
                    _series_trabajo(e, 'Press Banca')
                    _rendimiento_representativo_desde_series(e, 'press banca')
                    _rendimiento_representativo(e, 'Press Banca', 1, 1)
                    _metricas_comparables_por_unidad(e, 'Plancha', 'progresion_tiempo')
                    series_de_trabajo(e, 'Farmer')
            self.series = [q['sql'][:100] for q in ctx.captured_queries if 'FROM "entrenos_serierealizada"' in q['sql']]
        self.en_peticion(vista)
        self.assertEqual(len(self.series), 1, '\n'.join(self.series))

    def test_una_serie_cambiada_en_la_peticion_se_ve_despues(self):
        def vista(request):
            self.antes = _rendimiento_representativo_desde_series(self.copia(), 'press banca')
            SerieRealizada.objects.filter(entreno=self.entreno, serie_numero=3).update(peso_kg=Decimal('90'))
            self.despues = (_rendimiento_representativo_desde_series(self.copia(), 'press banca'),
                            [s.peso_kg for s in _series_trabajo(self.copia(), 'Press Banca')])
        self.en_peticion(vista)
        self.assertEqual(self.antes, (Decimal('80.00'), Decimal('7')))
        self.assertEqual(self.despues[0], (Decimal('90.00'), Decimal('6')))
        self.assertEqual(self.despues[1], [Decimal('80.00'), Decimal('90.00'), Decimal('70.00'), None])


class SesionEvaluadoraDesdeElHistorial(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='evaluadora', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'E'})
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        self.base = EjercicioBase.objects.create(nombre='Remo', grupo_muscular='otros', tipo_progresion='peso_reps')

        def sesion(dias, filas):
            e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=HOY + timedelta(days=dias))
            ejs = []
            for nombre, peso in filas:
                ejs.append(EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=nombre, peso_kg=peso,
                                                             repeticiones=10, rpe=8, completado=True))
                SerieRealizada.objects.create(entreno=e, ejercicio=self.base, serie_numero=len(ejs), repeticiones=10,
                                              peso_kg=peso, completado=True)
            return e, ejs

        self.origen, _ = sesion(-14, [('Remo', 50)])
        self.despues, (self.primera, self.segunda) = sesion(-7, [('Remo', 55), ('remo', 60)])   # dos filas
        sesion(0, [('Remo', 57.5)])
        self.log = GymDecisionLog.objects.create(cliente=self.cliente, ejercicio='Remo', ejercicio_normalizado='remo',
                                                 entreno_origen=self.origen, peso_anterior=50, reps_anteriores=10,
                                                 accion='subir_peso', valor_cambio=5, motivo='m')

    def test_misma_sesion_dentro_y_fuera_y_sin_consultar_el_historial_otra_vez(self):
        fuera = _sesion_evaluadora(self.log)

        def vista(request):
            from entrenos.services.historial_ejercicio_service import anteriores
            anteriores(self.cliente, self.origen, 'Remo')     # el cierre ya leyó el historial
            with CaptureQueriesContext(connection) as ctx:
                self.dentro = _sesion_evaluadora(self.log)
            self.er = [q for q in ctx.captured_queries if 'FROM "entrenos_ejerciciorealizado"' in q['sql']]
        self.en_peticion(vista)
        self.assertEqual(self.dentro, fuera)
        self.assertEqual(fuera['entreno_id'], self.despues.pk)
        self.assertEqual(len(self.er), 0, [q['sql'][:100] for q in self.er])

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))
