"""18-nov-2026 · Lentitud: entradas de ``necesita_deload_gym`` y RPE de series del planificador.

Producción (18-nov 08:17): ``necesita_deload_gym`` x10 en Ahora y en Cuerpo,
``_rpes_series_de_entreno`` x11-12. ``necesita_deload_gym`` no es solo una
consulta: si se cumple un criterio abre un ciclo de descarga
(``abrir_ciclo_deload`` escribe). Por eso no se memoriza la decisión, solo sus
lecturas de entrada (sesiones de dos semanas con RPE y energía); la decisión y
la escritura se siguen haciendo en cada llamada, y una escritura vacía la
memoria. ``obtener_ciclo_activo`` (que cierra ciclos vencidos) no se toca.

El planificador leía los RPE de las series de un entreno con una consulta por
entreno; ahora, la primera vez que falta uno, lee juntos los de los entrenos
más recientes del cliente.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import CicloDeload, EjercicioRealizado, EntrenoRealizado, SerieRealizada
from entrenos.services.briefing_service import necesita_deload_gym
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 11, 18)


def en_peticion(vista):
    PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))


class DecisionDeDescarga(TestCase):
    def cliente(self, nombre):
        user = User.objects.create_user(username=nombre, password='x')
        c, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': nombre})
        return c

    def sesiones(self, cliente, dias_atras, rpe, energia=None):
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia')
        for d in dias_atras:
            e = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=HOY - timedelta(days=d),
                                                energia_pre_sesion=energia)
            for n in ('Press', 'Remo'):
                EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=n, peso_kg=50, repeticiones=8,
                                                  rpe=rpe, completado=True)

    def escenarios(self):
        """(nombre, cliente, hoy) que cubren cada rama de la decisión."""
        insuficiente = self.cliente('insuficiente')
        self.sesiones(insuficiente, [1, 4], rpe=9)                       # < 3 sesiones
        energia = self.cliente('energia')
        self.sesiones(energia, [1, 3, 6], rpe=7, energia=3)              # criterio B → abre descarga
        rpe_alto = self.cliente('rpe-alto')
        self.sesiones(rpe_alto, [1, 3, 5, 8], rpe=9)
        self.sesiones(rpe_alto, [16, 19, 23], rpe=8.5)                   # criterio A → abre descarga
        descartada = self.cliente('descartada')
        self.sesiones(descartada, [1, 3, 5, 8], rpe=9)
        self.sesiones(descartada, [16, 19, 23], rpe=6)                   # previas bajas → no abre
        normal = self.cliente('normal')
        self.sesiones(normal, [1, 3, 5, 8, 10], rpe=7, energia=7)
        activo = self.cliente('ciclo-activo')
        CicloDeload.objects.create(cliente=activo, causa='fatiga_gym', fecha_inicio=HOY - timedelta(days=2),
                                   fecha_fin_prevista=HOY + timedelta(days=4))
        casos = [(n, c, h) for n, c in [('insuficiente', insuficiente), ('energia', energia),
                                        ('rpe_alto', rpe_alto), ('descartada', descartada),
                                        ('normal', normal), ('ciclo_activo', activo)]
                 for h in (HOY, HOY + timedelta(days=7))]                # cambio de semana: la ventana se mueve
        return casos

    def decidir(self, casos):
        return [(n, h, necesita_deload_gym(c, h),
                 CicloDeload.objects.filter(cliente=c, estado=CicloDeload.ESTADO_ACTIVO).count())
                for n, c, h in casos]

    def test_misma_decision_dentro_y_fuera_de_una_peticion(self):
        from django.db import transaction
        casos = self.escenarios()
        with transaction.atomic():                       # la decisión escribe: se deshace para empezar igual
            fuera = self.decidir(casos)
            transaction.set_rollback(True)
        dentro = []
        en_peticion(lambda r: dentro.extend(self.decidir(casos)))
        self.assertEqual(dentro, fuera)
        esperado = {('insuficiente', HOY): False, ('energia', HOY): True, ('rpe_alto', HOY): True,
                    ('descartada', HOY): False, ('normal', HOY): False, ('ciclo_activo', HOY): True}
        self.assertEqual({(n, h): d for n, h, d, _ in fuera if h == HOY}, esperado)

    def test_la_descarga_abierta_se_ve_en_la_llamada_siguiente_y_no_se_abre_dos_veces(self):
        c = self.cliente('dos-veces')
        self.sesiones(c, [1, 3, 6], rpe=7, energia=3)

        def vista(request):
            self.r = [necesita_deload_gym(c, HOY) for _ in range(5)]
        en_peticion(vista)
        self.assertEqual(self.r, [True] * 5)
        self.assertEqual(CicloDeload.objects.filter(cliente=c).count(), 1)

    def test_una_sesion_guardada_en_la_peticion_cambia_la_decision(self):
        c = self.cliente('nueva-sesion')
        self.sesiones(c, [1, 3], rpe=7, energia=3)          # 2 sesiones: datos insuficientes

        def vista(request):
            self.antes = necesita_deload_gym(c, HOY)
            self.sesiones(c, [0], rpe=7, energia=3)        # la tercera: ya hay datos y la energía es baja
            self.despues = necesita_deload_gym(c, HOY)
        en_peticion(vista)
        self.assertEqual((self.antes, self.despues), (False, True))

    def test_diez_llamadas_leen_las_sesiones_una_vez(self):
        c = self.cliente('diez')
        self.sesiones(c, [1, 3, 5, 8], rpe=9)
        self.sesiones(c, [16, 19, 23], rpe=6)

        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                for _ in range(10):
                    necesita_deload_gym(c, HOY)
            sql = [q['sql'] for q in ctx.captured_queries]
            self.entrenos = [s[:80] for s in sql if 'FROM "entrenos_entrenorealizado"' in s]
            self.ejercicios = [s[:80] for s in sql if 'FROM "entrenos_ejerciciorealizado"' in s]
        en_peticion(vista)
        # dos ventanas (2 semanas y las 2 anteriores): 1 lectura de entrenos y 1 de ejercicios por ventana
        self.assertLessEqual(len(self.entrenos), 2, self.entrenos)
        self.assertLessEqual(len(self.ejercicios), 2, self.ejercicios)


class RpesDeSeriesEnBloque(TestCase):
    def test_mismos_rpe_y_una_lectura_para_los_entrenos_recientes(self):
        from analytics.planificador_helms.core import _rpes_series_de_entreno, rpes_series
        user = User.objects.create_user(username='rpes', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'R'})
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia')
        base = EjercicioBase.objects.create(nombre='Press Banca', grupo_muscular='otros', tipo_progresion='peso_reps')
        ids = []
        for k in range(20):
            e = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=HOY - timedelta(days=k))
            EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio='Press Banca', peso_kg=50, repeticiones=8,
                                              completado=True)
            SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=1, repeticiones=8, peso_kg=50,
                                          rpe_real=7 + k % 3, completado=True)
            SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=2, repeticiones=8, peso_kg=50,
                                          rpe_real=None, completado=True)
            SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=3, repeticiones=8, peso_kg=50,
                                          rpe_real=9, completado=False)   # sin completar: también contaba
            ids.append(e.pk)
        fuera = [sorted(_rpes_series_de_entreno(i)) for i in ids]

        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                self.dentro = [sorted(rpes_series(cliente.pk, i)) for i in ids[:12]]
            self.series = [q['sql'][:80] for q in ctx.captured_queries if 'FROM "entrenos_serierealizada"' in q['sql']]
            self.antigua = sorted(rpes_series(cliente.pk, ids[19]))
        en_peticion(vista)
        self.assertEqual(self.dentro, fuera[:12])
        self.assertEqual(self.antigua, fuera[19])          # fuera de los recientes: se sigue leyendo
        self.assertEqual(len(self.series), 1, self.series)
