"""
Fase 5B del CONTRATO_ANALIZADOR_GESTOS.md — UI de gestión.

Cubre: formulario de cadencia (mismas invariantes que el modelo),
permisos, transiciones visibles (pausar/reactivar/cerrar reflejadas en
el dashboard, grid de días no interactivo si no está activo), y la
advertencia de reinicio del análisis — solo cuando ya existía cadencia
configurada y cambia, nunca en la primera configuración.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Gesto


class FormularioCadenciaInvariantesTestCase(TestCase):
    """El formulario debe rechazar exactamente las mismas combinaciones
    que Gesto._validar_invariantes_cadencia()."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', tipo='cultivo')
        self.url = f'/diario/habitos/{self.gesto.id}/cadencia/'

    def test_libre_sin_campos_adicionales_guarda(self):
        resp = self.client.post(self.url, {'tipo_cadencia': 'libre'})
        self.assertEqual(resp.status_code, 302)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'libre')

    def test_diaria_sin_campos_adicionales_guarda(self):
        resp = self.client.post(self.url, {'tipo_cadencia': 'diaria'})
        self.assertEqual(resp.status_code, 302)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'diaria')

    def test_semanal_con_frecuencia_valida_guarda(self):
        resp = self.client.post(self.url, {'tipo_cadencia': 'semanal', 'frecuencia_semanal_objetivo': '4'})
        self.assertEqual(resp.status_code, 302)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'semanal')
        self.assertEqual(self.gesto.frecuencia_semanal_objetivo, 4)

    def test_semanal_sin_frecuencia_es_invalido(self):
        resp = self.client.post(self.url, {'tipo_cadencia': 'semanal'})
        self.assertEqual(resp.status_code, 200)  # se re-renderiza el form con error, no redirige
        self.assertContains(resp, 'form-errors')
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'libre')  # no se guardó nada

    def test_semanal_con_frecuencia_fuera_de_rango_es_invalido(self):
        resp = self.client.post(self.url, {'tipo_cadencia': 'semanal', 'frecuencia_semanal_objetivo': '9'})
        self.assertEqual(resp.status_code, 200)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'libre')

    def test_dias_concretos_con_dias_validos_guarda(self):
        resp = self.client.post(self.url, {
            'tipo_cadencia': 'dias_concretos', 'dias_semana_objetivo': ['lunes', 'miercoles'],
        })
        self.assertEqual(resp.status_code, 302)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'dias_concretos')
        self.assertEqual(set(self.gesto.dias_semana_objetivo), {'lunes', 'miercoles'})

    def test_dias_concretos_vacio_es_invalido(self):
        resp = self.client.post(self.url, {'tipo_cadencia': 'dias_concretos'})
        self.assertEqual(resp.status_code, 200)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'libre')

    def test_dias_concretos_con_valor_invalido_es_rechazado(self):
        resp = self.client.post(self.url, {
            'tipo_cadencia': 'dias_concretos', 'dias_semana_objetivo': ['funday'],
        })
        # El campo ChoiceField ya rechaza valores fuera de las choices
        # declaradas antes de llegar a clean() — sigue sin persistir nada.
        self.assertEqual(resp.status_code, 200)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'libre')

    def test_dias_concretos_con_frecuencia_semanal_tambien_es_invalido(self):
        resp = self.client.post(self.url, {
            'tipo_cadencia': 'dias_concretos', 'dias_semana_objetivo': ['domingo'],
            'frecuencia_semanal_objetivo': '1',
        })
        self.assertEqual(resp.status_code, 200)
        self.gesto.refresh_from_db()
        self.assertEqual(self.gesto.tipo_cadencia, 'libre')


class PermisosCadenciaTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.otro_usuario = User.objects.create_user(username='ana', password='x')
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', tipo='cultivo')
        self.gesto_suelto = Gesto.objects.create(usuario=self.user, nombre='Fumar', tipo='suelto')

    def test_requiere_login(self):
        resp = self.client.get(f'/diario/habitos/{self.gesto.id}/cadencia/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.url)

    def test_no_puede_configurar_gesto_de_otro_usuario(self):
        self.client.force_login(self.otro_usuario)
        resp = self.client.get(f'/diario/habitos/{self.gesto.id}/cadencia/')
        self.assertEqual(resp.status_code, 404)

    def test_no_puede_configurar_cadencia_de_un_gesto_suelto(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/diario/habitos/{self.gesto_suelto.id}/cadencia/')
        self.assertEqual(resp.status_code, 404)


class AdvertenciaReinicioTestCase(TestCase):
    """Solo debe aparecer cuando ya existía cadencia_configurada_en y
    cambia — nunca en la primera configuración de un hábito histórico."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.url_tpl = '/diario/habitos/{}/cadencia/'

    def test_primera_configuracion_de_habito_historico_no_muestra_advertencia(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', tipo='cultivo')
        self.assertIsNone(gesto.cadencia_configurada_en)

        resp = self.client.post(self.url_tpl.format(gesto.id), {'tipo_cadencia': 'diaria'})
        self.assertEqual(resp.status_code, 302)  # se guarda directo, sin paso intermedio
        gesto.refresh_from_db()
        self.assertEqual(gesto.tipo_cadencia, 'diaria')
        self.assertIsNotNone(gesto.cadencia_configurada_en)

    def test_cambio_sobre_cadencia_ya_configurada_muestra_advertencia_y_no_guarda_todavia(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2026, 1, 1),
        )
        self.assertIsNotNone(gesto.cadencia_configurada_en)

        resp = self.client.post(self.url_tpl.format(gesto.id), {
            'tipo_cadencia': 'semanal', 'frecuencia_semanal_objetivo': '3',
        })
        self.assertEqual(resp.status_code, 200)  # no redirige: pide confirmación
        self.assertContains(resp, 'reiniciará el análisis de cumplimiento')
        gesto.refresh_from_db()
        self.assertEqual(gesto.tipo_cadencia, 'diaria')  # todavía no se guardó nada

    def test_confirmar_tras_advertencia_si_guarda(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2026, 1, 1),
        )
        resp = self.client.post(self.url_tpl.format(gesto.id), {
            'tipo_cadencia': 'semanal', 'frecuencia_semanal_objetivo': '3', 'confirmado': '1',
        })
        self.assertEqual(resp.status_code, 302)
        gesto.refresh_from_db()
        self.assertEqual(gesto.tipo_cadencia, 'semanal')
        self.assertEqual(gesto.frecuencia_semanal_objetivo, 3)

    def test_reenviar_los_mismos_valores_no_muestra_advertencia(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
            fecha_inicio=date(2026, 1, 1),
        )
        cadencia_configurada_en_original = gesto.cadencia_configurada_en

        resp = self.client.post(self.url_tpl.format(gesto.id), {
            'tipo_cadencia': 'semanal', 'frecuencia_semanal_objetivo': '3',
        })
        self.assertEqual(resp.status_code, 302)  # sin cambio real → guarda directo
        gesto.refresh_from_db()
        self.assertEqual(gesto.cadencia_configurada_en, cadencia_configurada_en_original)


class TransicionesVisiblesEnDashboardTestCase(TestCase):
    """Pausar/reactivar/cerrar deben reflejarse con claridad en el
    dashboard, y el grid de días no debe ser interactivo si el hábito
    no está activo."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.client.force_login(self.user)
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Meditar', tipo='cultivo')

    def test_pausar_aparece_en_dashboard_como_pausado_sin_grid_interactivo(self):
        self.client.post(f'/diario/habitos/{self.gesto.id}/pausar/')
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == self.gesto.id)
        self.assertEqual(item['habito'].estado, 'pausado')
        self.assertContains(resp, 'Pausado')
        self.assertContains(resp, 'Reactivar')
        self.assertNotContains(resp, 'dia-toggle" data-habito-id="%d"' % self.gesto.id)

    def test_reactivar_vuelve_a_aparecer_como_activo_con_grid_interactivo(self):
        self.client.post(f'/diario/habitos/{self.gesto.id}/pausar/')
        self.client.post(f'/diario/habitos/{self.gesto.id}/reactivar/')
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == self.gesto.id)
        self.assertEqual(item['habito'].estado, 'activo')
        self.assertContains(resp, 'dia-toggle" data-habito-id="%d"' % self.gesto.id)

    def test_cerrar_desaparece_de_activos_y_aparece_en_cerrados(self):
        self.client.post(f'/diario/habitos/{self.gesto.id}/cerrar/')
        resp = self.client.get('/diario/habitos/')
        ids_positivos = [i['habito'].id for i in resp.context['habitos_positivos']]
        self.assertNotIn(self.gesto.id, ids_positivos)
        ids_cerrados = [g.id for g in resp.context['habitos_cerrados_cultivo']]
        self.assertIn(self.gesto.id, ids_cerrados)
        self.assertContains(resp, 'Cerrado el')

    def test_gesto_activo_normal_conserva_grid_interactivo(self):
        resp = self.client.get('/diario/habitos/')
        self.assertContains(resp, 'dia-toggle" data-habito-id="%d"' % self.gesto.id)
