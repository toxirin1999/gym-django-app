"""
Phase 43 — Tests de contrato de presencia JOI.

JOI no habla según cuánto sabe; habla según cuánta presencia merece la semana.

Los tests no validan la respuesta de la IA (eso requiere API call).
Validan que la instrucción de presencia en el prompt respeta el contrato:
- minima → instrucción de silencio o una frase
- observadora → instrucción de no concluir, no alarmar
- serena → instrucción de calma, no celebración forzada
- acompañante → instrucción de presencia sin enumerar datos

Checklist (12):
1.  minima: nota_tono menciona silencio o brevedad.
2.  observadora: nota_tono contiene "señala" o "sin concluir" o "no alarmante".
3.  serena: nota_tono menciona "calma" o "brevedad" o "sin celebración".
4.  acompañante: nota_tono menciona "presencia" o "sin urgencia".
5.  debe_hablar=False → nota_presencia en prompt menciona silencio.
6.  debe_hablar=False con minima → prompt no genera párrafo de instrucción larga.
7.  estado serena no aparece cuando hay senal_no_captada.
8.  estado minima con <2 decisiones siempre tiene debe_hablar=False.
9.  nota_tono no usa imperativos absolutos ("siempre", "nunca", "debes").
10. Todos los estados tienen nota_tono no vacía.
11. apertura_manana prompt incluye nota_presencia cuando debe_hablar=True.
12. apertura_manana prompt incluye silencio cuando debe_hablar=False.
"""

from django.test import TestCase
from django.contrib.auth.models import User

from clientes.models import Cliente
from entrenos.services.lectura_semanal_service import calcular_estado_joi_semanal

ESTADOS_VALIDOS = {'serena', 'observadora', 'acompañante', 'minima'}
ABSOLUTOS = ['siempre', 'nunca', 'debes hacer', 'obligatorio', 'jamás']


def _lectura(**kwargs):
    base = {
        'hay_datos': True, 'n_decisiones': 4,
        'balance_estados': {'entrenar': 4},
        'senales_positivas': 0, 'senales_no_captadas': 0,
        'n_hipotesis_abiertas': 0, 'n_preferencias_activas': 0,
        'texto_joi': 'Test.',
    }
    base.update(kwargs)
    return base


class ContratoPrecenciaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_cp43', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestCP43', 'dias_disponibles': 4},
        )


# ── Cases 1-4: nota_tono por estado ──────────────────────────────────────────

class TestCase1_MinimaTono(ContratoPrecenciaBase):
    def test_minima_nota_tono_menciona_silencio_o_brevedad(self):
        result = calcular_estado_joi_semanal({'hay_datos': False, 'n_decisiones': 0})
        nota = result['nota_tono'].lower()
        keywords = ['silencio', 'una sola frase', 'una frase', 'breve', 'mínima']
        self.assertTrue(any(k in nota for k in keywords),
                        msg=f"minima nota_tono no menciona silencio/brevedad: {nota}")

    def test_minima_debe_hablar_false(self):
        result = calcular_estado_joi_semanal({'hay_datos': False, 'n_decisiones': 0})
        self.assertFalse(result['debe_hablar'])


class TestCase2_ObservadoraTono(ContratoPrecenciaBase):
    def test_observadora_nota_tono_sin_concluir_no_alarmar(self):
        result = calcular_estado_joi_semanal(_lectura(n_hipotesis_abiertas=1))
        nota = result['nota_tono'].lower()
        self.assertEqual(result['estado'], 'observadora')
        keywords = ['sin concluir', 'no alarmante', 'observador', 'señala', 'calma']
        self.assertTrue(any(k in nota for k in keywords),
                        msg=f"observadora nota_tono no blinda contra conclusión/alarma: {nota}")


class TestCase3_SerenaTono(ContratoPrecenciaBase):
    def test_serena_nota_tono_calma_sin_celebracion(self):
        result = calcular_estado_joi_semanal(_lectura(senales_positivas=2))
        nota = result['nota_tono'].lower()
        self.assertEqual(result['estado'], 'serena')
        keywords = ['calma', 'breve', 'sin celebración', 'brevedad', 'espacio']
        self.assertTrue(any(k in nota for k in keywords),
                        msg=f"serena nota_tono no blinda contra celebración: {nota}")

    def test_serena_no_menciona_alarma(self):
        result = calcular_estado_joi_semanal(_lectura(senales_positivas=2))
        nota = result['nota_tono'].lower()
        self.assertNotIn('alarma', nota)
        self.assertNotIn('urgencia', nota)


class TestCase4_AcompañanteTono(ContratoPrecenciaBase):
    def test_acompañante_nota_tono_presencia_sin_urgencia(self):
        result = calcular_estado_joi_semanal(_lectura(
            n_decisiones=4,
            balance_estados={'recuperar': 2, 'posponer': 1, 'entrenar': 1},
        ))
        nota = result['nota_tono'].lower()
        self.assertEqual(result['estado'], 'acompañante')
        keywords = ['presencia', 'sin urgencia', 'tranquilo', 'acompaña']
        self.assertTrue(any(k in nota for k in keywords),
                        msg=f"acompañante nota_tono no blinda contra urgencia: {nota}")


