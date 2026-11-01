#!/usr/bin/env python3
"""Build an auditable SchoolOps Chrome deployment bundle.

This does NOT publish an extension or claim a Chrome install succeeded. On Linux,
an administrator may separately apply a verified managed policy with --apply-linux.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import tempfile
from urllib.parse import urlsplit

from build_rules import build, domains, overlaps, YOUTUBE_PAGE_DOMAINS

ROOT = Path(__file__).resolve().parent
WEBSTORE_URL = "https://clients2.google.com/service/update2/crx"
CHROME_ID = re.compile(r"[a-p]{32}\Z")
LINUX_MANAGED_PATH = Path("/etc/opt/chrome/policies/managed/school-ops-youtube-guard.json")


def pretty_json(value):
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def validate_settings(raw):
    """Validate the complete wizard state before writing anything."""
    if not isinstance(raw, dict):
        raise ValueError("Installer settings must be an object")
    cfg = {
        "allowed_embed_sites": domains(raw.get("allowed_embed_sites", [])),
        "mode": raw.get("mode", "blacklist"),
        "allowed_sites": domains(raw.get("allowed_sites", [])),
        "blocked_sites": domains(raw.get("blocked_sites", [])),
    }
    # Reuse the already tested extension generator as the single rule authority.
    rules = build(cfg)
    if any(d.endswith(".invalid") or d == "invalid" for d in
           cfg["allowed_embed_sites"]):
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
    else:
        parsed = urlsplit(update_url)
        if extension_id and (parsed.scheme != "https" or not parsed.hostname or
                parsed.username or parsed.password or parsed.query or parsed.fragment or
                parsed.hostname in ("localhost", "127.0.0.1") or
                update_url == WEBSTORE_URL):
            raise ValueError("Self-hosted updates require your own HTTPS update manifest URL")
        if extension_id and (not parsed.path or parsed.path == "/"):
            raise ValueError("Provide a complete HTTPS URL to your update manifest")
    target_os = raw.get("target_os", "linux")
    if target_os not in ("linux", "windows", "macos", "chromeos"):
        raise ValueError("Choose Linux, Windows, macOS or ChromeOS")
    if any(overlaps(d, yt) for d in cfg["allowed_embed_sites"] for yt in YOUTUBE_PAGE_DOMAINS):
        raise ValueError("YouTube itself cannot be an approved school site")
    return {
        "config": cfg,
        "rules": rules,
        "extension_id": extension_id,
        "channel": channel,
        "update_url": update_url,
        "target_os": target_os,
    }


def policy_document(checked):
    if not checked["extension_id"]:
        raise ValueError("Cannot issue force-install policy before publication provides an extension ID")
    return {"ExtensionSettings": {
        checked["extension_id"]: {
            "installation_mode": "force_installed",
            "update_url": checked["update_url"],
        }
    }}


def extension_settings_value(checked):
    return policy_document(checked)["ExtensionSettings"]


def deployment_notes(checked):
    platform_notes = {
        "linux": (
            "Linux (Google Chrome): As root, apply deployment/linux-managed-policy.json "
            "to /etc/opt/chrome/policies/managed/school-ops-youtube-guard.json. "
            "For a guarded no-overwrite install, run from the source checkout: "
            "sudo python3 tools/browser/site_scoped_youtube_guard/installer_core.py "
            "--apply-linux /absolute/path/to/this/bundle. "
            "This action refuses to replace an existing policy."
        ),
        "windows": (
            "Windows: Import deployment/extension-settings-value.json as the "
            "Extension management settings policy using Chrome ADMX/GPO or your "
            "enterprise management console. This wizard does not edit the registry. "
            "Non-Web-Store force installs require the prerequisites documented by "
            "Google, including an Active Directory managed environment where Google requires it."
        ),
        "macos": (
            "macOS: Deploy the ExtensionSettings map from "
            "deployment/extension-settings-value.json through your MDM-managed "
            "com.google.Chrome preference payload. This wizard does not install "
            "configuration profiles."
        ),
        "chromeos": (
            "ChromeOS: Configure the extension's force-install and update source "
            "through your ChromeOS Admin console. Use the reviewed extension ID "
            "and update source below. This wizard does not enroll devices."
        ),
    }
    lines = [
        "# SchoolOps YouTube Guard deployment handoff",
        "",
        "Status: NOT INSTALLED.",
        ("PUBLISHING PENDING: no extension ID was entered; no install policy was created."
         if not checked["extension_id"] else
         "POLICY READY FOR ADMIN REVIEW: published extension ID entered."),
        "Extension publishing, policy application, and on-device browser",
        "verification are separate administrator steps.",
        "",
        "Target platform: " + checked["target_os"],
        "Extension ID: " + checked["extension_id"],
        "Distribution: " + checked["channel"],
        "Update manifest: " + checked["update_url"],
        "Approved embedding hosts: " + ", ".join(checked["config"]["allowed_embed_sites"]),
        "Browsing mode: " + checked["config"]["mode"],
        "",
        "1. Publish/sign THE EXACT extension/ contents for this configuration.",
        "   Preserve its ID and provide the confirmed update source. These files",
        "   are an unpacked build output, NOT an installable signed CRX.",
        "2. " + platform_notes[checked["target_os"]],
        "3. Restart Chrome 145+; inspect chrome://policy and chrome://extensions",
        "   on a standard-user managed device. Confirm force-installed status.",
        "4. Check the approved site plays its embedded YouTube video. Verify that",
        "   direct YouTube, new tabs and YouTube embeds elsewhere fail.",
        "5. Verify other browsers/apps and administrator privileges are restricted",
        "   separately if required. Configuration is not a proof of enforcement.",
        "",
        "WARNING: Applying ExtensionSettings may conflict with existing Chrome",
        "enterprise policies. Review and merge policy objects with IT; do not",
        "blindly replace an existing ExtensionSettings policy.",
        "",
        "Chrome policy references:",
        "https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest",
        "https://support.google.com/chrome/a/answer/7532015",
        "https://support.google.com/chrome/a/answer/7517525",
        "",
    ]
    return "\n".join(lines)


def export_bundle(raw, destination):
    """Generate a complete local review bundle; never overwrite or half-publish."""
    checked = validate_settings(raw)
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing directory: {destination}")
    if not destination.parent.is_dir():
        raise ValueError(f"Create the destination parent directory first: {destination.parent}")

    temp = Path(tempfile.mkdtemp(prefix=".schoolops-guard-", dir=destination.parent))
    try:
        ext = temp / "extension"
        deploy = temp / "deployment"
        ext.mkdir()
        deploy.mkdir()
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("minimum_chrome_version") != "145":
            raise ValueError("Unexpected Chrome minimum version: review manifest")
        files = {
            "extension/manifest.json": pretty_json(manifest),
            "extension/rules.json": pretty_json(checked["rules"]),
            "extension/config.json": pretty_json(checked["config"]),
            "deployment/README.md": deployment_notes(checked),
        }
        if checked["extension_id"]:
            files["deployment/linux-managed-policy.json"] = pretty_json(policy_document(checked))
            files["deployment/extension-settings-value.json"] = pretty_json(extension_settings_value(checked))
        # Encode once: disk bytes and digest inputs must be identical on every OS.
        # Binary writes preserve the generated UTF-8/LF form on Windows too.
        files = {key: value.encode("utf-8") for key, value in files.items()}
        for relative, data in files.items():
            (temp / relative).write_bytes(data)
        checksums = {
            key: hashlib.sha256(value).hexdigest()
            for key, value in sorted(files.items())
        }
        (temp / "SHA256SUMS.json").write_bytes(pretty_json(checksums).encode("utf-8"))
        # os.rename fails when the destination exists on POSIX.
        if destination.exists():
            raise FileExistsError(f"Destination appeared during export: {destination}")
        os.rename(temp, destination)
    except BaseException:
        import shutil
        shutil.rmtree(temp)
        raise
    return destination


def verify_policy_bundle(bundle):
    """Verify the whole exported bundle before installing its managed policy."""
    root = Path(bundle).resolve()
    hashes = json.loads((root / "SHA256SUMS.json").read_text(encoding="utf-8"))
    expected = {
        "extension/manifest.json",
        "extension/rules.json",
        "extension/config.json",
        "deployment/linux-managed-policy.json",
        "deployment/extension-settings-value.json",
        "deployment/README.md",
    }
    if not isinstance(hashes, dict) or set(hashes) != expected:
        raise ValueError("Bundle files or checksum inventory are missing or unexpected")
    for relative, claimed in hashes.items():
        content = (root / relative).read_bytes()
        if hashlib.sha256(content).hexdigest() != claimed:
            raise ValueError(f"Bundle checksum mismatch: {relative}")

    policy_file = root / "deployment/linux-managed-policy.json"
    content = policy_file.read_bytes()
    policy = json.loads(content)
    if set(policy) != {"ExtensionSettings"} or len(policy["ExtensionSettings"]) != 1:
        raise ValueError("Unexpected managed policy structure")
    (extension_id, settings), = policy["ExtensionSettings"].items()
    if set(settings) != {"installation_mode", "update_url"}:
        raise ValueError("Unexpected force-install settings")
    if settings.get("installation_mode") != "force_installed":
        raise ValueError("Policy is not force-installed")

    original = json.loads((root / "extension/config.json").read_text(encoding="utf-8"))
    url = settings["update_url"]
    channel = "web_store" if url == WEBSTORE_URL else "self_hosted"
    checked = validate_settings({
        **original,
        "extension_id": extension_id,
        "update_url": url,
        "channel": channel,
        "target_os": "linux",
    })
    generated_rules = json.loads((root / "extension/rules.json").read_text(encoding="utf-8"))
    if generated_rules != checked["rules"]:
        raise ValueError("Bundle rules differ from the validated administrator settings")
    admx = json.loads((root / "deployment/extension-settings-value.json").read_text(encoding="utf-8"))
    if admx != extension_settings_value(checked):
        raise ValueError("Linux and ADMX policies do not agree")
    manifest = json.loads((root / "extension/manifest.json").read_text(encoding="utf-8"))
    if manifest != json.loads((ROOT / "manifest.json").read_text(encoding="utf-8")):
        raise ValueError("Unexpected extension manifest")
    return content

def apply_linux_policy(bundle, target=LINUX_MANAGED_PATH):
    """Explicit privileged action, no silently overwriting existing policy."""
    if platform.system() != "Linux":
        raise RuntimeError("Linux managed-policy installation is only supported on Linux")
    if os.geteuid() != 0:
        raise PermissionError("Run --apply-linux as root after reviewing the bundle")
    content = verify_policy_bundle(bundle)
    target = Path(target)
    if target != LINUX_MANAGED_PATH:
        raise ValueError("Refusing to install to a noncanonical Chrome policy path")
    parent = target.parent
    parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if parent.is_symlink() or parent.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise PermissionError("Chrome's managed policy directory must be root-controlled")
    # Exclusive creation avoids clobbering another school/device policy.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o644)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-linux", metavar="BUNDLE",
                        help="As root, install a verified Linux managed-policy file")
    args = parser.parse_args()
    if args.apply_linux:
        print("Policy written:", apply_linux_policy(args.apply_linux))
        print("Not yet verified in Chrome; inspect chrome://policy and test on-device.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
