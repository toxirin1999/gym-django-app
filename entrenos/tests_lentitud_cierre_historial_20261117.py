"""17-nov-2026 · Lentitud: búsquedas de historial por ejercicio en el cierre.

Producción (20:02, cierre 407, commit 5ff106b): ``entrenos_ejerciciorealizado``
x56 de 218 consultas. Reproducido en local (48): cinco consultas por ejercicio.
- ``evidencia_de_ejercicio`` y ``_decisiones_entrenador`` releían los
  ejercicios de la sesión de hoy por cada decisión;
- ``_sesion_anterior``, ``_cambios_relevantes`` y ``proxima_vez_texto``
  buscaban por separado el historial del mismo ejercicio, con filtros de fecha
  y desempates distintos.
Ahora, dentro de una petición, los ejercicios de hoy se leen una vez y el
historial de cada ejercicio una vez (mismo filtro en la base de datos); cada
función aplica después su filtro de fechas y su desempate. El cierre completo
tiene que salir igual dentro y fuera de una petición.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog, GymDecisionVersion, SerieRealizada
from entrenos.services.cierre_entrenamiento_service import construir_contexto_cierre
from rutinas.models import EjercicioBase, Rutina

NOMBRES = ['Press Banca', 'Remo', 'Sentadilla Hack', 'Curl Martillo', 'Extension Triceps', 'Jalon al pecho',
           'Prensa', 'Gemelos']
HOY = date(2026, 11, 17)


class HistorialDelCierreEnBloque(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='cierre-historial', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'H'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        self.bases = {n: EjercicioBase.objects.create(nombre=n, grupo_muscular='otros', tipo_progresion='peso_reps')
                      for n in NOMBRES}
        self.n_version = 0
        # 10 semanas de historial; la de hace 2 semanas, descarga en press banca
        for k in range(10, 0, -1):
            self.sesion(HOY - timedelta(days=7 * k), extra=k, deload=('Press Banca',) if k == 2 else ())
        # dos sesiones el mismo día hace 3 días (desempate por id)
        self.sesion(HOY - timedelta(days=3), extra=11, nombres=['Remo', 'Curl Martillo'])
        self.sesion(HOY - timedelta(days=3), extra=12, nombres=['Remo', 'Curl Martillo'])
        self.hoy = self.sesion(HOY, extra=13)
        # una sesión posterior de gemelos: este cierre ya es historia para ese ejercicio
        self.sesion(HOY + timedelta(days=2), extra=14, nombres=['Gemelos'])
        for j, n in enumerate(NOMBRES):
            GymDecisionLog.objects.create(
                cliente=self.cliente, ejercicio=n.lower() if n == 'Press Banca' else n,
                ejercicio_normalizado=n.casefold(), entreno_origen=self.hoy,
                peso_anterior=50 + j * 5, reps_anteriores=10, rpe_anterior=7,
                accion='mantener' if j % 3 == 0 else 'subir_peso', valor_cambio=5, motivo='m',
            )

    def sesion(self, fecha, extra, nombres=NOMBRES, deload=()):
        self.n_version += 1
        v = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=fecha, version=self.n_version, decision_id=f'd{self.n_version}',
            origen='sistema', fingerprint='f', base_fingerprint='b', postura='empujar',
            snapshot={'entrenamiento': {'ejercicios': [
                {'nombre': n, 'repeticiones': '8-10', 'deload': n in deload} for n in NOMBRES]}},
        )
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha, gym_decision_version=v)
        for j, n in enumerate(nombres):
            peso = 40 + j * 5 + extra
            EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=n, peso_kg=peso, repeticiones=9, rpe=8,
                                              completado=True)
            for s in range(3):
                SerieRealizada.objects.create(entreno=e, ejercicio=self.bases[n], serie_numero=s + 1,
                                              repeticiones=10 - s, peso_kg=peso, rpe_real=8, completado=True)
        return e

    def contexto(self):
        return construir_contexto_cierre(self.cliente, EntrenoRealizado.objects.get(pk=self.hoy.pk))

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))

    CLAVES = ['comprobaciones', 'que_viene', 'resumen', 'no_hechos', 'cambios_relevantes', 'lectura_plan',
              'decisiones_entrenador', 'proxima_vez', 'prs', 'resumen_records']

    def test_el_cierre_sale_igual_dentro_y_fuera_de_una_peticion(self):
        fuera = self.contexto()
        dentro = {}
        self.en_peticion(lambda r: dentro.update(self.contexto()))
        for clave in self.CLAVES:
            with self.subTest(clave=clave):
                self.assertEqual(dentro.get(clave), fuera.get(clave))
        # el escenario tiene que producir decisiones y cambios, si no la comparación no prueba nada
        self.assertTrue(fuera['decisiones_entrenador'])
        self.assertTrue(fuera['cambios_relevantes'])

    def test_busquedas_de_historial_una_por_ejercicio_como_mucho(self):
        def vista(request):
            entreno = EntrenoRealizado.objects.get(pk=self.hoy.pk)
            with CaptureQueriesContext(connection) as ctx:
                construir_contexto_cierre(self.cliente, entreno)
            self.consultas = [q['sql'] for q in ctx.captured_queries
                              if 'FROM "entrenos_ejerciciorealizado"' in q['sql']]
        self.en_peticion(vista)
        # 16 = 9 búsquedas de historial (8 ejercicios + «press banca» en minúscula
        # en una decisión, otra clave) + 6 lecturas sueltas de los ejercicios de
        # hoy con filtros distintos + 1 lectura en bloque de ultima_sesion. Antes: 46.
        self.assertLessEqual(len(self.consultas), 16, '\n'.join(c[:120] for c in self.consultas))


class DesempateDentroDeUnaSesion(TestCase):
    """Dos registros del mismo ejercicio en una misma sesión anterior (nota 18: curl femoral repetido
    como alternativa al rumano).

    Antes no estaba definido: el porqué de la decisión (``_sesion_anterior``)
    cogía la primera fila y la sección de cambios (``_cambios_relevantes``) la
    última. Decisión de David (17-nov-2026): en todo el cierre, la primera fila
    registrada (suele ser el ejercicio principal), dentro y fuera de una petición.
    """

    def setUp(self):
        user = User.objects.create_user(username='desempate', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'D'})
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        antes = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=HOY - timedelta(days=7))
        self.primera = EjercicioRealizado.objects.create(entreno=antes, nombre_ejercicio='Curl Femoral', peso_kg=40,
                                                         repeticiones=12, completado=True)
        self.segunda = EjercicioRealizado.objects.create(entreno=antes, nombre_ejercicio='Curl Femoral', peso_kg=55,
                                                         repeticiones=8, completado=True)
        self.hoy = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=HOY)

    def elegidas(self):
        from entrenos.services.cierre_porque_service import _sesion_anterior
        from entrenos.services.historial_ejercicio_service import anteriores
        return (
            _sesion_anterior(self.cliente, self.hoy, 'Curl Femoral').pk,
            [e.pk for e in anteriores(self.cliente, self.hoy, 'Curl Femoral')],
        )

    def test_gana_la_primera_registrada_dentro_y_fuera_de_una_peticion(self):
        esperado = (self.primera.pk, [self.primera.pk, self.segunda.pk])
        self.assertEqual(self.elegidas(), esperado)
        dentro = []
        PeticionesLentasMiddleware(lambda r: dentro.append(self.elegidas()) or HttpResponse('ok'))(
            RequestFactory().get('/x/'))
        self.assertEqual(dentro[0], esperado)


class ClaveSinMayusculas(TestCase):
    def test_dos_grafias_que_solo_cambian_en_mayusculas_comparten_lectura(self):
        from entrenos.services.historial_ejercicio_service import anteriores, hay_posterior
        user = User.objects.create_user(username='clave', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'K'})
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        antes = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=HOY - timedelta(days=7))
        EjercicioRealizado.objects.create(entreno=antes, nombre_ejercicio='Press Banca', peso_kg=70, repeticiones=8,
                                          completado=True)
        hoy = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=HOY)

        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                self.a = [e.peso_kg for e in anteriores(cliente, hoy, 'Press Banca')]
                self.b = [e.peso_kg for e in anteriores(cliente, hoy, 'press banca')]
                self.c = hay_posterior(cliente, 'PRESS BANCA', HOY)
            self.n = len(ctx.captured_queries)
            return HttpResponse('ok')

        PeticionesLentasMiddleware(vista)(RequestFactory().get('/x/'))
        self.assertEqual((self.a, self.b, self.c), ([70.0], [70.0], False))
        self.assertEqual(self.n, 1)
