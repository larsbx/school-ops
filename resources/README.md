# Resource register

Register reviewed materials used in lessons. A resource may be a book, article,
video, activity, exercise set, or other teaching aid. Its record identifies the
source, intended use, review, and relevant outcomes.

| Resource ID | Provider or author | Title | Status | Resource record |
| --- | --- | --- | --- | --- |

No resources are registered yet.

The [second-grade mathematics search queue](second-grade-math-searches.md) lists
proposed Khan Academy queries for the first course. These are pending searches,
not selected or reviewed resources.

## Review and register a resource

1. Find material for a stated outcome. Use the
   [Khan Academy workflow](../docs/khan-academy.md) for its mathematics exercises.
2. Copy the [resource template](../templates/resource.md) to
   `resources/<resource-id>.md` and assign a stable resource ID.
3. Record the actual source, metadata, review date, starting skills, access needs,
   and outcome fit. Review its contribution to the chosen art and Trivium work;
   provider curricular labels are provenance rather than the curriculum structure.
4. Apply the [resource-specific readiness checks](../docs/curriculum-model.md#resource-readiness).
   Keep the record `draft` until those checks pass; record the review date and
   supporting pull request, then mark it `ready` and add it to this register.
   Link consuming lessons when they are authored.
5. If a resource changes or becomes unavailable, revise its record, update affected
   lessons, and retain the ID. Record a replacement when retiring it.

Instruction and practice resources need a source, intended role/audience, access,
and suitability review. They do not need a lesson sequence or assessment criteria.
For assessment use, link a ready assessment design containing the tasks, conditions,
and criteria. Review that design under the assessment requirements.

A resource can be ready while a consuming lesson is still draft. Preserve existing
register entries when their status changes, and recheck resource readiness after
changes to the source, access, or intended use.

Use source links and attribution. Record reuse rights before storing copies of
external material. Public records hold general sources; class-specific assignment
links belong in private planning.
