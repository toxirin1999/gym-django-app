"""
Phase 56.14 — Lesión no contamina ejercicios no relacionados.

La penalización de fase (AGUDA/SUB_AGUDA) solo debe reducir volumen
en ejercicios con risk_tags que conflictúan con la zona lesionada.
Un press de hombro no debe verse afectado por una lesión de rodilla.

Estrategia de tests: verificar el contrato matemático entre
volume_modifier y volume_modifier_excl_lesion_fase.

Checklist (4):
1. Con lesión AGUDA, excl_lesion_fase >= volume_modifier (penalty 0.3).
2. Con lesión SUB_AGUDA, excl_lesion_fase >= volume_modifier (penalty 0.15).
3. Sin lesión, ambos modifiers son iguales (phase_penalty = 0).
4. Fatiga global sin lesión reduce vol_mod_excl igual que vol_mod.
"""

from django.test import TestCase


def _derivar_modifier(score):
    """Misma tabla de umbral que bio_context.py."""
    if score >= 0.8:
        return 1.0
    if score >= 0.6:
        return 0.85
    if score >= 0.4:
        return 0.70
    return 0.50


class TestModifierExclLesionFaseMatematica(TestCase):
    """
    Verifica la relación matemática entre el modifier global y el excluyente
    sin necesidad de tocar la base de datos.
    """

    def _simular_readiness(self, helms_component, pain_component, phase_penalty):
        """
        Reproduce el cálculo de bio_context.py para devolver
        (volume_modifier, volume_modifier_excl_lesion_fase).
        """
        raw_score = (helms_component * 0.4) + (pain_component * 0.4) + ((1.0 - phase_penalty) * 0.2)
        score = max(0.0, min(1.0, raw_score))

        raw_excl = (helms_component * 0.4) + (pain_component * 0.4) + 0.2
        score_excl = max(0.0, min(1.0, raw_excl))

        return _derivar_modifier(score), _derivar_modifier(score_excl)

    # ── 1. AGUDA (penalty = 0.3) ──────────────────────────────────────────

    def test_aguda_excl_mayor_o_igual_que_global(self):
        """Con phase_penalty=0.3, excl >= global en todos los rangos."""
        casos = [
            (0.5, 0.5),   # score global ≈ 0.54 → 0.85 | excl ≈ 0.60 → 0.85
            (0.3, 0.3),   # score global ≈ 0.30 → 0.50 | excl ≈ 0.36 → 0.50
            (0.7, 0.7),   # score global ≈ 0.74 → 0.85 | excl ≈ 0.80 → 1.0
            (1.0, 1.0),   # score global ≈ 0.94 → 1.0  | excl = 1.0 → 1.0
        ]
        for helms, pain in casos:
            glob, excl = self._simular_readiness(helms, pain, phase_penalty=0.3)
            self.assertGreaterEqual(
                excl, glob,
                msg=f"AGUDA helms={helms} pain={pain}: excl={excl} debería >= global={glob}"
            )

    def test_aguda_excl_puede_ser_mayor(self):
        """Con score limítrofe, AGUDA puede bajar un umbral completo."""
        # helms=0.7, pain=0.7 → raw_global = 0.7*0.4 + 0.7*0.4 + (0.7)*0.2 = 0.28+0.28+0.14=0.74 → 0.85
        # raw_excl = 0.28+0.28+0.20 = 0.76 → 0.85 (mismo umbral, no cambia aquí)
        # helms=0.65, pain=0.65 → raw_global = 0.65*0.8 + 0.7*0.2 = 0.52+0.14=0.66 → 0.85
        # helms=0.55, pain=0.55 → raw_global = 0.55*0.8 + 0.7*0.2 = 0.44+0.14 = 0.58 → 0.50?
        # Caso donde el penalty AGUDA empuja de 0.85 a 0.70:
        # helms=0.6, pain=0.6 → raw_global = 0.6*0.8 + 0.7*0.2 = 0.48+0.14=0.62 → 0.85
        # helms=0.5, pain=0.4 → raw_global = 0.5*0.4+0.4*0.4+0.7*0.2 = 0.2+0.16+0.14=0.50 → 0.70
        # raw_excl = 0.2+0.16+0.20 = 0.56 → 0.50?? No, 0.56 >= 0.4 → 0.70 también
        # helms=0.4, pain=0.5 → raw_global = 0.4*0.4+0.5*0.4+0.7*0.2 = 0.16+0.20+0.14=0.50 → 0.70
        # raw_excl = 0.16+0.20+0.20 = 0.56 → 0.70 igual
        # helms=0.3, pain=0.3 → raw_global = 0.12+0.12+0.14=0.38 → 0.50
        # raw_excl = 0.12+0.12+0.20=0.44 → 0.70 ← AQUÍ SÍ CAMBIA
        glob, excl = self._simular_readiness(0.3, 0.3, phase_penalty=0.3)
        self.assertGreaterEqual(excl, glob)
        # En este caso 0.44 >= 0.4 → 0.70, 0.38 < 0.4 → 0.50: excl (0.70) > glob (0.50)
        self.assertGreater(excl, glob,
                           msg="Con helms=pain=0.3 y AGUDA, excl debe ser mayor que global")

    # ── 2. SUB_AGUDA (penalty = 0.15) ────────────────────────────────────

    def test_sub_aguda_excl_mayor_o_igual_que_global(self):
        """Con phase_penalty=0.15, excl >= global."""
        casos = [(0.5, 0.5), (0.3, 0.3), (0.7, 0.7), (1.0, 1.0)]
        for helms, pain in casos:
            glob, excl = self._simular_readiness(helms, pain, phase_penalty=0.15)
            self.assertGreaterEqual(excl, glob,
                                    msg=f"SUB_AGUDA helms={helms}: excl={excl} >= global={glob}")

    # ── 3. Sin lesión (penalty = 0.0): los dos modifiers son iguales ─────

    def test_sin_lesion_modifiers_identicos(self):
        """Con phase_penalty=0, raw_score == raw_score_excl → mismos modifiers."""
        casos = [(0.5, 0.5), (0.3, 0.3), (0.7, 0.7), (0.9, 0.9), (0.1, 0.1)]
        for helms, pain in casos:
            glob, excl = self._simular_readiness(helms, pain, phase_penalty=0.0)
            self.assertEqual(glob, excl,
                             msg=f"Sin lesión helms={helms}: glob={glob} debe == excl={excl}")

    # ── 4. Fatiga global sin lesión: ambos reducen igual ─────────────────

    def test_fatiga_sin_lesion_reduce_ambos_por_igual(self):
        """
        Carga alta (helms bajo, pain alto) sin lesión reduce vol_mod_excl y
        vol_mod por igual — la reducción viene de fatiga, no de lesión.
        """
        # Cuerpo muy fatigado: helms bajo, pain alto → score bajo → 0.50
        glob, excl = self._simular_readiness(0.1, 0.1, phase_penalty=0.0)
        self.assertEqual(glob, excl)
        self.assertEqual(glob, 0.50, msg="Cuerpo muy fatigado sin lesión → modifier 0.50")


class TestReturnDictContieneClaves(TestCase):
    """
    Verifica que el dict devuelto por get_readiness_score contiene
    las claves nuevas. Usa la BD de test real (sin mocks complejos).
    """

    def test_claves_nuevas_presentes_sin_lesion(self):
        """Con un cliente sin lesiones, las claves nuevas existen en el dict."""
        from django.contrib.auth.models import User
        from clientes.models import Cliente
        from core.bio_context import BioContextProvider

        user = User.objects.create_user(username='tester_vol56', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user)
        r = BioContextProvider.get_readiness_score(cliente)

        self.assertIn('volume_modifier_excl_lesion_fase', r)
        self.assertIn('has_active_injuries', r)
        # Sin lesión → penalty=0 → ambos modifiers iguales
        self.assertEqual(r['volume_modifier'], r['volume_modifier_excl_lesion_fase'])
        self.assertFalse(r['has_active_injuries'])
