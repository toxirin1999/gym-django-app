"""
Phase 44.1 — Tests del validador de salida JOI.

Phase 43 decide el tono antes de generar.
Phase 44 comprueba que la voz generada no traicione ese tono.

Checklist (12):
1.  minima permite silencio (texto vacío → válido).
2.  minima rechaza más de 2 frases.
3.  minima rechaza interpretación sin datos.
4.  serena rechaza celebración exagerada.
5.  serena permite calma breve.
6.  observadora rechaza conclusiones fuertes.
7.  observadora permite lenguaje tentativo.
8.  acompañante rechaza enumeraciones tipo informe.
9.  acompañante permite presencia sin urgencia.
10. fallback seguro no rompe la apertura (no lanza excepción).
11. Salida con identidad → rechazada en todos los estados.
12. texto_seguro siempre es string, nunca None.
"""

from django.test import TestCase

from joi.validador_salida import validar_salida_presencia_joi


class ValidadorSalidaBase(TestCase):
    def _validar(self, texto, estado):
        return validar_salida_presencia_joi(texto, estado)


# ── Case 1: minima permite silencio ──────────────────────────────────────────

class TestCase1_MinimaPermiteSilencio(ValidadorSalidaBase):
    def test_texto_vacio_es_valido(self):
        r = self._validar('', 'minima')
        self.assertTrue(r['valida'])
        self.assertIsInstance(r['texto_seguro'], str)

    def test_none_no_rompe(self):
        r = self._validar(None, 'minima')
        self.assertTrue(r['valida'])
        self.assertIsInstance(r['texto_seguro'], str)

    def test_frase_corta_valida(self):
        r = self._validar('Hoy no hace falta forzar una lectura.', 'minima')
        self.assertTrue(r['valida'])


# ── Case 2: minima rechaza demasiadas frases ──────────────────────────────────

class TestCase2_MinimaRechazaLargo(ValidadorSalidaBase):
    def test_tres_frases_rechazado(self):
        texto = ('Esta semana el sistema ha notado ciertos patrones. '
                 'Parece que hay un cambio en tu energía. '
                 'El plan lo está registrando para ajustarse mejor.')
        r = self._validar(texto, 'minima')
        self.assertFalse(r['valida'])
        self.assertIn('minima', r['motivo'])
        self.assertEqual(r['texto_seguro'], '')  # silence for minima


# ── Case 3: minima rechaza interpretación sin datos ───────────────────────────

class TestCase3_MinimaRechazaInterpretacion(ValidadorSalidaBase):
    def test_conclusiones_sin_datos_rechazadas(self):
        texto = 'Quizá estás atravesando una fase de menor energía y el plan lo está notando.'
        r = self._validar(texto, 'minima')
        self.assertFalse(r['valida'])
        self.assertEqual(r['texto_seguro'], '')


# ── Case 4: serena rechaza celebración ───────────────────────────────────────

class TestCase4_SerenaRechazaCelebracion(ValidadorSalidaBase):
    def test_gran_semana_rechazada(self):
        r = self._validar('¡Gran semana! Estás demostrando una disciplina increíble.', 'serena')
        self.assertFalse(r['valida'])
        self.assertIn('serena', r['motivo'])

    def test_increible_rechazado(self):
        r = self._validar('Tu progreso esta semana es increíble.', 'serena')
        self.assertFalse(r['valida'])

    def test_fallback_serena_es_neutro(self):
        texto = '¡Gran semana! El margen fue notable. Y además todo lo demás fue bien.'
        r = self._validar(texto, 'serena')
        # fallback should be the neutral fixed phrase, not the celebration
        self.assertFalse(r['valida'])
        self.assertNotIn('¡Gran semana!', r['texto_seguro'])
        self.assertGreater(len(r['texto_seguro']), 0)  # not empty (only minima is empty)


# ── Case 5: serena permite calma breve ────────────────────────────────────────

class TestCase5_SerenaPermiteCalma(ValidadorSalidaBase):
    def test_frase_serena_valida(self):
        texto = 'Esta semana hubo margen. No hace falta empujarlo más de lo necesario.'
        r = self._validar(texto, 'serena')
        self.assertTrue(r['valida'])
        self.assertEqual(r['texto_seguro'], texto.strip())


# ── Case 6: observadora rechaza conclusiones ──────────────────────────────────

