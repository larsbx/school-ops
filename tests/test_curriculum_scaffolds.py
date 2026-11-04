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

    def test_grade_two_unit_four_authored_geometry_and_keys(self):
        """Unit 4 draft has full lessons, distinct learner/key sheets and exact math."""
        unit = ROOT / "curriculum/mathematics/grade-2/units/form-measure"
        assessment = ROOT / "assessments/C-MATH-001"
        lesson_dir = unit / "lessons"
        lesson_files = sorted(lesson_dir.glob("*.md"))
        self.assertEqual(
            ["01-form-tiles.md", "02-magnitude-units.md",
             "03-marked-line.md", "04-partition-explain.md"],
            [f.name for f in lesson_files],
        )
        record = (unit / "README.md").read_text(encoding="utf-8")
        self.assertIn("U-MATH-001-04", record)
        self.assertIn("not teaching-ready", record)
        for outcome in ("O-MATH-001-008", "O-MATH-001-009", "O-MATH-001-012"):
            self.assertIn(outcome, record)
        for path in lesson_files:
            body = path.read_text(encoding="utf-8")
            for required in ("Grammar:", "Logic:", "Rhetoric:", "Observable goal:",
                             "Independent exit", "status: draft"):
                with self.subTest(path=path.name, required=required):
                    self.assertIn(required, body)

        practice_learner = (unit / "practice-learner.md").read_text(encoding="utf-8")
        practice_teacher = (unit / "practice-teacher.md").read_text(encoding="utf-8")
        learner = (assessment / "form-measure-learner.md").read_text(encoding="utf-8")
        teacher = (assessment / "form-measure-teacher.md").read_text(encoding="utf-8")
        for prefix in ("E1", "E2", "E3", "E4", "G1", "G2", "G3", "G4",
                       "G5", "G6", "G7", "G8", "L1-X1", "L2-X1", "L3-X1", "L4-X1"):
            self.assertIn(prefix, practice_learner)
            self.assertIn(prefix, practice_teacher)
        rows = {}
        for number in range(1, 9):
            item = f"G4-{number:02d}"
            self.assertEqual(1, learner.count(f"**{item}."))
            row = re.search(rf"^\\| {item} \\|[^\\n]*$", teacher, re.M)
            self.assertIsNotNone(row, f"missing teacher key row for {item}")
            rows[number] = row.group()
        self.assertNotIn("## Independent worked keys", learner)
        self.assertNotIn("| G4-01 |", learner)
        self.assertIn("not assigned a new assessment ID", learner)

        # Recompute independent quantities rather than trusting the prose alone.
        expected = {
            1: (3 * 3, 1 * 9),
            2: (2 * 2, 1 * 4),
            3: (14, 14 // 2),
            4: (12 - 5 * 2, 12 // 2),
            5: (2 + 7 - 3,),
            6: (11 - 3,),
            7: (4 * 4, 4 * 2),
            8: (2 * 3, 2 * 4, 7),
        }
        for number, answers in expected.items():
            for answer in answers:
                with self.subTest(item=number, answer=answer):
                    self.assertRegex(rows[number], rf"\\b{answer}\\b")

        # All internal Markdown references in this coherent draft must resolve.
        documents = [
            unit / "README.md", unit / "practice-learner.md",
            unit / "practice-teacher.md", *lesson_files,
            assessment / "form-measure-learner.md",
            assessment / "form-measure-teacher.md",
            ROOT / "curriculum/scaffolds/grade-2/geometry.md",
            ROOT / "curriculum/mathematics/grade-2/course-design.md",
        ]
        for path in documents:
            body = path.read_text(encoding="utf-8")
            for dest in re.findall(r"\\]\\(([^)]+)\\)", body):
                if dest.startswith(("https:", "http:", "mailto:")):
                    continue
                relative, sep, anchor = dest.partition("#")
                target = (path.parent / relative).resolve() if relative else path.resolve()
                with self.subTest(file=path.name, dest=dest):
                    self.assertTrue(target.is_file(), f"missing {dest} from {path}")
                    if sep and target.is_file() and target.suffix == ".md":
                        headings = re.findall(
                            r"^#{1,6} +(.+)$", target.read_text(encoding="utf-8"), re.M
                        )
                        slugs = {
                            re.sub(r"[^\\w -]", "", heading.lower()).replace(" ", "-")
                            for heading in headings
                        }
                        self.assertIn(anchor, slugs, f"missing anchor {dest} in {target}")


if __name__ == "__main__":
    unittest.main()
