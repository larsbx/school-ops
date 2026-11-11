"""Release GUI lifecycle contracts; no network, private keys or device writes."""
import queue
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

GUARD_ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(GUARD_ROOT))
try:
    import wizard
except ImportError:
    wizard = None


class Control:
    def __init__(self, state="normal"):
        self.properties = {"state": state}

    def cget(self, key):
        return self.properties[key]

    def configure(self, **values):
        self.properties.update(values)


@unittest.skipIf(wizard is None, "Optional tkinter GUI libraries not installed")
class ReleaseWizardTests(unittest.TestCase):
    def setUp(self):
        methods = ("_start_release_operation", "_poll_release", "load_setup", "open_setup",
                   "new_configuration", "resume_publication", "request_close", "previous",
                   "advance", "browse", "install_policy", "_publication_identity_changed")
        harness = type("HeadlessReleaseWizard", (), {
            name: getattr(wizard.GuardWizard, name) for name in methods})
        self.app = harness()
        self.app.index = 2
        self.app.bundle_path = Path(tempfile.gettempdir()) / "schoolops-prepared-release-fixture"
        self.app.policy_process = None
        self.app.release_operation = None
        self.app._release_control_states = []
        self.controls = ("open_button", "new_button", "prev", "next", "exit_button",
                         "apply_button", "remove_button", "publish_button", "prepare_release_button",
                         "verify_release_button", "channel_control", "id_entry", "confirmation")
        self.controls += ("target_os_control", "update_url_entry")
        for name in self.controls:
            setattr(self.app, name, Control("disabled" if name == "apply_button" else "normal"))
        self.app.release_status = Control()
        self.app.policy_status = Control()
        self.app.after = Mock()
        self.app.copy_text = Mock()
        self.app.destroy = Mock()
        self.app.confirmed = Mock()
        self.app.publication_receipt = {"scope": "downloaded_release_bytes"}

    def pending(self, kind="verify"):
        messages = queue.Queue()
        self.app.release_operation = {"kind": kind, "bundle": self.app.bundle_path.resolve(),
                                      "results": messages}
        self.app._release_control_states = [(getattr(self.app, name), getattr(self.app, name).cget("state"))
                                           for name in self.controls]
        for control, _state in self.app._release_control_states:
            control.configure(state="disabled")
        return messages

    def test_release_commands_preserve_paths_as_separate_arguments(self):
        folder = Path(tempfile.gettempdir()) / "release folder;not a command"
        arguments = wizard.release_command("sign", folder, "--key", "PUBLICLY_UNSPECIFIED_KEY.pem")
        self.assertEqual(arguments[-5:], ["--release", "sign", str(folder), "--key",
                                         "PUBLICLY_UNSPECIFIED_KEY.pem"])
        self.assertNotIn("--apply-policy", arguments)
        with patch.object(wizard.sys, "frozen", True, create=True):
            frozen = wizard.release_command("verify", folder)
            self.assertEqual(frozen[1:], ["--release", "verify", str(folder)])

    def test_identity_edits_clear_observation_and_store_attestation(self):
        self.app._publication_identity_changed()
        self.app.confirmed.set.assert_called_once_with(False)
        self.assertIsNone(self.app.publication_receipt)

    def test_release_worker_runs_off_ui_thread_and_locks_actions(self):
        entered = threading.Event()
        finish = threading.Event()
        worker_ids = []

        def task():
            worker_ids.append(threading.get_ident())
            entered.set()
            if not finish.wait(5):
                raise RuntimeError("fixture synchronization timed out")
            return "release-output"

        self.app._start_release_operation("prepare", task)
        self.assertTrue(entered.wait(5))
        self.assertNotEqual(worker_ids, [threading.get_ident()])
        self.assertEqual(self.app.release_operation["bundle"], self.app.bundle_path.resolve())
        for name in self.controls:
            self.assertEqual(getattr(self.app, name).cget("state"), "disabled")
        self.app.after.assert_called_once_with(100, self.app._poll_release)
        finish.set()
        success, result = self.app.release_operation["results"].get(timeout=5)
        self.assertTrue(success)
        self.assertEqual(result, "release-output")

    def test_pending_release_guards_navigation_policy_new_open_and_close(self):
        self.pending()
        before = self.app.bundle_path
        with patch.object(wizard.filedialog, "askopenfilename") as ask_open, \
                patch.object(wizard.filedialog, "askdirectory") as ask_directory, \
                patch.object(wizard, "load_bundle") as load, \
                patch.object(wizard, "verify_policy_bundle") as policy, \
                patch.object(wizard.messagebox, "showinfo") as close_message:
            self.app.open_setup()
            self.app.load_setup("another/setup.json")
            self.app.new_configuration()
            self.app.resume_publication()
            self.app.previous()
            self.app.advance()
            self.app.browse()
            self.app.install_policy()
            self.app.request_close()
            ask_open.assert_not_called()
            ask_directory.assert_not_called()
            load.assert_not_called()
            policy.assert_not_called()
            close_message.assert_called_once()
        self.assertEqual(self.app.bundle_path, before)
        self.app.destroy.assert_not_called()

    def test_failed_download_restores_controls_without_policy_or_bundle_change(self):
        messages = self.pending()
        before = self.app.bundle_path
        messages.put((False, "HTTPS package download failed"))
        with patch.object(wizard.messagebox, "showerror") as error, \
                patch.object(wizard, "change_local_policy") as policy:
            self.app._poll_release()
            error.assert_called_once()
            policy.assert_not_called()
        self.assertIsNone(self.app.release_operation)
        self.assertEqual(self.app.bundle_path, before)
        self.assertEqual(self.app.apply_button.cget("state"), "disabled")
        self.assertEqual(self.app.open_button.cget("state"), "normal")
        self.assertIn("download failed", self.app.release_status.properties["text"])

    def test_pending_poll_preserves_lock_and_reschedules(self):
        self.pending()
        self.app._poll_release()
        self.assertIsNotNone(self.app.release_operation)
        self.assertEqual(self.app.open_button.cget("state"), "disabled")
        self.app.after.assert_called_once_with(100, self.app._poll_release)

    def test_completed_result_cannot_replace_different_current_bundle(self):
        messages = self.pending()
        original = self.app.bundle_path
        self.app.bundle_path = original.with_name("different-prepared-configuration")
        self.app.load_setup = Mock()
        messages.put((True, original.with_name("verified-output")))
        self.app._poll_release()
        self.app.load_setup.assert_not_called()
        self.assertIn(str(original), self.app.release_status.properties["text"])
        self.assertIn("not changed", self.app.release_status.properties["text"])

    def test_success_reopens_verified_deployment_without_installing_policy(self):
        messages = self.pending()
        output = self.app.bundle_path.with_name("verified-output")
        self.app.load_setup = Mock()
        messages.put((True, output))
        with patch.object(wizard, "change_local_policy") as policy:
            self.app._poll_release()
            policy.assert_not_called()
        self.app.load_setup.assert_called_once_with(output)
        self.assertIn("remain unverified", self.app.policy_status.properties["text"])

    def test_preparation_copies_separate_signing_command_with_reviewable_report(self):
        messages = self.pending(kind="prepare")
        output = self.app.bundle_path.with_name("release folder")
        report = output.with_name(output.name + "-signing-result.json")
        messages.put((True, output))
        with patch.object(wizard.messagebox, "showinfo") as info, \
                patch.object(wizard, "change_local_policy") as policy:
            self.app._poll_release()
            policy.assert_not_called()
            info.assert_called_once()
            self.assertIn(str(report), info.call_args.args[1])
        self.assertEqual(self.app.release_path, output)
        self.app.copy_text.assert_called_once_with(wizard.display_command(wizard.release_command(
            "--report", report, "sign", output, "--key", "SIGNING_KEY.pem")))


if __name__ == "__main__":
    unittest.main()
