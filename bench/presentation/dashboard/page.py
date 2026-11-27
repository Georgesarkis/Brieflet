"""The page shell: CSS (light + dark), live-reload script, Mermaid loader. Filled by format(**sections)."""

MARK = ('<svg viewBox="0 0 120 120" width="36" height="36" aria-hidden="true"><rect x="2" y="2" width="116" height="116" '
        'rx="28" fill="#132A4D" stroke="#2A4772" stroke-width="2"/><path d="M37 30h23a11.5 11.5 0 0 1 0 23H37" fill="none" '
        'stroke="#FF6B5B" stroke-width="12" stroke-linejoin="round"/><path d="M37 67h27a12 12 0 0 1 0 24H37" fill="none" '
        'stroke="#5BC8FF" stroke-width="12" stroke-linejoin="round"/><path d="M44 24V97H37a7 7 0 0 1-7-7V31a7 7 0 0 1 7-7z" '
        'fill="#F4F7FB"/><circle cx="94" cy="91" r="6.5" fill="#FFB547"/></svg>')

HEAD = """<!doctype html>
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
.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 4px}}
.chip{{display:flex;gap:10px;align-items:center;text-align:left;font:inherit;color:var(--ink2);background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px 12px;cursor:pointer;min-height:44px}}
.chip[aria-pressed=true]{{border-color:var(--acc);color:var(--ink);box-shadow:inset 0 0 0 1px var(--acc)}}
.chip:focus-visible{{outline:2px solid var(--acc);outline-offset:2px}}.chip b{{font-weight:600;overflow-wrap:anywhere}}
.chip .src{{display:inline-flex;align-items:center;gap:4px;font-size:12px;color:var(--ink3)}}.chip .facts{{font-size:12px;color:var(--ink3)}}
table.fit{{font-size:13px;min-width:0}}.tw table.fit{{min-width:0}}table.fit th,table.fit td{{padding:6px 6px;white-space:normal}}
.more{{font:inherit;font-size:13px;color:var(--acc);background:none;border:1px solid var(--line);border-radius:999px;padding:4px 10px;cursor:pointer;white-space:nowrap;min-height:32px}}
.more:hover,.more:focus-visible{{border-color:var(--acc)}}
.rhead{{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:baseline}}
</style></head>
"""

LIVE = """<script>
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
"""

MERMAID = """<script type="module">
try {{
  const m = await import("https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs");
  m.default.initialize({{startOnLoad:false, theme:"neutral"}});
  await m.default.run({{querySelector:"pre.mermaid"}});
}} catch (e) {{ /* offline: the diagram source stays visible */ }}
</script>
"""

PAGE = HEAD + """<body><main>
<header>{mark}<div><h1>Brieflet benchmark</h1><div class="meta">{repo} @ {sha} · reader {model} · {runs} runs · last run {when}</div></div></header>
{live}
<nav><a href="../index.html">All repos</a><a href="#results">Results</a><a href="#models">Models</a><a href="#docs">Generated docs</a></nav>
<section id="results"><h2>Results</h2>{hero}{bars}{table}{perq}</section>
<section id="models"><h2>Models</h2>{models}</section>
<section id="docs"><h2>Generated docs (Brieflet setup)</h2>{docs}</section>
<footer>Built {built} by <code>python -m bench dashboard</code>. Raw rows: runs.jsonl · judge.jsonl</footer>
</main>
""" + LIVE + MERMAID + "</body></html>\n"
