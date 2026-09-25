from django.test import SimpleTestCase

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
