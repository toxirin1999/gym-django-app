"""24-oct-2026 · Paso 4: recuperación desde el reloj (Atajo) y esfuerzo del fútbol (Strava)."""

import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import BitacoraDiaria, Cliente
from clientes.salud_iphone_service import guardar_checkin_iphone, leer_atajo
from entrenos.models import ActividadRealizada
from entrenos.services import recuperacion_service as rec
from entrenos.services.porque_decision_service import construir_porque
from entrenos.services.sesion_recomendada import _aplicar_contexto

HOY = timezone.localdate()


class ConCliente(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='recupera', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'R'})
        self.addCleanup(cache.clear)

    def reloj(self, dias_atras, hrv=None, fc=None, sueno=None, energia=None):
        b = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=hrv, fc_reposo=fc,
                                          horas_sueno=sueno, energia_subjetiva=energia)
        BitacoraDiaria.objects.filter(pk=b.pk).update(fecha=HOY - timedelta(days=dias_atras))

    def base(self, dias=10, hrv=50, fc=52, sueno=7.5):
        for d in range(1, dias + 1):
            self.reloj(d, hrv=hrv, fc=fc, sueno=sueno)

    def partido(self, dias_atras, minutos=None, pulso=None, esfuerzo=None, strava=True):
        from hyrox.models import StravaActivityRaw
        fecha = HOY - timedelta(days=dias_atras)
        a = ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='futbol', titulo='Fútbol', fecha=fecha,
            duracion_minutos=minutos, hr_media=pulso, fuente='strava' if strava else 'manual',
        )
        if strava:
            raw = {'type': 'Soccer', 'moving_time': (minutos or 0) * 60}
            if esfuerzo is not None:
                raw['suffer_score'] = esfuerzo
            StravaActivityRaw.objects.create(
                cliente=self.cliente, strava_id=10_000 + a.id, fecha_actividad=fecha, tipo_strava='Soccer',
                duracion_segundos=(minutos or 0) * 60, hr_media=pulso, raw_json=raw,
                estado='created', actividad_hub=a,
            )
        return a


# ── Recuperación ─────────────────────────────────────────────────────────────

class LecturaRecuperacion(ConCliente):
    def test_sin_datos_de_hoy_no_dice_nada(self):
        self.base()
        self.assertIsNone(rec.lectura_recuperacion(self.cliente, HOY))

    def test_rojo_con_dos_senales_y_frase_de_entrenador(self):
        self.base(hrv=50, fc=52, sueno=7.5)
        self.reloj(0, hrv=40, fc=59, sueno=7.5)
        r = rec.lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'rojo')
        self.assertEqual(sorted(r['senales']), ['hrv', 'pulso'])
        self.assertIn('Hoy vas justo', r['frase'])
        self.assertIn('20 % por debajo de lo normal en ti', r['frase'])
        self.assertIn('7 pulsaciones más alto de lo habitual (59 frente a 52)', r['frase'])
        self.assertNotIn('HRV', r['frase'])
        json.dumps(r)  # va al snapshot de la decisión

    def test_variabilidad_muy_hundida_basta_para_rojo(self):
        self.base(hrv=60)
        self.reloj(0, hrv=42)
        self.assertEqual(rec.lectura_recuperacion(self.cliente, HOY)['nivel'], 'rojo')

    def test_ambar_por_dormir_poco(self):
        self.base()
        self.reloj(0, hrv=50, fc=52, sueno=5.5)
        r = rec.lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'ambar')
        self.assertIn('has dormido 5 h 30', r['frase'])
        self.assertIn('Entrenamos normal', r['frase'])

    def test_verde_cuando_estas_fresco(self):
        self.base()
        self.reloj(0, hrv=56, fc=49, sueno=8)
        r = rec.lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'verde')
        self.assertTrue(r['frase'].startswith('Hoy estás fresco'))

    def test_sin_media_aun_no_compara(self):
        self.base(dias=3)
        self.reloj(0, hrv=30, fc=70, sueno=7.2)
        r = rec.lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'verde')  # solo cuenta el sueño, que no necesita media

    def test_sin_media_y_sin_sueno_bueno(self):
        self.reloj(0, hrv=30, fc=70, sueno=6.5)
        r = rec.lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'sin_referencia')
        self.assertIn('En unos días tendré tu media', r['frase'])


