"""Independent arithmetic/key oracle plus exact blueprint/provenance checks."""
from collections import Counter
from .core import seal
from .place_value import generate
from .place_value_v1 import generate as generate_v1

UNITS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
DECADES = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))


def read_name(words):
    value = 0
    for token in words.replace('-', ' ').split():
        if token == 'hundred':
            value *= 100
        else:
            value += (UNITS | DECADES)[token]
    return value


def check(form):
    """Reject modified keys, ranges, coverage, blueprint or identity; return form."""
    if form != seal(form):
        raise ValueError('form identity mismatch')
    factories = {'1.0.0': generate_v1, '1.0.1': generate}
    if form.get('generator_version') not in factories:
        raise ValueError('unsupported generator version')
    factory = factories[form['generator_version']]
    digits = {'PV2': 2, 'PV3': 3}[form['route']]
    maximum = 10**digits-1
    def parts(n):
        # Decimal text oracle, distinct from factory division implementation.
        return [int(c) for c in str(n).zfill(digits)[::-1]]
    def total(g):
        return sum(count * unit for count, unit in zip(g, (1, 10, 100)))
    def expansion(n):
        return [v * 10**i for i, v in reversed(list(enumerate(parts(n))))]
    def sequence(d):
        return list(range(d['start'], d['start'] + d['step']*d['terms'], d['step']))
    def bounded(n):
        if type(n) is not int or not 0 <= n <= maximum:
            raise ValueError('out-of-route amount')
    for item in form['items']:
        d, a, k = item['data'], item['answer'], item['kind']
        if k == 'compose':
            expected = total(d['groups']); bounded(expected)
        elif k in ('expand', 'model', 'regroup', 'forms'):
            n = d['number']; bounded(n)
            if k == 'expand':
                expected = expansion(n)
            elif k == 'model':
                expected = parts(n)
            elif k == 'regroup':
                expected = a
                if len(a) != digits:
                    raise ValueError('missing regrouping stage')
                for stage in a:
                    if len(stage) != digits or any(type(x) is not int or x < 0 for x in stage) or total(stage) != n:
                        raise ValueError('regrouping changes amount')
                if a[0] != parts(n):
                    raise ValueError('initial groups')
                # Explicit conservation at each taught exchange.
                deltas = [[0, 10, -1], [10, -1, 0]] if digits == 3 else [[10, -1]]
                for before, after, delta in zip(a, a[1:], deltas):
                    if [y-x for x, y in zip(before, after)] != delta:
                        raise ValueError('incorrect exchange')
            else:
                if read_name(a['name']) != n:
                    raise ValueError('number name')
                expected = dict(name=a['name'], expanded=expansion(n), groups=parts(n))
        elif k == 'zeros':
            for n in d['numbers']: bounded(n)
            expected = [parts(n) for n in d['numbers']]
        elif k in ('count', 'boundary', 'counts'):
            sequences = d['sequences'] if k == 'counts' else [d]
            answers = []
            for s in sequences:
                values = sequence(s)
                for n in values: bounded(n)
                answers.append(values)
            expected = answers if k == 'counts' else answers[0]
        elif k in ('from-name', 'from-groups'):
            n = read_name(d['words']) if k == 'from-name' else total(d['groups'])
            bounded(n)
            expected = dict(number=n, expanded=expansion(n))
            if k == 'from-groups':
                if read_name(a['name']) != n: raise ValueError('number name')
                expected['name'] = a['name']
        elif k == 'compare':
            bounded(d['a']); bounded(d['b'])
            expected = ('=', '>', '<')[(d['a'] > d['b']) - (d['a'] < d['b'])]
        else:
            raise ValueError('unknown kind')
        if a != expected:
            raise ValueError(f"incorrect key: {item['id']}")
    counts = Counter(o for item in form['items'] for o in item['outcomes'])
    expected_counts = (4, 3, 3, 3) if form['mode'] == 'assessment' else (3, 3, 3, 3)
    if [counts[f'O-MATH-001-{i:03}'] for i in range(1, 5)] != list(expected_counts) or len(counts) != 4:
        raise ValueError('coverage mismatch')
    # Arithmetic correctness alone cannot establish prompt/criterion/blueprint integrity.
    reference = factory(form['route'], form['mode'], form['seed'], form['duration_seconds'] or 60)
    if form != reference:
        raise ValueError('form does not reproduce from its versioned configuration')
    return form
