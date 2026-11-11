#!/usr/bin/env python3
"""Prepare, resume and apply a SchoolOps Chrome deployment.

Publication is an operator attestation about the exact prepared ZIP. Neither a
checksum nor a policy write proves remote publication or Chrome enforcement.
"""
import argparse
import hashlib
from html import escape
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import tempfile
from urllib.parse import urlsplit
import zipfile

from build_rules import build, domains, overlaps, YOUTUBE_PAGE_DOMAINS
import platform_policy

ROOT = Path(__file__).resolve().parent
WEBSTORE_URL = "https://clients2.google.com/service/update2/crx"
CHROME_ID = re.compile(r"[a-p]{32}\Z")
LINUX_MANAGED_PATH = platform_policy.LINUX_MANAGED_PATH
EXTENSION_PATHS = {"extension/manifest.json", "extension/rules.json", "extension/config.json"}


def pretty_json(value):
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def read_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def validate_version(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){0,3}", value):
        raise ValueError("Extension version must be 1–4 dot-separated integers without leading zeros")
    parts = [int(part) for part in value.split(".")]
    if not any(parts) or any(part > 65535 for part in parts):
        raise ValueError("Extension version components must be 0–65535 and not all zero")
    return value


def validate_settings(raw):
    """Normalize settings before any output; this does not verify publication."""
    if not isinstance(raw, dict):
        raise ValueError("Installer settings must be an object")
    cfg = {
        "allowed_embed_sites": domains(raw.get("allowed_embed_sites", [])),
        "mode": raw.get("mode", "blacklist"),
        "allowed_sites": domains(raw.get("allowed_sites", [])),
        "blocked_sites": domains(raw.get("blocked_sites", [])),
    }
    rules = build(cfg)
    if any(d.endswith(".invalid") or d == "invalid" for d in cfg["allowed_embed_sites"]):
        raise ValueError("Replace the example .invalid site with the actual school hostname")
    extension_id = str(raw.get("extension_id", "")).strip().lower()
    if extension_id and not CHROME_ID.fullmatch(extension_id):
        raise ValueError("A published extension ID must have exactly 32 letters a-p")
    channel = raw.get("channel", "web_store")
    if channel not in ("web_store", "self_hosted"):
        raise ValueError("Select Chrome Web Store or managed self-hosted distribution")
    update_url = str(raw.get("update_url", "")).strip()
    if channel == "web_store":
        if update_url != WEBSTORE_URL:
            raise ValueError("Web Store installations must use the Chrome Web Store update URL")
    elif extension_id:
        parsed = urlsplit(update_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment or
                any(ord(c) < 33 for c in update_url) or
                parsed.hostname in ("localhost", "127.0.0.1") or update_url == WEBSTORE_URL):
            raise ValueError("Self-hosted updates require your own HTTPS update manifest URL")
        if not parsed.path or parsed.path == "/":
            raise ValueError("Provide a complete HTTPS URL to your update manifest")
    target_os = raw.get("target_os", "linux")
    if target_os not in ("linux", "windows", "macos", "chromeos"):
        raise ValueError("Choose Linux, Windows, macOS or ChromeOS")
    if any(overlaps(d, yt) for d in cfg["allowed_embed_sites"] for yt in YOUTUBE_PAGE_DOMAINS):
        raise ValueError("YouTube itself cannot be an approved school site")
    source_manifest = read_json((ROOT / "manifest.json").read_bytes())
    return {
        "config": cfg, "rules": rules, "extension_id": extension_id,
        "channel": channel, "update_url": update_url, "target_os": target_os,
        "extension_version": validate_version(raw.get("extension_version", source_manifest["version"])),
        "published_extension_sha256": raw.get("published_extension_sha256", ""),
        "publication_confirmed": raw.get("publication_confirmed") is True,
    }


def extension_files(checked):
    manifest = read_json((ROOT / "manifest.json").read_bytes())
    if manifest.get("minimum_chrome_version") != "145":
        raise ValueError("Unexpected Chrome minimum version: review manifest")
    manifest["version"] = checked["extension_version"]
    return {
        "extension/manifest.json": pretty_json(manifest).encode("utf-8"),
        "extension/rules.json": pretty_json(checked["rules"]).encode("utf-8"),
        "extension/config.json": pretty_json(checked["config"]).encode("utf-8"),
    }


def extension_zip(files):
    """Stable ZIP bytes across OSes, with manifest at its root for Store upload."""
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(EXTENSION_PATHS):
            info = zipfile.ZipInfo(name.removeprefix("extension/"), (2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])
    return result.getvalue()


def extension_digest(checked):
    return hashlib.sha256(extension_zip(extension_files(checked))).hexdigest()


