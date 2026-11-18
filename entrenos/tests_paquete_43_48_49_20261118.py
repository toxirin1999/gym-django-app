"""18-nov-2026 · notas 43 (inconcluso/pendiente) y 48 (sesión evaluadora)."""

from datetime import date, datetime, time, timedelta
from unittest import mock

from django.utils import timezone

from entrenos.models import GymDecisionLog
from entrenos.services import decision_log_service as d
from entrenos.services.aprendizaje_decisiones_service import _sesion_evaluadora, frase_decision
from entrenos.services.cierre_porque_service import comprobaciones_de_hoy
from entrenos.tests_ultima_sesion import Base


def _creada(log, fecha):
    GymDecisionLog.objects.filter(pk=log.pk).update(
        fecha_creacion=timezone.make_aware(datetime.combine(fecha, time(9, 0))))
    log.refresh_from_db()
    return log


class Comun(Base):
    def log(self, origen, fecha, accion='subir_peso', **kw):
        l = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio=self.hack.nombre, ejercicio_normalizado=d.normalizar_ejercicio(self.hack.nombre),
            entreno_origen=origen, accion=accion, motivo='x', peso_anterior=20, valor_cambio=25, **kw)
        return _creada(l, fecha)

    def bloques(self, familias):
        """Bloques.de(fecha) -> familia según un dict {fecha: familia}."""
        def de(f):
            fam = familias.get(f, 'hipertrofia')
            return {'familia': fam, 'nombre': fam.capitalize(), 'semana_plan': 1, 'origen': 'x'}
        return mock.patch('entrenos.services.comparabilidad_service.Bloques.de', side_effect=de)


class SesionEvaluadoraGuardada(Comun):
    def test_la_sesion_que_evalua_queda_guardada_y_es_la_citada(self):
        e0 = self.entreno(date(2026, 11, 2), {self.hack.nombre: '8-12'})
        self.hacer(e0, self.hack, [(20, 10, 7)] * 3)
        log = self.log(e0, date(2026, 11, 2))
        e1 = self.entreno(date(2026, 11, 9), {self.hack.nombre: '8-12'})
        self.hacer(e1, self.hack, [(25, 10, 7)] * 3)
        e2 = self.entreno(date(2026, 11, 16), {self.hack.nombre: '8-12'})
        self.hacer(e2, self.hack, [(25, 12, 7)] * 3)

        def evaluar(lg, ej, tipo):
            d._persistir_evaluacion_final(lg, 'validada', 'ok')
        with self.bloques({}), mock.patch.object(d, '_evaluar_log', side_effect=evaluar):
            d.evaluar_decisiones_para_entreno(e1)
        log.refresh_from_db()
        self.assertEqual(log.entreno_evaluador_id, e1.id)
        # La frase cita la sesión evaluadora (09/11), no otra posterior.
        despues = _sesion_evaluadora(log)
        self.assertEqual(despues['entreno_id'], e1.id)
        self.assertIn('Después (09/11): 25 kg × 10', frase_decision(log))

    def test_veredicto_y_serie_salen_de_la_misma_sesion_aunque_haya_otra_anterior_sin_evaluar(self):
        e0 = self.entreno(date(2026, 11, 2), {self.hack.nombre: '8-12'})
        self.hacer(e0, self.hack, [(20, 10, 7)] * 3)
        log = self.log(e0, date(2026, 11, 2))
        # Evaluada por una sesión posterior (e2) aunque exista otra intermedia (e1) no elegible.
        e1 = self.entreno(date(2026, 11, 9), {self.hack.nombre: '8-12'})
        self.hacer(e1, self.hack, [(30, 5, 9)] * 3)
        e2 = self.entreno(date(2026, 11, 16), {self.hack.nombre: '8-12'})
        self.hacer(e2, self.hack, [(25, 12, 7)] * 3)
        GymDecisionLog.objects.filter(pk=log.pk).update(
            resultado='validada', entreno_evaluador=e2, fecha_evaluacion=timezone.now())
        log.refresh_from_db()
        self.assertEqual(_sesion_evaluadora(log)['entreno_id'], e2.id)
        self.assertIn('Después (16/11): 25 kg × 12', frase_decision(log))

    def test_las_decisiones_antiguas_del_mismo_ejercicio_se_cierran_como_sustituidas(self):
        e0 = self.entreno(date(2026, 10, 20), {self.hack.nombre: '8-12'})
        vieja = self.log(e0, date(2026, 10, 20))
        e1 = self.entreno(date(2026, 11, 2), {self.hack.nombre: '8-12'})
        nueva = self.log(e1, date(2026, 11, 2))
        e2 = self.entreno(date(2026, 11, 9), {self.hack.nombre: '8-12'})
        self.hacer(e2, self.hack, [(25, 10, 7)] * 3)
        with self.bloques({}), mock.patch.object(d, '_evaluar_log', side_effect=lambda lg, ej, t: d._persistir_evaluacion_final(lg, 'validada', 'ok')):
            d.evaluar_decisiones_para_entreno(e2)
        vieja.refresh_from_db(); nueva.refresh_from_db()
        self.assertEqual(nueva.resultado, 'validada')
        self.assertEqual(vieja.resultado, 'neutra')
        self.assertIn('sustituida por otra del 02/11', vieja.notas_resultado)
        # Una decisión cerrada así no cita los datos de ninguna sesión.
        self.assertNotIn('Después', frase_decision(vieja))
        self.assertIn('la decisión del 20/10', frase_decision(vieja))

    def test_un_cambio_de_bloque_entre_decision_y_sesion_la_deja_inconclusa(self):
        e0 = self.entreno(date(2026, 11, 2), {self.hack.nombre: '8-12'})
        log = self.log(e0, date(2026, 11, 2))
        e1 = self.entreno(date(2026, 11, 16), {self.hack.nombre: '3-6'})
        self.hacer(e1, self.hack, [(25, 5, 8)] * 3)
        llamadas = []
        with self.bloques({date(2026, 11, 2): 'hipertrofia', date(2026, 11, 16): 'fuerza'}), \
                mock.patch.object(d, '_evaluar_log', side_effect=lambda *a: llamadas.append(a)):
            d.evaluar_decisiones_para_entreno(e1)
        log.refresh_from_db()
        self.assertEqual(llamadas, [])  # no se evalúa con un objetivo distinto
        self.assertEqual(log.resultado, 'neutra')
        self.assertIn('cambió el bloque', log.notas_resultado)
        self.assertIn('02/11', log.notas_resultado)
        self.assertIn('16/11', log.notas_resultado)

    def test_sin_cambio_de_bloque_no_hay_caducidad_por_dias(self):
        e0 = self.entreno(date(2026, 9, 1), {self.hack.nombre: '8-12'})
        log = self.log(e0, date(2026, 9, 1))
        e1 = self.entreno(date(2026, 11, 16), {self.hack.nombre: '8-12'})
        self.hacer(e1, self.hack, [(25, 10, 7)] * 3)
        with self.bloques({}), mock.patch.object(d, '_evaluar_log', side_effect=lambda lg, ej, t: d._persistir_evaluacion_final(lg, 'validada', 'ok')):
            d.evaluar_decisiones_para_entreno(e1)
        log.refresh_from_db()
        self.assertEqual(log.resultado, 'validada')


