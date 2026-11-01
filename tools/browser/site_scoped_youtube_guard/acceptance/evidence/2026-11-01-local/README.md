# Local execution: November 1, 2026

Result: **environment-blocked startup; zero browser network cases and zero
hypothetical DNR probes executed**. This is not evidence of rule correctness or
of a production defect.

The downloaded executable reports Google Chrome for Testing 151.0.7922.34.
Playwright 1.62.1 launched it, but this execution host refused Chrome's profile
socket operation (`process_singleton_posix.cc`, `Operation not permitted`). The
complete report retains configuration/launch metadata and the startup error.
The browser was not running far enough to report its version over CDP; the
`executableVersion` field records the binary's `--version` output instead.

The source commit is the parent checkout with uncommitted harness work. The
report's harness SHA-256 identifies the actual script used in this attempt.
The existing 36 Python tests and Node syntax check passed locally. Browser
acceptance must be established by a compatible execution environment; queued
GitHub Actions are not a passing result.
