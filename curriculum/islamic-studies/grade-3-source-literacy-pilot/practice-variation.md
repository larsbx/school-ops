# Fresh-session practice requirement — Grade 3 Islamic studies

**Design contract only: not an implemented generator.** The worked learner form and keys are for authoring review; they must not be repeatedly delivered as newly generated exercises.

- For every **new** practice session, create a **non-personal opaque session identifier**, independently vary neutral invented record content, citation metadata examples and card order, and derive answers from record types rather than embedded static answer lists.
- For a **continuing saved session**, retrieve its immutable form, source metadata, generator/schema version and separate teacher key by authorized session reference. Do not silently regenerate.
- Preserve **five P1 type-classification prompts, two locators, four P2 claim classifications, a rejection of unsupported attribution and an evidence limitation**. Prevent visible key leakage and duplicate tasks.
- Validate variant-to-key consistency; pin version and canonical content hash; reject forms with fictional scripture/hadith words, invented historical evidence, unavailable texts, insufficient novelty, missing attribution, or conflicting answer/rubric.
- Do not store a learner ID/score or identifiable seed in this repository; protected delivery lives in SchoolOps operational storage after authorization.
- Teacher and qualified religious-source reviewers still approve actual content. Generation does not prove pedagogical equivalence or religious correctness.

Implementation is **next engineering work**, not a completed capability. The existing Grade 2 mathematics exercise bank must be preserved.
