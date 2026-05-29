"""
Phase 14.1 — Panel UX regression tests.

Verifies the 10 context scenarios that determine card visibility:
1.  Sin datos semanales → SEM y OBS no aparecen
2.  Semana con datos, sin patrón → SEM visible, OBS no
3.  Patrón con sugerencia pendiente → OBS visible con patrón + sugerencia
4.  Patrón con sugerencia en cooldown → OBS sin sugerencia
5.  Evaluación de intervención → dentro de OBS
6.  Recomendación de continuidad → dentro de OBS, visualmente secundaria
7.  Sesión esencial → texto "esencial", nunca "modo_reducido"
8.  Sin patrón → OBS nunca aparece
9.  Freno activo → no satura el panel (no se muestra como contexto primario)
10. Lenguaje: "modo_reducido" no aparece en texto visible al usuario
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import SesionProgramada, SugerenciaPlan, IntervencionPlan
from entrenos.services.analisis_semanal_service import analizar_semana_entrenamiento
from entrenos.services.sugerencias_service import (
    get_sugerencia_activa, generar_recomendacion_continuidad,
)
from rutinas.models import Rutina


class PanelUXBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_ux14', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestUX', 'dias_disponibles': 4},
        )
        self.hoy = date(2026, 5, 20)
        cache.clear()

    def tearDown(self):
        cache.clear()


# ── Escenario 1 & 8: Sin datos semanales / Sin patrón ────────────────────────

class TestEscenario1_SinDatos(PanelUXBase):
    def test_analisis_sin_datos_devuelve_hay_datos_false(self):
        result = analizar_semana_entrenamiento(self.cliente, self.hoy)
        self.assertFalse(result['hay_datos'])

    def test_patron_sin_datos_devuelve_none(self):
        from entrenos.services.analisis_semanal_service import detectar_patron_multisemanal
        result = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNone(result)

    def test_sugerencia_sin_datos_devuelve_none(self):
        result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNone(result)


# ── Escenario 2: Semana con datos, sin patrón ─────────────────────────────────

class TestEscenario2_SemanaConDatosSinPatron(PanelUXBase):
    def setUp(self):
        super().setUp()
        from entrenos.models import EntrenoRealizado
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_ux')
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy
        )

    def test_hay_datos_esta_semana(self):
        result = analizar_semana_entrenamiento(self.cliente, self.hoy)
        self.assertTrue(result['hay_datos'])

    def test_sin_patron_multisemanal(self):
        from entrenos.services.analisis_semanal_service import detectar_patron_multisemanal
        result = detectar_patron_multisemanal(self.cliente, n_semanas=3, fecha_ref=self.hoy)
        self.assertIsNone(result)


# ── Escenario 3: Patrón con sugerencia pendiente ──────────────────────────────

class TestEscenario3_PatronConSugerencia(PanelUXBase):
    def test_sugerencia_creada_cuando_patron_existe(self):
        from unittest.mock import patch
        mock_datos = {'patron': 'carga_alta_sostenida', 'texto': 'No subir cargas.'}
        with patch('entrenos.services.analisis_semanal_service.obtener_sugerencia_con_patron',
                   return_value=mock_datos):
            sugerencia = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNotNone(sugerencia)
        self.assertEqual(sugerencia.patron, 'carga_alta_sostenida')
        self.assertEqual(sugerencia.estado, SugerenciaPlan.ESTADO_PENDIENTE)

    def test_sugerencia_pendiente_es_visible(self):
        sugerencia = SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='carga_alta_sostenida',
            texto='No subir cargas.', estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
        mock_datos = {'patron': 'carga_alta_sostenida', 'texto': 'No subir cargas.'}
        with patch('entrenos.services.analisis_semanal_service.obtener_sugerencia_con_patron',
                   return_value=mock_datos):
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertEqual(result.id, sugerencia.id)


# ── Escenario 4: Patrón con sugerencia en cooldown ────────────────────────────

class TestEscenario4_SugerenciaEnCooldown(PanelUXBase):
    def test_sugerencia_en_cooldown_no_visible(self):
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='carga_alta_sostenida',
            texto='No subir.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.hoy + timedelta(days=3),
        )
        mock_datos = {'patron': 'carga_alta_sostenida', 'texto': 'No subir.'}
        with patch('entrenos.services.analisis_semanal_service.obtener_sugerencia_con_patron',
                   return_value=mock_datos):
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNone(result)


# ── Escenario 5/6: Evaluación e intervención ──────────────────────────────────

class TestEscenario56_EvaluacionContinuidad(PanelUXBase):
    def test_evaluacion_no_existe_sin_intervenciones(self):
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        result = evaluar_intervencion_semana(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_recomendacion_sin_evaluacion_es_none(self):
        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana',
                   return_value=None):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_recomendacion_con_intervencion_activa_es_none(self):
        IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='test', fecha_inicio=self.hoy,
            fecha_fin=self.hoy + timedelta(days=3), estado=IntervencionPlan.ESTADO_ACTIVA,
        )
        mock_eval = {'resultado': 'favorable', 'tipo_intervencion': 'no_subir_cargas', 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana',
                   return_value=mock_eval):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)
        self.assertIsNone(result)  # don't pile up


# ── Escenario 7: Sesión esencial — lenguaje correcto ─────────────────────────

class TestEscenario7_LenguajeEsencial(PanelUXBase):
    def test_analisis_usa_termino_esencial(self):
        """Weekly analysis counts 'sesiones_esenciales', not 'modo_reducido'."""
        from entrenos.models import EntrenoRealizado
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_ux')
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy, modo_reducido=True
        )
        result = analizar_semana_entrenamiento(self.cliente, self.hoy)
        # The key is 'sesiones_esenciales', not 'modo_reducido'
        self.assertIn('sesiones_esenciales', result)
        self.assertEqual(result['sesiones_esenciales'], 1)
        self.assertNotIn('modo_reducido', result)

    def test_bloque_semanal_joi_no_contiene_modo_reducido(self):
        from entrenos.models import EntrenoRealizado
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_ux')
        EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=self.hoy, modo_reducido=True
        )
        from entrenos.services.analisis_semanal_service import bloque_semanal_para_joi
        result = bloque_semanal_para_joi(self.cliente, self.hoy) or ''
        self.assertNotIn('modo_reducido', result.lower())
        self.assertNotIn('modo reducido', result.lower())


# ── Escenario 9: Freno activo no satura el panel ─────────────────────────────

class TestEscenario9_FrenoNoSatura(PanelUXBase):
    def test_freno_activo_no_aparece_en_analisis_semanal(self):
        """The progression brake doesn't leak into weekly analysis — they're separate layers."""
        from entrenos.services.progresion_contextual_service import evaluar_permiso_progresion
        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        # The freno result is a dict — it's not in analisis_semanal
        analisis = analizar_semana_entrenamiento(self.cliente, self.hoy)
        self.assertNotIn('permiso_progresion', analisis)
        self.assertNotIn('progresion_bloqueada', analisis)


# ── Escenario 10: Lenguaje — auditoría ───────────────────────────────────────

class TestEscenario10_LenguajeGeneral(PanelUXBase):
    def test_sugerencias_no_usan_modo_reducido(self):
        from entrenos.services.analisis_semanal_service import _SUGERENCIAS_PATRON
        for patron, texto in _SUGERENCIAS_PATRON.items():
            self.assertNotIn('modo_reducido', texto.lower(), msg=f"Sugerencia {patron} contiene 'modo_reducido'")
            self.assertNotIn('modo reducido', texto.lower())

    def test_observaciones_no_usan_modo_reducido(self):
        from entrenos.services.analisis_semanal_service import _OBSERVACIONES_PATRON
        for patron, texto in _OBSERVACIONES_PATRON.items():
            self.assertNotIn('modo_reducido', texto.lower())
            self.assertNotIn('modo reducido', texto.lower())

    def test_mensajes_progresion_no_usan_terminos_culpa(self):
        from entrenos.services.progresion_contextual_service import _MENSAJES_PROGRESION
        for clave, texto in _MENSAJES_PROGRESION.items():
            for termino in ['fallaste', 'fracaso', 'incumpliste', 'modo_reducido']:
                self.assertNotIn(termino, texto.lower(), msg=f"Mensaje '{clave}' contiene '{termino}'")


# ── Escenario 11: Bib card — métricas career (Phase 56.17) ───────────────────

class TestEscenario11_BibSesiones(PanelUXBase):
    """
    The bib card must show the real career session count, not 0.
    entrenos_count must be in the view context whenever there are sessions.
    """

    def _get(self):
        from django.test import Client as DjangoClient
        from django.urls import reverse
        c = DjangoClient()
        c.login(username='tester_ux14', password='x')
        return c.get(reverse('clientes:mockup_demo'))

    def test_entrenos_count_en_contexto_sin_sesiones(self):
        """Con 0 entrenos, entrenos_count=0 en contexto (no ausente)."""
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertIn('entrenos_count', response.context,
                      "entrenos_count debe estar siempre en el contexto del bib")
        self.assertEqual(response.context['entrenos_count'], 0)

    def test_entrenos_count_refleja_sesiones_reales(self):
        """Con 2 entrenos creados, entrenos_count=2."""
        from entrenos.models import EntrenoRealizado
        from rutinas.models import Rutina
        rutina, _ = Rutina.objects.get_or_create(nombre='_test_bib56')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=self.hoy)
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina,
                                        fecha=self.hoy - __import__('datetime').timedelta(days=1))
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['entrenos_count'], 2,
                         "entrenos_count debe reflejar las sesiones reales, no mostrar 0")
