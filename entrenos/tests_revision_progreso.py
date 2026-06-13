"""
Phase 63 — Revisión de progreso (peso/cintura/rendimiento).

`get_revision_progreso(cliente, hoy)` combina tres señales que antes vivían
aisladas (peso, medidas corporales, rendimiento) y antepone una lectura
cruzada prudente cuando hay al menos 2 ejes con datos.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente, PesoDiario, RevisionProgreso
from rutinas.models import Rutina
from entrenos.models import EntrenoRealizado, RecordPersonal
from entrenos.services.revision_progreso_service import get_revision_progreso

HOY = date(2026, 1, 15)


class RevisionProgresoBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_revision', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Rutina test')

    def _crear_peso(self, peso_kg, dias_atras):
        obj = PesoDiario.objects.create(cliente=self.cliente, peso_kg=Decimal(str(peso_kg)))
        PesoDiario.objects.filter(pk=obj.pk).update(fecha=HOY - timedelta(days=dias_atras))
        return obj

    def _crear_revision(self, dias_atras, **medidas):
        obj = RevisionProgreso.objects.create(cliente=self.cliente, **medidas)
        RevisionProgreso.objects.filter(pk=obj.pk).update(fecha=HOY - timedelta(days=dias_atras))
        return obj

    def _crear_entreno(self, dias_atras, volumen):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina,
            fecha=HOY - timedelta(days=dias_atras),
            volumen_total_kg=Decimal(str(volumen)),
        )
        entreno.volumen_total_kg = Decimal(str(volumen))
        entreno.save(update_fields=['volumen_total_kg'])
        return entreno

    def _crear_record(self, dias_atras, ejercicio='Sentadilla', tipo='one_rep_max', valor=100):
        entreno = self._crear_entreno(dias_atras, volumen=1000)
        obj = RecordPersonal.objects.create(
            cliente=self.cliente, ejercicio_nombre=ejercicio, tipo_record=tipo,
            valor=Decimal(str(valor)), entreno=entreno,
        )
        RecordPersonal.objects.filter(pk=obj.pk).update(fecha_logrado=HOY - timedelta(days=dias_atras))
        return obj

    def _tipos(self, items):
        return [item['tipo'] for item in items]


class TestSinDatos(RevisionProgresoBase):
    def test_sin_datos_devuelve_lista_vacia(self):
        self.assertEqual(get_revision_progreso(self.cliente, HOY), [])


class TestSenalPeso(RevisionProgresoBase):
    def test_peso_bajando(self):
        self._crear_peso(80.0, dias_atras=25)
        self._crear_peso(78.0, dias_atras=2)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(self._tipos(items), ['peso'])
        self.assertEqual(items[0]['icono'], '📉')
        self.assertIn('bajando', items[0]['texto'])

    def test_un_solo_registro_no_genera_item(self):
        self._crear_peso(80.0, dias_atras=10)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(items, [])


class TestSenalMedidas(RevisionProgresoBase):
    def test_delta_cintura_y_peso_corporal(self):
        self._crear_revision(dias_atras=20, cintura=Decimal('90.0'), peso_corporal=Decimal('80.0'))
        self._crear_revision(dias_atras=5, cintura=Decimal('88.5'), peso_corporal=Decimal('79.0'))

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(self._tipos(items), ['medidas'])
        texto = items[0]['texto']
        self.assertIn('cintura -1.5 cm', texto)
        self.assertIn('peso corporal -1.0 kg', texto)
        self.assertIn('hace 15 días', texto)

    def test_una_sola_revision_no_genera_item(self):
        self._crear_revision(dias_atras=5, cintura=Decimal('90.0'))

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(items, [])

    def test_sin_cambios_no_genera_item(self):
        self._crear_revision(dias_atras=20, cintura=Decimal('90.0'), peso_corporal=Decimal('80.0'))
        self._crear_revision(dias_atras=5, cintura=Decimal('90.0'), peso_corporal=Decimal('80.0'))

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(items, [])


class TestSenalRendimiento(RevisionProgresoBase):
    def test_records_del_ultimo_mes(self):
        self._crear_record(dias_atras=10, ejercicio='Sentadilla', tipo='one_rep_max')

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(self._tipos(items), ['rendimiento'])
        self.assertEqual(items[0]['icono'], '🏆')
        self.assertEqual(items[0]['color'], 'info')
        self.assertIn('Sentadilla', items[0]['texto'])
        self.assertIn('1RM estimado', items[0]['texto'])

    def test_volumen_subiendo(self):
        self._crear_entreno(dias_atras=7, volumen=12000)
        self._crear_entreno(dias_atras=21, volumen=10000)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(self._tipos(items), ['rendimiento'])
        self.assertEqual(items[0]['icono'], '📈')
        self.assertIn('subiendo', items[0]['texto'])

    def test_sin_historial_previo_omite_tendencia_volumen(self):
        self._crear_record(dias_atras=10)

        items = get_revision_progreso(self.cliente, HOY)

        # Sólo el item de récord; sin item de tendencia de volumen.
        self.assertEqual(self._tipos(items), ['rendimiento'])
        self.assertEqual(items[0]['icono'], '🏆')


class TestLecturaCruzada(RevisionProgresoBase):
    def test_caso1_recomposicion(self):
        # Peso estable
        self._crear_peso(80.0, dias_atras=25)
        self._crear_peso(80.2, dias_atras=2)
        # Cintura bajando
        self._crear_revision(dias_atras=20, cintura=Decimal('90.0'))
        self._crear_revision(dias_atras=5, cintura=Decimal('89.0'))
        # Sin datos de rendimiento

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(items[0]['tipo'], 'lectura_cruzada')
        self.assertIn('recomposición', items[0]['texto'])
        self.assertIn('no parece necesario', items[0]['texto'])
        self.assertEqual(self._tipos(items), ['lectura_cruzada', 'peso', 'medidas'])

    def test_caso2_ganancia_util(self):
        # Peso subiendo
        self._crear_peso(78.0, dias_atras=25)
        self._crear_peso(79.0, dias_atras=2)
        # Cintura estable
        self._crear_revision(dias_atras=20, cintura=Decimal('88.0'))
        self._crear_revision(dias_atras=5, cintura=Decimal('88.2'))
        # Rendimiento mejora (récord)
        self._crear_record(dias_atras=10)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(items[0]['tipo'], 'lectura_cruzada')
        self.assertIn('mejora real', items[0]['texto'])
        self.assertIn('observando', items[0]['texto'])

    def test_caso3_alerta_suave(self):
        # Peso subiendo
        self._crear_peso(78.0, dias_atras=25)
        self._crear_peso(79.0, dias_atras=2)
        # Cintura subiendo
        self._crear_revision(dias_atras=20, cintura=Decimal('88.0'))
        self._crear_revision(dias_atras=5, cintura=Decimal('89.0'))
        # Rendimiento estable (volumen sin cambio significativo, sin récords)
        self._crear_entreno(dias_atras=7, volumen=10000)
        self._crear_entreno(dias_atras=21, volumen=10000)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(items[0]['tipo'], 'lectura_cruzada')
        self.assertIn('revisar adherencia o nutrición', items[0]['texto'])

    def test_caso4_deficit_fatiga(self):
        # Peso bajando
        self._crear_peso(80.0, dias_atras=25)
        self._crear_peso(78.5, dias_atras=2)
        # Sin datos de medidas
        # Rendimiento empeora (volumen bajando, sin récords)
        self._crear_entreno(dias_atras=7, volumen=8000)
        self._crear_entreno(dias_atras=21, volumen=10000)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(items[0]['tipo'], 'lectura_cruzada')
        self.assertIn('déficit', items[0]['texto'])
        self.assertIn('fatiga', items[0]['texto'])
        self.assertEqual(self._tipos(items), ['lectura_cruzada', 'peso', 'rendimiento'])

    def test_un_solo_eje_no_genera_lectura_cruzada(self):
        # Sólo peso, sin medidas ni rendimiento
        self._crear_peso(80.0, dias_atras=25)
        self._crear_peso(78.0, dias_atras=2)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(self._tipos(items), ['peso'])

    def test_dos_ejes_sin_caso_cubierto(self):
        # Peso bajando + cintura subiendo, sin rendimiento → combinación no cubierta
        self._crear_peso(80.0, dias_atras=25)
        self._crear_peso(78.5, dias_atras=2)
        self._crear_revision(dias_atras=20, cintura=Decimal('88.0'))
        self._crear_revision(dias_atras=5, cintura=Decimal('89.0'))

        items = get_revision_progreso(self.cliente, HOY)

        self.assertNotIn('lectura_cruzada', self._tipos(items))
        self.assertEqual(self._tipos(items), ['peso', 'medidas'])

    def test_tres_senales_orden_items(self):
        # Peso subiendo + cintura estable + rendimiento mejora (récord + volumen subiendo)
        self._crear_peso(78.0, dias_atras=25)
        self._crear_peso(79.2, dias_atras=2)
        self._crear_revision(dias_atras=20, cintura=Decimal('88.0'))
        self._crear_revision(dias_atras=5, cintura=Decimal('88.2'))
        self._crear_record(dias_atras=10)  # entreno de 1000 kg dentro de últimas 2 semanas
        self._crear_entreno(dias_atras=7, volumen=12000)
        self._crear_entreno(dias_atras=21, volumen=10000)

        items = get_revision_progreso(self.cliente, HOY)

        self.assertEqual(
            self._tipos(items),
            ['lectura_cruzada', 'peso', 'medidas', 'rendimiento', 'rendimiento'],
        )
        self.assertEqual(items[3]['icono'], '🏆')
        self.assertEqual(items[4]['icono'], '📈')
