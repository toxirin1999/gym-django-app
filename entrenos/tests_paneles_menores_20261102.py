"""2-nov-2026 · Paneles: marcador en descarga, frase con verbo y energía en el historial."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from entrenos.models import SemanaPlanGym
from entrenos.tests_ultima_sesion import Base

LUNES = date(2026, 11, 2)


class Frase(SimpleTestCase):
    def test_verbo_en_plural_con_dos_dias(self):
        from entrenos.services.marcador_semanal_service import _frase_falta
        f = _frase_falta([{'grupo': 'Pecho', 'hechas': 0, 'minimo': 7, 'maximo': 14, 'estado': 'bajo',
                           'cubren': ['Día 1', 'Día 5']}])
        self.assertTrue(f.endswith('el Día 1 y el Día 5 las cubren.'), f)


class MarcadorDescarga(Base):
    def test_en_descarga_cuenta_desde_el_lunes_y_sin_minimos(self):
        from collections import Counter
        from entrenos.services import marcador_semanal_service as m
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES, semana_plan=44, descarga=True,
                                     origen='descarga_programada')
        llamadas = []

        def hechas(cliente, hoy, dias=7):
            llamadas.append(dias)
            return Counter({'pecho': 2})
        with patch.object(m, 'series_plan_semana', return_value=(Counter({'pecho': 7}), [])), \
                patch.object(m, 'series_hechas', side_effect=hechas), \
                patch.object(m, '_pendientes', return_value=[]):
            r = m.marcador_semanal(self.cliente, LUNES + timedelta(days=1))
        self.assertEqual(llamadas, [2])
        self.assertTrue(r['descarga'])
        self.assertEqual(r['filas'][0]['estado'], 'ok')
        self.assertIn('Semana de descarga', r['frase'])
        self.assertIsNone(r['sobra'])


class Historial(Base):
    def test_energia_al_empezar_sin_check_in(self):
        from django.urls import reverse
        e = self.entreno(date.today(), {self.hack.nombre: '10-15'})
        e.energia_pre_sesion = 6
        e.save(update_fields=['energia_pre_sesion'])
        self.client.force_login(self.cliente.user)
        r = self.client.get(reverse('entrenos:timeline_atleta', args=[self.cliente.id]))
        self.assertContains(r, 'Energía al empezar')
