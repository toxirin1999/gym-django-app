"""18-nov-2026 · Día 3: sustitución de ejercicio (notas 14, 21 y 23)."""

import json
from types import SimpleNamespace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from decimal import Decimal

from django.http import QueryDict
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from entrenos.models import EjercicioRealizado
from entrenos.services.cierre_entrenamiento_service import _no_hechos, _sustituciones
from entrenos.tests_dia2_20261027 import Comun

HOY = timezone.localdate()


class Sustitucion(Comun):
    def _marcar(self, entreno, nombre, original):
        EjercicioRealizado.objects.filter(entreno=entreno, nombre_ejercicio=nombre).update(sustituye_a=original)

    def test_nota21_sustituido_no_es_sin_hacer(self):
        sissy = self.base('Sissy Squat', 'Cuádriceps')
        hack = self.base('Hack Squat', 'Cuádriceps')
        curl = self.base('Curl Femoral Tumbado', 'Isquios')
        e = self.entreno(HOY, {sissy.nombre: '10-15', curl.nombre: '12-15'})
        self.hacer(e, hack, [(30, 8, 7)] * 3)
        self.hacer(e, curl, [(40, 12, 8)] * 3)
        self._marcar(e, hack.nombre, sissy.nombre)
        ejercicios = list(EjercicioRealizado.objects.filter(entreno=e))
        self.assertEqual(_no_hechos(e, ejercicios), [])
        self.assertEqual(_sustituciones(e, ejercicios), [{'original': 'Sissy Squat', 'nuevo': 'Hack Squat', 'objetivo': ''}])

    def test_varios_del_mismo_grupo_y_uno_realmente_omitido(self):
        sissy = self.base('Sissy Squat', 'Cuádriceps')
        prensa = self.base('Prensa de Piernas', 'Cuádriceps')
        extension = self.base('Extensiones de Cuádriceps', 'Cuádriceps')
        hack = self.base('Hack Squat', 'Cuádriceps')
        e = self.entreno(HOY, {sissy.nombre: '10-15', prensa.nombre: '8-12', extension.nombre: '12-15'})
        self.hacer(e, hack, [(30, 8, 7)] * 3)
        self.hacer(e, extension, [(40, 12, 8)] * 3)
        self._marcar(e, hack.nombre, sissy.nombre)
        ejercicios = list(EjercicioRealizado.objects.filter(entreno=e))
        # El hack sustituye al sissy (lo dijo la pantalla); la prensa, del mismo músculo, no se hizo.
        self.assertEqual(_sustituciones(e, ejercicios), [{'original': 'Sissy Squat', 'nuevo': 'Hack Squat', 'objetivo': ''}])
        self.assertEqual(_no_hechos(e, ejercicios), ['Prensa de Piernas'])

    def test_compartir_musculo_no_basta_para_emparejar(self):
        sissy = self.base('Sissy Squat', 'Cuádriceps')
        hack = self.base('Hack Squat', 'Cuádriceps')
        e = self.entreno(HOY, {sissy.nombre: '10-15'})
        self.hacer(e, hack, [(30, 8, 7)] * 3)          # añadido, sin decir que sustituye a nada
        ejercicios = list(EjercicioRealizado.objects.filter(entreno=e))
        self.assertEqual(_sustituciones(e, ejercicios), [])
        self.assertEqual(_no_hechos(e, ejercicios), ['Sissy Squat'])

    def test_notas14_23_api_dice_si_el_nuevo_lleva_peso(self):
        self.client.force_login(self.cliente.user)
        url = reverse('entrenos:api_alternativas_maquina', args=[self.cliente.id])
        cand = {'cuadriceps': {'aislamiento': ['Hack Squat', 'Sissy Squat']}}
        with patch('analytics.planificador_helms.database.ejercicios.EJERCICIOS_DATABASE', cand), \
                patch('analytics.planificador_helms.utils.helpers.buscar_ejercicio_por_nombre',
                      side_effect=lambda n: {'tipo_progresion': 'peso_reps' if n == 'Hack Squat' else 'progresion_reps'}):
            r = self.client.post(url, json.dumps({'nombre': 'Otro', 'grupo_muscular': 'cuadriceps'}),
                                 content_type='application/json').json()
        por = {a['nombre']: a for a in r['alternativas']}
        self.assertTrue(por['Hack Squat']['usa_peso'])
        self.assertEqual(por['Hack Squat']['tipo_progresion'], 'peso_reps')
        self.assertFalse(por['Sissy Squat']['usa_peso'])

    def test_plantilla_reconstruye_la_tarjeta(self):
        activo = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('function adaptarTarjetaASustituto', activo)
        self.assertIn('adaptarTarjetaASustituto(fid, meta || {}, pesoHistorico);', activo)
        self.assertIn("'_tipo_progresion\"]'", activo)
        self.assertIn('alt.usa_peso === true', activo)
        cierre = Path('entrenos/templates/entrenos/post_entreno_resumen.html').read_text(encoding='utf-8')
        self.assertIn('Cambiado: {{ s.original }}', cierre)
        self.assertIn("_sustituye_a", activo)
        self.assertIn("hidSust.value = _swapNombreOriginal", activo)
        self.assertIn("sustituye_a=request.POST.get(f'{form_id}_sustituye_a'", Path('entrenos/views.py').read_text(encoding='utf-8'))


