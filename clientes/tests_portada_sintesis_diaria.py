from django.template.loader import get_template
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from types import SimpleNamespace
from unittest.mock import patch

from clientes.portada_hoy_service import construir_portada_hoy
from clientes.views import _seleccionar_portada_joi_texto


class PortadaHoyServiceTests(SimpleTestCase):
    def _build(self, **overrides):
        data = {
            "estado_sistema": {"estado": "SILENCIO", "estado_label": "Silencio", "texto": "No hay nada que forzar ahora.", "modulo_operativo": False},
            "decision_gym": {"estado": "descanso"},
            "sesion_gym": {"nombre": "Día de Descanso"},
            "hyrox_decision": {}, "sesion_hyrox": None,
            "hyrox_relevante": False, "hyrox_url": None,
            "recuperacion_url": "/hyrox/", "checkin_pendiente": True,
            "diario_pendiente": True, "diario_url": "/diario/",
            "senales": ["RPE estable", "Energía subiendo", "Descanso programado", "No debe verse"],
            "aprendizajes": [
                {"texto": "El RPE bajó manteniendo la carga", "consecuencia": "El plan conservará el volumen"},
                "Segundo aprendizaje que no debe verse",
            ],
        }
        data.update(overrides)
        return construir_portada_hoy(**data)

    def test_descanso_se_traduce_a_lenguaje_humano_sin_estado_tecnico(self):
        portada = self._build()
        self.assertEqual(portada["decision"]["titulo"], "Descanso programado")
        self.assertIn("distribución del plan", portada["decision"]["frase"])
        self.assertNotIn("SILENCIO", str(portada))
        self.assertIsNone(portada["accion_principal"])
        self.assertEqual(len(portada["senales"]), 3)

    def test_aprendizaje_visible_es_unico_y_expresa_consecuencia(self):
        portada = self._build()
        self.assertEqual(len(portada["aprendizajes"]), 1)
        self.assertIn("El plan conservará el volumen", portada["aprendizajes"][0])

    def test_sesion_ejecutable_tiene_una_unica_accion(self):
        portada = self._build(
            estado_sistema={"estado": "EN_MARGEN", "estado_label": "En margen", "texto": "Puedes ejecutar el plan.", "modulo_operativo": True, "accion_label": "Empezar sesión", "accion_url": "/entrenos/hoy/"},
            decision_gym={"estado": "entrenar"},
            sesion_gym={"nombre": "Tren inferior", "duracion_estimada": 55},
            checkin_pendiente=False,
        )
        self.assertEqual(portada["decision"]["titulo"], "Tren inferior")
        self.assertEqual(portada["accion_principal"]["url"], "/entrenos/hoy/")

    def test_sesion_hyrox_real_admite_objeto_de_modelo(self):
        portada = self._build(
            sesion_gym=None,
            decision_gym={"estado": "entrenar"},
            hyrox_relevante=True,
            sesion_hyrox=SimpleNamespace(titulo="Tempo Hyrox"),
            hyrox_decision={"puede_ejecutar_plan": True},
            checkin_pendiente=False,
        )
        self.assertEqual(portada["decision"]["titulo"], "Tempo Hyrox")


