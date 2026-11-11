"""Unit 2 local sessions: generate fresh forms or resume a saved form."""
import argparse
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

from .core import Sampler, canonical, seal

VERSION = 'unit2-session-1'
ACTIVITIES = ('entry', 'composition', 'difference', 'stories', 'parity', 'check')


def generate(activity, limit, seed):
    if activity not in ACTIVITIES or type(limit) is not int or limit not in (10, 20):
        raise ValueError('invalid activity or range')
    if not isinstance(seed, str) or len(seed) != 32 or any(c not in '0123456789abcdef' for c in seed):
        raise ValueError('invalid session seed')
    rng = Sampler(activity + ':' + str(limit), seed, version=VERSION)
    items = []

    def add(outcome, question, key):
        items.append(dict(id=f'U2-{len(items)+1:02}', outcome=outcome, question=question, key=key))

    def parts():
        total = rng.integer(5, limit)
        a = rng.integer(2, total - 2)
        return total, a, total - a

    if activity == 'entry':
        n = rng.integer(4, 10)
        a = rng.integer(2, n-1)
        add('001', f'Count out {n} single counters. Point once to each and name what you counted.',
            f'{n} single counters; each is counted exactly once.')
        add('004', f'Compare rows of {a} and {n} counters. Which has more? Show why.',
            f'{n} > {a}; matching leaves {n-a} unmatched in the longer row.')
        add('001', 'Bundle ten single counters. Explain what one bundle represents.',
            'One ten represents ten ones; bundling does not change the quantity.')
    if activity in ('composition', 'check'):
        total, a, b = parts()
        add('005', f'Split {total} counters into a part of {a} and another part. Model the split and check by addition.',
            f'{b} counters; disjoint parts of {a} and {b} exhaust {total}. Check {a} + {b} = {total}.')
    if activity == 'composition':
        total, a, b = parts()
        add('005', f'Join {a} and {b} counters. Move one counter from the first part to the second. Show both groupings and explain what stays fixed.',
            f'{a} + {b} = {a-1} + {b+1} = {total}; no counter entered or left.')
    if activity == 'difference':
        for _ in range(2):
            total, a, b = parts()
            add('005', f'Find {total} − {a}. Show the separated parts and reconstruct the whole.',
                f'{b}; removing {a} from {total} leaves {b}, and {a} + {b} = {total}.')
    if activity in ('stories', 'check'):
        total, a, b = parts()
        add('006', f'A basket has {a} apples. Add {b} apples. How many now? Model the joining and name the unit.',
            f'{total} apples; join the original {a} with the added {b}: {a} + {b} = {total}.')
        total, a, b = parts()
        add('006', f'There are {total} paper clips on a mat. Move {a} off. Model how many remain and name the unit.',
            f'{b} paper clips; separate {a} from {total}: {total} − {a} = {b}.')
        total, a, b = parts()
        add('006', f'One box contains {total} crayons and another contains {a}. How many more are in the first? Explain without changing either collection.',
            f'{b} crayons; match {a} across rows, leaving {b} unmatched in the longer row.')
    if activity in ('parity', 'check'):
        for n in (2*rng.integer(2, limit//2)-1, 2*rng.integer(2, limit//2)):
            add('013 (pairing only)', f'Pair {n} counters. Classify as even or odd and explain using the pairs and leftovers.',
                f'{n//2} disjoint pairs and {n%2} leftover; {"odd" if n%2 else "even"}.')
    return seal(dict(version=VERSION, activity=activity, limit=limit, seed=seed, items=items))


def load_session(directory):
    form = json.loads((directory/'session.json').read_text(encoding='utf-8'))
    if form['version'] != VERSION or form != generate(form['activity'], form['limit'], form['seed']):
        raise ValueError('unsupported or altered session')
    return form


def render(form, teacher=False):
    lines = ['# Grade 2 Unit 2 — ' + ('teacher key' if teacher else 'learner sheet'),
             '', 'Draft • untimed • session ' + form['form_id'], '',
             'Use counters or drawings. Show the model, result and reason.',
             'Read-aloud and oral, drawn, pointed or scribed responses are allowed.', '']
    for item in form['items']:
        lines.extend([f"## {item['id']}", '', item['question'], ''])
        if teacher:
            lines.extend(['Outcome: O-MATH-001-' + item['outcome'], '', 'Key: ' + item['key'], ''])
        else:
            lines.extend(['Response: __________________________________________', ''])
    return '\n'.join(lines)


def work(directory):
    """Continue at the first unanswered item, saving each response locally."""
    form = load_session(directory)
    path = directory/'progress.json'
    ids = {item['id'] for item in form['items']}
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        saved = {'form_id': form['form_id'], 'responses': {}}
    if not isinstance(saved, dict) or saved.get('form_id') != form['form_id']:
        raise ValueError('progress belongs to a different form')
    responses = saved.get('responses')
    if not isinstance(responses, dict) or any(
        k not in ids or not isinstance(v, str) or not v.strip()
        for k, v in responses.items()
    ):
        raise ValueError('invalid saved responses')
    for item in form['items']:
        item_id = item['id']
        if item_id in responses:
            continue
        print(f"{item_id}: {item['question']}")
        try:
            response = input('Response (blank to pause): ').strip()
        except EOFError:
            response = ''
        if not response:
            print('Paused. Earlier responses are saved.')
            return
        responses[item_id] = response
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as tmp:
            temp = Path(tmp.name)
            try:
                tmp.write(canonical(saved).encode('utf-8'))
                tmp.close()
                os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
    print(f"Finished: {len(responses)}/{len(ids)} responses saved for teacher review.")


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    new = sub.add_parser('new')
    new.add_argument('directory', type=Path)
    new.add_argument('--activity', choices=ACTIVITIES, default='check')
    new.add_argument('--limit', choices=(10, 20), type=int, required=True)
    resume = sub.add_parser('resume')
    resume.add_argument('directory', type=Path)
    resume.add_argument('--teacher', action='store_true', help='display the key instead of the learner sheet')
    interactive = sub.add_parser('work', help='answer or continue a private session')
    interactive.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'work':
            work(args.directory)
            return
        if args.command == 'resume':
            # Match saved UTF-8/LF sheets even when stdout uses Windows text mode.
            sys.stdout.buffer.write(render(load_session(args.directory), args.teacher).encode('utf-8'))
            return
        form = generate(args.activity, args.limit, secrets.token_hex(16))
        args.directory.mkdir(mode=0o700, exist_ok=False)
        for name, content in [('learner.md', render(form)), ('teacher.md', render(form, True)),
                              ('session.json', canonical(form))]:
            (args.directory/name).write_bytes(content.encode('utf-8'))
        print(form['form_id'])
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'Error: {error}\n')


if __name__ == '__main__':
    main()
