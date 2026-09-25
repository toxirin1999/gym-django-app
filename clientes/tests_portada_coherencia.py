from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from clientes.models import Cliente

from clientes.views import (
    _filtrar_resumen_semanal_para_portada,
    _normalizar_acwr_para_portada,
)


class PortadaCoherenciaTests(SimpleTestCase):
    def test_acwr_bajo_no_conserva_mensaje_de_zona_verde(self):
        analisis = _normalizar_acwr_para_portada({
            'acwr_actual': 0.49,
            'zona_riesgo': 'baja_carga',
            'dias_descanso': 0,
        })

        self.assertIsNone(analisis['dias_descanso'])

    def test_resumen_deduplica_el_mismo_pr_y_oculta_subida_en_descarga(self):
        resumen = [
            {'icono': '🏆', 'texto': 'Nuevo récord de peso máximo · Encogimientos con mancuernas'},
            {'icono': '🏆', 'texto': 'Nuevo récord de peso máximo · Encogimientos con mancuernas'},
            {'tipo': 'seccion', 'icono': '📈', 'texto': 'El plan sube carga'},
            {'tipo': 'progresion', 'icono': '↗', 'texto': 'Encogimientos con mancuernas: 24 kg'},
            {'icono': '✅', 'texto': 'Técnica estable en todas las series'},
        ]

        resultado = _filtrar_resumen_semanal_para_portada(resumen, en_descarga=True)

        self.assertEqual([item['texto'] for item in resultado], [
            'Nuevo récord de peso máximo · Encogimientos con mancuernas',
            'Técnica estable en todas las series',
        ])

    def test_resumen_normal_preserva_directiva_de_progresion(self):
        resumen = [{'icono': '📈', 'texto': 'El plan sube carga un 5% en press'}]

        self.assertEqual(
            _filtrar_resumen_semanal_para_portada(resumen, en_descarga=False),
            resumen,
        )


class WidgetAcwrCoherenciaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('acwr_portada', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)

    @patch('entrenos.services.services.EstadisticasService.analizar_acwr_unificado')
    def test_widget_lazy_no_afirma_zona_verde_con_carga_baja(self, analizar):
        analizar.return_value = {
            'acwr_actual': 0.49,
            'zona_riesgo': 'baja_carga',
            'dias_descanso': 0,
            'dataframe': [],
        }

        response = self.client.get(reverse('clientes:widget_acwr', args=[self.cliente.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Carga Baja')
        self.assertNotContains(response, 'Ya estás en zona verde')
