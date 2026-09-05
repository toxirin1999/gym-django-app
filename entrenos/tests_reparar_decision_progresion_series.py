import io
import json
from datetime import date

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado,
    EntrenoRealizado,
    GymAdaptationProfile,
    GymDecisionLog,
    GymDecisionVersion,
    SerieRealizada,
)
from rutinas.models import EjercicioBase, Rutina


class RepararDecisionProgresionSeriesTests(TestCase):
    NOMBRE = 'Press Militar Con Mancuernas (Sentado)'

    def setUp(self):
        user = User.objects.create_user('reparar-decision-series', password='x')
        self.cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre='_reparar_decision_series')
        base = EjercicioBase.objects.create(
            nombre=self.NOMBRE,
            grupo_muscular='hombros',
            tipo_progresion='peso_reps',
        )
        version = GymDecisionVersion.objects.create(
            cliente=self.cliente,
            fecha=date.today(),
            version=1,
            decision_id='gym-reparar-series',
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=True,
            fingerprint='reparar-series',
            base_fingerprint='reparar-series-base',
            postura='empujar',
            snapshot={
                'entrenamiento': {
                    'ejercicios': [{
                        'nombre': self.NOMBRE,
                        'reps_objetivo': 8,
                        'peso_recomendado_kg': 45,
                    }],
                },
            },
        )
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=date.today(),
            gym_decision_version=version,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=self.NOMBRE,
            peso_kg=45,
            series=5,
            repeticiones=8,
            rpe=8,
            grupo_muscular='hombros',
            completado=True,
        )
        for numero, reps in enumerate((9, 9, 9, 9, 6), 1):
            SerieRealizada.objects.create(
                entreno=entreno,
                ejercicio=base,
                serie_numero=numero,
                peso_kg=45,
                repeticiones=reps,
                rpe_real=8,
                completado=True,
            )
        self.decision = GymDecisionLog.objects.create(
            cliente=self.cliente,
            entreno_origen=entreno,
            ejercicio=self.NOMBRE.casefold(),
            ejercicio_normalizado=self.NOMBRE.casefold(),
            peso_anterior=45,
            reps_anteriores=8,
            rpe_anterior=8,
            accion='mantener',
            valor_cambio=None,
            motivo='Parámetros estables — mantener y enfocar en técnica',
            motivo_codigo='',
            confianza='media',
        )

    def ejecutar(self, *args):
        salida = io.StringIO()
        call_command(
            'reparar_decision_progresion_series',
            str(self.decision.pk),
            *args,
            stdout=salida,
        )
        return json.loads(salida.getvalue())

    def test_dry_run_propone_subida_sin_modificar_la_decision(self):
        GymAdaptationProfile.objects.filter(
            cliente=self.cliente,
            ejercicio=self.NOMBRE.casefold(),
        ).delete()

        resultado = self.ejecutar()

        self.decision.refresh_from_db()
        self.assertEqual(resultado['estado'], 'candidata')
        self.assertEqual(resultado['media_reps'], '8.4')
        self.assertEqual(resultado['objetivo_reps'], '8')
        self.assertEqual(resultado['propuesto']['accion'], 'subir_peso')
        self.assertEqual(resultado['propuesto']['motivo_codigo'], 'progresion_peso')
        self.assertEqual(self.decision.accion, 'mantener')
        self.assertFalse(GymAdaptationProfile.objects.filter(
            cliente=self.cliente,
            ejercicio=self.NOMBRE.casefold(),
        ).exists())

    def test_apply_corrige_y_es_idempotente(self):
        aplicado = self.ejecutar('--apply')

        self.decision.refresh_from_db()
        self.assertEqual(aplicado['estado'], 'aplicada')
        self.assertEqual(self.decision.accion, 'subir_peso')
        self.assertEqual(self.decision.motivo_codigo, 'progresion_peso')
        self.assertEqual(self.decision.reps_anteriores, 8)
        self.assertIn('Media 8,4 frente al objetivo 8', self.decision.motivo)

        repetido = self.ejecutar('--apply')
        self.assertEqual(repetido['estado'], 'ya_consistente')

    def test_permite_objetivo_explicito_si_el_snapshot_legacy_no_lo_conserva(self):
        version = self.decision.entreno_origen.gym_decision_version
        version.snapshot = {'entrenamiento': {'ejercicios': []}}
        version.save(update_fields=['snapshot'])

        with self.assertRaisesMessage(CommandError, 'objetivo inmutable'):
            self.ejecutar()

        resultado = self.ejecutar('--objetivo-reps', '8')

        self.assertEqual(resultado['estado'], 'candidata')
        self.assertEqual(resultado['objetivo_reps'], '8')
        self.assertEqual(resultado['objetivo_origen'], 'argumento_explicito')
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.accion, 'mantener')

    def test_rechaza_objetivo_explicito_que_contradice_el_snapshot(self):
        with self.assertRaisesMessage(CommandError, 'contradice el snapshot'):
            self.ejecutar('--objetivo-reps', '9')

    def test_rechaza_una_decision_que_ya_fue_aplicada(self):
        self.decision.estado_aplicacion = 'aplicada'
        self.decision.save(update_fields=['estado_aplicacion'])

        with self.assertRaisesMessage(CommandError, 'no está pendiente'):
            self.ejecutar('--apply')
