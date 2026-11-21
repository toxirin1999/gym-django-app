"""Etapa 3: la sesión de prueba aislada no toca el historial de otro cliente."""
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada, GymDecisionLog
from rutinas.models import EjercicioBase, Rutina
from hyrox.models import UserInjury


def _cmd(*args):
    out = StringIO()
    call_command('sesion_prueba_aislada', *args, stdout=out)
    return out.getvalue()


class SesionPruebaAislada(TestCase):
    def setUp(self):
        self.david = User.objects.create_user('david-real', password='x')
        self.cdavid = Cliente.objects.get(user=self.david)
        for n in ('Sentadilla', 'Prensa de Piernas', 'Press de Banca', 'Remo con Mancuerna'):
            EjercicioBase.objects.create(nombre=n, grupo_muscular='Piernas', tipo_progresion='peso_reps')
        self.n_bases = EjercicioBase.objects.count()

    def _foto_david(self):
        return (EntrenoRealizado.objects.filter(cliente=self.cdavid).count(),
                GymDecisionLog.objects.filter(cliente=self.cdavid).count(),
                UserInjury.objects.filter(cliente=self.cdavid).count(),
                SesionProgramada.objects.filter(cliente=self.cdavid).count())

    def test_crear_no_inventa_ejercicios_ni_toca_a_david(self):
        antes = self._foto_david()
        salida = _cmd('crear')
        self.assertIn('Sesión de prueba aislada lista', salida)
        self.assertEqual(EjercicioBase.objects.count(), self.n_bases)
        self.assertEqual(self._foto_david(), antes)
        cliente = Cliente.objects.get(user__username='prueba_aislada_gym')
        self.assertNotEqual(cliente.pk, self.cdavid.pk)

    def test_ejercicio_inexistente_se_rechaza_sin_crear_nada(self):
        with self.assertRaises(CommandError):
            _cmd('crear', '--ejercicios', 'Sentadilla,No existe')
        self.assertFalse(User.objects.filter(username='prueba_aislada_gym').exists())

    def test_recorrido_real_molestia_y_guardado_quedan_en_el_usuario_de_prueba_y_se_borran(self):
        antes = self._foto_david()
        salida = _cmd('crear')
        user = User.objects.get(username='prueba_aislada_gym')
        cliente = Cliente.objects.get(user=user)
        self.client.force_login(user)
        url = [l.strip() for l in salida.splitlines() if '/entrenamiento-activo/?' in l][0]
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e['nombre'] for e in resp.context['ejercicios_planificados']],
                         ['Sentadilla', 'Prensa de Piernas', 'Press de Banca', 'Remo con Mancuerna'])
        # Un entreno guardado con la sesión de prueba.
        r = self.client.post(
            reverse('entrenos:guardar_entrenamiento_activo', args=[cliente.pk]),
            {'fecha': '2026-11-21', 'rutina_nombre': 'PRUEBA', 'ej1_nombre': 'Sentadilla',
             'ej1_tipo_progresion': 'peso_reps', 'ej1_peso_1': '20', 'ej1_reps_1': '10',
             'ej1_rpe_1': '8', 'ej1_completado_1': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(EntrenoRealizado.objects.filter(cliente=cliente).count(), 1)
        self.assertEqual(self._foto_david(), antes)
        # Borrar exige confirmación y lo elimina todo.
        with self.assertRaises(CommandError):
            _cmd('borrar')
        _cmd('borrar', '--confirmar')
        self.assertFalse(User.objects.filter(username='prueba_aislada_gym').exists())
        self.assertFalse(EntrenoRealizado.objects.filter(cliente=cliente.pk).exists())
        self.assertFalse(Rutina.objects.filter(nombre__startswith='PRUEBA AISLADA').exists())
        self.assertEqual(EjercicioBase.objects.count(), self.n_bases)
        self.assertEqual(self._foto_david(), antes)
        self.assertTrue(User.objects.filter(username='david-real').exists())

    def test_no_borra_un_usuario_que_no_es_de_prueba(self):
        _cmd('crear')
        c = Cliente.objects.get(user__username='prueba_aislada_gym')
        c.nombre = 'Otro'
        c.save(update_fields=['nombre'])
        with self.assertRaises(CommandError):
            _cmd('borrar', '--confirmar')
        self.assertTrue(User.objects.filter(username='prueba_aislada_gym').exists())
