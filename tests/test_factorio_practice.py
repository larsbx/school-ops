import json
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.factorio_practice import MAX_RECEIPT_BYTES, inspect_receipt
from tools import verify_factorio_integration as integration


def completion(activity_id, mod_version):
    return {
        "schema": "schoolops.factorio.practice.v1",
        "activity_id": activity_id,
        "mod_version": mod_version,
        "result": "completed",
    }


SMELTING = completion("L-FACTORIO-SMELTING-01", "0.2.0")
CURRENT_SMELTING = completion("L-FACTORIO-SMELTING-01", "0.3.0")
RATIO = completion("L-FACTORIO-RATIO-01", "0.3.0")
SUPPLY = completion("L-FACTORIO-SUPPLY-01", "0.3.0")


class FactorioPracticeTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "receipt.json"

    def test_registered_receipts_return_only_draft_practice_claims(self):
        cases = (
            (SMELTING, "R-FACTORIO-001", "curriculum/pilots/factorio/README.md"),
            (CURRENT_SMELTING, "R-FACTORIO-001", "curriculum/pilots/factorio/README.md"),
            (RATIO, "R-FACTORIO-002", "curriculum/pilots/factorio/ratio-loading-bay/README.md"),
            (SUPPLY, "R-FACTORIO-003", "curriculum/pilots/factorio/factory-supply-order/README.md"),
        )
        for receipt, resource_id, record in cases:
            with self.subTest(activity=receipt["activity_id"]):
                self.path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
                self.assertEqual(inspect_receipt(self.path), {
                    "schoolops_record": record,
                    "resource_id": resource_id,
                    "activity_id": receipt["activity_id"],
                    "material_status": "draft",
                    "evidence": "unverified_practice_completion_claim",
                })

    def test_receipt_fields_are_exact_for_each_activity(self):
        for receipt in (SMELTING, CURRENT_SMELTING, RATIO, SUPPLY):
            missing_result = receipt.copy()
            del missing_result["result"]
            invalid = {
                "unregistered activity/version pair": completion("L-FACTORIO-RATIO-01", "0.2.0"),
                "unsupported prior version": dict(receipt, mod_version="0.1.0"),
                "arbitrary version": dict(receipt, mod_version="9.9.9"),
                "unknown activity": dict(receipt, activity_id="L-FACTORIO-UNKNOWN-01"),
                "learner identity": dict(receipt, learner_id="unknown"),
                "player name": dict(receipt, player_name="Example"),
                "wrong schema": dict(receipt, schema="schoolops.factorio.practice.v2"),
                "wrong result": dict(receipt, result="started"),
                "wrong value type": dict(receipt, mod_version=3),
                "missing result": missing_result,
            }
            for reason, payload in invalid.items():
                with self.subTest(activity=receipt["activity_id"], reason=reason):
                    self.path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        inspect_receipt(self.path)

    def test_duplicate_fields_are_rejected_even_with_matching_values(self):
        for receipt in (SMELTING, CURRENT_SMELTING, RATIO, SUPPLY):
            for field, value in receipt.items():
                with self.subTest(activity=receipt["activity_id"], field=field):
                    duplicate = json.dumps(receipt)[:-1] + ", " + json.dumps({field: value})[1:]
                    self.path.write_text(duplicate, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                        inspect_receipt(self.path)

    def test_receipt_byte_limit(self):
        for receipt in (SMELTING, CURRENT_SMELTING, RATIO, SUPPLY):
            with self.subTest(activity=receipt["activity_id"]):
                at_limit = json.dumps(receipt).encode("utf-8").ljust(MAX_RECEIPT_BYTES)
                self.path.write_bytes(at_limit)
                self.assertEqual(inspect_receipt(self.path)["activity_id"], receipt["activity_id"])
                self.path.write_bytes(at_limit + b" ")
                with self.assertRaisesRegex(ValueError, "too large"):
                    inspect_receipt(self.path)

    def test_malformed_and_non_object_receipts_are_rejected(self):
        for payload in (b"", b"{", b"null", b"[]", b'"text"', b"42", b"\xff",
                        json.dumps(RATIO).encode("utf-8") + b" {}"):
            with self.subTest(payload=payload):
                self.path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    inspect_receipt(self.path)

    def test_factory_supply_catalog_is_draft_and_not_world_proof(self):
        record = Path(__file__).resolve().parents[1] / (
            "curriculum/pilots/factorio/factory-supply-order/activity.json")
        metadata = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(set(metadata), {"status", "resource_id", "expected_receipt"})
        self.assertEqual(metadata["status"], "draft")
        self.assertEqual(metadata["expected_receipt"], SUPPLY)
        self.path.write_text(json.dumps(SUPPLY), encoding="utf-8")
        result = inspect_receipt(self.path)
        self.assertEqual(result["evidence"], "unverified_practice_completion_claim")
        self.assertEqual(result["material_status"], "draft")
        self.assertEqual(result["resource_id"], "R-FACTORIO-003")

    def test_cli_rejects_an_identity_field_without_echoing_its_value(self):
        self.path.write_text(json.dumps(dict(RATIO, learner_id="synthetic-private-id")),
                             encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "tools/factorio_practice.py"
        result = subprocess.run([sys.executable, str(script), str(self.path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("Invalid or unreadable practice receipt", result.stderr)
        self.assertNotIn("synthetic-private-id", result.stderr)


class FactorioIntegrationConsumerTest(unittest.TestCase):
    """Synthetic report-consumer tests; these do not run or simulate the game."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.checkout = self.root / "factorio"
        self.producer = self.root / "producer"
        self.checkout.mkdir()
        self.producer.mkdir()
        for relative in integration.CORE_SOURCE_PATHS:
            path = self.checkout / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic report-consumer fixture\n", encoding="utf-8")
        self.hashes = {relative: integration.sha256(self.checkout / relative)
                       for relative in sorted(integration.CORE_SOURCE_PATHS)}
        self.lock = {
            "schema": "schoolops.factorio.integration-lock.v1",
            "repository": "larsbx/factorio-mods", "revision": None,
            "source_status": "pending_publication_unverified",
            "factorio_version": "2.0.77", "mod_version": "0.3.0",
            "factorio_archive_sha256": integration.FACTORIO_ARCHIVE_SHA256,
            "producer_schema": "schoolops.factorio.acceptance.v1", "source_hashes": {},
        }
        self.lock_path = self.root / "lock.json"
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        self.identity = {"revision": None, "dirty": None, "mode": "local_snapshot"}
        artifacts = {"receipts": {}}
        for name, (relative, activity, _) in integration.RECEIPTS.items():
            path = self.producer / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(completion(activity, "0.3.0")), encoding="utf-8")
            artifacts["receipts"][name] = {"path": relative, "sha256": integration.sha256(path)}
        package = self.producer / "learning-lab_0.3.0.zip"
        package.write_bytes(b"synthetic package fixture, not a mod ZIP")
        artifacts["package"] = {"path": package.name, "sha256": integration.sha256(package)}
        self.report = {
            "schema": "schoolops.factorio.acceptance.v1", "status": "passed",
            "scope": "headless_software_acceptance", "material_status": "draft",
            "receipt_evidence": "unverified_practice_completion_claim",
            "source_revision": None, "source_dirty": None, "source_mode": "local_snapshot",
            "source_hashes": self.hashes,
            "engine": {"version": "2.0.77", "execution": "actual_headless",
                       "binary_sha256": "1" * 64, "provisioning": "official_sha256_archive",
                       "archive_sha256": integration.FACTORIO_ARCHIVE_SHA256},
            "checks": {name: {"status": "passed", "evidence": "synthetic parser fixture"}
                       for name in integration.REQUIRED_CHECKS},
            "artifacts": artifacts,
        }
        for name in ("desktop_gui", "connected_multiplayer"):
            self.report["checks"][name] = {"status": "not_run", "evidence": "outside headless scope"}
        self.report["checks"]["gui_handler_model"]["kind"] = "simulated_lua"
        self.write_report()

    def write_report(self):
        (self.producer / "report.json").write_text(json.dumps(self.report), encoding="utf-8")

    def validate(self):
        # Report/artifact bytes are synthetic test fixtures. The real SchoolOps
        # inspector runs here; game production is a separate acceptance step.
        return integration.validate_producer(self.producer, self.checkout, self.lock, self.identity,
                                             allow_local_source=True)

    def test_complete_report_parser_preserves_unsigned_claim_classification(self):
        result = self.validate()
        self.assertEqual(set(result["receipts"]), {"smelting", "ratio"})
        for record in result["receipts"].values():
            self.assertEqual(record["inspection"]["evidence"], "unverified_practice_completion_claim")
            self.assertEqual(record["inspection"]["material_status"], "draft")

    def test_candidate_supply_requires_engine_gates_and_exact_exported_bytes(self):
        payload = self.producer / "receipts/factory-supply-order.json"
        payload.write_text(json.dumps(SUPPLY), encoding="utf-8")
        self.report["artifacts"]["receipts"]["supply_unregistered"] = {
            "path": "receipts/factory-supply-order.json",
            "sha256": integration.sha256(payload),
        }
        for name in ("real_engine_supply", "supply_reload_active",
                     "supply_reload_complete", "actual_supply_receipt"):
            self.report["checks"][name] = {"status": "passed", "evidence": "synthetic parser fixture"}
        self.write_report()
        verified = self.validate()
        self.assertEqual(set(verified["receipts"]), {"smelting", "ratio", "supply_candidate"})
        self.assertEqual(verified["receipts"]["supply_candidate"]["inspection"]["evidence"],
                         "unverified_practice_completion_claim")
        self.report["checks"]["supply_reload_complete"]["status"] = "not_run"
        self.write_report()
        with self.assertRaises(integration.IntegrationError):
            self.validate()
        self.report["checks"]["supply_reload_complete"]["status"] = "passed"
        payload.write_text(json.dumps(dict(SUPPLY, learner_id="private-value")), encoding="utf-8")
        self.report["artifacts"]["receipts"]["supply_unregistered"]["sha256"] = integration.sha256(payload)
        self.write_report()
        with self.assertRaises(integration.IntegrationError):
            self.validate()

    def test_every_required_engine_gate_must_be_present_and_passed(self):
        original = json.loads(json.dumps(self.report))
        for name in integration.REQUIRED_CHECKS:
            for status in ("failed", "not_run", "skipped", True, None):
                with self.subTest(name=name, status=status):
                    self.report = json.loads(json.dumps(original))
                    self.report["checks"][name]["status"] = status
                    self.write_report()
                    with self.assertRaises(integration.IntegrationError):
                        self.validate()
            self.report = json.loads(json.dumps(original))
            del self.report["checks"][name]
            self.write_report()
            with self.assertRaises(integration.IntegrationError):
                self.validate()

    def test_mocked_missing_or_wrong_engine_cannot_be_reported_as_runtime_acceptance(self):
        original = self.report["engine"].copy()
        for mutation in ({"execution": "lua_mock"}, {"version": "2.0.78"},
                         {"binary_sha256": None}, {"archive_sha256": None},
                         {"archive_sha256": "2" * 64},
                         {"private_extra": "synthetic-private-field"},
                         {"provisioning": "unknown"}):
            self.report["engine"] = dict(original, **mutation)
            self.write_report()
            with self.subTest(mutation=mutation), self.assertRaises(integration.IntegrationError):
                self.validate()
        del self.report["engine"]
        self.write_report()
        with self.assertRaises(integration.IntegrationError):
            self.validate()

    def test_no_desktop_multiplayer_or_readiness_promotion(self):
        original = json.loads(json.dumps(self.report))
        for field, value in (("status", "failed"), ("scope", "learner_mastery"),
                             ("material_status", "ready"), ("receipt_evidence", "authenticated")):
            self.report = dict(original, **{field: value})
            self.write_report()
            with self.subTest(field=field), self.assertRaises(integration.IntegrationError):
                self.validate()
        for name in ("desktop_gui", "connected_multiplayer"):
            self.report = json.loads(json.dumps(original))
            self.report["checks"][name]["status"] = "passed"
            self.write_report()
            with self.assertRaises(integration.IntegrationError):
                self.validate()
        self.report = json.loads(json.dumps(original))
        self.report["checks"]["gui_handler_model"]["kind"] = "actual_headless"
        self.write_report()
        with self.assertRaises(integration.IntegrationError):
            self.validate()

    def test_source_claims_and_hashes_must_match_actual_bytes(self):
        self.report["source_revision"] = "a" * 40
        self.write_report()
        with self.assertRaises(integration.IntegrationError):
            self.validate()
        self.report["source_revision"] = None
        self.report["source_hashes"] = {}
        self.write_report()
        with self.assertRaises(integration.IntegrationError):
            self.validate()
        self.report["source_hashes"] = self.hashes
        self.write_report()
        (self.checkout / "tools/verify_learning_lab.py").write_text("changed bytes", encoding="utf-8")
        with self.assertRaises(integration.IntegrationError):
            self.validate()

    def test_receipt_identity_or_changed_version_is_rejected_even_with_updated_artifact_hash(self):
        for name in ("smelting", "ratio"):
            entry = self.report["artifacts"]["receipts"][name]
            path = self.producer / entry["path"]
            original = path.read_bytes()
            for extra in ({"learner_id": "synthetic-private-id"}, {"mod_version": "9.9.9"}):
                payload = dict(json.loads(original), **extra)
                path.write_text(json.dumps(payload), encoding="utf-8")
                entry["sha256"] = integration.sha256(path)
                self.write_report()
                with self.subTest(name=name, extra=extra), self.assertRaises(integration.IntegrationError):
                    self.validate()
            path.write_bytes(original)
            entry["sha256"] = integration.sha256(path)

    def test_report_artifact_paths_and_file_hashes_are_not_trusted(self):
        entry = self.report["artifacts"]["package"]
        original = entry.copy()
        for path in ("../outside.zip", "/tmp/example.zip", "other.zip"):
            entry["path"] = path
            self.write_report()
            with self.assertRaises(integration.IntegrationError):
                self.validate()
        entry.update(original)
        entry["sha256"] = "0" * 64
        self.write_report()
        with self.assertRaises(integration.IntegrationError):
            self.validate()

    def test_symlinked_evidence_and_source_are_rejected(self):
        external = self.root / "external"
        external.write_bytes((self.checkout / "mod.py").read_bytes())
        (self.checkout / "mod.py").unlink()
        (self.checkout / "mod.py").symlink_to(external)
        with self.assertRaises(integration.IntegrationError):
            self.validate()
        for relative in ("../external", "/tmp/example", "a/../external", "a\\b"):
            with self.subTest(relative=relative), self.assertRaises(integration.IntegrationError):
                integration.local_file(self.root, relative)

    def test_pending_lock_requires_explicit_local_source_mode(self):
        with self.assertRaises(integration.IntegrationError):
            integration.load_lock(self.lock_path)
        self.assertIsNone(integration.load_lock(self.lock_path, allow_local_source=True)["revision"])
        with self.assertRaises(integration.IntegrationError):
            integration.verify_source(self.checkout, dict(self.lock, revision="a" * 40))

    def test_pinned_source_checks_actual_git_head_and_untracked_files(self):
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "-c", "user.name=Synthetic fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
        identity = integration.git_identity(self.checkout)
        lock = dict(self.lock, revision=identity["revision"], source_hashes=self.hashes, source_status="pinned")
        self.assertEqual(integration.verify_source(self.checkout, lock), identity)
        with self.assertRaises(integration.IntegrationError):
            integration.verify_source(self.checkout, dict(lock, revision="a" * 40))
        (self.checkout / "untracked.lua").write_text("injected runtime fixture", encoding="utf-8")
        with self.assertRaises(integration.IntegrationError):
            integration.verify_source(self.checkout, lock)

    def test_missing_engine_or_failing_producer_is_nonzero_without_reading_receipts(self):
        output = self.root / "failed-run"
        failed = subprocess.CompletedProcess([], 1, b"synthetic-private-stdout", b"synthetic-private-stderr")
        real_run = subprocess.run

        def fail_only_producer(command, **kwargs):
            # Mock the game subprocess, not git rev-parse/status: those are
            # independently checked before and after producer execution.
            if len(command) > 1 and str(command[1]).endswith("verify_learning_lab.py"):
                return failed
            return real_run(command, **kwargs)

        with mock.patch.object(integration.subprocess, "run", side_effect=fail_only_producer), \
             mock.patch.object(integration, "validate_producer") as validator:
            report = integration.run_integration(self.checkout, output, allow_local_source=True,
                                                 lock_path=self.lock_path)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["checks"]["producer_execution"], "failed")
        self.assertEqual(report["checks"]["receipt_compatibility"], "not_run")
        validator.assert_not_called()
        public = (output / "report.json").read_text() + (output / "review.md").read_text()
        self.assertNotIn("synthetic-private-stdout", public)
        self.assertNotIn("synthetic-private-stderr", public)
        with mock.patch.object(integration, "run_integration", return_value=report), \
             mock.patch.object(sys, "argv", ["verify_factorio_integration.py", "--factorio-checkout",
                                            str(self.checkout), "--output", str(output)]), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO):
            self.assertEqual(integration.main(), 1)

    def test_stale_output_is_refused_instead_of_reusing_a_success_report(self):
        before = (self.producer / "report.json").read_bytes()
        with mock.patch.object(integration, "invoke_producer") as invoke:
            with self.assertRaises(integration.IntegrationError):
                integration.run_integration(self.checkout, self.producer, allow_local_source=True,
                                             lock_path=self.lock_path)
        invoke.assert_not_called()
        self.assertEqual((self.producer / "report.json").read_bytes(), before)

    def test_inspection_and_pipeline_leave_learner_records_absent(self):
        self.validate()
        forbidden = {"private", "learner-records", "student-records", "assignments", "grades"}
        self.assertFalse(forbidden.intersection(path.name for path in self.root.rglob("*")))
        # A receipt remains replayable as an unverified claim. Reinspection has
        # no state, identity association, or credit operation.
        path = self.root / "legacy-receipt.json"
        path.write_text(json.dumps(SMELTING), encoding="utf-8")
        self.assertEqual(inspect_receipt(path), inspect_receipt(path))

    def test_duplicate_report_keys_are_rejected(self):
        path = self.producer / "report.json"
        path.write_text(json.dumps(self.report)[:-1] + ', "status": "passed"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.validate()

    def test_inspector_output_cannot_add_private_fields_to_integration_evidence(self):
        result = {
            "schoolops_record": "curriculum/pilots/factorio/README.md",
            "resource_id": "R-FACTORIO-001", "activity_id": "L-FACTORIO-SMELTING-01",
            "material_status": "draft", "evidence": "unverified_practice_completion_claim",
            "learner_id": "synthetic-private-extra",
        }
        with mock.patch.object(integration, "inspect_receipt", return_value=result):
            with self.assertRaises(integration.IntegrationError):
                integration.validate_producer(self.producer, self.checkout, self.lock, self.identity,
                                              allow_local_source=True)
