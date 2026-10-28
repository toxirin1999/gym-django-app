"""27-oct-2026 · Repaso del Día 2: notas 2-23 y reglas E1/E2/E4/E5."""

import json
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada
from entrenos.services import criterios_entrenador_service as crit
from entrenos.services.cerebro_carga_service import (
    aplicar_decision_carga, decidir_carga, hecho_fuera_de_orden, proxima_vez_texto,
)
from entrenos.services.ultima_sesion_service import anotar_ultima_vez
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()


def _ej(nombre, rango, rpe=8, **extra):
    return {'nombre': nombre, 'repeticiones': rango, 'rpe_objetivo': rpe, 'tipo_progresion': 'peso_reps', **extra}


class Comun(Base):
    def base(self, nombre, grupo='x'):
        b, _ = EjercicioBase.objects.get_or_create(
            nombre=nombre, defaults={'grupo_muscular': grupo, 'tipo_progresion': 'peso_reps'})
        return b

    def energia(self, e, valor):
        EntrenoRealizado.objects.filter(pk=e.pk).update(energia_pre_sesion=valor)
        e.refresh_from_db()


class ReglaDeCarga(Comun):
    def test_nota4_caida_de_cuatro_es_cansancio(self):
        b = self.base('Machine Shoulder Press')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e, b, [(40, 16, 8), (40, 12, 10), (35, 10, 10)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20'), HOY)
        self.assertEqual((d['peso'], d['regla']), (40, 'fatiga'))

    def test_nota4_vuelve_al_peso_de_antes(self):
        b = self.base('Machine Shoulder Press')
        e1 = self.entreno(HOY - timedelta(days=8), {b.nombre: '15-20'})
        self.hacer(e1, b, [(40, 16, 8), (40, 12, 10), (35, 10, 10)])
        e2 = self.entreno(HOY - timedelta(days=1), {b.nombre: '15-20'})
        self.hacer(e2, b, [(35, 15, 8)] * 3)
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20'), HOY)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (40, 15, 'volver'))
        texto, accion, efecto = proxima_vez_texto(self.cliente, e2, b.nombre, 'peso_reps', con_efecto=True)
        self.assertEqual(efecto, 'Vuelve a 40 kg')

    def test_caida_gradual_no_vuelve(self):
        b = self.base('Curl Martillo')
        e1 = self.entreno(HOY - timedelta(days=8), {b.nombre: '15-20'})
        self.hacer(e1, b, [(30, 15, 8), (30, 13, 9), (30, 8, 10)])
        e2 = self.entreno(HOY - timedelta(days=1), {b.nombre: '15-20'})
        self.hacer(e2, b, [(25, 15, 8)] * 3)
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20'), HOY)
        self.assertNotEqual(d['regla'], 'volver')
        self.assertEqual(d['peso'], 25)

    def test_nota14_fuera_de_orden_no_baja(self):
        jalon, remo = self.base('Jalón al Pecho', 'Espalda'), self.base('Remo con Mancuerna a una mano', 'Espalda')
        e = self.entreno(HOY - timedelta(days=1), {jalon.nombre: '12-15', remo.nombre: '12-15'})
        self.hacer(e, remo, [(20, 14, 8)] * 3)        # el remo, que iba detrás, primero
        self.hacer(e, jalon, [(50, 15, 9), (50, 15, 9), (50, 12, 9), (50, 9, 9)])
        self.assertTrue(hecho_fuera_de_orden(e, jalon.nombre))
        self.assertFalse(hecho_fuera_de_orden(e, remo.nombre))
        d = decidir_carga(self.cliente, _ej(jalon.nombre, '12-15'), HOY)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (50, 15, 'fatiga'))
        self.assertIn('fuera de su orden', d['frase'])

    def test_e1_dia_de_energia_baja_no_baja(self):
        b = self.base('Curl Femoral Tumbado')
        for i, dias in enumerate((12, 10, 8)):
            prev = self.entreno(HOY - timedelta(days=dias), {})
            self.energia(prev, 7)
        e = self.entreno(HOY - timedelta(days=1), {b.nombre: '12-15'})
        self.energia(e, 5)
        self.hacer(e, b, [(40, 14, 9), (40, 14, 9), (40, 7, 9)])
        d = decidir_carga(self.cliente, _ej(b.nombre, '12-15', rpe=9), HOY)
        self.assertEqual((d['peso'], d['reps']), (40, 15))
        self.assertIn('energía 5 frente a tu 7 habitual', d['frase'])

    def test_e2_pallof_al_tope_pausa(self):
        b = self.base('Pallof Press', 'Core')
        e = self.entreno(HOY - timedelta(days=3), {b.nombre: '15-20'})
        self.hacer(e, b, [(25, 20, 8)] * 3)
        d = decidir_carga(self.cliente, _ej(b.nombre, '15-20'), HOY)
        self.assertEqual((d['peso'], d['reps']), (25, 20))
        self.assertIn('aguanta 2 s', d['frase'])

    def test_nota3_texto_mismo_peso_se_cambia_si_baja(self):
        ej = {'peso_kg': 70, 'reps_objetivo_hoy': 15,
              'progresion_motivo': 'Mismo peso: hoy a por 15 reps (la última vez 14).'}
        aplicar_decision_carga(ej, {'peso': 70.0, 'reps': 15, 'regla': 'bajar',
                                    'frase': 'La última vez 75 kg × 16, pero después 70 kg × 11: hoy 70 kg.'})
        self.assertTrue(ej['progresion_motivo'].startswith('La última vez 75'))

    def test_nota3_sin_aviso_por_la_serie_de_despues(self):
        b = self.base('Crunch en Polea (Cable Crunch)', 'Core')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e, b, [(75, 16, 9), (75, 16, 9), (75, 11, 10), (70, 11, 10)])
        ej = _ej(b.nombre, '15-20', rpe=9, peso_kg=70)
        anotar_ultima_vez(self.cliente, ej, HOY)
        self.assertNotIn('aviso_coherencia', ej)


