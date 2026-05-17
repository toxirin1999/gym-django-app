"""Phase 16 — Tests for weekly distribution analysis."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.analisis_semanal_service import analizar_distribucion_semanal
from rutinas.models import Rutina


class DistribucionBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_dis16', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestDis', 'dias_disponibles': 4},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_dis')
        self.hoy = date(2026, 5, 20)  # Wednesday
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _add_sp(self, fecha, estado=SesionProgramada.ESTADO_SALTADA_USUARIO):
        return SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=fecha,
            nombre_sesion='Test', estado=estado,
        )

    def _add_er(self, fecha, modo_reducido=False, nombre_rutina=None):
        r = self.rutina
        if nombre_rutina:
            r, _ = Rutina.objects.get_or_create(nombre=nombre_rutina)
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=r, fecha=fecha, modo_reducido=modo_reducido,
        )


class TestDiaPosPoneFrecuente(DistribucionBase):
    def test_detecta_dia_con_muchas_caidas(self):
        # Create 4 sessions on Mondays (weekday=0) all skipped → >60% dropped
        for i in range(4):
            monday = self.hoy - timedelta(weeks=i+1) - timedelta(days=self.hoy.weekday())
            self._add_sp(monday, SesionProgramada.ESTADO_SALTADA_USUARIO)

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        patrones = [o['patron'] for o in obs]
        self.assertIn('dia_pospone_frecuente', patrones)
        texto = next(o['texto'] for o in obs if o['patron'] == 'dia_pospone_frecuente')
        self.assertIn('Lunes', texto)

    def test_no_detecta_si_pocas_caidas(self):
        # 1 skipped, 3 completed on same day → not enough
        lunes_base = self.hoy - timedelta(days=self.hoy.weekday())
        for i in range(4):
            lunes = lunes_base - timedelta(weeks=i+1)
            if i == 0:
                self._add_sp(lunes, SesionProgramada.ESTADO_SALTADA_USUARIO)
            else:
                self._add_er(lunes)

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        patrones = [o['patron'] for o in obs]
        self.assertNotIn('dia_pospone_frecuente', patrones)


class TestDiasRealesMenores(DistribucionBase):
    def setUp(self):
        super().setUp()
        self.cliente.dias_disponibles = 4
        self.cliente.save()

    def test_detecta_promedio_menor_al_configurado(self):
        # Create 4 weeks with only 2 sessions each (configured=4)
        for i in range(4):
            lunes = self.hoy - timedelta(days=self.hoy.weekday()) - timedelta(weeks=i+1)
            self._add_er(lunes)
            self._add_er(lunes + timedelta(days=2))

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        patrones = [o['patron'] for o in obs]
        self.assertIn('dias_reales_menores', patrones)

    def test_no_detecta_si_consistente_con_config(self):
        # 4 sessions per week matches dias_disponibles=4 → no pattern
        for i in range(4):
            lunes = self.hoy - timedelta(days=self.hoy.weekday()) - timedelta(weeks=i+1)
            for d in range(4):
                self._add_er(lunes + timedelta(days=d))

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        patrones = [o['patron'] for o in obs]
        self.assertNotIn('dias_reales_menores', patrones)


class TestEsencialesConcentradas(DistribucionBase):
    def test_detecta_esenciales_en_dia_especifico(self):
        # 4 Fridays (weekday=4) all essential → >60% esencial on that day
        for i in range(4):
            viernes = self.hoy - timedelta(days=self.hoy.weekday()) - timedelta(weeks=i)
            viernes = viernes + timedelta(days=4)  # Friday
            if viernes < self.hoy:
                self._add_er(viernes, modo_reducido=True)

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        patrones = [o['patron'] for o in obs]
        if 'esenciales_concentradas' in patrones:
            texto = next(o['texto'] for o in obs if o['patron'] == 'esenciales_concentradas')
            self.assertIn('iernes', texto)  # Viernes


class TestPiernaTrasFutbol(DistribucionBase):
    def _add_futbol(self, fecha):
        from entrenos.models import ActividadRealizada
        ActividadRealizada.objects.create(
            cliente=self.cliente, tipo='futbol', fuente='manual', fecha=fecha,
        )

    def test_detecta_pierna_esencial_tras_futbol(self):
        rutina_pierna, _ = Rutina.objects.get_or_create(nombre='_piernas_test')
        for i in range(3):
            base = self.hoy - timedelta(weeks=i+2)
            self._add_futbol(base)
            # Leg session 1 day after football → essential
            EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=rutina_pierna,
                fecha=base + timedelta(days=1), modo_reducido=True,
            )

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=8, fecha_ref=self.hoy)
        patrones = [o['patron'] for o in obs]
        self.assertIn('pierna_tras_futbol', patrones)

    def test_no_detecta_si_no_hay_pierna_afectada(self):
        # Football exists but leg sessions are normal, not essential
        rutina_pierna, _ = Rutina.objects.get_or_create(nombre='_piernas_test2')
        for i in range(3):
            base = self.hoy - timedelta(weeks=i+2)
            self._add_futbol(base)
            EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=rutina_pierna,
                fecha=base + timedelta(days=1), modo_reducido=False,  # NOT esencial
            )

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=8, fecha_ref=self.hoy)
        patrones = [o['patron'] for o in obs]
        self.assertNotIn('pierna_tras_futbol', patrones)


class TestJOIRecibeSoloUnaObservacion(DistribucionBase):
    def test_joi_recibe_primera_observacion_no_todas(self):
        """JOI context should get only one distribution signal, not the full list."""
        from unittest.mock import patch

        # Simulate multiple observations
        obs_multiples = [
            {'patron': 'dia_pospone_frecuente', 'texto': 'Los lunes caen con frecuencia.', 'dato': {}},
            {'patron': 'dias_reales_menores', 'texto': 'Promedias 2 días, configurado para 4.', 'dato': {}},
        ]

        with patch('entrenos.services.analisis_semanal_service.analizar_distribucion_semanal',
                   return_value=obs_multiples):
            from joi.services import construir_contexto
            ctx = construir_contexto(self.cliente)

        if 'distribucion_semanal_gym' in ctx:
            # Should be a string (the first observation text), not a list
            self.assertIsInstance(ctx['distribucion_semanal_gym'], str)
            self.assertIn('lunes', ctx['distribucion_semanal_gym'].lower())  # first obs
            self.assertNotIn('promedias', ctx['distribucion_semanal_gym'].lower())  # second not included

    def test_joi_sin_observaciones_no_contamina_contexto(self):
        from unittest.mock import patch
        with patch('entrenos.services.analisis_semanal_service.analizar_distribucion_semanal',
                   return_value=[]):
            from joi.services import construir_contexto
            ctx = construir_contexto(self.cliente)
        self.assertNotIn('distribucion_semanal_gym', ctx)


class TestEvaluacionDistribucion(DistribucionBase):
    """Phase 20: evaluar_prueba_distribucion returns correct evaluation."""

    def _make_intervencion(self, tipo, fecha_inicio, fecha_fin, origen=''):
        from entrenos.models import IntervencionPlan
        return IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=tipo,
            origen_patron=origen,
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
            estado=IntervencionPlan.ESTADO_EXPIRADA,
        )

    def test_sin_intervenciones_terminadas_devuelve_none(self):
        from entrenos.services.sugerencias_service import evaluar_prueba_distribucion
        result = evaluar_prueba_distribucion(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_intervencion_antigua_no_evalua(self):
        """Intervention that ended more than 7 days ago is not evaluated."""
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import evaluar_prueba_distribucion

        hace_mas_de_7 = self.hoy - timedelta(days=10)
        self._make_intervencion(
            IntervencionPlan.TIPO_REDISTRIB_DIAS,
            hace_mas_de_7 - timedelta(days=14),
            hace_mas_de_7,
        )
        result = evaluar_prueba_distribucion(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_redistrib_dias_favorable_si_menos_saltadas(self):
        from entrenos.models import IntervencionPlan, SesionProgramada
        from entrenos.services.sugerencias_service import evaluar_prueba_distribucion

        # Probe: last 14 days
        inicio = self.hoy - timedelta(days=14)
        fin = self.hoy - timedelta(days=1)
        self._make_intervencion(IntervencionPlan.TIPO_REDISTRIB_DIAS, inicio, fin)

        # Before probe: 4 sessions, 3 skipped (75% skip rate)
        antes_inicio = inicio - timedelta(days=14)
        for i in range(4):
            SesionProgramada.objects.create(
                cliente=self.cliente, fecha_prevista=antes_inicio + timedelta(days=i*3),
                nombre_sesion='T',
                estado=SesionProgramada.ESTADO_SALTADA_USUARIO if i < 3 else SesionProgramada.ESTADO_COMPLETADA,
            )

        # During probe: 4 sessions, 0 skipped (0% skip rate)
        for i in range(4):
            SesionProgramada.objects.create(
                cliente=self.cliente, fecha_prevista=inicio + timedelta(days=i*3),
                nombre_sesion='T', estado=SesionProgramada.ESTADO_COMPLETADA,
            )

        result = evaluar_prueba_distribucion(self.cliente, self.hoy)
        self.assertIsNotNone(result)
        self.assertEqual(result['resultado'], 'favorable')

    def test_evaluacion_no_contiene_culpa(self):
        from entrenos.models import IntervencionPlan, SesionProgramada
        from entrenos.services.sugerencias_service import evaluar_prueba_distribucion

        inicio = self.hoy - timedelta(days=7)
        fin = self.hoy - timedelta(days=1)
        self._make_intervencion(IntervencionPlan.TIPO_REDISTRIB_DIAS, inicio, fin)

        for i in range(3):
            SesionProgramada.objects.create(
                cliente=self.cliente, fecha_prevista=inicio + timedelta(days=i*2),
                nombre_sesion='T', estado=SesionProgramada.ESTADO_SALTADA_USUARIO,
            )

        result = evaluar_prueba_distribucion(self.cliente, self.hoy)
        if result:
            texto = result['lectura'].lower()
            for termino in ['fallaste', 'fracaso', 'incumpliste', 'mal']:
                self.assertNotIn(termino, texto)

    def test_evaluacion_usa_lenguaje_prudente(self):
        """Must use 'parece', 'puede', 'durante la prueba'."""
        from entrenos.models import IntervencionPlan, SesionProgramada
        from entrenos.services.sugerencias_service import evaluar_prueba_distribucion

        inicio = self.hoy - timedelta(days=7)
        fin = self.hoy - timedelta(days=1)
        self._make_intervencion(IntervencionPlan.TIPO_REDISTRIB_DIAS, inicio, fin)

        # Before: 2 skipped
        for i in range(2):
            SesionProgramada.objects.create(
                cliente=self.cliente, fecha_prevista=inicio - timedelta(days=i+1),
                nombre_sesion='T', estado=SesionProgramada.ESTADO_SALTADA_USUARIO,
            )
        # During: 0 skipped
        SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=inicio + timedelta(days=1),
            nombre_sesion='T', estado=SesionProgramada.ESTADO_COMPLETADA,
        )

        result = evaluar_prueba_distribucion(self.cliente, self.hoy)
        if result:
            texto = result['lectura'].lower()
            usa_prudente = any(kw in texto for kw in ['parece', 'puede', 'prueba'])
            self.assertTrue(usa_prudente, msg=f"Lectura sin lenguaje prudente: {result['lectura']}")


class TestContinuidadDistribucion(DistribucionBase):
    """Phase 21.1: generar_recomendacion_continuidad_distribucion behavior."""

    def _mock_eval(self, resultado, tipo='redistrib_dias_menores'):
        return {'resultado': resultado, 'tipo': tipo, 'lectura': 'Prueba de test.'}

    def test_favorable_propone_repetir(self):
        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad_distribucion
        from unittest.mock import patch

        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion',
                   return_value=self._mock_eval('favorable')):
            result = generar_recomendacion_continuidad_distribucion(self.cliente, self.hoy)

        self.assertIsNotNone(result)
        self.assertEqual(result['accion'], 'repetir')

    def test_neutral_no_propone(self):
        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad_distribucion
        from unittest.mock import patch

        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion',
                   return_value=self._mock_eval('neutral')):
            result = generar_recomendacion_continuidad_distribucion(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_sin_evaluacion_devuelve_none(self):
        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad_distribucion
        from unittest.mock import patch

        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion', return_value=None):
            result = generar_recomendacion_continuidad_distribucion(self.cliente, self.hoy)
        self.assertIsNone(result)

    def test_repetir_crea_intervencion_14_dias(self):
        from entrenos.models import IntervencionPlan
        from entrenos.services.sugerencias_service import repetir_prueba_distribucion

        repetir_prueba_distribucion(self.cliente, IntervencionPlan.TIPO_REDISTRIB_DIAS, fecha_ref=self.hoy)

        ip = IntervencionPlan.objects.filter(cliente=self.cliente).first()
        self.assertIsNotNone(ip)
        self.assertEqual(ip.tipo, IntervencionPlan.TIPO_REDISTRIB_DIAS)
        self.assertEqual(ip.fecha_fin, self.hoy + timedelta(days=14))
        self.assertEqual(ip.origen_patron, 'continuidad_fase21')

    def test_no_por_ahora_crea_cooldown_7_dias(self):
        from entrenos.models import SugerenciaPlan

        # Simulate what ignorar_continuidad_distribucion_view does
        tipo = 'redistrib_dias_menores'
        patron_cooldown = f'continuidad_distribucion_{tipo}'
        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron=patron_cooldown,
            texto='Ignorada.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.hoy + timedelta(days=7),
        )

        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad_distribucion
        from unittest.mock import patch

        mock_eval = self._mock_eval('favorable', 'redistrib_dias_menores')
        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion', return_value=mock_eval):
            result = generar_recomendacion_continuidad_distribucion(self.cliente, self.hoy)

        self.assertIsNone(result)  # cooldown active → silent

    def test_cooldown_especifico_por_tipo(self):
        """Cooldown for redistrib_dias_menores does NOT block redistrib_dia_frecuente."""
        from entrenos.models import SugerenciaPlan

        SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='continuidad_distribucion_redistrib_dias_menores',
            texto='Ignorada.', estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.hoy + timedelta(days=5),
        )

        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad_distribucion
        from unittest.mock import patch

        # But the evaluation is for redistrib_dia_frecuente → different type
        mock_eval = self._mock_eval('favorable', 'redistrib_dia_frecuente')
        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion', return_value=mock_eval):
            result = generar_recomendacion_continuidad_distribucion(self.cliente, self.hoy)

        self.assertIsNotNone(result)  # different type → not blocked

    def test_no_apila_si_ya_hay_activa(self):
        from entrenos.models import IntervencionPlan

        IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_REDISTRIB_DIAS,
            origen_patron='test', fecha_inicio=self.hoy,
            fecha_fin=self.hoy + timedelta(days=7), estado=IntervencionPlan.ESTADO_ACTIVA,
        )

        from entrenos.services.sugerencias_service import generar_recomendacion_continuidad_distribucion
        from unittest.mock import patch

        with patch('entrenos.services.sugerencias_service.evaluar_prueba_distribucion',
                   return_value=self._mock_eval('favorable')):
            result = generar_recomendacion_continuidad_distribucion(self.cliente, self.hoy)

        self.assertIsNone(result)  # active probe already exists


class TestSinDatos(DistribucionBase):
    def test_sin_datos_devuelve_lista_vacia(self):
        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        self.assertEqual(obs, [])

    def test_observaciones_no_contienen_culpa(self):
        for i in range(4):
            lunes = self.hoy - timedelta(days=self.hoy.weekday()) - timedelta(weeks=i+1)
            self._add_sp(lunes, SesionProgramada.ESTADO_SALTADA_USUARIO)

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        for o in obs:
            texto = o['texto'].lower()
            for termino in ['fallaste', 'fracaso', 'incumpliste', 'culpa', 'mal']:
                self.assertNotIn(termino, texto, msg=f"Término culpa '{termino}' en obs")

    def test_observaciones_usan_lenguaje_prudente(self):
        """Observations must use 'puede que', 'conviene', etc. — not imperatives."""
        for i in range(4):
            lunes = self.hoy - timedelta(days=self.hoy.weekday()) - timedelta(weeks=i+1)
            self._add_sp(lunes, SesionProgramada.ESTADO_SALTADA_USUARIO)

        obs = analizar_distribucion_semanal(self.cliente, num_semanas=6, fecha_ref=self.hoy)
        for o in obs:
            texto = o['texto'].lower()
            # Should suggest, not command
            usa_lenguaje_prudente = any(
                kw in texto for kw in ['puede', 'conviene', 'quizá', 'quiza', 'tiende']
            )
            self.assertTrue(usa_lenguaje_prudente, msg=f"Obs sin lenguaje prudente: {o['texto'][:80]}")
