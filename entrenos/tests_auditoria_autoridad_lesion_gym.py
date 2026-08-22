"""Fase 6.5: auditoria pasiva de la doble autoridad de lesion Gym."""

import json
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.query import QuerySet
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionVersion, IntervencionMolestiaGym
from hyrox.models import UserInjury
from rehab.models import EpisodioRehab, FaseProtocolo, ProtocoloRehab, SesionRehab


class AuditoriaAutoridadLesionFixture(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("audit-lesion")
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro_user = User.objects.create_user("audit-lesion-otro")
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.fecha = date(2026, 8, 20)

    def physical(self, injuries=None):
        return {
            "schema_version": 1,
            "cliente_id": self.cliente.pk,
            "as_of_date": self.fecha.isoformat(),
            "signals": {
                "active_injuries": {
                    "status": "available" if injuries else "missing",
                    "items": injuries or [],
                }
            },
        }

    def injury(self, phase="AGUDA", tags=None, zone="Rodilla derecha"):
        return {
            "id": 7,
            "zone": zone,
            "phase": phase,
            "severity": 6,
            "restricted_tags": ["flexion_rodilla_profunda"] if tags is None else tags,
            "started_on": "2026-08-01",
            "resolved_on": None,
        }

    def version(self, *, physical="default", exercises="default", aviso=None,
                postura="empujar", version=1, vigente=True, cliente=None):
        if physical == "default":
            physical = self.physical([self.injury()])
        if exercises == "default":
            exercises = [{
                "nombre": "Sentadilla",
                "risk_tags": ["flexion_rodilla_profunda"],
            }]
        snapshot = {
            "physical_snapshot": physical,
            "entrenamiento": {"ejercicios": exercises},
        }
        if aviso is not None:
            snapshot["lesion_aviso"] = aviso
        return GymDecisionVersion.objects.create(
            cliente=cliente or self.cliente,
            fecha=self.fecha,
            version=version,
            decision_id=f"gym-lesion-{version}-{(cliente or self.cliente).pk}",
            origen=GymDecisionVersion.ORIGEN_MOTOR,
            vigente=vigente,
            fingerprint=f"fp-{version}-{(cliente or self.cliente).pk}",
            base_fingerprint="base",
            postura=postura,
            causa_principal="lesion" if postura == "proteger" else "",
            snapshot=snapshot,
        )

    def audit(self, **kwargs):
        from entrenos.services.auditoria_autoridad_lesion_gym_service import (
            auditar_autoridad_lesion_gym,
        )
        return auditar_autoridad_lesion_gym(
            cliente_id=self.cliente.pk,
            desde=self.fecha - timedelta(days=1),
            hasta=self.fecha + timedelta(days=1),
            limit=500,
            as_of=self.fecha,
            **kwargs,
        )


class AuthorityPropagationTests(AuditoriaAutoridadLesionFixture):
    def classification(self, **kwargs):
        result = self.audit(**kwargs)
        rows = [f for f in result["findings"] if f["plane"] == "authority_propagation"]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_missing_or_invalid_physical_snapshot_has_highest_priority(self):
        version = self.version(physical=None)
        version.snapshot.pop("physical_snapshot")
        version.save(update_fields=["snapshot"])
        self.assertEqual(
            self.classification()["classification"],
            "invalid_or_missing_physical_snapshot",
        )

    def test_injury_signal_contract_invalid(self):
        physical = self.physical()
        physical["signals"]["active_injuries"]["items"] = "not-a-list"
        self.version(physical=physical)
        self.assertEqual(
            self.classification()["classification"],
            "injury_snapshot_contract_invalid",
        )

    def test_missing_exercise_risk_tags_is_unverifiable(self):
        self.version(exercises=[{"nombre": "Sentadilla"}])
        self.assertEqual(
            self.classification()["classification"],
            "unverifiable_exercise_tags",
        )

    def test_blocking_injury_conflict_without_protection_is_not_enforced(self):
        self.version(postura="empujar")
        row = self.classification()
        self.assertEqual(row["classification"], "blocking_restriction_not_enforced")
        self.assertEqual(row["conflicting_exercises"], ["Sentadilla"])
        self.assertEqual(row["injury_ids"], [7])
        self.assertEqual(row["phases"], ["AGUDA"])
        self.assertEqual(row["zones"], ["Rodilla derecha"])
        self.assertEqual(row["restricted_tags"], ["flexion_rodilla_profunda"])
        self.assertTrue(row["exercise_tags_complete"])
        self.assertEqual(row["conflicting_tags"], ["flexion_rodilla_profunda"])
        self.assertEqual(row["actual"], {"postura": "empujar"})
        self.assertEqual(row["expected"], {"postura": "proteger"})

    def test_blocking_injury_protected_is_enforced(self):
        self.version(postura="proteger")
        self.assertEqual(self.classification()["classification"], "restriction_enforced")

    def test_return_conflict_requires_exposed_warning(self):
        self.version(physical=self.physical([self.injury(phase="RETORNO")]))
        row = self.classification()
        self.assertEqual(row["classification"], "return_warning_not_exposed")
        self.assertEqual(row["actual"], {"warning_exposed": False})
        self.assertEqual(row["expected"], {"warning_exposed": True})

    def test_return_conflict_with_warning_is_exposed(self):
        self.version(
            physical=self.physical([self.injury(phase="RETORNO")]),
            aviso={
                "fase": "RETORNO",
                "zona": "Rodilla derecha",
                "ejercicios_en_riesgo": ["Sentadilla"],
            },
        )
        self.assertEqual(self.classification()["classification"], "return_warning_exposed")

    def test_injury_without_session_conflict_is_neutral(self):
        self.version(exercises=[{"nombre": "Press", "risk_tags": ["hombro_inestable"]}])
        self.assertEqual(
            self.classification()["classification"], "injury_present_no_session_conflict"
        )

    def test_empty_restricted_tags_is_explicit(self):
        self.version(physical=self.physical([self.injury(tags=[])]), exercises=[])
        self.assertEqual(self.classification()["classification"], "injury_present_empty_tags")

    def test_no_injury_is_explicit(self):
        self.version(physical=self.physical([]), exercises=[])
        self.assertEqual(self.classification()["classification"], "no_injury_in_snapshot")

    def test_only_final_current_version_is_audited(self):
        self.version(version=1, vigente=True, postura="empujar")
        self.version(version=2, vigente=True, postura="proteger")
        row = self.classification()
        self.assertEqual(row["version"], 2)
        self.assertEqual(row["classification"], "restriction_enforced")

    @patch("django.core.cache.cache.set")
    @patch("core.services.physical_snapshot.build_physical_snapshot")
    @patch("entrenos.services.autoridad_diaria_gym_service.resolver_autoridad_diaria_gym")
    def test_audit_never_rebuilds_resolves_writes_or_caches(self, resolver, build, cache_set):
        version = self.version(postura="proteger")
        before = dict(version.snapshot)
        self.audit()
        resolver.assert_not_called()
        build.assert_not_called()
        cache_set.assert_not_called()
        version.refresh_from_db()
        self.assertEqual(version.snapshot, before)

    def test_audit_calls_neither_model_save_nor_queryset_update(self):
        self.version(postura="proteger")
        with patch.object(GymDecisionVersion, "save") as save, patch.object(
            QuerySet, "update"
        ) as update:
            self.audit()
        save.assert_not_called()
        update.assert_not_called()

    def test_other_client_versions_are_excluded(self):
        self.version(postura="proteger")
        self.version(cliente=self.otro, postura="empujar")
        rows = [
            row for row in self.audit()["findings"]
            if row["plane"] == "authority_propagation"
        ]
        self.assertEqual({row["cliente_id"] for row in rows}, {self.cliente.pk})


class SourceAlignmentTests(AuditoriaAutoridadLesionFixture):
    def setUp(self):
        super().setUp()
        self.protocol = ProtocoloRehab.objects.create(
            slug="rodilla", version=1, nombre="Rodilla", zona="rodilla",
            descripcion="x", fuente_referencia="x", advertencias="x",
        )
        self.phase = FaseProtocolo.objects.create(
            protocolo=self.protocol, orden=1, slug="inicio", nombre="Inicio",
            objetivo="x", duracion_minima_dias=1, duracion_tipica_dias=7,
            reglas_avance={}, reglas_retroceso={}, descripcion="x",
        )

    def episode(self, lateralidad="derecha", fecha_inicio=None, protocol=None):
        return EpisodioRehab.objects.create(
            cliente=self.cliente,
            protocolo=protocol or self.protocol,
            protocolo_version=1,
            lateralidad=lateralidad,
            fecha_inicio=fecha_inicio or self.fecha,
            fase_actual_desde=fecha_inicio or self.fecha,
            estado="ACTIVO",
            dolor_basal_inicial=3,
        )

    def live_injury(self, zone="Rodilla derecha", resolved_on=None):
        # bulk create avoids UserInjury's unrelated plan regeneration side effect.
        return UserInjury.objects.bulk_create([UserInjury(
            cliente=self.cliente,
            zona_afectada=zone,
            fase=UserInjury.Fase.SUB_AGUDA,
            fecha_inicio=self.fecha,
            fecha_resolucion=resolved_on,
            activa=True,
            tags_restringidos=["flexion_rodilla_profunda"],
        )])[0]

    def source_rows(self):
        rows = [f for f in self.audit()["findings"] if f["plane"] == "source_alignment"]
        return rows

    def episode_rows(self):
        return [row for row in self.source_rows() if row["entity"] == "rehab_episode"]

    def source_row(self):
        rows = self.episode_rows()
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_zone_and_laterality_match_is_strong(self):
        self.episode()
        self.live_injury()
        self.assertEqual(self.source_row()["classification"], "aligned")

    def test_zone_match_without_injury_laterality_is_probable(self):
        self.episode()
        self.live_injury("Rodilla")
        self.assertEqual(self.source_row()["classification"], "probable_alignment")

    def test_multiple_equally_valid_matches_are_ambiguous(self):
        self.episode()
        self.live_injury("Rodilla derecha")
        self.live_injury("Dolor de rodilla derecha")
        self.assertEqual(self.source_row()["classification"], "ambiguous_alignment")

    def test_no_sources_is_no_active_injury(self):
        self.assertEqual(self.source_rows(), [])

    def test_rehab_without_any_active_injury_is_explicit(self):
        self.episode()
        self.assertEqual(self.source_row()["classification"], "rehab_without_injury")

    def test_active_injury_without_episode_is_inventory_finding(self):
        injury = self.live_injury()
        row = self.source_rows()[0]
        self.assertEqual(row["entity"], "user_injury")
        self.assertEqual(row["entity_id"], injury.pk)
        self.assertEqual(row["classification"], "injury_without_rehab")

    def test_different_zones_are_unmatchable(self):
        self.episode()
        self.live_injury("Hombro izquierdo")
        self.assertEqual(self.source_row()["classification"], "unmatchable_zone")
        orphan = [row for row in self.source_rows() if row["entity"] == "user_injury"]
        self.assertEqual(orphan[0]["classification"], "injury_without_rehab")

    def test_two_independent_strong_matches_are_not_ambiguous(self):
        ankle = ProtocoloRehab.objects.create(
            slug="tobillo", version=1, nombre="Tobillo", zona="tobillo",
            descripcion="x", fuente_referencia="x", advertencias="x",
        )
        self.episode("derecha")
        self.episode("izquierda", protocol=ankle)
        self.live_injury("Rodilla der")
        self.live_injury("Tobillo izq")
        rows = self.episode_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["classification"] for row in rows], ["aligned", "aligned"])

    def test_bilateral_is_compatible_with_unilateral_alias(self):
        self.episode("bilateral")
        self.live_injury("Rodilla der")
        self.assertEqual(self.source_row()["classification"], "aligned")

    def test_opposite_sides_are_incompatible(self):
        self.episode("derecha")
        self.live_injury("Rodilla izq")
        self.assertEqual(self.source_row()["classification"], "unmatchable_zone")

    def test_future_episode_and_resolved_injury_are_excluded(self):
        self.episode(fecha_inicio=self.fecha + timedelta(days=1))
        self.live_injury(resolved_on=self.fecha)
        self.assertEqual(self.source_rows(), [])

    def test_latest_rehab_session_exposes_present_24h_response(self):
        episode = self.episode()
        self.live_injury()
        SesionRehab.objects.create(
            episodio=episode, fase=self.phase, fecha=self.fecha,
            estado="COMPLETADA", dolor_durante=3, dolor_post_24h=2,
        )
        evidence = self.source_row()["latest_rehab_session"]
        self.assertEqual(evidence, {
            "fecha": self.fecha.isoformat(), "estado": "COMPLETADA",
            "dolor_durante": 3, "dolor_post_24h": 2,
            "response_24h_status": "present",
        })

    def test_latest_rehab_session_marks_missing_and_absence_not_available(self):
        episode = self.episode()
        self.live_injury()
        self.assertEqual(
            self.source_row()["latest_rehab_session"]["response_24h_status"],
            "not_available",
        )
        SesionRehab.objects.create(
            episodio=episode, fase=self.phase, fecha=self.fecha,
            estado="PARCIAL", dolor_durante=4, dolor_post_24h=None,
        )
        self.assertEqual(
            self.source_row()["latest_rehab_session"]["response_24h_status"],
            "missing",
        )

    def test_interventions_are_inventory_only(self):
        IntervencionMolestiaGym.objects.create(
            cliente=self.cliente,
            zona_canonica="rodilla",
            risk_tags_snapshot=["flexion_rodilla_profunda"],
            original={"nombre": "Sentadilla"},
            original_normalizado="sentadilla",
            alternativa={"nombre": "Prensa"},
            alternativa_normalizada="prensa",
            iniciada_en="2026-08-20T10:00:00Z",
            vence_en="2026-08-27T10:00:00Z",
        )
        summary = self.audit()["summary"]
        self.assertEqual(summary["intervention_inventory"]["total"], 1)
        self.assertEqual(summary["intervention_inventory"]["by_status"], {"activa": 1})


class AuditoriaAutoridadLesionCommandTests(AuditoriaAutoridadLesionFixture):
    def test_jsonl_is_deterministic_and_read_only(self):
        self.version(postura="proteger")
        out = StringIO()
        call_command(
            "auditar_autoridad_lesion_gym",
            cliente=self.cliente.pk,
            desde="2026-08-19",
            hasta="2026-08-21",
            limit=10,
            stdout=out,
        )
        records = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(records[-1]["tipo_registro"], "resumen")
        self.assertTrue(records[-1]["solo_lectura"])
        self.assertNotIn("--apply", out.getvalue())

    def test_command_has_no_apply_option(self):
        with self.assertRaises(TypeError):
            call_command(
                "auditar_autoridad_lesion_gym",
                cliente=self.cliente.pk,
                apply=True,
            )

    def test_invalid_range_and_limit_are_rejected(self):
        with self.assertRaises(CommandError):
            call_command(
                "auditar_autoridad_lesion_gym", cliente=self.cliente.pk,
                desde="2026-08-22", hasta="2026-08-21",
            )
        with self.assertRaises(CommandError):
            call_command("auditar_autoridad_lesion_gym", cliente=self.cliente.pk, limit=0)
