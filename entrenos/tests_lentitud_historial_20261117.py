"""17-nov-2026 · Lentitud: historial del planificador sin una consulta por ejercicio.

`_obtener_historial_ejercicio` (camino sin precarga) hacía dos consultas por
ejercicio: el último ejercicio con ese nombre y sus series con RPE. En
producción eran 272 de 842 consultas en Ahora, 374 de 589 en Cuerpo y 166 de
530 en el cierre. Ahora lee el historial una vez y las series una vez por
entreno, con el mismo resultado que antes.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from clientes.models import Cliente
from core import memo_peticion
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 11, 17)


def _como_antes(cliente_id, nombre_ejercicio):
    """Las dos consultas del camino antiguo, tal cual."""
    resultado = {'peso_real': None, 'rpe_real': None, 'reps_real': None, 'peso_real_bruto': None}
    nombre_lower = nombre_ejercicio.lower()
    ej = EjercicioRealizado.objects.filter(
        nombre_ejercicio__icontains=nombre_lower, entreno__cliente_id=cliente_id,
    ).order_by('-entreno__fecha', '-id').first()
    if ej and ej.peso_kg:
        resultado['peso_real'] = float(ej.peso_kg)
        resultado['peso_real_bruto'] = resultado['peso_real']
    if ej and ej.repeticiones is not None:
        resultado['reps_real'] = int(ej.repeticiones)
    if ej:
        rpes = [float(s.rpe_real) for s in SerieRealizada.objects.filter(
            entreno=ej.entreno, ejercicio__nombre__icontains=nombre_lower, rpe_real__isnull=False,
        )]
        if rpes:
            resultado['rpe_real'] = sum(rpes) / len(rpes)
        elif ej.rpe is not None:
            resultado['rpe_real'] = float(ej.rpe)
    return resultado


class HistorialSinConsultaPorEjercicio(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='historial-lento', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'H'})
        otro = User.objects.create_user(username='historial-otro', password='x')
        self.otro, _ = Cliente.objects.get_or_create(user=otro, defaults={'nombre': 'O'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        self.banca = self.base('Press Banca')
        self.sentadilla = self.base('Sentadilla Hack')
        self.curl = self.base('Curl Martillo')

        viejo = self.entreno(self.cliente, 10)
        self.ejercicio(viejo, 'Press Banca', 70, 10, 8)
        self.series(viejo, self.banca, [7, 8])

        reciente = self.entreno(self.cliente, 3)
        self.ejercicio(reciente, 'Press Banca', 75, 8, 9)
        self.series(reciente, self.banca, [8, 9, None])
        self.ejercicio(reciente, 'Sentadilla Hack', 120, 10, 7)   # sin series con RPE: usa el del ejercicio
        self.ejercicio(reciente, 'Curl Martillo', 0, 12, None)    # sin peso ni RPE

        # mismo día, id mayor: gana este
        mismo_dia = self.entreno(self.cliente, 3)
        self.ejercicio(mismo_dia, 'Sentadilla Hack', 125, 9, 8)
        self.series(mismo_dia, self.sentadilla, [9])

        # de otro cliente: no cuenta
        ajeno = self.entreno(self.otro, 1)
        self.ejercicio(ajeno, 'Press Banca', 200, 1, 10)
        self.series(ajeno, self.banca, [10])

    def base(self, nombre):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='otros', tipo_progresion='peso_reps')

    def entreno(self, cliente, dias_atras):
        return EntrenoRealizado.objects.create(cliente=cliente, rutina=self.rutina, fecha=HOY - timedelta(days=dias_atras))

    def ejercicio(self, entreno, nombre, peso, reps, rpe):
        return EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=nombre, peso_kg=peso, repeticiones=reps, rpe=rpe,
        )

    def series(self, entreno, base, rpes):
        for i, rpe in enumerate(rpes, start=1):
            SerieRealizada.objects.create(
                entreno=entreno, ejercicio=base, serie_numero=i, repeticiones=8, peso_kg=70,
                rpe_real=rpe, completado=True,
            )

    def planificador(self):
        return PlanificadorHelms(PerfilCliente({
            'id': self.cliente.id, 'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia', 'dias_disponibles': 4,
        }))

    NOMBRES = ['Press Banca', 'press banca', 'PRESS', 'Sentadilla Hack', 'Curl Martillo', 'Remo', 'banca', 'hack']

    def test_mismo_resultado_que_las_consultas_antiguas(self):
        p = self.planificador()
        for nombre in self.NOMBRES:
            with self.subTest(nombre=nombre):
                self.assertEqual(p._obtener_historial_ejercicio(nombre), _como_antes(self.cliente.id, nombre))

    def test_valores_concretos(self):
        p = self.planificador()
        self.assertEqual(p._obtener_historial_ejercicio('press banca'),
                         {'peso_real': 75.0, 'rpe_real': 8.5, 'reps_real': 8, 'peso_real_bruto': 75.0})
        self.assertEqual(p._obtener_historial_ejercicio('Sentadilla Hack'),
                         {'peso_real': 125.0, 'rpe_real': 9.0, 'reps_real': 9, 'peso_real_bruto': 125.0})
        self.assertEqual(p._obtener_historial_ejercicio('Curl Martillo'),
                         {'peso_real': None, 'rpe_real': None, 'reps_real': 12, 'peso_real_bruto': None})

    def test_tildes_y_mayusculas_como_mysql(self):
        """MySQL compara sin tildes ni mayúsculas: «Jalón» encuentra «Jalon» y al revés."""
        jalon = self.base('Jalon al pecho')
        e = self.entreno(self.cliente, 1)
        self.ejercicio(e, 'Jalon al pecho', 55, 10, 8)
        self.series(e, jalon, [7])
        p = self.planificador()
        self.assertEqual(p._obtener_historial_ejercicio('JALÓN AL PECHO'),
                         {'peso_real': 55.0, 'rpe_real': 7.0, 'reps_real': 10, 'peso_real_bruto': 55.0})

    def en_peticion(self, vista):
        """Pasa ``vista`` por el middleware real (memoria por petición + escrituras que la vacían)."""
        peticion = RequestFactory().get('/x/')
        PeticionesLentasMiddleware(lambda r: vista(r) or type('R', (), {'status_code': 200})())(peticion)
        self.assertIsNone(memo_peticion._memo.get())

    def test_en_una_peticion_las_consultas_no_crecen_con_los_ejercicios(self):
        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                for _ in range(3):
                    p = self.planificador()          # Ahora crea varios planificadores
                    for nombre in self.NOMBRES:
                        p._obtener_historial_ejercicio(nombre)
            self.consultas = [q['sql'][:80] for q in ctx.captured_queries]
        self.en_peticion(vista)
        # 1 historial + series de 2 entrenos (los que tienen el último de cada ejercicio)
        self.assertLessEqual(len(self.consultas), 3, self.consultas)

    def test_fuera_de_una_peticion_un_planificador_lee_una_vez(self):
        p = self.planificador()
        with CaptureQueriesContext(connection) as ctx:
            for nombre in self.NOMBRES * 2:
                p._obtener_historial_ejercicio(nombre)
        self.assertLessEqual(len(ctx.captured_queries), 3)

    def test_una_escritura_en_la_peticion_se_ve_en_la_lectura_siguiente(self):
        def vista(request):
            self.antes = self.planificador()._obtener_historial_ejercicio('Press Banca')['peso_real']
            nuevo = self.entreno(self.cliente, 0)
            self.ejercicio(nuevo, 'Press Banca', 80, 6, 9)
            self.despues = self.planificador()._obtener_historial_ejercicio('Press Banca')['peso_real']
        self.en_peticion(vista)
        self.assertEqual((self.antes, self.despues), (75.0, 80.0))
