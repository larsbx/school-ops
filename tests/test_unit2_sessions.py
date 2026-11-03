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

    def test_work_saves_and_continues_without_resampling(self):
        def cli(*args, **kwargs):
            return subprocess.run([sys.executable, '-m', 'exercise_bank.unit2', *map(str, args)],
                                  text=True, capture_output=True, check=True, **kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'private-session'
            cli('new', path, '--activity', 'difference', '--limit', 10)
            manifest = (path/'session.json').read_bytes()
            self.assertIn('Paused', cli('work', path, input='First model\n\n').stdout)
            saved = json.loads((path/'progress.json').read_text())
            self.assertEqual(saved['responses'], {'U2-01': 'First model'})
            continued = cli('work', path, input='Second model\n').stdout
            self.assertNotIn('U2-01:', continued)
            self.assertIn('U2-02:', continued)
            self.assertIn('2/2', continued)
            self.assertEqual((path/'session.json').read_bytes(), manifest)
            self.assertNotIn('First model', cli('resume', path).stdout)
            saved = json.loads((path/'progress.json').read_text())
            self.assertEqual(saved['responses'], {'U2-01': 'First model', 'U2-02': 'Second model'})
