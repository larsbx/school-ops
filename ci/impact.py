#!/usr/bin/env python3
"""Deterministic, fail-closed change-impact selector for the exercise-bank CI.

The selector only excludes a suite when every changed path is either declared
documentation-only or covered by a known component. Unknown paths trigger full
coverage. This policy is about *test selection*, not proof of correctness.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
from pathlib import Path

POLICY = Path(__file__).with_name("policy.json")
SHA = re.compile(r"^[0-9a-fA-F]{40,64}$")


def matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return fnmatch.fnmatchcase(path, pattern)


def load_policy(path: Path = POLICY) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("version") != 1:
        raise ValueError("unsupported CI impact policy version")
    components = policy["components"]
    suites = policy["suites"]
    if not isinstance(components, dict) or not components:
        raise ValueError("components must be a nonempty mapping")
    if not isinstance(suites, dict) or not suites:
        raise ValueError("suites must be a nonempty mapping")
    for name, component in components.items():
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
            raise ValueError(f"unsafe component name: {name}")
        if not component["paths"] or not all(isinstance(p, str) and p for p in component["paths"]):
            raise ValueError(f"invalid paths for {name}")
        for dependency in component.get("depends_on", []):
            if dependency not in components:
                raise ValueError(f"{name} depends on unknown component {dependency}")
    for name, suite in suites.items():
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
            raise ValueError(f"unsafe suite name: {name}")
        if not suite["components"] or not all(c in components for c in suite["components"]):
            raise ValueError(f"suite {name} has unknown or empty components")
        if not suite["pattern"].startswith("test_") or "/" in suite["pattern"]:
            raise ValueError(f"unsafe test pattern for {name}")
        if suite["directory"] not in ("tests", "tools"):
            raise ValueError(f"unsafe test directory for {name}")
    if not isinstance(policy["full_on"], list) or not isinstance(policy["ignore"], list):
        raise ValueError("full_on and ignore must be lists")
    # A newly added test must never silently disappear from both targeted and
    # scheduled exhaustive runs. Enforce complete test-module registration.
    root = path.resolve().parent.parent
    discovered = {
        p.relative_to(root).as_posix()
        for directory in ("tests", "tools")
        for p in (root / directory).glob("test*.py")
        if p.is_file()
    }
    registered = {
        f"{suite['directory']}/{suite['pattern']}"
        for suite in suites.values()
    }
    unregistered = sorted(discovered - registered)
    if unregistered:
        raise ValueError(f"unregistered test modules: {unregistered}")
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError(f"cycle in component dependency graph at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in components[node].get("depends_on", []):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for name in components:
        visit(name)
    return policy


def changed_files(base: str, head: str) -> list[str]:
    if not SHA.fullmatch(base) or not SHA.fullmatch(head):
        raise ValueError("base/head must be full git object IDs")
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"]
    )
    return sorted(set(p for p in output.decode("utf-8", "strict").split("\x00") if p))


def plan(policy: dict, paths: list[str], force_full: bool = False) -> dict:
    paths = sorted(set(paths))
    components = policy["components"]
    affected: set[str] = set()
    unknown: list[str] = []
    reasons: list[str] = []

    if force_full:
        reasons.append("scheduled/manual/full fallback")
    else:
        for path in paths:
            if any(matches(path, pattern) for pattern in policy["full_on"]):
                reasons.append(f"critical path: {path}")
                continue
            if any(matches(path, pattern) for pattern in policy["ignore"]):
                continue
            matched = {
                name for name, info in components.items()
                if any(matches(path, pattern) for pattern in info["paths"])
            }
            if matched:
                affected.update(matched)
            else:
                unknown.append(path)
        if unknown:
            reasons.append("unmapped paths require conservative full coverage")

    all_suites = sorted(policy["suites"])
    if force_full or reasons:
        selected = all_suites
        mode = "full"
        closure = sorted(components)
    else:
        closure_set = set(affected)
        # Any component using a changed dependency is also affected.
        while True:
            additions = {
                name for name, info in components.items()
                if set(info.get("depends_on", [])) & closure_set
            }
            if additions <= closure_set:
                break
            closure_set.update(additions)
        closure = sorted(closure_set)
        selected = sorted(
            suite for suite, spec in policy["suites"].items()
            if set(spec["components"]) & closure_set
        )
        mode = "targeted" if selected else "documentation-only"
    return {
        "version": 1,
        "mode": mode,
        "changed_paths": paths,
        "direct_components": sorted(affected),
        "affected_components": closure,
        "suites": selected,
        "unknown_paths": unknown,
        "reasons": reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--output", default="ci-plan.json")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    if not args.full and (not args.base or not args.head):
        parser.error("provide --base and --head, or --full")
    policy = load_policy()
    paths = [] if args.full else changed_files(args.base, args.head)
    decision = plan(policy, paths, force_full=args.full)
    output = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    Path(args.output).write_text(output, encoding="utf-8")
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            handle.write("suites=" + json.dumps(decision["suites"], separators=(",", ":")) + "\n")
            handle.write("mode=" + decision["mode"] + "\n")
    print(output, end="")


if __name__ == "__main__":
    main()
