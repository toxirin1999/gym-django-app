"""
Phase 56.11 — Contrato semántico JOI entre módulos.

Principio: JOI no cambia de ética según el módulo.
Gym, Hyrox y Diario deben hablar con el mismo contrato.

Checklist (7):
1.  Diario: no convierte frases oscuras en diagnósticos psicológicos.
2.  Diario: puede nombrar peso emocional sin etiquetar identidad.
3.  Hyrox: no atribuye intención mental sin dato explícito.
4.  Hyrox: caracteres cirílicos son detectados por el validador.
5.  Readiness 60-70 usa la misma etiqueta en Gym y Hyrox.
6.  Readiness "bajo" solo aparece por debajo del umbral real (< 40).
7.  Validador pasa salida correcta sin violaciones.
"""

from django.test import TestCase

from joi.validador_semantico import (
    validar_semantica_joi,
    readiness_etiqueta,
    readiness_descripcion_corta,
    READINESS_BAJO_UMBRAL,
)


class TestContratoSemanticoJOI(TestCase):

    # ── 1. Diagnóstico prohibido ──────────────────────────────────────────────

    def test_diagnostico_apatia_detectado(self):
        """'apatía de vivir' es un diagnóstico prohibido."""
        txt = "Ayer escribiste algo oscuro. Eso es apatía de vivir, David."
        r = validar_semantica_joi(txt, modulo='diario')
        self.assertFalse(r['valida'])
        self.assertTrue(any('diagnostico' in v for v in r['violaciones']))

    def test_diagnostico_crisis_detectado(self):
        txt = "Tu cuerpo responde bien pero estás en una crisis."
        r = validar_semantica_joi(txt, modulo='diario')
        self.assertFalse(r['valida'])
        self.assertTrue(any('diagnostico' in v for v in r['violaciones']))

    # ── 2. Nombrar sin etiquetar ──────────────────────────────────────────────

    def test_nombrar_sin_etiquetar_es_valido(self):
        """Nombrar el estado sin sentenciarlo es correcto."""
        txt = "Ayer escribiste algo oscuro sobre el futuro. Eso pesa. Si entrenas, que sea simple."
        r = validar_semantica_joi(txt, modulo='diario')
        self.assertTrue(r['valida'], msg=f"Violaciones inesperadas: {r['violaciones']}")

    def test_nombrar_peso_emocional_sin_etiqueta_es_valido(self):
        txt = "Llevas días con algo encima. Hoy descansa sin culpa."
        r = validar_semantica_joi(txt, modulo='diario')
        self.assertTrue(r['valida'], msg=f"Violaciones: {r['violaciones']}")

    # ── 3. Atribución mental prohibida ───────────────────────────────────────

    def test_atribucion_mental_hyrox_detectada(self):
        """'tu mente intenta convencerse' es atribución mental prohibida."""
        txt = "Dieciséis minutos a RPE 8. Tu mente intenta convencerse de que puede."
        r = validar_semantica_joi(txt, modulo='hyrox')
        self.assertFalse(r['valida'])
        self.assertTrue(any('atribucion_mental' in v for v in r['violaciones']))

    def test_intentas_convencerte_detectado(self):
        txt = "Entrenaste con reserva, aunque intentas convencerte de que estás listo."
        r = validar_semantica_joi(txt, modulo='hyrox')
        self.assertFalse(r['valida'])

    def test_hyrox_datos_concretos_sin_atribucion_es_valido(self):
        """Usar datos concretos sin atribuir estados mentales es correcto."""
        txt = "Dieciséis minutos a RPE 8 en estaciones son práctica real del terreno que vas a encontrar."
        r = validar_semantica_joi(txt, modulo='hyrox')
        self.assertTrue(r['valida'], msg=f"Violaciones: {r['violaciones']}")

    # ── 4. Cirílicos detectados ───────────────────────────────────────────────

    def test_ciriilico_у_detectado(self):
        """El validador detecta caracteres cirílicos que escaparon al filtro."""
        txt = "Тu cuerpo respondió."  # 'Т' es cirílico
        r = validar_semantica_joi(txt, modulo='hyrox')
        self.assertFalse(r['valida'])
        self.assertIn('ciriilico_detectado', r['violaciones'])

    def test_у_ciriilico_detectado(self):
        """'у' cirílico (lookalike de 'y') debe ser detectado."""
        txt = "уo veo el cuerpo preparado."  # 'у' es Cyrillic
        r = validar_semantica_joi(txt, modulo='gym')
        self.assertFalse(r['valida'])

    def test_texto_latino_puro_no_falla_ciriilico(self):
        txt = "Tu cuerpo completó la sesión con margen."
        r = validar_semantica_joi(txt, modulo='gym')
        self.assertNotIn('ciriilico_detectado', r['violaciones'])

    # ── 5. Readiness 60-70: misma etiqueta en Gym y Hyrox ────────────────────

    def test_readiness_67_etiqueta_consistente(self):
        """Readiness 67 debe devolver 'Disponible con reserva' (misma escala)."""
        self.assertEqual(readiness_etiqueta(67), 'Disponible con reserva')

    def test_readiness_65_etiqueta_consistente(self):
        # 65 está en el rango 55-69 → "Disponible con reserva"
        self.assertEqual(readiness_etiqueta(65), 'Disponible con reserva')

    def test_readiness_70_etiqueta_consistente(self):
        # 70 empieza el rango "con margen"
        self.assertEqual(readiness_etiqueta(70), 'Disponible con margen')

    def test_readiness_descripcion_corta_67(self):
        self.assertEqual(readiness_descripcion_corta(67), 'disponible con reserva')

    def test_readiness_etiqueta_no_contiene_bajo_en_rango_medio(self):
        """Para readiness >= 40, la etiqueta no debe incluir la palabra 'bajo'."""
        for score in (40, 50, 60, 65, 70, 80, 90, 100):
            etiqueta = readiness_etiqueta(score)
            self.assertNotIn('bajo', etiqueta.lower(),
                             msg=f"'bajo' aparece en readiness={score}: '{etiqueta}'")

    # ── 6. "bajo" solo por debajo del umbral real ─────────────────────────────

    def test_umbral_bajo_definido(self):
        """READINESS_BAJO_UMBRAL debe ser <= 40."""
        self.assertLessEqual(READINESS_BAJO_UMBRAL, 40)

    def test_readiness_bajo_umbral_no_es_bajo(self):
        """Justo en el umbral, la etiqueta no es 'bajo'."""
        etiqueta = readiness_etiqueta(READINESS_BAJO_UMBRAL)
        self.assertNotIn('bajo', etiqueta.lower())

    def test_readiness_bajo_umbral_minus1_es_carga_alta(self):
        """Por debajo del umbral → 'Carga alta acumulada', nunca 'bajo'."""
        etiqueta = readiness_etiqueta(READINESS_BAJO_UMBRAL - 1)
        self.assertIn('Carga alta', etiqueta)

    def test_readiness_texto_bajo_en_prompt_detectado(self):
        """Si el texto generado dice 'readiness está bajo', el validador lo captura."""
        txt = "Tu readiness está bajo hoy — considera descansar."
        r = validar_semantica_joi(txt, modulo='hyrox')
        self.assertFalse(r['valida'])
        self.assertTrue(any('readiness_bajo_incorrecto' in v for v in r['violaciones']))

    # ── 7. Validador pasa salida limpia ──────────────────────────────────────

    def test_salida_limpia_sin_violaciones(self):
        """Un mensaje correcto no produce violaciones."""
        txt = (
            "Dieciséis minutos a RPE 8 en estaciones no son un trámite: son práctica real "
            "del terreno que vas a encontrar. Tu cuerpo respondió con reserva, no vacío. "
            "Hoy cuenta como familiaridad acumulada."
        )
        r = validar_semantica_joi(txt, modulo='hyrox')
        self.assertTrue(r['valida'], msg=f"Violaciones inesperadas: {r['violaciones']}")

    def test_salida_vacia_es_valida(self):
        """Texto vacío (JOI en silencio) no es una violación."""
        r = validar_semantica_joi('', modulo='gym')
        self.assertTrue(r['valida'])

    def test_texto_original_no_se_modifica(self):
        """El validador devuelve siempre el texto original sin modificarlo."""
        txt = "Llevas días con algo encima."
        r = validar_semantica_joi(txt, modulo='diario')
        self.assertEqual(r['texto'], txt)
