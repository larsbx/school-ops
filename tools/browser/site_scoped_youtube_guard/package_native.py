#!/usr/bin/env python3
"""Build an unsigned, standalone OS-specific SchoolOps GUI bundle with PyInstaller.

Creates a reviewable CI artifact and tests signing with disposable credentials.
It does not publish an extension, install policy, or enroll a device.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
APP = "SchoolOps-YouTube-Guard-Setup"
SUPPORTED = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def build_command(python, scratch, system=None):
    system = platform.system() if system is None else system
    if system not in SUPPORTED:
        raise ValueError(f"Unsupported native packaging platform: {system}")
    return [
        str(python), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        # Policy actions can be explicitly elevated. One-file extraction to a
        # temporary directory must not become a privileged executable source.
        "--onedir", "--name", APP,
        "--distpath", str(scratch / "dist"),
        "--workpath", str(scratch / "work"),
        "--specpath", str(scratch / "spec"),
        "--add-data", str(ROOT / "manifest.json") + os.pathsep + ".",
        str(ROOT / "wizard.py"),
    ]


def packaged_executable(scratch, system=None):
    system = platform.system() if system is None else system
    dist = scratch / "dist"
    if system == "Windows":
        return dist / APP / (APP + ".exe")
    if system == "Darwin":
        return dist / (APP + ".app") / "Contents" / "MacOS" / APP
    if system == "Linux":
        return dist / APP / APP
    raise ValueError("Unsupported platform")


def _release_cli_report(command_prefix, report_path, arguments, *, expect_failure=False):
    """Observe the report as well as exit status, including windowed executables."""
    command = [*map(str, command_prefix), "--release", "--report", str(report_path), *map(str, arguments)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120, check=False)
    if not report_path.is_file():
        diagnostic = result.stderr.decode("utf-8", "replace")[-2000:]
        raise RuntimeError(f"Release CLI {arguments[0]} produced no operation report "
                           f"(exit {result.returncode}): {diagnostic}")
    report = json.loads(report_path.read_bytes())
    expected_status = "failed" if expect_failure else "passed"
    if (not isinstance(report, dict) or report.get("schema") != 1 or
            report.get("scope") != "schoolops_release_operation" or
            report.get("command") != arguments[0] or report.get("status") != expected_status or
            bool(result.returncode) != expect_failure):
        raise RuntimeError(f"Release CLI {arguments[0]} did not produce the expected "
                           f"{expected_status} result (exit {result.returncode}): {report}")
    if expect_failure and not isinstance(report.get("error"), str):
        raise RuntimeError("Failed release CLI command omitted its error from the operation report")
    return report


def release_cli_smoke(command_prefix, *, work_parent=None):
    """Run real CLI signing with a temporary key; retain only public result data.

    package() passes the freshly built native executable. The unit test passes
    the source entry point to check this harness without building an installer.
    No remote endpoint or operating-system policy is accessed.
    """
    import crx3
    import installer_core as core
    import release_core

    openssl = shutil.which("openssl")
    if openssl is None:
        raise RuntimeError("Native release acceptance requires a locally installed OpenSSL 3")
    with tempfile.TemporaryDirectory(prefix="schoolops-native-release-", dir=work_parent) as temporary:
        root = Path(temporary)
        private, public = root / "disposable.key", root / "disposable-public.pem"
        subprocess.run([openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                        "-out", str(private)], capture_output=True, check=True, timeout=30)
        subprocess.run([openssl, "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                       capture_output=True, check=True, timeout=30)
        public_der = crx3.public_key_bytes(public)
        expected_id = crx3.extension_id(public_der)
        identity = _release_cli_report(command_prefix, root / "key-id-report.json", ["key-id", public])
        if identity.get("result") != expected_id:
            raise RuntimeError("Packaged release CLI returned a different signing identity")

        prepared = core.export_bundle({
            "allowed_embed_sites": ["portal.school.example"], "mode": "blacklist",
            "allowed_sites": [], "blocked_sites": ["social.example.net"],
            "extension_id": "", "channel": "self_hosted", "update_url": "",
            "extension_version": "0.1.0", "target_os": SUPPORTED[platform.system()],
        }, root / "prepared")
        release = root / "release"
        _release_cli_report(command_prefix, root / "prepare-report.json", [
            "prepare", prepared, release, "--public-key", public, "--expected-id", expected_id,
            "--expected-version", "0.1.0", "--update-url", "https://updates.school.example/update.xml",
            "--crx-url", "https://updates.school.example/guard-0.1.0.crx", "--initial-release",
        ])
        plan = release_core.load_release(release)
        if plan["extension_id"] != expected_id or plan["extension_version"] != "0.1.0":
            raise RuntimeError("Packaged release preparation changed the pinned identity or version")
        if (release / "extension.zip").read_bytes() != (prepared / "extension.zip").read_bytes():
            raise RuntimeError("Packaged release preparation changed the exact wizard ZIP")
        _release_cli_report(command_prefix, root / "sign-report.json", ["sign", release, "--key", private])
        signed_bytes = (release / "extension.crx").read_bytes()
        checked = crx3.verify(signed_bytes, expected_zip=(prepared / "extension.zip").read_bytes(),
                             expected_key=public_der, expected_id=expected_id)
        signed_snapshot = release_core._signed(release)
        if signed_snapshot[4]["crx_sha256"] != checked["crx_sha256"]:
            raise RuntimeError("Packaged release commit record differs from the verified CRX")

        # A failed native invocation must leave a readable failure report and
        # preserve the previously signed release, including in a windowed app.
        failure = _release_cli_report(command_prefix, root / "failed-sign-report.json",
            ["sign", release, "--key", root / "missing-fixture-key.pem"], expect_failure=True)
        if (release / "extension.crx").read_bytes() != signed_bytes:
            raise RuntimeError("A failed packaged signing command changed the committed CRX")
        release_core._signed(release)
        if (prepared / "deployment/linux-managed-policy.json").exists():
            raise RuntimeError("Release acceptance unexpectedly produced a managed policy")
        return {
            "schema": 1, "status": "passed",
            "scope": "Release CLI identity, preparation, signing and failure reporting with disposable "
                     "credentials; no HTTPS publication, policy application or managed-device checks",
            "commands": {"key-id": "passed", "prepare": "passed", "sign": "passed",
                         "missing-key": failure["status"]},
            "extensionId": expected_id, "extensionVersion": plan["extension_version"],
            "extensionZipSha256": checked["extension_zip_sha256"],
            "crxSha256": checked["crx_sha256"],
            "manifestSha256": signed_snapshot[4]["manifest_sha256"],
            "privateKeysRetained": False, "policyApplied": False, "remotePublication": False,
        }


def package(output):
    system = platform.system()
    if system not in SUPPORTED:
        raise RuntimeError(f"Build on a supported native runner: {system}")
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite native build output: " + str(output))
    if not output.parent.is_dir():
        raise ValueError("Native build output parent does not exist: " + str(output.parent))

    scratch = Path(tempfile.mkdtemp(prefix=".schoolops-native-", dir=output.parent))
    try:
        build = build_command(sys.executable, scratch, system)
        subprocess.run(build, cwd=ROOT, check=True, timeout=900)

        executable = packaged_executable(scratch, system)
        if not executable.is_file():
            raise FileNotFoundError("Missing expected native wizard executable: " + str(executable))
        smoke_path = scratch / "native-smoke.json"
        subprocess.run([str(executable), "--self-test", str(smoke_path)],
                       cwd=ROOT, check=True, timeout=120)
        if not smoke_path.is_file():
            raise RuntimeError("The packaged wizard did not produce its smoke-test report")
        smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        if smoke.get("status") != "passed" or smoke.get("frozen") is not True:
            raise RuntimeError("Packaged-wizard smoke test is not a verified pass")
        release_smoke = release_cli_smoke([executable], work_parent=scratch)

        out = scratch / "output"
        out.mkdir()
        if system == "Windows":
            archive = out / (APP + "-windows-unsigned.zip")
            source = scratch / "dist" / APP
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
                for item in sorted(source.rglob("*")):
                    if item.is_file():
                        zipped.write(item, item.relative_to(source.parent).as_posix())
        else:
            archive = out / (APP + "-" + SUPPORTED[system] + "-unsigned.tar.gz")
            source = (scratch / "dist" / (APP + ".app") if system == "Darwin"
                      else scratch / "dist" / APP)
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(source, arcname=source.name)

        try:
            git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     check=True, capture_output=True,
                                     text=True, timeout=15).stdout.strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            git_sha = None
        import PyInstaller
        metadata = {
            "schema": 1,
            "status": "unsigned_native_bundle_built",
            "notProven": [
                "graphical wizard interaction",
                "signed binary or verified OS installer",
                "production signing credentials or published Chrome extension",
                "real YouTube playback",
                "managed browser policy applied to device",
                "tamper-resistant standard-user enforcement",
            ],
            "sourceCommit": git_sha,
            "platform": system,
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "pyinstaller": PyInstaller.__version__,
            "archive": archive.name,
            "archiveSha256": sha256(archive),
            "nativeSmoke": smoke,
            "nativeReleaseSmoke": release_smoke,
        }
        (out / "build-report.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "native-smoke.json").write_text(
            json.dumps(smoke, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "native-release-smoke.json").write_text(
            json.dumps(release_smoke, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "SHA256SUMS.txt").write_text(
            metadata["archiveSha256"] + "  " + archive.name + "\n", encoding="utf-8"
        )
        (out / "START_HERE.txt").write_text(
            "SchoolOps Chrome Setup — unsigned candidate\n\n"
            "Extract the complete archive; keep the app and its support files together.\n"
            "Launch SchoolOps-YouTube-Guard-Setup (the .exe on Windows or .app on macOS).\n"
            "Prepare your websites, publish the generated extension.zip, then reopen\n"
            "that bundle's setup.json to create and apply the enterprise policy.\n"
            "For self-hosting, reopen the prepared bundle, choose Prepare self-hosted release,\n"
            "sign separately, and use Verify HTTPS & export after approved publication.\n"
            "Release signing and signature verification require a separately installed OpenSSL.\n"
            "The app accepts release CLI commands through --release; no private key enters the GUI.\n"
            "The setup app requests administrator access only for an explicit policy action.\n"
            "Chrome installation and website behavior require on-device checks.\n"
            "Use your approved software-distribution process; do not bypass OS security prompts.\n",
            encoding="utf-8",
        )
        os.rename(out, output)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True,
                        help="New, nonexisting output folder for unsigned artifacts")
    args = parser.parse_args()
    path = package(args.output_dir)
    print("Unsigned native GUI artifact created:", path)
    print("No Chrome or system policy has been installed.")


if __name__ == "__main__":
    main()
