"""17-nov-2026 · Repaso del Día 2 (notas 28, 29, 36, 42, 44, 45, 47, 52, sin apretar y señales)."""

from datetime import time, timedelta
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from entrenos.models import EjercicioRealizado, EntrenoRealizado
from entrenos.services.orden_sesiones_service import (
    ANTERIOR, DESCONOCIDO, POSTERIOR, orden_entre_sesiones,
)
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()


def _s(fecha, ejecucion=None, hora=None):
    return SimpleNamespace(fecha=fecha, fecha_ejecucion=ejecucion, hora_inicio=hora)


class OrdenEntreSesiones(SimpleTestCase):
    def test_fechas_distintas_y_coincidentes(self):
        self.assertEqual(orden_entre_sesiones(_s(HOY - timedelta(days=7)), _s(HOY)), ANTERIOR)
        self.assertEqual(orden_entre_sesiones(_s(HOY), _s(HOY - timedelta(days=7))), POSTERIOR)

    def test_mismo_dia_sin_hora_no_se_sabe(self):
        self.assertEqual(orden_entre_sesiones(_s(HOY), _s(HOY)), DESCONOCIDO)

    def test_mismo_dia_con_una_sola_hora_no_se_sabe(self):
        self.assertEqual(orden_entre_sesiones(_s(HOY, hora=time(8, 0)), _s(HOY)), DESCONOCIDO)

    def test_mismo_dia_con_la_misma_hora_no_se_sabe(self):
        self.assertEqual(orden_entre_sesiones(_s(HOY, hora=time(8, 0)), _s(HOY, hora=time(8, 0))), DESCONOCIDO)

    def test_mismo_dia_con_horas_distintas_se_ordena(self):
        self.assertEqual(orden_entre_sesiones(_s(HOY, hora=time(8, 0)), _s(HOY, hora=time(18, 0))), ANTERIOR)
        self.assertEqual(orden_entre_sesiones(_s(HOY, hora=time(18, 0)), _s(HOY, hora=time(8, 0))), POSTERIOR)

    def test_plan_y_ejecucion_que_discrepan_no_se_sabe(self):
        # plan antes, pero ejecutada después: el plan dice «anterior», la ejecución «posterior».
        movida = _s(HOY - timedelta(days=5), ejecucion=HOY - timedelta(days=1))
        actual = _s(HOY - timedelta(days=3), ejecucion=HOY - timedelta(days=3))
        self.assertEqual(orden_entre_sesiones(movida, actual), DESCONOCIDO)

    def test_la_ejecucion_manda_junto_al_plan_cuando_coinciden(self):
        a = _s(HOY - timedelta(days=7), ejecucion=HOY - timedelta(days=6))
        b = _s(HOY, ejecucion=HOY)
        self.assertEqual(orden_entre_sesiones(a, b), ANTERIOR)