class Criterios(Comun):
    def test_e1_variabilidad_baja(self):
        plan = [_ej('Sentadilla Hack', '12-15', rpe=8)]
        with patch.object(crit, '_variabilidad_baja', return_value='tu variabilidad cardiaca de hoy (32 ms) '
                          'está un 40 % por debajo de lo normal en ti'), \
                patch.object(crit, '_sueno_y_carga', return_value=(7.9, 1.1)):
            crit.aplicar_criterios(self.cliente, plan, HOY)
        self.assertEqual(plan[0]['rpe_objetivo'], 7)
        self.assertIn('32 ms', plan[0]['criterio_entrenador'])

    def test_nota2_energia_baja_baja_rpe_y_repite_reps(self):
        b = self.base('Jalón al Pecho', 'Espalda')
        for dias in (12, 10, 8):
            self.energia(self.entreno(HOY - timedelta(days=dias), {}), 7)
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '12-15'})
        self.hacer(e, b, [(50, 14, 8)] * 3)
        plan = [_ej(b.nombre, '12-15', rpe=8, peso_kg=50, reps_objetivo_hoy=15)]
        frase = crit.aplicar_energia(self.cliente, plan, HOY, 5)
        self.assertIn('energía 5 frente a tu 7 habitual', frase)
        self.assertEqual((plan[0]['rpe_objetivo'], plan[0]['reps_objetivo_hoy']), (7, 14))
        self.assertIsNone(crit.aplicar_energia(self.cliente, [_ej(b.nombre, '12-15')], HOY, 6))


class Cierre(Comun):
    def test_notas_18_21_22(self):
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes, _no_hechos
        crunch = self.base('Crunch en Polea (Cable Crunch)', 'Core')
        femoral = self.base('Curl Femoral Tumbado', 'Isquios')
        rumano = self.base('Peso Muerto Rumano', 'Isquios')
        e1 = self.entreno(HOY - timedelta(days=7), {crunch.nombre: '15-20', femoral.nombre: '12-15'})
        self.hacer(e1, crunch, [(75, 16, 9), (75, 16, 9), (75, 11, 10)])
        self.hacer(e1, femoral, [(40, 13, 9)] * 3)
        e2 = self.entreno(HOY, {crunch.nombre: '15-20', rumano.nombre: '12-15', femoral.nombre: '12-15'})
        snap = e2.gym_decision_version.snapshot
        snap['entrenamiento']['ejercicios'][0]['peso_kg'] = 70
        e2.gym_decision_version.snapshot = snap
        e2.gym_decision_version.save(update_fields=['snapshot'])
        self.hacer(e2, crunch, [(70, 15, 9)] * 4)
        self.hacer(e2, femoral, [(40, 14, 9)] * 3)
        self.hacer(e2, femoral, [(40, 14, 8), (40, 14, 8), (40, 7, 9)])
        ejercicios = list(EjercicioRealizado.objects.filter(entreno=e2))
        cambios = _cambios_relevantes(self.cliente, e2, ejercicios)
        nombres = [c['nombre'] for c in cambios]
        self.assertEqual(nombres.count('Curl Femoral Tumbado'), 1)
        c = next(c for c in cambios if c['nombre'] == crunch.nombre)
        self.assertEqual(c['tipo'], 'mantenida')
        self.assertIn('ajuste del plan', c['detalle'])
        self.assertEqual(_no_hechos(e2, ejercicios), ['Peso Muerto Rumano'])


