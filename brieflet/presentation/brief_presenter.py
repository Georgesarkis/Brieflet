"""Presenter: a Brief (data from the use case) → {relative path: Markdown text}."""
from __future__ import annotations

from ..application.generate_brief import Brief
from ..domain.learned import FILE as LEARNED
from .views import ai_context_md, claude_md, components_md, decisions_md, learned_md
from .views.footer import with_footer

NO_FOOTER = {claude_md.FILE, LEARNED}  # CLAUDE.md stays a pure pointer; assistants append to LEARNED.md


def present(brief: Brief, footer: bool) -> dict[str, str]:
    files = {components_md.FILE: components_md.render(brief.graph, brief.labels)}
    files[ai_context_md.FILE], cut = ai_context_md.render(brief.graph, brief.labels, brief.context)
    if cut:
        brief.notes.append(f"AI_CONTEXT cut to {ai_context_md.MAX_CHARS} chars")
    for r in brief.decisions:
        files[r.path] = decisions_md.render_record(r)
    if brief.decisions:
        files[decisions_md.INDEX] = decisions_md.render_index(brief.decisions)
    if brief.write_claude_md:
        files[claude_md.FILE] = claude_md.TEXT
    files[LEARNED] = learned_md.render(brief.learned)
    if footer:
        files = {rel: txt if rel in NO_FOOTER else with_footer(txt) for rel, txt in files.items()}
    return files