class Nota52CierreHistorico(Base):
    def base(self, nombre):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='x', tipo_progresion='peso_reps')

    def cambios(self, entreno):
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes
        return _cambios_relevantes(self.cliente, entreno, list(EjercicioRealizado.objects.filter(entreno=entreno)))

    def test_el_cierre_antiguo_no_compara_con_una_sesion_posterior(self):
        b = self.base('Jalón al Pecho')
        e0 = self.entreno(HOY - timedelta(days=21), {b.nombre: '12-15'})
        self.hacer(e0, b, [(50, 15, 7), (50, 15, 7)])
        e1 = self.entreno(HOY - timedelta(days=14), {b.nombre: '4-6'})
        self.hacer(e1, b, [(60, 6, 7), (60, 6, 7)])
        e2 = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e2, b, [(75, 6, 7), (75, 6, 7)])
        # El cierre de la sesión intermedia no cita la posterior (75 kg).
        texto = ' | '.join(c['detalle'] for c in self.cambios(e1))
        self.assertNotIn('75', texto)
        # El cierre de la última sigue comparando con la intermedia: 60 × 6 → 75 × 6.
        ultimo = self.cambios(e2)
        self.assertEqual(len(ultimo), 1)
        self.assertIn('60 × 6 → 75 × 6', ultimo[0]['detalle'])
        self.assertIn('+15', ultimo[0]['detalle'])

    def test_sin_sesion_anterior_valida_queda_sin_comparacion(self):
        b = self.base('Jalón al Pecho')
        e1 = self.entreno(HOY - timedelta(days=14), {b.nombre: '4-6'})
        self.hacer(e1, b, [(60, 6, 7), (60, 6, 7)])
        e2 = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e2, b, [(75, 6, 7), (75, 6, 7)])
        self.assertEqual(self.cambios(e1), [])

    def test_mismo_dia_sin_hora_omite_la_comparacion(self):
        b = self.base('Remo con Mancuerna')
        e0 = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e0, b, [(30, 6, 7), (30, 6, 7)])
        e1 = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=HOY - timedelta(days=1))
        self.hacer(e1, b, [(32.5, 5, 7), (32.5, 5, 7)])
        e2 = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=HOY - timedelta(days=1))
        self.hacer(e2, b, [(35, 4, 7), (35, 4, 7)])
        self.assertEqual(self.cambios(e2), [])

    def test_mismo_dia_con_horas_distintas_compara_con_la_anterior_del_dia(self):
        b = self.base('Remo con Mancuerna')
        e1 = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=HOY - timedelta(days=1), hora_inicio=time(8, 0))
        self.hacer(e1, b, [(32.5, 5, 7), (32.5, 5, 7)])
        e2 = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=HOY - timedelta(days=1), hora_inicio=time(18, 0))
        self.hacer(e2, b, [(35, 4, 7), (35, 4, 7)])
        texto = ' | '.join(c['detalle'] for c in self.cambios(e2))
        self.assertIn('32,5 × 5 → 35 × 4', texto)

    def test_sesion_movida_y_registrada_despues_de_otra_hecha_mas_tarde_no_se_compara(self):
        b = self.base('Press Militar')
        # Planificada hace 5 días, pero se hizo (y se guardó) ayer.
        movida = self.entreno(HOY - timedelta(days=5), {b.nombre: '4-6'})
        self.hacer(movida, b, [(60, 6, 7), (60, 6, 7)])
        EntrenoRealizado.objects.filter(pk=movida.pk).update(fecha_ejecucion=HOY - timedelta(days=1))
        # La otra se planificó hace 3 días y se hizo ese día.
        otra = self.entreno(HOY - timedelta(days=3), {b.nombre: '4-6'})
        self.hacer(otra, b, [(65, 6, 7), (65, 6, 7)])
        EntrenoRealizado.objects.filter(pk=otra.pk).update(fecha_ejecucion=HOY - timedelta(days=3))
        otra.refresh_from_db()
        # Por el plan, «movida» sería anterior a «otra»; por la ejecución, posterior: se omite.
        self.assertEqual(self.cambios(otra), [])

    def test_tope_de_maquina_no_toma_datos_de_una_sesion_posterior(self):
        b = self.base('Abducción en Máquina')
        e0 = self.entreno(HOY - timedelta(days=21), {b.nombre: '15-20'})
        self.hacer(e0, b, [(60, 10, 8), (60, 10, 8)])
        e1 = self.entreno(HOY - timedelta(days=14), {b.nombre: '15-20'})
        self.hacer(e1, b, [(60, 12, 8), (60, 12, 8)])
        e2 = self.entreno(HOY - timedelta(days=7), {b.nombre: '15-20'})
        self.hacer(e2, b, [(60, 12, 8), (60, 12, 8)])
        EjercicioRealizado.objects.filter(entreno__in=[e0, e1, e2]).update(es_tope_maquina=True)
        # Cierre de e1: la anterior es e0 (10 → 12 reps: progresó). La posterior (e2, 12 reps)
        # daría «mismas reps».
        texto = ' | '.join(c['detalle'] for c in self.cambios(e1))
        self.assertIn('progresó por reps', texto)
        self.assertNotIn('mismas reps', texto)

    def test_lo_que_compruebo_hoy_usa_solo_la_sesion_anterior(self):
        from entrenos.services.cierre_porque_service import _sesion_anterior
        b = self.base('Jalón al Pecho')
        e0 = self.entreno(HOY - timedelta(days=14), {b.nombre: '4-6'})
        self.hacer(e0, b, [(60, 6, 7)])
        e1 = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e1, b, [(65, 6, 7)])
        e2 = self.entreno(HOY, {b.nombre: '4-6'})
        self.hacer(e2, b, [(75, 6, 7)])
        previa = _sesion_anterior(self.cliente, e1, b.nombre)
        self.assertEqual(previa.entreno_id, e0.id)


