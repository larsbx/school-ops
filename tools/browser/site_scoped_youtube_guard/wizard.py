#!/usr/bin/env python3
"""SchoolOps YouTube Guard: graphical deployment wizard (Python 3 + Tkinter)."""
import platform
from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from installer_core import WEBSTORE_URL, export_bundle, validate_settings


def detect_os():
    return {
        "Windows": "windows",
        "Darwin": "macos",
        "Linux": "linux",
    }.get(platform.system(), "linux")


class GuardWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SchoolOps | YouTube Guard Setup")
        self.geometry("760x580")
        self.minsize(660, 510)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.index = 0
        self.pages = []
        self.labels = ["School websites", "Access rules", "Managed deployment", "Review & export"]
        self.mode = tk.StringVar(value="blacklist")
        self.channel = tk.StringVar(value="web_store")
        self.extension_id = tk.StringVar(value="")
        self.update_url = tk.StringVar(value=WEBSTORE_URL)
        self.target_os = tk.StringVar(value=detect_os())
        self.output = tk.StringVar(value=str(Path.home() / "schoolops-youtube-guard-deployment"))

        top = ttk.Frame(self, padding=(18, 12))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="SchoolOps · Site-Scoped YouTube Guard",
                  font=("TkDefaultFont", 17, "bold")).pack(anchor="w")
        self.progress = ttk.Label(top)
        self.progress.pack(anchor="w", pady=(6, 0))

        holder = ttk.Frame(self, padding=(18, 8))
        holder.grid(row=1, column=0, sticky="nsew")
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        for builder in (self._sites, self._access, self._deployment, self._finish):
            page = ttk.Frame(holder)
            page.grid(row=0, column=0, sticky="nsew")
            page.columnconfigure(0, weight=1)
            builder(page)
            self.pages.append(page)

        bottom = ttk.Frame(self, padding=(18, 12))
        bottom.grid(row=2, column=0, sticky="ew")
        self.prev = ttk.Button(bottom, text="Back", command=self.previous)
        self.prev.pack(side="left")
        self.next = ttk.Button(bottom, text="Next", command=self.advance)
        self.next.pack(side="right")
        ttk.Button(bottom, text="Exit", command=self.destroy).pack(side="right", padx=(0, 8))
        self._show()

    def _heading(self, parent, title, detail):
        ttk.Label(parent, text=title, font=("TkDefaultFont", 13, "bold")).pack(
            anchor="w", pady=(5, 9))
        ttk.Label(parent, text=detail, wraplength=690,
                  justify="left").pack(anchor="w", pady=(0, 14))

    def _input(self, parent, title, height=4):
        ttk.Label(parent, text=title).pack(anchor="w", pady=(7, 3))
        widget = tk.Text(parent, height=height, undo=True, wrap="none")
        widget.pack(fill="x", expand=False)
        return widget

    def _sites(self, page):
        self._heading(page, "Approved school websites",
                      "Enter hostnames only, one per line (for example portal.school.org). "
                      "Embedded YouTube may play on these sites. YouTube itself is never "
                      "an allowed main website. Subdomains of listed hosts are included.")
        self.sites = self._input(page, "School portal hostnames:", 6)
        ttk.Label(page, text="No actual school website is pre-approved. "
                  "The wizard does not collect student accounts or passwords.",
                  wraplength=690).pack(anchor="w", pady=12)

    def _access(self, page):
        self._heading(page, "Website access mode",
                      "Both modes always deny direct YouTube browsing. "
                      "The lists below control other top-level sites.")
        ttk.Radiobutton(page, text="Blacklist — allow most sites, block selected domains",
                        variable=self.mode, value="blacklist").pack(anchor="w")
        ttk.Radiobutton(page, text="Whitelist — block most sites, permit approved domains",
                        variable=self.mode, value="whitelist").pack(anchor="w")
        self.allow = self._input(page, "Additional ordinary websites to allow (whitelist mode):", 3)
        self.block = self._input(page, "Ordinary websites to block (blacklist or whitelist mode):", 3)
        ttk.Label(page, text="Use one hostname per line. The school portals from step 1 "
                  "are allowed automatically in whitelist mode.",
                  wraplength=690).pack(anchor="w", pady=(9, 0))

    def _deployment(self, page):
        self._heading(page, "Managed Chrome deployment",
                      "The wizard prepares an extension package and administrator policy. "
                      "It cannot publish a Chrome extension, enroll a device, or make an "
                      "unmanaged browser tamper-resistant.")
        ttk.Label(page, text="Operating system").pack(anchor="w")
        ttk.Combobox(page, state="readonly", textvariable=self.target_os,
                     values=("windows", "linux", "macos", "chromeos"),
                     width=16).pack(anchor="w", pady=(3, 9))
        ttk.Label(page, text="Distribution channel").pack(anchor="w")
        channel = ttk.Combobox(page, state="readonly", textvariable=self.channel,
                               values=("web_store", "self_hosted"), width=27)
        channel.pack(anchor="w", pady=(3, 9))
        channel.bind("<<ComboboxSelected>>", self._channel_changed)
        ttk.Label(page, text="Published extension ID (32 a-p characters; leave empty for draft)").pack(
            anchor="w")
        ttk.Entry(page, textvariable=self.extension_id, width=48).pack(anchor="w", pady=(3, 9))
        ttk.Label(page, text="Update manifest URL (must be hosted before deployment)").pack(anchor="w")
        ttk.Entry(page, textvariable=self.update_url, width=77).pack(
            fill="x", pady=(3, 6))
        ttk.Label(page, text="Without a real extension ID, the wizard exports a draft "
                  "for publishing but deliberately generates NO force-install policy. "
                  "Re-run this wizard after publication to finalize the policy.",
                  wraplength=690, foreground="#666666").pack(anchor="w", pady=(12, 0))

    def _channel_changed(self, _event=None):
        if self.channel.get() == "web_store":
            self.update_url.set(WEBSTORE_URL)
        elif self.update_url.get() == WEBSTORE_URL:
            self.update_url.set("")

    def _finish(self, page):
        self._heading(page, "Review and export",
                      "The bundle contains the configured extension, a checked rule set, "
                      "deployment guidance and SHA-256 checksums. Only published IDs "
                      "produce a managed Chrome policy; exporting alone installs nothing.")
        self.review = tk.Text(page, height=13, wrap="word", state="disabled")
        self.review.pack(fill="both", expand=True)
        ttk.Label(page, text="Destination folder (must not already exist):").pack(
            anchor="w", pady=(11, 4))
        row = ttk.Frame(page)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.output).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self.browse).pack(side="left", padx=(8, 0))

    @staticmethod
    def _lines(widget):
        return [line.strip() for line in widget.get("1.0", "end").splitlines() if line.strip()]

    def _settings(self):
        return {
            "allowed_embed_sites": self._lines(self.sites),
            "mode": self.mode.get(),
            "allowed_sites": self._lines(self.allow),
            "blocked_sites": self._lines(self.block),
            "channel": self.channel.get(),
            "extension_id": self.extension_id.get().strip(),
            "update_url": self.update_url.get().strip(),
            "target_os": self.target_os.get(),
        }

    def _review(self):
        checked = validate_settings(self._settings())
        cfg = checked["config"]
        summary = [
            "Approved school sites: " + ", ".join(cfg["allowed_embed_sites"]),
            "Website mode: " + cfg["mode"],
            "Extra allowed: " + (", ".join(cfg["allowed_sites"]) or "(none)"),
            "Blocked: " + (", ".join(cfg["blocked_sites"]) or "(none)"),
            "Standalone YouTube: always BLOCKED",
            "Off-site YouTube embeds: BLOCKED (browser validation needed)",
            "Target: " + checked["target_os"],
            "Publishing: " + checked["channel"],
            "Extension ID: " + (checked["extension_id"] or "(not published — draft only)"),
            "Managed policy: " + ("GENERATED — admin must deploy it" if checked["extension_id"]
                                   else "NOT GENERATED — extension ID required"),
            "Device restrictions: NOT VERIFIED",
        ]
        self.review.configure(state="normal")
        self.review.delete("1.0", "end")
        self.review.insert("1.0", "\n".join(summary))
        self.review.configure(state="disabled")

    def _show(self):
        self.pages[self.index].tkraise()
        self.progress.configure(text=f"Step {self.index + 1} of 4 — {self.labels[self.index]}")
        self.prev.configure(state="normal" if self.index else "disabled")
        self.next.configure(text="Export deployment bundle" if self.index == 3 else "Next")

    def previous(self):
        if self.index > 0:
            self.index -= 1
            self._show()

    def advance(self):
        if self.index == 3:
            try:
                path = export_bundle(self._settings(), self.output.get())
            except (ValueError, FileExistsError, OSError) as exc:
                messagebox.showerror("Cannot export", str(exc), parent=self)
                return
            messagebox.showinfo("Bundle created — not yet installed",
                                f"Created: {path}\n\nOpen deployment/README.md for the "
                                "administrator deployment steps. Verify Chrome policies "
                                "and playback separately.", parent=self)
            return
        if self.index == 2:
            try:
                self._review()
            except ValueError as exc:
                messagebox.showerror("Check your configuration", str(exc), parent=self)
                return
        self.index += 1
        self._show()

    def browse(self):
        path = filedialog.askdirectory(parent=self, title="Choose bundle parent folder")
        if path:
            self.output.set(str(Path(path) / "schoolops-youtube-guard-deployment"))


