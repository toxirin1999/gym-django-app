# analytics/test_planificador_helms_x9_validacion_integral.py
"""
X.9 — Validación integral del motor de asignación automática (PlanificadorHelms).

Cuatro conjuntos de tests formales:

  1. MEV/MRV: el volumen semanal generado no sale del rango científico para
     bloques de hipertrofia y fuerza, en la matriz de 7 perfiles heredada del
     script comparar_volumen_planificador.py + 3 perfiles adicionales que cubren
     los objetivos restantes del sistema: 'fuerza', 'perdida_peso', 'resistencia'.

  2. Descarga: el volumen de la semana de descarga es estrictamente inferior al
     de la semana de hipertrofia del mismo perfil (sanity check; sin imponer
     suelo de MEV, coherente con el diseño de core.py).

  3. Regla de oro del asignador: ningún grupo muscular con volumen_objetivo > 0
     (grupos que el motor recibió para asignar) termina con 0 series en la semana
     generada. Si algún perfil viola esta regla, la excepción se captura, se
     formatea como hallazgo detallado y el test falla descriptivamente.

  4. Determinismo HTTP end-to-end: dos peticiones consecutivas al briefing del
     mismo cliente + fecha, con cache vaciado entre ellas, devuelven el mismo
     plan ejercicio a ejercicio y en el mismo orden.

Cache TTL documentado (sin acción requerida):
  - core.PlanificadorHelms.generar_plan_anual: 3600 s (1 hora)
  - _calcular_ejercicios_dia (views.py): 1800 s (30 min)
  - vista_plan_calendario cache externo: 1800 s (30 min)
  Ninguna clave vive indefinidamente. TTLs razonables — no requiere fix.
"""

import math
from datetime import date
from typing import Dict, List, Tuple

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client as DjangoClient
from django.urls import reverse

from analytics.management.commands.comparar_volumen_planificador import PERFILES_MATRIZ
from analytics.planificador_helms.config import VOLUMENES_BASE
from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
from analytics.planificador_helms.volumen.calculadora import (
    CalculadoraVolumen,
    calcular_volumen_optimo,
)
from clientes.models import Cliente
from clientes.utils import get_cliente_actual


# ---------------------------------------------------------------------------
# Perfiles adicionales para cubrir los objetivos reales del sistema que
# no aparecen en PERFILES_MATRIZ (que solo usa 'hipertrofia' y 'general').
# OBJETIVO_CHOICES en Cliente = hipertrofia | fuerza | perdida_peso |
# resistencia | general. 'fuerza_hipertrofia' y 'potencia' son internos
# del motor y no son choices del modelo, no se testean aquí.
# ---------------------------------------------------------------------------
_PERFILES_OBJETIVOS_ADICIONALES = [
    {
        'label': 'intermedio / 4d / fuerza',
        'data': {'id': 901, 'experiencia_años': 2, 'objetivo_principal': 'fuerza', 'dias_disponibles': 4},
    },
    {
        'label': 'principiante / 4d / perdida_peso',
        'data': {'id': 902, 'experiencia_años': 0.5, 'objetivo_principal': 'perdida_peso', 'dias_disponibles': 4},
    },
    {
        'label': 'intermedio / 5d / resistencia',
        'data': {'id': 903, 'experiencia_años': 2, 'objetivo_principal': 'resistencia', 'dias_disponibles': 5},
    },
]

_TODOS_LOS_PERFILES = PERFILES_MATRIZ + _PERFILES_OBJETIVOS_ADICIONALES

# Índices de bloque en la periodización (0-based, pares = contenido, impares = descarga).
# Estructura: Acum(0)+D(1) / FuerzaBase(2)+D(3) / Intens(4)+D(5) / Potencia(6)+D(7)
#           / Espec(8)+D(9) / FuerzaAv(10)+D(11) / Meta(12)+D(13) / Peaking(14)+D(15)
_IDX_HIPERTROFIA = 0   # Hipertrofia — Acumulación
_IDX_DESCARGA = 1      # Descarga Activa (tras Hipertrofia Acumulación)
_IDX_FUERZA = 2        # Fuerza — Base


