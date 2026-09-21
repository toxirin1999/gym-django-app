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
from django.template.loader import render_to_string

from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan


PLAN_HELMS = {
    'plan_por_bloques': [
        {'nombre': 'Fuerza', 'objetivo': 'Elevar fuerza máxima', 'duracion': 52},
    ],
    'metadata': {'año_planificacion': 2026},
}

PLAN_HELMS_MULTIFASE = {
    'plan_por_bloques': [
        {'nombre': 'Fase A', 'objetivo': 'acondicionamiento', 'duracion': 8},
        {'nombre': 'Fase B', 'objetivo': 'hipertrofia', 'duracion': 8},
        {'nombre': 'Fase C', 'objetivo': 'fuerza', 'duracion': 8},
    ],
    'metadata': {
        'año_planificacion': 2026,
        'periodizacion_completa': [
            {'nombre': 'Fase A', 'rep_range': '10-12', 'rpe_inicio': 6, 'rpe_fin': 7, 'descanso': 90},
            {'nombre': 'Fase B', 'rep_range': '8-10', 'rpe_inicio': 7, 'rpe_fin': 9, 'descanso': 75},
            {'nombre': 'Fase C', 'rep_range': '4-6', 'rpe_inicio': 7, 'rpe_fin': 9, 'descanso': 240},
        ],
    },
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

    def test_balance_informativo_no_crea_hito_de_revision(self):
        EvaluacionSemanalGym.objects.create(
            contrato=self.contrato, estado_cumplimiento='minima_valida',
            sesiones_completadas=3,
            estado_revision=EvaluacionSemanalGym.ESTADO_INFORMATIVA,
        )

        resultado = self._proyectar(fecha=date(2026, 8, 29))

        self.assertNotEqual(
            (resultado.get('proximo_hito') or {}).get('tipo'),
            'revision_semanal',
        )

    def test_semana_completa_sin_semana_siguiente_materializada_anuncia_su_apertura(self):
        for dia in range(5):
            fecha_sesion = self.inicio + timedelta(days=dia)
            SesionProgramada.objects.create(
                cliente=self.cliente,
                contrato_semanal=self.contrato,
                fecha_prevista=fecha_sesion,
                fecha_realizada=fecha_sesion,
                estado=SesionProgramada.ESTADO_COMPLETADA,
                nombre_sesion=f'Día {dia + 1}',
            )

        resultado = self._proyectar(fecha=date(2026, 8, 29))

        self.assertEqual(resultado['proximo_hito']['tipo'], 'inicio_semana')
        self.assertEqual(resultado['proximo_hito']['fecha'], date(2026, 8, 31))
        self.assertEqual(resultado['proximo_hito']['etiqueta'], 'Inicio de la semana 2')

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

    def test_dashboard_ofrece_dos_accesos_a_trayectoria(self):
        plantilla = Path('clientes/templates/clientes/mockup_demo.html').read_text()
        self.assertEqual(plantilla.count("{% url 'clientes:trayectoria_plan' %}"), 2)
        self.assertIn('Ver trayectoria del plan', plantilla)
        self.assertIn('Trayectoria del plan', plantilla)


class TrayectoriaPlanMacrocicloTests(TestCase):
    """Cobertura del rediseño: mini-timeline horizontal del macrociclo,
    'siguiente fase' y 'fases cerradas', todo derivado del mismo listado
    que ya calculaba _periodizacion_actual (ninguna llamada extra al
    planificador ni ningun dato inventado)."""

    def setUp(self):
        self.user = User.objects.create_user('trayectoria_macro', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _proyectar(self, fecha):
        with patch(
            'entrenos.services.trayectoria_plan_service._generar_plan_helms',
            return_value=PLAN_HELMS_MULTIFASE,
        ):
            return proyectar_trayectoria_plan(self.cliente, fecha=fecha)

    def test_macrociclo_expone_fases_del_anio_con_estado_y_parametros_reales(self):
        resultado = self._proyectar(date(2026, 3, 15))
        macro = resultado['macrociclo']
        self.assertEqual(len(macro['fases']), 3)
        estados = {f['nombre']: f['estado'] for f in macro['fases']}
        self.assertEqual(estados, {'Fase A': 'completada', 'Fase B': 'actual', 'Fase C': 'pendiente'})
        fase_b = next(f for f in macro['fases'] if f['nombre'] == 'Fase B')
        self.assertEqual(fase_b['reps'], '8-10')
        self.assertEqual(fase_b['rpe_inicio'], 7)
        self.assertEqual(fase_b['rpe_fin'], 9)
        self.assertEqual(fase_b['descanso_seg'], 75)

    def test_macrociclo_siguiente_fase_es_la_inmediatamente_posterior(self):
        resultado = self._proyectar(date(2026, 3, 15))
        self.assertEqual(resultado['macrociclo']['siguiente_fase']['nombre'], 'Fase C')

    def test_macrociclo_ultima_fase_no_tiene_siguiente(self):
        resultado = self._proyectar(date(2026, 5, 1))  # dentro de Fase C
        self.assertIsNone(resultado['macrociclo']['siguiente_fase'])

    def test_macrociclo_fases_cerradas_son_solo_las_ya_finalizadas(self):
        resultado = self._proyectar(date(2026, 3, 15))
        nombres_cerradas = [f['nombre'] for f in resultado['macrociclo']['fases_cerradas']]
        self.assertEqual(nombres_cerradas, ['Fase A'])

    def test_periodizacion_actual_incluye_parametros_reales_de_la_fase(self):
        resultado = self._proyectar(date(2026, 3, 15))
        self.assertEqual(resultado['periodizacion']['reps'], '8-10')
        self.assertEqual(resultado['periodizacion']['rpe_inicio'], 7)
        self.assertEqual(resultado['periodizacion']['rpe_fin'], 9)

    def test_sin_plan_helms_disponible_macrociclo_es_none_sin_romper(self):
        with patch(
            'entrenos.services.trayectoria_plan_service._generar_plan_helms',
            side_effect=Exception('boom'),
        ):
            resultado = proyectar_trayectoria_plan(self.cliente, fecha=date(2026, 3, 15))
        self.assertIsNone(resultado['macrociclo'])
        self.assertIn('plan_helms_no_disponible', resultado['limitations'])


class TrayectoriaPlanLenguajeTemplateTests(TrayectoriaPlanTests):
    """El rediseño retira el lenguaje de depuracion interna de la plantilla;
    estas pruebas fijan ese contrato para que no vuelva a filtrarse."""

    def test_semana_sin_materializar_no_expone_lenguaje_de_backend(self):
        resultado = self._proyectar(fecha=date(2026, 8, 31))  # semana 2 del bloque, nunca creada
        self.assertIn('semana_no_materializada', resultado['limitations'])
        html = render_to_string('clientes/trayectoria_plan.html', {
            'cliente': self.cliente, 'trayectoria': resultado,
        })
        self.assertNotIn('Aún no materializada', html)
        self.assertNotIn('La trayectoria no anticipa ni crea sesiones', html)
        self.assertIn('Pendiente de iniciar', html)
        self.assertIn('Semana 36', html)

    def test_plantilla_no_incluye_disclaimer_ni_panel_de_limitaciones_crudo(self):
        resultado = self._proyectar()
        html = render_to_string('clientes/trayectoria_plan.html', {
            'cliente': self.cliente, 'trayectoria': resultado,
        })
        self.assertNotIn('Una lectura vertical desde la periodización anual', html)
        self.assertNotIn('Qué no puede afirmar esta lectura', html)
