"""
Phase 62G.1 — Agrupadores para el Centro de decisiones 2.0.

Lógica pura: agrupa traces y decisiones de carga para que el panel muestre
"qué evidencias siguen vivas" en vez de un log infinito. No toca el motor
ni los modelos — solo transforma listas ya existentes en grupos.
"""

from datetime import date, datetime

from django.test import SimpleTestCase

from entrenos.models import GymDecisionLog, IntervencionPlan, PreferenciaPlanAprendida
from entrenos.services.centro_decisiones_service import (
    agrupar_decisiones_carga,
    agrupar_traces_recientes,
    construir_estado_plan,
)


def _trace(decision_label, explicacion, fecha_label, lesion_label='', fecha=None):
    return {
        'fecha': fecha or date(2026, 5, 28),
        'fecha_label': fecha_label,
        'decision_label': decision_label,
        'explicacion': explicacion,
        'capas_usadas': [],
        'supresion_razon': None,
        'lesion_label': lesion_label,
        'tiene_detalles': bool(lesion_label),
        'evaluacion_label': None,
        'evaluacion_resumen': None,
    }


def _log(ejercicio, accion, motivo, fecha_creacion):
    log = GymDecisionLog(ejercicio=ejercicio, accion=accion, motivo=motivo)
    log.fecha_creacion = fecha_creacion
    return log


class TestAgruparTracesRecientes(SimpleTestCase):

    def test_traces_iguales_se_agrupan_con_count_y_ultima_fecha(self):
        traces = [
            _trace('Versión esencial', 'El plan priorizó ejercicios principales y dejó los accesorios como opcionales.', 'jueves 28 may', fecha=date(2026, 5, 28)),
            _trace('Versión esencial', 'El plan priorizó ejercicios principales y dejó los accesorios como opcionales.', 'martes 26 may', fecha=date(2026, 5, 26)),
            _trace('Versión esencial', 'El plan priorizó ejercicios principales y dejó los accesorios como opcionales.', 'domingo 24 may', fecha=date(2026, 5, 24)),
            _trace('Versión esencial', 'El plan priorizó ejercicios principales y dejó los accesorios como opcionales.', 'viernes 22 may', fecha=date(2026, 5, 22)),
        ]

        grupos = agrupar_traces_recientes(traces)

        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]['decision_label'], 'Versión esencial')
        self.assertEqual(grupos[0]['count'], 4)
        self.assertEqual(grupos[0]['fecha_label'], 'jueves 28 may')

    def test_grupos_distintos_no_se_mezclan(self):
        traces = [
            _trace('Sesión del plan', 'Sesión del plan ejecutada sin adaptaciones.', 'martes 19 may', fecha=date(2026, 5, 19)),
            _trace('Sesión del plan', 'Sesión del plan ejecutada sin adaptaciones.', 'lunes 18 may', fecha=date(2026, 5, 18)),
            _trace('Versión esencial', 'El plan priorizó ejercicios principales y dejó los accesorios como opcionales.', 'jueves 28 may', fecha=date(2026, 5, 28)),
        ]

        grupos = agrupar_traces_recientes(traces)

        self.assertEqual(len(grupos), 2)
        sesion_grupo = next(g for g in grupos if g['decision_label'] == 'Sesión del plan')
        self.assertEqual(sesion_grupo['count'], 2)
        self.assertEqual(sesion_grupo['fecha_label'], 'martes 19 may')

    def test_recuperacion_por_lesion_no_se_mezcla_con_descanso_normal(self):
        traces = [
            _trace(
                'Recuperación recomendada',
                'Descanso recomendado — lesión activa en ese momento.',
                'lunes 18 may',
                lesion_label='hombro en fase aguda',
                fecha=date(2026, 5, 18),
            ),
            _trace('Día de descanso', 'Día de descanso según el plan.', 'domingo 17 may', fecha=date(2026, 5, 17)),
        ]

        grupos = agrupar_traces_recientes(traces)

        self.assertEqual(len(grupos), 2)
        recuperacion = next(g for g in grupos if g['decision_label'] == 'Recuperación recomendada')
        descanso = next(g for g in grupos if g['decision_label'] == 'Día de descanso')
        self.assertEqual(recuperacion['count'], 1)
        self.assertEqual(recuperacion['lesion_label'], 'hombro en fase aguda')
        self.assertEqual(descanso['count'], 1)

    def test_detalle_conserva_items_originales(self):
        t1 = _trace('Versión esencial', 'explicación', 'jueves 28 may', fecha=date(2026, 5, 28))
        t2 = _trace('Versión esencial', 'explicación', 'martes 26 may', fecha=date(2026, 5, 26))

        grupos = agrupar_traces_recientes([t1, t2])

        self.assertEqual(grupos[0]['items'], [t1, t2])

    def test_lista_vacia_devuelve_lista_vacia(self):
        self.assertEqual(agrupar_traces_recientes([]), [])


