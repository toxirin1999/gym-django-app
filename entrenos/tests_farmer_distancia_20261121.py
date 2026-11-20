"""21-nov-2026 (N1): el Farmer se evalua por metros y carga comparable.

Caso real: Dia 4 (20/11), 3 x 72 m con 36 kg por mano tras 67 m (objetivo 67 + 5 = 72).
La evaluacion decia «mismo rendimiento en el tope» porque comparaba repeticiones (0) con el +5.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog, SerieRealizada
from entrenos.services.aprendizaje_decisiones_service import describir_accion, frase_decision
from entrenos.services.decision_log_service import (
    distancia_de_partida, evaluar_decisiones_para_entreno, evaluar_tope_distancia, objetivo_metros,
)
from rutinas.models import EjercicioBase, Rutina


class FarmerDistanciaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('farmer-n1', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='R farmer')
        self.base, _ = EjercicioBase.objects.get_or_create(
            nombre='Farmer Walk', defaults={'grupo_muscular': 'full_body', 'tipo_progresion': 'progresion_distancia'})
        self.base.tipo_progresion = 'progresion_distancia'
        self.base.save()

    def _entreno(self, dia, series, rpe=7):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 11, dia))
        EjercicioRealizado.objects.create(
            entreno=e, nombre_ejercicio='Farmer Walk', peso_kg=max(p for p, _ in series), series=len(series),
            repeticiones=0, rpe=rpe, completado=True, fallo_muscular=False, es_tope_maquina=True)
        for n, (peso, metros) in enumerate(series, 1):
            SerieRealizada.objects.create(entreno=e, ejercicio=self.base, serie_numero=n, repeticiones=0,
                                          distancia_metros=metros, peso_kg=peso, rpe_real=rpe, completado=True)
        return e

    def _log(self, origen, **kw):
        datos = dict(cliente=self.cliente, ejercicio='farmer walk', ejercicio_normalizado='farmer walk', accion='subir_reps', peso_anterior=36,
                     valor_cambio=5, reps_anteriores=0, motivo_codigo='tope_maquina', entreno_origen=origen,
                     motivo='Tope de peso alcanzado — progresión por distancia (+5 m)')
        datos.update(kw)
        return GymDecisionLog.objects.create(**datos)

    def _evaluar(self, log, nueva):
        evaluar_decisiones_para_entreno(nueva)
        log.refresh_from_db()
        return log

    def test_72_m_con_objetivo_72_es_validada_y_cita_metros(self):
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        nueva = self._entreno(20, [(36, 72)] * 3)
        log = self._evaluar(log, nueva)
        self.assertEqual(log.resultado, 'validada')
        self.assertIn('72 m', log.notas_resultado)
        self.assertIn('3 series', log.notas_resultado)
        self.assertIn('antes 67 m', log.notas_resultado)
        self.assertNotIn('Mismo rendimiento', log.notas_resultado)

    def test_una_serie_corta_no_valida(self):
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        log = self._evaluar(log, self._entreno(20, [(36, 72), (36, 72), (36, 69)]))
        self.assertEqual(log.resultado, 'neutra')
        self.assertIn('no en todas', log.notas_resultado)

    def test_mejora_sin_llegar_al_objetivo(self):
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        log = self._evaluar(log, self._entreno(20, [(36, 70)] * 3))
        self.assertEqual(log.resultado, 'neutra')
        self.assertIn('Mejoró de 67 a 70 m', log.notas_resultado)
        self.assertIn('72 m', log.notas_resultado)

    def test_carga_distinta_no_es_comparable(self):
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        log = self._evaluar(log, self._entreno(20, [(32, 80)] * 3))
        self.assertEqual(log.resultado, 'neutra')
        self.assertIn('no son comparables', log.notas_resultado)

    def test_menos_metros_es_fallida(self):
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        log = self._evaluar(log, self._entreno(20, [(36, 60)] * 3))
        self.assertEqual(log.resultado, 'fallida')

    def test_log_heredado_con_metros_en_reps_anteriores(self):
        log = self._log(None, reps_anteriores=47, peso_anterior=36)
        self.assertEqual(distancia_de_partida(log), 47)
        self.assertEqual(int(objetivo_metros(log)), 52)

    def test_sin_partida_no_inventa(self):
        log = self._log(None)
        nueva = self._entreno(20, [(36, 72)] * 3)
        resultado, notas = evaluar_tope_distancia(log, nueva.ejercicios_realizados.first())
        self.assertEqual(resultado, 'neutra')
        self.assertIn('No consta la distancia de partida', notas)

    def test_frase_cita_el_objetivo_en_metros_y_el_dato_de_hoy(self):
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        self.assertEqual(describir_accion(log), 'subí el objetivo a 72 m')
        log = self._evaluar(log, self._entreno(20, [(36, 72)] * 3))
        frase = frase_decision(log, etiqueta='Hoy')
        self.assertIn('subí el objetivo a 72 m', frase)
        self.assertIn('Hoy: 36 kg × 72 m en 3 series', frase)
        self.assertIn('Funcionó', frase)
        self.assertNotIn('a 5 m', frase)
        self.assertNotIn('inconcluso', frase)

    def test_sin_partida_la_frase_dice_el_incremento_no_un_objetivo(self):
        log = self._log(None)
        self.assertEqual(describir_accion(log), 'subí la distancia 5 m')


class FarmerPrescripcionYSeriesTests(FarmerDistanciaTests):
    """Objetivo y numero de series realmente prescritos; casos opcionales, incompletos y adicionales.

    La regla de progreso no cambia: todas las series completadas a la carga maxima >= objetivo.
    Lo que cambio fue la unidad (m en vez de reps), que hizo estricta una puerta que con el
    objetivo 5 era trivial.
    """

    def _version(self, entreno, objetivo, series):
        from entrenos.models import GymDecisionVersion
        v = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=entreno.fecha, version=1, decision_id=f'd{entreno.pk}',
            origen='generada', fingerprint='f' * 64, base_fingerprint='b' * 64, postura='normal',
            snapshot={'entrenamiento': {'ejercicios': [
                {'nombre': 'Farmer Walk', 'reps_objetivo': objetivo, 'series': series}]}})
        EntrenoRealizado.objects.filter(pk=entreno.pk).update(gym_decision_version=v)

    def test_usa_el_objetivo_prescrito_si_es_una_cifra_de_metros(self):
        log = self._log(self._entreno(12, [(36, 67)] * 3))
        nueva = self._entreno(20, [(36, 72)] * 3)
        self._version(nueva, 75, 3)
        log = self._evaluar(log, nueva)
        self.assertEqual(log.resultado, 'neutra')  # 72 < 75 prescrito
        self.assertIn('75 m', log.notas_resultado)

    def test_un_objetivo_de_5_del_contrato_antiguo_no_vale_y_se_calcula(self):
        from entrenos.services.decision_log_service import prescripcion_distancia, normalizar_ejercicio
        nueva = self._entreno(20, [(36, 72)] * 3)
        self._version(nueva, 5, 3)
        nueva.refresh_from_db()
        obj, previstas, fuente = prescripcion_distancia(nueva, normalizar_ejercicio('Farmer Walk'), 67, 5)
        self.assertEqual((obj, previstas, fuente), (72, 3, 'calculado'))

    def test_series_incompletas_se_dicen_pero_la_regla_es_la_misma(self):
        log = self._log(self._entreno(12, [(36, 67)] * 3))
        nueva = self._entreno(20, [(36, 72)] * 2)  # prescritas 3, hechas 2
        self._version(nueva, 72, 3)
        log = self._evaluar(log, nueva)
        self.assertEqual(log.resultado, 'validada')
        self.assertIn('2 de las 3 series previstas', log.notas_resultado)

    def test_serie_adicional_corta_cuenta_como_cualquier_otra(self):
        log = self._log(self._entreno(12, [(36, 67)] * 3))
        nueva = self._entreno(20, [(36, 72)] * 3 + [(36, 60)])  # una extra, mas corta
        self._version(nueva, 72, 3)
        log = self._evaluar(log, nueva)
        self.assertEqual(log.resultado, 'neutra')
        self.assertIn('no en todas', log.notas_resultado)

    def test_serie_adicional_que_llega_no_cambia_el_resultado(self):
        log = self._log(self._entreno(12, [(36, 67)] * 3))
        nueva = self._entreno(20, [(36, 72)] * 4)
        self._version(nueva, 72, 3)
        log = self._evaluar(log, nueva)
        self.assertEqual(log.resultado, 'validada')
        self.assertIn('4 de las 3 series previstas', log.notas_resultado)

    def test_serie_de_aproximacion_no_cuenta(self):
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        nueva = self._entreno(20, [(36, 72)] * 3)
        SerieRealizada.objects.create(entreno=nueva, ejercicio=self.base, serie_numero=9, repeticiones=0,
                                      distancia_metros=20, peso_kg=18, rpe_real=3, completado=True,
                                      es_aproximacion=True)
        log = self._evaluar(log, nueva)
        self.assertEqual(log.resultado, 'validada')


class VistaPreviaSoloLecturaTests(FarmerDistanciaTests):
    def test_la_vista_previa_no_modifica_nada_y_enseña_el_cambio(self):
        from io import StringIO
        from django.core.management import call_command
        origen = self._entreno(12, [(36, 67)] * 3)
        log = self._log(origen)
        nueva = self._entreno(20, [(36, 72)] * 3)
        # evaluacion antigua errada, como en produccion
        GymDecisionLog.objects.filter(pk=log.pk).update(
            resultado='neutra', notas_resultado='Mismo rendimiento en el tope; aún no alcanzó el objetivo',
            entreno_evaluador=nueva)
        antes = list(GymDecisionLog.objects.filter(pk=log.pk).values())
        out = StringIO()
        call_command('previsualizar_evaluacion_distancia', cliente=self.cliente.id, stdout=out)
        texto = out.getvalue()
        self.assertIn('SOLO LECTURA', texto)
        self.assertIn('CAMBIARIA', texto)
        self.assertIn('validada', texto)
        self.assertIn('objetivo: 72', texto)
        self.assertEqual(list(GymDecisionLog.objects.filter(pk=log.pk).values()), antes)


class PlanDinamicoFarmerTests(FarmerDistanciaTests):
    def test_el_plan_guarda_el_objetivo_en_metros_no_el_salto(self):
        from unittest.mock import patch
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        origen = self._entreno(12, [(36, 67)] * 3)
        self._log(origen)
        ejercicios = [{'nombre': 'Farmer Walk', 'grupo_muscular': 'full_body', 'tipo_ejercicio': 'accesorio',
                       'tipo_progresion': 'progresion_distancia', 'peso_kg': 36, 'series': 3,
                       'repeticiones': '20-30', 'rpe_objetivo': 8}]
        permiso = {'accion': 'progresion_permitida', 'motivo': 'ok', 'mensaje': '', 'aplica_a_principales': False,
                   'aplica_a_accesorios': False, 'hay_datos_semana': True}
        with patch('entrenos.services.progresion_contextual_service.evaluar_permiso_progresion', return_value=permiso), \
                patch('entrenos.services.decision_log_service.reconciliar_progresiones_distancia_heredadas'), \
                patch('entrenos.services.briefing_service.necesita_deload_gym', return_value=False):
            mod, _ = aplicar_plan_dinamico(self.cliente, ejercicios, date(2026, 11, 20))
        ej = mod[0]
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertEqual(ej['reps_objetivo'], 72)
        self.assertEqual(ej['progresion_motivo'], 'Hoy a por 72 m (la última vez 67).')
        self.assertEqual(ej['repeticiones_plan'], '20-30')
