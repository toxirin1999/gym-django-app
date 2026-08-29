from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    ContratoBloqueGym,
    ContratoSemanalGym,
    EstrategiaSemanalGym,
    EvaluacionSemanalGym,
    SesionProgramada,
)
from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan


PLAN_HELMS = {
    'plan_por_bloques': [
        {'nombre': 'Fuerza', 'objetivo': 'Elevar fuerza máxima', 'duracion': 52},
    ],
    'metadata': {'año_planificacion': 2026},
}


class TrayectoriaPlanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('trayectoria', password='x')
        self.otro_user = User.objects.create_user('trayectoria_otro', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.inicio = date(2026, 8, 24)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5,
            minimo_valido=3, vigente_desde=self.inicio, aprobado_por=self.user,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=1, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            semana_inicio=self.inicio, semanas_previstas=4,
            semana_fin_prevista=self.inicio + timedelta(days=27),
            estrategia=self.estrategia, objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='Convertir fuerza en progreso',
            objetivos_secundarios=['Gemelos'], limites_snapshot={},
            motor_nombre='Helms', motor_version='actual', fingerprint='trayectoria-fp',
        )
        self.contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia, bloque=self.bloque,
            indice_semana_bloque=1, semana=self.inicio,
            objetivo_sesiones=5, minimo_valido=3,
        )

    def _proyectar(self, fecha=date(2026, 8, 26)):
        with patch(
            'entrenos.services.trayectoria_plan_service._generar_plan_helms',
            return_value=PLAN_HELMS,
        ):
            return proyectar_trayectoria_plan(self.cliente, fecha=fecha)

    def test_compone_dos_carriles_y_fechas_reales_sin_inventar_evaluaciones(self):
        normal = SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=self.contrato,
            fecha_prevista=date(2026, 8, 24), estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Día 1',
        )
        pospuesta = SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=self.contrato,
            fecha_prevista=date(2026, 8, 25), pospuesta_hasta=date(2026, 8, 27),
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='Día 2',
        )
        realizada = SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=self.contrato,
            fecha_prevista=date(2026, 8, 26), fecha_realizada=date(2026, 8, 26),
            estado=SesionProgramada.ESTADO_COMPLETADA, nombre_sesion='Día 3',
        )
        resultado = self._proyectar()
        self.assertEqual(resultado['periodizacion']['carril'], 'Fase de periodización')
        self.assertEqual(resultado['periodizacion']['nombre'], 'Fuerza')
        self.assertEqual(resultado['bloque']['carril'], 'Objetivo del bloque')
        self.assertEqual(resultado['bloque']['objetivo'], 'Convertir fuerza en progreso')
        sesiones = {item['id']: item for item in resultado['semana']['sesiones']}
        self.assertEqual(sesiones[normal.id]['fecha_efectiva'], date(2026, 8, 24))
        self.assertEqual(sesiones[pospuesta.id]['fecha_efectiva'], date(2026, 8, 27))
        self.assertEqual(sesiones[realizada.id]['fecha_realizada'], date(2026, 8, 26))
        self.assertTrue(sesiones[realizada.id]['realizada'])
        self.assertIsNone(resultado['semana']['evaluacion'])
        self.assertEqual(resultado['proximo_hito']['sesion_id'], pospuesta.id)

    def test_solo_expone_evaluacion_persistida(self):
        evaluacion = EvaluacionSemanalGym.objects.create(
            contrato=self.contrato, estado_cumplimiento='minima_valida',
            sesiones_completadas=3, estado_revision=EvaluacionSemanalGym.ESTADO_PENDIENTE,
        )
        resultado = self._proyectar()
        self.assertEqual(resultado['semana']['evaluacion']['id'], evaluacion.id)
        self.assertEqual(resultado['semana']['evaluacion']['estado_revision'], 'pendiente')

    def test_proyeccion_es_read_only_y_declara_unknown_sin_rellenar_ceros(self):
        conteos = (
            ContratoBloqueGym.objects.count(), ContratoSemanalGym.objects.count(),
            SesionProgramada.objects.count(), EvaluacionSemanalGym.objects.count(),
        )
        resultado = proyectar_trayectoria_plan(self.otro, fecha=date(2026, 8, 26))
        self.assertEqual(resultado['estado'], 'unknown')
        self.assertTrue(resultado['limitations'])
        self.assertNotIn('sesiones_completadas', resultado)
        self.assertEqual(conteos, (
            ContratoBloqueGym.objects.count(), ContratoSemanalGym.objects.count(),
            SesionProgramada.objects.count(), EvaluacionSemanalGym.objects.count(),
        ))

    def test_fuente_helms_es_el_mismo_generador_del_calendario(self):
        with patch('entrenos.services.trayectoria_plan_service.crear_perfil_desde_cliente') as perfil, \
             patch('entrenos.services.trayectoria_plan_service.PlanificadorHelms') as planificador:
            perfil.return_value = type('Perfil', (), {'maximos_actuales': {}, 'año_planificacion': None})()
            planificador.return_value.generar_plan_anual.return_value = PLAN_HELMS
            proyectar_trayectoria_plan(self.cliente, fecha=date(2026, 8, 26))
        planificador.return_value.generar_plan_anual.assert_called_once_with()
        codigo = Path('entrenos/services/trayectoria_plan_service.py').read_text()
        self.assertNotIn('FaseCliente', codigo)
        self.assertNotIn('HistorialFase', codigo)


class TrayectoriaPlanViewTests(TrayectoriaPlanTests):
    def test_requiere_login_get_y_aisla_cliente(self):
        url = reverse('clientes:trayectoria_plan')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        with patch(
            'entrenos.services.trayectoria_plan_service._generar_plan_helms',
            return_value=PLAN_HELMS,
        ):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['trayectoria']['bloque']['id'], self.bloque.id)
        self.assertEqual(response.context['cliente'].id, self.cliente.id)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_template_es_movil_accesible_sin_tablas_ni_dependencias_externas(self):
        self.client.force_login(self.user)
        with patch(
            'entrenos.services.trayectoria_plan_service._generar_plan_helms',
            return_value=PLAN_HELMS,
        ):
            response = self.client.get(reverse('clientes:trayectoria_plan'))
        html = response.content.decode()
        self.assertIn('Línea temporal del plan', html)
        self.assertIn('aria-label=', html)
        self.assertIn('min-height: 44px', html)
        self.assertNotIn('<table', html)
        self.assertNotIn('https://', html)
        self.assertNotIn('http://', html)

    def test_dashboard_enlaza_una_sola_vez_a_trayectoria(self):
        plantilla = Path('clientes/templates/clientes/mockup_demo.html').read_text()
        self.assertEqual(plantilla.count("{% url 'clientes:trayectoria_plan' %}"), 1)
