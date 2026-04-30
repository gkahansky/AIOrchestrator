"""
Platform skill: render_markdown

Convert Markdown text to styled HTML for Playwright PDF rendering.

Handles:
  - Tables       — parsed into styled <table> with proper alignment; no ASCII art
  - Headings     — h1–h4
  - Bullet lists — ul/li (nested via indentation)
  - Numbered lists — ol/li
  - Bold **text** and italic *text*
  - Inline code  `text`
  - Blockquotes  > text
  - Horizontal rules ---
  - Visual markers [SCREENSHOT: url | caption] and [GENERATE IMAGE: desc | caption]
    replaced with <figure><img> blocks when a `visuals` dict is supplied.

Venture-agnostic. Does NOT emit <html>/<head>/<body> wrappers — returns body content only.
"""

import html as _html
import re
from typing import Optional

# Regex that detects visual markers embedded in the research text
MARKER_RE = re.compile(
    r'\[(SCREENSHOT|GENERATE IMAGE):\s*([^|\]]+?)(?:\s*\|\s*([^\]]*?))?\]',
    re.IGNORECASE,
)


def extract_visual_markers(text: str) -> list[tuple[str, str, str, str]]:
    """
    Find all visual markers in markdown text.

    Returns:
        List of (full_match, type, content, caption)
        type is "SCREENSHOT" or "GENERATE IMAGE".
    """
    results = []
    for m in MARKER_RE.finditer(text):
        full_match = m.group(0)
        marker_type = m.group(1).upper()
        content = m.group(2).strip()
        caption = (m.group(3) or "").strip()
        results.append((full_match, marker_type, content, caption))
    return results


def markdown_to_html(text: str, visuals: Optional[dict] = None) -> str:
    """
    Convert Markdown to HTML body content.

    Args:
        text:    Markdown string.
        visuals: Optional dict mapping full marker text → data URI string
                 (e.g. "data:image/png;base64,..."). Markers not present in
                 the dict are silently removed from output.

    Returns:
        HTML string suitable for embedding inside a <body>.
    """
    lines = text.split("\n")
    output: list[str] = []
    i = 0
    list_stack: list[str] = []   # tracks open "ul" / "ol" tags

    def close_all_lists():
        while list_stack:
            output.append(f"</{list_stack.pop()}>")

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        # ── Blank line ────────────────────────────────────────────────────────
        if not line:
            close_all_lists()
            i += 1
            continue

        # ── Visual marker (whole line) ────────────────────────────────────────
        if MARKER_RE.fullmatch(line) and visuals is not None:
            close_all_lists()
            m = MARKER_RE.fullmatch(line)
            data_uri = visuals.get(line, "")
            caption = (m.group(3) or m.group(2)).strip()
            if data_uri:
                output.append(
                    f'<figure>'
                    f'<img src="{data_uri}" alt="{_html.escape(caption)}">'
                    f'<figcaption>{_html.escape(caption)}</figcaption>'
                    f'</figure>'
                )
            i += 1
            continue

        # ── Horizontal rule ───────────────────────────────────────────────────
        if re.fullmatch(r'[-*_]{3,}', line):
            close_all_lists()
            output.append("<hr>")
            i += 1
            continue

        # ── Headings ──────────────────────────────────────────────────────────
        hm = re.match(r'^(#{1,4})\s+(.*)', line)
        if hm:
            close_all_lists()
            level = len(hm.group(1))
            content = _inline(hm.group(2))
            output.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        # ── Markdown table block ──────────────────────────────────────────────
        if line.startswith("|"):
            close_all_lists()
            table_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            output.append(_parse_table(table_lines))
            continue

        # ── Blockquote ────────────────────────────────────────────────────────
        if line.startswith("> "):
            close_all_lists()
            content = _inline(line[2:])
            output.append(f"<blockquote>{content}</blockquote>")
            i += 1
            continue

        # ── Bullet list item ──────────────────────────────────────────────────
        bm = re.match(r'^[-*+]\s+(.*)', line)
        if bm:
            if not list_stack or list_stack[-1] != "ul":
                if list_stack:
                    output.append(f"</{list_stack.pop()}>")
                output.append("<ul>")
                list_stack.append("ul")
            content = _inline(bm.group(1))
            output.append(f"<li>{content}</li>")
            i += 1
            continue

        # ── Numbered list item ────────────────────────────────────────────────
        nm = re.match(r'^\d+[.)]\s+(.*)', line)
        if nm:
            if not list_stack or list_stack[-1] != "ol":
                if list_stack:
                    output.append(f"</{list_stack.pop()}>")
                output.append("<ol>")
                list_stack.append("ol")
            content = _inline(nm.group(1))
            output.append(f"<li>{content}</li>")
            i += 1
            continue

        # ── Plain paragraph ───────────────────────────────────────────────────
        close_all_lists()
        output.append(f"<p>{_inline(line)}</p>")
        i += 1

    close_all_lists()
    return "\n".join(output)


