"""31-oct-2026: una sesión de descarga no es "la última vez".

En la descarga el peso se baja a propósito (o se limita el RPE). Si la semana
siguiente se leía esa sesión como referencia, el techo dejaba el ejercicio en
el peso de descarga más un salto de máquina. Idea tomada de openGym: las
descargas quedan en el historial pero nunca son la base de la progresión.
"""

from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from entrenos.models import CicloDeload, SemanaPlanGym
from entrenos.services.cerebro_carga_service import proxima_vez_texto
from entrenos.services.ultima_sesion_service import aplicar_techo, anotar_ultima_vez, ultima_sesion
from entrenos.tests_ultima_sesion import Base

HOY = timezone.localdate()
ANTES = HOY - timedelta(days=12)        # sesión normal
DESCARGA = HOY - timedelta(days=5)      # sesión de descarga


def _ej(peso=80.0):
    return {'nombre': 'Sentadilla Hack', 'repeticiones': '12-15', 'peso_kg': peso,
            'peso_recomendado_kg': peso, 'rpe_objetivo': 8, 'tipo_progresion': 'peso_reps'}


class Escenario(Base):
    def preparar(self, marca='semana'):
        normal = self.entreno(ANTES, {'Sentadilla Hack': '12-15'})
        self.hacer(normal, self.hack, [(80, 13, 8), (80, 13, 8), (80, 12, 8)])
        descarga = self.entreno(DESCARGA, {'Sentadilla Hack': '12-15'})
        self.hacer(descarga, self.hack, [(60, 12, 6), (60, 12, 6)])
        if marca == 'semana':
            SemanaPlanGym.objects.create(
                cliente=self.cliente, lunes=DESCARGA - timedelta(days=DESCARGA.weekday()),
                semana_plan=5, descarga=True, origen=SemanaPlanGym.ORIGEN_DESCARGA_PROGRAMADA,
            )
        elif marca == 'snapshot':
            v = descarga.gym_decision_version
            v.snapshot = {'entrenamiento': {'ejercicios': [{
                'nombre': 'Sentadilla Hack', 'repeticiones': '12-15',
                'motivo_peso': {'tipo': 'recalculado_descarga'},
            }]}}
            v.save(update_fields=['snapshot'])
        elif marca == 'ciclo':
            CicloDeload.objects.create(
                cliente=self.cliente, causa=CicloDeload.CAUSA_FATIGA_GYM,
                fecha_inicio=DESCARGA - timedelta(days=1), fecha_fin_prevista=DESCARGA + timedelta(days=5),
            )
        return normal, descarga


class UltimaSesionSaltaLaDescarga(Escenario):
    def test_semana_de_descarga_del_plan(self):
        normal, _ = self.preparar('semana')
        lec = ultima_sesion(self.cliente, 'Sentadilla Hack', HOY)
        self.assertEqual(lec['entreno'].pk, normal.pk)
        self.assertEqual(lec['referencia']['peso'], 80.0)
        self.assertEqual(lec['tras_descarga'], DESCARGA)

    def test_marca_del_snapshot(self):
        normal, _ = self.preparar('snapshot')
        self.assertEqual(ultima_sesion(self.cliente, 'Sentadilla Hack', HOY)['entreno'].pk, normal.pk)

    def test_ciclo_de_deload(self):
        normal, _ = self.preparar('ciclo')
        self.assertEqual(ultima_sesion(self.cliente, 'Sentadilla Hack', HOY)['entreno'].pk, normal.pk)

    def test_ciclo_cerrado_antes_ya_no_cuenta(self):
        _, descarga = self.preparar(None)
        CicloDeload.objects.create(
            cliente=self.cliente, causa=CicloDeload.CAUSA_MANUAL, estado=CicloDeload.ESTADO_CERRADO,
            fecha_inicio=DESCARGA - timedelta(days=3), fecha_fin_prevista=DESCARGA + timedelta(days=3),
            fecha_cierre=DESCARGA,
        )
        self.assertEqual(ultima_sesion(self.cliente, 'Sentadilla Hack', HOY)['entreno'].pk, descarga.pk)

    def test_sin_descarga_nada_cambia(self):
        _, ultima = self.preparar(None)
        lec = ultima_sesion(self.cliente, 'Sentadilla Hack', HOY)
        self.assertEqual(lec['entreno'].pk, ultima.pk)
        self.assertNotIn('tras_descarga', lec)

    def test_solo_hay_descarga_se_usa_marcada(self):
        descarga = self.entreno(DESCARGA, {'Sentadilla Hack': '12-15'})
        self.hacer(descarga, self.hack, [(60, 12, 6)])
        SemanaPlanGym.objects.create(
            cliente=self.cliente, lunes=DESCARGA - timedelta(days=DESCARGA.weekday()),
            semana_plan=5, descarga=True, origen=SemanaPlanGym.ORIGEN_DESCARGA_PROGRAMADA,
        )
        lec = ultima_sesion(self.cliente, 'Sentadilla Hack', HOY)
        self.assertEqual(lec['entreno'].pk, descarga.pk)
        self.assertTrue(lec['descarga'])

    def test_incluir_descarga_lee_la_ultima_tal_cual(self):
        _, descarga = self.preparar('semana')
        lec = ultima_sesion(self.cliente, 'Sentadilla Hack', HOY, incluir_descarga=True)
        self.assertEqual(lec['entreno'].pk, descarga.pk)


class PesoTrasLaDescarga(Escenario):
    def test_el_techo_no_deja_el_peso_en_el_de_descarga(self):
        self.preparar('semana')
        ej = _ej(80.0)
        self.assertIsNone(aplicar_techo(self.cliente, ej, HOY))
        self.assertEqual(ej['peso_kg'], 80.0)

    def test_la_ultima_vez_dice_de_donde_sale(self):
        self.preparar('semana')
        ej = _ej(80.0)
        anotar_ultima_vez(self.cliente, ej, HOY)
        self.assertTrue(ej['ultima_vez_texto'].startswith(f'{ANTES:%d/%m}:'))
        self.assertIn(f'(antes de la descarga del {DESCARGA:%d/%m})', ej['ultima_vez_texto'])

    def test_el_cierre_de_la_descarga_dice_que_no_cuenta(self):
        _, descarga = self.preparar('semana')
        texto, accion, efecto = proxima_vez_texto(
            self.cliente, descarga, 'Sentadilla Hack', 'peso_reps', con_efecto=True,
        )
        self.assertIn('Hoy era descarga', texto)
        self.assertIn('80 kg', texto)
        self.assertEqual(accion, 'Subir peso')
        self.assertEqual(efecto, 'Vuelve a 80 kg')


class AnclaDelPlanificador(Escenario):
    def test_el_ancla_ignora_la_semana_de_descarga(self):
        from analytics.planificador_helms.core import PlanificadorHelms
        self.preparar('semana')
        stub = SimpleNamespace(perfil=SimpleNamespace(id=self.cliente.id))
        PlanificadorHelms._precargar_historial_ejercicios(stub)
        res = PlanificadorHelms._obtener_historial_ejercicio(stub, 'Sentadilla Hack')
        self.assertEqual(res['peso_real_bruto'], 80.0)
        self.assertGreaterEqual(res['peso_real'], 79.0)
