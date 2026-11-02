"""2-nov-2026 · Recorrido de paneles: propuesta en descarga, decisiones, revisión y perfil."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionLog, PropuestaZonaGym, SemanaPlanGym
from entrenos.tests_decision_log_progresion_distancia import DecisionLogProgresionDistanciaBase
from rutinas.models import EjercicioBase

LUNES = date(2026, 11, 2)


class PropuestaEnDescarga(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='paneles', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'P'})
        inicio = date(2026, 10, 14)
        self.p = PropuestaZonaGym.objects.create(
            cliente=self.cliente, zona='isquios', ejercicios=['Curl Femoral Tumbado'], series_extra=2,
            direccion='subir', semanas=4, texto='x', estado=PropuestaZonaGym.ESTADO_ACEPTADA,
            inicio=inicio, fin=inicio + timedelta(days=27),
        )
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES, semana_plan=44, descarga=True,
                                     origen='descarga_programada')

    def test_se_pausa_y_se_alarga_una_semana(self):
        from entrenos.services.propuesta_zona_service import propuesta_visible
        v = propuesta_visible(self.cliente, LUNES)
        self.assertTrue(v['pausa'])
        self.assertEqual(v['semana'], 3)
        self.p.refresh_from_db()
        self.assertEqual(self.p.fin, date(2026, 11, 17))
        # La semana siguiente sigue donde estaba, sin contar la descarga.
        despues = propuesta_visible(self.cliente, LUNES + timedelta(days=7))
        self.assertFalse(despues['pausa'])
        self.assertEqual(despues['semana'], 3)

    def test_en_la_descarga_no_suma_series(self):
        from entrenos.services.volumen_grupo_service import series_por_grupo
        self.assertNotIn('isquios', series_por_grupo(self.cliente, LUNES + timedelta(days=1)))
        self.assertEqual(series_por_grupo(self.cliente, LUNES + timedelta(days=7)).get('isquios'), 2)

    def test_alargar_es_idempotente(self):
        from entrenos.services.propuesta_zona_service import sincronizar_pausas
        sincronizar_pausas(self.cliente)
        sincronizar_pausas(self.cliente)
        self.p.refresh_from_db()
        self.assertEqual(self.p.fin, date(2026, 11, 17))


class SubirRepsSinLlegar(DecisionLogProgresionDistanciaBase):
    def test_sube_pero_no_llega_al_objetivo_no_es_funciono(self):
        from entrenos.services.decision_log_service import evaluar_decisiones_para_entreno
        EjercicioBase.objects.get_or_create(
            nombre='Abducción de Cadera en Máquina',
            defaults={'grupo_muscular': 'gluteos', 'tipo_progresion': 'peso_reps'},
        )
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='abducción de cadera en máquina', accion='subir_reps',
            peso_anterior=60, valor_cambio=3, reps_anteriores=19, motivo='x', resultado=None,
        )
        entreno = self._entreno(self.hoy)
        self._ejercicio_realizado(entreno, nombre='Abducción de Cadera en Máquina', peso_kg=60,
                                  repeticiones=20, rpe=8.0)
        evaluar_decisiones_para_entreno(entreno)
        log.refresh_from_db()
        self.assertEqual(log.resultado, 'neutra')
        self.assertIn('sin llegar a las 22', log.notas_resultado)


class RevisionBloque(TestCase):
    def test_el_bloque_empieza_antes_del_primer_registro(self):
        from entrenos.services.periodizacion_dinamica_service import _periodizacion
        from entrenos.services.revision_bloque_service import _bloques_de_registros
        per = _periodizacion()
        bloque = next(b for b in per if len(b.get('semanas') or []) >= 5 and b['fase'] != 'descarga')
        sem = bloque['semanas']
        user = User.objects.create_user(username='revision', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'R'})
        lunes0 = date(2026, 10, 12)
        regs = [SemanaPlanGym.objects.create(cliente=cliente, lunes=lunes0 + timedelta(days=7 * i),
                                             semana_plan=sem[2 + i], origen='avance')
                for i in range(len(sem) - 2)]
        regs.append(SemanaPlanGym.objects.create(
            cliente=cliente, lunes=lunes0 + timedelta(days=7 * len(regs)), semana_plan=sem[-1] + 1,
            descarga=True, origen='descarga_programada'))
        g = _bloques_de_registros(regs, per)[0]
        self.assertEqual(g['inicio'], lunes0 - timedelta(days=14))
        self.assertEqual(g['semanas_reales'], len(sem))
        self.assertEqual(g['descargas'], 1)
        self.assertEqual(g['fin_contenido'], lunes0 + timedelta(days=7 * (len(sem) - 2) - 1))


from entrenos.tests_ultima_sesion import Base as BaseSesion  # noqa: E402


class EncogimientosArriba(BaseSesion):
    def test_primera_serie_por_encima_del_plan_no_baja_el_peso(self):
        from entrenos.services.decision_log_service import generar_decisiones_para_entreno
        b = EjercicioBase.objects.create(nombre='Encogimientos con Barra', grupo_muscular='Trapecio',
                                         tipo_progresion='peso_reps')
        e = self.entreno(LUNES - timedelta(days=2), {b.nombre: '15-20'})
        v = e.gym_decision_version
        v.snapshot = {'entrenamiento': {'ejercicios': [{'nombre': b.nombre, 'repeticiones': '15-20',
                                                       'peso_kg': 110}]}}
        v.save(update_fields=['snapshot'])
        self.hacer(e, b, [(120, 10, 9), (110, 12, 9), (110, 12, 9)])
        generar_decisiones_para_entreno(e)
        log = GymDecisionLog.objects.filter(cliente=self.cliente, ejercicio__icontains='encogimientos').first()
        self.assertIsNotNone(log)
        self.assertNotEqual(log.accion, 'bajar_peso')
        self.assertIn('por encima de los 110', log.motivo)


class PerfilFuerza(BaseSesion):
    def test_misma_fuente_que_la_evolucion_y_sin_ejercicios_de_tiempo(self):
        from clientes.views import _perfil_fuerza_90d
        plancha = EjercicioBase.objects.create(nombre='Plancha (Plank)', grupo_muscular='core',
                                               tipo_progresion='progresion_tiempo')
        e = self.entreno(LUNES - timedelta(days=5), {self.hack.nombre: '10-15', plancha.nombre: '30-60'})
        self.hacer(e, self.hack, [(100, 10, 8)] * 3)
        self.hacer(e, plancha, [(20, 60, 7)] * 2)
        perfil = _perfil_fuerza_90d(self.cliente, LUNES)
        nombres = [p['ejercicio'] for p in perfil]
        self.assertIn(self.hack.nombre, nombres)
        self.assertNotIn(plancha.nombre, nombres)


class Comandos(BaseSesion):
    def test_los_comandos_corren(self):
        from io import StringIO
        from django.core.management import call_command
        e = self.entreno(LUNES - timedelta(days=5), {self.gemelos.nombre: '10-15'})
        self.hacer(e, self.gemelos, [(100, 12, 8)] * 2)
        out = StringIO()
        call_command('ver_records_dudosos', self.cliente.id, stdout=out)
        self.assertIn('== Elevación de Gemelos en Prensa', out.getvalue())
        out = StringIO()
        call_command('revisar_subidas_reps', self.cliente.id, stdout=out)
        self.assertIn('0 por corregir', out.getvalue())
