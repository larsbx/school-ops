# Curriculum model

## Structure

A subject contains courses. A course contains ordered units; a unit contains
lessons. Each course, unit, and lesson names the learning outcomes it serves.
Assessments define how those outcomes will be demonstrated. Resource records
identify materials used to teach or practice them. Weekly plans schedule the work.

The [Trivium and Quadrivium](trivium-quadrivium.md) govern instructional design.
Course and lesson records name the relevant arts. Grammar, logic, and rhetoric
are practiced together at a level the learner can handle; arithmetic, geometry,
and astronomy supply the selected mathematical studies. Music is excluded.

Use `curriculum/<subject>/<course-slug>/` for a course, with a `README.md` course
record, `scope.md` brief, and `units/<unit-slug>/README.md` unit records. Lessons
live under their unit in `lessons/<lesson-slug>.md`.

Assessment designs live in `assessments/<course-id>/`. Shared resource records
live in `resources/<resource-id>.md`. Register courses and resources in their
respective indexes when adding them.

## Stable identifiers

| Record | Pattern | Example identifier |
| --- | --- | --- |
| Course | `C-<SUBJECT>-<NNN>` | `C-MATH-001` |
| Unit | `U-<SUBJECT>-<NNN>-<NN>` | `U-MATH-001-01` |
| Lesson | `L-<SUBJECT>-<NNN>-<NN>-<NN>` | `L-MATH-001-01-01` |
| Outcome | `O-<SUBJECT>-<NNN>-<NNN>` | `O-MATH-001-001` |
| Assessment | `A-<SUBJECT>-<NNN>-<NN>` | `A-MATH-001-01` |
| Resource | `R-<PROVIDER>-<NNN>` | `R-KHAN-001` |

These illustrate the naming convention; some are now used by the
[second-grade mathematics course](../curriculum/mathematics/grade-2/README.md).
The course and resource indexes identify actual records. Choose subject and
provider codes when adding records. IDs remain stable when titles or paths change;
update links after moves and do not reuse retired IDs.

Define outcomes once in the course outcome table. Units and lessons refer to those
IDs. An outcome describes observable work, such as a skill demonstrated under
stated conditions; the assessment supplies the evidence and success criterion.

## Prerequisites and the chosen arts

List prior outcome IDs with links, or describe an entry skill and how to check it.
Sequence units after their prerequisites. Resolve circular dependencies before
marking the course ready.

Grade level describes our intended starting audience. Establish actual starting
skills through entry work. Define mathematical goals within the chosen arts,
including the language, reasoning, and explanation each task develops. Numerical
ranges and local evidence criteria are curriculum choices to review after entry
work. Provider labels are resource provenance, not the organizing framework.

## Material status

| Status | Meaning |
| --- | --- |
| `draft` | Being developed; unresolved fields and questions remain visible |
| `ready` | Reviewed for the named level and usable with the recorded plan |
| `retired` | Retained for reference; replacement and reason are recorded |

Before marking material `ready`, state its level, prerequisites, outcomes, time,
materials, sequence, and assessment criteria. Verify its internal references and
resource suitability. Remove instructional placeholders. Record the review date
and supporting pull request. Apply the same checks to the child material included
in a ready course or unit.

Status describes teaching material. Learner mastery is a separate judgment based
on the stated assessment criteria; it cannot be inferred from material status or
exercise completion.
