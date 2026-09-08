from datetime import date
import json
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from clientes.models import Cliente
from entrenos.models import SesionProgramada
from entrenos.views import ajax_obtener_entrenamientos_mes


class CalendarioSesionProgramadaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("calendario_sp", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.fecha = date(2026, 9, 8)
        self.plan = {
            "entrenos_por_fecha": {
                self.fecha.isoformat(): {
                    "nombre_rutina": "Día 1 - Fuerza",
                    "ejercicios": [],
                }
            }
        }

    def _get_mes(self):
        request = RequestFactory().get(
            "/entrenos/ajax/entrenamientos-mes/",
            {"año": self.fecha.year, "mes": self.fecha.month},
        )
        request.user = self.user
        with patch("entrenos.views.obtener_o_generar_plan", return_value=self.plan):
            return ajax_obtener_entrenamientos_mes(request, self.cliente.pk)

    def test_json_mensual_identifica_la_sesion_pendiente_renderizada(self):
        sesion = SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.fecha,
            nombre_sesion="  DÍA 1 - FUERZA  ",
        )

        payload = json.loads(self._get_mes().content)
        entrenamiento = payload["entrenamientos"][self.fecha.isoformat()]

        self.assertEqual(entrenamiento["sesion_programada_id"], sesion.pk)

    def test_json_mensual_no_inventa_id_si_no_hay_sesion_compatible(self):
        SesionProgramada.objects.create(
            cliente=self.cliente,
            fecha_prevista=self.fecha,
            nombre_sesion="Otra sesión",
        )

        payload = json.loads(self._get_mes().content)
        entrenamiento = payload["entrenamientos"][self.fecha.isoformat()]

        self.assertNotIn("sesion_programada_id", entrenamiento)

    def test_template_transporta_id_solo_con_entero_positivo_en_tarjeta_y_modal(self):
        template = Path(
            "entrenos/templates/entrenos/vista_plan_calendario.html"
        ).read_text(encoding="utf-8")

        self.assertIn("function buildBriefingParams(entrenamiento, fecha)", template)
        self.assertIn("Number.isInteger(sesionProgramadaId)", template)
        self.assertIn("sesionProgramadaId > 0", template)
        self.assertIn(
            "buildBriefingParams(entrenamiento, fecha).toString()",
            template,
        )
        self.assertIn(
            "buildBriefingParams(entrenamiento, fechaSeleccionada).toString()",
            template,
        )
