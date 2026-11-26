"""One self-contained HTML page: models, generated docs, benchmark results. `python -m bench dashboard -c <cfg>`.

No server, no build. Open the file in a browser (or serve the results folder). Mermaid is the only external script,
for the component diagram; without network the diagram source is shown instead.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import statistics as st
from pathlib import Path

import yaml

MARK = ('<svg viewBox="0 0 120 120" width="36" height="36" aria-hidden="true"><rect x="2" y="2" width="116" height="116" '
        'rx="28" fill="#132A4D" stroke="#2A4772" stroke-width="2"/><path d="M37 30h23a11.5 11.5 0 0 1 0 23H37" fill="none" '
        'stroke="#FF6B5B" stroke-width="12" stroke-linejoin="round"/><path d="M37 67h27a12 12 0 0 1 0 24H37" fill="none" '
        'stroke="#5BC8FF" stroke-width="12" stroke-linejoin="round"/><path d="M44 24V97H37a7 7 0 0 1-7-7V31a7 7 0 0 1 7-7z" '
        'fill="#F4F7FB"/><circle cx="94" cy="91" r="6.5" fill="#FFB547"/></svg>')

ARM_TEXT = {
    "none": "Code only. No docs.",
    "graphify-ast": "Graphify code graph + a pointer to it.",
    "brieflet": "Brieflet docs: AI_CONTEXT, diagram, decisions. No graph.",
    "brieflet-graph": "Brieflet docs + the Graphify graph files together (the 22 Nov setup).",
    "brieflet-learn": "Brieflet + LEARNED.md: facts the AI had to dig out of the code on the OTHER half of the questions.",
}
LABEL = {"none": "No docs", "graphify-ast": "Graphify only", "brieflet": "Brieflet", "brieflet-graph": "Brieflet + Graphify",
         "brieflet-learn": "Brieflet + learning"}
lab = lambda a: LABEL.get(a, a)
SUPPORTED = {
    "Writers (make the docs)": [
        ("Ollama, local", "qwen3.5:9b (labels) + Bonsai 27B (prose) by default; any Ollama model", "$0"),
        ("Anthropic", "Claude Haiku 5.5 (labels) + Sonnet 5.5 (prose) by default", "≈ $0.12 per eShop-size repo"),
        ("OpenAI", "any chat model you set with --small-model / --write-model", "set the price yourself"),
    ],
    "Readers (answer questions in the benchmark)": [
        ("Claude Code on your login", "sonnet / opus / haiku", "$0 extra, uses your plan's limit"),
        ("Anthropic API", "claude-sonnet-5-5, claude-opus-5-5, claude-haiku-5-5", "pay per token, gated by --yes"),
        ("OpenAI API", "any model + price you add to prices.yaml", "pay per token, gated by --yes"),
    ],
}


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


def build(cfg: dict, rows: list[dict], verdicts: dict, row_key, expand, status: str = "", learned_dir=None) -> str:
    repo = next(iter(cfg["repos"]))
    rc = cfg["repos"][repo]
    arms = list(cfg["arms"])
    meta = {}
    art = expand(cfg, str(cfg.get("artifacts", "artifacts")) + "/" + repo)
    if (art / "meta.yaml").exists():
        meta = yaml.safe_load(open(art / "meta.yaml")) or {}

    ok = [r for r in rows if not r.get("error") and r["repo"] == repo]
    models = sorted({r["model"] for r in ok}) or [m["name"] for m in cfg["models"]]
    model = models[0]
    med = lambda xs: st.median(xs) if xs else None
    tin = lambda r: r["input_tokens"] + r["cache_read"] + r["cache_write"]

    stats = {}
    have = [{r["q"] for r in ok if r["arm"] == a and r["model"] == model} for a in arms]
    have = [h for h in have if h]
    qs = sorted(set.intersection(*have) if have else set(), key=lambda q: int(re.sub(r"\D", "", q) or 0))
    for arm in arms:
        g = [r for r in ok if r["arm"] == arm and r["model"] == model]
        if not g:
            continue
        per_q = {q: med([tin(r) for r in g if r["q"] == q]) for q in qs}
        sc = [verdicts[row_key(r)]["score"] for r in g if row_key(r) in verdicts and verdicts[row_key(r)].get("score") is not None]
        good = sum(1 for s in sc if s >= 2)
        judged_tokens = sum(tin(r) for r in g if row_key(r) in verdicts)
        stats[arm] = {
            "tokens": sum(v for v in per_q.values() if v is not None),
            "secs": sum(med([r["secs"] for r in g if r["q"] == q]) or 0 for q in qs),
            "usd": sum(med([r.get("cost_usd") or 0 for r in g if r["q"] == q]) or 0 for q in qs),
            "per_q": per_q,
            "q_score": {q: med([verdicts[row_key(r)]["score"] for r in g if r["q"] == q and row_key(r) in verdicts
                                and verdicts[row_key(r)].get("score") is not None]) for q in qs},
            "quality": st.mean(sc) if sc else None, "n_scored": len(sc), "good": good,
            "per_good": judged_tokens / good if good else None, "runs": len(g),
        }
    base = stats.get("none", {}).get("tokens")

    # ---------- hero
    hero = ""
    best = "brieflet" if "brieflet" in stats else next(iter(stats), None)
    if best and base:
        s = stats[best]
        d_tok = (s["tokens"] / base - 1) * 100
        d_sec = (s["secs"] / stats["none"]["secs"] - 1) * 100 if stats["none"]["secs"] else 0
        tiles = [(f"{d_tok:+.0f}%", "input tokens vs no docs"), (f"{d_sec:+.0f}%", "answer time vs no docs")]
        if s["quality"] is not None and stats["none"].get("quality") is not None:
            tiles.append((f"{s['quality']:.2f} vs {stats['none']['quality']:.2f}", "answer quality (0–3)"))
        hero = '<div class="tiles">' + "".join(f'<div class="tile"><div class="big">{esc(a)}</div><div class="sub">{esc(b)}</div></div>'
                                               for a, b in tiles) + "</div>"
        hero = (f'<p class="lede">With <strong>{esc(lab(best))}</strong> docs, {esc(model)} answered the same {len(qs)} questions '
                f'(the ones every setup finished):</p>' + hero)
    elif not stats:
        hero = '<p class="lede">No benchmark runs yet. Run <code>python -m bench run</code>, then refresh this page.</p>'

    # ---------- bars (one series: input tokens per arm; brieflet arms in accent)
    bars = ""
    if stats:
        mx = max(s["tokens"] for s in stats.values()) or 1
        rows_html = []
        for arm, s in stats.items():
            w = s["tokens"] / mx * 100
            vs = f" ({(s['tokens'] / base - 1) * 100:+.0f}%)" if base and arm != "none" else ""
            cls = "bar acc" if arm.startswith("brieflet") else "bar"
            tip = f"{lab(arm)}: {s['tokens']:,.0f} input tokens{vs}, {s['secs']:.0f} s, ${s['usd']:.3f} at API price"
            rows_html.append(f'<div class="brow"><div class="blab">{esc(lab(arm))}</div><div class="btrack">'
                             f'<div class="{cls}" style="width:{w:.1f}%" title="{esc(tip)}" tabindex="0"></div></div>'
                             f'<div class="bval">{s["tokens"] / 1000:,.0f}k{esc(vs)}</div></div>')
        bars = ('<h3>Input tokens, sum over all questions (median per question)</h3><div class="bars" role="img" '
                'aria-label="Input tokens per setup">' + "".join(rows_html) + "</div>")

    # ---------- results table
    table = ""
    if stats:
        tr = []
        for arm, s in stats.items():
            q = f"{s['quality']:.2f}" if s["quality"] is not None else "–"
            pg = f"{s['per_good']:,.0f}" if s["per_good"] else "–"
            tr.append(f"<tr><td><strong>{esc(lab(arm))}</strong><div class='muted'>{esc(ARM_TEXT.get(arm, ''))}</div></td>"
                      f"<td class='n'>{s['tokens']:,.0f}</td><td class='n'>{s['secs']:.0f}</td><td class='n'>${s['usd']:.3f}</td>"
                      f"<td class='n'>{q}</td><td class='n'>{s['good']}/{s['n_scored']}</td><td class='n'>{pg}</td></tr>")
        table = ('<div class="tw"><table><thead><tr><th>Setup</th><th>Input tokens</th><th>Seconds</th><th>Cost at API price</th>'
                 '<th>Quality 0–3</th><th>Good answers</th><th>Tokens per good answer</th></tr></thead><tbody>' + "".join(tr) +
                 "</tbody></table></div>")

    # ---------- per question
    perq = ""
    if stats:
        qtext = {q["id"]: q["text"] for q in yaml.safe_load(open(expand(cfg, rc["questions"])))["questions"]}
        head = "".join(f"<th>{esc(lab(a))}</th>" for a in stats)
        body = []
        for q in qs:
            cells = []
            for a, s in stats.items():
                v, sc = s["per_q"].get(q), s["q_score"].get(q)
                cells.append(f"<td class='n'>{'–' if v is None else f'{v / 1000:,.0f}k'}"
                             f"{'' if sc is None else f' · <span class=sc>{sc:g}</span>'}</td>")
            body.append(f"<tr><td><strong>{esc(q)}</strong><div class='muted'>{esc(qtext.get(q, ''))}</div></td>{''.join(cells)}</tr>")
        perq = ('<details><summary>Per question (median input tokens · quality)</summary><div class="tw"><table><thead><tr>'
                f"<th>Question</th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div></details>")

    # ---------- models
    writers = "".join(f"<tr><td>{esc(w.get('role'))}</td><td><code>{esc(w.get('model'))}</code></td><td>{esc(w.get('runtime'))}</td></tr>"
                      for w in meta.get("writers", []))
    readers = "".join(f"<tr><td>{esc(m['name'])}</td><td><code>{esc(m['model'])}</code></td><td>{esc(m['runner'])}"
                      f"{' (' + esc(m.get('billing', 'subscription')) + ')' if m['runner'] == 'claude_code' else ''}</td></tr>"
                      for m in cfg["models"])
    judge = cfg.get("judge") or {}
    supported = "".join(f"<h4>{esc(k)}</h4><div class='tw'><table><tbody>" +
                        "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td class='muted'>{esc(c)}</td></tr>" for a, b, c in v) +
                        "</tbody></table></div>" for k, v in SUPPORTED.items())
    models_html = (
        "<h3>Used in this run</h3>"
        f"<h4>Writers{(' · ' + esc(meta.get('generated'))) if meta.get('generated') else ''}"
        f"{(' · ' + esc(meta.get('hardware'))) if meta.get('hardware') else ''}</h4>"
        f"<div class='tw'><table><thead><tr><th>Job</th><th>Model</th><th>Runs on</th></tr></thead><tbody>{writers or '<tr><td colspan=3>unknown</td></tr>'}</tbody></table></div>"
        f"<h4>Readers</h4><div class='tw'><table><thead><tr><th>Name</th><th>Model</th><th>How</th></tr></thead><tbody>{readers}</tbody></table></div>"
        + (f"<h4>Judge</h4><p><code>{esc(judge.get('model'))}</code> via {esc(judge.get('runner'))}: grades each answer 0–3 against "
           "reference points, without knowing the setup.</p>" if judge else "")
        + "<h3>Supported</h3>" + supported)

    # ---------- generated docs
    docs = []
    for arm in arms:
        a = cfg["arms"][arm] or {}
        for ov in a.get("overlay", []):
            d = expand(cfg, ov, repo)
            if not d.is_dir() or arm != "brieflet":
                continue
            files = sorted([p for p in d.rglob("*.md")], key=lambda p: (p.name != "AI_CONTEXT.md", p.name != "CLAUDE.md",
                                                                         "decisions" in str(p), str(p)))
            for p in files:
                rel = p.relative_to(d).as_posix()
                txt = p.read_text(encoding="utf-8", errors="replace")
                docs.append(f"<details{' open' if rel == 'AI_CONTEXT.md' else ''}><summary><code>{esc(rel)}</code>"
                            f"<span class='muted'> · {len(txt):,} chars ≈ {len(txt) // 4:,} tokens</span></summary>"
                            f"<div class='doc'>{md(txt)}</div></details>")
    if (g := expand(cfg, str(cfg.get("artifacts", "artifacts")) + f"/{repo}/graphify-ast/docs/architecture/GRAPH_REPORT.md")).exists():
        n = len(g.read_text(errors="replace"))
        docs.append(f"<p class='muted'>For comparison: Graphify's <code>GRAPH_REPORT.md</code> is {n:,} chars ≈ {n // 4:,} tokens "
                    f"({n / max(1, len((art / 'brieflet' / 'AI_CONTEXT.md').read_text()) if (art / 'brieflet' / 'AI_CONTEXT.md').exists() else 1):.0f}× AI_CONTEXT.md).</p>")

    # ---------- learned facts (learning arm)
    if learned_dir and Path(learned_dir).is_dir():
        for f in sorted(Path(learned_dir).rglob("fold*.md")):
            txt = f.read_text(encoding="utf-8", errors="replace")
            n = sum(1 for l in txt.splitlines() if l.startswith("- "))
            docs.append(f"<details><summary><strong>Learned · {esc(f.parent.name)} · {esc(f.stem)}</strong>"
                        f"<span class='muted'> · {n} facts</span></summary><div class='doc'>{md(txt)}</div></details>")

    when = max((r["t"] for r in ok), default="")
    sha = str(rc.get("sha") or "")[:7]
    return PAGE.format(
        title=f"Brieflet benchmark · {esc(meta.get('repo', repo))}",
        mark=MARK, repo=esc(meta.get("repo", repo)), sha=esc(sha), when=esc(when.replace("T", " ")),
        runs=sum(s["runs"] for s in stats.values()), model=esc(model), hero=hero, bars=bars, table=table, perq=perq,
        models=models_html, docs="".join(docs) or "<p class='muted'>No generated docs found.</p>",
        built=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        live=(f"<div class='live' role='status'><span class='dot'></span>{esc(status)}</div>" if status else ""))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#F4F7FB;--panel:#FFFFFF;--line:#D9E2EE;--ink:#0B1B33;--ink2:#40536F;--ink3:#6B7C95;--acc:#1F9EE0;--bar:#A9B8CC;--coral:#E0533F}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#0B1B33;--panel:#11284A;--line:#22406A;--ink:#F4F7FB;--ink2:#B8C7DC;--ink3:#8597B2;--acc:#5BC8FF;--bar:#4A6185;--coral:#FF6B5B}}}}
:root[data-theme=dark]{{--bg:#0B1B33;--panel:#11284A;--line:#22406A;--ink:#F4F7FB;--ink2:#B8C7DC;--ink3:#8597B2;--acc:#5BC8FF;--bar:#4A6185;--coral:#FF6B5B}}
*{{box-sizing:border-box}}html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:20px 16px 64px}}
header{{display:flex;gap:12px;align-items:center;margin-bottom:8px}}
header h1{{font-size:22px;margin:0;letter-spacing:-.01em}}header .meta{{color:var(--ink3);font-size:14px}}
nav{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 20px}}
nav a{{color:var(--ink2);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:14px;background:var(--panel)}}
nav a:focus-visible,nav a:hover{{border-color:var(--acc);color:var(--ink)}}
section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;margin:0 0 16px}}
h2{{font-size:18px;margin:0 0 12px}}h3{{font-size:15px;margin:18px 0 8px;color:var(--ink2)}}h4{{font-size:14px;margin:14px 0 6px;color:var(--ink2)}}
.lede{{margin:0 0 12px;color:var(--ink2)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}}
.tile{{border:1px solid var(--line);border-radius:12px;padding:14px}}
.big{{font-size:30px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em}}.sub{{color:var(--ink3);font-size:14px}}
.bars{{display:grid;gap:8px}}.brow{{display:grid;grid-template-columns:120px 1fr auto;gap:10px;align-items:center}}
.blab{{font-size:14px;color:var(--ink2);overflow-wrap:anywhere}}.btrack{{height:18px}}
.bar{{height:18px;border-radius:0 4px 4px 0;background:var(--bar);min-width:2px}}.bar.acc{{background:var(--acc)}}
.bar:focus-visible{{outline:2px solid var(--acc);outline-offset:2px}}
.bval{{font-size:14px;font-variant-numeric:tabular-nums;color:var(--ink)}}
.tw{{overflow-x:auto;margin:6px 0}}.tw table{{min-width:560px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--ink3);font-weight:600;white-space:nowrap}}td.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.muted{{color:var(--ink3);font-size:13px}}.sc{{color:var(--ink2)}}
details{{border:1px solid var(--line);border-radius:10px;margin:8px 0;padding:0 12px}}
summary{{cursor:pointer;padding:10px 0;min-height:44px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.doc{{border-top:1px solid var(--line);padding:6px 0 10px;overflow-wrap:anywhere}}.doc h3,.doc h4,.doc h5{{color:var(--ink)}}
code{{font:13px ui-monospace,SFMono-Regular,Menlo,monospace;background:color-mix(in srgb,var(--line) 45%,transparent);padding:1px 5px;border-radius:5px}}
pre{{overflow-x:auto;background:color-mix(in srgb,var(--line) 30%,transparent);padding:10px;border-radius:8px;font-size:12px}}
pre.mermaid{{background:#fff;color:#0B1B33}}
.lnk{{color:var(--acc)}}footer{{color:var(--ink3);font-size:13px;text-align:center}}
.live{{display:inline-flex;gap:8px;align-items:center;border:1px solid var(--acc);border-radius:999px;padding:4px 12px;font-size:14px;margin:4px 0}}
.dot{{width:8px;height:8px;border-radius:50%;background:var(--acc);animation:p 1.4s ease-in-out infinite}}
@keyframes p{{50%{{opacity:.25}}}}@media (prefers-reduced-motion:reduce){{.dot{{animation:none}}}}
@media (max-width:520px){{.brow{{grid-template-columns:92px 1fr auto}}.big{{font-size:26px}}}}
</style></head>
<body><main>
<header>{mark}<div><h1>Brieflet benchmark</h1><div class="meta">{repo} @ {sha} · reader {model} · {runs} runs · last run {when}</div></div></header>
{live}
<nav><a href="#results">Results</a><a href="#models">Models</a><a href="#docs">Generated docs</a></nav>
<section id="results"><h2>Results</h2>{hero}{bars}{table}{perq}</section>
<section id="models"><h2>Models</h2>{models}</section>
<section id="docs"><h2>Generated docs (Brieflet setup)</h2>{docs}</section>
<footer>Built {built} by <code>python -m bench dashboard</code>. Raw rows: runs.jsonl · judge.jsonl</footer>
</main>
<script>
// Live: re-check this page every 15 s, reload only when it changed; keep scroll + open sections.
(() => {{
  const K = "bl-state";
  try {{
    const st = JSON.parse(sessionStorage.getItem(K) || "null");
    if (st) {{
      document.querySelectorAll("details").forEach((d, i) => {{ if (st.open.includes(i)) d.open = true; }});
      addEventListener("load", () => scrollTo(0, st.y));
      sessionStorage.removeItem(K);
    }}
  }} catch (e) {{}}
  let tag = null;
  const sig = r => (r.headers.get("etag") || "") + (r.headers.get("last-modified") || "");
  async function check() {{
    try {{
      const r = await fetch(location.pathname, {{method: "HEAD", cache: "no-store"}});
      const s = sig(r);
      if (tag === null) tag = s;
      else if (s && s !== tag) {{
        try {{
          const open = [...document.querySelectorAll("details")].flatMap((d, i) => d.open ? [i] : []);
          sessionStorage.setItem(K, JSON.stringify({{y: scrollY, open}}));
        }} catch (e) {{}}
        location.reload();
      }}
    }} catch (e) {{}}
  }}
  check(); setInterval(check, 15000);
}})();
</script>
<script type="module">
try {{
  const m = await import("https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs");
  m.default.initialize({{startOnLoad:false, theme:"neutral"}});
  await m.default.run({{querySelector:"pre.mermaid"}});
}} catch (e) {{ /* offline: the diagram source stays visible */ }}
</script>
</body></html>
"""
