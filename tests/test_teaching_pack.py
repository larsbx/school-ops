"""Source contracts for the authored pack; no learner results or provider calls."""
import hashlib
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT/'curriculum/mathematics/grade-2/units/place-value/teaching-pack'
LINK = re.compile(r'\[[^\]]*\]\(([^)]+)\)')


def anchors(path):
    found, counts = set(), {}
    for line in path.read_text().splitlines():
        if not line.startswith('#'): continue
        label = re.sub(r'`([^`]+)`', r'\1', line.lstrip('#').strip()).lower()
        slug = re.sub(r'[^\w\- ]', '', label).replace(' ', '-')
        count = counts.get(slug, 0); counts[slug] = count + 1
        found.add(slug + (f'-{count}' if count else ''))
    return found


class TeachingPackTests(unittest.TestCase):
    def test_all_repository_relative_links_and_anchors(self):
        for file in ROOT.rglob('*.md'):
            if '.git' in file.parts: continue
            for target in LINK.findall(file.read_text()):
                if re.match(r'\w+://|mailto:', target): continue
                path, _, anchor = unquote(target).partition('#')
                resolved = (file.parent/path).resolve() if path else file
                with self.subTest(file=str(file.relative_to(ROOT)), target=target):
                    self.assertTrue(resolved.exists())
                    if anchor and resolved.suffix == '.md':
                        self.assertIn(anchor, anchors(resolved))

    def test_learner_navigation_cannot_reach_keys(self):
        starts = [PACK/'learner/README.md', *PACK.glob('learner/*.md'),
                  *ROOT.glob('assessments/C-MATH-001/*tasks*.md')]
        visited, pending = set(), starts[:]
        while pending:
            f = pending.pop().resolve()
            if f in visited: continue
            visited.add(f)
            text = f.read_text()
            self.assertNotRegex(f.name, r'teacher|manifest|check\.md|review\.md')
            self.assertNotRegex(text, r'(?i)## .*teacher key|Key:|Model evidence:')
            for target in LINK.findall(text):
                if re.match(r'\w+://|mailto:', target): continue
                path = unquote(target).split('#')[0]
                dest = (f.parent/path).resolve()
                if path and dest.suffix == '.md': pending.append(dest)

    def test_every_new_worksheet_task_has_one_complete_key(self):
        total = 0
        for f in PACK.glob('learner/pv[23]-*.md'):
            tasks = re.findall(r'^## (P-PV[23]-\d\d-\d\d)$', f.read_text(), re.M)
            self.assertEqual(4, len(tasks)); self.assertEqual(4, len(set(tasks)))
            key = (PACK/'teacher'/f'{f.name[:3]}.md').read_text()
            for task in tasks:
                self.assertEqual(1, len(re.findall(r'^- '+task+r': .+', key, re.M)))
            total += len(tasks)
        self.assertEqual(28, total)

    def test_stable_record_ids_and_outcomes(self):
        unit = PACK.parent
        for i, f in enumerate(sorted((unit/'lessons').glob('*.md')), 1):
            self.assertIn(f'Lesson ID: L-MATH-001-01-{i:02}', f.read_text())
            self.assertIn('Status: draft', f.read_text())
        course = (unit.parent.parent/'README.md').read_text()
        definitions = re.findall(r'^\| (O-MATH-001-\d{3}) \|', course, re.M)
        self.assertEqual([f'O-MATH-001-{i:03}' for i in range(1,14)], definitions)
        for route, count in [('two-digit',12),('three-digit',12),('1000',2)]:
            f=ROOT/f'assessments/C-MATH-001/place-value-tasks-{route}.md'
            tags=re.findall(r'^\| (PV[23X]-\d\d) \|',f.read_text(),re.M)
            self.assertEqual(count,len(tags)); self.assertEqual(count,len(set(tags)))

    def test_print_source_and_pdf_hashes_and_audience(self):
        manifest=json.loads((PACK/'print/manifest.json').read_text())
        self.assertEqual(10,len(manifest['editions']))
        for name, edition in manifest['editions'].items():
            f=PACK/'print'/f'{name}.pdf'
            self.assertEqual(edition['pdf_sha256'],hashlib.sha256(f.read_bytes()).hexdigest())
            for source in edition['sources']:
                f=ROOT/source['path']
                self.assertEqual(source['sha256'],hashlib.sha256(f.read_bytes()).hexdigest())
                if edition['audience']=='learner':
                    self.assertNotRegex(f.name,r'teacher|manifest|check\.md|review\.md')
            if name in ('pv2-learner','pv3-learner'):
                self.assertFalse(any('/assessments/' in '/'+s['path'] or 'partner-card' in s['path']
                                     for s in edition['sources']))

    def test_numeric_equality_chains_in_new_keys(self):
        term=r'\d[\d,]*(?:\s+(?:hundreds?|tens?|ones?))?'
        expr=term+r'(?:\s*[+×]\s*'+term+r')*'
        chain=re.compile(expr+r'(?:\s*=\s*'+expr+r')+')
        checked=0
        def value(text):
            text=text.replace(',','')
            for word, multiplier in [('hundreds?',100),('tens?',10),('ones?',1)]:
                text=re.sub(r'(\d+)\s+'+word+r'\b',lambda m:str(int(m[1])*multiplier),text)
            # Only the tightly matched decimal + and multiplication grammar is evaluated.
            self.assertRegex(text,r'^[0-9+×\s]+$')
            return sum(__import__('math').prod(map(int,p.split('×'))) for p in text.split('+'))
        for f in (PACK/'teacher').glob('pv*.md'):
            sections=re.findall(r'### Complete lesson and learner key\n(.*?)(?=\nSuccess check:)',f.read_text(),re.S)
            for section in sections:
                for match in chain.finditer(section):
                    nums=[value(x.strip()) for x in match[0].split('=')]
                    self.assertEqual(len(set(nums)),1,match[0]);checked+=1
        self.assertGreaterEqual(checked,25)


if __name__=='__main__': unittest.main()
