"""17-nov-2026 · Lentitud: lecturas repetidas del cierre.

Producción (19:51, cierre 407): 263 consultas. Dos grupos se repetían por
ejercicio sobre los mismos datos:
- series de un entreno: ``_rendimiento_representativo`` x16 y
  ``_metricas_comparables_por_unidad`` x14 leían todas las series del entreno
  por cada ejercicio;
- versión del plan de una sesión: ``ejercicio_marcado_descarga`` x11 y
  ``rango_de_sesion`` x9 la leían por cada copia del mismo entreno.
Dentro de una petición ahora se leen una vez por entreno y una vez por versión.
Mismo resultado; un cambio guardado en la petición se ve en la lectura siguiente.
"""

from datetime import date
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import EntrenoRealizado, GymDecisionVersion, SerieRealizada
from entrenos.services.cierre_entrenamiento_service import (
    _metricas_comparables_por_unidad,
    _rendimiento_representativo,
)
from entrenos.services.sesion_descarga_service import ejercicio_marcado_descarga
from entrenos.services.ultima_sesion_service import rango_de_sesion
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 11, 17)


class LecturasDelCierreEnBloque(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='cierre-lento', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'C'})
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        self.version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=HOY, version=1, decision_id='d1', origen='sistema',
            fingerprint='f', base_fingerprint='b', postura='empujar',
            snapshot={'entrenamiento': {'ejercicios': [
                {'nombre': 'Press Banca', 'repeticiones': '8-10'},
                {'nombre': 'Remo', 'repeticiones': '10-12', 'deload': True},
                {'nombre': 'Plancha', 'repeticiones': '30-45'},
                {'nombre': 'Farmer', 'repeticiones': '30'},
            ]}},
        )
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina, fecha=HOY, gym_decision_version=self.version)
        b = {n: EjercicioBase.objects.create(nombre=n, grupo_muscular='otros', tipo_progresion=t)
             for n, t in [('Press Banca', 'peso_reps'), ('Remo', 'peso_reps'),
                          ('Plancha', 'progresion_tiempo'), ('Farmer', 'progresion_distancia')]}
        filas = [
            # (ejercicio, peso, reps, completado, aproximación, metros)
            ('Press Banca', 40, 12, True, True, None),       # aproximación: cuenta en rendimiento, no en métricas
            ('Press Banca', 70, 10, True, False, None),
            ('Press Banca', 75, 8, True, False, None),
            ('Press Banca', 80, 5, False, False, None),      # no completada: no cuenta
            ('Remo', 50, 12, True, False, None),
            ('Remo', None, 12, True, False, None),           # sin peso: no cuenta en rendimiento
            ('Plancha', None, 40, True, False, None),
            ('Plancha', None, 35, True, False, None),
            ('Farmer', 24, 1, True, False, 30),
            ('Farmer', 24, 1, True, False, 40),
        ]
        for i, (n, peso, reps, comp, aprox, metros) in enumerate(filas, start=1):
            SerieRealizada.objects.create(entreno=self.entreno, ejercicio=b[n], serie_numero=i, repeticiones=reps,
                                          peso_kg=peso, completado=comp, es_aproximacion=aprox,
                                          distancia_metros=metros)

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))

    def copia(self):
        """Otra instancia del mismo entreno, como las que trae cada búsqueda de historial."""
        return EntrenoRealizado.objects.get(pk=self.entreno.pk)

    def lecturas(self):
        return [
            _rendimiento_representativo(self.copia(), 'Press Banca', 1, 1),
            _rendimiento_representativo(self.copia(), 'Remo', 1, 1),
            _rendimiento_representativo(self.copia(), 'Sentadilla', 33, 7),           # sin series: el agregado
            _metricas_comparables_por_unidad(self.copia(), 'Plancha', 'progresion_tiempo'),
            _metricas_comparables_por_unidad(self.copia(), 'Farmer', 'progresion_distancia'),
            _metricas_comparables_por_unidad(self.copia(), 'Press Banca', 'peso_reps'),
            _metricas_comparables_por_unidad(self.copia(), 'Sentadilla', 'progresion_tiempo'),
            rango_de_sesion(self.copia(), 'Press Banca'),
            rango_de_sesion(self.copia(), 'Remo'),
            rango_de_sesion(self.copia(), 'Sentadilla'),
            ejercicio_marcado_descarga(self.copia(), 'Remo'),
            ejercicio_marcado_descarga(self.copia(), 'Press Banca'),
        ]

    def test_valores_esperados(self):
        self.assertEqual(self.lecturas(), [
            (75.0, 8), (50.0, 12), (33.0, 7),
            {'tipo': 'tiempo', 'segundos': 75},
            {'tipo': 'distancia', 'metros_por_serie': 35.0, 'carga_total_kg': 24.0},
            None, None,
            (8, 10), (10, 12), None,
            True, False,
        ])

    def test_dentro_de_una_peticion_da_lo_mismo(self):
        fuera = self.lecturas()
        dentro = []
        self.en_peticion(lambda r: dentro.extend(self.lecturas()))
        self.assertEqual(dentro, fuera)

    def test_series_y_version_una_vez_por_peticion(self):
        def vista(request):
            copias = [self.copia() for _ in range(6)]       # las copias se leen fuera del recuento
            with CaptureQueriesContext(connection) as ctx:
                for e in copias:
                    _rendimiento_representativo(e, 'Press Banca', 1, 1)
                    _metricas_comparables_por_unidad(e, 'Plancha', 'progresion_tiempo')
                    rango_de_sesion(e, 'Press Banca')
                    ejercicio_marcado_descarga(e, 'Remo')
            self.consultas = [q['sql'][:90] for q in ctx.captured_queries]
        self.en_peticion(vista)
        # Series del entreno (1), series de trabajo de ultima_sesion_service, que
        # tiene su propia lectura por entreno (1), y su versión (1). Antes: 19.
        self.assertLessEqual(len(self.consultas), 3, '\n'.join(self.consultas))

    def test_un_cambio_en_la_peticion_se_ve_despues(self):
        def vista(request):
            self.antes = (rango_de_sesion(self.copia(), 'Press Banca'),
                          _rendimiento_representativo(self.copia(), 'Press Banca', 1, 1))
            v = GymDecisionVersion.objects.get(pk=self.version.pk)
            v.snapshot['entrenamiento']['ejercicios'][0]['repeticiones'] = '4-6'
            v.save()
            SerieRealizada.objects.filter(entreno=self.entreno, peso_kg=75).update(peso_kg=77.5)
            self.despues = (rango_de_sesion(self.copia(), 'Press Banca'),
                            _rendimiento_representativo(self.copia(), 'Press Banca', 1, 1))
        self.en_peticion(vista)
        self.assertEqual(self.antes, ((8, 10), (75.0, 8)))
        # con rango 4-6, la referencia es la más pesada que llega a 4: 77,5 × 8
        self.assertEqual(self.despues, ((4, 6), (77.5, 8)))

    def test_un_entreno_sin_version_o_que_no_es_un_modelo_no_rompe(self):
        def vista(request):
            sin_version = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=self.entreno.rutina, fecha=HOY)
            self.r1 = rango_de_sesion(sin_version, 'Press Banca')
            falso = SimpleNamespace(gym_decision_version=SimpleNamespace(snapshot={'entrenamiento': {
                'ejercicios': [{'nombre': 'Press Banca', 'repeticiones': '6-8', 'deload': True}]}}))
            self.r2 = (rango_de_sesion(falso, 'Press Banca'), ejercicio_marcado_descarga(falso, 'Press Banca'))
        self.en_peticion(vista)
        self.assertIsNone(self.r1)
        self.assertEqual(self.r2, ((6, 8), True))
