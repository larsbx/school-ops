"""Read-only device-policy wizard action contract with no GUI display or OS writes."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(ROOT))
try:
    import wizard
except ImportError:
    wizard = None


@unittest.skipIf(wizard is None, "Optional tkinter GUI libraries not installed")
class LocalPolicyButtonTests(unittest.TestCase):
    def setUp(self):
        harness = type("HeadlessPolicyCheck", (), {
            "check_local_policy": wizard.GuardWizard.check_local_policy
        })
        self.app = harness()
        self.app.policy_process = None
        self.app.release_operation = None
        self.app.bundle_path = Path("/fixture/approved-bundle")
        self.app.policy_status = Mock()

    def test_matches_local_policy_only_never_browser_enforcement(self):
        report = {"local_policy_status": "matching"}
        with patch.object(wizard, "check_device_bundle", return_value=report) as observed, \
             patch.object(wizard, "format_device_result",
                          return_value="Local policy matches. Chrome is UNVERIFIED."):
            self.app.check_local_policy()
        observed.assert_called_once_with(self.app.bundle_path)
        text = self.app.policy_status.configure.call_args.kwargs["text"]
        self.assertIn("Read-only", text)
        self.assertIn("UNVERIFIED", text)

    def test_invalid_bundle_reports_failure_instead_of_success(self):
        with patch.object(wizard, "check_device_bundle",
                          side_effect=ValueError("Bundle changed")):
            self.app.check_local_policy()
        msg = self.app.policy_status.configure.call_args.kwargs["text"]
        self.assertIn("could not be inspected", msg)
        self.assertIn("UNVERIFIED", msg)

    def test_pending_policy_or_release_action_prevents_readback(self):
        for condition in ("policy_process", "release_operation", "bundle_path"):
            with self.subTest(condition=condition):
                setattr(self.app, condition, None if condition == "bundle_path" else object())
                with patch.object(wizard, "check_device_bundle") as observed:
                    self.app.check_local_policy()
                    observed.assert_not_called()
                self.app.policy_status.configure.assert_not_called()
                self.app.bundle_path = Path("/fixture/approved-bundle")
                self.app.policy_process = None
                self.app.release_operation = None


if __name__ == "__main__":
    unittest.main()
