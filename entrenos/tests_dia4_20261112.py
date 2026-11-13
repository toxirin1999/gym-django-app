"""Día 4 (12-nov-2026): escala 2 kg en laterales/Y-raises, aviso de RPE una vez, rango visible, texto en segundos."""
from django.test import SimpleTestCase
from pathlib import Path

from entrenos.services.maquina_service import salto_fisico


class EscalaPoleaConDiscos(SimpleTestCase):
    def test_laterales_e_y_raises_van_de_2_en_2(self):
        self.assertEqual(salto_fisico('Elevaciones laterales en polea'), 2.0)
        self.assertEqual(salto_fisico('Y-Raises'), 2.0)


class PlantillasYServicios(SimpleTestCase):
    base = Path(__file__).resolve().parent

    def test_template_planweight_y_peso_en_cierre_de_ejercicio(self):
        t = (self.base / 'templates/entrenos/entrenamiento_activo.html').read_text()
        self.assertIn('dataset.planWeight = String(Number((plan.peso)', t)
        self.assertIn('mismo peso', t)

    def test_margen_usa_rpe_rebajado_del_dia(self):
        s = (self.base / 'services/cerebro_carga_service.py').read_text()
        self.assertIn("rpe_dia = min(float(rpe_dia), _bajado)", s)

    def test_aprendizaje_usa_unidad_y_salta_descarga(self):
        s = (self.base / 'services/aprendizaje_decisiones_service.py').read_text()
        self.assertIn('_unidad_ejercicio', s)
        self.assertIn('es_sesion_descarga', s)

    def test_acotar_rango_visible_existe(self):
        s = (self.base / 'views.py').read_text()
        self.assertIn('def _acotar_rango_visible', s)


# ── Panel «Cómo responde tu cuerpo» (13-nov-2026) ────────────────────────────
from datetime import timedelta

from django.urls import reverse

from entrenos.tests_estado_carga_20261025 import HOY, Base


