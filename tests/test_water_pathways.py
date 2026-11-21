import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from exercise_bank import water_pathways as bank

PROJECT = Path(__file__).resolve().parents[1]


def fixture_seed(number):
    """Predictable test input, never an operational session seed."""
    return f"{number:032x}"


def write_private(path, value):
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


class WaterPathwaysContentTests(unittest.TestCase):
    def setUp(self):
        self.form = bank.generate(fixture_seed(1))
        self.layout = bank.inspect_form(self.form)
        self.key = bank.make_key(self.form, self.layout)

    def test_independent_arithmetic_and_record_oracle_across_1024_seeds(self):
        focuses, claim_kinds, correct_case_positions = set(), set(), set()
        higher_surface_labels = set()
        for number in range(1024):
            with self.subTest(number=number):
                form = bank.generate(fixture_seed(number))
                layout = bank.inspect_form(form)
                key = bank.make_key(form, layout)
                focuses.add(form.focus)
                claim_kinds.add(form.claim)
                for trial, outside in ((form.reading, key.reading_remainder_ml),
                                       (form.disputed, key.disputed_remainder_ml)):
                    self.assertEqual(trial.input_ml - trial.collector_ml, outside)
                    self.assertGreater(outside, 0)
                for row in (*form.comparison, *form.memo):
                    self.assertEqual(len(set(row.trials_ml)), 2)
                    self.assertTrue(all(0 <= number < row.input_ml for number in row.trials_ml))
                    self.assertEqual(Fraction(sum(row.trials_ml), 2).denominator, 1)
                for pair, numbers in ((layout.controlled, key.comparison), (form.memo, key.memo)):
                    means = tuple(Fraction(sum(row.trials_ml), len(row.trials_ml)) for row in pair)
                    self.assertEqual(means, numbers.means_ml)
                    self.assertEqual(max(means) - min(means), numbers.gap_ml)
                left, right = layout.controlled
                settings = ((left.input_ml, right.input_ml), (left.tilt, right.tilt),
                            (left.surface, right.surface))
                self.assertEqual(
                    [factor for factor, (a, b) in zip(("input", "tilt", "surface"), settings)
                     if a != b], [form.focus],
                )
                if form.focus == "surface":
                    higher = max(layout.controlled, key=lambda row: sum(row.trials_ml))
                    higher_surface_labels.add(higher.surface)
                correct_case_positions.add(form.case_order.index(0))
                self.assertEqual(key.destination, "unknown")
                values = bank.signatures(form, layout)
                self.assertEqual(len(values), len(set(values)))
        self.assertEqual(focuses, {"tilt", "surface"})
        self.assertEqual(claim_kinds, {"absorbed", "evaporated"})
        self.assertEqual(higher_surface_labels, {"bare", "cloth"})
        self.assertEqual(correct_case_positions, {0, 1, 2})

    def test_bad_measurements_fail_before_rendering(self):
        start = self.form.reading.input_ml
        for trial in (bank.Trial(start, start + 1), bank.Trial(start, -1),
                      bank.Trial(start, True), bank.Trial(start, 31.0), bank.Trial(0, 0)):
            with self.subTest(trial=trial), self.assertRaises(ValueError):
                bank.render_learner(replace(self.form, reading=trial))
        row, *rest = self.form.comparison
        for readings in ((25, 30), (30, 30), (30, 32, 34)):
            altered = replace(self.form, comparison=(replace(row, trials_ml=readings), *rest))
            with self.subTest(readings=readings), self.assertRaises(ValueError):
                bank.render_teacher(altered)

    def test_incorrect_remainder_mean_and_gap_are_rejected(self):
        mean1, mean2 = self.key.comparison.means_ml
        for key in (
            replace(self.key, reading_remainder_ml=self.key.reading_remainder_ml + 1),
            replace(self.key, disputed_remainder_ml=self.key.disputed_remainder_ml - 1),
            replace(self.key, comparison=replace(self.key.comparison, means_ml=(mean1 + 1, mean2))),
            replace(self.key, memo=replace(self.key.memo, gap_ml=-1)),
            replace(self.key, memo=replace(self.key.memo, gap_ml=self.key.memo.gap_ml + 1)),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                bank.verify_key(self.form, self.layout, key)

    def test_controlled_two_label_and_unequal_input_cases_are_distinct(self):
        valid, two_labels, unequal = (self.layout.cases[self.form.case_order.index(index)]
                                      for index in range(3))
        self.assertEqual(bank.changes(*valid), (self.layout.case_target,))
        self.assertEqual(bank.changes(*two_labels), ("tilt", "surface"))
        self.assertEqual(bank.changes(*unequal), ("input",))
        self.assertNotEqual(unequal[0].input_ml, unequal[1].input_ml)
        key_text = bank.render_teacher(self.form)
        self.assertIn("**Yes.** Changes in " + self.layout.case_target, key_text)
        self.assertIn("**No.** Changes in tilt, surface", key_text)
        self.assertIn("**No.** Changes in input", key_text)

    def test_two_valid_choices_are_rejected_as_ambiguous(self):
        controlled_left, controlled_right = self.layout.controlled
        input_pair = self.layout.cases[self.form.case_order.index(2)]
        replacement = next(row for row in input_pair if row not in self.layout.controlled)
        anchor = next(row for row in (controlled_left, controlled_right)
                      if row.label != replacement.label)
        duplicate_setup = replace(replacement, input_ml=anchor.input_ml,
                                  tilt=anchor.tilt, surface=anchor.surface)
        # Preserve distinct means and valid measurements, so only the setup is ambiguous.
        self.assertLess(max(duplicate_setup.trials_ml), duplicate_setup.input_ml)
        rows = tuple(duplicate_setup if row.label == replacement.label else row
                     for row in self.form.comparison)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            bank.inspect_form(replace(self.form, comparison=rows))

    def test_missing_comparison_and_repeated_case_order_are_rejected(self):
        left, right = self.form.memo
        broken = replace(self.form, memo=(left, replace(right, input_ml=right.input_ml + 1)))
        with self.assertRaisesRegex(ValueError, "memo must isolate"):
            bank.inspect_form(broken)
        for order in ((0, 0, 2), (False, True, 2)):
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, "each appear once"):
                bank.inspect_form(replace(self.form, case_order=order))

    def test_transformed_questions_have_the_same_exposure_signature(self):
        first, second = self.layout.controlled
        renamed = replace(first, label="Z", trials_ml=first.trials_ml[::-1])
        self.assertEqual(bank._comparison_signature((first, second)),
                         bank._comparison_signature((second, renamed)))
        different_readings = replace(renamed, trials_ml=(20, 22))
        self.assertEqual(bank._comparison_signature((first, second)),
                         bank._comparison_signature((different_readings, second)))
        unrelated_input = replace(renamed, input_ml=140)
        self.assertEqual(bank._mean_signature(first), bank._mean_signature(unrelated_input))

    def test_exposed_source_and_intraform_repeats_are_blocked(self):
        exposed_row = bank.Setup("Z", 80, "angled", "bare", (56, 60))
        self.assertIn(bank._mean_signature(exposed_row), bank.EXPOSED)
        self.assertIn(bank._trial_signature(bank.Trial(80, 60)), bank.EXPOSED)
        self.assertIn(bank._trial_signature(bank.Trial(70, 46)), bank.EXPOSED)
        remixed_pair = (replace(exposed_row, tilt="level"),
                        replace(exposed_row, tilt="level", surface="cloth"))
        self.assertIn(bank._comparison_signature(remixed_pair), bank.EXPOSED)

        repeated = replace(self.form, disputed=self.form.reading)
        with patch.object(bank, "_candidate", side_effect=[repeated, self.form]) as pick:
            self.assertEqual(bank.generate(fixture_seed(1)), self.form)
        self.assertEqual(pick.call_count, 2)

    def test_destination_claims_fail_and_teacher_qualifies_both_examples(self):
        for claim in ("absorbed", "evaporated", "proved flow", "spilled"):
            with self.subTest(claim=claim), self.assertRaisesRegex(ValueError, "cannot establish"):
                bank.verify_key(self.form, self.layout, replace(self.key, destination=claim))
        for claim in bank.CLAIMS:
            form = replace(self.form, claim=claim)
            learner = bank.render_learner(form)
            self.assertIn("A student says", learner)
            self.assertIn(bank.CLAIMS[claim] + ".”", learner)
            key = bank.render_teacher(form)
            self.assertIn("The destination is unknown.", key)
            self.assertIn(f"measurement of water {claim} would be needed", key)
        with self.assertRaisesRegex(ValueError, "unknown question kind"):
            bank.render_learner(replace(self.form, claim="proved flow"))

    def test_views_agree_and_keep_rubric_and_keys_out_of_learner_copy(self):
        table = bank.render_learner(self.form)
        linear = bank.render_learner(self.form, linear=True)
        without_records = lambda text: "\n".join(
            line for line in text.splitlines() if not line.startswith(("|", "- Setup "))
        )
        self.assertEqual(without_records(table), without_records(linear))
        for row in (*self.form.comparison, *self.form.memo):
            self.assertIn(f"| {row.label} | {row.input_ml} | {row.tilt} | {row.surface} | "
                          f"{row.trials_ml[0]} | {row.trials_ml[1]} |", table)
            self.assertIn(f"Setup {row.label}. Input {row.input_ml} mL. Tilt {row.tilt}. "
                          f"Surface {row.surface}. Trial 1 collector {row.trials_ml[0]} mL. "
                          f"Trial 2 collector {row.trials_ml[1]} mL.", linear)
        for text in (table, linear):
            for private in (fixture_seed(1), "session.json", "form_id", "teacher.md",
                            " = ", " ÷ ", "P1", "P2", "P3", "P4", "The destination is unknown."):
                self.assertNotIn(private, text)
            self.assertIn("Independent review required before classroom use", text)
        key_text = bank.render_teacher(self.form)
        for outcome in ("P1", "P2", "P3", "P4"):
            self.assertIn(outcome, key_text)
        self.assertIn("A reviewer other than the form preparer", key_text)
        self.assertIn("neutral read-aloud", key_text)
        self.assertIn("tactile labeled cards", key_text)

    def test_render_rejects_answer_injected_via_setup_label(self):
        row, *rest = self.form.comparison
        altered = replace(self.form, comparison=(replace(row, label="ANSWER-LEAK"), *rest))
        for render in (bank.render_learner, bank.render_teacher):
            with self.subTest(render=render), self.assertRaisesRegex(ValueError, "setup labels"):
                render(altered)

    def test_review_preview_mark_is_explicit(self):
        for render in (bank.render_learner, bank.render_teacher):
            with self.subTest(render=render):
                self.assertIn("Exposed synthetic example for review", render(self.form, example=True))
                self.assertNotIn("Exposed synthetic example for review", render(self.form))


