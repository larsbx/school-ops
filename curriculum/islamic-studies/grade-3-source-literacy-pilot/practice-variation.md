# Fresh-session practice requirement — Grade 3 Islamic studies

**Executable prototype (draft, not a classroom-approved bank).** The worked learner form and keys are an authoring example; daily practice can instead generate a newly assembled, source-safe form from [the generator](generate_practice.py). This is **not** certified to be psychometrically equivalent or validated Islamic studies teaching.

- For every **new** practice session, the CLI creates a **non-personal random opaque session identifier**, varies original fictional metadata, classroom scenarios, question text and item order, and derives the separated teacher answer mapping from each generated record's type. Qur'an 49:13 and Sahih al-Bukhari 8 remain metadata locators only; **no source quotations are generated**.
- For a **continuing saved session**, the CLI reads and verifies the **same saved form**, manifest and separate teacher key, rejecting edits; it never silently regenerates, reorders or overwrites the session.
- Preserve **five P1 type-classification prompts, two locators, four P2 claim classifications, a rejection of unsupported attribution and an evidence limitation**. Prevent visible key leakage and duplicate tasks.
- Validator verifies versioned deterministic regeneration, canonical form hash and exact bytes of both saved sheets. All generated religious references are text-free. **A generated form ID is not a signature**, a secret or proof of independent religious-source or educational suitability review.
- Do not store a learner ID/score or identifiable seed in this repository; protected delivery lives in SchoolOps operational storage after authorization.
- Teacher and qualified religious-source reviewers still approve actual content. Generation does not prove pedagogical equivalence or religious correctness.

## Use (draft, local, no student records)

From the repository root, with Python 3.11 or later:

```sh
python curriculum/islamic-studies/grade-3-source-literacy-pilot/generate_practice.py new --output /tmp/islamic-grade3-new-session
python curriculum/islamic-studies/grade-3-source-literacy-pilot/generate_practice.py resume --output /tmp/islamic-grade3-new-session
```

The `new` command refuses an existing output directory. It writes `learner.md`, **teacher-only** `teacher.md`, and **teacher/developer-only** `manifest.json`. Never put the last two into a public learner distribution. Do not put learner identifiers, answers or classroom data in the repository or the session ID. Save and resume through **authorized private operations**; this CLI does not implement access controls or a school database.

A new random session gives a distinct form identifier and varied original practice examples; this is **variation, not a formal guarantee of equal difficulty or unbounded novel concepts**. Claim about teacher review, source choice and classroom readiness remains **pending**. The existing Grade 2 mathematics bank is unchanged.
