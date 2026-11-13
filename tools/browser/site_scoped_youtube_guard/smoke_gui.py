#!/usr/bin/env python3
"""Exercise the real Tkinter preparation/resume/deploy UI without policy writes."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import subprocess
import time
from types import SimpleNamespace

from wizard import GuardWizard
import release_core


def main():
    app = GuardWizard()
    app.withdraw()
    try:
        assert app.index == 0
        app.sites.insert("1.0", "portal.school.example\n")
        app.advance()
        assert app.index == 1
        app.mode.set("blacklist")
        app.block.insert("1.0", "social.example.net\n")
        app.advance()
        assert app.index == 2
        assert str(app.id_entry.cget("state")) == "disabled"
        app.advance()
        assert app.index == 3
        summary = app.review.get("1.0", "end")
        assert "portal.school.example" in summary
        assert "Standalone YouTube: always BLOCKED" in summary
        assert "NOT GENERATED" in summary

        with TemporaryDirectory(prefix="schoolops-gui-smoke-") as temp:
            prepared = Path(temp) / "prepared"
            app.output.set(str(prepared))
            with patch("wizard.subprocess.Popen") as launched:
                app.advance()
                assert app.index == 4
                assert not launched.called, "Export must never initiate policy application"
            assert (prepared / "extension.zip").exists()
            assert not (prepared / "deployment/linux-managed-policy.json").exists()
            assert str(app.apply_button.cget("state")) == "disabled"

            app.load_setup(prepared / "setup.json")
            assert app.index == 2
            assert str(app.sites.cget("state")) == "disabled"
            assert str(app.id_entry.cget("state")) == "normal"
            app.extension_id.set("abcdefghijklmnopabcdefghijklmnop")
            app.confirmed.set(True)
            app.update_url.set(app.update_url.get())
            assert not app.confirmed.get(), "Editing publication identity must clear attestation"
            app.confirmed.set(True)
            app.advance()
            assert app.index == 3
            final = Path(temp) / "deployment"
            app.output.set(str(final))
            with patch("wizard.subprocess.Popen") as launched:
                app.advance()
                assert app.index == 4
                assert not launched.called
            assert (final / "deployment/linux-managed-policy.json").exists()
            assert (final / "deployment/schoolops-chrome.mobileconfig").exists()
            assert (prepared / "extension.zip").read_bytes() == (final / "extension.zip").read_bytes()
            assert "Chrome installation: not verified" in app.install_summary.get("1.0", "end")
            rules = json.loads((final / "extension/rules.json").read_text())
            assert rules[1]["condition"]["excludedTopDomains"] == ["portal.school.example"]
            app.load_setup(final)
            assert app.index == 4
            app.previous()
            assert "portal.school.example" in app.review.get("1.0", "end")
            app.new_configuration()
            assert app.index == 0
            assert not app.prepared_digest and not app.extension_id.get()
            assert str(app.sites.cget("state")) == "normal"
            assert app.version.get() == "0.1.1"

            # Exercise the separate self-hosted flow with a real disposable public
            # key and signing contract. No private key is passed to the GUI and
            # the .example endpoints below are never contacted.
            app.channel.set("self_hosted")
            app._channel_changed()
            app.advance()
            app.advance()
            app.advance()
            hosted = Path(temp) / "hosted-prepared"
            app.output.set(str(hosted))
            app.advance()
            app.load_setup(hosted)
            assert app.index == 2
            assert str(app.id_entry.cget("state")) == "disabled"
            assert str(app.confirmation.cget("state")) == "disabled"
            assert str(app.channel_control.cget("state")) == "disabled"
            assert str(app.prepare_release_button.cget("state")) == "normal"
            assert str(app.verify_release_button.cget("state")) == "normal"
            private = Path(temp) / "disposable-fixture.key"
            public = Path(temp) / "disposable-fixture.pub"
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                            "-out", str(private)], check=True, capture_output=True, timeout=30)
            subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                           check=True, capture_output=True, timeout=30)
            release = Path(temp) / "hosted-release"
            options = {"public_key": str(public), "expected_id": release_core.public_key_id(public),
                       "expected_version": "0.1.1", "update_url": "https://updates.school.example/update.xml",
                       "crx_url": "https://updates.school.example/guard-0.1.1.crx",
                       "previous_release": None, "initial_release": True}
            with patch("wizard.ReleasePreparationDialog", return_value=SimpleNamespace(result=options)), \
                    patch("wizard.filedialog.asksaveasfilename", return_value=str(release)), \
                    patch("wizard.messagebox.showinfo") as prepared_message, \
                    patch("wizard.messagebox.showerror") as failure, \
                    patch("wizard.change_local_policy") as policy, \
                    patch.object(app, "copy_text") as copied:
                app.prepare_self_hosted_release()
                assert app.release_operation is not None
                assert str(app.open_button.cget("state")) == "disabled"
                deadline = time.monotonic() + 30
                while app.release_operation is not None and time.monotonic() < deadline:
                    app.update()
                    time.sleep(0.01)
                assert app.release_operation is None, "Public-key release preparation did not finish"
                failure.assert_not_called()
                policy.assert_not_called()
                prepared_message.assert_called_once()
                copied.assert_called_once()
                assert "--report" in copied.call_args.args[0]
            assert app.release_path == release
            assert release_core.load_release(release)["extension_id"] == options["expected_id"]
            assert not (hosted / "deployment/linux-managed-policy.json").exists()
            assert not (release / "extension.crx").exists(), "Preparation must not sign by itself"
            assert str(app.channel_control.cget("state")) == "disabled"
    finally:
        app.destroy()
    print("Tkinter GUI smoke passed: Web Store prepare/resume/export; self-hosted locked controls, "
          "disposable public-key release preparation and asynchronous recovery.")
    print("No policy, Chrome extension or device restriction was installed.")


if __name__ == "__main__":
    main()
