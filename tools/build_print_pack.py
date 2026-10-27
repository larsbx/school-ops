"""Build standalone Grade 2 place-value print editions from reviewed source lists.

Run from any directory: python tools/build_print_pack.py
Optional dependency: pip install -r tools/requirements-print.txt
Does not fetch sources, collect learner data or change curriculum status.
"""
from pathlib import Path
import hashlib
import html
import json
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether,
    Table, TableStyle, HRFlowable,
)

ROOT = Path(__file__).resolve().parents[1]
UNIT = 'curriculum/mathematics/grade-2/units/place-value/'
PACK = UNIT + 'teaching-pack/'
ASSESS = 'assessments/C-MATH-001/'
# Explicit audience lists are the distribution boundary. No recursive inclusion.
EDITIONS = {
    'pv2-learner': ('learner', [UNIT+'two-cycle/learner.md', UNIT+'two-cycle/workbook.md',
                              *[PACK+f'learner/pv2-{i:02}.md' for i in (3, 4, 5)]]),
    'pv3-learner': ('learner', [UNIT+'two-cycle/learner.md', UNIT+'two-cycle/workbook.md',
                              *[PACK+f'learner/pv3-{i:02}.md' for i in (2, 3, 4, 5)]]),
    'partner-cards': ('learner', [UNIT+'two-cycle/partner-card-a.md', UNIT+'two-cycle/partner-card-b.md']),
    'entry-learner': ('learner', [ASSESS+'entry-tasks.md']),
    'pv2-check': ('learner', [ASSESS+'place-value-tasks-two-digit.md']),
    'pv3-check': ('learner', [ASSESS+'place-value-tasks-three-digit.md']),
    'pvx-check': ('learner', [ASSESS+'place-value-tasks-1000.md']),
    'm01-review': ('learner', [ASSESS+'tens-and-ones-cycle-tasks.md']),
    'pv2-teacher': ('teacher', [PACK+'teacher/pv2.md', UNIT+'two-cycle/teacher.md',
                              ASSESS+'entry-check.md', ASSESS+'place-value-check.md',
                              ASSESS+'tens-and-ones-cycle-review.md', PACK+'bank-workflow.md']),
    'pv3-teacher': ('teacher', [PACK+'teacher/pv3.md', UNIT+'two-cycle/teacher.md',
                              ASSESS+'entry-check.md', ASSESS+'place-value-check.md',
                              ASSESS+'tens-and-ones-cycle-review.md',
                              UNIT+'lessons/03-number-forms.md', UNIT+'lessons/04-counting.md',
                              PACK+'bank-workflow.md']),
}
WIDTH = 7.0 * inch
FONTDIR = Path('/usr/share/fonts/truetype/dejavu')


def register_fonts():
    # DejaVu supports the mathematical symbols in the original sources.
    for face, filename in [('Pack', 'DejaVuSans.ttf'), ('PackBold', 'DejaVuSans-Bold.ttf')]:
        path = FONTDIR / filename
        if not path.is_file():
            raise RuntimeError(f'Install DejaVu Sans fonts; missing {path}')
        pdfmetrics.registerFont(TTFont(face, str(path)))
    pdfmetrics.registerFontFamily('Pack', normal='Pack', bold='PackBold', italic='Pack', boldItalic='PackBold')


def inline(text):
    # Print editions intentionally have no clickable links or hidden URL targets.
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = text.replace('−', '-').replace('–', '-').replace('—', '-')
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<font name="Pack">\1</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    return text