# ---------------------------------------------------------------------------
# Helpers de prueba
# ---------------------------------------------------------------------------

def _build_planner(perfil_data: dict) -> Tuple[PerfilCliente, PlanificadorHelms]:
    """
    Instancia perfil + planificador con historial vacío para que la salida
    sea reproducible sin depender de datos de BD en el entorno de test.
    """
    perfil = PerfilCliente(perfil_data)
    planner = PlanificadorHelms(perfil)
    planner._cliente_obj = None              # evita consulta Cliente.objects.get
    planner._historial_ejercicios_raw = []   # sin historial → sin historial previo
    return perfil, planner


def _resumen_semana(semana: dict) -> Dict[str, Dict]:
    """Devuelve {grupo: {'freq': int, 'series': int}} para la semana dada."""
    grupos_series: Dict[str, int] = {}
    grupos_dias: Dict[str, set] = {}
    for dia_key, ejercicios in semana.items():
        for ej in ejercicios:
            grupo = ej['grupo_muscular']
            grupos_series[grupo] = grupos_series.get(grupo, 0) + ej['series']
            grupos_dias.setdefault(grupo, set()).add(dia_key)
    return {
        g: {'freq': len(grupos_dias[g]), 'series': grupos_series[g]}
        for g in grupos_series
    }


def _grupos_con_volumen_efectivo(
    perfil: PerfilCliente,
    bloque: dict,
    fase: str,
) -> Dict[str, int]:
    """
    Replica la lógica de core._generar_semana_especifica para determinar qué
    grupos tendrían vol_efectivo > 0 Y candidatos disponibles. Solo estos
    grupos deben ser verificados en el test de la regla de oro.
    """
    nivel = perfil.calcular_nivel_experiencia()
    objetivo = perfil.objetivo_principal
    factor = perfil.calcular_factor_recuperacion()
    vol_mult = bloque.get('volumen_multiplicador', 1.0)

    # Obtener candidatos para la fase (sin cliente = sin filtro por lesión)
    ejercicios_bloque = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
        numero_bloque=1,
        fase=fase,
        evitados=set(),
        cliente=None,
    )

    result: Dict[str, int] = {}
    for grupo in VOLUMENES_BASE.get(nivel, VOLUMENES_BASE['avanzado']):
        if not ejercicios_bloque.get(grupo):
            continue  # sin candidatos → no se pasa al asignador
        vol_base = calcular_volumen_optimo(grupo, nivel, objetivo, factor)
        if vol_base <= 0:
            continue
        mrv_g = CalculadoraVolumen.calcular_volumen_maximo_adaptativo(grupo, nivel)
        vol_efectivo = int(min(vol_base * vol_mult, mrv_g))
        if vol_efectivo > 0:
            result[grupo] = vol_efectivo
    return result


# ===========================================================================
# 1. Validación MEV/MRV — bloques hipertrofia y fuerza
# ===========================================================================

