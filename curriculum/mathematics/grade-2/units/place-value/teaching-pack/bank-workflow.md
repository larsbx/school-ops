# Bank workflow for the selected route

Draft • teacher/developer guide • C-MATH-001 / U-MATH-001-01

Use [version 1.0.1](../../../../../../bank/place-value/README.md) after the selected
route's prerequisites and local assessment review. Frozen public examples and
legacy forms are review artifacts. No generator output is an observed learner result.

From the repository root, with Python 3.11 or later:

```sh
python -m exercise_bank generate --route PV2 --mode drill --seed pack-practice-01 --duration 90 --output /tmp/pack-pv2-drill
python -m exercise_bank validate /tmp/pack-pv2-drill/manifest.json
python -m exercise_bank generate --route PV2 --mode assessment --seed pack-check-01 --output /tmp/pack-pv2-check
python -m exercise_bank validate /tmp/pack-pv2-check/manifest.json
```

For PV3 use `--route PV3` and different new output directories. PVX is never
generated. The 90-second drill is an example, not an agreed duration. No real
learner identifiers belong in seeds. Existing output directories are not overwritten.

| Mode | Placement and administration | Decision |
| --- | --- | --- |
| Drill | Optional after instruction in all four sampled relationships, or alongside later review; choose duration locally; print learner sheet before any timer | Review errors and unfinished work; no outcome or speed pass mark |
| Assessment | An untimed alternate application of A-MATH-001-02 in lesson 6 or reassessment after targeted review; allow extra time or split sittings | Check each outcome group and every model/reason; no aggregate score |

Before distribution, inspect all 12 prompts, key/model evidence, range, zero and
boundary cases, exposure and accessibility. Validate the manifest. Print only
`learner.md`; keep `teacher.md` and `manifest.json` away from learners. The manifest
contains answers. A different seed can repeat prompts; inspect freshness against
actual prior practice privately. Use A-MATH-001-02 items 01–03 plus the composition
in 04 for outcome 001; 04–06 for 002; 07–09 for 003; 10–12 for 004.

Read directions without solution cues. Allow objects, blank chart, speech, drawing,
pointing and adult scribing; no calculator. Spelling is not assessed. Recognize
substantive help as support. Give feedback after the attempt. Retain route, generator
version, form ID, support and per-outcome judgments privately. A fresh keyed form
supports reassessment but has no established psychometric equivalence to another seed.
