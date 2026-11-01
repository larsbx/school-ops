# 0008 — Curriculum source custody and shared platform storage

Date: 2026-10-30 (America/Chicago).
Status: **Selected integration target; implementation and cutover gated.**

Shared contract: [biz-kit storage/consolidation ADR](https://github.com/larsbx/biz-kit/blob/adf9d7d7e03e80af650124ce0fdfd02a232cb9b3/docs/architecture/2026-10-30-postgres-event-log-redis-consolidation.md)
([PR #207](https://github.com/larsbx/biz-kit/pull/207)); financial boundary:
[hawala-core ADR 0007](https://github.com/larsbx/hawala-core/pull/57).
These records specify design, not runtime acceptance.

## Context

[Decision 0007](0007-biz-kit-content-authority-and-extension-contract.md) separates curriculum source authority from biz-kit/apps/school_ops staff workflow logic. This repository runs no EventStore, Oban or financial ledger; it needs no datastore deployment.

## Decision

- Git retains curriculum, outcomes, assessments, keys, editorial readiness,
  attribution and reuse rights. Preserve IDs, exact source hashes and immutable
  revision pins. SQL imports and Redis indexes never become the authoring source.
- Hosted staff commands use current signed platform admission. Staff preparation
  completion is not teaching delivery, assessment validity or learner attainment.
  Preserve Trivium/Quadrivium, readiness-by-record-type and the exclusion of music.
- PostgreSQL may retain governed import manifests, workflow/effect receipts and
  bounded projections. Redis may cache revision-bound content indexes and
  schedule reviewed import/review/notification work through the shared worker.
  Add no SchoolOps-specific queue, log or identity issuer.
- Cache identity includes installation, authorized scope, content revision,
  schema and record ID. Missing pinned source fails explicitly; never silently
  use latest. Rebuild from verified source and governed import records.
- Keep learner-specific evidence and class assignment links out of this shared
  repository and public caches. Protected operational data needs a separate
  authorized scope/retention contract; this ADR does not introduce it.
- Hawala/TigerBeetle remains optional. Content import requires no financial
  identity or balance; no staff task establishes payment or settlement.

## Hosted backend inheritance

The [biz-kit SchoolOps architecture](https://github.com/larsbx/biz-kit/blob/main/docs/architecture/2026-10-23-school-ops.md)
owns the implementation of these operational obligations. It consumes the shared
platform contract rather than adding storage services to this repository:

| Concern | Inherited backend contract |
| --- | --- |
| Business admission and authorization | Signed platform admission under current installation/scope grants and revocation; declaration of a school role or content revision confers no permission |
| Durable state and retries | PostgreSQL retains admitted history, original source/effect IDs, immutable content bindings, operational intent and processed receipts; identical retry recovers the original result and changed-body reuse is refused |
| Replay and recovery | Bounded replay through a verified complete prefix; complete consumer bundle, receipt and cursor commit atomically when co-located, or recover through source-bound idempotent admission across transactions; unknown types and sequence gaps stop advancement |
| Scheduling and views | Shared Redis delivery, retry, cancellation and reclaim backed by durable intent/receipts; loss of Redis or a wakeup reconstructs work without duplicate task admission or external notification effects |

Recheck current authority before a scheduled effect. A lease, cached role,
completed preparation task or delivery ACK cannot authorize a school command.
Retain required effect evidence outside expiring caches and ACK only after
durable completion at its owner.

Biz-kit's replacement adapter remains subject to P1–P8; any financial bridge
also retains Hawala S-A1–S-A7 and existing financial release gates. Exact-revision
Lean/Quint refinement, concurrency, crash/replay and Redis-loss evidence belongs
in the backend implementation PR. This content repository neither implements
those adapters nor certifies them by merging an ADR.

## Acceptance and rollout

- Rebuild after Redis deletion and compare source hashes, IDs, links and
  editorial status; reject changed bytes, missing prerequisites and wrong-revision hits.
- Duplicate import/review jobs without duplicate task admission or notifications.
- Verify no personal evidence leaks and staff tasks cannot imply pupil attainment.
- Review links, ID references and readiness fields; no curriculum content changes.

Keep current permissions, services and durable owners until verified replacement,
recovery and single-writer cutover. Recorded historical acceptance does not certify
new adapters. A documentation merge alone moves no live authority.

## Source contracts

[Curriculum model](../curriculum-model.md) and [decision 0007](0007-biz-kit-content-authority-and-extension-contract.md).
