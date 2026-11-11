#!/usr/bin/env python3
"""SchoolOps YouTube Guard: graphical deployment wizard (Python 3 + Tkinter)."""
import platform
from pathlib import Path
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from installer_core import (ROOT, WEBSTORE_URL, change_local_policy, export_bundle,
                            load_bundle, publication_ready, validate_settings,
                            verify_policy_bundle)


def release_command(*arguments):
    """Reuse the installed app for release commands; no shell is executed."""
    command = [str(Path(sys.executable).resolve())]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve()))
    return [*command, "--release", *map(str, arguments)]


def display_command(arguments):
    return (subprocess.list2cmdline(arguments) if platform.system() == "Windows"
            else shlex.join(arguments))


class ReleasePreparationDialog(simpledialog.Dialog):
    """Collect reviewed public inputs; signing keys never enter the GUI."""
    def __init__(self, parent, *, extension_id, extension_version, update_url):
        self.defaults = {"public_key": "", "expected_id": extension_id,
                         "expected_version": extension_version, "update_url": update_url,
                         "crx_url": "", "previous_release": ""}
        self.values = {}
        super().__init__(parent, "Prepare self-hosted release")

    def body(self, parent):
        ttk.Label(parent, text="Use a public RSA key and the exact release URLs. Signing happens "
                  "separately. This action creates local release files and uploads nothing.",
                  wraplength=660).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        labels = (("public_key", "Public key file (PEM or DER)"),
                  ("expected_id", "Expected extension ID (32 letters a–p)"),
                  ("expected_version", "Prepared extension version"),
                  ("update_url", "HTTPS update manifest URL"),
                  ("crx_url", "HTTPS CRX URL unique to this version"),
                  ("previous_release", "Previous release folder (required for an update)"))
        for row, (name, label) in enumerate(labels, 1):
            ttk.Label(parent, text=label).grid(row=row * 2 - 1, column=0, columnspan=3, sticky="w")
            variable = self.values[name] = tk.StringVar(value=self.defaults[name])
            entry = ttk.Entry(parent, textvariable=variable, width=78)
            entry.grid(row=row * 2, column=0, columnspan=2, sticky="ew", pady=(2, 7))
            if name == "expected_version":
                entry.configure(state="readonly")
            if name in ("public_key", "previous_release"):
                ttk.Button(parent, text="Browse…", command=lambda key=name: self.browse(key)).grid(
                    row=row * 2, column=2, padx=(6, 0))
        self.initial_release = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, variable=self.initial_release,
            text="This is the first release for this signing identity; no previous release exists.").grid(
                row=13, column=0, columnspan=3, sticky="w", pady=(6, 4))
        ttk.Label(parent, text="For a first release, use the release CLI's key-id command to obtain "
                  "and review the public key's extension ID. Updates must retain the recorded ID "
                  "and increase the version.", wraplength=660).grid(row=14, column=0, columnspan=3,
                                                                    sticky="w", pady=(4, 0))

    def browse(self, name):
        if name == "public_key":
            path = filedialog.askopenfilename(parent=self, title="Select public RSA key only")
        else:
            path = filedialog.askdirectory(parent=self, title="Select the previous release folder")
        if path:
            self.values[name].set(path)

    def validate(self):
        values = {name: value.get().strip() for name, value in self.values.items()}
        if any(not values[name] for name in ("public_key", "expected_id", "expected_version",
                                             "update_url", "crx_url")):
            messagebox.showerror("Missing release input", "Fill in the public key, ID, version and both HTTPS URLs.",
                                 parent=self)
            return False
        if self.initial_release.get() == bool(values["previous_release"]):
            messagebox.showerror("Choose release history", "Select either a previous release folder or "
                                 "the explicit first-release confirmation.", parent=self)
            return False
        self.result = {**values, "previous_release": values["previous_release"] or None,
                       "initial_release": self.initial_release.get()}
        return True


def detect_os():
    return {
        "Windows": "windows",
        "Darwin": "macos",
        "Linux": "linux",
    }.get(platform.system(), "linux")


def policy_command(bundle, remove=False):
    """Argument vector only: no shell interpolation or execution-policy bypass."""
    command = [str(Path(sys.executable).resolve())]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve()))
    return [*command, "--remove-policy" if remove else "--apply-policy", str(Path(bundle).resolve())]


