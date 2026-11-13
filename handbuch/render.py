"""Turn a chapter written in Markdown into the HTML shown in the admin.

Chapters live in ``handbuch/inhalt/<slug>.md``. Besides plain Markdown they use:

- ``[TOC]`` for the table of contents (level-2 headings),
- ``## Heading {#anchor}`` for stable anchors the "?" links point to,
- ``![Alt text](bilder/file.jpg "Caption")`` for screenshots from
  ``handbuch/static/handbuch/bilder/``; an image on its own line becomes a
  figure with the caption below, opening the full image on click,
- ``!!! hinweis ""`` / ``!!! warnung ""`` followed by an indented block for
  hint and warning boxes.

The text is part of the code (not user input), so it is not sanitised.
"""

from django.templatetags.static import static
from functools import lru_cache
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from pathlib import Path
import markdown
import struct
import xml.etree.ElementTree as etree


KAPITEL_DIR = Path(__file__).resolve().parent / 'inhalt'
BILDER_DIR = Path(__file__).resolve().parent / 'static' / 'handbuch' / 'bilder'
BILDER_PREFIX = 'bilder/'


def image_size(path: Path):
    """Width and height of a PNG or JPEG, or None; reserves the space before loading."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack('>HH', data[i + 5:i + 9])
            return width, height
        i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
    return None


class _FigureProcessor(Treeprocessor):
    """Screenshots: static URL, size, and a figure with caption when alone in a paragraph."""

    def run(self, root):
        for img in root.iter('img'):
            src = img.get('src', '')
            if src.startswith(BILDER_PREFIX):
                name = src[len(BILDER_PREFIX):]
                img.set('src', static(f'handbuch/bilder/{name}'))
                size = image_size(BILDER_DIR / name)
                if size:
                    img.set('width', str(size[0]))
                    img.set('height', str(size[1]))
            img.set('loading', 'lazy')

        for paragraph in list(root.iter('p')):
            children = list(paragraph)
            if (len(children) == 1 and children[0].tag == 'img'
                    and not (paragraph.text or '').strip() and not (children[0].tail or '').strip()):
                img = children[0]
                caption = img.attrib.pop('title', '')
                paragraph.tag = 'figure'
                paragraph.remove(img)
                link = etree.SubElement(paragraph, 'a', href=img.get('src'), target='_blank')
                link.append(img)
                img.tail = None
                if caption:
                    etree.SubElement(paragraph, 'figcaption').text = caption


class _FigureExtension(Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(_FigureProcessor(md), 'handbuch_figures', 5)


def _converter():
    return markdown.Markdown(
        extensions=['tables', 'attr_list', 'admonition', 'sane_lists', 'toc', _FigureExtension()],
        extension_configs={'toc': {'title': 'Inhalt', 'toc_depth': '2'}},
        output_format='html',
    )


@lru_cache(maxsize=32)
def _render(path: str, mtime: float) -> str:
    return _converter().convert(Path(path).read_text(encoding='utf-8'))


def render_chapter(slug: str) -> str:
    """HTML of a chapter; re-read whenever its file changes."""
    path = KAPITEL_DIR / f'{slug}.md'
    return _render(str(path), path.stat().st_mtime)
