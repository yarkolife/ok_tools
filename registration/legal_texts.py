from bs4 import BeautifulSoup
from django.utils.html import escape
from django.utils.safestring import mark_safe
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import re


ALLOWED_TAGS = {
    'a',
    'br',
    'em',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'li',
    'ol',
    'p',
    'strong',
    'ul',
}

ALLOWED_ATTRIBUTES = {
    'a': {'href', 'rel', 'target'},
}

ALLOWED_LINK_SCHEMES = {'http', 'https', 'mailto', 'tel'}


def render_legal_text(raw_text: str, context: dict[str, Any]):
    """Render placeholders, convert markdown-like text to HTML and sanitize it."""
    rendered = _render_placeholders(raw_text, context)
    if not _looks_like_html(rendered):
        rendered = _markdown_to_html(rendered)
    sanitized = _sanitize_html(rendered)
    return mark_safe(sanitized)


def read_fallback_privacy_policy() -> str:
    """Read fallback privacy policy template file from files/privacy_policy.html."""
    from django.conf import settings

    fallback_path = Path(settings.BASE_DIR) / 'files' / 'privacy_policy.html'
    with fallback_path.open('r', encoding='utf-8') as fallback_file:
        return fallback_file.read()


def _render_placeholders(text: str, context: dict[str, Any]) -> str:
    """Render only placeholders in the form {{ VARIABLE }} using provided context."""
    placeholder_pattern = re.compile(r'\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}')

    def replace_placeholder(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        value = context.get(variable_name, '')
        if value is None:
            return ''
        return str(value)

    return placeholder_pattern.sub(replace_placeholder, text)


def _looks_like_html(text: str) -> bool:
    """Detect whether input likely already contains HTML tags."""
    return bool(re.search(r'<\s*/?\s*[a-zA-Z][^>]*>', text))


def _markdown_to_html(text: str) -> str:
    """Convert plain text with basic Markdown syntax into safe HTML structure."""
    lines = text.splitlines()
    html_lines: list[str] = []
    paragraph_buffer: list[str] = []
    list_buffer: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            paragraph_text = '<br>'.join(paragraph_buffer)
            html_lines.append(f'<p>{paragraph_text}</p>')
            paragraph_buffer.clear()

    def flush_list() -> None:
        if list_buffer:
            html_lines.append('<ul>')
            html_lines.extend(list_buffer)
            html_lines.append('</ul>')
            list_buffer.clear()

    for raw_line in lines:
        stripped = raw_line.strip()

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            heading_level = len(heading_match.group(1))
            heading_text = _format_inline(heading_match.group(2))
            html_lines.append(f'<h{heading_level}>{heading_text}</h{heading_level}>')
            continue

        list_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if list_match:
            flush_paragraph()
            list_item = _format_inline(list_match.group(1))
            list_buffer.append(f'<li>{list_item}</li>')
            continue

        flush_list()
        paragraph_buffer.append(_format_inline(stripped))

    flush_paragraph()
    flush_list()

    return '\n'.join(html_lines)


def _format_inline(text: str) -> str:
    """Apply minimal inline Markdown formatting with HTML escaping."""
    escaped = escape(text)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
    escaped = re.sub(r'\*(.+?)\*', r'<em>\1</em>', escaped)
    escaped = re.sub(r'\[(.+?)\]\((https?://[^\s)]+)\)', r'<a href="\2">\1</a>', escaped)
    return escaped


def _sanitize_html(html: str) -> str:
    """Sanitize HTML with a minimal whitelist of tags and attributes."""
    soup = BeautifulSoup(html, 'html.parser')

    for node in soup.find_all(True):
        if node.name not in ALLOWED_TAGS:
            if node.name in {'script', 'style'}:
                node.decompose()
            else:
                node.unwrap()
            continue

        allowed_attributes = ALLOWED_ATTRIBUTES.get(node.name, set())
        for attribute_name in list(node.attrs):
            if attribute_name not in allowed_attributes:
                del node.attrs[attribute_name]

        if node.name == 'a':
            _sanitize_anchor(node)

    return str(soup)


def _sanitize_anchor(node) -> None:
    """Sanitize anchor attributes and normalize secure defaults for links."""
    href = node.get('href', '').strip()
    if not href:
        node.attrs.pop('href', None)
        return

    parsed_url = urlparse(href)
    if parsed_url.scheme and parsed_url.scheme.lower() not in ALLOWED_LINK_SCHEMES:
        node.attrs.pop('href', None)

    target = node.get('target')
    if target not in {'_blank', '_self'}:
        node.attrs.pop('target', None)

    rel_values = node.get('rel')
    if isinstance(rel_values, str):
        rel_values = rel_values.split()
    rel_set = set(rel_values or [])

    if node.get('target') == '_blank':
        rel_set.update({'noopener', 'noreferrer'})

    if rel_set:
        node['rel'] = sorted(rel_set)
    else:
        node.attrs.pop('rel', None)
