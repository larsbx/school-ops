import json
import tempfile
import unittest
from pathlib import Path

from tools.factorio_practice import inspect_receipt


class FactorioPracticeTest(unittest.TestCase):
    def test_receipt_contract(self):
        receipt = {
            "schema": "schoolops.factorio.practice.v1",
            "activity_id": "L-FACTORIO-SMELTING-01",
            "mod_version": "0.2.0",
            "result": "completed"
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            result = inspect_receipt(path)
            self.assertEqual(result["resource_id"], "R-FACTORIO-001")
            self.assertEqual(result["material_status"], "draft")
            self.assertEqual(result["evidence"], "unverified_practice_completion_claim")

            invalid = (
                json.dumps(dict(receipt, player_name="Example")),
                json.dumps(dict(receipt, schema="schoolops.factorio.practice.v2")),
                json.dumps(dict(receipt, activity_id="unknown")),
                json.dumps(dict(receipt, mod_version="0.1.0")),
                json.dumps(dict(receipt, result="started")),
                json.dumps(receipt)[:-1] + ', "result": "completed"}',
                " " * 1025
            )
            for data in invalid:
                with self.subTest(data=data[:100]):
                    path.write_text(data, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        inspect_receipt(path)
