"""20-nov-2026: concurrencia real sobre la bitacora del dia.

Los bloqueos de fila (select_for_update) no hacen nada en SQLite, asi que esta prueba solo
tiene sentido con un motor transaccional como el de produccion (MySQL/InnoDB): se omite en
SQLite. Incluye un control: la logica anterior (bloqueo solo sobre filas del dia) SI crea
duplicados, para demostrar que la prueba es capaz de detectarlos.
"""
import threading
from datetime import date

from django.contrib.auth.models import User
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature

from clientes.bitacora_dia import fila_del_dia_para_escribir
from clientes.models import BitacoraDiaria, Cliente

HOY = date(2026, 11, 20)
HILOS = 8


def _en_paralelo(funcion):
    barrera = threading.Barrier(HILOS)
    errores = []

    def run(i):
        try:
            barrera.wait(timeout=10)
            funcion(i)
        except Exception as exc:  # pragma: no cover
            errores.append(repr(exc))
        finally:
            connections.close_all()

    hilos = [threading.Thread(target=run, args=(i,)) for i in range(HILOS)]
    [h.start() for h in hilos]
    [h.join(30) for h in hilos]
    return errores


@skipUnlessDBFeature('has_select_for_update')
class ConcurrenciaBitacoraTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite no bloquea filas: la prueba de concurrencia necesita MySQL/MariaDB')
        self.user = User.objects.create_user('bit-conc')
        self.cliente = Cliente.objects.get(user=self.user)

    def _filas(self):
        return BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=HOY).count()

    def test_control_logica_anterior_crea_duplicados(self):
        def antigua(i):
            with transaction.atomic():
                fila = (BitacoraDiaria.objects.select_for_update()
                        .filter(cliente=self.cliente, fecha=HOY).order_by('pk').first())
                if fila is None:
                    import time
                    time.sleep(0.05)  # ventana de carrera de dos importaciones casi simultaneas
                    fila = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=100 + i)
                    BitacoraDiaria.objects.filter(pk=fila.pk).update(fecha=HOY)
        self.assertEqual(_en_paralelo(antigua), [])
        self.assertGreater(self._filas(), 1, 'el control deberia reproducir el duplicado')

    def test_puerta_unica_no_crea_duplicados(self):
        def nueva(i):
            with transaction.atomic():
                fila, creada = fila_del_dia_para_escribir(self.cliente, HOY, {'hrv_ms': 100 + i})
                if not creada:
                    fila.hrv_ms = 100 + i
                    fila.save(update_fields=['hrv_ms'])
        self.assertEqual(_en_paralelo(nueva), [])
        self.assertEqual(self._filas(), 1)

    def test_guardar_checkin_iphone_simultaneo(self):
        from clientes.salud_iphone_service import guardar_checkin_iphone
        payload = {'hrv': 48, 'pulso_reposo': 52, 'sueno': 432, 'fecha': HOY.isoformat()}
        errores = _en_paralelo(lambda i: guardar_checkin_iphone(self.cliente, dict(payload), hoy=HOY))
        self.assertEqual(errores, [])
        self.assertEqual(self._filas(), 1)
