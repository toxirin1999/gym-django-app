"""31-oct-2026 · Recorrido de la app: coherencia entre pantallas."""

from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from entrenos.services.marcador_semanal_service import _frase


class Marcador(SimpleTestCase):
    def test_avisa_de_lo_que_falta_y_de_lo_que_sobra(self):
        falta = {'grupo': 'Trapecio', 'hechas': 3, 'minimo': 6, 'maximo': 14, 'estado': 'bajo', 'cubren': ['Día 4']}
        triceps = {'grupo': 'Tríceps', 'hechas': 17, 'minimo': 9, 'maximo': 14, 'estado': 'alto', 'cubren': ['Día 5']}
        biceps = {'grupo': 'Bíceps', 'hechas': 14.5, 'minimo': 9, 'maximo': 14, 'estado': 'alto', 'cubren': ['Día 5']}
        f = _frase([falta, triceps, biceps])
        self.assertTrue(f.startswith('Te faltan 3 series de trapecio'))
        self.assertIn('Ya van por encima del máximo tríceps (17 de 9–14) y bíceps (14,5 de 9–14)', f)
        self.assertIn('el Día 5 lo vuelve a cargar', f)


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
