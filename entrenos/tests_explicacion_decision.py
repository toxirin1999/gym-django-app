"""
Phase 30.1 — Tests for construir_explicacion_decision.

Validates that:
1.  todo_limpio=True when no special conditions.
2.  Lesión aviso produces a senal_activa.
3.  Preferencia aplicada produces a senal_activa.
4.  distribucion_aviso produces a senal_activa.
5.  Overlap: cuando preferencia y distribucion tratan el mismo patrón,
    distribucion queda suprimida (distribucion_aviso_suprimido=True).
6.  Modo reducido produce senal_activa.
7.  causa_label es legible para todas las causas conocidas.
8.  senales_activas está ordenado: lesión primero, luego preferencia, luego distribución.
9.  Sin solapamiento cuando los tipos son distintos.
10. Permiso de progresión frenado produce senal_activa.
"""

from django.test import TestCase

from entrenos.services.explicacion_decision_service import construir_explicacion_decision


def _decision(**kwargs):
    base = {
        'tipo': 'programada_hoy', 'estado': 'entrenar',
        'sesion_programada': None, 'entrenamiento': {},
        'mensaje': '', 'causa_principal': 'sesion_hoy',
        'modo_reducido': False, 'distribucion_aviso': None,
        'preferencia_aplicada': None, 'lesion_aviso': None,
    }
    base.update(kwargs)
    return base


class TestTodoLimpio(TestCase):
    def test_sin_senales_todo_limpio(self):
        result = construir_explicacion_decision(_decision())
        self.assertTrue(result['todo_limpio'])
        self.assertEqual(result['senales_activas'], [])

    def test_estado_descanso_no_es_limpio(self):
        result = construir_explicacion_decision(_decision(estado='descanso'))
        # descanso is a special state, not 'entrenar'
        # todo_limpio requires estado='entrenar' AND no signals
        self.assertFalse(result['todo_limpio'])


class TestLesionSenal(TestCase):
    def test_lesion_aviso_produce_senal(self):
        decision = _decision(lesion_aviso={
            'zona': 'Rodilla', 'fase': 'RETORNO',
            'es_bloqueante': False,
            'ejercicios_en_riesgo': ['Sentadilla', 'Prensa'],
            'mensaje': 'Revisar.',
        })
        result = construir_explicacion_decision(decision)
        self.assertEqual(len(result['senales_activas']), 1)
        self.assertIn('Rodilla', result['senales_activas'][0])

    def test_lesion_aguda_bloqueante_en_senal(self):
        decision = _decision(lesion_aviso={
            'zona': 'Hombro', 'fase': 'AGUDA',
            'es_bloqueante': True,
            'ejercicios_en_riesgo': ['Press militar'],
            'mensaje': 'Fase aguda.',
        })
        result = construir_explicacion_decision(decision)
        self.assertIn('Hombro', result['senales_activas'][0])


class TestPreferenciaSenal(TestCase):
    def test_preferencia_aplicada_produce_senal(self):
        decision = _decision(preferencia_aplicada={
            'tipo': 'evitar_pierna_tras_futbol',
            'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
            'accion_sugerida': 'posponer_recomendado',
        })
        result = construir_explicacion_decision(decision)
        self.assertTrue(any('separar pierna' in s for s in result['senales_activas']))


class TestDistribucionSenal(TestCase):
    def test_distribucion_sin_preferencia_produce_senal(self):
        decision = _decision(distribucion_aviso={
            'tipo': 'redistrib_pierna_futbol',
            'texto': 'Prueba activa: separar pierna del fútbol.',
            'accion_sugerida': 'posponer_opcional',
        })
        result = construir_explicacion_decision(decision)
        self.assertFalse(result['distribucion_aviso_suprimido'])
        self.assertTrue(any('pierna' in s.lower() for s in result['senales_activas']))


class TestOverlapSuprimido(TestCase):
    def test_preferencia_pierna_suplanta_distribucion_pierna(self):
        decision = _decision(
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda que separar pierna te dio más margen.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_pierna_futbol',
                'texto': 'Prueba: separar pierna del fútbol.',
                'accion_sugerida': 'posponer_opcional',
            },
        )
        result = construir_explicacion_decision(decision)
        self.assertTrue(result['distribucion_aviso_suprimido'])
        # Distribucion text NOT in senales_activas
        self.assertFalse(any('Prueba: separar' in s for s in result['senales_activas']))
        # Preference IS in senales_activas
        self.assertTrue(any('margen' in s for s in result['senales_activas']))

    def test_tipos_distintos_no_suprimen(self):
        decision = _decision(
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'Preferencia pierna.',
                'accion_sugerida': 'posponer_recomendado',
            },
            distribucion_aviso={
                'tipo': 'redistrib_dia_frecuente',  # different type
                'texto': 'Prueba: día frecuente.',
                'accion_sugerida': 'posponer_opcional',
            },
        )
        result = construir_explicacion_decision(decision)
        self.assertFalse(result['distribucion_aviso_suprimido'])
        # Both appear
        self.assertTrue(any('Preferencia' in s for s in result['senales_activas']))
        self.assertTrue(any('día frecuente' in s for s in result['senales_activas']))


