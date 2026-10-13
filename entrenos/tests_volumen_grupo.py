"""Paso 5 (13-oct-2026): el entrenador ajusta el volumen de cada músculo."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ContratoBloqueGym, GymDecisionLog, PropuestaZonaGym
from entrenos.services.propuesta_zona_service import (
    detectar_zona_con_fatiga, evaluar_propuestas_vencidas, frase_evaluacion, generar_propuesta_si_procede,
)
from entrenos.services.volumen_grupo_service import ajustes_volumen, series_por_grupo

HOY = date(2026, 10, 14)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='volumen', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'V'})
        self.addCleanup(cache.clear)

    def propuesta(self, zona='isquios', estado=PropuestaZonaGym.ESTADO_ACEPTADA, direccion='subir',
                  inicio=HOY - timedelta(days=3), resultado=None):
        return PropuestaZonaGym.objects.create(
            cliente=self.cliente, zona=zona, ejercicios=['Curl femoral tumbado'], series_extra=2,
            direccion=direccion, semanas=4, texto='x', estado=estado, inicio=inicio,
            fin=inicio + timedelta(days=27), resultado=resultado,
        )


class AjustesVolumen(Base):
    def test_propuesta_aceptada_en_curso_suma_dos_series(self):
        self.propuesta()
        self.assertEqual(series_por_grupo(self.cliente, HOY), {'isquios': 2})
        motivo = ajustes_volumen(self.cliente, HOY)['isquios']['motivos'][0]
        self.assertIn('+2 series de Isquios por la propuesta aceptada', motivo)

    def test_propuesta_de_bajar_resta(self):
        self.propuesta(zona='cuadriceps', direccion='bajar')
        self.assertEqual(series_por_grupo(self.cliente, HOY), {'cuadriceps': -2})

    def test_si_funciono_el_cambio_se_queda(self):
        self.propuesta(estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='validada',
                       inicio=HOY - timedelta(days=40))
        self.assertEqual(series_por_grupo(self.cliente, HOY), {'isquios': 2})

    def test_si_no_funciono_no_se_queda(self):
        self.propuesta(estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='fallida',
                       inicio=HOY - timedelta(days=40))
        self.assertEqual(series_por_grupo(self.cliente, HOY), {})

    def test_cuenta_solo_la_ultima_evaluacion_de_cada_zona(self):
        self.propuesta(estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='validada',
                       inicio=HOY - timedelta(days=80))
        self.propuesta(estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='fallida',
                       inicio=HOY - timedelta(days=40))
        self.assertEqual(series_por_grupo(self.cliente, HOY), {})

    def test_el_enfasis_del_bloque_suma_volumen_real(self):
        from entrenos.models import EstrategiaSemanalGym
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=HOY - timedelta(days=9),
        )
        ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=1, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            estrategia=estrategia, limites_snapshot={}, fingerprint='m' * 64,
            semana_inicio=HOY - timedelta(days=9), semanas_previstas=6,
            semana_fin_prevista=HOY + timedelta(days=30), objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='general', objetivos_secundarios=['gemelos', 'brazos'],
            motor_nombre='Helms', motor_version='x',
        )
        self.assertEqual(series_por_grupo(self.cliente, HOY), {'gemelos': 2, 'biceps': 2, 'triceps': 2})

    def test_tope_de_cuatro_series(self):
        self.propuesta()
        self.propuesta(estado=PropuestaZonaGym.ESTADO_ACEPTADA, inicio=HOY - timedelta(days=1))
        self.propuesta(estado=PropuestaZonaGym.ESTADO_ACEPTADA, inicio=HOY - timedelta(days=2))
        self.assertEqual(series_por_grupo(self.cliente, HOY), {'isquios': 4})


class PropuestaPorFatiga(Base):
    def fatiga(self, nombres):
        for n in nombres:
            GymDecisionLog.objects.create(
                cliente=self.cliente, ejercicio=n, accion='mantener', motivo='RPE alto',
                motivo_codigo='rpe_alto_sostenido',
            )

    def test_detecta_fatiga_en_dos_ejercicios_de_la_misma_zona(self):
        self.fatiga(['Sentadilla Hack', 'Prensa de Piernas'])
        hoy = timezone.localdate()
        with patch('entrenos.services.evolucion_muscular_service.calcular_evolucion_por_grupo',
                   return_value={'estado_por_zona': {}}):
            deteccion = detectar_zona_con_fatiga(self.cliente, hoy)
        self.assertEqual(deteccion['zona'], 'cuadriceps')

    def test_propone_bajar_si_no_hay_zona_que_retroceda(self):
        self.fatiga(['Sentadilla Hack', 'Prensa de Piernas'])
        hoy = timezone.localdate()
        with patch('entrenos.services.propuesta_zona_service.detectar_zona_en_retroceso', return_value=None), \
                patch('entrenos.services.evolucion_muscular_service.calcular_evolucion_por_grupo',
                      return_value={'estado_por_zona': {}}):
            p = generar_propuesta_si_procede(self.cliente, hoy)
        self.assertEqual(p.direccion, 'bajar')
        self.assertIn('Te propongo −2 series semanales de Cuádriceps', p.texto)
        self.assertIn('RPE alto o fallos no previstos en 2 ejercicios', p.texto)

    def test_una_sola_senal_no_basta(self):
        self.fatiga(['Sentadilla Hack'])
        self.assertIsNone(detectar_zona_con_fatiga(self.cliente, timezone.localdate()))

    def test_evaluacion_de_bajar_funciona_si_no_se_pierde_fuerza(self):
        p = self.propuesta(zona='cuadriceps', direccion='bajar', inicio=HOY - timedelta(days=40))
        with patch('entrenos.services.evolucion_muscular_service.comparar_ejercicios',
                   return_value=[{'ejercicio': 'Curl femoral tumbado', 'pct': -1.0, 'dudoso': False}]):
            evaluar_propuestas_vencidas(self.cliente, HOY)
        p.refresh_from_db()
        self.assertEqual(p.resultado, 'validada')
        self.assertEqual(
            frase_evaluacion(p),
            'Cuádriceps: propuse −2 series semanales durante 4 semanas y aceptaste. '
            'Funcionó: menos volumen sin perder fuerza (-1,0 % frente a las 4 semanas anteriores).',
        )


class PlanificadorAplicaElAjuste(Base):
    def test_el_grupo_ajustado_recibe_dos_series_mas_a_la_semana(self):
        from analytics.planificador_helms.core import PlanificadorHelms
        from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
        from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion

        def semana(con_ajuste):
            perfil = PerfilCliente({'id': self.cliente.id, 'experiencia_años': 7,
                                    'objetivo_principal': 'general', 'dias_disponibles': 5})
            planificador = PlanificadorHelms(perfil)
            planificador._historial_ejercicios_raw = []
            planificador._ajustes_grupo = {'isquios': 2} if con_ajuste else {}
            bloque = GeneradorPeriodizacion.generar_periodizacion_anual()[0]
            sem = planificador._generar_semana_especifica(bloque, 1)
            return sum(e['series'] for ejs in sem.values() for e in ejs if e['grupo_muscular'] == 'isquios')

        self.assertEqual(semana(True), semana(False) + 2)
