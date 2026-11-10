"""Structural and arithmetic checks for authored Grade 2 Unit 3.
Passing is not proof of pedagogical validity, learner readiness or mastery.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "curriculum/mathematics/grade-2/units/equal-groups-sharing"
CHECK = ROOT / "assessments/C-MATH-001"
IDS = [f"U3-{i:02}" for i in range(1, 7)]
LESSONS = ["01-equal-groups", "02-sharing", "03-double-halve", "04-critique"]


class Unit3AuthoringTests(unittest.TestCase):
    def test_authoring_link_and_four_trivium_lessons(self):
        course = (ROOT / "curriculum/mathematics/grade-2/README.md").read_text()
        unit = (UNIT / "README.md").read_text()
        self.assertIn("equal-groups-sharing/README.md", course)
        for token in ("U-MATH-001-03", "O-MATH-001-013", "draft", "E1", "E2", "E3"):
            self.assertIn(token, unit)
        for i, name in enumerate(LESSONS, 1):
            body = (UNIT / "lessons" / f"{name}.md").read_text()
            for token in (f"L-MATH-001-03-{i:02}", "draft", "Grammar", "Logic", "Rhetoric"):
                with self.subTest(lesson=name, token=token):
                    self.assertIn(token, body)

    def test_learner_teacher_separation_and_complete_key(self):
        learner = (CHECK / "equal-groups-sharing-learner.md").read_text()
        teacher = (CHECK / "equal-groups-sharing-teacher.md").read_text()
        self.assertEqual(IDS, re.findall(r"^### (U3-\d\d) —", learner, re.M))
        self.assertEqual(IDS, re.findall(r"^### (U3-\d\d) —", teacher, re.M))
        self.assertNotRegex(learner, r"(?i)teacher key|\banswer key\b|equal-groups-sharing-teacher.md")
        for token in ("not teaching-ready", "O-MATH-001-013", "Unit 2", "not assessed"):
            self.assertIn(token.lower(), teacher.lower())

    def test_math_ledger(self):
        key = (CHECK / "equal-groups-sharing-teacher.md").read_text()
        rows = re.findall(r"^\| (U3-\d\d) \| ([a-z-]+) \| (\d+) \| (\d+) \| (\d+) \| (.+) \|$", key, re.M)
        expected = [
            ("U3-01", "equal-groups", 4, 5, 20),
            ("U3-02", "array", 3, 6, 18),
            ("U3-03", "sharing", 4, 4, 16),
            ("U3-04", "group-size-given", 6, 3, 18),
            ("U3-05", "inverse-two", 2, 9, 18),
            ("U3-06", "leftover", 2, 8, 17),
        ]
        self.assertEqual(expected, [(id, kind, int(g), int(each), int(total))
                                    for id, kind, g, each, total, _ in rows])
        for id, kind, groups, each, total in expected:
            with self.subTest(id=id):
                self.assertEqual(groups * each + int(kind == "leftover"), total)

    def test_practice_complete_and_learner_safe(self):
        learner = (UNIT / "practice-learner.md").read_text()
        teacher = (UNIT / "practice-teacher.md").read_text()
        for tag in ("E1", "E2", "E3", *(f"P{i}" for i in range(1, 9))):
            with self.subTest(tag=tag):
                self.assertIn(f"### {tag} —", learner)
                self.assertEqual(1, len(re.findall(r"^\| " + tag + r" \|", teacher, re.M)))
        self.assertNotIn("practice-teacher.md", learner)
        self.assertNotIn("Teacher note", learner)


if __name__ == "__main__":
    unittest.main()