class Nota42ComprobacionCitaUnaSerie(SimpleTestCase):
    def _log(self, accion='subir_peso', peso=65):
        return SimpleNamespace(ejercicio='Jalón al Pecho', accion=accion, peso_sugerido=peso,
                               resultado='validada', notas_resultado='', entreno_origen_id=None)

    def _despues(self):
        return {
            'peso': 75.0, 'reps': 6, 'rpe': 6.0, 'entreno_id': 0, 'fecha': HOY,
            'series': [
                {'peso': 65.0, 'reps': 6, 'rpe': 6.0, 'metros': None},
                {'peso': 70.0, 'reps': 6, 'rpe': 6.0, 'metros': None},
                {'peso': 75.0, 'reps': 6, 'rpe': 7.0, 'metros': None},
            ],
        }

    def test_cita_el_peso_de_la_decision_con_su_propio_rpe(self):
        from entrenos.services.aprendizaje_decisiones_service import frase_decision
        frase = frase_decision(self._log(), etiqueta='Hoy', despues=self._despues())
        self.assertIn('subí el peso a 65 kg', frase)
        self.assertIn('Hoy: 65 kg × 6 con RPE 6', frase)
        self.assertNotIn('75 kg × 6 con RPE 6', frase)

    def test_sin_serie_al_peso_de_la_decision_cita_la_de_referencia_con_su_rpe(self):
        from entrenos.services.aprendizaje_decisiones_service import frase_decision
        despues = self._despues()
        despues['series'] = [s for s in despues['series'] if s['peso'] != 65.0]
        frase = frase_decision(self._log(), etiqueta='Hoy', despues=despues)
        self.assertIn('Hoy: 75 kg × 6 con RPE 7', frase)

    def test_el_detalle_usa_el_mismo_dato(self):
        from entrenos.services.aprendizaje_decisiones_service import detalle_decision
        detalle = detalle_decision(self._log(), self._despues())
        self.assertIn('65 kg × 6 con RPE 6', detalle['ocurrido'])


