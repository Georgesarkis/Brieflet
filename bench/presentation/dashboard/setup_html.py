"""Models section (writers, readers, judge, what's supported) and the generated-docs section."""
from __future__ import annotations

from pathlib import Path

from .markdown_html import esc, md
from .texts import SUPPORTED

FIRST_DOCS = ("AI_CONTEXT.md", "CLAUDE.md")


def models(meta: dict, readers: list[dict], judge: dict) -> str:
    writers = "".join(f"<tr><td>{esc(w.get('role'))}</td><td><code>{esc(w.get('model'))}</code></td><td>{esc(w.get('runtime'))}</td></tr>"
                      for w in meta.get("writers", []))
    rd = "".join(f"<tr><td>{esc(m['name'])}</td><td><code>{esc(m['model'])}</code></td><td>{esc(m['runner'])}"
                 f"{' (' + esc(m['billing']) + ')' if m.get('billing') else ''}</td></tr>"
                 for m in readers)
    supported = "".join(f"<h4>{esc(k)}</h4><div class='tw'><table><tbody>" +
                        "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td class='muted'>{esc(c)}</td></tr>" for a, b, c in v) +
                        "</tbody></table></div>" for k, v in SUPPORTED.items())
    return (
        "<h3>Used in this run</h3>"
        f"<h4>Writers{(' · ' + esc(meta.get('generated'))) if meta.get('generated') else ''}"
        f"{(' · ' + esc(meta.get('hardware'))) if meta.get('hardware') else ''}</h4>"
        f"<div class='tw'><table><thead><tr><th>Job</th><th>Model</th><th>Runs on</th></tr></thead><tbody>{writers or '<tr><td colspan=3>unknown</td></tr>'}</tbody></table></div>"
        f"<h4>Readers</h4><div class='tw'><table><thead><tr><th>Name</th><th>Model</th><th>How</th></tr></thead><tbody>{rd}</tbody></table></div>"
        + (f"<h4>Judge</h4><p><code>{esc(judge.get('model'))}</code> via {esc(judge.get('runner'))}: grades each answer 0–3 against "
           "reference points, without knowing the setup.</p>" if judge else "")
        + "<h3>Supported</h3>" + supported)


def doc_files(folder: Path) -> str:
    """Every .md the Brieflet setup puts in front of the reader, AI_CONTEXT.md first and open."""
    files = sorted(folder.rglob("*.md"), key=lambda p: (p.name != FIRST_DOCS[0], p.name != FIRST_DOCS[1], "decisions" in str(p), str(p)))
    out = []
    for p in files:
        rel = p.relative_to(folder).as_posix()
        txt = p.read_text(encoding="utf-8", errors="replace")
        out.append(f"<details{' open' if rel == FIRST_DOCS[0] else ''}><summary><code>{esc(rel)}</code>"
                   f"<span class='muted'> · {len(txt):,} chars ≈ {len(txt) // 4:,} tokens</span></summary>"
                   f"<div class='doc'>{md(txt)}</div></details>")
    return "".join(out)


def graph_compare(graph_report: Path, ai_context: Path) -> str:
    if not graph_report.exists():
        return ""
    n = len(graph_report.read_text(errors="replace"))
    ctx = len(ai_context.read_text()) if ai_context.exists() else 1
    return (f"<p class='muted'>For comparison: Graphify's <code>GRAPH_REPORT.md</code> is {n:,} chars ≈ {n // 4:,} tokens "
            f"({n / max(1, ctx):.0f}× AI_CONTEXT.md).</p>")


def learned_folds(learned_dir: Path | None) -> str:
    if not learned_dir or not Path(learned_dir).is_dir():
        return ""
    out = []
    for f in sorted(Path(learned_dir).rglob("fold*.md")):
        txt = f.read_text(encoding="utf-8", errors="replace")
        n = sum(1 for l in txt.splitlines() if l.startswith("- "))
        out.append(f"<details><summary><strong>Learned · {esc(f.parent.name)} · {esc(f.stem)}</strong>"
                   f"<span class='muted'> · {n} facts</span></summary><div class='doc'>{md(txt)}</div></details>")
    return "".join(out)
