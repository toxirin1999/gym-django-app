"""
Phase 1.5 — Validation suite for SesionProgramada logic.

Covers the 10-case checklist:
1. No pending + training today → tipo=programada_hoy
2. No pending + rest today → tipo=descanso
3. Pending visible + "Hoy no puedo" → all postponed to tomorrow
4. Postponed pending + same day → not visible
5. Postponed pending + next day → visible again
6. Pending completed from flow → closed with fecha_realizada and FK
7. Pending skipped → gone from active flow
8. Previous week + current week → previous omitted
9. Cache: complete/skip/postpone reflected immediately
10. proximo_entrenamiento backward compatibility
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.analisis_semanal_service import bloque_semanal_para_joi
from entrenos.services.sesion_recomendada import (
    calcular_bloque_esencial,
    cerrar_sesion_programada,
    inferir_prioridad_sesion,
    obtener_sesion_recomendada_hoy,
    posponer_entrenamiento_hoy,
    saltar_sesion_programada,
    sincronizar_pendientes_recientes,
    _aplicar_contexto,
    _reconciliar_pendientes_semana,
)
from rutinas.models import Rutina


TRAINING_DAY = {
    'rutina_nombre': 'Día 1 - Hipertrofia',
    'nombre_rutina': 'Día 1 - Hipertrofia',
    'ejercicios': [
        {
            'nombre': 'Sentadilla con Barra',
            'grupo_muscular': 'cuadriceps',
            'series': 4,
            'repeticiones': '6-8',
            'peso_kg': 80,
            'tipo_ejercicio': 'compuesto_principal',
        }
    ],
    'objetivo': 'Hipertrofia',
    'bloque': 'Hipertrofia Fase 1',
    'dia': 1,
    'semana_nombre': 'Semana 3',
}

TRAINING_DAY_NORMAL = {
    'rutina_nombre': 'Día 3 - Accesorios',
    'nombre_rutina': 'Día 3 - Accesorios',
    'ejercicios': [
        {
            'nombre': 'Curl de Bíceps',
            'grupo_muscular': 'biceps',
            'series': 3,
            'repeticiones': '10-12',
            'peso_kg': 15,
            'tipo_ejercicio': 'aislamiento',
        }
    ],
    'objetivo': 'Hipertrofia',
    'bloque': 'Hipertrofia Fase 1',
    'dia': 3,
    'semana_nombre': 'Semana 3',
}

REST_DAY = {
    'rutina_nombre': 'Día de Descanso',
    'ejercicios': [],
    'objetivo': 'Descanso',
}


def make_mock_planificador(day_map: dict):
    """
    Returns a mock planificador whose generar_entrenamiento_para_fecha
    returns values from day_map keyed by date, defaulting to REST_DAY.
    """
    mock = MagicMock()
    mock.generar_entrenamiento_para_fecha.side_effect = lambda d: day_map.get(d, REST_DAY)
    return mock


class SesionProgramadaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_sp', password='x')
        # A post_save signal may auto-create Cliente. Use get_or_create to be safe.
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={
                'nombre': 'Tester',
                'dias_disponibles': 4,
                'objetivo_principal': 'hipertrofia',
            },
        )
        self.cliente.dias_disponibles = 4
        self.cliente.objetivo_principal = 'hipertrofia'
        self.cliente.save(update_fields=['dias_disponibles', 'objetivo_principal'])
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_rutina')
        self.hoy = date(2026, 5, 20)  # Fixed date for reproducibility
        cache.clear()  # Prevent file-based cache leaking between tests

    def tearDown(self):
        cache.clear()


class TestCase1_SinPendientesEntrenamientoHoy(SesionProgramadaBase):
    """Case 1: No pending sessions, today is a training day → tipo=programada_hoy."""

    def test_sin_pendientes_entrenamiento_hoy(self):
        day_map = {self.hoy: TRAINING_DAY}
        mock_plan = make_mock_planificador(day_map)

        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        self.assertEqual(decision['tipo'], 'programada_hoy')
        self.assertEqual(decision['estado'], 'entrenar')
        self.assertIsNone(decision['sesion_programada'])
        self.assertIsNotNone(decision['entrenamiento'])
        self.assertTrue(decision['entrenamiento']['ejercicios'])


class TestCase2_SinPendientesDescansoHoy(SesionProgramadaBase):
    """Case 2: No pending sessions, today is a rest day → tipo=descanso."""

    def test_sin_pendientes_descanso_hoy(self):
        # All days are rest days
        mock_plan = make_mock_planificador({})

        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        self.assertEqual(decision['tipo'], 'descanso')
        self.assertEqual(decision['estado'], 'descanso')
        self.assertIsNone(decision['sesion_programada'])


class TestCase3_HoyNoPuedoPosponeTodas(SesionProgramadaBase):
    """Case 3: "Hoy no puedo" postpones ALL visible pending sessions to tomorrow."""

    def setUp(self):
        super().setUp()
        # Create 3 pending sessions for this week
        for offset in range(3):
            SesionProgramada.objects.create(
                cliente=self.cliente,
                fecha_prevista=self.hoy - timedelta(days=offset + 1),
                estado=SesionProgramada.ESTADO_PENDIENTE,
                nombre_sesion=f'Sesión {offset + 1}',
            )

    def test_posponer_entrenamiento_hoy_congela_todas(self):
        visibles_antes = SesionProgramada.objects.filter(
            cliente=self.cliente,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            pospuesta_hasta__isnull=True,
        ).count()
        self.assertEqual(visibles_antes, 3)

        posponer_entrenamiento_hoy(self.cliente, self.hoy)

        manana = self.hoy + timedelta(days=1)
        pospuestas = SesionProgramada.objects.filter(
            cliente=self.cliente,
            pospuesta_hasta=manana,
        ).count()
        self.assertEqual(pospuestas, 3)

    def test_posponer_oculta_pendientes_hoy(self):
        from django.db.models import Q
        posponer_entrenamiento_hoy(self.cliente, self.hoy)

        visibles = SesionProgramada.objects.filter(
            cliente=self.cliente,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        ).filter(
            Q(pospuesta_hasta__isnull=True) | Q(pospuesta_hasta__lte=self.hoy)
        ).count()
        self.assertEqual(visibles, 0)


class TestCase4_PospuestaNoAparece(SesionProgramadaBase):
    """Case 4: A postponed session does not appear on the postponed date."""

    def setUp(self):
        super().setUp()
        manana = self.hoy + timedelta(days=1)
        self.sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=1),
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Sesión pospuesta',
            pospuesta_hasta=manana,
        )

    def test_pospuesta_no_aparece_hoy(self):
        mock_plan = make_mock_planificador({})  # rest day today

        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        self.assertEqual(decision['tipo'], 'descanso')
        self.assertIsNone(decision['sesion_programada'])


class TestCase5_PospuestaAparececeMañana(SesionProgramadaBase):
    """Case 5: A postponed session becomes visible the next day."""

    def setUp(self):
        super().setUp()
        manana = self.hoy + timedelta(days=1)
        self.sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=1),
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Sesión recuperada',
            pospuesta_hasta=manana,
        )

    def test_pospuesta_aparece_mañana(self):
        manana = self.hoy + timedelta(days=1)
        training_manana = {manana: TRAINING_DAY}
        mock_plan = make_mock_planificador(training_manana)

        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, manana)

        self.assertEqual(decision['tipo'], 'pendiente')
        self.assertEqual(decision['sesion_programada'].id, self.sp.id)


class TestCase6_CompletarPendienteCierraCorrectamente(SesionProgramadaBase):
    """Case 6: Completing a pending session closes it with fecha_realizada and FK."""

    def setUp(self):
        super().setUp()
        self.sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=4),
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Día 1 - Hipertrofia',
        )
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=self.hoy,
        )

    def test_cerrar_sesion_programada(self):
        cerrar_sesion_programada(self.sp.id, self.entreno)

        self.sp.refresh_from_db()
        self.assertEqual(self.sp.estado, SesionProgramada.ESTADO_COMPLETADA)
        self.assertEqual(self.sp.fecha_realizada, self.hoy)
        self.assertEqual(self.sp.entreno_realizado_id, self.entreno.id)
        self.assertEqual(self.sp.fecha_prevista, self.hoy - timedelta(days=4))

    def test_cerrar_sesion_no_afecta_otras_pendientes(self):
        otra = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=2),
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Día 2',
        )
        cerrar_sesion_programada(self.sp.id, self.entreno)

        otra.refresh_from_db()
        self.assertEqual(otra.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_cerrar_sesion_inexistente_no_explota(self):
        cerrar_sesion_programada(99999, self.entreno)  # must not raise


class TestCase7_SaltarSesion(SesionProgramadaBase):
    """Case 7: Skipped session disappears from active flow definitively."""

    def setUp(self):
        super().setUp()
        self.sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=2),
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Sesión a saltar',
        )

    def test_saltar_cambia_estado(self):
        saltar_sesion_programada(self.sp)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.estado, SesionProgramada.ESTADO_SALTADA_USUARIO)

    def test_saltada_no_aparece_como_pendiente(self):
        saltar_sesion_programada(self.sp)
        mock_plan = make_mock_planificador({})

        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        self.assertEqual(decision['tipo'], 'descanso')
        self.assertIsNone(decision['sesion_programada'])


class TestCase8_ReconciliacionSemanal(SesionProgramadaBase):
    """Case 8: Previous-week pending is omitted when current-week sessions exist."""

    def setUp(self):
        super().setUp()
        # Week 20: 2026-05-11 to 2026-05-17
        # Week 21: 2026-05-18 to 2026-05-24 (self.hoy = 2026-05-20)
        self.semana_anterior = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 5, 13),  # week 20
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Semana anterior',
        )
        self.semana_actual = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 5, 19),  # week 21
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Semana actual',
        )

    def test_semana_anterior_alta_se_conserva_si_hay_actual(self):
        # Phase 2B: a single alta from a previous week is KEPT alongside current-week sessions.
        # (Only normal-priority previous-week sessions are omitted; a single alta survives.)
        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        self.semana_anterior.refresh_from_db()
        self.semana_actual.refresh_from_db()

        # Both are alta — the previous-week alta survives (Phase 2B rule)
        self.assertEqual(self.semana_anterior.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(self.semana_actual.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_semana_anterior_normal_omitida_si_hay_actual(self):
        # A normal-priority previous-week session IS omitted when current-week sessions exist.
        self.semana_anterior.prioridad = SesionProgramada.PRIORIDAD_NORMAL
        self.semana_anterior.save()

        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        self.semana_anterior.refresh_from_db()
        self.assertEqual(self.semana_anterior.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)

    def test_solo_semana_anterior_conserva_mas_reciente(self):
        self.semana_actual.delete()

        antigua = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=date(2026, 5, 8),   # even older
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Muy antigua',
        )

        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        self.semana_anterior.refresh_from_db()
        antigua.refresh_from_db()

        # Only the most recent old session survives
        self.assertEqual(self.semana_anterior.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(antigua.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)


class TestCase9_CacheNoBloquea(SesionProgramadaBase):
    """Case 9: _marcar_completadas runs without cache so completions are immediate."""

    def test_completar_reflexa_inmediatamente(self):
        sp = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=1),
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='A completar',
        )
        # Simulate an EntrenoRealizado logged for yesterday
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=self.hoy - timedelta(days=1),
        )

        # Prime the cache so the expensive loop is skipped
        from django.core.cache import cache
        cache.set(f'sesion_sync_{self.cliente.id}_{self.hoy.isoformat()}', True, 3600)

        # Even with cache set, _marcar_completadas should close the session
        mock_plan = make_mock_planificador({})
        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        sp.refresh_from_db()
        self.assertEqual(sp.estado, SesionProgramada.ESTADO_COMPLETADA)
        # Since the only pending was closed, decision should be rest
        self.assertEqual(decision['tipo'], 'descanso')

        cache.clear()


class TestCase10_BackwardCompat(SesionProgramadaBase):
    """Case 10: proximo_entrenamiento key is always present and backward-compatible."""

    def test_programada_hoy_tiene_proximo_entrenamiento(self):
        mock_plan = make_mock_planificador({self.hoy: TRAINING_DAY})
        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        ent = decision['entrenamiento']
        self.assertIn('rutina_nombre', ent)
        self.assertIn('nombre_rutina', ent)
        self.assertEqual(ent['rutina_nombre'], ent['nombre_rutina'])
        self.assertIn('ejercicios', ent)

    def test_pendiente_reconstruye_entrenamiento(self):
        ayer = self.hoy - timedelta(days=1)
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=ayer,
            estado=SesionProgramada.ESTADO_PENDIENTE,
            nombre_sesion='Pendiente',
        )
        day_map = {ayer: TRAINING_DAY}
        mock_plan = make_mock_planificador(day_map)
        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        self.assertEqual(decision['tipo'], 'pendiente')
        ent = decision['entrenamiento']
        self.assertIn('rutina_nombre', ent)
        self.assertTrue(ent['ejercicios'])

    def test_descanso_tiene_entrenamiento_none_o_vacio(self):
        mock_plan = make_mock_planificador({})
        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            decision = obtener_sesion_recomendada_hoy(self.cliente, self.hoy)

        self.assertEqual(decision['tipo'], 'descanso')
        ent = decision.get('entrenamiento') or {}
        self.assertFalse(ent.get('ejercicios'))


# ── Phase 2A tests ─────────────────────────────────────────────────────────────

TRAINING_DAY_MIXTO = {
    'rutina_nombre': 'Día 2 - Hipertrofia',
    'nombre_rutina': 'Día 2 - Hipertrofia',
    'ejercicios': [
        {
            'nombre': 'Aperturas con Mancuernas',
            'grupo_muscular': 'pecho',
            'series': 3, 'repeticiones': '12-15', 'peso_kg': 12,
            'tipo_ejercicio': 'aislamiento',
        },
        {
            'nombre': 'Press Banca con Barra',
            'grupo_muscular': 'pecho',
            'series': 4, 'repeticiones': '6-8', 'peso_kg': 80,
            'tipo_ejercicio': 'compuesto_principal',
        },
    ],
    'objetivo': 'Hipertrofia',
    'bloque': 'Hipertrofia Fase 1',
    'dia': 2,
    'semana_nombre': 'Semana 3',
}

TRAINING_DAY_SECUNDARIO = {
    'rutina_nombre': 'Día 3 - Torso secundario',
    'nombre_rutina': 'Día 3 - Torso secundario',
    'ejercicios': [
        {
            'nombre': 'Press Inclinado con Mancuernas',
            'grupo_muscular': 'pecho',
            'series': 3, 'repeticiones': '10-12', 'peso_kg': 22,
            'tipo_ejercicio': 'compuesto_secundario',  # NOT compuesto_principal
        },
    ],
    'objetivo': 'Hipertrofia',
    'bloque': 'Hipertrofia Fase 1',
    'dia': 3,
    'semana_nombre': 'Semana 3',
}


class TestPhase2A_InferirPrioridad(SesionProgramadaBase):
    """Phase 2A: inferir_prioridad_sesion assigns alta/normal correctly."""

    def test_compuesto_principal_grupo_grande_es_alta(self):
        prioridad = inferir_prioridad_sesion(TRAINING_DAY)
        self.assertEqual(prioridad, SesionProgramada.PRIORIDAD_ALTA)

    def test_aislamiento_es_normal(self):
        prioridad = inferir_prioridad_sesion(TRAINING_DAY_NORMAL)
        self.assertEqual(prioridad, SesionProgramada.PRIORIDAD_NORMAL)

    def test_descanso_es_none(self):
        prioridad = inferir_prioridad_sesion(REST_DAY)
        self.assertIsNone(prioridad)

    def test_compuesto_principal_grupo_pequeno_es_normal(self):
        # Bicep curl even if labeled compuesto_principal is still normal (small group)
        session = {
            'ejercicios': [
                {'nombre': 'Curl de Bíceps', 'grupo_muscular': 'biceps',
                 'tipo_ejercicio': 'compuesto_principal'}
            ]
        }
        prioridad = inferir_prioridad_sesion(session)
        self.assertEqual(prioridad, SesionProgramada.PRIORIDAD_NORMAL)

    def test_sin_tipo_ejercicio_cae_a_normal(self):
        session = {
            'ejercicios': [
                {'nombre': 'Sentadilla', 'grupo_muscular': 'cuadriceps', 'series': 4}
            ]
        }
        prioridad = inferir_prioridad_sesion(session)
        self.assertEqual(prioridad, SesionProgramada.PRIORIDAD_NORMAL)

    def test_compuesto_secundario_grupo_grande_es_normal(self):
        # Only compuesto_principal triggers alta; secondary compounds don't.
        prioridad = inferir_prioridad_sesion(TRAINING_DAY_SECUNDARIO)
        self.assertEqual(prioridad, SesionProgramada.PRIORIDAD_NORMAL)

    def test_session_mixta_es_alta_si_tiene_algun_cp_grande(self):
        # Even if the first exercise is aislamiento, a CP in a large group makes it alta.
        prioridad = inferir_prioridad_sesion(TRAINING_DAY_MIXTO)
        self.assertEqual(prioridad, SesionProgramada.PRIORIDAD_ALTA)

    def test_aislamiento_grupo_grande_es_normal(self):
        # Leg extension = cuadriceps + aislamiento → normal
        session = {
            'ejercicios': [
                {'nombre': 'Extension de Cuadriceps', 'grupo_muscular': 'cuadriceps',
                 'tipo_ejercicio': 'aislamiento'}
            ]
        }
        prioridad = inferir_prioridad_sesion(session)
        self.assertEqual(prioridad, SesionProgramada.PRIORIDAD_NORMAL)


class TestPhase2B_ReconciliacionConPrioridad(SesionProgramadaBase):
    """Phase 2B: reconciliation respects alta/normal priority."""

    def _make_sp(self, fecha, prioridad, estado='pendiente'):
        return SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=fecha,
            estado=estado,
            prioridad=prioridad,
            nombre_sesion='Test',
        )

    def test_normal_anterior_omitida_si_hay_sesion_actual(self):
        # Week 21 (current): one session
        sesion_actual = self._make_sp(date(2026, 5, 19), SesionProgramada.PRIORIDAD_ALTA)
        # Week 20 (previous): one normal session
        sesion_normal_ant = self._make_sp(date(2026, 5, 13), SesionProgramada.PRIORIDAD_NORMAL)

        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        sesion_normal_ant.refresh_from_db()
        sesion_actual.refresh_from_db()
        self.assertEqual(sesion_normal_ant.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertEqual(sesion_actual.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_alta_anterior_se_conserva_si_hay_sesion_actual(self):
        sesion_actual = self._make_sp(date(2026, 5, 19), SesionProgramada.PRIORIDAD_ALTA)
        sesion_alta_ant = self._make_sp(date(2026, 5, 13), SesionProgramada.PRIORIDAD_ALTA)

        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        sesion_alta_ant.refresh_from_db()
        sesion_actual.refresh_from_db()
        self.assertEqual(sesion_alta_ant.estado, SesionProgramada.ESTADO_PENDIENTE)
        self.assertEqual(sesion_actual.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_solo_una_alta_anterior_se_conserva(self):
        sesion_actual = self._make_sp(date(2026, 5, 19), SesionProgramada.PRIORIDAD_ALTA)
        alta_vieja = self._make_sp(date(2026, 5, 8), SesionProgramada.PRIORIDAD_ALTA)
        alta_reciente = self._make_sp(date(2026, 5, 13), SesionProgramada.PRIORIDAD_ALTA)

        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        alta_vieja.refresh_from_db()
        alta_reciente.refresh_from_db()
        self.assertEqual(alta_vieja.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertEqual(alta_reciente.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_solo_normales_anteriores_conserva_mas_reciente(self):
        normal_vieja = self._make_sp(date(2026, 5, 8), SesionProgramada.PRIORIDAD_NORMAL)
        normal_reciente = self._make_sp(date(2026, 5, 13), SesionProgramada.PRIORIDAD_NORMAL)

        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        normal_vieja.refresh_from_db()
        normal_reciente.refresh_from_db()
        self.assertEqual(normal_vieja.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertEqual(normal_reciente.estado, SesionProgramada.ESTADO_PENDIENTE)

    def test_motivo_estado_de_sesion_omitida(self):
        # Omitted sessions must have a non-empty motivo_estado.
        self._make_sp(date(2026, 5, 19), SesionProgramada.PRIORIDAD_ALTA)  # current week
        omitida = self._make_sp(date(2026, 5, 13), SesionProgramada.PRIORIDAD_NORMAL)

        _reconciliar_pendientes_semana(self.cliente, self.hoy)

        omitida.refresh_from_db()
        self.assertEqual(omitida.estado, SesionProgramada.ESTADO_OMITIDA_SISTEMA)
        self.assertTrue(omitida.motivo_estado.strip())

    def test_sincronizar_asigna_prioridad_real(self):
        # Integration: sincronizar_pendientes_recientes uses inferir_prioridad_sesion
        # so the SesionProgramada gets the correct priority, not always ALTA.
        ayer = self.hoy - timedelta(days=1)
        day_map = {ayer: TRAINING_DAY_NORMAL}  # accessory day → prioridad normal
        mock_plan = make_mock_planificador(day_map)

        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            sincronizar_pendientes_recientes(self.cliente, self.hoy)

        sp = SesionProgramada.objects.filter(cliente=self.cliente, fecha_prevista=ayer).first()
        self.assertIsNotNone(sp)
        self.assertEqual(sp.prioridad, SesionProgramada.PRIORIDAD_NORMAL)

    def test_sincronizar_alta_para_sesion_principal(self):
        ayer = self.hoy - timedelta(days=1)
        day_map = {ayer: TRAINING_DAY}  # main compound day → prioridad alta
        mock_plan = make_mock_planificador(day_map)

        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=mock_plan):
            sincronizar_pendientes_recientes(self.cliente, self.hoy)

        sp = SesionProgramada.objects.filter(cliente=self.cliente, fecha_prevista=ayer).first()
        self.assertIsNotNone(sp)
        self.assertEqual(sp.prioridad, SesionProgramada.PRIORIDAD_ALTA)


# ── Phase 3 tests ──────────────────────────────────────────────────────────────

class TestPhase4D_BloqueEsencial(SesionProgramadaBase):
    """Phase 4D: calcular_bloque_esencial reads principal vs optional breakdown."""

    def _make_entreno(self, modo_reducido=True):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=self.hoy,
            modo_reducido=modo_reducido,
        )
        return entreno

    def _add_ejercicio(self, entreno, es_bloque_principal):
        from entrenos.models import EjercicioRealizado
        return EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Test Ej',
            series=3, repeticiones=8, peso_kg=50,
            es_bloque_principal=es_bloque_principal,
        )

    def test_session_normal_returns_none(self):
        entreno = self._make_entreno(modo_reducido=False)
        self._add_ejercicio(entreno, es_bloque_principal=None)
        result = calcular_bloque_esencial(entreno)
        self.assertIsNone(result)

    def test_esencial_sin_clasificacion_returns_none(self):
        entreno = self._make_entreno()
        self._add_ejercicio(entreno, es_bloque_principal=None)
        result = calcular_bloque_esencial(entreno)
        self.assertIsNone(result)

    def test_cuenta_principales_y_opcionales(self):
        entreno = self._make_entreno()
        self._add_ejercicio(entreno, es_bloque_principal=True)
        self._add_ejercicio(entreno, es_bloque_principal=True)
        self._add_ejercicio(entreno, es_bloque_principal=False)
        result = calcular_bloque_esencial(entreno)
        self.assertIsNotNone(result)
        self.assertEqual(result['principales_completados'], 2)
        self.assertEqual(result['opcionales_completados'], 1)

    def test_solo_principales_completo(self):
        entreno = self._make_entreno()
        entreno.principales_planificados = 1
        entreno.save()
        self._add_ejercicio(entreno, es_bloque_principal=True)
        result = calcular_bloque_esencial(entreno)
        self.assertTrue(result['bloque_principal_completo'])

    def test_bloque_incompleto_cuando_faltan_principales(self):
        entreno = self._make_entreno()
        entreno.principales_planificados = 3  # 3 planificados
        entreno.save()
        self._add_ejercicio(entreno, es_bloque_principal=True)  # solo 1 completado
        result = calcular_bloque_esencial(entreno)
        self.assertFalse(result['bloque_principal_completo'])
        self.assertEqual(result['principales_completados'], 1)
        self.assertEqual(result['principales_planificados'], 3)
        self.assertEqual(result['porcentaje_principal'], 33)

    def test_sin_principales_no_completo(self):
        entreno = self._make_entreno()
        self._add_ejercicio(entreno, es_bloque_principal=False)
        result = calcular_bloque_esencial(entreno)
        self.assertFalse(result['bloque_principal_completo'])

    def test_porcentaje_opcional_correcto(self):
        entreno = self._make_entreno()
        entreno.opcionales_planificados = 4
        entreno.save()
        self._add_ejercicio(entreno, es_bloque_principal=True)
        self._add_ejercicio(entreno, es_bloque_principal=False)
        result = calcular_bloque_esencial(entreno)
        self.assertEqual(result['opcionales_planificados'], 4)
        self.assertEqual(result['opcionales_completados'], 1)
        self.assertEqual(result['porcentaje_opcional'], 25)


class TestPhase5_AnalisisSemanal(SesionProgramadaBase):
    """Phase 5: analizar_semana_entrenamiento returns correct summary and narrative."""

    def setUp(self):
        super().setUp()
        from entrenos.services.analisis_semanal_service import analizar_semana_entrenamiento
        self._analizar = analizar_semana_entrenamiento

    def _make_entreno(self, fecha, modo_reducido=False, principales_plan=0, opcionales_plan=0):
        e = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            modo_reducido=modo_reducido,
            principales_planificados=principales_plan or None,
            opcionales_planificados=opcionales_plan or None,
        )
        return e

    def _add_ej(self, entreno, es_principal):
        from entrenos.models import EjercicioRealizado
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='EJ', series=3,
            repeticiones=8, peso_kg=50, es_bloque_principal=es_principal,
        )

    def test_sin_datos_hay_datos_false(self):
        result = self._analizar(self.cliente, self.hoy)
        self.assertFalse(result['hay_datos'])

    def test_sesion_normal_contada(self):
        self._make_entreno(self.hoy)
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['sesiones_completadas'], 1)
        self.assertEqual(result['sesiones_normales'], 1)
        self.assertEqual(result['sesiones_esenciales'], 0)
        self.assertTrue(result['hay_datos'])

    def test_sesion_esencial_contada(self):
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=2, opcionales_plan=2)
        self._add_ej(e, True)
        self._add_ej(e, True)
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['sesiones_esenciales'], 1)
        self.assertEqual(result['bloques_principales_completos'], 1)
        self.assertEqual(result['bloques_principales_parciales'], 0)

    def test_bloque_parcial_detectado(self):
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=3)
        self._add_ej(e, True)  # only 1 of 3 completed
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['bloques_principales_parciales'], 1)
        self.assertEqual(result['bloques_principales_completos'], 0)

    def test_saltadas_contadas(self):
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=1),
            estado=SesionProgramada.ESTADO_SALTADA_USUARIO,
        )
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['sesiones_saltadas'], 1)
        self.assertTrue(result['hay_datos'])

    def test_lectura_sin_datos(self):
        result = self._analizar(self.cliente, self.hoy)
        self.assertIn('no hay', result['lectura_textual'].lower())

    def test_lectura_bloque_parcial_contiene_advertencia(self):
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=3)
        self._add_ej(e, True)
        result = self._analizar(self.cliente, self.hoy)
        self.assertIn('carga', result['lectura_textual'].lower())

    def test_lectura_todo_esencial_y_completo(self):
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=1)
        self._add_ej(e, True)
        result = self._analizar(self.cliente, self.hoy)
        self.assertIn('continuidad', result['lectura_textual'].lower())

    def test_lectura_sesion_normal_completa(self):
        self._make_entreno(self.hoy)
        result = self._analizar(self.cliente, self.hoy)
        self.assertIn('sólida', result['lectura_textual'].lower())

    # ── Phase 5.1 — Checklist coverage ────────────────────────────────────────

    def test_lectura_mixta_detecta_bloques_mantenidos(self):
        # Normal + esencial complete → mixed week, principals held
        self._make_entreno(self.hoy - timedelta(days=1))  # normal
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=1)
        self._add_ej(e, True)
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['sesiones_normales'], 1)
        self.assertEqual(result['sesiones_esenciales'], 1)
        self.assertIn('mixta', result['lectura_textual'].lower())

    def test_alta_completitud_opcional_da_margen(self):
        # Normal session — pct_opcional_medio high → "margen"
        # We need a modo_reducido session with high optional pct to trigger this
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=1, opcionales_plan=1)
        self._add_ej(e, True)   # principal done
        self._add_ej(e, False)  # optional done
        result = self._analizar(self.cliente, self.hoy)
        # All esencial path → continuidad (margen path requires normal sessions too)
        self.assertTrue(result['hay_datos'])
        self.assertEqual(result['porcentaje_opcional_medio'], 100)

    def test_omitidas_contadas_sin_penalizar(self):
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.hoy - timedelta(days=2),
            estado=SesionProgramada.ESTADO_OMITIDA_SISTEMA,
        )
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['sesiones_omitidas'], 1)
        self.assertTrue(result['hay_datos'])
        # Omissions don't count as completions
        self.assertEqual(result['sesiones_completadas'], 0)

    def test_sesiones_otra_semana_no_contaminan(self):
        # Session from two weeks ago should not appear in this week's analysis
        self._make_entreno(self.hoy - timedelta(days=15))
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['sesiones_completadas'], 0)
        self.assertFalse(result['hay_datos'])

    def test_lectura_no_contiene_terminos_culpa(self):
        # Narrative must not use blame language
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=3)
        self._add_ej(e, True)  # partial — triggers warning case
        result = self._analizar(self.cliente, self.hoy)
        texto = result['lectura_textual'].lower()
        for termino in ['fallaste', 'incumpliste', 'fracaso', 'mal', 'debe']:
            self.assertNotIn(termino, texto, msg=f"Término de culpa encontrado: '{termino}'")

    def test_lectura_alerta_es_suave_no_fallo(self):
        # Even the warning case should suggest "observar", not "failed"
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=3)
        self._add_ej(e, True)
        result = self._analizar(self.cliente, self.hoy)
        texto = result['lectura_textual'].lower()
        self.assertIn('observar', texto)

    def test_historico_normal_sin_modo_reducido_no_rompe(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy,
        )
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['sesiones_completadas'], 1)
        self.assertEqual(result['sesiones_esenciales'], 0)
        self.assertTrue(result['hay_datos'])

    # ── Phase 6 — Semantic state labels ───────────────────────────────────────

    def test_estado_sin_datos(self):
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['estado_semana'], 'sin_datos')
        self.assertEqual(result['continuidad'], 'baja')
        self.assertEqual(result['suficiencia'], 'parcial')

    def test_estado_carga_alta_cuando_bloque_parcial(self):
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=3)
        self._add_ej(e, True)  # 1 of 3
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['estado_semana'], 'carga_alta')
        self.assertEqual(result['suficiencia'], 'parcial')

    def test_estado_solida_cuando_normal(self):
        self._make_entreno(self.hoy - timedelta(days=2))
        self._make_entreno(self.hoy - timedelta(days=1))
        self._make_entreno(self.hoy)
        result = self._analizar(self.cliente, self.hoy)
        self.assertEqual(result['estado_semana'], 'solida')
        self.assertEqual(result['continuidad'], 'alta')
        self.assertEqual(result['suficiencia'], 'completa')

    def test_estado_margen_extra_cuando_opcional_alto(self):
        self._make_entreno(self.hoy - timedelta(days=1))  # normal
        e = self._make_entreno(self.hoy, modo_reducido=True, principales_plan=1, opcionales_plan=1)
        self._add_ej(e, True)
        self._add_ej(e, False)
        result = self._analizar(self.cliente, self.hoy)
        # Has normal session + esencial with 100% opcional → margen_extra expected
        self.assertIn(result['margen'], ('alto', 'medio'))

    def test_estado_semana_keys_siempre_presentes(self):
        result = self._analizar(self.cliente, self.hoy)
        for key in ('estado_semana', 'continuidad', 'suficiencia', 'margen'):
            self.assertIn(key, result, msg=f"Missing key: {key}")

    # ── Phase 6.1 — bloque_semanal_para_joi ───────────────────────────────────

    def test_bloque_joi_none_sin_datos(self):
        result = bloque_semanal_para_joi(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_bloque_joi_string_con_sesion(self):
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy
        )
        result = bloque_semanal_para_joi(self.cliente, self.hoy)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 20)

    def test_bloque_joi_no_contiene_fallos(self):
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy
        )
        result = bloque_semanal_para_joi(self.cliente, self.hoy)
        texto = (result or '').lower()
        for termino in ['fallaste', 'fracaso', 'mal', 'incumpliste']:
            self.assertNotIn(termino, texto)

    def test_bloque_joi_menciona_sesiones(self):
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy
        )
        result = bloque_semanal_para_joi(self.cliente, self.hoy)
        self.assertIn('sesión', result.lower())

    def test_bloque_joi_carga_alta_texto_apropiado(self):
        e = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy,
            modo_reducido=True, principales_planificados=3,
        )
        from entrenos.models import EjercicioRealizado
        EjercicioRealizado.objects.create(
            entreno=e, nombre_ejercicio='Sq', series=3, repeticiones=8,
            peso_kg=50, es_bloque_principal=True,
        )  # 1/3 → parcial
        result = bloque_semanal_para_joi(self.cliente, self.hoy)
        self.assertIsNotNone(result)
        # Should mention load/principal issue
        self.assertIn('carga', result.lower())


class TestPhase3A_AplicarContexto(SesionProgramadaBase):
    """Phase 3A/3B/3C: _aplicar_contexto enriches the base decision correctly."""

    def _base(self, tipo='programada_hoy'):
        sp = None
        if tipo == 'pendiente':
            sp = SesionProgramada.objects.create(
                cliente=self.cliente,
                fecha_prevista=self.hoy - timedelta(days=1),
                estado=SesionProgramada.ESTADO_PENDIENTE,
                prioridad=SesionProgramada.PRIORIDAD_ALTA,
            )
        return {
            'tipo': tipo,
            'estado': 'entrenar',
            'sesion_programada': sp,
            'entrenamiento': TRAINING_DAY if tipo != 'descanso' else REST_DAY,
            'mensaje': 'base message',
            'causa_principal': None,
            'modo_reducido': False,
        }

    def _ctx(self, **kwargs):
        defaults = {
            'lesion_activa': False, 'lesion_fase': None,
            'futbol_reciente': False, 'energia_baja': False,
            'energia_valor': None, 'readiness_bajo': False, 'readiness_valor': None,
        }
        defaults.update(kwargs)
        return defaults

    def test_sin_contexto_estado_es_entrenar(self):
        d = _aplicar_contexto(self._base(), self._ctx(), self.hoy)
        self.assertEqual(d['estado'], 'entrenar')
        self.assertEqual(d['causa_principal'], 'sesion_hoy')
        self.assertFalse(d['modo_reducido'])

    def test_lesion_activa_da_recuperar(self):
        d = _aplicar_contexto(self._base(), self._ctx(lesion_activa=True, lesion_fase='AGUDA'), self.hoy)
        self.assertEqual(d['estado'], 'recuperar')
        self.assertEqual(d['causa_principal'], 'lesion')

    def test_readiness_bajo_da_recuperar(self):
        d = _aplicar_contexto(self._base(), self._ctx(readiness_bajo=True, readiness_valor=30), self.hoy)
        self.assertEqual(d['estado'], 'recuperar')
        self.assertEqual(d['causa_principal'], 'fatiga_alta')

    def test_energia_baja_da_version_reducida(self):
        d = _aplicar_contexto(self._base(), self._ctx(energia_baja=True, energia_valor=2), self.hoy)
        self.assertEqual(d['estado'], 'version_reducida')
        self.assertEqual(d['causa_principal'], 'energia_baja')
        self.assertTrue(d['modo_reducido'])

    def test_futbol_da_posponer(self):
        d = _aplicar_contexto(self._base(), self._ctx(futbol_reciente=True), self.hoy)
        self.assertEqual(d['estado'], 'posponer')
        self.assertEqual(d['causa_principal'], 'futbol_reciente')

    def test_lesion_tiene_prioridad_sobre_futbol(self):
        d = _aplicar_contexto(
            self._base(),
            self._ctx(lesion_activa=True, futbol_reciente=True),
            self.hoy,
        )
        self.assertEqual(d['estado'], 'recuperar')
        self.assertEqual(d['causa_principal'], 'lesion')

    def test_pendiente_alta_sin_contexto_da_pendiente_prioritaria(self):
        d = _aplicar_contexto(self._base('pendiente'), self._ctx(), self.hoy)
        self.assertEqual(d['estado'], 'entrenar')
        self.assertEqual(d['causa_principal'], 'pendiente_prioritaria')

    def test_descanso_no_cambia_por_contexto(self):
        base = self._base('descanso')
        base['tipo'] = 'descanso'
        d = _aplicar_contexto(base, self._ctx(lesion_activa=True), self.hoy)
        self.assertEqual(d['estado'], 'descanso')
        self.assertEqual(d['causa_principal'], 'descanso_planificado')

    def test_mensaje_refleja_causa(self):
        d = _aplicar_contexto(self._base(), self._ctx(lesion_activa=True), self.hoy)
        self.assertIn('lesión', d['mensaje'].lower())

    def test_contexto_fisico_incluido_en_decision(self):
        ctx = self._ctx(energia_baja=True, energia_valor=2)
        d = _aplicar_contexto(self._base(), ctx, self.hoy)
        self.assertIn('contexto_fisico', d)
        self.assertEqual(d['contexto_fisico']['energia_valor'], 2)
