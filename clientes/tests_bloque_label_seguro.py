from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import ContratoBloqueGym, EstrategiaSemanalGym
from entrenos.services.contrato_bloque_gym_service import consultar_bloque_gym_colaborativo


class BloqueLabelSeguroTests(TestCase):
    def test_label_legacy_es_seguro_y_card_lo_rotula_objetivo_general(self):
        user = User.objects.create_user('label-bloque')
        cliente = Cliente.objects.get(user=user)
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=cliente, version=1, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=date(2026, 8, 24), aprobado_por=user,
        )
        bloque = ContratoBloqueGym.objects.create(
            cliente=cliente, version=1, estado='activo', semana_inicio=date(2026, 8, 24),
            semanas_previstas=4, semana_fin_prevista=date(2026, 9, 20), estrategia=estrategia,
            objetivo_sesiones=5, minimo_valido=3, objetivo_principal='HIPERTROFIA ',
            objetivos_secundarios=[], limites_snapshot={}, motor_nombre='Helms', motor_version='actual',
            fingerprint='legacy-label-safe',
        )
        card = consultar_bloque_gym_colaborativo(cliente)['card']
        self.assertEqual(card['objetivo_label'], 'Hipertrofia Muscular')
        self.assertEqual(bloque.objetivo_principal, 'HIPERTROFIA ')
        self.client.force_login(user)
        response = self.client.get('/clientes/plan/decisiones/')
        self.assertContains(response, 'Objetivo general')
