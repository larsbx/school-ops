# Verification and review record

**Local review evidence from 26 November 2026; publication update on
27 November 2026. Not teaching approval.**

Base main: `2aa3eb3a7934a564755823c0fb604ff1bb3b3cfd` (merged PR #67).
The original PR head was `faa1067c93e0eea47422c06cbe5414ba3ebe3efc`.
Its earlier hosted success does not verify this companion increment.

On 27 November 2026 the user explicitly authorized a PR against main and merge
after applicable checks. The local results below describe the original reviewed
snapshot. The companion's PR records its final head revision and hosted results;
neither repository inclusion nor passing CI establishes teaching readiness.

## Source and deterministic extraction

The offline source verifier passed: **8 original NASA/JPL responses, 5,772
position rows, 4 daylight intervals, 16 selected bearings, 8 midpoint rounding
checks and 4 limited USNO Greenwich event comparisons**. All selected bearings
have positive airless model elevation. Source response/receipt/text hashes,
target, body, coordinates, frame, clock and date windows were checked. Derived
JSON and learner-record Markdown are reproduced byte for byte.

The source comparison is limited to Greenwich event labels. No usable second-
provider Sydney or bearing output was obtained. Source snapshots are calculations;
engineering checks and cross-provider agreement are not observations.

## Automated acceptance

All three local interpreter runs passed on Python **3.11, 3.12 and 3.13**:

| Executed discovery | Per interpreter | Result |
| --- | --- | --- |
| `python -m unittest discover -s tests -p 'test*.py' -v` | 277 tests, including the 34 new solar tests | Passed; one existing Windows-registry integration test skipped on Linux |
| `python -m unittest discover -s tools -p 'test*.py' -v` | 22 tests | Passed |
| `python -m unittest discover -s ci -p 'test_*.py' -v` | 21 tests | Passed |

The separate 34-test solar suite also passed on Python 3.12 and 3.13 before the
full runs. Do not add those repeated tests to the full-suite count. The new suite
is registered in the existing impact policy; no required workflow is disabled.

Negative controls cover modified raw bytes and coherently re-pinned wrong
metadata, unexpected time overrides, source coordinates/target/frame/calendar/
refraction, incomplete or duplicate minute samples, nonfinite/missing values,
below-horizon exclusion, half ties and north wrap, fixed-clock date rollover,
sample-order substitution, source/teaching omission separation and original
synthetic-record preservation. Tests parse actual learner/teacher content for
the task-key pairings and numerical agreement. Human reasoning is still scored
against the prose criteria, not certified by matching keywords.

All 27 local Markdown references in the companion resolved in the original
review. The base pilot's original files are unchanged. No hosted workflow was
triggered for the initial 26 November package, which was prepared for review
without publishing changes. Current hosted results belong to the companion PR
and its exact head revision. PR #67's earlier hosted success is separate
historical evidence.

## Independent review findings corrected

- Reject unexpected request parameters, including unreviewed clock overrides.
- Preserve source-missing and below-horizon states instead of presenting them
  as deliberate omissions or numerical learner bearings.
- Bind the task keys to the frozen sample-time order and stated rounding rules.
- Align C11's five source/choice/assumption claims and C12's full evidence limits
  with the machine-readable answer scaffolding and separate teacher key.

## Remaining review

Scientific/source-method admission; Grade 4 suitability and entry skills;
fixed-clock and decimal-rounding scaffolds; accessible equivalent modes and print
review; proposed time allocation; fresh independently reviewed assessment forms;
outcome-specific evidence thresholds; and any eventual course/resource registration.
No learner results, observation evidence, readiness promotion or teaching
approval accompanies this increment. The user-authorized repository publication
does not resolve the scientific or pedagogical review decisions above.
