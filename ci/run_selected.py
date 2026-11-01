#!/usr/bin/env python3
"""Execute exactly the test suites permitted by the validated impact plan."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from impact import load_policy


def main() -> int:
    policy = load_policy()
    selected = json.loads(os.environ["SELECTED_SUITES"])
    if not isinstance(selected, list) or any(
        not isinstance(name, str) or name not in policy["suites"] for name in selected
    ) or len(selected) != len(set(selected)):
        raise ValueError("invalid selected suite set")
    if not selected:
        print("No code suites selected; policy self-tests ran in plan job.")
    failures = []
    for name in selected:
        info = policy["suites"][name]
        directory = Path(info["directory"])
        if not list(directory.glob(info["pattern"])):
            raise ValueError(f"no test module for selected suite {name}")
        print(f"::group::Suite {name}", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover",
             "-s", str(directory), "-p", info["pattern"], "-v"],
            check=False,
        )
        print("::endgroup::", flush=True)
        if result.returncode != 0:
            failures.append(name)
    if failures:
        print(f"Failing suites: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