class Nota22ComprobacionCitaLaSerieDelRecord(SimpleTestCase):
    def _log(self):
        return SimpleNamespace(ejercicio='Elevación de Gemelos en Multipower', accion='subir_peso',
                               peso_sugerido=105, resultado='validada', notas_resultado='',
                               entreno_origen_id=None)

    def _despues(self):
        return {
            'peso': 110.0, 'reps': 15, 'rpe': 7.5, 'entreno_id': 0, 'fecha': HOY,
            'series': [
                {'peso': 105.0, 'reps': 15, 'rpe': 7.0, 'metros': None},
                {'peso': 110.0, 'reps': 15, 'rpe': 8.0, 'metros': None},
            ],
        }

    def test_cita_las_dos_series_con_sus_datos(self):
        from entrenos.services.aprendizaje_decisiones_service import detalle_decision, frase_decision
        frase = frase_decision(self._log(), etiqueta='Hoy', despues=self._despues())
        self.assertIn('Hoy: 105 kg × 15 con RPE 7 y después 110 kg × 15 con RPE 8', frase)
        self.assertIn('y después 110 kg × 15 con RPE 8', detalle_decision(self._log(), self._despues())['ocurrido'])

    def test_sin_serie_mas_pesada_no_anade_nada(self):
        from entrenos.services.aprendizaje_decisiones_service import frase_decision
        despues = self._despues()
        despues['series'] = despues['series'][:1]
        despues['peso'], despues['rpe'] = 105.0, 7.0
        self.assertNotIn('después', frase_decision(self._log(), etiqueta='Hoy', despues=despues))


class Notas9y18Plantilla(SimpleTestCase):
    def test_titulo_con_margen_y_aviso_de_record_al_abrir(self):
        activo = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn("const tituloObj=conMargen?'En objetivo, con margen':'Ejercicio en objetivo';", activo)
        self.assertIn('por debajo del ${rpeObjEj} previsto: te sobró margen.', activo)
        # el aviso «NUEVO PR» se evalúa también con el peso propuesto ya puesto
        self.assertIn("if(m0&&Number.isFinite(v0)&&v0>0){ try{ detectarPR(m0[1],+m0[2],v0); }catch(e){} }", activo)
        # propuesto/escrito = «sería récord»; hecho = «NUEVO PR»
        self.assertIn("'🏆 SERÍA RÉCORD — '", activo)
        self.assertIn('function prDeSerieHecha', activo)
        self.assertIn("🏆 NUEVO PR (antes: ", activo)


