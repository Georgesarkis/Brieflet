"""index.html: one button per tested repo (full name, open/closed source, size, language). Pick one or several:
the page shows the combined result per setup, one short row per repo, and each repo's details folded below.
The full page per repo (models, generated docs) is one click away."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .markdown_html import esc
from .page import HEAD, LIVE, MARK
from .repo_info import RepoInfo
from .texts import lab

OPEN = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><rect x="2.5" y="7" width="11" height="7.5" rx="1.5" '
        'fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M5 7V4.8a3 3 0 0 1 5.8-1" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round"/></svg>')
CLOSED = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><rect x="2.5" y="7" width="11" height="7.5" rx="1.5" '
          'fill="currentColor"/><path d="M5 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>')


@dataclass
class Repo:
    info: RepoInfo
    body: str          # results html (hero, bars, table, per question)
    page: str          # relative link to this repo's full dashboard
    model: str
    runs: int
    when: str
    stats: dict = field(default_factory=dict)   # arm → {tokens, usd, secs, quality, good, scored}


def source_badge(r: RepoInfo) -> str:
    txt = "Open source" + (f" · {r.license}" if r.license else "") if r.open_source else "Closed source"
    return f'<span class="src">{OPEN if r.open_source else CLOSED}{esc(txt)}</span>'


def facts(r: RepoInfo) -> str:
    return " · ".join(x for x in (r.language, r.size) if x)


def chip(i: int, r: RepoInfo) -> str:
    return (f'<button type="button" class="chip" aria-pressed="true" data-i="{i}"><span>'
            f'<b>{esc(r.name)}</b><br>{source_badge(r)}<br><span class="facts">{esc(facts(r))}</span></span></button>')


def section(i: int, rp: Repo) -> str:
    r = rp.info
    return (f'<section class="repo" data-i="{i}" id="repo-{esc(r.key)}"><div class="rhead"><h2>{esc(r.name)}'
            f'{(" <span class=muted>@ " + esc(r.sha) + "</span>") if r.sha else ""}</h2>'
            f'<a class="lnk" href="{esc(rp.page)}">Full page: models + generated docs →</a></div>'
            f'<p class="muted">{source_badge(r)} · {esc(facts(r))} · reader {esc(rp.model)} · {rp.runs} runs'
            f' · last run {esc(rp.when.replace("T", " "))}</p>{rp.body}</section>')


def arms_of(repos: list[Repo]) -> list[str]:
    out: list[str] = []
    for rp in repos:
        out += [a for a in rp.stats if a not in out]
    return out


def _pct(a: float | None, b: float | None) -> str:
    return f"{(a / b - 1) * 100:+.0f}%" if a and b else "–"


def cell(rp: Repo, arm: str) -> str:
    st = rp.stats.get(arm)
    if not st:
        return "<td class='n muted'>–</td>"
    base = rp.stats.get("none", {}).get("tokens")
    tok = f"{st['tokens'] / 1000:,.0f}k" if arm == "none" or not base else _pct(st["tokens"], base)
    q = f" · <span class=sc>{st['quality']:.2f}</span>" if st.get("quality") is not None else ""
    return f"<td class='n'>{tok}{q}</td>"


def per_repo(repos: list[Repo], arms: list[str]) -> str:
    head = "".join(f"<th>{esc(lab(a))}</th>" for a in arms)
    rows = "".join(f'<tr data-i="{i}"><td><strong>{esc(rp.info.name)}</strong>'
                   f'<div class="muted">{esc(facts(rp.info))}</div></td>{"".join(cell(rp, a) for a in arms)}'
                   f'<td><button type="button" class="more" data-only="{i}">View more →</button></td></tr>'
                   for i, rp in enumerate(repos))
    return ('<h3>Per repo</h3><p class="muted">Input tokens vs no docs · quality 0–3. No docs shows its own token count.</p>'
            f'<div class="tw"><table class="fit"><thead><tr><th>Repo</th>{head}<th></th></tr></thead><tbody>{rows}</tbody></table></div>')


def combined_shell() -> str:
    return ('<h2 id="combined-title">Combined</h2><p class="muted">Tokens and cost summed over the picked repos, vs no docs'
            ' on the same repos. Quality = average. Good = scored 2–3. Wins = repos where it used fewer tokens than no docs.</p>'
            '<div class="tw"><table class="fit"><thead><tr><th>Setup</th><th>Tokens</th><th>Cost</th><th>Quality</th><th>Good</th>'
            '<th>Tokens / good</th><th>Wins</th></tr></thead><tbody id="combined"></tbody></table></div>')


SCRIPT = """<script>
// Repo buttons: pick one or several. Choice kept in the URL (#repos=0,2) and this browser.
(() => {
  const chips = [...document.querySelectorAll(".chip[data-i]")], all = document.getElementById("all");
  const secs = [...document.querySelectorAll("section.repo")], over = document.getElementById("overview"), K = "bl-repos";
  const data = JSON.parse(document.getElementById("data").textContent);
  const rows = [...document.querySelectorAll("tr[data-i]")];
  const pct = (a, b) => (a && b) ? ((a / b - 1) * 100).toFixed(0).replace(/^(?!-)/, "+") + "%" : "–";
  const combine = on => {
    const pick = data.repos.filter((r, i) => on.has(String(i)));
    document.getElementById("combined-title").textContent =
      `Combined: ${pick.length} repo${pick.length === 1 ? "" : "s"}`;
    document.getElementById("combined").innerHTML = data.arms.map(a => {
      const have = pick.filter(r => r.stats[a]);
      if (!have.length) return "";
      const both = have.filter(r => r.stats.none);
      const sum = (rs, arm, k) => rs.reduce((t, r) => t + (r.stats[arm][k] || 0), 0);
      const qs = have.map(r => r.stats[a].quality).filter(q => q !== null && q !== undefined);
      const good = sum(have, a, "good"), scored = sum(have, a, "scored"), tok = sum(have, a, "tokens");
      const wins = both.filter(r => r.stats[a].tokens < r.stats.none.tokens).length;
      const vs = a === "none" ? Math.round(tok / 1000).toLocaleString() + "k" : pct(sum(both, a, "tokens"), sum(both, "none", "tokens"));
      const usd = a === "none" ? "$" + sum(have, a, "usd").toFixed(2) : pct(sum(both, a, "usd"), sum(both, "none", "usd"));
      const q = qs.length ? (qs.reduce((x, y) => x + y, 0) / qs.length).toFixed(2) : "–";
      const pg = good ? Math.round(tok / good / 1000).toLocaleString() + "k" : "–";
      return `<tr><td><strong>${data.labels[a] || a}</strong></td><td class="n">${vs}</td>` +
        `<td class="n">${usd}</td><td class="n">${q}</td><td class="n">${good}/${scored}</td><td class="n">${pg}</td>` +
        `<td class="n">${a === "none" ? "–" : wins + "/" + both.length}</td></tr>`;
    }).join("");
  };
  const show = on => {
    combine(on);
    rows.forEach(r => r.hidden = !on.has(r.dataset.i));
    chips.forEach(c => c.setAttribute("aria-pressed", on.has(c.dataset.i)));
    const one = on.size === 1;               // one repo = its full view; two or more = the summary
    over.hidden = one;
    secs.forEach(s => s.hidden = !(one && on.has(s.dataset.i)));
    all.setAttribute("aria-pressed", on.size === chips.length);
    const v = [...on].join(","); history.replaceState(null, "", "#repos=" + v);
    try { localStorage.setItem(K, v); } catch (e) {}
  };
  const cur = () => new Set(chips.filter(c => c.getAttribute("aria-pressed") === "true").map(c => c.dataset.i));
  let start = (location.hash.match(/repos=([\\d,]*)/) || [])[1];
  try { if (start === undefined) start = localStorage.getItem(K) ?? undefined; } catch (e) {}
  const ids = new Set(chips.map(c => c.dataset.i));
  const first = start === undefined ? ids : new Set(start.split(",").filter(x => ids.has(x)));
  show(first.size ? first : ids);
  chips.forEach(c => c.addEventListener("click", () => {
    const on = cur(); on.has(c.dataset.i) ? on.delete(c.dataset.i) : on.add(c.dataset.i);
    show(on.size ? on : new Set([c.dataset.i]));   // never zero repos picked
  }));
  document.querySelectorAll(".more").forEach(b => b.addEventListener("click", () => {
    show(new Set([b.dataset.only])); scrollTo(0, 0);
  }));
  all.addEventListener("click", () => show(new Set(chips.map(c => c.dataset.i))));
})();
</script>
"""


def page(repos: list[Repo], built: str) -> str:
    if not repos:
        body = '<section><p class="lede">No benchmark runs yet.</p></section>'
        bar = ""
    else:
        bar = ('<div class="chips" role="group" aria-label="Repos to show">'
               '<button type="button" class="chip" id="all" aria-pressed="true"><b>All repos</b></button>'
               + "".join(chip(i, rp.info) for i, rp in enumerate(repos)) + "</div>")
        arms = arms_of(repos)
        data = {"arms": arms, "labels": {a: lab(a) for a in arms}, "repos": [{"name": rp.info.name, "stats": rp.stats} for rp in repos]}
        body = (f'<section id="overview">{combined_shell()}{per_repo(repos, arms)}</section>'
                + "".join(section(i, rp) for i, rp in enumerate(repos))
                + '<script type="application/json" id="data">' + json.dumps(data).replace("</", "<\\/") + "</script>")
    head = HEAD.replace("{title}", "Brieflet benchmark · all repos").replace("{{", "{").replace("}}", "}")
    live = LIVE.replace("{{", "{").replace("}}", "}")
    n = len(repos)
    return (head + f'<body><main><header>{MARK}<div><h1>Brieflet benchmark</h1><div class="meta">{n} repo{"s" if n != 1 else ""}'
            f' tested · pick one or several</div></div></header>{bar}{body}'
            f'<footer>Built {esc(built)} by <code>python -m bench dashboard</code>.</footer></main>'
            + live + (SCRIPT if repos else "") + "</body></html>\n")