# ── Fútbol ───────────────────────────────────────────────────────────────────

class EsfuerzoFutbol(ConCliente):
    def test_sin_futbol_reciente(self):
        self.partido(5, 90, 150, 120)
        self.assertIsNone(rec.esfuerzo_futbol(self.cliente, HOY))

    def test_partido_duro_con_esfuerzo_de_strava(self):
        for d in (30, 23, 16, 9):
            self.partido(d, 80, 145, 100)
        self.partido(1, 95, 158, 150)
        r = rec.esfuerzo_futbol(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'alto')
        self.assertIn('Ayer el fútbol fue de los duros para ti (95 min, pulso medio 158)', r['frase'])

    def test_partido_suave_no_rebaja(self):
        for d in (30, 23, 16, 9):
            self.partido(d, 80, 145, 100)
        self.partido(1, 40, 120, 35)
        r = rec.esfuerzo_futbol(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'suave')
        self.assertIn('pierna normal', r['frase'])

    def test_sin_esfuerzo_strava_usa_minutos_por_pulso(self):
        for d in (30, 23, 16):
            self.partido(d, 80, 150)
        self.partido(2, 85, 152)
        r = rec.esfuerzo_futbol(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'normal')
        self.assertTrue(r['frase'].startswith('Anteayer jugaste un partido normal para ti'))

    def test_pocos_partidos_para_comparar(self):
        self.partido(1, 90, 150, 110, strava=False)
        r = rec.esfuerzo_futbol(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'sin_datos')
        self.assertIn('versión suave', r['frase'])

    def test_rato_corto_sin_historial_es_suave(self):
        self.partido(1, 30, 130)
        self.assertEqual(rec.esfuerzo_futbol(self.cliente, HOY)['nivel'], 'suave')

    def test_raw_json_guardado_como_texto(self):
        a = self.partido(1, 60, 140, 80)
        a.strava_source.raw_json = json.dumps({'suffer_score': 80})
        a.strava_source.save()
        a.refresh_from_db()
        self.assertEqual(rec._datos_partido(a)['esfuerzo'], 80)


# ── Decisión del día ─────────────────────────────────────────────────────────

def _ctx(**extra):
    ctx = {'lesion_activa': False, 'readiness_bajo': False, 'energia_baja': False,
           'futbol_reciente': False, 'hyrox_reciente': False, 'acwr_alto': False}
    ctx.update(extra)
    return ctx


PIERNA = {'ejercicios': [{'nombre': 'Sentadilla Hack', 'grupo_muscular': 'cuadriceps'}]}


