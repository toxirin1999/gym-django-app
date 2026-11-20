"""19-nov-2026 · Consulta de evolución por ejercicio (Entrega 1): servicio, pantallas, confirmaciones y perfil de fuerza."""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (ConfirmacionCargaEjercicio, EntrenoRealizado, EjercicioRealizado, RecordPersonal,
                             SemanaPlanGym, SerieRealizada)
from entrenos.services import evolucion_ejercicio_service as svc
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 11, 19)


def lunes_de(f):
    return f - timedelta(days=f.weekday())


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='evej', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'E'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        self.curl = EjercicioBase.objects.create(nombre='Curl Femoral Tumbado', grupo_muscular='isquios',
                                                 equipo='maquina', tipo_progresion='peso_reps')
        # Como en producción: sin equipo; la app lo reconoce como dos mancuernas por el nombre.
        self.arnold = EjercicioBase.objects.create(nombre='Press Arnold', grupo_muscular='hombros',
                                                   tipo_progresion='peso_reps')
        self.farmer = EjercicioBase.objects.create(nombre='Farmer Walk', grupo_muscular='antebrazos',
                                                   tipo_progresion='progresion_distancia')
        self.client.force_login(self.user)

    def reg(self, fecha, base, series, tipo=None, metros=False, aprox=(), mult=None, total=False, media=False):
        """series = [(peso, valor, rpe)]; valor son reps, o metros con metros=True.
        mult/total reproducen cómo registra la app (p. ej. tipo 'total', mult 1, peso_total = peso).
        media=True: entreno antiguo, solo con el agregado del ejercicio (sin detalle por serie)."""
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        if not media:
            for i, (peso, valor, rpe) in enumerate(series, start=1):
                SerieRealizada.objects.create(
                    entreno=e, ejercicio=base, serie_numero=i, repeticiones=1 if metros else valor,
                    distancia_metros=valor if metros else None, peso_kg=peso, tipo_carga=tipo, rpe_real=rpe,
                    multiplicador_carga=mult, peso_total_kg=(peso * (mult or 1)) if total else None,
                    completado=True, es_aproximacion=i in aprox)
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=base.nombre, peso_kg=series[0][0], series=len(series),
                                          repeticiones=1 if metros else series[0][1], tipo_carga=tipo,
                                          multiplicador_carga=mult, completado=True)
        return e

    def plan(self, fecha, semana, descarga=False):
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=lunes_de(fecha), semana_plan=semana,
                                     descarga=descarga, origen='descarga_programada' if descarga else 'calendario')

    def curl_datos(self):
        self.reg(date(2026, 10, 8), self.curl, [(45, 6, 8), (40, 10, 8)])
        self.reg(date(2026, 10, 20), self.curl, [(40, 13, 9)] * 3)
        self.reg(date(2026, 10, 27), self.curl, [(40, 14, 8), (40, 7, 9)])
        self.reg(date(2026, 11, 10), self.curl, [(40, 12, 7)] * 2)
        self.reg(date(2026, 11, 17), self.curl, [(45, 8, 7)] * 2)


class Calculos(Base):
    def test_40x10_a_40x14_es_10_por_ciento_sin_redondeos_intermedios(self):
        self.reg(date(2026, 10, 8), self.curl, [(40, 10, 8)])
        self.reg(date(2026, 10, 27), self.curl, [(40, 14, 8)])
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '40', HOY)
        self.assertEqual(c['conclusion']['extra'], 'Información adicional: fuerza estimada +10,0 %.')
        self.assertEqual(svc.porcentaje(53.3333333, 58.6666667), '+10,0 %')

    def test_45x6_a_45x8_es_5_6(self):
        self.reg(date(2026, 10, 8), self.curl, [(45, 6, 8)])
        self.reg(date(2026, 11, 17), self.curl, [(45, 8, 7)])
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '45', HOY)
        self.assertIn('+5,6 %', c['conclusion']['extra'])

    def test_farmer_47_a_67_metros(self):
        self.reg(date(2026, 9, 15), self.farmer, [(36, 47, None)], tipo='por_mano', metros=True)
        self.reg(date(2026, 11, 12), self.farmer, [(36, 67, None)], tipo='por_mano', metros=True)
        c = svc.consulta(self.cliente, 'Farmer Walk', 90, '36', HOY)
        self.assertIn('de 47 a 67 m', c['conclusion']['titulo'])
        self.assertIn('+42,6 %', c['conclusion']['extra'])


