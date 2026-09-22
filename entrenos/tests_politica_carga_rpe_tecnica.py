from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    EntrenoRealizado,
    EjercicioRealizado,
    GymDecisionLog,
    SerieRealizada,
)
from entrenos.services.decision_log_service import generar_decisiones_para_entreno
from rutinas.models import EjercicioBase, Rutina


class PoliticaIncrementosFisicosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='incrementos_fisicos')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Incrementos', 'dias_disponibles': 4},
        )

    def _log(self, nombre, peso):
        return GymDecisionLog(
            cliente=self.cliente,
            ejercicio=nombre,
            ejercicio_normalizado=nombre.lower(),
            accion='subir_peso',
            valor_cambio=5,
            peso_anterior=peso,
        )

    def test_maquina_redondea_sugerencia_canonica_a_saltos_de_5_kg(self):
        EjercicioBase.objects.create(
            nombre='Press de pecho en máquina', grupo_muscular='Pecho',
            equipo='Máquina selectorizada', incremento_kg=2.5,
        )
        self.assertEqual(self._log('Press de pecho en máquina', 60).peso_sugerido, 65)

    def test_barra_redondea_sugerencia_canonica_a_saltos_de_2_kg(self):
        EjercicioBase.objects.create(
            nombre='Press banca con barra', grupo_muscular='Pecho',
            equipo='Barra y discos', incremento_kg=2.5,
        )
        self.assertEqual(self._log('Press banca con barra', 80).peso_sugerido, 84)

    def test_contexto_ui_usa_la_misma_politica_fisica(self):
        maquina = EjercicioBase.objects.create(
            nombre='Remo en máquina', grupo_muscular='Espalda', equipo='Máquina',
        )
        barra = EjercicioBase.objects.create(
            nombre='Sentadilla con barra', grupo_muscular='Pierna', equipo='Barra',
        )
        self.assertEqual(float(maquina.incremento_fisico_kg), 5.0)
        self.assertEqual(float(barra.incremento_fisico_kg), 2.0)


class RPERealObligatorioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rpe_obligatorio', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'RPE', 'dias_disponibles': 4},
        )
        Rutina.objects.create(nombre='Fuerza RPE')
        EjercicioBase.objects.create(nombre='Sentadilla RPE', grupo_muscular='Pierna')
        self.client.force_login(self.user)
        self.url = reverse(
            'entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id},
        )

    def _post(self, rpe_real=None):
        data = {
            'fecha': '2026-09-17', 'rutina_nombre': 'Fuerza RPE',
            'ej1_nombre': 'Sentadilla RPE', 'ej1_tipo_progresion': 'peso_reps',
            'ej1_peso_1': '80', 'ej1_reps_1': '8', 'ej1_completado_1': '1',
            'ej1_rpe_obj_1': '7', 'ej1_tecnica_1': 'buena',
        }
        if rpe_real is not None:
            data['ej1_rpe_1'] = rpe_real
        return self.client.post(
            self.url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_backend_rechaza_serie_completada_sin_rpe_real_aunque_haya_objetivo(self):
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertIn('RPE real', response.json()['error'])
        self.assertFalse(EntrenoRealizado.objects.filter(cliente=self.cliente).exists())

    def test_backend_acepta_y_persiste_rpe_real_explicito(self):
        response = self._post('8')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SerieRealizada.objects.get().rpe_real, 8)

    def test_ui_no_preselecciona_ni_rellena_rpe_real_con_el_objetivo(self):
        source = open('entrenos/templates/entrenos/entrenamiento_activo.html').read()
        self.assertNotIn('name="{{ ejercicio.form_id }}_rpe_{{ sn }}" value="{{ ejercicio.rpe_objetivo }}"', source)
        self.assertNotIn('rpe-pick-btn {% if ejercicio.rpe_objetivo ==', source)
        self.assertIn('Selecciona el RPE real', source)


class RepsExtraYTecnicaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reps_tecnica')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'Reps técnica', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Rutina técnica')
        self.base = EjercicioBase.objects.create(
            nombre='Press técnico', grupo_muscular='Pecho', tipo_progresion='peso_reps',
        )

    def _generar(self, tecnica):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 9, 17),
        )
        ejercicio = EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press técnico', peso_kg=60,
            series=1, repeticiones=10, rpe=8, completado=True,
        )
        SerieRealizada.objects.create(
            entreno=entreno, ejercicio=self.base, serie_numero=1, peso_kg=60,
            repeticiones=10, rpe_real=8, tecnica_calidad=tecnica, completado=True,
        )
        with patch(
            'entrenos.services.decision_log_service._objetivo_repeticiones_snapshot',
            return_value=Decimal('8'),
        ):
            generar_decisiones_para_entreno(entreno)
        return GymDecisionLog.objects.get(entreno_origen=entreno)

    def test_reps_extra_con_cualquier_tecnica_no_comprometida_alimentan_progresion(self):
        for tecnica in ('buena', 'aceptable'):
            with self.subTest(tecnica=tecnica):
                GymDecisionLog.objects.all().delete()
                log = self._generar(tecnica)
                self.assertEqual(log.accion, 'subir_peso')

    def test_reps_extra_con_tecnica_comprometida_bloquean_progresion(self):
        log = self._generar('comprometida')
        self.assertEqual(log.accion, 'mantener')
        self.assertEqual(log.motivo_codigo, 'tecnica_comprometida')
