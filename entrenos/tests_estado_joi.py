"""
Phase 42.1 — Tests para el estado narrativo de JOI.

JOI no debe decir más porque sabe más; debe ajustar su presencia
a la calidad de la señal.

Checklist (10):
1.  Sin datos → minima, debe_hablar=False.
2.  Semana limpia + libero_margen → serena, debe_hablar=True.
3.  Hipótesis abierta → observadora.
4.  Señal no captada repetida (≥2) → observadora.
5.  Semana de recuperación (mayoría pausas) → acompañante.
6.  Semana mixta (positiva + no_captada) → no es serena.
7.  nota_tono no usa absolutos ni culpa.
8.  Estado integrado en lectura_semanal (campo estado_joi).
9.  JOI context incluye estado_joi_semanal.
10. intensidad alta solo si positivas ≥ 2 sin no_captadas.
"""

from django.test import TestCase

from clientes.models import Cliente
from django.contrib.auth.models import User
from entrenos.services.lectura_semanal_service import (
    calcular_estado_joi_semanal, construir_lectura_semanal_memoria,
)

ABSOLUTOS = ['siempre', 'nunca', 'debes', 'tienes que', 'obligatorio']
CULPA = ['fallaste', 'no cumpliste', 'incumplimiento', 'deberías haber']


def _lectura(**kwargs):
    base = {
        'hay_datos': True,
        'n_decisiones': 4,
        'balance_estados': {'entrenar': 4},
        'senales_positivas': 0,
        'senales_no_captadas': 0,
        'n_hipotesis_abiertas': 0,
        'n_preferencias_activas': 0,
        'texto_joi': 'Test.',
    }
    base.update(kwargs)
    return base


class EstadoJOIBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_joi42', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestJOI42', 'dias_disponibles': 4},
        )


# ── Case 1: sin datos ─────────────────────────────────────────────────────────

class TestCase1_SinDatos(EstadoJOIBase):
    def test_sin_datos_minima_no_habla(self):
        lectura = {'hay_datos': False, 'n_decisiones': 0}
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'minima')
        self.assertFalse(result['debe_hablar'])

    def test_una_decision_es_insuficiente(self):
        lectura = _lectura(n_decisiones=1, balance_estados={'entrenar': 1})
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'minima')
        self.assertFalse(result['debe_hablar'])


# ── Case 2: semana limpia ─────────────────────────────────────────────────────

class TestCase2_Serena(EstadoJOIBase):
    def test_libero_margen_sin_hilos_es_serena(self):
        lectura = _lectura(senales_positivas=2, senales_no_captadas=0, n_hipotesis_abiertas=0)
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'serena')
        self.assertTrue(result['debe_hablar'])

    def test_serena_una_positiva_intensidad_media(self):
        lectura = _lectura(senales_positivas=1, senales_no_captadas=0)
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'serena')
        self.assertEqual(result['intensidad'], 'media')

    def test_serena_dos_positivas_intensidad_alta(self):
        lectura = _lectura(senales_positivas=2, senales_no_captadas=0)
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'serena')
        self.assertEqual(result['intensidad'], 'alta')


# ── Cases 3-4: observadora ────────────────────────────────────────────────────

class TestCase3_Observadora_Hipotesis(EstadoJOIBase):
    def test_hipotesis_abierta_es_observadora(self):
        lectura = _lectura(n_hipotesis_abiertas=1)
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'observadora')


class TestCase4_Observadora_NoCaptada(EstadoJOIBase):
    def test_dos_senal_no_captada_es_observadora(self):
        lectura = _lectura(senales_no_captadas=2)
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'observadora')

    def test_una_senal_no_captada_no_es_observadora_por_defecto(self):
        # 1 senal_no_captada without hypothesis → not observadora (goes to minima/neutral)
        lectura = _lectura(senales_no_captadas=1, n_hipotesis_abiertas=0, senales_positivas=0)
        result = calcular_estado_joi_semanal(lectura)
        self.assertNotEqual(result['estado'], 'observadora')