def render_markdown(source, audience, styles):
    """Render the deliberately bounded prose/list/table subset used by this pack.

    Reject unsupported image/HTML syntax rather than silently dropping content.
    Assessment task tables become roomy response blocks in learner editions.
    """
    text = source.read_text(encoding='utf-8')
    if re.search(r'!\[|<script|<iframe', text, re.I):
        raise ValueError(f'Unsupported source markup: {source}')
    story, lines, i = [], text.splitlines(), 0
    paragraph = []

    def flush():
        if paragraph:
            story.append(Paragraph(inline(' '.join(paragraph)), styles['body']))
            paragraph.clear()

    def response():
        story.extend([Spacer(1, 8), HRFlowable(width='100%', color=colors.HexColor('#9ba5ac')),
                      Spacer(1, 18), HRFlowable(width='100%', color=colors.HexColor('#9ba5ac')),
                      Spacer(1, 8)])

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush(); i += 1; continue
        if line.startswith('```'):
            flush(); i += 1; code = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i]); i += 1
            # Wrap long shell invocations into readable paragraphs; source remains exact.
            for cmd in code:
                story.append(Paragraph(inline(cmd), styles['code']))
            i += 1; continue
        if line.startswith('|'):
            flush(); rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = [x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', x) for x in row): rows.append(row)
                i += 1
            if audience == 'learner':
                # Every learner table is a task table in this explicit source list.
                for row in rows[1:]:
                    block = [Paragraph(inline(row[0]), styles['h3']),
                             Paragraph(inline(' '.join(row[1:])), styles['body']),
                             Spacer(1, 65)]
                    story.append(KeepTogether(block))
                continue
            n = len(rows[0])
            weights = [0.22, 0.78] if n == 2 else [1/n] * n
            cells = [[Paragraph(inline(c), styles['cell']) for c in row] for row in rows]
            table = Table(cells, colWidths=[WIDTH*w for w in weights], repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9eef0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LINEBELOW', (0, 0), (-1, 0), .6, colors.HexColor('#8797a0')),
                ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor('#d1d9dd')),
                ('LEFTPADDING', (0, 0), (-1, -1), 7),
                ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.extend([table, Spacer(1, 8)]); continue
        if line.startswith('#'):
            flush(); hashes, heading = line.split(' ', 1)
            style = styles['h1' if len(hashes)==1 else 'h2' if len(hashes)==2 else 'h3']
            story.append(Paragraph(inline(heading), style)); i += 1; continue
        if '_'*8 in line:
            flush()
            # Existing M01 answer lines are writing space, not literal long rules.
            label = re.sub(r'_{3,}', '', line).strip()
            if label: story.append(Paragraph(inline(label), styles['body']))
            response(); i += 1
            # Consecutive blank rules in source are one response area.
            while i < len(lines) and (not lines[i].strip() or re.fullmatch(r'_+', lines[i].strip())):
                i += 1
            continue
        if re.match(r'^(- |\d+\. )', line):
            flush(); paragraph.append(line); i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r'^(#|\||- |\d+\. )', lines[i].strip()):
                paragraph.append(lines[i].strip()); i += 1
            flush(); continue
        paragraph.append(line); i += 1
    flush()
    if audience == 'learner':
        # Keep each prompt and its response area on the same page.
        grouped, j = [], 0
        while j < len(story):
            flow = story[j]
            if (isinstance(flow, Paragraph) and flow.style.name in ('Task', 'Heading')
                    and re.match(r'^(?:[ABRW]\d|E\d|P-PV[23]-)', flow.getPlainText())):
                block = [flow]; j += 1
                while j < len(story):
                    nxt = story[j]
                    if isinstance(nxt, Paragraph) and nxt.style.name in ('Task', 'Heading', 'Title'):
                        break
                    block.append(nxt); j += 1
                grouped.append(KeepTogether(block))
            else:
                grouped.append(flow); j += 1
        story = grouped
    return story


def main():
    register_fonts()
    styles = {
        'body': ParagraphStyle('Body', fontName='Pack', fontSize=11.5, leading=17, spaceAfter=9),
        'h1': ParagraphStyle('Title', fontName='PackBold', fontSize=21, leading=26, spaceAfter=16, keepWithNext=True),
        'h2': ParagraphStyle('Heading', fontName='PackBold', fontSize=15, leading=20, spaceBefore=15, spaceAfter=9, keepWithNext=True),
        'h3': ParagraphStyle('Task', fontName='PackBold', fontSize=12, leading=17, spaceBefore=10, spaceAfter=7, keepWithNext=True),
        'cell': ParagraphStyle('Cell', fontName='Pack', fontSize=10, leading=14, spaceAfter=2),
        'code': ParagraphStyle('Code', fontName='Pack', fontSize=9.5, leading=14, spaceAfter=7, splitLongWords=True),
    }
    output = ROOT / PACK / 'print'
    output.mkdir(exist_ok=True)
    manifest = {'format': 1, 'status': 'draft', 'page_size': 'US Letter', 'editions': {}}
    for name, (audience, paths) in EDITIONS.items():
        story = []
        for index, rel in enumerate(paths):
            if index: story.append(PageBreak())
            source = ROOT / rel
            if audience == 'learner':
                content = source.read_text()
                if re.search(r'\]\([^)]*(teacher|manifest|place-value-check|entry-check|cycle-review)', content):
                    raise ValueError(f'Key link in learner source: {rel}')
            story.extend(render_markdown(source, audience, styles))
        destination = output / f'{name}.pdf'
        def footer(canvas, doc):
            canvas.saveState(); canvas.setFont('Pack', 8)
            canvas.setFillColor(colors.HexColor('#53636e'))
            canvas.drawString(.75*inch, .42*inch, f'Grade 2 place value | DRAFT | {name} | {audience.upper()}')
            canvas.drawRightString(7.75*inch, .42*inch, str(doc.page)); canvas.restoreState()
        doc = SimpleDocTemplate(str(destination), pagesize=(8.5*inch, 11*inch),
                                rightMargin=.75*inch, leftMargin=.75*inch,
                                topMargin=.65*inch, bottomMargin=.7*inch,
                                title=f'Grade 2 {name} (draft)', author='school-ops', invariant=1)
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        manifest['editions'][name] = {
            'audience': audience,
            'sources': [{'path': rel, 'sha256': hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()} for rel in paths],
            'pdf_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
        }
        print(destination.relative_to(ROOT))
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
