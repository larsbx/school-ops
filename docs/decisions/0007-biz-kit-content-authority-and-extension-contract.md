# 0007 — Curriculum authority and biz-kit SchoolOps extension contract

- Decision date: 2026-10-28
- Status: **proposed cross-repository architecture; no content or runtime migration**
- Paired decisions: [biz-kit extension ADR](https://github.com/larsbx/biz-kit/blob/main/docs/architecture/2026-10-28-cross-repository-extension-and-hawala-capability.md), [hawala-core ADR 0006](https://github.com/larsbx/hawala-core/blob/main/docs/decisions/0006-biz-kit-extension-host-boundary.md), [Eatsbot retirement ADR](https://github.com/larsbx/eatsbot/blob/dev/docs/modules/decisions/pages/biz-kit-interoperability-and-source-ownership.adoc), [d-patch ADR-0015](https://github.com/larsbx/d-patch/blob/main/docs/adr/0015-biz-kit-extension-and-hawala-client-boundaries.md).

## Context

This repository remains the authoritative **curriculum authoring** source: courses, units, lessons, learning outcomes, assessments, keys, resource references and pedagogy. Biz-kit's `apps/school_ops` supplies a distinct **application backend**, currently importing pinned read-only curriculum content and composing platform `TaskCore` workflows. [Biz-kit SchoolOps architecture](https://github.com/larsbx/biz-kit/blob/main/docs/architecture/2026-10-23-school-ops.md) explicitly separates authoring state from staff workflow admission and learner outcomes.

Biz-kit is proposing a versioned application-extension contract to prevent duplicated identity, task and event systems. The related Hawala integration proposals are financial-domain contracts, not a reason to add financial dependencies to this education-content repository.

## Decision

### S1. Keep two different sources of authority

**Curriculum content:** `larsbx/school-ops` owns editorial changes, stable content IDs, outcomes, assessment criteria, versions, review/readiness decisions and the Trivium/Quadrivium organization. Biz-kit may ingest an **immutable, attributed snapshot**, not edit source content through its application ledger.

**School operations:** `biz-kit/apps/school_ops` owns SchoolOps domain application logic and its interface to biz-kit's shared identity, scoped grants, TaskCore, task scheduling, event admission, evidence custody and operational projections. Never introduce competing task writers, principal registries or operational ledgers into this source-content repository.

Learner scores, identities, accommodations, class assignments, attendance, consent and teacher/student relationship grants are **not** public Git curriculum content. They require separate private operational authorization and privacy/retention rules.

### S2. Pin and validate each imported content revision

An import manifest should record:

- Upstream Git repository and exact immutable commit SHA.
- Paths and blob/object digests for every imported asset; stable course/unit/lesson/outcome/assessment identifiers.
- Content format/schema version, completeness and missing references; no silent rewritten IDs or loss of assessment provenance.
- Editorial status (`draft`, reviewed, ready) and review record; a pinned commit is **not** proof a lesson has been taught or that a learner has achieved an outcome.
- Required source attribution, licensing/reuse restrictions and approved external resources; keep references to third-party material rather than copying it without rights.
- Monotonic import/change manifest enabling deterministic rebuild and rollback without rewriting content history.

Validate source graph/duplicate IDs, outcome-to-assessment linkage, answer-key consistency, revision provenance, and missing course prerequisites before publication. Version changes require a new reviewed import, not an untracked copy inside biz-kit.

### S3. Participate in the common extension contract without adding a second runtime

The proposed **BizKit.ExtensionV1** is the *platform's* logical extension contract; no claim is made that such a module already exists. A SchoolOps domain manifest should declare ID, version, supported content schema and source pins, dependencies, capabilities, scoped permissions, commands/events/projections, lifecycle and migration behavior, and reproducible conformance tests.

Use an integrated Elixir adapter in `apps/school_ops`, and a separately versioned import/content format at this repository boundary. A content revision is not an authenticated command; a schema declaration or school role name does not create platform grants. Staff workflow commands must use biz-kit's real authorized admission, not the pure `TaskCore.Workflow.plan/1` preview as if it had committed a task.

A completed staff preparation task records workflow progress only. It does not prove editorial readiness, classroom delivery, individual assessment validity, or pupil learning. Preserve all existing instructional and curriculum review standards.

### S4. Keep Hawala optional and outside the curriculum authority

Hawala-core defines a separate QR-presented identity and Iroh-based financial protocol. A participating biz-kit installation may eventually expose Hawala functionality for authorized business/financial applications. This does **not** mean SchoolOps content imports require Hawala identity, Iroh, custody permissions or financial ledger state.

If a future school business workflow needs a payment, it must use the same general platform and verified Hawala capability boundary as other products, without letting curriculum authoring grant consent, authorize money, or represent financial finality. Financial `Committed(intent)` is not a paid invoice. This ADR makes no decision to build such features.

### S5. Inherit storage through the hosted backend

[Decision 0008](0008-platform-storage-and-operations.md) supplements this
authority split with the selected October 30 storage contract. Its operational
obligations apply to `biz-kit/apps/school_ops`; they introduce no PostgreSQL,
Redis, TigerBeetle or financial identity dependency into curriculum authoring.
The proposed extension contract and its implementation gates remain separate.

## Rollout and verification

1. Review this decision alongside the four platform/financial/product companion ADRs; do not prematurely declare the merged but still-Proposed Hawala native integration ADR pair (#42/#173) accepted.
2. Publish and test the pinned-content import manifest schema, source blob checks and invariant error cases. Reject unpinned updates, duplicate IDs, bad references, teaching-readiness inflation and missing provenance.
3. Implement the SchoolOps domain adapter for the platform's actual extension contract after it is designed; use declared capabilities as *requests*, never authority.
4. Prove real scoped task admission, revocation, duplicate/retry semantics and event replay against the actual biz-kit ledger; keep content authoring and staff-task state independent.
5. Keep learner-personal information, records and payment-related objects out of public imported assets. Add privacy/authorization review before any protected school operational state is stored.

## Consequences

The repository remains an active curriculum production and review system rather than a frozen snapshot or migrated platform codebase. Biz-kit SchoolOps becomes a conforming application consumer of pinned content and reusable platform services. No existing curriculum policy, classroom readiness status or learner evidence changes as a result of this proposed ADR.

This document is **not** an implementation of the extension host, live school commands, personal-records storage or Hawala finance.
