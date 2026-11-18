"""2-nov-2026 · Paneles: marcador en descarga, frase con verbo y energía en el historial."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from entrenos.models import SemanaPlanGym
from entrenos.tests_ultima_sesion import Base

LUNES = date(2026, 11, 2)


class Frase(SimpleTestCase):
    def test_dias_pendientes_se_nombran_con_y(self):
        from entrenos.services.marcador_semanal_service import _frase
        f = _frase([{'grupo': 'Pecho', 'hechas': 0, 'plan': 14, 'pendientes': 7, 'proyectadas': 7,
                     'estado': 'falta', 'cubren': ['Día 1', 'Día 5']}])
        self.assertIn('las sesiones pendientes (Día 1 y Día 5) aportan 7', f)


class MarcadorDescarga(Base):
    def test_en_descarga_cuenta_desde_el_lunes(self):
        from collections import Counter
        from entrenos.services import marcador_semanal_service as m
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=LUNES, semana_plan=44, descarga=True,
                                     origen='descarga_programada')
        llamadas = []

        def hechas(cliente, desde, hasta):
            llamadas.append((hasta - desde).days + 1)
            return Counter({'pecho': 2}), Counter({'pecho': 2}), Counter()
        with patch.object(m, 'series_plan_semana', return_value=(Counter({'pecho': 7}), [])), \
                patch.object(m, 'series_hechas_detalle', side_effect=hechas), \
                patch.object(m, '_pendientes', return_value=[]):
            r = m.marcador_semanal(self.cliente, LUNES + timedelta(days=1))
        self.assertEqual(llamadas, [2])
        self.assertTrue(r['descarga'])
        self.assertEqual(r['filas'][0]['estado'], 'falta')
        self.assertTrue(r['periodo'].startswith('Semana de descarga'))
        self.assertNotIn('sobra', r)


class Historial(Base):
    def test_energia_al_empezar_sin_check_in(self):
        from django.urls import reverse
        e = self.entreno(date.today(), {self.hack.nombre: '10-15'})
        e.energia_pre_sesion = 6
        e.save(update_fields=['energia_pre_sesion'])
        self.client.force_login(self.cliente.user)
        r = self.client.get(reverse('entrenos:timeline_atleta', args=[self.cliente.id]))
        self.assertContains(r, 'Energía al empezar')
