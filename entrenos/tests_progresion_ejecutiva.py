"""
Phase 62H — Progresión ejecutiva.

Regla madre: si el sistema calcula un peso_sugerido (GymDecisionLog
pendiente de evaluar, accion subir_peso/bajar_peso), la siguiente sesión
debe usarlo — salvo que un freno contextual tenga una razón explícita para
posponerlo.

- bajar_peso: ajuste de seguridad, se aplica siempre (no se pospone).
- subir_peso: se pospone si el freno contextual frena progresión esta semana.
- mantener / cambiar_variante / deload: comportamiento previo, sin cambios.

Checklist (10 + contrato visual):
1.  subir_peso pendiente aplica peso_sugerido.
2.  bajar_peso pendiente aplica peso_sugerido.
3.  mantener pendiente no toca peso.
4.  Sin log pendiente → usa carry-forward (sin cambios del plan dinámico).
5.  Log con resultado != None (ya evaluado) no se aplica.
6.  Freno contextual mantener_carga pospone subir_peso.
7.  Freno contextual NO bloquea bajar_peso (regla asimétrica).
8.  cambiar_variante sigue funcionando como antes (regresión).
9.  deload sigue funcionando como antes (regresión).
10. vista_entrenamiento_activo usa el peso aplicado (progresion_aplicada) en
    vez de obtener_ultimo_peso_ejercicio.

Contrato visual: el briefing muestra "progresión aplicada/pospuesta" sin
atribuir la decisión a JOI.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import GymDecisionLog, EntrenoRealizado, EjercicioRealizado, SerieRealizada
from rutinas.models import EjercicioBase, Rutina
from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
from entrenos.services.progresion_contextual_service import evaluar_permiso_local_ejercicio


PERMISO_PERMITIDO = {
    'accion': 'progresion_permitida',
    'motivo': 'ok',
    'mensaje': 'Semana con margen. La progresión está autorizada.',
    'aplica_a_principales': False,
    'aplica_a_accesorios': False,
    'hay_datos_semana': True,
}

PERMISO_MANTENER_CARGA = {
    'accion': 'mantener_carga',
    'motivo': 'carga_alta_semanal',
    'mensaje': 'El plan detecta carga alta esta semana (bloque principal incompleto). No se sube peso.',
    'aplica_a_principales': True,
    'aplica_a_accesorios': True,
    'hay_datos_semana': True,
}

_PERMISO_PATH = 'entrenos.services.progresion_contextual_service.evaluar_permiso_progresion'
_DELOAD_PATH = 'entrenos.services.briefing_service.necesita_deload_gym'
_PERMISO_LOCAL_PATH = 'entrenos.services.progresion_contextual_service.evaluar_permiso_local_ejercicio'

PERMISO_LOCAL_OK = {'puede_subir': True, 'motivo': None, 'mensaje': None}


class ProgresionEjecutivaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_pe62h', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestPE62H', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 6, 11)

    def _ejercicio(self, nombre='Press Banca con Barra', peso_kg=80.0,
                    grupo_muscular='pecho', tipo_ejercicio='compuesto_principal'):
        return {
            'nombre': nombre,
            'grupo_muscular': grupo_muscular,
            'tipo_ejercicio': tipo_ejercicio,
            'peso_kg': peso_kg,
            'series': 4,
            'repeticiones': '8',
            'rpe_objetivo': 8,
        }

    def _log_pendiente(self, accion, ejercicio='Press Banca',
                        peso_anterior=80.0, valor_cambio=5.0, motivo='Motivo de test.'):
        return GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio=ejercicio, accion=accion,
            peso_anterior=peso_anterior, valor_cambio=valor_cambio,
            motivo=motivo, resultado=None,
        )


# ── Case 1: subir_peso pendiente aplica peso_sugerido ────────────────────────

class TestCase1_SubirPesoAplica(ProgresionEjecutivaBase):
    def test_subir_peso_pendiente_aplica_peso_sugerido(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0,
                                   motivo='RPE bajo dos sesiones seguidas — sube carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), \
                patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertEqual(ej['progresion_accion'], 'subir_peso')
        self.assertEqual(ej['peso_kg'], 85.0)  # 80 * 1.05 → redondeo a 2.5
        self.assertTrue(any(c['tipo'] == 'progresion_aplicada' for c in cambios))

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'aplicada')
        self.assertIsNone(log.motivo_postergacion)
        self.assertIsNotNone(log.fecha_aplicacion)


# ── Case 2: bajar_peso pendiente aplica peso_sugerido ────────────────────────

class TestCase2_BajarPesoAplica(ProgresionEjecutivaBase):
    def test_bajar_peso_pendiente_aplica_peso_sugerido(self):
        log = self._log_pendiente('bajar_peso', peso_anterior=80.0, valor_cambio=10.0,
                                   motivo='RPE muy alto sin fallo — reduce carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertEqual(ej['progresion_accion'], 'bajar_peso')
        self.assertEqual(ej['peso_kg'], 72.5)  # 80 * 0.9 → redondeo a 2.5
        self.assertTrue(any(c['tipo'] == 'progresion_aplicada' for c in cambios))

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'aplicada')
        self.assertIsNone(log.motivo_postergacion)


# ── Case 3: mantener pendiente no toca peso ──────────────────────────────────

class TestCase3_MantenerNoTocaPeso(ProgresionEjecutivaBase):
    def test_mantener_pendiente_no_toca_peso(self):
        self._log_pendiente('mantener', peso_anterior=80.0, valor_cambio=None,
                             motivo='Parámetros estables — mantener y enfocar en técnica.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertFalse(ej.get('progresion_aplicada', False))
        self.assertFalse(ej.get('progresion_pospuesta', False))
        self.assertEqual(ej['peso_kg'], 80.0)
        self.assertEqual(cambios, [])


# ── Case 4: sin log pendiente → carry-forward sin cambios ────────────────────

class TestCase4_SinLogPendiente(ProgresionEjecutivaBase):
    def test_sin_log_pendiente_no_modifica_nada(self):
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertFalse(ej.get('progresion_aplicada', False))
        self.assertFalse(ej.get('progresion_pospuesta', False))
        self.assertEqual(ej['peso_kg'], 80.0)
        self.assertEqual(cambios, [])


# ── Case 5: log ya evaluado (resultado != None) no se aplica ────────────────

class TestCase5_LogYaEvaluadoNoAplica(ProgresionEjecutivaBase):
    def test_log_con_resultado_no_se_aplica(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0)
        log.resultado = 'validada'
        log.save()

        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), \
                patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertFalse(ej.get('progresion_aplicada', False))
        self.assertEqual(ej['peso_kg'], 80.0)
        self.assertEqual(cambios, [])


# ── Case 6: freno contextual mantener_carga pospone subir_peso ──────────────

class TestCase6_FrenoPosponeSubirPeso(ProgresionEjecutivaBase):
    def test_mantener_carga_pospone_subir_peso(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0,
                                   motivo='RPE bajo dos sesiones seguidas — sube carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_PERMISO_PATH, return_value=PERMISO_MANTENER_CARGA), \
                patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertFalse(ej.get('progresion_aplicada', False))
        self.assertTrue(ej.get('progresion_pospuesta'))
        self.assertEqual(ej['peso_kg'], 80.0)  # no se sube
        self.assertEqual(ej['progresion_motivo'], PERMISO_MANTENER_CARGA['mensaje'])
        self.assertTrue(any(c['tipo'] == 'progresion_pospuesta' for c in cambios))

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'pospuesta')
        self.assertEqual(log.motivo_postergacion, PERMISO_MANTENER_CARGA['mensaje'])
        primera_fecha = log.fecha_aplicacion
        self.assertIsNotNone(primera_fecha)

        # Segunda llamada con el mismo freno: no debe reescribir fecha_aplicacion
        with patch(_PERMISO_PATH, return_value=PERMISO_MANTENER_CARGA), \
                patch(_DELOAD_PATH, return_value=False):
            aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        log.refresh_from_db()
        self.assertEqual(log.fecha_aplicacion, primera_fecha)


# ── Case 7: freno contextual NO bloquea bajar_peso (regla asimétrica) ───────

class TestCase7_FrenoNoBloqueaBajarPeso(ProgresionEjecutivaBase):
    def test_mantener_carga_no_bloquea_bajar_peso(self):
        log = self._log_pendiente('bajar_peso', peso_anterior=80.0, valor_cambio=10.0,
                                   motivo='RPE muy alto sin fallo — reduce carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_PERMISO_PATH, return_value=PERMISO_MANTENER_CARGA), \
                patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertEqual(ej['progresion_accion'], 'bajar_peso')
        self.assertFalse(ej.get('progresion_pospuesta', False))
        self.assertEqual(ej['peso_kg'], 72.5)

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'aplicada')
        self.assertIsNone(log.motivo_postergacion)


# ── Case 8: cambiar_variante sigue funcionando como antes ───────────────────

class TestCase8_CambiarVarianteRegresion(ProgresionEjecutivaBase):
    def test_estancamiento_sigue_sustituyendo_ejercicio(self):
        GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='Press Banca', accion='cambiar_variante',
            motivo='Sin progresión en 3 sesiones — cambio de estímulo recomendado.',
        )
        ejercicios = [self._ejercicio(nombre='Press Banca con Barra', peso_kg=80.0,
                                       grupo_muscular='pecho')]

        with patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('sustituido'))
        self.assertEqual(ej.get('motivo_sustitucion'), 'estancamiento')
        self.assertNotEqual(ej['nombre'], 'Press Banca con Barra')
        self.assertTrue(any(c['tipo'] == 'sustitucion_estancamiento' for c in cambios))


# ── Case 9: deload sigue funcionando como antes ──────────────────────────────

class TestCase9_DeloadRegresion(ProgresionEjecutivaBase):
    def test_deload_activo_sigue_reduciendo_series_y_rpe(self):
        ejercicios = [self._ejercicio(peso_kg=80.0)]
        ejercicios[0]['series'] = 4
        ejercicios[0]['rpe_objetivo'] = 9

        with patch(_DELOAD_PATH, return_value=True):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('deload'))
        self.assertEqual(ej['series'], 3)
        self.assertEqual(ej['rpe_objetivo'], 7)
        self.assertTrue(any(c['tipo'] == 'deload' for c in cambios))


# ── Case 10: vista_entrenamiento_activo respeta progresion_aplicada ─────────

class TestCase10_VistaActivaUsaProgresion(ProgresionEjecutivaBase):
    def _get(self, ejercicios):
        import json
        c = Client()
        c.login(username='tester_pe62h', password='x')
        params = {
            'fecha': self.hoy.strftime('%Y-%m-%d'),
            'rutina_nombre': '',
            'ejercicios': json.dumps(ejercicios),
        }
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        return c.get(url, params)

    def test_peso_inicial_usa_peso_aplicado_no_carry_forward(self):
        ejercicio = self._ejercicio(nombre='Press Banca con Barra', peso_kg=85.0)
        ejercicio['progresion_aplicada'] = True
        ejercicio['progresion_accion'] = 'subir_peso'
        ejercicio['progresion_motivo'] = 'RPE bajo dos sesiones seguidas — sube carga.'

        response = self._get([ejercicio])
        self.assertEqual(response.status_code, 200)

        ejercicios_planificados = response.context['ejercicios_planificados']
        self.assertEqual(ejercicios_planificados[0]['peso_inicial_kg'], 85.0)


# ══════════════════════════════════════════════════════════════════════════
# Phase 62K — Freno local por ejercicio para subir_peso
# ══════════════════════════════════════════════════════════════════════════

# ── Sección A: unit tests de evaluar_permiso_local_ejercicio ────────────────

class PermisoLocalEjercicioBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_pl62k', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestPL62K', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina Test 62K')
        self.hoy = date(2026, 6, 11)

    def _entreno(self, fecha):
        return EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)

    def _ejercicio_realizado(self, entreno, nombre='Press Banca', **kwargs):
        defaults = dict(nombre_ejercicio=nombre, peso_kg=80.0, series=4, repeticiones=8, completado=True)
        defaults.update(kwargs)
        return EjercicioRealizado.objects.create(entreno=entreno, **defaults)

    def _ejercicio_base(self, nombre):
        return EjercicioBase.objects.get_or_create(
            nombre=nombre, defaults={'grupo_muscular': 'pecho'},
        )[0]

    def _serie(self, entreno, ejercicio_base, tecnica_calidad=None, serie_numero=1, **kwargs):
        defaults = dict(repeticiones=8, completado=True, peso_kg=80.0, tecnica_calidad=tecnica_calidad)
        defaults.update(kwargs)
        return SerieRealizada.objects.create(
            entreno=entreno, ejercicio=ejercicio_base, serie_numero=serie_numero, **defaults,
        )


class TestPermisoLocal01_SinHistorial(PermisoLocalEjercicioBase):
    def test_sin_historial_permite_subir(self):
        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertTrue(resultado['puede_subir'])
        self.assertIsNone(resultado['motivo'])
        self.assertIsNone(resultado['mensaje'])


class TestPermisoLocal02_DeloadActivo(PermisoLocalEjercicioBase):
    def test_deload_activo_bloquea_sin_mirar_historial(self):
        with patch(_DELOAD_PATH, return_value=True):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertFalse(resultado['puede_subir'])
        self.assertEqual(resultado['motivo'], 'deload')


class TestPermisoLocal03_TecnicaComprometida(PermisoLocalEjercicioBase):
    def test_tecnica_comprometida_en_ultima_sesion_bloquea(self):
        entreno = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno, nombre='Press Banca')
        ej_base = self._ejercicio_base('Press Banca')
        self._serie(entreno, ej_base, tecnica_calidad='comprometida')

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertFalse(resultado['puede_subir'])
        self.assertEqual(resultado['motivo'], 'tecnica_comprometida')


class TestPermisoLocal04_TecnicaBuenaOAceptable(PermisoLocalEjercicioBase):
    def test_tecnica_buena_o_aceptable_permite_subir(self):
        entreno = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno, nombre='Press Banca')
        ej_base = self._ejercicio_base('Press Banca')
        self._serie(entreno, ej_base, tecnica_calidad='buena', serie_numero=1)
        self._serie(entreno, ej_base, tecnica_calidad='aceptable', serie_numero=2)

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertTrue(resultado['puede_subir'])
        self.assertIsNone(resultado['motivo'])


class TestPermisoLocal05_MolestiaReciente(PermisoLocalEjercicioBase):
    def test_molestia_en_penultima_sesion_bloquea(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca', molestia_reportada=True)
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca')

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertFalse(resultado['puede_subir'])
        self.assertEqual(resultado['motivo'], 'molestia_reciente')


class TestPermisoLocal06_SinMolestia(PermisoLocalEjercicioBase):
    def test_sin_molestia_en_ultimas_dos_permite_subir(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca')
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca')

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertTrue(resultado['puede_subir'])


class TestPermisoLocal07_FalloRepetidoNoControlado(PermisoLocalEjercicioBase):
    def test_fallo_repetido_no_controlado_bloquea(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca', fallo_muscular=True, rir=1)
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca', fallo_muscular=True, rir=2)

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertFalse(resultado['puede_subir'])
        self.assertEqual(resultado['motivo'], 'fallo_repetido_no_controlado')


class TestPermisoLocal08_FalloControladoRirCero(PermisoLocalEjercicioBase):
    def test_fallo_con_rir_cero_se_considera_controlado(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca', fallo_muscular=True, rir=0)
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca', fallo_muscular=True, rir=0)

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertTrue(resultado['puede_subir'])


class TestPermisoLocal09_FalloConTopeMaquina(PermisoLocalEjercicioBase):
    def test_fallo_con_tope_maquina_no_bloquea(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca', fallo_muscular=True, rir=1, es_tope_maquina=True)
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca', fallo_muscular=True, rir=1, es_tope_maquina=True)

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertTrue(resultado['puede_subir'])


class TestPermisoLocal10_SoloUltimaConFalloNoEsRepetido(PermisoLocalEjercicioBase):
    def test_fallo_solo_en_ultima_sesion_no_bloquea(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca', fallo_muscular=False)
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca', fallo_muscular=True, rir=1)

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertTrue(resultado['puede_subir'])


class TestPermisoLocal11_PrioridadDeloadSobreTecnica(PermisoLocalEjercicioBase):
    def test_deload_gana_sobre_tecnica_comprometida(self):
        entreno = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno, nombre='Press Banca')
        ej_base = self._ejercicio_base('Press Banca')
        self._serie(entreno, ej_base, tecnica_calidad='comprometida')

        with patch(_DELOAD_PATH, return_value=True):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertEqual(resultado['motivo'], 'deload')


class TestPermisoLocal12_PrioridadFalloSobreTecnica(PermisoLocalEjercicioBase):
    def test_fallo_repetido_gana_sobre_tecnica_comprometida(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca', fallo_muscular=True, rir=1)
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca', fallo_muscular=True, rir=2)
        ej_base = self._ejercicio_base('Press Banca')
        self._serie(entreno2, ej_base, tecnica_calidad='comprometida')

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertEqual(resultado['motivo'], 'fallo_repetido_no_controlado')


class TestPermisoLocal13_PrioridadTecnicaSobreMolestia(PermisoLocalEjercicioBase):
    def test_tecnica_comprometida_gana_sobre_molestia_reciente(self):
        entreno = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno, nombre='Press Banca', molestia_reportada=True)
        ej_base = self._ejercicio_base('Press Banca')
        self._serie(entreno, ej_base, tecnica_calidad='comprometida')

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertEqual(resultado['motivo'], 'tecnica_comprometida')


class TestPermisoLocal14_HistorialLimpio(PermisoLocalEjercicioBase):
    def test_historial_limpio_permite_subir_sin_motivo(self):
        entreno1 = self._entreno(date(2026, 6, 4))
        self._ejercicio_realizado(entreno1, nombre='Press Banca')
        entreno2 = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno2, nombre='Press Banca')

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertEqual(resultado, {'puede_subir': True, 'motivo': None, 'mensaje': None})


class TestPermisoLocal15_TecnicaEjercicioDistintoNoBloquea(PermisoLocalEjercicioBase):
    """
    Caso simple sin prefijo compartido: técnica comprometida registrada para
    OTRO ejercicio ("Sentadilla Frontal") no debe bloquear "Press Banca" cuyo
    propio historial está limpio.

    Límite conocido (no cubierto por este test): si el otro ejercicio
    comparte prefijo con el evaluado (p.ej. "Press Banca" vs "Press Banca
    Inclinado"), el icontains=nombre[:18] puede cruzar ambos — ver TODO en
    evaluar_permiso_local_ejercicio.
    """
    def test_tecnica_comprometida_en_otro_ejercicio_no_bloquea(self):
        entreno_pb = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno_pb, nombre='Press Banca')

        entreno_sent = self._entreno(date(2026, 6, 9))
        self._ejercicio_realizado(entreno_sent, nombre='Sentadilla Frontal')
        ej_base_sent = self._ejercicio_base('Sentadilla Frontal')
        self._serie(entreno_sent, ej_base_sent, tecnica_calidad='comprometida')

        with patch(_DELOAD_PATH, return_value=False):
            resultado = evaluar_permiso_local_ejercicio(self.cliente, 'Press Banca', self.hoy)

        self.assertTrue(resultado['puede_subir'])
        self.assertIsNone(resultado['motivo'])


# ── Sección B: integración con _aplicar_progresion_ejecutiva ────────────────

class TestCase11_FrenoLocalTecnicaPosponeSubirPeso(ProgresionEjecutivaBase):
    def test_freno_local_tecnica_pospone_subir_peso(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0,
                                   motivo='RPE bajo dos sesiones seguidas — sube carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        permiso_local = {
            'puede_subir': False, 'motivo': 'tecnica_comprometida',
            'mensaje': 'Técnica comprometida en la última sesión — prioriza forma antes de subir peso.',
        }

        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), \
                patch(_DELOAD_PATH, return_value=False), \
                patch(_PERMISO_LOCAL_PATH, return_value=permiso_local):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_pospuesta'))
        self.assertFalse(ej.get('progresion_aplicada', False))
        self.assertEqual(ej['peso_kg'], 80.0)
        self.assertEqual(ej['progresion_motivo'], permiso_local['mensaje'])
        self.assertEqual(ej['progresion_motivo_local'], 'tecnica_comprometida')
        self.assertTrue(any(c['tipo'] == 'progresion_pospuesta' for c in cambios))

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'pospuesta')
        self.assertEqual(log.motivo_postergacion, permiso_local['mensaje'])


class TestCase12_FrenoLocalMolestiaPosponeSubirPeso(ProgresionEjecutivaBase):
    def test_freno_local_molestia_pospone_subir_peso(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0,
                                   motivo='RPE bajo dos sesiones seguidas — sube carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        permiso_local = {
            'puede_subir': False, 'motivo': 'molestia_reciente',
            'mensaje': 'Molestia reportada en las últimas sesiones de este ejercicio — no se sube peso por seguridad.',
        }

        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), \
                patch(_DELOAD_PATH, return_value=False), \
                patch(_PERMISO_LOCAL_PATH, return_value=permiso_local):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_pospuesta'))
        self.assertEqual(ej['peso_kg'], 80.0)
        self.assertEqual(ej['progresion_motivo'], permiso_local['mensaje'])
        self.assertEqual(ej['progresion_motivo_local'], 'molestia_reciente')

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'pospuesta')
        self.assertEqual(log.motivo_postergacion, permiso_local['mensaje'])


class TestCase13_FrenoLocalFalloRepetidoPosponeSubirPeso(ProgresionEjecutivaBase):
    def test_freno_local_fallo_repetido_pospone_subir_peso(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0,
                                   motivo='RPE bajo dos sesiones seguidas — sube carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        permiso_local = {
            'puede_subir': False, 'motivo': 'fallo_repetido_no_controlado',
            'mensaje': 'Fallo muscular sin control aparente en las últimas 2 sesiones — consolidar antes de subir.',
        }

        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), \
                patch(_DELOAD_PATH, return_value=False), \
                patch(_PERMISO_LOCAL_PATH, return_value=permiso_local):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_pospuesta'))
        self.assertEqual(ej['peso_kg'], 80.0)
        self.assertEqual(ej['progresion_motivo'], permiso_local['mensaje'])
        self.assertEqual(ej['progresion_motivo_local'], 'fallo_repetido_no_controlado')

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'pospuesta')
        self.assertEqual(log.motivo_postergacion, permiso_local['mensaje'])


class TestCase14_DeloadBloqueaSubirPesoMismoEjercicio(ProgresionEjecutivaBase):
    """Regresión del Gap 2: deload activo no debe permitir 'sube peso + descarga'
    en el mismo ejercicio dentro del mismo ciclo."""

    def test_deload_pospone_subir_peso_y_reduce_series_rpe(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0,
                                   motivo='RPE bajo dos sesiones seguidas — sube carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]
        ejercicios[0]['series'] = 4
        ejercicios[0]['rpe_objetivo'] = 9

        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), \
                patch(_DELOAD_PATH, return_value=True):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]

        # subir_peso pospuesto por el freno local de deload
        self.assertTrue(ej.get('progresion_pospuesta'))
        self.assertFalse(ej.get('progresion_aplicada', False))
        self.assertEqual(ej.get('progresion_motivo_local'), 'deload')
        self.assertEqual(ej['peso_kg'], 80.0)  # no sube

        # el bloque de deload estructural sigue aplicando igual
        self.assertTrue(ej.get('deload'))
        self.assertEqual(ej['series'], 3)
        self.assertLessEqual(ej['rpe_objetivo'], 7)

        self.assertTrue(any(c['tipo'] == 'progresion_pospuesta' for c in cambios))
        self.assertTrue(any(c['tipo'] == 'deload' for c in cambios))

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'pospuesta')


class TestCase15_FrenoLocalNoAfectaBajarPeso(ProgresionEjecutivaBase):
    def test_freno_local_bloqueado_no_afecta_bajar_peso(self):
        log = self._log_pendiente('bajar_peso', peso_anterior=80.0, valor_cambio=10.0,
                                   motivo='RPE muy alto sin fallo — reduce carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        permiso_local_bloqueado = {
            'puede_subir': False, 'motivo': 'deload',
            'mensaje': 'Semana de descarga activa — no se sube peso en este ejercicio.',
        }

        with patch(_DELOAD_PATH, return_value=False), \
                patch(_PERMISO_LOCAL_PATH, return_value=permiso_local_bloqueado):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertEqual(ej['progresion_accion'], 'bajar_peso')
        self.assertFalse(ej.get('progresion_pospuesta', False))
        self.assertEqual(ej['peso_kg'], 72.5)

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'aplicada')
        self.assertIsNone(log.motivo_postergacion)


class TestCase16_HistorialLimpioSubirPesoSeAplica(ProgresionEjecutivaBase):
    def test_historial_limpio_subir_peso_se_aplica_con_freno_local_real(self):
        log = self._log_pendiente('subir_peso', peso_anterior=80.0, valor_cambio=5.0,
                                   motivo='RPE bajo dos sesiones seguidas — sube carga.')
        ejercicios = [self._ejercicio(peso_kg=80.0)]

        with patch(_PERMISO_PATH, return_value=PERMISO_PERMITIDO), \
                patch(_DELOAD_PATH, return_value=False):
            ejercicios_mod, cambios = aplicar_plan_dinamico(self.cliente, ejercicios, self.hoy)

        ej = ejercicios_mod[0]
        self.assertTrue(ej.get('progresion_aplicada'))
        self.assertEqual(ej['progresion_accion'], 'subir_peso')
        self.assertEqual(ej['peso_kg'], 85.0)
        self.assertTrue(any(c['tipo'] == 'progresion_aplicada' for c in cambios))

        log.refresh_from_db()
        self.assertEqual(log.estado_aplicacion, 'aplicada')
        self.assertIsNone(log.motivo_postergacion)


# ── Contrato visual: progresión no se atribuye a JOI ─────────────────────────

class TestCaseVisual_ContratoBriefing(TestCase):
    def test_template_tiene_ramas_progresion(self):
        with open('entrenos/templates/entrenos/briefing_entrenamiento.html', encoding='utf-8') as f:
            tpl = f.read()
        self.assertIn("cambio.tipo == 'progresion_aplicada'", tpl)
        self.assertIn("cambio.tipo == 'progresion_pospuesta'", tpl)

    def test_copy_progresion_no_menciona_joi(self):
        with open('entrenos/templates/entrenos/briefing_entrenamiento.html', encoding='utf-8') as f:
            tpl = f.read()
        inicio = tpl.index("cambio.tipo == 'progresion_aplicada'")
        fin = tpl.index('{% endif %}', inicio)
        bloque = tpl[inicio:fin]
        self.assertNotIn('JOI', bloque)
        self.assertNotIn('joi', bloque)
