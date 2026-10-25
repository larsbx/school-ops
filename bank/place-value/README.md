# Seeded place-value bank v1

- Bank identifier: `C-MATH-001/place-value`
- Generator: `1.0.1` (legacy `1.0.0` preserved); form schema: `1`
- Status: draft; readiness review pending
- Audience: Grade 2 after demonstrated entry and route prerequisites
- Art: Arithmetic — decimal grouping, conservation under exchanges, repeated steps and order
- Source: original school-ops prompts, following [A-MATH-001-02](../../assessments/C-MATH-001/place-value-check.md)
- Unit: [U-MATH-001-01](../../curriculum/mathematics/grade-2/units/place-value/README.md)
- Developer and administration workflow: [exercise-bank.md](../../docs/exercise-bank.md)

## Route selection and prerequisites

Use the [entry check](../../assessments/C-MATH-001/entry-check.md) and lesson evidence,
not age or a generated score, to select the taught scope. PV2 follows lesson 1 and
the two-digit routes in lessons 3–5. PV3 additionally requires lesson 2's hundreds
and the three-digit routes in lessons 3–5. The unit links every lesson and its checks.
No dates, weekly time or learner skills are inferred.

| Route | Maximum amount in every item and answer | Remains pending |
| --- | --- | --- |
| PV2 | 99; ones/tens only | Hundreds and thousand boundary |
| PV3 | 999; ones/tens/hundreds | Thousand boundary |
| PVX | Not generated; existing separate [supplement](../../assessments/C-MATH-001/place-value-tasks-1000.md) | Further four-digit work |

PVX stays outside the generator. It requires the separate lesson 3 thousand
activity and lesson 4 boundary activity and their checks, as specified in the unit.
There is no automatic extension option, mixed-range test or fallback to larger values.

## Two purposes

**Fluency drills** contain 12 short tasks: three each for composing grouped amounts,
counting five terms, expanding numerals and selecting comparison symbols. A
configurable 1–86,400-second duration and optional local countdown establish a
practice window, not a mastery threshold. The 60-second software default is an
example configuration, not an agreed teaching budget or a validated suitable pace.
Choose duration after readiness review and entry work. Stop at the practice-window
end, then review; unfinished items are not failures. Explanations, complete naming
and conceptual understanding are not assessed by drills.

**Conceptual assessments** contain 12 tasks aligned to the existing PV2/PV3 forms.
No speed threshold applies. The 15–20-minute planning estimate permits extra time
and split sittings. Models and spoken/drawn explanations are required where asked.
Grammar is visible in names, units and symbols; logic in preservation under
exchange, repeated steps and place comparison; rhetoric in explanations another
person can inspect. A timer must never replace these evidence requirements.

## Assessment coverage

Outcome IDs below have prefix `O-MATH-001-`. The manifest records full IDs per item.

| Generated item | Outcome | Required evidence |
| --- | --- | --- |
| 01 | 001 | Model amount; name one-unit and groups; identify every digit amount |
| 02 | 001 | Unpack one ten; PV3 first unpacks one hundred, then one ten; preserve amount at every stage |
| 03 | 001 | Model zero positions and explain absence of additional groups |
| 04 | 001 and 002 | Five consecutive terms across tens (PV2) or hundreds (PV3); explain adding one and each conserving exchange |
| 05 | 002 | Five terms by fives, starting term included; explain step |
| 06 | 002 | Five terms by tens; PV3 also five terms by hundreds; explain counted units |
| 07 | 003 | Name, expanded form and model; connect places to amounts |
| 08 | 003 | Spoken/written number name to numeral and place-value sum |
| 09 | 003 | Groups to numeral, name and sum; explain zero ones |
| 10–12 | 004 | Same-leading-place comparison, different-leading-place comparison, equality; symbols and reasons |

Apply the normative assessment's [outcome criteria](../../assessments/C-MATH-001/place-value-check.md#outcome-criteria),
including every part of each task. All models, conversions, sequences and comparisons
must be correct in their outcome group, with the requested reasons and models.
PV2 does not establish the hundreds component of outcome 001. Do not substitute
a total score, timer completion or drill accuracy for outcome judgments.

## Administration and review

Materials: paper, pencil, counters/bundled sticks or base-ten blocks and a blank
place-value chart; no calculator. Read directions aloud without answer cues.
Accept spoken names with customary “and,” omitted zero sum terms and spelling
support. During an assessment, record answer cues or teaching prompts privately as
support. Use standalone `learner.md` only; keys and manifests remain out of view.

The public repository is not a secure assessment delivery system. A seed generates
a reproducible form, not secrecy or guaranteed novelty; inspect a fresh form before
use. New seeds may still repeat quantities or full prompts. Previously practiced
or exposed applications need fresh reviewed keyed tasks. Give feedback after the
attempt, revisit the specific relationship and reassess in the same taught scope.
Keep independent / supported / needing review / not assessed judgments privately.

This bank and its generated materials remain draft. Before assessment use, review
actual exported tasks, prompt/key agreement, route prerequisites, permitted support,
accessibility, time/materials and outcome criteria under the
[assessment readiness rules](../../docs/curriculum-model.md#readiness-by-record-type).
Record the review date and supporting PR when those checks are complete. Software
tests do not mark this bank, its parent assessment, lessons, unit or course ready.
No learner results are recorded or implied.

## Review examples

Frozen, publicly exposed conceptual forms for authoring review (not fresh independent
assessment applications): [PV2 learner](examples/pv2/learner.md),
[PV2 key](examples/pv2/teacher.md), [PV3 learner](examples/pv3/learner.md),
[PV3 key](examples/pv3/teacher.md). Tests reproduce their manifests and rendered
sheets byte for byte. Use fresh reviewed applications for learner evidence.
