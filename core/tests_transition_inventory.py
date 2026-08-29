import hashlib
import json
from io import StringIO
from pathlib import Path

from django.core.management import call_command, get_commands, load_command_class
from django.test import SimpleTestCase
from django.urls import reverse


class TransitionInventoryContractTests(SimpleTestCase):
    def _inventory(self):
        from core.services.transition_inventory_service import build_transition_inventory

        return build_transition_inventory()

    def test_inventory_is_deterministic_canonical_and_has_no_timestamp(self):
        first = self._inventory()
        second = self._inventory()

        self.assertEqual(first, second)
        self.assertEqual(first['schema_version'], 1)
        self.assertTrue(first['solo_lectura'])
        self.assertNotIn('generated_at', first)
        self.assertNotIn('fecha_generacion', first)

        unsigned = {key: value for key, value in first.items() if key != 'fingerprint'}
        canonical = json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
        self.assertEqual(first['fingerprint'], hashlib.sha256(canonical).hexdigest())

    def test_schema_enums_ids_dependencies_and_authority_are_valid(self):
        inventory = self._inventory()
        surfaces = inventory['superficies']
        ids = [item['id'] for item in surfaces]

        self.assertGreaterEqual(len(surfaces), 15)
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(inventory['resumen']['total_superficies'], len(surfaces))

        allowed_states = set(inventory['contrato']['estados'])
        allowed_authorities = set(inventory['contrato']['autoridades'])
        forbidden = {'archived', 'postponed', 'legacy_compat'}
        for item in surfaces:
            self.assertIn(item['estado'], allowed_states)
            self.assertIn(item['autoridad'], allowed_authorities)
            self.assertEqual(item['dependencias'], sorted(set(item['dependencias'])))
            self.assertTrue(set(item['dependencias']).issubset(ids))
            if item['estado'] in forbidden:
                self.assertEqual(item['autoridad'], 'none')

    def test_declared_routes_commands_and_processes_are_resolvable(self):
        inventory = self._inventory()
        available_commands = get_commands()

        for surface in inventory['superficies']:
            for route in surface['rutas']:
                self.assertTrue(reverse(route['name'], args=route.get('args') or None))
            for command_name in surface['comandos']:
                self.assertIn(command_name, available_commands)
                load_command_class(available_commands[command_name], command_name)
            for process in surface['procesos']:
                module_name, attribute = process.rsplit('.', 1)
                module = __import__(module_name, fromlist=[attribute])
                self.assertTrue(callable(getattr(module, attribute)))

    def test_inventory_exposes_no_pii_biometrics_or_free_text(self):
        inventory = self._inventory()
        forbidden_keys = {
            'cliente_id', 'usuario_id', 'nombre_usuario', 'email', 'notas',
            'texto', 'mensaje', 'hrv', 'frecuencia_cardiaca', 'sueno',
            'lesion', 'dolor', 'token', 'secret',
        }

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertNotIn(key.lower(), forbidden_keys)
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(inventory)

    def test_management_command_is_read_only_and_emits_same_json(self):
        from entrenos.management.commands.auditar_inventario_transicion_gym import Command

        parser = Command().create_parser('manage.py', 'auditar_inventario_transicion_gym')
        destinations = {action.dest for action in parser._actions}
        self.assertNotIn('apply', destinations)
        self.assertNotIn('cliente', destinations)

        output = StringIO()
        call_command('auditar_inventario_transicion_gym', stdout=output)
        self.assertEqual(json.loads(output.getvalue()), self._inventory())

    def test_week_two_runbook_uses_real_read_only_first_commands(self):
        runbook = (
            Path(__file__).resolve().parents[1]
            / 'docs'
            / 'fase0_inventario_vivo.md'
        ).read_text(encoding='utf-8')

        self.assertIn('31/08/2026–06/09/2026', runbook)
        self.assertIn('--cliente 2', runbook)
        self.assertIn('auditar_inventario_transicion_gym', runbook)
        self.assertIn('preparar_semana_gym', runbook)
        self.assertIn('--fecha-referencia 2026-08-30', runbook)
        self.assertIn('--solo-domingo', runbook)
        self.assertIn('materializar_contrato_semanal_gym', runbook)
        self.assertIn('--semana 2026-08-31', runbook)
        self.assertIn('cerrar_semana_gym', runbook)
        self.assertIn('auditar_semana_gym', runbook)
        self.assertIn('--desde 2026-08-31', runbook)
        self.assertIn('--hasta 2026-09-06', runbook)
        self.assertIn('dry-run', runbook.lower())
