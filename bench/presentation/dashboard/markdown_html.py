"""Small Markdown → HTML for our own generated docs (headings, lists, tables, bold, code, links, mermaid)."""
from __future__ import annotations

import html
import re


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def md(text: str) -> str:
    """Small Markdown → HTML for our own generated docs (headings, lists, tables, bold, code, links, mermaid)."""
    out, lines, i = [], text.splitlines(), 0

    def inline(s: str) -> str:
        s = esc(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<span class="lnk">\1</span>', s)

    while i < len(lines):
        l = lines[i]
        if l.startswith("```mermaid"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append(f'<pre class="mermaid">{esc(chr(10).join(lines[i + 1:j]))}</pre>')
            i = j + 1
            continue
        if l.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append(f"<pre><code>{esc(chr(10).join(lines[i + 1:j]))}</code></pre>")
            i = j + 1
            continue
        if l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in l.strip().strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            out.append('<div class="tw"><table><thead><tr>' + "".join(f"<th>{inline(h)}</th>" for h in head) +
                       "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) +
                       "</tbody></table></div>")
            i = j
            continue
        if m := re.match(r"^(#{1,4})\s+(.*)", l):
            n = min(len(m.group(1)) + 2, 6)
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif re.match(r"^\s*[-*]\s+", l):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(f"<li>{inline(re.sub(r'^\s*[-*]\s+', '', lines[i]))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif l.strip() and not l.startswith("<!--"):
            out.append(f"<p>{inline(l)}</p>")
        i += 1
    return "\n".join(out)