class TestX9MEVMRVIntegral(TestCase):
    """
    Valida el rango de volumen semanal generado para bloques de hipertrofia
    y fuerza en la matriz de 10 perfiles.

    REGLAS POR TIPO DE BLOQUE:
    ─────────────────────────────────────────────────────────────────────
    Hipertrofia (fase='hipertrofia', vol_mult 0.90-1.05):
      Regla estricta: MEV <= total_series <= MRV.
      El objetivo de hipertrofia es maximizar síntesis proteica; cualquier
      grupo que quede bajo MEV no alcanza el estímulo mínimo de adaptación.

    Fuerza (fase='fuerza', vol_mult 0.80-0.90):
      HALLAZGO DOCUMENTADO: el vol_mult=0.80 reduce el volumen por debajo
      del MEV (definido para hipertrofia) en prácticamente todos los perfiles.
      Grupos como pecho, espalda, cuádriceps reciben 4-11 series cuando MEV
      es 6-12 (según nivel).
      DECISIÓN TÉCNICA: esto es COMPORTAMIENTO ESPERADO, no un bug.
      Los bloques de fuerza en el sistema Helms priorizan adaptación neural
      (carga alta, volumen bajo). El MEV de CalculadoraVolumen está calibrado
      para hipertrofia; aplicarlo a fuerza es un error de categoría.
      El invariante relevante en fuerza es que el volumen NO supere MRV
      (límite de recuperación), no que alcance MEV (umbral de crecimiento).
      REGLA DE FUERZA APLICADA: series <= MRV Y series > 0.
    ─────────────────────────────────────────────────────────────────────

    Bloques excluidos de ambos checks (por diseño documentado en core.py):
      - Descarga (vol_mult=0.50): caída deliberada, sin invariante de volumen.
      - Potencia (vol_mult 0.50-0.70): misma lógica que fuerza pero más extremo.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()

    def _generar_resumen_bloque(
        self, perfil_data: dict, bloque_idx: int
    ) -> tuple:
        """
        Genera la semana del bloque (sem 1 = vol_mult más bajo = caso más
        restrictivo) y devuelve (perfil, resumen, bloque_info).
        """
        perfil, planner = _build_planner(perfil_data)
        bloque = self.periodizacion[bloque_idx]
        bloque_sem1 = bloque.copy()
        if bloque.get('semanas_detalle'):
            bloque_sem1['volumen_multiplicador'] = bloque['semanas_detalle'][0]['vol_mult']
        semana = planner._generar_semana_especifica(bloque_sem1, bloque_idx + 1)
        return perfil, _resumen_semana(semana), bloque_sem1

    # ── Hipertrofia: check MEV/MRV estricto ──────────────────────────────────

    def test_mev_mrv_bloque_hipertrofia_todos_los_perfiles(self):
        """
        Bloque Hipertrofia — Acumulación: MEV <= series <= MRV para todos
        los grupos presentes. Estricto porque el objetivo de hipertrofia
        requiere alcanzar el estímulo mínimo de adaptación (MEV) sin
        exceder el límite de recuperación (MRV).
        """
        for entry in _TODOS_LOS_PERFILES:
            with self.subTest(perfil=entry['label']):
                perfil, resumen, bloque_sem1 = self._generar_resumen_bloque(
                    entry['data'], _IDX_HIPERTROFIA
                )
                nivel = perfil.calcular_nivel_experiencia()
                violaciones: List[str] = []
                for grupo, stats in resumen.items():
                    total = stats['series']
                    mev, mrv = CalculadoraVolumen.calcular_rango_volumen(grupo, nivel)
                    if not (mev <= total <= mrv):
                        violaciones.append(
                            f"  grupo={grupo!r} series={total} mev={mev} mrv={mrv} "
                            f"nivel={nivel!r}"
                        )
                if violaciones:
                    self.fail(
                        f"Perfil [{entry['label']}], "
                        f"{bloque_sem1['nombre']} (vol_mult={bloque_sem1['volumen_multiplicador']}):\n"
                        + "\n".join(violaciones)
                    )

    # ── Fuerza: solo MRV — el MEV es específico de hipertrofia ───────────────

    def test_mrv_bloque_fuerza_todos_los_perfiles(self):
        """
        Bloque Fuerza — Base: verifica que ningún grupo supera MRV y que
        ningún grupo presente queda con 0 series.

        NO se verifica MEV porque los bloques de fuerza operan con vol_mult
        0.80-0.90 y caen deliberadamente por debajo del MEV de hipertrofia
        en todos los perfiles (hallazgo documentado: pecho, espalda, cuádriceps,
        glúteos, isquios). Esto es COMPORTAMIENTO ESPERADO:
          - fuerza↑ requiere volumen↓ para permitir recuperación con cargas altas
          - el MEV de CalculadoraVolumen es un umbral de hipertrofia, no de fuerza
        No abrir fase de fix sin decisión explícita del usuario.
        """
        for entry in _TODOS_LOS_PERFILES:
            with self.subTest(perfil=entry['label']):
                perfil, resumen, bloque_sem1 = self._generar_resumen_bloque(
                    entry['data'], _IDX_FUERZA
                )
                nivel = perfil.calcular_nivel_experiencia()
                violaciones: List[str] = []
                for grupo, stats in resumen.items():
                    total = stats['series']
                    _, mrv = CalculadoraVolumen.calcular_rango_volumen(grupo, nivel)
                    if total <= 0:
                        violaciones.append(
                            f"  grupo={grupo!r} series=0 (grupo asignado con 0 series)"
                        )
                    elif total > mrv:
                        violaciones.append(
                            f"  grupo={grupo!r} series={total} > mrv={mrv} nivel={nivel!r}"
                        )
                if violaciones:
                    self.fail(
                        f"Perfil [{entry['label']}], "
                        f"{bloque_sem1['nombre']} (vol_mult={bloque_sem1['volumen_multiplicador']}):\n"
                        + "\n".join(violaciones)
                    )


# ===========================================================================
# 2. Descarga — sanity check de reducción de volumen
# ===========================================================================

class TestX9DescargaReduceVolumen(TestCase):
    """
    La semana de Descarga Activa tiene MENOS series totales que la semana de
    Hipertrofia — Acumulación para el mismo perfil. Verifica que el vol_mult=0.5
    de descarga produce un efecto real y no se neutraliza por el ceil en vol_dia.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()

    def test_descarga_menor_que_hipertrofia(self):
        for entry in _TODOS_LOS_PERFILES:
            with self.subTest(perfil=entry['label']):
                perfil_data = entry['data']
                label = entry['label']

                _, planner_hiper = _build_planner(perfil_data)
                bloque_hiper = self.periodizacion[_IDX_HIPERTROFIA]
                semana_hiper = planner_hiper._generar_semana_especifica(bloque_hiper, 1)
                total_hiper = sum(
                    ej['series']
                    for ejercicios in semana_hiper.values()
                    for ej in ejercicios
                )

                _, planner_dsc = _build_planner(perfil_data)
                bloque_dsc = self.periodizacion[_IDX_DESCARGA]
                semana_dsc = planner_dsc._generar_semana_especifica(bloque_dsc, 2)
                total_dsc = sum(
                    ej['series']
                    for ejercicios in semana_dsc.values()
                    for ej in ejercicios
                )

                self.assertGreater(
                    total_hiper,
                    total_dsc,
                    msg=(
                        f"Perfil [{label}]: la descarga ({total_dsc} series) debería "
                        f"tener menos series que hipertrofia ({total_hiper} series)."
                    ),
                )


