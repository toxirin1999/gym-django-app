"""Sesión de prueba aislada del entrenamiento activo (etapa 3, 21-nov-2026).

Crea un usuario/cliente SEPARADO (``prueba_aislada_gym``) y una URL de la
pantalla del entreno con ejercicios fijos, para comprobar sustituciones, molestias, reintentos y
recuperación sin crear lesiones, decisiones ni actividad en el historial de
David (cliente 2).

Uso:
    python manage.py sesion_prueba_aislada crear
    python manage.py sesion_prueba_aislada estado
    python manage.py sesion_prueba_aislada borrar --confirmar

Aislamiento: todo lo que la prueba escribe (series, molestias, decisiones,
puntos) cuelga del usuario de prueba y desaparece con ``borrar``. No crea
ejercicios base ni rutinas: usa los que ya existen (por nombre) y no deja ninguna
fila compartida. El plan viaja en la propia URL (parámetro ``ejercicios``, el
mismo transporte que usa la pantalla), sin decisión del motor.

Límites (ver la nota de entrega): las señales de gamificación y rankings se
disparan también para el usuario de prueba; el cliente de prueba aparece en
tablas globales (p. ej. ligas) mientras exista.
"""
import secrets

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

USERNAME = 'prueba_aislada_gym'
NOMBRE_CLIENTE = 'PRUEBA AISLADA'
NOMBRE_RUTINA = 'PRUEBA AISLADA - Dia de comprobaciones'  # solo el título que se muestra
EJERCICIOS_POR_DEFECTO = [
    'Sentadilla', 'Prensa de Piernas', 'Press de Banca', 'Remo con Mancuerna',
]


class Command(BaseCommand):
    help = 'Crea, consulta o borra la sesión de prueba aislada del entrenamiento activo.'

    def add_arguments(self, parser):
        parser.add_argument('accion', choices=['crear', 'estado', 'borrar'])
        parser.add_argument('--ejercicios', default=','.join(EJERCICIOS_POR_DEFECTO),
                            help='Nombres de EjercicioBase existentes, separados por comas.')
        parser.add_argument('--nueva-clave', action='store_true',
                            help='Genera otra contraseña para el usuario de prueba existente.')
        parser.add_argument('--confirmar', action='store_true',
                            help='Necesario para borrar.')

    # -- utilidades --------------------------------------------------------
    def _usuario(self):
        return User.objects.filter(username=USERNAME).first()

    def _cliente(self, user):
        from clientes.models import Cliente
        return Cliente.objects.filter(user=user).first()

    def _es_de_prueba(self, cliente):
        return bool(cliente) and (cliente.nombre or '') == NOMBRE_CLIENTE

    def handle(self, *args, **opts):
        getattr(self, f"_{opts['accion']}")(opts)

    def _url(self, cliente, bases):
        import json
        from urllib.parse import urlencode
        ejercicios = [{
            'nombre': b.nombre, 'series': 3, 'repeticiones': 10, 'rpe_objetivo': 8,
            'peso_kg': 20, 'tipo_progresion': 'peso_reps',
            'grupo_muscular': b.grupo_muscular or 'otros',
        } for b in bases]
        qs = urlencode({
            'fecha': timezone.localdate().isoformat(), 'rutina_nombre': NOMBRE_RUTINA,
            'ejercicios': json.dumps(ejercicios, ensure_ascii=False, separators=(',', ':')),
        })
        return f'/entrenos/cliente/{cliente.pk}/entrenamiento-activo/?{qs}'

    # -- crear -------------------------------------------------------------
    def _crear(self, opts):
        from rutinas.models import EjercicioBase

        nombres = [n.strip() for n in opts['ejercicios'].split(',') if n.strip()]
        bases, faltan = [], []
        for n in nombres:
            base = EjercicioBase.objects.filter(nombre__iexact=n).first()
            (bases if base else faltan).append(base or n)
        if faltan:
            raise CommandError(
                'No existen estos ejercicios base (no se crean para no ensuciar el catálogo): '
                + ', '.join(faltan))
        if not bases:
            raise CommandError('Indica al menos un ejercicio.')

        clave = None
        with transaction.atomic():
            user = self._usuario()
            if user is None:
                clave = secrets.token_urlsafe(9)
                user = User.objects.create_user(USERNAME, password=clave)
            elif opts['nueva_clave']:
                clave = secrets.token_urlsafe(9)
                user.set_password(clave)
                user.save(update_fields=['password'])
            cliente = self._cliente(user)
            if cliente is None:
                raise CommandError('El usuario de prueba existe pero no tiene cliente; bórralo y vuelve a crear.')
            if cliente.nombre != NOMBRE_CLIENTE:
                cliente.nombre = NOMBRE_CLIENTE
                cliente.save(update_fields=['nombre'])


        out = self.stdout.write
        out(self.style.SUCCESS('Sesión de prueba aislada lista.'))
        out(f'  Usuario:  {USERNAME}')
        out(f'  Cliente:  {cliente.pk} (no es el tuyo)')
        out('  Clave:    ' + (clave if clave else '(sin cambios; usa --nueva-clave para generar otra)'))
        out('  Ejercicios: ' + ', '.join(b.nombre for b in bases))
        out('  Entra con ese usuario en una ventana privada (tu sesión no se toca) y abre:')
        out('    ' + self._url(cliente, bases))
        out('  Al terminar: python manage.py sesion_prueba_aislada borrar --confirmar')

    # -- estado ------------------------------------------------------------
    def _estado(self, opts):
        from entrenos.models import EntrenoRealizado
        user = self._usuario()
        cliente = self._cliente(user) if user else None
        if not cliente:
            self.stdout.write('No existe la sesión de prueba aislada.')
            return
        self.stdout.write(f'Existe: usuario {USERNAME}, cliente {cliente.pk}, '
                          f'entrenos guardados: {EntrenoRealizado.objects.filter(cliente=cliente).count()}.')

    # -- borrar ------------------------------------------------------------
    def _borrar(self, opts):
        from django.db.models import ProtectedError
        if not opts['confirmar']:
            raise CommandError('Borrar elimina el usuario de prueba y todo lo que creó. Repite con --confirmar.')
        user = self._usuario()
        if user is None:
            self.stdout.write('Nada que borrar.')
            return
        cliente = self._cliente(user)
        if cliente is not None and not self._es_de_prueba(cliente):
            raise CommandError('El usuario existe pero su cliente no está marcado como de prueba; no se borra.')
        try:
            with transaction.atomic():
                user.delete()
        except ProtectedError as exc:
            raise CommandError(f'Hay registros protegidos que impiden borrar: {exc}')
        self.stdout.write(self.style.SUCCESS('Sesión de prueba aislada borrada.'))
