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


# 18-nov-2026: «subir volumen» está en espera (SUBIR_VOLUMEN_ACTIVO = False) hasta justificar
# cómo se decide el ajuste. Este ciclo de vida (proponer → aceptar → comprobar) se prueba con el
# interruptor activado, para que siga funcionando cuando se reactive; que en espera no genera
# nada se prueba en tests_trayectoria_panel_20261118.
@patch('entrenos.services.propuesta_zona_service.SUBIR_VOLUMEN_ACTIVO', True)
class PropuestaZonaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('propuesta-zona', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = timezone.localdate()
        # El bloque del plan (comparabilidad) se prueba aparte: aquí, siempre el mismo.
        parche = patch('entrenos.services.comparabilidad_service.Bloques.de', return_value={
            'familia': 'hipertrofia', 'nombre': 'Hipertrofia — Prueba', 'semana_plan': 1, 'origen': 'prueba'})
        parche.start()
        self.addCleanup(parche.stop)

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
        self.assertIn('+2 series semanales de Isquios', propuesta.texto)  # paso 5
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

    # 2-nov-2026: con la fecha real, la base de pruebas puede caer en una semana
    # de descarga del plan, y ahí la propuesta se pausa (tests_paneles_20261102).
    @patch('entrenos.services.propuesta_zona_service.en_pausa_por_descarga', return_value=False)
    def test_aceptada_suma_series_desde_manana_y_no_en_descarga(self, _pausa):
        self._isquios_caen()
        p = aceptar_propuesta(generar_propuesta_si_procede(self.cliente, self.hoy), self.hoy)
        self.assertEqual(p.inicio, self.hoy + timedelta(days=1))
        self.assertEqual(p.fin, p.inicio + timedelta(days=27))
        # Paso 5: el volumen lo pone el planificador (+2 series semanales de
        # la zona); aquí solo se explica el cambio, sin tocar series.
        from entrenos.services.volumen_grupo_service import series_por_grupo
        self.assertEqual(series_por_grupo(self.cliente, self.hoy), {})  # hoy aún no
        self.assertEqual(series_por_grupo(self.cliente, p.inicio), {'isquios': 2})
        ejercicios = [{'nombre': 'Buenos Días', 'grupo_muscular': 'isquios', 'series': 3},
                      {'nombre': 'Press banca', 'grupo_muscular': 'pecho', 'series': 3}]
        cambios = []
        aplicar_a_ejercicios(self.cliente, ejercicios, p.inicio, cambios)
        self.assertEqual([e['series'] for e in ejercicios], [3, 3])
        self.assertEqual(cambios[0]['tipo'], 'propuesta_zona')
        self.assertIn('+2 series semanales de Isquios', cambios[0]['razon'])
        otros = [{'nombre': 'Buenos días', 'grupo_muscular': 'isquios', 'series': 3}]
        sin_cambios = []
        aplicar_a_ejercicios(self.cliente, otros, p.inicio, sin_cambios, es_descarga=True)
        self.assertEqual(sin_cambios, [])

    def test_al_terminar_comprueba_si_funciono(self):
        self._isquios_caen()
        p = aceptar_propuesta(generar_propuesta_si_procede(self.cliente, self.hoy), self.hoy)
        inicio = self.hoy - timedelta(days=35)
        PropuestaZonaGym.objects.filter(pk=p.pk).update(inicio=inicio, fin=inicio + timedelta(days=27))
        p.refresh_from_db()
        # 4 semanas antes: 45×5; durante la propuesta: 50×6 → sube.
        self._sesion(p.inicio - timedelta(days=5), 'Buenos días', 45, 5)
        self._sesion(p.inicio + timedelta(days=10), 'Buenos días', 50, 6)
        # 18-nov-2026 (nota 49): sin constancia de que se aplicó, el efecto no se da por comprobado.
        evaluadas = evaluar_propuestas_vencidas(self.cliente, self.hoy)
        self.assertEqual(len(evaluadas), 1)
        p.refresh_from_db()
        self.assertEqual(p.resultado, 'neutra')
        self.assertIn('no consta que la propuesta', p.notas_resultado)
        self.assertIn('Buenos días: 45 kg × 5', p.notas_resultado)
        self.assertIn('50 kg × 6', p.notas_resultado)

    def test_con_la_aplicacion_registrada_se_comprueba_y_cita_fechas_y_datos(self):
        self._isquios_caen()
        p = aceptar_propuesta(generar_propuesta_si_procede(self.cliente, self.hoy), self.hoy)
        inicio = self.hoy - timedelta(days=35)
        PropuestaZonaGym.objects.filter(pk=p.pk).update(inicio=inicio, fin=inicio + timedelta(days=27))
        p.refresh_from_db()
        self._sesion(p.inicio - timedelta(days=5), 'Buenos días', 45, 5)
        durante = p.inicio + timedelta(days=10)
        self._sesion(durante, 'Buenos días', 50, 6)
        with patch('entrenos.services.propuesta_zona_service.sesiones_con_ajuste_registrado',
                   return_value=[durante]):
            evaluar_propuestas_vencidas(self.cliente, self.hoy)
        p.refresh_from_db()
        self.assertEqual(p.estado, PropuestaZonaGym.ESTADO_EVALUADA)
        self.assertEqual(p.resultado, 'validada')
        self.assertIn('frente a las 4 semanas anteriores', p.notas_resultado)
        self.assertIn(f'({durante:%d/%m})', p.notas_resultado)

    def test_marcas_fuera_de_la_ventana_dejan_el_efecto_sin_determinar(self):
        self._isquios_caen()
        p = aceptar_propuesta(generar_propuesta_si_procede(self.cliente, self.hoy), self.hoy)
        inicio = self.hoy - timedelta(days=35)
        PropuestaZonaGym.objects.filter(pk=p.pk).update(inicio=inicio, fin=inicio + timedelta(days=27))
        p.refresh_from_db()
        # La marca «antes» ya cae dentro de la propuesta: no mide un antes y un durante.
        self._sesion(p.inicio + timedelta(days=2), 'Buenos días', 45, 5)
        self._sesion(p.inicio + timedelta(days=20), 'Buenos días', 50, 6)
        with patch('entrenos.services.propuesta_zona_service.sesiones_con_ajuste_registrado',
                   return_value=[p.inicio + timedelta(days=2)]):
            evaluar_propuestas_vencidas(self.cliente, self.hoy)
        p.refresh_from_db()
        self.assertEqual(p.resultado, 'neutra')
        self.assertTrue('sin determinar' in p.notas_resultado or 'Sin evidencia' in p.notas_resultado)

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
        self.assertTrue(resumen['items'][0]['texto'].startswith('Isquios: propuse +2 series semanales'))
        self.assertIn('Funcionó: fuerza estimada +6 %', resumen['items'][0]['texto'])

    def test_guardar_una_sesion_genera_la_propuesta(self):
        self._isquios_caen()
        from entrenos.services.propuesta_zona_service import tras_guardar_sesion
        self.assertIsNotNone(tras_guardar_sesion(self.cliente, self.hoy))

    def test_reevaluar_guarda_el_anterior_y_su_motivo_y_lo_dice_la_frase(self):
        from entrenos.services.propuesta_zona_service import frase_evaluacion, reevaluar_propuesta
        self._isquios_caen()
        p = aceptar_propuesta(generar_propuesta_si_procede(self.cliente, self.hoy), self.hoy)
        inicio = self.hoy - timedelta(days=35)
        PropuestaZonaGym.objects.filter(pk=p.pk).update(
            inicio=inicio, fin=inicio + timedelta(days=27), estado=PropuestaZonaGym.ESTADO_EVALUADA,
            resultado='validada', notas_resultado='Fuerza estimada +21,0 % frente a las 4 semanas anteriores')
        p.refresh_from_db()
        # Solo vista previa: no guarda.
        r, notas, cambio = reevaluar_propuesta(self.cliente, p, 'motivo', hoy=self.hoy, aplicar=False)
        p.refresh_from_db()
        self.assertEqual(p.resultado, 'validada')
        r, notas, cambio = reevaluar_propuesta(self.cliente, p, 'no medía un antes y un durante', hoy=self.hoy)
        p.refresh_from_db()
        self.assertTrue(cambio)
        self.assertEqual(p.resultado, 'neutra')
        anterior = p.deteccion['evaluacion_anterior']
        self.assertEqual(anterior['resultado'], 'validada')
        self.assertIn('+21,0 %', anterior['notas'])
        self.assertEqual(anterior['motivo'], 'no medía un antes y un durante')
        frase = frase_evaluacion(p)
        self.assertIn(f'Corregido el {self.hoy:%d/%m}: antes constaba «funcionó»', frase)
        self.assertIn('+21,0 %', frase)
        self.assertIn('Motivo: no medía un antes y un durante', frase)
