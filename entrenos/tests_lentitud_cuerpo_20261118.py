"""18-nov-2026 · Lentitud de Cuerpo: bitácora y carga leídas una vez por petición.

Producción (18-nov 07:40, Cuerpo, 359 consultas): ``carga_por_dia`` x35,
``_medias_base`` x33, ``_datos_hoy`` x31 (``clientes_bitacoradiaria`` x70,
``entrenos_actividadrealizada`` x49). Cada día de las gráficas volvía a leer
la bitácora (su mañana y las 4 semanas anteriores para «lo normal en ti») y las
actividades (7 días frente a las 4 semanas anteriores).

Dentro de una petición se lee una vez todo el historial del cliente (bitácora y
actividades con carga): así ningún punto se queda sin los días anteriores al
inicio de la gráfica. Cada función filtra después su rango exacto. Fuera de una
petición, las consultas de siempre. Comparación día por día entre los dos
caminos.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import BitacoraDiaria, Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import ActividadRealizada
from entrenos.services import estado_carga_service as carga
from entrenos.services import panel_cuerpo_service as panel
from entrenos.services import recuperacion_service as recup

HOY = date(2026, 11, 18)
DIAS = 60   # historial de 60 días: la gráfica de 14 necesita hasta 41 días atrás


class CuerpoEnBloque(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='cuerpo-lento', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'C'})
        otro = User.objects.create_user(username='cuerpo-otro', password='x')
        self.otro, _ = Cliente.objects.get_or_create(user=otro, defaults={'nombre': 'O'})
        for i in range(DIAS, -1, -1):
            d = HOY - timedelta(days=i)
            if i % 9 == 4:
                continue                                       # día sin check-in
            if i % 7 == 2:
                self.bitacora(d, sueno=Decimal('7.5'))         # sin reloj: solo sueño a mano
            elif i % 11 == 3:
                self.bitacora(d, fc=55)                        # señal parcial: solo pulso
            elif i % 13 == 5:
                self.bitacora(d, hrv=0, fc=0, sueno=Decimal('0'))   # ceros, no nulos
            else:
                self.bitacora(d, hrv=60 + (i % 5) * 4 - (12 if i in (0, 1, 6) else 0), fc=52 + (i % 3),
                              sueno=Decimal('7.25') - (Decimal('1.5') if i in (0, 6) else 0), energia=6 + i % 3)
            if i == 6:
                self.bitacora(d, hrv=40)                        # segundo check-in del mismo día
            # actividades con carga: fecha real distinta de la del plan, sin carga, duración imposible, ceros
            if i % 2 == 0:
                self.actividad(d, carga=300 + i * 3, fecha_plan=d + timedelta(days=1) if i % 6 == 0 else None)
            if i % 10 == 1:
                self.actividad(d, carga=None)
            if i % 15 == 7:
                self.actividad(d, carga=900, duracion=300)
            if i % 17 == 8:
                self.actividad(d, carga=0)
        self.bitacora(HOY, hrv=99, cliente=self.otro)
        ActividadRealizada.objects.create(cliente=self.otro, tipo='gym', titulo='x', fecha=HOY, carga_ua=999,
                                          duracion_minutos=60)

    def bitacora(self, d, hrv=None, fc=None, sueno=None, energia=None, cliente=None):
        b = BitacoraDiaria.objects.create(cliente=cliente or self.cliente, hrv_ms=hrv, fc_reposo=fc,
                                          horas_sueno=sueno, energia_subjetiva=energia)
        BitacoraDiaria.objects.filter(pk=b.pk).update(fecha=d)   # fecha es auto_now_add

    def actividad(self, d, carga, duracion=60, fecha_plan=None):
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='gym', titulo='s', fecha=fecha_plan or d,
                                          fecha_realizado=d if fecha_plan else None, carga_ua=carga,
                                          duracion_minutos=duracion)

    def por_dia(self):
        """Todo lo que Cuerpo calcula por fecha, para cada uno de los últimos 45 días."""
        filas = []
        for i in range(45):
            d = HOY - timedelta(days=i)
            filas.append((
                d,
                recup._datos_hoy(self.cliente, d),
                recup._medias_base(self.cliente, d),
                recup.lectura_recuperacion(self.cliente, d),
                carga.carga_por_dia(self.cliente, d - timedelta(days=34), d),
                carga.lectura_carga(self.cliente, d),
            ))
        return filas

    def pantalla(self):
        return {
            'cuerpo': carga.lectura_cuerpo(self.cliente, HOY),
            'camino': panel.camino(self.cliente, HOY),
            'variabilidad': panel.variabilidad(self.cliente, HOY),
            'pulso': panel.pulso(self.cliente, HOY),
            'sueno': panel.sueno(self.cliente, HOY),
            'medidor': panel.medidor_carga(self.cliente, HOY),
            'media_hrv': recup.media_variabilidad(self.cliente, HOY),
        }

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))

    def test_el_escenario_cubre_los_casos(self):
        filas = self.por_dia()
        niveles = {f[3]['nivel'] if f[3] else None for f in filas}
        self.assertTrue({None, 'verde'} <= niveles and niveles & {'ambar', 'rojo'}, niveles)
        self.assertTrue(any(f[2] for f in filas[:14]))                     # hay «lo normal en ti»
        self.assertTrue(any(f[1] == {'fc_reposo': 55.0} for f in filas))   # señal parcial
        self.assertTrue(any(f[1].get('hrv_ms') == 0.0 for f in filas))     # cero, no nulo

    def test_dia_por_dia_igual_dentro_y_fuera_de_una_peticion(self):
        fuera = self.por_dia()
        dentro = []
        self.en_peticion(lambda r: dentro.extend(self.por_dia()))
        for a, b in zip(fuera, dentro):
            with self.subTest(fecha=a[0]):
                self.assertEqual(b, a)

    def test_la_pantalla_sale_igual(self):
        fuera = self.pantalla()
        dentro = {}
        self.en_peticion(lambda r: dentro.update(self.pantalla()))
        for clave in fuera:
            with self.subTest(clave=clave):
                self.assertEqual(dentro[clave], fuera[clave])

    def test_una_lectura_de_bitacora_y_otra_de_carga(self):
        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                self.por_dia()
                self.pantalla()
            sql = [q['sql'] for q in ctx.captured_queries]
            self.bit = [s[:90] for s in sql if 'FROM "clientes_bitacoradiaria"' in s]
            self.act = [s[:90] for s in sql if 'FROM "entrenos_actividadrealizada"' in s and '"carga_ua"' in s]
        self.en_peticion(vista)
        self.assertEqual(len(self.bit), 1, '\n'.join(self.bit))
        self.assertLessEqual(len(self.act), 2, '\n'.join(self.act))   # carga + (camino) sesiones del día

    def test_lo_guardado_en_la_peticion_se_ve_despues(self):
        def vista(request):
            self.antes = (recup._datos_hoy(self.cliente, HOY), carga.lectura_carga(self.cliente, HOY))
            self.bitacora(HOY, hrv=30)
            self.actividad(HOY, carga=1000)
            self.despues = (recup._datos_hoy(self.cliente, HOY), carga.lectura_carga(self.cliente, HOY))
        self.en_peticion(vista)
        self.assertEqual(self.despues[0]['hrv_ms'], 30.0)
        self.assertEqual(self.despues[1]['semana'], self.antes[1]['semana'] + 1000)
