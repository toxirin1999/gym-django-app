"""26-oct-2026 · Repaso del Día 1: notas 1-23 y criterios de entrenador."""

from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase
from django.utils import timezone

from clientes.models import BitacoraDiaria
from entrenos.models import EjercicioRealizado, GymDecisionLog, SerieRealizada
from entrenos.services.cerebro_carga_service import (
    aplicar_decision_carga, decidir_carga, hundimiento_en_sesion, proxima_vez_texto,
)
from entrenos.services.descanso_service import get_descanso_sugerido
from entrenos.services.recuperacion_service import lectura_recuperacion
from entrenos.services.ultima_sesion_service import serie_referencia
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()


def _ej(nombre, rango, rpe=8):
    return {'nombre': nombre, 'repeticiones': rango, 'rpe_objetivo': rpe, 'tipo_progresion': 'peso_reps'}


def _rpe_en_snapshot(entreno, rpes):
    snap = entreno.gym_decision_version.snapshot
    for ej in snap['entrenamiento']['ejercicios']:
        if ej['nombre'] in rpes:
            ej['rpe_objetivo'] = rpes[ej['nombre']]
    entreno.gym_decision_version.snapshot = snap
    entreno.gym_decision_version.save(update_fields=['snapshot'])


class ReglaDeCarga(Base):
    def base(self, nombre, grupo='x'):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular=grupo, tipo_progresion='peso_reps')

    def test_nota22_la_referencia_es_la_mediana(self):
        ref = serie_referencia([
            {'peso': 30, 'reps': 17, 'rpe': 7}, {'peso': 30, 'reps': 19, 'rpe': 9}, {'peso': 30, 'reps': 19, 'rpe': 9},
        ], 15)
        self.assertEqual(int(ref['reps_mediana']), 19)
        b = self.base('Press Francés con Barra Z')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e, b, [(30, 17, 7), (30, 19, 9), (30, 19, 9)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20', rpe=9), HOY)
        self.assertEqual((d['peso'], d['reps']), (30, 20))

    def test_nota11_tope_con_margen_en_todas_dos_reps(self):
        b = self.base('Elevación de Gemelos de Pie (Máquina)')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        _rpe_en_snapshot(e, {b.nombre: 9})
        self.hacer(e, b, [(100, 17, 8)] * 3)
        EjercicioRealizado.objects.filter(entreno=e).update(es_tope_maquina=True)
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20', rpe=9), HOY)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (100, 19, 'tope'))

    def test_nota16_hundimiento_de_golpe_mantiene_el_peso(self):
        b = self.base('Convergent Machine Press')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '12-15'})
        self.hacer(e, b, [(62.5, 14, 8), (62.5, 8, 10), (60, 10, 9), (60, 8, 9)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '12-15'), HOY)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (62.5, 14, 'fatiga'))
        self.assertIn('fue cansancio, no el peso', d['frase'])
        e_hoy = self.entreno(HOY, {b.nombre: '12-15'})
        self.hacer(e_hoy, b, [(62.5, 14, 8), (62.5, 8, 10), (60, 10, 9), (60, 8, 9)])
        texto, accion, efecto = proxima_vez_texto(self.cliente, e_hoy, b.nombre, 'peso_reps', con_efecto=True)
        self.assertEqual((accion, efecto), ('Mantener', 'Repite 62,5 kg'))
        self.assertIn('se hundió a 8', texto)

    def test_un_descenso_gradual_si_baja(self):
        series = [{'peso': 30, 'reps': 15, 'rpe': 8}, {'peso': 30, 'reps': 13, 'rpe': 9}, {'peso': 30, 'reps': 8, 'rpe': 10}]
        self.assertIsNone(hundimiento_en_sesion(series, 15, 9))
        # La primera ya iba por encima del esfuerzo pedido: tampoco cuenta.
        self.assertIsNone(hundimiento_en_sesion(
            [{'peso': 60, 'reps': 14, 'rpe': 10}, {'peso': 60, 'reps': 8, 'rpe': 10}], 12, 8))

    def test_nota1_el_texto_sigue_a_la_regla(self):
        ej = {'peso_kg': 145, 'reps_objetivo_hoy': 14,
              'progresion_motivo': 'Mismo peso: hoy a por 13 reps (la última vez 12); con 15 en todas las series, sube la carga.'}
        aplicar_decision_carga(ej, {'peso': 145.0, 'reps': 14, 'regla': 'mantener',
                                    'frase': 'Mismo peso: hoy a por 14 reps (la última vez 13).'})
        self.assertIn('a por 14', ej['progresion_motivo'])
        # Si el texto ya cuadra, se queda.
        ej2 = {'peso_kg': 30, 'reps_objetivo_hoy': 15, 'progresion_motivo': 'Hoy a por 15 reps.'}
        aplicar_decision_carga(ej2, {'peso': 30.0, 'reps': 15, 'regla': 'mantener', 'frase': 'otra'})
        self.assertEqual(ej2['progresion_motivo'], 'Hoy a por 15 reps.')


