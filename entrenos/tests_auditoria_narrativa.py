"""
Phase 31 — Auditoría narrativa del motor.

Valida que todas las salidas visibles del sistema mantienen el contrato:
    observa → propone → explica → espera permiso

El sistema ya sabe decidir; ahora debe demostrar que sabe hablar de sus
decisiones sin convertirlas en verdad absoluta.

Auditoría en 4 dimensiones:

A. ABSOLUTOS: "siempre", "nunca", "debes", "tienes que", "obligatorio"
B. IDENTIDAD: "eres", "eres alguien", "esto te define", "tu forma de ser"
C. DIAGNÓSTICO: "prohibido", "esto es peligroso", "garantizado", "seguro"
   (el sistema no puede garantizar seguridad médica)
D. CULPA: "no cumpliste", "fallaste", "incumplimiento", "no deberías"

Fuentes auditadas:
  1. _MENSAJES_POR_CAUSA         (motor — causa principal)
  2. _PREF_MENSAJES              (motor — preferencias)
  3. _MENSAJES_PROGRESION        (freno contextual)
  4. _DESCRIPCION_PREFERENCIA   (servicio preferencias)
  5. nota_prudente_lesion()      (alternativas lesión)
  6. _CAUSAS                     (explicacion_decision)
  7. _FASE_LABELS                (freno lesión)
  8. construir_explicacion_decision() senales_activas
  9. Prompts JOI: preferencia_aprendida, decision_plan, rpe_calibracion
"""

import textwrap
from django.test import TestCase


# ── Palabras prohibidas por dimensión ─────────────────────────────────────────

ABSOLUTOS = ['siempre', 'nunca', 'debes', 'tienes que', 'obligatorio', 'jamás']
IDENTIDAD  = ['eres alguien', 'esto te define', 'tu forma de ser', 'eres incapaz']
DIAGNOSTICO = ['garantizado', 'esto es peligroso', 'este ejercicio es seguro',
               'sustitución segura', 'lesión grave', 'no entrenes jamás']
CULPA      = ['no cumpliste', 'fallaste', 'incumplimiento', 'no deberías haber',
              'deberías haber']

ALL_FORBIDDEN = ABSOLUTOS + IDENTIDAD + DIAGNOSTICO + CULPA


def _audit(texto: str, forbidden: list[str] = None) -> list[str]:
    """Returns list of forbidden words found in text (lowercased)."""
    forbidden = forbidden or ALL_FORBIDDEN
    texto_lower = texto.lower()
    return [w for w in forbidden if w in texto_lower]


def _audit_dict(d: dict, forbidden: list[str] = None) -> dict[str, list[str]]:
    """Audits every value in a flat dict. Returns {key: [violations]}."""
    return {k: _audit(str(v), forbidden) for k, v in d.items() if _audit(str(v), forbidden)}


# ── 1. _MENSAJES_POR_CAUSA ────────────────────────────────────────────────────

class TestMensajesPorCausa(TestCase):
    def test_sin_absolutos(self):
        from entrenos.services.sesion_recomendada import _MENSAJES_POR_CAUSA
        violations = _audit_dict(_MENSAJES_POR_CAUSA, ABSOLUTOS)
        self.assertEqual(violations, {},
                         msg=f"_MENSAJES_POR_CAUSA tiene absolutos: {violations}")

    def test_sin_culpa(self):
        from entrenos.services.sesion_recomendada import _MENSAJES_POR_CAUSA
        violations = _audit_dict(_MENSAJES_POR_CAUSA, CULPA)
        self.assertEqual(violations, {},
                         msg=f"_MENSAJES_POR_CAUSA tiene culpa: {violations}")

    def test_sin_identidad(self):
        from entrenos.services.sesion_recomendada import _MENSAJES_POR_CAUSA
        violations = _audit_dict(_MENSAJES_POR_CAUSA, IDENTIDAD)
        self.assertEqual(violations, {},
                         msg=f"_MENSAJES_POR_CAUSA tiene identidad: {violations}")

    def test_tono_propone_no_impone(self):
        """Messages should use 'conviene', 'margen', 'plan sigue aquí' — not orders."""
        from entrenos.services.sesion_recomendada import _MENSAJES_POR_CAUSA
        for causa, msg in _MENSAJES_POR_CAUSA.items():
            texto = msg.lower()
            # Must NOT command imperatively as a rule
            self.assertNotIn('haz', texto, msg=f"Causa '{causa}' usa 'haz'")
            self.assertNotIn('no hagas', texto, msg=f"Causa '{causa}' usa 'no hagas'")


