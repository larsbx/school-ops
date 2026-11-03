#!/usr/bin/env python3
"""Draft, source-safe Grade 3 metadata practice; NEVER a classroom-ready test.

new: create a fresh, nonpersonal session and separate learner/teacher materials.
resume: verify, read and preserve exactly the saved form (no regeneration).
No learner scores, names, accommodations or external text are stored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import secrets
from pathlib import Path

VERSION = "g3-is-source-metadata-v1"
KINDS = {
    "quran_locator": "Qur'anic passage locator",
    "translation_metadata": "Translation metadata without words",
    "teacher_explanation": "Teacher-created explanation",
    "hadith_locator": "Hadith collection/report locator",
    "fictional_note": "Invented classroom note",
}
CLAIMS = {
    "fictional_quote": "Quotation from a fictional diary",
    "teacher_comment": "Teacher explanation",
    "cautious_inference": "Qualified learner inference",
    "unsupported_claim": "Unsupported historical/authenticity claim",
}
NAMES = ("Hana", "Samir", "Laila", "Yusuf", "Mariam", "Zayd")
OBJECTS = ("notebook", "ruler", "pencil", "folder", "book", "card")
PLACES = ("shelf", "desk", "table", "drawer", "box", "bag")
SESSION_RE = re.compile(r"[0-9a-f]{32}\Z")


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build(session_id: str) -> tuple[str, str, dict]:
    """Produce a reproducible exercise form; all content is original metadata."""
    if not SESSION_RE.fullmatch(session_id):
        raise ValueError("expected a random 32-character lowercase hex session")
    rng = random.Random(int(digest((VERSION + ":" + session_id).encode()), 16))
    name, obj, place = (rng.choice(NAMES), rng.choice(OBJECTS), rng.choice(PLACES))
    tag = session_id[:8].upper()
    records = [
        ("quran_locator", "Qur'an, sūrah 49, āyah 13. Arabic wording and English text not included."),
        ("translation_metadata", "Translation file " + tag +
         ": passage 49:13; translator and edition not selected; English wording absent."),
        ("teacher_explanation", "Classroom author: teacher. Original note: '" +
         rng.choice(("A locator points to a record.", "A summary is not exact source wording.",
                     "Source labels help us look up claims.")) + "'"),
        ("hadith_locator", "Collection: Sahih al-Bukhari; report 8. Text and independent chain study absent."),
        ("fictional_note", "Fictional note " + tag + ": " + name + " placed a " +
         obj + " on a " + place + "."),
    ]
    rng.shuffle(records)
    cards = [{"id": chr(65 + n), "text": value, "kind": kind}
             for n, (kind, value) in enumerate(records)]
    claims = [
        ("fictional_quote", "Invented diary " + tag + " directly says '" +
         name + " saw a " + obj + ".'"),
        ("teacher_comment", "A teacher note says: 'We must check which source words are supplied.'"),
        ("cautious_inference", name +
         " suggests: 'The missing translator field means I cannot quote that translation.'"),
        ("unsupported_claim", "A student says: 'The number of a hadith report by itself proves " +
         "a precise Hijrah route and independently authenticates every narrator.'"),
    ]
    rng.shuffle(claims)
    claim_cards = [{"id": "T" + str(n + 1), "text": value, "kind": kind}
                   for n, (kind, value) in enumerate(claims)]

    learner = [
        "# Grade 3 source-literacy practice — NEW draft session",
        "",
        "- Session reference: " + session_id,
        "- Status: unapproved educational practice, **not** a Qur'an or hadith text.",
        "- No named translator, copied scripture, authenticated report, or actual Hijrah route appears here.",
        "- You may answer orally, on paper, by pointing or AAC. No devotional or personal questions.",
        "",
        "## Record cards",
        "",
        "| Card | Original learning record |",
        "| --- | --- |",
    ]
    learner += ["| " + c["id"] + " | " + c["text"] + " |" for c in cards]
    learner += [
        "",
        "## Task 1 (G3-IS-P1)",
        "",
        "For each record card, classify it as Qur'an locator, missing-translation metadata, "
        "teacher explanation, hadith locator or fictional note. Use each type once.",
        "",
        "## Task 2 (G3-IS-P1)",
        "",
        "Identify the sūrah and āyah of the Qur'an locator, the collection and number of "
        "the hadith locator, and explain why the translator's wording remains unknown.",
        "",
        "## Claim cards",
        "",
        "| Card | Original exercise statement |",
        "| --- | --- |",
    ]
    learner += ["| " + c["id"] + " | " + c["text"] + " |" for c in claim_cards]
    learner += [
        "",
        "## Task 3 (G3-IS-P2)",
        "",
        "Classify each T-card as quotation of a fictional diary, teacher explanation, "
        "qualified learner inference, or unsupported historical/authenticity claim.",
        "",
        "## Task 4 (G3-IS-P2)",
        "",
        "Explain which statement cannot be justified from a report number alone; "
        "also explain why missing translator metadata cannot establish exact English words.",
        "",
        "These cards are original educational fiction and metadata, never primary source words.",
        "",
    ]
    teacher = [
        "# Teacher key — keep separate from learner materials",
        "",
        "- Session reference: " + session_id,
        "- Draft evidence only; no automated religious/source approval or learner grading.",
        "",
        "## Task 1: record classifications",
        "",
    ]
    teacher += ["- " + c["id"] + ": " + KINDS[c["kind"]] for c in cards]
    teacher += [
        "",
        "## Task 2: lookup and uncertainty",
        "",
        "- Qur'an reference: sūrah 49, āyah 13.",
        "- Hadith reference: Sahih al-Bukhari, report 8.",
        "- No chosen translator, edition or English wording supplied. Report number is not authentication.",
        "",
        "## Task 3: claim classifications",
        "",
    ]
    teacher += ["- " + c["id"] + ": " + CLAIMS[c["kind"]] for c in claim_cards]
    teacher += [
        "",
        "## Task 4: model rationale",
        "",
        "- The unsupported claim confuses report metadata with historical evidence and chain review.",
        "- Translation metadata lacking translator/edition/words cannot establish an exact quotation.",
        "- **G3-IS-P1**: 4/5 type labels and both locators. Correct false sacred attribution.",
        "- **G3-IS-P2**: 3/4 claim labels, rejects unsupported claim, and states missing translation words.",
        "- Human teacher judges reasoning; do not infer mastery or assess personal faith or worship.",
        "",
    ]
    learner_text, teacher_text = "\n".join(learner), "\n".join(teacher)
    manifest = {
        "schema": 1, "version": VERSION, "status": "draft-not-ready",
        "session_id": session_id, "records": cards, "claims": claim_cards,
        "learner_sha256": digest(learner_text.encode("utf-8")),
        "teacher_sha256": digest(teacher_text.encode("utf-8")),
    }
    manifest["form_id"] = digest(canonical(manifest))
    return learner_text, teacher_text, manifest


def new_session(output: Path, session_id: str | None = None) -> dict:
    """Create a new directory only. CLI never accepts caller-specified IDs."""
    session_id = session_id or secrets.token_hex(16)
    learner, teacher, manifest = build(session_id)
    output.mkdir(parents=True, exist_ok=False)
    (output / "learner.md").write_text(learner, encoding="utf-8")
    (output / "teacher.md").write_text(teacher, encoding="utf-8")
    (output / "manifest.json").write_bytes(canonical(manifest))
    return manifest


def resume_session(output: Path) -> dict:
    """Validate exact saved artifacts; do not modify them or re-sample tasks."""
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("invalid manifest")
    learner, teacher, expected = build(manifest["session_id"])
    if manifest != expected:
        raise ValueError("saved manifest differs from the versioned form")
    if (output / "learner.md").read_text(encoding="utf-8") != learner:
        raise ValueError("learner sheet differs from saved form")
    if (output / "teacher.md").read_text(encoding="utf-8") != teacher:
        raise ValueError("teacher key differs from saved form")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("new", "resume"))
    parser.add_argument("--output", required=True, type=Path,
                        help="private output directory; never inside Git or learner-public export")
    args = parser.parse_args()
    manifest = new_session(args.output) if args.action == "new" else resume_session(args.output)
    print("Session preserved" if args.action == "resume" else "New independent session created")
    print("Form ID:", manifest["form_id"])
    print("Private artifacts:", args.output)


if __name__ == "__main__":
    main()
