"""14-nov-2026 · Repaso del Día 5: notas 4, 8, 16, 17 y 18."""

from datetime import timedelta

from django.utils import timezone

from entrenos.models import EjercicioRealizado
from entrenos.services.cerebro_carga_service import aplicar_decision_carga, decidir_carga
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()


def _ej(nombre, rango, rpe=8):
    return {'nombre': nombre, 'repeticiones': rango, 'rpe_objetivo': rpe, 'tipo_progresion': 'peso_reps'}


class Reparaciones(Base):
    def base(self, nombre):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='x', tipo_progresion='peso_reps')

    def test_nota4_rango_nuevo_parte_de_la_serie_que_mas_se_acerco(self):
        b = self.base('Extensiones sobre la Cabeza con Mancuerna')
        e = self.entreno(HOY - timedelta(days=9), {b.nombre: '15-20'})
        self.hacer(e, b, [(15, 4, 10), (10, 7, 9)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '8-12'), HOY)
        self.assertIsNotNone(d)
        self.assertLessEqual(d['peso'], 10)

    def test_nota8_fatiga_sustituye_el_texto_del_plan(self):
        ej = {'peso_kg': 15, 'reps_objetivo_hoy': 15,
              'progresion_motivo': '15 kg × 14; hoy a por 15'}
        decision = {'peso': 15, 'reps': 15, 'regla': 'fatiga', 'frase': 'Llegaste muy cansado: repetimos 15 kg.'}
        aplicar_decision_carga(ej, decision)
        self.assertEqual(ej['progresion_motivo'], decision['frase'])

    def test_nota17_cierre_dice_que_empezo_por_debajo_del_rango(self):
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes
        b = self.base('Curl Martillo')
        e1 = self.entreno(HOY - timedelta(days=7), {b.nombre: '12-15'})
        self.hacer(e1, b, [(30, 15, 8)] * 2)
        e2 = self.entreno(HOY, {b.nombre: '12-15'})
        self.hacer(e2, b, [(30, 10, 9), (25, 15, 8), (25, 15, 8)])
        c = _cambios_relevantes(self.cliente, e2, list(EjercicioRealizado.objects.filter(entreno=e2)))[0]
        self.assertIn('empezó con 30 × 10, por debajo del rango', c['detalle'])

    def test_nota18_cierre_dice_la_fecha_de_la_sesion_comparada(self):
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes
        b = self.base('Press Militar')
        e0 = self.entreno(HOY - timedelta(days=20), {b.nombre: '8-12'})
        self.hacer(e0, b, [(55, 10, 8)] * 2)
        e1 = self.entreno(HOY - timedelta(days=10), {b.nombre: '4-6'})
        self.hacer(e1, b, [(65, 5, 8)] * 2)
        e2 = self.entreno(HOY, {b.nombre: '8-12'})
        self.hacer(e2, b, [(55, 12, 7)] * 2)
        c = _cambios_relevantes(self.cliente, e2, list(EjercicioRealizado.objects.filter(entreno=e2)))[0]
        self.assertIn(f'sesión del {(HOY - timedelta(days=20)):%d/%m}', c['detalle'])
