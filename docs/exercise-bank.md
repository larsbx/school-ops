# Developing and using local exercise banks

The first bank is [Grade 2 place value](../bank/place-value/README.md).
Requires Python 3.11 or later; no third-party dependencies, services, learner accounts
or provider APIs. Run from the repository root.

## Generate and validate

```sh
python -m unittest discover -s tests -v
python -m exercise_bank generate --route PV2 --mode drill --seed practice-001 --duration 90 --output /tmp/pv2-drill
python -m exercise_bank validate /tmp/pv2-drill/manifest.json
python -m exercise_bank timer /tmp/pv2-drill/manifest.json
python -m exercise_bank generate --route PV3 --mode assessment --seed check-001 --output /tmp/pv3-check
python -m exercise_bank validate /tmp/pv3-check/manifest.json
```

Select PV2 independently for its conceptual assessment by changing `--route` to
`PV2`. Routes and modes must be explicit. Seeds contain 1–128 ASCII letters,
digits, dots, underscores or hyphens; use non-personal labels. The output directory
must be new; generation never overwrites an existing path. Keep routine exports
outside the repository. No seed may encode a learner identity.

Each export contains:

| File | Audience and role |
| --- | --- |
| `learner.md` | Standalone question sheet; no key or link to teacher files |
| `teacher.md` | Same prompts with key, outcome IDs and item evidence requirements |
| `manifest.json` | Teacher/developer artifact with typed inputs, exact keys, criteria and reproducibility metadata |

Print or export only the learner sheet for learners. A Markdown reader or print
workflow is sufficient; a browser app, PDF exporter and automatic response grader
are outside this first implementation. Teacher keys use explicitly labelled
place-value arrays. Models and explanations require human judgment; keys are
model evidence, not an automated mastery oracle.

`--duration` configures drill seconds. `timer` validates the manifest, then uses a
monotonic clock for a local countdown with start/end messages. It collects no
responses or results. Print the form before starting. Assessment manifests have
null duration and reject the timer command; non-default duration overrides on
assessment generation are rejected. Assessment time remains an adjustable planning
estimate, never a completion deadline.

## Reproducibility contract

The form identity is SHA-256 of canonical JSON excluding `form_id`: UTF-8,
lexicographically sorted keys, no insignificant separators, Unicode unescaped,
with one final LF. Schema 1 includes bank, generator version, route, mode, seed,
range, duration, timing policy, status and ordered typed items. It contains no
creation timestamps, paths, learner identities or machine-dependent state.

Sampling uses SHA-256 over canonical `[generator_version, bank/route/mode, seed]`
followed by the decimal ASCII counter starting at 0. Rejection sampling maps the
256-bit result to an inclusive interval without modulo bias. This is reproducible
item selection, not a cryptographic secrecy claim. Item order is a frozen coverage
blueprint, not a random shuffle. Duration changes form identity, but not questions.
Each form has 12 items; duplicates are possible and no psychometric equivalence
between seeds is claimed.

`validate` checks the content identity, independently recomputes arithmetic and
keys, checks ranges and exact outcome coverage, then verifies the complete form
against its versioned configuration. The separate oracle uses decimal text digits,
number-name parsing, range construction and exchange conservation rather than
calling factory answer helpers. Exact regeneration additionally protects prompt
inputs, criteria and blueprint provenance. Human review still checks the rendered
prompt against the key and curriculum. Hashes are integrity identifiers, not
signatures; an adversary can rehash content, so identity alone is insufficient.

`bank/place-value/golden-ids.json` freezes the four `review-1` forms. Do not simply
refresh fixtures when a test fails. Change generator version for any change to
sampling, blueprint, key, prompt or rendering semantics; change schema for an
incompatible representation. Preserve old generators in versioned modules before
releasing a successor so archived forms remain reproducible. Version 1.0.1 is current; the validator also accepts archived 1.0.0 forms
through `place_value_v1.py`. Original fixtures remain under
`bank/place-value/legacy-v1/`. Version 1.0.1 keeps PV3 assessment item 09
and its item 12 equality pair within 100–990; the old generator can produce
two-digit amounts for those items, so legacy forms need that scope review
before use. Other unsupported versions are rejected.

## Extend to another unit or course

1. Add its draft bank record under `bank/<unit>/`, linked to stable existing course,
   unit and outcome IDs and normative lesson prerequisites and assessment criteria.
   Register it in the [bank index](../bank/README.md). Author curriculum records
   first if the course or outcomes do not yet exist; do not invent observed skills.
2. Implement a separate factory/renderer and independent answer oracle. Use shared
   `core.py` canonicalization, sampling, identity and timing. Give the bank its own
   namespace; keep route/range/extension and fluency/conceptual contracts explicit.
3. Add CLI bank dispatch when a second bank exists rather than adding unrelated
   content to the place-value factory. No claim of existing K–12 content follows
   from reusable engine conventions.
4. Define typed item inputs, full outcome IDs, keys, explanation rubrics and a fixed
   coverage blueprint. Assess prerequisites, boundaries, zero/equality cases and
   permitted supports; do not infer understanding from short-answer accuracy.
5. Add independent arithmetic/key checks, adversarial key/metadata/coverage mutations,
   boundary cases, multi-seed reproduction, frozen fixtures and learner/key separation
   tests. Run CI and manually inspect representative exported learner/key pairs.
6. Open a PR documenting validation and unresolved teaching decisions; apply each
   record's readiness review before marking any teaching material ready.

The GitHub Actions workflow runs the suite on Python 3.11, 3.12 and 3.13. Local
validation on 2026-10-23 passed 11 tests, including 1,000 seed/route/mode forms,
all number names 0–999, seeded boundary coverage, re-sealed key/coverage mutations,
CLI exports/validation and a real one-second drill countdown. Hosted results must
be checked on the PR; local success does not claim hosted execution or learner use.

On 2026-10-25 the PV3 scope regression was fixed with versioned generation,
1,001 targeted seeds and unchanged legacy hashes and rendered fixtures.
