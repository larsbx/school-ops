# Development priorities — 2026-10-25

This is a development audit and proposed work order, not a teaching schedule.
Keep the selected Trivium/Quadrivium progression, modern practical usage and
exclusion of music. The [record-type rules](../docs/curriculum-model.md) apply to
the material being reviewed; finishing K–12 is not a prerequisite for using a
reviewed lesson or unit.

## Verified starting point

Audit base: main `ccacc596d63a7b04d33d62bc77636fd93de9f995`.

| Area | Evidence at audit | Consequence |
| --- | --- | --- |
| K–12 scope | [Subject map](../curriculum/subject-map.md) names the intended scope; one course exists | A framework and reusable templates are not completed K–12 coverage |
| Grade 2 arithmetic | [C-MATH-001](../curriculum/mathematics/grade-2/README.md): 13 outcomes, seven proposed units; only unit 1 has six lessons | Finish the existing progression in reviewable units |
| First-unit checks | PV2, PV3, separate keys and optional PVX authored in merged #4 | Teaching/assessment readiness remains pending; preserve taught-range distinctions |
| External practice | Seven optional hundreds-route resources reviewed in merged #5 | Two-digit-only and thousand gaps remain; online completion is not mastery evidence |
| Exercise bank | [#7](https://github.com/larsbx/school-ops/pull/7) open; corrected head `20411367` | New generation is 1.0.1; archived 1.0.0 forms remain reproducible |
| Source archive | [#8](https://github.com/larsbx/school-ops/pull/8) open; corrected head `4f278443` | Collection tooling and source metadata do not supply reviewed lessons or reuse rights |
| Delivery | Weekly time, teaching dates, actual entry skills and materials are unresolved | Authoring can continue; a dated teaching plan needs those local decisions |

The preparation checklist in [#2](https://github.com/larsbx/school-ops/issues/2)
has been corrected to reflect merged #4 and #5. Issue
[#6](https://github.com/larsbx/school-ops/issues/6) stays open until the proposed
bank is merged.

## Repairs completed on the open branches

- **#7:** Require three-digit multiples of ten in PV3 assessment item 09 and its
  item 12 equality pair. Preserve the old factory and original fixtures rather
  than silently changing previously generated forms. Thirteen local tests pass,
  including 1,001 targeted regression seeds, the existing 1,000-form sweep,
  independent arithmetic/key checks and unchanged legacy identities/renderings.
- **#8:** Resume bounded uploads of existing local-only copies, give exact URLs
  distinct storage paths, verify hashes before migrating legacy local copies,
  reject invalid batch sizes before effects, and check the actual Archive.org
  metadata endpoint against robots rules. Twenty-two offline tests pass.
  Missing rclone retains local copies; upload-only failure stops without pruning.
- Both corrected heads pass hosted checks on Python 3.11, 3.12 and 3.13.
  The five existing review findings were addressed and their threads resolved.
  This records the tested corrections, not an independent new review of every
  branch change. Both PRs remain open at this audit.

Existing remote archive aliases have not been audited or migrated. The corrective
work ran no crawl or upload. Source suitability and reuse rights remain unresolved.

## Ordered work

| Priority | Work | Concrete result | Completion evidence |
| --- | --- | --- | --- |
| 1 | Review and integrate the corrected bank | Reusable route-specific local practice and conceptual forms on main | #7 current-head checks, task/key/version review and merge; keep teaching material draft until its own review |
| 2 | [First-unit teaching pack and readiness](https://github.com/larsbx/school-ops/issues/9) | One navigable PV2 or PV3 route with materials, lessons, learner sheets, separate keys and outcome criteria | A dated review identifies exactly which records/scopes pass and which local decisions remain |
| 3 | [Author unit 2](https://github.com/larsbx/school-ops/issues/10) | Complete draft composition, difference, stories and parity lessons with assessment | O-MATH-001-005/006 task-to-key evidence; only the parity portion of 013 is introduced |
| 4 | [K–12 prerequisite/coverage map](https://github.com/larsbx/school-ops/issues/11) | Honest inventory and bounded proposals for later arithmetic, geometry, astronomy and language/reasoning studies | Every proposal has entry evidence, a concrete task, assessment requirement and dependency; unselected scopes stay explicit |
| 5 | Continue Grade 2 units 3–7 | Equal groups/sharing, geometry/measurement, observed sky cycles, applications and synthesis | Each unit has lessons, worked tasks, separate keys and outcome-specific checks before bank expansion |
| Supporting | Integrate and maintain the source archiver | Reliable metadata capture for selected source investigations | #8 checks and merge, followed by source-by-source review before curriculum registration |

First-unit review and unit-2 authoring can proceed while teaching arrangements
remain open. Use the existing record-type rules once per declared scope; do not
add a new approval ladder or require the unfinished whole course to become ready
before a ready unit can be planned.

For the K–12 map, provisional K–2, 3–5, 6–8 and 9–12 bands are authoring bins,
not standards alignment or assumed readiness. Do not create empty course folders
or assign new course IDs merely to fill the table. Grammar, logic and rhetoric
must be visible mathematical/linguistic work, with dedicated language or reasoning
course proposals distinguished from practices already embedded in mathematics.

## Evidence-bank growth

Expand banks after the matching curriculum and outcome criteria exist. Track
route, taught range, outcome/skill component, item family, generator version,
seed/form identity, exposure and review status. A new seed alone does not
guarantee a new question or independent assessment; compare actual prompts/inputs
against earlier published items. Keep public authoring/exposure history separate
from private learner evidence. Timed practice and outcome judgments remain distinct.

## Local decisions needed for delivery

Before a dated weekly plan, record actual available weekly time and dates,
materials/access, and entry evidence selecting the quantity range and review.
These decisions do not block drafting the next unit or mapping missing coverage.
Store learner-specific evidence privately. Make no learner-progress or assignment
claims from repository content.

Recurring review settings are managed separately from this development plan.
This change establishes no new schedule and reports no teaching run.
