"""Iniciativa: zona que retrocede → propuesta → aceptar → +series → comprobar."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, PropuestaZonaGym
from entrenos.services.propuesta_zona_service import (
    PropuestaNoVigente, aceptar_propuesta, aplicar_a_ejercicios,
    detectar_zona_en_retroceso, evaluar_propuestas_vencidas,
    generar_propuesta_si_procede, propuesta_visible, rechazar_propuesta,
)
from rutinas.models import Rutina


class PropuestaZonaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('propuesta-zona', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = timezone.localdate()

    def _sesion(self, fecha, nombre, peso, reps=8, grupo='Isquios'):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre=f'{nombre}{fecha}'), fecha=fecha,
        )
        EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
            entreno=entreno, nombre_ejercicio=nombre, grupo_muscular=grupo,
            peso_kg=peso, repeticiones=reps, series=3, completado=True,
        )])

    def _isquios_caen(self):
        self._sesion(self.hoy - timedelta(days=120), 'Buenos días', 50, 8)
        self._sesion(self.hoy - timedelta(days=10), 'Buenos días', 45, 5)
        self._sesion(self.hoy - timedelta(days=120), 'Curl femoral tumbado', 70, 6)
        self._sesion(self.hoy - timedelta(days=10), 'Curl femoral tumbado', 55, 5)

    def test_detecta_la_zona_y_cita_el_dato(self):
        self._isquios_caen()
        deteccion = detectar_zona_en_retroceso(self.cliente, self.hoy)
        self.assertEqual(deteccion['zona'], 'isquios')
        propuesta = generar_propuesta_si_procede(self.cliente, self.hoy)
        self.assertIn('Isquios: -', propuesta.texto)
        self.assertIn('kg × ', propuesta.texto)
        self.assertIn('+1 serie en', propuesta.texto)
        self.assertEqual(set(propuesta.ejercicios), {'Buenos días', 'Curl femoral tumbado'})

    def test_sin_retroceso_no_propone(self):
        self._sesion(self.hoy - timedelta(days=120), 'Buenos días', 45, 8)
        self._sesion(self.hoy - timedelta(days=10), 'Buenos días', 50, 8)
        self.assertIsNone(generar_propuesta_si_procede(self.cliente, self.hoy))

    def test_una_sola_a_la_vez_y_enfriamiento_tras_rechazo(self):
        self._isquios_caen()
        p = generar_propuesta_si_procede(self.cliente, self.hoy)
        self.assertIsNone(generar_propuesta_si_procede(self.cliente, self.hoy))
        rechazar_propuesta(p)
        self.assertIsNone(generar_propuesta_si_procede(self.cliente, self.hoy))
        with self.assertRaises(PropuestaNoVigente):
            aceptar_propuesta(p)

    def test_aceptada_suma_series_desde_manana_y_no_en_descarga(self):
        self._isquios_caen()
        p = aceptar_propuesta(generar_propuesta_si_procede(self.cliente, self.hoy), self.hoy)
        self.assertEqual(p.inicio, self.hoy + timedelta(days=1))
        self.assertEqual(p.fin, p.inicio + timedelta(days=27))
        ejercicios = [{'nombre': 'Buenos Días', 'series': 3}, {'nombre': 'Press banca', 'series': 3}]
        cambios = []
        aplicar_a_ejercicios(self.cliente, ejercicios, self.hoy, cambios)
        self.assertEqual(ejercicios[0]['series'], 3)  # hoy aún no
        aplicar_a_ejercicios(self.cliente, ejercicios, p.inicio, cambios)
        self.assertEqual([e['series'] for e in ejercicios], [4, 3])
        self.assertEqual(cambios[0]['tipo'], 'propuesta_zona')
        otros = [{'nombre': 'Buenos días', 'series': 3}]
        aplicar_a_ejercicios(self.cliente, otros, p.inicio, [], es_descarga=True)
        self.assertEqual(otros[0]['series'], 3)

    def test_al_terminar_comprueba_si_funciono(self):
        self._isquios_caen()
        p = aceptar_propuesta(generar_propuesta_si_procede(self.cliente, self.hoy), self.hoy)
        inicio = self.hoy - timedelta(days=35)
        PropuestaZonaGym.objects.filter(pk=p.pk).update(inicio=inicio, fin=inicio + timedelta(days=27))
        p.refresh_from_db()
        # 4 semanas antes: 45×5; durante la propuesta: 50×6 → sube.
        self._sesion(p.inicio - timedelta(days=5), 'Buenos días', 45, 5)
        self._sesion(p.inicio + timedelta(days=10), 'Buenos días', 50, 6)
        evaluadas = evaluar_propuestas_vencidas(self.cliente, self.hoy)
        self.assertEqual(len(evaluadas), 1)
        p.refresh_from_db()
        self.assertEqual(p.estado, PropuestaZonaGym.ESTADO_EVALUADA)
        self.assertEqual(p.resultado, 'validada')
        self.assertIn('frente a las 4 semanas anteriores', p.notas_resultado)

    def test_visible_en_ahora_y_responder(self):
        self._isquios_caen()
        p = generar_propuesta_si_procede(self.cliente, self.hoy)
        self.assertEqual(propuesta_visible(self.cliente, self.hoy)['tipo'], 'pendiente')
        self.client.force_login(self.user)
        ctx = {'_decision_gym_raw': {}, 'proximo_entrenamiento': {}, 'explicacion_decision': {}, 'acwr_actual': None}
        with patch('clientes.views._get_dashboard_context_data', return_value=ctx), \
                patch('core.organismo.resolver_estado_sistema_hoy', return_value={
                    'estado': 'EN_MARGEN', 'texto': 'Hay margen.', 'accion_label': None, 'accion_url': None,
                }):
            response = self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertContains(response, 'El entrenador propone')
        self.assertContains(response, 'Aplicar desde mañana')
        respuesta = self.client.post(reverse('entrenos:aceptar_propuesta_zona', args=[p.id]))
        self.assertEqual(respuesta.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.estado, PropuestaZonaGym.ESTADO_ACEPTADA)
        self.assertEqual(propuesta_visible(self.cliente, self.hoy)['tipo'], 'en_curso')

    def test_otro_usuario_no_puede_responder(self):
        self._isquios_caen()
        p = generar_propuesta_si_procede(self.cliente, self.hoy)
        otro = get_user_model().objects.create_user('ajeno-propuesta', password='x')
        self.client.force_login(otro)
        self.assertEqual(self.client.post(reverse('entrenos:aceptar_propuesta_zona', args=[p.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('entrenos:aceptar_propuesta_zona', args=[p.id])).status_code, 405)

    def test_la_propuesta_evaluada_sale_en_memoria(self):
        from entrenos.services.aprendizaje_decisiones_service import decisiones_evaluadas
        self._isquios_caen()
        p = generar_propuesta_si_procede(self.cliente, self.hoy)
        PropuestaZonaGym.objects.filter(pk=p.pk).update(
            estado=PropuestaZonaGym.ESTADO_EVALUADA, resultado='validada',
            notas_resultado='Fuerza estimada +6 % frente a las 4 semanas anteriores',
            evaluada_en=timezone.now(),
        )
        resumen = decisiones_evaluadas(self.cliente)
        self.assertEqual(resumen['funcionaron'], 1)
        self.assertTrue(resumen['items'][0]['texto'].startswith('Isquios: propuse +1 serie en '))
        self.assertIn('Funcionó: fuerza estimada +6 %', resumen['items'][0]['texto'])

    def test_guardar_una_sesion_genera_la_propuesta(self):
        self._isquios_caen()
        from entrenos.services.propuesta_zona_service import tras_guardar_sesion
        self.assertIsNotNone(tras_guardar_sesion(self.cliente, self.hoy))
