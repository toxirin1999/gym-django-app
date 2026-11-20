"""20-nov-2026: «Ver ajustes» detalla lo que aplica el planificador (ajustes efectivos)."""
from datetime import date, datetime, timezone as tz
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import PropuestaZonaGym
from entrenos.services.ajustes_detalle_service import detalle_ajustes

VOL = 'entrenos.services.volumen_grupo_service.'
PAUSA = 'entrenos.services.propuesta_zona_service.pausa_subir_volumen'
APLIC = 'entrenos.services.propuesta_zona_service.sesiones_con_ajuste_registrado'
HOY = date(2026, 11, 20)
AJUSTE = {'isquios': {'series': 2, 'motivos': ['+2 series de Isquios: el cambio funcionó']}}


class VerAjustesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ver_ajustes', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    def _propuesta(self, **kw):
        datos = dict(
            cliente=self.cliente, zona='isquios', series_extra=2, texto='t', estado='evaluada',
            inicio=date(2026, 10, 14), fin=date(2026, 11, 17), resultado='validada',
            notas_resultado='Mejora observada: Buenos Días +36,4 %; Curl femoral +10 %.',
            deteccion={'revision': {'estado': 'pendiente', 'fecha': '2026-12-06'}},
            evaluada_en=datetime(2026, 11, 18, 9, 0, tzinfo=tz.utc), respondida_en=datetime(2026, 10, 13, 9, 0, tzinfo=tz.utc))
        datos.update(kw)
        p = PropuestaZonaGym.objects.create(**datos)
        PropuestaZonaGym.objects.filter(pk=p.pk).update(creada_en=datetime(2026, 10, 12, 9, 0, tzinfo=tz.utc))
        return p

    def _detalle(self, ajustes=AJUSTE, aplic=(), pausa=None, revisiones=()):
        with patch(VOL + 'ajustes_volumen', return_value=ajustes), \
                patch(VOL + 'revisiones_pendientes', return_value=list(revisiones)), \
                patch(PAUSA, return_value=pausa), patch(APLIC, return_value=list(aplic)):
            return detalle_ajustes(self.cliente, HOY)

    def test_tarjeta_de_isquios_con_alcance_motivo_vigencia_e_historial(self):
        self._propuesta()
        (t,) = self._detalle(aplic=[date(2026, 10, 17), date(2026, 11, 17)])
        self.assertEqual(t['titulo'], 'Isquios · +2 series por semana')
        self.assertIn('repartidas por el planificador', t['alcance'])
        self.assertIn('+36,4 %', t['motivo'])
        self.assertEqual(t['aplicacion'], 'Ajuste registrado en 2 sesiones, del 17/10 al 17/11.')
        self.assertEqual(t['vigencia'], 'Se aplica hasta el 06/12 inclusive; revisión como máximo ese día. Sin decisión, deja de aplicarse el 07/12.')
        self.assertIn('no permite atribuir', t['sabe'])
        fechas = [h['fecha'] for h in t['historial']]
        self.assertEqual(fechas, sorted(fechas, key=lambda f: (f[3:], f[:2]), reverse=True))
        textos = ' '.join(h['texto'] for h in t['historial'])
        self.assertIn('identificada al reconstruir', textos)
        self.assertIn('Propuesta aceptada', textos)

    def test_sin_sesiones_con_ajuste_registrado_no_afirma_que_se_aplicara(self):
        self._propuesta()
        (t,) = self._detalle(aplic=[])
        self.assertEqual(t['aplicacion'], 'No consta en las sesiones que el ajuste llegara a aplicarse.')
        self.assertNotIn('Primera aplicación', ' '.join(h['texto'] for h in t['historial']))

    def test_si_no_esta_validada_no_dice_lo_que_se_sabe(self):
        self._propuesta(resultado='neutra')
        (t,) = self._detalle()
        self.assertIsNone(t['sabe'])

    def test_sin_propuesta_el_motivo_es_el_del_planificador(self):
        (t,) = self._detalle()
        self.assertEqual(t['motivo'], '+2 series de isquios: el cambio funcionó.')
        self.assertEqual(t['historial'], [])

    def test_pausa_y_revision_pendiente(self):
        pausa = {'zonas': ('triceps', 'trapecios'), 'fin_previsto': date(2026, 12, 6), 'bloque': 'Fuerza — Hipertrofia'}
        rev = {'series': 2, 'nombre_zona': 'Isquios', 'limite': date(2026, 12, 6)}
        tarjetas = self._detalle(ajustes={}, pausa=pausa, revisiones=[rev])
        self.assertEqual([t['tipo'] for t in tarjetas], ['revision', 'pausa'])
        self.assertEqual(tarjetas[1]['titulo'], 'Tríceps y trapecio · aumento de series en pausa')
        self.assertIn('Pausa hasta el 06/12', tarjetas[1]['vigencia'])

    def test_no_introduce_reglas_de_vigencia_ni_comparacion_semanal(self):
        self._propuesta()
        texto = str(self._detalle())
        for frase in ('+3 %', 'frente a la anterior', 'recoloc', 'aplaz'):
            self.assertNotIn(frase, texto)

    def test_la_pantalla_se_muestra_y_enlaza_a_plan(self):
        self._propuesta()
        with patch(VOL + 'ajustes_volumen', return_value=AJUSTE), patch(VOL + 'revisiones_pendientes', return_value=[]), \
                patch(PAUSA, return_value=None), patch(APLIC, return_value=[]):
            resp = self.client.get(reverse('clientes:ver_ajustes'))
        self.assertContains(resp, 'Ajustes del entrenador')
        self.assertContains(resp, 'Isquios · +2 series por semana')
        self.assertContains(resp, reverse('clientes:trayectoria_plan'))

    def test_sin_ajustes_la_pantalla_lo_dice(self):
        with patch(VOL + 'ajustes_volumen', return_value={}), patch(VOL + 'revisiones_pendientes', return_value=[]), \
                patch(PAUSA, return_value=None):
            resp = self.client.get(reverse('clientes:ver_ajustes'))
        self.assertContains(resp, 'no aplica ningún ajuste')


