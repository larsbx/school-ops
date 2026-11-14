# Automated Factorio practice checks

SchoolOps and the Learning Lab share a repeatable software check. The private
Factorio repository runs the pinned game engine, exercises the original smelting
and Ratio Loading Bay activities, exports their practice receipts, and checks
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

Both activities currently use original synthetic material. Khan Academy and
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
has its own original draft activity and exact offline receipt mapping. The
existing pinned Factorio PR #7 producer does not create this receipt. The
inspector's synthetic tests are **not** proof of actual game execution. If a
producer supplies a candidate receipt, the integration verifier also requires
the new actual-engine inventory, active/completed reload, and server receipt
gates before classifying it as an unverified practice claim. It does not
pretend that optional candidate inspection updates the immutable compatibility
lock. Owner review and tested producer/consumer revision pins still gate rollout.
