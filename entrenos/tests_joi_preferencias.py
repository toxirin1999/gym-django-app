"""
Phase 23.1 — Tests for JOI integration with learned plan preferences.

Checklist:
1.  Signal fires generar_mensaje_joi when PreferenciaPlanAprendida is created (ACTIVA).
2.  Signal does NOT fire if estado != ACTIVA (e.g., REVOCADA).
3.  Signal does NOT fire on plain update without estado change.
4.  Signal fires on reactivation (SUSPENDIDA → ACTIVA via update_fields=['estado']).
5.  Lock prevents duplicate JOI messages for same (cliente, tipo) within 24h.
6.  'preferencia_aprendida' trigger exists in _PROMPT_BUILDERS.
7.  _prompt_preferencia_aprendida returns non-empty string for each known tipo.
8.  Prompt does NOT use forbidden absolute words (siempre, nunca, regla obligatoria).
9.  Prompt mentions evidencia_count.
10. construir_contexto includes 'preferencias_plan_activas' when prefs exist.
11. construir_contexto omits key when no active prefs.
12. preferencias_plan_activas has tipo, descripcion, evidencia fields.
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import IntervencionPlan, PreferenciaPlanAprendida
from entrenos.services.preferencias_service import crear_preferencia


class JOIPreferenciasBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_joi23', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestJOI23', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 21)
        cache.clear()

    def tearDown(self):
        cache.clear()


# ── Cases 1-5: Signal behaviour ──────────────────────────────────────────────

class TestCase1_SignalDispara(JOIPreferenciasBase):
    def test_signal_llama_generar_mensaje_joi_al_crear(self):
        with patch('joi.services.generar_mensaje_joi') as mock_joi:
            PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=self.hoy,
                ultima_confirmacion=self.hoy,
                evidencia_count=2,
            )
        mock_joi.assert_called_once()
        args = mock_joi.call_args
        self.assertEqual(args[0][1], 'preferencia_aprendida')


class TestCase2_SignalNoDisparaRevocada(JOIPreferenciasBase):
    def test_signal_no_dispara_si_estado_revocada(self):
        with patch('joi.services.generar_mensaje_joi') as mock_joi:
            PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                estado=PreferenciaPlanAprendida.ESTADO_REVOCADA,
                fecha_inicio=self.hoy,
                ultima_confirmacion=self.hoy,
            )
        mock_joi.assert_not_called()


class TestCase3_SignalNoDisparaUpdateSinEstado(JOIPreferenciasBase):
    def test_signal_no_dispara_en_update_sin_estado(self):
        pref = PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
        )
        cache.clear()  # clear lock set by creation
        with patch('joi.services.generar_mensaje_joi') as mock_joi:
            pref.evidencia_count = 3
            pref.save(update_fields=['evidencia_count'])
        mock_joi.assert_not_called()


class TestCase4_SignalDisparaReactivacion(JOIPreferenciasBase):
    def test_signal_dispara_al_reactivar_suspendida(self):
        pref = PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            estado=PreferenciaPlanAprendida.ESTADO_SUSPENDIDA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
        )
        cache.clear()
        with patch('joi.services.generar_mensaje_joi') as mock_joi:
            pref.estado = PreferenciaPlanAprendida.ESTADO_ACTIVA
            pref.save(update_fields=['estado'])
        mock_joi.assert_called_once()
        self.assertEqual(mock_joi.call_args[0][1], 'preferencia_aprendida')


class TestCase5_LockEvitaDuplicados(JOIPreferenciasBase):
    def test_lock_evita_segundo_mensaje_mismo_tipo(self):
        with patch('joi.services.generar_mensaje_joi') as mock_joi:
            # First creation fires
            PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=self.hoy,
                ultima_confirmacion=self.hoy,
            )
            # Second preference of different type — lock is per (cliente, tipo)
            PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_DIA,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=self.hoy,
                ultima_confirmacion=self.hoy,
            )
        # Both should fire (different lock keys)
        self.assertEqual(mock_joi.call_count, 2)

    def test_lock_bloquea_reactivacion_mismo_tipo_mismo_dia(self):
        with patch('joi.services.generar_mensaje_joi') as mock_joi:
            # First creation fires JOI and sets lock
            pref = PreferenciaPlanAprendida.objects.create(
                cliente=self.cliente,
                tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
                estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
                fecha_inicio=self.hoy,
                ultima_confirmacion=self.hoy,
            )
            # Revoke it (estado changes — but not to ACTIVA, so no JOI)
            pref.estado = PreferenciaPlanAprendida.ESTADO_REVOCADA
            pref.save(update_fields=['estado'])
            # Reactivate: lock is still set → JOI should NOT fire again
            pref.estado = PreferenciaPlanAprendida.ESTADO_ACTIVA
            pref.save(update_fields=['estado'])
        # Only the first creation should have called JOI
        self.assertEqual(mock_joi.call_count, 1)


# ── Cases 6-9: Prompt builder ────────────────────────────────────────────────

class TestCase6_TriggerRegistrado(JOIPreferenciasBase):
    def test_trigger_preferencia_aprendida_en_builders(self):
        from joi.services import _PROMPT_BUILDERS
        self.assertIn('preferencia_aprendida', _PROMPT_BUILDERS)


class TestCase7_PromptNoVacio(JOIPreferenciasBase):
    def test_prompt_retorna_texto_para_cada_tipo(self):
        from joi.services import _PROMPT_BUILDERS
        builder = _PROMPT_BUILDERS['preferencia_aprendida']
        ctx = {}
        for tipo in [
            PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            PreferenciaPlanAprendida.TIPO_EVITAR_DIA,
            PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
            PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA,
        ]:
            datos = {'tipo_preferencia': tipo, 'descripcion': 'prueba', 'evidencia_count': 2}
            resultado = builder(ctx, datos)
            self.assertIsInstance(resultado, str)
            self.assertGreater(len(resultado), 20, msg=f"Prompt vacío para tipo={tipo}")


class TestCase8_PromptNoAbsolutos(JOIPreferenciasBase):
    def test_prompt_no_usa_palabras_absolutas(self):
        from joi.services import _PROMPT_BUILDERS
        builder = _PROMPT_BUILDERS['preferencia_aprendida']
        ctx = {}
        forbidden = ['regla obligatoria', 'nunca cambiará', 'siempre hará', 'imposible']
        for tipo in [PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL]:
            datos = {'tipo_preferencia': tipo, 'descripcion': 'prueba', 'evidencia_count': 2}
            texto = builder(ctx, datos).lower()
            for palabra in forbidden:
                self.assertNotIn(palabra, texto, msg=f"Prompt usa '{palabra}'")


class TestCase9_PromptMencionaEvidencia(JOIPreferenciasBase):
    def test_prompt_menciona_evidencia_count(self):
        from joi.services import _PROMPT_BUILDERS
        builder = _PROMPT_BUILDERS['preferencia_aprendida']
        ctx = {}
        datos = {
            'tipo_preferencia': PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            'descripcion': 'El plan intentará no colocar pierna.',
            'evidencia_count': 3,
        }
        texto = builder(ctx, datos)
        self.assertIn('3', texto)


# ── Cases 10-12: construir_contexto ──────────────────────────────────────────

class TestCase10_ContextoConPreferencias(JOIPreferenciasBase):
    def test_construir_contexto_incluye_preferencias_activas(self):
        PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
            descripcion='El plan intentará no colocar pierna.',
            evidencia_count=2,
        )
        cache.clear()
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        self.assertIn('preferencias_plan_activas', ctx)
        self.assertGreater(len(ctx['preferencias_plan_activas']), 0)


class TestCase11_ContextoSinPreferencias(JOIPreferenciasBase):
    def test_construir_contexto_omite_clave_sin_preferencias(self):
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        # Key should be absent or empty — no active prefs
        prefs = ctx.get('preferencias_plan_activas', [])
        self.assertEqual(prefs, [])


class TestCase12_CamposPreferenciasEnContexto(JOIPreferenciasBase):
    def test_preferencias_activas_tiene_campos_correctos(self):
        PreferenciaPlanAprendida.objects.create(
            cliente=self.cliente,
            tipo=PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
            estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
            fecha_inicio=self.hoy,
            ultima_confirmacion=self.hoy,
            descripcion='El plan tomará como referencia menos días.',
            evidencia_count=2,
        )
        cache.clear()
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        prefs = ctx.get('preferencias_plan_activas', [])
        self.assertEqual(len(prefs), 1)
        p = prefs[0]
        self.assertIn('tipo', p)
        self.assertIn('descripcion', p)
        self.assertIn('evidencia', p)
        self.assertEqual(p['tipo'], PreferenciaPlanAprendida.TIPO_MENOS_DIAS)
