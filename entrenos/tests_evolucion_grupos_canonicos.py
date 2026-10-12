"""Evolución: un único nombre por grupo muscular (sin duplicados por tildes)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from entrenos.services.estadisticas_service import EstadisticasService, _grupo_canonico
from rutinas.models import Rutina


class GruposCanonicosTests(TestCase):
    def test_variantes_de_tilde_se_unen(self):
        self.assertEqual(_grupo_canonico('Cuadriceps'), 'Cuádriceps')
        self.assertEqual(_grupo_canonico('Cúadriceps'), _grupo_canonico('cuádriceps'))
        self.assertEqual(_grupo_canonico(None, 'Jalón al pecho'), 'Espalda')
        self.assertEqual(_grupo_canonico(None, 'zzz'), 'Otros')

    def test_distribucion_sin_duplicados(self):
        user = get_user_model().objects.create_user('evo-grupos', password='x')
        cliente = Cliente.objects.get(user=user)
        entreno = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=Rutina.objects.create(nombre='r'), fecha=timezone.localdate(),
        )
        for grupo in ('Cuadriceps', 'Cuádriceps', 'cuadriceps'):
            EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
                entreno=entreno, nombre_ejercicio=f'Prensa {grupo}', grupo_muscular=grupo,
                peso_kg=100, series=3, repeticiones=10, completado=True,
            )])
        datos = EstadisticasService.calcular_distribucion_muscular(cliente, '30d')
        self.assertEqual(datos['labels'], ['Cuádriceps'])
