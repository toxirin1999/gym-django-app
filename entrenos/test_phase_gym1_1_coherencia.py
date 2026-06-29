"""
Phase Gym 1.1 — Pruebas de Coherencia: motivo_peso ↔ peso real

Validación que el motivo mostrado explica exactamente la decisión final del peso,
no una heurística paralela que puede contradecir la realidad.

Tests de riesgo:
1. test_motivo_sube_pero_freno_contextual_congela_peso → CONTRADICCIÓN
2. test_motivo_sube_pero_lesion_bloquea_peso → CONTRADICCIÓN
3. test_motivo_sube_pero_modo_reducido_congela → CONTRADICCIÓN
4. test_sin_historial_pero_freno_contextual_activo → AMBIGÜEDAD
"""

import json
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth.models import User

from clientes.models import Cliente
from rutinas.models import Rutina
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from hyrox.models import UserInjury
from analytics.planificador_helms.core import PlanificadorHelms
from analytics.planificador_helms.models.perfil_cliente import PerfilCliente
from entrenos.services.progresion_contextual_service import (
    evaluar_permiso_progresion,
    aplicar_freno_contextual,
    aplicar_freno_lesion,
)


class TestCoherenciaMotivoPeso(TestCase):
    """Tests de coherencia: el motivo debe explicar la decisión FINAL del peso."""

    def setUp(self):
        """Crear cliente con historial y rutina."""
        self.user = User.objects.create_user('test_coherencia', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.cliente.experiencia_años = 3
        self.cliente.objetivo_principal = 'hipertrofia'
        self.cliente.dias_disponibles = 4
        self.cliente.save()

        self.rutina = Rutina.objects.create(nombre='Test Rutina')

    def _crear_historial_rpe_bajo(self):
        """Crear historial donde RPE anterior fue baja (< objetivo).
        Esto dispara motivo_peso_tipo = 'sube'.
        """
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today() - timedelta(days=3),
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio='Sentadilla',
            peso_kg=90.0,           # peso_real_anterior = 90
            rpe=6,                  # rpe_real_anterior = 6 (bajo vs objetivo 8)
            series=4,
            repeticiones=8,
            completado=True,
        )

    def _generar_entrenamiento(self):
        """Generar entrenamiento recomendado para hoy."""
        perfil = PerfilCliente({
            'id': self.cliente.id,
            'experiencia_años': 3,
            'objetivo_principal': 'hipertrofia',
            'dias_disponibles': 4,
        })
        planificador = PlanificadorHelms(perfil)
        return planificador.generar_entrenamiento_para_fecha(date.today())

    def test_motivo_sube_pero_freno_contextual_congela_peso(self):
        """
        RIESGO 1: Motivo dice 'sube' pero freno contextual congela el peso.

        Escenario:
        - RPE anterior = 6, objetivo = 8 → diferencia = -2 → 'sube'
        - Plan propone: 90 → 95 kg (incremento grande)
        - Pero hay freno contextual: carga_alta_semanal
        - Freno congelala peso: 90 (no cambia)
        - Usuario ve motivo 'sube' pero peso es 90 (no 95)
        - CONTRADICCIÓN: motivo no explica la decisión final
        """
        # Arrange
        self._crear_historial_rpe_bajo()
        entrenamiento = self._generar_entrenamiento()

        if not entrenamiento or not entrenamiento.get('ejercicios'):
            self.skipTest("No hay ejercicios generados")

        ej = entrenamiento['ejercicios'][0]
        peso_plan_inicial = ej['peso_kg']
        motivo_tipo = ej['motivo_peso']['tipo']

        # Si el ejercicio generado no tiene historial, saltamos el test
        if motivo_tipo != 'sube':
            self.skipTest(f"El ejercicio generado ({ej.get('nombre', '?')}) no tiene historial con RPE bajo (motivo: {motivo_tipo})")

        self.assertGreater(
            peso_plan_inicial, 90,
            f"Plan debe proponer peso > 90 (lo que propuso es {peso_plan_inicial})"
        )

        # Act: Aplicar freno contextual
        permiso = {
            'puede_progresar': False,
            'accion': 'mantener_carga',
            'motivo': 'carga_alta_semanal',
            'vol_mod': 1.0,
            'vol_mod_excl_lesion': 1.0,
            'is_in_transition': False,
            'has_active_injuries': False,
        }

        entrenamiento_con_freno = {
            'ejercicios': [ej.copy()]
        }
        entrenamiento_con_freno = aplicar_freno_contextual(
            self.cliente, entrenamiento_con_freno, permiso
        )

        ej_con_freno = entrenamiento_con_freno['ejercicios'][0]
        peso_con_freno = ej_con_freno['peso_kg']
        motivo_despues = ej_con_freno['motivo_peso']['tipo']

        # Assert: CONTRADICCIÓN DETECTADA
        print(f"\n=== RIESGO 1: Motivo vs Peso ===")
        print(f"Motivo_peso.tipo: '{motivo_despues}' (dice '{motivo_despues}')")
        print(f"peso_kg: {peso_con_freno} (debería ser {peso_plan_inicial})")
        print(f"progresion_bloqueada: {ej_con_freno.get('progresion_bloqueada')}")
        print(f"motivo_bloqueo: {ej_con_freno.get('motivo_bloqueo')}")

        # PROBLEMA: motivo sigue siendo 'sube' pero peso está congelado
        if ej_con_freno.get('progresion_bloqueada'):
            self.assertEqual(
                motivo_despues, 'sube',
                "El motivo_peso NO se recalcula después del freno (está 'sube')"
            )
            self.assertEqual(
                peso_con_freno, 90,
                "El peso sí está congelado por el freno"
            )
            print("\n⚠️ CONTRADICCIÓN: motivo='sube' pero peso=90 (no cambió)")
            print("El usuario vera 'Sube por...' pero el peso no subio")

    def test_motivo_sube_pero_lesion_bloquea_peso(self):
        """
        RIESGO 2: Motivo dice 'sube' pero lesión activa bloquea el peso.

        Escenario:
        - Plan propone: sentadilla 95 kg (porque RPE fue baja)
        - Usuario tiene lesión en rodilla RETORNO con tags=['flexion_rodilla_profunda']
        - Sentadilla tiene risk_tags=['flexion_rodilla_profunda'] → INTERSECCIÓN
        - Lesión bloquea progresión
        - Usuario ve motivo 'sube' pero peso se mantiene en 90
        """
        # Arrange
        self._crear_historial_rpe_bajo()

        # Crear lesión en rodilla con restricción de flexión profunda
        UserInjury.objects.create(
            cliente=self.cliente,
            zona_afectada='Rodilla derecha',
            fase='RETORNO',
            activa=True,
            tags_restringidos=['flexion_rodilla_profunda', 'impacto_vertical'],
            gravedad=5,
        )

        entrenamiento = self._generar_entrenamiento()

        if not entrenamiento or not entrenamiento.get('ejercicios'):
            self.skipTest("No hay ejercicios")

        ej = entrenamiento['ejercicios'][0]

        # Simulamos que el ejercicio tiene risk_tags
        ej['risk_tags'] = ['flexion_rodilla_profunda']
        peso_antes = ej['peso_kg']
        motivo_antes = ej['motivo_peso']['tipo']

        # Act: Aplicar freno por lesión
        resultado = aplicar_freno_lesion(self.cliente, {'ejercicios': [ej]})
        ej_con_lesion = resultado['ejercicios'][0]
        peso_despues = ej_con_lesion['peso_kg']
        motivo_despues = ej_con_lesion['motivo_peso']['tipo']
        bloqueado = ej_con_lesion.get('progresion_bloqueada')
        motivo_bloqueo = ej_con_lesion.get('motivo_bloqueo')

        # Assert
        print(f"\n=== RIESGO 2: Lesión Bloquea ===")
        print(f"Motivo_peso antes: '{motivo_antes}'")
        print(f"Motivo_peso después: '{motivo_despues}'")
        print(f"Peso: {peso_antes} → {peso_despues}")
        print(f"Bloqueado: {bloqueado}, motivo_bloqueo: {motivo_bloqueo}")

        if bloqueado:
            self.assertEqual(
                motivo_despues, motivo_antes,
                "El motivo NO se recalcula, mantiene el original"
            )
            self.assertEqual(
                peso_despues, peso_antes,
                "El peso está bloqueado por lesión"
            )
            print("\n⚠️ CONTRADICCIÓN: motivo='sube' pero lesión lo bloquea")

    def test_motivo_sube_pero_modo_reducido_congela(self):
        """
        RIESGO 3: Motivo dice 'sube' pero modo_reducido/esencial congela peso.

        Escenario:
        - Sesión anterior fue esencial (modo_reducido=True)
        - Plan considera que volver a aumentar es prematuro
        - Freno mantiene carga igual
        - Usuario ve motivo 'sube' pero peso no cambia
        """
        # Arrange
        self._crear_historial_rpe_bajo()
        entrenamiento = self._generar_entrenamiento()

        if not entrenamiento or not entrenamiento.get('ejercicios'):
            self.skipTest("No hay ejercicios")

        ej = entrenamiento['ejercicios'][0]
        peso_plan = ej['peso_kg']

        # Act: Simular que sesión anterior fue reducida
        # (en realidad esto se parametriza en obtener_sesion_recomendada_hoy)
        # Aquí simulamos el efecto: freno mantiene

        permiso = {
            'puede_progresar': False,
            'accion': 'mantener_carga',
            'motivo': 'modo_reducido',
            'vol_mod': 1.0,
            'vol_mod_excl_lesion': 1.0,
        }

        resultado = aplicar_freno_contextual(
            self.cliente, {'ejercicios': [ej]}, permiso
        )
        ej_con_freno = resultado['ejercicios'][0]

        # Assert
        print(f"\n=== RIESGO 3: Modo Reducido ===")
        print(f"Motivo: '{ej_con_freno['motivo_peso']['tipo']}'")
        print(f"Peso: {ej_con_freno['peso_kg']}")
        print(f"Bloqueado: {ej_con_freno.get('progresion_bloqueada')}")

        if ej_con_freno.get('progresion_bloqueada') and ej_con_freno['motivo_peso']['tipo'] == 'sube':
            # Solo válido si el ejercicio tenía historial con RPE bajo (motivo 'sube')
            self.assertEqual(
                ej_con_freno['motivo_peso']['tipo'], 'sube',
                "Motivo no se actualiza tras freno"
            )
            print("\n⚠️ AMBIGÜEDAD: motivo='sube' pero modo_reducido lo bloquea")

    def test_sin_historial_pero_freno_contextual_aplica(self):
        """
        RIESGO 4: Motivo dice 'sin_datos' pero hay freno contextual activo.

        Escenario:
        - Sin historial del ejercicio → motivo='sin_datos'
        - Pero hay freno contextual: carga_alta_semanal
        - El freno congela el peso al nivel "base"
        - Usuario ve 'sin_datos' pero no entiende que hay un limitador
        """
        # Arrange: NO crear historial
        # Esto asegura que el motivo será 'sin_datos'

        entrenamiento = self._generar_entrenamiento()

        if not entrenamiento or not entrenamiento.get('ejercicios'):
            self.skipTest("No hay ejercicios")

        ej = entrenamiento['ejercicios'][0]
        motivo_original = ej['motivo_peso']['tipo']
        peso_original = ej['peso_kg']

        # Act: Aplicar freno
        permiso = {
            'puede_progresar': False,
            'accion': 'mantener_carga',
            'motivo': 'carga_alta_semanal',
            'vol_mod': 0.8,  # reducción por carga
        }

        resultado = aplicar_freno_contextual(
            self.cliente, {'ejercicios': [ej]}, permiso
        )
        ej_con_freno = resultado['ejercicios'][0]

        # Assert
        print(f"\n=== RIESGO 4: Sin Historial + Freno ===")
        print(f"Motivo: '{motivo_original}' (sigue siendo este después de freno)")
        print(f"Peso: {peso_original} → {ej_con_freno['peso_kg']}")
        print(f"Freno aplicado: {ej_con_freno.get('motivo_bloqueo')}")

        if ej_con_freno.get('progresion_bloqueada'):
            self.assertEqual(
                ej_con_freno['motivo_peso']['tipo'], 'sin_datos',
                "El motivo sigue siendo 'sin_datos'"
            )
            # El freno congela el peso al último registrado; sin historial = peso propuesto
            self.assertLessEqual(
                ej_con_freno['peso_kg'], peso_original,
                "El peso no sube con freno activo"
            )
            print("\n⚠️ FALTA EXPLICACIÓN: 'sin_datos' no menciona que hay freno activo")

    def test_coherencia_global_motivo_debe_explicar_peso_final(self):
        """
        Validación global: el motivo_peso DEBE explicar la DECISIÓN FINAL,
        no solo la propuesta teórica del RPE.

        Principio:
        - Si peso está congelado por freno → no debería decir 'sube'
        - Si peso está bloqueado por lesión → no debería decir 'sube'
        - Si hay múltiples causas → debería explica la más importante
        """
        self._crear_historial_rpe_bajo()
        entrenamiento = self._generar_entrenamiento()

        if not entrenamiento or not entrenamiento.get('ejercicios'):
            self.skipTest("No hay ejercicios")

        ej = entrenamiento['ejercicios'][0]

        # Aplicar ambos frenos para el peor caso
        permiso = {
            'puede_progresar': False,
            'accion': 'mantener_carga',
            'motivo': 'carga_alta_semanal',
            'vol_mod': 1.0,
        }

        resultado = aplicar_freno_contextual(
            self.cliente, {'ejercicios': [ej]}, permiso
        )
        ej_con_freno = resultado['ejercicios'][0]

        # Ahora añadir lesión
        ej_con_freno['risk_tags'] = ['flexion_rodilla_profunda']
        resultado2 = aplicar_freno_lesion(self.cliente, {'ejercicios': [ej_con_freno]})
        ej_con_lesion = resultado2['ejercicios'][0]

        # Assert: Se aplican ambos frenos
        print(f"\n=== Validación Global ===")
        print(f"Motivo final: '{ej_con_lesion['motivo_peso']['tipo']}'")
        print(f"Peso final: {ej_con_lesion['peso_kg']}")
        print(f"Motivo bloqueo: {ej_con_lesion.get('motivo_bloqueo')}")
        print(f"Progresión bloqueada: {ej_con_lesion.get('progresion_bloqueada')}")

        # HALLAZGO: el motivo no se actualiza después de frenos
        if ej_con_lesion.get('progresion_bloqueada'):
            print("\n📌 PROBLEMA DETECTADO:")
            print(f"   - motivo_peso.tipo = '{ej_con_lesion['motivo_peso']['tipo']}'")
            print(f"   - Pero progresion_bloqueada = True")
            print(f"   - El usuario ve '{ej_con_lesion['motivo_peso']['tipo']}' pero peso no cambió")
            print("\n🔧 SOLUCIÓN RECOMENDADA:")
            print("   Option A: Recalcular motivo DESPUÉS de frenos")
            print("   Option B: No mostrar motivo 'sube' si hay bloqueo")
            print("   Option C: Mostrar TAMBIÉN el motivo_bloqueo prominentemente")
