"""Reproducibility, saved continuation, separation and arithmetic invariants."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from exercise_bank.unit3 import ACTIVITIES, generate, render

class Unit3Sessions(unittest.TestCase):
    def test_all_activity_families_and_routes(self):
        for limit in (12, 24):
            for activity in ACTIVITIES:
                for value in range(30):
                    form = generate(activity, limit, f"{value:032x}")
                    with self.subTest(limit=limit, activity=activity, value=value):
                        self.assertTrue(form["items"])
                        self.assertEqual(len(form["items"]), 6 if activity == "check" else
                                         3 if activity == "entry" else 2)
                        self.assertEqual(len(form["items"]), render(form, True).count("Key: "))
                        self.assertNotIn("Key:", render(form))
                        self.assertNotIn(form["seed"], render(form))
                        for idx, item in enumerate(form["items"], 1):
                            self.assertEqual(f"U3-{idx:02}", item["id"])
                            self.assertEqual(item["groups"] * item["each"] + item["leftover"],
                                             item["total"])
                            self.assertLessEqual(item["total"], limit)
                            self.assertIn("O-MATH-001-013", render(form, True))
        seed = "0" * 32
        self.assertEqual(generate("check", 24, seed), generate("check", 24, seed))
        self.assertNotEqual(generate("check", 24, seed)["items"],
                            generate("check", 24, "1" * 32)["items"])

    def test_new_resume_private_key_tamper_and_no_overwrite(self):
        def cli(*args, check=False):
            return subprocess.run([sys.executable, "-m", "exercise_bank.unit3", *map(str, args)],
                                  capture_output=True, check=check)
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "one", Path(temp) / "two"
            cli("new", a, "--limit", "24", check=True)
            cli("new", b, "--limit", "24", check=True)
            self.assertNotEqual((a / "session.json").read_bytes(), (b / "session.json").read_bytes())
            self.assertEqual(cli("resume", a, check=True).stdout, (a / "learner.md").read_bytes())
            self.assertEqual(cli("resume", a, "--teacher", check=True).stdout,
                             (a / "teacher.md").read_bytes())
            self.assertNotIn(b"Key:", (a / "learner.md").read_bytes())
            self.assertNotEqual(cli("new", a, "--limit", "24").returncode, 0)
            teacher = a / "teacher.md"
            original = teacher.read_bytes()
            teacher.write_bytes(original + b"extra")
            self.assertNotEqual(cli("resume", a).returncode, 0)
            teacher.write_bytes(original)
            manifest = a / "session.json"
            data = json.loads(manifest.read_text())
            data["items"][0]["key"] = "tampered"
            manifest.write_text(json.dumps(data))
            self.assertNotEqual(cli("resume", a).returncode, 0)

    def test_interactive_pause_then_continue_exact_form(self):
        def cli(*args, response):
            return subprocess.run([sys.executable, "-m", "exercise_bank.unit3", *map(str, args)],
                                  text=True, capture_output=True, input=response, check=True)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "private"
            subprocess.run([sys.executable, "-m", "exercise_bank.unit3", "new", str(directory),
                            "--limit", "12"], check=True, capture_output=True)
            original = (directory / "session.json").read_bytes()
            paused = cli("work", directory, response="first-response\n\n")
            self.assertIn("Paused", paused.stdout)
            saved = json.loads((directory / "progress.json").read_text())
            self.assertEqual(saved["responses"], {"U3-01": "first-response"})
            complete = cli("work", directory, response="response\n" * 5)
            self.assertIn("Finished: 6/6", complete.stdout)
            self.assertNotIn("U3-01:", complete.stdout)
            self.assertEqual((directory / "session.json").read_bytes(), original)
            self.assertEqual(len(json.loads((directory / "progress.json").read_text())["responses"]), 6)

if __name__ == "__main__":
    unittest.main()