class TestAgruparDecisionesCarga(SimpleTestCase):

    def test_siete_decisiones_mantener_se_agrupan(self):
        ejercicios = [
            'press banca', 'sentadilla', 'remo', 'dominadas',
            'curl biceps', 'press militar', 'zancadas',
        ]
        logs = [
            _log(ej, 'mantener', 'Parámetros estables — enfocar en técnica.', datetime(2026, 5, 28, 10, 0))
            for ej in ejercicios
        ]

        grupos = agrupar_decisiones_carga(logs)

        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]['accion'], 'mantener')
        self.assertEqual(grupos[0]['count'], 7)
        self.assertEqual(len(grupos[0]['ejercicios']), 7)
        self.assertIn('Press Banca', grupos[0]['ejercicios'])

    def test_reducir_peso_y_cambiar_variante_no_se_mezclan(self):
        logs = [
            _log('press militar maquina', 'bajar_peso', 'Tope de máquina.', datetime(2026, 5, 27, 10, 0)),
            _log('curl martillo', 'cambiar_variante', 'Molestia recurrente.', datetime(2026, 5, 26, 10, 0)),
        ]

        grupos = agrupar_decisiones_carga(logs)

        self.assertEqual(len(grupos), 2)
        acciones = {g['accion'] for g in grupos}
        self.assertEqual(acciones, {'bajar_peso', 'cambiar_variante'})

    def test_motivo_principal_es_del_log_mas_reciente_del_grupo(self):
        logs = [
            _log('press banca', 'mantener', 'Motivo más reciente.', datetime(2026, 5, 28, 10, 0)),
            _log('sentadilla', 'mantener', 'Motivo antiguo.', datetime(2026, 5, 20, 10, 0)),
        ]

        grupos = agrupar_decisiones_carga(logs)

        self.assertEqual(grupos[0]['motivo_principal'], 'Motivo más reciente.')

    def test_detalle_conserva_logs_originales(self):
        log1 = _log('press banca', 'mantener', 'motivo', datetime(2026, 5, 28, 10, 0))
        log2 = _log('sentadilla', 'mantener', 'motivo', datetime(2026, 5, 20, 10, 0))

        grupos = agrupar_decisiones_carga([log1, log2])

        self.assertEqual(grupos[0]['items'], [log1, log2])

    def test_lista_vacia_devuelve_lista_vacia(self):
        self.assertEqual(agrupar_decisiones_carga([]), [])


class TestConstruirEstadoPlan(SimpleTestCase):

    def test_todo_vacio_devuelve_modo_normal(self):
        estado = construir_estado_plan([], [], [])

        self.assertFalse(estado['hay_senales_activas'])
        self.assertIn('modo normal', estado['narrativa'])

    def test_una_preferencia_activa_se_nombra_en_la_narrativa(self):
        pref = PreferenciaPlanAprendida(
            tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            descripcion='evitar pierna tras fútbol',
        )

        estado = construir_estado_plan([pref], [], [])

        self.assertTrue(estado['hay_senales_activas'])
        self.assertIn('1 señal activa', estado['narrativa'])
        self.assertIn('evitar pierna tras fútbol', estado['narrativa'])

    def test_varias_senales_se_enumeran_juntas(self):
        pref = PreferenciaPlanAprendida(
            tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            descripcion='evitar pierna tras fútbol',
        )
        interv = IntervencionPlan(
            tipo=IntervencionPlan.TIPO_NO_SUBIR,
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )

        estado = construir_estado_plan([pref], [interv], [])

        self.assertTrue(estado['hay_senales_activas'])
        self.assertIn('2 señales activas', estado['narrativa'])
        self.assertIn('evitar pierna tras fútbol', estado['narrativa'])
        self.assertIn('No subir cargas', estado['narrativa'])
