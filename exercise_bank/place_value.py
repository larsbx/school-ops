"""PV2/PV3 item factory. Frozen v1 blueprint follows A-MATH-001-02."""
import re
from .core import SCHEMA, VERSION, Sampler, seal, seconds

BANK = 'C-MATH-001/place-value'
OUT = 'O-MATH-001-'
PLACES = ('ones', 'tens', 'hundreds')
SMALL = ('zero one two three four five six seven eight nine ten eleven twelve '
         'thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
TENS = ('zero ten twenty thirty forty fifty sixty seventy eighty ninety').split()


def name(n):
    if n < 20:
        return SMALL[n]
    if n < 100:
        return TENS[n // 10] + ('-' + SMALL[n % 10] if n % 10 else '')
    return SMALL[n // 100] + ' hundred' + (' ' + name(n % 100) if n % 100 else '')


def groups(n, digits):
    return [n // 10**i % 10 for i in range(digits)]


def expanded(n, digits):
    return [n // 10**i % 10 * 10**i for i in reversed(range(digits))]


def generate(route, mode, seed, duration=60):
    if route not in ('PV2', 'PV3') or mode not in ('drill', 'assessment'):
        raise ValueError('choose PV2 or PV3 and drill or assessment; PVX is separate')
    if type(seed) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', seed):
        raise ValueError('seed must contain 1–128 ASCII letters, digits, dots, underscores or hyphens')
    duration = seconds(duration)
    digits = 2 if route == 'PV2' else 3
    maximum = 10**digits - 1
    rng = Sampler(BANK + '/' + route + '/' + mode, seed)
    items = []

    def add(kind, data, answer, outcomes, criterion):
        items.append(dict(id=f'{route}-{len(items)+1:02}', kind=kind, data=data,
                          answer=answer, outcomes=[OUT + f'{o:03}' for o in outcomes],
                          criterion=criterion))

    def number():
        return rng.integer(10**(digits-1), maximum)

    if mode == 'drill':
        # Deliberately partial evidence: speed cannot certify the full outcome.
        for _ in range(3):
            n = number()
            add('compose', {'groups': groups(n, digits)}, n, [1], 'Correct total only; grouping reasoning not assessed.')
            step = rng.integer(0, 2)
            step = (1, 5, 10)[step]
            start = rng.integer(0, maximum - 4 * step)
            add('count', {'start': start, 'step': step, 'terms': 5},
                [start + i * step for i in range(5)], [2], 'Complete five-term sequence; explanation not assessed.')
            n = number()
            add('expand', {'number': n}, expanded(n, digits), [3], 'Place-value sum only; names and model not assessed.')
            a, b = number(), number()
            add('compare', {'a': a, 'b': b}, '<' if a < b else '>' if a > b else '=', [4],
                'Correct symbol only; comparison reason not assessed.')
    else:
        n = number()
        add('model', {'number': n}, groups(n, digits), [1],
            'All digit amounts correct; name the one-unit and show ten/hundred groups made from it.')
        # Ensure both exchanges are possible on PV3, and ones remain within route.
        g = [rng.integer(1, 9) for _ in range(digits)]
        n = sum(v * 10**i for i, v in enumerate(g))
        regrouped = g.copy()
        if digits == 3:
            regrouped[2] -= 1
            regrouped[1] += 10
        intermediate = regrouped.copy()
        regrouped[1] -= 1
        regrouped[0] += 10
        add('regroup', {'number': n}, [g, intermediate, regrouped] if digits == 3 else [g, regrouped], [1],
            'Show every exchange; one ten is ten ones, one hundred is ten tens; no ones added or removed.')
        zero = rng.integer(1, 9) * 10**(digits-1)
        other = ((zero // 10) % 9 + 1) * 10 if digits == 2 else zero + rng.integer(1, 9)
        add('zeros', {'numbers': [other, zero]}, [groups(other, digits), groups(zero, digits)], [1],
            'All models correct; explain every zero as no additional groups in that position.')
        boundary = rng.integer(2, 9) * 10**(digits-1)
        add('boundary', {'start': boundary-3, 'step': 1, 'terms': 5}, list(range(boundary-3, boundary+2)), [1, 2],
            'All terms correct; after adding one, demonstrate ten ones into one ten' +
            (' and then ten tens into one hundred.' if digits == 3 else '.') + ' Each exchange preserves the new amount.')
        start = rng.integer(1, 15) * 5
        add('count', {'start': start, 'step': 5, 'terms': 5}, list(range(start, start+21, 5)), [2],
            'All terms correct, including starting term; identify and explain step five.')
        start = rng.integer(10, maximum-40)
        sequences = [{'start': start, 'step': 10, 'terms': 5}]
        if digits == 3:
            sequences.append({'start': rng.integer(1, 5)*100, 'step': 100, 'terms': 5})
        add('counts', {'sequences': sequences}, [[s['start']+i*s['step'] for i in range(5)] for s in sequences], [2],
            'All terms correct; identify each counted unit and explain each repeated step.')
        n = number() if digits == 2 else rng.integer(1, 9)*100+rng.integer(1, 9)
        add('forms', {'number': n}, {'name': name(n), 'expanded': expanded(n, digits), 'groups': groups(n, digits)}, [3],
            'Correct spoken name and sum; connect numeral places to the concrete model. Spelling support allowed.')
        n = number()
        add('from-name', {'words': name(n)}, {'number': n, 'expanded': expanded(n, digits)}, [3],
            'Correct numeral and place-value sum; read directions without answer cues.')
        n = rng.integer(1, maximum//10)*10
        add('from-groups', {'groups': groups(n, digits)}, {'number': n, 'name': name(n), 'expanded': expanded(n, digits)}, [3],
            'Correct numeral, spoken name and sum; explain zero ones. Zero terms in sum optional.')
        # Compare same leading place, then different leading places, then equality.
        lead = rng.integer(1, 8)
        a = lead*10**(digits-1) + (12 if digits == 3 else 2)
        b = lead*10**(digits-1) + (21 if digits == 3 else 7)
        for a, b in ((a, b), ((lead+1)*10**(digits-1), lead*10**(digits-1)+9), (n, n)):
            add('compare', {'a': a, 'b': b}, '<' if a < b else '>' if a > b else '=', [4],
                'Correct relation and symbol; explain first differing place, or equality, using the counted units.')
    return seal(dict(schema_version=SCHEMA, generator_version=VERSION, bank=BANK,
                     status='draft', route=route, mode=mode, seed=seed, range=[0, maximum],
                     duration_seconds=duration if mode == 'drill' else None,
                     timing='hard-stop-practice' if mode == 'drill' else 'untimed-split-sittings-allowed',
                     items=items))


def prompt(item, digits, mode):
    d, k = item['data'], item['kind']
    def group_text(g):
        return ', '.join(f'{g[i]} {PLACES[i]}' for i in reversed(range(digits)))
    if k == 'compose':
        text = f"Write the total: {group_text(d['groups'])}."
    elif k == 'expand':
        text = f"Write {d['number']} as a sum of place values."
    elif k == 'model':
        text = f"Build or draw {d['number']}; label each grouped unit and identify the one-unit. Explain the digit amounts."
    elif k == 'regroup':
        text = f"Model {d['number']}. " + ('Unpack one hundred into tens, then unpack' if digits == 3 else 'Unpack') + ' one ten into ones. Show each stage and explain why the amount stays the same.'
    elif k == 'zeros':
        text = f"Model {d['numbers'][0]} and {d['numbers'][1]}. Explain every zero position."
    elif k in ('count', 'boundary'):
        text = f"Give {d['terms']} terms by {d['step']} starting at {d['start']}, including the starting value."
        if mode == 'assessment':
            text += ' Explain the repeated step.'
        if k == 'boundary':
            text += ' Demonstrate and explain every exchange at the place boundary after adding one.'
    elif k == 'counts':
        text = ' '.join(f"Give {s['terms']} terms by {s['step']} starting at {s['start']}, including the start." for s in d['sequences']) + ' Explain each step and its counted unit.'
    elif k == 'forms':
        text = f"Name {d['number']} aloud, write its place-value sum and model it. Explain how the places match the model."
    elif k == 'from-name':
        text = f"Write the numeral and place-value sum for: {d['words']}."
    elif k == 'from-groups':
        text = f"Write the numeral, say its name and write its place-value sum: {group_text(d['groups'])}. Explain zero ones."
    elif k == 'compare':
        text = f"Complete {d['a']} __ {d['b']} with <, > or =."
        if mode == 'assessment':
            text += ' Explain using the first differing place or equal amounts.'
    else:
        raise ValueError('unknown item kind')
    return text