class ConclusionCurl(Base):
    def test_describe_lo_observado_con_esfuerzo(self):
        self.curl_datos()
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '40', HOY)['conclusion']
        self.assertEqual(c['titulo'], '40 kg: de 10 a 14 reps')
        norm = c['detalle'].replace('\u00a0', ' ')
        self.assertIn('08/10: 10 reps a RPE 8 → 27/10: 14 reps a RPE 8', norm)
        self.assertIn('Última: 12 reps a RPE 7 el 10/11', norm)

    def test_el_bloque_es_contexto_no_afirma_ni_descarta(self):
        self.reg(date(2026, 10, 27), self.curl, [(40, 14, 8)])
        self.reg(date(2026, 11, 10), self.curl, [(40, 12, 7)])
        self.plan(date(2026, 10, 27), 40)     # hipertrofia metabólica
        self.plan(date(2026, 11, 10), 46)     # fuerza
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '40', HOY)['conclusion']
        texto = ' '.join(c['avisos'] + [c['titulo'], c['detalle']]).lower()
        self.assertIn('contexto', texto)
        self.assertNotIn('has perdido', texto)
        self.assertNotIn('retroced', texto)
        self.assertEqual(c['estado'], 'comparada')       # el cambio de bloque no la invalida

    def test_descarga_visible_pero_fuera_de_la_conclusion(self):
        self.reg(date(2026, 10, 8), self.curl, [(40, 10, 8)])
        self.reg(date(2026, 11, 3), self.curl, [(40, 5, 5)])      # semana de descarga
        self.reg(date(2026, 11, 10), self.curl, [(40, 12, 7)])
        self.plan(date(2026, 11, 3), 44, descarga=True)
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '40', HOY)
        self.assertEqual(c['conclusion']['titulo'], '40 kg: de 10 a 12 reps')
        self.assertIn('descarga', c['conclusion']['nota'])
        puntos = {p['fecha']: p for p in c['puntos']}
        self.assertIn(date(2026, 11, 3), puntos)                  # se ve en la gráfica
        self.assertEqual(puntos[date(2026, 11, 3)]['excluida'], 'descarga')
        self.assertEqual(sum(1 for u in c['ultimas'] if u['excluida']), 1)   # y en las sesiones


class PeriodoYCarga(Base):
    def test_conclusion_grafica_y_sesiones_siguen_periodo_y_carga(self):
        self.curl_datos()
        for dias in (30, 90, 180):
            for token in ('40', '45'):
                c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', dias, token, HOY)
                self.assertEqual(c['dias'], dias)
                self.assertEqual(c['carga']['token'], token)
                self.assertTrue(all(c['desde'] < p['fecha'] <= HOY for p in c['puntos']))
                self.assertTrue(all(c['desde'] < u['fecha'] <= HOY for u in c['ultimas']))
        c30 = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 30, '40', HOY)
        self.assertEqual([p['fecha'] for p in c30['puntos']], [date(2026, 10, 27), date(2026, 11, 10)])
        self.assertEqual(c30['conclusion']['estado'], 'comparada')
        c45 = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '45', HOY)
        self.assertEqual([p['valor'] for p in c45['puntos']], [6, 8])

    def test_sesiones_de_otras_cargas_se_marcan_y_enlazan(self):
        self.curl_datos()
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '40', HOY)
        por_fecha = {u['fecha']: u for u in c['ultimas']}
        self.assertFalse(por_fecha[date(2026, 11, 17)]['con_carga'])
        self.assertEqual(por_fecha[date(2026, 11, 17)]['token'], '45')
        self.assertTrue(por_fecha[date(2026, 11, 10)]['con_carga'])

    def test_las_cargas_son_exactas_a_ambos_lados_de_cualquier_limite(self):
        pesos = [39.9, 40, 40.4, 40.5, 40.6, 40.0001]       # la BD guarda 2 decimales: 40.0001 se almacena como 40.00 y es lo que se compara
        for i, p in enumerate(pesos):
            self.reg(date(2026, 10, 1) + timedelta(days=i), self.curl, [(p, 10 + i, 8)])
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, None, HOY)
        tokens = sorted(k['token'] for k in c['cargas'])
        self.assertEqual(c['mas_cargas'], 1)
        # 39,9 · 40 · 40,4 · 40,5 · 40,6 son cinco cargas distintas (cuatro visibles + una en el detalle)
        todas = {k['token'] for k in c['cargas']}
        self.assertLessEqual(todas, {'39.9', '40', '40.4', '40.5', '40.6'})
        for token, esperado in (('39.9', [10]), ('40', [11, 15]), ('40.4', [12]), ('40.5', [13]), ('40.6', [14])):
            cc = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, token, HOY)
            self.assertEqual([p['valor'] for p in cc['puntos']], esperado, token)
        h = svc.cargar_historial(self.cliente, 'Curl Femoral Tumbado')
        originales = [x['peso'] for s in h['sesiones'] for x in s['series']]
        self.assertEqual(originales, [39.9, 40.0, 40.4, 40.5, 40.6, 40.0])      # se comparan los valores efectivamente guardados (2 decimales), sin agrupar

    def test_39_9_y_40_no_se_unen_en_una_linea(self):
        self.reg(date(2026, 10, 17), self.curl, [(39.9, 12, 9)])
        self.reg(date(2026, 10, 20), self.curl, [(40, 13, 9)])
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 90, '40', HOY)
        self.assertEqual([p['fecha'] for p in c['puntos']], [date(2026, 10, 20)])
        self.assertEqual(c['conclusion']['estado'], 'una_sesion')

    def test_la_carga_se_convierte_solo_con_confirmacion_y_el_original_se_conserva(self):
        self.reg(date(2026, 10, 1), self.arnold, [(37.5, 12, 7)], tipo='total', mult=1, total=True)
        self.reg(date(2026, 10, 8), self.arnold, [(37.5, 10, 7)], tipo='total', mult=1, total=True)
        antes = svc.consulta(self.cliente, 'Press Arnold', 90, None, HOY)
        self.assertEqual(antes['carga']['token'], '37.5~')                       # sin confirmar: tal cual
        ConfirmacionCargaEjercicio.objects.create(
            cliente=self.cliente, ejercicio_clave='press arnold', ejercicio_nombre='Press Arnold',
            ambiguedad='unidad_carga', respuesta='total_dos', desde=date(2026, 10, 1), hasta=date(2026, 10, 8))
        despues = svc.consulta(self.cliente, 'Press Arnold', 90, None, HOY)
        self.assertEqual(despues['carga']['token'], '18.75')                     # mitad exacta, sin redondeos a 0,5
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        self.assertEqual([x['peso'] for s in h['sesiones'] for x in s['series']], [37.5, 37.5])   # original intacto


