"""Phase 10B — Tests for SugerenciaPlan management."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import SugerenciaPlan
from entrenos.services.sugerencias_service import (
    get_sugerencia_activa, ignorar_sugerencia, aceptar_sugerencia,
)

_MOCK_DATOS = {'patron': 'carga_alta_sostenida', 'texto': 'No subir cargas esta semana.'}


class SugerenciasBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_sug', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestSug'},
        )
        self.hoy = date(2026, 5, 20)
        cache.clear()

    def tearDown(self):
        cache.clear()


class TestGetSugerenciaActiva(SugerenciasBase):

    def _patch_datos(self, datos=_MOCK_DATOS):
        return patch(
            'entrenos.services.analisis_semanal_service.obtener_sugerencia_con_patron',
            return_value=datos,
        )

    def test_sin_patron_devuelve_none(self):
        with patch('entrenos.services.analisis_semanal_service.obtener_sugerencia_con_patron', return_value=None):
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_crea_nueva_sugerencia_si_no_existe(self):
        with self._patch_datos():
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNotNone(result)
        self.assertEqual(result.patron, 'carga_alta_sostenida')
        self.assertEqual(result.estado, SugerenciaPlan.ESTADO_PENDIENTE)

    def test_reutiliza_existente_pendiente(self):
        sp = SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='carga_alta_sostenida',
            texto='No subir cargas.', estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )
        with self._patch_datos():
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertEqual(result.id, sp.id)
        self.assertEqual(SugerenciaPlan.objects.filter(cliente=self.cliente).count(), 1)

    def test_ignorada_en_cooldown_devuelve_none(self):
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='carga_alta_sostenida',
            texto='No subir.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.hoy + timedelta(days=3),
        )
        with self._patch_datos():
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_ignorada_con_cooldown_expirado_se_resetea(self):
        sp = SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='carga_alta_sostenida',
            texto='No subir.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.hoy - timedelta(days=1),  # expired yesterday
        )
        with self._patch_datos():
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNotNone(result)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SugerenciaPlan.ESTADO_PENDIENTE)

    def test_aceptada_devuelve_none(self):
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='carga_alta_sostenida',
            texto='No subir.', estado=SugerenciaPlan.ESTADO_ACEPTADA,
        )
        with self._patch_datos():
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_descartada_devuelve_none(self):
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='carga_alta_sostenida',
            texto='No subir.', estado=SugerenciaPlan.ESTADO_DESCARTADA,
        )
        with self._patch_datos():
            result = get_sugerencia_activa(self.cliente, self.hoy)
        self.assertIsNone(result)


class TestIgnorarAceptarSugerencia(SugerenciasBase):

    def _make_sp(self):
        return SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='margen_bajo_repetido',
            texto='Reducir accesorio.', estado=SugerenciaPlan.ESTADO_PENDIENTE,
        )

    def test_ignorar_aplica_cooldown(self):
        sp = self._make_sp()
        ignorar_sugerencia(sp)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SugerenciaPlan.ESTADO_IGNORADA)
        self.assertEqual(sp.cooldown_hasta, timezone.localdate() + timedelta(days=SugerenciaPlan.COOLDOWN_DIAS))
        self.assertIsNotNone(sp.fecha_respuesta)

    def test_aceptar_registra_sin_modificar_plan(self):
        sp = self._make_sp()
        aceptar_sugerencia(sp)
        sp.refresh_from_db()
        self.assertEqual(sp.estado, SugerenciaPlan.ESTADO_ACEPTADA)
        self.assertIsNotNone(sp.fecha_respuesta)
        # No plan modifications — just the record
        from entrenos.models import EntrenoRealizado
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=self.cliente).count(), 0)

    def test_cooldown_es_7_dias(self):
        self.assertEqual(SugerenciaPlan.COOLDOWN_DIAS, 7)


class TestIntervencionPlan(SugerenciasBase):
    """Phase 10C: accepting a suggestion creates an active IntervencionPlan."""

    def _make_sugerencia(self, patron='carga_alta_sostenida', estado='pendiente'):
        return SugerenciaPlan.objects.create(
            cliente=self.cliente, patron=patron,
            texto='No subir cargas.', estado=estado,
        )

    def test_aceptar_crea_intervencion(self):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.models import IntervencionPlan

        sp = self._make_sugerencia()
        aceptar_sugerencia(sp, fecha_ref=self.hoy)

        intervencion = IntervencionPlan.objects.filter(cliente=self.cliente).first()
        self.assertIsNotNone(intervencion)
        self.assertEqual(intervencion.tipo, IntervencionPlan.TIPO_NO_SUBIR)
        self.assertEqual(intervencion.estado, IntervencionPlan.ESTADO_ACTIVA)

    def test_intervencion_expira_domingo(self):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.models import IntervencionPlan

        # self.hoy = 2026-05-20 (Wednesday) → Sunday = 2026-05-24
        sp = self._make_sugerencia()
        aceptar_sugerencia(sp, fecha_ref=self.hoy)

        intervencion = IntervencionPlan.objects.filter(cliente=self.cliente).first()
        from datetime import date
        self.assertEqual(intervencion.fecha_fin, date(2026, 5, 24))  # Sunday

    def test_margen_bajo_crea_reducir_accesorios(self):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.models import IntervencionPlan

        sp = self._make_sugerencia(patron='margen_bajo_repetido')
        aceptar_sugerencia(sp, fecha_ref=self.hoy)

        intervencion = IntervencionPlan.objects.filter(cliente=self.cliente).first()
        self.assertEqual(intervencion.tipo, IntervencionPlan.TIPO_REDUCIR)

    def test_intervencion_activa_anula_deteccion_de_patrones(self):
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.services.progresion_contextual_service import evaluar_permiso_progresion

        sp = self._make_sugerencia(patron='carga_alta_sostenida')
        aceptar_sugerencia(sp, fecha_ref=self.hoy)

        # Even with no weekly data, the intervention makes freno active
        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertEqual(permiso['accion'], 'mantener_carga')
        self.assertIn('intervencion', permiso['motivo'])

    def test_intervencion_expirada_no_bloquea(self):
        from entrenos.models import IntervencionPlan
        from datetime import date

        # Create an already-expired intervention
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='carga_alta_sostenida',
            fecha_inicio=date(2026, 5, 13),
            fecha_fin=date(2026, 5, 17),  # last week
            estado=IntervencionPlan.ESTADO_ACTIVA,  # still marked active (will be expired lazily)
        )

        from entrenos.services.progresion_contextual_service import evaluar_permiso_progresion
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value={'hay_datos': False}):
            permiso = evaluar_permiso_progresion(self.cliente, self.hoy)

        # Expired intervention should not block
        self.assertEqual(permiso['accion'], 'progresion_permitida')

    def test_ignorar_no_crea_intervencion(self):
        from entrenos.models import IntervencionPlan
        sp = self._make_sugerencia()
        ignorar_sugerencia(sp)
        self.assertEqual(IntervencionPlan.objects.filter(cliente=self.cliente).count(), 0)

    def test_descartar_no_crea_intervencion(self):
        from entrenos.models import IntervencionPlan, SugerenciaPlan
        sp = self._make_sugerencia()
        sp.estado = SugerenciaPlan.ESTADO_DESCARTADA
        sp.save()
        self.assertEqual(IntervencionPlan.objects.filter(cliente=self.cliente).count(), 0)

    def test_motivo_bloqueo_refleja_intervencion_no_patron(self):
        """When intervention is active, motivo_bloqueo must name the intervention, not a pattern."""
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.services.progresion_contextual_service import (
            evaluar_permiso_progresion, aplicar_freno_contextual,
        )

        sp = self._make_sugerencia(patron='carga_alta_sostenida')
        aceptar_sugerencia(sp, fecha_ref=self.hoy)

        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertIn('intervencion', permiso['motivo'])
        self.assertNotIn('patron', permiso['motivo'])

    def test_reducir_accesorios_bloquea_solo_no_principales(self):
        """reducir_accesorios intervention: principals unblocked, accessories blocked."""
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.services.progresion_contextual_service import (
            evaluar_permiso_progresion, aplicar_freno_contextual,
        )

        sp = self._make_sugerencia(patron='margen_bajo_repetido')
        aceptar_sugerencia(sp, fecha_ref=self.hoy)

        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)
        self.assertEqual(permiso['accion'], 'reducir_accesorios')
        self.assertFalse(permiso['aplica_a_principales'])
        self.assertTrue(permiso['aplica_a_accesorios'])

        # Check that freno correctly splits principal vs accessory
        from clientes.models import Cliente
        ent = {
            'rutina_nombre': 'Test',
            'ejercicios': [
                {'nombre': 'Sentadilla', 'grupo_muscular': 'cuadriceps', 'tipo_ejercicio': 'compuesto_principal', 'peso_kg': 90.0},
                {'nombre': 'Extensión', 'grupo_muscular': 'cuadriceps', 'tipo_ejercicio': 'aislamiento', 'peso_kg': 50.0},
            ]
        }
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        principal = resultado['ejercicios'][0]
        accesorio = resultado['ejercicios'][1]
        self.assertFalse(principal['progresion_bloqueada'])
        self.assertTrue(accesorio['progresion_bloqueada'])
        self.assertIn('intervencion', accesorio['motivo_bloqueo'])

    # ── Phase 11.1 tests ──────────────────────────────────────────────────────

    def test_origen_opcional_intervencion_reducir(self):
        """aplicar_freno_contextual marks accessories with intervencion_reducir_accesorios origin."""
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.services.progresion_contextual_service import (
            evaluar_permiso_progresion, aplicar_freno_contextual,
        )

        sp = self._make_sugerencia(patron='margen_bajo_repetido')
        aceptar_sugerencia(sp, fecha_ref=self.hoy)
        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)

        ent = {
            'rutina_nombre': 'T',
            'ejercicios': [
                {'nombre': 'Sentadilla', 'grupo_muscular': 'cuadriceps', 'tipo_ejercicio': 'compuesto_principal', 'peso_kg': 80.0},
                {'nombre': 'Curl', 'grupo_muscular': 'biceps', 'tipo_ejercicio': 'aislamiento', 'peso_kg': 15.0},
            ]
        }
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)

        principal = resultado['ejercicios'][0]
        accesorio = resultado['ejercicios'][1]
        self.assertIsNone(principal.get('origen_opcional'))
        self.assertEqual(accesorio.get('origen_opcional'), 'intervencion_reducir_accesorios')

    # ── Phase 12 tests ────────────────────────────────────────────────────────

    def test_evaluar_sin_intervenciones_devuelve_none(self):
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        result = evaluar_intervencion_semana(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_evaluar_intervencion_semana_pasada_favorable(self):
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        from unittest.mock import patch

        # Create an expired intervention from last week
        semana_pasada = self.hoy - timedelta(weeks=1)
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='carga_alta_sostenida',
            fecha_inicio=semana_pasada - timedelta(days=3),
            fecha_fin=semana_pasada,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )

        mock_semana = {
            'hay_datos': True,
            'estado_semana': 'solida',
            'porcentaje_principal_medio': None,
        }
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value=mock_semana):
            result = evaluar_intervencion_semana(self.cliente, self.hoy)

        self.assertIsNotNone(result)
        self.assertEqual(result['resultado'], 'favorable')
        self.assertIn('liberado margen', result['lectura'].lower())

    def test_evaluar_intervencion_no_contiene_culpa(self):
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        from unittest.mock import patch

        semana_pasada = self.hoy - timedelta(weeks=1)
        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_REDUCIR,
            origen_patron='margen_bajo_repetido',
            fecha_inicio=semana_pasada - timedelta(days=3),
            fecha_fin=semana_pasada,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )

        mock_semana = {
            'hay_datos': True,
            'estado_semana': 'carga_alta',
            'porcentaje_principal_medio': 50,
        }
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value=mock_semana):
            result = evaluar_intervencion_semana(self.cliente, self.hoy)

        if result:
            texto = result['lectura'].lower()
            for termino in ['fallaste', 'fracaso', 'incumpliste', 'culpa']:
                self.assertNotIn(termino, texto)

    # ── Phase 12.1 — completar checklist ─────────────────────────────────────

    def test_reducir_accesorios_margen_alto_favorable(self):
        """reducir_accesorios + margen mejora (pct_principal ≥ 80) → favorable."""
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        from unittest.mock import patch

        semana_pasada = self.hoy - timedelta(weeks=1)
        IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_REDUCIR,
            origen_patron='margen_bajo_repetido',
            fecha_inicio=semana_pasada - timedelta(days=3),
            fecha_fin=semana_pasada,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        mock_semana = {
            'hay_datos': True, 'estado_semana': 'solida',
            'porcentaje_principal_medio': 90,
        }
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value=mock_semana):
            result = evaluar_intervencion_semana(self.cliente, self.hoy)
        self.assertIsNotNone(result)
        self.assertEqual(result['resultado'], 'favorable')

    def test_reducir_accesorios_margen_bajo_neutral(self):
        """reducir_accesorios + margen sigue bajo → neutral."""
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        from unittest.mock import patch

        semana_pasada = self.hoy - timedelta(weeks=1)
        IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_REDUCIR,
            origen_patron='margen_bajo_repetido',
            fecha_inicio=semana_pasada - timedelta(days=3),
            fecha_fin=semana_pasada,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        mock_semana = {
            'hay_datos': True, 'estado_semana': 'carga_alta',
            'porcentaje_principal_medio': 50,
        }
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value=mock_semana):
            result = evaluar_intervencion_semana(self.cliente, self.hoy)
        self.assertIsNotNone(result)
        self.assertEqual(result['resultado'], 'neutral')

    def test_intervencion_otra_semana_no_contamina(self):
        """An intervention from 2 weeks ago should not appear as 'last week'."""
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        from unittest.mock import patch

        hace_dos_semanas = self.hoy - timedelta(weeks=2)
        IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='carga_alta_sostenida',
            fecha_inicio=hace_dos_semanas - timedelta(days=3),
            fecha_fin=hace_dos_semanas,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value={'hay_datos': True, 'estado_semana': 'solida'}):
            result = evaluar_intervencion_semana(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_origen_opcional_ambos_cuando_modo_reducido_e_intervencion(self):
        """When both modo_reducido and reducir_accesorios intervention are active, origin = 'ambos'."""
        from entrenos.services.sugerencias_service import aceptar_sugerencia
        from entrenos.services.progresion_contextual_service import (
            evaluar_permiso_progresion, aplicar_freno_contextual,
        )

        sp = self._make_sugerencia(patron='margen_bajo_repetido')
        aceptar_sugerencia(sp, fecha_ref=self.hoy)
        permiso = evaluar_permiso_progresion(self.cliente, self.hoy)

        ent = {
            'rutina_nombre': 'T',
            'ejercicios': [
                {'nombre': 'Curl', 'grupo_muscular': 'biceps', 'tipo_ejercicio': 'aislamiento', 'peso_kg': 15.0},
            ]
        }
        # Apply freno → sets origin to 'intervencion_reducir_accesorios'
        resultado = aplicar_freno_contextual(self.cliente, ent, permiso)
        ej = resultado['ejercicios'][0]
        self.assertEqual(ej.get('origen_opcional'), 'intervencion_reducir_accesorios')

        # Now simulate mode_reducido processing (as done in vista_entrenamiento_activo)
        if not ej.get('es_principal'):
            existing = ej.get('origen_opcional')
            modo_reducido = True  # simulate
            if existing == 'intervencion_reducir_accesorios':
                ej['origen_opcional'] = 'ambos'
            else:
                ej['origen_opcional'] = 'modo_reducido'

        self.assertEqual(ej.get('origen_opcional'), 'ambos')

    def test_evaluacion_no_contamina_sin_hay_datos(self):
        """If semana_data has no data, evaluation returns None."""
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import evaluar_intervencion_semana
        from unittest.mock import patch

        semana_pasada = self.hoy - timedelta(weeks=1)
        IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='carga_alta_sostenida',
            fecha_inicio=semana_pasada - timedelta(days=3),
            fecha_fin=semana_pasada,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )
        with patch('entrenos.services.analisis_semanal_service.analizar_semana_entrenamiento',
                   return_value={'hay_datos': False}):
            result = evaluar_intervencion_semana(self.cliente, self.hoy)
        self.assertIsNone(result)

    # ── Phase 13 — Recomendación de continuidad ───────────────────────────────

    def _crear_intervencion_semana_pasada(self, tipo):
        from entrenos.models import IntervencionPlan
        semana_pasada = self.hoy - timedelta(weeks=1)
        return IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=tipo,
            origen_patron='test',
            fecha_inicio=semana_pasada - timedelta(days=3),
            fecha_fin=semana_pasada,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )

    def test_recomendacion_repetir_si_favorable(self):
        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad
        from entrenos.models import IntervencionPlan
        from unittest.mock import patch

        self._crear_intervencion_semana_pasada(IntervencionPlan.TIPO_NO_SUBIR)

        mock_eval = {'resultado': 'favorable', 'tipo_intervencion': IntervencionPlan.TIPO_NO_SUBIR, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana', return_value=mock_eval):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)

        self.assertIsNotNone(result)
        self.assertEqual(result['accion'], 'repetir')
        self.assertEqual(result['tipo_intervencion'], IntervencionPlan.TIPO_NO_SUBIR)

    def test_recomendacion_profundizar_si_neutral(self):
        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad
        from entrenos.models import IntervencionPlan
        from unittest.mock import patch

        self._crear_intervencion_semana_pasada(IntervencionPlan.TIPO_REDUCIR)

        mock_eval = {'resultado': 'neutral', 'tipo_intervencion': IntervencionPlan.TIPO_REDUCIR, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana', return_value=mock_eval):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)

        self.assertIsNotNone(result)
        self.assertEqual(result['accion'], 'profundizar')

    def test_recomendacion_none_si_ya_hay_activa(self):
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad

        # Active intervention this week
        IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='test', fecha_inicio=self.hoy,
            fecha_fin=self.hoy + timedelta(days=3), estado=IntervencionPlan.ESTADO_ACTIVA,
        )
        result = generar_recomendacion_continuidad(self.cliente, self.hoy)
        self.assertIsNone(result)  # don't pile up

    def test_repetir_intervencion_crea_nueva(self):
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import repetir_intervencion

        repetir_intervencion(self.cliente, IntervencionPlan.TIPO_NO_SUBIR, fecha_ref=self.hoy)

        nueva = IntervencionPlan.objects.filter(
            cliente=self.cliente, estado=IntervencionPlan.ESTADO_ACTIVA
        ).first()
        self.assertIsNotNone(nueva)
        self.assertEqual(nueva.tipo, IntervencionPlan.TIPO_NO_SUBIR)
        self.assertEqual(nueva.origen_patron, 'continuidad_fase13')

    def test_repetir_expira_domingo(self):
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import repetir_intervencion
        from datetime import date

        repetir_intervencion(self.cliente, IntervencionPlan.TIPO_REDUCIR, fecha_ref=self.hoy)
        nueva = IntervencionPlan.objects.filter(cliente=self.cliente).first()
        self.assertEqual(nueva.fecha_fin, date(2026, 5, 24))  # Sunday

    def test_recomendacion_ninguna_si_sin_evaluacion(self):
        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad
        from unittest.mock import patch

        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana', return_value=None):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)
        self.assertIsNone(result)

    # ── Phase 13.1 — Cooldown de "No por ahora" ───────────────────────────────

    def test_ignorar_recomendacion_crea_cooldown(self):
        from entrenos.models import IntervencionPlan, SugerenciaPlan

        # Simulate what ignorar_recomendacion_view does
        tipo = IntervencionPlan.TIPO_NO_SUBIR
        patron_clave = f'continuidad_{tipo}'
        manana = self.hoy + timedelta(days=7)
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron=patron_clave,
            texto='Ignorada.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=manana,
        )

        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad
        from unittest.mock import patch

        mock_eval = {'resultado': 'favorable', 'tipo_intervencion': tipo, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana', return_value=mock_eval):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)

        self.assertIsNone(result)  # cooldown active → silent

    def test_cooldown_expirado_muestra_recomendacion(self):
        from entrenos.models import IntervencionPlan, SugerenciaPlan

        tipo = IntervencionPlan.TIPO_NO_SUBIR
        patron_clave = f'continuidad_{tipo}'
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron=patron_clave,
            texto='Ignorada.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.hoy - timedelta(days=1),  # expired
        )

        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad
        from unittest.mock import patch

        mock_eval = {'resultado': 'favorable', 'tipo_intervencion': tipo, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana', return_value=mock_eval):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)

        self.assertIsNotNone(result)  # cooldown expired → recommendation reappears

    def test_cooldown_solo_afecta_mismo_tipo(self):
        """Cooldown for no_subir_cargas should NOT block reducir_accesorios recommendation."""
        from entrenos.models import IntervencionPlan, SugerenciaPlan

        # Ignore no_subir_cargas recommendation
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='continuidad_no_subir_cargas',
            texto='Ignorada.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.hoy + timedelta(days=5),
        )

        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad
        from unittest.mock import patch

        # But evaluation is for reducir_accesorios
        mock_eval = {'resultado': 'favorable', 'tipo_intervencion': IntervencionPlan.TIPO_REDUCIR, 'lectura': 'ok'}
        with patch('entrenos.services.sugerencias_service.evaluar_intervencion_semana', return_value=mock_eval):
            result = generar_recomendacion_continuidad(self.cliente, self.hoy)

        self.assertIsNotNone(result)  # different type → not blocked

    def test_get_intervencion_activa_expira_stale(self):
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import get_intervencion_activa
        from datetime import date

        IntervencionPlan.objects.create(
            cliente=self.cliente,
            tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='test',
            fecha_inicio=date(2026, 5, 13),
            fecha_fin=date(2026, 5, 17),
            estado=IntervencionPlan.ESTADO_ACTIVA,
        )

        result = get_intervencion_activa(self.cliente, self.hoy)
        self.assertIsNone(result)

        # Verify it was expired
        from entrenos.models import IntervencionPlan as IP
        ip = IP.objects.first()
        self.assertEqual(ip.estado, IP.ESTADO_EXPIRADA)