class TestModoReducido(TestCase):
    def test_modo_reducido_produce_senal(self):
        result = construir_explicacion_decision(_decision(modo_reducido=True))
        self.assertTrue(any('esencial' in s.lower() for s in result['senales_activas']))


class TestCausaLabel(TestCase):
    def test_todas_las_causas_conocidas_tienen_label(self):
        from entrenos.services.explicacion_decision_service import _CAUSAS
        causas = ['lesion', 'fatiga_alta', 'energia_baja', 'futbol_reciente',
                  'sesion_hoy', 'descanso_planificado']
        for causa in causas:
            result = construir_explicacion_decision(_decision(causa_principal=causa))
            self.assertNotEqual(result['causa_label'], causa,
                                msg=f"causa '{causa}' no tiene label legible")

    def test_causa_desconocida_devuelve_la_misma_causa(self):
        result = construir_explicacion_decision(_decision(causa_principal='causa_rara'))
        self.assertEqual(result['causa_label'], 'causa_rara')


class TestOrdenSenales(TestCase):
    def test_lesion_primera_en_senales(self):
        decision = _decision(
            lesion_aviso={
                'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
                'ejercicios_en_riesgo': ['Sentadilla'], 'mensaje': 'Revisar rodilla.',
            },
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda separar pierna del fútbol.',
                'accion_sugerida': 'posponer_recomendado',
            },
        )
        result = construir_explicacion_decision(decision)
        self.assertGreaterEqual(len(result['senales_activas']), 2)
        self.assertIn('Rodilla', result['senales_activas'][0])


class TestPermisoProgresion(TestCase):
    def test_freno_contextual_produce_senal(self):
        decision = _decision(entrenamiento={
            'ejercicios': [],
            'permiso_progresion': {
                'accion': 'mantener_carga',
                'mensaje': 'El plan frena la subida de cargas esta semana.',
            }
        })
        result = construir_explicacion_decision(decision)
        self.assertTrue(any('frena' in s.lower() for s in result['senales_activas']))

    def test_progresion_permitida_no_produce_senal(self):
        decision = _decision(entrenamiento={
            'ejercicios': [],
            'permiso_progresion': {
                'accion': 'progresion_permitida',
                'mensaje': 'Progresión autorizada.',
            }
        })
        result = construir_explicacion_decision(decision)
        self.assertFalse(any('Progresión autorizada' in s for s in result['senales_activas']))


# ── Phase 3.1 — Señal corporal del diario en ¿Por qué hoy? ──────────────────

def _senal(intensidad):
    _textos = {
        'suave':    'Algo de carga corporal en los últimos días.',
        'moderada': 'Varios cierres recientes con cuerpo cargado o apagado.',
        'alta':     'El cuerpo ha registrado dolor en los últimos días.',
    }
    return {'hay_senal': True, 'intensidad': intensidad, 'texto': _textos[intensidad]}


class TestSenalDiarioEnExplicacion(TestCase):

    def test_sin_senal_diario_todo_limpio(self):
        result = construir_explicacion_decision(_decision(), senal_diario={'hay_senal': False})
        self.assertTrue(result['todo_limpio'])
        self.assertEqual(result['senales_activas'], [])

    def test_senal_suave_aparece_en_senales_activas(self):
        result = construir_explicacion_decision(_decision(), senal_diario=_senal('suave'))
        self.assertFalse(result['todo_limpio'])
        self.assertTrue(any('carga corporal' in s.lower() for s in result['senales_activas']))

    def test_senal_moderada_aparece_en_senales_activas(self):
        result = construir_explicacion_decision(_decision(), senal_diario=_senal('moderada'))
        self.assertTrue(any('cargado' in s.lower() or 'apagado' in s.lower() for s in result['senales_activas']))

    def test_senal_alta_aparece_en_senales_activas(self):
        result = construir_explicacion_decision(_decision(), senal_diario=_senal('alta'))
        self.assertTrue(any('dolor' in s.lower() for s in result['senales_activas']))

    def test_senal_diario_es_ultima_senal(self):
        decision = _decision(modo_reducido=True)
        result = construir_explicacion_decision(decision, senal_diario=_senal('moderada'))
        ultima = result['senales_activas'][-1].lower()
        self.assertIn('cargado', ultima)

    def test_senal_diario_no_menciona_bloqueo_ni_cambio_obligatorio(self):
        for intensidad in ('suave', 'moderada', 'alta'):
            result = construir_explicacion_decision(_decision(), senal_diario=_senal(intensidad))
            for senal in result['senales_activas']:
                texto = senal.lower()
                self.assertNotIn('bloquea', texto)
                self.assertNotIn('prohibido', texto)
                self.assertNotIn('debes', texto)

    def test_senal_diario_none_no_rompe(self):
        result = construir_explicacion_decision(_decision(), senal_diario=None)
        self.assertTrue(result['todo_limpio'])
