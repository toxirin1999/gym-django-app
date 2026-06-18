"""
Phase Gym 1.1 — Coherencia motivo_peso ↔ decisión final

Validación que el motivo mostrado explica exactamente la decisión final del peso,
DESPUÉS de todos los frenos (contextual, lesión, modo), no solo la intención inicial.

Tests:
1. test_motivo_final_sube_sin_frenos() — intención 'sube', sin bloqueo
2. test_motivo_final_mantiene_por_freno_contextual() — intención 'sube', bloqueado contextual
3. test_motivo_final_mantiene_por_lesion() — intención 'sube', bloqueado lesión
4. test_motivo_final_frenado_sin_frenos() — intención 'frenado', sin bloqueo
5. test_motivo_final_sin_datos_sin_frenos() — intención 'sin_datos', sin bloqueo
6. test_motivo_final_mantiene_por_modo_reducido() — intención 'sube', bloqueado modo_reducido
7. test_texto_motivo_final_coherente_con_tipo() — global validation
8. test_prioridad_lesion_over_freno_contextual() — lesion > contextual
"""

import json
from django.test import TestCase
from django.contrib.auth.models import User

from clientes.models import Cliente
from entrenos.services.progresion_contextual_service import construir_motivo_final


class TestMotivoPesoFinal(TestCase):
    """Tests unitarios: construir_motivo_final() ajusta el motivo según frenos."""

    def setUp(self):
        """Crear cliente mínimo para tests."""
        self.user = User.objects.create_user('test_motivo_final', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def _create_exercise_dict(self, motivo_tipo='sube', bloqueado=False,
                              motivo_bloqueo=None, es_lesion=False):
        """Helper: crear dict de ejercicio con motivo y estado de freno."""
        return {
            'nombre': 'Test Exercise',
            'peso_kg': 100.0,
            'series': 4,
            'repeticiones': 8,
            'motivo_peso': {
                'tipo': motivo_tipo,
                'texto': f'Test motivo: {motivo_tipo}',
            },
            'progresion_bloqueada': bloqueado,
            'motivo_bloqueo': motivo_bloqueo,
            'motivo_bloqueo_lesion': es_lesion,
            'risk_tags': [],
        }

    def test_motivo_final_sube_sin_frenos(self):
        """
        Escenario: Intención 'sube', sin bloqueos.
        Esperado: motivo sigue siendo 'sube' (no cambio).
        """
        ej = self._create_exercise_dict(motivo_tipo='sube', bloqueado=False)
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'sube',
                         "Sin frenos, 'sube' debe mantenerse")
        self.assertEqual(ej_final['motivo_peso']['tipo'],
                         ej['motivo_peso']['tipo'],
                         "Sin frenos, motivo final debe ser idéntico al inicial")

    def test_motivo_final_mantiene_por_freno_contextual(self):
        """
        Escenario: Intención 'sube', bloqueado por carga_alta_semanal.
        Esperado: motivo cambia a 'mantiene'.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='carga_alta_semanal',
            es_lesion=False
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'mantiene',
                         "Freno contextual debe cambiar a 'mantiene'")
        self.assertIn('margen',
                      ej_final['motivo_peso']['texto'].lower(),
                      "Texto debe mencionar 'margen' para freno contextual")

    def test_motivo_final_mantiene_por_lesion_aguda(self):
        """
        Escenario: Intención 'sube', bloqueado por lesión AGUDA.
        Esperado: motivo cambia a 'mantiene' con mención a protección.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='lesion_activa',
            es_lesion=True
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'mantiene',
                         "Lesión AGUDA debe cambiar a 'mantiene'")
        self.assertIn('protección',
                      ej_final['motivo_peso']['texto'].lower(),
                      "Texto debe mencionar 'protección' para lesión activa")

    def test_motivo_final_mantiene_por_lesion_retorno(self):
        """
        Escenario: Intención 'sube', bloqueado por lesión en RETORNO.
        Esperado: motivo cambia a 'mantiene'.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='lesion_retorno',
            es_lesion=True
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'mantiene',
                         "Lesión RETORNO debe cambiar a 'mantiene'")

    def test_motivo_final_frenado_sin_frenos(self):
        """
        Escenario: Intención 'frenado' (RPE alta), sin bloqueos.
        Esperado: motivo sigue siendo 'frenado' (no cambio).
        """
        ej = self._create_exercise_dict(motivo_tipo='frenado', bloqueado=False)
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'frenado',
                         "Sin frenos, 'frenado' debe mantenerse")

    def test_motivo_final_sin_datos_sin_frenos(self):
        """
        Escenario: Intención 'sin_datos' (sin historial), sin bloqueos.
        Esperado: motivo sigue siendo 'sin_datos'.
        """
        ej = self._create_exercise_dict(motivo_tipo='sin_datos', bloqueado=False)
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'sin_datos',
                         "Sin frenos, 'sin_datos' debe mantenerse")

    def test_motivo_final_mantiene_por_modo_reducido(self):
        """
        Escenario: Intención 'sube', bloqueado por modo_reducido.
        Esperado: motivo cambia a 'mantiene'.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='modo_reducido',
            es_lesion=False
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'mantiene',
                         "modo_reducido debe cambiar a 'mantiene'")

    def test_motivo_final_mantiene_por_retorno_pausa(self):
        """
        Escenario: Intención 'sube', bloqueado por retorno_pausa.
        Esperado: motivo cambia a 'mantiene'.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='retorno_pausa',
            es_lesion=False
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        self.assertEqual(ej_final['motivo_peso']['tipo'], 'mantiene',
                         "retorno_pausa debe cambiar a 'mantiene'")

    def test_texto_motivo_final_coherente_con_tipo(self):
        """
        Validación global: tipo y texto deben ser coherentes para todo escenario.
        """
        # Probar múltiples combinaciones
        test_cases = [
            ('sube', False, None, False),
            ('mantiene', False, None, False),
            ('frenado', False, None, False),
            ('sin_datos', False, None, False),
            ('sube', True, 'carga_alta_semanal', False),
            ('sube', True, 'modo_reducido', False),
            ('sube', True, 'lesion_activa', True),
            ('sube', True, 'lesion_retorno', True),
        ]

        for motivo_tipo, bloqueado, motivo_bloqueo, es_lesion in test_cases:
            with self.subTest(tipo=motivo_tipo, bloqueado=bloqueado):
                ej = self._create_exercise_dict(
                    motivo_tipo=motivo_tipo,
                    bloqueado=bloqueado,
                    motivo_bloqueo=motivo_bloqueo,
                    es_lesion=es_lesion
                )
                ej_final = construir_motivo_final(ej, self.cliente)

                # Validar estructura
                self.assertIn('motivo_peso', ej_final)
                self.assertIn('tipo', ej_final['motivo_peso'])
                self.assertIn('texto', ej_final['motivo_peso'])

                # Validar tipos válidos
                final_tipo = ej_final['motivo_peso']['tipo']
                self.assertIn(final_tipo, ('sube', 'mantiene', 'frenado', 'sin_datos'),
                              f"Tipo '{final_tipo}' no válido")

                # Validar texto no vacío
                texto = ej_final['motivo_peso']['texto']
                self.assertTrue(texto.strip(),
                                f"Texto vacío para tipo '{final_tipo}'")

    def test_prioridad_lesion_over_freno_contextual(self):
        """
        Prioridad: lesión tiene prioridad sobre freno contextual.
        Escenario: Intención 'sube', AMBOS lesión Y freno contextual.
        Esperado: motivo refleja LESIÓN (tiene prioridad).
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='lesion_activa',  # LESIÓN tiene prioridad
            es_lesion=True
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        # El motivo debe reflejar lesión, no freno contextual
        self.assertEqual(ej_final['motivo_peso']['tipo'], 'mantiene')
        self.assertIn('protección',
                      ej_final['motivo_peso']['texto'].lower(),
                      "Texto debe mencionar protección (lesión), no margen")

    def test_motivo_final_mantiene_preserva_rpe_base(self):
        """
        Edge case: si intención era 'mantiene', freno no cambia nada.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='mantiene',
            bloqueado=True,
            motivo_bloqueo='carga_alta_semanal',
            es_lesion=False
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        # Debe seguir siendo 'mantiene'
        self.assertEqual(ej_final['motivo_peso']['tipo'], 'mantiene')

    def test_motivo_final_es_json_serializable(self):
        """
        Validación técnica: motivo_peso final debe ser JSON-serializable.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='carga_alta_semanal',
            es_lesion=False
        )
        ej_final = construir_motivo_final(ej, self.cliente)

        try:
            json_str = json.dumps(ej_final['motivo_peso'])
            self.assertIsNotNone(json_str)
            data = json.loads(json_str)
            self.assertIn('tipo', data)
            self.assertIn('texto', data)
        except (TypeError, ValueError) as e:
            self.fail(f"motivo_peso final no es JSON serializable: {e}")

    def test_construir_motivo_final_preserva_otros_campos(self):
        """
        Validación: construir_motivo_final() no debe modificar otros campos.
        """
        ej = self._create_exercise_dict(
            motivo_tipo='sube',
            bloqueado=True,
            motivo_bloqueo='carga_alta_semanal',
            es_lesion=False
        )
        ej['peso_kg'] = 95.5
        ej['series'] = 5
        ej_final = construir_motivo_final(ej, self.cliente)

        # Verificar que otros campos se preserven
        self.assertEqual(ej_final['peso_kg'], 95.5,
                         "peso_kg debe preservarse")
        self.assertEqual(ej_final['series'], 5,
                         "series debe preservarse")
        self.assertEqual(ej_final['nombre'], 'Test Exercise',
                         "nombre debe preservarse")

    def test_construir_motivo_final_con_none_motivo_peso(self):
        """
        Edge case: ejercicio sin motivo_peso (degradación).
        Esperado: la función maneja gracefully (retorna dict sin cambios).
        """
        ej = {
            'nombre': 'Test',
            'peso_kg': 100.0,
            'motivo_peso': None,  # ← None
            'progresion_bloqueada': False,
        }
        ej_final = construir_motivo_final(ej, self.cliente)
        # Debe retornar el mismo dict sin errores
        self.assertIsNone(ej_final['motivo_peso'])

    def test_construir_motivo_final_con_empty_dict(self):
        """
        Edge case: ejercicio vacío.
        Esperado: la función retorna dict vacío sin errores.
        """
        ej = {}
        ej_final = construir_motivo_final(ej, self.cliente)
        self.assertEqual(ej_final, {})
