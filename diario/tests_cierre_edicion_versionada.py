import json
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import (
    CierreNocturnoOperacion,
    Interaccion,
    InteraccionSombra,
    PersonaImportante,
    PersonaInterina,
    ReflexionLibre,
)
from diario.services.cierre_service import (
    ejecutar_cierre_nocturno,
    ejecutar_enriquecimiento_cierre,
)


class EdicionVersionadaProyeccionesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-versionado')
        self.fecha = timezone.localdate()

    def _operacion(self, texto, expected):
        return ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=self.fecha,
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
        ).operacion

    def _enriquecer(self, operacion, *, persona='', micro=''):
        with (
            patch('joi.services.parsear_cierre_diario', return_value={
                'personas': [persona] if persona else [], 'etiquetas': [],
            }),
            patch('joi.services.enriquecer_cierre', return_value={
                'micro_verdad': micro,
                'interacciones': ([{
                    'persona': persona, 'tipo': 'neutra', 'descripcion': persona,
                }] if persona else []),
            }),
            patch('joi.services.generar_respuesta_cierre', return_value='respuesta'),
        ):
            return ejecutar_enriquecimiento_cierre(operacion.pk)

    def test_edicion_a_b_sustituye_proyecciones_y_conserva_historial(self):
        primera = self._operacion('Texto A', 0)
        resultado_a = self._enriquecer(primera, persona='Ana', micro='Verdad A')
        segunda = self._operacion('Texto B', 1)
        resultado_b = self._enriquecer(segunda, persona='Bea', micro='Verdad B')

        primera.refresh_from_db()
        self.assertEqual(primera.estado, 'superseded')
        self.assertEqual(primera.resultado['retracted_by_version'], 2)
        self.assertEqual(primera.resultado['reflexiones'], resultado_a['reflexiones'])
        self.assertFalse(ReflexionLibre.objects.filter(pk__in=resultado_a['reflexiones']).exists())
        self.assertTrue(ReflexionLibre.objects.filter(pk__in=resultado_b['reflexiones']).exists())
        self.assertFalse(PersonaInterina.objects.filter(nombre='Ana').exists())
        self.assertEqual(resultado_b['schema_version'], 2)
        self.assertIn('ledger', resultado_b)

    def test_edicion_a_vacio_restaura_persona_interina_y_radar(self):
        interina = PersonaInterina.objects.create(
            usuario=self.user, nombre='Ana', estado='sombra', veces_mencionada=1,
        )
        primera = self._operacion('Texto A', 0)
        self._enriquecer(primera, persona='Ana')
        interina.refresh_from_db()
        self.assertEqual((interina.estado, interina.veces_mencionada), ('radar', 2))

        segunda = self._operacion('', 1)
        self._enriquecer(segunda)
        interina.refresh_from_db()
        self.assertEqual((interina.estado, interina.veces_mencionada), ('sombra', 1))
        self.assertFalse(InteraccionSombra.objects.filter(persona_interina=interina).exists())

    def test_retraccion_no_pisa_cambio_externo_en_persona_o_manual(self):
        from joi.models import ManualDavid

        primera = self._operacion('Texto A', 0)
        resultado = self._enriquecer(primera, persona='Ana', micro='Verdad A')
        interina = PersonaInterina.objects.get(nombre='Ana')
        interina.estado = 'promovida'
        interina.save(update_fields=['estado'])
        manual = ManualDavid.objects.get(pk=resultado['manual'][0])
        manual.notas_revision = 'revisada por usuario'
        manual.save(update_fields=['notas_revision'])

        segunda = self._operacion('', 1)
        self._enriquecer(segunda)
        interina.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(interina.estado, 'promovida')
        self.assertTrue(manual.activa)
        self.assertNotEqual(manual.estado, 'descartada')

    def test_enriquecimiento_tardio_de_version_anterior_no_retrae_activa(self):
        primera = self._operacion('Texto A', 0)
        segunda = self._operacion('Texto B', 1)
        resultado_b = self._enriquecer(segunda, persona='Bea')
        self._enriquecer(primera, persona='Ana')

        primera.refresh_from_db()
        self.assertEqual(primera.estado, 'superseded')
        self.assertTrue(ReflexionLibre.objects.filter(pk__in=resultado_b['reflexiones']).exists())
        self.assertFalse(PersonaInterina.objects.filter(nombre='Ana').exists())

    def test_replay_enriquecimiento_misma_operacion_no_recrea(self):
        operacion = self._operacion('Texto A', 0)
        primero = self._enriquecer(operacion, persona='Ana')
        segundo = self._enriquecer(operacion, persona='Otra')
        self.assertEqual(primero, segundo)
        self.assertEqual(ReflexionLibre.objects.count(), 1)
        self.assertEqual(CierreNocturnoOperacion.objects.get(pk=operacion.pk).estado, 'completed')

    def test_persona_conocida_a_b_deja_solo_interaccion_b(self):
        PersonaImportante.objects.create(usuario=self.user, nombre='Ana')
        PersonaImportante.objects.create(usuario=self.user, nombre='Bea')
        primera = self._operacion('Texto A', 0)
        resultado_a = self._enriquecer(primera, persona='Ana')
        segunda = self._operacion('Texto B', 1)
        resultado_b = self._enriquecer(segunda, persona='Bea')

        self.assertFalse(Interaccion.objects.filter(pk__in=resultado_a['interacciones']).exists())
        self.assertTrue(Interaccion.objects.filter(pk__in=resultado_b['interacciones']).exists())

    def test_edicion_retrae_promocion_automatica_y_conserva_datos_manuales(self):
        primera = self._operacion('Texto A', 0)
        resultado_a = self._enriquecer(primera, persona='Ana')
        sombra = InteraccionSombra.objects.get(pk=resultado_a['sombras'][0])
        interina = sombra.persona_interina

        self.client.force_login(self.user)
        respuesta = self.client.post(
            reverse('diario:promover_persona_interina'),
            data=json.dumps({'id': interina.pk, 'accion': 'promover'}),
            content_type='application/json',
        )
        self.assertEqual(respuesta.status_code, 200)

        persona = PersonaImportante.objects.get(usuario=self.user, nombre='Ana')
        automatica = Interaccion.objects.get(origen_sombra=sombra)
        manual = Interaccion.objects.create(
            usuario=self.user,
            titulo='Registro manual',
            descripcion='Creada conscientemente por el usuario.',
            fecha=self.fecha,
        )
        manual.personas.add(persona)

        segunda = self._operacion('Texto B sin esa persona', 1)
        self._enriquecer(segunda)

        self.assertFalse(InteraccionSombra.objects.filter(pk=sombra.pk).exists())
        self.assertFalse(Interaccion.objects.filter(pk=automatica.pk).exists())
        self.assertTrue(PersonaImportante.objects.filter(pk=persona.pk).exists())
        self.assertTrue(Interaccion.objects.filter(pk=manual.pk).exists())
        self.assertTrue(manual.personas.filter(pk=persona.pk).exists())

    def test_fallo_materializando_b_revierte_retraccion_de_a(self):
        primera = self._operacion('Texto A', 0)
        resultado_a = self._enriquecer(primera, persona='Ana')
        segunda = self._operacion('Texto B', 1)

        with (
            patch('joi.services.parsear_cierre_diario', return_value={'personas': [], 'etiquetas': []}),
            patch('joi.services.enriquecer_cierre', return_value={}),
            patch('joi.services.generar_respuesta_cierre', return_value='respuesta'),
            patch('diario.services.cierre_service.ReflexionLibre.objects.create', side_effect=RuntimeError('fallo')),
            self.assertRaises(RuntimeError),
        ):
            ejecutar_enriquecimiento_cierre(segunda.pk)

        primera.refresh_from_db()
        self.assertEqual(primera.estado, 'completed')
        self.assertTrue(ReflexionLibre.objects.filter(pk__in=resultado_a['reflexiones']).exists())
        self.assertTrue(PersonaInterina.objects.filter(nombre='Ana').exists())

    def test_sombra_usa_fecha_del_cierre_y_no_fecha_del_analisis(self):
        self.fecha = date(2026, 5, 12)
        operacion = self._operacion('Texto histórico', 0)

        self._enriquecer(operacion, persona='Ana')

        self.assertEqual(InteraccionSombra.objects.get().fecha, self.fecha)

    def test_varias_interacciones_de_una_persona_cuentan_una_mencion_por_cierre(self):
        operacion = self._operacion('Vi dos veces a Ana', 0)
        with (
            patch('joi.services.parsear_cierre_diario', return_value={
                'personas': ['Ana'], 'etiquetas': [],
            }),
            patch('joi.services.enriquecer_cierre', return_value={
                'micro_verdad': '',
                'interacciones': [
                    {'persona': 'Ana', 'tipo': 'neutra', 'descripcion': 'Primera'},
                    {'persona': 'ana', 'tipo': 'apoyo', 'descripcion': 'Segunda'},
                ],
            }),
            patch('joi.services.generar_respuesta_cierre', return_value='respuesta'),
        ):
            ejecutar_enriquecimiento_cierre(operacion.pk)

        persona = PersonaInterina.objects.get()
        self.assertEqual(persona.veces_mencionada, 1)
        self.assertEqual(persona.interacciones.count(), 2)


class ReaparicionPersonaArchivadaEnCierreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cierre-persona-archivada')
        self.fecha = date(2026, 7, 10)

    def _operacion(self, texto, *, fecha=None, expected=0):
        return ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=fecha or self.fecha,
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
        ).operacion

    def _enriquecer(self, operacion, interacciones):
        nombres = list(dict.fromkeys(
            item['persona'] for item in interacciones if item.get('persona')
        ))
        with (
            patch('joi.services.parsear_cierre_diario', return_value={
                'personas': nombres, 'etiquetas': [],
            }),
            patch('joi.services.enriquecer_cierre', return_value={
                'micro_verdad': '', 'interacciones': interacciones,
            }),
            patch('joi.services.generar_respuesta_cierre', return_value='respuesta'),
        ):
            return ejecutar_enriquecimiento_cierre(operacion.pk)

    @staticmethod
    def _item(nombre='Ana', descripcion='Encuentro'):
        return {
            'persona': nombre,
            'tipo': 'neutra',
            'descripcion': descripcion,
        }

    def test_persona_activa_sigue_generando_interaccion_real(self):
        persona = PersonaImportante.objects.create(
            usuario=self.user, nombre='Ana', archivada=False,
        )

        resultado = self._enriquecer(
            self._operacion('Vi a Ana'), [self._item()],
        )

        self.assertEqual(len(resultado['interacciones']), 1)
        self.assertEqual(resultado['sombras'], [])
        self.assertEqual(Interaccion.objects.get().personas.get(), persona)
        self.assertFalse(PersonaInterina.objects.exists())

    def test_archivada_sin_interina_reaparece_como_primera_senal_sombra(self):
        persona = PersonaImportante.objects.create(
            usuario=self.user, nombre='ANA', archivada=True,
        )

        resultado = self._enriquecer(
            self._operacion('Volví a ver a Ana'), [self._item('ana')],
        )

        persona.refresh_from_db()
        interina = PersonaInterina.objects.get()
        self.assertTrue(persona.archivada)
        self.assertEqual(resultado['interacciones'], [])
        self.assertEqual(len(resultado['sombras']), 1)
        self.assertEqual(interina.estado, 'sombra')
        self.assertEqual(interina.veces_mencionada, 1)
        self.assertIsNone(interina.persona_importante)
        self.assertEqual(PersonaImportante.objects.count(), 1)

    def test_archivada_repetida_avanza_de_sombra_a_radar_sin_reactivarse(self):
        persona = PersonaImportante.objects.create(
            usuario=self.user, nombre='Ana', archivada=True,
        )
        primera = self._operacion('Vi a Ana', fecha=date(2026, 7, 10))
        self._enriquecer(primera, [self._item()])

        segunda = self._operacion('Volví a ver a Ana', fecha=date(2026, 7, 11))
        self._enriquecer(segunda, [self._item()])

        persona.refresh_from_db()
        interina = PersonaInterina.objects.get()
        self.assertTrue(persona.archivada)
        self.assertEqual(interina.estado, 'radar')
        self.assertEqual(interina.veces_mencionada, 2)
        self.assertIsNone(interina.persona_importante)
        self.assertEqual(Interaccion.objects.count(), 0)
        self.assertEqual(InteraccionSombra.objects.count(), 2)

    def test_varias_interacciones_archivada_cuentan_una_mencion_por_cierre(self):
        persona = PersonaImportante.objects.create(
            usuario=self.user, nombre='Ana', archivada=True,
        )
        interina = PersonaInterina.objects.create(
            usuario=self.user, nombre='ANA', estado='sombra',
            veces_mencionada=1,
        )

        self._enriquecer(self._operacion('Vi dos veces a Ana'), [
            self._item('Ana', 'Primera'),
            self._item('ana', 'Segunda'),
        ])

        persona.refresh_from_db()
        interina.refresh_from_db()
        self.assertTrue(persona.archivada)
        self.assertEqual(interina.veces_mencionada, 2)
        self.assertEqual(interina.estado, 'radar')
        self.assertEqual(interina.interacciones.count(), 2)
        self.assertEqual(Interaccion.objects.count(), 0)

    def test_edicion_retrae_sombra_y_restaura_contador_de_archivada(self):
        persona = PersonaImportante.objects.create(
            usuario=self.user, nombre='Ana', archivada=True,
        )
        interina = PersonaInterina.objects.create(
            usuario=self.user, nombre='Ana', estado='sombra',
            veces_mencionada=1,
        )
        primera = self._operacion('Vi a Ana')
        self._enriquecer(primera, [self._item()])
        interina.refresh_from_db()
        self.assertEqual((interina.estado, interina.veces_mencionada), ('radar', 2))

        segunda = self._operacion('', expected=1)
        self._enriquecer(segunda, [])

        persona.refresh_from_db()
        interina.refresh_from_db()
        self.assertTrue(persona.archivada)
        self.assertEqual((interina.estado, interina.veces_mencionada), ('sombra', 1))
        self.assertFalse(InteraccionSombra.objects.exists())
        self.assertFalse(Interaccion.objects.exists())
