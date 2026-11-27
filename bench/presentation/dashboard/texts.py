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
        ("Anthropic", "Claude Haiku 5.5 (labels) + Sonnet 5.5 (prose) by default", "≈ $0.12 per eShop-size repo"),
        ("OpenAI", "any chat model you set with --small-model / --write-model", "set the price yourself"),
    ],
    "Readers (answer questions in the benchmark)": [
        ("Claude Code on your login", "sonnet / opus / haiku", "$0 extra, uses your plan's limit"),
        ("Anthropic API", "claude-sonnet-5-5, claude-opus-5-5, claude-haiku-5-5", "pay per token, gated by --yes"),
        ("OpenAI API", "any model + price you add to prices.yaml", "pay per token, gated by --yes"),
    ],
}
