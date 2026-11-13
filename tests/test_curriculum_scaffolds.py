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


    def test_grade3_geometry_exposed_reference_math_and_links(self):
        """Check supplied tile-count and edge-count controls and link custody."""
        pilot = ROOT / "curriculum" / "geometry" / "grade-3-tiling-pilot"
        examples = (
            (("###", "###"), 6, 10),
            (("####",), 4, 10),
            (("##.", "###"), 5, 10),
            (("######",), 6, 14),
            (("###", "###", "###"), 9, 12),
        )
        for rows, area, boundary in examples:
            filled = {(x, y) for y, row in enumerate(rows) for x, value in enumerate(row) if value == "#"}
            perimeter = sum(
                (x + dx, y + dy) not in filled
                for x, y in filled
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            with self.subTest(rows=rows):
                self.assertEqual(area, len(filled))
                self.assertEqual(boundary, perimeter)
        key = (pilot / "draft-assessments" / "reference-teacher.md").read_text(encoding="utf-8")
        for label in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"):
            self.assertIn(label, key)
        for token in ("6 square units", "4 square units", "5 square units", "9 square units",
                      "10 length units", "12 length units", "14 length units", "6 length units"):
            self.assertIn(token, key)
        for file in pilot.rglob("*.md"):
            body = file.read_text(encoding="utf-8")
            with self.subTest(file=file.relative_to(ROOT)):
                self.assertNotRegex(body, r"(?:C|U|L|O|A)-GEO-[0-9]{3}")
                for dest in re.findall(r"\]\(([^)]+)\)", body):
                    if dest.startswith(("https:", "http:", "mailto:", "#")):
                        continue
                    target = (file.parent / dest.split("#", 1)[0]).resolve()
                    self.assertTrue(target.is_file(), f"bad pilot link: {file} -> {dest}")
        for file in ("entry-learner.md", "guided-learner.md",
                     "draft-assessments/reference-learner.md"):
            learner = (pilot / file).read_text(encoding="utf-8")
            self.assertNotIn("entry-teacher.md", learner)
            self.assertNotIn("guided-teacher.md", learner)
            self.assertNotIn("reference-teacher.md", learner)
        self.assertIn("grade-3-tiling-pilot/README.md",
                      (BASE / "grade-3" / "geometry.md").read_text(encoding="utf-8"))


    def test_grade3_geometry_transfer_clinic_cases_and_key_separation(self):
        """Replay all new physical boundary cases, and guard public learner/key separation."""
        root = ROOT / "curriculum" / "geometry" / "grade-3-tiling-pilot"
        learner = (root / "transfer-learner.md").read_text(encoding="utf-8")
        key = (root / "transfer-teacher.md").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("transfer-learner.md", readme)
        self.assertIn("transfer-teacher.md", readme)
        self.assertIn("not an adopted timetable", readme)
        self.assertNotIn("transfer-teacher.md", learner)
        self.assertNotIn("reference-teacher.md", learner)
        self.assertIn("not a secure assessment", learner)
        for n in range(1, 6):
            with self.subTest(task=n):
                self.assertIn(f"## T{n} ", learner)
                self.assertIn(f"**T{n}**", key)
        # The oracle counts each complete shared tile side twice when removing
        # internal sides, including the inner boundary of the eight-tile ring.
        examples = (
            (("###", "#.#", "###"), 8, 16),
            (("#.", ".#"), 2, 8),
            (("##",), 2, 6),
            (("###", "#..", "##."), 6, 14),
            (("###", "###"), 6, 10),
            (("##", "##", "##"), 6, 10),
        )
        for rows, expected_area, expected_boundary in examples:
            cells = {(x, y) for y, row in enumerate(rows)
                     for x, symbol in enumerate(row) if symbol == "#"}
            boundary = sum((x + dx, y + dy) not in cells
                           for x, y in cells
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            with self.subTest(rows=rows):
                self.assertEqual(expected_area, len(cells))
                self.assertEqual(expected_boundary, boundary)
        self.assertEqual(12 + 4, 16)  # outer plus inner ring exposed edges
        self.assertEqual(4 * (2 * 2), 16)  # cm²: 4 tiles of 2cm by 2cm
        self.assertEqual(4 * (1 * 1), 4)   # cm²: 4 tiles of 1cm by 1cm
        for token in ("8 square units", "12 length units", "16 length units",
                      "not side-connected", "6 length units", "14 length units",
                      "4 cm²", "16 cm²", "8 cm", "16 cm",
                      "not an adopted grade expectation"):
            self.assertIn(token, key)
        self.assertNotRegex(learner + key, r"(?:C|U|L|O|A)-GEO-[0-9]{3}")

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




class Grade3ArithmeticBridgeDraftTests(unittest.TestCase):
    """Check the original unregistered Grade 3 pilot without claiming pedagogy."""

    BASE = ROOT / "curriculum/mathematics/grade-3-bridge-pilot"

    def test_scope_status_and_separate_reference_keys(self):
        course_index = (ROOT / "curriculum/README.md").read_text(encoding="utf-8")
        bridge = (self.BASE / "README.md").read_text(encoding="utf-8")
        scaffold = (BASE / "grade-3/mathematics.md").read_text(encoding="utf-8")
        self.assertNotIn("grade-3-bridge-pilot", course_index)  # still unregistered
        self.assertIn("not ready", bridge)
        self.assertIn("unassigned", bridge)
        self.assertIn("unregistered", scaffold)
        self.assertIn("grade-3-bridge-pilot/README.md", scaffold)
        self.assertIn("Music is excluded", bridge)
        self.assertIn("qualified religious-source", bridge)
        for target in ("G3M-P1", "G3M-P2", "G3M-P3"):
            self.assertIn(target, bridge)
        learner = (self.BASE / "draft-assessments/reference-learner.md").read_text(encoding="utf-8")
        teacher = (self.BASE / "draft-assessments/reference-teacher.md").read_text(encoding="utf-8")
        for i in range(1, 10):
            self.assertEqual(1, learner.count(f"**S{i}.**"))
            self.assertEqual(1, teacher.count(f"| S{i} |"))
        self.assertNotRegex(learner, r"\]\([^)]*(?:teacher|README\.md)")
        self.assertNotIn("## Provisional criteria", learner)
        self.assertIn("fixed, publicly exposed", learner)
        self.assertIn("not ready", teacher)
        for i in range(1, 5):
            self.assertIn(f"**E{i} ", (self.BASE / "entry-learner.md").read_text(encoding="utf-8"))
            self.assertIn(f"| E{i} |", (self.BASE / "entry-teacher.md").read_text(encoding="utf-8"))

    def test_three_trivium_lessons_with_25_minute_authoring_blocks(self):
        lessons = sorted((self.BASE / "lessons").glob("*.md"))
        self.assertEqual(["01-four-place-number.md", "02-arrays-and-parts.md",
                          "03-equal-parts.md"], [p.name for p in lessons])
        for i, path in enumerate(lessons, 1):
            body = path.read_text(encoding="utf-8")
            self.assertIn("DRAFT", body)
            self.assertIn("Grammar", body)
            self.assertIn("Logic", body)
            self.assertIn("Rhetoric", body)
            self.assertIn(f"X{i}", body)
            mins = [int(n) for n in re.findall(r"^\| [^|]+ \| (\d+) \|$", body, re.M)]
            self.assertEqual(25, sum(mins), path.name)
        teacher = (self.BASE / "draft-assessments/reference-teacher.md").read_text(encoding="utf-8")
        for i in range(1, 4):
            self.assertIn(f"X{i}", teacher)

    def test_exposed_arithmetic_and_local_markdown_references(self):
        from test_islamic_studies_prototype import local_link_errors
        teacher = (self.BASE / "draft-assessments/reference-teacher.md").read_text(encoding="utf-8")
        expected = {
            "S1": (5006, 5 * 1000 + 0 * 100 + 0 * 10 + 6),
            "S2": (2480, 2804),
            "S3": (3099, 3909),
            "S4": (4 * 8, 4 * 3 + 4 * 5),
            "S5": (6 * 3, 6 * 1 + 6 * 2),
            "S6": (4 * (2 + 3), 4 * 2 + 4 * 3),
            "S7": (12 // 2, 12 // 4),
            "S8": (4 * 4 // 4, 4),
            "S9": (8 // 2, 8 // 4),
        }
        for tag, (left, right) in expected.items():
            with self.subTest(tag=tag):
                if tag in ("S2", "S3", "S7", "S9"):
                    self.assertGreater(right, left if tag in ("S2", "S3") else 0)
                else:
                    self.assertEqual(left, right)
                self.assertIn(f"| {tag} |", teacher)
        for expected_token in ("5,006", "2,480 < 2,804", "3,099 < 3,909",
                               "12 + 20 = 32", "6 + 12 = 18", "8 + 12 = 20",
                               "6 squares", "4 squares", "4 squares > 2 squares"):
            self.assertIn(expected_token, teacher)
        for file in self.BASE.rglob("*.md"):
            with self.subTest(file=str(file.relative_to(self.BASE))):
                self.assertEqual([], local_link_errors(file))
                # Existing Grade 2 outcome IDs are legitimate *references*.
                # The Grade 3 pilot must not prematurely allocate its own IDs.
                self.assertNotRegex(file.read_text(encoding="utf-8"),
                                    r"(?:C|U|L|O|A)-MATH-002(?:-[0-9]{2,3})?")


class Grade3LanguageEvidenceDraftTests(unittest.TestCase):
    """Draft document and model-answer invariants; not teaching approval."""

    PILOT = ROOT / "curriculum/language/grade-3-evidence-writing-pilot"

    def test_entry_outcomes_and_no_ids(self):
        pilot = (self.PILOT / "README.md").read_text(encoding="utf-8")
        scaffold = (BASE / "grade-3/language.md").read_text(encoding="utf-8")
        self.assertIn("not ready", pilot)
        self.assertIn("unassigned", pilot)
        self.assertIn("Music is excluded", pilot)
        self.assertIn("Islamic studies", pilot)
        self.assertIn("grade-3-evidence-writing-pilot/README.md", scaffold)
        entry = (self.PILOT / "entry-learner.md").read_text(encoding="utf-8")
        key = (self.PILOT / "entry-teacher.md").read_text(encoding="utf-8")
        for i in range(1, 5):
            self.assertIn(f"**E{i}.**", entry)
            self.assertIn(f"| E{i} |", key)
            self.assertIn(f"G3-LANG-P{i}", pilot)

    def test_lessons_keys_and_exposed_reference(self):
        lessons = (self.PILOT / "lessons.md").read_text(encoding="utf-8")
        guide = (self.PILOT / "teacher-guide.md").read_text(encoding="utf-8")
        for i in range(1, 5):
            self.assertIn(f"Episode {i}", lessons)
            self.assertIn(f"X{i}", lessons)
            self.assertIn(f"**X{i}:**", guide)
        self.assertEqual(4, lessons.count("| Rhetoric"))
        for art in ("Grammar", "Logic", "Rhetoric"):
            self.assertIn(art, lessons)
        practice = (self.PILOT / "guided-learner.md").read_text(encoding="utf-8")
        for i in range(1, 9):
            self.assertEqual(1, practice.count(f"**G{i}.**"))
            self.assertIn(f"| G{i} |", guide)
        student = (self.PILOT / "draft-assessments/reference-learner.md").read_text(encoding="utf-8")
        key = (self.PILOT / "draft-assessments/reference-teacher.md").read_text(encoding="utf-8")
        for i in range(1, 11):
            self.assertEqual(1, student.count(f"**S{i}.**"))
            self.assertIn(f"| S{i} |", key)
        self.assertNotIn("reference-teacher.md", student)
        self.assertIn("9 − 12 = −3", key)
        self.assertIn("11 − 10 = +1", key)

    def test_source_lines_and_relative_links(self):
        from test_islamic_studies_prototype import local_link_errors
        packet = (self.PILOT / "source-packet.md").read_text(encoding="utf-8")
        for letter, end in (("A", 6), ("B", 4)):
            for i in range(1, end + 1):
                self.assertEqual(1, packet.count(f"**{letter}{i}.**"))
        for file in self.PILOT.rglob("*.md"):
            with self.subTest(file=file.name):
                self.assertEqual([], local_link_errors(file))
                self.assertNotRegex(file.read_text(encoding="utf-8"),
                                    r"(?:C|U|L|O|A)-LANG-[0-9]{3}")

class Unit4GeometryDraftTests(unittest.TestCase):
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
            row = re.search(rf"^\| {item} \|[^\n]*$", teacher, re.M)
            self.assertIsNotNone(row, f"missing teacher key row for {item}")
            rows[number] = row.group()
        self.assertNotIn("## Independent worked keys", learner)
        self.assertNotIn("| G4-01 |", learner)
        self.assertNotIn("practice-teacher.md", practice_learner)
        self.assertNotIn("form-measure-teacher.md", learner)
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
                    self.assertRegex(rows[number], rf"\b{answer}\b")

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
            for dest in re.findall(r"\]\(([^)]+)\)", body):
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
                            re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")
                            for heading in headings
                        }
                        self.assertIn(anchor, slugs, f"missing anchor {dest} in {target}")




if __name__ == "__main__":
    unittest.main()
