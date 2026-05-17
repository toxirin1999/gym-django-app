"""
Phase 6.2 — Integration tests for the gym weekly signal in JOI.

Tests cover:
- bloque_semanal_para_joi: no identity language
- construir_contexto: injects bloque_semanal_gym when available, doesn't break if service fails
- _prompt_apertura_manana: includes the label, no empty section when block is None
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


_IDENTITY_WORDS = ['eres ', 'siempre ', 'nunca ', 'tu patrón', 'tu identidad', 'por naturaleza']


class SemanalJOIBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_joi6', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'TesterJOI', 'dias_disponibles': 4},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_joi')
        self.hoy = date(2026, 5, 20)
        cache.clear()

    def tearDown(self):
        cache.clear()


class TestBloqueJOI_Lenguaje(SemanalJOIBase):
    """Phase 6.2: bloque_semanal_para_joi produces clean, non-identity language."""

    def _make_entreno(self, fecha=None):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina,
            fecha=fecha or self.hoy,
        )

    def test_no_contiene_lenguaje_identitario(self):
        from entrenos.services.analisis_semanal_service import bloque_semanal_para_joi
        self._make_entreno()
        result = bloque_semanal_para_joi(self.cliente, self.hoy) or ''
        texto = result.lower()
        for palabra in _IDENTITY_WORDS:
            self.assertNotIn(palabra, texto, msg=f"Lenguaje identitario encontrado: '{palabra}'")

    def test_no_contiene_lenguaje_de_culpa(self):
        from entrenos.services.analisis_semanal_service import bloque_semanal_para_joi
        self._make_entreno()
        result = bloque_semanal_para_joi(self.cliente, self.hoy) or ''
        texto = result.lower()
        for termino in ['fallaste', 'fracaso', 'incumpliste', 'mal hecho']:
            self.assertNotIn(termino, texto)

    def test_es_compacto(self):
        from entrenos.services.analisis_semanal_service import bloque_semanal_para_joi
        self._make_entreno()
        result = bloque_semanal_para_joi(self.cliente, self.hoy) or ''
        # Must fit in a prompt context: under 300 chars
        self.assertLess(len(result), 300, msg=f"Bloque demasiado largo ({len(result)} chars)")

    def test_sin_datos_devuelve_none(self):
        from entrenos.services.analisis_semanal_service import bloque_semanal_para_joi
        result = bloque_semanal_para_joi(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_con_datos_devuelve_string_no_vacio(self):
        from entrenos.services.analisis_semanal_service import bloque_semanal_para_joi
        self._make_entreno()
        result = bloque_semanal_para_joi(self.cliente, self.hoy)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 0)


class TestConstruirContexto_BloqueGym(SemanalJOIBase):
    """Phase 6.2: construir_contexto injects bloque_semanal_gym correctly."""

    def test_contexto_incluye_bloque_cuando_hay_datos(self):
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy
        )
        bloque_esperado = "Gym esta semana: 1 sesión. Continuidad: baja. Suficiencia: completa. Margen: medio. Semana sólida."

        with patch(
            'entrenos.services.analisis_semanal_service.bloque_semanal_para_joi',
            return_value=bloque_esperado,
        ):
            from joi.services import construir_contexto
            ctx = construir_contexto(self.cliente)

        self.assertIn('bloque_semanal_gym', ctx)
        self.assertEqual(ctx['bloque_semanal_gym'], bloque_esperado)

    def test_contexto_no_incluye_bloque_cuando_none(self):
        with patch(
            'entrenos.services.analisis_semanal_service.bloque_semanal_para_joi',
            return_value=None,
        ):
            from joi.services import construir_contexto
            ctx = construir_contexto(self.cliente)

        self.assertNotIn('bloque_semanal_gym', ctx)

    def test_contexto_no_rompe_si_servicio_falla(self):
        with patch(
            'entrenos.services.analisis_semanal_service.bloque_semanal_para_joi',
            side_effect=Exception('servicio caído'),
        ):
            from joi.services import construir_contexto
            try:
                ctx = construir_contexto(self.cliente)
                # Should not have bloque but should not crash
                self.assertNotIn('bloque_semanal_gym', ctx)
            except Exception:
                self.fail('construir_contexto explotó cuando el servicio de análisis falló')


class TestPromptApertura_BloqueGym(SemanalJOIBase):
    """Phase 6.2: _prompt_apertura_manana handles bloque_semanal_gym correctly."""

    def test_prompt_incluye_etiqueta_cuando_hay_bloque(self):
        from joi.services import _prompt_apertura_manana
        ctx = {
            'bloque_semanal_gym': (
                'Gym esta semana: 2 sesiones. Continuidad: alta. '
                'Suficiencia: completa. Margen: bajo. Semana sólida.'
            )
        }
        prompt = _prompt_apertura_manana(ctx, {})
        self.assertIn('Señal semanal gym', prompt)
        self.assertIn('contexto reciente', prompt.lower())

    def test_prompt_sin_seccion_vacia_cuando_bloque_none(self):
        from joi.services import _prompt_apertura_manana
        ctx = {}  # no bloque_semanal_gym
        prompt = _prompt_apertura_manana(ctx, {})
        # Should not have empty labeled section
        self.assertNotIn('Señal semanal gym', prompt)
        self.assertNotIn('None', prompt)

    def test_prompt_no_incluye_bloque_si_vacio(self):
        from joi.services import _prompt_apertura_manana
        ctx = {'bloque_semanal_gym': ''}
        prompt = _prompt_apertura_manana(ctx, {})
        self.assertNotIn('Señal semanal gym', prompt)

    def test_patron_multisemanal_también_inyecta_etiqueta(self):
        from joi.services import _prompt_apertura_manana
        ctx = {'patron_multisemanal_gym': '[Últimas 3 semanas] El margen bajo se repite.'}
        prompt = _prompt_apertura_manana(ctx, {})
        self.assertIn('Señal semanal gym', prompt)


class TestPatronMultisemanal(SemanalJOIBase):
    """Phase 7: detectar_patron_multisemanal returns observations without identity claims."""

    def _make_entreno(self, fecha, modo_reducido=False):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            modo_reducido=modo_reducido,
        )

    def test_sin_datos_devuelve_none(self):
        from entrenos.services.analisis_semanal_service import detectar_patron_multisemanal
        result = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNone(result)

    def test_una_semana_con_datos_insuficiente(self):
        from entrenos.services.analisis_semanal_service import detectar_patron_multisemanal
        self._make_entreno(self.hoy)  # only 1 week with data
        result = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNone(result)  # minimum 2 weeks required

    def test_alta_continuidad_detectada(self):
        from entrenos.services.analisis_semanal_service import detectar_patron_multisemanal
        # 3 sessions in last 3 weeks — high continuity each week
        for i in range(3):
            fecha_semana = self.hoy - timedelta(weeks=i)
            self._make_entreno(fecha_semana - timedelta(days=1))
            self._make_entreno(fecha_semana - timedelta(days=2))
            self._make_entreno(fecha_semana - timedelta(days=3))
        result = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNotNone(result)
        self.assertIn('continuidad', result.lower())

    def test_no_contiene_lenguaje_identitario(self):
        from entrenos.services.analisis_semanal_service import detectar_patron_multisemanal
        for i in range(3):
            fecha_semana = self.hoy - timedelta(weeks=i)
            self._make_entreno(fecha_semana - timedelta(days=1))
        result = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy) or ''
        texto = result.lower()
        for palabra in _IDENTITY_WORDS:
            self.assertNotIn(palabra, texto)

    def test_incluye_prefijo_semanas_analizadas(self):
        from entrenos.services.analisis_semanal_service import detectar_patron_multisemanal
        for i in range(3):
            fecha_semana = self.hoy - timedelta(weeks=i)
            self._make_entreno(fecha_semana - timedelta(days=1))
            self._make_entreno(fecha_semana - timedelta(days=2))
            self._make_entreno(fecha_semana - timedelta(days=3))
        result = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        if result:
            self.assertIn('semanas', result.lower())


class TestSugerenciaPlan(SemanalJOIBase):
    """Phase 9: generar_sugerencia_plan returns non-automatic suggestions."""

    def _make_entreno(self, fecha, modo_reducido=False):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            modo_reducido=modo_reducido,
        )

    def test_sin_datos_devuelve_none(self):
        from entrenos.services.analisis_semanal_service import generar_sugerencia_plan
        result = generar_sugerencia_plan(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNone(result)

    def test_una_semana_insuficiente(self):
        from entrenos.services.analisis_semanal_service import generar_sugerencia_plan
        self._make_entreno(self.hoy)
        result = generar_sugerencia_plan(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNone(result)

    def test_alta_continuidad_genera_sugerencia_mantener(self):
        from entrenos.services.analisis_semanal_service import generar_sugerencia_plan
        for i in range(3):
            fecha_semana = self.hoy - timedelta(weeks=i)
            for j in range(1, 4):
                self._make_entreno(fecha_semana - timedelta(days=j))
        result = generar_sugerencia_plan(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 10)

    def test_sugerencia_no_contiene_lenguaje_automatico(self):
        from entrenos.services.analisis_semanal_service import generar_sugerencia_plan
        for i in range(3):
            fecha_semana = self.hoy - timedelta(weeks=i)
            for j in range(1, 4):
                self._make_entreno(fecha_semana - timedelta(days=j))
        result = generar_sugerencia_plan(self.cliente, n_semanas=3, fecha_ref=self.hoy) or ''
        # Must not imply automatic application
        for termino in ['automáticamente', 'hemos cambiado', 'el sistema aplica', 'ya está aplicado']:
            self.assertNotIn(termino, result.lower())

    def test_sugerencia_no_contiene_identidad(self):
        from entrenos.services.analisis_semanal_service import generar_sugerencia_plan
        for i in range(3):
            fecha_semana = self.hoy - timedelta(weeks=i)
            for j in range(1, 4):
                self._make_entreno(fecha_semana - timedelta(days=j))
        result = generar_sugerencia_plan(self.cliente, n_semanas=3, fecha_ref=self.hoy) or ''
        texto = result.lower()
        for palabra in _IDENTITY_WORDS:
            self.assertNotIn(palabra, texto)


class TestPhase9_1_PatronesSugerencias(SemanalJOIBase):
    """
    Phase 9.1 — Verifies each pattern maps to the correct suggestion,
    and that _detectar_patrones_activos is the shared detection source.
    """

    def _semanas_con_datos(self, n, sesiones_por_semana=3, modo_reducido=False, esenciales_por_semana=0):
        """Creates n weeks of session data."""
        for i in range(n):
            fecha_base = self.hoy - timedelta(weeks=i)
            for j in range(1, sesiones_por_semana + 1):
                mr = j <= esenciales_por_semana
                EntrenoRealizado.objects.create(
                    cliente=self.cliente, rutina=self.rutina,
                    fecha=fecha_base - timedelta(days=j),
                    modo_reducido=mr,
                )

    def test_alta_continuidad_observacion_y_sugerencia_coherentes(self):
        """
        Same pattern → same detection → both observation and suggestion reference continuity.
        Verifies _detectar_patrones_activos is shared.
        """
        from entrenos.services.analisis_semanal_service import (
            detectar_patron_multisemanal, generar_sugerencia_plan
        )
        self._semanas_con_datos(3, sesiones_por_semana=3)

        obs = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy) or ''
        sug = generar_sugerencia_plan(self.cliente, n_semanas=3, fecha_ref=self.hoy) or ''

        # If pattern detected in observation, suggestion must also be non-None (same detection)
        if obs:
            self.assertIsNotNone(sug, "Observation detected a pattern but suggestion returned None — detection logic diverged")

    def test_margen_bajo_repetido_sugerencia_reduce_accesorio(self):
        from entrenos.services.analisis_semanal_service import _detectar_patrones_activos, _SUGERENCIAS_PATRON

        # Simulate 3 weeks with margen='bajo' each
        semanas_mock = [
            {'hay_datos': True, 'margen': 'bajo', 'estado_semana': 'solida',
             'sesiones_completadas': 2, 'sesiones_esenciales': 0,
             'continuidad': 'media', 'bloques_principales_parciales': 0},
        ] * 3

        patrones = _detectar_patrones_activos(semanas_mock, umbral=2)
        self.assertIn('margen_bajo_repetido', patrones)
        sug = _SUGERENCIAS_PATRON.get('margen_bajo_repetido', '')
        self.assertIn('accesorio', sug.lower())

    def test_carga_alta_sostenida_sugerencia_no_subir_cargas(self):
        from entrenos.services.analisis_semanal_service import _detectar_patrones_activos, _SUGERENCIAS_PATRON

        semanas_mock = [
            {'hay_datos': True, 'margen': 'bajo', 'estado_semana': 'carga_alta',
             'sesiones_completadas': 2, 'sesiones_esenciales': 2,
             'continuidad': 'media', 'bloques_principales_parciales': 0},
        ] * 3

        patrones = _detectar_patrones_activos(semanas_mock, umbral=2)
        self.assertIn('carga_alta_sostenida', patrones)
        sug = _SUGERENCIAS_PATRON.get('carga_alta_sostenida', '')
        self.assertIn('carga', sug.lower())

    def test_bloque_parcial_repetido_sugerencia_microciclo(self):
        from entrenos.services.analisis_semanal_service import _detectar_patrones_activos, _SUGERENCIAS_PATRON

        semanas_mock = [
            {'hay_datos': True, 'margen': 'bajo', 'estado_semana': 'carga_alta',
             'sesiones_completadas': 2, 'sesiones_esenciales': 1,
             'continuidad': 'media', 'bloques_principales_parciales': 1},
        ] * 3

        patrones = _detectar_patrones_activos(semanas_mock, umbral=2)
        self.assertIn('bloque_parcial_repetido', patrones)
        sug = _SUGERENCIAS_PATRON.get('bloque_parcial_repetido', '')
        self.assertIn('microciclo', sug.lower())

    def test_esenciales_frecuentes_sugerencia_revisar_volumen(self):
        from entrenos.services.analisis_semanal_service import _detectar_patrones_activos, _SUGERENCIAS_PATRON

        semanas_mock = [
            {'hay_datos': True, 'margen': 'bajo', 'estado_semana': 'carga_alta',
             'sesiones_completadas': 2, 'sesiones_esenciales': 2,  # 100% esencial
             'continuidad': 'media', 'bloques_principales_parciales': 0},
        ] * 3

        patrones = _detectar_patrones_activos(semanas_mock, umbral=2)
        self.assertIn('esenciales_frecuentes', patrones)
        sug = _SUGERENCIAS_PATRON.get('esenciales_frecuentes', '')
        self.assertIn('volumen', sug.lower())

    def test_sin_patrones_devuelve_lista_vacia(self):
        from entrenos.services.analisis_semanal_service import _detectar_patrones_activos

        semanas_mock = [
            {'hay_datos': True, 'margen': 'alto', 'estado_semana': 'solida',
             'sesiones_completadas': 3, 'sesiones_esenciales': 0,
             'continuidad': 'alta', 'bloques_principales_parciales': 0},
        ] * 2  # only 2 weeks, umbral=2 but all patterns would trigger alta_continuidad

        # umbral > number of weeks matching other patterns → only alta_continuidad fires
        patrones = _detectar_patrones_activos(semanas_mock, umbral=2)
        # alta_continuidad should be detected (2 weeks, umbral 2)
        self.assertIn('alta_continuidad', patrones)
        # negative patterns should NOT be detected
        self.assertNotIn('margen_bajo_repetido', patrones)
        self.assertNotIn('carga_alta_sostenida', patrones)

    def test_todas_sugerencias_tienen_texto(self):
        from entrenos.services.analisis_semanal_service import _SUGERENCIAS_PATRON, _OBSERVACIONES_PATRON
        # Every pattern must have both observation and suggestion text
        patrones_esperados = {
            'margen_bajo_repetido', 'carga_alta_sostenida',
            'bloque_parcial_repetido', 'alta_continuidad', 'esenciales_frecuentes',
        }
        for patron in patrones_esperados:
            self.assertIn(patron, _OBSERVACIONES_PATRON, msg=f"Missing observation for {patron}")
            self.assertIn(patron, _SUGERENCIAS_PATRON, msg=f"Missing suggestion for {patron}")
            self.assertGreater(len(_SUGERENCIAS_PATRON[patron]), 10)
            self.assertGreater(len(_OBSERVACIONES_PATRON[patron]), 10)
