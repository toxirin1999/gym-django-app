from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado,
    EjercicioLiftinDetallado,
    EntrenoRealizado,
    RecordPersonal,
    SerieRealizada,
    SesionEntrenamiento,
    GymDecisionLog,
    GymDecisionVersion,
)
from entrenos.services.decision_log_service import generar_decisiones_para_entreno
from entrenos.services.records_service import RecordsService
from rutinas.models import EjercicioBase, Rutina


class AutoridadSeriesBase(TestCase):
    NOMBRE = 'Curl Femoral Autoridad Series'
    SERIES = ((60, 4), (65, 4), (65, 3), (65, 3))

    def setUp(self):
        self.user = User.objects.create_user('autoridad-series', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='_autoridad_series')
        self.base = EjercicioBase.objects.create(
            nombre=self.NOMBRE,
            grupo_muscular='piernas',
        )

    def crear_entreno_detallado(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=self.NOMBRE,
            peso_kg=Decimal('63.75'),
            series=4,
            repeticiones=3,
            grupo_muscular='piernas',
            completado=True,
        )
        for numero, (peso, reps) in enumerate(self.SERIES, 1):
            SerieRealizada.objects.create(
                entreno=entreno,
                ejercicio=self.base,
                serie_numero=numero,
                peso_kg=peso,
                repeticiones=reps,
                completado=True,
            )
        return entreno


class RecordsDesdeSeriesTests(AutoridadSeriesBase):
    def test_peso_y_volumen_del_record_proceden_de_series_completadas(self):
        entreno = self.crear_entreno_detallado()

        RecordsService.detectar_records_sesion(entreno)

        self.assertEqual(
            RecordPersonal.objects.get(tipo_record='peso_maximo').valor,
            Decimal('65'),
        )
        self.assertEqual(
            RecordPersonal.objects.get(tipo_record='volumen_total').valor,
            Decimal('890'),
        )

    def test_sin_series_conserva_fallback_del_agregado_manual(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Peso Muerto Legacy Autoridad',
            peso_kg=100,
            series=2,
            repeticiones=5,
            grupo_muscular='piernas',
            completado=True,
        )

        RecordsService.detectar_records_sesion(entreno)

        self.assertEqual(
            RecordPersonal.objects.get(
                ejercicio_nombre='Peso Muerto Legacy Autoridad',
                tipo_record='peso_maximo',
            ).valor,
            Decimal('100'),
        )
        self.assertEqual(
            RecordPersonal.objects.get(
                ejercicio_nombre='Peso Muerto Legacy Autoridad',
                tipo_record='volumen_total',
            ).valor,
            Decimal('1000'),
        )


class VolumenEntrenoDesdeSeriesTests(AutoridadSeriesBase):
    def test_calcular_volumen_total_no_suma_agregado_y_detalle(self):
        entreno = self.crear_entreno_detallado()

        self.assertEqual(entreno.calcular_volumen_total(), Decimal('890'))

    def test_sin_series_conserva_fallback_liftin(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
        )
        EjercicioLiftinDetallado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Press Banca Liftin Autoridad',
            peso_kg=80,
            series_realizadas=3,
            repeticiones_min=5,
            completado=True,
        )

        self.assertEqual(entreno.calcular_volumen_total(), Decimal('1200'))