class Estados(Base):
    def test_sin_sesiones_en_el_periodo(self):
        self.curl_datos()
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 30, '40', date(2026, 12, 21))
        self.assertEqual(c['conclusion']['estado'], 'sin_sesiones')
        self.assertIn('Última con esta carga: 10/11', c['conclusion']['detalle'])
        self.assertEqual(c['puntos'], [])

    def test_una_sola_sesion(self):
        self.curl_datos()
        c = svc.consulta(self.cliente, 'Curl Femoral Tumbado', 30, '45', HOY)
        self.assertEqual(c['conclusion']['estado'], 'una_sesion')
        self.assertIn('no hay con qué compararla', c['conclusion']['detalle'])

    def test_historial_solo_fuera_del_periodo_no_rompe_la_pantalla(self):
        self.reg(date(2026, 1, 10), self.curl, [(40, 10, 8)])
        r = self.client.get(reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'curl-femoral-tumbado']) + '?dias=30')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sin sesiones')

    def test_cambio_de_unidad_en_farmer_separa_los_registros_antiguos(self):
        self.reg(date(2026, 8, 11), self.farmer, [(75, 37, None)], tipo='total')            # reps = ¿metros? y peso total
        self.reg(date(2026, 9, 8), self.farmer, [(36, 41, None)], tipo='por_mano')           # sin metros
        self.reg(date(2026, 9, 15), self.farmer, [(36, 42, None)], tipo='por_mano', metros=True)
        self.reg(date(2026, 11, 12), self.farmer, [(36, 67, None)], tipo='por_mano', metros=True)
        c = svc.consulta(self.cliente, 'Farmer Walk', 180, '36', HOY)
        self.assertEqual([p['valor'] for p in c['puntos']], [42, 67])        # los antiguos no se unen
        self.assertTrue(c['bandas'])
        self.assertEqual(c['bandas'][0][2], 'Otra unidad')
        h = svc.cargar_historial(self.cliente, 'Farmer Walk')
        self.assertEqual(len(h['sesiones']), 4)                              # pero siguen en el historial
        self.assertEqual(h['tramos'][0]['ambiguedad'], 'unidad_medida')

    def test_ejercicio_sin_registros_da_404(self):
        r = self.client.get(reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'no-existe']))
        self.assertEqual(r.status_code, 404)


