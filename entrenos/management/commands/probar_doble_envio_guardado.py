"""Nota 31: prueba de doble envío del guardado contra la base de datos real (MySQL).

    python manage.py probar_doble_envio_guardado

Crea un usuario y un cliente de prueba propios (``prueba_nota31_<marca>``) y
lanza dos envíos del mismo cierre a la vez, en dos hilos con conexiones
distintas. Para asegurar que se solapan, quien consigue el bloqueo del cliente
lo mantiene unos segundos antes de seguir.

Escenario 1 · dos envíos a la vez: una sola sesión, sus series una vez y el
mismo ID de cierre en las dos respuestas.
Escenario 2 · el primero falla a mitad: su transacción se deshace y el segundo
guarda la sesión.

Al terminar borra todo lo que creó (usuario, cliente y lo que cuelga de ellos,
el ejercicio y las rutinas de prueba), salvo con ``--conservar``. No toca datos
de otros clientes.
"""

import threading
import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import connections
from django.test import RequestFactory
from django.utils import timezone

ESPERA_CON_BLOQUEO_S = 2.0


class Command(BaseCommand):
    help = 'Nota 31: dos envíos simultáneos del guardado contra MySQL, con un cliente de prueba.'

    def add_arguments(self, parser):
        parser.add_argument('--conservar', action='store_true', help='No borrar los datos de prueba al terminar.')

    def handle(self, *args, **opts):
        from clientes.models import Cliente
        from entrenos import views
        from entrenos.models import EntrenoRealizado, SerieRealizada
        from rutinas.models import EjercicioBase, Rutina

        marca = timezone.now().strftime('%Y%m%d%H%M%S')
        nombre_usuario = f'prueba_nota31_{marca}'
        ejercicio = f'Prueba Nota31 {marca}'
        rutinas = [f'Prueba Nota31 A {marca}', f'Prueba Nota31 B {marca}']
        self.stdout.write(f'Motor: {connections["default"].vendor} · cliente de prueba: {nombre_usuario}')

        user = User.objects.create_user(nombre_usuario, password=None)
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': nombre_usuario})
        base = EjercicioBase.objects.create(nombre=ejercicio, grupo_muscular='pecho')
        bloquear_original = views._bloquear_cliente_para_guardar
        ok = True
        try:
            def bloquear_y_esperar(c):
                bloquear_original(c)
                time.sleep(ESPERA_CON_BLOQUEO_S)     # quien tenga el bloqueo lo retiene: el otro tiene que esperar

            views._bloquear_cliente_para_guardar = bloquear_y_esperar

            # Escenario 1
            r = self._dos_envios(views, user, cliente, rutinas[0], ejercicio)
            n_e = EntrenoRealizado.objects.filter(cliente=cliente, rutina__nombre=rutinas[0]).count()
            n_s = SerieRealizada.objects.filter(entreno__cliente=cliente, entreno__rutina__nombre=rutinas[0]).count()
            ids = {x.get('entreno_id') for x in r}
            bien = n_e == 1 and n_s == 2 and len(ids) == 1 and None not in ids and all(x.get('success') for x in r)
            ok &= bien
            self.stdout.write(f'Escenario 1 (a la vez): sesiones={n_e} series={n_s} respuestas={r} '
                              f'→ {"OK" if bien else "FALLO"}')

            # Escenario 2: el primero en conseguir el bloqueo falla a mitad
            original_create = SerieRealizada.objects.create
            fallado = {'hecho': False}
            cerrojo = threading.Lock()

            def create_que_falla_una_vez(*a, **k):
                with cerrojo:
                    if not fallado['hecho']:
                        fallado['hecho'] = True
                        raise RuntimeError('fallo provocado a mitad del guardado (prueba nota 31)')
                return original_create(*a, **k)

            SerieRealizada.objects.create = create_que_falla_una_vez
            try:
                r = self._dos_envios(views, user, cliente, rutinas[1], ejercicio)
            finally:
                SerieRealizada.objects.create = original_create
            n_e = EntrenoRealizado.objects.filter(cliente=cliente, rutina__nombre=rutinas[1]).count()
            n_s = SerieRealizada.objects.filter(entreno__cliente=cliente, entreno__rutina__nombre=rutinas[1]).count()
            exitos = [x for x in r if x.get('success')]
            bien = (n_e == 1 and n_s == 2 and len(exitos) == 1 and not exitos[0].get('ya_guardado')
                    and any(x.get('success') is False for x in r))
            ok &= bien
            self.stdout.write(f'Escenario 2 (el primero falla): sesiones={n_e} series={n_s} respuestas={r} '
                              f'→ {"OK" if bien else "FALLO"}')
        finally:
            views._bloquear_cliente_para_guardar = bloquear_original
            if opts['conservar']:
                self.stdout.write(f'Datos conservados: usuario {nombre_usuario}.')
            else:
                user.delete()                                   # cliente y lo que cuelga de él
                Cliente.objects.filter(pk=cliente.pk).delete()
                base.delete()
                Rutina.objects.filter(nombre__in=rutinas).delete()
                self.stdout.write('Datos de prueba borrados.')
        self.stdout.write(self.style.SUCCESS('NOTA 31: OK') if ok else self.style.ERROR('NOTA 31: FALLO'))

    def _dos_envios(self, views, user, cliente, rutina, ejercicio):
        import json

        datos = {
            'fecha': timezone.localdate().isoformat(), 'rutina_nombre': rutina,
            'ej1_nombre': ejercicio, 'ej1_tipo_progresion': 'peso_reps',
            'ej1_peso_1': '60', 'ej1_reps_1': '8', 'ej1_rpe_1': '8', 'ej1_completado_1': '1',
            'ej1_peso_2': '62.5', 'ej1_reps_2': '8', 'ej1_rpe_2': '8.5', 'ej1_completado_2': '1',
            'duracion_minutos_real': '50',
        }
        salida = [None, None]
        salida_lock = threading.Lock()
        barrera = threading.Barrier(2)

        def enviar(i):
            try:
                req = RequestFactory().post(f'/entrenos/cliente/{cliente.pk}/guardar/', datos,
                                            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                req.user = user
                from django.contrib.messages.storage.cookie import CookieStorage
                req._messages = CookieStorage(req)      # el guardado avisa con mensajes
                barrera.wait()
                resp = views.guardar_entrenamiento_activo(req, cliente.pk)
                try:
                    cuerpo = json.loads(resp.content)
                except ValueError:
                    cuerpo = {'status': resp.status_code}
                with salida_lock:
                    salida[i] = {k: cuerpo.get(k) for k in ('success', 'entreno_id', 'ya_guardado', 'error')}
            except Exception as exc:  # noqa: BLE001
                with salida_lock:
                    salida[i] = {'success': False, 'error': repr(exc)}
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=enviar, args=(i,)) for i in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        return salida
