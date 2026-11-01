"""Regression tests for the fail-closed CI impact planner."""
import tempfile
import unittest
from pathlib import Path

from impact import load_policy, matches, plan


POLICY = load_policy()


class ImpactPlanningTests(unittest.TestCase):
    def test_documentation_changes_select_repository_link_validation(self):
        decision = plan(POLICY, ["docs/guide.md", "README.md"])
        self.assertEqual(decision["mode"], "targeted")
        self.assertEqual(decision["suites"], ["teaching"])

    def test_documentation_with_unknown_path_falls_back_to_full(self):
        decision = plan(POLICY, ["README.md", "unknown.new"])
        self.assertEqual(decision["mode"], "full")

    def test_bank_change_includes_downstream_teaching(self):
        decision = plan(POLICY, ["exercise_bank/generator.py"])
        self.assertEqual(decision["suites"], ["bank", "teaching"])

    def test_curriculum_change_includes_dependents_transitively(self):
        decision = plan(POLICY, ["curriculum/scaffolds/islamic_studies.md"])
        self.assertEqual(decision["suites"], ["bank", "curriculum", "teaching"])

    def test_installer_change_includes_native(self):
        decision = plan(POLICY, ["tools/browser/site_scoped_youtube_guard/installer_core.py"])
        self.assertEqual(decision["suites"], ["installer", "native"])

    def test_browser_rule_change_includes_installer_and_native(self):
        decision = plan(POLICY, ["tools/browser/site_scoped_youtube_guard/build_rules.py"])
        self.assertEqual(decision["suites"], ["guard", "installer", "native"])

    def test_unmapped_path_runs_every_suite(self):
        decision = plan(POLICY, ["tools/browser/new_feature.py"])
        self.assertEqual(decision["mode"], "full")
        self.assertEqual(decision["unknown_paths"], ["tools/browser/new_feature.py"])
        self.assertEqual(decision["suites"], sorted(POLICY["suites"]))

    def test_critical_change_runs_every_suite(self):
        decision = plan(POLICY, [".github/workflows/exercise-bank.yml"])
        self.assertEqual(decision["mode"], "full")
        self.assertEqual(decision["suites"], sorted(POLICY["suites"]))

    def test_mixed_documentation_and_unknown_fails_closed(self):
        decision = plan(POLICY, ["README.md", "new-root-file"])
        self.assertEqual(decision["mode"], "full")

    def test_scheduled_full(self):
        decision = plan(POLICY, [], force_full=True)
        self.assertEqual(decision["mode"], "full")
        self.assertEqual(decision["suites"], sorted(POLICY["suites"]))

    def test_empty_delta_is_only_policy_smoke(self):
        decision = plan(POLICY, [])
        self.assertEqual(decision["suites"], [])

    def test_directory_pattern_root_and_descendants(self):
        self.assertTrue(matches("docs", "docs/**"))
        self.assertTrue(matches("docs/a/b.md", "docs/**"))
        self.assertFalse(matches("document.txt", "docs/**"))

    def test_invalid_policy_fails_instead_of_skipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "policy.json"
            target.write_text('{"version":99}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_policy(target)

    def test_new_unregistered_test_is_rejected_by_policy_validation(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ci").mkdir()
            (root / "tests").mkdir()
            (root / "tests" / "test_future_module.py").write_text(
                "import unittest\n", encoding="utf-8"
            )
            config = root / "ci" / "policy.json"
            config.write_text(json.dumps(POLICY), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unregistered test modules"):
                load_policy(config)

    def test_dependency_cycle_fails_instead_of_skipping(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "policy.json"
            broken = json.loads(json.dumps(POLICY))
            broken["components"]["curriculum"]["depends_on"] = ["teaching"]
            target.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cycle"):
                load_policy(target)


if __name__ == "__main__":
    unittest.main()
