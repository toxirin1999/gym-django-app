"""Plan reconoce lo entrenado aunque la semana no tenga contrato materializado."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from clientes import tests_trayectoria_plan as base
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan
from rutinas.models import Rutina

PLAN_HELMS_CON_SESIONES = base.PLAN_HELMS_CON_SESIONES


class SesionesHelmsRealizadasTests(TestCase):
    def setUp(self):
        # Mismo bloque que la suite base, sin heredar (ni repetir) sus tests.
        base.TrayectoriaPlanTests.setUp(self)
        self.contrato.delete()

    def _proyectar_helms(self, fecha=date(2026, 8, 26)):
        with patch(
            'entrenos.services.trayectoria_plan_service._generar_plan_helms',
            return_value=PLAN_HELMS_CON_SESIONES,
        ):
            return proyectar_trayectoria_plan(self.cliente, fecha=fecha)

    def _entreno(self, nombre, fecha, ejecucion=None, cliente=None, estado=None):
        return EntrenoRealizado.objects.create(
            cliente=cliente or self.cliente, rutina=Rutina.objects.create(nombre=nombre),
            fecha=fecha, fecha_ejecucion=ejecucion or fecha,
            estado_cierre=estado or EntrenoRealizado.ESTADO_COMPLETA,
        )

    def _sesiones(self, resultado):
        return {s['nombre']: s for s in resultado['semana']['sesiones']}

    def test_sesion_hecha_se_marca_realizada(self):
        self._entreno('Día 1 - Fuerza', date(2026, 8, 24))
        sesiones = self._sesiones(self._proyectar_helms())
        dia1 = sesiones['Día 1 - Fuerza']
        self.assertTrue(dia1['realizada'])
        self.assertTrue(dia1['completa'])
        self.assertEqual(dia1['estado'], SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(dia1['fecha_realizada'], date(2026, 8, 24))
        self.assertFalse(sesiones['Día 2 - Fuerza']['realizada'])

    def test_ya_no_cuenta_como_no_registrada(self):
        self._entreno('Día 1 - Fuerza', date(2026, 8, 24))
        self.assertEqual(self._proyectar_helms()['semana']['sesiones_no_registradas'], 0)

    def test_sin_entreno_sigue_pendiente_y_no_registrada(self):
        # 13-oct-2026: sigue pendiente, pero no se pierde: la cola la pasa a hoy.
        resultado = self._proyectar_helms()
        dia1 = self._sesiones(resultado)['Día 1 - Fuerza']
        self.assertFalse(dia1['realizada'])
        self.assertEqual(dia1['fecha_efectiva'], date(2026, 8, 26))
        self.assertEqual(resultado['semana']['sesiones_no_registradas'], 0)

    def test_sesion_hecha_otro_dia_de_la_semana_tambien_cuenta(self):
        # Planificada el lunes, hecha (y guardada) el martes.
        self._entreno('Día 1 - Fuerza', date(2026, 8, 25))
        dia1 = self._sesiones(self._proyectar_helms())['Día 1 - Fuerza']
        self.assertTrue(dia1['realizada'])
        self.assertEqual(dia1['fecha_realizada'], date(2026, 8, 25))

    def test_cierre_parcial(self):
        self._entreno('Día 1 - Fuerza', date(2026, 8, 24), estado=EntrenoRealizado.ESTADO_PARCIAL)
        dia1 = self._sesiones(self._proyectar_helms())['Día 1 - Fuerza']
        self.assertTrue(dia1['realizada'])
        self.assertTrue(dia1['parcial'])
        self.assertFalse(dia1['completa'])

    def test_sesion_hecha_hoy_no_es_el_proximo_hito(self):
        self._entreno('Día 2 - Fuerza', date(2026, 8, 26))
        resultado = self._proyectar_helms()
        self.assertNotEqual((resultado['proximo_hito'] or {}).get('etiqueta'), 'Día 2 - Fuerza')

    def test_entreno_de_otra_semana_o_de_otro_cliente_no_cuenta(self):
        self._entreno('Día 1 - Fuerza', date(2026, 8, 17))
        self._entreno('Día 1 - Fuerza', date(2026, 8, 24), cliente=self.otro)
        self.assertFalse(self._sesiones(self._proyectar_helms())['Día 1 - Fuerza']['realizada'])

    def test_un_entreno_no_cubre_dos_sesiones(self):
        plan = {
            **PLAN_HELMS_CON_SESIONES,
            'entrenos_por_fecha': {
                '2026-08-24': {'nombre_rutina': 'Día 1 - Fuerza', 'ejercicios': [{'nombre': 'Press'}]},
                '2026-08-27': {'nombre_rutina': 'Día 1 - Fuerza', 'ejercicios': [{'nombre': 'Press'}]},
            },
        }
        self._entreno('Día 1 - Fuerza', date(2026, 8, 24))
        with patch('entrenos.services.trayectoria_plan_service._generar_plan_helms', return_value=plan):
            resultado = proyectar_trayectoria_plan(self.cliente, fecha=date(2026, 8, 26))
        hechas = [s['realizada'] for s in resultado['semana']['sesiones']]
        self.assertEqual(hechas, [True, False])
