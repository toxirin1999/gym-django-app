"""
Phase Hábitos 2.0E — presencia_cierre repointeado a Gesto/RegistroGesto.

presencia_cierre quedó fuera del repoint de 2.0D (seguía usando
ProsocheHabito/ProsocheHabitoDia). Estos tests cubren el comportamiento
correcto sobre Gesto/RegistroGesto, mismo patrón ya usado en
habito_toggle_dia / HabitosService.toggle_dia.
"""
import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Gesto, RegistroGesto


class PresenciaCierreGestosGetTestCase(TestCase):
    """1. GET muestra todos los Gesto activos del usuario."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto_cultivo = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )
        self.gesto_suelto = Gesto.objects.create(
            usuario=self.user, nombre='Fumar', tipo='suelto', estado='activo'
        )

    def test_get_muestra_todos_los_gestos_activos(self):
        resp = self.client.get('/diario/presencia/cierre/', SERVER_NAME='127.0.0.1')
        habitos_con_estado = resp.context['habitos_con_estado']
        nombres = {item['habito'].nombre for item in habitos_con_estado}
        self.assertEqual(nombres, {'Meditar', 'Fumar'})

    def test_get_no_depende_de_prosoche_habito_del_mes(self):
        # Ningún ProsocheHabito existe para este usuario/mes y aun así
        # los Gesto activos aparecen.
        resp = self.client.get('/diario/presencia/cierre/', SERVER_NAME='127.0.0.1')
        self.assertEqual(len(resp.context['habitos_con_estado']), 2)


class PresenciaCierrePostMarcarTestCase(TestCase):
    """2. POST marcando un gesto crea RegistroGesto(estado='cumplido') hoy."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )
        self.hoy = date.today()

    def test_post_marca_gesto_crea_registro_cumplido(self):
        self.client.post(
            '/diario/presencia/cierre/',
            {
                'reflexion_libre': '',
                'habitos_completados': json.dumps([self.gesto.id]),
            },
            SERVER_NAME='127.0.0.1',
        )
        self.assertTrue(
            RegistroGesto.objects.filter(
                gesto=self.gesto, fecha=self.hoy, estado='cumplido'
            ).exists()
        )


class PresenciaCierrePostDesmarcarTestCase(TestCase):
    """3. POST desmarcando un gesto previamente completado hoy borra su RegistroGesto."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )
        self.hoy = date.today()
        RegistroGesto.objects.create(gesto=self.gesto, fecha=self.hoy, estado='cumplido')

    def test_post_desmarca_gesto_borra_registro(self):
        self.client.post(
            '/diario/presencia/cierre/',
            {
                'reflexion_libre': '',
                'habitos_completados': json.dumps([]),
            },
            SERVER_NAME='127.0.0.1',
        )
        self.assertFalse(
            RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy).exists()
        )


class PresenciaCierrePostSinCambioTestCase(TestCase):
    """4. POST que no cambia el estado de un gesto no duplica ni borra su RegistroGesto."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto_cumplido = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )
        self.gesto_pendiente = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo', estado='activo'
        )
        self.hoy = date.today()
        RegistroGesto.objects.create(
            gesto=self.gesto_cumplido, fecha=self.hoy, estado='cumplido'
        )

    def test_post_sin_cambios_mantiene_estado(self):
        self.client.post(
            '/diario/presencia/cierre/',
            {
                'reflexion_libre': '',
                # gesto_cumplido sigue marcado, gesto_pendiente sigue sin marcar
                'habitos_completados': json.dumps([self.gesto_cumplido.id]),
            },
            SERVER_NAME='127.0.0.1',
        )
        self.assertEqual(
            RegistroGesto.objects.filter(
                gesto=self.gesto_cumplido, fecha=self.hoy, estado='cumplido'
            ).count(),
            1,
        )
        self.assertFalse(
            RegistroGesto.objects.filter(gesto=self.gesto_pendiente, fecha=self.hoy).exists()
        )


class PresenciaCierreGestosNoActivosTestCase(TestCase):
    """5. Un Gesto pausado o cerrado NO aparece en habitos_con_estado."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto_activo = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )
        self.gesto_pausado = Gesto.objects.create(
            usuario=self.user, nombre='Correr', tipo='cultivo', estado='pausado'
        )
        self.gesto_cerrado = Gesto.objects.create(
            usuario=self.user, nombre='Viejo hábito', tipo='cultivo', estado='cerrado'
        )

    def test_solo_gestos_activos_aparecen(self):
        resp = self.client.get('/diario/presencia/cierre/', SERVER_NAME='127.0.0.1')
        nombres = {item['habito'].nombre for item in resp.context['habitos_con_estado']}
        self.assertEqual(nombres, {'Meditar'})
