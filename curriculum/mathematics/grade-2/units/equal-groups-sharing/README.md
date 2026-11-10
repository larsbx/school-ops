# Equal groups, sharing, doubling, and halving

- Unit ID: **U-MATH-001-03** (already reserved in [C-MATH-001](../../README.md)); **status: draft, not teaching-ready**.
- Intended audience: Grade 2 after individually checked prerequisites; no assumption that completing Grade 2 Unit 2 establishes readiness.
- Primary Quadrivium art: **arithmetic**. All lessons include grammar (naming the chosen unit and relationship), logic (a count-preserving argument or counterexample), and rhetoric (an explanation another learner can follow). Music excluded.
- Outcome served: **O-MATH-001-013**, restricted here to **equal groups, equal sharing, doubling, and halving**. Unit 2 introduced the **parity/pairing** component. This unit does **not** certify the whole outcome independently; outcomes 005 and 006 supply reviewed prerequisites and incidental practice, not new mastery claims. Outcome 007 (larger place-value calculation) remains unassessed.
- Proposed number route: collections **0–24**; introductory group models use **2–6 groups** with **2–6 objects** per group, while doubling can use a pair of groups of up to **9**; fallback **0–12** after demonstrated counting. Explicitly distinguish group *number*, group *size*, and total. No general times-table fluency, fractions, negative numbers, long division, or multi-digit multiplication.
- Materials: identical counters (at least 24), two to six paper circles/boxes, a blank grid and pencil. Braille/tactile or enlarged representations and equivalent AAC/oral/pointing/scribed responses may replace paper notation.
- Illustrative planning duration: four flexible **25-minute** episodes plus separate diagnostic and untimed independent unit check; neither a timetable nor a pace criterion has been approved. Use flexible breaks.

## Prerequisite entry work and routes

Issue the learner-visible **E1–E3** from [practice sheet](practice-learner.md); the [private teacher key](practice-teacher.md) states the complete responses and decision rules. First review [Unit 1 grouping](../place-value/README.md) and [Unit 2 composition, comparison, and pairing](../composition-difference-parity/README.md) as *source of prior instruction*, not as proof of achievement.

| Skill | Independent evidence required before the corresponding lesson | On missing evidence |
| --- | --- | --- |
| **E1. Count and conserve amount** | Count 12 counters once each and rearrange into rows; explain unchanged total. | Repeat with 6–10 objects, visually/tactually pair and count, recheck with a fresh collection before Episode 1. |
| **E2. Separate equal from unequal parts** | Sort 3 groups of 4 versus groups of 5, 4 and 3; correctly name which is equal and why. | Build disjoint equal groups of 2–3 objects with adult modeling; recheck before Episodes 1–2. |
| **E3. Composition and parity precursor** | Represent 6 + 6 as 12 and demonstrate 12 counters paired with none left; do not infer sharing mastery from pairing. | Revisit Unit 2 composition/parity tasks and recheck before doubling/halving. |

Recheck each unmet skill separately: a total entry score is **not** a substitute. Use the smaller 0–12 route or shorter episodes when warranted; retain the same model/reason criterion. Count with manipulatives and provide read-aloud instructions without mathematical solution cues. Supports are not failures. Actual individual responses are kept **only in private learner records**, never in GitHub.

## Draft teaching progression

1. [Make and explain equal groups](lessons/01-equal-groups.md): count disjoint groups, compare two orientations of a rectangular arrangement, rule out unequal groups.
2. [Share versus group](lessons/02-sharing.md): distinguish a known number of containers from a known number in each container and check by reconstruction.
3. [Double and halve](lessons/03-double-halve.md): construct equal halves for even collections, treat odd leftovers as *not* a whole-number equal split.
4. [Critique and transfer](lessons/04-critique.md): explain a correct claim, identify a faulty grouping argument, complete an independent check.

The [original guided practice](practice-learner.md) is separate from the [complete teacher key](practice-teacher.md). For **new independent sessions** generate a fresh [unit-3 exercise-bank form](../../../../../exercise_bank/unit3.py), after reviewing taught range, task variation and suitability:

```sh
python -m exercise_bank.unit3 new /private/unit3-check-001 --activity check --limit 24
python -m exercise_bank.unit3 resume /private/unit3-check-001
python -m exercise_bank.unit3 resume /private/unit3-check-001 --teacher
python -m exercise_bank.unit3 work /private/unit3-check-001
```

Choose `--limit 12` for the smaller route and `--activity entry|groups|sharing|double|check` for targeted fresh practice. **Every `new` must use a new private directory** and OS-random seed; `resume` verifies and returns exactly the saved form (and `work` continues saved responses). Distribute **only** `learner.md`, keep `teacher.md`, `session.json` and optional `progress.json` private, and never commit session data. Generated prompts and correct answers vary by seed within the taught range, but distinct seeds may still yield equivalent questions; check actual learner exposure rather than assuming uniqueness. Saved-session continuity does not resample. The generator is draft software, not automated grading or approval.

The original fixed [learner check exemplars](../../../../../assessments/C-MATH-001/equal-groups-sharing-learner.md) and [complete teacher key and criterion rubric](../../../../../assessments/C-MATH-001/equal-groups-sharing-teacher.md) supply an independently auditable source contract. **Do not reuse those exposed fixed examples as unseen assessment**; prefer a generated and reviewed check for each new session. The numerical/adapted-route validity of new generated variants still needs human review before teaching.

## Decisions, progress and acceptance boundaries

Collect separately (a) a correct disjoint equal-group drawing/physical model, (b) accurate group size/count/total, (c) a reconstruction or counterexample, and (d) a communicable reason. A bare product or quotient is insufficient. For O-MATH-001-013 review **pairing (Unit 2)** and each of **grouping, sharing, doubling, halving** individually; do not average away missing components. Provide a fresh equivalent independent task after targeted feedback. Teacher and learner must review actual access modes, available materials, range, time, task freshness, and whether a pupil's response was independent; no learner results are asserted here. All records remain **draft** pending the curriculum model's separate course/unit/lesson/assessment readiness reviews, including agreed delivery time and teaching observations.
