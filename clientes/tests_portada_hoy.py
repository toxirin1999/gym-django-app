from django.test import SimpleTestCase

from clientes.portada_hoy_service import construir_portada_hoy


class PortadaHoyBuilderTests(SimpleTestCase):
    def build(self, **overrides):
        data = {
            "estado_sistema": {
                "estado": "EN_MARGEN",
                "estado_label": "En margen",
                "texto": "El plan admite la sesión prevista.",
                "accion_label": "Empezar Gym",
                "accion_url": "/entrenos/empezar/",
                "modulo_principal": "gym",
                "modulo_operativo": True,
            },
            "decision_gym": {"estado": "normal"},
            "sesion_gym": {"nombre": "Fuerza A"},
            "hyrox_decision": {"puede_ejecutar_plan": True, "causa": "normal"},
            "sesion_hyrox": None,
            "hyrox_relevante": False,
            "hyrox_url": "/hyrox/registrar/",
            "recuperacion_url": "/hyrox/",
            "checkin_pendiente": False,
            "diario_pendiente": False,
            "diario_url": "/diario/",
            "diario_label": "Abrir el día",
            "senales": [],
            "aprendizajes": [],
        }
        data.update(overrides)
        return construir_portada_hoy(**data)

    def test_seguridad_gana_y_nunca_ofrece_inicio(self):
        portada = self.build(
            estado_sistema={
                "estado": "PROTEGIENDO", "estado_label": "Protegiendo",
                "texto": "Hoy protegemos la rodilla.",
                "accion_label": "Registrar recuperación", "accion_url": "/rehab/hoy/",
                "modulo_principal": "gym", "modulo_operativo": False,
            },
            checkin_pendiente=True,
        )
        self.assertEqual(portada["accion_principal"]["prioridad"], "P0")
        self.assertEqual(portada["accion_principal"]["url"], "/rehab/hoy/")
        self.assertNotIn("empezar", portada["accion_principal"]["label"].lower())

    def test_hyrox_bloqueado_es_p0_cuando_es_relevante(self):
        portada = self.build(
            sesion_gym=None,
            decision_gym={"estado": "descanso"},
            hyrox_relevante=True,
            sesion_hyrox={"titulo": "Intervals"},
            hyrox_decision={"puede_ejecutar_plan": False, "causa": "lesion"},
        )
        self.assertEqual(portada["accion_principal"]["prioridad"], "P0")
        self.assertEqual(portada["accion_principal"]["url"], "/hyrox/")

    def test_hyrox_bloqueado_no_desplaza_gym_viable_si_no_es_modulo_principal(self):
        portada = self.build(
            hyrox_relevante=True,
            sesion_hyrox={"titulo": "Intervals"},
            hyrox_decision={"puede_ejecutar_plan": False, "causa": "carga"},
        )
        self.assertEqual(portada["accion_principal"]["prioridad"], "P2")
        self.assertEqual(portada["sesion_dominante"]["modulo"], "gym")

    def test_checkin_pendiente_gana_si_hay_sesion_viable(self):
        portada = self.build(checkin_pendiente=True)
        self.assertEqual(portada["accion_principal"]["prioridad"], "P1")
        self.assertEqual(portada["accion_principal"]["tipo"], "modal_checkin")

    def test_solo_gym_usa_accion_del_estado_sistema(self):
        portada = self.build()
        self.assertEqual(portada["accion_principal"]["prioridad"], "P2")
        self.assertEqual(portada["sesion_dominante"]["modulo"], "gym")
        self.assertIsNone(portada["sesion_alternativa"])

    def test_solo_hyrox_viable_es_p3(self):
        portada = self.build(
            sesion_gym=None,
            decision_gym={"estado": "descanso"},
            hyrox_relevante=True,
            sesion_hyrox={"titulo": "Hyrox Engine"},
        )
        self.assertEqual(portada["accion_principal"]["prioridad"], "P3")
        self.assertEqual(portada["sesion_dominante"]["modulo"], "hyrox")

    def test_ambas_deja_gym_dominante_e_hyrox_como_alternativa(self):
        portada = self.build(
            hyrox_relevante=True,
            sesion_hyrox={"titulo": "Hyrox Engine"},
        )
        self.assertEqual(portada["sesion_dominante"]["modulo"], "gym")
        self.assertEqual(portada["sesion_alternativa"]["modulo"], "hyrox")
        self.assertNotIn("accion", portada["sesion_alternativa"])

    def test_diario_es_p4_solo_si_no_hay_sesion_ejecutable(self):
        portada = self.build(
            sesion_gym=None,
            decision_gym={"estado": "descanso"},
            diario_pendiente=True,
        )
        self.assertEqual(portada["accion_principal"]["prioridad"], "P4")
        self.assertEqual(portada["accion_principal"]["url"], "/diario/")
        self.assertEqual(portada["accion_principal"]["label"], "Abrir el día")

    def test_sin_sesion_ni_diario_no_inventa_accion(self):
        portada = self.build(sesion_gym=None, decision_gym={"estado": "descanso"})
        self.assertIsNone(portada["accion_principal"])

    def test_limita_senales_y_aprendizajes_a_tres(self):
        portada = self.build(
            senales=["s1", "s2", "s3", "s4"],
            aprendizajes=["a1", "a2", "a3", "a4"],
        )
        self.assertEqual(portada["senales"], ["s1", "s2", "s3"])
        self.assertEqual(portada["aprendizajes"], ["a1", "a2", "a3"])

    def test_normaliza_items_estructurados_y_descarta_vacios(self):
        portada = self.build(
            senales=[{"texto": "Carga elevada"}, {}, None],
            aprendizajes=[{"titulo": "Mejoró la técnica"}, {"sin_texto": True}],
        )
        self.assertEqual(portada["senales"], ["Carga elevada"])
        self.assertEqual(portada["aprendizajes"], ["Mejoró la técnica"])
