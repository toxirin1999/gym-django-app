"""Nota 31 (18-nov-2026): doble envío del guardado del entreno.

Dos envíos del mismo cierre (doble toque, reintento tras una respuesta perdida)
podían comprobar a la vez que la sesión no existía y guardar los dos. Ahora el
guardado bloquea la fila del cliente dentro de su transacción antes de
comprobar, y comprueba con una lectura bloqueante: el segundo envío espera,
relee y devuelve el mismo cierre sin volver a escribir series ni efectos.

Qué cuenta como reintento (regla de siempre): mismo cliente, misma rutina,
misma fecha del plan, origen manual y ejecutada hoy. Otra rutina el mismo día
es otra sesión. Limitación conocida: repetir la misma rutina el mismo día se
trata como reintento.

En SQLite ``select_for_update`` no bloquea, así que aquí se prueba el orden
(bloqueo antes de comprobar, y la comprobación después del bloqueo ve lo que
otro envío confirmó mientras se esperaba). La prueba concurrente de verdad es
contra MySQL: ``python manage.py probar_doble_envio_guardado``.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    ActividadRealizada, EjercicioRealizado, EntrenoRealizado, GymDecisionLog, SerieRealizada,
)
from rutinas.models import EjercicioBase, Rutina

NOMBRE = 'Press Banca Nota31'


def datos(rutina='Dia Nota31', fecha=None):
    return {
        'fecha': (fecha or date.today()).isoformat(),
        'rutina_nombre': rutina,
        'ej1_nombre': NOMBRE, 'ej1_tipo_progresion': 'peso_reps',
        'ej1_peso_1': '60', 'ej1_reps_1': '8', 'ej1_rpe_1': '8', 'ej1_completado_1': '1',
        'ej1_peso_2': '62.5', 'ej1_reps_2': '8', 'ej1_rpe_2': '8.5', 'ej1_completado_2': '1',
        'duracion_minutos_real': '50',
    }


class DobleEnvioDelGuardado(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('nota31', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        EjercicioBase.objects.create(nombre=NOMBRE, grupo_muscular='pecho')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk])

    def enviar(self, **kw):
        return self.client.post(self.url, datos(**kw), HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def recuento(self):
        return {
            'entrenos': EntrenoRealizado.objects.filter(cliente=self.cliente).count(),
            'ejercicios': EjercicioRealizado.objects.filter(entreno__cliente=self.cliente).count(),
            'series': SerieRealizada.objects.filter(entreno__cliente=self.cliente).count(),
            'decisiones': GymDecisionLog.objects.filter(cliente=self.cliente).count(),
            'actividades': ActividadRealizada.objects.filter(cliente=self.cliente).count(),
            'rutinas': Rutina.objects.filter(nombre='Dia Nota31').count(),
        }

    def test_el_reintento_devuelve_el_mismo_cierre_sin_repetir_efectos(self):
        primero = self.enviar().json()
        tras_primero = self.recuento()
        segundo = self.enviar().json()
        self.assertTrue(primero['success'])
        self.assertEqual(segundo['entreno_id'], primero['entreno_id'])
        self.assertTrue(segundo.get('ya_guardado'))
        self.assertEqual(self.recuento(), tras_primero)
        self.assertEqual(tras_primero['entrenos'], 1)
        self.assertEqual(tras_primero['series'], 2)

    def test_si_otro_envio_confirma_mientras_espera_devuelve_ese_cierre(self):
        """Orden simulado: el primer envío confirma justo mientras el segundo espera el bloqueo.

        Si la comprobación se hiciera antes del bloqueo, no vería esa sesión y guardaría otra.
        """
        import entrenos.views as v
        bloquear = v._bloquear_cliente_para_guardar
        rutina = Rutina.objects.create(nombre='Dia Nota31')
        del_otro = {}

        def el_otro_confirma_mientras_espero(cliente):
            del_otro['entreno'] = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=rutina, fecha=date.today(), fecha_ejecucion=date.today(),
                fuente_datos='manual',
            )
            return bloquear(cliente)

        antes = self.recuento()
        with patch.object(v, '_bloquear_cliente_para_guardar', side_effect=el_otro_confirma_mientras_espero):
            r = self.enviar().json()
        self.assertEqual(r['entreno_id'], del_otro['entreno'].pk)
        self.assertTrue(r.get('ya_guardado'))
        despues = self.recuento()
        self.assertEqual(despues['entrenos'], antes['entrenos'] + 1)   # solo la del otro envío
        self.assertEqual(despues['series'], antes['series'])
        self.assertEqual(despues['decisiones'], antes['decisiones'])

    def test_si_el_primero_falla_el_segundo_guarda(self):
        real = SerieRealizada.objects.create
        llamadas = {'n': 0}

        def falla_una_vez(*a, **k):
            llamadas['n'] += 1
            if llamadas['n'] == 1:
                raise RuntimeError('fallo a mitad del guardado')
            return real(*a, **k)

        with patch.object(SerieRealizada.objects, 'create', side_effect=falla_una_vez):
            primero = self.enviar()
        self.assertEqual(primero.status_code, 400)
        self.assertEqual(self.recuento()['entrenos'], 0)          # se deshizo entero
        segundo = self.enviar().json()
        self.assertTrue(segundo['success'])
        self.assertFalse(segundo.get('ya_guardado', False))
        self.assertEqual((self.recuento()['entrenos'], self.recuento()['series']), (1, 2))

    def test_otra_rutina_el_mismo_dia_es_otra_sesion(self):
        a = self.enviar().json()
        b = self.enviar(rutina='Dia Nota31 tarde').json()
        self.assertNotEqual(a['entreno_id'], b['entreno_id'])
        self.assertFalse(b.get('ya_guardado', False))
        self.assertEqual(self.recuento()['entrenos'], 2)
