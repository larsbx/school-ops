# Grade 4 water-pathways draft forms

The local generator creates fictional records for reviewers of the
[Grade 4 water-pathways pilot](https://github.com/larsbx/school-ops/pull/61).
It uses the SchoolOps exercise bank's versioned sampler. Starting volumes are
60–140 mL and two-trial means are whole numbers. The teacher key checks the
arithmetic and supplies separate criteria for the pilot's four local outcomes.

Learners compare recorded setups with one changed factor, two changed factors,
or unequal starting volumes. Subtracting the collector reading from the input
gives a calculated amount missing from that collector. The amount's destination
and any physical mechanism remain unknown.

## Generate and replay

Run from the repository root with Python 3.11 or later on a local POSIX
filesystem. Create a dedicated owner-only directory outside the repository.
Use the same directory for forms that share an audience and give each new form
its own session name.

```sh
water_forms_root="$(mktemp -d)"
python3 -m exercise_bank.water_pathways new "$water_forms_root" review-01
python3 -m exercise_bank.water_pathways resume "$water_forms_root" review-01
python3 -m exercise_bank.water_pathways resume "$water_forms_root" review-01 --linear
python3 -m exercise_bank.water_pathways resume "$water_forms_root" review-01 --teacher
```

Each session contains `learner.md`, the equivalent named-entry
`learner-linear.md`, `teacher.md` and the seeded `session.json`.
Keep the key, manifest and root-level `exposures.sqlite3` private. Keep the
registry with the session directories on backup and restore. The generator
blocks known exposed questions and reserves questions across sessions in that
registry. A failed save can leave a reservation, so use a new session name for
a retry. A reviewer must check exposures outside that registry.

## Review before classroom use

A reviewer other than the form preparer must check the exact learner and
teacher copies, including arithmetic, comparison ambiguity, causal language,
prior exposure, prerequisites, reading load, time and the separate outcome
criteria. Confirm equivalent access using large print, neutral read-aloud or
tactile labeled cards as needed. Written, spoken, signed, AAC, typed and exactly
scribed responses can show the same evidence. Review any calculator use
against the arithmetic criterion. The draft uses fictional records and requires
no liquid handling.

Record the independent review and applicable curriculum and teaching-readiness
decisions in private school records. The generator produces review drafts
throughout and collects no learner evidence.
[SchoolOps curriculum readiness model](curriculum-model.md)
