"""
Fase 3 del CONTRATO_ANALIZADOR_GESTOS.md — modelo de cadencia y pausas.

Cubre, tal como se acotó la fase: migración de hábitos existentes a
'libre' con cadencia_configurada_en=null, invariantes de validación por
tipo_cadencia, transiciones de PausaGesto (pausar/reactivar/cerrar) y
casos límite. No prueba métricas ni el analizador — no existen todavía.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import Gesto, PausaGesto
from .services.habitos_service import HabitosService


class MigracionCadenciaTestCase(TestCase):
    """Un Gesto creado sin especificar cadencia (el camino de siempre)
    debe quedar en 'libre' con cadencia_configurada_en=null — el mismo
    estado en el que la migración deja a los Gesto históricos."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_gesto_creado_sin_cadencia_queda_en_libre_sin_fecha_configurada(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Meditar', tipo='cultivo')
        self.assertEqual(gesto.tipo_cadencia, Gesto.CADENCIA_LIBRE)
        self.assertIsNone(gesto.frecuencia_semanal_objetivo)
        self.assertEqual(gesto.dias_semana_objetivo, [])
        self.assertIsNone(gesto.cadencia_configurada_en)

    def test_gesto_suelto_tambien_queda_en_libre_por_defecto(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Fumar', tipo='suelto')
        self.assertEqual(gesto.tipo_cadencia, Gesto.CADENCIA_LIBRE)
        self.assertIsNone(gesto.cadencia_configurada_en)


class CadenciaConfiguradaEnTestCase(TestCase):
    """Los cuatro casos del §2.2 del contrato."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_caso_1_gesto_nuevo_con_cadencia_elegida_usa_fecha_inicio(self):
        inicio = date(2026, 6, 1)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Correr', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=inicio,
        )
        self.assertEqual(gesto.cadencia_configurada_en, inicio)

    def test_caso_2_gesto_libre_no_recibe_fecha_configurada_automatica(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', tipo='cultivo')
        self.assertIsNone(gesto.cadencia_configurada_en)

    def test_caso_3_primera_configuracion_explicita_usa_hoy(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', tipo='cultivo')
        self.assertIsNone(gesto.cadencia_configurada_en)

        gesto.configurar_cadencia(Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3)
        gesto.refresh_from_db()
        self.assertEqual(gesto.cadencia_configurada_en, timezone.localdate())
        self.assertEqual(gesto.tipo_cadencia, Gesto.CADENCIA_SEMANAL)
        self.assertEqual(gesto.frecuencia_semanal_objetivo, 3)

    def test_caso_4_cambio_posterior_reinicia_a_hoy(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2026, 1, 1),
        )
        self.assertEqual(gesto.cadencia_configurada_en, date(2026, 1, 1))

        gesto.configurar_cadencia(Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=4)
        gesto.refresh_from_db()
        self.assertEqual(gesto.cadencia_configurada_en, timezone.localdate())
        self.assertNotEqual(gesto.cadencia_configurada_en, date(2026, 1, 1))
        self.assertEqual(gesto.tipo_cadencia, Gesto.CADENCIA_SEMANAL)


class InvariantesCadenciaTestCase(TestCase):
    """Tabla de invariantes del §2.2: combinaciones válidas e inválidas
    por tipo_cadencia."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def _gesto(self, **kwargs):
        defaults = dict(usuario=self.user, nombre='Test', tipo='cultivo')
        defaults.update(kwargs)
        return Gesto(**defaults)

    # -- libre / diaria: frecuencia y días deben ir vacíos --

    def test_libre_valido_sin_frecuencia_ni_dias(self):
        self._gesto(tipo_cadencia=Gesto.CADENCIA_LIBRE)._validar_invariantes_cadencia()

    def test_diaria_valida_sin_frecuencia_ni_dias(self):
        self._gesto(tipo_cadencia=Gesto.CADENCIA_DIARIA)._validar_invariantes_cadencia()

    def test_diaria_con_frecuencia_es_invalida(self):
        gesto = self._gesto(tipo_cadencia=Gesto.CADENCIA_DIARIA, frecuencia_semanal_objetivo=3)
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    def test_libre_con_dias_semana_es_invalida(self):
        gesto = self._gesto(tipo_cadencia=Gesto.CADENCIA_LIBRE, dias_semana_objetivo=['lunes'])
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    # -- semanal: frecuencia 1-7 obligatoria, sin días --

    def test_semanal_valida_con_frecuencia_en_rango(self):
        self._gesto(tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=4)._validar_invariantes_cadencia()

    def test_semanal_sin_frecuencia_es_invalida(self):
        gesto = self._gesto(tipo_cadencia=Gesto.CADENCIA_SEMANAL)
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    def test_semanal_con_frecuencia_fuera_de_rango_es_invalida(self):
        gesto = self._gesto(tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=8)
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    def test_semanal_con_dias_semana_es_invalida(self):
        gesto = self._gesto(
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
            dias_semana_objetivo=['lunes'],
        )
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    # -- dias_concretos: lista no vacía, sin duplicados, valores válidos --

    def test_dias_concretos_valida_con_lista_correcta(self):
        self._gesto(
            tipo_cadencia=Gesto.CADENCIA_DIAS_CONCRETOS,
            dias_semana_objetivo=['lunes', 'miercoles', 'viernes'],
        )._validar_invariantes_cadencia()

    def test_dias_concretos_vacia_es_invalida(self):
        gesto = self._gesto(tipo_cadencia=Gesto.CADENCIA_DIAS_CONCRETOS, dias_semana_objetivo=[])
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    def test_dias_concretos_con_duplicados_es_invalida(self):
        gesto = self._gesto(
            tipo_cadencia=Gesto.CADENCIA_DIAS_CONCRETOS, dias_semana_objetivo=['lunes', 'lunes'],
        )
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    def test_dias_concretos_con_valor_no_valido_es_invalida(self):
        gesto = self._gesto(
            tipo_cadencia=Gesto.CADENCIA_DIAS_CONCRETOS, dias_semana_objetivo=['funday'],
        )
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    def test_dias_concretos_con_frecuencia_semanal_es_invalida(self):
        gesto = self._gesto(
            tipo_cadencia=Gesto.CADENCIA_DIAS_CONCRETOS,
            dias_semana_objetivo=['domingo'], frecuencia_semanal_objetivo=1,
        )
        with self.assertRaises(ValidationError):
            gesto._validar_invariantes_cadencia()

    def test_configurar_cadencia_invalida_no_persiste_cambios(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Correr', tipo='cultivo')
        with self.assertRaises(ValidationError):
            gesto.configurar_cadencia(Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=None)
        gesto.refresh_from_db()
        self.assertEqual(gesto.tipo_cadencia, Gesto.CADENCIA_LIBRE)
        self.assertIsNone(gesto.cadencia_configurada_en)


class PausaGestoTransicionesTestCase(TestCase):
    """Pausar, reactivar, cerrar — incluida la regla de colapso del
    mismo día y el cierre de pausa al cerrar definitivamente."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Meditar', tipo='cultivo')

    def test_pausar_crea_pausa_abierta_y_cambia_estado(self):
        HabitosService.pausar_gesto(self.gesto, fecha=date(2026, 6, 22))
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'pausado')
        pausa = self.gesto.pausas.get()
        self.assertEqual(pausa.fecha_inicio, date(2026, 6, 22))
        self.assertIsNone(pausa.fecha_fin)

    def test_pausar_dos_veces_es_idempotente_no_crea_segunda_pausa(self):
        HabitosService.pausar_gesto(self.gesto, fecha=date(2026, 6, 22))
        HabitosService.pausar_gesto(self.gesto, fecha=date(2026, 6, 23))
        self.assertEqual(self.gesto.pausas.count(), 1)
        pausa = self.gesto.pausas.get()
        self.assertEqual(pausa.fecha_inicio, date(2026, 6, 22))  # la primera, no se sobrescribe

    def test_reactivar_cierra_la_pausa_y_reactiva_el_gesto(self):
        HabitosService.pausar_gesto(self.gesto, fecha=date(2026, 6, 22))
        HabitosService.reactivar_gesto(self.gesto, fecha=date(2026, 7, 1))
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'activo')
        pausa = self.gesto.pausas.get()
        self.assertEqual(pausa.fecha_fin, date(2026, 7, 1))

    def test_reactivar_mismo_dia_colapsa_borra_la_pausa(self):
        HabitosService.pausar_gesto(self.gesto, fecha=date(2026, 6, 22))
        HabitosService.reactivar_gesto(self.gesto, fecha=date(2026, 6, 22))
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'activo')
        self.assertEqual(self.gesto.pausas.count(), 0)

    def test_reactivar_sin_pausa_abierta_no_falla_solo_reactiva(self):
        # Caso defensivo: estado inconsistente (p. ej. editado a mano).
        self.gesto.estado = 'pausado'
        self.gesto.save(update_fields=['estado'])
        HabitosService.reactivar_gesto(self.gesto, fecha=date(2026, 7, 1))
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.estado, 'activo')

    def test_cerrar_gesto_pausado_cierra_la_pausa_abierta(self):
        HabitosService.pausar_gesto(self.gesto, fecha=date(2026, 6, 22))
        fecha_cierre = date(2026, 7, 5)
        HabitosService._cerrar_pausa_abierta(self.gesto, fecha_cierre)
        self.gesto.estado = 'cerrado'
        self.gesto.fecha_cierre = fecha_cierre
        self.gesto.save(update_fields=['estado', 'fecha_cierre'])

        pausa = self.gesto.pausas.get()
        self.assertEqual(pausa.fecha_fin, fecha_cierre)

    def test_cerrar_gesto_pausado_mismo_dia_de_la_pausa_colapsa(self):
        misma_fecha = date(2026, 6, 22)
        HabitosService.pausar_gesto(self.gesto, fecha=misma_fecha)
        HabitosService._cerrar_pausa_abierta(self.gesto, misma_fecha)
        self.assertEqual(self.gesto.pausas.count(), 0)

    def test_pausa_abierta_duplicada_viola_restriccion_de_base_de_datos(self):
        """La restricción a nivel de BD es la última línea de defensa,
        incluso saltándose el servicio."""
        PausaGesto.objects.create(gesto=self.gesto, fecha_inicio=date(2026, 6, 1), fecha_fin=None)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PausaGesto.objects.create(gesto=self.gesto, fecha_inicio=date(2026, 6, 10), fecha_fin=None)


class ToggleDiaCasosLimiteTestCase(TestCase):
    """habito_toggle_dia no debe admitir registros manuales sobre un
    Gesto pausado o cerrado. habito_reactivar solo actúa sobre
    Gesto 'pausado'."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto_pausado = Gesto.objects.create(
            usuario=self.user, nombre='Correr', tipo='cultivo', estado='pausado'
        )
        self.gesto_cerrado = Gesto.objects.create(
            usuario=self.user, nombre='Viejo hábito', tipo='cultivo', estado='cerrado'
        )
        self.gesto_activo = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )

    def test_toggle_sobre_gesto_pausado_no_crea_registro(self):
        hoy = timezone.localdate()
        resp = self.client.post(
            '/diario/habitos/toggle-dia/',
            data='{"habito_id": %d, "dia": %d}' % (self.gesto_pausado.id, hoy.day),
            content_type='application/json',
        )
        self.assertEqual(resp.json()['success'], False)
        self.assertFalse(self.gesto_pausado.registros.exists())

    def test_toggle_sobre_gesto_cerrado_no_crea_registro(self):
        hoy = timezone.localdate()
        resp = self.client.post(
            '/diario/habitos/toggle-dia/',
            data='{"habito_id": %d, "dia": %d}' % (self.gesto_cerrado.id, hoy.day),
            content_type='application/json',
        )
        self.assertEqual(resp.json()['success'], False)
        self.assertFalse(self.gesto_cerrado.registros.exists())

    def test_toggle_sobre_gesto_activo_sigue_funcionando(self):
        hoy = timezone.localdate()
        resp = self.client.post(
            '/diario/habitos/toggle-dia/',
            data='{"habito_id": %d, "dia": %d}' % (self.gesto_activo.id, hoy.day),
            content_type='application/json',
        )
        self.assertEqual(resp.json()['success'], True)
        self.assertTrue(self.gesto_activo.registros.filter(fecha=hoy, estado='cumplido').exists())

    def test_reactivar_endpoint_ignora_gesto_activo(self):
        resp = self.client.post(f'/diario/habitos/{self.gesto_activo.id}/reactivar/')
        self.assertEqual(resp.status_code, 404)
        self.gesto_activo.refresh_from_db()
        self.assertEqual(self.gesto_activo.estado, 'activo')

    def test_reactivar_endpoint_funciona_sobre_gesto_pausado(self):
        resp = self.client.post(f'/diario/habitos/{self.gesto_pausado.id}/reactivar/')
        self.assertEqual(resp.status_code, 302)
        self.gesto_pausado.refresh_from_db()
        self.assertEqual(self.gesto_pausado.estado, 'activo')
