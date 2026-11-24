"""Structural and finite rule controls; not pedagogical acceptance."""
import itertools
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "curriculum/reasoning/grade-4-exceptions-pilot"


def admit(t, p, h, c):
    return not c and ((t and p) or h)


def decision(row):
    values = [[0, 1] if x == "?" else [int(x)] for x in row]
    outcomes = {bool(admit(*r)) for r in itertools.product(*values)}
    return "undetermined" if len(outcomes) == 2 else ("admit" if True in outcomes else "deny")


class Grade4ReasoningTests(unittest.TestCase):
    def read(self, name):
        return (PILOT / name).read_text(encoding="utf-8")

    def test_packet_and_exhaustive_override(self):
        rows = dict((m[0], m[1:]) for m in re.findall(
            r"^\| ([A-J]) \| ([01?]) \| ([01?]) \| ([01?]) \| ([01?]) \|$",
            self.read("rule-packet.md"), re.M))
        expected = dict(zip("ABCDEFGHIJ", (
            "admit", "deny", "admit", "deny", "undetermined",
            "admit", "deny", "undetermined", "deny", "deny")))
        self.assertEqual(set(expected), set(rows))
        self.assertEqual(expected, {k: decision(v) for k, v in rows.items()})
        for t, p, h, c in itertools.product((0, 1), repeat=4):
            routes = ((t == 1 and p == 1), h == 1)
            self.assertEqual(bool(admit(t, p, h, c)), c == 0 and any(routes))
            if c:
                self.assertFalse(admit(t, p, h, c))
        self.assertEqual("undetermined", decision("?100"))
        self.assertEqual("admit", decision("1?10"))
        self.assertEqual("deny", decision("?000"))
        self.assertTrue(admit(0, 0, 1, 0))
        self.assertFalse(admit(0, 0, 1, 1))

    def test_keys_and_lessons(self):
        for prefix, count, learner, teacher in (
            ("E", 4, "entry-learner.md", "entry-teacher.md"),
            ("G", 8, "guided-learner.md", "guided-teacher.md"),
            ("S", 10, "draft-assessments/reference-learner.md",
             "draft-assessments/reference-teacher.md"),
        ):
            for i in range(1, count+1):
                self.assertEqual(1, self.read(learner).count(f"**{prefix}{i}.**"))
                self.assertIn(f"| {prefix}{i} |", self.read(teacher))
            self.assertNotIn(Path(teacher).name, self.read(learner))
        for i in range(1, 5):
            self.assertEqual(1, self.read("entry-learner.md").count(f"**R{i}.**"))
            self.assertIn(f"| X{i} |", self.read("guided-teacher.md"))
        lessons = self.read("lessons.md")
        for art in ("Grammar:", "Logic:", "Rhetoric:"):
            self.assertEqual(4, lessons.count("| " + art))
        for episode in re.split(r"(?=^## Episode \d)", lessons, flags=re.M)[1:]:
            self.assertEqual(25, sum(map(int, re.findall(r"\| (\d+) \|$", episode, re.M))))

    def test_links_and_draft_boundary(self):
        for path in PILOT.rglob("*.md"):
            body = path.read_text(encoding="utf-8")
            self.assertNotRegex(body, r"(?:C|U|L|O|A)-[A-Z]+-\d{3}")
            for target in re.findall(r"\]\(([^)]+)\)", body):
                self.assertTrue((path.parent / target).resolve().is_file(), target)
        for token in ("not ready", "unassigned", "qualified religious-source", "Music is excluded"):
            self.assertIn(token, self.read("README.md"))
        self.assertIn("grade-4-exceptions-pilot/README.md",
                      (ROOT / "curriculum/scaffolds/grade-4/reasoning.md").read_text(encoding="utf-8"))
        self.assertIn("grade-4-exceptions-pilot/README.md",
                      (ROOT / "curriculum/README.md").read_text(encoding="utf-8"))
