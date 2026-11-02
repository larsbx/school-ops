"""Static acceptance checks for authored-but-unregistered Islamic studies prototype."""
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from test_teaching_pack import anchors, LINK

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "curriculum" / "islamic-studies" / "grade-2-prototype"
LESSONS = COURSE / "units" / "sources-pillars-character" / "lessons"
OUTCOMES = ("IS2-P01", "IS2-P02", "IS2-P03", "IS2-P04")


def local_link_errors(file):
    """Check file and same-document fragments, including percent-encoded links."""
    errors = []
    for dest in LINK.findall(file.read_text(encoding="utf-8")):
        parts = urlsplit(dest)
        if parts.scheme or parts.netloc:
            continue
        path = unquote(parts.path)
        target = (file.parent / path).resolve() if path else file
        if not target.is_file():
            errors.append(f"missing file: {dest}")
        elif parts.fragment and target.suffix == ".md":
            if unquote(parts.fragment) not in anchors(target):
                errors.append(f"missing anchor: {dest}")
    return errors


def section(text, heading):
    return text.split("## " + heading + "\n", 1)[1].split("\n## ", 1)[0]


def pillar_evidence_errors(lesson, course, final):
    """Static P02 contract, not semantic/source approval or learner evidence.

    Count the actual independent prompts, not supported activities. Compare the
    authored goal, repeated threshold, course and final rubric to that evidence.
    Other outcomes still require pedagogical review beyond the structural checks.
    """
    errors = []
    goal = section(lesson, "Observable goal")
    feedback = section(lesson, "Teacher key, feedback and progression")
    course_goal = next(line for line in course.splitlines() if line.startswith("| IS2-P02 |"))
    rubric = next(line for line in final.splitlines() if line.startswith("| IS2-P02 |"))
    thresholds = [re.findall(r"(\d+)/(\d+)", text) for text in (goal, feedback, course_goal, rubric)]
    if any(not ratios or any(ratio != ("4", "5") for ratio in ratios) for ratios in thresholds):
        errors.append("P02 goal and rubric thresholds must agree on 4/5")
    task = section(lesson, "Independent exit prompts")
    prompts = re.findall(r"^\| (M\d+) \| ([^|]+) \|$", task, re.M)
    choices = re.findall(r"^\| ([A-E]) \| ([^|]+) \|$", task, re.M)
    if [p[0] for p in prompts] != [f"M{i}" for i in range(1, 6)]:
        errors.append("independent check needs five distinct prompts")
    if [p[0] for p in choices] != list("ABCDE"):
        errors.append("independent check needs five distinct choices")
    activity = next(line for line in lesson.splitlines() if line.startswith("| Independent exit check |"))
    count = re.search(r"Collect (\d+) independent matches", activity)
    if count is None or int(count[1]) != len(prompts) or "#independent-exit-prompts" not in activity:
        errors.append("exit activity must collect every independent prompt")
    task3 = re.search(r"\*\*Task 3[^\n]+", final)[0]
    final_key = next(line for line in final.splitlines() if line.startswith("- **Task 3:**"))
    pairs = dict(re.findall(r"(M\d+) → ([A-E])", feedback))
    if set(pairs) != {p[0] for p in prompts} or len(set(pairs.values())) != 5:
        errors.append("exit key must cover each prompt with a distinct choice")
    for prompt, term in prompts:
        if term not in task3 or f"{term} → {pairs.get(prompt)}" not in final_key:
            errors.append(f"{prompt} term/key disagrees with unit Task 3")
    for letter, description in choices:
        if f"({letter}) {description}" not in task3:
            errors.append(f"choice {letter} disagrees with unit Task 3")
    if "**Source question:** Name Card H's collection and report number." not in task:
        errors.append("independent source evidence is required as well as matches")
    if "Cover the worked matching strip, Card H summary and teacher keys" not in task:
        errors.append("assessment must hide supplied pairings")
    return errors


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
            with self.subTest(file=str(file.relative_to(COURSE))):
                self.assertEqual([], local_link_errors(file))

    def test_link_validator_rejects_original_anchor_and_missing_files(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            path.write_text("## Prototype outcomes (local labels only)\n\n"
                            "[good](#prototype-outcomes-local-labels-only)\n"
                            "[encoded](README.md#prototype%2Doutcomes-local-labels-only)\n",
                            encoding="utf-8")
            self.assertEqual([], local_link_errors(path))
            path.write_text(path.read_text() + "[bad](#prototype-outcomes)\n"
                            "[bad file](absent.md#anything)\n", encoding="utf-8")
            self.assertEqual(["missing anchor: #prototype-outcomes",
                              "missing file: absent.md#anything"], local_link_errors(path))

    def test_lesson_goals_thresholds_and_final_coverage(self):
        final = (COURSE / "draft-assessments/unit-check.md").read_text(encoding="utf-8")
        for file, key in zip(sorted(LESSONS.glob("*.md")), OUTCOMES):
            lesson = file.read_text(encoding="utf-8")
            goal = section(lesson, "Observable goal").split(":** ", 1)[1].split(" See [", 1)[0]
            threshold = re.search(r"\*\*Evidence threshold:\*\* ([^\n]+)", lesson)[1]
            with self.subTest(outcome=key):
                self.assertEqual(goal, threshold)
                self.assertIn(f"**{key}:**", lesson)
                minutes = re.findall(r"^\| (?!\*\*Total)[^|]+ \| [^|]+ \| (\d+) \|$", lesson, re.M)
                self.assertEqual(25, sum(map(int, minutes)))
                row = next(line for line in final.splitlines() if line.startswith(f"| {key} |"))
                tasks = re.findall(r"Task (\d+)", row)
                self.assertTrue(tasks)
                for number in tasks:
                    self.assertRegex(final, rf"\*\*Task {number}[^\n]+\(P0{key[-1]}\)")
                    self.assertIn(f"- **Task {number}:**", final)

    def test_p02_independent_evidence_and_regressions(self):
        lesson = (LESSONS / "02-five-pillars.md").read_text(encoding="utf-8")
        course = (COURSE / "README.md").read_text(encoding="utf-8")
        final = (COURSE / "draft-assessments/unit-check.md").read_text(encoding="utf-8")
        self.assertEqual([], pillar_evidence_errors(lesson, course, final))
        mutations = [
            lesson.replace("Collect 5 independent matches", "Each learner gives two pillar-description matches"),
            lesson.replace("| M5 | ḥajj |\n", ""),
            lesson.replace("At least 4/5", "At least 4/4", 1),
            lesson.replace("at least 4/5 plus", "at least 3/5 plus"),
            lesson.replace("**Source question:** Name Card H's collection and report number.", ""),
            lesson.replace("M5 → A", "M5 → B"),
            lesson.replace("Cover the worked matching strip, Card H summary and teacher keys", "Show the matching strip"),
        ]
        for broken in mutations:
            with self.subTest(mutation=mutations.index(broken)):
                self.assertTrue(pillar_evidence_errors(broken, course, final))
        self.assertTrue(pillar_evidence_errors(lesson, course, final.replace("4/5", "3/5")))

    def test_no_formal_reserved_identifiers(self):
        for file in COURSE.rglob("*.md"):
            with self.subTest(file=file.name):
                self.assertNotRegex(file.read_text(encoding="utf-8"), r"(?:C|U|L|O|A)-ISLM-[0-9]{3}")


if __name__ == "__main__":
    unittest.main()
