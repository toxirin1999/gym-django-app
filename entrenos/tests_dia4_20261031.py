"""31-oct-2026 · Reparaciones del repaso del Día 4."""

from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from entrenos.models import GymDecisionVersion
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()


class Escalas(SimpleTestCase):
    def test_nota2_sin_calentamiento_por_debajo_de_10(self):
        from entrenos.services.calentamiento_service import get_aproximaciones_calentamiento
        self.assertIsNone(get_aproximaciones_calentamiento(8, incremento=1))
        self.assertIsNotNone(get_aproximaciones_calentamiento(36, incremento=2))

    def test_nota4_barra_olimpica(self):
        from entrenos.services.maquina_service import peso_minimo, salto_fisico, tipo_equipo_carga
        self.assertEqual(tipo_equipo_carga('Encogimientos con Barra'), 'barra_olimpica')
        self.assertEqual(tipo_equipo_carga('Buenos Días (Good Mornings)'), 'barra_olimpica')
        self.assertEqual(salto_fisico('Encogimientos con Barra'), 5.0)
        self.assertEqual(peso_minimo('Buenos Días (Good Mornings)'), 20.0)
        self.assertNotEqual(tipo_equipo_carga('Sentadilla Hack'), 'barra_olimpica')
        self.assertNotEqual(tipo_equipo_carga('Elevación de Gemelos en Multipower'), 'barra_olimpica')
        self.assertEqual(tipo_equipo_carga('Curl con Barra Z'), 'barra_z')
        self.assertIsNone(peso_minimo('Jalon brazos rectos'))


class Decisiones(Base):
    def _snapshot(self, entreno, ejercicios):
        v = entreno.gym_decision_version
        v.snapshot = {'entrenamiento': {'ejercicios': ejercicios}}
        v.save(update_fields=['snapshot'])

    def test_nota4_nunca_por_debajo_de_la_barra(self):
        from entrenos.services.cerebro_carga_service import decidir_carga
        b = EjercicioBase.objects.create(nombre='Buenos Días (Good Mornings)', grupo_muscular='Isquiotibiales',
                                         tipo_progresion='peso_reps')
        e = self.entreno(HOY - timedelta(days=45), {b.nombre: '6-8'})
        self.hacer(e, b, [(22, 6, 9), (22, 6, 9), (22, 5, 9)])
        d = decidir_carga(self.cliente, {'nombre': b.nombre, 'repeticiones': '15-20', 'rpe_objetivo': 7,
                                         'tipo_progresion': 'peso_reps', 'peso_kg': 22}, HOY)
        self.assertEqual(d['peso'], 20.0)
        self.assertIn('hoy 20 kg (la barra vacía)', d['frase'])

    def test_nota7_primera_serie_por_encima_del_plan(self):
        from entrenos.services.cerebro_carga_service import decidir_carga
        b = EjercicioBase.objects.create(nombre='Encogimientos con Barra', grupo_muscular='Trapecio',
                                         tipo_progresion='peso_reps')
        e = self.entreno(HOY - timedelta(days=1), {b.nombre: '15-20'})
        self._snapshot(e, [{'nombre': b.nombre, 'repeticiones': '15-20', 'peso_kg': 110, 'reps_objetivo_hoy': 17}])
        self.hacer(e, b, [(120, 10, 9), (110, 12, 9), (110, 12, 9)])
        ej = {'nombre': b.nombre, 'repeticiones': '15-20', 'rpe_objetivo': 9, 'tipo_progresion': 'peso_reps',
              'peso_kg': 110}
        d = decidir_carga(self.cliente, ej, HOY)
        self.assertEqual((d['peso'], d['reps']), (110.0, 17))
        self.assertIn('empezaste con 120 kg', d['frase'])

    def test_nota3_tarjeta_con_la_mediana(self):
        from entrenos.views import obtener_ultimo_peso_ejercicio
        b = EjercicioBase.objects.create(nombre='Press Militar', grupo_muscular='Hombros',
                                         tipo_progresion='peso_reps')
        e = self.entreno(HOY - timedelta(days=3), {b.nombre: '6-8'})
        self.hacer(e, b, [(22, 6, 9), (22, 6, 9), (22, 5, 9)])
        datos = obtener_ultimo_peso_ejercicio(self.cliente.id, b.nombre, HOY, rango='15-20')
        self.assertEqual(datos['repeticiones'], 6)

    def test_nota10_mas_peso_por_debajo_no_es_subida(self):
        from entrenos.services.cierre_entrenamiento_service import _comparar_referencias
        b = EjercicioBase.objects.create(nombre='Encogimientos con Barra', grupo_muscular='Trapecio',
                                         tipo_progresion='peso_reps')
        antes = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(antes, b, [(110, 16, 9)] * 3)
        hoy = self.entreno(HOY, {b.nombre: '15-20'})
        self.hacer(hoy, b, [(120, 10, 9), (110, 12, 9), (110, 12, 9)])
        c = _comparar_referencias(hoy, antes, b.nombre)
        self.assertEqual(c['tipo'], 'mantenida')
        self.assertIn('por debajo del rango', c['detalle'])


class Aprendizaje(Base):
    def test_nota11_el_peso_que_se_propuso_de_verdad(self):
        from entrenos.models import GymDecisionLog
        from entrenos.services.aprendizaje_decisiones_service import frase_decision
        b = EjercicioBase.objects.create(nombre='Curl Femoral Sentado', grupo_muscular='Isquiotibiales',
                                         tipo_progresion='peso_reps')
        antes = self.entreno(HOY - timedelta(days=7), {b.nombre: '6-8'})
        self.hacer(antes, b, [(50, 5, 10)] * 3)
        hoy = self.entreno(HOY, {b.nombre: '15-20'})
        v = hoy.gym_decision_version
        v.snapshot = {'entrenamiento': {'ejercicios': [{'nombre': b.nombre, 'peso_kg': 35}]}}
        v.save(update_fields=['snapshot'])
        self.hacer(hoy, b, [(35, 15, 8)] * 3)
        log = GymDecisionLog.objects.create(cliente=self.cliente, ejercicio=b.nombre, accion='bajar_peso',
                                            peso_anterior=50, valor_cambio=10, entreno_origen=antes,
                                            resultado='validada')
        self.assertIn('bajé el peso a 35 kg', frase_decision(log))