class Datos(Comun):
    def test_nota17_corregir_solo_un_dia(self):
        b = self.base('Curl Femoral Tumbado', 'Isquios')
        e0 = self.entreno(HOY - timedelta(days=30), {b.nombre: '12-15'})
        self.hacer(e0, b, [(60, 10, 9)])
        e = self.entreno(HOY, {b.nombre: '12-15'})
        self.hacer(e, b, [(60, 14, 8), (60, 14, 8), (60, 7, 9)])
        call_command('corregir_peso_apuntado', self.cliente.id, '--ejercicio', b.nombre, '--de', '60', '--a', '40',
                     '--fecha', HOY.isoformat(), '--aplicar', stdout=StringIO())
        self.assertEqual(SerieRealizada.objects.filter(entreno=e, peso_kg=40).count(), 3)
        self.assertEqual(SerieRealizada.objects.filter(entreno=e0, peso_kg=60).count(), 1)


class Alternativas(Comun):
    def test_nota15_16_alternativas(self):
        femoral = self.base('Curl Femoral Tumbado', 'Isquios')
        e = self.entreno(HOY - timedelta(days=5), {femoral.nombre: '12-15'})
        self.hacer(e, femoral, [(40, 13, 9)] * 3)
        self.client.force_login(self.cliente.user)
        url = reverse('entrenos:api_alternativas_maquina', args=[self.cliente.id])
        candidatos = {'isquiotibiales': {'compuesto_principal': ['Peso Muerto Rumano', 'Curl Femoral Tumbado',
                                                                  'Buenos Días (Good Mornings)', 'Curl Nórdico']}}
        with patch('analytics.planificador_helms.database.ejercicios.EJERCICIOS_DATABASE', candidatos):
            r = self.client.post(url, json.dumps({'nombre': 'Peso Muerto Rumano', 'grupo_muscular': 'isquiotibiales',
                                                  'excluir': ['Curl Femoral Tumbado']}),
                                 content_type='application/json').json()
            nombres = [a['nombre'] for a in r['alternativas']]
            self.assertNotIn('Curl Femoral Tumbado', nombres)
            r = self.client.post(url, json.dumps({'nombre': 'Peso Muerto Rumano', 'grupo_muscular': 'isquiotibiales'}),
                                 content_type='application/json').json()
        femo = next(a for a in r['alternativas'] if a['nombre'] == 'Curl Femoral Tumbado')
        self.assertEqual((femo['peso_historico_kg'], femo['reps'], femo['ultima']), (40, 13, '40 kg × 13'))


class Plantillas(SimpleTestCase):
    def test_textos(self):
        activo = Path('entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn("'peso-' + fid + '-' + sn", activo)
        self.assertNotIn('nuevoNombre.toUpperCase()', activo)
        self.assertIn('excluir: enSesion', activo)
        self.assertIn('aviso_energia', activo)
        self.assertIn("deFin.textContent='HECHO'", activo)
        self.assertIn('const idx=siguientePendiente();', activo)
        cuerpo = Path('clientes/templates/clientes/cuerpo.html').read_text(encoding='utf-8')
        self.assertIn('main svg{', cuerpo)
        nav = Path('templates/includes/bottom_nav.html').read_text(encoding='utf-8')
        self.assertIn('margin:0 !important', nav)
        cierre = Path('entrenos/templates/entrenos/post_entreno_resumen.html').read_text(encoding='utf-8')
        self.assertIn('Sin hacer:', cierre)
