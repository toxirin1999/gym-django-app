import datetime
import json
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym
from django.core.exceptions import ValidationError
from entrenos.models import GymDecisionVersion, CicloDeload
from joi.models import MensajeJOI
from hyrox.models import ContratoCampanaHyrox, HyroxObjective, HyroxSession
from hyrox.campaign_authority import (
    auditar_campana,
    resolver_autoridad_campana,
)


class CampanaHyrox7ATests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('campana7a')
        self.cliente = self.user.cliente_perfil
        self.hoy = datetime.date(2026, 8, 22)
        self.objetivo = HyroxObjective.objects.create(
            cliente=self.cliente, fecha_evento=datetime.date(2026, 12, 1)
        )
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5,
            minimo_valido=3, vigente_desde=self.hoy,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=1, estado='activo',
            semana_inicio=self.hoy, semanas_previstas=4,
            semana_fin_prevista=datetime.date(2026, 9, 20), estrategia=estrategia,
            objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='hipertrofia', objetivos_secundarios=[],
            limites_snapshot={}, motor_nombre='Helms', motor_version='actual',
            fingerprint='a' * 64,
        )

    def test_legacy_es_inactiva_y_solo_permite_carga_strava_seguridad(self):
        autoridad = resolver_autoridad_campana(self.cliente, self.hoy)
        self.assertEqual(autoridad['estado'], 'inactiva')
        self.assertEqual(autoridad['origen'], 'inactiva_legacy')
        self.assertTrue(autoridad['permisos']['aportar_carga'])
        self.assertTrue(autoridad['permisos']['sincronizar_strava'])
        self.assertTrue(autoridad['permisos']['seguridad'])
        self.assertFalse(autoridad['permisos']['generar_plan'])
        self.assertFalse(autoridad['permisos']['competir_con_gym'])

    def test_activa_exige_objetivo_futuro_y_bloque_abierto(self):
        ContratoCampanaHyrox.objects.create(
            cliente=self.cliente, version=1, estado='activa', objetivo=self.objetivo,
            bloque_gym=self.bloque, objetivo_snapshot={'fecha_evento': '2026-12-01'},
            bloque_gym_snapshot={'estado': 'activo'}, limites_snapshot={},
            fingerprint='b' * 64,
        )
        autoridad = resolver_autoridad_campana(self.cliente, self.hoy)
        self.assertTrue(autoridad['permisos']['generar_plan'])
        self.objetivo.fecha_evento = datetime.date(2026, 1, 1)
        self.objetivo.save(update_fields=['fecha_evento'])
        autoridad = resolver_autoridad_campana(self.cliente, self.hoy)
        self.assertEqual(autoridad['estado'], 'inactiva')
        self.assertIn('objetivo_vencido', autoridad['hallazgos'])

    def test_dry_run_no_escribe_y_apply_solo_crea_contrato(self):
        out = StringIO()
        call_command('configurar_campana_hyrox', cliente=self.cliente.pk,
                     estado='exploracion', stdout=out)
        self.assertEqual(ContratoCampanaHyrox.objects.count(), 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload['solo_lectura'])
        sesiones = HyroxSession.objects.count()
        call_command('configurar_campana_hyrox', cliente=self.cliente.pk,
                     estado='exploracion', apply=True, stdout=StringIO())
        self.assertEqual(ContratoCampanaHyrox.objects.count(), 1)
        self.assertEqual(HyroxSession.objects.count(), sesiones)

    def test_auditoria_detecta_objetivo_legacy_y_sesion_futura(self):
        HyroxSession.objects.create(objective=self.objetivo, fecha=self.hoy + datetime.timedelta(days=2))
        reporte = auditar_campana(self.cliente, self.hoy)
        codigos = {x['code'] for x in reporte['hallazgos']}
        self.assertIn('objetivo_activo_sin_campana', codigos)
        self.assertIn('sesion_futura_sin_campana_activa', codigos)

    def test_snapshot_aprobado_es_inmutable(self):
        contrato = ContratoCampanaHyrox.objects.create(
            cliente=self.cliente, version=1, estado='exploracion',
            objetivo_snapshot={}, bloque_gym_snapshot={}, limites_snapshot={},
            fingerprint='c' * 64, aprobado_en=datetime.datetime.now(datetime.timezone.utc),
        )
        contrato.limites_snapshot = {'mutado': True}
        with self.assertRaisesMessage(ValidationError, 'Una campaña aprobada es inmutable; crea una versión sucesora.'):
            contrato.save()

    def test_snapshot_persistido_es_append_only_aunque_legacy_no_tenga_aprobacion(self):
        contrato = ContratoCampanaHyrox.objects.create(
            cliente=self.cliente, version=1, estado='inactiva',
            objetivo_snapshot={}, bloque_gym_snapshot={}, limites_snapshot={},
            fingerprint='d' * 64,
        )
        contrato.estado = 'exploracion'
        with self.assertRaises(ValidationError):
            contrato.save()

    def test_apply_rechaza_version_optimista_obsoleta(self):
        call_command('configurar_campana_hyrox', cliente=self.cliente.pk,
                     estado='exploracion', apply=True, version_esperada=0,
                     stdout=StringIO())
        with self.assertRaises(Exception):
            call_command('configurar_campana_hyrox', cliente=self.cliente.pk,
                         estado='finalizada', apply=True, version_esperada=0,
                         stdout=StringIO())
        self.assertEqual(ContratoCampanaHyrox.objects.count(), 1)

    def test_auditoria_es_estrictamente_solo_lectura(self):
        antes = (ContratoCampanaHyrox.objects.count(), HyroxObjective.objects.count(),
                 HyroxSession.objects.count())
        out = StringIO()
        call_command('auditar_campana_hyrox', cliente=self.cliente.pk,
                     fecha='2026-08-22', stdout=out)
        despues = (ContratoCampanaHyrox.objects.count(), HyroxObjective.objects.count(),
                   HyroxSession.objects.count())
        self.assertEqual(antes, despues)
        lineas = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(lineas[0]['tipo'], 'meta')
        self.assertTrue(lineas[0]['solo_lectura'])
        self.assertEqual(lineas[-1]['tipo'], 'resumen')

    def test_matriz_permisos_exacta_para_cuatro_estados(self):
        from hyrox.campaign_authority import PERMISOS
        comunes = {'aportar_carga': True, 'sincronizar_strava': True,
                   'seguridad': True, 'registro_manual': True,
                   'competir_con_gym': False}
        for estado in ('inactiva', 'exploracion', 'activa', 'finalizada'):
            for clave, valor in comunes.items():
                self.assertEqual(PERMISOS[estado][clave], valor)
        self.assertTrue(PERMISOS['exploracion']['lecturas_exploracion'])
        self.assertFalse(PERMISOS['exploracion']['generar_plan'])
        for permiso in ('generar_plan', 'programar_sesiones', 'correctivos',
                        'autoajuste', 'joi_hyrox'):
            self.assertTrue(PERMISOS['activa'][permiso])
            self.assertFalse(PERMISOS['finalizada'][permiso])

    def test_apply_identico_es_idempotente_y_persiste_actor(self):
        from hyrox.campaign_authority import configurar
        primero = configurar(self.cliente, 'exploracion', actor=self.user)
        segundo = configurar(self.cliente, 'exploracion', actor=self.user,
                             version_esperada=1)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(ContratoCampanaHyrox.objects.count(), 1)
        self.assertEqual(primero.aprobado_por, self.user)

    def test_reingreso_a_semantica_historica_crea_sucesora_y_luego_es_idempotente(self):
        from hyrox.campaign_authority import configurar, resolver_autoridad_campana
        v1 = configurar(self.cliente, 'exploracion', actor=self.user)
        v2 = configurar(self.cliente, 'activa', self.objetivo, self.bloque,
                        actor=self.user, version_esperada=1)
        v3 = configurar(self.cliente, 'exploracion', actor=self.user,
                        version_esperada=2)
        repetida = configurar(self.cliente, 'exploracion', actor=self.user,
                              version_esperada=3)
        self.assertEqual((v1.version, v2.version, v3.version), (1, 2, 3))
        self.assertNotEqual(v1.fingerprint, v3.fingerprint)
        self.assertEqual(repetida.pk, v3.pk)
        self.assertEqual(ContratoCampanaHyrox.objects.count(), 3)
        autoridad = resolver_autoridad_campana(self.cliente, self.hoy)
        self.assertEqual(autoridad['estado'], 'exploracion')
        self.assertEqual(autoridad['version'], 3)

    def test_dry_run_solo_marca_existente_si_la_vigente_es_identica(self):
        from hyrox.campaign_authority import configurar, previsualizar
        v1 = configurar(self.cliente, 'exploracion', actor=self.user)
        configurar(self.cliente, 'activa', self.objetivo, self.bloque,
                   actor=self.user, version_esperada=1)
        retorno = previsualizar(self.cliente, 'exploracion')
        self.assertFalse(retorno['propuesta_existente'])
        self.assertEqual(retorno['version'], 3)
        self.assertNotEqual(retorno['fingerprint'], v1.fingerprint)

    def test_actor_debe_ser_propietario(self):
        from hyrox.campaign_authority import configurar
        ajeno = User.objects.create_user('ajeno7a')
        with self.assertRaisesMessage(ValueError, 'El actor no es propietario del cliente.'):
            configurar(self.cliente, 'exploracion', actor=ajeno)

    def test_finalizada_es_terminal_y_activa_no_nace_directamente(self):
        from hyrox.campaign_authority import configurar
        with self.assertRaisesMessage(ValueError, 'Transición inválida: ausencia → activa.'):
            configurar(self.cliente, 'activa', self.objetivo, self.bloque, actor=self.user)
        explorar = configurar(self.cliente, 'exploracion', actor=self.user)
        activa = configurar(self.cliente, 'activa', self.objetivo, self.bloque,
                            actor=self.user, version_esperada=explorar.version)
        final = configurar(self.cliente, 'finalizada', actor=self.user,
                           version_esperada=activa.version)
        with self.assertRaisesMessage(ValueError, 'Una campaña finalizada es terminal.'):
            configurar(self.cliente, 'exploracion', actor=self.user,
                        version_esperada=final.version)

    def test_finalizada_identica_es_idempotente_pero_no_puede_revivir(self):
        from hyrox.campaign_authority import configurar
        explorar = configurar(self.cliente, 'exploracion', actor=self.user)
        final = configurar(self.cliente, 'finalizada', actor=self.user,
                           version_esperada=explorar.version)
        repetida = configurar(self.cliente, 'finalizada', actor=self.user,
                              version_esperada=final.version)
        self.assertEqual(repetida.pk, final.pk)
        self.assertEqual(ContratoCampanaHyrox.objects.count(), 2)
        with self.assertRaisesMessage(ValueError, 'Una campaña finalizada es terminal.'):
            configurar(self.cliente, 'inactiva', actor=self.user,
                        version_esperada=final.version)

    def test_inventario_tiene_codigos_estables_y_contrato_explicito(self):
        from hyrox.campaign_authority import INVENTARIO_AUTOMATIZACIONES
        codigos = {x['code'] for x in INVENTARIO_AUTOMATIZACIONES}
        esperados = {'plan_generacion', 'plan_regeneracion', 'auto_adjust_override',
                     'lesion_regeneracion', 'adaptacion_doble', 'rm_pace',
                     'correctivos', 'deload', 'bitacora_fatiga', 'gym_fatiga_rm',
                     'cinco_k', 'joi_countdown', 'joi_post', 'joi_readiness',
                     'joi_estancamiento', 'dashboard_gym_no_canonico'}
        self.assertTrue(esperados.issubset(codigos))
        for item in INVENTARIO_AUTOMATIZACIONES:
            self.assertEqual(set(item), {'code', 'superficie', 'mutacion',
                                         'permiso_requerido', 'siempre_permitido',
                                         'cubierto_7a'})

    def test_comandos_no_mutan_otros_motores(self):
        antes = (GymDecisionVersion.objects.count(), CicloDeload.objects.count(),
                 MensajeJOI.objects.count(), HyroxSession.objects.count(),
                 HyroxObjective.objects.count())
        call_command('configurar_campana_hyrox', cliente=self.cliente.pk,
                     estado='exploracion', apply=True, stdout=StringIO())
        call_command('auditar_campana_hyrox', cliente=self.cliente.pk,
                     fecha='2026-08-22', stdout=StringIO())
        despues = (GymDecisionVersion.objects.count(), CicloDeload.objects.count(),
                   MensajeJOI.objects.count(), HyroxSession.objects.count(),
                   HyroxObjective.objects.count())
        self.assertEqual(antes, despues)
