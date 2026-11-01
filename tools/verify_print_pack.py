"""Verify print text, geometry and audience separation; optionally render page PNGs.

Install tools/requirements-print.txt. Run:
python tools/verify_print_pack.py --render-directory /tmp/place-value-pages
Review those rendered pages visually as well; geometry alone cannot judge layout.
"""
import argparse
import json
from pathlib import Path
import re

import fitz

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT/'curriculum/mathematics/grade-2/units/place-value/teaching-pack'


def normalize(text):
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = text.replace('−', '-').replace('–', '-').replace('—', '-')
    return re.sub(r'[^\w]+', '', text).replace('_', '').lower()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(render_directory=None):
    manifest = json.loads((PACK/'print/manifest.json').read_text())
    page_count = 0
    if render_directory:
        render_directory.mkdir(parents=True, exist_ok=True)
    for name, edition in manifest['editions'].items():
        with fitz.open(PACK/'print'/f'{name}.pdf') as document:
            # Exclude page footers when matching source lines spanning a page boundary.
            text = '\n'.join(page.get_text(clip=fitz.Rect(0, 0, 612, 745)) for page in document)
            normalized = normalize(text)
            for source in edition['sources']:
                for line in (ROOT/source['path']).read_text().splitlines():
                    if not line.strip() or line.startswith('```') or re.fullmatch(r'[| :\-]+', line):
                        continue
                    parts = line.strip('|').split('|') if line.startswith('|') else [line]
                    for part in parts:
                        key = normalize(part)
                        if len(key) > 5:
                            require(key in normalized, f'{name}: missing source text: {part}')
            if edition['audience'] == 'learner':
                require(not re.search(r'Complete lesson and learner key|Teacher key or model evidence|Model evidence:|Key:', text),
                        f'{name}: teacher key marker found')
            for index, page in enumerate(document):
                require((page.rect.width, page.rect.height) == (612, 792), f'{name}: page size')
                require(not list(page.annots() or []) and not page.get_links(), f'{name}: annotations')
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines', []):
                        for span in line['spans']:
                            x0, y0, x1, y1 = span['bbox']
                            require(x0 >= 53 and x1 <= 559 and y0 >= 20 and y1 <= 772,
                                    f'{name}, page {index+1}: text outside print bounds')
                            require('\ufffd' not in span['text'], f'{name}: replacement glyph')
                if render_directory:
                    page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25)).save(
                        render_directory/f'{name}-{index+1:02}.png')
            page_count += len(document)
    print(f"Verified {len(manifest['editions'])} editions / {page_count} pages: source text, bounds, annotations and audience markers")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--render-directory', type=Path)
    verify(parser.parse_args().render_directory)
