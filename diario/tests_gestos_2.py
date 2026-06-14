"""
Phase Hábitos 2.0D — Tests de repoint de consumidores a Gesto/RegistroGesto.

Cubre: dashboard, proyección mensual, toggle_dia, mejor_racha, pausar/cerrar,
aceptar_habito_invitacion, TriggerHabito.gesto (creación + backfill) e
insignias sobre RegistroGesto.
"""
import importlib
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.apps import apps

from diario.models import (
    Gesto, RegistroGesto, ProsocheMes, ProsocheHabito, TriggerHabito, Insignia,
)
from diario.services import HabitosService, InsigniasService

_migracion_0020 = importlib.import_module('diario.migrations.0020_backfill_triggerhabito_gesto')
backfill_gesto = _migracion_0020.backfill_gesto


class HabitosDashboardSinProsocheMesTestCase(TestCase):
    """1. habitos_dashboard funciona sin ProsocheMes del mes/año actual."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.usuario)

    def test_dashboard_devuelve_200_y_lista_gestos_activos(self):
        Gesto.objects.create(usuario=self.usuario, nombre='Leer', tipo='cultivo')
        Gesto.objects.create(usuario=self.usuario, nombre='Fumar', tipo='suelto')
        Gesto.objects.create(usuario=self.usuario, nombre='Viejo gesto', tipo='cultivo', estado='cerrado')

        # No existe ningún ProsocheMes para el usuario.
        self.assertFalse(ProsocheMes.objects.filter(usuario=self.usuario).exists())

        response = self.client.get(reverse('diario:habitos_dashboard'))

        self.assertEqual(response.status_code, 200)
        nombres_positivos = [item['habito'].nombre for item in response.context['habitos_positivos']]
        nombres_negativos = [item['habito'].nombre for item in response.context['habitos_negativos']]

        self.assertIn('Leer', nombres_positivos)
        self.assertIn('Fumar', nombres_negativos)
        self.assertNotIn('Viejo gesto', nombres_positivos)


class ProyeccionMensualTestCase(TestCase):
    """2. proyeccion_mensual sin ProsocheMes correspondiente no falla."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(usuario=self.usuario, nombre='Meditar', tipo='cultivo')

    def test_proyeccion_devuelve_dict_completo_sin_error(self):
        # Año/mes sin ningún ProsocheMes asociado.
        proyeccion = HabitosService.proyeccion_mensual(self.gesto, 2024, 7)

        self.assertEqual(len(proyeccion), 31)  # julio tiene 31 días
        for dia in proyeccion:
            self.assertIn('numero', dia)
            self.assertIn('completado', dia)
            self.assertFalse(dia['completado'])

    def test_proyeccion_marca_dias_cumplidos(self):
        RegistroGesto.objects.create(gesto=self.gesto, fecha=date(2026, 6, 5), estado='cumplido')
        RegistroGesto.objects.create(gesto=self.gesto, fecha=date(2026, 6, 10), estado='fallado')

        proyeccion = HabitosService.proyeccion_mensual(self.gesto, 2026, 6)

        por_numero = {d['numero']: d['completado'] for d in proyeccion}
        self.assertTrue(por_numero[5])
        self.assertFalse(por_numero[10])
        self.assertFalse(por_numero[1])


class ToggleDiaTestCase(TestCase):
    """3 y 4. toggle_dia crea/borra RegistroGesto y actualiza mejor_racha."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(usuario=self.usuario, nombre='Entrenar', tipo='cultivo')

    def test_toggle_crea_y_borra_registro(self):
        fecha = date(2026, 6, 10)

        resultado_on = HabitosService.toggle_dia(self.gesto, fecha)
        self.assertTrue(resultado_on)
        self.assertTrue(
            RegistroGesto.objects.filter(gesto=self.gesto, fecha=fecha, estado='cumplido').exists()
        )

        resultado_off = HabitosService.toggle_dia(self.gesto, fecha)
        self.assertFalse(resultado_off)
        self.assertFalse(
            RegistroGesto.objects.filter(gesto=self.gesto, fecha=fecha).exists()
        )

    def test_toggle_actualiza_mejor_racha(self):
        hoy = timezone.localdate()
        self.assertEqual(self.gesto.mejor_racha, 0)

        # Construye una racha de 3 días consecutivos terminando hoy.
        for offset in range(2, -1, -1):
            fecha = hoy - timedelta(days=offset)
            HabitosService.toggle_dia(self.gesto, fecha)

        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.mejor_racha, 3)
        self.assertEqual(self.gesto.get_racha_actual(), 3)


class RachaEndToEndTestCase(TestCase):
    """5. get_racha_actual cruza meses vía toggle_dia."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(usuario=self.usuario, nombre='Caminar', tipo='cultivo')

    def test_racha_cruza_mes_via_toggle(self):
        import unittest.mock as mock

        hoy = date(2026, 3, 1)
        ayer = date(2026, 2, 28)

        HabitosService.toggle_dia(self.gesto, ayer)
        HabitosService.toggle_dia(self.gesto, hoy)

        with mock.patch('diario.models.timezone.localdate', return_value=hoy):
            self.assertEqual(self.gesto.get_racha_actual(), 2)