class Confirmaciones(Base):
    def arnold_datos(self):
        # Tramo 1: sin tipo de carga (hasta el 14/08). Tramo 2: «total ×1» con peso total = peso (desde el 19/09).
        self.reg(date(2026, 7, 24), self.arnold, [(30, 15, 7)] * 3)
        self.reg(date(2026, 8, 7), self.arnold, [(35, 15, 7), (40, 12, 7)])
        for f, s in [((9, 19), [(40, 12, 7)] * 2), ((10, 17), [(40, 9, 8), (30, 12, 8)]), ((10, 20), [(30, 12, 9)]),
                     ((10, 27), [(25, 15, 8)] * 3), ((11, 10), [(30, 12, 7)] * 2), ((11, 17), [(35, 8, 6)]),
                     ((11, 18), [(35, 12, 6), (40, 8, 7)])]:
            self.reg(date(2026, *f), self.arnold, s, tipo='total', mult=1, total=True)

    def url(self, nombre, **kw):
        return reverse(nombre, args=[self.cliente.id, 'press-arnold'])

    def test_tramos_ambiguos_se_preguntan_por_separado(self):
        self.arnold_datos()
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        self.assertEqual([(t['desde'], t['hasta']) for t in h['tramos']],
                         [(date(2026, 7, 24), date(2026, 8, 7)), (date(2026, 9, 19), date(2026, 11, 18))])
        self.assertTrue(all(t['estado'] == 'pendiente' for t in h['tramos']))

    def test_la_pantalla_empieza_sin_opcion_y_con_desplegable(self):
        self.arnold_datos()
        r = self.client.get(self.url('clientes:confirmar_carga_ejercicio') + '?tramo=1')
        self.assertEqual(r.status_code, 200)
        self.assertNotRegex(r.content.decode(), r'<input[^>]*checked')
        self.assertContains(r, '<details>')
        self.assertContains(r, 'Por qué te lo pregunto')
        self.assertNotContains(r, 'type="checkbox"')
        self.assertContains(r, 'name="desde"')
        self.assertContains(r, 'No lo recuerdo')

    def test_guardar_sin_opcion_da_error_y_no_guarda(self):
        self.arnold_datos()
        r = self.client.post(self.url('clientes:confirmar_carga_ejercicio'),
                             {'tramo': 1, 'desde': '2026-09-19', 'hasta': '2026-11-18'})
        self.assertContains(r, 'Elige una respuesta')
        self.assertEqual(ConfirmacionCargaEjercicio.objects.count(), 0)

    def test_fechas_fuera_del_tramo_o_invertidas_dan_error(self):
        self.arnold_datos()
        u = self.url('clientes:confirmar_carga_ejercicio')
        r = self.client.post(u, {'tramo': 1, 'respuesta': 'por_mancuerna', 'desde': '2026-07-24', 'hasta': '2026-11-18'})
        self.assertContains(r, 'Las fechas deben estar entre')
        r = self.client.post(u, {'tramo': 1, 'respuesta': 'por_mancuerna', 'desde': '2026-11-18', 'hasta': '2026-09-19'})
        self.assertContains(r, 'no puede ser posterior')
        r = self.client.post(u, {'tramo': 1, 'respuesta': 'por_mancuerna', 'desde': 'x', 'hasta': ''})
        self.assertContains(r, 'las dos fechas')
        self.assertEqual(ConfirmacionCargaEjercicio.objects.count(), 0)

    def test_error_de_base_de_datos_no_guarda_y_conserva_la_eleccion(self):
        self.arnold_datos()
        with mock.patch.object(ConfirmacionCargaEjercicio.objects, 'create', side_effect=DatabaseError('x')):
            r = self.client.post(self.url('clientes:confirmar_carga_ejercicio'),
                                 {'tramo': 1, 'respuesta': 'total_dos', 'desde': '2026-09-19', 'hasta': '2026-11-18'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No se ha guardado')
        self.assertContains(r, 'value="total_dos" checked')
        self.assertEqual(ConfirmacionCargaEjercicio.objects.count(), 0)

    def test_guardar_aplica_solo_a_ese_tramo_y_no_toca_los_registros(self):
        self.arnold_datos()
        antes = list(SerieRealizada.objects.order_by('id').values_list('id', 'peso_kg', 'repeticiones', 'tipo_carga', 'rpe_real'))
        r = self.client.post(self.url('clientes:confirmar_carga_ejercicio'),
                             {'tramo': 1, 'respuesta': 'por_mancuerna', 'desde': '2026-09-19', 'hasta': '2026-11-18'})
        self.assertRedirects(r, self.url('clientes:evolucion_ejercicio') + '?ok=1', fetch_redirect_response=False)
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        self.assertEqual([t['estado'] for t in h['tramos']], ['pendiente', 'confirmada'])   # confirmar hoy no valida lo antiguo
        despues = list(SerieRealizada.objects.order_by('id').values_list('id', 'peso_kg', 'repeticiones', 'tipo_carga', 'rpe_real'))
        self.assertEqual(antes, despues)

    def test_acotar_fechas_deja_el_resto_pendiente(self):
        self.arnold_datos()
        self.client.post(self.url('clientes:confirmar_carga_ejercicio'),
                         {'tramo': 1, 'respuesta': 'por_mancuerna', 'desde': '2026-09-19', 'hasta': '2026-09-19'})
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        self.assertEqual(h['tramos'][1]['estado'], 'parcial')
        pend = {s['fecha']: s['pendiente'] for s in h['sesiones']}
        self.assertFalse(pend[date(2026, 9, 19)])
        self.assertTrue(pend[date(2026, 11, 18)])

    def test_no_lo_recuerdo_deja_pendiente_pero_se_guarda(self):
        self.arnold_datos()
        self.client.post(self.url('clientes:confirmar_carga_ejercicio'),
                         {'tramo': 1, 'respuesta': 'no_recuerdo', 'desde': '2026-09-19', 'hasta': '2026-11-18'})
        self.assertEqual(ConfirmacionCargaEjercicio.objects.count(), 1)
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        self.assertEqual(h['tramos'][1]['estado'], 'pendiente')

    def test_corregir_conserva_el_historial_y_manda_la_mas_reciente(self):
        self.arnold_datos()
        u = self.url('clientes:confirmar_carga_ejercicio')
        self.client.post(u, {'tramo': 1, 'respuesta': 'por_mancuerna', 'desde': '2026-09-19', 'hasta': '2026-11-18'})
        self.client.post(u, {'tramo': 1, 'respuesta': 'total_dos', 'desde': '2026-09-19', 'hasta': '2026-11-18'})
        self.assertEqual(ConfirmacionCargaEjercicio.objects.count(), 2)
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        ses = {s['fecha']: s for s in h['sesiones']}
        self.assertEqual(ses[date(2026, 11, 18)]['confirmacion'].respuesta, 'total_dos')
        self.assertAlmostEqual(ses[date(2026, 11, 18)]['series'][1]['carga_efectiva'], 20.0)    # 40 total → 20 por mancuerna
        vig = [x['vigente'] for x in svc_hist(h)]
        self.assertEqual(vig, [True, False])
        r = self.client.get(self.url('clientes:evolucion_ejercicio_detalle'))
        self.assertContains(r, 'sustituida o sin efecto')
        self.assertContains(r, 'Total de las dos')
        self.assertContains(r, 'Por mancuerna')
        r = self.client.get(u + '?tramo=1&corregir=%d' % h['confirmaciones'][1].id)
        self.assertContains(r, 'value="por_mancuerna" checked')

    def test_consulta_con_carga_pendiente_describe_pero_avisa(self):
        self.arnold_datos()
        c = svc.consulta(self.cliente, 'Press Arnold', 180, None, HOY)
        self.assertEqual(c['conclusion']['estado'], 'pendiente_carga')
        self.assertIn('Comparación pendiente de comprobar la carga.', c['conclusion']['avisos'])
        self.assertFalse(c['conclusion']['filtros']['valida'])
        self.assertTrue(c['puntos'])          # el historial sigue consultable
        r = self.client.get(self.url('clientes:evolucion_ejercicio') + '?dias=180')
        self.assertContains(r, 'Comparación pendiente de comprobar la carga.')

    def test_confirmada_la_comparacion_pasa_a_valida(self):
        self.reg(date(2026, 10, 8), self.arnold, [(40, 10, 7)], tipo='total', mult=1, total=True)
        self.reg(date(2026, 10, 27), self.arnold, [(40, 14, 7)], tipo='total', mult=1, total=True)
        self.client.post(self.url('clientes:confirmar_carga_ejercicio'),
                         {'tramo': 0, 'respuesta': 'por_mancuerna', 'desde': '2026-10-08', 'hasta': '2026-10-27'})
        c = svc.consulta(self.cliente, 'Press Arnold', 90, '40', HOY)
        self.assertTrue(c['conclusion']['filtros']['valida'])

    def test_no_alimenta_al_entrenador(self):
        from entrenos.services.evolucion_muscular_service import comparar_ejercicios
        self.arnold_datos()
        antes = comparar_ejercicios(self.cliente, HOY, 90)
        self.client.post(self.url('clientes:confirmar_carga_ejercicio'),
                         {'tramo': 1, 'respuesta': 'total_dos', 'desde': '2026-09-19', 'hasta': '2026-11-18'})
        self.assertEqual(antes, comparar_ejercicios(self.cliente, HOY, 90))
        import inspect
        from entrenos.services import evolucion_muscular_service as m
        self.assertNotIn('evolucion_ejercicio_service', inspect.getsource(m))


def svc_hist(h):
    vigentes = {s['confirmacion'].id for s in h['sesiones'] if s.get('confirmacion')}
    return [{'vigente': c.id in vigentes} for c in h['confirmaciones']]


class Pantallas(Base):
    def test_accesos_normales_desde_memoria(self):
        self.curl_datos()
        r = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertEqual(r.status_code, 200)
        url = reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'curl-femoral-tumbado'])
        self.assertContains(r, url)

    def test_pantalla_principal_selectores_y_filas(self):
        self.curl_datos()
        url = reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'curl-femoral-tumbado'])
        with mock.patch('entrenos.services.evolucion_ejercicio_service.date') as d:
            d.today.return_value = HOY
            d.side_effect = lambda *a, **k: date(*a, **k)
            r = self.client.get(url + '?dias=90&carga=40')
        self.assertEqual(r.status_code, 200)
        for t in ('30 días', '90 días', '180 días', '40 kg', '45 kg', '<svg', 'Últimas sesiones',
                  'Otra carga: 45 kg', 'Ver todas las series y otras cargas'):
            self.assertContains(r, t)
        self.assertContains(r, 'carga=45')      # tocar una sesión de otra carga la selecciona

    def test_parametros_invalidos_no_rompen(self):
        self.curl_datos()
        url = reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'curl-femoral-tumbado'])
        for q in ('?dias=abc', '?dias=7', '?carga=zzz', '?carga=999&dias=180', '?carga='):
            self.assertEqual(self.client.get(url + q).status_code, 200, q)

    def test_detalle_muestra_todas_las_series_originales(self):
        self.reg(date(2026, 10, 8), self.curl, [(20, 15, None), (45, 6, 8), (40, 10, 8)], aprox=(1,))
        r = self.client.get(reverse('clientes:evolucion_ejercicio_detalle', args=[self.cliente.id, 'curl-femoral-tumbado']))
        self.assertContains(r, 'calent.')
        self.assertContains(r, '45 kg')
        self.assertContains(r, 'Cómo se elige la serie de cada sesión')
        self.assertContains(r, 'no cambia el plan')

    def test_detalle_farmer_conserva_lo_antiguo_aparte(self):
        self.reg(date(2026, 8, 11), self.farmer, [(75, 37, None)], tipo='total')
        self.reg(date(2026, 9, 8), self.farmer, [(36, 41, None)], tipo='por_mano')
        r = self.client.get(reverse('clientes:evolucion_ejercicio_detalle', args=[self.cliente.id, 'farmer-walk']))
        self.assertContains(r, '41 (campo repeticiones)')
        self.assertContains(r, 'Carga por comprobar')

    def test_otro_usuario_no_ve_el_ejercicio(self):
        self.curl_datos()
        otro = User.objects.create_user(username='otro', password='x')
        Cliente.objects.get_or_create(user=otro, defaults={'nombre': 'O'})
        self.client.force_login(otro)
        r = self.client.get(reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'curl-femoral-tumbado']))
        self.assertEqual(r.status_code, 404)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'curl-femoral-tumbado']))
        self.assertEqual(r.status_code, 302)