def publication_ready(checked):
    if not checked["extension_id"]:
        raise ValueError("Cannot issue force-install policy before publication provides an extension ID")
    if not checked["publication_confirmed"]:
        raise ValueError("Confirm publication of the exact prepared extension ZIP before generating policy")
    if checked["published_extension_sha256"] != extension_digest(checked):
        raise ValueError("Published extension fingerprint differs: reopen the prepared setup.json; "
                         "changed websites or version require a new publication")


def policy_document(checked):
    publication_ready(checked)
    entry = {"installation_mode": "force_installed", "update_url": checked["update_url"]}
    if checked["channel"] == "self_hosted":
        entry["override_update_url"] = True
    return {"ExtensionSettings": {checked["extension_id"]: entry}}


def extension_settings_value(checked):
    return policy_document(checked)["ExtensionSettings"]


def flat_settings(checked):
    return {**checked["config"], **{key: checked[key] for key in (
        "extension_id", "channel", "update_url", "target_os", "extension_version",
        "published_extension_sha256", "publication_confirmed")}}


def deployment_notes(checked):
    published = bool(checked["extension_id"])
    platform_notes = {
        "linux": "Open this bundle in the Setup app and choose Install policy (administrator). "
                 "Linux needs pkexec for the graphical elevation prompt, or run the displayed sudo command. "
                 "The installer refuses conflicting ExtensionSettings in other managed JSON files.",
        "windows": "Open this bundle in the Setup app, choose Install policy (administrator), and accept "
                   "Windows UAC. The installer merges this ID into HKLM's 64-bit ExtensionSettings value; "
                   "unrelated entries are preserved. GPO/cloud-managed environments should instead merge "
                   "deployment/extension-settings-value.json in the authoritative policy console.",
        "macos": "Import deployment/schoolops-chrome.mobileconfig in your MDM as a computer-level profile. "
                 "If Chrome already has ExtensionSettings, merge the supplied value in that existing "
                 "profile instead of deploying a competing profile. Local profile installation alone "
                 "does not establish enterprise enrollment.",
        "chromeos": "In Google Admin: Devices > Chrome > Apps & extensions > Users & browsers, select the "
                    "intended organizational unit, add the extension by ID/update source, set Force install, "
                    "and Save. Device enrollment and policy scope are configured in that console.",
    }
    return "\n".join([
        "# SchoolOps Chrome setup", "", "Status: NOT INSTALLED.",
        ("POLICY READY: publication is operator-confirmed, not remotely verified." if published else
         "PUBLISHING PENDING: no extension ID; no install policy was created."), "",
        "Target platform: " + checked["target_os"],
        "Extension version: " + checked["extension_version"],
        "Extension ZIP SHA-256: " + extension_digest(checked),
        "Extension ID: " + (checked["extension_id"] or "pending publication"),
        "Distribution: " + checked["channel"],
        "Update manifest: " + checked["update_url"],
        "Approved embedding hosts: " + ", ".join(checked["config"]["allowed_embed_sites"]),
        "Browsing mode: " + checked["config"]["mode"], "",
        "## 1. Prepare and publish once", "",
        "Upload extension.zip to your Chrome Web Store developer account, or sign the exact extension/ "
        "contents for your managed self-hosted channel. Preserve the signing key and extension ID. "
        "The ZIP is an upload package, not an installable signed CRX. No Store listing is created here.",
        "Reopen setup.json in the Setup app, enter the published ID/update URL, confirm that you published "
        "this exact configuration, and export to a new folder. The ZIP fingerprint prevents accidental "
        "configuration drift; it does not authenticate the remote publisher.",
        "For later website changes, choose New configuration, increase the version, publish the new build "
        "under the same extension ID/signing key, and prepare a new deployment. Existing devices update "
        "through the chosen publishing channel. Static website settings are not storage.managed policies.", "",
        "## 2. Install the enterprise policy", "", platform_notes[checked["target_os"]], "",
        "For self-hosting, the HTTPS update URL must serve XML identifying the signed CRX, matching "
        "extension ID and version. The CRX/update URL must work without browser session cookies. "
        "Windows requires Active Directory/Azure AD join or Chrome Enterprise Core enrollment; "
        "macOS requires MDM/MCX management or Chrome Enterprise Core enrollment. The local installer "
        "does not enroll a device. Prefer the Web Store route when those prerequisites are absent.", "",
        "## 3. Verify in Chrome 145+", "",
        "- Open chrome://policy, Reload policies, and confirm ExtensionSettings has Status OK and the expected ID/source.",
        "- Open chrome://extensions, verify the exact ID/version and managed/force-installed status on a standard-user account.",
        "- Verify approved-portal YouTube playback, direct/new-tab YouTube blocking and off-site embed blocking.",
        "- Restart Chrome and repeat. Check separate device controls if other browsers/apps/admin access are in scope.",
        "Bundle checks, policy application, installed extension and browser behavior are separate results.", "",
        "## Remove this local policy", "",
        "Reopen this same deployment bundle and choose Remove local policy. Windows/Linux removal requires "
        "the installer's machine-level ownership receipt and an unchanged matching policy. Other Chrome settings are "
        "preserved. If policy was applied through GPO/MDM/Admin Console, remove it there instead. "
        "Removal changes the force-install policy; check Chrome separately for extension removal.", "",
        "## References", "",
        "https://support.google.com/chrome/a/answer/9867568",
        "https://support.google.com/chrome/a/answer/9027408",
        "https://support.google.com/chrome/a/answer/6306504",
        "https://developer.chrome.com/docs/extensions/how-to/distribute/host-on-linux", "",
    ])