class Cierre(Base):
    def test_nota20_compara_con_la_ultima_vez_del_mismo_rango(self):
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes
        b = EjercicioBase.objects.create(nombre='Extensiones de Tríceps con Polea Alta', grupo_muscular='t',
                                         tipo_progresion='peso_reps')
        e0 = self.entreno(HOY - timedelta(days=21), {b.nombre: '15-20'})
        self.hacer(e0, b, [(35, 15, 9)] * 2)
        e1 = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e1, b, [(20, 16, 6), (25, 25, 9)])
        e2 = self.entreno(HOY, {b.nombre: '15-20'})
        self.hacer(e2, b, [(30, 15, 9)] * 2)
        c = _cambios_relevantes(self.cliente, e2, list(EjercicioRealizado.objects.filter(entreno=e2)))[0]
        self.assertEqual(c['tipo'], 'subida')
        self.assertIn('25 × 25 → 30 × 15', c['detalle'])

    def test_nota21_la_mejor_serie(self):
        from entrenos.services.cierre_entrenamiento_service import _comparar_referencias
        b = EjercicioBase.objects.create(nombre='Press Francés con Barra Z', grupo_muscular='t', tipo_progresion='peso_reps')
        e1 = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e1, b, [(30, 16, 9), (30, 16, 8)])
        e2 = self.entreno(HOY, {b.nombre: '15-20'})
        self.hacer(e2, b, [(30, 17, 7), (30, 19, 9), (30, 19, 9)])
        self.assertIn('30 × 16 → 30 × 19 (+3 reps)', _comparar_referencias(e2, e1, b.nombre)['detalle'])

    def test_nota19_juzga_con_el_rpe_del_plan(self):
        from entrenos.services.decision_log_service import evaluar_decisiones_para_entreno
        b = EjercicioBase.objects.create(nombre='Extensiones de Tríceps con Polea Alta', grupo_muscular='t',
                                         tipo_progresion='peso_reps')
        e1 = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e1, b, [(25, 25, 9)])
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio=b.nombre, ejercicio_normalizado='extensiones de triceps con polea alta',
            entreno_origen=e1, peso_anterior=25, reps_anteriores=25, accion='subir_peso', valor_cambio=5,
            motivo='x', motivo_codigo='progresion_peso', estado_aplicacion='aplicada',
        )
        e2 = self.entreno(HOY, {b.nombre: '15-20'})
        _rpe_en_snapshot(e2, {b.nombre: 9})
        self.hacer(e2, b, [(30, 15, 9)] * 2)
        evaluar_decisiones_para_entreno(e2)
        log.refresh_from_db()
        self.assertNotEqual(log.resultado, 'fallida', log.notas_resultado)


class LecturaDelDia(Base):
    def fila(self, dias, **datos):
        f = BitacoraDiaria.objects.create(cliente=self.cliente, **datos)
        BitacoraDiaria.objects.filter(pk=f.pk).update(fecha=HOY - timedelta(days=dias))

    def test_nota2_el_sueno_apuntado_a_mano_no_hace_media(self):
        for d in range(2, 9):
            self.fila(d, horas_sueno=8.1)
        self.fila(1, horas_sueno=7.8, hrv_ms=55, fc_reposo=59)
        self.fila(0, horas_sueno=6.57, hrv_ms=81, fc_reposo=58)
        lectura = lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(lectura['nivel'], 'sin_referencia')
        self.assertNotIn('lo que sueles', lectura['frase'])

    def test_nota3_dice_tambien_lo_bueno(self):
        for d in range(1, 7):
            self.fila(d, horas_sueno=8.0, hrv_ms=55, fc_reposo=59)
        self.fila(0, horas_sueno=5.5, hrv_ms=81, fc_reposo=58)
        lectura = lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(lectura['nivel'], 'ambar')
        self.assertIn('Lo bueno: el reloj te ve bien recuperado', lectura['frase'])


