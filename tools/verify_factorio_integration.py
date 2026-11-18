#!/usr/bin/env python3
"""Run the pinned Factorio producer and inspect its real-engine practice receipts.

This verifies software compatibility on synthetic disposable saves. Receipts
remain unsigned, replayable practice claims. It never creates learner records,
grades, assignments, provider credentials, or classroom approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

try:
    from .factorio_practice import inspect_receipt, unique_fields
except ImportError:
    from factorio_practice import inspect_receipt, unique_fields


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = Path(__file__).with_name("factorio_integration.lock.json")
FACTORIO_ARCHIVE_SHA256 = "c4efc11529f74d37c96933e291e0db73fd9f5aa4738913d9301b24680b3e947f"
REQUIRED_CHECKS = (
    "real_engine_smelting", "real_engine_ratio", "ratio_reload_active",
    "ratio_reload_complete", "gui_handler_model", "content_binding",
    "deterministic_package", "runtime",
)
SUPPLY_SOURCE_PATHS = frozenset({
    "mods/learning-lab/supply_order.lua",
    "tests/supply_reload.lua",
})
CORE_SOURCE_PATHS = {
    "mod.py", "tools/factorio_runtime.py", "tools/verify_learning_lab.py",
    "tests/learning-lab.lua", "tests/learning-lab-ui.lua",
    "tests/learning_lab_reload.py", "tests/ratio_reload.lua",
    "mods/learning-lab/info.json", "mods/learning-lab/lesson.lua",
    "mods/learning-lab/ratio_bay.lua", "mods/learning-lab/progress_binding.lua",
    "mods/learning-lab/ui.lua",
}
RECEIPTS = {
    "smelting": ("receipts/from-ore-to-plate.json", "L-FACTORIO-SMELTING-01", "R-FACTORIO-001"),
    "ratio": ("receipts/ratio-loading-bay.json", "L-FACTORIO-RATIO-01", "R-FACTORIO-002"),
}
SCHOOL_SOURCE_PATHS = (
    "tools/verify_factorio_integration.py", "tools/factorio_practice.py",
    "tools/factorio_integration.lock.json",
    "curriculum/pilots/factorio/activity.json",
    "curriculum/pilots/factorio/ratio-loading-bay/activity.json",
    "curriculum/pilots/factorio/factory-supply-order/activity.json",
)


class IntegrationError(ValueError):
    """A bounded software acceptance condition was not established."""


def require(condition, message):
    if not condition:
        raise IntegrationError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_string(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def bounded_json(path, maximum=524288):
    with path.open("rb") as source:
        raw = source.read(maximum + 1)
    require(len(raw) <= maximum, "JSON evidence exceeds the byte limit")
    def reject_constant(_):
        raise IntegrationError("non-finite JSON value")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields,
                       parse_constant=reject_constant)
    require(type(value) is dict, "JSON evidence must be an object")
    return value


def local_file(root, relative):
    """Reject report-selected absolute, traversing, or symlinked evidence paths."""
    require(type(relative) is str and relative and "\\" not in relative,
            "invalid relative evidence path")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ".." not in pure.parts and "." not in pure.parts
            and pure.as_posix() == relative, "invalid relative evidence path")
    root = Path(root)
    require(not root.is_symlink(), "evidence root must not be a symlink")
    candidate = root
    for part in pure.parts:
        candidate = candidate / part
        require(not candidate.is_symlink(), "evidence path must not contain symlinks")
    require(candidate.is_file(), "required evidence file is missing")
    require(candidate.resolve().is_relative_to(root.resolve()), "evidence escaped its root")
    return candidate


def load_lock(path=LOCK_PATH, *, allow_local_source=False):
    lock = bounded_json(Path(path))
    require(lock.get("schema") == "schoolops.factorio.integration-lock.v1", "unknown integration lock")
    require(lock.get("repository") == "larsbx/factorio-mods", "unexpected source repository")
    require(lock.get("factorio_version") == "2.0.77", "unsupported engine lock")
    require(lock.get("factorio_archive_sha256") == FACTORIO_ARCHIVE_SHA256,
            "unsupported engine archive digest")
    require(lock.get("mod_version") == "0.3.0", "unsupported mod lock")
    require(lock.get("producer_schema") == "schoolops.factorio.acceptance.v1", "unsupported producer schema")
    hashes = lock.get("source_hashes")
    require(type(hashes) is dict, "source hashes must be an object")
    require(all(type(name) is str and digest_string(value) for name, value in hashes.items()),
            "invalid locked source digest")
    if not allow_local_source:
        require(type(lock.get("revision")) is str and
                re.fullmatch(r"[0-9a-f]{40}", lock["revision"]) is not None,
                "Factorio revision has not been pinned to a published commit")
        require(lock.get("source_status") == "pinned", "source lock is not pinned")
        require(CORE_SOURCE_PATHS <= set(hashes), "source lock lacks required file hashes")
    return lock


def git_identity(root):
    """Read real checkout state; no caller-supplied commit identity is accepted."""
    root = Path(root)
    if not (root / ".git").exists():
        return {"revision": None, "dirty": None, "mode": "local_snapshot"}
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    require(re.fullmatch(r"[0-9a-f]{40}", revision) is not None, "invalid checkout commit")
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                           check=True, capture_output=True, text=True).stdout
    return {"revision": revision, "dirty": bool(dirty), "mode": "git_checkout"}


def verify_source(checkout, lock, *, allow_local_source=False):
    checkout = Path(checkout)
    require(checkout.is_dir() and not checkout.is_symlink(), "Factorio checkout must be a real directory")
    identity = git_identity(checkout)
    if not allow_local_source:
        require(identity["mode"] == "git_checkout", "pinned acceptance requires a Git checkout")
        require(identity["revision"] == lock["revision"], "Factorio checkout differs from the locked commit")
        require(identity["dirty"] is False, "pinned acceptance requires a clean checkout including untracked files")
        for relative, expected in lock["source_hashes"].items():
            require(sha256(local_file(checkout, relative)) == expected, "locked source bytes differ")
    else:
        for relative in CORE_SOURCE_PATHS:
            local_file(checkout, relative)
    return identity


def artifact_file(output, entry, expected_path):
    require(type(entry) is dict and entry.get("path") == expected_path
            and digest_string(entry.get("sha256")), "invalid artifact binding")
    path = local_file(output, entry["path"])
    require(sha256(path) == entry["sha256"], "artifact bytes differ from reported digest")
    return path


def validate_producer(output, checkout, lock, identity, *, allow_local_source=False):
    """Validate this invocation's evidence; not a receipt-authentication service."""
    report = bounded_json(local_file(output, "report.json"))
    require(report.get("schema") == lock["producer_schema"] and report.get("status") == "passed",
            "producer did not report successful bounded acceptance")
    require(report.get("scope") == "headless_software_acceptance"
            and report.get("material_status") == "draft"
            and report.get("receipt_evidence") == "unverified_practice_completion_claim",
            "producer overstates its evidence scope")
    require(report.get("source_revision") == identity["revision"]
            and report.get("source_dirty") is identity["dirty"]
            and report.get("source_mode") == identity["mode"], "producer source identity differs")
    hashes = report.get("source_hashes")
    require(type(hashes) is dict and CORE_SOURCE_PATHS <= set(hashes), "producer source hashes are incomplete")
    for relative, expected in hashes.items():
        require(digest_string(expected), "producer source digest is invalid")
        require(sha256(local_file(checkout, relative)) == expected, "producer source bytes changed")
    if not allow_local_source:
        require(hashes == lock["source_hashes"], "producer source set differs from the lock")
    engine = report.get("engine")
    require(type(engine) is dict and set(engine) == {
                "version", "execution", "binary_sha256", "provisioning", "archive_sha256"
            } and engine.get("version") == lock["factorio_version"]
            and engine.get("execution") == "actual_headless"
            and digest_string(engine.get("binary_sha256")), "actual pinned engine execution was not established")
    require(engine.get("provisioning") in ("official_sha256_archive", "explicit_local_binary"),
            "unknown engine provisioning")
    if engine["provisioning"] == "official_sha256_archive":
        require(engine.get("archive_sha256") == lock["factorio_archive_sha256"],
                "engine archive differs from the pinned official archive")
    else:
        require(engine.get("archive_sha256") is None, "local engine must not claim a verified archive")
    checks = report.get("checks")
    require(type(checks) is dict, "producer checks are missing")
    for name in REQUIRED_CHECKS:
        check = checks.get(name)
        require(type(check) is dict and check.get("status") == "passed"
                and type(check.get("evidence")) is str and bool(check["evidence"]),
                "required producer check did not pass: " + name)
    require(checks["gui_handler_model"].get("kind") == "simulated_lua",
            "GUI callback model must remain explicitly simulated Lua evidence")
    for name in ("desktop_gui", "connected_multiplayer"):
        require(type(checks.get(name)) is dict and checks[name].get("status") == "not_run",
                "this pipeline cannot certify desktop or connected multiplayer acceptance")
    artifacts = report.get("artifacts")
    require(type(artifacts) is dict and type(artifacts.get("receipts")) is dict,
            "producer artifacts are missing")
    inspected = {}
    for name, (relative, activity, resource) in RECEIPTS.items():
        receipt = artifact_file(output, artifacts["receipts"].get(name), relative)
        payload = bounded_json(receipt, maximum=1024)
        require(payload == {
            "schema": "schoolops.factorio.practice.v1", "activity_id": activity,
            "mod_version": lock["mod_version"], "result": "completed",
        }, "runtime receipt is not the exact supported activity/version claim")
        result = inspect_receipt(receipt)
        expected_record = "curriculum/pilots/factorio/" + ("" if name == "smelting" else "ratio-loading-bay/") + "README.md"
        require(result == {
            "schoolops_record": expected_record, "resource_id": resource,
            "activity_id": activity, "material_status": "draft",
            "evidence": "unverified_practice_completion_claim",
        },
                "SchoolOps receipt classification changed")
        inspected[name] = {"receipt_sha256": sha256(receipt), "inspection": result}
    # Optional candidate receipt: never infer actual engine execution from a
    # manually supplied four-field JSON or from catalog registration alone.
    # The immutable lock still governs the original two-receipt baseline.
    candidate = artifacts["receipts"].get("supply_unregistered")
    if candidate is not None:
        # A legacy producer with only baseline sources cannot self-declare
        # supply acceptance by appending a four-field receipt and green gates.
        require(SUPPLY_SOURCE_PATHS <= set(hashes),
                "candidate supply receipt lacks source-bound supply implementation/tests")
        for name in ("real_engine_supply", "supply_reload_active",
                     "supply_reload_complete", "actual_supply_receipt"):
            gate = checks.get(name)
            require(type(gate) is dict and gate.get("status") == "passed"
                    and type(gate.get("evidence")) is str and bool(gate["evidence"]),
                    "candidate supply engine gate did not pass: " + name)
        supply = artifact_file(output, candidate, "receipts/factory-supply-order.json")
        payload = bounded_json(supply, maximum=1024)
        require(payload == {
            "schema": "schoolops.factorio.practice.v1", "activity_id": "L-FACTORIO-SUPPLY-01",
            "mod_version": lock["mod_version"], "result": "completed"
        }, "candidate supply receipt differs from the supported exact payload")
        result = inspect_receipt(supply)
        require(result == {
            "schoolops_record": "curriculum/pilots/factorio/factory-supply-order/README.md",
            "resource_id": "R-FACTORIO-003",
            "activity_id": "L-FACTORIO-SUPPLY-01",
            "material_status": "draft", "evidence": "unverified_practice_completion_claim"
        }, "candidate supply SchoolOps classification differs")
        inspected["supply_candidate"] = {"receipt_sha256": sha256(supply), "inspection": result}
    package = artifact_file(output, artifacts.get("package"), "learning-lab_" + lock["mod_version"] + ".zip")
    return {"producer_report_sha256": sha256(output / "report.json"),
            "producer_source_hashes": hashes, "engine": engine,
            "gui_handler_evidence": "simulated_lua",
            "receipts": inspected, "package_sha256": sha256(package)}