def start_page(checked):
    published = bool(checked["extension_id"])
    status = "Ready to apply policy" if published else "Ready to publish your extension"
    action = ("Reopen setup.json in the SchoolOps Setup app and choose Install policy. "
              "For macOS or ChromeOS, follow the managed deployment instructions below." if published else
              "Publish extension.zip using your Chrome Web Store developer account or managed "
              "self-hosted channel. Then reopen setup.json and enter the published extension ID.")
    policy_links = ("<li><a href='deployment/extension-settings-value.json'>ExtensionSettings for GPO/MDM</a></li>"
                    "<li><a href='deployment/linux-managed-policy.json'>Linux managed policy</a></li>"
                    "<li><a href='deployment/schoolops-chrome.mobileconfig'>macOS management profile</a></li>"
                    if published else "")
    return f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SchoolOps · Chrome setup</title>
<style>body{{font:17px/1.6 system-ui,sans-serif;max-width:850px;margin:3rem auto;padding:0 1.3rem;color:#16302d;background:#f5f8f7}}h1{{line-height:1.2}}.card{{background:white;border:1px solid #d5dfdc;border-radius:12px;padding:1.4rem;margin:1rem 0}}code{{overflow-wrap:anywhere}}a{{color:#075e50}}pre{{white-space:pre-wrap;font:inherit}}.label{{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#4f6862}}</style>
<p class="label">SchoolOps / Chrome setup</p><h1>{status}</h1>
<p>{escape(action)}</p><div class="card"><strong>Your configuration</strong>
<p>Chrome 145+ · {escape(checked['target_os'])} · version {escape(checked['extension_version'])}<br>
School websites: {escape(', '.join(checked['config']['allowed_embed_sites']))}<br>
Browsing mode: {escape(checked['config']['mode'])}<br>
Extension ID: <code>{escape(checked['extension_id'] or 'Awaiting publication')}</code></p>
<p class="label">Exact extension ZIP fingerprint</p><code>{extension_digest(checked)}</code></div>
<div class="card"><h2>Your setup files</h2><ul>
<li><a href="extension.zip">Extension ZIP for publication</a></li>
<li><a href="setup.json">Saved setup — reopen in the Setup app</a></li>{policy_links}
<li><a href="deployment/README.md">Administrator instructions</a></li></ul></div>
<div class="card"><h2>Installation checks</h2><p>Exported files are ready. Policy application, Chrome installation and website behavior still need checking.</p>
<ol><li>Apply policy through the Setup app or your management console.</li>
<li>In Chrome, open <code>chrome://policy</code>, reload, and check Status OK.</li>
<li>Open <code>chrome://extensions</code> and confirm the ID, version and managed installation.</li>
<li>Test the approved portal, direct YouTube links and off-site embeds on a standard-user account.</li></ol></div>
<details><summary>Platform instructions and recovery</summary><pre>{escape(deployment_notes(checked))}</pre></details>
</html>'''


def bundle_files(checked):
    files = extension_files(checked)
    archive = extension_zip(files)
    digest = hashlib.sha256(archive).hexdigest()
    if checked["extension_id"]:
        publication_ready(checked)
    setup = {"schema": 1, "extension_zip_sha256": digest, "settings": flat_settings(checked)}
    files.update({
        "extension.zip": archive,
        "setup.json": pretty_json(setup).encode("utf-8"),
        "START_HERE.html": start_page(checked).encode("utf-8"),
        "deployment/README.md": deployment_notes(checked).encode("utf-8"),
    })
    if checked["extension_id"]:
        policy = pretty_json(policy_document(checked)).encode("utf-8")
        files.update({
            "deployment/linux-managed-policy.json": policy,
            "deployment/extension-settings-value.json": pretty_json(extension_settings_value(checked)).encode("utf-8"),
            "deployment/schoolops-chrome.mobileconfig": platform_policy.macos_profile(policy),
        })
    return files


def export_bundle(raw, destination):
    """Write a resumable bundle without replacing an existing folder."""
    checked = validate_settings(raw)
    files = bundle_files(checked)
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing directory: {destination}")
    if not destination.parent.is_dir():
        raise ValueError(f"Create the destination parent directory first: {destination.parent}")
    temp = Path(tempfile.mkdtemp(prefix=".schoolops-guard-", dir=destination.parent))
    try:
        for relative, data in files.items():
            target = temp / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        checksums = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
        (temp / "SHA256SUMS.json").write_bytes(pretty_json(checksums).encode("utf-8"))
        # Reserve the name exclusively: POSIX rename can replace another empty
        # directory and is not a no-overwrite primitive.
        destination.mkdir()
        try:
            for child in temp.iterdir():
                os.rename(child, destination / child.name)
        except BaseException:
            shutil.rmtree(destination)
            raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return destination


def _verified_bundle(bundle):
    root = Path(bundle)
    if root.name == "setup.json":
        root = root.parent
    root = root.expanduser().resolve()
    hashes = read_json((root / "SHA256SUMS.json").read_bytes())
    allowed = EXTENSION_PATHS | {"extension.zip", "setup.json", "START_HERE.html", "deployment/README.md",
                                "deployment/linux-managed-policy.json", "deployment/extension-settings-value.json",
                                "deployment/schoolops-chrome.mobileconfig"}
    if not isinstance(hashes, dict) or not set(hashes).issubset(allowed) or "setup.json" not in hashes:
        raise ValueError("Bundle files or checksum inventory are missing or unexpected")
    snapshot = {}
    for name, claimed in hashes.items():
        path = root / name
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            raise ValueError(f"Bundle file must be a regular local file: {name}")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != claimed:
            raise ValueError(f"Bundle checksum mismatch: {name}")
        snapshot[name] = data
    setup = read_json(snapshot["setup.json"])
    if not isinstance(setup, dict) or setup.get("schema") != 1:
        raise ValueError("Unsupported setup format; prepare a new bundle with this version of Setup")
    checked = validate_settings(setup.get("settings"))
    if setup.get("extension_zip_sha256") != extension_digest(checked):
        raise ValueError("Saved extension fingerprint differs from the configured extension")
    expected = bundle_files(checked)
    if set(snapshot) != set(expected):
        raise ValueError("Bundle files or checksum inventory are missing or unexpected")
    # Explanatory text is covered by transport hashes, not by the current app's
    # wording. An updated guide must not make a saved setup impossible to reopen
    # or its owned policy impossible to remove. Never execute bundle-provided code.
    for name, data in expected.items():
        if name in {"START_HERE.html", "deployment/README.md"}:
            continue
        if snapshot[name] != data:
            raise ValueError(f"Bundle rules differ or file is inconsistent with validated settings: {name}")
    return root, checked, snapshot


def load_bundle(bundle):
    """Reopen the prepared build; an ID can then be attached without drift."""
    root, checked, _snapshot = _verified_bundle(bundle)
    settings = flat_settings(checked)
    settings["published_extension_sha256"] = extension_digest(checked)
    return root, settings


def verify_policy_bundle(bundle):
    _root, checked, snapshot = _verified_bundle(bundle)
    if not checked["extension_id"]:
        raise ValueError("Publishing pending: this bundle does not contain an install policy")
    return snapshot["deployment/linux-managed-policy.json"]


def apply_linux_policy(bundle, target=LINUX_MANAGED_PATH):
    if platform.system() != "Linux":
        raise RuntimeError("Linux policy installation is only supported on Linux")
    if os.geteuid() != 0:
        raise PermissionError("Run the policy installer as administrator after reviewing the bundle")
    return platform_policy.apply_linux_policy_content(verify_policy_bundle(bundle), target=target)


def change_local_policy(bundle, remove=False):
    content = verify_policy_bundle(bundle)
    system = platform.system()
    if system == "Windows":
        action = (platform_policy.remove_windows_policy_content if remove else
                  platform_policy.apply_windows_policy_content)
    elif system == "Linux":
        action = (platform_policy.remove_linux_policy_content if remove else
                  platform_policy.apply_linux_policy_content)
    else:
        raise RuntimeError("Use the generated management profile/Admin Console instructions on this platform")
    return action(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--apply-linux", metavar="BUNDLE", help="Apply a verified Linux bundle as root")
    actions.add_argument("--apply-policy", metavar="BUNDLE", help="Apply a verified local policy as administrator")
    actions.add_argument("--remove-policy", metavar="BUNDLE", help="Remove only this installer's unchanged owned policy")
    args = parser.parse_args()
    if args.apply_linux:
        print("Local policy:", apply_linux_policy(args.apply_linux))
    elif args.apply_policy or args.remove_policy:
        print("Local policy:", change_local_policy(args.apply_policy or args.remove_policy, bool(args.remove_policy)))
    else:
        parser.print_help()
        return
    print("Check chrome://policy and chrome://extensions; browser installation has not been verified.")


if __name__ == "__main__":
    main()
