"""Regla 4: el entrenador comprueba si acertó, con el dato de la sesión siguiente."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog
from entrenos.services.aprendizaje_decisiones_service import (
    decisiones_evaluadas, describir_accion, frase_decision,
)
from rutinas.models import EjercicioBase, Rutina


class AprendizajeDecisionesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('regla4', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        EjercicioBase.objects.create(nombre='Press banca')

    def _entreno(self, dias_atras, peso, reps, rpe):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre=f'r{dias_atras}'),
            fecha=timezone.localdate() - timedelta(days=dias_atras),
        )
        EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
            entreno=entreno, nombre_ejercicio='Press banca', peso_kg=peso,
            repeticiones=reps, series=3, rpe=rpe, completado=True,
        )])
        return entreno

    def _log(self, origen, resultado, notas='', accion='subir_peso', valor=5.0):
        return GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio='press banca', ejercicio_normalizado='press banca',
            entreno_origen=origen, accion=accion, valor_cambio=valor,
            peso_anterior=60, reps_anteriores=10, rpe_anterior=7, motivo='x',
            resultado=resultado, notas_resultado=notas, fecha_evaluacion=timezone.now(),
        )

    def test_subida_validada_cita_el_peso_y_la_sesion_siguiente(self):
        origen = self._entreno(10, 60, 10, 7)
        self._entreno(5, 62.5, 10, 7)
        texto = frase_decision(self._log(origen, 'validada'))
        self.assertTrue(texto.startswith('Press banca: subí el peso a '))
        self.assertIn('Después: 62,5 kg × 10 con RPE 7.', texto)
        self.assertTrue(texto.endswith('Funcionó.'))
        self.assertNotIn('+5 kg', texto)  # el 5 es un porcentaje interno

    def test_fallida_explica_por_que(self):
        origen = self._entreno(10, 60, 10, 7)
        self._entreno(5, 62.5, 8, 9.5)
        texto = frase_decision(self._log(origen, 'fallida', 'El objetivo exigió un RPE 9.5, sin margen sostenible'))
        self.assertIn('No funcionó: el objetivo exigió un RPE 9.5', texto)

    def test_sin_sesion_siguiente_no_inventa_el_despues(self):
        origen = self._entreno(10, 60, 10, 7)
        texto = frase_decision(self._log(origen, 'neutra', 'Falta el RPE'))
        self.assertNotIn('Después', texto)
        self.assertIn('Aún sin conclusión', texto)

    def test_mantener_cita_el_peso(self):
        log = GymDecisionLog(ejercicio='Remo', accion='mantener', peso_anterior=50, motivo='x')
        self.assertEqual(describir_accion(log), 'mantuve 50 kg')

    def test_resumen_cuenta_por_veredicto_y_ventana(self):
        self._log(self._entreno(12, 60, 10, 7), 'validada')
        self._log(self._entreno(11, 60, 10, 7), 'fallida', 'x')
        viejo = self._log(self._entreno(10, 60, 10, 7), 'validada')
        GymDecisionLog.objects.filter(pk=viejo.pk).update(fecha_evaluacion=timezone.now() - timedelta(days=60))
        resumen = decisiones_evaluadas(self.cliente)
        self.assertEqual((resumen['total'], resumen['funcionaron'], resumen['no_funcionaron']), (2, 1, 1))
        self.assertEqual(len(resumen['items']), 1)  # mismo ejercicio: una línea

    def test_memoria_muestra_el_bloque(self):
        origen = self._entreno(10, 60, 10, 7)
        self._entreno(5, 62.5, 10, 7)
        self._log(origen, 'validada')
        self.client.force_login(self.user)
        response = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertContains(response, 'Lo que decidí y si funcionó')
        self.assertContains(response, '1 de 1 funcionaron')
        self.assertContains(response, 'Después: 62,5 kg × 10 con RPE 7.')

    def test_la_lista_omite_consolidaciones_y_repite_un_ejercicio_una_vez(self):
        self._log(self._entreno(12, 60, 10, 7), 'neutra', 'Sin cambio claro', accion='mantener')
        self._log(self._entreno(11, 60, 10, 7), 'validada')
        self._log(self._entreno(10, 60, 10, 7), 'fallida', 'x')
        resumen = decisiones_evaluadas(self.cliente)
        self.assertEqual(resumen['con_conclusion'], 2)
        self.assertEqual(len(resumen['items']), 1)
        self.assertNotIn('mantuve', resumen['items'][0]['texto'])

    def test_peso_corporal_no_dice_cero_kg(self):
        origen = self._entreno(10, 0, 6, 6)
        self._entreno(5, 0, 7, 6)
        log = self._log(origen, 'validada', accion='subir_reps', valor=1)
        texto = frase_decision(log)
        self.assertIn('Después: 7 reps con RPE 6.', texto)
        self.assertNotIn('0 kg', texto)