def invoke_producer(checkout, output):
    command = [sys.executable, str(local_file(checkout, "tools/verify_learning_lab.py")),
               "--output", str(output)]
    # Do not copy arbitrary process output into the public review summary.
    # The producer owns bounded logs from disposable synthetic scenarios.
    result = subprocess.run(command, cwd=checkout, capture_output=True, timeout=1200)
    require(result.returncode == 0, "Factorio producer failed; inspect its synthetic-run evidence")


def write_summary(output, report):
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Factorio–SchoolOps software acceptance", "",
             "Status: **" + report["status"] + "**.", "",
             "Source mode: `" + report["acceptance_mode"] + "`.", "",
             "This run uses disposable synthetic practice. Completion receipts remain unsigned, replayable, unverified practice claims.",
             "No learner record, grade, assignment, provider progress, or classroom approval is created.", ""]
    for name, status in report["checks"].items():
        lines.append("- " + name + ": " + status)
    if "verification" in report:
        verification = report["verification"]
        lines.extend(["", "Engine: actual headless Factorio " + verification["engine"]["version"] + ".",
                      "GUI callback evidence: simulated Lua objects; no desktop interaction is claimed."])
    if "failure" in report:
        lines.extend(["", "Failure: " + report["failure"]])
    lines.extend(["", "Desktop visual review and connected multiplayer acceptance remain unexecuted.", ""])
    (output / "review.md").write_text("\n".join(lines), encoding="utf-8")


