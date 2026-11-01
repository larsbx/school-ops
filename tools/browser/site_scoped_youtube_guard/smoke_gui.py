#!/usr/bin/env python3
"""Minimal real Tkinter flow check for an ephemeral test display (Xvfb).

This verifies the source GUI and review/export interactions, not a native
Windows/macOS binary or actual Chrome installation.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from wizard import GuardWizard


def main():
    app = GuardWizard()
    app.withdraw()
    try:
        assert app.index == 0, "Wizard must start at school site configuration"
        app.sites.insert("1.0", "portal.school.example\n")
        app.advance()
        assert app.index == 1, "Missing site -> access transition"
        app.mode.set("blacklist")
        app.block.insert("1.0", "social.example.net\n")
        app.advance()
        assert app.index == 2, "Missing access -> deployment transition"
        app.extension_id.set("")
        app.advance()
        assert app.index == 3, "Missing deployment -> review transition"
        summary = app.review.get("1.0", "end")
        assert "portal.school.example" in summary
        assert "Standalone YouTube: always BLOCKED" in summary
        assert "NOT GENERATED" in summary, "Unpublished extension must not have policy"

        with TemporaryDirectory(prefix="schoolops-gui-smoke-") as temp:
            bundle = Path(temp) / "prepared"
            app.output.set(str(bundle))
            with patch("wizard.messagebox.showinfo") as shown:
                app.advance()
                assert shown.called, "Export did not report its result"
            assert (bundle / "extension/manifest.json").exists()
            rules = json.loads((bundle / "extension/rules.json").read_text())
            assert rules[1]["condition"]["excludedTopDomains"] == ["portal.school.example"]
            assert not (bundle / "deployment/linux-managed-policy.json").exists()
    finally:
        app.destroy()
    print("Tkinter GUI smoke passed: four steps, explicit review and draft export.")
    print("No managed policy, Chrome extension, or device restriction was installed.")


if __name__ == "__main__":
    main()
