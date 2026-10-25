"""Revisión del Día 3 de David (18-oct-2026).

Suelo de peso en la última carga que entró, unidades "por brazo / por pierna",
zancadas con kettlebell, peso del ejercicio nuevo tras un cambio, plurales del
cierre y récords que no lo eran.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from entrenos.models import RecordPersonal
from entrenos.services.cierre_entrenamiento_service import _efecto_decision
from entrenos.services.maquina_service import salto_fisico, tipo_equipo_carga
from entrenos.services.peso_semantica_service import normalizar_semantica_carga
from entrenos.services.plan_dinamico_service import _rehacer_peso_variante
from entrenos.services.records_service import RecordsService
from entrenos.services.ultima_sesion_service import aplicar_techo
from entrenos.tests_ultima_sesion import AYER, HOY, Base


class Unidades(SimpleTestCase):
    def unidad(self, nombre):
        return normalizar_semantica_carga({'nombre': nombre}).get('reps_unidad', '')

    def test_por_brazo_y_por_pierna(self):
        self.assertEqual(self.unidad('Curl Martillo con Mancuernas'), 'por brazo')
        self.assertEqual(self.unidad('Zancadas con Kettlebell'), 'por pierna')
        self.assertEqual(self.unidad('Sentadilla Búlgara'), 'por pierna')
        self.assertEqual(self.unidad('Pallof Press'), 'por lado')
        self.assertEqual(self.unidad('Jalón al Pecho'), '')

    def test_kettlebell_de_2_en_2(self):
        # 25-oct-2026: kettlebells sueltas (8, 10…) o una mancuerna si falta el peso.
        self.assertEqual(tipo_equipo_carga('Zancadas con Kettlebell'), 'kettlebell')
        self.assertEqual(salto_fisico('Zancadas con Kettlebell'), 2)

    def test_plural_del_cierre(self):
        uno = SimpleNamespace(accion='subir_reps', valor_cambio=1)
        dos = SimpleNamespace(accion='subir_reps', valor_cambio=2)
        self.assertEqual(_efecto_decision(uno, 'peso_reps'), 'Añadirá 1 repetición')
        self.assertEqual(_efecto_decision(dos, 'peso_reps'), 'Añadirá 2 repeticiones')


class SueloDePeso(Base):
    def test_no_baja_de_la_carga_que_ya_entro_en_rango(self):
        # Gemelos: la última vez 100 × 15 (rango 15-20); el plan traía 95.
        e = self.entreno(AYER, {self.gemelos.nombre: '15-20'})
        self.hacer(e, self.gemelos, [(100, 15, 8)] * 3)
        ej = {'nombre': self.gemelos.nombre, 'repeticiones': '15-20', 'peso_kg': 95.0,
              'rpe_objetivo': 9, 'tipo_progresion': 'peso_reps'}
        aplicar_techo(self.cliente, ej, HOY)
        self.assertEqual(ej['peso_kg'], 100)


class CambioDeEjercicio(Base):
    def test_sin_historial_del_nuevo_no_hereda_el_peso(self):
        ej = {'nombre': 'Curl Martillo con Mancuernas', 'repeticiones': '10-12', 'peso_kg': 30.0,
              'rpe_objetivo': 8, 'progresion_aplicada': True, 'peso_kg_anterior': 30}
        _rehacer_peso_variante(self.cliente, ej, HOY)
        self.assertEqual(ej['peso_kg'], 0)
        self.assertNotIn('peso_kg_anterior', ej)
        self.assertIn('Sin datos recientes con Curl Martillo', ej['progresion_motivo'])

    def test_con_historial_parte_del_nuevo(self):
        e = self.entreno(AYER, {'Prensa de Piernas': '10-12'})
        self.hacer(e, self.prensa, [(140, 10, 8)] * 3)
        ej = {'nombre': 'Prensa de Piernas', 'repeticiones': '10-12', 'peso_kg': 60.0, 'rpe_objetivo': 8}
        _rehacer_peso_variante(self.cliente, ej, HOY)
        self.assertEqual(ej['peso_kg'], 140)
        self.assertEqual(ej['reps_objetivo_hoy'], 11)


class Records(Base):
    def test_igualar_una_marca_anterior_no_es_record(self):
        antes = self.entreno(AYER, {self.gemelos.nombre: '15-20'})
        self.hacer(antes, self.gemelos, [(100, 15, 8)])
        hoy = self.entreno(HOY, {self.gemelos.nombre: '15-20'})
        self.hacer(hoy, self.gemelos, [(100, 12, 9)])
        self.assertIsNone(RecordsService._verificar_record_peso(self.cliente, self.gemelos.nombre, 100, hoy))
        vigente = RecordPersonal.objects.get(cliente=self.cliente, tipo_record='peso_maximo', superado=False)
        self.assertEqual((float(vigente.valor), vigente.entreno_id), (100.0, antes.id))

    def test_superarla_si_lo_es(self):
        antes = self.entreno(AYER, {self.gemelos.nombre: '15-20'})
        self.hacer(antes, self.gemelos, [(95, 15, 8)])
        hoy = self.entreno(HOY, {self.gemelos.nombre: '15-20'})
        self.hacer(hoy, self.gemelos, [(100, 15, 9)])
        record = RecordsService._verificar_record_peso(self.cliente, self.gemelos.nombre, 100, hoy)
        self.assertIsNotNone(record)
        self.assertEqual(record.entreno_id, hoy.id)


class RangoPorPierna(SimpleTestCase):
    def test_zancadas_y_bulgaras_hasta_12_por_pierna(self):
        from entrenos.services.peso_semantica_service import rango_unilateral_pierna
        self.assertEqual(rango_unilateral_pierna('Zancadas con Kettlebell', '15-20'), '8-12')
        self.assertEqual(rango_unilateral_pierna('Sentadilla Búlgara', '12-15'), '8-12')
        self.assertEqual(rango_unilateral_pierna('Sentadilla Búlgara', '6-8'), '6-8')
        # Los unilaterales de máquina o aislamiento conservan el rango del programa.
        self.assertEqual(rango_unilateral_pierna('Elevación de Gemelos Unilateral (Mancuerna)', '15-20'), '15-20')
        self.assertEqual(rango_unilateral_pierna('Prensa de Piernas', '15-20'), '15-20')


class MigracionCurlMartilloTotal(Base):
    def test_historial_por_mancuerna_pasa_a_total_y_rehace_records(self):
        import importlib
        from datetime import date
        from django.apps import apps
        from rutinas.models import EjercicioBase
        mig = importlib.import_module('entrenos.migrations.0066_farmer_zancadas_y_curl_martillo_total')
        curl = EjercicioBase.objects.create(nombre='Curl Martillo con Mancuernas', grupo_muscular='biceps')
        self.cliente.pk  # noqa
        antes = self.entreno(date(2026, 10, 8), {curl.nombre: '10-12'})
        self.hacer(antes, curl, [(17.5, 6, 9)])
        hoy = self.entreno(date(2026, 10, 18), {curl.nombre: '10-12'})
        self.hacer(hoy, curl, [(30, 8, 7)])
        RecordPersonal.objects.create(cliente=self.cliente, ejercicio_nombre=curl.nombre,
                                      tipo_record='peso_maximo', valor=30, entreno=hoy)
        mig.CLIENTE = self.cliente.id
        mig.curl_a_total(apps, None)
        vigente = RecordPersonal.objects.get(cliente=self.cliente, tipo_record='peso_maximo', superado=False)
        self.assertEqual((float(vigente.valor), vigente.entreno_id), (35.0, antes.id))
        self.assertFalse(RecordPersonal.objects.filter(entreno=hoy, tipo_record='peso_maximo').exists())
