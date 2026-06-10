"""
Phase 62F — vista de cierre post-entreno.

GET /entrenos/cliente/<id>/entreno/<id>/cierre/ renderiza el resumen de la
sesión recién guardada con secciones condicionales (lectura del plan,
cambios relevantes, próxima vez, récords, JOI) y dos CTAs de salida.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, RecordPersonal
from joi.models import MensajeJOI
from rutinas.models import Rutina


def _permiso(accion, motivo='ok'):
    return {
        'accion': accion,
        'motivo': motivo,
        'mensaje': '',
        'aplica_a_principales': accion == 'mantener_carga',
        'aplica_a_accesorios': accion in ('mantener_carga', 'reducir_accesorios'),
        'hay_datos_semana': True,
    }


class PostEntrenoResumenViewBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_cierre62f_view', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestCierre62FView', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Push Day')

        anterior = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 5, 25),
        )
        EjercicioRealizado.objects.create(
            entreno=anterior, nombre_ejercicio='Press banca', grupo_muscular='pecho',
            peso_kg=60.0, series=4, repeticiones=8, completado=True,
        )

        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 6, 1),
        )
        EjercicioRealizado.objects.create(
            entreno=self.entreno, nombre_ejercicio='Press banca', grupo_muscular='pecho',
            peso_kg=62.5, series=4, repeticiones=8, completado=True,
        )

    def _url(self):
        return reverse('entrenos:post_entreno_resumen', kwargs={
            'cliente_id': self.cliente.id, 'entreno_id': self.entreno.id,
        })


class TestPostEntrenoResumenView(PostEntrenoResumenViewBase):
    def test_get_devuelve_200(self):
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)

    def test_renderiza_titulo_y_resumen(self):
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(self._url())
        self.assertContains(resp, 'Push Day')
        self.assertContains(resp, 'Press banca')

    def test_ctas_presentes(self):
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(self._url())
        self.assertContains(resp, 'Volver al panel')
        self.assertContains(resp, 'Ver análisis completo')
        self.assertContains(resp, reverse('entrenos:dashboard_evolucion', kwargs={'cliente_id': self.cliente.id}))
        self.assertContains(resp, reverse('home'))

    def test_sin_freno_no_muestra_lectura_plan_ni_proxima_vez(self):
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(self._url())
        self.assertNotContains(resp, 'Lectura del plan')
        self.assertNotContains(resp, 'Próxima vez')

    def test_con_freno_muestra_lectura_plan_y_proxima_vez(self):
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('mantener_carga', 'retorno_pausa')):
            resp = self.client.get(self._url())
        self.assertContains(resp, 'Lectura del plan')
        self.assertContains(resp, 'Próxima vez')
        self.assertContains(resp, 'pausa')

    def test_sin_joi_mensaje_no_muestra_card_joi(self):
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(self._url())
        self.assertNotContains(resp, '"joi-card"')

    def test_con_joi_mensaje_muestra_card_joi(self):
        from datetime import datetime, time
        from django.utils import timezone
        msg = MensajeJOI.objects.create(
            user=self.user, trigger='entreno_completado', mensaje='Hoy aguantaste algo más.',
        )
        MensajeJOI.objects.filter(id=msg.id).update(
            creado_en=timezone.make_aware(datetime.combine(self.entreno.fecha, time(8, 0)))
        )

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(self._url())
        self.assertContains(resp, 'Hoy aguantaste algo más.')

    def test_con_records_muestra_seccion_records(self):
        RecordPersonal.objects.create(
            cliente=self.cliente, entreno=self.entreno, ejercicio_nombre='Press banca',
            tipo_record='peso_maximo', valor=62.5, superado=False,
        )
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(self._url())
        self.assertContains(resp, 'Récords')
        self.assertContains(resp, 'Nuevo récord')

    def test_entreno_de_otro_cliente_404(self):
        otro_user = User.objects.create_user(username='otro_cliente_62f', password='x')
        otro_cliente, _ = Cliente.objects.get_or_create(
            user=otro_user, defaults={'nombre': 'Otro62F', 'dias_disponibles': 4},
        )
        url = reverse('entrenos:post_entreno_resumen', kwargs={
            'cliente_id': otro_cliente.id, 'entreno_id': self.entreno.id,
        })
        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
