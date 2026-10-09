# Developing the curriculum

## Make the work reviewable

1. Open a curriculum proposal, curriculum gap, or resource review issue using the
   repository's issue templates. Describe the outcome and intended learner level.
2. Create a focused branch. Copy the relevant [templates](templates/README.md),
   replace placeholders, and keep incomplete material in `draft`.
3. Register new courses in the [curriculum index](curriculum/README.md) and new
   resources in the [resource register](resources/README.md).
4. Open a pull request describing the resulting teaching material and how its
   prerequisites, outcomes, sources, and assessment criteria were reviewed.
5. After review and merge, use the material in a weekly plan. Record curriculum
   changes from the review in a later issue or pull request.

## Review a curriculum change

- Is the intended grade or grade range stated, with starting skills identified?
- Are outcomes observable, and is each one connected to an assessment criterion?
- Does the material identify its Quadrivium art and include grammar, reasoning,
  and explanation as described in the curriculum framework?
- Do prerequisites refer to existing records or explicitly named entry skills?
- Are activities feasible within the stated time and materials?
- Are source titles, links, and review dates recorded accurately?
- Does `ready` material satisfy the [readiness rules](docs/curriculum-model.md)?
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
