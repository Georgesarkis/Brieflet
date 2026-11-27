"""Results section: headline tiles, token bars, the per-setup table and the per-question table."""
from __future__ import annotations

from ...domain.results import ArmStats
from .markdown_html import esc
from .texts import ARM_TEXT, lab


def hero(stats: dict[str, ArmStats], model: str, n_questions: int) -> str:
    base = stats.get("none")
    best = "brieflet" if "brieflet" in stats else next(iter(stats), None)
    if not stats:
        return '<p class="lede">No benchmark runs yet. Run <code>python -m bench run</code>, then refresh this page.</p>'
    if not (best and base and base.tokens):
        return ""
    s = stats[best]
    d_tok = (s.tokens / base.tokens - 1) * 100
    d_sec = (s.secs / base.secs - 1) * 100 if base.secs else 0
    tiles = [(f"{d_tok:+.0f}%", "input tokens vs no docs"), (f"{d_sec:+.0f}%", "answer time vs no docs")]
    if s.quality is not None and base.quality is not None:
        tiles.append((f"{s.quality:.2f} vs {base.quality:.2f}", "answer quality (0–3)"))
    html = '<div class="tiles">' + "".join(f'<div class="tile"><div class="big">{esc(a)}</div><div class="sub">{esc(b)}</div></div>'
                                           for a, b in tiles) + "</div>"
    return (f'<p class="lede">With <strong>{esc(lab(best))}</strong> docs, {esc(model)} answered the same {n_questions} questions '
            f'(the ones every setup finished):</p>' + html)


def _vs(stats: dict[str, ArmStats], arm: str, s: ArmStats) -> str:
    base = stats["none"].tokens if "none" in stats else None
    return f" ({(s.tokens / base - 1) * 100:+.0f}%)" if base and arm != "none" else ""


def bars(stats: dict[str, ArmStats]) -> str:
    """One series: input tokens per setup; Brieflet setups in the accent colour."""
    if not stats:
        return ""
    mx = max(s.tokens for s in stats.values()) or 1
    rows = []
    for arm, s in stats.items():
        vs = _vs(stats, arm, s)
        cls = "bar acc" if arm.startswith("brieflet") else "bar"
        tip = f"{lab(arm)}: {s.tokens:,.0f} input tokens{vs}, {s.secs:.0f} s, ${s.usd:.3f} at API price"
        rows.append(f'<div class="brow"><div class="blab">{esc(lab(arm))}</div><div class="btrack">'
                    f'<div class="{cls}" style="width:{s.tokens / mx * 100:.1f}%" title="{esc(tip)}" tabindex="0"></div></div>'
                    f'<div class="bval">{s.tokens / 1000:,.0f}k{esc(vs)}</div></div>')
    return ('<h3>Input tokens, sum over all questions (median per question)</h3><div class="bars" role="img" '
            'aria-label="Input tokens per setup">' + "".join(rows) + "</div>")


def table(stats: dict[str, ArmStats]) -> str:
    if not stats:
        return ""
    tr = []
    for arm, s in stats.items():
        q = f"{s.quality:.2f}" if s.quality is not None else "–"
        pg = f"{s.per_good:,.0f}" if s.per_good else "–"
        tr.append(f"<tr><td><strong>{esc(lab(arm))}</strong><div class='muted'>{esc(ARM_TEXT.get(arm, ''))}</div></td>"
                  f"<td class='n'>{s.tokens:,.0f}</td><td class='n'>{s.secs:.0f}</td><td class='n'>${s.usd:.3f}</td>"
                  f"<td class='n'>{q}</td><td class='n'>{s.good}/{s.n_scored}</td><td class='n'>{pg}</td></tr>")
    return ('<div class="tw"><table><thead><tr><th>Setup</th><th>Input tokens</th><th>Seconds</th><th>Cost at API price</th>'
            '<th>Quality 0–3</th><th>Good answers</th><th>Tokens per good answer</th></tr></thead><tbody>' + "".join(tr) +
            "</tbody></table></div>")


def per_question(stats: dict[str, ArmStats], qs: list[str], qtext: dict[str, str]) -> str:
    if not stats:
        return ""
    head = "".join(f"<th>{esc(lab(a))}</th>" for a in stats)
    body = []
    for q in qs:
        cells = []
        for s in stats.values():
            v, sc = s.per_q.get(q), s.q_score.get(q)
            cells.append(f"<td class='n'>{'–' if v is None else f'{v / 1000:,.0f}k'}"
                         f"{'' if sc is None else f' · <span class=sc>{sc:g}</span>'}</td>")
        body.append(f"<tr><td><strong>{esc(q)}</strong><div class='muted'>{esc(qtext.get(q, ''))}</div></td>{''.join(cells)}</tr>")
    return ('<details><summary>Per question (median input tokens · quality)</summary><div class="tw"><table><thead><tr>'
            f"<th>Question</th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div></details>")
