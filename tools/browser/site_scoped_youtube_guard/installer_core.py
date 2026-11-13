#!/usr/bin/env python3
"""Prepare, resume and apply a SchoolOps Chrome deployment.

Web Store publication uses an operator attestation. Self-hosted releases retain
a bound observation of independently downloaded bytes. Neither establishes
managed-device installation or continuing endpoint availability.
"""
import argparse
from datetime import datetime
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
    checked = {
        "config": cfg, "rules": rules, "extension_id": extension_id,
        "channel": channel, "update_url": update_url, "target_os": target_os,
        "extension_version": validate_version(raw.get("extension_version", source_manifest["version"])),
        "published_extension_sha256": raw.get("published_extension_sha256", ""),
        "publication_confirmed": raw.get("publication_confirmed") is True,
    }
    if "publication_receipt" in raw:
        checked["publication_receipt"] = validate_publication_receipt(raw["publication_receipt"], checked)
    return checked


def validate_publication_receipt(receipt, checked):
    """Check a saved observation's scope and binding, not its authenticity.

    This local, unsigned record is produced by the HTTPS release verifier and
    retained for review. It is not an authorization token or an enduring claim
    about the server. Reverification requires release_core.verify_publication.
    """
    fields = {"schema", "scope", "release_id", "extension_id", "extension_version",
              "extension_zip_sha256", "update_url", "crx_url", "crx_sha256",
              "manifest_sha256", "public_key_sha256", "observed_at_utc",
              "managed_device_enforcement", "policy_applied", "verification"}
    if not isinstance(receipt, dict) or set(receipt) != fields:
        raise ValueError("Self-hosted publication receipt has missing or unexpected fields")
    if (type(receipt["schema"]) is not int or receipt["schema"] != 1 or
            receipt["scope"] != "downloaded_release_bytes" or checked["channel"] != "self_hosted"):
        raise ValueError("Unsupported self-hosted publication receipt scope")
    for name in ("release_id", "extension_zip_sha256", "crx_sha256",
                 "manifest_sha256", "public_key_sha256"):
        value = receipt[name]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Invalid publication receipt fingerprint: " + name)
    for name in ("extension_id", "extension_version", "update_url"):
        if receipt[name] != checked[name]:
            raise ValueError("Publication receipt differs from prepared settings: " + name)
    if receipt["extension_zip_sha256"] != extension_digest(checked):
        raise ValueError("Publication receipt fingerprint differs from the prepared extension")
    crx_url = receipt["crx_url"]
    if not isinstance(crx_url, str):
        raise ValueError("Publication receipt requires an HTTPS CRX URL")
    parsed = urlsplit(crx_url)
    source = urlsplit(checked["update_url"])
    try:
        same_origin = (parsed.hostname, parsed.port or 443) == (source.hostname, source.port or 443)
    except ValueError as exc:
        raise ValueError("Publication receipt contains an invalid HTTPS port") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or
            parsed.password is not None or source.username is not None or source.password is not None or
            parsed.query or parsed.fragment or any(ord(c) < 33 for c in crx_url) or
            not parsed.path or parsed.path == "/" or not same_origin):
        raise ValueError("Publication receipt CRX URL must use the update manifest's HTTPS origin")
    if receipt["managed_device_enforcement"] is not False or receipt["policy_applied"] is not False:
        raise ValueError("Publication receipt cannot claim device enforcement or policy application")
    verification = receipt["verification"]
    checks = {"identity_ok", "version_ok", "zip_ok", "crx_ok", "signature_ok", "tls_ok",
              "manifest_ok", "download_ok"}
    if (not isinstance(verification, dict) or set(verification) != checks or
            any(value is not True for value in verification.values())):
        raise ValueError("Publication receipt requires every release verification check")
    observed = receipt["observed_at_utc"]
    try:
        if (not isinstance(observed, str) or not re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", observed)):
            raise ValueError("not a UTC timestamp")
        datetime.fromisoformat(observed.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError("Publication receipt requires a UTC observation timestamp") from exc
    # Detach callers' mutable dictionaries from the validated settings.
    return read_json(pretty_json(receipt))


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


def publication_ready(checked, *, allow_legacy_self_hosted=False):
    if not checked["extension_id"]:
        raise ValueError("Cannot issue force-install policy before publication provides an extension ID")
    if not checked["publication_confirmed"]:
        raise ValueError("Confirm publication of the exact prepared extension ZIP before generating policy")
    if checked["published_extension_sha256"] != extension_digest(checked):
        raise ValueError("Published extension fingerprint differs: reopen the prepared setup.json; "
                         "changed websites or version require a new publication")
    if checked["channel"] == "self_hosted":
        receipt = checked.get("publication_receipt")
        if receipt is None and not allow_legacy_self_hosted:
            raise ValueError("Self-hosted publication requires HTTPS release verification; "
                             "use Verify HTTPS & export or the release verifier")
        if receipt is not None:
            validate_publication_receipt(receipt, checked)


def policy_document(checked, *, allow_legacy_self_hosted=False):
    publication_ready(checked, allow_legacy_self_hosted=allow_legacy_self_hosted)
    entry = {"installation_mode": "force_installed", "update_url": checked["update_url"]}
    if checked["channel"] == "self_hosted":
        entry["override_update_url"] = True
    return {"ExtensionSettings": {checked["extension_id"]: entry}}


def extension_settings_value(checked, *, allow_legacy_self_hosted=False):
    return policy_document(checked, allow_legacy_self_hosted=allow_legacy_self_hosted)["ExtensionSettings"]


def flat_settings(checked):
    settings = {**checked["config"], **{key: checked[key] for key in (
        "extension_id", "channel", "update_url", "target_os", "extension_version",
        "published_extension_sha256", "publication_confirmed")}}
    if "publication_receipt" in checked:
        settings["publication_receipt"] = checked["publication_receipt"]
    return settings


def deployment_notes(checked):
    published = bool(checked["extension_id"])
    self_hosted = checked["channel"] == "self_hosted"
    publication_steps = (
        "Reopen the prepared setup.json in the Setup app and choose Prepare self-hosted release. "
        "Supply a public RSA key, pinned extension ID, exact version, HTTPS manifest/CRX URLs and "
        "the previous release (or explicit first-release declaration). Sign using the release CLI "
        "or an approved external signing tool; private keys never enter the GUI or release files. "
        "Review the intended publication actions before separately approved production upload. "
        "Use Verify HTTPS & export after publication; it downloads and checks the manifest and CRX "
        "against this exact prepared ZIP before producing a policy bundle."
        if self_hosted else
        "Upload extension.zip to your Chrome Web Store developer account. Reopen setup.json in the "
        "Setup app, enter the published ID, confirm that you published this exact configuration, "
        "and export to a new folder. The ZIP fingerprint prevents accidental configuration drift; "
        "the Store publication confirmation remains the operator's statement."
    )
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
        ("POLICY READY: exact HTTPS release bytes were observed; see publication-receipt.json." if
         checked.get("publication_receipt") else
         "POLICY READY: publication is operator-confirmed, not remotely verified." if published else
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
        publication_steps,
        "Preserve the signing key and extension ID. The ZIP is an upload package, not an installable "
        "signed CRX. No Store listing is created here. A saved publication receipt records a past "
        "download observation; it does not authenticate local records or guarantee future server content.",
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
              "Reopen setup.json in the SchoolOps Setup app, choose Prepare self-hosted release, "
              "sign and publish through your approved process, then choose Verify HTTPS & export."
              if checked["channel"] == "self_hosted" else
              "Publish extension.zip using your Chrome Web Store developer account or managed "
              "self-hosted channel. Then reopen setup.json and enter the published extension ID.")
    policy_links = ("<li><a href='deployment/extension-settings-value.json'>ExtensionSettings for GPO/MDM</a></li>"
                    "<li><a href='deployment/linux-managed-policy.json'>Linux managed policy</a></li>"
                    "<li><a href='deployment/schoolops-chrome.mobileconfig'>macOS management profile</a></li>"
                    if published else "")
    if checked.get("publication_receipt"):
        policy_links += "<li><a href='deployment/publication-receipt.json'>Observed release verification</a></li>"
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


def bundle_files(checked, *, allow_legacy_self_hosted=False):
    files = extension_files(checked)
    archive = extension_zip(files)
    digest = hashlib.sha256(archive).hexdigest()
    if checked["extension_id"]:
        publication_ready(checked, allow_legacy_self_hosted=allow_legacy_self_hosted)
    setup = {"schema": 1, "extension_zip_sha256": digest, "settings": flat_settings(checked)}
    files.update({
        "extension.zip": archive,
        "setup.json": pretty_json(setup).encode("utf-8"),
        "START_HERE.html": start_page(checked).encode("utf-8"),
        "deployment/README.md": deployment_notes(checked).encode("utf-8"),
    })
    if checked["extension_id"]:
        policy = pretty_json(policy_document(checked,
            allow_legacy_self_hosted=allow_legacy_self_hosted)).encode("utf-8")
        files.update({
            "deployment/linux-managed-policy.json": policy,
            "deployment/extension-settings-value.json": pretty_json(extension_settings_value(checked,
                allow_legacy_self_hosted=allow_legacy_self_hosted)).encode("utf-8"),
            "deployment/schoolops-chrome.mobileconfig": platform_policy.macos_profile(policy),
        })
        if "publication_receipt" in checked:
            files["deployment/publication-receipt.json"] = pretty_json(
                checked["publication_receipt"]).encode("utf-8")
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
                                "deployment/schoolops-chrome.mobileconfig", "deployment/publication-receipt.json"}
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
    # Old self-hosted exports remain readable, including owned-policy removal.
    # Fresh export and installation still require the new observation receipt.
    expected = bundle_files(checked, allow_legacy_self_hosted=True)
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


def verify_policy_bundle(bundle, *, allow_legacy_self_hosted=False):
    _root, checked, snapshot = _verified_bundle(bundle)
    if not checked["extension_id"]:
        raise ValueError("Publishing pending: this bundle does not contain an install policy")
    publication_ready(checked, allow_legacy_self_hosted=allow_legacy_self_hosted)
    return snapshot["deployment/linux-managed-policy.json"]


def apply_linux_policy(bundle, target=LINUX_MANAGED_PATH):
    if platform.system() != "Linux":
        raise RuntimeError("Linux policy installation is only supported on Linux")
    if os.geteuid() != 0:
        raise PermissionError("Run the policy installer as administrator after reviewing the bundle")
    return platform_policy.apply_linux_policy_content(verify_policy_bundle(bundle), target=target)


def change_local_policy(bundle, remove=False):
    content = verify_policy_bundle(bundle, allow_legacy_self_hosted=remove)
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