class PanelCuerpoMejoras(Base):
    HOY = HOY

    def setUp(self):
        super().setUp()
        for i in range(1, 9):
            self.reloj(i, hrv=70, fc=57, sueno=7.5)
        self.reloj(0, hrv=42, fc=52, sueno=6.7)

    def test_dias_con_detalle_y_hoy(self):
        from entrenos.services.estado_carga_service import estado_carga
        from entrenos.services.panel_cuerpo_service import dias_recientes
        dias = dias_recientes(estado_carga(self.cliente, self.HOY), self.cliente)
        self.assertTrue(dias[-1]['hoy'])
        self.assertTrue(dias[-1]['detalle'])

    def test_sueno_en_horas_y_minutos_y_con_ejes(self):
        from entrenos.services.panel_cuerpo_service import sueno
        s = sueno(self.cliente, self.HOY)
        self.assertEqual(s['hoy_valor'], '6 h 42')
        self.assertIn('h', s['eje_max'])
        self.assertIn('eje_min', s)

    def test_frase_reloj_separa_hoy_de_la_tendencia(self):
        from entrenos.services.panel_cuerpo_service import frase_reloj, pulso, sueno, variabilidad
        txt = frase_reloj(variabilidad(self.cliente, self.HOY), pulso(self.cliente, self.HOY),
                          sueno(self.cliente, self.HOY))
        self.assertIn('Variabilidad por debajo de tu rango hoy', txt)
        self.assertIn('Pulso tranquilo', txt)
        self.assertNotIn('compensan', txt)
        self.assertNotIn('Tendencia', txt)

    def test_ultimos_dias_lleva_la_tendencia(self):
        from entrenos.services.estado_carga_service import estado_carga
        from entrenos.services.panel_cuerpo_service import frase_ultimos_dias, pulso, sueno, variabilidad
        txt = frase_ultimos_dias(estado_carga(self.cliente, self.HOY), variabilidad(self.cliente, self.HOY),
                                 pulso(self.cliente, self.HOY), sueno(self.cliente, self.HOY))
        self.assertIn('Tendencia de 7 días', txt)

    def test_dias_con_detalle_y_hoy(self):
        from entrenos.services.estado_carga_service import estado_carga
        from entrenos.services.panel_cuerpo_service import dias_recientes
        dias = dias_recientes(estado_carga(self.cliente, self.HOY), self.cliente)
        self.assertTrue(dias[-1]['hoy'])
        self.assertIn('por debajo de lo habitual', dias[-1]['detalle'])

    # ── Paquete 2: cabecera = decisión de Ahora, qué cambió, qué haría cambiar, sello ──
    def test_que_cambio_solo_cuenta_ajustes_materializados(self):
        from entrenos.services.panel_cuerpo_service import que_cambio
        decision = {'estado': 'entrenar', 'sesion_materializada': True, 'cambios_materializados': [
            {'tipo': 'criterio_entrenador', 'ejercicio_original': 'A',
             'razon': 'Hoy RPE 7 en vez de 8: variabilidad un 38 % por debajo de lo habitual. Deja una o dos reps en reserva.'},
            {'tipo': 'criterio_entrenador', 'ejercicio_original': 'B', 'razon': 'Hoy RPE 7 en vez de 8.'},
            {'tipo': 'criterio_entrenador', 'ejercicio_original': 'D', 'razon': 'Hoy RPE 7 en vez de 8.'},
            {'tipo': 'progresion_aplicada', 'ejercicio_original': 'C', 'razon': 'sube'},
        ]}
        items = que_cambio(decision, 'ENTRENAR')
        self.assertEqual(len(items), 1)
        self.assertIn('RPE objetivo un punto menos en 3 ejercicios: variabilidad', items[0])
        self.assertNotIn('sube', ' '.join(items))

    def test_que_cambio_sin_ajustes_y_sin_sesion(self):
        from entrenos.services.panel_cuerpo_service import que_cambio
        self.assertIn('tal como está en el plan', que_cambio({'estado': 'entrenar', 'sesion_materializada': True})[0])
        self.assertIn('no hay sesión', que_cambio({}, 'DESCANSAR')[0])
        self.assertIn('versión reducida', que_cambio({'estado': 'version_reducida', 'sesion_materializada': True})[0])

    def test_cabecera_usa_la_decision_de_ahora(self):
        from unittest.mock import patch
        from entrenos.services.panel_cuerpo_service import decision_de_hoy
        with patch('entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym',
                   return_value={'estado': 'version_reducida', 'sesion_materializada': True,
                                 'cambios_materializados': []}), \
             patch('core.organismo.resolver_estado_sistema_hoy',
                   return_value={'estado': 'EN_MARGEN', 'motivo': 'gym_version_reducida',
                                 'texto': 'Hay margen, con carga ajustada.'}):
            d = decision_de_hoy(self.cliente, self.user, self.HOY)
        self.assertEqual(d['titulo'], 'Entrenar')
        self.assertEqual(d['frase'], 'Hay margen, con carga ajustada.')
        self.assertIn('versión reducida', d['cambios'][0])

    def test_que_haria_cambiar_la_respuesta(self):
        from entrenos.services.panel_cuerpo_service import tres_preguntas
        est = {'respuesta': 'vas_bien', 'carga': {'ratio': 0.63}, 'malos_5': 2, 'dias_5': 5, 'buenos_14': 12,
               'dias_14': 12, 'esfuerzo': {'subiendo': False}, 'molestias': []}
        d, p, m = tres_preguntas(est)
        self.assertEqual(d['pregunta'], '¿Hace falta descanso extra?')
        self.assertEqual(d['respuesta'], 'Hoy no')
        self.assertIn('esta regla no se activa', d['cambia'])
        self.assertIn('ahora −37 %', p['cambia'])
        self.assertEqual(m['respuesta'], 'Aún no se puede valorar')
        self.assertEqual(m['tono'], 'pendiente')
        self.assertIn('solo pude comparar 12 de los 14', m['cambia'])

    def test_sello_distingue_importacion_de_medicion(self):
        from datetime import datetime, timezone as tz
        from clientes.models import BitacoraDiaria
        from entrenos.services.panel_cuerpo_service import sello_reloj
        # sincronización de hoy a las 07:42 con datos de ayer (hoy sin medir)
        BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=self.HOY).delete()
        BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=self.HOY - timedelta(days=1)).update(
            salud_importado_en=datetime(self.HOY.year, self.HOY.month, self.HOY.day, 6, 42, tzinfo=tz.utc))
        sello = sello_reloj(self.cliente, self.HOY)
        self.assertTrue(sello['atraso'])
        self.assertIn('ayer', sello['mediciones'])
        self.assertTrue(sello['importacion'].startswith('hoy '))

    def test_sello_hoy_completo_y_sin_hora(self):
        from entrenos.services.panel_cuerpo_service import sello_reloj
        sello = sello_reloj(self.cliente, self.HOY)
        self.assertFalse(sello['atraso'])
        self.assertIn('las tres señales son de esta mañana', sello['mediciones'])
        self.assertIsNone(sello['importacion'])

    def test_guardar_checkin_registra_la_hora_de_importacion(self):
        from clientes.models import BitacoraDiaria
        from clientes.salud_iphone_service import guardar_checkin_iphone
        guardar_checkin_iphone(self.cliente, {'fecha': self.HOY.isoformat(), 'hrv_ms': 55, 'fc_reposo': 54,
                                              'horas_sueno': 7.2}, hoy=self.HOY)
        fila = BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=self.HOY).first()
        self.assertIsNotNone(fila.salud_importado_en)

    def test_pagina_nueva(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('clientes:cuerpo'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for txt in ('Qué vio el reloj esta mañana', 'Qué muestran los últimos días', 'Qué cambió en mi entreno',
                    'Qué haría cambiar la respuesta', 'id="tab-sueno"', 'Toca un día para ver qué lo marcó',
                    'Importación del reloj'):
            self.assertIn(txt, html)
        self.assertNotIn('no cambia tu plan', html)
        self.assertNotIn('compensan', html)



class PanelCuerpoAppDiseno(PanelCuerpoMejoras):
    """14-nov-2026: rediseño tipo app (tarjetas, medidor, preguntas desplegables)."""

    def test_tarjetas_con_rango_y_estado(self):
        from entrenos.services.panel_cuerpo_service import pulso, sueno, tarjetas_senales, variabilidad
        t = tarjetas_senales(variabilidad(self.cliente, self.HOY), pulso(self.cliente, self.HOY),
                             sueno(self.cliente, self.HOY))
        self.assertEqual([x['clave'] for x in t], ['variabilidad', 'pulso', 'sueno'])
        self.assertEqual(t[0]['valor'], '42')
        self.assertIs(t[0]['ok'], False)
        self.assertIn('bajo', t[0]['estado'])
        self.assertIsNotNone(t[0]['banda_ini'])
        self.assertIs(t[1]['ok'], True)
        self.assertEqual(t[2]['valor'], '6 h 42')

    def test_chips_de_cambios(self):
        from entrenos.services.panel_cuerpo_service import chips_de_cambios
        self.assertEqual(chips_de_cambios(['La sesión va en versión reducida.', 'RPE objetivo un punto menos en 4 ejercicios: x.']),
                         ['Versión reducida', 'RPE −1 · 4 ejerc.'])
        self.assertEqual(chips_de_cambios(['La sesión va tal como estaba prevista.']), [])

    def test_pagina_con_tarjetas_y_acordeon(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('clientes:cuerpo')).content.decode()
        for txt in ('class="tiles"', 'data-tab="pulso"', 'class="preg"', '¿Y ahora qué?'):
            self.assertIn(txt, html)