class Nota40ArnoldMismaCuenta(SimpleTestCase):
    def test_el_mensaje_del_ejercicio_usa_la_mediana_como_la_regla_del_cierre(self):
        from pathlib import Path
        fuente = (Path(__file__).parent / 'templates' / 'entrenos' / 'entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('baseReglaEj+(conMargen?2:1)', fuente)
        self.assertNotIn('let objSig=mejorEj+(conMargen?2:1);', fuente)

    def test_8_y_9_con_margen_piden_10_igual_que_el_cierre(self):
        from entrenos.services.ultima_sesion_service import objetivo_reps_hoy
        # Regla del cierre: mediana 8,5 → 8 (redondeo par) → +1 → +1 por margen.
        base = int(round(8.5))
        self.assertEqual(objetivo_reps_hoy(base, (8, 12)) + 1, 10)


class Textos(SimpleTestCase):
    def test_nota47_el_cierre_dice_reps_y_no_series_de_fuerza(self):
        from pathlib import Path
        fuente = (Path(__file__).parent / 'templates' / 'entrenos' / 'post_entreno_resumen.html').read_text(encoding='utf-8')
        self.assertNotIn('series de fuerza', fuente)
        self.assertIn('<span class="work-detail">reps</span>', fuente)

    def test_nota36_un_solo_nombre_para_el_dia_reducido(self):
        from pathlib import Path
        base = Path(__file__).parent
        for ruta in ('templates/entrenos/entrenamiento_activo.html', 'templates/entrenos/briefing_entrenamiento.html',
                     'services/cierre_entrenamiento_service.py', 'services/recuperacion_service.py',
                     'services/sesion_recomendada.py', 'services/porque_decision_service.py'):
            texto = (base / ruta).read_text(encoding='utf-8')
            for viejo in ('versión esencial', 'Versión esencial', 'versión suave', 'Sesión ajustada'):
                self.assertNotIn(viejo, texto, f'{viejo} en {ruta}')
        self.assertIn('Versión reducida', (base / 'services/cierre_entrenamiento_service.py').read_text(encoding='utf-8'))

    def test_nota45_con_menos_esfuerzo_no_dice_que_el_ajuste_fue_justo(self):
        from pathlib import Path
        texto = (Path(__file__).parent / 'services' / 'recuperacion_service.py').read_text(encoding='utf-8')
        self.assertIn('quizá no hacía falta ajustar tanto', texto)


class Nota29SinPromesaVacia(SimpleTestCase):
    def test_ningun_texto_promete_volver_a_comprobar(self):
        from pathlib import Path
        texto = (Path(__file__).parent / 'services' / 'decision_log_service.py').read_text(encoding='utf-8')
        self.assertNotIn('lo vuelvo a comprobar', texto)
        self.assertEqual(texto.count('El resultado de hoy queda sin evaluar'), 3)


class SinApretar(Base):
    def base(self, nombre):
        return EjercicioBase.objects.create(nombre=nombre, grupo_muscular='x', tipo_progresion='peso_reps')

    def _ej(self, nombre, peso, rpe=7, rpe_plan=8):
        return {'nombre': nombre, 'tipo_progresion': 'peso_reps', 'repeticiones_plan': '4-6',
                'rpe_objetivo': rpe, 'rpe_objetivo_plan': rpe_plan, 'peso_kg': peso,
                'regla_carga': 'subir', 'reps_objetivo_hoy': 4}

    def test_mantiene_el_peso_previsto_si_las_reps_entran_dentro_del_rpe(self):
        from entrenos.services.cerebro_carga_service import limitar_esfuerzo
        b = self.base('Jalón al Pecho')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e, b, [(60, 6, 5), (60, 6, 5)])  # «5 o menos»: se estima como RPE 4
        ej = self._ej(b.nombre, 65)
        self.assertIsNone(limitar_esfuerzo(self.cliente, ej, HOY))
        self.assertEqual(ej['peso_kg'], 65)

    def test_baja_el_peso_si_para_cumplir_las_reps_hay_que_pasarse_del_rpe(self):
        from entrenos.services.cerebro_carga_service import limitar_esfuerzo
        b = self.base('Jalón al Pecho')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e, b, [(60, 6, 7), (60, 6, 7)])
        ej = self._ej(b.nombre, 75)
        cambio = limitar_esfuerzo(self.cliente, ej, HOY)
        self.assertIsNotNone(cambio)
        self.assertLess(ej['peso_kg'], 75)
        self.assertGreaterEqual(ej['peso_kg'], 60)
        self.assertTrue(ej['limite_esfuerzo'])
        self.assertIn('RPE 7 en vez de 8', ej['progresion_motivo'])
        self.assertIn('75 kg', ej['progresion_motivo'])

    def test_nunca_baja_del_peso_de_la_ultima_vez(self):
        from entrenos.services.cerebro_carga_service import limitar_esfuerzo
        b = self.base('Jalón al Pecho')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e, b, [(60, 4, 9), (60, 4, 9)])
        ej = self._ej(b.nombre, 65, rpe=6, rpe_plan=8)
        limitar_esfuerzo(self.cliente, ej, HOY)
        self.assertGreaterEqual(ej['peso_kg'], 60)

    def test_sin_limite_de_esfuerzo_no_toca_nada(self):
        from entrenos.services.cerebro_carga_service import limitar_esfuerzo
        b = self.base('Jalón al Pecho')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '4-6'})
        self.hacer(e, b, [(60, 6, 7), (60, 6, 7)])
        ej = self._ej(b.nombre, 75, rpe=8, rpe_plan=8)
        self.assertIsNone(limitar_esfuerzo(self.cliente, ej, HOY))
        self.assertEqual(ej['peso_kg'], 75)