class PerfilFuerza(Base):
    def test_incluye_la_mejor_serie_aunque_no_sea_la_ultima_ni_la_de_la_comparacion(self):
        self.reg(date(2026, 9, 1), self.curl, [(55, 10, 8)])
        self.reg(date(2026, 11, 10), self.curl, [(40, 12, 7)])
        p = svc.perfil_fuerza(self.cliente, HOY, 90)
        fila = next(x for x in p if x['ejercicio'] == 'Curl Femoral Tumbado')
        self.assertEqual((fila['peso'], fila['reps']), (55.0, 10))
        self.assertEqual(fila['rm'], 73.3)            # 55 × (1 + 10/30)
        self.assertEqual(fila['fecha'], date(2026, 9, 1))

    def test_series_estimacion_y_record_van_separados(self):
        e = self.reg(date(2026, 9, 1), self.curl, [(55, 10, 8)])
        RecordPersonal.objects.create(cliente=self.cliente, ejercicio_nombre='Curl Femoral Tumbado',
                                      tipo_record='peso_maximo', valor=60, entreno=e)
        fila = svc.perfil_fuerza(self.cliente, HOY, 90)[0]
        self.assertEqual(fila['registrada'], '55 kg × 10')
        self.assertEqual(fila['rm'], 73.3)
        self.assertEqual(fila['record'], 60.0)

    def test_no_cuenta_calentamientos_ni_ejercicios_de_distancia_o_tiempo(self):
        plancha = EjercicioBase.objects.create(nombre='Plancha (Plank)', grupo_muscular='core',
                                               tipo_progresion='progresion_tiempo')
        self.reg(date(2026, 11, 1), self.curl, [(80, 12, None), (40, 10, 8)], aprox=(1,))
        self.reg(date(2026, 11, 1), plancha, [(20, 60, 7)])
        self.reg(date(2026, 11, 2), self.farmer, [(36, 50, None)], tipo='por_mano', metros=True)
        nombres = [x['ejercicio'] for x in svc.perfil_fuerza(self.cliente, HOY, 90)]
        self.assertNotIn('Plancha (Plank)', nombres)
        self.assertNotIn('Farmer Walk', nombres)
        fila = svc.perfil_fuerza(self.cliente, HOY, 90)[0]
        self.assertEqual(fila['peso'], 40.0)

    def test_se_ve_en_memoria_con_las_tres_cosas(self):
        self.reg(date(2026, 11, 1), self.curl, [(55, 10, 8)])
        r = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertContains(r, 'Mejor serie: 55 kg × 10')
        self.assertContains(r, '1RM EST.')


