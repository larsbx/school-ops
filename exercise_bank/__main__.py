"""python -m exercise_bank: generate, validate, or time a local drill."""
import argparse
import json
from pathlib import Path
from .core import canonical, countdown
from .place_value import generate, prompt
from .validate import check


def model_evidence(item, digits):
    """Concrete inspectable models supplement the independent numeric key."""
    d, k = item['data'], item['kind']
    def units(g):
        return ' + '.join(f'{g[i]} {("ones", "tens", "hundreds")[i]}' for i in reversed(range(digits)))
    if k == 'regroup':
        return ' = '.join(units(g) for g in item['answer']) + f" = {d['number']} ones. Exchanging equal-valued groups adds or removes no ones."
    if k == 'boundary':
        n = d['start'] + 3
        if digits == 2:
            return f'{n-1} plus one gives {n//10-1} tens and 10 ones; exchange for {n//10} tens and 0 ones.'
        return f'{n-1} plus one gives {n//100-1} hundreds, 9 tens and 10 ones; then {n//100-1} hundreds and 10 tens; then {n//100} hundreds, 0 tens and 0 ones. Exchanges preserve {n} ones after the addition.'
    if k == 'compare':
        a, b = d['a'], d['b']
        if a == b:
            return f'Both amounts are {a}; their groups agree in every place.'
        for power, unit in reversed(list(enumerate(('ones', 'tens', 'hundreds')[:digits]))):
            x, y = a // 10**power % 10, b // 10**power % 10
            if x != y:
                return f'Higher places agree, if any. At the first differing place, {x} {unit} compared with {y} {unit} determines {a} {item["answer"]} {b}.'
    return item['criterion']


def render(form, teacher=False):
    digits = 2 if form['route'] == 'PV2' else 3
    lines = [f"# {form['route']} {form['mode']} — {'teacher key' if teacher else 'learner sheet'}", '',
             f"Draft • generator {form['generator_version']} • seed {form['seed']!r}", '',
             f"Form ID: {form['form_id']}", '', f"Range: {form['range'][0]}–{form['range'][1]}", '',
             'Use only after the selected route prerequisites and readiness review.', '',
             'Materials: paper, pencil, counters/base-ten blocks, blank place-value chart; no calculator.', '',
             'Directions may be read aloud without answer cues. Spoken/drawn explanations allowed.', '']
    if form['mode'] == 'drill':
        lines += [f"Duration: {form['duration_seconds']} seconds. Stop at time; unfinished items are not evidence of failure.", '',
                  'Fluency practice only: no mastery or conceptual-understanding claim.', '']
    else:
        lines += ['No speed threshold. Plan 15–20 minutes; allow extra time or split sittings.', '',
                  'Explain and model where asked. Starting values count as the first term.', '']
    for item in form['items']:
        lines += [f"## {item['id']}", '', prompt(item, digits, form['mode']), '']
        if teacher:
            lines += ['Outcomes: ' + ', '.join(item['outcomes']), '',
                      'Key: ' + json.dumps(item['answer'], ensure_ascii=False), '',
                      'Evidence: ' + item['criterion'], '',
                      'Model evidence: ' + model_evidence(item, digits), '']
        else:
            lines += ['Answer / model / explanation: ______________________________', '', '']
    if teacher:
        lines += ['Group arrays list ones, tens, hundreds (where applicable); expanded arrays list highest place first.', '',
                  'Accept omitted zero terms, accurate spoken names (including customary “and”), and spelling support.', '',
                  'Apply A-MATH-001-02 outcome criteria separately. Every part must be checked; a correct result alone is insufficient when reasoning is requested.', '',
                  'Record independent / supported / needs review / not assessed privately. No total score replaces outcome evidence.', '',
                  'Keep this key and the manifest out of learner view. Previously practiced or exposed full prompts require fresh reviewed applications.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    g = subs.add_parser('generate')
    g.add_argument('--route', required=True, choices=['PV2', 'PV3'])
    g.add_argument('--mode', required=True, choices=['drill', 'assessment'])
    g.add_argument('--seed', required=True)
    g.add_argument('--duration', type=int, default=60, help='drill seconds only; assessments are untimed')
    g.add_argument('--output', type=Path, required=True, help='new directory; existing paths are never overwritten')
    v = subs.add_parser('validate'); v.add_argument('manifest', type=Path)
    t = subs.add_parser('timer'); t.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'generate':
            form = check(generate(args.route, args.mode, args.seed, args.duration))
            if args.mode == 'assessment' and args.duration != 60:
                raise ValueError('--duration applies only to drills; assessments have no speed threshold')
            args.output.mkdir(parents=True, exist_ok=False)
            (args.output/'manifest.json').write_text(canonical(form), encoding='utf-8')
            (args.output/'learner.md').write_text(render(form), encoding='utf-8')
            (args.output/'teacher.md').write_text(render(form, True), encoding='utf-8')
            print(form['form_id'])
        else:
            form = check(json.loads(args.manifest.read_text(encoding='utf-8')))
            if args.command == 'timer':
                if form['mode'] != 'drill': raise ValueError('only drills have a countdown')
                countdown(form['duration_seconds'])
            else:
                print('Valid arithmetic, keys, scope, coverage, identity and reproduction:', form['form_id'])
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OSError) as error:
        parser.exit(2, f'Error: {error}\n')


if __name__ == '__main__':
    main()
