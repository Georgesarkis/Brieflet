"""Words on the dashboard: setup names, what each setup contains, supported models."""
from __future__ import annotations

ARM_TEXT = {
    "none": "Code only. No docs.",
    "graphify-ast": "Graphify code graph + a pointer to it.",
    "brieflet": "Brieflet docs: AI_CONTEXT, diagram, decisions. No graph.",
    "brieflet-graph": "Brieflet docs + the Graphify graph files together (the 22 Nov setup).",
    "brieflet-learn": "Brieflet + LEARNED.md: facts the AI had to dig out of the code on the OTHER half of the questions.",
    "codegraph": "CodeGraph as installed: local code index, MCP search tool + a hook that adds code to every question.",
}
LABEL = {"none": "No docs", "graphify-ast": "Graphify only", "brieflet": "Brieflet", "brieflet-graph": "Brieflet + Graphify",
         "brieflet-learn": "Brieflet + learning", "codegraph": "CodeGraph"}


def lab(arm: str) -> str:
    return LABEL.get(arm, arm)


SUPPORTED = {
    "Writers (make the docs)": [
        ("Ollama, local", "qwen3.5:9b (labels) + Bonsai 27B (prose) by default; any Ollama model", "$0"),
        ("Plugin backends", "anything registered under brieflet.llm_backends", "estimate first, needs --yes if paid"),
    ],
    "Readers (answer questions in the benchmark)": [
        ("fake", "offline stand-in for tests", "$0"),
        ("Plugin runners", "anything registered under brieflet.bench_runners", "estimate first, needs --yes if paid"),
    ],
}
