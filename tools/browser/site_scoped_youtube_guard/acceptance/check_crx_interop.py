#!/usr/bin/env python3
"""Check the supported CRX3 profile against Chromium's own extension packer.

Every run creates and removes its own RSA key, extension directory and browser
profile. No extension is installed, no policy is applied, and no production
release is published. This is packer interoperability, not managed enforcement.
An unavailable browser or failed comparison exits nonzero; there is no skip.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile


GUARD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUARD_ROOT))
import crx3  # noqa: E402
import installer_core as core  # noqa: E402


def _run(argv, operation, *, timeout=30):
    """Do not echo commands, key paths or signer diagnostics into the report."""
    try:
        completed = subprocess.run(argv, input=b"", stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=timeout,
                                   check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(operation + " could not complete") from exc
    if completed.returncode:
        raise ValueError(f"{operation} failed with exit code {completed.returncode}")
    return completed.stdout


def _browser(explicit):
    candidates = [explicit] if explicit else [
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    raise ValueError("Chromium packer not found; supply --chromium /path/to/chrome")


def check(chromium=None, *, no_sandbox=False):
    executable = _browser(chromium)
    browser_version = _run([executable, "--version"], "Chromium version check").decode(
        "utf-8", "replace").strip()
    openssl_version = _run(["openssl", "version"], "OpenSSL version check").decode(
        "utf-8", "replace").strip()
    checked = core.validate_settings({
        "allowed_embed_sites": ["school.example.org"], "channel": "self_hosted",
        "update_url": "", "extension_version": "1.0.0",
    })
    expected_files = {
        name.removeprefix("extension/"): data
        for name, data in core.extension_files(checked).items()
    }
    with tempfile.TemporaryDirectory(prefix="schoolops-crx-interop-") as temporary:
        root = Path(temporary)
        extension = root / "extension"
        extension.mkdir()
        for name, data in expected_files.items():
            (extension / name).write_bytes(data)
        key = root / "disposable.pem"
        _run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
              "rsa_keygen_bits:2048", "-out", str(key)], "Disposable key generation")
        key.chmod(0o600)
        public = _run(["openssl", "pkey", "-in", str(key), "-pubout", "-outform", "DER"],
                      "Public key export")
        arguments = [
            executable, "--headless", "--disable-gpu", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", "--no-first-run",
            "--no-default-browser-check", "--host-resolver-rules=MAP * ~NOTFOUND",
            "--user-data-dir=" + str(root / "profile"),
            "--pack-extension=" + str(extension), "--pack-extension-key=" + str(key),
        ]
        if no_sandbox:
            arguments.append("--no-sandbox")
        _run(arguments, "Chromium extension packing")
        packed = crx3.read_file(root / "extension.crx", crx3.MAX_CRX_BYTES)
        if len(packed) < 12 or packed[:4] != b"Cr24":
            raise ValueError("Chromium did not produce a CRX file")
        format_version, header_size = struct.unpack("<II", packed[4:12])
        if (format_version != 3 or not 0 < header_size <= crx3.MAX_HEADER_BYTES
                or 12 + header_size >= len(packed)):
            raise ValueError("Chromium output is outside the supported CRX3 profile")
        archive = packed[12 + header_size:]
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            if sorted(zipped.namelist()) != sorted(expected_files):
                raise ValueError("Chromium package changed the expected file inventory")
            if any(zipped.read(name) != data for name, data in expected_files.items()):
                raise ValueError("Chromium package changed the prepared extension files")
        identity = crx3.extension_id(public)
        verified = crx3.verify(packed, expected_zip=archive, expected_key=public,
                              expected_id=identity)
        signature = crx3.sign_payload(crx3.signing_input(archive, public), key)
        rebuilt = crx3.assemble(archive, public, signature)
        if rebuilt != packed:
            raise ValueError("OpenSSL CRX3 output differs from Chromium's exact CRX bytes")
        # Give the verifier the altered payload as its expected ZIP so that the
        # signature check, rather than the ZIP-equality guard, must reject it.
        tampered_archive = archive[:-1] + bytes([archive[-1] ^ 1])
        tampered_crx = packed[:12 + header_size] + tampered_archive
        try:
            crx3.verify(tampered_crx, expected_zip=tampered_archive,
                        expected_key=public, expected_id=identity)
        except ValueError:
            pass
        else:
            raise ValueError("Negative control accepted a changed signed ZIP payload")
        report = {
            "schema": 1, "status": "passed", "scope": "chromium_packer_interoperability",
            "chromium_version": browser_version, "openssl_version": openssl_version,
            "source_sha256": {
                name: hashlib.sha256((GUARD_ROOT / name).read_bytes()).hexdigest()
                for name in ("crx3.py", "installer_core.py", "manifest.json", "build_rules.py",
                             "acceptance/check_crx_interop.py")
            },
            "checks": {"chromium_crx_verified": True, "payload_files_match_wizard": True,
                       "reassembled_crx_identical": True, "changed_payload_rejected": True},
            "artifact": verified, "zip_source": "chromium_packer",
            "disposable_rsa_key_bits": 2048, "fresh_temporary_browser_profile": True,
            "sandbox_disabled_for_isolated_fixture": no_sandbox,
            "extension_installed": False, "policy_applied": False,
            "production_published": False, "managed_device_enforcement": False,
        }
    # Report success only after TemporaryDirectory has removed the key/profile.
    report["temporary_credentials_and_profile_removed"] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium", help="Chromium/Chrome executable (otherwise auto-detected)")
    parser.add_argument("--report", type=Path, help="Write the JSON result to a local artifact path")
    parser.add_argument("--no-sandbox", action="store_true",
                        help="Only for isolated disposable CI or container fixtures")
    args = parser.parse_args(argv)
    try:
        report = check(args.chromium, no_sandbox=args.no_sandbox)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        report = {"schema": 1, "status": "failed", "scope": "chromium_packer_interoperability",
                  "error": str(exc), "managed_device_enforcement": False}
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
