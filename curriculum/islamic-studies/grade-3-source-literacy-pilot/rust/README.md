# Grade 3 Islamic studies practice — Rust implementation (v2)

**Status: draft generator, not a teaching-ready curriculum, learner grading system, or certified religious resource.** This Rust crate implements the established Grade 3 **G3-IS-P1/P2** source-label and inference exercises; it neither registers a course nor alters the Grade 2 mathematics bank.

## New and resumed sessions

From the repository root, with a supported stable Rust toolchain:

```sh
cargo run --manifest-path curriculum/islamic-studies/grade-3-source-literacy-pilot/rust/Cargo.toml -- new --output /tmp/g3-is-rust-session
cargo run --manifest-path curriculum/islamic-studies/grade-3-source-literacy-pilot/rust/Cargo.toml -- resume --output /tmp/g3-is-rust-session
cargo test --manifest-path curriculum/islamic-studies/grade-3-source-literacy-pilot/rust/Cargo.toml
```

**New** uses the OS's cryptographic random source to create a private 128-bit nonce, derives a deterministic ChaCha20 sampling stream, varies original fictional records and claim order, and creates a **new, previously nonexistent** directory containing `learner.md`, **teacher-only** `teacher.md`, and **teacher/developer-only** `manifest.json`. It cannot overwrite a prior directory or accept a caller-provided nonce on the CLI. The learner sheet carries only a 12-character **one-way public reference**, never the private nonce that would allow key reconstruction.

**Resume** validates the Rust-v2 schema/version, exact canonical manifest and deterministically reconstructed learner/teacher bytes, and leaves all three files unchanged. It fails closed on modification, incomplete artifacts, file symlinks or an unknown version. **A hash detects accidental/inadvertent changes; it is not a signature**. Anyone with access to the private nonce and the public source can reconstruct answers: keep `teacher.md` and `manifest.json` in authorized staff storage, and only distribute `learner.md`.

On Unix, created session directories and files request `0700`/`0600` respectively. On Windows, access depends on inherited ACLs. Do **not** place output inside the public Git checkout or school learner-web directory. If file creation fails midway, the partial directory is not reused; an operator must review/discard it privately.

## Versioning and existing Python sessions

Rust forms use `schema=2` and `version=g3-is-source-metadata-rust-v2`. Sampling and content hashes **are not byte-compatible** with Python `schema=1` (`g3-is-source-metadata-v1`) because the latter uses Python's seeded MT RNG. **Keep [the existing Python v1 generator](../generate_practice.py) for old saved sessions.** Rust `resume` deliberately rejects a Python-v1 manifest without modifying it. Do not silently convert or lose archived forms; a separate reviewed migration would need an explicit evidence and rollback design. The Rust crate is the proposed **new-session default** after acceptance.

The Rust manifest stores five typed source-record items, four typed claim items, an opaque private session nonce, source-corpus-independent mock card text, two SHA-256 sheet digests and a canonical JSON + LF form identifier. Fixed religious **metadata locators** (Qur'an 49:13 and Sahih al-Bukhari 8) are not Arabic scripture, English translations, hadith wording, verified history or an independent authenticity study. A newly generated *form* is not automatically a pedagogically novel *concept* or a psychometrically equivalent test.

## Acceptance

- `cargo test` checks SHA-256 against a known vector, deterministic same-nonce rebuild, changed forms across distinct nonces, exactly five/four unique typed prompts, separate keys, no private nonce in learner output, rejection of invalid nonces, read-only resume, no overwrite, malformed/tampered manifest, modified learner text and cross-version rejection.
- The [change-scoped Rust CI workflow](../../../../.github/workflows/grade3-islamic-practice-rust.yml) tests the crate when relevant files change. The existing Python v1 suite stays in place to prevent legacy-session regressions.
- Qualified source, child-suitability, translation, pedagogical validity, private staff access controls and future SchoolOps integration remain **unresolved human/operational reviews**, not granted by passing Rust tests.
- No learner identities, personal religious practice or assessment results are stored or evaluated in Git.

[Grade 3 pilot](../README.md) · [source review](../source-and-readiness.md) · [practice contract](../practice-variation.md)