class Ejemplos(Base):
    def test_ejemplos_disponibles_solo_con_registros(self):
        self.assertEqual(svc.ejemplos_disponibles(self.cliente, HOY), [])
        self.curl_datos()
        self.assertEqual([e['slug'] for e in svc.ejemplos_disponibles(self.cliente, HOY)], ['curl-femoral-tumbado'])

    def test_historial_con_entreno_sin_detalle_por_serie_se_conserva(self):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 2, 13))
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio='Curl Femoral Tumbado', peso_kg=55, series=4,
                                          repeticiones=7, completado=True)
        h = svc.cargar_historial(self.cliente, 'Curl Femoral Tumbado')
        self.assertEqual(h['sesiones'][0]['fuente'], 'media')
        r = self.client.get(reverse('clientes:evolucion_ejercicio_detalle', args=[self.cliente.id, 'curl-femoral-tumbado']))
        self.assertContains(r, 'media')


class DeteccionDeAmbiguedades(Base):
    """La ambigüedad sale de CÓMO se registró la carga, no de la escala de pesos configurada hoy."""

    def arnold_real(self):
        """Los registros reales de David (consulta de solo lectura, 19-nov-2026)."""
        a = self.arnold
        for f, p in [((2025, 9, 4), 40), ((2025, 9, 11), 40), ((2025, 9, 18), 40), ((2025, 9, 25), 37.5),
                     ((2025, 10, 9), 37.5), ((2025, 10, 16), 44), ((2026, 1, 8), 40), ((2026, 1, 15), 20),
                     ((2026, 1, 22), 20), ((2026, 1, 29), 40)]:
            self.reg(date(*f), a, [(p, 10, 8)], media=True)            # entrenos sin detalle por serie, sin tipo de carga
        self.reg(date(2026, 2, 5), a, [(40, 10, None)] * 4)             # series sin tipo de carga ni multiplicador
        self.reg(date(2026, 2, 12), a, [(42.5, 7, None)] * 4)
        for f, s in [((7, 24), [(30, 15, 7)] * 3), ((7, 31), [(32.5, 15, 7)] * 2), ((8, 7), [(35, 15, 7), (40, 12, 7)]),
                     ((8, 14), [(37.5, 15, 7)] * 4)]:
            self.reg(date(2026, *f), a, s)
        for f, s in [((9, 19), [(40, 12, 7)] * 2), ((10, 17), [(40, 9, 8), (30, 12, 8)]), ((10, 20), [(30, 12, 9)]),
                     ((10, 27), [(25, 15, 8)] * 3), ((11, 10), [(30, 12, 7)] * 2), ((11, 17), [(35, 8, 6)]),
                     ((11, 18), [(35, 12, 6), (40, 8, 7)])]:
            self.reg(date(2026, *f), a, s, tipo='total', mult=1, total=True)

    def test_tramos_del_arnold_con_los_registros_reales(self):
        self.arnold_real()
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        self.assertEqual(
            [(t['desde'], t['hasta'], t['n'], t['firma_txt']) for t in h['tramos']],
            [(date(2025, 9, 4), date(2025, 10, 16), 6, 'sin tipo de carga'),
             (date(2026, 1, 8), date(2026, 2, 12), 6, 'sin tipo de carga'),
             (date(2026, 7, 24), date(2026, 8, 14), 4, 'sin tipo de carga'),
             (date(2026, 9, 19), date(2026, 11, 18), 7, 'peso total ×1')])
        self.assertTrue(all(t['estado'] == 'pendiente' for t in h['tramos']))

    def test_el_tramo_de_septiembre_se_detecta_aunque_todos_los_pesos_esten_en_escala(self):
        # 40, 30, 20, 25 y 35 son múltiplos de 5: la escala actual (5 kg en total) no los pone en duda.
        self.arnold_real()
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        pesos = {x['peso'] for s in h['sesiones'] if s['fecha'] >= date(2026, 9, 19) for x in s['series']}
        self.assertTrue(all(p % 5 == 0 for p in pesos))
        self.assertEqual(h['tramos'][-1]['ambiguedad'], 'unidad_carga')

    def test_por_mano_x2_es_inequivoco_aunque_los_pesos_vayan_de_2_5_en_2_5(self):
        self.reg(date(2026, 10, 1), self.arnold, [(32.5, 12, 7)] * 2, tipo='por_mano', mult=2, total=True)
        self.reg(date(2026, 10, 8), self.arnold, [(37.5, 10, 7)] * 2, tipo='por_mano', mult=2, total=True)
        self.assertEqual(svc.cargar_historial(self.cliente, 'Press Arnold')['tramos'], [])
        c = svc.consulta(self.cliente, 'Press Arnold', 90, None, HOY)
        self.assertNotEqual(c['conclusion']['estado'], 'pendiente_carga')

    def test_por_mano_sin_multiplicador_no_basta(self):
        self.reg(date(2026, 10, 1), self.arnold, [(30, 12, 7)], tipo='por_mano')
        t = svc.cargar_historial(self.cliente, 'Press Arnold')['tramos']
        self.assertEqual(t[0]['firma_txt'], 'por mano')

    def test_otros_ejercicios_con_pesos_decimales_no_se_marcan(self):
        self.reg(date(2026, 10, 8), self.curl, [(53.8, 3, 8), (61.3, 3, 8)])
        self.assertEqual(svc.cargar_historial(self.cliente, 'Curl Femoral Tumbado')['tramos'], [])

    def test_un_hueco_de_mas_de_seis_semanas_separa_los_tramos(self):
        for dias, tramos in ((42, 1), (43, 2)):
            ConfirmacionCargaEjercicio.objects.all().delete()
            SerieRealizada.objects.all().delete()
            EntrenoRealizado.objects.all().delete()
            self.reg(date(2026, 8, 1), self.arnold, [(30, 12, 7)])
            self.reg(date(2026, 8, 1) + timedelta(days=dias), self.arnold, [(30, 12, 7)])
            self.assertEqual(len(svc.cargar_historial(self.cliente, 'Press Arnold')['tramos']), tramos, dias)

    def test_el_cambio_de_forma_de_registro_separa_los_tramos(self):
        self.reg(date(2026, 8, 1), self.arnold, [(30, 12, 7)])
        self.reg(date(2026, 8, 8), self.arnold, [(30, 12, 7)], tipo='total', mult=1, total=True)
        t = svc.cargar_historial(self.cliente, 'Press Arnold')['tramos']
        self.assertEqual([x['firma_txt'] for x in t], ['sin tipo de carga', 'peso total ×1'])

    def test_la_pantalla_dice_como_consta_el_registro(self):
        self.arnold_real()
        r = self.client.get(reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, 'press-arnold']) + '?dias=180')
        self.assertContains(r, 'Consta como: peso total ×1')
        self.assertContains(r, 'Consta como: sin tipo de carga')        # 24/07–14/08 cae dentro de 180 días
        self.assertContains(r, 'Tramos anteriores por comprobar')        # los de 2025 y enero-febrero, en el detalle
        r = self.client.get(reverse('clientes:confirmar_carga_ejercicio', args=[self.cliente.id, 'press-arnold']))
        self.assertContains(r, '19/09/2026 – 18/11/2026')                # por defecto, el tramo pendiente más reciente
        self.assertContains(r, 'consta como «peso total ×1»')


