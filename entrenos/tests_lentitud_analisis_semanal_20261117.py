"""17-nov-2026 · Lentitud: análisis de distribución semanal de Ahora.

En producción (19:28) el tramo ``analisis_semanal`` hacía 74 consultas en una
carga de Ahora: se ejecuta dos veces (``distribucion_semanal`` y
``sugerencia_distribucion``), leía la rutina de cada entreno por separado
(x54) y contaba los entrenos semana a semana (x12). Mismas observaciones y la
misma sugerencia creada; menos consultas.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from clientes.models import Cliente
from core.lentitud_middleware import PeticionesLentasMiddleware
from entrenos.models import ActividadRealizada, EntrenoRealizado, SesionProgramada, SugerenciaPlan
from entrenos.services.analisis_semanal_service import (
    analizar_distribucion_semanal,
    get_sugerencia_distribucion_activa,
)
from rutinas.models import Rutina

REF = date(2026, 11, 18)   # miércoles; ventana de 6 semanas desde el 7-oct


class AnalisisSemanalEnBloque(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='semanal-lento', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'S'})
        Cliente.objects.filter(pk=self.cliente.pk).update(dias_disponibles=5)
        self.cliente.refresh_from_db()
        torso, _ = Rutina.objects.get_or_create(nombre='Torso A')
        pierna, _ = Rutina.objects.get_or_create(nombre='Pierna B')

        lunes = date(2026, 10, 5)
        for semana in range(6):              # lunes 5-oct … 9-nov
            l = lunes + timedelta(weeks=semana)
            # martes torso normal, viernes pierna en versión reducida
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=torso, fecha=l + timedelta(days=1))
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=pierna, fecha=l + timedelta(days=4),
                                            modo_reducido=True)
            # fútbol el jueves anterior a la pierna
            ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Fútbol',
                                              fecha=l + timedelta(days=3), duracion_minutos=60, fuente='manual')
        # martes 17-nov (semana en curso: no cuenta en el promedio semanal)
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=torso, fecha=date(2026, 11, 17))
        # lunes programados 12-oct … 16-nov: 4 saltados de 6
        for i in range(6):
            SesionProgramada.objects.create(
                cliente=self.cliente, fecha_prevista=date(2026, 10, 12) + timedelta(weeks=i),
                estado=SesionProgramada.ESTADO_SALTADA_USUARIO if i < 4 else SesionProgramada.ESTADO_COMPLETADA,
            )
        # otro cliente: no cuenta
        otro = User.objects.create_user(username='semanal-otro', password='x')
        otro_c, _ = Cliente.objects.get_or_create(user=otro, defaults={'nombre': 'O'})
        EntrenoRealizado.objects.create(cliente=otro_c, rutina=pierna, fecha=date(2026, 11, 13), modo_reducido=True)

    ESPERADO = [
        ('dia_pospone_frecuente', {'dia': 'Lunes', 'total': 6, 'caidas': 4}),
        ('dias_reales_menores', {'promedio': 2.0, 'configurado': 5}),
        ('esenciales_concentradas', {'dia': 'Viernes', 'total': 6, 'esenciales': 6}),
        ('pierna_tras_futbol', {'pierna_esencial': 6, 'total': 6}),
    ]

    def en_peticion(self, vista):
        PeticionesLentasMiddleware(lambda r: vista(r) or HttpResponse('ok'))(RequestFactory().get('/x/'))

    def test_detecta_los_cuatro_patrones_con_sus_datos(self):
        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=REF)
        self.assertEqual([(o['patron'], o['dato']) for o in obs], self.ESPERADO)
        self.assertIn('Las sesiones del Lunes caen con frecuencia (4 de 6 veces)', obs[0]['texto'])

    def test_dentro_de_una_peticion_da_lo_mismo(self):
        fuera = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=REF)
        dentro = []
        self.en_peticion(lambda r: dentro.extend(analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=REF)))
        self.assertEqual(dentro, fuera)

    def test_las_dos_llamadas_de_ahora_hacen_pocas_consultas(self):
        """Ahora llama a la sugerencia y a la distribución: la segunda no repite lecturas."""
        def vista(request):
            with CaptureQueriesContext(connection) as ctx:
                get_sugerencia_distribucion_activa(self.cliente, REF)          # crea la sugerencia
                analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=REF)
            self.consultas = [q['sql'][:90] for q in ctx.captured_queries]
        self.en_peticion(vista)
        # 4 lecturas del análisis (programadas, entrenos con rutina, fútbol, conteo
        # semanal) + sugerencia (buscar y crear, con su savepoint) + el análisis de
        # nuevo tras la escritura (4). Antes: 74 en producción.
        self.assertLessEqual(len(self.consultas), 14, '\n'.join(self.consultas))

    def test_la_segunda_llamada_sin_escrituras_no_consulta(self):
        def vista(request):
            analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=REF)
            with CaptureQueriesContext(connection) as ctx:
                analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=REF)
            self.segunda = len(ctx.captured_queries)
        self.en_peticion(vista)
        self.assertEqual(self.segunda, 0)

    def test_sigue_creando_la_sugerencia_desde_ahora(self):
        self.en_peticion(lambda r: get_sugerencia_distribucion_activa(self.cliente, REF))
        sug = SugerenciaPlan.objects.get(cliente=self.cliente)
        self.assertEqual(sug.patron, 'distribucion_dia_pospone_frecuente')
        self.assertEqual(sug.estado, SugerenciaPlan.ESTADO_PENDIENTE)
