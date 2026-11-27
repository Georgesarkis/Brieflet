"""View: AI_CONTEXT.md, the short map an assistant reads first."""
from __future__ import annotations

from ...application.model_answers import ContextDraft
from ...application.prompts import component_table
from ...domain.components import ComponentGraph
from ...domain.learned import FILE as LEARNED
from .components_md import FILE as COMPONENTS
from .decisions_md import INDEX as DECISIONS

FILE = "AI_CONTEXT.md"
MAX_CHARS = 7000


def render(graph: ComponentGraph, labels: dict[str, str], ctx: ContextDraft) -> tuple[str, bool]:
    """→ (markdown, was it cut to MAX_CHARS)."""
    where = [f"- **{topic}** → " + ", ".join(f"`{p}`" for p in paths) for topic, paths in ctx.where]
    talk = [f"- {t}" for t in ctx.how_they_talk]
    txt = "\n".join([
        "# AI context", "",
        "Short, current map of this repo for AI assistants and new developers, written by Brieflet. "
        "Component table, diagram and paths come from the code; the prose is a model's.", "",
        "## Overview", "", ctx.overview or "(overview not generated: the model gave no answer)", "",
        "## Components", "", "| Box | What it is | Where | Talks to |", "|---|---|---|---|",
        *component_table(graph, labels), "",
        f"Diagram: [{COMPONENTS}]({COMPONENTS}).", "",
        "## How they talk", "", *(talk or ["- see the arrows in the diagram"]), "",
        "## Where to look for X", "", *(where or ["- (no verified entries)"]), "",
        "## More", "", f"- Architecture decisions: [{DECISIONS}]({DECISIONS})",
        f"- Facts found in the code later: [{LEARNED}]({LEARNED})", ""])
    if len(txt) <= MAX_CHARS:
        return txt, False
    return txt[:MAX_CHARS].rsplit("\n", 1)[0] + "\n", True
