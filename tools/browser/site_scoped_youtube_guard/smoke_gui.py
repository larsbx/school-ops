#!/usr/bin/env python3
"""Exercise the real Tkinter preparation/resume/deploy UI without policy writes."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from wizard import GuardWizard


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
    finally:
        app.destroy()
    print("Tkinter GUI smoke passed: prepare, resume frozen ZIP, attest publication, export, reopen and new version.")
    print("No policy, Chrome extension or device restriction was installed.")


if __name__ == "__main__":
    main()
