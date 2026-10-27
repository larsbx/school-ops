import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from exercise_bank.core import canonical, countdown, seal
from exercise_bank.place_value import generate, groups, name
from exercise_bank.place_value_v1 import generate as generate_v1
from exercise_bank.validate import check, read_name
from exercise_bank.__main__ import render


class BankTests(unittest.TestCase):
    def test_many_seeds_all_routes_modes(self):
        for route in ('PV2', 'PV3'):
            for mode in ('drill', 'assessment'):
                for seed in range(250):
                    with self.subTest(route=route, mode=mode, seed=seed):
                        form = generate(route, mode, str(seed))
                        self.assertEqual(form, check(form))
                        self.assertEqual(12, len(form['items']))
                        self.assertEqual(form, generate(route, mode, str(seed)))

    def test_frozen_version_fixtures(self):
        fixtures = json.loads(Path('bank/place-value/golden-ids.json').read_text())
        for key, digest in fixtures.items():
            route, mode = key.split('/')
            self.assertEqual(digest, generate(route, mode, 'review-1')['form_id'])

    def test_review_examples_match_frozen_generator_and_renderer(self):
        for route in ('PV2', 'PV3'):
            directory = Path('bank/place-value/examples') / route.lower()
            form = generate(route, 'assessment', 'review-1')
            self.assertEqual(canonical(form), (directory / 'manifest.json').read_text())
            self.assertEqual(render(form), (directory / 'learner.md').read_text())
            self.assertEqual(render(form, True), (directory / 'teacher.md').read_text())
            check(json.loads((directory / 'manifest.json').read_text()))

    def test_pv3_representation_and_equality_require_hundreds(self):
        for seed in ('16', *(str(i) for i in range(1000))):
            form = check(generate('PV3', 'assessment', seed))
            amount = form['items'][8]['answer']['number']
            self.assertGreaterEqual(amount, 100)
            self.assertLessEqual(amount, 990)
            self.assertEqual(0, amount % 10)
            self.assertEqual({'a': amount, 'b': amount}, form['items'][11]['data'])

    def test_legacy_forms_and_rendered_fixtures_still_reproduce(self):
        base = Path('bank/place-value/legacy-v1')
        fixtures = json.loads((base / 'golden-ids.json').read_text())
        for key, digest in fixtures.items():
            route, mode = key.split('/')
            self.assertEqual(digest, check(generate_v1(route, mode, 'review-1'))['form_id'])
        for route in ('PV2', 'PV3'):
            directory = base / 'examples' / route.lower()
            form = check(generate_v1(route, 'assessment', 'review-1'))
            self.assertEqual(canonical(form), (directory / 'manifest.json').read_text())
            self.assertEqual(render(form), (directory / 'learner.md').read_text())
            self.assertEqual(render(form, True), (directory / 'teacher.md').read_text())
        # Keep the known legacy shortcoming reproducible, rather than silently rewriting it.
        self.assertEqual(40, generate_v1('PV3', 'assessment', '16')['items'][8]['answer']['number'])

    def test_exhaustive_number_names_and_digit_arithmetic(self):
        for n in range(1000):
            self.assertEqual(n, read_name(name(n)))
            width = 2 if n < 100 else 3
            self.assertEqual([int(c) for c in str(n).zfill(width)[::-1]], groups(n, width))

    def test_boundaries_zero_places_and_coverage(self):
        seen = {r: set() for r in ('PV2', 'PV3')}
        for route in seen:
            for seed in range(250):
                f = generate(route, 'assessment', str(seed))
                item = f['items'][3]
                boundary = item['data']['start'] + 3
                seen[route].add(boundary)
                self.assertEqual(boundary, item['answer'][3])
                self.assertEqual(['O-MATH-001-001', 'O-MATH-001-002'], item['outcomes'])
                zeros = f['items'][2]['answer']
                self.assertEqual(0, zeros[1][0])
                if route == 'PV3': self.assertEqual(0, zeros[0][1])
                self.assertEqual('=', f['items'][11]['answer'])
            unit = 10 if route == 'PV2' else 100
            self.assertEqual({i*unit for i in range(2, 10)}, seen[route])
        # Every generated amount including sequence endpoints is independently bounded by check().

    def test_reject_tampered_keys_even_after_resealing(self):
        for route in ('PV2', 'PV3'):
            for mode in ('assessment', 'drill'):
                f = generate(route, mode, 'mutation')
                for i in range(12):
                    bad = copy.deepcopy(f)
                    bad['items'][i]['answer'] = 'wrong'
                    with self.assertRaises((ValueError, TypeError, KeyError)):
                        check(seal(bad))

    def test_reject_coverage_range_prompt_and_metadata_mutations(self):
        f = generate('PV2', 'assessment', 'mutation')
        mutations = [lambda x: x['items'][3]['outcomes'].pop(),
                     lambda x: x.update(range=[0, 999]),
                     lambda x: x['items'][3]['data'].update(start=98),
                     lambda x: x['items'][0]['data'].update(number=100),
                     lambda x: x['items'][0].update(criterion='accept any answer'),
                     lambda x: x.update(generator_version='2.0.0'),
                     lambda x: x.update(duration_seconds=20)]
        for mutate in mutations:
            bad = copy.deepcopy(f); mutate(bad)
            with self.assertRaises(ValueError): check(seal(bad))
        f['seed'] = 'changed'
        with self.assertRaises(ValueError): check(f)

    def test_configuration_and_route_isolation(self):
        for route in ('PVX', 'PV4', '', None):
            with self.assertRaises(ValueError): generate(route, 'drill', 'a')
        for duration in (0, -1, 86401, True, 1.5):
            with self.assertRaises(ValueError): generate('PV2', 'drill', 'a', duration)
        for seed in ('', 'a\nb', '# heading', 'a'*129, 1):
            with self.assertRaises(ValueError): generate('PV2', 'drill', seed)
        self.assertNotEqual(generate('PV2', 'drill', 'a')['items'], generate('PV2', 'drill', 'b')['items'])
        a, b = [generate('PV2', 'drill', 'a', d) for d in (30, 120)]
        self.assertEqual(a['items'], b['items'])
        self.assertNotEqual(a['form_id'], b['form_id'])
        self.assertIsNone(generate('PV3', 'assessment', 'a')['duration_seconds'])

    def test_learner_key_separation_and_prompts(self):
        for route in ('PV2', 'PV3'):
            for mode in ('drill', 'assessment'):
                f = generate(route, mode, 'review-1')
                learner, teacher = render(f), render(f, True)
                self.assertNotIn('Key:', learner)
                self.assertNotIn('teacher.md', learner)
                self.assertNotIn('manifest.json', learner)
                self.assertNotIn('Evidence:', learner)
                self.assertEqual(12, teacher.count('Key:'))
                self.assertEqual(12, learner.count('Answer / model / explanation:'))
                if mode == 'assessment':
                    self.assertIn('No speed threshold', learner)
                    self.assertIn('Explain', learner)

    def test_countdown_with_fake_clock(self):
        now, messages = [0.0], []
        def sleep(n):
            self.assertGreater(n, 0)
            now[0] += n
        countdown(3, clock=lambda: now[0], sleep=sleep, emit=messages.append)
        self.assertEqual(3, now[0]); self.assertEqual(2, len(messages))

    def test_cli_exports_validation_nonoverwrite_and_hashseed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'form'
            args = [sys.executable, '-m', 'exercise_bank', 'generate', '--route', 'PV2', '--mode', 'drill', '--seed', 'review-1', '--duration', '1', '--output', str(target)]
            first = subprocess.run(args, capture_output=True, check=True)
            subprocess.run([sys.executable, '-m', 'exercise_bank', 'validate', str(target/'manifest.json')], capture_output=True, check=True)
            subprocess.run([sys.executable, '-m', 'exercise_bank', 'timer', str(target/'manifest.json')], capture_output=True, check=True)
            self.assertNotEqual(0, subprocess.run(args, capture_output=True).returncode)
            original = (target/'manifest.json').read_bytes()
            args[-1] = str(Path(tmp)/'second')
            second = subprocess.run(args, env=dict(os.environ, PYTHONHASHSEED='913'), capture_output=True, check=True)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(original, (Path(args[-1])/'manifest.json').read_bytes())
            args[args.index('drill')] = 'assessment'
            args[-1] = str(Path(tmp)/'third')
            self.assertNotEqual(0, subprocess.run(args, capture_output=True).returncode)


if __name__ == '__main__':
    unittest.main()
