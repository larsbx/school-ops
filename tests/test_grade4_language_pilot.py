"""Structural checks for the unregistered Grade 4 perspectives authoring pilot."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "curriculum/language/grade-4-perspectives-pilot"


class Grade4LanguageDraftTests(unittest.TestCase):
    def test_entry_and_teacher_keys_are_separate_and_complete(self):
        entry = (PILOT / "entry-learner.md").read_text(encoding="utf-8")
        teacher = (PILOT / "entry-teacher.md").read_text(encoding="utf-8")
        guided = (PILOT / "guided-learner.md").read_text(encoding="utf-8")
        guided_key = (PILOT / "guided-teacher.md").read_text(encoding="utf-8")
        reference = (PILOT / "draft-assessments/reference-learner.md").read_text(encoding="utf-8")
        key = (PILOT / "draft-assessments/reference-teacher.md").read_text(encoding="utf-8")
        for i in range(1, 5):
            self.assertIn(f"**E{i} ", entry)
            self.assertIn(f"| E{i} |", teacher)
            self.assertIn(f"**X{i} ", guided_key)
        for i in range(1, 9):
            self.assertIn(f"**G{i}.**", guided)
            self.assertIn(f"| G{i} |", guided_key)
        for i in range(1, 11):
            self.assertIn(f"**S{i}.**", reference)
            self.assertIn(f"| S{i} |", key)
        self.assertNotIn("reference-teacher.md", reference)
        self.assertNotIn("guided-teacher.md", guided)
        self.assertNotIn("entry-teacher.md", entry)

    def test_four_trivium_episodes_25_minutes_each(self):
        lessons = (PILOT / "lessons.md").read_text(encoding="utf-8")
        episodes = re.split(r"^## Episode [1-4] — ", lessons, flags=re.M)
        self.assertEqual(5, len(episodes))
        for i, episode in enumerate(episodes[1:], 1):
            for art in ("Grammar:", "Logic:", "Rhetoric:", f"X{i}"):
                self.assertIn(art, episode)
            minutes = [int(n) for n in re.findall(r"^\| [^|]+ \| (\d+) \|$", episode, re.M)]
            self.assertEqual(25, sum(minutes), i)

    def test_local_links_and_scope_guards(self):
        readme = (PILOT / "README.md").read_text(encoding="utf-8")
        scaffold = (ROOT / "curriculum/scaffolds/grade-4/language.md").read_text(encoding="utf-8")
        index = (ROOT / "curriculum/README.md").read_text(encoding="utf-8")
        self.assertIn("unassigned", readme)
        self.assertIn("not ready", readme)
        self.assertIn("grade-4-perspectives-pilot/README.md", scaffold)
        self.assertIn("grade-4-perspectives-pilot/README.md", index)
        self.assertIn("Islamic studies", readme)
        self.assertIn("music is excluded", readme)
        self.assertNotRegex(readme, r"(?:C|U|L|O|A)-LANG-[0-9]{3}")
        for path in PILOT.rglob("*.md"):
            with self.subTest(path=path.name):
                body = path.read_text(encoding="utf-8")
                for target in re.findall(r"\]\(([^)]+)\)", body):
                    if target.startswith(("https:", "http:", "mailto:", "#")):
                        continue
                    resolved = (path.parent / target.split("#", 1)[0]).resolve()
                    self.assertTrue(resolved.is_file(), f"broken link: {path} -> {target}")

    def test_source_labels_and_claim_limit(self):
        packet = (PILOT / "source-packet.md").read_text(encoding="utf-8")
        reference = (PILOT / "draft-assessments/reference-learner.md").read_text(encoding="utf-8")
        for card, n in (("A", 5), ("B", 5), ("C", 4)):
            for i in range(1, n+1):
                self.assertIn(f"**{card}{i}.**", packet)
        for card in "DEF":
            self.assertIn(f"**{card}1.**", reference)
        key = (PILOT / "draft-assessments/reference-teacher.md").read_text(encoding="utf-8")
        self.assertIn("not a valid hidden assessment", key)
        self.assertIn("at 15:05", key)
        self.assertIn("at 15:10", key)


if __name__ == "__main__":
    unittest.main()