class TestCase6_ObservadoraRechazaConclusion(ValidadorSalidaBase):
    def test_conclusion_fuerte_rechazada(self):
        texto = 'El sistema ha detectado que estás acumulando fatiga muscular progresiva.'
        r = self._validar(texto, 'observadora')
        self.assertFalse(r['valida'])
        self.assertEqual(r['texto_seguro'], validar_salida_presencia_joi(
            'Hay una señal que se ha repetido. Todavía no dice qué cambiar, solo dónde mirar.',
            'observadora',
        )['texto_seguro'])


# ── Case 7: observadora permite tentativo ────────────────────────────────────

class TestCase7_ObservadoraPermiteTentativo(ValidadorSalidaBase):
    def test_lenguaje_tentativo_valido(self):
        texto = 'Hay una señal que se ha repetido. Todavía no dice qué cambiar, solo dónde mirar.'
        r = self._validar(texto, 'observadora')
        self.assertTrue(r['valida'])

    def test_quiza_valido(self):
        texto = 'Quizá hay algo aquí que merece un poco más de atención la próxima vez.'
        r = self._validar(texto, 'observadora')
        self.assertTrue(r['valida'])


# ── Case 8: acompañante rechaza enumeración ───────────────────────────────────

class TestCase8_AcompañanteRechazaEnum(ValidadorSalidaBase):
    def test_enumeracion_de_datos_rechazada(self):
        texto = 'Has pausado 3 veces, recuperado 2 sesiones y reducido carga en 1 bloque.'
        r = self._validar(texto, 'acompañante')
        self.assertFalse(r['valida'])
        self.assertIn('acompañante', r['motivo'])

    def test_urgencia_rechazada(self):
        r = self._validar('Debes descansar más si quieres recuperarte bien.', 'acompañante')
        self.assertFalse(r['valida'])


# ── Case 9: acompañante permite presencia ─────────────────────────────────────

class TestCase9_AcompañantePermitePresencia(ValidadorSalidaBase):
    def test_presencia_sin_urgencia_valida(self):
        texto = 'Esta semana pidió más margen. A veces sostener el ritmo también es saber aflojar.'
        r = self._validar(texto, 'acompañante')
        self.assertTrue(r['valida'])


# ── Case 10: fallback no rompe ────────────────────────────────────────────────

class TestCase10_FallbackNoRompe(ValidadorSalidaBase):
    def test_fallo_silencioso_no_lanza(self):
        # Even with None client, should not raise
        result = validar_salida_presencia_joi(
            'Texto con increíble celebración!!!',
            'serena',
        )
        self.assertIsInstance(result, dict)
        self.assertIn('texto_seguro', result)
        self.assertIsInstance(result['texto_seguro'], str)

    def test_estado_desconocido_pasa_sin_modificar(self):
        texto = 'Un texto cualquiera.'
        r = self._validar(texto, 'estado_no_existe')
        self.assertTrue(r['valida'])
        self.assertEqual(r['texto_seguro'], texto)


# ── Case 11: identidad rechazada en todos los estados ────────────────────────

class TestCase11_IdentidadRechazada(ValidadorSalidaBase):
    def test_identidad_rechazada_en_serena(self):
        r = self._validar('Eres alguien que siempre busca mejorar.', 'serena')
        self.assertFalse(r['valida'])
        self.assertIn('identidad', r['motivo'])

    def test_identidad_rechazada_en_observadora(self):
        r = self._validar('Esto te define como atleta de alto rendimiento.', 'observadora')
        self.assertFalse(r['valida'])

    def test_identidad_rechazada_en_acompañante(self):
        r = self._validar('Eres alguien que sabe cuándo descansar.', 'acompañante')
        self.assertFalse(r['valida'])


# ── Case 12: texto_seguro siempre es string ───────────────────────────────────

class TestCase12_TextoSeguroSiempreString(ValidadorSalidaBase):
    def test_texto_seguro_nunca_none(self):
        casos = [
            ('', 'minima'),
            (None, 'minima'),
            ('¡Gran semana! Esto es increíble.', 'serena'),
            ('Has pausado 5 veces y reducido 3 bloques.', 'acompañante'),
            ('El sistema ha detectado que estás en una fase crítica.', 'observadora'),
        ]
        for texto, estado in casos:
            r = validar_salida_presencia_joi(texto, estado)
            self.assertIsNotNone(r['texto_seguro'],
                                 msg=f"texto_seguro es None para estado={estado}, texto={texto!r}")
            self.assertIsInstance(r['texto_seguro'], str)