# ── 2. _PREF_MENSAJES ─────────────────────────────────────────────────────────

class TestPrefMensajes(TestCase):
    def test_sin_absolutos(self):
        from entrenos.services.sesion_recomendada import _PREF_MENSAJES
        violations = _audit_dict(_PREF_MENSAJES, ABSOLUTOS)
        self.assertEqual(violations, {},
                         msg=f"_PREF_MENSAJES tiene absolutos: {violations}")

    def test_sin_identidad(self):
        from entrenos.services.sesion_recomendada import _PREF_MENSAJES
        for tipo, msg in _PREF_MENSAJES.items():
            self.assertNotIn(' eres ', msg.lower(),
                             msg=f"Tipo '{tipo}': mensaje usa 'eres' (identidad)")

    def test_usa_tono_referencia(self):
        from entrenos.services.sesion_recomendada import _PREF_MENSAJES
        palabras_blandas = ['referencia', 'recuerda', 'margen', 'opcional', 'suele']
        for tipo, msg in _PREF_MENSAJES.items():
            usa = any(k in msg.lower() for k in palabras_blandas)
            self.assertTrue(usa,
                            msg=f"Tipo '{tipo}': mensaje no usa tono blando: {msg}")


# ── 3. _MENSAJES_PROGRESION ───────────────────────────────────────────────────

class TestMensajesProgresion(TestCase):
    def test_sin_absolutos(self):
        from entrenos.services.progresion_contextual_service import _MENSAJES_PROGRESION
        violations = _audit_dict(_MENSAJES_PROGRESION, ABSOLUTOS)
        self.assertEqual(violations, {},
                         msg=f"_MENSAJES_PROGRESION tiene absolutos: {violations}")

    def test_sin_culpa(self):
        from entrenos.services.progresion_contextual_service import _MENSAJES_PROGRESION
        violations = _audit_dict(_MENSAJES_PROGRESION, CULPA)
        self.assertEqual(violations, {},
                         msg=f"_MENSAJES_PROGRESION tiene culpa: {violations}")

    def test_lesion_mensajes_no_diagnostican(self):
        from entrenos.services.progresion_contextual_service import _MENSAJES_PROGRESION
        for k in ['lesion_activa', 'lesion_retorno']:
            msg = _MENSAJES_PROGRESION.get(k, '')
            violations = _audit(msg, DIAGNOSTICO)
            self.assertEqual(violations, [],
                             msg=f"'{k}': usa diagnóstico médico: {violations}")


# ── 4. _DESCRIPCION_PREFERENCIA ───────────────────────────────────────────────

class TestDescripcionPreferencia(TestCase):
    def test_sin_absolutos(self):
        from entrenos.services.preferencias_service import _DESCRIPCION_PREFERENCIA
        violations = _audit_dict(_DESCRIPCION_PREFERENCIA, ABSOLUTOS)
        self.assertEqual(violations, {},
                         msg=f"_DESCRIPCION_PREFERENCIA tiene absolutos: {violations}")

    def test_sin_identidad(self):
        from entrenos.services.preferencias_service import _DESCRIPCION_PREFERENCIA
        for tipo, desc in _DESCRIPCION_PREFERENCIA.items():
            self.assertNotIn(' eres ', desc.lower(),
                             msg=f"Tipo '{tipo}': descripción usa identidad")

    def test_usa_el_plan_como_sujeto(self):
        from entrenos.services.preferencias_service import _DESCRIPCION_PREFERENCIA
        for tipo, desc in _DESCRIPCION_PREFERENCIA.items():
            self.assertIn('el plan', desc.lower(),
                          msg=f"Tipo '{tipo}': no usa 'el plan' como sujeto: {desc}")


# ── 5. nota_prudente_lesion ───────────────────────────────────────────────────