class PortadaSintesisTemplateTests(SimpleTestCase):
    def _render(self, **context):
        base = {
            "cliente": SimpleNamespace(id=7),
            "portada_hoy": {"aprendizajes": []},
            "analisis_semanal": {},
            "portada_diario_url": "/diario/",
            "portada_diario_label": "Abrir diario",
        }
        base.update(context)
        return get_template("clientes/mockup_demo.html").render(base)

    def test_jerarquia_editorial_y_ausencias(self):
        source = get_template("clientes/mockup_demo.html").template.source
        for marker in ("data-daily-header", "data-today-card", "data-diary-card", "data-plan-learning", "data-week-summary", "data-secondary-tools"):
            self.assertEqual(source.count(marker), 1, marker)
        self.assertNotIn("rb-bib-name", source)
        self.assertNotIn("modeSwitcherRb", source)
        self.assertNotIn("rbGymContent", source)
        self.assertNotIn("rbHyroxContent", source)

    def test_accesos_secundarios_no_compiten_en_cabecera(self):
        source = get_template("clientes/mockup_demo.html").template.source
        header = source[source.index("data-daily-header"):source.index("</header>")]
        tools = source[source.index("data-secondary-tools"):]
        for label in ("Mi cuerpo", "Strava", "Rehab", "Gym", "Hyrox"):
            self.assertNotIn(label, header)
            self.assertIn(label, tools)

    def test_mobile_no_desborda_y_objetivos_tactiles(self):
        source = get_template("clientes/mockup_demo.html").template.source
        self.assertIn("overflow-x: hidden", source)
        self.assertIn("min-width: 0", source)
        self.assertIn("min-height: 44px", source)

    def test_checkin_ofrece_energia_del_uno_al_diez(self):
        source = get_template("clientes/mockup_demo.html").template.source
        for valor in range(1, 11):
            self.assertIn(f'data-energy="{valor}"', source)

    def test_semana_usa_sesiones_completadas_no_total_historico(self):
        source = get_template("clientes/mockup_demo.html").template.source
        week = source[source.index("data-week-summary"):source.index("</section>", source.index("data-week-summary"))]
        self.assertIn("analisis_semanal.sesiones_completadas", week)
        self.assertNotIn("entrenos_count", week)
        self.assertIn(">Sesiones<", week)

    def test_conserva_mensajes_y_recuperacion_de_entreno_operativos(self):
        source = get_template("clientes/mockup_demo.html").template.source
        self.assertIn("{% if messages %}", source)
        self.assertIn("data-django-message", source)
        self.assertIn("data-workout-recovery", source)
        self.assertIn("entreno_activo_", source)
        self.assertIn("localStorage.removeItem", source)
        self.assertIn("86400000", source)

    def test_recupera_memoria_del_plan_en_seccion_propia_y_colapsada(self):
        source = get_template("clientes/mockup_demo.html").template.source
        self.assertEqual(source.count("data-plan-memory class="), 1)
        memory = source[source.index("data-plan-memory"):source.index("data-secondary-tools")]
        self.assertIn("Lo que el plan está aprendiendo", memory)
        self.assertNotIn(" open", memory.split(">", 1)[0])
        self.assertNotIn("Herramientas y evolución", memory)

    def test_memoria_recupera_contextos_reales_sin_duplicar_aprendizaje_principal(self):
        source = get_template("clientes/mockup_demo.html").template.source
        memory = source[source.index("data-plan-memory"):source.index("data-secondary-tools")]
        for context_name in (
            "alertas_sistema",
            "patron_multisemanal",
            "sugerencia_activa",
            "evaluacion_intervencion",
            "intervencion_distribucion",
            "evaluacion_distribucion",
            "distribucion_semanal",
            "preferencias_activas",
            "calendario_plan",
            "resumen_semanal_gym",
            "resumen_semanal_hyrox",
        ):
            self.assertIn(context_name, memory)
        self.assertIn("clientes:memoria_entrenador", memory)
        self.assertNotIn("portada_hoy.aprendizajes", memory)

    def test_memoria_degrada_con_estado_vacio_honesto(self):
        source = get_template("clientes/mockup_demo.html").template.source
        memory = source[source.index("data-plan-memory"):source.index("data-secondary-tools")]
        self.assertIn("data-plan-memory-empty", memory)
        self.assertIn("Aún no hay observaciones adicionales", memory)

    def test_candidata_preferencia_renderiza_evidencia_y_contrato_operativo(self):
        html = self._render(candidata_preferencia={
            "evidencia_count": 4,
            "descripcion": "rindes mejor separando tren inferior",
            "tipo_preferencia": "distribucion",
            "tipo_intervencion": "separar_inferior",
        })
        self.assertIn("En 4 pruebas", html)
        self.assertIn("rindes mejor separando tren inferior", html)
        self.assertIn(reverse("clientes:convertir_preferencia"), html)
        self.assertIn('name="tipo_preferencia" value="distribucion"', html)
        self.assertIn('name="tipo_intervencion" value="separar_inferior"', html)
        self.assertIn("Seguir probando", html)

    def test_continuidad_intervencion_renderiza_repetir_e_ignorar_con_campos(self):
        html = self._render(
            evaluacion_intervencion={"lectura": "El ajuste redujo el RPE."},
            recomendacion_continuidad={
                "accion": "repetir", "texto": "Conviene otra semana.",
                "tipo_intervencion": "reducir_volumen",
            },
        )
        self.assertIn("Conviene otra semana.", html)
        self.assertIn(reverse("clientes:repetir_intervencion"), html)
        self.assertIn(reverse("clientes:ignorar_recomendacion"), html)
        self.assertEqual(html.count('name="tipo_intervencion" value="reducir_volumen"'), 2)
        self.assertIn("Repetir esta semana", html)

    def test_continuidad_intervencion_profundizar_no_inventa_endpoint_de_repeticion(self):
        html = self._render(
            evaluacion_intervencion={"lectura": "Hay señal parcial."},
            recomendacion_continuidad={
                "accion": "profundizar", "texto": "Hace falta más evidencia.",
                "tipo_intervencion": "ajuste_parcial",
            },
        )
        self.assertIn("Profundizar", html)
        self.assertNotIn(reverse("clientes:repetir_intervencion"), html)
        self.assertIn(reverse("clientes:ignorar_recomendacion"), html)

    def test_continuidad_distribucion_renderiza_acciones_y_tipo_exacto(self):
        html = self._render(
            evaluacion_distribucion={"lectura": "La distribución fue favorable."},
            continuidad_distribucion={"texto": "Repite para confirmar.", "tipo_intervencion": "espaciar_inferior"},
        )
        self.assertIn("Repite para confirmar.", html)
        self.assertIn(reverse("clientes:repetir_prueba_distribucion"), html)
        self.assertIn(reverse("clientes:ignorar_continuidad_distribucion"), html)
        self.assertEqual(html.count('name="tipo_intervencion" value="espaciar_inferior"'), 2)
        self.assertIn("Repetir 2 semanas", html)

    def test_sugerencia_diario_pendiente_vive_en_diario_y_usa_endpoints_reales(self):
        source = get_template("clientes/mockup_demo.html").template.source
        diary = source[source.index("data-diary-card"):source.index("data-plan-learning")]
        self.assertIn("sugerencia_diario", diary)
        html = self._render(sugerencia_diario=SimpleNamespace(id=31, estado="pendiente", texto="Vigila la tensión lumbar."))
        self.assertIn("Vigila la tensión lumbar.", html)
        self.assertIn(reverse("clientes:aceptar_sugerencia", args=[31]), html)
        self.assertIn(reverse("clientes:ignorar_sugerencia", args=[31]), html)
        self.assertIn("Vigilar 14 días", html)

    def test_revision_progreso_solo_renderiza_datos_reales_y_enlace_aplicable(self):
        vacio = self._render()
        self.assertNotIn("Revisión de progreso", vacio)
        html = self._render(revision_progreso=[{"icono": "↗", "texto": "La cintura bajó 2 cm.", "color": "positivo"}])
        self.assertIn("Revisión de progreso", html)
        self.assertIn("La cintura bajó 2 cm.", html)
        self.assertIn(reverse("clientes:mi_cuerpo", args=[7]), html)

    def test_ultimas_sesiones_es_plegable_y_respeta_la_jerarquia(self):
        source = get_template("clientes/mockup_demo.html").template.source
        self.assertEqual(source.count("data-recent-sessions"), 1)
        self.assertLess(source.index("data-plan-memory"), source.index("data-recent-sessions"))
        self.assertLess(source.index("data-recent-sessions"), source.index("data-secondary-tools"))
        recent = source[source.index("data-recent-sessions"):source.index("data-secondary-tools")]
        self.assertIn("Últimas sesiones", recent)
        self.assertNotIn(" open", recent.split(">", 1)[0])

    def test_ultimas_sesiones_muestra_datos_reales_y_fallbacks(self):
        source = get_template("clientes/mockup_demo.html").template.source
        recent = source[source.index("data-recent-sessions"):source.index("data-secondary-tools")]
        for contract in (
            "actividades_recientes_focus",
            "act.titulo",
            "act.entreno_gym.rutina.nombre",
            "act.get_tipo_display",
            "act.fecha_efectiva",
            "act.fecha",
            "act.rpe_medio",
            "act.duracion_minutos",
            "act.es_anticipada",
        ):
            self.assertIn(contract, recent)
        self.assertIn("Fecha real", recent)
        self.assertIn("Planificada", recent)
        self.assertIn("Anticipado", recent)

    def test_ultimas_sesiones_se_oculta_si_no_hay_actividad(self):
        source = get_template("clientes/mockup_demo.html").template.source
        marker = source.index("data-recent-sessions")
        opening_guard = source.rfind("{% if actividades_recientes_focus %}", 0, marker)
        self.assertNotEqual(opening_guard, -1)
        self.assertLess(opening_guard, source.index("<details data-recent-sessions"))
        self.assertIn("{% endif %}", source[source.index("data-recent-sessions"):source.index("data-secondary-tools")])

    def test_ultimas_sesiones_tiene_layout_movil_sin_desbordes(self):
        source = get_template("clientes/mockup_demo.html").template.source
        self.assertIn(".recent-session{min-width:0", source)
        self.assertIn("overflow-wrap:anywhere", source)
        self.assertIn("grid-template-columns:minmax(0,1fr) auto", source)


