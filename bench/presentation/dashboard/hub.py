"""index.html: one button per tested repo (full name, open/closed source, size, language). Pick one or several;
each picked repo shows its results. The full page per repo (models, generated docs) is one click away."""
from __future__ import annotations

from dataclasses import dataclass

from .markdown_html import esc
from .page import HEAD, LIVE, MARK
from .repo_info import RepoInfo

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


SCRIPT = """<script>
// Repo buttons: pick one or several. Choice kept in the URL (#repos=0,2) and this browser.
(() => {
  const chips = [...document.querySelectorAll(".chip[data-i]")], all = document.getElementById("all");
  const secs = [...document.querySelectorAll("section.repo")], K = "bl-repos";
  const show = on => {
    chips.forEach(c => c.setAttribute("aria-pressed", on.has(c.dataset.i)));
    secs.forEach(s => s.hidden = !on.has(s.dataset.i));
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
        body = "".join(section(i, rp) for i, rp in enumerate(repos))
    head = HEAD.replace("{title}", "Brieflet benchmark · all repos").replace("{{", "{").replace("}}", "}")
    live = LIVE.replace("{{", "{").replace("}}", "}")
    n = len(repos)
    return (head + f'<body><main><header>{MARK}<div><h1>Brieflet benchmark</h1><div class="meta">{n} repo{"s" if n != 1 else ""}'
            f' tested · pick one or several</div></div></header>{bar}{body}'
            f'<footer>Built {esc(built)} by <code>python -m bench dashboard</code>.</footer></main>'
            + live + (SCRIPT if repos else "") + "</body></html>\n")
