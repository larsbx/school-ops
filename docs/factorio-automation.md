# Automated Factorio practice checks

SchoolOps and the Learning Lab share a repeatable software check. The private
Factorio repository runs the pinned game engine, exercises the original smelting, Ratio Loading Bay, and Factory Supply Order
activities, exports their practice receipts, and checks
them with a pinned public SchoolOps inspector. It prepares the mod package and
a review report containing the source revisions and executed checks.

The existing SchoolOps Exercise bank workflow automatically runs receipt and
consumer regression tests on affected changes and its scheduled full run. The
real-engine workflow and its mod ZIP remain in the private Factorio repository.
There is no cross-repository credential requirement in public SchoolOps CI.

## What the owner reviews

The review report distinguishes real headless inventory and save checks,
modeled GUI callback checks, consumer acceptance, and checks that were not
executed. Source and package hashes identify the tested
bytes. A missing engine, failed required check, changed receipt, or changed
source prevents a successful compatibility result.

The activities remain draft guided practice. Desktop presentation, connected
multiplayer, accessibility, teaching time, and classroom suitability retain
their own review decisions. Software success does not approve curriculum or
establish learner mastery.

All three activities currently use original synthetic material. Khan Academy and
Membean content selection, authorized reuse, and provider progress integration
remain separate dependencies. Automation does not invent provider permissions
or copy account information into the mod.

## Learner-data boundary

The acceptance runs use disposable synthetic saves. The receipt inspector
returns an unsigned, replayable `unverified_practice_completion_claim`.
It creates no learner identity association, assignment, learner record, grade,
or provider progress update. Real teaching observations remain in the school's
authorized private workflow.

## Reproduce a supported pair locally

Developers with the private Factorio source can run:

```sh
python3 tools/verify_factorio_integration.py \
  --factorio-checkout /path/to/factorio-mods \
  --output /tmp/schoolops-factorio-review
```

The Factorio checkout must match the immutable compatibility lock and be clean.
Use a new output directory outside both source checkouts. The command invokes
the upstream verifier, checks its actual engine evidence, and inspects the
receipts. `report.json` and `review.md` retain the result, including failure.

During development, `--allow-local-source` explicitly permits an uncommitted
working tree or materialized snapshot and labels the result `local_source`.
That result cannot stand in for exact published-revision or hosted acceptance.
The development flag is not used by the private hosted compatibility workflow.

See [the technical contract](factorio-automation.llm.txt), the
[smelting pilot](../curriculum/pilots/factorio/README.md), and the
[Ratio Loading Bay pilot](../curriculum/pilots/factorio/ratio-loading-bay/README.md).

## New Factory Supply Order candidate

[Factory Supply Order](../curriculum/pilots/factorio/factory-supply-order/README.md)
has its own original draft activity and exact offline receipt mapping.
The proposed reverse lock pins private Factorio producer
`f8f14b42b9f03c489e9a5f72e5458c8d13f5d654`, whose private
[hosted acceptance](https://github.com/larsbx/factorio-mods/actions/runs/44098312981)
passed actual headless Factorio 2.0.77 with the official archive digest.
That producer's three real server-written receipts were inspected by merged
SchoolOps `36688338abe6e3d8eabb4a20c21e45c2b82aeca6`, each only as
a draft unsigned claim. This is **forward producer-side evidence**, not yet
a strict reverse execution of this proposed lock.

The inspector requires the exact rehashed supply implementation and
save/reload sources. It now also rejects a missing, failed or `not_run`
`supply_reissue_guard`: a real saved active checkpoint must refuse to
reissue 17 plates when station references are lost on another surface.
Legacy producers with invented green supply gates are refused. Synthetic
consumer tests do not constitute engine execution. Desktop GUI input,
connected multiplayer, source rights, and classroom review remain separate;
this source lock authorizes none of them.
