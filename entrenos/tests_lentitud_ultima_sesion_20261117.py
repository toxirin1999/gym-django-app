"""17-nov-2026 · Lentitud: `ultima_sesion` y `series_de_trabajo` sin una consulta por ejercicio.

En producción, primera carga: series_de_trabajo x23 en Ahora y x31 en el
cierre; ultima_sesion x16 / x23; rango_de_sesion x25 y
ejercicio_marcado_descarga x18-39 (cada uno leía la versión del plan de la
sesión). Dentro de una petición ahora se leen en bloque: los ejercicios del
cliente una vez, cada entreno candidato una vez (con su versión) y las series
de cada entreno una vez. Fuera de una petición (comandos, tareas) se usa la
consulta de siempre, así que comparar los dos caminos prueba que eligen la
misma sesión y las mismas series.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import Cliente
from core import memo_peticion
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionVersion, SerieRealizada
from entrenos.services.ultima_sesion_service import series_de_trabajo, ultima_sesion
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 11, 17)


def resumen(lectura):
    """Lo que importa de una lectura, sin objetos de modelo."""
    if lectura is None:
        return None
    ref = lectura['referencia']
    return {
        'entreno': lectura['entreno'].pk,
        'fecha': lectura['fecha'],
        'series': lectura['series'],
        'peso': ref['peso'], 'reps': ref['reps'], 'rpe': ref['rpe'], 'en_rango': ref['en_rango'],
        'es_tope_maquina': lectura['es_tope_maquina'],
        'descarga': lectura.get('descarga', False),
        'tras_descarga': lectura.get('tras_descarga'),
        # la versión del plan de la sesión elegida tiene que venir con ella
        'version': lectura['entreno'].gym_decision_version_id,
    }


class UltimaSesionEnBloque(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='ultima-lenta', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'U'})
        otro = User.objects.create_user(username='ultima-otro', password='x')
        self.otro, _ = Cliente.objects.get_or_create(user=otro, defaults={'nombre': 'O'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        self.banca = self.base('Press Banca')
        self.jalon = self.base('Jalón al pecho')
        self.curl = self.base('Curl Martillo')
        self.version_n = 0

        # Press banca: normal hace 12 días, normal hace 5, DESCARGA hace 2 (marcada en el plan)
        e = self.entreno(12, rango='8-10')
        self.ej(e, 'Press Banca', self.banca, [(70, 10, 8), (70, 9, 9)])
        e = self.entreno(5, rango='8-10')
        self.ej(e, 'Press Banca', self.banca, [(72.5, 9, 8), (72.5, 8, 9)])
        e = self.entreno(2, rango='8-10', deload=['Press Banca'])
        self.ej(e, 'press banca', self.banca, [(60, 10, 6)])

        # Jalón: dos sesiones el mismo día (gana la de id mayor), la de antes con tildes distintas
        e = self.entreno(4, rango='10-12')
        self.ej(e, 'Jalon al pecho', self.jalon, [(50, 12, 8)])
        e = self.entreno(4, rango='10-12')
        self.ej(e, 'Jalón al pecho', self.jalon, [(52.5, 11, 9)], tope=True)

        # Curl: la última sin series registradas (se salta), la anterior sí
        e = self.entreno(9, rango='12-15')
        self.ej(e, 'Curl Martillo', self.curl, [(16, 14, 8), (16, 12, 9)])
        e = self.entreno(1, rango='12-15')
        self.ej(e, 'Curl Martillo', self.curl, [])
        # una aproximación y una serie no completada no cuentan
        SerieRealizada.objects.create(entreno=e, ejercicio=self.curl, serie_numero=1, repeticiones=10,
                                      peso_kg=8, completado=True, es_aproximacion=True)
        SerieRealizada.objects.create(entreno=e, ejercicio=self.curl, serie_numero=2, repeticiones=10,
                                      peso_kg=18, completado=False)

        # otro cliente con banca más reciente: no cuenta
        e = EntrenoRealizado.objects.create(cliente=self.otro, rutina=self.rutina, fecha=HOY - timedelta(days=1))
        self.ej(e, 'Press Banca', self.banca, [(150, 3, 10)])

    # ── datos ──────────────────────────────────────────────
    def base(self, nombre):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='otros', tipo_progresion='peso_reps')

    def entreno(self, dias_atras, rango, deload=()):
        fecha = HOY - timedelta(days=dias_atras)
        self.version_n += 1
        version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=fecha, version=self.version_n, decision_id=f'd{self.version_n}',
            origen='sistema', fingerprint='f', base_fingerprint='b', postura='empujar',
            snapshot={'entrenamiento': {'ejercicios': [
                {'nombre': n, 'repeticiones': rango, 'deload': n in deload}
                for n in ('Press Banca', 'Jalón al pecho', 'Curl Martillo')
            ]}},
        )
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha, gym_decision_version=version,
        )

    def ej(self, entreno, nombre, base, series, tope=False):
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=nombre, peso_kg=series[0][0] if series else 0,
            repeticiones=series[0][1] if series else 1, completado=True, es_tope_maquina=tope,
        )
        for i, (peso, reps, rpe) in enumerate(series, start=1):
            SerieRealizada.objects.create(entreno=entreno, ejercicio=base, serie_numero=i, repeticiones=reps,
                                          peso_kg=peso, rpe_real=rpe, completado=True)

    def en_peticion(self, vista):
        """Pasa ``vista`` por el middleware real (memoria por petición + escrituras que la vacían)."""
        PeticionesLentasMiddleware(lambda r: vista(r) or type('R', (), {'status_code': 200})())(
            RequestFactory().get('/x/'))
        self.assertIsNone(memo_peticion._memo.get())

    CASOS = [
        ('Press Banca', HOY, None, False),
        ('Press Banca', HOY, 8, False),
        ('Press Banca', HOY, None, True),                     # incluir_descarga: la de hace 2 días
        ('Press Banca', HOY - timedelta(days=5), None, False),  # antes de: solo la de hace 12
        ('PRESS BANCA', HOY, None, False),
        ('Jalón al pecho', HOY, None, False),
        ('Jalón al pecho', HOY, 10, False),   # «Jalon» sin tilde no se compara: SQLite distingue tildes y MySQL no
        ('Curl Martillo', HOY, None, False),
        ('Curl Martillo', HOY - timedelta(days=9), None, False),  # nada antes
        ('Remo', HOY, None, False),
    ]

    def lecturas(self):
        return [resumen(ultima_sesion(self.cliente, n, f, reps_min=r, incluir_descarga=d))
                for n, f, r, d in self.CASOS]

    # ── pruebas ────────────────────────────────────────────
    def test_dentro_de_una_peticion_elige_lo_mismo_que_la_consulta_de_siempre(self):
        fuera = self.lecturas()           # sin petición: camino de siempre
        dentro = []
        self.en_peticion(lambda r: dentro.extend(self.lecturas()))
        for caso, a, b in zip(self.CASOS, fuera, dentro):
            with self.subTest(caso=caso):
                self.assertEqual(b, a)

    def test_valores_esperados(self):
        def vista(request):
            banca = resumen(ultima_sesion(self.cliente, 'Press Banca', HOY))
            # salta la descarga de hace 2 días y lo dice
            self.assertEqual((banca['fecha'], banca['peso'], banca['tras_descarga']),
                             (HOY - timedelta(days=5), 72.5, HOY - timedelta(days=2)))
            jalon = resumen(ultima_sesion(self.cliente, 'JALÓN AL PECHO', HOY))
            self.assertEqual((jalon['peso'], jalon['es_tope_maquina']), (52.5, True))
            curl = resumen(ultima_sesion(self.cliente, 'Curl Martillo', HOY))
            self.assertEqual((curl['fecha'], curl['peso']), (HOY - timedelta(days=9), 16.0))
            self.assertEqual([s['peso'] for s in curl['series']], [16.0, 16.0])
            solo_descarga = resumen(ultima_sesion(self.cliente, 'Press Banca', HOY, incluir_descarga=True))
            self.assertEqual(solo_descarga['peso'], 60.0)
        self.en_peticion(vista)

    def test_series_de_trabajo_iguales_dentro_y_fuera(self):
        entrenos = list(EntrenoRealizado.objects.filter(cliente=self.cliente))
        nombres = ['Press Banca', 'press banca', 'Jalón al pecho', 'Curl Martillo', 'Remo']
        fuera = [series_de_trabajo(e, n) for e in entrenos for n in nombres]
        dentro = []
        self.en_peticion(lambda r: dentro.extend(series_de_trabajo(e, n) for e in entrenos for n in nombres))
        self.assertEqual(dentro, fuera)

    def test_en_una_peticion_las_consultas_no_crecen_con_los_ejercicios(self):
        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                for _ in range(3):
                    self.lecturas()
            self.consultas = [q['sql'][:90] for q in ctx.captured_queries]
        self.en_peticion(vista)
        # 1 ejercicios del cliente + 1 periodos de descarga + series de 7 entrenos (7)
        # + entrenos candidatos leídos en bloque, no uno a uno (3). Antes eran 28.
        self.assertLessEqual(len(self.consultas), 12, '\n'.join(self.consultas))
        lecturas_de_entrenos = [c for c in self.consultas if c.startswith('SELECT "entrenos_entrenorealizado"')]
        self.assertLessEqual(len(lecturas_de_entrenos), 3, '\n'.join(self.consultas))

    def test_un_entreno_guardado_en_la_misma_peticion_se_ve_despues(self):
        def vista(request):
            self.antes = resumen(ultima_sesion(self.cliente, 'Press Banca', HOY + timedelta(days=1)))
            e = self.entreno(0, rango='8-10')
            self.ej(e, 'Press Banca', self.banca, [(75, 8, 9)])
            self.despues = resumen(ultima_sesion(self.cliente, 'Press Banca', HOY + timedelta(days=1)))
        self.en_peticion(vista)
        self.assertEqual(self.antes['peso'], 72.5)
        self.assertEqual((self.despues['fecha'], self.despues['peso']), (HOY, 75.0))
