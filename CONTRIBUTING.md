# Developing the curriculum

## Make the work reviewable

1. Open a curriculum proposal, curriculum gap, or resource review issue using the
   repository's issue templates. Describe the outcome and intended learner level.
2. Create a focused branch. Copy the relevant [templates](templates/README.md),
   replace placeholders, and keep incomplete material in `draft`.
3. Register new courses in the [curriculum index](curriculum/README.md) and new
   resources in the [resource register](resources/README.md).
4. Open a pull request describing the resulting teaching material and how its
   applicable record-type requirements were reviewed: courses, units, and lessons
   need sequence and evidence criteria; resources need source, access, and suitability.
5. After review and merge, use the material in a weekly plan. Record curriculum
   changes from the review in a later issue or pull request.

## Review a curriculum change

- Is the intended grade or grade range stated, with starting skills identified?
- For course, unit, lesson, and assessment records, are outcomes observable and
  connected to assessment criteria?
- Does the material identify its Quadrivium art and include grammar, reasoning,
  and explanation as described in the curriculum framework?
- Do prerequisites refer to existing records or explicitly named entry skills?
- Are activities feasible within the stated time and materials?
- Are source titles, links, and review dates recorded accurately?
- Does `ready` material satisfy its [record-type readiness rules](docs/curriculum-model.md#readiness-by-record-type)?
  Instruction/practice resources need no assessment criteria; assessment resources
  link a ready assessment design.
- Are relative links and index entries correct, with stable IDs preserved?

Review documentation by checking its links, references, and teaching completeness.
Introduce automated validation when structured data or runnable code needs it.

## Files and source materials

Use lowercase, hyphenated filenames. Record decisions in
`docs/decisions/NNNN-short-title.md`; preserve dated decisions and add a new
decision when changing direction. Reference external teaching materials with
attribution and links. Record redistribution rights before including copies.

Shared planning documents contain curriculum decisions. Learner-specific evidence
belongs in the private records system; `private/`, `learner-records/`, and
`student-records/` are ignored locally.
