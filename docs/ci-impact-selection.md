# Change-impact CI (initial pilot)

This repository pilots a change-impact selector for the existing **Exercise bank**
workflow. Its job names remain `validate (3.11)`, `validate (3.12)` and
`validate (3.13)`; all three interpreter versions remain covered. The workflow
is unconditional for pull requests and merge groups. Selection happens after
the workflow starts, so a path-filtered workflow is not mistaken for a passed
required check.

## Contract

- `ci/policy.json` records components, source/test path ownership, directed
  `depends_on` edges, and the unittest module for each suite.
- `ci/impact.py` uses an exact Git comparison base and computes the reverse
  dependency closure. It writes the complete decision to `ci-plan.json`.
- `ci/run_selected.py` executes only allowlisted suite identifiers without a
  shell, and fails when a selected test module is missing.
- Selection self-tests run on **every** PR, including documentation-only PRs.
- Unknown files, CI/workflow changes, and a requested full run select **all**
  suites and execute unrestricted discovery in both `tests/` and `tools/`.
  Any test module not registered in the policy causes validation to fail closed. Invalid policy, invalid diff, and policy self-test failures block CI;
  they never produce a green skip.
- Deletes/renames are compared with `--no-renames` so both sides of a rename
  participate in impact selection. The full clone is needed for merge-base
  calculations.
- Repository Markdown changes select the **teaching** suite because it performs
  repository-wide relative-link and anchor validation. Unknown files still
  select full verification. The selector self-tests and final check always run.
- A nightly scheduled run (04:17 UTC), and manual `workflow_dispatch`, run
  unrestricted test discovery on all three Python versions.
- A constant `Exercise bank required gate` fails unless both selection and
  all selected matrix runs have succeeded.

The selector is deliberately conservative: an unmapped path causes full
coverage. An incorrectly *mapped* path is a policy defect, so changes to that
policy cause a full run and should be reviewed along with nightly full-run
results. This is not a proof that all regressions are discoverable.

The Grade 2 Islamic studies prototype acceptance module is registered as the
`islamic-prototype` suite under teaching. It runs whenever teaching is affected,
including changes to its shared Markdown validation helper. These are static
authoring checks; they do not approve sources or teaching readiness.

## Example selections

| Change | Selected suites |
| --- | --- |
| `README.md` or `docs/guide.md` | islamic-prototype, teaching (repository Markdown links) |
| `exercise_bank/generator.py` | bank, islamic-prototype, teaching |
| `curriculum/scaffolds/new.md` | bank, curriculum, islamic-prototype, teaching |
| `tools/browser/site_scoped_youtube_guard/build_rules.py` | guard, installer, native |
| `ci/policy.json` or `.github/workflows/*.yml` | all |
| unrecognized new file | all |

The existing dedicated Chrome browser-acceptance and native packaging
workflows are **not** removed or replaced by this pilot. Their expensive and
platform-specific checks are independent acceptance obligations.

## Branch protection and rollout

GitHub App access in the initial implementation could not read branch
protection, so its required status checks have **not** been changed. Verify
the repo's rules and pending checks before switching protected status checks.
The original `validate` job ID and Python matrix remain in place as a
compatibility measure; add the constant `Exercise bank required gate` as a
required check once the first PR and merge-group runs pass. Only then consider
removing obsolete required contexts.

The same dependency-aware approach can be generalized across Biz-kit and
the research repositories, but mathematical certificates need content-hash
and transitive proof-dependency invalidation before their exhaustive checks
can be safely skipped. This pilot does **not** weaken those checks.

## Reproduce locally

```sh
python -m unittest discover -s ci -p 'test_*.py' -v
python ci/impact.py --full --output /tmp/ci-plan.json
SELECTED_SUITES='["bank","curriculum"]' python ci/run_selected.py
```
