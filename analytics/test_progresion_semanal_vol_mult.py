# analytics/test_progresion_semanal_vol_mult.py
"""
Bug real encontrado probando en la app: `generar_entrenamiento_para_fecha`
(el camino que usa entrenos/services/sesion_recomendada.py para construir
SesionProgramada — lo que el usuario ve como "plan de hoy") usaba siempre
`volumen_multiplicador` = vol_fin del bloque (el pico de la ÚLTIMA semana),
sin importar en qué semana del bloque estuviera el usuario realmente.

`generar_plan_anual` SÍ calculaba correctamente el multiplicador progresivo
por semana (semanas_detalle[i]['vol_mult'], interpolado linealmente entre
vol_inicio y vol_fin) — pero `generar_entrenamiento_para_fecha` no reutilizaba
esa lógica, así que cualquier semana del bloque (incluida la primera) recibía
el volumen máximo de la última semana.

Ejemplo real: david en semana 4 de 7 de "Hipertrofia — Especialización"
(vol_inicio=1.15, vol_fin=1.3) debería tener vol_mult≈1.225 (progreso 3/6),
pero el bug le daba 1.3 fijo — el mismo volumen que en la semana 7.
"""

from datetime import date

from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion


def _build_planner(perfil_data: dict) -> PlanificadorHelms:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    return planner


PERFIL_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
    'año_planificacion': 2026,
}


class TestVolMultProgresivoPorSemana(TestCase):
    """El multiplicador de volumen debe seguir la progresión real de la
    semana dentro del bloque, no el pico fijo de la última semana."""

    def test_primera_semana_del_bloque_no_usa_vol_fin(self):
        """
        La primera semana de cualquier bloque de contenido debe usar un
        vol_mult cercano a vol_inicio, NO vol_fin — si usara vol_fin, la
        progresión de volumen dentro del bloque no existiría.
        """
        planner = _build_planner(PERFIL_DAVID)
        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        bloque = next(b for b in periodizacion if b['fase'] == 'hipertrofia_especifica')
        primera_semana_num = bloque['semanas'][0]

        # Reconstruir la fecha correspondiente a la primera semana del bloque.
        año = 2026
        primer_dia = date(año, 1, 1)
        dias_para_lunes = (0 - primer_dia.weekday() + 7) % 7
        inicio_plan = primer_dia + __import__('datetime').timedelta(days=dias_para_lunes)
        fecha = inicio_plan + __import__('datetime').timedelta(days=(primera_semana_num - 1) * 7)

        resultado = planner.generar_entrenamiento_para_fecha(fecha)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.get('semana_en_bloque'), 1)

        vol_mult_esperado = bloque['vol_inicio']  # progreso=0 en la primera semana
        # No podemos leer vol_mult directamente del resultado (no se expone),
        # así que comparamos el total de series con la última semana del bloque
        # — si el bug estuviera presente, ambas semanas darían el MISMO total.
        ultima_semana_num = bloque['semanas'][-1]
        fecha_ultima = inicio_plan + __import__('datetime').timedelta(
            days=(ultima_semana_num - 1) * 7
        )
        resultado_ultima = planner.generar_entrenamiento_para_fecha(fecha_ultima)
        self.assertEqual(resultado_ultima.get('semana_en_bloque'), len(bloque['semanas']))

        total_primera = sum(e['series'] for e in resultado.get('ejercicios', []))
        total_ultima = sum(e['series'] for e in resultado_ultima.get('ejercicios', []))

        self.assertLess(
            total_primera, total_ultima,
            f"Primera semana del bloque ({total_primera} series) debería tener "
            f"MENOS volumen que la última ({total_ultima}) — la progresión no "
            f"se está aplicando, ambas están usando vol_fin."
        )