class Nota28RepsEditadas(TestCase):
    def setUp(self):
        from clientes.models import Cliente
        from rutinas.models import Rutina
        self.user = User.objects.create_user(username='reps_editadas', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'RE', 'dias_disponibles': 4})
        Rutina.objects.get_or_create(nombre='Push Day Test')
        EjercicioBase.objects.get_or_create(
            nombre='Press banca', defaults={'grupo_muscular': 'pecho', 'tipo_progresion': 'peso_reps'})
        self.client.force_login(self.user)

    def _post(self, editadas):
        data = {
            'fecha': '2026-06-10', 'rutina_nombre': 'Push Day Test', 'sesion_programada_id': '',
            'modo_reducido': '0', 'duracion_minutos_real': '40',
            'series_completadas': '', 'series_totales': '', 'ejercicios_completados': '',
            'ejercicios_totales': '', 'volumen_total_sesion': '', 'rpe_medio_sesion': '',
            'rpe_global_sesion': '', 'energia_pre_sesion': '',
            'ej1_nombre': 'Press banca', 'ej1_tipo_progresion': 'peso_reps', 'ej1_es_principal': '',
            'ej1_es_tope_maquina': 'false', 'ej1_molestia_reportada': 'false',
        }
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '60'
            data[f'ej1_reps_{i}'] = '8'
            data[f'ej1_rpe_{i}'] = '7'
            data[f'ej1_completado_{i}'] = '1'
            if i in editadas:
                data[f'ej1_reps_editadas_{i}'] = '1'
            else:
                data[f'ej1_reps_editadas_{i}'] = '0'
        return data

    def test_cada_serie_guarda_si_se_editaron_las_reps(self):
        from entrenos.models import SerieRealizada
        url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})
        self.client.post(url, self._post(editadas={2}))
        series = {s.serie_numero: s.reps_editadas for s in SerieRealizada.objects.filter(entreno__cliente=self.cliente)}
        self.assertEqual(series, {1: False, 2: True, 3: False})

    def test_sin_el_campo_las_reps_no_se_marcan_como_editadas(self):
        from entrenos.models import SerieRealizada
        data = self._post(editadas=set())
        for i in range(1, 4):
            data.pop(f'ej1_reps_editadas_{i}')
        url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})
        self.client.post(url, data)
        self.assertFalse(SerieRealizada.objects.filter(entreno__cliente=self.cliente, reps_editadas=True).exists())

    def test_la_marca_no_cambia_peso_reps_ni_rpe(self):
        from entrenos.models import SerieRealizada
        url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})
        self.client.post(url, self._post(editadas={1, 2, 3}))
        for s in SerieRealizada.objects.filter(entreno__cliente=self.cliente):
            self.assertEqual((float(s.peso_kg), s.repeticiones, s.rpe_real), (60.0, 8, 7.0))

    def test_la_pantalla_declara_el_campo_y_la_marca(self):
        from pathlib import Path
        fuente = (Path(__file__).parent / 'templates' / 'entrenos' / 'entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('_reps_editadas_{{ sn }}', fuente)
        self.assertIn("document.getElementById('repsed-'+k)", fuente)


class SenalesAlDecidirTests(TestCase):
    """Registro «Qué sabía el entrenador al decidir»."""

    def setUp(self):
        from django.contrib.auth.models import User
        from clientes.models import Cliente
        u = User.objects.create_user('sad', password='x')
        self.cliente = Cliente.objects.filter(user=u).first() or Cliente.objects.create(user=u)

    def _log(self):
        from entrenos.models import GymDecisionLog
        return GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Jalon', ejercicio_normalizado='jalon',
            accion='mantener', motivo='x', peso_anterior=60, reps_anteriores=6, rpe_anterior=7)

    def test_se_guardan_senales_al_crear(self):
        log = self._log()
        log.refresh_from_db()
        s = log.senales_al_decidir
        self.assertIn('calculado_en', s)
        self.assertEqual(s['ultima_vez']['peso'], 60)
        self.assertIn('veredicto_dia', s)

    def test_hora_de_llegada_del_reloj_consta(self):
        from clientes.models import BitacoraDiaria
        from django.utils import timezone
        b = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=55, horas_sueno=7)
        BitacoraDiaria.objects.filter(pk=b.pk).update(salud_importado_en=timezone.now())
        log = self._log()
        log.refresh_from_db()
        self.assertEqual(log.senales_al_decidir['salud_hoy']['hrv_ms'], 55)
        self.assertTrue(log.senales_al_decidir['salud_hoy']['disponible_desde'])

    def test_no_se_sobrescribe_y_las_lineas_se_muestran(self):
        from entrenos.services.senales_al_decidir_service import lineas_para_mostrar, registrar_senales
        log = self._log()
        log.refresh_from_db()
        antes = dict(log.senales_al_decidir)
        registrar_senales(log)
        log.refresh_from_db()
        self.assertEqual(antes, log.senales_al_decidir)
        self.assertTrue(lineas_para_mostrar(log))
