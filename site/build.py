"""Build the website into _site/: the static pages in site/ plus HTML pages rendered from the markdown guides.

The markdown in docs/ (and the dashboard READMEs) stays the single source; this script only reads it.
Run from anywhere: python site/build.py [--out DIR]
"""

import argparse
import html
import posixpath
import re
import shutil
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
REPO = 'https://github.com/SunilParameswaran/Second_Opinion'
PAGES = 'https://sunilparameswaran.github.io/Second_Opinion/'
# Files in site/ that build the website but are not part of it.
NOT_PUBLISHED = {'build.py', 'README.md', 'requirements.txt'}

# (markdown source, page slug under docs/, sidebar title, one-line summary)
GUIDES = [
    ('docs/methodology.md', 'methodology', 'Methodology',
     'Problem framing, the full method, design decisions and limitations'),
    ('docs/data_prep/README.md', 'data-prep', 'Data preparation',
     'Input format, preparation outputs, verification and supplementary reports'),
    ('docs/history_detector/README.md', 'history-detector', 'History detector',
     'Measurement groups, scoring, rules, cases, options and the artificial-fault evaluation'),
    ('docs/isolation_forest/README.md', 'isolation-forest', 'Isolation Forest',
     'Features, eligibility, chronological splits, thresholds and the budget comparison'),
    ('web_dashboard/README.md', 'web-dashboard', 'Web dashboard',
     'The browser-based review workspace with an optional Claude explanation'),
    ('dashboard/README.md', 'dashboard', 'Streamlit dashboard',
     'The operator prototype and the dry-weather exploration'),
]
PAGE_OF = {source: slug for source, slug, _, _ in GUIDES}

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Second Opinion</title>
<meta name="description" content="{description}">
<meta name="theme-color" content="#04090d">
<meta property="og:title" content="{title} · Second Opinion">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{pages}assets/banner.png">
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono&display=swap">
<link rel="stylesheet" href="{root}assets/site.css">
</head>
<body>
<header class="top"><a class="brand" href="{root}">Second Opinion</a><nav><a href="{root}pipeline/">Pipeline</a><a class="on" href="{root}docs/">Docs</a><a href="{repo}">GitHub ↗</a></nav></header>
<div class="docs">
  <aside><p class="lbl">Guides</p><ul>
{sidebar}
  </ul></aside>
  <main class="prose">
{body}
{edit}
    <div class="foot"><span>Second Opinion · Built for TAI / Z-info</span><a href="#">Back to top ↑</a></div>
  </main>
</div>
</body>
</html>
"""


def slugify(title: str) -> str:
    """GitHub-style heading ids, so links written for GitHub keep working on the site."""
    return re.sub(r'[^\w\- ]', '', title.strip().lower()).replace(' ', '-')


def markdown() -> MarkdownIt:
    md = MarkdownIt('commonmark', {'html': False}).enable('table')
    anchors_plugin(md, min_level=2, max_level=3, slug_func=slugify, permalink=True, permalinkSymbol='#')
    return md


def rewrite(link: str, source: str, page_root: str) -> str:
    """Point a relative repository link at its site page, or at GitHub when it is not on the site."""
    if not link or link.startswith('#') or re.match(r'^[a-z][a-z0-9+.-]*:', link, re.I):
        return link
    path, _, anchor = link.partition('#')
    anchor = '#' + anchor if anchor else ''
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    if target in PAGE_OF:
        return f'{page_root}docs/{PAGE_OF[target]}/{anchor}'
    kind = 'tree' if path.endswith('/') or (ROOT / target).is_dir() else 'blob'
    return f'{REPO}/{kind}/main/{target}{anchor}'


def render(md: MarkdownIt, source: str, page_root: str) -> tuple[str, str]:
    """Return (page title, HTML body) for one markdown file."""
    tokens = md.parse((ROOT / source).read_text(encoding='utf-8'))
    title = source
    for i, token in enumerate(tokens):
        if token.type == 'heading_open' and token.tag == 'h1':
            title = tokens[i + 1].content
            break
    for token in tokens:
        for child in token.children or []:
            if child.type == 'link_open':
                child.attrs['href'] = rewrite(str(child.attrs.get('href', '')), source, page_root)
            elif child.type == 'image':
                child.attrs['src'] = rewrite(str(child.attrs.get('src', '')), source, page_root)
    return title, md.renderer.render(tokens, md.options, {})


def sidebar(page_root: str, current: str | None) -> str:
    items = []
    for _, slug, name, _ in GUIDES:
        on = ' class="on" aria-current="page"' if slug == current else ''
        items.append(f'    <li><a{on} href="{page_root}docs/{slug}/">{html.escape(name)}</a></li>')
    return '\n'.join(items)


def page(title: str, description: str, root: str, current: str | None, body: str, edit: str = '') -> str:
    return TEMPLATE.format(title=html.escape(title), description=html.escape(description), root=root, pages=PAGES,
                           repo=REPO, sidebar=sidebar(root, current), body=body, edit=edit)


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE, out, ignore=lambda folder, names: [n for n in names if n in NOT_PUBLISHED or n == '__pycache__'])
    # README graphics, so pages and link previews can use them.
    for image in (ROOT / 'docs' / 'assets').glob('*.png'):
        shutil.copy2(image, out / 'assets' / image.name)

    md = markdown()
    for source, slug, name, summary in GUIDES:
        root = '../../'
        title, body = render(md, source, root)
        edit = f'    <p class="edit"><a href="{REPO}/edit/main/{source}">Edit this page on GitHub ↗</a></p>'
        target = out / 'docs' / slug / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(title, summary, root, slug, body, edit), encoding='utf-8')

    cards = '\n'.join(f'    <a href="{slug}/"><span class="lbl">{i:02d}</span><b>{html.escape(name)}</b><span>{html.escape(summary)}</span></a>'
                      for i, (_, slug, name, summary) in enumerate(GUIDES, 1))
    body = ('    <h1>Documentation</h1>\n'
            '    <p>How Second Opinion prepares measurements, scores them against their own history, and ranks what to check first. '
            'Start with the methodology, then read the guide for the stage you are working on. '
            'For a hands-on view of each stage, see the <a href="../pipeline/">interactive pipeline</a>.</p>\n'
            f'    <div class="cards">\n{cards}\n    </div>')
    (out / 'docs' / 'index.html').write_text(
        page('Documentation', 'Guides to the Second Opinion method and each pipeline stage.', '../', None, body), encoding='utf-8')
    print(f'Built {len(GUIDES)} guides into {out}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, default=ROOT / '_site', help='output directory (replaced on every build)')
    build(parser.parse_args().out)