def _policy_cli(bundle, remove=False):
    """The separately elevated process owns the write and reports its real result."""
    code = 0
    try:
        status = change_local_policy(bundle, remove)
        descriptions = {
            "installed": "Local policy written.",
            "already_configured": "Matching local policy is already configured.",
            "removed": "This installer's local policy was removed.",
            "already_absent": "This installer's local policy is already absent.",
            "not_owned": "Policy was not created by this installer. Nothing was removed.",
        }
        message = descriptions[status] + "\nCheck chrome://policy and chrome://extensions. Chrome has not been verified."
        if status == "not_owned":
            code = 1
    except (ValueError, OSError, RuntimeError) as exc:
        message, code = str(exc), 1
    if platform.system() == "Windows":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "SchoolOps local policy", 0x10 if code else 0x40)
    elif sys.stdout is not None:
        print(message, file=sys.stderr if code else sys.stdout)
    return code


class GuardWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SchoolOps | YouTube Guard Setup")
        self.geometry("820x720")
        self.minsize(780, 690)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.index = 0
        self.pages = []
        self.labels = ["School websites", "Access rules", "Publication", "Review & export", "Install & verify"]
        self.mode = tk.StringVar(value="blacklist")
        self.channel = tk.StringVar(value="web_store")
        self.extension_id = tk.StringVar(value="")
        self.update_url = tk.StringVar(value=WEBSTORE_URL)
        self.target_os = tk.StringVar(value=detect_os())
        self.version = tk.StringVar(value=json.loads((ROOT / "manifest.json").read_text())["version"])
        self.confirmed = tk.BooleanVar(value=False)
        self.extension_id.trace_add("write", self._publication_identity_changed)
        self.update_url.trace_add("write", self._publication_identity_changed)
        self.prepared_digest = ""
        self.bundle_path = None
        self.config_widgets = []
        self.policy_process = None
        self.policy_operation = None
        self._policy_control_states = []
        self.release_operation = None
        self.release_path = None
        self.publication_receipt = None
        self._release_control_states = []
        self.output = tk.StringVar(value=str(Path.home() / "schoolops-youtube-guard-deployment"))

        top = ttk.Frame(self, padding=(18, 12))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="SchoolOps · Site-Scoped YouTube Guard",
                  font=("TkDefaultFont", 17, "bold")).pack(anchor="w")
        self.progress = ttk.Label(top)
        self.progress.pack(anchor="w", pady=(6, 0))
        toolbar = ttk.Frame(top)
        toolbar.pack(fill="x", pady=(10, 0))
        self.open_button = ttk.Button(toolbar, text="Open prepared setup…", command=self.open_setup)
        self.open_button.pack(side="left")
        self.new_button = ttk.Button(toolbar, text="New configuration", command=self.new_configuration)
        self.new_button.pack(side="left", padx=8)

        holder = ttk.Frame(self, padding=(18, 8))
        holder.grid(row=1, column=0, sticky="nsew")
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        for builder in (self._sites, self._access, self._deployment, self._finish, self._install):
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
        self.exit_button = ttk.Button(bottom, text="Exit", command=self.request_close)
        self.exit_button.pack(side="right", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self.request_close)
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
        self.config_widgets.append(self.sites)
        ttk.Label(page, text="No actual school website is pre-approved. "
                  "The wizard does not collect student accounts or passwords.",
                  wraplength=690).pack(anchor="w", pady=12)

    def _access(self, page):
        self._heading(page, "Website access mode",
                      "Both modes always deny direct YouTube browsing. "
                      "The lists below control other top-level sites.")
        for label, value in (("Blacklist — allow most sites, block selected domains", "blacklist"),
                             ("Whitelist — block most sites, permit approved domains", "whitelist")):
            control = ttk.Radiobutton(page, text=label, variable=self.mode, value=value)
            control.pack(anchor="w")
            self.config_widgets.append(control)
        self.allow = self._input(page, "Additional ordinary websites to allow (whitelist mode):", 3)
        self.block = self._input(page, "Ordinary websites to block (blacklist or whitelist mode):", 3)
        self.config_widgets.extend([self.allow, self.block])
        ttk.Label(page, text="Use one hostname per line. The school portals from step 1 "
                  "are allowed automatically in whitelist mode.",
                  wraplength=690).pack(anchor="w", pady=(9, 0))

    def _deployment(self, page):
        self._heading(page, "Prepare once, then connect your published extension",
                      "Export the extension ZIP, then reopen its saved setup. The Web Store route "
                      "uses your publication confirmation. Self-hosting verifies the signed CRX "
                      "and HTTPS update manifest before exporting policy.")
        ttk.Label(page, text="Extension version (increase for a changed published configuration)").pack(anchor="w")
        version = ttk.Entry(page, textvariable=self.version, width=18)
        version.pack(anchor="w", pady=(3, 9))
        self.config_widgets.append(version)
        ttk.Label(page, text="Operating system").pack(anchor="w")
        self.target_os_control = ttk.Combobox(page, state="readonly", textvariable=self.target_os,
                     values=("windows", "linux", "macos", "chromeos"), width=16)
        self.target_os_control.pack(anchor="w", pady=(3, 9))
        ttk.Label(page, text="Distribution channel").pack(anchor="w")
        self.channel_control = ttk.Combobox(page, state="readonly", textvariable=self.channel,
                               values=("web_store", "self_hosted"), width=27)
        self.channel_control.pack(anchor="w", pady=(3, 9))
        self.channel_control.bind("<<ComboboxSelected>>", self._channel_changed)
        ttk.Label(page, text="Published extension ID (32 a-p characters; leave empty to prepare)").pack(
            anchor="w")
        self.id_entry = ttk.Entry(page, textvariable=self.extension_id, width=48, state="disabled")
        self.id_entry.pack(anchor="w", pady=(3, 9))
        ttk.Label(page, text="Update manifest URL (must be hosted before deployment)").pack(anchor="w")
        self.update_url_entry = ttk.Entry(page, textvariable=self.update_url, width=77)
        self.update_url_entry.pack(fill="x", pady=(3, 6))
        self.confirmation = ttk.Checkbutton(page, variable=self.confirmed, state="disabled",
            text="I published the exact prepared extension ZIP under this ID and update source.")
        self.confirmation.pack(anchor="w", pady=(10, 0))
        self.publication_note = ttk.Label(page, text="Export a prepared bundle first. Open its setup.json after publication.",
                                         wraplength=740, foreground="#52655f")
        self.publication_note.pack(anchor="w", pady=(8, 0))
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(12, 0))
        self.prepare_release_button = ttk.Button(row, text="Prepare self-hosted release…",
                                                command=self.prepare_self_hosted_release,
                                                state="disabled")
        self.prepare_release_button.pack(side="left")
        self.verify_release_button = ttk.Button(row, text="Verify HTTPS & export…",
                                               command=self.verify_self_hosted_release,
                                               state="disabled")
        self.verify_release_button.pack(side="left", padx=8)
        self.release_status = ttk.Label(page, text="", wraplength=740, foreground="#52655f")
        self.release_status.pack(anchor="w", pady=(8, 0))

    def _channel_changed(self, _event=None):
        self.confirmed.set(False)
        self.publication_receipt = None
        self.release_path = None
        if self.channel.get() == "web_store":
            self.update_url.set(WEBSTORE_URL)
        elif self.update_url.get() == WEBSTORE_URL:
            self.update_url.set("")
        self._publication_controls()

    def _publication_identity_changed(self, *_args):
        self.confirmed.set(False)
        self.publication_receipt = None

    def _publication_controls(self):
        prepared = bool(self.prepared_digest)
        hosted = self.channel.get() == "self_hosted"
        self.id_entry.configure(state="normal" if prepared and not hosted else "disabled")
        self.confirmation.configure(state="normal" if prepared and not hosted else "disabled")
        self.target_os_control.configure(state="readonly")
        self.update_url_entry.configure(state="disabled" if prepared and hosted else "normal")
        state = "normal" if prepared and hosted else "disabled"
        self.prepare_release_button.configure(state=state)
        self.verify_release_button.configure(state=state)

    def prepare_self_hosted_release(self):
        if self.policy_process is not None or self.release_operation is not None or not self.bundle_path:
            return
        if self.channel.get() != "self_hosted":
            return
        dialog = ReleasePreparationDialog(self, extension_id=self.extension_id.get(),
            extension_version=self.version.get(), update_url=self.update_url.get())
        if not dialog.result:
            return
        destination = filedialog.asksaveasfilename(parent=self, title="New local release folder",
            initialdir=str(self.bundle_path.parent), initialfile=self.bundle_path.name + "-release")
        if not destination:
            return
        from release_core import prepare_release
        bundle = self.bundle_path
        options = dict(dialog.result)
        self._start_release_operation("prepare", lambda: prepare_release(bundle, destination, **options))

    def verify_self_hosted_release(self):
        if self.policy_process is not None or self.release_operation is not None or not self.bundle_path:
            return
        if self.channel.get() != "self_hosted":
            return
        release = filedialog.askdirectory(parent=self, title="Select prepared and signed release folder",
            initialdir=str(self.release_path or self.bundle_path.parent))
        if not release:
            return
        destination = filedialog.asksaveasfilename(parent=self, title="New verified deployment folder",
            initialdir=str(self.bundle_path.parent), initialfile=self.bundle_path.name + "-verified")
        if not destination:
            return
        try:
            from release_core import export_verified_deployment, load_release
            plan = load_release(release)
        except (ValueError, OSError, RuntimeError) as exc:
            messagebox.showerror("Cannot verify release", str(exc), parent=self)
            return
        if not messagebox.askyesno("Verify this publication?",
                "Download and verify these exact HTTPS resources, then export a local deployment bundle:\n\n"
                + plan["update_url"] + "\n" + plan["crx_url"] + "\n\nExtension ID: "
                + plan["extension_id"] + "\nVersion: " + plan["extension_version"]
                + "\n\nNo extension will be installed and no policy will be changed.", parent=self):
            return
        bundle = self.bundle_path
        target_os = self.target_os.get()
        self._start_release_operation("verify", lambda: export_verified_deployment(
            bundle, release, destination, target_os=target_os))

    def _start_release_operation(self, kind, action):
        """Run bounded local/HTTPS work off the Tk thread, bound to this bundle."""
        if self.policy_process is not None or self.release_operation is not None:
            return
        results = queue.Queue(maxsize=1)
        self.release_operation = {"kind": kind, "bundle": Path(self.bundle_path).resolve(), "results": results}
        controls = (self.open_button, self.new_button, self.prev, self.next, self.exit_button,
                    self.apply_button, self.remove_button, self.publish_button,
                    self.prepare_release_button, self.verify_release_button, self.channel_control,
                    self.id_entry, self.confirmation, self.target_os_control, self.update_url_entry)
        self._release_control_states = [(control, control.cget("state")) for control in controls]
        for control, _state in self._release_control_states:
            control.configure(state="disabled")
        self.release_status.configure(text="Preparing local release…" if kind == "prepare" else
                                     "Checking the HTTPS manifest and signed package…")

        def work():
            try:
                result = (True, action())
            except Exception as exc:
                result = (False, str(exc))
            results.put(result)

        threading.Thread(target=work, name="schoolops-release", daemon=True).start()
        self.after(100, self._poll_release)

    def _poll_release(self):
        operation = self.release_operation
        if operation is None:
            return
        try:
            success, result = operation["results"].get_nowait()
        except queue.Empty:
            self.after(100, self._poll_release)
            return
        self.release_operation = None
        for control, state in self._release_control_states:
            control.configure(state=state)
        self._release_control_states = []
        if not success:
            self.release_status.configure(text="Release action failed: " + result)
            messagebox.showerror("Release action failed", result, parent=self)
            return
        current = Path(self.bundle_path).resolve() if self.bundle_path is not None else None
        if current != operation["bundle"]:
            self.release_status.configure(text="Release result saved for " + str(operation["bundle"])
                + ": " + str(result) + ". The currently selected setup was not changed.")
            return
        if operation["kind"] == "prepare":
            self.release_path = Path(result)
            report = self.release_path.with_name(self.release_path.name + "-signing-result.json")
            command = display_command(release_command("--report", report,
                                                      "sign", result, "--key", "SIGNING_KEY.pem"))
            self.release_status.configure(text="Local release prepared: " + str(result)
                + "\nSign separately, review the publication plan, then use Verify HTTPS & export.")
            self.copy_text(command)
            messagebox.showinfo("Release prepared; signing command copied",
                "Release folder:\n" + str(result) + "\n\nSigning command:\n" + command
                + "\n\nRead the command result in:\n" + str(report)
                + "\n\nReplace SIGNING_KEY.pem with your approved signing key location in a terminal. "
                "The GUI does not collect private keys. Review the release publication plan before "
                "any production upload. Publication and managed-device changes need separate approval.", parent=self)
        else:
            try:
                self.load_setup(result)
            except (ValueError, OSError, KeyError) as exc:
                self.release_status.configure(text="Verified deployment saved at " + str(result)
                    + ", but reopening failed: " + str(exc))
                messagebox.showerror("Could not reopen verified deployment", str(exc), parent=self)
                return
            self.policy_status.configure(text="Exact HTTPS release bytes verified; receipt saved. "
                "Policy application and managed Chrome installation remain unverified.")

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

    def _install(self, page):
        self._heading(page, "Install and check Chrome",
                      "Your saved bundle can be reused on each intended device. Apply the policy, "
                      "then verify the extension and website behavior in Chrome.")
        self.install_summary = tk.Text(page, height=10, wrap="word", state="disabled")
        self.install_summary.pack(fill="both", expand=True)
        row = ttk.Frame(page)
        row.pack(fill="x", pady=12)
        ttk.Button(row, text="Open setup guide", command=self.open_guide).pack(side="left")
        ttk.Button(row, text="Open bundle folder", command=self.open_folder).pack(side="left", padx=8)
        self.publish_button = ttk.Button(row, text="Enter published ID…", command=self.resume_publication)
        self.publish_button.pack(side="left")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(0, 12))
        self.apply_button = ttk.Button(row, text="Install policy (administrator)", command=self.install_policy)
        self.apply_button.pack(side="left")
        self.remove_button = ttk.Button(row, text="Remove local policy", command=lambda: self.install_policy(True))
        self.remove_button.pack(side="left", padx=8)
        self.policy_status = ttk.Label(page, text="Policy application: not checked", wraplength=740)
        self.policy_status.pack(anchor="w", pady=8)
        ttk.Label(page, text="Paste these addresses into Chrome. Browser security prevents a setup page "
                  "from opening them automatically.", wraplength=740).pack(anchor="w")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=8)
        for address in ("chrome://policy", "chrome://extensions"):
            ttk.Button(row, text="Copy " + address,
                       command=lambda value=address: self.copy_text(value)).pack(side="left", padx=(0, 8))

    def copy_text(self, value):
        self.clipboard_clear()
        self.clipboard_append(value)

    def _set_lock(self, locked):
        for control in self.config_widgets:
            control.configure(state="disabled" if locked else "normal")
        self.channel_control.configure(state="disabled" if locked else "readonly")
        self._publication_controls()

    def load_setup(self, path):
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        root, settings = load_bundle(path)
        self._set_lock(False)
        for control, key in ((self.sites, "allowed_embed_sites"), (self.allow, "allowed_sites"),
                             (self.block, "blocked_sites")):
            control.delete("1.0", "end")
            control.insert("1.0", "\n".join(settings[key]))
        for variable, key in ((self.mode, "mode"), (self.channel, "channel"),
                              (self.extension_id, "extension_id"), (self.update_url, "update_url"),
                              (self.target_os, "target_os"), (self.version, "extension_version"),
                              (self.confirmed, "publication_confirmed")):
            variable.set(settings[key])
        self.prepared_digest = settings["published_extension_sha256"]
        self.publication_receipt = settings.get("publication_receipt")
        self.release_path = None
        self.bundle_path = root
        self.output.set(str(root.with_name(root.name + "-deployment")))
        self.publication_note.configure(text="Prepared configuration locked · ZIP SHA-256: " + self.prepared_digest)
        self._set_lock(True)
        self.index = 4 if settings["extension_id"] else 2
        if self.index == 4:
            self._install_review()
        self._show()

    def open_setup(self):
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        path = filedialog.askopenfilename(parent=self, title="Open the prepared bundle's setup.json",
                                          filetypes=[("SchoolOps setup", "setup.json")])
        if path:
            try:
                self.load_setup(path)
            except (ValueError, OSError, KeyError) as exc:
                messagebox.showerror("Cannot open setup", str(exc), parent=self)

    def new_configuration(self):
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        if self.prepared_digest:
            parts = [int(part) for part in self.version.get().split(".")]
            if parts[-1] < 65535:
                parts[-1] += 1
                self.version.set(".".join(map(str, parts)))
        self._set_lock(False)
        self.prepared_digest = ""
        self.publication_receipt = None
        self.release_path = None
        self.extension_id.set("")
        self.confirmed.set(False)
        self.bundle_path = None
        self._publication_controls()
        self.release_status.configure(text="")
        self.publication_note.configure(text="Export a prepared bundle first. Open its setup.json after publication.")
        self.index = 0
        self._show()

    def resume_publication(self):
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        if self.bundle_path:
            self.load_setup(self.bundle_path)
            self.index = 2
            self._show()

    def _install_review(self):
        _root, settings = load_bundle(self.bundle_path)
        published = bool(settings["extension_id"])
        same_os = settings["target_os"] == detect_os()
        local = published and same_os and platform.system() in ("Windows", "Linux")
        legacy_hosted = (settings["channel"] == "self_hosted" and published
                         and not settings.get("publication_receipt"))
        publication = ("Exact HTTPS release bytes observed; saved receipt available" if
                       settings.get("publication_receipt") else
                       "Operator-confirmed; remote package not verified" if published else
                       "Awaiting publication")
        summary = ["Bundle: " + str(self.bundle_path),
                   "Website configuration and extension ZIP: verified",
                   "Extension version: " + settings["extension_version"],
                   "Extension ID: " + (settings["extension_id"] or "awaiting publication"),
                   "Target: " + settings["target_os"],
                   "Publication: " + publication,
                   "Policy: " + ("HTTPS verification required before a new installation" if legacy_hosted else
                                  "ready to apply" if published else "awaiting publication"),
                   "Chrome installation: not verified", "Website behavior: not verified", "",
                   ("Use Install policy here, or your organization's policy console." if local else
                    "Open the setup guide for publication or platform-specific management steps.")]
        self.install_summary.configure(state="normal")
        self.install_summary.delete("1.0", "end")
        self.install_summary.insert("1.0", "\n".join(summary))
        self.install_summary.configure(state="disabled")
        self.apply_button.configure(state="normal" if local and not legacy_hosted else "disabled")
        self.remove_button.configure(state="normal" if local else "disabled")
        self.publish_button.configure(state="normal" if not published or legacy_hosted else "disabled")
        self.policy_status.configure(text="Policy application: not checked")

    def open_guide(self):
        if self.bundle_path:
            webbrowser.open((self.bundle_path / "START_HERE.html").as_uri())

    def open_folder(self):
        if not self.bundle_path:
            return
        try:
            if platform.system() == "Windows":
                os.startfile(str(self.bundle_path))
            else:
                subprocess.Popen(["open" if platform.system() == "Darwin" else "xdg-open", str(self.bundle_path)])
        except OSError as exc:
            messagebox.showerror("Cannot open folder", str(exc), parent=self)

    def request_close(self):
        if getattr(self, "release_operation", None) is not None:
            messagebox.showinfo("Release check still running",
                "Wait for the release action to finish. Setup will show its result before "
                "closing; no administrator action is involved.", parent=self)
            return
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            messagebox.showinfo("Policy action still running",
                "Finish or cancel the administrator prompt first. Setup will show the policy "
                "action's result before you close this window.", parent=self)
            return
        self.destroy()

    def _lock_policy_controls(self):
        controls = (self.open_button, self.new_button, self.prev, self.next,
                    self.exit_button, self.apply_button, self.remove_button, self.publish_button)
        controls += tuple(getattr(self, name) for name in ("prepare_release_button", "verify_release_button")
                          if hasattr(self, name))
        self._policy_control_states = [(control, control.cget("state")) for control in controls]
        for control, _state in self._policy_control_states:
            control.configure(state="disabled")

    def _restore_policy_controls(self):
        for control, state in self._policy_control_states:
            control.configure(state=state)
        self._policy_control_states = []

    def install_policy(self, remove=False):
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        try:
            operation_bundle = Path(self.bundle_path).resolve()
            verify_policy_bundle(operation_bundle, allow_legacy_self_hosted=remove)
            args = policy_command(operation_bundle, remove)
            if remove and not messagebox.askyesno("Remove this local policy?",
                    "Remove only this installer's unchanged policy. Verify Chrome afterward. "
                    "Policies controlled by your management console must be removed there.", parent=self):
                return
            if platform.system() == "Windows":
                import ctypes
                # A new PyInstaller process must not inherit the parent's
                # bootloader/extraction lifecycle when the main window closes.
                previous_reset = os.environ.get("PYINSTALLER_RESET_ENVIRONMENT")
                os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                try:
                    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", args[0],
                        subprocess.list2cmdline(args[1:]), None, 1)
                finally:
                    if previous_reset is None:
                        os.environ.pop("PYINSTALLER_RESET_ENVIRONMENT", None)
                    else:
                        os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = previous_reset
                if result <= 32:
                    raise OSError("Windows did not start the administrator action (it may have been cancelled)")
                self.policy_status.configure(text="Administrator action opened. Its result appears in a separate window; "
                                            "then check Chrome policies and the installed extension.")
            elif platform.system() == "Linux":
                if os.geteuid() == 0:
                    launch = args
                elif shutil.which("pkexec"):
                    launch = ["pkexec", *args]
                else:
                    command = shlex.join(["sudo", *args])
                    self.copy_text(command)
                    messagebox.showinfo("Administrator terminal command copied",
                        "This desktop has no pkexec prompt. Paste this command in a terminal:\n\n" + command,
                        parent=self)
                    return
                self.policy_process = subprocess.Popen(launch, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"})
                self.policy_operation = {"bundle": operation_bundle, "remove": remove}
                self._lock_policy_controls()
                self.policy_status.configure(text="Waiting for the administrator policy action…\nBundle: "
                                             + str(self.policy_operation["bundle"]))
                self.after(250, self._poll_policy)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Policy action could not start", str(exc), parent=self)

    def _poll_policy(self):
        if self.policy_process is None:
            return
        if self.policy_process.poll() is None:
            self.after(250, self._poll_policy)
            return
        process, operation = self.policy_process, self.policy_operation
        try:
            out, err = process.communicate()
        except (OSError, UnicodeError) as exc:
            out, err = "", "Could not read the policy action's output: " + str(exc)
        finally:
            self.policy_process = None
            self.policy_operation = None
            self._restore_policy_controls()

        action = "Remove policy" if operation["remove"] else "Install policy"
        result = ((err or out or "Administrator action failed or was cancelled").strip()
                  if process.returncode else
                  (out or err or "Policy action exited successfully; no detailed result was returned.").strip())
        result = action + " — " + str(operation["bundle"]) + "\n" + result
        try:
            current = Path(self.bundle_path).resolve() if self.bundle_path is not None else None
            if current == operation["bundle"]:
                self._install_review()
            else:
                result += "\nThis result belongs to the bundle above; the currently selected bundle was not changed."
        except (ValueError, OSError, KeyError, TypeError) as exc:
            # Refresh failure must not erase or mislabel the actual child result.
            for control in (self.apply_button, self.remove_button, self.publish_button):
                control.configure(state="disabled")
            self.install_summary.configure(state="normal")
            self.install_summary.delete("1.0", "end")
            self.install_summary.insert("1.0", "The saved bundle could not be rechecked. "
                "Reopen a valid setup before another policy action.\n" + str(exc))
            self.install_summary.configure(state="disabled")
            result += "\nThe policy action finished, but Setup could not recheck its saved bundle: " + str(exc)
        self.policy_status.configure(text=result)
        if process.returncode:
            messagebox.showerror("Policy action failed", result, parent=self)

    @staticmethod
    def _lines(widget):
        return [line.strip() for line in widget.get("1.0", "end").splitlines() if line.strip()]

    def _settings(self):
        settings = {
            "allowed_embed_sites": self._lines(self.sites),
            "mode": self.mode.get(),
            "allowed_sites": self._lines(self.allow),
            "blocked_sites": self._lines(self.block),
            "channel": self.channel.get(),
            "extension_id": self.extension_id.get().strip(),
            "update_url": self.update_url.get().strip(),
            "target_os": self.target_os.get(),
            "extension_version": self.version.get().strip(),
            "publication_confirmed": self.confirmed.get(),
            "published_extension_sha256": self.prepared_digest,
        }
        if self.publication_receipt is not None:
            settings["publication_receipt"] = self.publication_receipt
        return settings

    def _review(self):
        checked = validate_settings(self._settings())
        if checked["extension_id"]:
            publication_ready(checked)
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
            "Extension version: " + checked["extension_version"],
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
        self.progress.configure(text=f"Step {self.index + 1} of 5 — {self.labels[self.index]}")
        self.prev.configure(state="normal" if self.index else "disabled")
        self.next.configure(text={3: "Export deployment bundle", 4: "Finish"}.get(self.index, "Next"))

    def previous(self):
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        if self.index > 0:
            if self.index - 1 == 3:
                try:
                    self._review()
                except ValueError as exc:
                    messagebox.showerror("Publication verification required", str(exc), parent=self)
                    return
            self.index -= 1
            self._show()

    def advance(self):
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        if self.index == 4:
            self.request_close()
            return
        if self.index == 3:
            try:
                path = export_bundle(self._settings(), self.output.get())
            except (ValueError, FileExistsError, OSError) as exc:
                messagebox.showerror("Cannot export", str(exc), parent=self)
                return
            self.bundle_path = path
            self._install_review()
            self.index = 4
            self._show()
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
        if self.policy_process is not None or getattr(self, "release_operation", None) is not None:
            return
        path = filedialog.askdirectory(parent=self, title="Choose bundle parent folder")
        if path:
            self.output.set(str(Path(path) / "schoolops-youtube-guard-deployment"))


def _package_self_test(report_path):
    """Exercise packaged data and export without opening a GUI or changing policy."""
    from installer_core import ROOT, export_bundle
    import release_core
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
        if manifest != source_manifest:
            raise RuntimeError("Packaged extension manifest differs from source")
        if manifest.get("minimum_chrome_version") != "145":
            raise RuntimeError("Unsupported Chrome version")
        if rules[0]["condition"].get("resourceTypes") != ["main_frame"]:
            raise RuntimeError("Direct YouTube navigation rule missing")
        if rules[1]["condition"].get("excludedTopDomains") != ["portal.school.example"]:
            raise RuntimeError("Scoped YouTube embed rule missing")
        if (bundle / "deployment/linux-managed-policy.json").exists():
            raise RuntimeError("An unpublished extension must not generate managed policy")
        release_settings = release_core._archive_settings((bundle / "extension.zip").read_bytes())
        if release_settings["extension_version"] != manifest["version"]:
            raise RuntimeError("Packaged release parser did not preserve the prepared ZIP version")
        _root, published = load_bundle(bundle)
        published.update(extension_id="abcdefghijklmnopabcdefghijklmnop", publication_confirmed=True)
        final = export_bundle(published, Path(temp) / "published")
        verify_policy_bundle(final)
        if (bundle / "extension.zip").read_bytes() != (final / "extension.zip").read_bytes():
            raise RuntimeError("Publication changed the prepared extension ZIP")
    report = {
        "status": "passed",
        "scope": "Packaged application and release modules, prepared ZIP parsing, "
                 "draft/resume/policy bundle generation; NO GUI, "
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
    if len(sys.argv) >= 3 and sys.argv[1] == "--release":
        import release_core
        sys.argv = ["schoolops-release", *sys.argv[2:]]
        release_core.main()
    elif len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        _package_self_test(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--apply-linux" and platform.system() != "Linux":
        raise SystemExit("--apply-linux is only supported on Linux")
    elif len(sys.argv) == 3 and sys.argv[1] in ("--apply-policy", "--apply-linux", "--remove-policy"):
        raise SystemExit(_policy_cli(sys.argv[2], sys.argv[1] == "--remove-policy"))
    elif len(sys.argv) != 1:
        raise SystemExit("Usage: Setup [--self-test REPORT | --release COMMAND ... | "
                         "--apply-policy BUNDLE | --remove-policy BUNDLE]")
    else:
        GuardWizard().mainloop()
