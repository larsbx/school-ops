#!/usr/bin/env python3
"""Build an unsigned, standalone OS-specific SchoolOps GUI bundle with PyInstaller.

Creates a reviewable CI artifact; it does NOT install browser policy, enroll a
device, create a signed CRX, or make the extension tamper-resistant.
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
    flags = ["--onedir"] if system == "Darwin" else ["--onefile"]
    return [
        str(python), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        *flags, "--name", APP,
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
        return dist / (APP + ".exe")
    if system == "Darwin":
        return dist / (APP + ".app") / "Contents" / "MacOS" / APP
    if system == "Linux":
        return dist / APP
    raise ValueError("Unsupported platform")


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

        out = scratch / "output"
        out.mkdir()
        if system == "Windows":
            archive = out / (APP + "-windows-unsigned.exe")
            shutil.copy2(executable, archive)
        else:
            archive = out / (APP + "-" + SUPPORTED[system] + "-unsigned.tar.gz")
            source = (scratch / "dist" / (APP + ".app") if system == "Darwin"
                      else executable)
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
                "published Chrome extension and signed CRX",
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
        }
        (out / "build-report.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "native-smoke.json").write_text(
            json.dumps(smoke, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "SHA256SUMS.txt").write_text(
            metadata["archiveSha256"] + "  " + archive.name + "\n", encoding="utf-8"
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
