from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.utils import get_cliente_actual
from diario.models import PersonaImportante, PersonaInterina


class ContextoRelacionalJOITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('joi-simbiosis')
        self.cliente = get_cliente_actual(self.user)
        self.hoy = date.today()

    def test_solo_una_persona_confirmada_y_recurrente_alimenta_a_joi(self):
        confirmada = PersonaImportante.objects.create(
            usuario=self.user, nombre='Ana', tipo_relacion='amigo',
        )
        PersonaInterina.objects.create(
            usuario=self.user,
            nombre='Ana',
            estado='promovida',
            veces_mencionada=3,
            persona_importante=confirmada,
        )
        PersonaInterina.objects.create(
            usuario=self.user, nombre='Bea', estado='radar', veces_mencionada=4,
        )

        from joi.context_builders.life_context import build_life_context
        contexto = build_life_context(
            self.cliente, self.hoy, self.hoy - timedelta(days=7),
        )

        self.assertEqual(contexto['presencia_relacional'], [{
            'nombre': 'Ana',
            'veces': 3,
            'dias_desde': 0,
            'tipo_relacion': 'amigo',
        }])

    @patch('joi.services.extraer_entidades_simbiosis')
    @patch('joi.services.generar_tema_abierto')
    @patch('joi.services._llamar_haiku_sintesis', return_value='Síntesis')
    @patch('joi.services._leer_diario_reciente', return_value='Diario')
    @patch('joi.services._sintetizador_contexto_vital', return_value={})
    @patch('joi.services.construir_contexto', return_value={})
    def test_sintesis_no_confirma_personas_sin_decision_del_usuario(
        self, _contexto, _vital, _diario, _llamada, _tema, extraer,
    ):
        from joi.services import generar_sintesis_joi

        mensaje = generar_sintesis_joi(self.cliente)

        self.assertIsNotNone(mensaje)
        extraer.assert_not_called()