class ObjetivoDelHueco(Comun):
    """18-nov-2026: el sustituto hereda el rango de reps y el RPE del hueco del plan."""

    ASIGNADO = {'rango': '12-15', 'reps_objetivo': 12, 'rpe_objetivo': 8.0, 'hereda_de': 'Sissy Squat'}

    def _plan(self, e, ejercicios):
        v = e.gym_decision_version
        v.snapshot = {'entrenamiento': {'ejercicios': ejercicios}}
        v.save(update_fields=['snapshot'])

    def _dia1_fuerza(self):
        """Hack en su día de fuerza: 4-6 reps, objetivo 6."""
        d1 = self.entreno(HOY - timedelta(days=9), {'Sentadilla Hack': '4-6'})
        self._plan(d1, [{'nombre': 'Sentadilla Hack', 'repeticiones': '4-6', 'reps_objetivo': 6, 'rpe_objetivo': 8}])
        self.hacer(d1, self.hack, [(30, 6, 7)] * 3)
        return d1

    def _dia3_sissy_por_hack(self, con_objetivo=True):
        e = self.entreno(HOY, {'Sissy Squat': '12-15'})
        self._plan(e, [{'nombre': 'Sissy Squat', 'repeticiones': '12-15', 'reps_objetivo': 12, 'rpe_objetivo': 8}])
        self.hacer(e, self.hack, [(30, 4, 6), (30, 8, 7), (30, 9, 8)])
        EjercicioRealizado.objects.filter(entreno=e, nombre_ejercicio='Sentadilla Hack').update(
            sustituye_a='Sissy Squat', objetivo_asignado=self.ASIGNADO if con_objetivo else {})
        return e

    def test_el_objetivo_es_el_del_hueco_y_no_el_del_hack_de_otro_dia(self):
        from entrenos.services.decision_log_service import _objetivo_repeticiones_snapshot, _rpe_objetivo_snapshot
        from entrenos.services.ultima_sesion_service import rango_de_sesion
        d1 = self._dia1_fuerza()
        e = self._dia3_sissy_por_hack()
        self.assertEqual(_objetivo_repeticiones_snapshot(e, 'sentadilla hack'), Decimal('12'))
        self.assertEqual(_rpe_objetivo_snapshot(e, 'sentadilla hack'), 8.0)
        self.assertEqual(rango_de_sesion(e, 'Sentadilla Hack'), (12, 15))
        # y el del otro día sigue siendo el suyo
        self.assertEqual(_objetivo_repeticiones_snapshot(d1, 'sentadilla hack'), Decimal('6'))
        self.assertEqual(rango_de_sesion(d1, 'Sentadilla Hack'), (4, 6))

    def test_sin_objetivo_asignado_no_se_inventa_uno(self):
        from entrenos.services.decision_log_service import _objetivo_repeticiones_snapshot
        from entrenos.services.ultima_sesion_service import rango_de_sesion
        self._dia1_fuerza()
        e = self._dia3_sissy_por_hack(con_objetivo=False)
        self.assertIsNone(_objetivo_repeticiones_snapshot(e, 'sentadilla hack'))
        self.assertIsNone(rango_de_sesion(e, 'Sentadilla Hack'))

    def test_la_decision_se_juzga_contra_12_y_no_contra_6(self):
        from entrenos.models import GymDecisionLog
        from entrenos.services.decision_log_service import generar_decisiones_para_entreno
        self._dia1_fuerza()
        e = self._dia3_sissy_por_hack()
        generar_decisiones_para_entreno(e)
        d = GymDecisionLog.objects.get(entreno_origen=e, ejercicio_normalizado='sentadilla hack')
        self.assertNotEqual(d.accion, 'subir_peso')            # 7 de media frente a 12: no supera nada
        self.assertNotIn('frente al objetivo 6', d.motivo)

    def test_un_sustituto_no_cuenta_como_el_mismo_rango_de_otro_dia(self):
        from entrenos.services.ultima_sesion_service import ultima_sesion_mismo_rango
        d1 = self._dia1_fuerza()
        self._dia3_sissy_por_hack()
        lectura = ultima_sesion_mismo_rango(self.cliente, 'Sentadilla Hack', HOY + timedelta(days=4), (4, 6))
        self.assertEqual(lectura['entreno'].pk, d1.pk)          # no la del 18/11, hecha en 12-15

    def test_una_decision_mantener_pendiente_no_bloquea_otros_dias(self):
        from entrenos.models import GymDecisionLog
        from entrenos.services.plan_dinamico_service import _aplicar_progresion_ejecutiva
        self._dia1_fuerza()
        e = self._dia3_sissy_por_hack()
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='sentadilla hack', ejercicio_normalizado='sentadilla hack',
            entreno_origen=e, accion='mantener', peso_anterior=30.0, reps_anteriores=7, rpe_anterior=8.0,
            motivo='Sin objetivo: progresión pendiente')
        ej = {'nombre': 'Sentadilla Hack', 'repeticiones': '4-6', 'peso_kg': 30.0, 'reps_objetivo': 6}
        antes = dict(ej)
        cambios = []
        _aplicar_progresion_ejecutiva(self.cliente, [ej], HOY + timedelta(days=4), cambios)
        self.assertEqual(ej, antes)
        self.assertEqual(cambios, [])

    def test_formulario_guarda_el_objetivo_solo_si_es_sustituto(self):
        from entrenos.views import _objetivo_sustituto_del_formulario
        post = QueryDict(mutable=True)
        post['ej1_objetivo_sustituto'] = json.dumps({'rango': '12-15', 'reps_objetivo': 12, 'rpe_objetivo': 8,
                                                     'hereda_de': 'otro', 'basura': 'x'})
        self.assertEqual(_objetivo_sustituto_del_formulario(post, 'ej1', 'Sissy Squat'),
                         {'rango': '12-15', 'reps_objetivo': 12, 'rpe_objetivo': 8.0, 'hereda_de': 'Sissy Squat'})
        self.assertEqual(_objetivo_sustituto_del_formulario(post, 'ej1', ''), {})
        post['ej2_objetivo_sustituto'] = '{no es json'
        self.assertEqual(_objetivo_sustituto_del_formulario(post, 'ej2', 'Sissy Squat'), {})
        post['ej3_objetivo_sustituto'] = json.dumps({'rango': '12; DROP', 'reps_objetivo': 9999, 'rpe_objetivo': 40})
        self.assertEqual(_objetivo_sustituto_del_formulario(post, 'ej3', 'Sissy Squat'), {})

    def test_el_cierre_dice_el_objetivo_del_hueco(self):
        self._dia1_fuerza()
        e = self._dia3_sissy_por_hack()
        ejercicios = list(EjercicioRealizado.objects.filter(entreno=e))
        self.assertEqual(_sustituciones(e, ejercicios), [
            {'original': 'Sissy Squat', 'nuevo': 'Sentadilla Hack', 'objetivo': '12-15 reps · RPE 8'}])

    def test_api_propone_el_peso_para_el_rango_del_hueco(self):
        self._dia1_fuerza()                                     # 30 kg × 6 en 4-6
        self.client.force_login(self.cliente.user)
        url = reverse('entrenos:api_alternativas_maquina', args=[self.cliente.id])
        cand = {'cuadriceps': {'aislamiento': ['Sentadilla Hack']}}
        with patch('analytics.planificador_helms.database.ejercicios.EJERCICIOS_DATABASE', cand), \
                patch('analytics.planificador_helms.utils.helpers.buscar_ejercicio_por_nombre',
                      side_effect=lambda n: {'tipo_progresion': 'peso_reps'}):
            r = self.client.post(url, json.dumps({'nombre': 'Sissy Squat', 'grupo_muscular': 'cuadriceps',
                                                  'rango': '12-15', 'rpe_objetivo': 8}),
                                 content_type='application/json').json()
        alt = r['alternativas'][0]
        self.assertEqual(alt['peso_historico_kg'], 30.0)        # la última vez, tal cual
        self.assertLess(alt['peso_hueco_kg'], 30.0)             # para 12-15 reps se carga menos
        self.assertIn('12-15', alt['peso_hueco_motivo'])

    def test_plantilla_muestra_y_guarda_el_objetivo(self):
        activo = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('function objetivoDelHueco', activo)
        self.assertIn('function anotarObjetivoHeredado', activo)
        self.assertIn('_objetivo_sustituto', activo)
        self.assertIn('sa-obj-heredado', activo)
        self.assertIn('Objetivo del hueco de ', activo)
        self.assertIn("rango: (objetivoDelHueco(formId, nombre).rango || '')", activo)
        self.assertIn('const objetivoHueco = objetivoDelHueco(fid, _swapNombreOriginal);', activo)
        self.assertIn('objetivoHueco.reps_objetivo || repsHistorico', activo)
        cierre = Path('entrenos/templates/entrenos/post_entreno_resumen.html').read_text(encoding='utf-8')
        self.assertIn('objetivo del hueco: {{ s.objetivo }}', cierre)
