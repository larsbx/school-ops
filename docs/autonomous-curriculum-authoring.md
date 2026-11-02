# Autonomous K–12 curriculum authoring — proposal and review contract

**Decision state: proposed.** This document governs automated *drafting* and structural verification. It does not confer course-registration authority, adopt a timetable, grant religious scholarly approval, establish learner mastery or authorize automatic merging. The human curriculum owner retains final review.

## Automated operating loop

1. **Inspect current evidence:** read `AGENTS.md`, [curriculum model](curriculum-model.md), [classical model](trivium-quadrivium.md), [K–12 matrix](../curriculum/scaffolds/README.md), [course index](../curriculum/README.md), issues, all relevant open PRs and last validated CI results. Do not infer current state from an older assistant summary.
2. **Select one bounded, non-duplicate unit of work:** prefer improving a real author's scope, entry checks, observable goals, actual lesson tasks/teacher keys and assessment alignment over expanding boilerplate. A grade×subject scaffold is a planning record, not a registered course. Inspect open PR file overlap before selecting. Do **not** recreate Grade 2 mathematics or the unregistered Grade 2 Islamic studies prototype.
3. **Check prerequisites and selected arts:** every proposed lesson needs substantive grammar, logic and rhetoric. Supply authentic arithmetic, geometry or astronomy only when those mathematical operations are actually taught and measured. Music is excluded.
4. **Author reproducibly:** each change names its record kind/status; prerequisites and how they are checked; actual learner prompts or clearly designated future plans; teacher/model answers where genuine assessment items are authored; outcome/evidence mapping; accepted supports; scope boundaries and unresolved decisions. Use local planning labels instead of claiming canonical IDs for unapproved courses.
5. **Source and suitability review:** use verified locators and explicit source types, not unverified excerpts or claims of public-domain rights. For Islamic studies distinguish Qur'an, Arabic text, translation, hadith collection/report, commentary, fiqh positions, sīrah and later historical interpretation. Qualified reviews remain required before admission. Do not grade worship, private faith, family practices or sincerity.
6. **Run deterministic checks:** execute scoped unit tests, link/anchor checks, stable-ID/reference checks, spelling and formatting where available, and verify the exact PR-head workflow status. Fix reproducible failures (including pre-existing shared failures where possible on their proper branch), but never call a queued or unrun check passing.
7. **Open or advance a GitHub PR:** present changed paths, original source decisions, prerequisite/assessment mapping, checks actually run, unresolved blockers and reviewer decisions. Prefer one independently reviewable PR per coherent work package, with a title searchable by grade and subject. Avoid identical or overlapping open PRs. It is acceptable to continue creating *independent* drafts while earlier drafts await human review.
8. **Hand off, do not self-approve:** do not auto-merge, declare `ready`, apply governance approvals, assign reviewers, change branch protection or represent independent source/teaching verification as completed. The curriculum owner reviews PRs later. An external scheduler may initiate the loop; GitHub CI supplies deterministic validation, not pedagogical acceptance.

## Parallel pipeline and statuses

| Layer | Automated action | Evidence required | Human-only boundary |
| --- | --- | --- | --- |
| Planning | Find K–12 subject gaps; draft scope and proposed progression; track a non-duplicated PR | Current matrix + repo/PR references | Course selection/adoption and scope approval |
| Authoring | Draft actual learner tasks, teacher keys, explanations, rubrics and prerequisite remediation | Outcome/task crosswalk, clearly labeled source material and original keys | Pedagogical usefulness, classroom fit, faith/fiqh and historical expertise |
| Verification | Verify links, IDs, invariant format, rubric consistency, repeatable exercise answers and CI status | Exact revision and commands/results; disclose unavailable verification | Does not prove validity or classroom readiness |
| Delivery | Open PR with a searchable title and review-blocker checklist | Branch, changed paths, CI link, tested status | Final approval, merge, course registration, scheduled teaching |
| Learning | None on shared GitHub; never fabricate learner records | Privacy rules in `AGENTS.md` | Teaching, learner evidence, accommodations and mastery decisions in private system |

### Work selection / review queue

- Inspect current open PRs before creating a new branch; identify the most advanced unclaimed grade/subject gap and take a bounded next increment.
- Preserve and prefer the authoritative Grade 2 mathematics course. Do not copy its PV2/PV3 items or claim a proposal supersedes it.
- The existing 13×8 scaffold matrix has **planning coverage**, not 104 registered courses. A new grade/subject proposal is an *increment* only when its outcome/prerequisite/lesson/assessment evidence is genuinely more complete than the existing file.
- Islamic studies remains included from K–12, with grade-appropriate epistemic progression and source custody; do not silently upgrade exploratory fiqh, hadith or history into an accepted ruling or authenticated fact.
- Check the most recent grade/subject PRs for text overlap, not only for identical filenames. Do not create a new PR every cycle if an existing one should be advanced.
- Keep **one open PR per coherent independent work slice** where feasible; no mass mechanical PR generation or unnecessary rebases that erase reviewer context.

### Review package checklist (for each PR)

- [ ] Scope identifies proposed versus implemented content and the target grade/subject.
- [ ] Differences from existing work (including open PRs) are explicit.
- [ ] Proposed prerequisites have concrete checks/remediation and accessible alternatives.
- [ ] Grammar, logic and rhetoric work and mathematical arts, where applicable, are explicit and meaningful.
- [ ] Outcomes, tasks and teacher keys agree; automated answer checks are identified.
- [ ] Exact source locators, attribution, authenticity and resource-rights limitations are visible.
- [ ] Islamic studies qualified religious/age/translation review remains visibly unresolved unless evidenced.
- [ ] No invented class timetable, attendance, learner results, private records or `ready` promotion.
- [ ] Branch/head commit, scoped test commands, hosted CI state and unresolved failures are recorded.
- [ ] Human decision items are deferred to curriculum owner; no automatic approval or merge.

## Automation scheduling boundary

A **separate recurring curriculum-builder task** can run the above loop and push draft content through the connected GitHub tools. Existing [school curriculum review](../docs/roadmap.md) continues as a **read-only** weekly audit and exercise proposal. Do not conflate reporting with accepted course registration. GitHub Actions should be used for repeatable structural checks; no GitHub Action is authorized to merge or make theological or educational judgments.

If access, tool permissions, CI, source custody or prerequisite evidence prevent a safe write, publish a precise *blocked/draft* work item with reasons instead of falsely claiming completion.

[Course readiness by record type](curriculum-model.md#readiness-by-record-type) · [K–12 planning index](../curriculum/scaffolds/README.md) · [Islamic studies guide](../curriculum/scaffolds/islamic-studies-guide.md)