class ConfirmacionExacta(Base):
    """Una confirmación resuelve exactamente las fechas indicadas y conserva su historial."""

    def setUp(self):
        super().setUp()
        for f in [(10, 1), (10, 8), (10, 15), (10, 22), (10, 29)]:
            self.reg(date(2026, *f), self.arnold, [(30, 12, 7)], tipo='total', mult=1, total=True)
        self.url = reverse('clientes:confirmar_carga_ejercicio', args=[self.cliente.id, 'press-arnold'])

    def estado(self):
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        return {s['fecha'].strftime('%d/%m'): ('pend' if s['pendiente'] else s['confirmacion'].respuesta)
                for s in h['sesiones']}

    def guardar(self, respuesta, desde, hasta):
        return self.client.post(self.url, {'tramo': 0, 'respuesta': respuesta, 'desde': desde, 'hasta': hasta})

    def test_resuelve_exactamente_las_fechas_indicadas_extremos_incluidos(self):
        self.guardar('por_mancuerna', '2026-10-08', '2026-10-22')
        self.assertEqual(self.estado(), {'01/10': 'pend', '08/10': 'por_mancuerna', '15/10': 'por_mancuerna',
                                         '22/10': 'por_mancuerna', '29/10': 'pend'})

    def test_un_dia_de_fecha_unica(self):
        self.guardar('total_dos', '2026-10-15', '2026-10-15')
        self.assertEqual(self.estado()['15/10'], 'total_dos')
        self.assertEqual([k for k, v in self.estado().items() if v == 'pend'], ['01/10', '08/10', '22/10', '29/10'])

    def test_una_sesion_nueva_despues_de_lo_confirmado_sigue_pendiente(self):
        self.guardar('por_mancuerna', '2026-10-01', '2026-10-29')
        self.reg(date(2026, 11, 5), self.arnold, [(30, 12, 7)], tipo='total', mult=1, total=True)
        self.assertEqual(self.estado()['05/11'], 'pend')
        self.assertEqual(self.estado()['29/10'], 'por_mancuerna')

    def test_una_correccion_posterior_solo_cambia_sus_fechas_y_conserva_las_filas(self):
        self.guardar('por_mancuerna', '2026-10-01', '2026-10-29')
        self.guardar('total_dos', '2026-10-15', '2026-10-22')
        self.assertEqual(self.estado(), {'01/10': 'por_mancuerna', '08/10': 'por_mancuerna', '15/10': 'total_dos',
                                         '22/10': 'total_dos', '29/10': 'por_mancuerna'})
        self.assertEqual(list(ConfirmacionCargaEjercicio.objects.order_by('id').values_list('respuesta', 'desde', 'hasta')),
                         [('por_mancuerna', date(2026, 10, 1), date(2026, 10, 29)),
                          ('total_dos', date(2026, 10, 15), date(2026, 10, 22))])
        h = svc.cargar_historial(self.cliente, 'Press Arnold')
        self.assertEqual([c.respuesta for c in h['confirmaciones']], ['total_dos', 'por_mancuerna'])   # más reciente primero
        r = self.client.get(reverse('clientes:evolucion_ejercicio_detalle', args=[self.cliente.id, 'press-arnold']))
        self.assertContains(r, 'vigente')

    def test_no_lo_recuerdo_posterior_devuelve_esas_fechas_a_pendiente_sin_borrar_nada(self):
        self.guardar('por_mancuerna', '2026-10-01', '2026-10-29')
        self.guardar('no_recuerdo', '2026-10-08', '2026-10-15')
        self.assertEqual(self.estado()['08/10'], 'pend')
        self.assertEqual(self.estado()['22/10'], 'por_mancuerna')
        self.assertEqual(ConfirmacionCargaEjercicio.objects.count(), 2)

    def test_la_confirmacion_no_se_aplica_a_otro_tramo_ni_a_otro_ejercicio(self):
        self.reg(date(2026, 7, 1), self.arnold, [(30, 12, 7)])             # tramo anterior, sin tipo de carga
        self.guardar('por_mancuerna', '2026-10-01', '2026-10-29')
        e = self.estado()
        self.assertEqual(e['01/07'], 'pend')
        self.reg(date(2026, 10, 8), self.curl, [(40, 10, 8)])
        self.assertEqual(svc.cargar_historial(self.cliente, 'Curl Femoral Tumbado')['tramos'], [])


