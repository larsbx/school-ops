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
