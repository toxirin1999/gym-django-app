"""Paso 4 (13-oct-2026): periodización dinámica.

El plan avanza solo con semanas entrenadas, la descarga llega cuando hay
señales (o como tarde a las 8 semanas) y cada decisión se explica con el dato.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, GymDecisionLog, SemanaPlanGym
from entrenos.services import periodizacion_dinamica_service as svc
from entrenos.services.porque_decision_service import construir_porque
from rutinas.models import Rutina

LUNES = date(2026, 3, 2)   # semana 9 del calendario: Fuerza — Base (contenido)
SENAL = {'codigo': 'fatiga_ejercicios', 'texto': 'RPE alto o fallos no previstos en 3 ejercicios en 14 días'}
SENAL_2 = {'codigo': 'energia_baja', 'texto': 'energía media 3,7/10 en 7 días'}


class Base(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='periodo', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'P'})
        self.cliente.dias_disponibles = 4
        self.cliente.save(update_fields=['dias_disponibles'])
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - X')
        self.addCleanup(cache.clear)

    def entrenar_semana(self, lunes, sesiones):
        for i in range(sesiones):
            f = lunes + timedelta(days=i)
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=f, fecha_ejecucion=f)

    def resolver(self, lunes, senales=()):
        with patch.object(svc, 'senales_fatiga', return_value=list(senales)):
            return svc.resolver_semana(self.cliente, lunes, hoy=lunes)


class ArranqueYAvance(Base):
    def test_arranca_en_la_semana_del_calendario(self):
        info = self.resolver(LUNES)
        self.assertEqual(info['semana_plan'], svc.semana_calendario(LUNES))
        self.assertEqual(info['origen'], SemanaPlanGym.ORIGEN_CALENDARIO)

    def test_avanza_si_la_semana_se_entreno(self):
        inicial = self.resolver(LUNES)['semana_plan']
        self.entrenar_semana(LUNES, 2)  # 2 de 4 = la mitad
        info = self.resolver(LUNES + timedelta(days=7))
        self.assertEqual(info['semana_plan'], inicial + 1)
        self.assertEqual(info['origen'], SemanaPlanGym.ORIGEN_AVANCE)

    def test_repite_si_la_semana_apenas_se_entreno(self):
        inicial = self.resolver(LUNES)['semana_plan']
        self.entrenar_semana(LUNES, 1)
        info = self.resolver(LUNES + timedelta(days=7))
        self.assertEqual(info['semana_plan'], inicial)
        self.assertEqual(info['origen'], SemanaPlanGym.ORIGEN_REPETICION)
        self.assertEqual(
            info['motivo'],
            'La semana pasada hiciste 1 de 4 sesiones: repito la semana en vez de avanzar.',
        )

    def test_vacaciones_no_hacen_avanzar_el_plan(self):
        inicial = self.resolver(LUNES)['semana_plan']
        info = self.resolver(LUNES + timedelta(days=21))  # tres semanas sin entrenar
        self.assertEqual(info['semana_plan'], inicial)

    def test_el_pasado_no_cambia(self):
        self.resolver(LUNES)
        self.entrenar_semana(LUNES, 4)
        primero = self.resolver(LUNES + timedelta(days=7))
        EntrenoRealizado.objects.all().delete()
        segundo = self.resolver(LUNES + timedelta(days=7))
        self.assertEqual(primero, segundo)

    def test_las_semanas_futuras_se_proyectan_sin_guardarse(self):
        actual = self.resolver(LUNES)['semana_plan']
        with patch.object(svc, 'senales_fatiga', return_value=[]):
            futura = svc.resolver_semana(self.cliente, LUNES + timedelta(days=14), hoy=LUNES)
        self.assertEqual(futura['semana_plan'], actual + 2)
        self.assertTrue(futura['proyectada'])
        self.assertEqual(SemanaPlanGym.objects.filter(cliente=self.cliente).count(), 1)


class DescargaProgramada(Base):
    """La semana 13 del plan es la descarga que cierra Fuerza — Base."""

    def preparar(self, semanas_sin_descarga):
        lunes0 = LUNES - timedelta(days=7 * semanas_sin_descarga)
        for k in range(semanas_sin_descarga):
            SemanaPlanGym.objects.create(
                cliente=self.cliente, lunes=lunes0 + timedelta(days=7 * k),
                semana_plan=12 - semanas_sin_descarga + 1 + k, origen=SemanaPlanGym.ORIGEN_AVANCE,
            )
        self.entrenar_semana(LUNES - timedelta(days=7), 4)
        self.assertTrue(svc.es_semana_descarga(13))

    def test_sin_senales_y_pocas_semanas_se_salta(self):
        self.preparar(3)
        info = self.resolver(LUNES)
        self.assertEqual(info['semana_plan'], 14)
        self.assertFalse(info['descarga'])
        self.assertEqual(info['origen'], SemanaPlanGym.ORIGEN_DESCARGA_SALTADA)
        self.assertIn('Me salto la descarga del bloque', info['motivo'])

    def test_con_una_senal_se_hace(self):
        self.preparar(3)
        info = self.resolver(LUNES, senales=[SENAL])
        self.assertEqual(info['semana_plan'], 13)
        self.assertTrue(info['descarga'])
        self.assertEqual(info['motivo'], f"Semana de descarga del bloque: {SENAL['texto']}.")

    def test_tras_cinco_semanas_se_hace_aunque_no_haya_senales(self):
        self.preparar(5)
        info = self.resolver(LUNES)
        self.assertTrue(info['descarga'])
        self.assertEqual(info['origen'], SemanaPlanGym.ORIGEN_DESCARGA_PROGRAMADA)


class DescargaIntercalada(Base):
    def preparar(self, semanas):
        lunes0 = LUNES - timedelta(days=7 * semanas)
        for k in range(semanas):
            SemanaPlanGym.objects.create(
                cliente=self.cliente, lunes=lunes0 + timedelta(days=7 * k),
                semana_plan=1 + k, origen=SemanaPlanGym.ORIGEN_AVANCE,
            )
        self.entrenar_semana(LUNES - timedelta(days=7), 4)

    def test_dos_senales_meten_una_descarga_y_luego_se_retoma(self):
        self.preparar(4)  # semanas 1-4 hechas; toca la 5 (contenido)
        info = self.resolver(LUNES, senales=[SENAL, SENAL_2])
        self.assertTrue(info['descarga'])
        self.assertEqual(info['origen'], SemanaPlanGym.ORIGEN_DESCARGA_SENAL)
        self.assertEqual(info['semana_plan'], 5)
        self.assertEqual(info['motivo'], f"Semana de descarga: {SENAL['texto']} y {SENAL_2['texto']}.")

        siguiente = self.resolver(LUNES + timedelta(days=7))
        self.assertFalse(siguiente['descarga'])
        self.assertEqual(siguiente['semana_plan'], 5)

    def test_una_sola_senal_no_basta(self):
        self.preparar(4)
        self.assertFalse(self.resolver(LUNES, senales=[SENAL])['descarga'])

    def test_como_tarde_a_las_ocho_semanas(self):
        self.preparar(8)  # semanas 1-8 sin descarga; toca la 9 (contenido)
        info = self.resolver(LUNES)
        self.assertTrue(info['descarga'])
        self.assertEqual(info['origen'], SemanaPlanGym.ORIGEN_DESCARGA_OBLIGATORIA)
        self.assertEqual(info['motivo'], 'Semana de descarga: llevas 8 semanas entrenando sin descargar.')

    def test_el_bloque_de_descarga_intercalado_es_el_siguiente_de_descarga(self):
        bloque, _ = svc.bloque_para_semana({'semana_plan': 5, 'descarga': True})
        self.assertEqual(bloque['fase'], 'descarga')


class Senales(Base):
    def test_fatiga_en_tres_ejercicios(self):
        hoy = timezone.localdate()
        for nombre in ('Press banca', 'Remo', 'Sentadilla'):
            GymDecisionLog.objects.create(
                cliente=self.cliente, ejercicio=nombre, accion='mantener',
                motivo='RPE alto', motivo_codigo='rpe_alto_sostenido',
            )
        codigos = [s['codigo'] for s in svc.senales_fatiga(self.cliente, hoy)]
        self.assertIn('fatiga_ejercicios', codigos)

    def test_sin_datos_no_hay_senales(self):
        self.assertEqual(svc.senales_fatiga(self.cliente, timezone.localdate()), [])


class PlanYPorque(Base):
    def test_el_planificador_usa_la_semana_resuelta_y_lo_explica(self):
        from analytics.planificador_helms.core import PlanificadorHelms
        from analytics.planificador_helms.models.perfil_cliente import PerfilCliente

        hoy = timezone.localdate()
        lunes = svc.lunes_de(hoy)
        SemanaPlanGym.objects.create(
            cliente=self.cliente, lunes=lunes, semana_plan=3,
            origen=SemanaPlanGym.ORIGEN_REPETICION,
            motivo='La semana pasada hiciste 1 de 4 sesiones: repito la semana en vez de avanzar.',
        )
        perfil = PerfilCliente({'id': self.cliente.id, 'experiencia_años': 3,
                                'objetivo_principal': 'hipertrofia', 'dias_disponibles': 4})
        planificador = PlanificadorHelms(perfil)
        entreno = planificador.generar_entrenamiento_para_fecha(lunes)
        self.assertEqual(entreno['semana_plan'], 3)
        self.assertEqual(entreno['bloque'], 'Hipertrofia — Acumulación')
        self.assertEqual(entreno['semana_en_bloque'], 3)
        decision = {'estado': 'entrenar', 'entrenamiento': entreno, 'contexto_fisico': {}}
        self.assertEqual(
            construir_porque(decision),
            'La semana pasada hiciste 1 de 4 sesiones: repito la semana en vez de avanzar.',
        )

    def test_descarga_intercalada_usa_volumen_de_descarga(self):
        from analytics.planificador_helms.core import PlanificadorHelms
        from analytics.planificador_helms.models.perfil_cliente import PerfilCliente

        hoy = timezone.localdate()
        lunes = svc.lunes_de(hoy)
        SemanaPlanGym.objects.create(
            cliente=self.cliente, lunes=lunes, semana_plan=3, descarga=True,
            origen=SemanaPlanGym.ORIGEN_DESCARGA_SENAL, motivo='Semana de descarga: x e y.',
        )
        perfil = PerfilCliente({'id': self.cliente.id, 'experiencia_años': 3,
                                'objetivo_principal': 'hipertrofia', 'dias_disponibles': 4})
        entreno = PlanificadorHelms(perfil).generar_entrenamiento_para_fecha(lunes)
        self.assertIn('Descarga', entreno['bloque'])
        self.assertTrue(entreno['periodizacion']['descarga'])