class NombreDelCatalogoEnProduccion(Base):
    """En producción el Farmer se llama «Farmer Walk (Paseo Del Granjero)»: debe verse como ejemplo."""

    def test_farmer_con_el_nombre_completo_del_catalogo_sale_en_memoria_y_se_abre(self):
        EjercicioBase.objects.filter(pk=self.farmer.pk).update(nombre='Farmer Walk (Paseo Del Granjero)')
        self.farmer.refresh_from_db()
        self.reg(date(2026, 9, 15), self.farmer, [(36, 47, None)], tipo='por_mano', metros=True)
        self.reg(date(2026, 11, 12), self.farmer, [(36, 67, None)], tipo='por_mano', metros=True)
        ej = {e['slug']: e for e in svc.ejemplos_disponibles(self.cliente, HOY)}
        self.assertEqual(ej['farmer-walk']['nombre'], 'Farmer Walk (Paseo Del Granjero)')
        for slug in ('farmer-walk', 'farmer-walk-paseo-del-granjero'):
            r = self.client.get(reverse('clientes:evolucion_ejercicio', args=[self.cliente.id, slug]) + '?dias=180')
            self.assertEqual(r.status_code, 200, slug)
            self.assertContains(r, 'Farmer Walk (Paseo Del Granjero)')
        r = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertContains(r, 'farmer-walk')

    def test_el_nombre_exacto_tiene_prioridad_sobre_el_prefijo(self):
        otro = EjercicioBase.objects.create(nombre='Press Arnold Alterno', grupo_muscular='hombros', tipo_progresion='peso_reps')
        self.reg(date(2026, 10, 1), otro, [(20, 10, 7)])
        self.reg(date(2026, 10, 1), self.arnold, [(40, 10, 7)])
        self.assertEqual(svc.resolver_ejercicio(self.cliente, 'press-arnold'), 'Press Arnold')
