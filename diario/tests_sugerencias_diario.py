"""
Phase Diario-Gym 3.5 — Tests para sugerencia corporal autorizable.

El diario no interviene el entrenamiento; pide permiso para que el plan vigile una señal.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from unittest.mock import patch

from clientes.utils import get_cliente_actual
from diario.services.sugerencias_diario import get_sugerencia_diario
from entrenos.models import IntervencionPlan, SugerenciaPlan


def _cliente(username='test_sug_diario'):
    user = User.objects.create_user(username, password='x')
    return get_cliente_actual(user)


def _tendencia_notable():
    return {'hay_tendencia': True, 'nivel': 'notable', 'n_alineados': 4, 'n_semanas': 4, 'texto': 'Tendencia notable.'}


def _tendencia_suave():
    return {'hay_tendencia': True, 'nivel': 'suave', 'n_alineados': 2, 'n_semanas': 4, 'texto': 'Tendencia suave.'}


def _sin_tendencia():
    return {'hay_tendencia': False}


# ── Servicio generar_sugerencia_diario ──────────────────────────────────────

class GenerarSugerenciaDiarioTest(TestCase):

    def setUp(self):
        self.cliente = _cliente()

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_sin_tendencia())
    def test_sin_tendencia_no_crea_sugerencia(self, _mock):
        resultado = get_sugerencia_diario(self.cliente)
        self.assertIsNone(resultado)

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_tendencia_suave())
    def test_tendencia_suave_no_crea_sugerencia(self, _mock):
        resultado = get_sugerencia_diario(self.cliente)
        self.assertIsNone(resultado)

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_tendencia_notable())
    def test_tendencia_notable_crea_sugerencia(self, _mock):
        resultado = get_sugerencia_diario(self.cliente)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.patron, 'diario_tendencia_corporal')
        self.assertEqual(resultado.estado, SugerenciaPlan.ESTADO_PENDIENTE)

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_tendencia_notable())
    def test_no_duplica_sugerencia_pendiente(self, _mock):
        get_sugerencia_diario(self.cliente)
        get_sugerencia_diario(self.cliente)
        n = SugerenciaPlan.objects.filter(cliente=self.cliente, patron='diario_tendencia_corporal').count()
        self.assertEqual(n, 1)

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_tendencia_notable())
    def test_cooldown_activo_no_muestra(self, _mock):
        sg = SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='...',
            estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=date.today() + timedelta(days=3),
        )
        resultado = get_sugerencia_diario(self.cliente)
        self.assertIsNone(resultado)

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_tendencia_notable())
    def test_no_crea_si_intervencion_vigilar_senal_activa(self, _mock):
        from rutinas.models import Rutina
        from entrenos.models import EntrenoRealizado
        rutina, _ = Rutina.objects.get_or_create(nombre='Test Rutina Sug')
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=10),
        )
        resultado = get_sugerencia_diario(self.cliente)
        self.assertIsNone(resultado)

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_tendencia_notable())
    def test_descartada_no_reaparece(self, _mock):
        SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='...',
            estado=SugerenciaPlan.ESTADO_DESCARTADA,
        )
        resultado = get_sugerencia_diario(self.cliente)
        self.assertIsNone(resultado)

    @patch('diario.services.sugerencias_diario._calcular_tendencia', return_value=_tendencia_notable())
    def test_aceptada_no_reaparece(self, _mock):
        SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='...',
            estado=SugerenciaPlan.ESTADO_ACEPTADA,
        )
        resultado = get_sugerencia_diario(self.cliente)
        self.assertIsNone(resultado)


# ── Aceptar: crea IntervencionPlan vigilar_senal ──────────────────────────────

class AceptarSugerenciaDiarioTest(TestCase):

    def setUp(self):
        self.cliente = _cliente('test_acepta_sug')

    def test_aceptar_crea_intervencion_vigilar_senal(self):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        sg = SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='...',
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
        aceptar_sugerencia(sg)
        ip = IntervencionPlan.objects.filter(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
        ).first()
        self.assertIsNotNone(ip)
        self.assertEqual(ip.estado, IntervencionPlan.ESTADO_ACTIVA)

    def test_aceptar_dura_14_dias(self):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        sg = SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='...',
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
        hoy = date.today()
        aceptar_sugerencia(sg, fecha_ref=hoy)
        ip = IntervencionPlan.objects.get(cliente=self.cliente, tipo=IntervencionPlan.TIPO_VIGILAR_SENAL)
        self.assertEqual(ip.fecha_fin, hoy + timedelta(days=14))

    def test_aceptar_no_cambia_cargas(self):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        sg = SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='...',
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
        aceptar_sugerencia(sg)
        ip = IntervencionPlan.objects.get(cliente=self.cliente, tipo=IntervencionPlan.TIPO_VIGILAR_SENAL)
        self.assertNotEqual(ip.tipo, IntervencionPlan.TIPO_NO_SUBIR)
        self.assertNotEqual(ip.tipo, IntervencionPlan.TIPO_REDUCIR)


# ── Ignorar: aplica cooldown 7 días ──────────────────────────────────────────

class IgnorarSugerenciaDiarioTest(TestCase):

    def setUp(self):
        self.cliente = _cliente('test_ignora_sug')

    def test_ignorar_aplica_cooldown(self):
        from entrenos.services.sugerencias_service import ignorar_sugerencia
        sg = SugerenciaPlan.objects.create(
            cliente=self.cliente,
            patron='diario_tendencia_corporal',
            texto='...',
            estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
        ignorar_sugerencia(sg)
        sg.refresh_from_db()
        self.assertEqual(sg.estado, SugerenciaPlan.ESTADO_IGNORADA)
        self.assertEqual(sg.cooldown_hasta, date.today() + timedelta(days=7))


# ── Motor: vigilar_senal añade aviso contextual ──────────────────────────────

class MotorVigilarSenalTest(TestCase):

    def setUp(self):
        self.cliente = _cliente('test_motor_vigilar')

    def test_vigilar_senal_activa_añade_aviso(self):
        from entrenos.services.sesion_recomendada import _aplicar_efecto_distribucion
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=10),
        )
        decision = {'causa_principal': 'sesion_hoy', 'distribucion_aviso': None}
        resultado = _aplicar_efecto_distribucion(self.cliente, decision, date.today())
        self.assertIsNotNone(resultado.get('distribucion_aviso'))
        self.assertEqual(resultado['distribucion_aviso']['tipo'], 'vigilar_senal')

    def test_vigilar_senal_no_actua_con_lesion(self):
        from entrenos.services.sesion_recomendada import _aplicar_efecto_distribucion
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=10),
        )
        decision = {'causa_principal': 'lesion', 'distribucion_aviso': None}
        resultado = _aplicar_efecto_distribucion(self.cliente, decision, date.today())
        self.assertIsNone(resultado.get('distribucion_aviso'))

    def test_vigilar_senal_texto_no_cambia_sesion(self):
        from entrenos.services.sesion_recomendada import _aplicar_efecto_distribucion
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=10),
        )
        decision = {'causa_principal': 'sesion_hoy', 'distribucion_aviso': None}
        resultado = _aplicar_efecto_distribucion(self.cliente, decision, date.today())
        texto = resultado['distribucion_aviso']['texto'].lower()
        self.assertIn('no cambia la sesión', texto)
