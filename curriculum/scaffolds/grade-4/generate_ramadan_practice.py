"""Generate or verify a private Grade 4 Ramadan draft practice session."""

import argparse
import hashlib
import json
import random
import re
import secrets
from pathlib import Path

VERSION = "grade4-ramadan-v1"
DRIVES = ("book drive", "coat collection", "school-supply drive", "food collection")
ACCESS = {True: "step-free entrance", False: "room reached only by stairs"}
PRIVACY = {True: "anonymous drop box", False: "public list of donor names"}


def build(seed):
    if not isinstance(seed, str) or not re.fullmatch(r"[0-9a-f]{32}", seed):
        raise ValueError("invalid session seed")
    rng = random.Random(int(seed, 16))
    drive = rng.choice(DRIVES)
    alternate = rng.choice([(False, True), (True, False)])
    plans = [(True, True), alternate]
    rng.shuffle(plans)
    winner = next(label for label, plan in zip("AB", plans) if all(plan))
    public_id = hashlib.sha256(f"{VERSION}:{seed}".encode()).hexdigest()
    learner = [
        "# Ramadan community care — draft practice",
        f"Form reference: {public_id}",
        "",
        "Card 1: Qur’an 2:185 (locator only). Use the approved reading supplied by your teacher.",
        f"Card 2: The fictional Ramadan {drive} requires step-free drop-off and private donor names.",
        f"Card 3: A learner claims the {drive} notice tells us which pupils must fast.",
        "",
    ]
    teacher = [
        "# Private teacher key — draft",
        f"Form reference: {public_id}",
        "",
        "L1: Require the source reference, fictional notice and learner inference labels, "
        "one limit of each, and an idea supported by the approved reading. "
        "Defer the reading criterion until the approved reading is available.",
    ]
    for label, (access, privacy) in zip("AB", plans):
        learner.append(f"Plan {label}: {ACCESS[access]} with an {PRIVACY[privacy]}."
                       if privacy else f"Plan {label}: {ACCESS[access]} with a {PRIVACY[privacy]}.")
        teacher.append(f"L2 plan {label}: access {'met' if access else 'unmet'}, "
                       f"privacy {'met' if privacy else 'unmet'}.")
    learner += [
        "",
        "Label the three cards, explain a limit of each and give an idea from the approved reading.",
        "Compare both plans against both rules. Can the notice support the learner's claim?",
        "Recommend a plan or a revision. Cite a notice detail and explain your reason. "
        "Where could you take an individual fasting question privately?",
    ]
    teacher += [
        "L2: The notice cannot establish an individual fasting obligation.",
        f"L3: Accept plan {winner} or a feasible revision of the other plan that meets both rules. "
        "Require a cited notice detail, linked reason and private referral to a qualified religious educator.",
    ]
    manifest = {"version": VERSION, "seed": seed, "form_reference": public_id}
    return {
        "learner.md": ("\n".join(learner) + "\n").encode(),
        "teacher.md": ("\n".join(teacher) + "\n").encode(),
        "manifest.json": (json.dumps(manifest, sort_keys=True) + "\n").encode(),
    }


def new_session(output):
    artifacts = build(secrets.token_hex(16))
    output.mkdir(mode=0o700)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)


def resume_session(output):
    if output.is_symlink():
        raise ValueError("session directory cannot be a symlink")
    paths = [output / name for name in ("learner.md", "teacher.md", "manifest.json")]
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError("missing or invalid session file")
    manifest = json.loads(paths[-1].read_bytes())
    if not isinstance(manifest, dict) or manifest.get("version") != VERSION:
        raise ValueError("unsupported session version")
    artifacts = build(manifest.get("seed"))
    for path in paths:
        if path.read_bytes() != artifacts[path.name]:
            raise ValueError(f"{path.name} differs from the saved form")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("new", "resume"))
    parser.add_argument("--output", type=Path, required=True, help="private session directory")
    args = parser.parse_args()
    try:
        if args.action == "new":
            new_session(args.output)
        else:
            resume_session(args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
