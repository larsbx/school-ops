"""Contract tests for the unregistered Grade 3 conditional-reasoning teaching pilot."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "curriculum" / "reasoning" / "grade-3-conditional-pilot"
CARD = re.compile(
    r"^\| \*\*([A-F])\*\* \| (blue|red|green) \| (triangle|square)"
    r" \| (yes|no) \| (yes|no) \| (yes|no) \|$", re.M
)
LINK = re.compile(r"\]\(([^)]+)\)")


def cards():
    content = (BASE / "rule-cards.md").read_text(encoding="utf-8")
    data = CARD.findall(content)
    return {name: (color, shape, dot == "yes", stripe == "yes", number == "yes")
            for name, color, shape, dot, stripe, number in data}


class GradeThreeReasoningPilotTests(unittest.TestCase):
    def test_original_six_card_logic_and_explicit_converse_controls(self):
        c = cards()
        self.assertEqual(set("ABCDEF"), set(c))
        self.assertEqual(("blue", "triangle", True, True, True), c["A"])
        self.assertEqual(("green", "square", False, False, True), c["E"])
        self.assertTrue(all(color != "blue" or dot for color, _, dot, _, _ in c.values()))
        self.assertTrue(all(shape != "triangle" or stripe
                            for _, shape, _, stripe, _ in c.values()))
        self.assertTrue(all(not stripe or number for _, _, _, stripe, number in c.values()))
        self.assertTrue(all(shape != "triangle" or number
                            for _, shape, _, _, number in c.values()))
        # These specifically falsify naive reversal and unsupported dot → number.
        self.assertEqual(("red", "square", True, False, False), c["D"])
        self.assertFalse(c["E"][3])  # numbered but not striped
        self.assertFalse(c["B"][4])  # dotted but not numbered

    def test_draft_status_record_boundaries_and_all_local_links(self):
        overview = (BASE / "README.md").read_text(encoding="utf-8")
        for token in ("draft", "not ready", "unassigned", "G3R-P1", "G3R-P2",
                      "G3R-P3", "grammar", "logic", "rhetoric", "Music excluded"):
            self.assertIn(token, overview)
        for path in BASE.rglob("*.md"):
            body = path.read_text(encoding="utf-8")
            self.assertNotRegex(body, r"(?:C|U|L|O|A)-(?:REAS|LOG)-[0-9]{3}")
            for href in LINK.findall(body):
                if href.startswith(("https://", "http://", "#")):
                    continue
                target = (path.parent / href.split("#", 1)[0]).resolve()
                with self.subTest(file=path.name, href=href):
                    self.assertTrue(target.is_file(), f"missing linked target: {target}")
        scaffold = (ROOT / "curriculum/scaffolds/grade-3/reasoning.md").read_text(
            encoding="utf-8")
        self.assertIn("../../reasoning/grade-3-conditional-pilot/README.md", scaffold)

    def test_four_usable_25_minute_trivium_lessons_and_exit_models(self):
        lessons = sorted((BASE / "lessons").glob("*.md"))
        self.assertEqual(4, len(lessons))
        for number, path in enumerate(lessons, 1):
            body = path.read_text(encoding="utf-8")
            for token in ("draft/not ready", "Grammar", "Logic", "Rhetoric",
                          "Independent exit X" + str(number),
                          "Teacher exit key X" + str(number), "Feedback"):
                self.assertIn(token, body)
            minutes = [int(n) for n in re.findall(r"^\| [^|\n]+ \| (\d+) \|", body, re.M)]
            self.assertEqual(25, sum(minutes), path.name)

    def test_one_to_one_entry_practice_and_reference_teacher_keys(self):
        for basename, label, count in (
            ("entry", "E", 4),
            ("practice", "P", 8),
            ("draft-assessments/reference", "Q", 9),
        ):
            learner = (BASE / (basename + "-learner.md")).read_text(encoding="utf-8")
            teacher = (BASE / (basename + "-teacher.md")).read_text(encoding="utf-8")
            expected = set(range(1, count + 1))
            learner_ids = {int(n) for n in re.findall(r"^\*\*" + label + r"(\d+)\b", learner, re.M)}
            teacher_ids = {int(n) for n in re.findall(
                r"^\| \*\*" + label + r"(\d+)\*\* \|", teacher, re.M)}
            self.assertEqual(expected, learner_ids, basename + ": learner")
            self.assertEqual(expected, teacher_ids, basename + ": teacher")
            self.assertNotIn("Teacher exit key", learner)
            self.assertNotIn("Complete correct answer", learner)
        key = (BASE / "draft-assessments/reference-teacher.md").read_text(encoding="utf-8")
        self.assertIn("**Q6**", key)
        self.assertIn("**R2**", key)
        self.assertIn("**R3**", key)
        self.assertIn("**Q7**", key)
        self.assertIn("**E**", key)
        self.assertIn("**Q9**", key)
        self.assertIn("**Unknown**", key)


if __name__ == "__main__":
    unittest.main()
