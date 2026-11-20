"""20-nov-2026: «Ver motivo» explica la version concreta con lo que esa version guardo."""
from datetime import date, datetime, timezone as dt_tz
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import GymDecisionVersion
from entrenos.services.motivo_decision_service import motivo_de_version

DIA = date(2026, 11, 20)


def _snapshot(values, status='available', record_id=143, extra=None):
    snap = {
        'estado': 'version_reducida', 'causa_principal': 'futbol_reciente', 'causas_secundarias': [],
        'mensaje': 'Entrenar con carga ajustada.',
        'physical_snapshot': {'signals': {'checkin': {
            'status': status, 'observed_on': '2026-11-20', 'age_days': 0, 'values': values,
            'provenance': {'source': 'clientes.BitacoraDiaria', 'record_id': record_id}}}},
        'cambios_materializados': [{'tipo': 'x', 'razon': 'Pierna con una serie menos.', 'ejercicio_original': 'Sentadilla'}],
    }
    snap.update(extra or {})
    return snap


class VerMotivoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('motivo', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    def _version(self, n, snapshot, vigente=True, hora=None):
        v = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=DIA, version=n, decision_id=f'd{n}', origen='motor',
            vigente=vigente, fingerprint='f' * 64, base_fingerprint='b' * 64, postura='sostener',
            causa_principal='futbol_reciente', snapshot=snapshot)
        if hora:
            GymDecisionVersion.objects.filter(pk=v.pk).update(creado_en=hora)
        return GymDecisionVersion.objects.get(pk=v.pk)

    def test_version_que_solo_leyo_el_pulso_dice_que_faltaban_variabilidad_sueno_y_energia(self):
        v = self._version(1, _snapshot({'resting_hr': 52, 'hrv_ms': None, 'sleep_hours': None, 'energy': None}))
        m = motivo_de_version(v)
        self.assertEqual(len(m['avisos']), 1)
        self.assertIn('no constaba', m['avisos'][0])
        for nombre in ('variabilidad cardiaca', 'sueño', 'energía'):
            self.assertIn(nombre, m['avisos'][0])
        self.assertNotIn('pulso', m['avisos'][0])
        faltan = [f['nombre'] for f in m['datos']['filas'] if f['valor'] is None]
        self.assertEqual(faltan, ['Variabilidad cardiaca', 'Sueño', 'Energía'])

    def test_no_usa_valores_recibidos_despues_aunque_la_bitacora_actual_los_tenga(self):
        v = self._version(1, _snapshot({'resting_hr': 52, 'hrv_ms': None, 'sleep_hours': None, 'energy': None}))
        b = BitacoraDiaria.objects.create(
            cliente=self.cliente, hrv_ms=130, horas_sueno=Decimal('7.99'), fc_reposo=52)
        BitacoraDiaria.objects.filter(pk=b.pk).update(fecha=DIA)
        with CaptureQueriesContext(connection) as q:
            resp = self.client.get(reverse('clientes:ver_motivo'), {'fecha': '2026-11-20'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn('130', html)
        self.assertNotIn('7,99', html)
        self.assertIn('No constaba al decidir', html)
        self.assertIn('Esta explicación no los usa', html)
        self.assertFalse([x for x in q.captured_queries if 'bitacoradiaria' in x['sql'].lower()])
        self.assertEqual(motivo_de_version(v)['datos']['origen']['fila'], 143)

    def test_version_con_datos_los_enseña_con_su_origen(self):
        v = self._version(2, _snapshot({'resting_hr': 52, 'hrv_ms': 130, 'sleep_hours': 7.99, 'energy': 7}, record_id=142))
        m = motivo_de_version(v)
        self.assertEqual(m['avisos'], [])
        textos = {f['nombre']: f['texto'] for f in m['datos']['filas']}
        self.assertEqual(textos['Variabilidad cardiaca'], '130 ms')
        self.assertEqual(textos['Sueño'], '7,99 h')
        self.assertEqual(m['datos']['origen']['fila'], 142)

    def test_version_sin_snapshot_fisico_no_inventa_datos(self):
        v = self._version(1, {'estado': 'entrenar', 'causa_principal': ''})
        m = motivo_de_version(v)
        self.assertIsNone(m['datos'])
        self.assertIn('no guardó los datos físicos', m['avisos'][0])

    def test_hora_de_la_version_en_madrid(self):
        v = self._version(1, _snapshot({'resting_hr': 52, 'hrv_ms': None, 'sleep_hours': None, 'energy': None}),
                          hora=datetime(2026, 11, 20, 7, 8, 57, tzinfo=dt_tz.utc))
        self.assertEqual(motivo_de_version(v)['creada_texto'], '20/11 08:08:57')

    def test_causas_y_cambios_salen_de_la_version(self):
        v = self._version(1, _snapshot({'resting_hr': 52, 'hrv_ms': 50, 'sleep_hours': 7, 'energy': 6},
                                       extra={'causas_secundarias': ['readiness_bajo']}))
        m = motivo_de_version(v)
        self.assertEqual([c['codigo'] for c in m['causas']], ['futbol_reciente', 'readiness_bajo'])
        self.assertTrue(m['causas'][0]['principal'])
        self.assertEqual(m['cambios'][0]['ejercicio'], 'Sentadilla')

    def test_no_contiene_frases_de_reglas_pendientes(self):
        self._version(1, _snapshot({'resting_hr': 52, 'hrv_ms': 50, 'sleep_hours': 7, 'energy': 6}))
        html = self.client.get(reverse('clientes:ver_motivo'), {'fecha': '2026-11-20'}).content.decode()
        for frase in ('por debajo de la media', 'caso mixto', '1,13', '+5 %', 'mediana'):
            self.assertNotIn(frase, html)

    def test_varias_versiones_y_eleccion_de_version(self):
        self._version(1, _snapshot({'resting_hr': 52, 'hrv_ms': None, 'sleep_hours': None, 'energy': None}), vigente=False)
        self._version(2, _snapshot({'resting_hr': 52, 'hrv_ms': None, 'sleep_hours': None, 'energy': None}))
        html = self.client.get(reverse('clientes:ver_motivo'), {'fecha': '2026-11-20', 'version': '1'}).content.decode()
        self.assertIn('Versión 1', html)
        self.assertIn('Otras versiones', html)

    def test_sin_version_no_falla(self):
        resp = self.client.get(reverse('clientes:ver_motivo'), {'fecha': '2026-11-20'})
        self.assertContains(resp, 'Sin decisión registrada')


class VerMotivoAhoraYPropiedadTests(TestCase):
    """Ahora enlaza a la version que representa; las versiones ajenas no se alcanzan."""

    def setUp(self):
        self.user = User.objects.create_user('motivo_a', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=User.objects.create_user('motivo_b', password='x'))
        self.client.force_login(self.user)

    def _v(self, cliente, n, vigente, estado='version_reducida'):
        return GymDecisionVersion.objects.create(
            cliente=cliente, fecha=DIA, version=n, decision_id=f'{cliente.pk}-{n}', origen='motor',
            vigente=vigente, fingerprint='f' * 64, base_fingerprint='b' * 64, postura='sostener',
            causa_principal='futbol_reciente',
            snapshot=_snapshot({'resting_hr': 52 + n, 'hrv_ms': None, 'sleep_hours': None, 'energy': None},
                               extra={'estado': estado}),
        )

    def test_el_enlace_de_ahora_fija_la_version_que_la_pantalla_representa(self):
        from clientes.views import _url_ver_motivo
        url = _url_ver_motivo({'version_persistida': 1}, DIA)
        self.assertEqual(url, reverse('clientes:ver_motivo') + '?fecha=2026-11-20&version=1')
        # sin version persistida: sin parametros (cae en la vigente)
        self.assertEqual(_url_ver_motivo({}, DIA), reverse('clientes:ver_motivo'))
        self.assertEqual(_url_ver_motivo({'version_persistida': True}, DIA), reverse('clientes:ver_motivo'))

    def test_la_url_fijada_abre_esa_version_aunque_haya_otra_vigente(self):
        self._v(self.cliente, 1, vigente=False)
        self._v(self.cliente, 2, vigente=True)
        resp = self.client.get(reverse('clientes:ver_motivo'), {'fecha': '2026-11-20', 'version': '1'})
        self.assertEqual(resp.context['motivo']['version'], 1)
        self.assertFalse(resp.context['motivo']['vigente'])

    def test_una_version_de_otro_usuario_no_se_alcanza(self):
        self._v(self.cliente, 1, vigente=True)
        self._v(self.otro, 7, vigente=True)
        resp = self.client.get(reverse('clientes:ver_motivo'), {'fecha': '2026-11-20', 'version': '7'})
        self.assertIsNone(resp.context['motivo'])
        self.assertContains(resp, 'Sin decisión registrada')
        resp = self.client.get(reverse('clientes:ver_motivo'), {'fecha': '2026-11-20'})
        self.assertEqual(resp.context['motivo']['version'], 1)
        self.assertEqual([o['version'] for o in resp.context['otras_versiones']], [])

    def test_la_pagina_ahora_renderiza_el_enlace_con_la_version_de_su_decision(self):
        from unittest.mock import patch
        from clientes import views as vistas
        original = vistas._get_dashboard_context_data

        def con_version(*a, **k):
            ctx = original(*a, **k)
            ctx['_decision_gym_raw'] = dict(ctx.get('_decision_gym_raw') or {}, version_persistida=3)
            return ctx

        with patch.object(vistas, '_get_dashboard_context_data', side_effect=con_version):
            resp = self.client.get(reverse('clientes:dashboard_silencioso_preview'))
        self.assertEqual(resp.status_code, 200)
        esperado = reverse('clientes:ver_motivo') + '?fecha=' + resp.context['quiet_decision']['motivo_url'].split('fecha=')[1]
        self.assertEqual(resp.context['quiet_decision']['motivo_url'], esperado)
        self.assertIn('version=3', resp.context['quiet_decision']['motivo_url'])
        self.assertContains(resp, 'href="%s">Ver motivo' % resp.context['quiet_decision']['motivo_url'].replace('&', '&amp;'))
