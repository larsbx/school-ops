"""Static acceptance checks for authored-but-unregistered Islamic studies prototype."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "curriculum" / "islamic-studies" / "grade-2-prototype"
LESSONS = COURSE / "units" / "sources-pillars-character" / "lessons"
OUTCOMES = ("IS2-P01", "IS2-P02", "IS2-P03", "IS2-P04")


class IslamicStudiesPrototypeTests(unittest.TestCase):
    def test_authored_material_set_and_draft_boundaries(self):
        course = (COURSE / "README.md").read_text(encoding="utf-8")
        self.assertIn("unregistered and not teaching-ready", course)
        self.assertIn("unassigned", course)
        self.assertIn("Grade 2 Islamic studies", course)
        self.assertEqual(len(list(LESSONS.glob("*.md"))), 4)
        for key in OUTCOMES:
            self.assertIn(key, course)
            self.assertIn(key, (COURSE / "draft-assessments" / "unit-check.md").read_text(encoding="utf-8"))
        self.assertIn("not a direct quotation", (COURSE / "units" / "sources-pillars-character" / "teacher-pack.md").read_text(encoding="utf-8"))
        for file in LESSONS.glob("*.md"):
            with self.subTest(file=file.name):
                content = file.read_text(encoding="utf-8")
                self.assertIn("**25**", content)
                self.assertIn("not ready", content)
                self.assertIn("## Trivium work", content)

    def test_assessment_has_actual_tasks_and_model_answers(self):
        entry = (COURSE / "draft-assessments" / "entry-check.md").read_text(encoding="utf-8")
        final = (COURSE / "draft-assessments" / "unit-check.md").read_text(encoding="utf-8")
        self.assertIn("## Tasks (actual prompts)", entry)
        for number in range(1, 6):
            self.assertIn("**Task " + str(number), final)
        self.assertIn("## Teacher answer key", final)
        self.assertIn("No averaged score is sufficient", final)
        self.assertIn("no score", final)

    def test_all_local_markdown_links(self):
        for file in COURSE.rglob("*.md"):
            for dest in re.findall(r"[]][(]([^)]+)[)]", file.read_text(encoding="utf-8")):
                if dest.startswith(("http:", "https:", "#")):
                    continue
                target = (file.parent / dest.split("#")[0]).resolve()
                with self.subTest(file=str(file.relative_to(COURSE)), dest=dest):
                    self.assertTrue(target.is_file(), f"broken link: {file}: {dest}")

    def test_no_formal_reserved_identifiers(self):
        for file in COURSE.rglob("*.md"):
            with self.subTest(file=file.name):
                self.assertNotRegex(file.read_text(encoding="utf-8"), r"(?:C|U|L|O|A)-ISLM-[0-9]{3}")


if __name__ == "__main__":
    unittest.main()