class PortadaJoiSelectionTests(SimpleTestCase):
    class Mensaje:
        def __init__(self, mensaje):
            self.mensaje = mensaje

    def test_dia_normal_prioriza_mensaje_joi_y_muestra_una_fuente(self):
        self.assertEqual(
            _seleccionar_portada_joi_texto(
                self.Mensaje("Mensaje vivo"), "Capa corta", tipo_dia="sesion"
            ),
            "Mensaje vivo",
        )


class PortadaJoiViewIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("portada-joi-source", password="x")
        self.client.force_login(self.user)

    @patch("clientes.views._seleccionar_portada_joi_texto", return_value="Texto seleccionado")
    @patch("joi.context_processors.get_mensaje_portada")
    def test_view_entrega_mensaje_canonico_real_al_selector(self, get_mensaje, selector):
        mensaje = object()
        get_mensaje.return_value = mensaje

        response = self.client.get(reverse("clientes:mockup_demo"))

        self.assertEqual(response.status_code, 200)
        self.assertIs(selector.call_args.args[0], mensaje)
        self.assertContains(response, "Texto seleccionado")

    def test_descanso_descarta_voz_contradictoria_sin_inventar_alternativa(self):
        self.assertEqual(
            _seleccionar_portada_joi_texto(
                PortadaJoiSelectionTests.Mensaje("Hoy puedes apretar"), "Sigue avanzando", tipo_dia="descanso"
            ),
            "",
        )

    def test_descanso_acepta_solo_texto_joi_semanticamente_coherente(self):
        self.assertEqual(
            _seleccionar_portada_joi_texto(
                PortadaJoiSelectionTests.Mensaje("La recuperación también pertenece al plan"),
                "Capa corta",
                tipo_dia="proteccion",
            ),
            "La recuperación también pertenece al plan",
        )