class DecisionDelDia(SimpleTestCase):
    def test_rojo_rebaja_con_la_frase(self):
        recu = {'nivel': 'rojo', 'frase': 'Hoy vas justo: has dormido solo 5 h.'}
        d = _aplicar_contexto({'tipo': 'hoy', 'entrenamiento': PIERNA}, _ctx(recuperacion=recu), HOY)
        self.assertEqual((d['estado'], d['causa_principal']), ('version_reducida', 'recuperacion_baja'))
        self.assertEqual(d['mensaje'], recu['frase'])
        self.assertEqual(construir_porque(d), recu['frase'])

    def test_ambar_entrena_normal_y_lo_dice(self):
        recu = {'nivel': 'ambar', 'frase': 'Hoy no estás al cien: has dormido solo 5 h 30.'}
        d = _aplicar_contexto({'tipo': 'hoy', 'entrenamiento': PIERNA}, _ctx(recuperacion=recu), HOY)
        self.assertEqual(d['estado'], 'entrenar')
        self.assertEqual(construir_porque(d), recu['frase'])

    def test_futbol_suave_no_rebaja_la_pierna(self):
        futbol = {'nivel': 'suave', 'frase': 'Ayer el fútbol fue tranquilo.'}
        d = _aplicar_contexto({'tipo': 'hoy', 'entrenamiento': PIERNA},
                              _ctx(futbol_reciente=True, futbol_esfuerzo=futbol), HOY)
        self.assertEqual(d['estado'], 'entrenar')

    def test_futbol_duro_rebaja_con_su_frase(self):
        futbol = {'nivel': 'alto', 'frase': 'Ayer el fútbol fue de los duros para ti.'}
        d = _aplicar_contexto({'tipo': 'hoy', 'entrenamiento': PIERNA},
                              _ctx(futbol_reciente=True, futbol_esfuerzo=futbol), HOY)
        self.assertEqual((d['estado'], d['mensaje']), ('version_reducida', futbol['frase']))
        self.assertEqual(construir_porque(d), futbol['frase'])

    def test_futbol_sin_strava_sigue_como_antes(self):
        d = _aplicar_contexto({'tipo': 'hoy', 'entrenamiento': PIERNA}, _ctx(futbol_reciente=True), HOY)
        self.assertEqual(d['causa_principal'], 'futbol_reciente')
        self.assertIn('fútbol', construir_porque(d))


class ContextoFisicoReal(ConCliente):
    def test_el_contexto_trae_la_lectura(self):
        from entrenos.services.sesion_recomendada import _obtener_contexto_fisico
        self.base()
        self.reloj(0, hrv=40, fc=60, sueno=5)
        ctx = _obtener_contexto_fisico(self.cliente, HOY)
        self.assertEqual(ctx['recuperacion']['nivel'], 'rojo')


# ── Atajo del iPhone ─────────────────────────────────────────────────────────

class LeerAtajo(SimpleTestCase):
    def test_numeros_limpios(self):
        self.assertEqual(leer_atajo({'hrv': 48, 'pulso_reposo': 52, 'sueno': 7.5}, HOY),
                         {HOY: {'hrv_ms': 48, 'fc_reposo': 52, 'horas_sueno': 7.5}})

    def test_texto_con_coma_unidades_y_listas(self):
        r = leer_atajo({'hrv': '41,2\n55,8', 'pulso_reposo': '53 lpm', 'sueno': '450'}, HOY)[HOY]
        self.assertEqual(r, {'hrv_ms': 48, 'fc_reposo': 53, 'horas_sueno': 7.5})

    def test_sueno_en_segundos_y_minutos(self):
        self.assertEqual(leer_atajo({'sueno': 27000}, HOY)[HOY]['horas_sueno'], 7.5)
        self.assertEqual(leer_atajo({'sueno_minutos': 90}, HOY)[HOY]['horas_sueno'], 1.5)

    def test_sueno_en_formato_reloj(self):
        self.assertEqual(leer_atajo({'sueno': '7:12:00'}, HOY)[HOY]['horas_sueno'], 7.2)
        self.assertEqual(leer_atajo({'sueno': '6:30'}, HOY)[HOY]['horas_sueno'], 6.5)

    def test_valores_absurdos_o_vacios(self):
        self.assertEqual(leer_atajo({'hrv': '', 'pulso_reposo': 5, 'sueno': 0}, HOY), {})
        self.assertEqual(leer_atajo({}, HOY), {})

    def test_fecha_opcional(self):
        ayer = HOY - timedelta(days=1)
        self.assertIn(ayer, leer_atajo({'hrv': 50, 'fecha': ayer.isoformat()}, HOY))