class Nota43InconclusoYPendiente(Comun):
    def test_pendiente_no_se_confunde_con_inconcluso(self):
        e0 = self.entreno(date(2026, 11, 2), {self.hack.nombre: '8-12'})
        pendiente = self.log(e0, date(2026, 11, 2))
        e00 = self.entreno(date(2026, 11, 3), {self.hack.nombre: '8-12'})
        inconcluso = self.log(e00, date(2026, 11, 3))
        GymDecisionLog.objects.filter(pk=inconcluso.pk).update(
            resultado='neutra', notas_resultado='Resultado inconcluso: llegabas muy cansado (25 kg × 6; antes 25 × 10)')
        inconcluso.refresh_from_db()
        t_pend, t_inc = frase_decision(pendiente), frase_decision(inconcluso)
        self.assertTrue(t_pend.endswith('Pendiente de comprobar.'))
        self.assertNotIn('inconcluso', t_pend.lower())
        self.assertIn('Resultado inconcluso: llegabas muy cansado', t_inc)
        self.assertNotIn('Resultado inconcluso: resultado inconcluso', t_inc.lower())
        self.assertNotIn('Pendiente', t_inc)

    def test_el_cierre_muestra_la_evaluacion_neutra_con_su_motivo(self):
        e0 = self.entreno(date(2026, 11, 2), {self.hack.nombre: '8-12'})
        self.hacer(e0, self.hack, [(20, 10, 7)] * 3)
        log = self.log(e0, date(2026, 11, 2))
        e1 = self.entreno(date(2026, 11, 9), {self.hack.nombre: '8-12'})
        self.hacer(e1, self.hack, [(25, 6, 9)] * 3)
        GymDecisionLog.objects.filter(pk=log.pk).update(
            resultado='neutra', entreno_evaluador=e1,
            notas_resultado='Resultado inconcluso: llegabas muy cansado (25 kg × 6; antes 25 × 10)')
        items = comprobaciones_de_hoy(self.cliente, e1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['resultado'], 'neutra')
        self.assertIn('Resultado inconcluso: llegabas muy cansado (25 kg × 6; antes 25 × 10)', items[0]['texto'])