class DecisionProgresionDesdeSeriesTests(AutoridadSeriesBase):
    def crear_version_con_objetivo(self, repeticiones=8):
        return GymDecisionVersion.objects.create(
            cliente=self.cliente,
            fecha=date.today(),
            version=1,
            decision_id='gym-objetivo-series',
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=True,
            fingerprint='objetivo-series',
            base_fingerprint='objetivo-series-base',
            postura='empujar',
            snapshot={
                'entrenamiento': {
                    'ejercicios': [{
                        'nombre': self.NOMBRE,
                        'reps_objetivo': repeticiones,
                        'peso_recomendado_kg': 45,
                    }],
                },
            },
        )

    def test_media_superior_al_objetivo_considera_superado_el_ejercicio(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            gym_decision_version=self.crear_version_con_objetivo(8),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=self.NOMBRE,
            peso_kg=45,
            series=5,
            repeticiones=8,  # promedio legacy: no es la autoridad causal
            rpe=8,
            grupo_muscular='piernas',
            completado=True,
        )
        for numero, reps in enumerate((9, 9, 9, 9, 6), 1):
            SerieRealizada.objects.create(
                entreno=entreno,
                ejercicio=self.base,
                serie_numero=numero,
                peso_kg=45,
                repeticiones=reps,
                rpe_real=8,
                completado=True,
            )

        generar_decisiones_para_entreno(entreno)

        decision = GymDecisionLog.objects.get(entreno_origen=entreno)
        self.assertEqual(decision.peso_anterior, 45)
        self.assertEqual(decision.reps_anteriores, 8)
        self.assertEqual(decision.accion, 'subir_peso')
        self.assertIn('media 8,4', decision.motivo.lower())
        self.assertIn('objetivo 8', decision.motivo)

    def test_media_inferior_al_objetivo_bloquea_una_subida(self):
        anterior = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
        )
        EjercicioRealizado.objects.create(
            entreno=anterior,
            nombre_ejercicio=self.NOMBRE,
            peso_kg=45,
            series=5,
            repeticiones=8,
            rpe=7,
            grupo_muscular='piernas',
            completado=True,
        )
        version = self.crear_version_con_objetivo(8)
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            gym_decision_version=version,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=self.NOMBRE,
            peso_kg=45,
            series=5,
            repeticiones=7,
            rpe=7,
            grupo_muscular='piernas',
            completado=True,
        )
        for numero, reps in enumerate((8, 8, 7, 7, 7), 1):
            SerieRealizada.objects.create(
                entreno=entreno,
                ejercicio=self.base,
                serie_numero=numero,
                peso_kg=45,
                repeticiones=reps,
                rpe_real=7,
                completado=True,
            )

        generar_decisiones_para_entreno(entreno)

        decision = GymDecisionLog.objects.get(entreno_origen=entreno)
        self.assertEqual(decision.accion, 'mantener')
        self.assertIn('media 7,4', decision.motivo.lower())
        self.assertIn('objetivo 8', decision.motivo)

    def test_decision_sin_series_conserva_el_resumen_legacy(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=self.NOMBRE,
            peso_kg=45,
            series=5,
            repeticiones=8,
            rpe=8,
            grupo_muscular='piernas',
            completado=True,
        )

        generar_decisiones_para_entreno(entreno)

        decision = GymDecisionLog.objects.get(entreno_origen=entreno)
        self.assertEqual(decision.peso_anterior, 45)
        self.assertEqual(decision.reps_anteriores, 8)


class GuardadoSesionDesdeBackendTests(AutoridadSeriesBase):
    def test_sesion_ignora_volumen_del_front_y_usa_suma_exacta_backend(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk]),
            {
                'fecha': date.today().isoformat(),
                'rutina_nombre': self.rutina.nombre,
                'ej1_nombre': self.NOMBRE,
                'ej1_tipo_progresion': 'peso_reps',
                'ej1_peso_1': '60', 'ej1_reps_1': '4', 'ej1_completado_1': '1',
                'ej1_peso_2': '65', 'ej1_reps_2': '4', 'ej1_completado_2': '1',
                'ej1_peso_3': '65', 'ej1_reps_3': '3', 'ej1_completado_3': '1',
                'ej1_peso_4': '65', 'ej1_reps_4': '3', 'ej1_completado_4': '1',
                'volumen_total_sesion': '5100',
            },
        )

        self.assertEqual(response.status_code, 302)
        entreno = EntrenoRealizado.objects.get(cliente=self.cliente)
        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(entreno.volumen_total_kg, Decimal('890'))
        self.assertEqual(sesion.volumen_sesion, Decimal('890'))
