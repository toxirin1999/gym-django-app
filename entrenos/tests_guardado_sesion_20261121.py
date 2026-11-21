"""Paquete 1 · Guardado (21-nov-2026).

Identificador de sesion, huella del contenido, correccion de una sesion ya
guardada y conflicto entre dos correcciones. Las pruebas de concurrencia real
(dos hilos) estan en ``tests_guardado_sesion_concurrencia_20261121.py`` y
necesitan MariaDB/MySQL.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import (
    CorreccionSesionGym, EjercicioRealizado, EntrenoRealizado, GymDecisionLog,
    RecordPersonal, SerieRealizada,
)
from entrenos.services import guardado_sesion_service as gs
from rutinas.models import EjercicioBase

NOMBRE = 'Press Banca Guardado'
TOKEN_A = 'tokenAAAAAAAAAAAAAAAA1'
TOKEN_B = 'tokenBBBBBBBBBBBBBBBB2'


def datos(token=TOKEN_A, reps=('8', '8'), peso=('60', '62.5'), rutina='Dia Guardado', **extra):
    d = {
        'fecha': date.today().isoformat(),
        'rutina_nombre': rutina,
        'sesion_token': token,
        'ej1_nombre': NOMBRE, 'ej1_tipo_progresion': 'peso_reps',
        'duracion_minutos_real': '50',
    }
    for i, (p, r) in enumerate(zip(peso, reps), start=1):
        d.update({
            f'ej1_peso_{i}': p, f'ej1_reps_{i}': r, f'ej1_rpe_{i}': '8',
            f'ej1_completado_{i}': '1',
        })
    d.update(extra)
    return d


class GuardadoConIdentificador(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('guardado21', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        EjercicioBase.objects.create(nombre=NOMBRE, grupo_muscular='pecho')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk])

    def enviar(self, payload):
        return self.client.post(self.url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def entrenos(self):
        return EntrenoRealizado.objects.filter(cliente=self.cliente)

    # -- identidad -----------------------------------------------------------

    def test_primer_envio_guarda_token_huella_y_revision(self):
        r = self.enviar(datos()).json()
        self.assertTrue(r['success'])
        e = self.entrenos().get()
        self.assertEqual(e.sesion_token, TOKEN_A)
        self.assertEqual(e.huella_contenido, gs.huella_de_post(self._post(datos())))
        self.assertEqual(e.revision, 1)
        self.assertEqual(r['huella'], e.huella_contenido)
        self.assertEqual(r['revision'], 1)

    def _post(self, d):
        from django.http import QueryDict
        q = QueryDict(mutable=True)
        for k, v in d.items():
            q[k] = v
        return q

    def test_reintento_identico_pasada_la_medianoche_no_duplica(self):
        primero = self.enviar(datos()).json()
        manana = timezone.localdate() + timedelta(days=1)
        with patch('django.utils.timezone.localdate', return_value=manana):
            segundo = self.enviar(datos()).json()
        self.assertTrue(segundo['ya_guardado'])
        self.assertEqual(segundo['entreno_id'], primero['entreno_id'])
        self.assertEqual(segundo['huella'], primero['huella'])
        self.assertEqual(self.entrenos().count(), 1)

    def test_dos_sesiones_reales_de_la_misma_rutina_son_dos_entrenos(self):
        a = self.enviar(datos(token=TOKEN_A)).json()
        b = self.enviar(datos(token=TOKEN_B)).json()
        self.assertNotEqual(a['entreno_id'], b['entreno_id'])
        self.assertEqual(self.entrenos().count(), 2)

    def test_la_duracion_no_cambia_la_huella(self):
        self.enviar(datos())
        r = self.enviar(datos(duracion_minutos_real='71')).json()
        self.assertTrue(r['ya_guardado'])
        self.assertEqual(self.entrenos().count(), 1)

    def test_token_invalido_se_rechaza(self):
        r = self.enviar(datos(token='corto'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.entrenos().count(), 0)

    def test_sin_token_sigue_la_defensa_antigua(self):
        d = datos()
        d.pop('sesion_token')
        primero = self.enviar(d).json()
        segundo = self.enviar(d).json()
        self.assertTrue(segundo['ya_guardado'])
        self.assertEqual(segundo['entreno_id'], primero['entreno_id'])
        self.assertIsNone(self.entrenos().get().sesion_token)

    # -- correccion ----------------------------------------------------------

    def _enviar_y_corregir(self, nuevo):
        primero = self.enviar(datos()).json()
        corregido = datos(**nuevo)
        corregido['bases_huella'] = primero['huella']
        return primero, self.enviar(corregido).json()

    def test_contenido_distinto_con_base_conocida_corrige_la_misma_sesion(self):
        primero, r = self._enviar_y_corregir({'reps': ('10', '9'), 'peso': ('60', '65')})
        self.assertTrue(r['success'])
        self.assertTrue(r['corregida'])
        self.assertEqual(r['entreno_id'], primero['entreno_id'])
        self.assertEqual(r['revision'], 2)
        self.assertNotEqual(r['huella'], primero['huella'])
        self.assertEqual(self.entrenos().count(), 1)
        e = self.entrenos().get()
        self.assertEqual(e.huella_contenido, r['huella'])
        # series y volumen reflejan lo corregido, sin restos de la version anterior
        self.assertEqual(SerieRealizada.objects.filter(entreno=e).count(), 2)
        self.assertEqual(EjercicioRealizado.objects.filter(entreno=e).count(), 1)
        self.assertEqual(float(e.volumen_total_kg), 60 * 10 + 65 * 9)
        self.assertEqual(
            sorted(SerieRealizada.objects.filter(entreno=e).values_list('repeticiones', flat=True)),
            [9, 10],
        )

    def test_la_correccion_deja_traza_con_lo_anterior(self):
        primero, r = self._enviar_y_corregir({'reps': ('10', '9')})
        c = CorreccionSesionGym.objects.get()
        self.assertEqual(c.entreno_id, primero['entreno_id'])
        self.assertEqual(c.huella_anterior, primero['huella'])
        self.assertEqual(c.huella_nueva, r['huella'])
        self.assertEqual(c.revision_resultante, 2)
        self.assertEqual(c.origen, 'reintento')
        self.assertEqual(c.snapshot_anterior['volumen_total_kg'], 60 * 8 + 62.5 * 8)
        self.assertEqual(len(c.snapshot_anterior['series']), 2)

    def test_la_correccion_no_repite_puntos_ni_latch(self):
        primero = self.enviar(datos()).json()
        e = EntrenoRealizado.objects.get(pk=primero['entreno_id'])
        self.assertTrue(e.procesado_gamificacion)
        puntos = e.puntos_ganados
        d = datos(reps=('10', '9'))
        d['bases_huella'] = primero['huella']
        self.enviar(d)
        e.refresh_from_db()
        self.assertTrue(e.procesado_gamificacion)
        self.assertEqual(e.puntos_ganados, puntos)

    def test_records_se_rehacen_con_los_datos_corregidos(self):
        primero = self.enviar(datos(peso=('60', '62.5'))).json()
        e = EntrenoRealizado.objects.get(pk=primero['entreno_id'])
        antes = list(RecordPersonal.objects.filter(entreno=e, tipo_record='peso_maximo')
                     .values_list('valor', flat=True))
        d = datos(peso=('60', '70'))
        d['bases_huella'] = primero['huella']
        self.enviar(d)
        despues = list(RecordPersonal.objects.filter(entreno=e, tipo_record='peso_maximo')
                       .values_list('valor', flat=True))
        self.assertEqual([float(v) for v in antes], [62.5])
        self.assertEqual([float(v) for v in despues], [70.0])

    def test_decision_ya_usada_se_conserva_y_se_senala(self):
        primero = self.enviar(datos()).json()
        e = EntrenoRealizado.objects.get(pk=primero['entreno_id'])
        log = GymDecisionLog.objects.get(entreno_origen=e)
        posterior = EntrenoRealizado.objects.create(
            cliente=self.cliente, fecha=date.today() + timedelta(days=3),
            rutina=e.rutina, fuente_datos='manual',
        )
        GymDecisionLog.objects.filter(pk=log.pk).update(
            entreno_evaluador=posterior, resultado='validada')
        d = datos(reps=('12', '12'))
        d['bases_huella'] = primero['huella']
        self.enviar(d)
        log.refresh_from_db()
        self.assertEqual(log.entreno_origen_id, e.id)
        self.assertEqual(log.resultado, 'validada')
        self.assertEqual(log.entreno_evaluador_id, posterior.id)
        c = CorreccionSesionGym.objects.get()
        self.assertEqual(log.correccion_id, c.id)
        self.assertEqual([x['id'] for x in c.efectos['decisiones_conservadas']], [log.id])

    def test_decision_no_usada_se_regenera_con_los_datos_corregidos(self):
        primero = self.enviar(datos()).json()
        e = EntrenoRealizado.objects.get(pk=primero['entreno_id'])
        antes = GymDecisionLog.objects.get(entreno_origen=e)
        d = datos(reps=('15', '15'))
        d['bases_huella'] = primero['huella']
        self.enviar(d)
        despues = GymDecisionLog.objects.get(entreno_origen=e)
        self.assertEqual(GymDecisionLog.objects.filter(entreno_origen=e).count(), 1)
        self.assertEqual(despues.reps_anteriores, 15)
        self.assertNotEqual(despues.reps_anteriores, antes.reps_anteriores)
        self.assertIsNone(despues.correccion_id)

    def test_decision_que_esta_sesion_evaluo_se_reabre_y_se_reevalua(self):
        # Sesion previa con una decision pendiente sobre el mismo ejercicio.
        previo = self.enviar(datos(token=TOKEN_B)).json()
        EntrenoRealizado.objects.filter(pk=previo['entreno_id']).update(
            fecha=date.today() - timedelta(days=7))
        GymDecisionLog.objects.filter(entreno_origen_id=previo['entreno_id']).update(resultado=None)
        actual = self.enviar(datos(token=TOKEN_A)).json()
        evaluadas = GymDecisionLog.objects.filter(entreno_evaluador_id=actual['entreno_id'])
        evaluadas_ids = list(evaluadas.values_list('id', flat=True))
        self.assertTrue(evaluadas_ids, 'la sesion actual debia evaluar la decision previa')
        d = datos(token=TOKEN_A, reps=('9', '9'))
        d['bases_huella'] = actual['huella']
        self.enviar(d)
        c = CorreccionSesionGym.objects.get()
        self.assertEqual(sorted(c.efectos['decisiones_reabiertas']), sorted(evaluadas_ids))

    # -- conflicto -----------------------------------------------------------

    def test_sin_base_conocida_el_contenido_distinto_es_conflicto_y_no_escribe(self):
        primero = self.enviar(datos()).json()
        r = self.enviar(datos(reps=('10', '10')))
        self.assertEqual(r.status_code, 409)
        j = r.json()
        self.assertTrue(j['conflicto'])
        self.assertEqual(j['huella'], primero['huella'])
        e = self.entrenos().get()
        self.assertEqual(e.huella_contenido, primero['huella'])
        self.assertEqual(e.revision, 1)
        self.assertEqual(CorreccionSesionGym.objects.count(), 0)
        self.assertEqual(float(e.volumen_total_kg), 60 * 8 + 62.5 * 8)

    def test_dos_correcciones_concurrentes_la_segunda_no_pisa_a_la_primera(self):
        """Dos moviles parten de la misma huella H0; el primero gana, el segundo recibe conflicto."""
        h0 = self.enviar(datos()).json()['huella']
        a = datos(reps=('10', '10')); a['bases_huella'] = h0
        b = datos(reps=('7', '7')); b['bases_huella'] = h0
        ra = self.enviar(a)
        rb = self.enviar(b)
        self.assertEqual(ra.status_code, 200)
        self.assertEqual(rb.status_code, 409)
        e = self.entrenos().get()
        self.assertEqual(e.huella_contenido, ra.json()['huella'])
        self.assertEqual(e.revision, 2)
        self.assertEqual(float(e.volumen_total_kg), 60 * 10 + 62.5 * 10)

    def test_resolver_conflicto_aplica_la_mia_sabiendo_lo_que_hay(self):
        h0 = self.enviar(datos()).json()['huella']
        a = datos(reps=('10', '10')); a['bases_huella'] = h0
        ha = self.enviar(a).json()['huella']
        b = datos(reps=('7', '7')); b['bases_huella'] = h0
        self.assertEqual(self.enviar(b).status_code, 409)
        b['resolver_conflicto'] = ha
        rb = self.enviar(b)
        self.assertEqual(rb.status_code, 200)
        e = self.entrenos().get()
        self.assertEqual(e.revision, 3)
        self.assertEqual(e.huella_contenido, rb.json()['huella'])
        self.assertEqual(
            list(CorreccionSesionGym.objects.order_by('revision_resultante')
                 .values_list('origen', flat=True)),
            ['reintento', 'conflicto_resuelto'],
        )

    def test_resolver_conflicto_con_una_huella_vieja_no_vale(self):
        h0 = self.enviar(datos()).json()['huella']
        a = datos(reps=('10', '10')); a['bases_huella'] = h0
        self.enviar(a)
        b = datos(reps=('7', '7')); b['resolver_conflicto'] = h0
        self.assertEqual(self.enviar(b).status_code, 409)

    def test_un_error_en_la_correccion_deja_la_version_anterior_intacta(self):
        primero = self.enviar(datos()).json()
        d = datos(reps=('10', '10')); d['bases_huella'] = primero['huella']
        with patch('entrenos.services.decision_log_service.cerrar_aprendizaje_gym',
                   side_effect=RuntimeError('boom')):
            r = self.enviar(d)
        self.assertEqual(r.status_code, 400)
        e = self.entrenos().get()
        self.assertEqual(e.huella_contenido, primero['huella'])
        self.assertEqual(e.revision, 1)
        self.assertEqual(float(e.volumen_total_kg), 60 * 8 + 62.5 * 8)
        self.assertEqual(SerieRealizada.objects.filter(entreno=e).count(), 2)
        self.assertEqual(CorreccionSesionGym.objects.count(), 0)

    # -- comprobar si llego --------------------------------------------------

    def comprobar(self, token, client=None):
        url = reverse('entrenos:comprobar_sesion_guardada', args=[self.cliente.pk, token])
        return (client or self.client).get(url)

    def test_comprobar_devuelve_el_estado_de_esa_sesion(self):
        primero = self.enviar(datos(token=TOKEN_A)).json()
        self.enviar(datos(token=TOKEN_B, reps=('5', '5')))
        j = self.comprobar(TOKEN_A).json()
        self.assertTrue(j['existe'])
        self.assertEqual(j['huella'], primero['huella'])
        self.assertEqual(j['entreno_id'], primero['entreno_id'])
        self.assertEqual(j['revision'], 1)

    def test_comprobar_una_sesion_que_no_llego(self):
        j = self.comprobar('tokenCCCCCCCCCCCCCCCC3').json()
        self.assertEqual(j, {'success': True, 'existe': False})

    def test_comprobar_no_ve_sesiones_de_otro_cliente(self):
        self.enviar(datos())
        otro = User.objects.create_user('otro21', password='x')
        cli = self.client_class()
        cli.force_login(otro)
        self.assertEqual(self.comprobar(TOKEN_A, client=cli).status_code, 404)
