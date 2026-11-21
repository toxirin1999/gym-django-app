"""Concurrencia real del guardado con identificador (solo MySQL/MariaDB).

En SQLite ``select_for_update`` no bloquea, asi que estas pruebas se omiten alli.
Ejecutar: ``python manage.py test entrenos.tests_guardado_sesion_concurrencia_20261121
--settings=<settings con MariaDB>``.
"""

import threading
from datetime import date

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import CorreccionSesionGym, EntrenoRealizado, SerieRealizada
from rutinas.models import EjercicioBase

NOMBRE = 'Press Banca Concurrencia'


def datos(token, reps=('8', '8'), **extra):
    d = {
        'fecha': date.today().isoformat(), 'rutina_nombre': 'Dia Concurrencia',
        'sesion_token': token, 'ej1_nombre': NOMBRE, 'ej1_tipo_progresion': 'peso_reps',
        'duracion_minutos_real': '50',
    }
    for i, r in enumerate(reps, start=1):
        d.update({f'ej1_peso_{i}': '60', f'ej1_reps_{i}': r, f'ej1_rpe_{i}': '8', f'ej1_completado_{i}': '1'})
    d.update(extra)
    return d


class ConcurrenciaReal(TransactionTestCase):
    def setUp(self):
        if connection.vendor not in ('mysql', 'mariadb'):
            self.skipTest('requiere MySQL/MariaDB: SQLite no bloquea filas')
        self.user = User.objects.create_user('conc21', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        EjercicioBase.objects.create(nombre=NOMBRE, grupo_muscular='pecho')
        self.url = reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk])

    def _lanzar(self, payloads):
        resultados = [None] * len(payloads)
        barrera = threading.Barrier(len(payloads))

        def trabajo(i):
            try:
                c = Client()
                c.force_login(self.user)
                barrera.wait(timeout=10)
                r = c.post(self.url, payloads[i], HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                resultados[i] = (r.status_code, r.json())
            except Exception as exc:  # pragma: no cover - se ve en el assert
                resultados[i] = ('error', repr(exc))
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=trabajo, args=(i,)) for i in range(len(payloads))]
        [h.start() for h in hilos]
        [h.join(timeout=60) for h in hilos]
        return resultados

    def test_dos_envios_identicos_a_la_vez_dejan_una_sola_sesion(self):
        tok = 'tokConcurrente00001'
        res = self._lanzar([datos(tok), datos(tok)])
        self.assertEqual([r[0] for r in res], [200, 200], res)
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=self.cliente).count(), 1)
        self.assertEqual(sum(1 for r in res if r[1].get('ya_guardado')), 1)
        self.assertEqual(SerieRealizada.objects.filter(entreno__cliente=self.cliente).count(), 2)

    def test_dos_sesiones_distintas_a_la_vez_son_dos(self):
        res = self._lanzar([datos('tokConcurrente00002'), datos('tokConcurrente00003')])
        self.assertEqual([r[0] for r in res], [200, 200], res)
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=self.cliente).count(), 2)

    def test_dos_correcciones_a_la_vez_desde_la_misma_base_una_gana_y_la_otra_recibe_conflicto(self):
        tok = 'tokConcurrente00004'
        h0 = self.client_post(datos(tok))['huella']
        a = datos(tok, reps=('10', '10'), bases_huella=h0)
        b = datos(tok, reps=('7', '7'), bases_huella=h0)
        res = self._lanzar([a, b])
        codigos = sorted(r[0] for r in res)
        self.assertEqual(codigos, [200, 409], res)
        e = EntrenoRealizado.objects.get(cliente=self.cliente)
        ganadora = next(r for r in res if r[0] == 200)[1]
        self.assertEqual(e.huella_contenido, ganadora['huella'])
        self.assertEqual(e.revision, 2)
        self.assertEqual(CorreccionSesionGym.objects.count(), 1)
        self.assertEqual(SerieRealizada.objects.filter(entreno=e).count(), 2)

    def client_post(self, payload):
        c = Client()
        c.force_login(self.user)
        return c.post(self.url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()