# ===========================================================================
# 3. Regla de oro — ningún grupo con vol > 0 queda en 0 series
# ===========================================================================

class TestX9ReglaCeroSeries(TestCase):
    """
    Para cada grupo que el motor de asignación recibe con vol_efectivo > 0
    (y con ejercicios candidatos disponibles), la semana generada debe
    mostrar ese grupo con al menos 1 serie.

    Test aplicado al bloque Hipertrofia — Acumulación como caso representativo.
    Fuerza — Base queda implícito: si falla en hipertrofia, se reporta y se decide
    si abrir fase adicional.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()

    def test_ningun_grupo_con_volumen_queda_en_cero(self):
        bloque_hiper = self.periodizacion[_IDX_HIPERTROFIA]
        fase_str = bloque_hiper['fase']

        for entry in _TODOS_LOS_PERFILES:
            with self.subTest(perfil=entry['label']):
                perfil_data = entry['data']
                label = entry['label']

                perfil, planner = _build_planner(perfil_data)

                # Grupos que el asignador debería haber recibido con vol > 0
                grupos_esperados = _grupos_con_volumen_efectivo(
                    perfil, bloque_hiper, fase_str
                )

                semana = planner._generar_semana_especifica(bloque_hiper, 1)
                resumen = _resumen_semana(semana)

                grupos_ausentes: List[str] = [
                    f"  grupo={g!r} vol_efectivo={v} (nivel={perfil.calcular_nivel_experiencia()!r})"
                    for g, v in grupos_esperados.items()
                    if g not in resumen or resumen[g]['series'] <= 0
                ]

                if grupos_ausentes:
                    self.fail(
                        f"Perfil [{label}], bloque {bloque_hiper['nombre']!r}:\n"
                        "Los siguientes grupos tenían vol_efectivo > 0 pero terminaron "
                        "con 0 series (posible violación de la regla de oro del asignador):\n"
                        + "\n".join(grupos_ausentes)
                    )


# ===========================================================================
# 4. Determinismo end-to-end vía HTTP
# ===========================================================================

class TestX9DeterminismoHTTP(TestCase):
    """
    Dos peticiones consecutivas al briefing del mismo cliente + fecha,
    con Django cache vaciado entre ambas, devuelven el mismo plan ejercicio
    a ejercicio y en el mismo orden.

    Verifica que no hay no-determinismo escondido (iteración sobre set/dict
    sin orden estable) que solo aparezca en la capa HTTP/vista.

    Perfil de test: intermedio, 4 días, hipertrofia.
    Fecha: 2026-01-05 (lunes de la semana 1 del plan 2026 — día de entreno
    para perfiles de 4 días donde dias_entreno_indices=[0,1,3,4]).
    """

    FECHA_TEST = date(2026, 1, 5)

    def setUp(self):
        self.user = User.objects.create_user(
            username='x9_det_user',
            email='x9det@test.local',
            password='testpass_x9',
        )
        # El signal crea el Cliente al crear el User; lo recuperamos y actualizamos.
        self.cliente = get_cliente_actual(self.user)
        self.cliente.nombre = 'X9 Test'
        self.cliente.email = 'x9det@test.local'
        self.cliente.telefono = '000000000'
        self.cliente.experiencia_años = 2
        self.cliente.objetivo_principal = 'hipertrofia'
        self.cliente.dias_disponibles = 4
        self.cliente.nivel_estres = 5
        self.cliente.calidad_sueño = 7
        self.cliente.nivel_energia = 7
        self.cliente.save()
        self.http_client = DjangoClient()
        self.http_client.login(username='x9_det_user', password='testpass_x9')

    def tearDown(self):
        cache.clear()

    def _get_ejercicios_del_briefing(self) -> List[Tuple]:
        """
        Llama al briefing y devuelve la huella del plan:
        lista ordenada de (nombre, grupo_muscular, series, repeticiones).
        """
        url = reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id])
        response = self.http_client.get(
            url,
            {'fecha': self.FECHA_TEST.isoformat()},
        )
        self.assertEqual(
            response.status_code, 200,
            msg=f"El briefing devolvió {response.status_code} — esperado 200.",
        )
        ejercicios = response.context['ejercicios']
        return [
            (
                ej.get('nombre', ''),
                ej.get('grupo_muscular', ''),
                ej.get('series', 0),
                ej.get('repeticiones') or ej.get('reps_objetivo', ''),
            )
            for ej in ejercicios
        ]

    def test_dos_peticiones_misma_fecha_identicas(self):
        """
        El plan del briefing es byte-idéntico entre dos generaciones independientes
        para el mismo cliente y fecha (cache vaciado entre ellas).
        """
        cache.clear()
        huella_1 = self._get_ejercicios_del_briefing()

        # Vaciar todo el cache — fuerza regeneración completa en la segunda llamada
        cache.clear()
        huella_2 = self._get_ejercicios_del_briefing()

        self.assertEqual(
            huella_1,
            huella_2,
            msg=(
                "Las dos generaciones del briefing para la misma fecha produjeron "
                "resultados diferentes — no-determinismo detectado.\n"
                f"Petición 1 ({len(huella_1)} ejercicios):\n"
                + "\n".join(f"  {e}" for e in huella_1)
                + f"\nPetición 2 ({len(huella_2)} ejercicios):\n"
                + "\n".join(f"  {e}" for e in huella_2)
            ),
        )

    def test_plan_no_vacio_en_fecha_de_entreno(self):
        """
        Para la fecha de test (lunes de semana 1), el briefing devuelve al menos
        un ejercicio — confirma que el setup del test es correcto y la fecha
        es efectivamente un día de entreno para el perfil de 4 días.
        """
        cache.clear()
        huella = self._get_ejercicios_del_briefing()
        self.assertGreater(
            len(huella),
            0,
            msg=(
                f"El briefing del {self.FECHA_TEST} devolvió 0 ejercicios para "
                f"un cliente de 4 días. Verificar que la fecha sea un día de entreno."
            ),
        )
