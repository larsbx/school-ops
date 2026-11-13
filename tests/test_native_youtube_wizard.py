"""Native SchoolOps wizard packaging contracts; no GUI or device install."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(ROOT))
import package_native as native  # noqa: E402
try:
    import wizard  # noqa: E402
except ImportError:
    # A curriculum-only CI runner may not include optional GUI/Tk libraries.
    # The dedicated native packaging jobs still require the actual GUI build.
    wizard = None


class NativeWizardTests(unittest.TestCase):
    @unittest.skipIf(wizard is None, "Optional tkinter GUI libraries not installed")
    def test_headless_source_self_test_exports_valid_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "smoke.json"
            wizard._package_self_test(target)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertFalse(report["frozen"])
            self.assertEqual(report["chromeMinimum"], "145")
            self.assertEqual(report["ruleCount"], 3)
            self.assertIn("NO GUI", report["scope"])
            with self.assertRaises(FileExistsError):
                wizard._package_self_test(target)

    def test_native_build_requires_explicit_platform_and_bundled_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            for system in ("Linux", "Darwin", "Windows"):
                with self.subTest(system=system):
                    args = native.build_command(sys.executable, scratch, system)
                    self.assertIn("--windowed", args)
                    self.assertIn("--clean", args)
                    self.assertIn("--add-data", args)
                    index = args.index("--add-data")
                    self.assertIn("manifest.json", args[index + 1])
                    self.assertTrue(args[-1].endswith("wizard.py"))
                    self.assertNotIn("--uac-admin", args)
                    self.assertIn("--onedir", args)
                    self.assertNotIn("--onefile", args)
                    program = native.packaged_executable(scratch, system)
                    self.assertIn(native.APP, str(program))
            with self.assertRaises(ValueError):
                native.build_command(sys.executable, scratch, "OtherOS")
            with self.assertRaises(ValueError):
                native.packaged_executable(scratch, "OtherOS")

    def test_checksum_is_content_based(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = Path(tmp) / "content.bin"
            item.write_bytes(b"schoolops")
            digest1 = native.sha256(item)
            self.assertEqual(len(digest1), 64)
            item.write_bytes(b"schoolops changed")
            self.assertNotEqual(digest1, native.sha256(item))

    def test_no_native_output_may_be_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "already-exists"
            folder.mkdir()
            with self.assertRaises(FileExistsError):
                native.package(folder)

    @unittest.skipIf(wizard is None, "Optional tkinter GUI libraries not installed")
    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required for release signing acceptance")
    def test_release_smoke_harness_exercises_source_cli_and_removes_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "smoke workspace with spaces"
            parent.mkdir()
            report = native.release_cli_smoke([sys.executable, ROOT / "wizard.py"], work_parent=parent)
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["commands"], {"key-id": "passed", "prepare": "passed",
                                                 "sign": "passed", "missing-key": "failed"})
            self.assertEqual(len(report["extensionId"]), 32)
            self.assertEqual(len(report["crxSha256"]), 64)
            self.assertFalse(report["privateKeysRetained"])
            self.assertFalse(report["policyApplied"])
            self.assertFalse(report["remotePublication"])
            self.assertEqual(list(parent.iterdir()), [], "Disposable signing credentials must be removed")

    def test_native_release_success_requires_report_and_matching_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "operation.json"
            with patch.object(native.subprocess, "run", return_value=Mock(returncode=0, stderr=b"")):
                with self.assertRaisesRegex(RuntimeError, "no operation report"):
                    native._release_cli_report(["unexecuted-native-fixture"], report, ["sign"])
            for exit_code, status in ((1, "passed"), (0, "failed"), (0, "running")):
                report.write_text(json.dumps({"schema": 1, "scope": "schoolops_release_operation",
                                              "command": "sign", "status": status}), encoding="utf-8")
                with self.subTest(exit_code=exit_code, status=status), \
                        patch.object(native.subprocess, "run",
                                     return_value=Mock(returncode=exit_code, stderr=b"")), \
                        self.assertRaisesRegex(RuntimeError, "expected passed"):
                    native._release_cli_report(["unexecuted-native-fixture"], report, ["sign"])


class FakeControl:
    def __init__(self, state="normal"):
        self.properties = {"state": state}

    def cget(self, name):
        return self.properties[name]

    def configure(self, **values):
        self.properties.update(values)


@unittest.skipIf(wizard is None, "Optional tkinter GUI libraries not installed")
class NativeWizardPolicyLifecycleTests(unittest.TestCase):
    """Exercise real lifecycle methods without a display or privileged process."""

    def setUp(self):
        methods = ("load_setup", "open_setup", "new_configuration", "resume_publication",
                   "request_close", "previous", "advance", "browse", "install_policy",
                   "_lock_policy_controls", "_restore_policy_controls", "_poll_policy")
        harness = type("HeadlessWizard", (), {name: getattr(wizard.GuardWizard, name) for name in methods})
        self.app = harness()
        self.app.index = 4
        self.app.bundle_path = (Path(tempfile.gettempdir()) / "schoolops-lifecycle-test-bundle").resolve()
        self.app.policy_process = None
        self.app.policy_operation = None
        self.app._policy_control_states = []
        self.control_names = ("open_button", "new_button", "prev", "next", "exit_button",
                              "apply_button", "remove_button", "publish_button")
        for name in self.control_names:
            setattr(self.app, name, FakeControl("disabled" if name == "publish_button" else "normal"))
        self.app.policy_status = FakeControl()
        self.app.install_summary = Mock()
        self.app._install_review = Mock()
        self.app.after = Mock()
        self.app.destroy = Mock()

    def pending(self, returncode=None, out="", err=""):
        process = Mock()
        process.poll.return_value = returncode
        process.returncode = returncode
        process.communicate.return_value = (out, err)
        self.app.policy_process = process
        self.app.policy_operation = {"bundle": self.app.bundle_path, "remove": False}
        self.app._lock_policy_controls()
        return process

    def assert_navigation_restored(self):
        for name in ("open_button", "new_button", "prev", "next", "exit_button"):
            self.assertEqual(getattr(self.app, name).cget("state"), "normal", name)
        self.assertIsNone(self.app.policy_process)
        self.assertIsNone(self.app.policy_operation)

    def test_pending_policy_guards_navigation_new_open_and_close(self):
        process = self.pending()
        original = self.app.bundle_path
        with (patch.object(wizard.filedialog, "askopenfilename") as ask_open,
              patch.object(wizard.filedialog, "askdirectory") as ask_directory,
              patch.object(wizard, "load_bundle") as load,
              patch.object(wizard.messagebox, "showinfo") as close_message):
            self.app.open_setup()
            self.app.load_setup("another/setup.json")
            self.app.new_configuration()
            self.app.resume_publication()
            self.app.previous()
            self.app.advance()
            self.app.browse()
            self.app.request_close()
            ask_open.assert_not_called()
            ask_directory.assert_not_called()
            load.assert_not_called()
            close_message.assert_called_once()
        self.assertEqual(self.app.bundle_path, original)
        self.assertEqual(self.app.index, 4)
        self.app.destroy.assert_not_called()
        process.terminate.assert_not_called()
        for name in self.control_names:
            self.assertEqual(getattr(self.app, name).cget("state"), "disabled", name)

    def test_launch_captures_the_bundle_and_locks_controls(self):
        process = Mock()
        with (patch.object(wizard, "verify_policy_bundle"),
              patch.object(wizard.platform, "system", return_value="Linux"),
              patch.object(wizard.os, "geteuid", return_value=0, create=True),
              patch.object(wizard.subprocess, "Popen", return_value=process) as launch):
            self.app.install_policy()
        self.assertEqual(self.app.policy_operation, {"bundle": self.app.bundle_path, "remove": False})
        self.assertIs(self.app.policy_process, process)
        self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        self.app.after.assert_called_once_with(250, self.app._poll_policy)
        for name in self.control_names:
            self.assertEqual(getattr(self.app, name).cget("state"), "disabled", name)

    def test_pending_poll_does_not_release_navigation(self):
        process = self.pending()
        self.app._poll_policy()
        process.communicate.assert_not_called()
        self.assertIs(self.app.policy_process, process)
        self.app.after.assert_called_once_with(250, self.app._poll_policy)
        self.assertEqual(self.app.exit_button.cget("state"), "disabled")

    def test_success_is_preserved_when_saved_bundle_disappears(self):
        original = self.app.bundle_path
        self.pending(0, "Local policy written. Chrome has not been verified.\n")
        self.app._install_review.side_effect = FileNotFoundError("saved bundle was removed")
        with patch.object(wizard.messagebox, "showerror") as show_error:
            self.app._poll_policy()
            show_error.assert_not_called()
        self.assert_navigation_restored()
        message = self.app.policy_status.properties["text"]
        self.assertIn(str(original), message)
        self.assertIn("Local policy written.", message)
        self.assertIn("could not recheck", message)
        self.assertEqual(self.app.apply_button.cget("state"), "disabled")
        self.assertEqual(self.app.remove_button.cget("state"), "disabled")
        self.app.request_close()
        self.app.destroy.assert_called_once()

    def test_completed_result_stays_bound_to_original_bundle(self):
        original = self.app.bundle_path
        self.pending(0, "Matching local policy is already configured.\n")
        # Defense in depth if external/programmatic state changes bypass UI guards.
        other = original.with_name("another-bundle")
        self.app.bundle_path = other
        self.app._poll_policy()
        self.assert_navigation_restored()
        self.assertEqual(self.app.bundle_path, other)
        self.app._install_review.assert_not_called()
        message = self.app.policy_status.properties["text"]
        self.assertIn(str(original), message)
        self.assertIn("currently selected bundle was not changed", message)

    def test_failed_action_restores_controls_and_reports_its_bundle(self):
        original = self.app.bundle_path
        self.pending(1, err="Administrator action cancelled")
        self.app.policy_operation["remove"] = True
        with patch.object(wizard.messagebox, "showerror") as show_error:
            self.app._poll_policy()
            show_error.assert_called_once()
            self.assertIn(str(original), show_error.call_args.args[1])
            self.assertIn("Remove policy", show_error.call_args.args[1])
        self.assert_navigation_restored()
        self.assertIn("cancelled", self.app.policy_status.properties["text"])
        self.assertEqual(self.app.apply_button.cget("state"), "normal")
        self.assertEqual(self.app.publish_button.cget("state"), "disabled")


if __name__ == "__main__":
    unittest.main()
