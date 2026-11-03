"""Grade 2 Unit 3: fresh seeded exercise sessions; exact saved-form continuation.

This tool writes *draft* forms. It does not grade responses or certify mastery.
Run in a private directory: python -m exercise_bank.unit3 new PATH --limit 24.
"""
import argparse
import json
import os
import secrets
import tempfile
from pathlib import Path

from .core import Sampler, canonical, seal

VERSION = "unit3-session-1"
ACTIVITIES = ("entry", "groups", "sharing", "double", "check")


def generate(activity, limit, seed):
    if activity not in ACTIVITIES or type(limit) is not int or limit not in (12, 24):
        raise ValueError("activity/limit must be one of the documented routes")
    if not isinstance(seed, str) or len(seed) != 32 or any(c not in "0123456789abcdef" for c in seed):
        raise ValueError("invalid 128-bit session seed")
    rng = Sampler(f"unit3:{activity}:{limit}", seed, version=VERSION)
    items = []

    def add(component, question, key, *, model, groups, each, total, leftover=0):
        if groups * each + leftover != total or total > limit:
            raise ValueError("invalid answer fixture")
        items.append(dict(id=f"U3-{len(items)+1:02}", component=component, question=question,
                          key=key, model=model, groups=groups, each=each, total=total,
                          leftover=leftover))

    def pair(distinct=False):
        options = [(g, s) for g in range(2, 7) for s in range(2, 7)
                   if g * s <= limit and (not distinct or g != s)]
        return options[rng.integer(0, len(options) - 1)]

    if activity == "entry":
        count = rng.integer(6, min(12, limit))
        add("count/conservation", f"Count {count} counters. Put them in a row, rearrange them, and explain what happened to the total.",
            f"{count} counters; each counted once; rearrangement preserves the count.",
            model="count", groups=1, each=count, total=count)
        size = rng.integer(2, min(4, limit // 3))
        add("equal vs unequal", f"Compare three boxes with {size},{size},{size} counters to three with {size+1},{size},{size-1}. Which has equal-sized groups? Explain.",
            f"The three groups of {size} are equal; {size+1},{size},{size-1} are unequal though both total {3*size}.",
            model="equal-check", groups=3, each=size, total=3*size)
        half = rng.integer(2, limit // 2)
        add("composition/pairing", f"Show {half} + {half} with counters and pair the collection. Explain whether anything is left over.",
            f"{2*half} counters, {half} disjoint pairs, zero leftover.",
            model="pairing", groups=2, each=half, total=2*half)

    if activity in ("groups", "check"):
        g, s = pair()
        add("equal grouping", f"Build {g} disjoint equal groups of {s} counters. Name the group count, the size of one group and the total; explain why none was counted twice.",
            f"{g} groups of {s}; total {g*s}. Check with {g} disjoint sets each of size {s}.",
            model="equal-groups", groups=g, each=s, total=g*s)
        g, s = pair(distinct=True)
        add("array conservation", f"Arrange {g*s} counters into {g} rows of {s}; rearrange the same counters into {s} rows of {g}. Did the total change? Explain.",
            f"{g} rows of {s} and {s} rows of {g} both contain {g*s}; no counters enter or leave.",
            model="array", groups=g, each=s, total=g*s)

    if activity in ("sharing", "check"):
        g, s = pair()
        add("sharing", f"Share {g*s} counters equally among {g} boxes. How many counters in each box? Draw or model and recombine to check.",
            f"{s} counters in each of {g} boxes; {g} groups of {s} exhaust {g*s}.",
            model="sharing", groups=g, each=s, total=g*s)
        g, s = pair()
        add("group count", f"Place {g*s} counters into groups of {s}. How many groups can be made? Name the units in the answer and check.",
            f"{g} groups, each holding {s} counters, account for all {g*s} counters.",
            model="group-size-given", groups=g, each=s, total=g*s)

    if activity in ("double", "check"):
        half = rng.integer(2, limit // 2)
        add("doubling/halving", f"Double {half} counters with two equal sets. Then halve the result. Show both operations and explain the inverse.",
            f"Double {half} is {2*half}; two equal sets of {half}. Half of {2*half} is {half}.",
            model="inverse-two", groups=2, each=half, total=2*half)
        odds = list(range(5, limit + 1, 2))
        odd = odds[rng.integer(0, len(odds) - 1)]
        add("whole-object limits", f"Can {odd} whole counters be shared into two equal groups with no leftovers? Model the best equal whole-number attempt and justify.",
            f"No: two equal groups of {odd//2} use {odd-1}; one counter remains. {odd//2}+{odd//2}+1={odd}.",
            model="leftover", groups=2, each=odd//2, total=odd, leftover=1)

    return seal(dict(version=VERSION, activity=activity, limit=limit, seed=seed, items=items))


def render(form, teacher=False):
    lines = ["# Grade 2 Unit 3 — " + ("teacher key" if teacher else "learner sheet"),
             "", f"Draft · untimed · form {form['form_id']}", "",
             "Model, name the units, and explain your reason. Use counters, tactile objects,",
             "paper, an oral response, AAC, or a scribe without solution hints.", ""]
    for item in form["items"]:
        lines += [f"## {item['id']}", "", item["question"], ""]
        if teacher:
            lines += [f"Component: O-MATH-001-013 ({item['component']})", "", "Key: " + item["key"], ""]
        else:
            lines += ["Response: __________________________________________", ""]
    return "\n".join(lines)


def load_session(directory):
    form = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    if not isinstance(form, dict) or (form.get("version") != VERSION or
        form != generate(form["activity"], form["limit"], form["seed"])):
        raise ValueError("unsupported or altered Unit 3 session")
    for filename, teacher in (("learner.md", False), ("teacher.md", True)):
        if (directory / filename).read_bytes() != render(form, teacher).encode("utf-8"):
            raise ValueError(f"altered {filename}")
    return form


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(data.encode("utf-8"))


def work(directory):
    form = load_session(directory)
    path = directory / "progress.json"
    ids = {item["id"] for item in form["items"]}
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        saved = {"form_id": form["form_id"], "responses": {}}
    if not isinstance(saved, dict) or saved.get("form_id") != form["form_id"]:
        raise ValueError("progress does not belong to this form")
    responses = saved.get("responses")
    if not isinstance(responses, dict) or any(
        k not in ids or not isinstance(v, str) or not v.strip() for k, v in responses.items()
    ):
        raise ValueError("invalid saved responses")
    for item in form["items"]:
        if item["id"] in responses:
            continue
        print(f"{item['id']}: {item['question']}")
        try:
            response = input("Response (blank to pause): ").strip()
        except EOFError:
            response = ""
        if not response:
            print("Paused. Existing responses are saved.")
            return
        responses[item["id"]] = response
        payload = canonical({"form_id": form["form_id"], "responses": responses}).encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as tmp:
            pending = Path(tmp.name)
            try:
                tmp.write(payload)
                tmp.close()
                os.replace(pending, path)
            finally:
                pending.unlink(missing_ok=True)
    print(f"Finished: {len(responses)}/{len(ids)} saved, for private teacher review.")


def main():
    parser = argparse.ArgumentParser(__doc__)
    cmd = parser.add_subparsers(dest="command", required=True)
    new = cmd.add_parser("new")
    new.add_argument("directory", type=Path)
    new.add_argument("--limit", type=int, choices=(12, 24), required=True)
    new.add_argument("--activity", choices=ACTIVITIES, default="check")
    resume = cmd.add_parser("resume")
    resume.add_argument("directory", type=Path)
    resume.add_argument("--teacher", action="store_true")
    ongoing = cmd.add_parser("work")
    ongoing.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "work":
            work(args.directory)
        elif args.command == "resume":
            print(render(load_session(args.directory), args.teacher), end="")
        else:
            form = generate(args.activity, args.limit, secrets.token_hex(16))
            args.directory.mkdir(mode=0o700, exist_ok=False)
            for name, content in (
                ("learner.md", render(form)), ("teacher.md", render(form, True)),
                ("session.json", canonical(form))
            ):
                write_private(args.directory / name, content)
            print(form["form_id"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()