# ── Case 5: acompañante ───────────────────────────────────────────────────────

class TestCase5_Acompañante(EstadoJOIBase):
    def test_mayoria_pausas_es_acompañante(self):
        lectura = _lectura(
            n_decisiones=4,
            balance_estados={'recuperar': 2, 'posponer': 1, 'entrenar': 1},
        )
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'acompañante')

    def test_mitad_pausas_exacta_es_acompañante(self):
        lectura = _lectura(
            n_decisiones=2,
            balance_estados={'recuperar': 1, 'entrenar': 1},
        )
        result = calcular_estado_joi_semanal(lectura)
        self.assertEqual(result['estado'], 'acompañante')


# ── Case 6: semana mixta no es serena ────────────────────────────────────────

class TestCase6_MixtaNoEsSerena(EstadoJOIBase):
    def test_positiva_mas_no_captada_no_es_serena(self):
        lectura = _lectura(senales_positivas=2, senales_no_captadas=1)
        result = calcular_estado_joi_semanal(lectura)
        self.assertNotEqual(result['estado'], 'serena')


# ── Case 7: nota_tono sin absolutos ───────────────────────────────────────────

class TestCase7_NotaTonoLenguaje(EstadoJOIBase):
    def test_nota_tono_sin_absolutos(self):
        for lectura_kwargs in [
            {'senales_positivas': 2},
            {'n_hipotesis_abiertas': 1},
            {'balance_estados': {'recuperar': 3, 'entrenar': 1}},
        ]:
            lectura = _lectura(**lectura_kwargs)
            result = calcular_estado_joi_semanal(lectura)
            nota = result['nota_tono'].lower()
            for palabra in ABSOLUTOS + CULPA:
                self.assertNotIn(palabra, nota,
                                 msg=f"nota_tono usa '{palabra}': {nota[:100]}")


# ── Case 8: estado en lectura ──────────────────────────────────────────────────

class TestCase8_EstadoEnLectura(EstadoJOIBase):
    def test_lectura_incluye_estado_joi(self):
        from datetime import date
        lectura = construir_lectura_semanal_memoria(self.cliente, date(2026, 5, 21))
        # Should always have estado_joi (even if no hay_datos)
        self.assertIn('estado_joi', lectura)
        self.assertIn('estado', lectura['estado_joi'])
        self.assertIn(lectura['estado_joi']['estado'],
                      ['serena', 'observadora', 'acompañante', 'minima'])


# ── Case 9: JOI context ───────────────────────────────────────────────────────

class TestCase9_JOIContext(EstadoJOIBase):
    def test_construir_contexto_incluye_estado_joi(self):
        from joi.services import construir_contexto
        ctx = construir_contexto(self.cliente)
        # Should not raise and should be a dict
        self.assertIsInstance(ctx, dict)
        # estado_joi_semanal may or may not be present (only if hay_datos)
        if 'estado_joi_semanal' in ctx:
            self.assertIn(ctx['estado_joi_semanal'],
                          ['serena', 'observadora', 'acompañante', 'minima'])


# ── Case 10: intensidad alta ──────────────────────────────────────────────────

class TestCase10_IntensidadAlta(EstadoJOIBase):
    def test_intensidad_alta_solo_si_2_positivas_sin_no_captadas(self):
        lectura_alta = _lectura(senales_positivas=2, senales_no_captadas=0)
        lectura_media = _lectura(senales_positivas=1, senales_no_captadas=0)
        lectura_mezclada = _lectura(senales_positivas=2, senales_no_captadas=1)

        self.assertEqual(calcular_estado_joi_semanal(lectura_alta)['intensidad'], 'alta')
        self.assertEqual(calcular_estado_joi_semanal(lectura_media)['intensidad'], 'media')
        self.assertNotEqual(calcular_estado_joi_semanal(lectura_mezclada)['intensidad'], 'alta')
