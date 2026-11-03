import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from exercise_bank.unit2 import ACTIVITIES, generate, render


class Unit2Sessions(unittest.TestCase):
    def test_range_and_key_separation(self):
        import re
        for limit in (10, 20):
            for activity in ACTIVITIES:
                for i in range(50):
                    form = generate(activity, limit, f'{i:032x}')
                    self.assertTrue(form['items'])
                    self.assertNotIn('Key:', render(form))
                    self.assertEqual(render(form, True).count('Key:'), len(form['items']))
                    for item in form['items']:
                        for field in ('question', 'key'):
                            self.assertTrue(all(int(n) <= limit for n in re.findall(r'\d+', item[field])))
        self.assertNotEqual(generate('check', 20, '0'*32)['items'],
                            generate('check', 20, '1'*32)['items'])

    def test_new_resume_and_tamper(self):
        def cli(*args, **kwargs):
            return subprocess.run([sys.executable, '-m', 'exercise_bank.unit2', *map(str, args)],
                                  capture_output=True, **kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'a', Path(tmp)/'b'
            one = cli('new', a, '--limit', 20, check=True).stdout
            two = cli('new', b, '--limit', 20, check=True).stdout
            self.assertNotEqual(one, two)
            self.assertEqual(cli('resume', a, check=True).stdout, (a/'learner.md').read_bytes())
            self.assertEqual(cli('resume', a, '--teacher', check=True).stdout, (a/'teacher.md').read_bytes())
            self.assertNotEqual(cli('new', a, '--limit', 20).returncode, 0)
            p = a/'session.json'
            form = json.loads(p.read_text())
            form['items'][0]['key'] = 'altered'
            p.write_text(json.dumps(form))
            self.assertNotEqual(cli('resume', a).returncode, 0)
