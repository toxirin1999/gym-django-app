import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.forms import CierreDiarioForm
from diario.models import (
    CierreNocturnoOperacion,
    Gesto,
    Interaccion,
    InteraccionSombra,
    ProsocheDiario,
    ProsocheMes,
    PersonaInterina,
    PersonaImportante,
    ReflexionLibre,
    RegistroGesto,
    SeguimientoVires,
)
from diario.services.cierre_service import (
    ConflictoVersionCierre,
    ejecutar_cierre_nocturno,
    ejecutar_enriquecimiento_cierre,
)


class CierreDiarioFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-form')
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', estado='activo')

    def form(self, **overrides):
        data = {
            'reflexion_libre': 'Un día consciente',
            'friccion_no': '3',
            'cuerpo_cierre': 'ligero',
            'estado_animo_noche': '4',
            'habitos_completados': json.dumps([self.gesto.pk]),
            'idempotency_key': str(uuid.uuid4()),
            'expected_version': '0',
            **overrides,
        }
        return CierreDiarioForm(data=data, usuario=self.user)

    def test_post_vacio_no_es_confirmacion_valida(self):
        self.assertFalse(CierreDiarioForm(data={}, usuario=self.user).is_valid())

    def test_friccion_es_eleccion_consciente_y_animo_pm_restringido(self):
        self.assertFalse(self.form(friccion_no='').is_valid())
        self.assertFalse(self.form(estado_animo_noche='3').is_valid())

    def test_habitos_deben_ser_lista_de_ids_activos_del_usuario(self):
        ajeno = User.objects.create_user('ajeno')
        gesto_ajeno = Gesto.objects.create(usuario=ajeno, nombre='Ajeno', estado='activo')
        self.assertFalse(self.form(habitos_completados=json.dumps([gesto_ajeno.pk])).is_valid())
        self.assertFalse(self.form(habitos_completados='{"id": 1}').is_valid())

    def test_reflexion_tiene_maximo_validado(self):
        self.assertFalse(self.form(reflexion_libre='x' * 5001).is_valid())


class CierreNocturnoCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-command')
        self.hoy = timezone.localdate()
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', estado='activo')

    def payload(self, **overrides):
        return {
            'reflexion_libre': 'Hoy sostuve el límite.',
            'friccion_no': 4,
            'cuerpo_cierre': 'cargado',
            'estado_animo_noche': 2,
            'habitos_completados': [self.gesto.pk],
            'simbiosis_respuesta': '',
            **overrides,
        }

    def ejecutar(self, token=None, expected=0, **payload):
        return ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=self.hoy,
            payload=self.payload(**payload),
            idempotency_key=token or uuid.uuid4(),
            expected_version=expected,
        )

    def test_crea_padres_solo_al_ejecutar_y_no_pisa_animo_am(self):
        resultado = self.ejecutar()
        entrada = resultado.entrada
        entrada.estado_animo = 5
        entrada.save(update_fields=['estado_animo'])
        self.ejecutar(expected=1, reflexion_libre='Texto cambiado')
        entrada.refresh_from_db()
        self.assertEqual(entrada.estado_animo, 5)
        self.assertEqual(entrada.estado_animo_noche, 2)
        self.assertEqual(entrada.cierre_version, 2)
        self.assertIsNotNone(entrada.cierre_confirmado_en)

    def test_replay_mismo_token_y_hash_con_token_distinto_son_noop(self):
        token = uuid.uuid4()
        primero = self.ejecutar(token=token)
        replay = self.ejecutar(token=token, expected=0)
        mismo_hash = self.ejecutar(expected=1)
        self.assertEqual(replay.operacion.pk, primero.operacion.pk)
        self.assertEqual(mismo_hash.entrada.cierre_version, 1)
        self.assertEqual(CierreNocturnoOperacion.objects.count(), 2)
        self.assertEqual(CierreNocturnoOperacion.objects.filter(result_version=1).count(), 1)

    def test_expected_version_obsoleta_da_conflicto(self):
        self.ejecutar()
        with self.assertRaises(ConflictoVersionCierre):
            self.ejecutar(expected=0, reflexion_libre='Cambio real')

    def test_sincronizacion_gestos_es_determinista(self):
        self.ejecutar()
        self.assertTrue(RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy).exists())
        self.ejecutar(expected=1, reflexion_libre='Cambio', habitos_completados=[])
        self.assertFalse(RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy).exists())


class ProyeccionesCierreSimbiosisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-proyecciones')
        self.hoy = timezone.localdate()

    def _operacion(self, texto, expected=0, fecha=None):
        resultado = ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=fecha or self.hoy,
            payload={
                'reflexion_libre': texto,
                'friccion_no': 3,
                'cuerpo_cierre': '',
                'estado_animo_noche': 4,
                'habitos_completados': [],
                'simbiosis_respuesta': '',
            },
            idempotency_key=uuid.uuid4(),
            expected_version=expected,
        )
        return resultado.operacion

    def _enriquecer(self, operacion, *, nombre='Ana', micro='Necesito poner límites claros.'):
        enriquecido = {
            'titulo_logos': 'Un límite sereno',
            'categoria_estoica': 'templanza',
            'micro_verdad': micro,
            'interacciones': [{
                'persona': nombre,
                'tipo': 'neutra',
                'descripcion': 'Conversamos.',
            }] if nombre else [],
        }
        with (
            patch('joi.services.parsear_cierre_diario', return_value={
                'personas': [nombre] if nombre else [], 'etiquetas': ['limites'],
            }),
            patch('joi.services.enriquecer_cierre', return_value=enriquecido),
            patch('joi.services.generar_respuesta_cierre', return_value='Lectura'),
        ):
            return ejecutar_enriquecimiento_cierre(operacion.pk)

    def test_persona_interina_case_insensitive_incrementa_y_nota_inicial_es_unica(self):
        from joi.models import ManualDavid

        primera = self._operacion('Primera mención')
        self._enriquecer(primera, nombre='Ana', micro='')
        segunda = self._operacion('Segunda mención', fecha=self.hoy + timedelta(days=1))
        self._enriquecer(segunda, nombre='ana', micro='')

        self.assertEqual(PersonaInterina.objects.count(), 1)
        interina = PersonaInterina.objects.get()
        self.assertEqual(interina.nombre, 'Ana')
        self.assertEqual(interina.veces_mencionada, 2)
        self.assertEqual(interina.estado, 'radar')
        self.assertEqual(
            ManualDavid.objects.filter(
                user=self.user, entrada__icontains="Entidad nueva detectada: 'Ana'",
            ).count(),
            1,
        )

    def test_descartada_reaparece_tras_dos_nuevas_sin_saltar_a_radar(self):
        interina = PersonaInterina.objects.create(
            usuario=self.user, nombre='Marta', estado='descartada',
            veces_mencionada=8, menciones_desde_descarte=0,
        )
        primera = self._operacion('Marta una vez')
        self._enriquecer(primera, nombre='marta', micro='')
        interina.refresh_from_db()
        self.assertEqual(interina.estado, 'descartada')
        self.assertEqual(interina.menciones_desde_descarte, 1)

        segunda = self._operacion('Marta otra vez', fecha=self.hoy + timedelta(days=1))
        self._enriquecer(segunda, nombre='MARTA', micro='')
        interina.refresh_from_db()
        self.assertEqual(interina.estado, 'sombra')
        self.assertEqual(interina.menciones_desde_descarte, 0)
        self.assertEqual(interina.veces_mencionada, 10)

    def test_microverdad_activa_obvia_y_replay_no_crean_duplicados(self):
        from joi.models import ManualDavid

        ManualDavid.objects.create(
            user=self.user, entrada='Necesito poner límites claros.',
            origen='patron_detectado', activa=True,
        )
        operacion = self._operacion('Aprendí algo')
        self._enriquecer(operacion, nombre='', micro='necesito poner límites claros.')
        self._enriquecer(operacion, nombre='', micro='necesito poner límites claros.')

        self.assertEqual(ManualDavid.objects.filter(user=self.user, activa=True).count(), 1)
        self.assertEqual(ReflexionLibre.objects.count(), 1)

    def test_categoria_estoica_se_conserva_en_etiquetas_de_reflexion(self):
        operacion = self._operacion('Hoy elegí templanza')
        self._enriquecer(operacion, nombre='', micro='')

        etiquetas = ReflexionLibre.objects.get().etiquetas.split(',')
        self.assertIn('templanza', etiquetas)


class PresenciaCierreViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-view', password='x')
        self.client.force_login(self.user)
        self.url = reverse('diario:presencia_cierre')
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', estado='activo')

    def data(self, **overrides):
        datos = {
            'reflexion_libre': 'Cierre real',
            'friccion_no': '3',
            'cuerpo_cierre': '',
            'estado_animo_noche': '4',
            'habitos_completados': json.dumps([self.gesto.pk]),
            'idempotency_key': str(uuid.uuid4()),
            'expected_version': '0',
            **overrides,
        }
        if 'analisis_cierre_token' not in datos:
            from diario.services.analisis_cierre_service import crear_artefacto, firmar_artefacto
            analisis = {
                'estado': 'ok_sin_senales',
                'parseo': {'personas': [], 'impulsos': [], 'etiquetas': []},
                'enriquecido': {'interacciones': [], 'micro_verdad': None},
            }
            datos['analisis_cierre_token'] = firmar_artefacto(crear_artefacto(
                usuario=self.user, fecha=timezone.localdate(),
                texto=datos['reflexion_libre'], analisis=analisis,
            ))
        return datos

    def operacion(self, *, resultado=None, estado='completed', token=None):
        token = token or uuid.uuid4()
        comando = ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=timezone.localdate(),
            payload={
                'reflexion_libre': 'Cierre real',
                'friccion_no': 3,
                'cuerpo_cierre': '',
                'estado_animo_noche': 4,
                'habitos_completados': [self.gesto.pk],
                'simbiosis_respuesta': '',
                'simbiosis_pregunta': '',
            },
            idempotency_key=token,
            expected_version=0,
        )
        comando.operacion.estado = estado
        comando.operacion.resultado = resultado or {}
        comando.operacion.save(update_fields=['estado', 'resultado', 'updated_at'])
        return comando.operacion

    def test_lectura_inmediata_presenta_dia_completo_si_apertura_y_cierre_estan_confirmados(self):
        operacion = self.operacion()
        operacion.entrada.apertura_confirmada_en = timezone.now()
        operacion.entrada.save(update_fields=['apertura_confirmada_en'])

        response = self.client.get(f'{self.url}?cierre_operacion={operacion.idempotency_key}')

        self.assertEqual(response.context['estado_cierre'], 'dia_completo')
        self.assertContains(response, 'Día completo.')
        self.assertContains(response, 'Apertura y cierre están registrados.')

    def test_lectura_durable_sin_uuid_presenta_cierre_sin_apertura(self):
        self.operacion()

        response = self.client.get(self.url)

        self.assertEqual(response.context['estado_cierre'], 'solo_noche')
        self.assertContains(response, 'Cierre registrado.')
        self.assertContains(response, 'Hoy no hubo apertura; el cierre está registrado.')

    def test_texto_matutino_legacy_sin_confirmacion_no_convierte_el_cierre_en_dia_completo(self):
        operacion = self.operacion()
        operacion.entrada.persona_quiero_ser = 'Presente y sereno'
        operacion.entrada.save(update_fields=['persona_quiero_ser'])

        response = self.client.get(self.url)

        self.assertEqual(response.context['estado_cierre'], 'solo_noche')
        self.assertContains(response, 'Cierre registrado.')
        self.assertNotContains(response, 'Día completo.')

    def test_get_es_puro(self):
        response = self.client.get(self.url)
        self.assertFalse(ProsocheMes.objects.exists())
        self.assertFalse(ProsocheDiario.objects.exists())
        self.assertFalse(SeguimientoVires.objects.exists())
        self.assertFalse(RegistroGesto.objects.exists())
        html = response.content.decode()
        self.assertIn('<option value="" selected>Elige conscientemente</option>', html)
        self.assertNotIn('<option value="1" selected>', html)
        self.assertNotIn('<option value="2" selected>', html)
        self.assertNotIn('<option value="4" selected>', html)
        self.assertNotIn('<option value="5" selected>', html)

    def test_post_invalido_ajax_no_escribe(self):
        response = self.client.post(self.url, {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIn(response.status_code, (400, 422))
        self.assertFalse(ProsocheDiario.objects.exists())

    @patch('diario.services.cierre_service.ejecutar_enriquecimiento_cierre', side_effect=RuntimeError('IA caída'))
    def test_fallo_ia_conserva_confirmacion_y_es_retryable(self, _enriquecer):
        response = self.client.post(self.url, self.data(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['confirmacion'], 'Cierre guardado.')
        entrada = ProsocheDiario.objects.get()
        self.assertIsNotNone(entrada.cierre_confirmado_en)
        self.assertEqual(CierreNocturnoOperacion.objects.get().estado, 'failed')

    @patch('diario.services.cierre_service.ejecutar_enriquecimiento_cierre')
    def test_post_tradicional_siempre_prg(self, enriquecer):
        enriquecer.return_value = {'respuesta_joi': 'Lectura visible'}
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302)
        self.assertIn('cierre_operacion=', response.url)

    def test_template_tiene_un_solo_listener_y_no_submit_nativo(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertEqual(html.count("addEventListener('submit'"), 1)
        self.assertNotIn(".submit();", html)
        self.assertIn('idempotency_key', html)
        self.assertIn('expected_version', html)

    @patch('diario.services.cierre_service.ejecutar_enriquecimiento_cierre', return_value={})
    def test_ajax_devuelve_url_estable_y_js_navega_sin_panel_efimero(self, _enriquecer):
        response = self.client.post(self.url, self.data(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        token = response.json()['operacion']
        self.assertEqual(
            response.json()['result_url'],
            f'{self.url}?cierre_operacion={token}',
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn('window.location.assign(data.result_url)', html)
        self.assertNotIn('setTimeout', html)
        self.assertNotIn('cierre-respuesta-visible', html)
        self.assertNotIn("window.location.href = \"{% url 'diario:dashboard_diario' %}\"", html)

    def test_resultado_persistente_explica_lo_guardado_sin_convertirlo_en_voz_joi(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user, contenido='Cierre real', tipo='espontanea'
        )
        op = self.operacion(resultado={
            'respuesta_joi': 'Veo que hoy protegiste un límite.',
            'reflexiones': [reflexion.pk],
            'manual': [91],
            'interacciones': [81],
            'sombras': [71],
            'simbiosis': {'personas': ['Ana', 'Luis']},
        })
        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()
        self.assertIn('Veo que hoy protegiste un límite.', html)
        self.assertIn('Lo que guardó el Diario', html)
        self.assertIn('1 gesto', html)
        self.assertIn('Leer', html)
        self.assertIn('1 reflexión incorporada a Logos', html)
        self.assertNotIn('Ana', html)
        self.assertNotIn('Luis', html)
        self.assertIn('id="editar-cierre"', html)
        self.assertIn('editar=1', html)
        self.assertNotIn('JOI — Lo que guardó el Diario', html)

    def test_deteccion_sin_proyeccion_no_afirma_relacion_ni_ofrece_simbiosis(self):
        op = self.operacion(resultado={
            'respuesta_joi': '', 'reflexiones': [], 'interacciones': [], 'sombras': [],
            'simbiosis': {'personas': ['Nombre solo parseado']},
        })

        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()

        self.assertNotIn('Nombre solo parseado', html)
        self.assertNotIn('Relaciones incorporadas', html)
        self.assertNotIn('Abrir Simbiosis', html)

    def test_ledger_real_muestra_conteo_relacional_y_cta_simbiosis(self):
        persona = PersonaImportante.objects.create(usuario=self.user, nombre='Ana')
        interaccion = Interaccion.objects.create(
            usuario=self.user, titulo='Conversación', descripcion='Hablamos con calma',
        )
        interaccion.personas.add(persona)
        interina = PersonaInterina.objects.create(usuario=self.user, nombre='Luis')
        sombra = InteraccionSombra.objects.create(
            persona_interina=interina, descripcion='Mención real',
        )
        op = self.operacion(resultado={
            'schema_version': 2,
            'ledger': {
                'reflexiones': [], 'interacciones': [{'id': interaccion.pk}],
                'sombras': [{'id': sombra.pk, 'persona_interina_id': interina.pk}],
                'personas_interinas': [{'id': interina.pk}],
            },
            'simbiosis': {'personas': ['Ana', 'Luis', 'Nombre no materializado']},
        })

        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()

        self.assertIn('2 registros relacionales incorporados', html)
        self.assertIn(f'href="{reverse("diario:simbiosis_dashboard")}"', html)
        self.assertNotIn('Nombre no materializado', html)

    def test_ids_ajenos_o_inexistentes_del_resultado_se_ignoran(self):
        ajeno = User.objects.create_user('proyecciones-ajenas')
        reflexion_ajena = ReflexionLibre.objects.create(
            usuario=ajeno, contenido='No pertenece al cierre', tipo='espontanea',
        )
        interaccion_ajena = Interaccion.objects.create(
            usuario=ajeno, titulo='Ajena', descripcion='No visible',
        )
        op = self.operacion(resultado={
            'schema_version': 2,
            'ledger': {
                'reflexiones': [{'id': reflexion_ajena.pk}, {'id': 999999}],
                'interacciones': [{'id': interaccion_ajena.pk}, {'id': 999999}],
                'sombras': [{'id': 999999, 'persona_interina_id': 999999}],
                'personas_interinas': [{'id': 999999}],
            },
            'simbiosis': {'personas': ['Inventada']},
        })

        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()

        self.assertNotIn('Inventada', html)
        self.assertNotIn('Abrir Simbiosis', html)
        self.assertNotIn(reverse('diario:logos_ver_reflexion', args=[reflexion_ajena.pk]), html)

    def test_reflexion_real_enlaza_a_su_url_exacta(self):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user, contenido='Reflexión materializada', tipo='espontanea',
        )
        op = self.operacion(resultado={
            'schema_version': 2,
            'ledger': {'reflexiones': [{'id': reflexion.pk}]},
        })

        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()

        self.assertIn(
            f'href="{reverse("diario:logos_ver_reflexion", args=[reflexion.pk])}"', html,
        )

    def test_gestos_guardados_reales_enlazan_al_panel(self):
        op = self.operacion(resultado={})

        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()

        self.assertIn('1 gesto incorporado', html)
        self.assertIn(f'href="{reverse("diario:habitos_dashboard")}"', html)

    def test_resultado_sin_voz_joi_usa_confirmacion_neutral(self):
        op = self.operacion(resultado={
            'respuesta_joi': '', 'reflexiones': [], 'manual': [],
            'interacciones': [], 'sombras': [], 'simbiosis': {'personas': []},
        })
        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()
        self.assertIn('Cierre registrado.', html)
        self.assertNotIn('Invitación de JOI', html)

    def test_fallo_enriquecimiento_no_afirma_aprendizajes(self):
        op = self.operacion(estado='failed', resultado={})
        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()
        self.assertIn('Cierre registrado.', html)
        self.assertIn('análisis no está disponible', html)
        self.assertIn('puedes reintentarlo', html)
        self.assertNotIn('Relaciones detectadas', html)
        self.assertNotIn('Tu reflexión quedó guardada', html)

    def test_noop_resuelve_resultado_canonico_en_get(self):
        canonical = self.operacion(resultado={
            'respuesta_joi': 'Lectura canónica', 'reflexiones': [],
            'manual': [], 'interacciones': [], 'sombras': [],
            'simbiosis': {'personas': ['Marta']},
        })
        replay = ejecutar_cierre_nocturno(
            usuario=self.user, fecha=timezone.localdate(),
            payload=canonical.enrichment_payload,
            idempotency_key=uuid.uuid4(), expected_version=1,
        ).operacion
        html = self.client.get(f'{self.url}?cierre_operacion={replay.idempotency_key}').content.decode()
        self.assertIn('Lectura canónica', html)
        self.assertNotIn('Marta', html)

    def test_get_sin_uuid_resuelve_la_operacion_completada_de_la_version_activa(self):
        obsoleta = self.operacion(resultado={
            'respuesta_joi': 'Lectura obsoleta', 'reflexiones': [],
            'simbiosis': {'personas': ['Marta']},
        })
        entrada = obsoleta.entrada
        entrada.cierre_version = 2
        entrada.save(update_fields=['cierre_version'])
        activa = CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=uuid.uuid4(), expected_version=1,
            result_version=2, payload_hash='b' * 64, estado='completed',
            enrichment_payload={
                **obsoleta.enrichment_payload,
                'habitos_completados': [self.gesto.pk],
            },
            resultado={
                'respuesta_joi': 'Lectura durable activa',
                'reflexiones': [123],
                'propuesta_habito': {
                    'nombre': 'Preparar mochila',
                    'descripcion': 'Antes de dormir',
                    'tipo': 'positivo',
                },
                'simbiosis': {'personas': ['Ana']},
            },
        )
        CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=uuid.uuid4(), expected_version=2,
            result_version=None, payload_hash='b' * 64, estado='noop',
            resultado={'canonical_operation_id': activa.pk},
        )

        html = self.client.get(self.url).content.decode()

        self.assertIn('Lectura durable activa', html)
        self.assertIn('Preparar mochila', html)
        self.assertNotIn('Ana', html)
        self.assertNotIn('reflexión incorporada a Logos', html)
        self.assertNotIn('Lectura obsoleta', html)

    def test_get_sin_uuid_no_reutiliza_lectura_obsoleta_si_la_version_activa_fallo(self):
        obsoleta = self.operacion(resultado={
            'respuesta_joi': 'No debe reaparecer',
            'simbiosis': {'personas': ['Marta']},
        })
        entrada = obsoleta.entrada
        entrada.cierre_version = 2
        entrada.respuesta_joi_cierre = 'No debe reaparecer'
        entrada.save(update_fields=['cierre_version', 'respuesta_joi_cierre'])
        CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=uuid.uuid4(), expected_version=1,
            result_version=2, payload_hash='c' * 64, estado='failed',
            enrichment_payload=obsoleta.enrichment_payload, resultado={},
        )

        html = self.client.get(self.url).content.decode()

        self.assertNotIn('No debe reaparecer', html)
        self.assertIn('análisis no está disponible', html)

    def test_propuesta_valida_es_accionable_y_aceptacion_no_duplica(self):
        propuesta = {'nombre': 'Preparar mañana', 'descripcion': 'Dejar ropa lista', 'tipo': 'positivo'}
        op = self.operacion(resultado={
            'respuesta_joi': '', 'propuesta_habito': propuesta,
            'reflexiones': [], 'manual': [], 'interacciones': [], 'sombras': [],
            'simbiosis': {'personas': []},
        })
        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()
        self.assertIn('id="habito-invitacion"', html)
        self.assertIn(reverse('diario:aceptar_habito_invitacion'), html)
        self.assertIn('X-CSRFToken', html)
        self.assertIn('operacion:', html)
        self.assertIn(str(op.idempotency_key).replace('-', '\\u002D'), html)
        body = json.dumps({**propuesta, 'operacion': str(op.idempotency_key)})
        endpoint = reverse('diario:aceptar_habito_invitacion')
        primero = self.client.post(endpoint, body, content_type='application/json').json()
        segundo = self.client.post(endpoint, body, content_type='application/json').json()
        self.assertTrue(primero['creado'])
        self.assertFalse(segundo['creado'])
        self.assertEqual(Gesto.objects.filter(usuario=self.user, nombre='Preparar mañana').count(), 1)

    def test_aceptar_habito_rechaza_payload_manipulado_y_operacion_ajena(self):
        propuesta = {'nombre': 'Preparar mañana', 'descripcion': 'Dejar ropa lista', 'tipo': 'positivo'}
        op = self.operacion(resultado={'propuesta_habito': propuesta})
        endpoint = reverse('diario:aceptar_habito_invitacion')

        manipulado = self.client.post(endpoint, json.dumps({
            **propuesta, 'nombre': 'Hábito inyectado',
            'operacion': str(op.idempotency_key),
        }), content_type='application/json')

        ajeno = User.objects.create_user('cierre-ajeno')
        mes = ProsocheMes.objects.create(
            usuario=ajeno, mes=timezone.localdate().strftime('%B'),
            año=timezone.localdate().year,
        )
        entrada_ajena = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=timezone.localdate(), cierre_version=1,
            cierre_confirmado_en=timezone.now(),
        )
        op_ajena = CierreNocturnoOperacion.objects.create(
            entrada=entrada_ajena, idempotency_key=uuid.uuid4(),
            expected_version=0, result_version=1, payload_hash='d' * 64,
            estado='completed', resultado={'propuesta_habito': propuesta},
        )
        respuesta_ajena = self.client.post(endpoint, json.dumps({
            **propuesta, 'operacion': str(op_ajena.idempotency_key),
        }), content_type='application/json')

        self.assertEqual(manipulado.status_code, 400)
        self.assertEqual(respuesta_ajena.status_code, 400)
        self.assertFalse(Gesto.objects.filter(usuario=self.user).exclude(pk=self.gesto.pk).exists())

    def test_aceptar_habito_rechaza_operacion_obsoleta_fallida_o_noop(self):
        propuesta = {'nombre': 'Preparar mañana', 'descripcion': 'Dejar ropa lista', 'tipo': 'positivo'}
        obsoleta = self.operacion(resultado={'propuesta_habito': propuesta})
        entrada = obsoleta.entrada
        entrada.cierre_version = 2
        entrada.save(update_fields=['cierre_version'])
        fallida = CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=uuid.uuid4(), expected_version=1,
            result_version=2, payload_hash='e' * 64, estado='failed',
            resultado={'propuesta_habito': propuesta},
        )
        noop = CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=uuid.uuid4(), expected_version=2,
            result_version=None, payload_hash='e' * 64, estado='noop',
            resultado={'canonical_operation_id': fallida.pk},
        )
        endpoint = reverse('diario:aceptar_habito_invitacion')

        for operacion in (obsoleta, fallida, noop):
            response = self.client.post(endpoint, json.dumps({
                **propuesta, 'operacion': str(operacion.idempotency_key),
            }), content_type='application/json')
            self.assertEqual(response.status_code, 400)

        self.assertFalse(Gesto.objects.filter(usuario=self.user).exclude(pk=self.gesto.pk).exists())

    def test_sin_propuesta_no_renderiza_card_vacia(self):
        op = self.operacion(resultado={'respuesta_joi': '', 'simbiosis': {'personas': []}})
        html = self.client.get(f'{self.url}?cierre_operacion={op.idempotency_key}').content.decode()
        self.assertNotIn('id="habito-invitacion"', html)

    def test_lectura_ofrece_edicion_explicita_y_editar_precarga_version(self):
        mes = ProsocheMes.objects.create(usuario=self.user, mes=timezone.localdate().strftime('%B'), año=timezone.localdate().year)
        entrada = ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=timezone.localdate(), cierre_confirmado_en=timezone.now(),
            cierre_version=3, reflexiones_dia='Texto anterior', estado_animo_noche=5,
            respuesta_joi_cierre='Lectura anterior',
        )
        SeguimientoVires.objects.create(usuario=self.user, fecha=timezone.localdate(), nivel_estres=4, cuerpo_cierre='cargado')
        lectura = self.client.get(self.url).content.decode()
        self.assertIn('id="editar-cierre"', lectura)
        self.assertIn('id="cierre-form" style="display:none"', lectura)
        edicion = self.client.get(f'{self.url}?editar=1').content.decode()
        self.assertNotIn('id="cierre-form" style="display:none"', edicion)
        self.assertNotIn('id="cierre-guardado-titulo"', edicion)
        self.assertIn('value="3"', edicion)
        self.assertIn('<option value="5" selected>Pleno</option>', edicion)

    @patch('joi.services.enriquecer_cierre', return_value={'interacciones': [], 'micro_verdad': None})
    @patch('joi.services.parsear_cierre_diario', return_value={'personas': [], 'etiquetas': []})
    @patch('joi.services.generar_respuesta_cierre', side_effect=[RuntimeError('cae'), 'Lectura recuperada'])
    def test_token_nuevo_mismo_hash_reintenta_operacion_canonica_sin_duplicar(self, _respuesta, _parseo, _enriq):
        primero = self.client.post(self.url, self.data(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(primero.status_code, 200)
        canonical = CierreNocturnoOperacion.objects.get(result_version=1)
        self.assertEqual(canonical.estado, 'failed')
        segundo = self.client.post(
            self.url, self.data(expected_version='1'), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(segundo.status_code, 200)
        canonical.refresh_from_db()
        self.assertEqual(canonical.estado, 'completed')
        self.assertEqual(ProsocheDiario.objects.get().cierre_version, 1)
        self.assertEqual(ReflexionLibre.objects.count(), 1)
        self.assertEqual(CierreNocturnoOperacion.objects.count(), 2)


class EstadoDiarioCierreTests(TestCase):
    def test_solo_cierre_confirmado_cuenta_como_noche(self):
        from diario.services.estado_diario import calcular_estado_diario_hoy
        falso = ProsocheDiario(reflexiones_dia='texto sin confirmar')
        self.assertEqual(calcular_estado_diario_hoy(falso)['estado'], 'sin_entrada')
        falso.cierre_confirmado_en = timezone.now()
        self.assertEqual(calcular_estado_diario_hoy(falso)['estado'], 'solo_noche')


class PromptCierreJOITests(TestCase):
    @patch('joi.services._llamar_haiku', return_value='Respuesta')
    @patch('joi.services._bloque_manual', return_value='MANUAL')
    @patch('joi.services._bloque_narrativa', return_value='NARRATIVA')
    def test_orden_narrativa_manual_trigger_sin_narrativa_duplicada(self, narrativa, manual, llamar):
        from joi.services import generar_respuesta_cierre
        user = User.objects.create_user('prompt-cierre')
        self.assertEqual(generar_respuesta_cierre('Mi cierre', {}, user), 'Respuesta')
        manual.assert_called_once_with(user, incluir_narrativa=False)
        prompt = llamar.call_args.args[0]
        self.assertLess(prompt.index('NARRATIVA'), prompt.index('MANUAL'))
        self.assertLess(prompt.index('MANUAL'), prompt.index('TRIGGER — CIERRE DE HOY'))
        self.assertEqual(prompt.count('NARRATIVA'), 1)

    @patch('joi.services._llamar_haiku', side_effect=RuntimeError('sin red'))
    def test_fallback_de_voz_es_vacio(self, _llamar):
        from joi.services import generar_respuesta_cierre
        user = User.objects.create_user('prompt-fallback')
        self.assertEqual(generar_respuesta_cierre('Mi cierre', {}, user), '')
