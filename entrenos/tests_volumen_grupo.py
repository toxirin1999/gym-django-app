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

    def _validada_con_revision(self, **revision):
        p = self.propuesta(estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='validada',
                           inicio=HOY - timedelta(days=40))
        from entrenos.services.propuesta_zona_service import fijar_revision
        fijar_revision(p, date(2026, 12, 6), 'fin del bloque', hoy=HOY)
        return p

    def test_con_revision_el_ajuste_vale_hasta_la_fecha_y_despues_no_se_prolonga_solo(self):
        p = self._validada_con_revision()
        self.assertEqual(series_por_grupo(self.cliente, date(2026, 12, 6)), {'isquios': 2})
        motivo = ajustes_volumen(self.cliente, date(2026, 12, 6))['isquios']['motivos'][0]
        self.assertIn('se mantiene hasta el 06/12 inclusive y el 07/12 deja de aplicarse si no decides', motivo)
        # El 7/12 ya no rige: antes seguía 182 días.
        self.assertEqual(series_por_grupo(self.cliente, date(2026, 12, 7)), {})
        from entrenos.services.volumen_grupo_service import revisiones_pendientes
        self.assertEqual(revisiones_pendientes(self.cliente, date(2026, 12, 6)), [])
        pend = revisiones_pendientes(self.cliente, date(2026, 12, 7))
        self.assertEqual([x['zona'] for x in pend], ['isquios'])
        self.assertIn('el 07/12 deja de aplicarse si no decides', frase_evaluacion(p))

    def test_decision_explicita_prolonga_o_retira(self):
        from entrenos.services.propuesta_zona_service import decidir_revision
        p = self._validada_con_revision()
        decidir_revision(p, 'prolongar', 'sigue progresando', hasta=date(2027, 1, 31), hoy=date(2026, 12, 7))
        self.assertEqual(series_por_grupo(self.cliente, date(2026, 12, 20)), {'isquios': 2})
        self.assertEqual(series_por_grupo(self.cliente, date(2027, 2, 1)), {})
        decidir_revision(p, 'retirar', 'ya no hace falta', hoy=date(2027, 1, 5))
        self.assertEqual(series_por_grupo(self.cliente, date(2027, 1, 10)), {})
        p.refresh_from_db()
        self.assertEqual(len(p.deteccion['revision']['decisiones']), 2)
        with self.assertRaises(ValueError):
            decidir_revision(p, 'prolongar', 'sin fecha')

    def test_sin_revision_rige_la_regla_antigua_de_182_dias(self):
        self.propuesta(estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='validada',
                       inicio=HOY - timedelta(days=40))
        self.assertEqual(series_por_grupo(self.cliente, HOY + timedelta(days=100)), {'isquios': 2})
        self.assertEqual(series_por_grupo(self.cliente, HOY + timedelta(days=300)), {})

    def test_el_ajuste_validado_no_se_pausa_en_descarga_comportamiento_pendiente_de_resolver(self):
        """PENDIENTE (18-nov-2026): una propuesta aceptada se pausa en la descarga; una validada no."""
        self._validada_con_revision()
        with patch('entrenos.services.propuesta_zona_service.en_pausa_por_descarga', return_value=True):
            self.assertEqual(series_por_grupo(self.cliente, date(2026, 12, 1)), {'isquios': 2})

    def test_el_comando_de_revision_hace_vista_previa_sin_guardar(self):
        from io import StringIO

        from django.core.management import call_command
        p = self.propuesta(estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='validada',
                           inicio=HOY - timedelta(days=40))
        salida = StringIO()
        with patch('entrenos.services.marcador_semanal_service.series_plan_semana',
                   return_value=(__import__('collections').Counter({'isquios': 4}), [])):
            call_command('revision_propuesta_zona', self.cliente.pk, p.pk, fijar='2026-12-06',
                         semanas=['2026-11-30', '2026-12-07'], stdout=salida)
        p.refresh_from_db()
        self.assertNotIn('revision', p.deteccion or {})
        texto = salida.getvalue()
        self.assertIn('no se guarda nada', texto)
        self.assertIn('PENDIENTE DE RESOLVER · Descarga', texto)
        self.assertIn('30/11', texto)
        self.assertIn('sin ajuste', texto)
        self.assertIn('Proyección con las reglas y los datos actuales. No reconstruye lo prescrito en semanas '
                      'pasadas o en curso. Las sesiones futuras pueden cambiar al generarse. Para consultar lo '
                      'prescrito, usa las versiones guardadas de cada sesión.', texto)

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
        fila = {'ejercicio': 'Curl femoral tumbado', 'pct': -1.0, 'dudoso': False,
                'antes': {'peso_kg': 40.0, 'reps': 10, 'fecha': p.inicio - timedelta(days=3)},
                'ahora': {'peso_kg': 40.0, 'reps': 10, 'fecha': p.inicio + timedelta(days=12)}}
        with patch('entrenos.services.evolucion_muscular_service.comparar_ejercicios', return_value=[fila]), \
                patch('entrenos.services.propuesta_zona_service.sesiones_con_ajuste_registrado',
                      return_value=[p.inicio + timedelta(days=12)]):
            evaluar_propuestas_vencidas(self.cliente, HOY)
        p.refresh_from_db()
        self.assertEqual(p.resultado, 'validada')
        self.assertTrue(frase_evaluacion(p).startswith(
            'Cuádriceps: propuse −2 series semanales durante 4 semanas y aceptaste. '
            'Funcionó: menos volumen sin perder fuerza (-1,0 % frente a las 4 semanas anteriores).'))
        self.assertIn('Curl femoral tumbado: 40 kg × 10', frase_evaluacion(p))


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
