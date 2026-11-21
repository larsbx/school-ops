"""Generate and replay draft Grade 4 fictional water-pathways forms locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sqlite3
import stat
import sys
from contextlib import closing
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory

from .core import Sampler, canonical, seal

VERSION = "water-pathways-session-1"
FACTORS = ("input", "tilt", "surface")
TILTS = ("level", "angled")
SURFACES = ("bare", "cloth")
CLAIMS = {
    "absorbed": "soaked into the surface",
    "evaporated": "evaporated",
}
COMPARISON_LABELS = ("J", "K", "L", "M")
MEMO_LABELS = ("R", "S")
ATTEMPTS = 256
ROOT_DB = "exposures.sqlite3"


@dataclass(frozen=True)
class Trial:
    input_ml: int
    collector_ml: int


@dataclass(frozen=True)
class Setup:
    label: str
    input_ml: int
    tilt: str
    surface: str
    trials_ml: tuple[int, int]


Pair = tuple[Setup, Setup]


@dataclass(frozen=True)
class Form:
    reading: Trial
    comparison: tuple[Setup, ...]
    focus: str
    case_order: tuple[int, int, int]
    disputed: Trial
    claim: str
    memo: Pair


@dataclass(frozen=True)
class Layout:
    controlled: Pair
    case_target: str
    cases: tuple[Pair, ...]


@dataclass(frozen=True)
class PairNumbers:
    means_ml: tuple[int, int]
    gap_ml: int


@dataclass(frozen=True)
class Key:
    reading_remainder_ml: int
    comparison: PairNumbers
    disputed_remainder_ml: int
    memo: PairNumbers
    destination: str = "unknown"


def _choice(rng, choices):
    return choices[rng.integer(0, len(choices) - 1)]


def _shuffle(rng, values):
    pool = list(values)
    return tuple(pool.pop(rng.integer(0, len(pool) - 1)) for _ in range(len(pool)))


def _trial(rng):
    start = rng.integer(60, 140)
    return Trial(start, rng.integer(12, start - 8))


def _setups(rng, labels, conditions):
    rows = []
    used_means = set()
    for label, (start, tilt, surface) in zip(labels, conditions, strict=True):
        choices = [mean for mean in range(18, start - 11) if mean not in used_means]
        mean = _choice(rng, choices)
        used_means.add(mean)
        offset = rng.integer(1, 8)
        readings = _shuffle(rng, (mean - offset, mean + offset))
        rows.append(Setup(label, start, tilt, surface, readings))
    return tuple(rows)


def _candidate(rng):
    focus = _choice(rng, ("tilt", "surface"))
    tilt, other_tilt = _shuffle(rng, TILTS)
    surface, other_surface = _shuffle(rng, SURFACES)
    start = rng.integer(60, 140)
    other_input = _choice(rng, [amount for amount in range(60, 141) if amount != start])
    comparison = _setups(rng, COMPARISON_LABELS, _shuffle(rng, (
        (start, tilt, surface),
        (start, tilt, other_surface),
        (start, other_tilt, surface),
        (other_input, tilt, surface),
    )))

    memo_input = rng.integer(60, 140)
    memo_tilt, alternate_tilt = _shuffle(rng, TILTS)
    memo_surface, alternate_surface = _shuffle(rng, SURFACES)
    alternate = (
        (memo_tilt, alternate_surface) if focus == "tilt"
        else (alternate_tilt, memo_surface)
    )
    memo = _setups(rng, MEMO_LABELS, (
        (memo_input, memo_tilt, memo_surface),
        (memo_input, *alternate),
    ))
    return Form(_trial(rng), comparison, focus, _shuffle(rng, range(3)),
                _trial(rng), _choice(rng, tuple(CLAIMS)), memo)


def setup_facts(row: Setup):
    return row.input_ml, row.tilt, row.surface


def changes(first: Setup, second: Setup) -> tuple[str, ...]:
    return tuple(field for field, left, right in zip(
        FACTORS, setup_facts(first), setup_facts(second), strict=True
    ) if left != right)


def _check_trial(trial: Trial):
    start, collected = trial.input_ml, trial.collector_ml
    if type(start) is not int or not 60 <= start <= 140:
        raise ValueError("input must be a whole number from 60 to 140 mL")
    if type(collected) is not int or not 0 <= collected < start:
        raise ValueError("collector reading must be a whole number below input")


def collector_mean(row: Setup) -> int:
    total = sum(row.trials_ml)
    mean, remainder = divmod(total, 2)
    if remainder:
        raise ValueError("two collector trials must have a whole-number mean")
    return mean


def _check_rows(rows, labels):
    if tuple(row.label for row in rows) != labels:
        raise ValueError("unexpected setup labels")
    means = set()
    for row in rows:
        if row.tilt not in TILTS or row.surface not in SURFACES:
            raise ValueError("unknown recorded setup label")
        if len(row.trials_ml) != 2 or row.trials_ml[0] == row.trials_ml[1]:
            raise ValueError("expected two distinct collector trials")
        for collected in row.trials_ml:
            _check_trial(Trial(row.input_ml, collected))
        means.add(collector_mean(row))
    if len(means) != len(rows):
        raise ValueError("expected distinct collector means within each record")


def inspect_form(form: Form) -> Layout:
    """Derive pair roles from the displayed records and reject ambiguous forms."""
    _check_trial(form.reading)
    _check_trial(form.disputed)
    _check_rows(form.comparison, COMPARISON_LABELS)
    _check_rows(form.memo, MEMO_LABELS)
    if form.focus not in ("tilt", "surface") or form.claim not in CLAIMS:
        raise ValueError("unknown question kind")
    if (any(type(index) is not int for index in form.case_order)
            or sorted(form.case_order) != [0, 1, 2]):
        raise ValueError("comparison cases must each appear once")

    pair_by_changes = {changes(*pair): pair for pair in combinations(form.comparison, 2)}
    expected = {
        ("tilt",), ("surface",), ("tilt", "surface"),
        ("input",), ("input", "tilt"), ("input", "surface"),
    }
    if pair_by_changes.keys() != expected:
        raise ValueError("ambiguous or missing recorded comparison")
    target = "surface" if form.focus == "tilt" else "tilt"
    if changes(*form.memo) != (target,):
        raise ValueError("memo must isolate its recorded setup difference")
    cases = (pair_by_changes[(target,)], pair_by_changes[("tilt", "surface")],
             pair_by_changes[("input",)])
    return Layout(pair_by_changes[(form.focus,)], target,
                  tuple(cases[index] for index in form.case_order))


def _trial_signature(trial: Trial):
    return ("subtraction", trial.input_ml, trial.collector_ml)


def _mean_signature(row: Setup):
    return ("mean", *sorted(row.trials_ml))


def _comparison_signature(pair: Pair):
    return ("comparison", *sorted(setup_facts(row) for row in pair))


def signatures(form: Form, layout: Layout):
    """Use the facts a question tests, ignoring labels, wording and trial order."""
    return (
        _trial_signature(form.reading),
        _trial_signature(form.disputed),
        *(_mean_signature(row) for row in (*layout.controlled, *form.memo)),
        *(_comparison_signature(pair) for pair in (layout.controlled, *layout.cases, form.memo)),
    )


def _exposed_signatures():
    # Pinned PR #61 Packet A and Packet T, including source-driven G/X/S prompts.
    packet_a = (
        Setup("A", 100, "angled", "bare", (72, 68)),
        Setup("B", 100, "angled", "cloth", (41, 39)),
        Setup("C", 100, "level", "bare", (26, 30)),
    )
    packet_t = (
        Setup("D", 80, "angled", "bare", (60, 56)),
        Setup("E", 80, "angled", "cloth", (36, 40)),
        Setup("F", 80, "level", "bare", (22, 26)),
        Setup("G", 120, "angled", "bare", (86, 90)),
    )
    blocked = {_trial_signature(Trial(70, 46))}  # Entry E1.
    for packet in (packet_a, packet_t):
        for row in packet:
            blocked.add(_mean_signature(row))
            blocked.update(_trial_signature(Trial(row.input_ml, reading))
                           for reading in row.trials_ml)
        blocked.update(_comparison_signature(pair) for pair in combinations(packet, 2))
    # Entry E3 leaves the matching tilt label unspecified.
    for tilt in TILTS:
        blocked.add(("comparison", (80, tilt, "bare"), (80, tilt, "cloth")))
    return frozenset(blocked)


# The two exposed review copies contribute fingerprints only.
DEMONSTRATION_DIGESTS = frozenset({
    "080360cd1227f814126212f5e83c5523f382e3f2d47dd8ffd89e1abbc14de109",
    "10722a7da70adca656901685a4d4868cf11417050c09e995a06eb8222e93cff0",
    "1de6953961b71ddc78eaa2fca30dfb935fd8b41f8e24463868e6ff8f4634ddf1",
    "29ff2e330e3d5d8a4e07fa8c6187311e146bc5675588a8b8a3d0f513ddcaacb8",
    "34e13b36f36c5271573519b99ba2fc5d27bbcb897145246591b4efa8c08d3482",
    "398bc4aa9b8c0e274ca55df7eb905204a87a8f7c870f6f9819f899e843bfd339",
    "47d9e8d334090769a1500614ecb606c318da2337be3877587e391e9dffa6057f",
    "498e2826e9aed90e5554cdec523a4a01adfc9a42a3651ad35e6026461e4745a3",
    "65d19e65904420e2846b38ccf1f83f45c8acc3d1f80685c0fb90da9fcd04881a",
    "6ac8faf331ed4c12fe287710813f1999c000991e1be46584a18e6d615c6cd2b4",
    "6b9f042f26d3805f8aeff66b1db23f7ff123584178a246934730ac7fa4e680eb",
    "6e6989da658a691a64e5728b0693ad480fa8ae1b9a91c71870c70f81d82dc3c1",
    "7ba37ca87e346df2057890d58f0abbaccb9217cc6b5d357f1be6261d16330ee7",
    "82d5064e8b8495f0728fc90de2935c18c38f080b279c8ba7a0968c727ef64b75",
    "8ce82523c8b4bee29c7cc5a7d10e66b6a7a54f5df08d131cf1dc28f5b7210471",
    "a67b56c93d8633c7867fed7a2b8188a0cc0fe28c56a2a3d69105422caddea6f2",
    "ab6d99e0ac95c7a3bb7312a02320f5e7052f2259081a8ca589041001728b61d4",
    "b2d27c96b18432802501598dbabdffdb1ad82e22ab4e79852c36812731011cea",
    "b9876799bfabffb1b021bf69ee24cf9ceb41c32f87fa3ef713aab8fc9611bd91",
    "c1e3d2ee6f0dab598398ef736b32fc57ed7d7b2dc2782408db76034bfdecfa99",
    "dc75427e16dacbf16608239f80185a41692eb30174c8601e1598dfc301acc7b5",
    "e5e368c8c3dd6a1e8d8c5bb4b7ea3400ae378a3edf50c6e2e7792fdfd2259732",
})
EXPOSED = _exposed_signatures()


def generate(seed: str) -> Form:
    """Generate a replayable candidate. Session issuance also checks exposure."""
    if not isinstance(seed, str) or not re.fullmatch(r"[0-9a-f]{32}", seed):
        raise ValueError("invalid private session manifest")
    rng = Sampler("grade4-water-pathways", seed, version=VERSION)
    for _ in range(ATTEMPTS):
        form = _candidate(rng)
        layout = inspect_form(form)
        values = signatures(form, layout)
        if len(values) == len(set(values)):
            return form
    raise ValueError("could not generate distinct draft questions")


def _pair_numbers(pair: Pair) -> PairNumbers:
    first, second = map(collector_mean, pair)
    return PairNumbers((first, second), abs(first - second))


def make_key(form: Form, layout: Layout) -> Key:
    key = Key(
        form.reading.input_ml - form.reading.collector_ml,
        _pair_numbers(layout.controlled),
        form.disputed.input_ml - form.disputed.collector_ml,
        _pair_numbers(form.memo),
    )
    verify_key(form, layout, key)
    return key


def verify_key(form: Form, layout: Layout, key: Key):
    """Check inverse arithmetic and the limits of the recorded measurements."""
    for trial, remainder in ((form.reading, key.reading_remainder_ml),
                             (form.disputed, key.disputed_remainder_ml)):
        if type(remainder) is not int or remainder < 0:
            raise ValueError("invalid remainder")
        if trial.collector_ml + remainder != trial.input_ml:
            raise ValueError("remainder does not reconcile with input")
    for pair, numbers in ((layout.controlled, key.comparison), (form.memo, key.memo)):
        for row, mean in zip(pair, numbers.means_ml, strict=True):
            if type(mean) is not int or 2 * mean != sum(row.trials_ml):
                raise ValueError("mean does not reconcile with trials")
        low, high = sorted(numbers.means_ml)
        if type(numbers.gap_ml) is not int or numbers.gap_ml < 0 or low + numbers.gap_ml != high:
            raise ValueError("gap does not reconcile with means")
    if key.destination != "unknown":
        raise ValueError("collector-only data cannot establish a destination or physical cause")


def _record(title, rows, linear):
    heading = f"## {title}\n"
    if linear:
        return "\n".join([heading, *[
            f"- Setup {row.label}. Input {row.input_ml} mL. Tilt {row.tilt}. "
            f"Surface {row.surface}. Trial 1 collector {row.trials_ml[0]} mL. "
            f"Trial 2 collector {row.trials_ml[1]} mL."
            for row in rows
        ]])
    return "\n".join([
        heading,
        "| Setup | Input (mL) | Tilt | Surface | Trial 1 collector (mL) | Trial 2 collector (mL) |",
        "| --- | ---: | --- | --- | ---: | ---: |",
        *(f"| {row.label} | {row.input_ml} | {row.tilt} | {row.surface} | "
          f"{row.trials_ml[0]} | {row.trials_ml[1]} |" for row in rows),
    ])


def _pair_label(pair: Pair):
    return f"{pair[0].label} and {pair[1].label}"


def _review_status(example):
    if example:
        return "**Exposed synthetic example for review.**\n\n"
    return ""


def render_learner(form: Form, *, linear=False, example=False) -> str:
    """Render only recorded values, fixed prompts and access instructions."""
    layout = inspect_form(form)
    trial = form.reading
    disputed = form.disputed
    proposals = "\n".join(f"- {_pair_label(pair)}" for pair in layout.cases)
    return (
        "# Water-pathways assessment draft\n\n"
        + _review_status(example)
        + "**Independent review required before classroom use.** These are made-up records.\n\n"
        "Input is the water at the start of each trial. The collector holds water caught during a "
        "trial. The setup entries are input, tilt, and surface. Tilt tells whether a setup "
        "is level or angled. mL means milliliters.\n\n"
        "Include units for amounts. You can write, type, speak, sign, or use a communication aid "
        "or a scribe. You may read a table or use the same entries as a list or on labeled cards. "
        "You can ask for the directions and entries to be read aloud.\n\n"
        "## 1. Read one trial\n\n"
        f"The input was {trial.input_ml} mL. The collector held {trial.collector_ml} mL. "
        "Name the two recorded amounts. Work out how much water was not in the collector. "
        "Can this record tell you where that amount ended up? Explain.\n\n"
        + _record("Comparison record", form.comparison, linear)
        + "\n\n## 2. Choose and compare\n\n"
        f"Choose the two setups that differ only in {form.focus}. Name the entries that "
        "match. Find the mean (average) of the two collector readings for each setup. "
        "Show your calculations and find the difference between the means.\n\n"
        "## 3. Check three proposed pairs\n\n"
        f"For each pair, could you compare a change in {layout.case_target} alone, with "
        "the same input? Name the entries that match and any entries that differ.\n\n"
        f"{proposals}\n\n"
        "## 4. Check a statement about another trial\n\n"
        f"The input was {disputed.input_ml} mL. The collector held {disputed.collector_ml} mL. "
        f"A student says, “All the water that was not in the collector {CLAIMS[form.claim]}.” "
        "Work out how much water was not in the collector. Explain what you can check with this "
        "record and what evidence would help you decide whether the student is right.\n\n"
        + _record("Record for your note", form.memo, linear)
        + "\n\n## 5. Write or tell a short note\n\n"
        "Use the made-up record for your note. Say where your numbers came from. Give the two "
        "mean collector readings and their difference. Say what matches and differs in the setups. "
        "Include one thing the record leaves unanswered.\n\n"
        "## 6. Plan one extra measurement\n\n"
        "If you repeated the comparison in question 5, name one extra measurement that could "
        "help you find water that was not in the collector. Say what it would tell you, which two "
        "setup entries you would keep the same, and why the table or list cannot give you "
        "the new measurement.\n"
    )


def _settings(pair: Pair):
    return " compared with ".join(
        f"{row.label} ({row.input_ml} mL input, {row.tilt}, {row.surface})" for row in pair
    )


def _mean_work(pair: Pair, numbers: PairNumbers):
    equations = [
        f"{row.label} ({row.trials_ml[0]} + {row.trials_ml[1]}) ÷ 2 = {mean} mL"
        for row, mean in zip(pair, numbers.means_ml, strict=True)
    ]
    low, high = sorted(numbers.means_ml)
    return ", ".join(equations) + f". Difference {high} − {low} = {numbers.gap_ml} mL."


def _pair_explanation(pair: Pair, focus: str):
    different = changes(*pair)
    fixed = ", ".join(factor for factor in FACTORS if factor not in different)
    answer = "Yes" if different == (focus,) else "No"
    return (f"- {_pair_label(pair)}. **{answer}.** Changes in {', '.join(different)}. "
            f"Matches in {fixed}. {_settings(pair)}.")


def render_teacher(form: Form, *, example=False) -> str:
    layout = inspect_form(form)
    key = make_key(form, layout)
    trial = form.reading
    disputed = form.disputed
    model_cases = "\n".join(_pair_explanation(pair, layout.case_target) for pair in layout.cases)
    fixed = "tilt" if layout.case_target == "surface" else "surface"
    return (
        "# Water-pathways teacher key for private review\n\n"
        + _review_status(example)
        + "**Independent review required before classroom use.** "
        "This is a draft for fictional data. Keep the key with the reviewer.\n\n"
        "## Worked answers\n\n"
        f"**1.** The reported input is {trial.input_ml} mL and the collector reading is "
        f"{trial.collector_ml} mL. {trial.input_ml} − {trial.collector_ml} = "
        f"{key.reading_remainder_ml} mL not in the collector. The destination is unknown "
        "because the record only reports input and collector volume.\n\n"
        f"**2.** {_pair_label(layout.controlled)} differ in recorded {form.focus} only. "
        f"{_settings(layout.controlled)}. {_mean_work(layout.controlled, key.comparison)} "
        "This is a comparison within the fictional record.\n\n"
        f"**3.** Comparing {layout.case_target} alone at equal input.\n\n{model_cases}\n\n"
        f"**4.** {disputed.input_ml} − {disputed.collector_ml} = "
        f"{key.disputed_remainder_ml} mL not in the collector. This amount comes from "
        f"subtraction. The destination is unknown. A separate measurement of water "
        f"{form.claim} would be needed to support that claim.\n\n"
        f"**5.** In the fictional record for the note, {_settings(form.memo)}. "
        f"Recorded {layout.case_target} is the only changed setup entry. "
        f"{_mean_work(form.memo, key.memo)} The record leaves open where the rest of the "
        "water went and what would happen in a real setup.\n\n"
        "**6.** One possible measurement is the volume pooled on a tray after a trial. "
        "It could show how much water was in the tray at that time. The record only "
        f"reports collector readings. Hold input and {fixed} fixed while comparing "
        f"{layout.case_target}. Accept other coherent proposed independent measurements. "
        "The prompt is a plan on paper.\n\n"
        "## Proposed outcome criteria\n\n"
        "| Pilot outcome | Evidence to inspect separately |\n"
        "| --- | --- |\n"
        "| P1 · Read and calculate | Q1 distinguishes both recorded amounts, the calculated "
        "remainder with mL, and the unmeasured destination. |\n"
        "| P2 · Use replicates and compare setups | Q2 gives both correct means and the gap "
        "with mL and justifies the chosen pair from the recorded setup. Q3 correctly "
        "identifies the single-change pair with matching entries. |\n"
        "| P3 · Critique unsupported claims | Q3 explains both barriers separately using the "
        "changed labels and input volumes. Q4 calculates the remainder, rejects the claimed "
        "destination as unsupported, and identifies the missing independent observation. |\n"
        "| P4 · Communicate and propose a measurement | Q5 attributes correct figures and "
        "setup comparisons to the made-up record and gives a specific limit. Q6 specifies "
        "an extra measurable quantity, what it could show, compatible controls, and why "
        "the record cannot supply it. |\n\n"
        "Record missing components separately. If further evidence is needed, use a "
        "different independently reviewed form after targeted instruction. Keep any "
        "actual learner response or judgment in the school’s private records.\n\n"
        "## Independent review before any classroom use\n\n"
        "- A reviewer other than the form preparer checks this exact learner form and key. "
        "Record the reviewer, date, private manifest reference and decision outside this tool.\n"
        "- Recalculate the key and confirm one intended single-change answer, the two "
        "different comparison barriers, and the boundary between arithmetic and causation.\n"
        "- Check prior learner exposure, taught arithmetic range, reading load, directions, "
        "timing, planned access modes and outcome criteria. A form needs separate "
        "curriculum and teaching-readiness review before classroom use.\n"
        "- Compare the table and linear copy. Offer large print, neutral read-aloud of "
        "named entries or tactile labeled cards. Speech, sign, AAC, typing and exact "
        "scribing can preserve the same evidence. Keep reasoning prompts neutral. "
        "Review calculator use against the arithmetic criterion. No liquid handling is required.\n"
    )


def _require_private(path: Path, *, directory=False):
    info = path.lstat()
    predicate = stat.S_ISDIR if directory else stat.S_ISREG
    if not predicate(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("use an owner-only directory and regular owner-only files")


def _session_path(root: Path, name: str):
    _require_private(root, directory=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("session name must be a simple local folder name")
    return root / name


def _write_private(path: Path, content: str):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(content.encode("utf-8"))


def _registry(root: Path):
    path = root / ROOT_DB
    # Refuse an accidentally deleted registry when earlier session folders remain.
    if not os.path.lexists(path) and any(root.iterdir()) and not os.path.lexists(path):
        raise ValueError("exposure registry is missing from a nonempty private root")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _require_private(path)
    else:
        os.close(fd)
    return sqlite3.connect(path, timeout=10)


def _bundled_files(seed: str, form: Form):
    return {
        "learner.md": render_learner(form),
        "learner-linear.md": render_learner(form, linear=True),
        "teacher.md": render_teacher(form),
        "session.json": canonical(seal({"version": VERSION, "seed": seed, "form": asdict(form)})),
    }


def _signature_digests(values):
    return [hashlib.sha256(canonical(value).encode("utf-8")).hexdigest() for value in values]


def _reserve_and_prepare(root: Path, target: Path):
    with closing(_registry(root)) as database, database:
        database.execute("BEGIN IMMEDIATE")
        if not database.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'exposures'"
        ).fetchone():
            if any(entry.name not in (ROOT_DB, f"{ROOT_DB}-journal") for entry in root.iterdir()):
                raise ValueError("exposure registry is incomplete in a nonempty private root")
            database.execute(
                "CREATE TABLE exposures (signature TEXT PRIMARY KEY, session TEXT NOT NULL)"
            )
        if os.path.lexists(target) or database.execute(
            "SELECT 1 FROM exposures WHERE session = ? LIMIT 1", (target.name,)
        ).fetchone():
            raise FileExistsError("use a new private session name")
        for _ in range(ATTEMPTS):
            seed = secrets.token_hex(16)
            form = generate(seed)
            values = signatures(form, inspect_form(form))
            if not EXPOSED.isdisjoint(values):
                continue
            digests = _signature_digests(values)
            if not DEMONSTRATION_DIGESTS.isdisjoint(digests):
                continue
            placeholders = ", ".join("?" for _ in digests)
            if database.execute(
                f"SELECT 1 FROM exposures WHERE signature IN ({placeholders}) LIMIT 1", digests
            ).fetchone():
                continue
            files = _bundled_files(seed, form)
            database.executemany("INSERT INTO exposures VALUES (?, ?)",
                                 ((digest, target.name) for digest in digests))
            return files
        raise ValueError("no fresh questions found within the attempt limit")


def new_session(root: Path, name: str) -> Path:
    """Reserve the questions before saving a complete local draft bundle."""
    target = _session_path(root, name)
    files = _reserve_and_prepare(root, target)
    # On write failure the reservation stays, so an uncertain exposure is never reissued.
    with TemporaryDirectory(prefix=".water-pathways-", dir=root) as pending:
        staging = Path(pending) / "draft"
        staging.mkdir(mode=0o700)
        for filename, content in files.items():
            _write_private(staging / filename, content)
        if os.path.lexists(target):
            raise FileExistsError("use a new private session name")
        staging.rename(target)
    return target


def _read_private(path: Path):
    _require_private(path)
    return path.read_bytes()


def resume_session(root: Path, name: str) -> dict[str, str]:
    directory = _session_path(root, name)
    _require_private(directory, directory=True)
    manifest = json.loads(_read_private(directory / "session.json"))
    if not isinstance(manifest, dict) or manifest.get("version") != VERSION:
        raise ValueError("unsupported private session manifest")
    seed = manifest.get("seed")
    form = generate(seed)
    files = _bundled_files(seed, form)
    for filename, content in files.items():
        if _read_private(directory / filename) != content.encode("utf-8"):
            raise ValueError(f"saved {filename} differs from exact replay")
    registry = root / ROOT_DB
    _require_private(registry)
    with closing(sqlite3.connect(registry.absolute().as_uri() + "?mode=ro", uri=True)) as database:
        stored = {digest for (digest,) in database.execute(
            "SELECT signature FROM exposures WHERE session = ?", (name,)
        )}
    if stored != set(_signature_digests(signatures(form, inspect_form(form)))):
        raise ValueError("saved session does not match its question reservations")
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="write a new private draft for review")
    resume = commands.add_parser("resume", help="verify and display the exact saved draft")
    for command in (new, resume):
        command.add_argument("private_root", type=Path)
        command.add_argument("name")
    audience = resume.add_mutually_exclusive_group()
    audience.add_argument("--linear", action="store_true")
    audience.add_argument("--teacher", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            new_session(args.private_root, args.name)
            print("Private draft saved for independent review.")
        else:
            filename = ("teacher.md" if args.teacher else
                        "learner-linear.md" if args.linear else "learner.md")
            files = resume_session(args.private_root, args.name)
            sys.stdout.buffer.write(files[filename].encode("utf-8"))
    except (OSError, ValueError, sqlite3.Error) as error:
        # A corrupt manifest may contain private metadata. Diagnostics use fixed messages.
        if isinstance(error, (json.JSONDecodeError, UnicodeError)):
            parser.exit(2, "Error: invalid private session manifest\n")
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()
