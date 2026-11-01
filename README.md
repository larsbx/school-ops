# school-ops

> Storage decision (2026-10-30): [0008 — Curriculum source custody and shared platform storage](docs/decisions/0008-platform-storage-and-operations.md).
> Selected integration target; implementation and cutover remain gated.
> Current services, permissions and durable owners remain in force.

Develop and organize our K–12 curriculum: learning goals, course sequences,
teaching materials, assessments, and weekly plans.

The [Trivium and Quadrivium](docs/trivium-quadrivium.md) organize the curriculum:
grammar, logic, and rhetoric guide inquiry across arithmetic, geometry,
and astronomy. Second grade identifies our starting learners; the course develops
understanding through concrete work, reasoning, and explanation.

This repository is the shared source of truth for curriculum development.
GitHub issues track work; pull requests review changes; the files hold the
current curriculum. Khan Academy is a source of assignable mathematics practice.

## Start here

Our first course is [Second-grade mathematics](curriculum/mathematics/grade-2/README.md).
Start with its [entry check](assessments/C-MATH-001/entry-check.md), then the draft
[place-value unit](curriculum/mathematics/grade-2/units/place-value/README.md).

1. Complete a [scope brief](templates/scope-brief.md) for the first course:
   intended learners, starting skills, chosen arts, goals, and available time.
2. Review the [subject map](curriculum/subject-map.md) and register the course in
   the [curriculum index](curriculum/README.md).
3. Use the [course](templates/course.md), [unit](templates/unit.md), and
   [lesson](templates/lesson.md) templates to connect outcomes, prerequisites,
   activities, and assessments.
4. Select materials through the [resource workflow](resources/README.md).
   For mathematics, follow the [Khan Academy workflow](docs/khan-academy.md).
5. Prepare a [weekly plan](templates/weekly-plan.md), teach the planned work,
   and use the review to update the next plan and curriculum backlog.

For reusable teaching sequences, use the [instructional pattern library](templates/instruction/README.md).
It includes Interchange, Khan-style feedback, test–teach–test, scaffold fading,
retrieval/spacing and inquiry, with original Grade 2 examples and complete keys.
The [M01 two-cycle pilot](curriculum/mathematics/grade-2/units/place-value/two-cycle/README.md)
provides a complete draft learner/workbook/teacher material family.

## Repository map

| Location | Purpose |
| --- | --- |
| [curriculum/](curriculum/README.md) | Subject map, course index, courses, units, and lessons |
| [resources/](resources/README.md) | Reviewed resource register and source records |
| [assessments/](assessments/README.md) | Assessment designs, rubrics, and completion criteria |
| [planning/](planning/README.md) | Weekly plans and curriculum review decisions |
| [tools/](tools/archive_source.py) | Source-archiving crawler and its tests |
| [templates/](templates/README.md) | Reusable briefs, course plans, and teaching documents |
| [docs/curriculum-model.md](docs/curriculum-model.md) | Identifiers, prerequisites, outcomes, and readiness rules |
| [docs/trivium-quadrivium.md](docs/trivium-quadrivium.md) | The seven arts and their application in lessons |
| [docs/roadmap.md](docs/roadmap.md) | Development milestones and acceptance criteria |
| [docs/decisions/](docs/decisions/0001-k12-scope.md) | Recorded curriculum decisions |

> Proposed [decision 0007](docs/decisions/0007-biz-kit-content-authority-and-extension-contract.md)
> preserves this repository as authoritative curriculum content while the SchoolOps
> application uses the shared biz-kit extension/admission boundary.

## Current state

The first subject and grade are selected: second-grade mathematics, `C-MATH-001`.
Its draft includes a course outline, outcomes, an entry check, and six first-unit
lessons with a place-value assessment. Other subject coverage remains open.

The first unit has a prepared two-digit route and separate learner tasks and
teacher keys for two-digit, three-digit, and optional 1,000 checks. Its
[authoring review](docs/reviews/2026-10-09-first-unit.md) records corrections;
teaching records remain draft pending their applicable readiness review.

The organizing framework is selected: the Trivium and Quadrivium. Teaching dates
and weekly time remain undecided.
Seven Khan Academy resources are reviewed for optional place-value practice after
hundreds. The [route review](docs/reviews/2026-10-11-khan-place-value.md) preserves
the two-digit route and records unresolved bounded-practice and thousand gaps.
No teaching results or class assignments have been recorded.
See the [roadmap](docs/roadmap.md) for the remaining development work.

## Working method

Use a curriculum proposal issue to agree on the learning goal and scope. Develop
the material on a branch, review its outcomes and assessment coverage in a pull
request, and merge the reviewed version. A draft may contain open questions;
material marked `ready` must satisfy the [readiness rules](docs/curriculum-model.md).

Keep shared curriculum and teaching plans here. Store learner names, individual
scores, accommodations, and assignment links exposing class details in a private
system. Weekly reviews in this repository record changes to teaching plans.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

The draft [local seeded bank](bank/place-value/README.md) generates PV2/PV3
fluency practice and untimed conceptual forms with separate learner sheets, keys
and reproducible manifests. No learner evidence or teaching readiness is implied.


The [complete draft first-unit teaching pack](curriculum/mathematics/grade-2/units/place-value/teaching-pack/README.md)
provides separate PV2/PV3 teaching routes, learner sheets, teacher keys and print
editions, with record-specific authoring/readiness findings. The course stays draft.

## Managed browser access control (prototype)

The [site-scoped YouTube guard](tools/browser/site_scoped_youtube_guard/README.md)
includes a [graphical setup wizard](tools/browser/site_scoped_youtube_guard/wizard.py),
an MV3 Chrome 145+ extension and testable rule generator that allow
YouTube embeds on an approved school portal while blocking standalone YouTube
navigation. This is **not deployed**, has no real approved hostname yet, and
requires independently enforced Chrome/device management before it is tamper-resistant.
The wizard can prepare a signed-release handoff and Chrome policy, but does not
publish a signed CRX or silently change enterprise management settings.

## Proposed K–12 class and subject scaffolds

Browse the [13 class overviews and 104 grade/subject planning files](curriculum/scaffolds/README.md). They are **not** 91 courses or ready lessons. Each proposes starting evidence, investigation topics and an assessment task, and preserves Grade 2 mathematics as the authoritative authored course.

Islamic studies now has grade-specific proposals throughout K–12. Its [subject guide](curriculum/scaffolds/islamic-studies-guide.md) requires careful Qur'anic attribution, hadith authentication evidence, scholarly context and qualified review. These files are planning scaffolds, not teaching-ready courses.
