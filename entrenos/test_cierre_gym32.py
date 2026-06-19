"""
Tests para Phase Gym 3.2 — Cierre fiel y sin ruido.

Valida que el cierre post-sesión:
1. Renderiza todos los PRs reales (no duplicados)
2. Oculta cambios < 0.25 kg
3. No muestra cambios de variante (0↔carga) como regresión
4. Comunica si fue sesión ajustada (modo_reducido)
"""

from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, RecordPersonal
from rutinas.models import Rutina
from entrenos.services.cierre_entrenamiento_service import (
    construir_contexto_cierre,
    _cambios_relevantes,
    _resumen_sesion,
)


class TestCierreGym32(TestCase):
    """Tests para Phase Gym 3.2 — Cierre sin ruido."""

    def setUp(self):
        """Crear usuario y cliente para tests."""
        self.user = User.objects.create_user('test_gym32', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Test Rutina', programa=None)

    def test_registros_muestra_3_prs_sin_duplicados(self):
        """
        Test 1: Si hay 3 PRs reales (2 peso + 1 volumen del mismo ejercicio),
        REGISTROS debe mostrar los 3.
        """
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            volumen_total_kg=1000.0,
            modo_reducido=False
        )

        # Crear 3 PRs: 2 del mismo ejercicio (peso + volumen), 1 de otro
        RecordPersonal.objects.create(
            cliente=self.cliente,
            entreno=entreno,
            ejercicio_nombre='Jalón',
            tipo_record='peso_maximo',
            valor=40.0
        )
        RecordPersonal.objects.create(
            cliente=self.cliente,
            entreno=entreno,
            ejercicio_nombre='Curl',
            tipo_record='peso_maximo',
            valor=29.4
        )
        RecordPersonal.objects.create(
            cliente=self.cliente,
            entreno=entreno,
            ejercicio_nombre='Curl',
            tipo_record='volumen_total',
            valor=705.6
        )

        contexto = construir_contexto_cierre(self.cliente, entreno)
        prs = contexto['prs']

        # Debe haber 3 PRs, no 2 (sin .distinct())
        self.assertEqual(
            len(prs),
            3,
            "REGISTROS debe mostrar 3 PRs: 2 peso + 1 volumen (sin eliminar duplicados por ejercicio)"
        )

    def test_cambios_menores_025kg_ocultos(self):
        """
        Test 2: Cambios menores a 0.25 kg no deben aparecer en Cambios relevantes.
        """
        entreno_anterior = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 6, 10),
            volumen_total_kg=500.0
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_anterior,
            nombre_ejercicio='Curl',
            peso_kg=29.375,
            series=3,
            repeticiones=8,
            completado=True
        )

        entreno_hoy = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            volumen_total_kg=1000.0
        )
        ej_hoy = EjercicioRealizado.objects.create(
            entreno=entreno_hoy,
            nombre_ejercicio='Curl',
            peso_kg=29.40,  # +0.025 kg (redondeado a +0.02)
            series=3,
            repeticiones=8,
            completado=True
        )

        cambios = _cambios_relevantes(self.cliente, entreno_hoy, [ej_hoy])

        # No debe haber cambio +0.02 kg
        self.assertEqual(
            len(cambios),
            0,
            "Cambios menores a 0.25 kg no deben mostrarse (+0.02 kg oculto)"
        )

    def test_cambio_025kg_si_se_muestra(self):
        """
        Test 3: Cambios mayores o iguales a 0.25 kg sí deben mostrarse.
        """
        entreno_anterior = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 6, 10),
            volumen_total_kg=500.0
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_anterior,
            nombre_ejercicio='Curl',
            peso_kg=29.0,
            series=3,
            repeticiones=8,
            completado=True
        )

        entreno_hoy = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            volumen_total_kg=1000.0
        )
        ej_hoy = EjercicioRealizado.objects.create(
            entreno=entreno_hoy,
            nombre_ejercicio='Curl',
            peso_kg=29.25,  # +0.25 kg (exacto)
            series=3,
            repeticiones=8,
            completado=True
        )

        cambios = _cambios_relevantes(self.cliente, entreno_hoy, [ej_hoy])

        # Debe haber cambio +0.25 kg (en el límite, se muestra)
        self.assertEqual(len(cambios), 1, "Cambios >= 0.25 kg deben mostrarse")
        self.assertIn('+0.25', cambios[0]['detalle'])

    def test_cambio_variante_0_a_carga_no_muestra_regresion(self):
        """
        Test 4: Si ejercicio pasa de 0 kg a carga (o viceversa),
        no debe mostrarse como cambio de carga (es cambio de variante).
        """
        entreno_anterior = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 2, 10),
            volumen_total_kg=500.0
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_anterior,
            nombre_ejercicio='Dead Hang',
            peso_kg=35.0,  # Con lastre
            series=3,
            repeticiones=8,
            completado=True
        )

        entreno_hoy = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            volumen_total_kg=1000.0
        )
        ej_hoy = EjercicioRealizado.objects.create(
            entreno=entreno_hoy,
            nombre_ejercicio='Dead Hang',
            peso_kg=0.0,  # Sin lastre (peso corporal)
            series=3,
            repeticiones=8,
            completado=True
        )

        cambios = _cambios_relevantes(self.cliente, entreno_hoy, [ej_hoy])

        # No debe haber cambio -35 kg (es cambio de variante, no regresión)
        self.assertEqual(
            len(cambios),
            0,
            "Cambio de variante 0↔carga no debe mostrarse como regresión (-35 kg)"
        )

    def test_sesion_ajustada_aparece_en_resumen_modo_reducido(self):
        """
        Test 5: Si modo_reducido=True, resumen debe incluir "Sesión ajustada".
        """
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            volumen_total_kg=500.0,
            modo_reducido=True  # Sesión ajustada
        )

        resumen = _resumen_sesion(entreno, [])

        self.assertIsNotNone(
            resumen['sesion_tipo'],
            "Resumen debe incluir sesion_tipo cuando modo_reducido=True"
        )
        self.assertIn('Sesión ajustada', resumen['sesion_tipo'])

    def test_sesion_normal_sin_label(self):
        """
        Test 6: Si modo_reducido=False, no debe haber sesion_tipo.
        """
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            volumen_total_kg=1000.0,
            modo_reducido=False
        )

        resumen = _resumen_sesion(entreno, [])

        self.assertIsNone(
            resumen['sesion_tipo'],
            "Resumen no debe incluir sesion_tipo cuando modo_reducido=False"
        )

    def test_contexto_completo_coherente(self):
        """
        Test 7: Contexto completo coherente después de los 4 fixes.
        """
        # Crear sesión anterior para comparar
        entreno_anterior = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 5, 5),
            volumen_total_kg=800.0
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_anterior,
            nombre_ejercicio='Curl',
            peso_kg=29.375,
            series=3,
            completado=True
        )

        # Crear sesión hoy (modo_reducido + 1 PR)
        entreno_hoy = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date.today(),
            volumen_total_kg=1000.0,
            modo_reducido=True
        )
        ej_hoy = EjercicioRealizado.objects.create(
            entreno=entreno_hoy,
            nombre_ejercicio='Curl',
            peso_kg=29.40,  # +0.025 kg (oculto)
            series=3,
            completado=True
        )

        # Crear 1 PR
        RecordPersonal.objects.create(
            cliente=self.cliente,
            entreno=entreno_hoy,
            ejercicio_nombre='Curl',
            tipo_record='peso_maximo',
            valor=29.40
        )

        contexto = construir_contexto_cierre(self.cliente, entreno_hoy)

        # Validaciones
        self.assertEqual(len(contexto['prs']), 1, "Debe haber 1 PR")
        self.assertEqual(len(contexto['cambios_relevantes']), 0, "Cambio +0.02 kg oculto")
        self.assertIn('Sesión ajustada', contexto['resumen']['sesion_tipo'], "Modo reducido comunicado")