class CriteriosDeEntrenador(Base):
    def test_pecho_ayer_baja_un_punto(self):
        from entrenos.services.criterios_entrenador_service import aplicar_criterios
        dips = EjercicioBase.objects.create(nombre='Dips (Fondos en Pecho)', grupo_muscular='Pecho', tipo_progresion='peso_reps')
        conv = EjercicioBase.objects.create(nombre='Convergent Machine Press', grupo_muscular='Pecho inferior',
                                            tipo_progresion='peso_reps')
        e = self.entreno(HOY - timedelta(days=1), {dips.nombre: '15-20'})
        self.hacer(e, dips, [(80, 16, 7)] * 4)
        plan = [_ej(conv.nombre, '12-15', rpe=8), _ej('Sentadilla Hack', '12-15', rpe=8)]
        aplicadas = aplicar_criterios(self.cliente, plan, HOY)
        self.assertEqual(len(aplicadas), 1)
        self.assertEqual(plan[0]['rpe_objetivo'], 7)
        self.assertEqual(plan[0]['rpe_objetivo_plan'], 8)
        self.assertIn('ayer ya hiciste 4 series de pecho', plan[0]['criterio_entrenador'])
        self.assertEqual(plan[1]['rpe_objetivo'], 8)

    def test_nunca_por_debajo_de_7(self):
        from entrenos.services.criterios_entrenador_service import aplicar_criterios
        dips = EjercicioBase.objects.create(nombre='Dips (Fondos en Pecho)', grupo_muscular='Pecho', tipo_progresion='peso_reps')
        e = self.entreno(HOY - timedelta(days=1), {dips.nombre: '15-20'})
        self.hacer(e, dips, [(80, 16, 7)] * 4)
        plan = [_ej(dips.nombre, '15-20', rpe=7)]
        self.assertEqual(aplicar_criterios(self.cliente, plan, HOY), [])
        self.assertEqual(plan[0]['rpe_objetivo'], 7)

    def test_sueno_corto_con_carga_alta(self):
        from unittest.mock import patch
        from entrenos.services import criterios_entrenador_service as c
        plan = [_ej('Sentadilla Hack', '12-15', rpe=8)]
        with patch.object(c, '_sueno_y_carga', return_value=(6.0, 1.41)):
            c.aplicar_criterios(self.cliente, plan, HOY)
        self.assertEqual(plan[0]['rpe_objetivo'], 7)
        self.assertIn('41 % más de carga', plan[0]['criterio_entrenador'])
        plan = [_ej('Sentadilla Hack', '12-15', rpe=8)]
        with patch.object(c, '_sueno_y_carga', return_value=(6.0, 1.1)):
            c.aplicar_criterios(self.cliente, plan, HOY)
        self.assertEqual(plan[0]['rpe_objetivo'], 8)


class Datos(Base):
    def test_corregir_peso_apuntado(self):
        e = self.entreno(HOY - timedelta(days=1), {self.hack.nombre: '12-15'})
        self.hacer(e, self.hack, [(21, 14, 8)] * 2)
        out = StringIO()
        call_command('corregir_peso_apuntado', self.cliente.id, '--ejercicio', 'sentadilla hack',
                     '--de', '21', '--a', '20', stdout=out)
        self.assertIn('2 series', out.getvalue())
        self.assertEqual(SerieRealizada.objects.filter(peso_kg=21).count(), 2)  # sin --aplicar no cambia
        call_command('corregir_peso_apuntado', self.cliente.id, '--ejercicio', 'Sentadilla Hack',
                     '--de', '21', '--a', '20', '--aplicar', stdout=StringIO())
        self.assertEqual(SerieRealizada.objects.filter(peso_kg=20).count(), 2)
        self.assertEqual(EjercicioRealizado.objects.get(entreno=e).peso_kg, 20)


class Plantillas(SimpleTestCase):
    def test_textos_y_pantallas(self):
        activo = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('function siguientePendiente()', activo)
        self.assertIn('Lo dejo para el final', activo)
        self.assertNotIn('no se guardarán hasta que cierres', activo)
        self.assertIn('TERMINAR EJERCICIO', activo)
        self.assertIn('no sale con este material', activo)
        self.assertIn('Ya bajé el peso una vez', activo)
        self.assertIn('Se hundió por cansancio', activo)
        briefing = Path('entrenos/templates/entrenos/briefing_entrenamiento.html').read_text(encoding='utf-8')
        self.assertIn("estado_sistema.estado != 'EN_MARGEN'", briefing)
        self.assertIn('Tu energía al empezar · 2 semanas', briefing)
        self.assertIn('ej.criterio_entrenador', briefing)
        self.assertIn('ej.repeticiones_plan|default:ej.repeticiones', briefing)

    def test_nota17_press_frances_descansa_1_30(self):
        self.assertEqual(get_descanso_sugerido(nombre='Press Francés con Barra Z', reps='15-20')['label'], '1:30')
        self.assertEqual(get_descanso_sugerido(nombre='Press Inclinado con Mancuernas', reps='15-20')['label'], '2:30')