# ─── Table parser ──────────────────────────────────────────────────────────────

def _parse_table(lines: list[str]) -> str:
    """
    Parse a Markdown table (list of pipe-delimited lines) into styled HTML.

    Expects at least two lines (header + separator); any additional lines are
    data rows.  Alignment is read from the separator row (`:--`, `--:`, `:--:`).
    """
    if len(lines) < 2:
        # Not enough lines for a proper table — fall back to <pre>
        return "<pre>" + _html.escape("\n".join(lines)) + "</pre>"

    def _split_cells(line: str) -> list[str]:
        """Split a pipe-delimited row into stripped cell strings."""
        return [c.strip() for c in line.strip("|").split("|")]

    headers = _split_cells(lines[0])
    sep_cells = _split_cells(lines[1])
    data_rows = [_split_cells(ln) for ln in lines[2:]] if len(lines) > 2 else []

    # Parse alignment from separator cells
    aligns: list[str] = []
    for s in sep_cells:
        s = s.strip()
        if s.startswith(":") and s.endswith(":"):
            aligns.append("center")
        elif s.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")

    def _align_style(idx: int) -> str:
        a = aligns[idx] if idx < len(aligns) else "left"
        return f' style="text-align:{a}"'

    # Build HTML
    parts: list[str] = ['<table>']

    # Header
    parts.append("<thead><tr>")
    for idx, h in enumerate(headers):
        parts.append(f"<th{_align_style(idx)}>{_inline(h)}</th>")
    parts.append("</tr></thead>")

    # Body
    if data_rows:
        parts.append("<tbody>")
        for row in data_rows:
            # Pad short rows to match header column count
            padded = row + [""] * max(0, len(headers) - len(row))
            parts.append("<tr>")
            for idx, cell in enumerate(padded[: len(headers)]):
                parts.append(f"<td{_align_style(idx)}>{_inline(cell)}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")

    parts.append("</table>")
    return "\n".join(parts)


# ─── Inline formatter ──────────────────────────────────────────────────────────

def _inline(text: str) -> str:
    """Apply inline Markdown formatting: bold, italic, code, links, HTML-escape."""
    # Escape HTML entities first (before we add our own tags)
    text = _html.escape(text)

    # Inline code (must be before bold/italic to protect backtick content)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Bold+italic ***text***
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)

    # Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Italic *text* (not adjacent to another *)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)

    # Bold __text__
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

    # Links [text](url)  — already HTML-escaped, unescape the URL part carefully
    def _link(m: re.Match) -> str:
        label = m.group(1)
        url = m.group(2).replace("&amp;", "&")
        return f'<a href="{_html.escape(url)}">{label}</a>'

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link, text)

    # Source citations [Source: name, year] — style as superscript
    text = re.sub(
        r'\[Source:\s*([^\]]+)\]',
        r'<sup class="citation">[Source: \1]</sup>',
        text,
    )

    return text
