"""20-nov-2026: tests de servicio de motivo_decision_service y ajustes_detalle_service (sin vistas)."""
from datetime import date, datetime, timezone as tz
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import GymDecisionVersion, PropuestaZonaGym
from entrenos.services.ajustes_detalle_service import detalle_ajustes
from entrenos.services.motivo_decision_service import motivo_de_version

DIA = date(2026, 11, 20)
VOL = 'entrenos.services.volumen_grupo_service.'
PAUSA = 'entrenos.services.propuesta_zona_service.pausa_subir_volumen'


def _version(cliente, valores, n=1):
    return GymDecisionVersion.objects.create(
        cliente=cliente, fecha=DIA, version=n, decision_id=f'd{n}', origen='motor', vigente=True,
        fingerprint='f' * 64, base_fingerprint='b' * 64, postura='sostener', causa_principal='futbol_reciente',
        snapshot={'estado': 'version_reducida', 'causa_principal': 'futbol_reciente', 'causas_secundarias': [],
                  'mensaje': 'm', 'physical_snapshot': {'signals': {'checkin': {
                      'status': 'available', 'observed_on': '2026-11-20', 'age_days': 0, 'values': valores,
                      'provenance': {'record_id': 143}}}}})


class MotivoDecisionServicioTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.get(user=User.objects.create_user('svc_motivo', password='x'))

    def test_dice_que_faltaba_y_no_usa_la_bitacora_actual(self):
        v = _version(self.cliente, {'resting_hr': 52, 'hrv_ms': None, 'sleep_hours': None, 'energy': None})
        BitacoraDiaria.objects.create(cliente=self.cliente, fecha=DIA, hrv_ms=130, horas_sueno=7.99)
        m = motivo_de_version(v)
        html = str(m)
        self.assertIn('No constaba al decidir', html)
        self.assertNotIn('130', html)
        self.assertNotIn('7,99', html)

    def test_con_datos_los_muestra(self):
        v = _version(self.cliente, {'resting_hr': 52, 'hrv_ms': 61, 'sleep_hours': 7.5, 'energy': 4})
        html = str(motivo_de_version(v))
        self.assertIn('52', html)
        self.assertIn('61', html)


class AjustesDetalleServicioTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.get(user=User.objects.create_user('svc_ajustes', password='x'))

    def test_sin_ajustes_no_hay_tarjetas(self):
        with patch(VOL + 'ajustes_volumen', return_value={}), patch(VOL + 'revisiones_pendientes', return_value=[]), \
                patch(PAUSA, return_value=None):
            self.assertEqual(detalle_ajustes(self.cliente, DIA), [])

    def test_la_pausa_genera_su_tarjeta(self):
        pausa = {'zonas': ('triceps', 'trapecios'), 'fin_previsto': date(2026, 12, 6), 'bloque': 'Fuerza — Hipertrofia'}
        with patch(VOL + 'ajustes_volumen', return_value={}), patch(VOL + 'revisiones_pendientes', return_value=[]), \
                patch(PAUSA, return_value=pausa):
            (t,) = detalle_ajustes(self.cliente, DIA)
        self.assertEqual(t['tipo'], 'pausa')
        self.assertIn('Tríceps y trapecio', t['titulo'])

    def test_ajuste_sin_propuesta_cita_el_motivo_del_planificador(self):
        with patch(VOL + 'ajustes_volumen', return_value={'pecho': {'series': 2, 'motivos': ['+2 series de pecho por el énfasis del bloque']}}), \
                patch(VOL + 'revisiones_pendientes', return_value=[]), patch(PAUSA, return_value=None):
            (t,) = detalle_ajustes(self.cliente, DIA)
        self.assertIn('énfasis del bloque', t['motivo'])
        self.assertEqual(t['historial'], [])
