"""31-oct-2026 · Recorrido de la app: coherencia entre pantallas."""

from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from entrenos.services.marcador_semanal_service import _frase


class Marcador(SimpleTestCase):
    def test_avisa_de_lo_que_falta_y_de_lo_que_supera_con_hechos(self):
        falta = {'grupo': 'Trapecio', 'hechas': 3, 'plan': 6, 'pendientes': 1.5, 'proyectadas': 4.5,
                 'estado': 'falta', 'cubren': ['Día 4']}
        triceps = {'grupo': 'Tríceps', 'hechas': 12, 'plan': 9, 'pendientes': 5, 'proyectadas': 17,
                   'estado': 'supera', 'cubren': ['Día 5']}
        f = _frase([falta, triceps])
        self.assertTrue(f.startswith('Trapecio: llevas 3 de 6 que pide el plan'))
        self.assertIn('las sesiones pendientes (Día 4) aportan 1,5 y quedarías en 4,5', f)
        self.assertIn('Tríceps: llevas 12 y las pendientes suman 5 (17); el plan de la semana pide 9.', f)
        self.assertNotIn('cansan', f)


class Semantica(SimpleTestCase):
    def test_zancadas_cuentan_las_dos_piernas(self):
        from entrenos.services.peso_semantica_service import normalizar_semantica_carga
        z = normalizar_semantica_carga({'nombre': 'Zancadas con Kettlebell', 'peso_kg': 16})
        self.assertEqual((z['peso_formato'], z['reps_unidad']), ('por_lado', 'por pierna'))


class Trayectoria(SimpleTestCase):
    def test_dias_restantes_al_final_del_bloque(self):
        from clientes.views import _progreso_temporal_para_trayectoria
        p = _progreso_temporal_para_trayectoria({
            'periodizacion': {'inicio': date(2026, 9, 28), 'fin': date(2026, 11, 1)},
            'fecha_corte': date(2026, 10, 31),
        })
        self.assertEqual((p['dias_restantes'], p['semanas_restantes']), (1, 1))


class ProximaSesion(SimpleTestCase):
    def test_ahora_usa_la_cola(self):
        from clientes.views import _proxima_tras_hoy
        with patch('entrenos.services.sesion_recomendada._siguiente_de_cola',
                   return_value={'nombre': 'Dia 5 - Hipertrofia', 'fecha': date(2026, 10, 30)}):
            self.assertEqual(_proxima_tras_hoy(object()), 'Dia 5 - Hipertrofia')
