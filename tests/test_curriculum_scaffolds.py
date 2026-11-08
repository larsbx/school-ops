"""Validate the K–12 planning matrix, references and source-review guards."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "curriculum" / "scaffolds"
GRADES = ("k", *map(str, range(1, 13)))
SUBJECTS = ("mathematics", "geometry", "astronomy", "language", "reasoning", "natural-science", "history-geography", "islamic-studies",)


class CurriculumScaffoldTests(unittest.TestCase):
    def test_complete_matrix_and_planning_disclaimers(self):
        for grade in GRADES:
            directory = BASE / f"grade-{grade}"
            self.assertTrue((directory / "README.md").is_file())
            self.assertEqual({p.stem for p in directory.glob("*.md")} - {"README"}, set(SUBJECTS))
            for subject in SUBJECTS:
                with self.subTest(grade=grade, subject=subject):
                    body = (directory / f"{subject}.md").read_text(encoding="utf-8")
                    for token in ("planning scaffold", "unassigned", "not ready",
                                  "Proposed entry evidence", "Proposed sequence",
                                  "Proposed culminating performance", "**Grammar:**",
                                  "**Logic:**", "**Rhetoric:**", "Gates before course"):
                        self.assertIn(token, body)
                    if (grade, subject) != ("2", "mathematics"):
                        self.assertNotRegex(body, r"C-[A-Z]+-[0-9]{3}")

    def test_relative_links_exist(self):
        for file in BASE.rglob("*.md"):
            for target in re.findall(r"[]][(]([^)]+)[)]", file.read_text(encoding="utf-8")):
                if target.startswith(("http:", "https:", "#")):
                    continue
                linked = (file.parent / target.split("#")[0]).resolve()
                with self.subTest(file=file.name, target=target):
                    self.assertTrue(linked.is_file(), f"broken link in {file}: {target}")

    def test_islamic_studies_source_and_scope_guards(self):
        guide = (BASE / "islamic-studies-guide.md").read_text(encoding="utf-8")
        for term in ("Qur'an", "hadith", "fiqh", "isnād", "matn", "not yet verified",
                     "private faith", "qualified"):
            self.assertIn(term, guide)
        for grade in GRADES:
            plan = (BASE / f"grade-{grade}" / "islamic-studies.md").read_text(encoding="utf-8")
            overview = (BASE / f"grade-{grade}" / "README.md").read_text(encoding="utf-8")
            with self.subTest(grade=grade):
                self.assertIn("Islamic studies", plan)
                self.assertIn("[Open plan](islamic-studies.md)", overview)
                self.assertIn("Do not grade private faith", plan)
                self.assertIn("islamic-studies-guide.md", plan)

    def test_existing_grade_two_course_retained(self):
        body = (BASE / "grade-2" / "mathematics.md").read_text(encoding="utf-8")
        self.assertIn("C-MATH-001", body)
        self.assertIn("seven-unit progression", body)



    def test_grade3_islamic_source_literacy_pilot_integrity(self):
        from test_islamic_studies_prototype import local_link_errors
        root = ROOT / "curriculum" / "islamic-studies" / "grade-3-source-literacy-pilot"
        self.assertTrue(root.is_dir())
        doc = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("not ready", doc)
        self.assertIn("unassigned", doc)
        self.assertIn("G3-IS-P1", doc)
        self.assertIn("G3-IS-P2", doc)
        self.assertEqual(2, len(list((root / "lessons").glob("*.md"))))
        check = (root / "draft-assessments" / "unit-check-learner.md").read_text(encoding="utf-8")
        key = (root / "draft-assessments" / "unit-check-teacher.md").read_text(encoding="utf-8")
        for number in (1, 2, 3, 4, 5):
            self.assertIn(f"**Task {number}", check)
        self.assertIn("4/5", key)
        self.assertIn("3/4", key)
        self.assertIn("T4", key)
        self.assertIn("Card B", key)
        for path in root.rglob("*.md"):
            with self.subTest(path=path.name):
                self.assertEqual([], local_link_errors(path))
                body = path.read_text(encoding="utf-8")
                self.assertNotRegex(body, r"(?:C|U|L|O|A)-ISLM-[0-9]{3}")
        for lesson in (root / "lessons").glob("*.md"):
            body = lesson.read_text(encoding="utf-8")
            self.assertIn("## Trivium", body)
            mins = [int(parts[-2].strip()) for row in body.splitlines() if row.startswith("| ") and (parts := row.split("|")) and parts[-2].strip().isdigit()]
            self.assertEqual(25, sum(map(int, mins)))


    def test_grade3_new_practice_sessions_and_replay(self):
        from importlib.util import module_from_spec, spec_from_file_location
        from tempfile import TemporaryDirectory
        path = (ROOT / "curriculum" / "islamic-studies" /
                "grade-3-source-literacy-pilot" / "generate_practice.py")
        spec = spec_from_file_location("islamic_grade3_practice", path)
        self.assertIsNotNone(spec)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        first = module.build("0" * 32)
        self.assertEqual(first, module.build("0" * 32))
        second = module.build("1" * 32)
        self.assertNotEqual(first[0], second[0])
        self.assertNotEqual(first[2]["form_id"], second[2]["form_id"])
        self.assertEqual(set(module.KINDS), {card["kind"] for card in first[2]["records"]})
        self.assertEqual(set(module.CLAIMS), {card["kind"] for card in first[2]["claims"]})
        self.assertEqual(5, len(first[2]["records"]))
        self.assertEqual(4, len(first[2]["claims"]))
        self.assertNotIn("## Task 1: record classifications", first[0])
        self.assertIn("## Task 1: record classifications", first[1])
        with self.assertRaises(ValueError):
            module.build("learner-name")
        with TemporaryDirectory() as directory:
            target = Path(directory) / "form"
            manifest = module.new_session(target, "0" * 32)
            self.assertEqual(manifest, module.resume_session(target))
            before = [(target / name).read_bytes()
                      for name in ("learner.md", "teacher.md", "manifest.json")]
            module.resume_session(target)
            self.assertEqual(before, [(target / name).read_bytes()
                                      for name in ("learner.md", "teacher.md", "manifest.json")])
            with self.assertRaises(FileExistsError):
                module.new_session(target, "1" * 32)
            (target / "learner.md").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.resume_session(target)

class RamadanPracticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from importlib.util import module_from_spec, spec_from_file_location

        path = BASE / "grade-4" / "generate_ramadan_practice.py"
        spec = spec_from_file_location("grade4_ramadan_practice", path)
        cls.practice = module_from_spec(spec)
        spec.loader.exec_module(cls.practice)

    def test_generated_keys_agree_with_learner_plans(self):
        variants = set()
        for index in range(128):
            seed = f"{index:032x}"
            artifacts = self.practice.build(seed)
            learner = artifacts["learner.md"].decode("utf-8")
            teacher = artifacts["teacher.md"].decode("utf-8")
            with self.subTest(seed=seed):
                self.assertNotIn(seed, learner)
                self.assertNotIn("L3: Accept plan", learner)
                plans = re.findall(r"^Plan ([AB]): (.+)$", learner, re.MULTILINE)
                self.assertEqual(["A", "B"], [label for label, _ in plans])
                valid = []
                for label, description in plans:
                    access = "step-free entrance" in description
                    privacy = "anonymous drop box" in description
                    self.assertIn(
                        f"L2 plan {label}: access {'met' if access else 'unmet'}, "
                        f"privacy {'met' if privacy else 'unmet'}.",
                        teacher,
                    )
                    if access and privacy:
                        valid.append(label)
                    else:
                        self.assertNotEqual(access, privacy)
                        failed_rule = "privacy" if access else "access"
                self.assertEqual(1, len(valid))
                self.assertIn(f"L3: Accept plan {valid[0]} or a feasible revision", teacher)
                variants.add((valid[0], failed_rule))
        self.assertEqual(
            {(label, rule) for label in "AB" for rule in ("access", "privacy")},
            variants,
        )

    def test_resume_preserves_bytes_and_rejects_each_altered_artifact(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            target = Path(directory) / "session"
            other = Path(directory) / "other"
            self.practice.new_session(target)
            self.practice.new_session(other)
            original = {path.name: path.read_bytes() for path in target.iterdir()}
            self.assertNotEqual(original["manifest.json"], (other / "manifest.json").read_bytes())
            self.practice.resume_session(target)
            with self.assertRaises(FileExistsError):
                self.practice.new_session(target)
            self.assertEqual(original, {path.name: path.read_bytes() for path in target.iterdir()})
            for name, data in original.items():
                with self.subTest(artifact=name):
                    path = target / name
                    path.write_bytes(data + b" ")
                    with self.assertRaises(ValueError):
                        self.practice.resume_session(target)
                    self.assertEqual(data + b" ", path.read_bytes())
                    path.write_bytes(data)
            self.practice.resume_session(target)


if __name__ == "__main__":
    unittest.main()
