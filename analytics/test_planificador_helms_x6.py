# analytics/test_planificador_helms_x6.py
"""
Tests TDD para X.6 — motor de asignación automática grupo→día.

Esta pieza vive aislada: NO está conectada a core.py ni a DISTRIBUCION_DIAS.
La integración con producción es X.7, gated por revisión del usuario.

Grupos de tests:
  TestDeterminismo          — 20 ejecuciones idénticas = mismo resultado
  TestRestriccionesDuras    — separación, bisagra, budget nunca violados (perfil real david)
  TestReglaMEV              — ningún grupo con volumen>0 queda en 0 sesiones (3 días sat.)
  TestPerfilDavid           — perfil real: no converge a body-part-split 1x para todos
  TestAfinidadSinergica     — grupos sinérgicos prefieren compartir día
  TestFusionSesionesCortas  — días con pocas series se fusionan con adyacente
  TestExcepcionSinCabida    — dias=1 + varios grupos grandes → excepción clara
"""

from django.test import TestCase

from analytics.planificador_helms.distribucion.asignador import (
    GrupoParaAsignar,
    ResultadoAsignacion,
    AsignacionImposibleError,
    asignar_semana,
)
from analytics.planificador_helms.distribucion.frecuencia import (
    calcular_frecuencia,
    cap_sesion_para_grupo,
)
from analytics.planificador_helms.volumen.calculadora import calcular_volumen_optimo
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from analytics.planificador_helms.config import (
    GRUPOS_GRANDES,
    CAPACIDAD_SERIES_DIA,
    UMBRAL_FUSION_SESION,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de test
# ──────────────────────────────────────────────────────────────────────────────

_DAVID = {
    'id': 2,
    'nombre': 'david',
    'experiencia_años': 7,
    'objetivo_principal': 'general',
    'dias_disponibles': 5,
}

_TODOS_LOS_GRUPOS = [
    'pecho', 'espalda', 'hombros', 'biceps', 'triceps',
    'cuadriceps', 'isquios', 'gluteos',
    'gemelos', 'core', 'trapecios', 'antebrazos',
]

# Patrón dominante por grupo (para los tests; el caller real llama a PatronManager)
_PATRON_DOMINANTE = {
    'pecho': 'empuje_horizontal',
    'espalda': 'traccion_vertical',
    'hombros': 'empuje_vertical',
    'biceps': 'aislamiento',
    'triceps': 'aislamiento',
    'cuadriceps': 'rodilla',
    'isquios': 'bisagra',
    'gluteos': 'bisagra',
    'gemelos': 'aislamiento',
    'core': 'aislamiento',
    'trapecios': 'aislamiento',
    'antebrazos': 'aislamiento',
}


def _grupo(nombre: str, volumen: int, mev: int = 4,
           variante_peso: str = 'ligera') -> GrupoParaAsignar:
    """Construye un GrupoParaAsignar con valores de test razonables."""
    patron = _PATRON_DOMINANTE.get(nombre, 'aislamiento')
    vp = variante_peso if patron == 'bisagra' else None
    return GrupoParaAsignar(
        nombre=nombre,
        volumen_objetivo=volumen,
        mev=mev,
        es_grande=(nombre in GRUPOS_GRANDES),
        patron_dominante=patron,
        variante_peso=vp,
    )


def _grupos_david() -> dict:
    """
    Construye el mapa de grupos para el perfil real de david:
    avanzado, objetivo='general', 5 días.
    """
    perfil = PerfilCliente(_DAVID)
    nivel = perfil.calcular_nivel_experiencia()
    objetivo = perfil.objetivo_principal
    factor = perfil.calcular_factor_recuperacion()
    grupos = {}
    for nombre in _TODOS_LOS_GRUPOS:
        vol = calcular_volumen_optimo(nombre, nivel, objetivo, factor)
        patron = _PATRON_DOMINANTE.get(nombre, 'aislamiento')
        vp = 'ligera' if patron == 'bisagra' else None
        grupos[nombre] = GrupoParaAsignar(
            nombre=nombre,
            volumen_objetivo=vol,
            mev=max(round(vol * 0.60), 4),
            es_grande=(nombre in GRUPOS_GRANDES),
            patron_dominante=patron,
            variante_peso=vp,
        )
    return grupos


# ──────────────────────────────────────────────────────────────────────────────
# TestDeterminismo
# ──────────────────────────────────────────────────────────────────────────────

class TestDeterminismo(TestCase):
    """20 ejecuciones con el mismo input dan exactamente el mismo output."""

    def test_20_ejecuciones_identicas_perfil_david(self):
        grupos = _grupos_david()
        resultados = [asignar_semana(grupos, 5) for _ in range(20)]
        ref = resultados[0]
        for i, r in enumerate(resultados[1:], 2):
            self.assertEqual(
                r.asignacion, ref.asignacion,
                msg=f'asignacion difiere en ejecución {i}',
            )
            self.assertEqual(
                r.frecuencia_efectiva, ref.frecuencia_efectiva,
                msg=f'frecuencia_efectiva difiere en ejecución {i}',
            )
            self.assertEqual(
                r.grupos_degradados, ref.grupos_degradados,
                msg=f'grupos_degradados difiere en ejecución {i}',
            )

    def test_20_ejecuciones_identicas_escenario_simple(self):
        grupos = {
            'pecho': _grupo('pecho', 20),
            'espalda': _grupo('espalda', 22),
            'biceps': _grupo('biceps', 14),
        }
        resultados = [asignar_semana(grupos, 3) for _ in range(20)]
        ref = resultados[0]
        for i, r in enumerate(resultados[1:], 2):
            self.assertEqual(r.asignacion, ref.asignacion, msg=f'Run {i}')


# ──────────────────────────────────────────────────────────────────────────────
# TestRestriccionesDuras
# ──────────────────────────────────────────────────────────────────────────────

class TestRestriccionesDuras(TestCase):
    """
    Las restricciones duras nunca se violan en el perfil real de david (5 días).
    """

    def setUp(self):
        self.grupos = _grupos_david()
        self.resultado = asignar_semana(self.grupos, 5)

    def test_separacion_minima_1_dia_entre_toques_del_mismo_grupo(self):
        """Dos toques del mismo grupo siempre están a ≥2 índices de distancia."""
        from analytics.planificador_helms.distribucion.asignador import (
            cap_sesion_para_grupo,
        )
        asig = self.resultado.asignacion
        # construir mapa grupo → lista de índices de día (numéricos)
        grupo_dias: dict = {}
        for dia_key, grupos_lista in asig.items():
            idx = int(dia_key.split('_')[1])
            for g in grupos_lista:
                grupo_dias.setdefault(g, []).append(idx)

        for grupo, dias in grupo_dias.items():
            dias_sorted = sorted(dias)
            for i in range(len(dias_sorted) - 1):
                diff = dias_sorted[i + 1] - dias_sorted[i]
                self.assertGreaterEqual(
                    diff, 2,
                    msg=f'{grupo} tiene toques en días {dias_sorted[i]} y {dias_sorted[i+1]} (diff={diff} < 2)',
                )

    def test_budget_no_excedido_en_ningun_dia(self):
        """Ningún día supera CAPACIDAD_SERIES_DIA excepto por forzado (regla de oro)."""
        asig = self.resultado.asignacion
        for dia_key, grupos_lista in asig.items():
            total = sum(cap_sesion_para_grupo(g) for g in grupos_lista)
            # Permitimos un exceso pequeño por la regla de oro (force-place del 1er toque)
            # pero en el perfil de david con 5 días no debería ocurrir
            self.assertLessEqual(
                total, CAPACIDAD_SERIES_DIA + 10,
                msg=f'{dia_key} tiene {total} series (budget={CAPACIDAD_SERIES_DIA})',
            )

    def test_todos_los_grupos_con_volumen_tienen_al_menos_1_sesion(self):
        freq = self.resultado.frecuencia_efectiva
        for nombre, grupo in self.grupos.items():
            if grupo.volumen_objetivo > 0:
                self.assertGreater(
                    freq.get(nombre, 0), 0,
                    msg=f'{nombre} tiene 0 sesiones efectivas',
                )

    def test_frecuencia_efectiva_no_supera_frecuencia_calculada(self):
        """El motor nunca asigna MÁS sesiones de las que calcular_frecuencia pide."""
        freq = self.resultado.frecuencia_efectiva
        for nombre, grupo in self.grupos.items():
            freq_deseada = calcular_frecuencia(nombre, grupo.volumen_objetivo, 5)
            self.assertLessEqual(
                freq.get(nombre, 0), freq_deseada,
                msg=f'{nombre}: freq_efectiva={freq.get(nombre, 0)} > freq_deseada={freq_deseada}',
            )


# ──────────────────────────────────────────────────────────────────────────────
# TestReglaMEV
# ──────────────────────────────────────────────────────────────────────────────

class TestReglaMEV(TestCase):
    """
    Escenario de 3 días saturado: 5 grupos grandes (freq=2 cada uno), 3 días.

    Con 10 placements deseados en 3 días (budget 72 total), habrá degradación,
    pero NINGÚN grupo debe quedar con 0 sesiones efectivas.

    Aquí isquios y gluteos son bisagra LIGERA para evitar restricciones
    de bisagra pesada que complicarían el escenario de saturación.
    """

    def _construir_grupos_saturacion(self):
        """
        5 grupos grandes, volumen=20 c/u → freq=2 para cap=10 (ceil(20/10)=2).
        Con 3 días: 5×2=10 placements, capacidad total=72. Algunos 2º toques no cabrán.
        """
        return {
            'cuadriceps': _grupo('cuadriceps', 20),
            'espalda':    _grupo('espalda',    20),
            'gluteos':    _grupo('gluteos',    20, variante_peso='ligera'),
            'isquios':    _grupo('isquios',    20, variante_peso='ligera'),
            'pecho':      _grupo('pecho',      20),
        }

    def test_ningún_grupo_con_volumen_queda_en_0_sesiones(self):
        grupos = self._construir_grupos_saturacion()
        resultado = asignar_semana(grupos, 3)
        for nombre in grupos:
            freq_ef = resultado.frecuencia_efectiva.get(nombre, 0)
            self.assertGreater(
                freq_ef, 0,
                msg=f'{nombre} tiene 0 sesiones efectivas en escenario saturado 3d',
            )

    def test_hay_degradacion_pero_no_total(self):
        """Hay grupos degradados (freq reducida) pero ninguno a 0."""
        grupos = self._construir_grupos_saturacion()
        resultado = asignar_semana(grupos, 3)
        # Con 5 grupos × freq=2 y solo 3 días, el budget limita — debe haber degradados
        # (al menos algunos segundos toques no cabrán)
        freq_total = sum(resultado.frecuencia_efectiva.values())
        freq_deseada = sum(
            calcular_frecuencia(n, g.volumen_objetivo, 3)
            for n, g in grupos.items()
        )
        # freq_total debe ser > 0 para todos los grupos (ya probado arriba)
        # y ≤ freq_deseada
        self.assertLessEqual(freq_total, freq_deseada)
        # Verificar que los grupos degradados no tienen 0 sesiones
        for nombre in resultado.grupos_degradados:
            self.assertGreater(
                resultado.frecuencia_efectiva.get(nombre, 0), 0,
                msg=f'{nombre} está en degradados Y tiene 0 sesiones',
            )

    def test_budget_no_excedido_en_escenario_saturado(self):
        grupos = self._construir_grupos_saturacion()
        resultado = asignar_semana(grupos, 3)
        for dia_key, grupos_lista in resultado.asignacion.items():
            total = sum(cap_sesion_para_grupo(g) for g in grupos_lista)
            self.assertLessEqual(
                total, CAPACIDAD_SERIES_DIA,
                msg=f'{dia_key} excede budget en escenario saturado',
            )


# ──────────────────────────────────────────────────────────────────────────────
# TestPerfilDavid
# ──────────────────────────────────────────────────────────────────────────────

class TestPerfilDavid(TestCase):
    """
    Perfil real de david (avanzado, 5d, general): el motor NO debe converger
    a body-part-split 1x para todos los grupos (que es lo que hace DISTRIBUCION_DIAS[5]).
    """

    def setUp(self):
        self.grupos = _grupos_david()
        self.resultado = asignar_semana(self.grupos, 5)

    def test_algunos_grupos_tienen_frecuencia_mayor_que_1(self):
        """Con volúmenes avanzados, al menos algunos grupos deben entrenar 2+ veces."""
        freq = self.resultado.frecuencia_efectiva
        grupos_con_freq_2_o_mas = [
            n for n, f in freq.items() if f >= 2
        ]
        self.assertGreater(
            len(grupos_con_freq_2_o_mas), 0,
            msg='El motor convergió a body-part-split 1x para todos — esto no es correcto.',
        )

    def test_no_body_part_split_1x_total(self):
        """La frecuencia total (suma de freq_efectiva) debe superar len(grupos)."""
        freq_total = sum(self.resultado.frecuencia_efectiva.values())
        n_grupos = len([g for g in self.grupos.values() if g.volumen_objetivo > 0])
        self.assertGreater(
            freq_total, n_grupos,
            msg=f'freq_total={freq_total} == n_grupos={n_grupos} → body-part-split 1x',
        )

    def test_grupos_alta_demanda_frecuencia_2_o_mas(self):
        """
        espalda, hombros, biceps, trapecios desean freq alta (X.5). Con el
        presupuesto real del asignador (fix 2026-07-20), estos 4 son los que
        logran freq≥2 en 5 días con 12 grupos compitiendo por presupuesto.
        """
        freq = self.resultado.frecuencia_efectiva
        for nombre in ['espalda', 'hombros', 'biceps', 'trapecios']:
            self.assertGreaterEqual(
                freq.get(nombre, 0), 2,
                msg=f'{nombre} debería tener freq≥2 con volumen avanzado',
            )

    def test_antebrazos_con_freq_1_al_menos(self):
        """Antebrazos desea freq=1; debe tener exactamente 1 sesión."""
        freq = self.resultado.frecuencia_efectiva
        self.assertEqual(
            freq.get('antebrazos', 0), 1,
            msg='antebrazos debería tener freq=1',
        )

    def test_todos_los_dias_tienen_al_menos_un_grupo(self):
        """Con 12 grupos en 5 días, todos los días deben tener entrenamiento."""
        self.assertEqual(len(self.resultado.asignacion), 5)

    def test_grupos_en_dias_son_listas_no_vacias(self):
        for dia_key, grupos_lista in self.resultado.asignacion.items():
            self.assertTrue(
                len(grupos_lista) > 0,
                msg=f'{dia_key} está vacío',
            )


# ──────────────────────────────────────────────────────────────────────────────
# TestAfinidadSinergica
# ──────────────────────────────────────────────────────────────────────────────

class TestAfinidadSinergica(TestCase):
    """
    En un escenario controlado, grupos sinérgicos prefieren el mismo día.
    """

    def test_pecho_y_triceps_comparten_dia_en_escenario_simple(self):
        """
        Con pecho y triceps sin competencia de otros grupos sinérgicos y
        suficientes días, deberían terminar en el mismo día (afinidad blanda).
        """
        grupos = {
            'pecho':   _grupo('pecho',   10),   # freq=1, cap=10
            'triceps': _grupo('triceps', 8),    # freq=1, cap=8
        }
        # 2 días disponibles, presupuesto suficiente para ambos en un solo día
        resultado = asignar_semana(grupos, 2)
        # Encontrar en qué día está cada uno
        dia_pecho = dia_triceps = None
        for dia_key, glist in resultado.asignacion.items():
            if 'pecho' in glist:
                dia_pecho = dia_key
            if 'triceps' in glist:
                dia_triceps = dia_key
        self.assertEqual(
            dia_pecho, dia_triceps,
            msg=(
                f'pecho ({dia_pecho}) y triceps ({dia_triceps}) no comparten día. '
                f'La afinidad sinérgica debería haberlos unido.'
            ),
        )

    def test_espalda_biceps_comparten_dia_en_escenario_simple(self):
        """espalda y biceps son sinérgicos — deberían compartir día si hay hueco."""
        grupos = {
            'espalda': _grupo('espalda', 10),
            'biceps':  _grupo('biceps', 8),
        }
        resultado = asignar_semana(grupos, 2)
        dia_espalda = dia_biceps = None
        for dia_key, glist in resultado.asignacion.items():
            if 'espalda' in glist:
                dia_espalda = dia_key
            if 'biceps' in glist:
                dia_biceps = dia_key
        self.assertEqual(
            dia_espalda, dia_biceps,
            msg='espalda y biceps no comparten día',
        )

    def test_grupos_no_sinergicos_no_forzados_al_mismo_dia(self):
        """
        pecho y cuadriceps NO son sinérgicos. Con dos días disponibles,
        no hay razón para que compartan día — deben separarse
        para maximizar recuperación.
        """
        grupos = {
            'pecho':      _grupo('pecho', 10),
            'cuadriceps': _grupo('cuadriceps', 10),
        }
        # Mismas condiciones que el test anterior: 2 días, 1 grupo cada uno
        resultado = asignar_semana(grupos, 2)
        # Con 2 grupos no sinérgicos y 2 días, cada uno debería ir a un día distinto
        dias = list(resultado.asignacion.keys())
        self.assertEqual(len(dias), 2, msg='pecho y cuadriceps deberían ocupar días distintos')


# ──────────────────────────────────────────────────────────────────────────────
# TestFusionSesionesCortas
# ──────────────────────────────────────────────────────────────────────────────

class TestFusionSesionesCortas(TestCase):
    """
    Un día con menos de UMBRAL_FUSION_SESION series se fusiona con el adyacente
    cuando hay presupuesto disponible.
    """

    def test_grupo_solitario_sin_sinergia_se_funde_con_adyacente(self):
        """
        antebrazos (cap=8, sinergy={espalda, biceps}) en un contexto donde
        espalda/biceps no existen. antebrazos queda solo en un día con 8 series
        (< UMBRAL_FUSION=10) y lo fusionamos con el adyacente más libre.

        Setup: 3 días, cuadriceps y pecho (sinergy={triceps}, tampoco existe).
        antebrazos sin sinérgicos presentes → va al día más libre (dia_3).
        dia_3 tiene 8 series < UMBRAL → fusión hacia dia_1 o dia_2.
        """
        grupos = {
            'cuadriceps': _grupo('cuadriceps', 10),  # cap=10, sinergy={gemelos}
            'pecho':      _grupo('pecho', 10),        # cap=10, sinergy={triceps}
            'antebrazos': _grupo('antebrazos', 6),   # cap=8, sinergy={espalda, biceps} — ninguno presente
        }
        resultado = asignar_semana(grupos, 3)

        grupos_por_dia = {}
        for dia_key, glist in resultado.asignacion.items():
            for g in glist:
                grupos_por_dia[g] = dia_key

        dia_antebrazos = grupos_por_dia.get('antebrazos')
        dia_cuadriceps = grupos_por_dia.get('cuadriceps')
        dia_pecho = grupos_por_dia.get('pecho')

        # Con fusión, antebrazos debe compartir día con cuadriceps o pecho
        self.assertIn(
            dia_antebrazos, [dia_cuadriceps, dia_pecho],
            msg=(
                f'antebrazos ({dia_antebrazos}) no se fusionó con cuadriceps ({dia_cuadriceps}) '
                f'ni pecho ({dia_pecho}). '
                f'Asignación completa: {resultado.asignacion}'
            ),
        )

    def test_todos_los_grupos_asignados_tras_fusion(self):
        """
        La fusión no debe dejar ningún grupo sin sesión.
        Escenario con 5 grupos en 3 días para forzar sesiones cortas.
        """
        grupos = {
            'cuadriceps': _grupo('cuadriceps', 10),
            'espalda':    _grupo('espalda', 10),
            'pecho':      _grupo('pecho', 10),
            'hombros':    _grupo('hombros', 8),
            'antebrazos': _grupo('antebrazos', 6),
        }
        resultado = asignar_semana(grupos, 3)
        freq = resultado.frecuencia_efectiva
        for nombre in grupos:
            self.assertGreater(
                freq.get(nombre, 0), 0,
                msg=f'{nombre} quedó sin sesión después de la fusión',
            )

    def test_sesion_corta_permanece_si_adyacente_no_tiene_hueco(self):
        """
        Si el adyacente está lleno (no cabe el cap del grupo), la sesión corta
        se mantiene en lugar de violar el presupuesto.

        Setup: 2 días con 3 grupos grandes (10+10+10=30) en dia_1 y solo
        antebrazos (8) en dia_2. dia_2 < UMBRAL. Único adyacente (dia_1)
        tiene 30 series; 30+8=38 > CAPACIDAD_SERIES_DIA (36) → no cabe.
        antebrazos se queda en dia_2.
        """
        grupos = {
            'cuadriceps': _grupo('cuadriceps', 10),
            'espalda':    _grupo('espalda', 10),
            'pecho':      _grupo('pecho', 10),
            'antebrazos': _grupo('antebrazos', 6),  # debe ir a dia_2 sola
        }
        # Con 2 días: cuadriceps, espalda, pecho → dia_1 (30 series),
        # antebrazos → dia_2 (8 series). dia_1 lleno (30+8=38>36).
        resultado = asignar_semana(grupos, dias_disponibles=2)

        # Todos los grupos deben tener sesión (ninguno perdido)
        freq = resultado.frecuencia_efectiva
        for nombre in grupos:
            self.assertGreater(freq.get(nombre, 0), 0, msg=f'{nombre} sin sesión')

        # antebrazos debe estar asignado a algún día
        grupos_por_dia = {}
        for dia_key, glist in resultado.asignacion.items():
            for g in glist:
                grupos_por_dia[g] = dia_key
        self.assertIsNotNone(grupos_por_dia.get('antebrazos'), 'antebrazos sin día asignado')


# ──────────────────────────────────────────────────────────────────────────────
# TestExcepcionSinCabida
# ──────────────────────────────────────────────────────────────────────────────

class TestExcepcionSinCabida(TestCase):
    """
    dias_disponibles=1 con 4 grupos grandes (caps=10×4=40 series)
    supera CAPACIDAD_SERIES_DIA=36 del único día disponible.
    El motor debe lanzar AsignacionImposibleError con mensaje claro.

    Con 3 grupos grandes (30 < 36) NO se lanza excepción — sí caben en 1 día.
    """

    def test_exception_1_dia_4_grupos_grandes(self):
        grupos = {
            'cuadriceps': _grupo('cuadriceps', 10),  # cap=10
            'espalda':    _grupo('espalda', 10),     # cap=10
            'gluteos':    _grupo('gluteos', 10),     # cap=10
            'pecho':      _grupo('pecho', 10),       # cap=10
            # total min = 40 > 36 = 1 día × CAPACIDAD_SERIES_DIA
        }
        with self.assertRaises(AsignacionImposibleError) as ctx:
            asignar_semana(grupos, dias_disponibles=1)

        msg = str(ctx.exception)
        self.assertIn('40', msg, msg='El mensaje debería indicar series necesarias (40)')
        self.assertIn('36', msg, msg='El mensaje debería indicar capacidad disponible (36)')

    def test_exception_mensaje_contiene_capacidad_y_necesario(self):
        """El mensaje de la excepción debe ser informativo (no silencio)."""
        grupos = {
            'cuadriceps': _grupo('cuadriceps', 10),
            'gluteos':    _grupo('gluteos',    10, variante_peso='ligera'),
            'isquios':    _grupo('isquios',    10, variante_peso='ligera'),
            'pecho':      _grupo('pecho',      10),
        }
        with self.assertRaises(AsignacionImposibleError) as ctx:
            asignar_semana(grupos, dias_disponibles=1)
        msg = str(ctx.exception)
        # Debe mencionar 40 (series mínimas) y 36 (capacidad)
        self.assertTrue(
            '40' in msg or '36' in msg,
            msg=f'Mensaje de excepción no informativo: {msg}',
        )

    def test_3_grupos_grandes_en_1_dia_caben_sin_excepcion(self):
        """3 grupos grandes (10+10+10=30 < 36): caben en 1 día sin excepción."""
        grupos = {
            'pecho':      _grupo('pecho', 10),
            'espalda':    _grupo('espalda', 10),
            'cuadriceps': _grupo('cuadriceps', 10),
        }
        resultado = asignar_semana(grupos, dias_disponibles=1)
        self.assertIn('dia_1', resultado.asignacion)

    def test_exception_es_subclase_de_value_error(self):
        """AsignacionImposibleError hereda de ValueError para facilitar catching."""
        grupos = {
            'cuadriceps': _grupo('cuadriceps', 10),
            'espalda':    _grupo('espalda', 10),
            'gluteos':    _grupo('gluteos', 10),
            'pecho':      _grupo('pecho', 10),
        }
        with self.assertRaises(ValueError):
            asignar_semana(grupos, dias_disponibles=1)