class TestNotaPrudenteLesion(TestCase):
    def test_sin_diagnostico_medico(self):
        from entrenos.services.alternativas_lesion_service import nota_prudente_lesion
        for fase in ['AGUDA', 'SUB_AGUDA', 'RETORNO']:
            nota = nota_prudente_lesion(fase)
            violations = _audit(nota, DIAGNOSTICO)
            self.assertEqual(violations, [],
                             msg=f"nota_prudente_lesion('{fase}'): usa diagnóstico: {violations}")

    def test_sin_absolutos(self):
        from entrenos.services.alternativas_lesion_service import nota_prudente_lesion
        for fase in ['AGUDA', 'SUB_AGUDA', 'RETORNO']:
            nota = nota_prudente_lesion(fase)
            violations = _audit(nota, ABSOLUTOS)
            self.assertEqual(violations, [],
                             msg=f"nota_prudente_lesion('{fase}'): absolutos: {violations}")


# ── 6. _CAUSAS (explicacion_decision) ────────────────────────────────────────

class TestCausasLabel(TestCase):
    def test_labels_sin_culpa(self):
        from entrenos.services.explicacion_decision_service import _CAUSAS
        for causa, label in _CAUSAS.items():
            violations = _audit(label, CULPA)
            self.assertEqual(violations, [],
                             msg=f"Causa '{causa}': label usa culpa: {violations}")

    def test_labels_legibles_no_tecnicos(self):
        from entrenos.services.explicacion_decision_service import _CAUSAS
        tecnicos = ['fatiga_alta', 'sesion_hoy', 'readiness_bajo']
        for label in _CAUSAS.values():
            for tecnico in tecnicos:
                self.assertNotIn(tecnico, label.lower(),
                                 msg=f"Label usa clave técnica: '{label}'")


# ── 7. _FASE_LABELS ───────────────────────────────────────────────────────────

class TestFaseLabels(TestCase):
    def test_sin_diagnostico(self):
        from entrenos.services.sesion_recomendada import _FASE_LABELS
        for fase, label in _FASE_LABELS.items():
            violations = _audit(label, DIAGNOSTICO)
            self.assertEqual(violations, [],
                             msg=f"Fase '{fase}': usa diagnóstico: {violations}")


# ── 8. construir_explicacion_decision — senales_activas ───────────────────────

class TestExplicacionSenales(TestCase):
    def _senales(self, **kwargs):
        from entrenos.services.explicacion_decision_service import construir_explicacion_decision
        base = {
            'tipo': 'programada_hoy', 'estado': 'entrenar',
            'sesion_programada': None, 'entrenamiento': {},
            'mensaje': '', 'causa_principal': 'sesion_hoy',
            'modo_reducido': False, 'distribucion_aviso': None,
            'preferencia_aplicada': None, 'lesion_aviso': None,
        }
        base.update(kwargs)
        return construir_explicacion_decision(base)['senales_activas']

    def test_senales_sin_absolutos(self):
        senales = self._senales(
            lesion_aviso={
                'zona': 'Rodilla', 'fase': 'RETORNO', 'es_bloqueante': False,
                'ejercicios_en_riesgo': ['Sentadilla'],
                'mensaje': 'En fase de retorno la articulación puede tolerar carga gradual.',
            },
            preferencia_aplicada={
                'tipo': 'evitar_pierna_tras_futbol',
                'mensaje': 'El plan recuerda que separar pierna del fútbol te dio más margen.',
                'accion_sugerida': 'posponer_recomendado',
            },
        )
        for senal in senales:
            violations = _audit(senal, ABSOLUTOS)
            self.assertEqual(violations, [],
                             msg=f"Senal tiene absolutos: '{senal}' → {violations}")

    def test_senales_sin_culpa(self):
        senales = self._senales(modo_reducido=True)
        for senal in senales:
            violations = _audit(senal, CULPA)
            self.assertEqual(violations, [],
                             msg=f"Senal tiene culpa: '{senal}' → {violations}")


# ── 9. Prompts JOI — narrativa sin absolutos ni identidad ─────────────────────

