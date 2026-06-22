"""
Phase Gym Peso 2.1 — guardar_entrenamiento_activo ya no dispara one_rm_data
en descarga, ni con RPE bajo confianza, ni de golpe al e1RM observado.

Bug confirmado en servidor real antes de esta fase (Client().post() real,
RM base 92.5kg, descarga prescrita 72.5kg x10 RPE objetivo 6):
  SANO (real = exactamente lo prescrito)  -> RM subía a 106.3kg
  INTERESANTE (80kg x10 RPE6)             -> RM subía a 117.3kg
  PELIGROSO (88kg x10 RPE9)               -> RM subía a 120.3kg

Estos tests fuerzan _necesita_deload_gym_hoy (vía rutina_nombre con
'descarga', que es la misma señal que usa la vista GET en
vista_entrenamiento_activo) para no depender de fabricar 2+ semanas de
historial de fatiga real solo para activar el criterio de
necesita_deload_gym.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from rutinas.models import Rutina


class TestGatingRMGuardarEntrenamiento(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_gating_rm', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestGatingRM', 'dias_disponibles': 4},
        )
        self.cliente.one_rm_data = {'sentadilla': 92.5}
        self.cliente.save(update_fields=['one_rm_data'])
        Rutina.objects.get_or_create(nombre='Descarga Test')
        Rutina.objects.get_or_create(nombre='Fuerza Test')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:guardar_entrenamiento_activo', kwargs={'cliente_id': self.cliente.id})

    def _base_post(self, rutina_nombre):
        return {
            'fecha': '2026-06-22',
            'rutina_nombre': rutina_nombre,
            'sesion_programada_id': '',
            'modo_reducido': '0',
            'duracion_minutos_real': '40',
            'series_completadas': '', 'series_totales': '',
            'ejercicios_completados': '', 'ejercicios_totales': '',
            'volumen_total_sesion': '', 'rpe_medio_sesion': '',
            'rpe_global_sesion': '', 'energia_pre_sesion': '',
            'ej1_nombre': 'Sentadilla',
            'ej1_tipo_progresion': 'peso_reps',
            'ej1_es_principal': '',
            'ej1_es_tope_maquina': 'false',
            'ej1_molestia_reportada': 'false',
        }

    def _refrescar_rm_de(self, nombre):
        self.cliente.refresh_from_db()
        return self.cliente.one_rm_data.get(nombre)

    def _refrescar_rm(self):
        self.cliente.refresh_from_db()
        return self.cliente.one_rm_data.get('sentadilla')

    def test_1_descarga_peso_y_rpe_exactos_no_sube_rm(self):
        """RM antes 92.5 -> descarga prescrita y real idénticas (72.5kg x10 RPE6)."""
        data = self._base_post('Descarga Test')
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '72.5'
            data[f'ej1_reps_{i}'] = '10'
            data[f'ej1_rpe_{i}'] = '6'
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 302)
        rm_despues = self._refrescar_rm()
        self.assertEqual(rm_despues, 92.5, f"RM no debía subir en descarga, quedó en {rm_despues}")

    def test_2_descarga_real_por_encima_de_lo_prescrito_no_sube_rm(self):
        """Descarga real 80kg x10 RPE6 (algo por encima de lo prescrito)."""
        data = self._base_post('Descarga Test')
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '80'
            data[f'ej1_reps_{i}'] = '10'
            data[f'ej1_rpe_{i}'] = '6'
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 302)
        rm_despues = self._refrescar_rm()
        self.assertEqual(rm_despues, 92.5, f"RM no debía subir en descarga, quedó en {rm_despues}")

    def test_3_descarga_muy_por_encima_con_rpe_alto_no_sube_rm(self):
        """Descarga real 88kg x10 RPE9 (muy por encima, RPE alto)."""
        data = self._base_post('Descarga Test')
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '88'
            data[f'ej1_reps_{i}'] = '10'
            data[f'ej1_rpe_{i}'] = '9'
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 302)
        rm_despues = self._refrescar_rm()
        self.assertEqual(rm_despues, 92.5, f"RM no debía subir en descarga, quedó en {rm_despues}")

    def test_4_fase_no_descarga_sube_pero_con_tope_suavizado(self):
        """Fase normal con e1RM observado claramente mayor: sube, pero no al e1RM crudo."""
        data = self._base_post('Fuerza Test')
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '100'
            data[f'ej1_reps_{i}'] = '5'
            data[f'ej1_rpe_{i}'] = '8'
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 302)
        rm_despues = self._refrescar_rm()
        self.assertGreater(rm_despues, 92.5)
        self.assertLessEqual(rm_despues, round(92.5 * 1.03, 2))

    def test_5_sin_rpe_real_no_sube_rm(self):
        """Sin RPE real registrado: confianza baja, no se toca one_rm_data."""
        data = self._base_post('Fuerza Test')
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '100'
            data[f'ej1_reps_{i}'] = '5'
            data[f'ej1_rpe_{i}'] = ''
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 302)
        rm_despues = self._refrescar_rm()
        self.assertEqual(rm_despues, 92.5, f"RM no debía subir sin RPE real, quedó en {rm_despues}")

    def test_7_descarga_dos_ejercicios_uno_sin_historial_no_se_contaminan(self):
        """Bug real: sesión con DOS ejercicios a la vez en descarga, uno con RM
        previo (Sentadilla, 92.5) y otro sin historial (Press Banca, primera vez).
        Sentadilla debe mantenerse intacta; Press Banca debe guardar su RM
        inicial en vez de quedarse en None para siempre."""
        data = self._base_post('Descarga Test')
        data['ej2_nombre'] = 'Press Banca'
        data['ej2_tipo_progresion'] = 'peso_reps'
        data['ej2_es_principal'] = ''
        data['ej2_es_tope_maquina'] = 'false'
        data['ej2_molestia_reportada'] = 'false'
        for i in range(1, 4):
            data[f'ej1_peso_{i}'] = '72.5'
            data[f'ej1_reps_{i}'] = '10'
            data[f'ej1_rpe_{i}'] = '6'
            data[f'ej2_peso_{i}'] = '40'
            data[f'ej2_reps_{i}'] = '8'
            data[f'ej2_rpe_{i}'] = '7'
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 302)

        rm_sentadilla = self._refrescar_rm_de('sentadilla')
        self.assertEqual(rm_sentadilla, 92.5, f"RM con historial no debía cambiar en descarga, quedó en {rm_sentadilla}")

        rm_press_banca = self._refrescar_rm_de('press banca')
        self.assertIsNotNone(rm_press_banca, "RM inicial de ejercicio sin historial no debía quedarse en None")
        self.assertGreater(rm_press_banca, 0, "RM inicial de ejercicio sin historial no debía quedarse en 0")

    def test_6_no_regresion_peso_de_trabajo_no_se_toca(self):
        """Esta fase no debe tocar resolver_peso_objetivo (Phase Gym Peso 2)."""
        from analytics.planificador_helms.calculo.compatibilidad_fase import resolver_peso_objetivo
        r = resolver_peso_objetivo(
            peso_anterior=107.5, reps_anteriores=3, rpe_anterior=8,
            rep_range_hoy='10-15', rpe_objetivo_hoy=6, es_descarga_hoy=True,
        )
        self.assertTrue(r['aplica'])
        self.assertEqual(r['motivo_tipo'], 'recalculado_descarga')
        self.assertLess(r['peso'], 90.0)
