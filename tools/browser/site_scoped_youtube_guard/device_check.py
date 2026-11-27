#!/usr/bin/env python3
"""Read-only, bounded local Chrome policy diagnostics for SchoolOps.

These checks observe *local machine policy files/registry only*. They never
claim Chrome loaded the policy, that the extension is force-installed, or that
YouTube behavior works. Cloud, GPO and MDM policy sources need a separately
reviewed Chrome/device check. No privileged write occurs in this module.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform

import installer_core
import platform_policy

OWN_LINUX_NAME = platform_policy.LINUX_MANAGED_PATH.name
STATES = frozenset(("matching", "missing", "different", "conflicting", "uninspectable",
                    "unsupported", "wrong_target"))


def _read_json(value):
    if not isinstance(value, (bytes, str)):
        raise ValueError("Policy file is not text")
    parsed = platform_policy._json(value)
    if not isinstance(parsed, dict):
        raise ValueError("Chrome policy file must contain an object")
    return parsed


def classify_linux(files, expected, own_name=OWN_LINUX_NAME):
    """Pure classifier. All managed *.json files must be supplied, not a subset.

    Unknown/malformed files block a "matching" verdict, because they might
    contain an additional ExtensionSettings policy. No precedence is guessed.
    """
    if not isinstance(files, dict):
        raise ValueError("Policy inventory must be a dictionary")
    if not isinstance(expected, dict) or set(expected) != {"ExtensionSettings"}:
        raise ValueError("Expected policy must contain ExtensionSettings only")
    observed = {}
    for name, contents in files.items():
        if not isinstance(name, str) or "/" in name or "\\" in name or not name.endswith(".json"):
            raise ValueError("Invalid managed Chrome policy filename")
        try:
            observed[name] = _read_json(contents)
        except (ValueError, UnicodeDecodeError, TypeError):
            return "uninspectable"
    other_entries = [
        name for name, parsed in observed.items()
        if name != own_name and "ExtensionSettings" in parsed
    ]
    if other_entries:
        return "conflicting"
    if own_name not in observed:
        return "missing"
    if observed[own_name] != expected:
        return "different"
    return "matching"


def inspect_linux(expected):
    """Read the real root-controlled Chrome managed directory with no writes."""
    directory = platform_policy._policy_directory(
        platform_policy.LINUX_MANAGED_PATH, create=False
    )
    if directory is None:
        return "missing"
    try:
        files = {}
        for name in os.listdir(directory):
            if not name.endswith(".json"):
                continue
            # Existing platform helper refuses symlinks, non-root-owned files
            # and oversized content. Do not reinterpret failure as 'absent'.
            content = platform_policy._read_at(directory, name)
            if content is None:
                return "uninspectable"
            files[name] = content
        return classify_linux(files, expected)
    finally:
        os.close(directory)


def inspect_windows(expected):
    """Read HKLM's 64-bit ExtensionSettings value, without elevation or writes."""
    _, available = platform_policy._windows_snapshot()
    (extension_id, expected_value), = expected["ExtensionSettings"].items()
    if extension_id not in available:
        return "missing"
    return "matching" if available[extension_id] == expected_value else "different"


def check_bundle(bundle, *, system=None):
    """Return a privacy-minimal, explicit diagnostic without altering policy."""
    system = platform.system() if system is None else system
    source = Path(bundle)
    # This validates exact bundle files/rules/publishing settings and checksums.
    policy_bytes = installer_core.verify_policy_bundle(source)
    root, settings = installer_core.load_bundle(source)
    # The expected Chrome policy is derived from the verified bytes only.
    expected = _read_json(policy_bytes)
    (extension_id, _), = expected["ExtensionSettings"].items()
    os_names = {"Windows": "windows", "Linux": "linux",
                "Darwin": "macos", "ChromeOS": "chromeos"}
    detected = os_names.get(system)
    if detected != settings["target_os"]:
        state = "wrong_target"
    elif detected == "linux":
        try:
            state = inspect_linux(expected)
        except (OSError, ValueError, PermissionError, TypeError):
            state = "uninspectable"
    elif detected == "windows":
        try:
            state = inspect_windows(expected)
        except (OSError, ValueError, PermissionError, TypeError):
            state = "uninspectable"
    else:
        state = "unsupported"
    if state not in STATES:
        raise RuntimeError("Unexpected policy check result")
    return {
        "schema": 1,
        "scope": "read_only_local_machine_policy",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target_os": settings["target_os"],
        "observed_os": detected or "other",
        "extension_id": extension_id,
        "expected_policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "local_policy_status": state,
        "local_policy_matches_expected": True if state == "matching" else
                                         False if state in ("missing", "different", "conflicting") else None,
        "chrome_effective_policy": "not_verified",
        "extension_installed_and_locked": "not_verified",
        "youtube_playback_and_blocking": "not_verified",
        "tamper_resistance": "not_established",
    }


def format_result(report):
    explanations = {
        "matching": "The local machine policy matches this reviewed bundle.",
        "missing": "No matching local machine policy entry was found.",
        "different": "The local machine policy entry differs from this bundle.",
        "conflicting": "Another Linux managed policy defines ExtensionSettings; resolve in IT.",
        "uninspectable": "Cannot safely inspect a local machine policy. No pass is inferred.",
        "unsupported": "The target uses a management system not inspected by this tool.",
        "wrong_target": "This bundle targets a different operating system.",
    }
    return (explanations[report["local_policy_status"]] +
            " Chrome policy loading, extension installation/lock, and YouTube " +
            "behavior remain UNVERIFIED. Check chrome://policy and " +
            "chrome://extensions on a managed standard-user account.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="Path to reviewed exported deployment bundle")
    parser.add_argument("--report", help="New JSON report path; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        result = check_bundle(args.bundle)
        if args.report:
            with open(args.report, "x", encoding="utf-8") as handle:
                json.dump(result, handle, sort_keys=True, indent=2)
                handle.write("\n")
        print(format_result(result))
        return 0 if result["local_policy_status"] == "matching" else 1
    except (OSError, ValueError, RuntimeError) as exc:
        print("Policy diagnosis failed safely: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