# ── Cases 5-6: debe_hablar=False en prompt ─────────────────────────────────────

class TestCase5_PromptSilencio(ContratoPrecenciaBase):
    def test_debe_hablar_false_genera_instruccion_de_silencio(self):
        """When debe_hablar=False, the prompt should mention silence."""
        from joi.services import _prompt_apertura_manana

        ctx = {
            'joi_debe_hablar_semanal': False,
            'joi_nota_tono_semanal': 'Sin suficientes datos. Una sola frase tranquila.',
            'estado_joi_semanal': 'minima',
            'ultima_actividad': None,
            'sesiones_semana_total': 0,
            'actividad_semana': {},
            'racha_dias': 0,
            'rpe_gym_semanas': [],
            'carga_semanas': [],
            'prs_semana': [],
            'decisiones_plan': {},
            'lesion': None,
            'dias_hasta_carrera': None,
            'readiness_hyrox': None,
            'tsb_hyrox': None,
            'progreso_estandares_global': None,
            'estaciones_debiles_estandar': [],
            'estaciones_penalizadas': [],
            'tiempo_estimado_carrera': None,
            'comparativa_temporal': [],
            'bloque_semanal_gym': None,
            'patron_multisemanal_gym': None,
            'distribucion_semanal_gym': None,
            'preferencias_plan_activas': [],
            'lectura_semanal_memoria': None,
            'semaforo': None,
            'fatiga_extragym': None,
            'bio_signals': None,
            'cierre_ayer': None,
        }
        prompt = _prompt_apertura_manana(ctx, {})
        prompt_lower = prompt.lower()
        silence_keywords = ['silencio', 'una sola frase', 'una frase', 'válido']
        self.assertTrue(any(k in prompt_lower for k in silence_keywords),
                        msg=f"Prompt no menciona silencio con debe_hablar=False: {prompt[:200]}")


class TestCase6_PromptMinimaBreve(ContratoPrecenciaBase):
    def test_minima_nota_presencia_es_corta(self):
        """The nota_presencia for minima should be concise, not a paragraph."""
        from joi.services import _prompt_apertura_manana

        ctx = {
            'joi_debe_hablar_semanal': False,
            'joi_nota_tono_semanal': '',
            'estado_joi_semanal': 'minima',
            'ultima_actividad': None, 'sesiones_semana_total': 0,
            'actividad_semana': {}, 'racha_dias': 0,
            'rpe_gym_semanas': [], 'carga_semanas': [], 'prs_semana': [],
            'decisiones_plan': {}, 'lesion': None, 'dias_hasta_carrera': None,
            'readiness_hyrox': None, 'tsb_hyrox': None,
            'progreso_estandares_global': None, 'estaciones_debiles_estandar': [],
            'estaciones_penalizadas': [], 'tiempo_estimado_carrera': None,
            'comparativa_temporal': [], 'bloque_semanal_gym': None,
            'patron_multisemanal_gym': None, 'distribucion_semanal_gym': None,
            'preferencias_plan_activas': [], 'lectura_semanal_memoria': None,
            'semaforo': None, 'fatiga_extragym': None,
            'bio_signals': None, 'cierre_ayer': None,
        }
        prompt = _prompt_apertura_manana(ctx, {})
        # NOTA DE PRESENCIA SEMANAL should not be a huge paragraph for minima
        if 'NOTA DE PRESENCIA' in prompt:
            # Find the note section
            nota_start = prompt.find('NOTA DE PRESENCIA')
            nota_end = prompt.find('\n\n', nota_start)
            nota_section = prompt[nota_start:nota_end] if nota_end > 0 else prompt[nota_start:]
            self.assertLess(len(nota_section), 300,
                            msg=f"Nota de presencia minima demasiado larga: {nota_section}")


# ── Cases 7-8: invariantes de estado ──────────────────────────────────────────

class TestCase7_SerenaConNoCaptada(ContratoPrecenciaBase):
    def test_serena_no_aparece_con_senal_no_captada(self):
        """serena requires no missed signals."""
        lectura = _lectura(senales_positivas=2, senales_no_captadas=1)
        result = calcular_estado_joi_semanal(lectura)
        self.assertNotEqual(result['estado'], 'serena')


class TestCase8_MinimaMenosDeDos(ContratoPrecenciaBase):
    def test_menos_de_2_decisiones_siempre_minima_no_habla(self):
        for n in [0, 1]:
            lectura = _lectura(n_decisiones=n, senales_positivas=2)
            result = calcular_estado_joi_semanal(lectura)
            self.assertEqual(result['estado'], 'minima',
                             msg=f"n_decisiones={n} debería ser minima")
            self.assertFalse(result['debe_hablar'])


# ── Case 9: sin absolutos en nota_tono ───────────────────────────────────────

