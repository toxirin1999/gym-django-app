from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, SesionEntrenamiento
from entrenos.services.briefing_service import get_briefing_gym
from entrenos.services.cierre_entrenamiento_service import construir_contexto_cierre
from rutinas.models import Rutina


class IncidentesSecundariosAcceptanceTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="incidentes_secundarios")
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={"nombre": "Incidentes", "dias_disponibles": 4}
        )
        self.rutina = Rutina.objects.create(nombre="Rutina incidentes")

    @patch("entrenos.services.briefing_service.necesita_deload_gym", return_value=False)
    @patch(
        "entrenos.services.progresion_contextual_service.evaluar_permiso_local_ejercicio",
        return_value={"motivo": None, "mensaje": ""},
    )
    def test_tope_muestra_peso_real_y_solo_progresa_reps(self, _permiso, _deload):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today() - timedelta(days=1)
        )
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio="Prensa",
            peso_kg=180,
            series=3,
            repeticiones=10,
            rpe=5,
            es_tope_maquina=True,
        )

        briefing = get_briefing_gym(
            self.cliente, [{"nombre": "Prensa", "peso_recomendado_kg": 200}], date.today()
        )

        alerta = briefing["alertas_por_ejercicio"]["Prensa"][0]
        self.assertEqual(alerta["peso_kg"], 180)
        self.assertEqual(alerta["reps_objetivo"], 11)
        texto = " ".join(m["texto"] for m in briefing["mensajes"]).lower()
        self.assertNotIn("subir peso", texto)
        self.assertNotIn("200", alerta["texto"])
        self.assertIn("180", alerta["texto"])

    def test_semantica_bilateral_y_unilateral_de_mancuernas(self):
        from entrenos.services.peso_semantica_service import normalizar_semantica_carga

        bilateral = normalizar_semantica_carga(
            {"nombre": "Press Militar con Mancuernas", "peso_kg": 40}
        )
        unilateral = normalizar_semantica_carga(
            {"nombre": "Remo unilateral con mancuerna", "peso_kg": 30}
        )
        pesa_rusa = normalizar_semantica_carga(
            {"nombre": "Swing con pesa rusa", "peso_kg": 24}
        )

        self.assertEqual(bilateral["peso_formato"], "total_ambas")
        self.assertEqual(bilateral["peso_por_mancuerna_kg"], 20)
        self.assertEqual(unilateral["peso_formato"], "por_lado")
        self.assertNotIn("peso_por_mancuerna_kg", unilateral)
        self.assertEqual(unilateral["peso_kg"], 30)
        self.assertEqual(pesa_rusa["nombre"], "Swing con pesa rusa")
        self.assertEqual(pesa_rusa["peso_formato"], "total")

    @patch("entrenos.services.briefing_service.necesita_deload_gym", return_value=False)
    @patch(
        "entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion",
        return_value={"accion": "progresion_permitida", "motivo": "ok"},
    )
    def test_cierre_cuenta_ejercicios_persistidos_completados(self, _permiso, _deload):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(), numero_ejercicios=2
        )
        for nombre in ("Press", "Remo"):
            EjercicioRealizado.objects.create(entreno=entreno, nombre_ejercicio=nombre)
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio="Oculto incompleto", completado=False
        )
        SesionEntrenamiento.objects.update_or_create(
            entreno=entreno,
            defaults={"duracion_minutos": 30, "ejercicios_completados": 9},
        )

        contexto = construir_contexto_cierre(self.cliente, entreno)

        self.assertEqual(contexto["resumen"]["n_ejercicios"], 2)

    def test_feedback_final_es_sobrio_y_determinista(self):
        template = (
            Path(__file__).parent / "templates" / "entrenos" / "entrenamiento_activo.html"
        ).read_text(encoding="utf-8")
        for frase in ("Al límite", "adaptación máxima", "Sin cuartel"):
            self.assertNotIn(frase, template)
        self.assertIn("Sesión exigente registrada", template)
        selector = template.split("function elegirFrase", 1)[1].split("}", 1)[0]
        self.assertNotIn("Math.random", selector)

    def test_superficies_explican_la_semantica_del_peso(self):
        activo = (
            Path(__file__).parent / "templates" / "entrenos" / "entrenamiento_activo.html"
        ).read_text(encoding="utf-8")
        briefing = (
            Path(__file__).parent / "templates" / "entrenos" / "briefing_entrenamiento.html"
        ).read_text(encoding="utf-8")

        for template in (activo, briefing):
            self.assertIn("peso_formato", template)
            self.assertIn("total de ambas", template)
            self.assertIn("por lado", template)
