from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, IntervencionPlan, SugerenciaPlan
from rutinas.models import Rutina


def snapshot():
    return {
        'version': 1, 'patron': 'esenciales_frecuentes', 'fecha_referencia': '2026-07-01',
        'vigente': True,
        'evidencia': {'ventana_semanas': 3, 'semanas_observadas': [
            {'desde': '2026-06-09', 'hasta': '2026-06-15', 'completadas': 2,
             'esenciales': 1, 'cumple_umbral': True},
            {'desde': '2026-06-16', 'hasta': '2026-06-22', 'completadas': 2,
             'esenciales': 1, 'cumple_umbral': True}], 'semanas_que_cumplen': 2},
        'cambio': {'codigo': 'freeze_load_increases', 'tipo_intervencion': 'no_subir_cargas',
                   'duracion_dias': 7},
        'unchanged': ['series'], 'evaluacion': {'criterio': 'comparar'},
    }


class CicloBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ciclo3b3', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Base 3B3')
        self.inicio = date(2026, 7, 1)

    def intervencion(self, estado=IntervencionPlan.ESTADO_ACTIVA):
        sug = SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='esenciales_frecuentes', texto='x',
            estado=SugerenciaPlan.ESTADO_ACEPTADA, contrato_snapshot=snapshot(),
        )
        return IntervencionPlan.objects.create(
            cliente=self.cliente, sugerencia=sug, tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='esenciales_frecuentes', fecha_inicio=self.inicio,
            fecha_fin=self.inicio + timedelta(days=6), estado=estado,
        )

    def sesion(self, fecha, esencial=False):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            modo_reducido=esencial, numero_ejercicios=1, volumen_total_kg=100,
        )


class ProductorTests(CicloBase):
    @patch('entrenos.services.ciclo_intervencion_esenciales_service.construir_contrato_sugerencia')
    def test_productor_crea_una_vez_con_evidencia_vigente(self, construir):
        contrato = snapshot(); construir.return_value = contrato
        from entrenos.services.ciclo_intervencion_esenciales_service import producir_sugerencia_tras_finalizacion
        primera = producir_sugerencia_tras_finalizacion(self.cliente.pk, self.inicio)
        segunda = producir_sugerencia_tras_finalizacion(self.cliente.pk, self.inicio)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(SugerenciaPlan.objects.filter(cliente=self.cliente, patron='esenciales_frecuentes').count(), 1)

    @patch('entrenos.services.ciclo_intervencion_esenciales_service.construir_contrato_sugerencia')
    def test_productor_respeta_cooldown_futuro_y_ajuste_activo(self, construir):
        construir.return_value = snapshot()
        ignorada = SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='esenciales_frecuentes', texto='x',
            estado=SugerenciaPlan.ESTADO_IGNORADA,
            cooldown_hasta=self.inicio + timedelta(days=2), contrato_snapshot=snapshot(),
        )
        from entrenos.services.ciclo_intervencion_esenciales_service import producir_sugerencia_tras_finalizacion
        self.assertIsNone(producir_sugerencia_tras_finalizacion(self.cliente.pk, self.inicio))
        ignorada.estado = SugerenciaPlan.ESTADO_ACEPTADA; ignorada.cooldown_hasta = None
        ignorada.save(update_fields=['estado', 'cooldown_hasta'])
        IntervencionPlan.objects.create(
            cliente=self.cliente, sugerencia=ignorada, tipo=IntervencionPlan.TIPO_NO_SUBIR,
            origen_patron='esenciales_frecuentes', fecha_inicio=self.inicio,
            fecha_fin=self.inicio + timedelta(days=6), estado=IntervencionPlan.ESTADO_ACTIVA,
        )
        self.assertIsNone(producir_sugerencia_tras_finalizacion(self.cliente.pk, self.inicio))

    @patch('entrenos.services.ciclo_intervencion_esenciales_service.construir_contrato_sugerencia')
    def test_nueva_evidencia_descarta_pendiente_anterior_y_crea_episodio(self, construir):
        vieja = snapshot()
        pendiente = SugerenciaPlan.objects.create(
            cliente=self.cliente, patron='esenciales_frecuentes', texto='x', contrato_snapshot=vieja,
        )
        nueva = snapshot(); nueva['evidencia'] = dict(nueva['evidencia'], semanas_que_cumplen=3)
        construir.return_value = nueva
        from entrenos.services.ciclo_intervencion_esenciales_service import producir_sugerencia_tras_finalizacion
        episodio = producir_sugerencia_tras_finalizacion(self.cliente.pk, self.inicio)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, SugerenciaPlan.ESTADO_DESCARTADA)
        self.assertNotEqual(episodio.pk, pendiente.pk)

    def test_crear_entreno_no_produce_sugerencia_prematuramente(self):
        self.sesion(self.inicio)
        self.assertFalse(SugerenciaPlan.objects.exists())

    @patch('entrenos.services.ciclo_intervencion_esenciales_service.producir_sugerencia_tras_finalizacion')
    def test_finalizador_programa_productor_solo_en_commit(self, producir):
        from entrenos.services.ciclo_intervencion_esenciales_service import programar_produccion_tras_finalizacion
        entreno = self.sesion(self.inicio)
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            programar_produccion_tras_finalizacion(entreno)
        producir.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        from django.utils import timezone
        producir.assert_called_once_with(self.cliente.pk, timezone.localdate())


