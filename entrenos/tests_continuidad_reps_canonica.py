import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client as DjangoClient, TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from rutinas.models import Rutina


class ContinuidadRepsCanonicaTests(TestCase):
    NOMBRE = 'Elevaciones De Piernas Colgado Canonica Test'

    def setUp(self):
        self.user = User.objects.create_user(username='continuidad_reps', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={'nombre': 'Continuidad reps', 'dias_disponibles': 4},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_continuidad_reps')
        self.http = DjangoClient()
        self.http.force_login(self.user)

    def _registrar_historico(self, reps):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today() - timedelta(days=3),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=self.NOMBRE,
            peso_kg=0,
            repeticiones=reps,
            rpe=8,
        )

    def _abrir_sesion(self, **extra):
        ejercicio = {
            'nombre': self.NOMBRE,
            'series': 3,
            'repeticiones': '8-12',
            'peso_kg': 0,
            'tipo_progresion': 'progresion_reps',
            'tipo_ejercicio': 'accesorio',
            '_autoridad_gym_materializada': True,
            **extra,
        }
        response = self.http.get(
            reverse('entrenos:entrenamiento_activo', args=[self.cliente.id]),
            {
                'fecha': date.today().isoformat(),
                'rutina_nombre': 'Sesion canonica de test',
                'ejercicios': json.dumps([ejercicio]),
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.context['ejercicios_planificados'][0]

    def test_sin_decision_explicita_continua_desde_ultima_repeticion(self):
        self._registrar_historico(9)

        ejercicio = self._abrir_sesion()

        self.assertEqual(ejercicio['reps_objetivo'], 9)

    def test_decision_subir_reps_materializada_se_aplica_despues_del_historico(self):
        self._registrar_historico(9)

        ejercicio = self._abrir_sesion(
            reps_objetivo=10,
            progresion_aplicada=True,
            progresion_accion='subir_reps',
        )

        self.assertEqual(ejercicio['reps_objetivo'], 10)

    def test_decision_mantener_materializada_no_se_sobrescribe(self):
        self._registrar_historico(9)

        ejercicio = self._abrir_sesion(
            reps_objetivo=8,
            progresion_accion='mantener',
        )

        self.assertEqual(ejercicio['reps_objetivo'], 8)

    def test_continuidad_respeta_el_limite_superior_del_rango(self):
        self._registrar_historico(15)

        ejercicio = self._abrir_sesion()

        self.assertEqual(ejercicio['reps_objetivo'], 12)