def _package_self_test(report_path):
    """Exercise packaged data and export without opening a GUI or changing policy."""
    from installer_core import ROOT, export_bundle
    config = {
        "allowed_embed_sites": ["portal.school.example"],
        "mode": "blacklist",
        "allowed_sites": [],
        "blocked_sites": ["social.example.net"],
        "extension_id": "",
        "channel": "web_store",
        "update_url": WEBSTORE_URL,
        "target_os": detect_os(),
    }
    with TemporaryDirectory(prefix="schoolops-wizard-selftest-") as temp:
        bundle = export_bundle(config, Path(temp) / "deployment")
        manifest = json.loads((bundle / "extension/manifest.json").read_text(encoding="utf-8"))
        rules = json.loads((bundle / "extension/rules.json").read_text(encoding="utf-8"))
        source_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        assert manifest == source_manifest, "Packaged manifest changed"
        assert manifest["minimum_chrome_version"] == "145", "Unsupported Chrome version"
        assert rules[0]["condition"]["resourceTypes"] == ["main_frame"]
        assert rules[1]["condition"]["excludedTopDomains"] == ["portal.school.example"]
        assert not (bundle / "deployment/linux-managed-policy.json").exists(), (
            "An unpublished extension must not generate managed policy"
        )
    report = {
        "status": "passed",
        "scope": "Packaged application data and draft bundle generation; NO GUI, "
                 "Chrome, signed extension or managed-device installation tested",
        "frozen": bool(getattr(sys, "frozen", False)),
        "chromeMinimum": manifest["minimum_chrome_version"],
        "ruleCount": len(rules),
    }
    path = Path(report_path)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite self-test report: {path}")
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        _package_self_test(sys.argv[2])
    elif len(sys.argv) != 1:
        raise SystemExit("Usage: wizard.py [--self-test /path/to/new/report.json]")
    else:
        GuardWizard().mainloop()
