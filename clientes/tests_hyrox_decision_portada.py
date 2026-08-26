from datetime import date, timedelta
from contextlib import nullcontext
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym
from hyrox.models import ContratoCampanaHyrox, HyroxObjective, HyroxSession


class HyroxDecisionPortadaAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('portada_hyrox', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=date.today() + timedelta(days=90),
            estado='activo',
        )
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente,
            version=1,
            objetivo_sesiones=4,
            minimo_valido=2,
            vigente_desde=date.today(),
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente,
            version=1,
            estado='activo',
            semana_inicio=date.today(),
            semanas_previstas=4,
            semana_fin_prevista=date.today() + timedelta(days=27),
            estrategia=estrategia,
            objetivo_sesiones=4,
            minimo_valido=2,
            objetivo_principal='hipertrofia',
            objetivos_secundarios=[],
            limites_snapshot={},
            motor_nombre='Helms',
            motor_version='actual',
            fingerprint='b' * 64,
        )
        self.contrato = ContratoCampanaHyrox.objects.create(
            cliente=self.cliente,
            version=1,
            estado='activa',
            objetivo=self.objetivo,
            bloque_gym=self.bloque,
            objetivo_snapshot={
                'id': self.objetivo.pk,
                'fecha_evento': str(self.objetivo.fecha_evento),
            },
            bloque_gym_snapshot={'id': self.bloque.pk, 'estado': 'activo'},
            limites_snapshot={},
            fingerprint='h' * 64,
        )
        self.client.force_login(self.user)

    def _get(self, decision=None, error=None, estado_sistema=None):
        kwargs = {'side_effect': error} if error else {'return_value': decision}
        estado_patch = (
            patch(
                'core.organismo.resolver_estado_sistema_hoy',
                return_value=estado_sistema,
            )
            if estado_sistema else nullcontext()
        )
        with (
            patch('hyrox.decision_service.calcular_hyrox_decision', **kwargs) as autoridad,
            estado_patch,
        ):
            response = self.client.get(reverse('clientes:mockup_demo'))
        return response, autoridad

    def test_portada_inyecta_decision_pero_sin_sesion_no_inventa_ejecucion(self):
        decision = {
            'estado': 'empujar', 'causa': 'normal', 'titulo': 'Empujar',
            'subtitulo': 'Señales favorables', 'mensaje': 'Ejecuta con intención.',
            'accion_label': 'Ejecutar plan', 'puede_ejecutar_plan': True,
            'permitido': ['Sesión planificada'], 'evitar': [],
        }

        response, autoridad = self._get(decision=decision)

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context['hyrox_decision'], decision)
        autoridad.assert_called_once()
        self.assertContains(response, 'Sin sesión programada')
        self.assertContains(response, 'Sin datos suficientes')
        self.assertNotContains(response, 'Ejecutar Hyrox')

    def test_bloqueo_soberano_muestra_proteccion_y_no_cta_de_ejecucion(self):
        decision = {
            'estado': 'recuperar', 'causa': 'fatiga', 'titulo': 'Recuperar',
            'subtitulo': 'Fatiga acumulada alta',
            'mensaje': 'La carga reciente pesa demasiado.',
            'accion_label': 'Recuperación activa', 'puede_ejecutar_plan': False,
            'permitido': ['Zona 2 suave', 'Movilidad'],
            'evitar': ['Series duras', 'Trabajo al fallo'],
        }

        response, _ = self._get(decision=decision)
        html = response.content.decode()
        inicio = html.index('id="rbHyroxContent"')
        fin = html.index('<!-- ── DIARIO', inicio)
        card_hyrox = html[inicio:fin]

        self.assertIn('Fatiga acumulada alta', card_hyrox)
        self.assertIn('Series duras', card_hyrox)
        self.assertIn('recuperación', card_hyrox.lower())
        self.assertNotIn('Ejecutar Hyrox', card_hyrox)
        self.assertNotIn('fas fa-bolt', card_hyrox)

    def test_fallo_de_autoridad_degrada_a_protegido_sin_optimo_ni_ejecucion(self):
        response, _ = self._get(error=RuntimeError('motor no disponible'))

        self.assertEqual(response.status_code, 200)
        decision = response.context['hyrox_decision']
        self.assertFalse(decision['puede_ejecutar_plan'])
        self.assertEqual(decision['causa'], 'autoridad_no_disponible')
        html = response.content.decode()
        inicio = html.index('id="rbHyroxContent"')
        fin = html.index('<!-- ── DIARIO', inicio)
        card_hyrox = html[inicio:fin]
        self.assertIn('Decisión no disponible', card_hyrox)
        self.assertNotIn('Óptimo', card_hyrox)
        self.assertNotIn('Ejecutar Hyrox', card_hyrox)

    def test_objetivo_legacy_y_sesion_futura_sin_contrato_no_hacen_hyrox_relevante(self):
        ContratoCampanaHyrox.objects.all().delete()
        HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=date.today() + timedelta(days=1),
            titulo='Legacy no autorizado',
            estado='planificado',
        )
        decision = {
            'estado': 'empujar', 'causa': 'normal', 'titulo': 'Empujar',
            'subtitulo': 'Hyrox dominaría', 'mensaje': 'Ejecutar.',
            'accion_label': 'Ejecutar plan', 'puede_ejecutar_plan': True,
            'permitido': ['Sesión planificada'], 'evitar': [],
        }

        response, autoridad = self._get(
            decision=decision,
            estado_sistema={
                'estado': 'PROTEGIENDO',
                'estado_label': 'Protegiendo',
                'texto': 'Hoy protegemos la rodilla.',
                'accion_label': 'Registrar recuperación',
                'accion_url': '/hyrox/',
                'modulo_principal': 'gym',
                'modulo_operativo': False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['hyrox_objetivo'])
        self.assertIsNone(response.context['hyrox_proxima_sesion'])
        autoridad.assert_not_called()
        sesiones_portada = (
            response.context['portada_hoy']['sesion_dominante'],
            response.context['portada_hoy']['sesion_alternativa'],
        )
        self.assertFalse(any(
            sesion and sesion['modulo'] == 'hyrox' for sesion in sesiones_portada
        ))
        self.assertEqual(response.context['portada_hoy']['accion_principal']['prioridad'], 'P0')
        self.assertIn('rodilla', response.context['portada_hoy']['decision']['frase'])

    def test_campana_activa_usa_exactamente_su_objetivo_contractual(self):
        objetivo_legacy = HyroxObjective.objects.create(
            cliente=self.cliente,
            fecha_evento=date.today() + timedelta(days=30),
            estado='activo',
        )
        HyroxSession.objects.create(
            objective=objetivo_legacy,
            fecha=date.today() + timedelta(days=1),
            titulo='Legacy primero',
            estado='planificado',
        )
        sesion_contractual = HyroxSession.objects.create(
            objective=self.objetivo,
            fecha=date.today() + timedelta(days=2),
            titulo='Sesión contractual',
            estado='planificado',
        )
        decision = {
            'estado': 'empujar', 'causa': 'normal', 'titulo': 'Empujar',
            'subtitulo': 'Señales favorables', 'mensaje': 'Ejecuta.',
            'accion_label': 'Ejecutar plan', 'puede_ejecutar_plan': True,
            'permitido': ['Sesión planificada'], 'evitar': [],
        }

        response, autoridad = self._get(decision=decision)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['hyrox_objetivo'].pk, self.contrato.objetivo_id)
        self.assertEqual(response.context['hyrox_proxima_sesion'].pk, sesion_contractual.pk)
        autoridad.assert_called_once()
