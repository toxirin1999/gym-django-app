"""Reparto semanal con tope de series por músculo y sesión (12-oct-2026).

Decisión de David: pasadas ~8 series duras de un músculo en la misma sesión,
cada serie extra rinde cada vez menos. El volumen semanal de cada grupo se
reparte en tantas sesiones como haga falta para no pasar de 8; si la semana no
da para todas, se recorta volumen (hacia el MEV) antes que amontonarlo.
"""

import math

from django.test import TestCase

from analytics.planificador_helms.config import (
    CAPACIDAD_SERIES_DIA, GRUPOS_GRANDES, TOPE_SERIES_MUSCULO_SESION,
)
from analytics.planificador_helms.distribucion.asignador import (
    GrupoParaAsignar, _dist, asignar_semana,
)
# Se importa el módulo (no las clases) para que el runner no vuelva a
# descubrir y ejecutar aquí los tests de caracterización.
import analytics.test_planificador_helms_volumen_caracterizacion as caract
from analytics.test_planificador_helms_volumen_caracterizacion import _build_planner, _semana_bloque0

VOLUMENES_DAVID = dict(
    pecho=16, espalda=16, cuadriceps=16, hombros=12, gluteos=12, isquios=10,
    gemelos=10, biceps=10, triceps=10, core=8, trapecios=6, antebrazos=4,
)


def _grupos(volumenes):
    bisagra = {'isquios', 'gluteos'}
    return {
        n: GrupoParaAsignar(
            nombre=n, volumen_objetivo=v, mev=4, es_grande=n in GRUPOS_GRANDES,
            patron_dominante='bisagra' if n in bisagra else 'otro',
            variante_peso='ligera' if n in bisagra else None,
        )
        for n, v in volumenes.items()
    }


def _series_por_grupo_y_dia(semana):
    out = {}
    for dia, ejercicios in semana.items():
        for ej in ejercicios:
            clave = (dia, ej['grupo_muscular'])
            out[clave] = out.get(clave, 0) + ej['series']
    return out


class TestAsignadorRepartoSemanaDavid(TestCase):
    """La semana real de David (5 días) con sus volúmenes de octubre."""

    def setUp(self):
        self.resultado = asignar_semana(_grupos(VOLUMENES_DAVID), 5)

    def test_todo_grupo_con_mas_de_8_series_va_en_dos_sesiones(self):
        for grupo, vol in VOLUMENES_DAVID.items():
            if vol > TOPE_SERIES_MUSCULO_SESION:
                with self.subTest(grupo=grupo):
                    self.assertGreaterEqual(self.resultado.frecuencia_efectiva[grupo], 2)

    def test_sin_degradaciones(self):
        self.assertEqual(self.resultado.grupos_degradados, [])
        self.assertEqual(self.resultado.volumen_efectivo, {})

    def test_dias_equilibrados_y_dentro_del_presupuesto(self):
        cargas = []
        for grupos_dia in self.resultado.asignacion.values():
            cargas.append(sum(
                math.ceil(VOLUMENES_DAVID[g] / self.resultado.frecuencia_efectiva[g])
                for g in grupos_dia
            ))
        self.assertLessEqual(max(cargas), CAPACIDAD_SERIES_DIA)
        self.assertLessEqual(max(cargas) - min(cargas), 8, cargas)

    def test_48_horas_entre_sesiones_del_mismo_grupo(self):
        dias_por_grupo = {}
        for dia, grupos_dia in self.resultado.asignacion.items():
            for g in grupos_dia:
                dias_por_grupo.setdefault(g, []).append(int(dia.split('_')[1]))
        for g, dias in dias_por_grupo.items():
            for a in dias:
                for b in dias:
                    if a < b:
                        self.assertGreaterEqual(_dist(a, b, 5), 2, (g, dias))


class TestSeparacionEnDiasReales(TestCase):
    def test_con_4_dias_martes_y_jueves_estan_a_48_horas(self):
        # 4 días = lunes, martes, jueves, viernes: índices 2 y 3 son mar y jue.
        self.assertEqual(_dist(2, 3, 4), 2)
        self.assertEqual(_dist(1, 2, 4), 1)

    def test_con_4_dias_casi_todo_se_entrena_dos_veces(self):
        resultado = asignar_semana(_grupos(VOLUMENES_DAVID), 4)
        una_vez = [
            g for g, f in resultado.frecuencia_efectiva.items()
            if f < 2 and VOLUMENES_DAVID[g] > TOPE_SERIES_MUSCULO_SESION
        ]
        self.assertLessEqual(len(una_vez), 1, resultado.frecuencia_efectiva)


class TestSemanaSaturada(TestCase):
    def test_recorta_volumen_en_vez_de_amontonarlo(self):
        volumenes = {g: v * 2 for g, v in VOLUMENES_DAVID.items()}  # 260 series en 3 días
        resultado = asignar_semana(_grupos(volumenes), 3)
        self.assertTrue(resultado.volumen_efectivo)
        for g, vol in resultado.volumen_efectivo.items():
            self.assertLess(vol, volumenes[g])
            self.assertGreaterEqual(vol, 1)


class TestPlanCompletoNingunMusculoSeAmontona(TestCase):
    """Con el plan completo (planificador + GestorFatiga), en todos los perfiles."""

    PERFILES = [
        caract.TestCaracterizacionDavid, caract.TestCaracterizacionNovato3d,
        caract.TestCaracterizacionIntermedio4d, caract.TestCaracterizacionIntermedio5d,
        caract.TestCaracterizacionAvanzado6d, caract.TestCaracterizacionAvanzado3d,
        caract.TestCaracterizacionNovato6d,
    ]

    def test_ningun_musculo_pasa_de_10_series_en_una_sesion(self):
        for clase in self.PERFILES:
            _, planner = _build_planner(clase.PERFIL)
            semana = _semana_bloque0(planner)
            for (dia, grupo), series in _series_por_grupo_y_dia(semana).items():
                with self.subTest(perfil=clase.__name__, dia=dia, grupo=grupo):
                    self.assertLessEqual(series, 10)

    def test_david_nunca_pasa_de_8(self):
        _, planner = _build_planner(caract.TestCaracterizacionDavid.PERFIL)
        semana = _semana_bloque0(planner)
        for (dia, grupo), series in _series_por_grupo_y_dia(semana).items():
            with self.subTest(dia=dia, grupo=grupo):
                self.assertLessEqual(series, TOPE_SERIES_MUSCULO_SESION)