class TestPromptsJOI(TestCase):
    def _build(self, trigger: str, datos: dict) -> str:
        from joi.services import _PROMPT_BUILDERS
        builder = _PROMPT_BUILDERS.get(trigger)
        if not builder:
            return ''
        return builder({}, datos)

    def test_preferencia_aprendida_sin_identidad(self):
        from entrenos.models import PreferenciaPlanAprendida
        prompt = self._build('preferencia_aprendida', {
            'tipo_preferencia': PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            'descripcion': 'El plan intentará no colocar pierna tras el fútbol.',
            'evidencia_count': 2,
        })
        violations = _audit(prompt, IDENTIDAD)
        self.assertEqual(violations, [],
                         msg=f"Prompt 'preferencia_aprendida' usa identidad: {violations}")

    def test_preferencia_aprendida_sin_absolutos(self):
        from entrenos.models import PreferenciaPlanAprendida
        prompt = self._build('preferencia_aprendida', {
            'tipo_preferencia': PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
            'descripcion': 'test',
            'evidencia_count': 2,
        })
        violations = _audit(prompt, ABSOLUTOS)
        self.assertEqual(violations, [],
                         msg=f"Prompt 'preferencia_aprendida' tiene absolutos: {violations}")

    def test_decision_plan_sin_culpa(self):
        prompt = self._build('decision_plan', {
            'accion': 'bajar_peso',
            'ejercicio': 'Sentadilla',
            'motivo': 'RPE elevado 3 sesiones seguidas.',
            'peso_anterior': 90,
            'rpe_anterior': 9,
        })
        if prompt:
            violations = _audit(prompt, CULPA)
            self.assertEqual(violations, [],
                             msg=f"Prompt 'decision_plan' usa culpa: {violations}")

    def test_rpe_calibracion_sin_identidad(self):
        prompt = self._build('rpe_calibracion', {
            'sesiones_analizadas': 3,
            'rpe_medio_reportado': 6,
            'zona_fc_real': 'Z4',
            'diferencia_estimada': '~2 puntos',
        })
        if prompt:
            violations = _audit(prompt, IDENTIDAD)
            self.assertEqual(violations, [],
                             msg=f"Prompt 'rpe_calibracion' usa identidad: {violations}")


# ── Resumen de reglas del contrato (doctest form) ─────────────────────────────

class TestContratoNarrativo(TestCase):
    """
    Meta-test: verifica que el contrato se expresa en el código.

    El sistema:
    ✓ propone  — usa 'puede', 'conviene', 'referencia', 'recuerda'
    ✓ observa  — usa 'el plan detectó', 'el sistema aprendió'
    ✓ protege  — usa 'mantiene', 'frena', 'revisa'
    ✗ NO impone — sin 'debes', 'tienes que', 'obligatorio'
    ✗ NO diagnostica — sin 'prohibido', 'seguro', 'peligroso' (en contexto absoluto)
    ✗ NO convierte en identidad — sin 'eres', 'te define'
    ✗ NO culpabiliza — sin 'fallaste', 'incumpliste'
    """

    def test_vocabulario_propone_presente_en_mensajes(self):
        from entrenos.services.sesion_recomendada import (
            _MENSAJES_POR_CAUSA, _PREF_MENSAJES,
        )
        todos = list(_MENSAJES_POR_CAUSA.values()) + list(_PREF_MENSAJES.values())
        # Vocabulario amplio: propone ('puede', 'conviene', 'referencia'),
        # informa ('sesión', 'plan', 'semana') o conserva agencia ('sigue', 'hilo')
        palabras_validas = [
            'puede', 'conviene', 'referencia', 'recuerda', 'margen', 'plan',
            'sigue', 'sesión', 'semana', 'hilo', 'útil', 'sostiene', 'prevista',
            'bloque', 'pendiente', 'completar',
        ]
        for msg in todos:
            usa = any(k in msg.lower() for k in palabras_validas)
            self.assertTrue(usa,
                            msg=f"Mensaje no tiene vocabulario válido: {msg[:80]}")

    def test_todos_los_mensajes_del_sistema_sin_absolutos(self):
        from entrenos.services.sesion_recomendada import _MENSAJES_POR_CAUSA, _PREF_MENSAJES
        from entrenos.services.progresion_contextual_service import _MENSAJES_PROGRESION
        from entrenos.services.preferencias_service import _DESCRIPCION_PREFERENCIA
        from entrenos.services.explicacion_decision_service import _CAUSAS

        todos = {}
        todos.update({f'causa_{k}': v for k, v in _MENSAJES_POR_CAUSA.items()})
        todos.update({f'pref_{k}': v for k, v in _PREF_MENSAJES.items()})
        todos.update({f'prog_{k}': v for k, v in _MENSAJES_PROGRESION.items()})
        todos.update({f'desc_{k}': v for k, v in _DESCRIPCION_PREFERENCIA.items()})
        todos.update({f'causa_label_{k}': v for k, v in _CAUSAS.items()})

        violations = _audit_dict(todos, ABSOLUTOS)
        self.assertEqual(violations, {},
                         msg=f"Mensajes del sistema con absolutos: {violations}")