class EvaluacionTests(CicloBase):
    def evaluar(self, fecha):
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        return evaluar_intervencion(self.intervencion(), fecha_ref=fecha, aplicar=True)

    def test_no_evalua_en_fecha_fin(self):
        iv = self.intervencion()
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        self.assertIsNone(evaluar_intervencion(iv, iv.fecha_fin, aplicar=True))

    def test_datos_insuficientes_con_menos_de_dos_sesiones(self):
        self.sesion(self.inicio)
        self.assertEqual(self.evaluar(self.inicio + timedelta(days=7))['resultado'], 'datos_insuficientes')

    def test_senal_reducida_si_esenciales_menor_cincuenta_por_ciento_y_limites_inclusivos(self):
        self.sesion(self.inicio, esencial=True)
        self.sesion(self.inicio + timedelta(days=6), esencial=False)
        self.sesion(self.inicio + timedelta(days=3), esencial=False)
        self.sesion(self.inicio - timedelta(days=1), esencial=True)
        self.sesion(self.inicio + timedelta(days=7), esencial=True)
        resultado = self.evaluar(self.inicio + timedelta(days=7))
        self.assertEqual(resultado['resultado'], 'senal_reducida')
        self.assertEqual(resultado['sesiones_completadas'], 3)

    def test_persistente_si_esenciales_al_menos_cincuenta_por_ciento_e_idempotente(self):
        iv = self.intervencion()
        self.sesion(self.inicio, esencial=True); self.sesion(self.inicio + timedelta(days=1), esencial=False)
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        a = evaluar_intervencion(iv, self.inicio + timedelta(days=7), aplicar=True)
        b = evaluar_intervencion(iv, self.inicio + timedelta(days=8), aplicar=True)
        self.assertEqual(a, b)
        iv.refresh_from_db(); iv.sugerencia.refresh_from_db()
        self.assertEqual(iv.estado, IntervencionPlan.ESTADO_EXPIRADA)
        self.assertEqual(iv.sugerencia.contrato_snapshot['evaluacion']['resultado'], 'persistente')

    def test_cancelada_no_se_evalua(self):
        iv = self.intervencion(IntervencionPlan.ESTADO_CANCELADA)
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        self.assertIsNone(evaluar_intervencion(iv, self.inicio + timedelta(days=20), aplicar=True))


class CancelacionYCentroTests(CicloBase):
    def setUp(self):
        super().setUp(); self.web = Client(); self.web.login(username='ciclo3b3', password='x')

    def test_cancelar_es_post_propietario_e_idempotente(self):
        iv = self.intervencion()
        from django.utils import timezone
        iv.fecha_inicio = timezone.localdate()
        iv.fecha_fin = timezone.localdate() + timedelta(days=6)
        iv.save(update_fields=['fecha_inicio', 'fecha_fin'])
        url = reverse('clientes:cancelar_intervencion_esenciales', args=[iv.pk])
        self.assertEqual(self.web.get(url).status_code, 405)
        self.assertEqual(self.web.post(url).status_code, 302)
        self.assertEqual(self.web.post(url).status_code, 302)
        iv.refresh_from_db(); self.assertEqual(iv.estado, IntervencionPlan.ESTADO_CANCELADA)
        self.assertEqual(iv.fecha_fin, timezone.localdate() + timedelta(days=6))

    def test_otro_usuario_no_puede_cancelar(self):
        iv = self.intervencion(); otro = User.objects.create_user('otro3b3', password='x')
        self.web.logout(); self.web.login(username='otro3b3', password='x')
        self.assertEqual(self.web.post(reverse('clientes:cancelar_intervencion_esenciales', args=[iv.pk])).status_code, 404)

    def test_get_centro_es_puro_y_muestra_copy_humano(self):
        before = (SugerenciaPlan.objects.count(), IntervencionPlan.objects.count())
        response = self.web.get(reverse('clientes:plan_decisiones'))
        self.assertEqual(before, (SugerenciaPlan.objects.count(), IntervencionPlan.objects.count()))
        self.assertContains(response, 'El plan no necesita ninguna decisión tuya ahora')

    def test_resultado_historico_no_se_presenta_como_activo(self):
        iv = self.intervencion(); self.sesion(self.inicio); self.sesion(self.inicio + timedelta(days=1))
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        evaluar_intervencion(iv, self.inicio + timedelta(days=7), aplicar=True)
        response = self.web.get(reverse('clientes:plan_decisiones'))
        self.assertContains(response, 'Qué aprendió el plan')
        self.assertContains(response, 'Resultado del ajuste')
        html = response.content.decode()
        self.assertLess(html.index('Activo ahora'), html.index('Qué aprendió el plan'))
        self.assertLess(html.index('Qué aprendió el plan'), html.index('Decisiones recientes'))