@unittest.skipUnless(os.name == "posix", "private directory permissions require POSIX")
class WaterPathwaysSessionTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)

    def issue(self, name="first", number=1):
        with patch.object(bank.secrets, "token_hex", return_value=fixture_seed(number)) as seed:
            result = bank.new_session(self.root, name)
        seed.assert_called_once_with(16)
        return result

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "exercise_bank.water_pathways", *args],
            cwd=PROJECT, capture_output=True, check=False,
        )

    def test_owner_only_creation_and_exact_replay(self):
        session = self.issue()
        replay = bank.resume_session(self.root, "first")
        self.assertEqual(set(replay), {"learner.md", "learner-linear.md", "teacher.md", "session.json"})
        self.assertEqual(session.stat().st_mode & 0o777, 0o700)
        for filename, verified in replay.items():
            path = session / filename
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_bytes(), verified.encode("utf-8"))
        self.assertEqual((self.root / bank.ROOT_DB).stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(replay["session.json"])["seed"], fixture_seed(1))

    def test_cli_creates_draft_and_displays_only_requested_audience(self):
        result = self.cli("new", str(self.root), "cli")
        self.assertEqual(result.returncode, 0, result.stderr)
        session = self.root / "cli"
        manifest = json.loads((session / "session.json").read_text())
        for flags, filename in (((), "learner.md"), (("--linear",), "learner-linear.md"),
                                (("--teacher",), "teacher.md")):
            result = self.cli("resume", str(self.root), "cli", *flags)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, (session / filename).read_bytes())
            self.assertNotIn(manifest["seed"].encode(), result.stdout)
            self.assertNotIn(manifest["form_id"].encode(), result.stdout)

    def test_injected_manifest_metadata_is_refused_without_printing_it(self):
        session = self.issue()
        path = session / "session.json"
        manifest = json.loads(path.read_text())
        marker = "ANSWER-LEAK-TEST"
        manifest["teacher_answer"] = marker
        write_private(path, json.dumps(manifest))
        result = self.cli("resume", str(self.root), "first")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(marker.encode(), result.stderr)

    def test_answer_injection_into_learner_file_is_refused(self):
        session = self.issue()
        path = session / "learner-linear.md"
        write_private(path, path.read_text() + "\nANSWER-LEAK-TEST\n")
        with self.assertRaisesRegex(ValueError, "learner-linear.md differs"):
            bank.resume_session(self.root, "first")

    def test_key_changed_to_unsupported_cause_is_refused(self):
        session = self.issue()
        key = session / "teacher.md"
        write_private(key, key.read_text().replace("The destination is unknown.", "It all evaporated."))
        with self.assertRaisesRegex(ValueError, "teacher.md differs"):
            bank.resume_session(self.root, "first")

    def test_a_valid_bundle_copied_to_a_new_name_does_not_resume(self):
        source = self.issue()
        shutil.copytree(source, self.root / "copy")
        with self.assertRaisesRegex(ValueError, "does not match its question reservations"):
            bank.resume_session(self.root, "copy")

    def test_existing_session_cannot_be_overwritten(self):
        self.issue()
        before = bank.resume_session(self.root, "first")
        with self.assertRaises(FileExistsError):
            bank.new_session(self.root, "first")
        self.assertEqual(bank.resume_session(self.root, "first"), before)

    def test_repeat_under_a_new_name_is_resampled(self):
        self.issue()
        repeated, fresh = fixture_seed(1), fixture_seed(3)
        with patch.object(bank.secrets, "token_hex", side_effect=(repeated, fresh)) as seed:
            second = bank.new_session(self.root, "second")
        self.assertEqual(seed.call_count, 2)
        self.assertEqual(json.loads((second / "session.json").read_text())["seed"], fresh)

    def test_a_single_repeated_item_in_an_otherwise_new_form_is_resampled(self):
        self.issue()
        first = bank.generate(fixture_seed(1))
        newer = bank.generate(fixture_seed(3))
        altered = replace(newer, reading=first.reading)
        final_seed = fixture_seed(4)
        actual_generate = bank.generate
        with patch.object(bank.secrets, "token_hex", side_effect=(fixture_seed(3), final_seed)):
            with patch.object(bank, "generate", side_effect=(altered, actual_generate(final_seed))):
                second = bank.new_session(self.root, "second")
        self.assertEqual(json.loads((second / "session.json").read_text())["seed"], final_seed)
        bank.resume_session(self.root, "second")

    def test_public_source_and_fingerprinted_review_exposures_are_blocked(self):
        generate = bank.generate
        source_seed, exposed_seed, fresh_seed = map(fixture_seed, (100, 1, 3))
        source_overlap = replace(generate(source_seed), reading=bank.Trial(80, 60))
        exposed = generate(exposed_seed)
        observed = bank.signatures(exposed, bank.inspect_form(exposed))[0]
        blocked = bank.DEMONSTRATION_DIGESTS | set(bank._signature_digests([observed]))
        candidates = [source_overlap, exposed, generate(fresh_seed)]
        with (patch.object(bank, "DEMONSTRATION_DIGESTS", blocked),
              patch.object(bank.secrets, "token_hex", side_effect=(source_seed, exposed_seed, fresh_seed)),
              patch.object(bank, "generate", side_effect=candidates)):
            session = bank.new_session(self.root, "first")
        manifest = json.loads((session / "session.json").read_text())
        self.assertEqual(manifest["seed"], fresh_seed)

    def test_newly_known_exposure_does_not_change_an_existing_form_on_replay(self):
        self.issue()
        before = bank.resume_session(self.root, "first")
        form = bank.generate(fixture_seed(1))
        updated_blocklist = bank.EXPOSED | set(bank.signatures(form, bank.inspect_form(form)))
        with patch.object(bank, "EXPOSED", updated_blocklist):
            self.assertEqual(bank.resume_session(self.root, "first"), before)

    def test_retry_limit_refuses_a_repeated_form_and_creates_no_directory(self):
        self.issue()
        with patch.object(bank, "ATTEMPTS", 3), patch.object(
            bank.secrets, "token_hex", return_value=fixture_seed(1)
        ) as seed, self.assertRaisesRegex(ValueError, "no fresh questions"):
            bank.new_session(self.root, "second")
        self.assertEqual(seed.call_count, 3)
        self.assertFalse((self.root / "second").exists())

    def test_failed_output_write_leaves_no_partial_bundle_and_reserves_questions(self):
        repeated, fresh = fixture_seed(1), fixture_seed(3)
        with patch.object(bank, "_write_private", side_effect=OSError("simulated write failure")):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                self.issue()
        self.assertEqual({path.name for path in self.root.iterdir()}, {bank.ROOT_DB})
        with self.assertRaises(FileExistsError):
            bank.new_session(self.root, "first")
        with patch.object(bank.secrets, "token_hex", side_effect=(repeated, fresh)) as seed:
            bank.new_session(self.root, "second")
        self.assertEqual(seed.call_count, 2)

    def test_two_concurrent_creates_cannot_reserve_same_questions(self):
        per_worker = threading.local()
        start = threading.Barrier(2, timeout=5)

        def worker_seed(size):
            self.assertEqual(size, 16)
            seed = getattr(per_worker, "next_seed", fixture_seed(1))
            per_worker.next_seed = fixture_seed(3)
            return seed

        def create(name):
            start.wait()
            return bank.new_session(self.root, name)

        with patch.object(bank.secrets, "token_hex", side_effect=worker_seed):
            with ThreadPoolExecutor(max_workers=2) as pool:
                sessions = list(pool.map(create, ("first", "second")))
        seeds = {json.loads((path / "session.json").read_text())["seed"] for path in sessions}
        self.assertEqual(seeds, {fixture_seed(1), fixture_seed(3)})
        for path in sessions:
            bank.resume_session(self.root, path.name)

    def test_missing_and_empty_exposure_registries_do_not_reset_freshness(self):
        self.issue()
        registry = self.root / bank.ROOT_DB
        registry.unlink()
        with self.assertRaisesRegex(ValueError, "registry is missing"):
            bank.new_session(self.root, "second")
        write_private(registry, "")
        with self.assertRaisesRegex(ValueError, "registry is incomplete"):
            bank.new_session(self.root, "second")
        self.assertFalse((self.root / "second").exists())

    def test_resume_rejects_unreserved_signature_even_with_exact_files(self):
        self.issue()
        with sqlite3.connect(self.root / bank.ROOT_DB) as database:
            database.execute("DELETE FROM exposures")
        with self.assertRaisesRegex(ValueError, "does not match its question reservations"):
            bank.resume_session(self.root, "first")

    def test_refuses_shared_root_and_path_traversal(self):
        with self.assertRaisesRegex(ValueError, "simple local folder name"):
            bank.new_session(self.root, "../unsafe")
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            bank.new_session(self.root, "first")

    def test_refuses_teacher_key_symlink(self):
        session = self.issue()
        key = session / "teacher.md"
        original = session / "original.md"
        key.rename(original)
        key.symlink_to(original)
        with self.assertRaisesRegex(ValueError, "regular owner-only files"):
            bank.resume_session(self.root, "first")


if __name__ == "__main__":
    unittest.main()
