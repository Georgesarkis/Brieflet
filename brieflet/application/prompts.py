"""What the models are asked. System prompts + the evidence each prompt carries."""
from __future__ import annotations

from ..domain.components import ComponentGraph
from ..domain.decisions import DecisionCandidate

LABEL_SYSTEM = """You name boxes in a software architecture diagram. For each box give a label of 2-4 plain words saying
what it does for the user or the system (e.g. "Online store UI", "Shopping basket", "Product catalog", "Event bus").
No quotes, no brackets, no product names that are not in the input.
Answer ONLY with JSON: {"labels": {"<id>": "<label>"}}"""

DECISION_SYSTEM = """You write an Architecture Decision Record (ADR) for a .NET microservices repo from the evidence given
(commit messages, changed files, code excerpts). Write only what the evidence supports; when you have to
guess the motive, say "probably". Short plain sentences. No markdown headings, no code blocks.
Answer ONLY with JSON: {"title": "<max 10 words, imperative, e.g. Add a wishlist service>",
"context": "<2-4 sentences: the situation and the need>", "decision": "<2-4 sentences: what was decided and how it is built>",
"consequences": "<2-4 sentences: good and bad effects>", "confidence": "low|medium|high"}"""

CONTEXT_SYSTEM = """You write the overview part of AI_CONTEXT.md, a SHORT guide an AI coding assistant reads before it works on
this repo. You get the component table (from code) and the top folders.
Rules: plain sentences, only facts from the input, real folder paths from the input only.
Answer ONLY with JSON: {"overview": "<3-5 sentences: what the system is and its main parts>",
"how_they_talk": ["<one line per communication style, e.g. WebApp calls basket-api over gRPC>"],
"where": [{"topic": "<what a developer looks for, e.g. checkout flow>", "paths": ["src/..."]}]}  (max 12 where entries)"""

# Asked at the end of a question so the assistant reports what the docs were missing (benchmark learning pass).
LEARNED_ASK = ("\n\n(After your answer: if the project docs did not already contain what you needed and you had to search "
               "the code, end with a block that starts with the line LEARNED: followed by up to 3 lines in the form "
               "'- <fact, max 25 words> → `path/to/file`'. If the docs were enough, end with the line LEARNED: none)")

MAX_OUT = {"labels": 400, "context": 1200, "decision": 900}


def component_table(graph: ComponentGraph, labels: dict[str, str]) -> list[str]:
    """Markdown rows | Box | What it is | Where | Talks to |, shared by the prompt and AI_CONTEXT.md."""
    return [f"| {c.name} | {graph.label_for(c, labels)} | " + (f"`{c.path}`" if c.path else c.tech or "")
            + f" | {graph.talks_to(c.id) or '—'} |" for c in graph.components]


def label_prompt(graph: ComponentGraph) -> str:
    lines = []
    for c in graph.components:
        talks = [l.target + (f" ({l.label})" if l.label else "") for l in graph.outgoing(c.id)]
        lines.append(f"- id {c.id}: name {c.name}, kind {c.kind}" + (f", folder {c.path}" if c.path else "")
                     + (f", tech {c.tech}" if c.tech else "")
                     + (f", packages {', '.join(c.packages[:8])}" if c.packages else "")
                     + (f", talks to {', '.join(talks)}" if talks else ""))
    return "BOXES:\n" + "\n".join(lines)


def context_prompt(graph: ComponentGraph, labels: dict[str, str], files: list[str]) -> str:
    tops = sorted({"/".join(f.split("/")[:2]) for f in files if f.startswith(("src/", "tests/")) and f.count("/") >= 2})
    return ("COMPONENT TABLE (from code):\n| Box | What it is | Where | Talks to |\n" + "\n".join(component_table(graph, labels))
            + "\n\nTOP FOLDERS:\n" + "\n".join(tops[:60]))


def decision_prompt(c: DecisionCandidate) -> str:
    commits = "\n".join(f"- {x}" for x in c.commits) or "(no commit history available)"
    return (f"WHAT THE CODE SHOWS: {c.type}: {c.reason}\n\nCOMMITS THAT ADDED THE EVIDENCE:\n{commits}\n\n"
            "EVIDENCE FILES:\n" + "\n".join(c.evidence) + f"\n\nCODE EXCERPT:\n{c.excerpt[:5000]}")
