from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ContratoSemanalGym, SesionProgramada
from entrenos.services.contrato_bloque_gym_service import (
    activar_bloque_gym,
    preparar_bloque_gym_colaborativo,
)


class CentroOperativoVisualTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('centro-operativo-ui')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.hoy = date(2026, 8, 27)

    def test_jerarquia_operativa_y_detalles_cerrados(self):
        with self.settings(USE_TZ=True):
            with timezone.override('Europe/Madrid'):
                response = self.client.get(reverse('clientes:plan_decisiones'))
        html = response.content.decode()
        self.assertLess(html.index('Siguiente paso'), html.index('Activo ahora'))
        self.assertIn('class="dc-hero is-compact"', html)
        self.assertIn('<details class="dc-definitions">', html)
        self.assertIn('<details class="dc-technical-shell">', html)
        self.assertNotIn('<details class="dc-technical-shell" open', html)
        self.assertContains(response, 'Progreso semanal desconocido')

    def test_resumen_visible_muestra_sesion_y_progreso_real(self):
        lunes = date(2026, 8, 24)
        bloque = preparar_bloque_gym_colaborativo(
            self.cliente, actor=self.user, semana_inicio=lunes, semanas_previstas=4,
            objetivo_principal='fuerza', objetivos_secundarios=[], motivo='',
        )
        activar_bloque_gym(bloque, actor=self.user, version_esperada=bloque.version)
        contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=bloque.estrategia, bloque=bloque,
            indice_semana_bloque=1, semana=lunes, objetivo_sesiones=5, minimo_valido=3,
        )
        SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=contrato, fecha_prevista=lunes,
            estado=SesionProgramada.ESTADO_COMPLETADA, nombre_sesion='Día 1',
        )
        SesionProgramada.objects.create(
            cliente=self.cliente, contrato_semanal=contrato, fecha_prevista=lunes + timedelta(days=4),
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='Día 2 — Fuerza',
        )

        with self.settings(USE_TZ=True):
            with timezone.override('Europe/Madrid'):
                with self.subTest('fecha fijada por patch en vista'):
                    from unittest.mock import patch
                    with patch('clientes.views.timezone.localdate', return_value=self.hoy):
                        response = self.client.get(reverse('clientes:plan_decisiones'))

        self.assertContains(response, 'Día 2 — Fuerza')
        self.assertContains(response, '1 de 5 completadas')
        self.assertContains(response, 'Semana 1 de 4')

    def test_solo_tres_grupos_recientes_quedan_visibles(self):
        source = Path('clientes/templates/clientes/plan_decisiones.html').read_text()
        self.assertIn('traces_agrupados|slice:":3"', source)
        self.assertIn('traces_agrupados|slice:"3:"', source)