class EndpointAtajo(ConCliente):
    def test_el_atajo_rellena_el_checkin_de_hoy(self):
        token = self.cliente.get_or_create_api_token()
        r = self.client.post(reverse('clientes:api_salud_iphone'),
                             data=json.dumps({'hrv': '47,6', 'pulso_reposo': 51, 'sueno': 432}),
                             content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(r.status_code, 200)
        b = BitacoraDiaria.objects.get(cliente=self.cliente, fecha=HOY)
        self.assertEqual((b.hrv_ms, b.fc_reposo, float(b.horas_sueno)), (48, 51, 7.2))

    def test_el_formato_de_health_auto_export_sigue_valiendo(self):
        guardado = guardar_checkin_iphone(self.cliente, {'data': {'metrics': [
            {'name': 'resting_heart_rate', 'units': 'count/min', 'data': [{'date': HOY.isoformat(), 'qty': 50}]},
        ]}}, hoy=HOY)
        self.assertEqual(guardado, {HOY.isoformat(): {'fc_reposo': 50}})

    def test_la_pagina_lee_la_base_de_datos_no_la_cache(self):
        token = self.cliente.get_or_create_api_token()
        self.client.post(reverse('clientes:api_salud_iphone'), data=json.dumps({'pulso_reposo': 60}),
                         content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}')
        cache.clear()  # en producción la caché es por proceso y se borra al recargar
        self.client.force_login(self.user)
        r = self.client.get(reverse('clientes:salud_iphone'))
        self.assertContains(r, 'pulso en reposo 60')
        self.assertNotContains(r, 'Todavía no ha llegado nada')

    def test_la_pagina_explica_el_atajo(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('clientes:salud_iphone'))
        self.assertContains(r, 'Crear el Atajo')
        self.assertContains(r, 'pulso_reposo')
        self.assertNotContains(r, 'Health Auto Export')


# ── Cierre y comando ─────────────────────────────────────────────────────────

class ComprobacionCierre(ConCliente):
    def _entreno(self, dias_atras, causa, rpe):
        from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionVersion
        from rutinas.models import Rutina
        fecha = HOY - timedelta(days=dias_atras)
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=Rutina.objects.create(nombre=f'R{dias_atras}'),
                                            fecha=fecha)
        if causa:
            e.gym_decision_version = GymDecisionVersion.objects.create(
                cliente=self.cliente, fecha=fecha, version=1, decision_id=f'd-{fecha}',
                origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64, base_fingerprint='b' * 64,
                postura='empujar', snapshot={'causa_principal': causa, 'estado': 'version_reducida'},
            )
            e.save(update_fields=['gym_decision_version'])
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio='Remo', peso_kg=50, series=3,
                                          repeticiones=10, rpe=rpe, completado=True)
        return e

    def test_rebaja_justa(self):
        self._entreno(5, None, 8)
        e = self._entreno(0, 'recuperacion_baja', 8)
        frase = rec.comprobacion_cierre(self.cliente, e)
        self.assertIn('porque llegabas cansado', frase)
        self.assertIn('la rebaja fue justa', frase)

    def test_aun_asi_costo_mas(self):
        self._entreno(5, None, 7)
        e = self._entreno(0, 'futbol_reciente', 9)
        self.assertIn('te costó más de lo normal', rec.comprobacion_cierre(self.cliente, e))

    def test_sesion_normal_no_dice_nada(self):
        self._entreno(5, None, 7)
        self.assertIsNone(rec.comprobacion_cierre(self.cliente, self._entreno(0, 'sesion_hoy', 8)))

    def test_se_ve_en_el_cierre(self):
        self._entreno(5, None, 8)
        e = self._entreno(0, 'recuperacion_baja', 8)
        self.client.force_login(self.user)
        r = self.client.get(reverse('entrenos:post_entreno_resumen', args=[self.cliente.id, e.id]))
        self.assertContains(r, 'Cómo llegabas hoy')


class ComandoVerRecuperacion(ConCliente):
    def test_solo_lectura(self):
        self.base()
        self.reloj(0, hrv=40, fc=60, sueno=5)
        self.partido(1, 90, 150, 120)
        antes = (BitacoraDiaria.objects.count(), ActividadRealizada.objects.count())
        out = StringIO()
        call_command('ver_recuperacion', str(self.cliente.id), stdout=out)
        self.assertIn('Nivel: rojo', out.getvalue())
        self.assertIn('FÚTBOL', out.getvalue())
        self.assertEqual(antes, (BitacoraDiaria.objects.count(), ActividadRealizada.objects.count()))
