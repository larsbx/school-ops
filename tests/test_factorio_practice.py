import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.factorio_practice import MAX_RECEIPT_BYTES, inspect_receipt


def completion(activity_id, mod_version):
    return {
        "schema": "schoolops.factorio.practice.v1",
        "activity_id": activity_id,
        "mod_version": mod_version,
        "result": "completed",
    }


SMELTING = completion("L-FACTORIO-SMELTING-01", "0.2.0")
RATIO = completion("L-FACTORIO-RATIO-01", "0.3.0")


class FactorioPracticeTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "receipt.json"

    def test_registered_receipts_return_only_draft_practice_claims(self):
        cases = (
            (SMELTING, "R-FACTORIO-001", "curriculum/pilots/factorio/README.md"),
            (RATIO, "R-FACTORIO-002", "curriculum/pilots/factorio/ratio-loading-bay/README.md"),
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
        for receipt, other in ((SMELTING, RATIO), (RATIO, SMELTING)):
            missing_result = receipt.copy()
            del missing_result["result"]
            invalid = {
                "other activity": dict(receipt, activity_id=other["activity_id"]),
                "other version": dict(receipt, mod_version=other["mod_version"]),
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
        for receipt in (SMELTING, RATIO):
            for field, value in receipt.items():
                with self.subTest(activity=receipt["activity_id"], field=field):
                    duplicate = json.dumps(receipt)[:-1] + ", " + json.dumps({field: value})[1:]
                    self.path.write_text(duplicate, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                        inspect_receipt(self.path)

    def test_receipt_byte_limit(self):
        for receipt in (SMELTING, RATIO):
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