class MedicionEstructuradaTests(VerAjustesTests):
    """Si la nota guardada dice «4 semanas anteriores» pero la ventana real es de 35 dias."""

    NOTA = ('Fuerza estimada +23,2 % frente a las 4 semanas anteriores. Datos: Buenos Días: '
            '22 kg × 6 (16/09) → 30 kg × 6 (12/11), +36,4 %')

    def _comparar(self):
        return [{'ejercicio': 'Buenos Días', 'zona': 'isquios', 'pct': 36.4, 'dudoso': False, 'ligero': False,
                 'antes': {'peso_kg': 22, 'reps': 6, 'fecha': date(2026, 9, 16)},
                 'ahora': {'peso_kg': 30, 'reps': 6, 'fecha': date(2026, 11, 12)}}]

    def test_muestra_ventanas_reales_y_conserva_la_nota_antigua_en_el_historial(self):
        self._propuesta(notas_resultado=self.NOTA, semanas=4, ejercicios=['Buenos Días'])
        with patch('entrenos.services.evolucion_muscular_service.comparar_ejercicios', return_value=self._comparar()):
            (t,) = self._detalle(aplic=[date(2026, 10, 17)])
        m = t['medicion']
        self.assertEqual(m['ventana_actual'], '14/10–17/11 (35 días)')
        self.assertEqual(m['ventana_anterior'], '09/09–13/10 (35 días)')
        self.assertEqual(m['ejercicios'][0]['antes'], '22 kg × 6 (16/09)')
        self.assertIsNone(t['motivo'])
        self.assertIn('no permite atribuir', t['sabe'])
        self.assertTrue(any(self.NOTA in h['texto'] for h in t['historial']))
        fechas = [h['fecha'] for h in t['historial']]
        self.assertEqual(fechas, sorted(fechas, key=lambda f: (f[3:], f[:2]), reverse=True))

    def test_pagina_enseña_los_datos_estructurados(self):
        self._propuesta(notas_resultado=self.NOTA, semanas=4, ejercicios=['Buenos Días'])
        with patch('entrenos.services.evolucion_muscular_service.comparar_ejercicios', return_value=self._comparar()), \
                patch(VOL + 'ajustes_volumen', return_value=AJUSTE), patch(VOL + 'revisiones_pendientes', return_value=[]), \
                patch(PAUSA, return_value=None), patch(APLIC, return_value=[date(2026, 10, 17)]):
            resp = self.client.get(reverse('clientes:ver_ajustes'))
        self.assertContains(resp, 'Ventana de la propuesta: 14/10–17/11 (35 días)')
        self.assertContains(resp, 'Buenos Días: 22 kg × 6 (16/09) → 30 kg × 6 (12/11)')

    def test_si_la_nota_describe_bien_las_ventanas_no_se_toca(self):
        self._propuesta(notas_resultado=self.NOTA, semanas=5, ejercicios=['Buenos Días'])
        (t,) = self._detalle()
        self.assertNotIn('medicion', t)
        self.assertIn('+23,2 %', t['motivo'])