class PesoSugeridoEnLaRejilla(Comun):
    def _log(self, anterior, accion='subir_peso', cambio=1):
        from rutinas.models import EjercicioBase
        patcher = mock.patch.object(EjercicioBase, 'incremento_fisico_kg', 5.0)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._n = getattr(self, '_n', 0) + 1
        e = self.entreno(date(2026, 10, 1) + timedelta(days=self._n), {self.hack.nombre: '8-12'})
        return GymDecisionLog(cliente=self.cliente, ejercicio=self.hack.nombre, entreno_origen=e,
                              accion=accion, motivo='x', peso_anterior=anterior, valor_cambio=cambio)

    def test_un_peso_anterior_fuera_de_escala_no_da_un_peso_imposible(self):
        # Sentadilla Hack: máquina de 5 kg. 20,5 + salto no puede dar 25,5.
        self.assertEqual(self._log(20.5).peso_sugerido % 5, 0)
        self.assertEqual(self._log(20.5, 'bajar_peso').peso_sugerido % 5, 0)

    def test_en_escala_el_comportamiento_no_cambia(self):
        self.assertEqual(self._log(20).peso_sugerido, 25)
        self.assertEqual(self._log(25, 'bajar_peso').peso_sugerido, 20)


class GuardaDeBloqueSoloHaciaAdelante(Comun):
    def test_una_sesion_anterior_a_la_decision_no_se_cierra_por_bloque(self):
        # Datos antiguos: la decisión se creó «ahora» pero la sesión es previa; no hay cambio de bloque que juzgar.
        e0 = self.entreno(date(2026, 11, 16), {self.hack.nombre: '8-12'})
        log = self.log(e0, date(2026, 11, 16))
        e1 = self.entreno(date(2026, 10, 10), {self.hack.nombre: '8-12'})
        with self.bloques({date(2026, 11, 16): 'fuerza', date(2026, 10, 10): 'hipertrofia'}):
            self.assertIsNone(d.motivo_no_aplicable(log, e1))


class CasoHistoricoPressFrances(Comun):
    """492: creada el 11/10, evaluada el 17/11 con la sesión del 16/11; la primera posterior era del 19/10."""

    def _escenario(self):
        e0 = self.entreno(date(2026, 10, 11), {self.hack.nombre: '8-12'})
        self.hacer(e0, self.hack, [(25, 16, 8)] * 3)
        log = self.log(e0, date(2026, 10, 11))
        e1 = self.entreno(date(2026, 10, 19), {self.hack.nombre: '8-12'})
        self.hacer(e1, self.hack, [(30, 16, 8)] * 3)            # primera posterior (RPE 8)
        e2 = self.entreno(date(2026, 11, 16), {self.hack.nombre: '8-12'})
        self.hacer(e2, self.hack, [(45, 8, 10)] * 3)            # la que evaluó (RPE 10)
        return log, e1, e2

    def test_sin_sesion_guardada_se_cita_la_ultima_elegible_hasta_la_evaluacion_no_la_primera(self):
        log, e1, e2 = self._escenario()
        GymDecisionLog.objects.filter(pk=log.pk).update(
            resultado='fallida', notas_resultado='RPE 10, por encima del 8',
            fecha_evaluacion=timezone.make_aware(datetime(2026, 11, 17, 10, 0)))
        log.refresh_from_db()
        with self.bloques({}):
            ses = _sesion_evaluadora(log)
            texto = frase_decision(log)
        self.assertEqual(ses['entreno_id'], e2.id)
        self.assertIn('Después (16/11): 45 kg × 8 con RPE 10', texto)
        self.assertNotIn('30 kg × 16', texto)
        self.assertIn('No funcionó', texto)

    def test_si_no_se_puede_identificar_la_sesion_se_dice(self):
        e0 = self.entreno(date(2026, 10, 11), {self.hack.nombre: '8-12'})
        log = self.log(e0, date(2026, 10, 11))
        # Evaluada el 12/10 y ninguna sesión del ejercicio hasta ese día después de la decisión.
        e1 = self.entreno(date(2026, 10, 19), {self.hack.nombre: '8-12'})
        self.hacer(e1, self.hack, [(30, 16, 8)] * 3)
        GymDecisionLog.objects.filter(pk=log.pk).update(
            resultado='fallida', notas_resultado='RPE 10, por encima del 8',
            fecha_evaluacion=timezone.make_aware(datetime(2026, 10, 12, 10, 0)))
        log.refresh_from_db()
        texto = frase_decision(log)
        self.assertNotIn('Después', texto)
        self.assertIn('No consta la sesión que la evaluó.', texto)
        self.assertIn('No funcionó', texto)
