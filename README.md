# school-ops

Develop and organize our K–12 curriculum: learning goals, course sequences,
teaching materials, assessments, and weekly plans.

This repository is the shared source of truth for curriculum development.
GitHub issues track work; pull requests review changes; the files hold the
current curriculum. Khan Academy is a source of assignable mathematics practice.

## Start here

1. Complete a [scope brief](templates/scope-brief.md) for the first course:
   intended grades, starting skills, goals, available time, and any chosen standards.
2. Review the [subject map](curriculum/subject-map.md) and register the course in
   the [curriculum index](curriculum/README.md).
3. Use the [course](templates/course.md), [unit](templates/unit.md), and
   [lesson](templates/lesson.md) templates to connect outcomes, prerequisites,
   activities, and assessments.
4. Select materials through the [resource workflow](resources/README.md).
   For mathematics, follow the [Khan Academy workflow](docs/khan-academy.md).
5. Prepare a [weekly plan](templates/weekly-plan.md), teach the planned work,
   and use the review to update the next plan and curriculum backlog.

## Repository map

| Location | Purpose |
| --- | --- |
| [curriculum/](curriculum/README.md) | Subject map, course index, courses, units, and lessons |
| [resources/](resources/README.md) | Reviewed resource register and source records |
| [assessments/](assessments/README.md) | Assessment designs, rubrics, and completion criteria |
| [planning/](planning/README.md) | Weekly plans and curriculum review decisions |
| [templates/](templates/README.md) | Reusable briefs, course plans, and teaching documents |
| [docs/curriculum-model.md](docs/curriculum-model.md) | Identifiers, prerequisites, outcomes, and readiness rules |
| [docs/roadmap.md](docs/roadmap.md) | Development milestones and acceptance criteria |
| [docs/decisions/](docs/decisions/0001-k12-scope.md) | Recorded curriculum decisions |

## Current state

The repository has a K–12 organizing framework and reusable templates. The
subject map is a proposal; individual course grades and subject coverage remain
to be selected. There are no approved courses, registered teaching resources,
completed assessments, or learner-progress claims yet.

The next milestone is to define the scope of one course and develop its first
unit. See the [roadmap](docs/roadmap.md).

## Working method

Use a curriculum proposal issue to agree on the learning goal and scope. Develop
the material on a branch, review its outcomes and assessment coverage in a pull
request, and merge the reviewed version. A draft may contain open questions;
material marked `ready` must satisfy the [readiness rules](docs/curriculum-model.md).

Keep shared curriculum and teaching plans here. Store learner names, individual
scores, accommodations, and assignment links exposing class details in a private
system. Weekly reviews in this repository record changes to teaching plans.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.
