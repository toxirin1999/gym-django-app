from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from core.services.physical_snapshot import build_physical_snapshot
from rehab.models import (
    EpisodioRehab,
    FaseProtocolo,
    ProtocoloRehab,
    RegistroDiarioRehab,
    SesionRehab,
)


AS_OF = date(2026, 8, 22)


class ActiveRehabSnapshotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("snapshot-rehab")
        self.cliente = Cliente.objects.get(user=self.user)
        self.protocol = ProtocoloRehab.objects.create(
            slug="knee-load", version=3, nombre="Rodilla", zona="rodilla",
            descripcion="clinica", fuente_referencia="fuente", criterios_alta={},
            advertencias="privado",
        )
        self.phase = FaseProtocolo.objects.create(
            protocolo=self.protocol, orden=2, slug="carga", nombre="Carga",
            objetivo="objetivo", duracion_minima_dias=3, duracion_tipica_dias=7,
            reglas_avance={}, reglas_retroceso={}, descripcion="privada",
        )

    def episode(self, **changes):
        protocol = changes.pop("protocolo", self.protocol)
        attrs = {
            "cliente": self.cliente,
            "protocolo": protocol,
            "protocolo_version": protocol.version,
            "fase_actual": self.phase if protocol == self.protocol else None,
            "lateralidad": "bilateral",
            "fecha_inicio": AS_OF - timedelta(days=5),
            "fase_actual_desde": AS_OF - timedelta(days=2),
            "estado": "ACTIVO",
            "dolor_basal_inicial": 4,
            "notas": "texto médico que no debe salir",
        }
        attrs.update(changes)
        return EpisodioRehab.objects.create(**attrs)

    def test_missing_is_explicit_and_exposes_capability(self):
        snapshot = build_physical_snapshot(self.cliente, AS_OF)

        self.assertIn("active_rehab_v1", snapshot["capabilities"])
        self.assertEqual(snapshot["capabilities"], sorted(set(snapshot["capabilities"])))
        self.assertEqual(snapshot["signals"]["active_rehab"], {
            "schema_version": 1,
            "status": "missing",
            "temporal_basis": "current_state_at_capture",
            "items": [],
            "provenance": {"source": "rehab.EpisodioRehab", "record_ids": []},
        })

    def test_active_episode_contract_is_factual_bilateral_and_without_notes(self):
        episode = self.episode()

        signal = build_physical_snapshot(self.cliente, AS_OF)["signals"]["active_rehab"]

        self.assertEqual(signal["status"], "available")
        self.assertEqual(signal["items"], [{
            "episode_id": episode.pk,
            "protocol_id": self.protocol.pk,
            "protocol_slug": "knee-load",
            "protocol_version": 3,
            "protocol_zone": "rodilla",
            "laterality": "bilateral",
            "started_on": "2026-08-17",
            "state": "ACTIVO",
            "phase_id": self.phase.pk,
            "phase_slug": "carga",
            "phase_order": 2,
            "phase_since": "2026-08-20",
            "observation_status": "active_unobserved",
            "latest_daily": None,
            "latest_session": None,
            "executive_capacity": {
                "can_derive_restrictions": False,
                "reason": "rehab_has_no_gym_risk_contract",
            },
        }])
        self.assertEqual(signal["provenance"]["record_ids"], [episode.pk])
        serialized = str(signal).lower()
        self.assertNotIn("texto médico", serialized)
        self.assertNotIn("privad", serialized)
        self.assertNotIn("dolor_basal_inicial", serialized)

    def test_only_current_active_episodes_and_nullable_phase_are_observed_in_order(self):
        def other_protocol(slug):
            return ProtocoloRehab.objects.create(
                slug=slug, version=1, nombre=slug, zona="rodilla",
                descripcion="", fuente_referencia="", criterios_alta={}, advertencias="",
            )

        phase_null = self.episode(
            fase_actual=None, fecha_inicio=AS_OF - timedelta(days=10),
            fase_actual_desde=AS_OF - timedelta(days=10),
        )
        second = self.episode(
            protocolo=other_protocol("second"), fecha_inicio=AS_OF - timedelta(days=1),
        )
        self.episode(
            protocolo=other_protocol("paused"), estado="PAUSADO",
            fecha_inicio=AS_OF - timedelta(days=20),
        )
        self.episode(
            protocolo=other_protocol("closed"), estado="ALTA",
            fecha_inicio=AS_OF - timedelta(days=20),
        )
        self.episode(
            protocolo=other_protocol("future"), fecha_inicio=AS_OF + timedelta(days=1),
        )

        items = build_physical_snapshot(self.cliente, AS_OF)["signals"]["active_rehab"]["items"]

        self.assertEqual([item["episode_id"] for item in items], [phase_null.pk, second.pk])
        self.assertIsNone(items[0]["phase_id"])
        self.assertIsNone(items[0]["phase_slug"])
        self.assertIsNone(items[0]["phase_order"])

    def test_latest_observations_never_use_future_and_zero_is_preserved(self):
        episode = self.episode()
        daily = RegistroDiarioRehab.objects.create(
            episodio=episode, fecha=AS_OF - timedelta(days=1), dolor_manana=0,
            rigidez_manana=0, bandera_roja=False, notas="secreto diario",
        )
        RegistroDiarioRehab.objects.create(
            episodio=episode, fecha=AS_OF + timedelta(days=1), dolor_manana=9,
            rigidez_manana=9, bandera_roja=True,
        )
        session = SesionRehab.objects.create(
            episodio=episode, fase=self.phase, fecha=AS_OF, estado="PARCIAL",
            dolor_durante=0, dolor_post_24h=None, notas="secreto sesión",
        )
        SesionRehab.objects.create(
            episodio=episode, fase=self.phase, fecha=AS_OF + timedelta(days=1),
            estado="COMPLETADA", dolor_durante=9, dolor_post_24h=9,
        )

        item = build_physical_snapshot(self.cliente, AS_OF)["signals"]["active_rehab"]["items"][0]

        self.assertEqual(item["observation_status"], "active_observed")
        self.assertEqual(item["latest_daily"], {
            "record_id": daily.pk, "date": "2026-08-21", "morning_pain": 0,
            "stiffness": 0, "red_flag": False,
        })
        self.assertEqual(item["latest_session"], {
            "session_id": session.pk, "date": "2026-08-22", "state": "PARCIAL",
            "pain_during": 0, "pain_post_24h": None,
        })
        self.assertNotIn("secreto", str(item).lower())

    def test_builder_is_read_only(self):
        episode = self.episode()
        before = {
            "episodes": EpisodioRehab.objects.count(),
            "daily": RegistroDiarioRehab.objects.count(),
            "sessions": SesionRehab.objects.count(),
            "phase": episode.fase_actual_id,
        }

        build_physical_snapshot(self.cliente, AS_OF)

        episode.refresh_from_db()
        self.assertEqual(before, {
            "episodes": EpisodioRehab.objects.count(),
            "daily": RegistroDiarioRehab.objects.count(),
            "sessions": SesionRehab.objects.count(),
            "phase": episode.fase_actual_id,
        })
