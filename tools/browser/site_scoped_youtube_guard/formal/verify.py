#!/usr/bin/env python3
"""Cold-build the release proofs, audit axioms, and replay the bounded model.

This runner never signs, publishes, changes policy, or contacts an update server.
Install the pinned toolchains first; it does not download executables itself.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD_KEYS = (
    "identity_ok", "version_ok", "zip_ok", "crx_ok", "signature_ok", "tls_ok",
    "manifest_ok", "download_ok",
)


def audit_axioms(output, expected, allowed):
    found = {}
    for line in output.splitlines():
        match = re.fullmatch(r"'([^']+)' (?:depends on axioms: \[([^\]]*)\]|does not depend on any axioms)", line)
        if match:
            name, raw = match.groups()
            if name in found:
                raise ValueError("Duplicate axiom-audit declaration: " + name)
            axioms = set(filter(None, (item.strip() for item in (raw or "").split(","))))
            if not axioms.issubset(allowed):
                raise ValueError("Unexpected axioms: " + repr(sorted(axioms - allowed)))
            found[name] = sorted(axioms)
    if set(found) != set(expected):
        raise ValueError("Axiom-audit inventory differs from the committed obligations")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE / "verification-output")
    parser.add_argument("--lake", default="lake")
    parser.add_argument("--quint", default=str(HERE / "node_modules/.bin/quint"))
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    commands = []

    def run(label, command, expected_code=0):
        result = subprocess.run(command, cwd=HERE, text=True, encoding="utf-8",
                                errors="strict", stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=240, check=False)
        (output_dir / (label + ".log")).write_text(result.stdout, encoding="utf-8", newline="\n")
        commands.append({"label": label, "command": command, "exit_code": result.returncode})
        if result.returncode != expected_code:
            raise RuntimeError(f"{label}: expected exit {expected_code}, got {result.returncode}; "
                               f"see {output_dir / (label + '.log')}")
        return result.stdout

    manifest = json.loads((HERE / "proof-obligations.json").read_text(encoding="utf-8"))
    names = re.findall(r"^theorem (\w+)", (HERE / "Release.lean").read_text(encoding="utf-8"), re.M)
    if names != manifest["theorems"]:
        raise ValueError("Release theorem inventory differs from proof-obligations.json")
    qualified = [manifest["namespace"] + "." + name for name in names]
    audit_names = re.findall(r"^#print axioms (\S+)$", (HERE / "Audit.lean").read_text(encoding="utf-8"), re.M)
    if audit_names != qualified:
        raise ValueError("Audit.lean omits or changes registered proof obligations")
    for source in ("Release.lean", "Audit.lean", "GuardProbe.lean"):
        if re.search(r"\b(sorry|admit|axiom)\b", (HERE / source).read_text(encoding="utf-8")):
            raise ValueError("Untrusted proof placeholder/declaration in " + source)

    lean_version = run("lean-version", [args.lake, "env", "lean", "--version"]).strip()
    quint_version = run("quint-version", [args.quint, "--version"]).strip()
    if not re.search(r"version 4\.19\.0(?:\D|$)", lean_version):
        raise ValueError("Use the pinned Lean 4.19.0 toolchain")
    if quint_version != "0.33.1":
        raise ValueError("Use the locked Quint 0.33.1 dependency")
    run("lean-clean", [args.lake, "clean"])
    run("lean-build", [args.lake, "build"])
    axiom_output = run("lean-axioms", [args.lake, "env", "lean", "Audit.lean"])
    axiom_report = audit_axioms(axiom_output, qualified, set(manifest["allowed_axioms"]))

    # Actual compiler controls: a false theorem must fail, and both a custom
    # assumption and a proof placeholder must be rejected by the axiom auditor.
    with tempfile.TemporaryDirectory(prefix="schoolops-proof-controls-") as td:
        control = Path(td) / "Control.lean"
        control.write_text("import Release\nopen SchoolOps.Release\n"
                           "example : admitted { allChecks with identity_ok := false } = true := by decide\n",
                           encoding="utf-8")
        rejected = run("lean-false-proposition-control", [args.lake, "env", "lean", str(control)], 1)
        if "decide" not in rejected or "false" not in rejected:
            raise ValueError("False-proposition control failed for an unrelated reason")
        control.write_text("axiom external_assumption : False\ntheorem injected : False := external_assumption\n"
                           "#print axioms injected\n", encoding="utf-8")
        injected = run("lean-unexpected-axiom-control", [args.lake, "env", "lean", str(control)])
        control.write_text("theorem placeholder : False := by sorry\n#print axioms placeholder\n", encoding="utf-8")
        placeholder = run("lean-placeholder-control", [args.lake, "env", "lean", str(control)])
        for name, text in (("injected", injected), ("placeholder", placeholder)):
            try:
                audit_axioms(text, [name], set(manifest["allowed_axioms"]))
            except ValueError as exc:
                if "Unexpected axioms" not in str(exc):
                    raise
            else:
                raise ValueError("Axiom auditor accepted the " + name + " control")

    lean_table = run("lean-admission-table", [args.lake, "env", "lean", "--run", "GuardProbe.lean"])
    parsed_lean = {int(mask): value == "true" for mask, value in
                   re.findall(r"^(\d+):(true|false)$", lean_table, re.M)}
    if set(parsed_lean) != set(range(256)):
        raise ValueError("Lean admission table is incomplete")

    run("quint-typecheck", [args.quint, "typecheck", "release.qnt"])
    tests_output = run("quint-tests", [args.quint, "test", "release.qnt", "--backend", "typescript", "--verbosity", "2"])
    if "8 passing" not in tests_output:
        raise ValueError("Expected all eight named Quint scenario checks")
    base_repl = [args.quint, "repl", "--backend", "typescript", "--quiet", "--require", "release.qnt::release"]
    quint_table = run("quint-admission-table", base_repl + ["acceptedMasks", ".exit"]).strip()
    if quint_table != "Set(255)":
        raise ValueError("Quint's full admission projection differs")
    fixed_point = run("quint-exhaustive-closure", base_repl +
                      ["(exhaustiveClosed, exhaustiveSafe, exhaustiveCount)", ".exit"]).strip()
    match = re.fullmatch(r"\(true, true, (\d+)\)", fixed_point)
    if not match:
        raise ValueError("Finite model safety or successor closure failed")
    state_count = int(match.group(1))
    mutants = []
    for label, action in (("manifest-first", "mutantManifestStep"),
                          ("missing-manifest-accepted", "mutantAcceptanceStep")):
        trace_path = output_dir / (label + ".itf.json")
        result = run("quint-control-" + label, [args.quint, "run", "release.qnt", "--backend", "typescript",
            "--step", action, "--invariant", "safety", "--seed", "271828", "--max-samples", "100",
            "--max-steps", "12", "--verbosity", "2", "--out-itf", str(trace_path)], 1)
        if "Invariant violated" not in result:
            raise ValueError("Quint negative control did not find the intended violation")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        states = [row["s"] for row in trace["states"]]
        if label == "manifest-first":
            witness = any(s["activated"] and not s["uploaded"] for s in states)
        else:
            witness = any(s["verified"] and int(s["lastMask"]["#bigint"]) & 64 == 0 for s in states)
        if not witness or trace["#meta"]["status"] != "violation":
            raise ValueError("Quint negative trace lacks its required concrete witness")
        mutants.append(label)

    # This comparison is deliberately narrow: the eight Boolean admission bits,
    # not the implementation's cryptographic or file/network parsers.
    sys.path.insert(0, str(HERE.parent))
    runtime = importlib.import_module("release_core")
    runtime_table = {}
    for mask in range(256):
        guards = {name: bool(mask & (1 << position)) for position, name in enumerate(GUARD_KEYS)}
        runtime_table[mask] = runtime.publication_admitted(guards)
        if type(runtime_table[mask]) is not bool:
            raise ValueError("Runtime admission must return a strict Boolean")
    if runtime_table != parsed_lean or {m for m, accepted in runtime_table.items() if accepted} != {255}:
        raise ValueError("Runtime, Lean and Quint admission projections differ")
    good = dict.fromkeys(GUARD_KEYS, True)
    malformed = [{**good, "unexpected": True}, {}, None, [], True]
    for key in GUARD_KEYS:
        malformed.append({k: v for k, v in good.items() if k != key})
        malformed.extend({**good, key: value} for value in (1, "true", None, [], {}))
    for guards in malformed:
        if runtime.publication_admitted(guards) is not False:
            raise ValueError("Runtime accepted malformed admission guard fields")

    sources = [HERE / name for name in ("Release.lean", "Audit.lean", "GuardProbe.lean", "release.qnt",
               "proof-obligations.json", "verify.py", "lean-toolchain", "package.json", "package-lock.json")]
    sources.append(HERE.parent / "release_core.py")
    source_hashes = {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    report = {"schema": 1, "status": "passed", "scope": "Abstract release state machine and exact eight-Boolean admission projection",
        "excluded": ["cryptographic correctness", "TLS/parser correctness", "complete runtime refinement",
                     "persistent remote availability", "Chrome installation", "managed-device enforcement", "policy changes"],
        "lean_version": lean_version, "quint_version": quint_version,
        "lean_theorems": len(qualified), "axioms": axiom_report,
        "quint_scenario_checks": 8, "quint_reachable_states": state_count,
        "quint_reachability_fixed_point": True, "quint_negative_controls": mutants,
        "admission_assignments_compared": 256, "malformed_runtime_guard_inputs": len(malformed),
        "lean_negative_controls": ["false proposition", "unexpected axiom", "proof placeholder"],
        "source_sha256": source_hashes, "commands": commands}
    (output_dir / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                                  encoding="utf-8", newline="\n")
    print(f"PASS: {len(qualified)} Lean theorems; axiom audit; {state_count} Quint states at successor closure; "
          f"8 scenarios; 5 negative controls; 256 admission assignments; {len(malformed)} malformed runtime inputs")
    print(output_dir / "verification.json")


if __name__ == "__main__":
    main()