class PausarCerrarTestCase(TestCase):
    """6 y 7. Pausar y cerrar conservan historial y filtran el dashboard."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.usuario)
        self.gesto = Gesto.objects.create(usuario=self.usuario, nombre='Yoga', tipo='cultivo')
        RegistroGesto.objects.create(gesto=self.gesto, fecha=date(2026, 6, 1), estado='cumplido')
        RegistroGesto.objects.create(gesto=self.gesto, fecha=date(2026, 6, 2), estado='cumplido')

    def test_pausar_cambia_estado_y_conserva_registros(self):
        count_antes = self.gesto.registros.count()

        response = self.client.post(reverse('diario:habito_pausar', args=[self.gesto.id]))

        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'pausado')
        self.assertEqual(self.gesto.registros.count(), count_antes)
        self.assertEqual(response.status_code, 302)

    def test_cerrar_cambia_estado_fija_fecha_y_desaparece_del_dashboard(self):
        count_antes = self.gesto.registros.count()

        response = self.client.post(reverse('diario:habito_cerrar', args=[self.gesto.id]))

        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'cerrado')
        self.assertEqual(self.gesto.fecha_cierre, timezone.localdate())
        self.assertEqual(self.gesto.registros.count(), count_antes)
        self.assertEqual(response.status_code, 302)

        dashboard_response = self.client.get(reverse('diario:habitos_dashboard'))
        nombres = [item['habito'].nombre for item in dashboard_response.context['habitos_positivos']]
        self.assertNotIn('Yoga', nombres)


class AceptarHabitoInvitacionTestCase(TestCase):
    """8. aceptar_habito_invitacion crea un Gesto, no un ProsocheHabito."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.usuario)

    def test_crea_gesto_no_prosochehabito(self):
        import json

        count_prosoche_antes = ProsocheHabito.objects.count()

        response = self.client.post(
            reverse('diario:aceptar_habito_invitacion'),
            data=json.dumps({'nombre': 'Estirar', 'descripcion': 'Por la mañana', 'tipo': 'positivo'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])

        self.assertTrue(Gesto.objects.filter(usuario=self.usuario, nombre='Estirar', tipo='cultivo').exists())
        self.assertEqual(ProsocheHabito.objects.count(), count_prosoche_antes)


class TriggerHabitoGestoTestCase(TestCase):
    """9. habito_registrar_trigger crea TriggerHabito con gesto poblado y habito=None."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.usuario)
        self.gesto = Gesto.objects.create(usuario=self.usuario, nombre='Fumar', tipo='suelto')

    def test_trigger_nuevo_tiene_gesto_poblado(self):
        response = self.client.post(
            reverse('diario:habito_registrar_trigger', args=[self.gesto.id]),
            data={
                'fecha': '2026-06-10',
                'hora': '20:00',
                'emocion_previa': 'estres',
                'situacion': 'Tras una reunión larga',
                'personas_presentes': '',
                'intensidad_deseo': 5,
                'cediste': False,
                'estrategia_usada': 'Salí a caminar',
                'aprendizaje': '',
            },
        )

        trigger = TriggerHabito.objects.latest('id')
        self.assertEqual(trigger.gesto_id, self.gesto.id)
        self.assertIsNone(trigger.habito_id)
        self.assertIn(response.status_code, (200, 302))


class BackfillTriggerHabitoGestoTestCase(TestCase):
    """10. Backfill de TriggerHabito.gesto para triggers legacy."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.prosoche_mes = ProsocheMes.objects.create(usuario=self.usuario, mes='June', año=2026)
        self.habito_legacy = ProsocheHabito.objects.create(
            prosoche_mes=self.prosoche_mes,
            nombre='Fumar',
            tipo_habito='negativo',
        )
        self.gesto = Gesto.objects.create(usuario=self.usuario, nombre='Fumar', tipo='suelto')

    def test_backfill_popula_gesto_por_match_usuario_nombre(self):
        trigger = TriggerHabito.objects.create(
            habito=self.habito_legacy,
            gesto=None,
            fecha=date(2026, 6, 1),
            hora='10:00',
            emocion_previa='estres',
            situacion='Test',
            intensidad_deseo=5,
            cediste=True,
        )
        self.assertIsNone(trigger.gesto_id)

        backfill_gesto(apps, schema_editor=None)

        trigger.refresh_from_db()
        self.assertEqual(trigger.gesto_id, self.gesto.id)


class InsigniaDiasCumplidosTestCase(TestCase):
    """11. Insignias por 'N días cumplidos' siguen disparando desde RegistroGesto."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(usuario=self.usuario, nombre='Leer', tipo='cultivo')

    def test_insignia_1dia_se_otorga_con_un_registro_cumplido(self):
        RegistroGesto.objects.create(gesto=self.gesto, fecha=date(2026, 6, 1), estado='cumplido')

        otorgadas = InsigniasService.verificar_insignias_habito(self.gesto, self.usuario)

        codigos_otorgados = [Insignia.objects.get(nombre=i.nombre).codigo for i in otorgadas]
        self.assertIn('habito_positivo_1dia', codigos_otorgados)

    def test_insignia_7dias_se_otorga_con_siete_registros_cumplidos(self):
        for dia in range(1, 8):
            RegistroGesto.objects.create(gesto=self.gesto, fecha=date(2026, 6, dia), estado='cumplido')

        otorgadas = InsigniasService.verificar_insignias_habito(self.gesto, self.usuario)

        codigos_otorgados = [Insignia.objects.get(nombre=i.nombre).codigo for i in otorgadas]
        self.assertIn('habito_positivo_1dia', codigos_otorgados)
        self.assertIn('habito_positivo_7dias', codigos_otorgados)
