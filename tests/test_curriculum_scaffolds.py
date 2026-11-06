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

class Unit6ApplicationsDraftTests(unittest.TestCase):
    """Original Unit 6 authorship contracts; arithmetic is checked independently.

    Structural tests do not approve lesson suitability, access or teaching readiness.
    """

    UNIT = ROOT / "curriculum/mathematics/grade-2/units/practical-applications"
    ASS = ROOT / "assessments/C-MATH-001"

    def test_existing_unit_authored_not_a_new_course(self):
        course = (ROOT / "curriculum/mathematics/grade-2/README.md").read_text(encoding="utf-8")
        unit = (self.UNIT / "README.md").read_text(encoding="utf-8")
        self.assertIn("| U-MATH-001-06 | [Applications:", course)
        self.assertIn("U-MATH-001-06", unit)
        self.assertIn("draft, not teaching-ready", unit)
        self.assertIn("Music excluded", unit)
        lessons = sorted((self.UNIT / "lessons").glob("*.md"))
        self.assertEqual(["01-collections.md", "02-journeys.md", "03-records.md", "04-choice.md"],
                         [p.name for p in lessons])
        for lesson in lessons:
            body = lesson.read_text(encoding="utf-8")
            self.assertIn("Status:", body)
            self.assertIn("Grammar", body)
            self.assertIn("Logic", body)
            self.assertIn("rhetoric", body.lower())
            self.assertIn("Independent", body)
            self.assertIn("Feedback", body)
        for outcome in ("006", "007", "009", "011"):
            self.assertIn(outcome, unit)

    def test_entry_gates_and_practice_keys_stay_separate(self):
        learner = (self.UNIT / "practice-learner.md").read_text(encoding="utf-8")
        key = (self.UNIT / "practice-teacher.md").read_text(encoding="utf-8")
        for tag in ("E1", "E2", "E3", "E4", *(f"P{i}" for i in range(1, 9))):
            self.assertRegex(learner, rf"\\b{tag}\\b")
            self.assertIn(tag, key)
        self.assertNotIn("(practice-teacher.md)", learner)
        self.assertNotRegex(learner, r"(?im)^(?:##|###) .*key|\\*\\*key:")
        self.assertIn("private", key)
        self.assertIn("supported", key)

    def test_exposed_reference_check_and_independent_arithmetic(self):
        learner = (self.ASS / "applications-learner.md").read_text(encoding="utf-8")
        key = (self.ASS / "applications-teacher.md").read_text(encoding="utf-8")
        for item in range(1, 7):
            self.assertIn(f"U6-{item:02}", learner)
            self.assertIn(f"U6-{item:02}", key)
        self.assertNotIn("(applications-teacher.md)", learner)
        self.assertIn("fixed", learner.lower())
        self.assertIn("not assessed", key.lower())
        self.assertIn(f"| U6-01 | 76 + 58 | **{76+58} counters**", key)
        self.assertIn(f"| U6-02 | 143 − 67 | **{143-67} spaces**", key)
        self.assertIn(f"| U6-03 | 96 − 48 | **{96-48} paper shapes**", key)
        self.assertIn(f"| U6-04 | 70 + 25 − 13 | **{70+25} then {70+25-13}**", key)
        self.assertIn(f"| U6-05 | 14, 9, 16 | **{14+9+16} stamps** total; **{16-9} stamps**", key)
        a, b, needed = 3*9, 2*14, 26
        self.assertIn(f"**A {a}, {a-needed} extra; B {b}, {b-needed} extras**", key)
        self.assertEqual(75 + 28, 103)
        self.assertEqual(118 - 49, 69)
        self.assertEqual(4 * 7 - 25, 3)
        self.assertEqual(3 * 9 - 25, 2)

    def test_explicit_missing_observation_and_review_gates(self):
        unit = (self.UNIT / "README.md").read_text(encoding="utf-8")
        key = (self.ASS / "applications-teacher.md").read_text(encoding="utf-8")
        self.assertIn("Actual observed astronomy components remain separately unassessed", unit)
        self.assertIn("sky/actual observation components remain unassessed", key)
        self.assertIn("Human-only gates", unit)
        self.assertIn("not ready", key)
        self.assertIn("no learner responses", (self.UNIT / "lessons/01-collections.md").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
