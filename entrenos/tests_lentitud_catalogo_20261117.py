"""17-nov-2026 · Lentitud: catálogo de ejercicios y topes de máquina por nombre.

Producción (20:37, cierre 407, 187 consultas; 20:20, Ahora, 397):
``rutinas_ejerciciobase`` x36 en el cierre y x50 en Ahora, y ``tope_de`` x8 en
los dos. Varias funciones buscaban la misma fila del catálogo por separado
(``salto_carga``, ``_nombre_visible``, ``peso_sugerido``, ``_grupo_ejercicio``,
``ajustar_escala_y_reps``…), todas con ``nombre__iexact`` y ``.first()``: como
el modelo no define orden, ``.first()`` es la fila de id menor. Ahora comparten
una búsqueda por nombre (sin mayúsculas en la clave, mismo ``iexact`` en la base
de datos) y los topes del cliente se leen una vez por petición. Misma fila
elegida, mismos valores por defecto; un tope cambiado en la petición se ve en la
lectura siguiente.
"""

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import GymDecisionLog, TopeMaquinaGym
from entrenos.services.catalogo_service import base_por_nombre
from entrenos.services.cierre_entrenamiento_service import _nombre_visible
from entrenos.services.criterios_entrenador_service import _grupo_ejercicio
from entrenos.services.maquina_service import salto_carga, tope_de
from rutinas.models import EjercicioBase


class CatalogoYTopesEnBloque(TestCase):
    def setUp(self):
        u1 = User.objects.create_user(username='catalogo-1', password='x')
        u2 = User.objects.create_user(username='catalogo-2', password='x')
        self.c1, _ = Cliente.objects.get_or_create(user=u1, defaults={'nombre': 'A'})
        self.c2, _ = Cliente.objects.get_or_create(user=u2, defaults={'nombre': 'B'})
        self.prensa = EjercicioBase.objects.create(nombre='Prensa Inclinada', grupo_muscular='Piernas',
                                                   equipo='maquina', tipo_progresion='peso_reps')
        self.curl = EjercicioBase.objects.create(nombre='Curl Araña', grupo_muscular='Bíceps', equipo='',
                                                 tipo_progresion='peso_reps', incremento_kg=1.25)
        # Duplicado que solo cambia en mayúsculas (posible en SQLite; en MySQL la
        # colación lo impide): manda el de id menor, como hacía `.first()`.
        self.remo = EjercicioBase.objects.create(nombre='Remo Bajo', grupo_muscular='Espalda',
                                                 equipo='maquina', tipo_progresion='peso_reps')
        self.remo_dup = EjercicioBase.objects.create(nombre='REMO BAJO', grupo_muscular='Hombro',
                                                     equipo='mancuerna_una', tipo_progresion='peso_reps')
        TopeMaquinaGym.objects.create(cliente=self.c1, ejercicio_normalizado='prensa inclinada',
                                      ejercicio='Prensa Inclinada', peso_max_kg=180)
        TopeMaquinaGym.objects.create(cliente=self.c2, ejercicio_normalizado='prensa inclinada',
                                      ejercicio='Prensa Inclinada', peso_max_kg=120)
        TopeMaquinaGym.objects.create(cliente=self.c1, ejercicio_normalizado='remo bajo',
                                      ejercicio='Remo Bajo', peso_max_kg=75)

    NOMBRES = ['Prensa Inclinada', 'prensa inclinada', 'PRENSA INCLINADA', '  Prensa Inclinada ',
               'Curl Araña', 'curl araña', 'Remo Bajo', 'REMO BAJO', 'remo bajo', 'Sin Catalogo', '']

    def log(self, nombre):
        return GymDecisionLog(cliente=self.c1, ejercicio=nombre, peso_anterior=100, valor_cambio=5,
                              accion='subir_peso', motivo='m')

    def lecturas(self):
        filas = []
        for n in self.NOMBRES:
            base = base_por_nombre(n)
            filas.append((
                n,
                base.pk if base else None,
                salto_carga(self.c1, n),
                _nombre_visible(n),
                _grupo_ejercicio(n, 'otros'),
                self.log(n).peso_sugerido,
                tope_de(self.c1, n),
                tope_de(self.c2, n),
            ))
        return filas

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))

    def test_misma_fila_que_cada_consulta_original(self):
        for n in self.NOMBRES:
            with self.subTest(nombre=n):
                original = EjercicioBase.objects.filter(nombre__iexact=n or '').first()
                elegida = base_por_nombre(n)
                self.assertEqual(elegida.pk if elegida else None, original.pk if original else None)
        self.assertEqual(base_por_nombre('remo bajo').pk, self.remo.pk)

    def test_dentro_de_una_peticion_da_lo_mismo(self):
        fuera = self.lecturas()
        dentro = []
        self.en_peticion(lambda r: dentro.extend(self.lecturas()))
        self.assertEqual(dentro, fuera)

    def test_valores_esperados(self):
        def vista(request):
            self.assertEqual(tope_de(self.c1, 'prensa inclinada'), 180.0)
            self.assertEqual(tope_de(self.c2, 'Prensa Inclinada'), 120.0)
            self.assertIsNone(tope_de(self.c2, 'Remo Bajo'))
            self.assertIsNone(base_por_nombre('Sin Catalogo'))
            self.assertEqual(_nombre_visible('Sin Catalogo'), 'Sin Catalogo')
            self.assertEqual(_nombre_visible('prensa inclinada'), 'Prensa Inclinada')
            self.assertEqual(_grupo_ejercicio('REMO BAJO', 'otros'), _grupo_ejercicio('Remo Bajo', 'otros'))
        self.en_peticion(vista)

    def test_cada_nombre_y_los_topes_se_leen_una_vez(self):
        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                for _ in range(3):
                    for n in ['Prensa Inclinada', 'prensa inclinada', 'Curl Araña', 'Remo Bajo', 'Sin Catalogo']:
                        base_por_nombre(n)
                        _nombre_visible(n)
                        _grupo_ejercicio(n, 'otros')
                        self.log(n).peso_sugerido
                        tope_de(self.c1, n)
            self.consultas = [q['sql'] for q in ctx.captured_queries]
        self.en_peticion(vista)
        catalogo = [c for c in self.consultas if 'FROM "rutinas_ejerciciobase"' in c]
        topes = [c for c in self.consultas if 'FROM "entrenos_topemaquinagym"' in c]
        # 4 nombres distintos sin mayúsculas (prensa, curl, remo, sin catálogo) → 4; topes del cliente → 1
        self.assertEqual((len(catalogo), len(topes)), (4, 1), '\n'.join(c[:120] for c in self.consultas))

    def test_un_tope_cambiado_en_la_peticion_se_ve_despues(self):
        def vista(request):
            self.antes = tope_de(self.c1, 'Prensa Inclinada')
            TopeMaquinaGym.objects.filter(cliente=self.c1, ejercicio_normalizado='prensa inclinada').update(
                peso_max_kg=200)
            TopeMaquinaGym.objects.create(cliente=self.c1, ejercicio_normalizado='curl araña',
                                          ejercicio='Curl Araña', peso_max_kg=20)
            self.despues = (tope_de(self.c1, 'Prensa Inclinada'), tope_de(self.c1, 'Curl Araña'))
        self.en_peticion(vista)
        self.assertEqual((self.antes, self.despues), (180.0, (200.0, 20.0)))