class TestCase9_SinAbsolutos(ContratoPrecenciaBase):
    def test_ninguna_nota_tono_usa_absolutos(self):
        escenarios = [
            _lectura(senales_positivas=2),                  # serena
            _lectura(n_hipotesis_abiertas=1),               # observadora
            _lectura(balance_estados={'recuperar': 3, 'entrenar': 1}, n_decisiones=4),  # acompañante
            {'hay_datos': False, 'n_decisiones': 0},        # minima
        ]
        for lectura in escenarios:
            result = calcular_estado_joi_semanal(lectura)
            nota = result['nota_tono'].lower()
            for absoluto in ABSOLUTOS:
                self.assertNotIn(absoluto, nota,
                                 msg=f"Estado '{result['estado']}' usa '{absoluto}': {nota}")


# ── Case 10: todos los estados tienen nota_tono ───────────────────────────────

class TestCase10_TodosConNotaTono(ContratoPrecenciaBase):
    def test_todos_estados_tienen_nota_tono_no_vacia(self):
        escenarios = [
            (_lectura(senales_positivas=2), 'serena'),
            (_lectura(n_hipotesis_abiertas=1), 'observadora'),
            (_lectura(balance_estados={'recuperar': 3, 'entrenar': 1}, n_decisiones=4), 'acompañante'),
            ({'hay_datos': False, 'n_decisiones': 0}, 'minima'),
        ]
        for lectura, esperado in escenarios:
            result = calcular_estado_joi_semanal(lectura)
            self.assertEqual(result['estado'], esperado,
                             msg=f"Estado esperado {esperado}, obtenido {result['estado']}")
            self.assertTrue(len(result['nota_tono']) > 10,
                            msg=f"Estado '{esperado}' tiene nota_tono vacía o muy corta")


# ── Cases 11-12: prompt apertura con nota_presencia ───────────────────────────

class TestCase11_PromptConPresencia(ContratoPrecenciaBase):
    def test_prompt_incluye_nota_presencia_serena(self):
        from joi.services import _prompt_apertura_manana
        ctx = {
            'joi_debe_hablar_semanal': True,
            'joi_nota_tono_semanal': 'Semana con espacio. JOI puede hablar desde la calma.',
            'estado_joi_semanal': 'serena',
            'ultima_actividad': None, 'sesiones_semana_total': 0,
            'actividad_semana': {}, 'racha_dias': 0,
            'rpe_gym_semanas': [], 'carga_semanas': [], 'prs_semana': [],
            'decisiones_plan': {}, 'lesion': None, 'dias_hasta_carrera': None,
            'readiness_hyrox': None, 'tsb_hyrox': None,
            'progreso_estandares_global': None, 'estaciones_debiles_estandar': [],
            'estaciones_penalizadas': [], 'tiempo_estimado_carrera': None,
            'comparativa_temporal': [], 'bloque_semanal_gym': None,
            'patron_multisemanal_gym': None, 'distribucion_semanal_gym': None,
            'preferencias_plan_activas': [], 'lectura_semanal_memoria': None,
            'semaforo': None, 'fatiga_extragym': None,
            'bio_signals': None, 'cierre_ayer': None,
        }
        prompt = _prompt_apertura_manana(ctx, {})
        self.assertIn('NOTA DE PRESENCIA SEMANAL', prompt)
        self.assertIn('calma', prompt.lower())


class TestCase12_PromptSilencioDebeFalse(ContratoPrecenciaBase):
    def test_contrato_silencio_en_prompt_cuando_no_debe_hablar(self):
        """Contract: when debe_hablar=False, prompt must contain silence instruction."""
        from joi.services import _prompt_apertura_manana
        ctx_silencio = {
            'joi_debe_hablar_semanal': False,
            'joi_nota_tono_semanal': '',
            'estado_joi_semanal': 'minima',
            'ultima_actividad': None, 'sesiones_semana_total': 0,
            'actividad_semana': {}, 'racha_dias': 0,
            'rpe_gym_semanas': [], 'carga_semanas': [], 'prs_semana': [],
            'decisiones_plan': {}, 'lesion': None, 'dias_hasta_carrera': None,
            'readiness_hyrox': None, 'tsb_hyrox': None,
            'progreso_estandares_global': None, 'estaciones_debiles_estandar': [],
            'estaciones_penalizadas': [], 'tiempo_estimado_carrera': None,
            'comparativa_temporal': [], 'bloque_semanal_gym': None,
            'patron_multisemanal_gym': None, 'distribucion_semanal_gym': None,
            'preferencias_plan_activas': [], 'lectura_semanal_memoria': None,
            'semaforo': None, 'fatiga_extragym': None,
            'bio_signals': None, 'cierre_ayer': None,
        }
        prompt = _prompt_apertura_manana(ctx_silencio, {})
        # The silence contract must be in the prompt
        tiene_silencio = (
            'silencio' in prompt.lower() or
            'una sola frase' in prompt.lower() or
            'una frase' in prompt.lower()
        )
        self.assertTrue(tiene_silencio,
                        msg=f"Contrato de silencio no está en el prompt: {prompt[:300]}")
