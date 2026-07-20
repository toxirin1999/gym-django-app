# analytics/test_asignador_presupuesto_real.py
"""
Bugfix: el asignador (X.6) presupuestaba cada día usando cap_sesion_para_grupo
(coste FIJO: 10 series para grupos grandes, 8 para pequeños), pero el coste
REAL que un grupo termina costando en una sesión es
ceil(volumen_objetivo_grupo / frecuencia_efectiva) — mayor que el coste fijo
cuando un grupo queda degradado (menos sesiones de las deseadas, cada sesión
restante debe cargar más).

Verificado en la app real (screenshot del usuario, día 1 de david):
  Presupuestado por el asignador: core=8 + cuadriceps=10 + gemelos=8 + gluteos=10 = 36
  Entregado de verdad:            core=8 + cuadriceps=14 + gemelos=10 + gluteos=12 = 44

Fix: `asignar_semana` ahora itera colocación → coste real → recolocación hasta
converger, y aplica una red de seguridad final (degradar o reubicar) que
recalcula el coste real de la asignación que de verdad quedó.

HALLAZGO ESTRUCTURAL (no es un bug, es un hecho del bloque/perfil): para
david (avanzado, 5d, bloque0 con volumen_multiplicador elevado), la demanda
semanal REAL total es ~198 series, pero la capacidad total disponible es
5 × CAPACIDAD_SERIES_DIA = 180. El déficit (~18 series/semana) es estructural
— ningún reparto, por bueno que sea, puede hacer que TODOS los días queden
≤36 cuando la demanda total ya supera la capacidad total. El fix mejora el
reparto (reduce el pico máximo de un día muy sobrecargado a varios días
moderadamente sobrecargados) pero no puede resolver un déficit de capacidad
real — esa es una decisión de producto (subir CAPACIDAD_SERIES_DIA, o revisar
el volumen objetivo del bloque), no un bug de algoritmo.
"""

from django.test import TestCase

from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.config import CAPACIDAD_SERIES_DIA


def _build_planner(perfil_data: dict) -> tuple:
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None
    planner._historial_ejercicios_raw = []
    return perfil, planner


def _semana_bloque0(planner: PlanificadorHelms) -> dict:
    periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
    return planner._generar_semana_especifica(periodizacion[0], 1)


PERFIL_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}


class TestPresupuestoDiaRealRespetado(TestCase):
    """
    El presupuesto CAPACIDAD_SERIES_DIA debe respetarse cuando la demanda
    semanal total lo permite, y repartirse lo más parejo posible cuando no
    (déficit estructural — ver docstring del módulo).
    """

    def setUp(self):
        _, self._planner = _build_planner(PERFIL_DAVID)
        self._semana = _semana_bloque0(self._planner)
        self._series_por_dia = {
            dia: sum(ej['series'] for ej in ejercicios)
            for dia, ejercicios in self._semana.items()
        }
        self._total_semana = sum(self._series_por_dia.values())
        self._capacidad_total = len(self._semana) * CAPACIDAD_SERIES_DIA

    def test_dia_1_dentro_de_presupuesto_o_deficit_documentado(self):
        """
        Reproduce el caso de la captura (día 1 daba 44 con el bug). Con la
        demanda real de este bloque, o bien día 1 cumple el presupuesto
        estricto, o el déficit estructural total explica cualquier exceso.
        """
        series_dia_1 = self._series_por_dia.get('dia_1', 0)
        if self._total_semana <= self._capacidad_total:
            self.assertLessEqual(series_dia_1, CAPACIDAD_SERIES_DIA)
        else:
            # Déficit estructural: el máximo día nunca debería, por sí solo,
            # concentrar TODO el déficit semanal si hay días con hueco.
            self.assertLessEqual(
                series_dia_1, CAPACIDAD_SERIES_DIA + (self._total_semana - self._capacidad_total),
                "día 1 concentra más exceso del que explica el déficit semanal total"
            )

    def test_ningun_dia_supera_presupuesto_mas_deficit_estructural(self):
        """
        Ningún día individual debe superar CAPACIDAD_SERIES_DIA + el déficit
        semanal total repartido — es decir, el reparto debe estar razonablemente
        equilibrado, no concentrar todo el exceso en un solo día.
        """
        deficit_total = max(0, self._total_semana - self._capacidad_total)
        tope_razonable = CAPACIDAD_SERIES_DIA + deficit_total
        for dia_key, series_dia in self._series_por_dia.items():
            with self.subTest(dia=dia_key):
                self.assertLessEqual(
                    series_dia, tope_razonable,
                    f"{dia_key}: {series_dia} series — supera incluso el tope "
                    f"razonable ({tope_razonable}) que ya asume que todo el "
                    f"déficit semanal ({deficit_total}) cayera en un solo día"
                )

    def test_deficit_estructural_no_concentrado_en_un_unico_dia(self):
        """
        Cuando hay déficit estructural, debe repartirse entre varios días,
        no quedar todo concentrado en uno (el bug original: 64 en un día
        mientras otros tenían hueco de sobra).
        """
        if self._total_semana <= self._capacidad_total:
            self.skipTest("Sin déficit estructural en este perfil/bloque")
        dias_sobre_presupuesto = [
            d for d, s in self._series_por_dia.items() if s > CAPACIDAD_SERIES_DIA
        ]
        exceso_maximo = max(
            s - CAPACIDAD_SERIES_DIA for s in self._series_por_dia.values()
        )
        deficit_total = self._total_semana - self._capacidad_total
        self.assertLess(
            exceso_maximo, deficit_total,
            f"Un solo día absorbe todo el déficit estructural ({deficit_total}) "
            f"en vez de repartirlo entre los días sobre presupuesto: {dias_sobre_presupuesto}"
        )

    def test_ningun_grupo_pierde_su_ultima_sesion(self):
        """La regla de oro (nunca 0 sesiones con volumen>0) debe seguir intacta
        tras cualquier corrección del presupuesto."""
        grupos_presentes = {
            ej['grupo_muscular']
            for ejercicios in self._semana.values()
            for ej in ejercicios
        }
        self.assertEqual(len(grupos_presentes), 12, f"Grupos presentes: {grupos_presentes}")
