import json
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import ActividadRealizada, GymDecisionVersion
from hyrox.models import StravaActivityRaw


class AuditarSemanaGymCommandTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='audit_semana_gym', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user,
            defaults={'nombre': 'Audit Semana Gym'},
        )
        self.desde = date(2026, 8, 3)
        self.hasta = date(2026, 8, 9)

        checkin = BitacoraDiaria.objects.create(
            cliente=self.cliente,
            horas_sueno=7.5,
            hrv_ms=62,
            fc_reposo=51,
            energia_subjetiva=8,
        )
        BitacoraDiaria.objects.filter(pk=checkin.pk).update(fecha=date(2026, 8, 4))
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='gym',
            titulo='Torso A',
            fecha=date(2026, 8, 5),
            fecha_realizado=date(2026, 8, 6),
            duracion_minutos=70,
            rpe_medio=7.5,
            carga_ua=525,
            fuente='manual',
        )
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='futbol',
            titulo='Partido',
            fecha=date(2026, 8, 7),
            duracion_minutos=60,
            rpe_medio=8,
            carga_ua=480,
            fuente='strava',
        )
        StravaActivityRaw.objects.create(
            cliente=self.cliente,
            strava_id=9001,
            fecha_actividad=date(2026, 8, 7),
            tipo_strava='Soccer',
            nombre_strava='Partido tarde',
            duracion_segundos=3600,
            hr_media=148,
            hr_maxima=181,
            raw_json={},
            estado='created',
        )
        GymDecisionVersion.objects.create(
            cliente=self.cliente,
            fecha=date(2026, 8, 5),
            version=1,
            decision_id='gym-2026-08-05-base',
            schema_version=2,
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=False,
            fingerprint='a' * 64,
            base_fingerprint='a' * 64,
            postura='empujar',
            causa_principal='sesion_hoy',
            snapshot={'postura': 'empujar'},
        )
        GymDecisionVersion.objects.create(
            cliente=self.cliente,
            fecha=date(2026, 8, 5),
            version=2,
            decision_id='gym-2026-08-05-v2',
            schema_version=2,
            origen=GymDecisionVersion.ORIGEN_CORRECCION,
            vigente=True,
            fingerprint='b' * 64,
            base_fingerprint='a' * 64,
            postura='sostener',
            causa_principal='sesion_hoy',
            snapshot={'postura': 'sostener'},
            ajustes={'postura': 'sostener'},
            motivo_correccion='Dormí peor de lo esperado',
        )

    def _ejecutar(self):
        salida = StringIO()
        call_command(
            'auditar_semana_gym',
            cliente=self.cliente.pk,
            desde=self.desde.isoformat(),
            hasta=self.hasta.isoformat(),
            stdout=salida,
        )
        return [json.loads(line) for line in salida.getvalue().splitlines() if line]

    def test_emite_contrato_jsonl_completo_y_solo_lectura(self):
        conteos_antes = {
            'decisiones': GymDecisionVersion.objects.count(),
            'actividades': ActividadRealizada.objects.count(),
            'checkins': BitacoraDiaria.objects.count(),
            'strava': StravaActivityRaw.objects.count(),
        }

        registros = self._ejecutar()

        self.assertEqual(registros[0]['tipo_registro'], 'ventana')
        self.assertEqual(registros[0]['desde'], '2026-08-03')
        self.assertEqual(registros[0]['hasta'], '2026-08-09')
        self.assertEqual(
            [r['version'] for r in registros if r['tipo_registro'] == 'decision'],
            [1, 2],
        )
        sesion = next(r for r in registros if r['tipo_registro'] == 'sesion_gym')
        self.assertEqual(sesion['fecha_planificada'], '2026-08-05')
        self.assertEqual(sesion['fecha_realizada'], '2026-08-06')
        self.assertEqual(sesion['rpe'], 7.5)
        checkin = next(r for r in registros if r['tipo_registro'] == 'checkin')
        self.assertEqual(checkin['hrv_ms'], 62)
        externa = next(r for r in registros if r['tipo_registro'] == 'carga_externa')
        self.assertEqual(externa['tipo'], 'futbol')
        resumen = registros[-1]
        self.assertEqual(resumen['tipo_registro'], 'resumen')
        self.assertTrue(resumen['solo_lectura'])
        self.assertEqual(resumen['dias_con_datos'], 4)
        self.assertEqual(resumen['versiones_decision'], 2)
        self.assertEqual(resumen['sesiones_gym'], 1)
        self.assertEqual(resumen['actividades_externas'], 1)
        self.assertEqual(resumen['checkins'], 1)
        self.assertEqual(conteos_antes, {
            'decisiones': GymDecisionVersion.objects.count(),
            'actividades': ActividadRealizada.objects.count(),
            'checkins': BitacoraDiaria.objects.count(),
            'strava': StravaActivityRaw.objects.count(),
        })

    def test_excluye_datos_fuera_de_la_ventana(self):
        fuera = BitacoraDiaria.objects.create(
            cliente=self.cliente,
            hrv_ms=99,
        )
        BitacoraDiaria.objects.filter(pk=fuera.pk).update(fecha=date(2026, 8, 2))

        registros = self._ejecutar()

        checkins = [r for r in registros if r['tipo_registro'] == 'checkin']
        self.assertEqual([r['fecha'] for r in checkins], ['2026-08-04'])

    def test_incluye_sesion_por_fecha_real_aunque_el_plan_sea_anterior(self):
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='gym',
            titulo='Reubicada desde domingo',
            fecha=date(2026, 8, 2),
            fecha_realizado=date(2026, 8, 3),
            duracion_minutos=50,
            rpe_medio=7,
            carga_ua=350,
            fuente='manual',
        )

        registros = self._ejecutar()

        sesiones = [r for r in registros if r['tipo_registro'] == 'sesion_gym']
        self.assertEqual(len(sesiones), 2)
        reubicada = next(r for r in sesiones if r['titulo'] == 'Reubicada desde domingo')
        self.assertEqual(reubicada['fecha_planificada'], '2026-08-02')
        self.assertEqual(reubicada['fecha_realizada'], '2026-08-03')
