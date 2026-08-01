import io
import json
from datetime import date

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from diario.models import Interaccion, InteraccionSombra, PersonaImportante, PersonaInterina


class ReconciliacionSimbiosisLegacyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reconciliacion-simbiosis')
        self.persona = PersonaImportante.objects.create(usuario=self.user, nombre='Ana')
        self.interina = PersonaInterina.objects.create(
            usuario=self.user,
            nombre='Ana',
            estado='promovida',
            persona_importante=self.persona,
        )
        self.sombra = self._crear_sombra()
        self.legacy = self._crear_legacy()

    def _crear_sombra(self, **overrides):
        datos = {
            'persona_interina': self.interina,
            'fecha': date(2026, 6, 15),
            'descripcion': 'Hablamos de un asunto importante.',
            'mi_sentir': 'Acompañado',
            'aprendizaje': 'Puedo pedir ayuda',
            'tipo_interaccion': 'apoyo',
        }
        datos.update(overrides)
        return InteraccionSombra.objects.create(**datos)

    def _crear_legacy(self, **overrides):
        datos = {
            'usuario': self.user,
            'titulo': 'Mención detectada · Ana',
            'fecha': date(2026, 6, 15),
            'descripcion': 'Hablamos de un asunto importante.',
            'mi_sentir': 'Acompañado',
            'aprendizaje': 'Puedo pedir ayuda',
            'tipo_interaccion': 'apoyo',
        }
        datos.update(overrides)
        interaccion = Interaccion.objects.create(**datos)
        interaccion.personas.add(self.persona)
        return interaccion

    def _ejecutar(self, *args):
        salida = io.StringIO()
        call_command('reconciliar_simbiosis_legacy', *args, stdout=salida)
        return salida.getvalue().strip().splitlines()

    def test_dry_run_reporta_candidato_inequivoco_sin_mutar(self):
        lineas = self._ejecutar()

        self.legacy.refresh_from_db()
        self.assertIsNone(self.legacy.origen_sombra_id)
        hallazgo = json.loads(lineas[0])
        self.assertEqual(hallazgo['confidence'], 'high')
        self.assertEqual(hallazgo['proposed'], {'origen_sombra_id': self.sombra.pk})
        self.assertEqual(
            lineas[-1],
            'mode=dry-run candidates=1 eligible=1 applied=0 ambiguous=0',
        )

    def test_apply_enlaza_la_coincidencia_unica(self):
        lineas = self._ejecutar('--apply')

        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.origen_sombra_id, self.sombra.pk)
        self.assertEqual(lineas[-1], 'mode=apply candidates=1 eligible=1 applied=1 ambiguous=0')

    def test_dos_sombras_coincidentes_son_ambiguas_y_no_se_enlazan(self):
        self._crear_sombra()

        lineas = self._ejecutar('--apply')

        self.legacy.refresh_from_db()
        self.assertIsNone(self.legacy.origen_sombra_id)
        hallazgo = json.loads(lineas[0])
        self.assertEqual(hallazgo['confidence'], 'ambiguous')
        self.assertEqual(hallazgo['proposed'], None)
        self.assertEqual(lineas[-1], 'mode=apply candidates=1 eligible=0 applied=0 ambiguous=1')

    def test_no_cruza_usuarios_aunque_el_contenido_coincida(self):
        self.sombra.delete()
        otro = User.objects.create_user('reconciliacion-ajena')
        persona_ajena = PersonaImportante.objects.create(usuario=otro, nombre='Ana')
        interina_ajena = PersonaInterina.objects.create(
            usuario=otro,
            nombre='Ana',
            estado='promovida',
            persona_importante=persona_ajena,
        )
        self._crear_sombra(persona_interina=interina_ajena)

        lineas = self._ejecutar('--apply')

        self.legacy.refresh_from_db()
        self.assertIsNone(self.legacy.origen_sombra_id)
        self.assertEqual(json.loads(lineas[0])['confidence'], 'none')

    def test_replay_no_vuelve_a_evaluar_una_interaccion_enlazada(self):
        self._ejecutar('--apply')

        lineas = self._ejecutar('--apply')

        self.assertEqual(lineas, ['mode=apply candidates=0 eligible=0 applied=0 ambiguous=0'])

    def test_filtros_por_usuario_y_limite_acotan_los_candidatos(self):
        segunda = self._crear_legacy(titulo='Mención detectada · Ana')
        otro = User.objects.create_user('fuera-del-filtro')
        Interaccion.objects.create(
            usuario=otro,
            titulo='Mención detectada · Nadie',
            descripcion='Sin pareja',
        )

        lineas = self._ejecutar('--user-id', str(self.user.pk), '--limit', '1')

        self.assertEqual(lineas[-1], 'mode=dry-run candidates=1 eligible=1 applied=0 ambiguous=0')
        segunda.refresh_from_db()
        self.assertIsNone(segunda.origen_sombra_id)