class CommandTests(CicloBase):
    def test_dry_run_no_persiste_y_apply_si(self):
        iv = self.intervencion(); self.sesion(self.inicio); self.sesion(self.inicio + timedelta(days=1))
        out = StringIO(); call_command('evaluar_intervenciones_esenciales', fecha='2026-07-08', stdout=out)
        iv.refresh_from_db(); self.assertEqual(iv.estado, IntervencionPlan.ESTADO_ACTIVA)
        self.assertIn('mode=dry-run candidates=1 evaluated=0', out.getvalue())
        out = StringIO(); call_command('evaluar_intervenciones_esenciales', '--apply', fecha='2026-07-08', stdout=out)
        iv.refresh_from_db(); self.assertEqual(iv.estado, IntervencionPlan.ESTADO_EXPIRADA)
        self.assertIn('mode=apply candidates=1 evaluated=1', out.getvalue())


class JoiResultadoTests(CicloBase):
    def test_prompt_es_descriptivo_y_prohibe_causalidad(self):
        from joi.services import _prompt_resultado_intervencion
        prompt = _prompt_resultado_intervencion({}, {
            'resultado': 'senal_reducida', 'sesiones_completadas': 3,
            'sesiones_esenciales': 1,
        })
        self.assertIn('3 sesiones, 1 esenciales', prompt)
        self.assertIn('sin atribuir causalidad', prompt)
        self.assertIn('no digas que el ajuste causó', prompt)

    @patch('joi.services.generar_mensaje_joi')
    def test_task_joi_persiste_message_id_y_es_idempotente(self, generar):
        iv = self.intervencion()
        self.sesion(self.inicio); self.sesion(self.inicio + timedelta(days=1))
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        evaluar_intervencion(iv, self.inicio + timedelta(days=7), aplicar=True)
        from joi.models import MensajeJOI
        msg = MensajeJOI.objects.create(
            user=self.user, trigger='resultado_intervencion', mensaje='Lectura', contexto={},
        )
        generar.return_value = msg
        from joi.tasks import generar_resultado_intervencion_joi
        primero = generar_resultado_intervencion_joi.run(iv.pk)
        segundo = generar_resultado_intervencion_joi.run(iv.pk)
        self.assertEqual(primero['mensaje_id'], msg.pk)
        self.assertTrue(segundo['duplicado'])
        generar.assert_called_once()

    @patch('joi.services.generar_mensaje_joi', return_value=None)
    def test_fallo_joi_deja_pendiente_y_reintento_publica(self, generar):
        iv = self.intervencion(); self.sesion(self.inicio); self.sesion(self.inicio + timedelta(days=1))
        from entrenos.services.ciclo_intervencion_esenciales_service import evaluar_intervencion
        evaluar_intervencion(iv, self.inicio + timedelta(days=7), aplicar=True)
        from joi.tasks import generar_resultado_intervencion_joi
        self.assertIsNone(generar_resultado_intervencion_joi.run(iv.pk)['mensaje_id'])
        iv.sugerencia.refresh_from_db()
        self.assertEqual(iv.sugerencia.contrato_snapshot['evaluacion']['joi']['estado'], 'pendiente')
        from joi.models import MensajeJOI
        msg = MensajeJOI.objects.create(user=self.user, trigger='resultado_intervencion', mensaje='x', contexto={})
        generar.return_value = msg
        self.assertEqual(generar_resultado_intervencion_joi.run(iv.pk)['mensaje_id'], msg.pk)

    @patch('joi.services._llamar_haiku', return_value='Lectura no causal.')
    def test_prompt_resultado_prioriza_narrativa_manual_y_trigger_sin_duplicarla(self, llamar):
        from joi.models import ManualDavid, NarrativaActiva
        NarrativaActiva.objects.create(user=self.user, capa_corta='NARRATIVA_UNICA', estado='activa')
        ManualDavid.objects.create(
            user=self.user, entrada='MANUAL_REAL', origen='patron_detectado', tipo='patron',
        )
        from joi.services import generar_mensaje_joi
        generar_mensaje_joi(self.cliente, 'resultado_intervencion', {
            'resultado': 'persistente', 'sesiones_completadas': 2, 'sesiones_esenciales': 1,
        })
        prompt = llamar.call_args.args[0]
        self.assertEqual(prompt.count('NARRATIVA_UNICA'), 1)
        self.assertLess(prompt.index('NARRATIVA_UNICA'), prompt.index('MANUAL_REAL'))
        self.assertLess(prompt.index('MANUAL_REAL'), prompt.index('RESULTADO DE UN AJUSTE'))

    @patch('joi.tasks.generar_resultado_intervencion_joi.delay')
    def test_tarea_diaria_no_encola_dos_veces_recien_evaluada(self, delay):
        iv = self.intervencion(); self.sesion(self.inicio); self.sesion(self.inicio + timedelta(days=1))
        from entrenos.tasks import evaluar_intervenciones_esenciales_diarias
        resultado = evaluar_intervenciones_esenciales_diarias.run()
        self.assertEqual(resultado['evaluadas'], 1)
        delay.assert_called_once_with(iv.pk)