def run_integration(checkout, output, *, allow_local_source=False, lock_path=LOCK_PATH):
    checkout, output = Path(checkout), Path(output)
    require(not output.is_symlink(), "output must not be a symlink")
    require(not output.resolve().is_relative_to(checkout.resolve())
            and not output.resolve().is_relative_to(REPO_ROOT.resolve()),
            "acceptance output must be outside both source checkouts")
    require(not output.exists() or not any(output.iterdir()), "output must be new or empty; stale evidence is refused")
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "schoolops.factorio.integration-acceptance.v1", "status": "failed",
        "acceptance_mode": "local_source" if allow_local_source else "pinned_git_checkout",
        "scope": "headless_software_compatibility", "material_status": "draft",
        "receipt_evidence": "unverified_practice_completion_claim",
        "checks": {name: "not_run" for name in ("source_binding", "producer_execution", "receipt_compatibility")},
        "unexecuted": ["desktop_visual_review", "connected_multiplayer", "classroom_suitability", "live_provider_integration"],
    }
    active = "source_binding"
    try:
        lock = load_lock(lock_path, allow_local_source=allow_local_source)
        identity = verify_source(checkout, lock, allow_local_source=allow_local_source)
        report["factorio_source"] = identity
        report["schoolops_source"] = git_identity(REPO_ROOT)
        report["schoolops_source_hashes"] = {name: sha256(local_file(REPO_ROOT, name)) for name in SCHOOL_SOURCE_PATHS}
        report["checks"][active] = "passed"
        active = "producer_execution"
        invoke_producer(checkout, output / "producer")
        report["checks"][active] = "passed"
        require(git_identity(checkout) == identity, "source identity changed during execution")
        active = "receipt_compatibility"
        report["verification"] = validate_producer(output / "producer", checkout, lock, identity,
                                                   allow_local_source=allow_local_source)
        report["checks"][active] = "passed"
        report["status"] = "passed"
    except (OSError, ValueError, RecursionError, subprocess.SubprocessError) as error:
        report["checks"][active] = "failed"
        # Only controlled messages are published; malformed private fields and
        # subprocess output are not echoed in a failure report.
        report["failure"] = str(error) if type(error) is IntegrationError else type(error).__name__
    write_summary(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factorio-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-local-source", action="store_true",
                        help="Explicit development mode; does not claim a pinned or hosted revision")
    args = parser.parse_args()
    try:
        report = run_integration(args.factorio_checkout, args.output,
                                 allow_local_source=args.allow_local_source)
    except (OSError, ValueError) as error:
        print("Factorio integration did not run: " + type(error).__name__, file=sys.stderr)
        return 2
    print("Factorio integration: " + report["status"] + " (" + report["acceptance_mode"] + ").")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
