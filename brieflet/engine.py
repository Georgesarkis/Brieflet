"""`brieflet init`: write a short AI context for a repo, from code + a small model.

Ported from geolinux's dev_docs worker (bootstrap path), without the phone approval, git push or CI parts.
Output files (relative to --out, default the repo itself):
  AI_CONTEXT.md                      the short map an assistant reads first (prose by the write model, facts from code)
  CLAUDE.md                          2-line pointer so Claude Code reads AI_CONTEXT.md first (only if none exists)
  docs/architecture/components.md    Mermaid diagram + table, from code (model only names the boxes)
  docs/decisions/NNNN-*.md           decision records inferred from code + commits (Status: Inferred)
  DECISIONS.md                       index of the decision records
Today the component parser understands .NET Aspire AppHosts only.
"""
from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

from .components import Tree, clean_label, parse, render
from . import learned
from .llm import LLM, LLMError

COMPONENTS = "docs/architecture/components.md"
ADR_DIR = "docs/decisions"
DECISIONS = "DECISIONS.md"
AI_CONTEXT = "AI_CONTEXT.md"
CLAUDE_MD = "CLAUDE.md"
STATUS_INFERRED = "Inferred — needs human confirm"
SECRET_RE = re.compile(r"(passw|passphrase|api[_-]?key\s*[:=]|token\s*[:=]|secret\s*[:=]|BEGIN [A-Z ]*PRIVATE|"
                       r"sk-ant-|sk-[A-Za-z0-9]{20}|ghp_[A-Za-z0-9]{10})", re.I)
CONTEXT_MAX_CHARS = 7000
MAX_ADRS = 10

CLAUDE_TXT = """# CLAUDE.md

Read **[AI_CONTEXT.md](AI_CONTEXT.md) first**: the components, what each one owns, how they talk and where to look for X.
Only search the code when it does not answer the question.

- Component diagram: [docs/architecture/components.md](docs/architecture/components.md)
- Architecture decisions: [DECISIONS.md](DECISIONS.md) → `docs/decisions/`
- Facts found in the code later: [LEARNED.md](LEARNED.md)
""" + learned.RULE

SYS_LABEL = """You name boxes in a software architecture diagram. For each box give a label of 2-4 plain words saying
what it does for the user or the system (e.g. "Online store UI", "Shopping basket", "Product catalog", "Event bus").
No quotes, no brackets, no product names that are not in the input.
Answer ONLY with JSON: {"labels": {"<id>": "<label>"}}"""

SYS_ADR = """You write an Architecture Decision Record (ADR) for a .NET microservices repo from the evidence given
(commit messages, changed files, code excerpts). Write only what the evidence supports; when you have to
guess the motive, say "probably". Short plain sentences. No markdown headings, no code blocks.
Answer ONLY with JSON: {"title": "<max 10 words, imperative, e.g. Add a wishlist service>",
"context": "<2-4 sentences: the situation and the need>", "decision": "<2-4 sentences: what was decided and how it is built>",
"consequences": "<2-4 sentences: good and bad effects>", "confidence": "low|medium|high"}"""

SYS_CONTEXT = """You write the overview part of AI_CONTEXT.md, a SHORT guide an AI coding assistant reads before it works on
this repo. You get the component table (from code) and the top folders.
Rules: plain sentences, only facts from the input, real folder paths from the input only.
Answer ONLY with JSON: {"overview": "<3-5 sentences: what the system is and its main parts>",
"how_they_talk": ["<one line per communication style, e.g. WebApp calls basket-api over gRPC>"],
"where": [{"topic": "<what a developer looks for, e.g. checkout flow>", "paths": ["src/..."]}]}  (max 12 where entries)"""

# (key, type, what the code shows, regex that finds the evidence). .NET-specific for now.
CANDIDATES = [
    ("aspire-orchestration", "infra-config", "the whole system is composed and started by a .NET Aspire AppHost", None),
    ("rabbitmq-event-bus", "communication", "services publish/subscribe integration events over RabbitMQ", r"AddRabbitMQ\(|AddRabbitMqEventBus\("),
    ("grpc", "communication", "some services are called over gRPC", r"MapGrpcService<|AddGrpcClient<"),
    ("postgresql-storage", "storage", "services store data in PostgreSQL", r"AddPostgres\(|AddNpgsqlDbContext<"),
    ("redis", "storage", "data is kept in Redis", r"AddRedis(Client)?\("),
    ("identity-service", "auth", "a separate identity service issues tokens (OpenID Connect) for the apps and APIs",
     r"AddIdentityServer|Duende|AddOpenIdConnect|AddJwtBearer"),
    ("outbox-integration-event-log", "new-pattern", "integration events are saved with the data change (outbox) before publishing",
     r"IntegrationEventLog"),
    ("cqrs-mediatr", "new-pattern", "commands/queries go through MediatR (CQRS)", r"IRequestHandler<|AddMediatR"),
    ("yarp-bff", "communication", "a YARP reverse proxy is a backend-for-frontend", r"AddYarp\("),
    ("webhooks", "communication", "external systems get events through registered webhooks", r"Webhook"),
]


def slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:50] or "decision"


def plain(v, n: int) -> str:
    s = " ".join(l.lstrip("#").strip() for l in str(v or "").splitlines() if not l.strip().startswith("```"))
    return " ".join(s.split())[:n]


class Init:
    def __init__(self, repo: Path, llm: LLM, out: Path | None = None, rev: str = "HEAD", log=print):
        self.repo, self.llm, self.log = Path(repo).resolve(), llm, log
        self.out = Path(out).resolve() if out else self.repo
        self.t = Tree(self.repo, rev)
        self.notes: list[str] = []

    # ---------------------------------------------------------------- plan (no model calls)
    def plan(self) -> dict:
        comp = parse(self.t)
        if not comp["nodes"]:
            raise SystemExit("No .NET Aspire AppHost found: Brieflet's component parser supports Aspire repos only (for now).")
        adrs = self.adr_candidates(comp)
        calls = [("small", len(self._label_prompt(comp)) + len(SYS_LABEL), 400),
                 ("write", len(self._context_prompt(comp, {})) + len(SYS_CONTEXT), 1200)]
        calls += [("write", len(self._adr_prompt(a)) + len(SYS_ADR), 900) for a in adrs]
        return {"comp": comp, "adrs": adrs, "calls": calls}

    def _git(self, *a) -> str:
        r = subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, timeout=120)
        return r.stdout if r.returncode == 0 else ""

    def adr_candidates(self, comp: dict) -> list[dict]:
        code = [f for f in self.t.files if f.endswith((".cs", ".csproj", ".props"))]
        out = []
        for key, typ, reason, pat in CANDIDATES:
            if pat is None:
                ev = [comp["apphost"] + "/" + x for x in ("AppHost.cs", "Program.cs") if self.t.has(comp["apphost"] + "/" + x)]
            else:
                rx = re.compile(pat)
                ev = [f for f in code if rx.search(self.t.read(f) or "")][:6]
            if not ev:
                continue
            commits = []
            for f in ev[:3]:
                h = self._git("log", "--diff-filter=A", "--format=%H %as %s", "--", f).strip().splitlines()
                if h:
                    commits.append(h[-1])
            excerpt = ""
            for f in ev[:3]:
                ls = (self.t.read(f) or "").splitlines()
                hit = [i for i, l in enumerate(ls) if re.search(r"Add\w+|Map\w+|IntegrationEvent|IRequestHandler|Webhook", l)]
                if hit:
                    excerpt += f"--- {f}\n" + "\n".join(ls[max(0, hit[0] - 2): hit[0] + 8]) + "\n"
            out.append({"key": key, "type": typ, "reason": reason, "evidence": ev, "excerpt": excerpt,
                        "commits": list(dict.fromkeys(commits))})
        return out[:MAX_ADRS]

    # ---------------------------------------------------------------- prompts
    @staticmethod
    def _label_prompt(comp: dict) -> str:
        lines = []
        for n in comp["nodes"]:
            talks = [e["b"] + (f" ({e['label']})" if e["label"] else "") for e in comp["edges"] if e["a"] == n["id"]]
            lines.append(f"- id {n['id']}: name {n['name']}, kind {n['kind']}" + (f", folder {n['path']}" if n.get("path") else "")
                         + (f", tech {n['tech']}" if n.get("tech") else "")
                         + (f", packages {', '.join(n.get('packages', [])[:8])}" if n.get("packages") else "")
                         + (f", talks to {', '.join(talks)}" if talks else ""))
        return "BOXES:\n" + "\n".join(lines)

    def _rows(self, comp: dict, labels: dict) -> list[str]:
        names = {n["id"]: n["name"] for n in comp["nodes"]}
        rows = []
        for n in comp["nodes"]:
            talks = ", ".join(f"{names[e['b']]} ({e['label']})" if e["label"] else names[e["b"]]
                              for e in comp["edges"] if e["a"] == n["id"])
            rows.append(f"| {n['name']} | {labels.get(n['id'], n['kind'])} | " +
                        (f"`{n['path']}`" if n.get("path") else n.get("tech", "")) + f" | {talks or '—'} |")
        return rows

    def _context_prompt(self, comp: dict, labels: dict) -> str:
        tops = sorted({"/".join(f.split("/")[:2]) for f in self.t.files if f.startswith(("src/", "tests/")) and f.count("/") >= 2})
        return ("COMPONENT TABLE (from code):\n| Box | What it is | Where | Talks to |\n" + "\n".join(self._rows(comp, labels)) +
                "\n\nTOP FOLDERS:\n" + "\n".join(tops[:60]))

    @staticmethod
    def _adr_prompt(a: dict) -> str:
        ctext = "\n".join(f"- {c}" for c in a["commits"]) or "(no commit history available)"
        return (f"WHAT THE CODE SHOWS: {a['type']}: {a['reason']}\n\nCOMMITS THAT ADDED THE EVIDENCE:\n{ctext}\n\n"
                "EVIDENCE FILES:\n" + "\n".join(a["evidence"]) + f"\n\nCODE EXCERPT:\n{a['excerpt'][:5000]}")

    # ---------------------------------------------------------------- model steps
    def ask(self, role, system, prompt, max_out):
        try:
            return self.llm.ask_json(role, system, prompt, max_out)[0]
        except LLMError as e:
            self.notes.append(f"model call failed ({role}): {e}")
            return None

    def labels(self, comp: dict) -> dict:
        d = self.ask("small", SYS_LABEL, self._label_prompt(comp), 400)
        got = d.get("labels") if isinstance(d, dict) else None
        return {n["id"]: (clean_label((got or {}).get(n["id"])) if isinstance(got, dict) else "") or n["kind"]
                for n in comp["nodes"]}

    def ai_context(self, comp: dict, labels: dict) -> str:
        d = self.ask("write", SYS_CONTEXT, self._context_prompt(comp, labels), 1200)
        d = d if isinstance(d, dict) else {}
        where = []
        for w in (d.get("where") or [])[:12]:
            if not isinstance(w, dict):
                continue
            paths = [p.strip("`/ ") for p in (w.get("paths") or []) if isinstance(p, str)]
            good = [p for p in paths if self.t.has(p) or self.t.has_dir(p)]
            if paths and not good:
                self.notes.append(f"AI_CONTEXT 'where' entry dropped (path not in repo): {plain(w.get('topic'), 40)}")
                continue
            if good:
                where.append(f"- **{plain(w.get('topic'), 60)}** → " + ", ".join(f"`{p}`" for p in good[:4]))
        talk = [f"- {plain(x, 200)}" for x in (d.get("how_they_talk") or []) if isinstance(x, str)][:8]
        overview = plain(d.get("overview"), 900) or "(overview not generated: the model gave no answer)"
        txt = "\n".join([
            "# AI context", "",
            "Short, current map of this repo for AI assistants and new developers, written by Brieflet. "
            "Component table, diagram and paths come from the code; the prose is a model's.", "",
            "## Overview", "", overview, "",
            "## Components", "", "| Box | What it is | Where | Talks to |", "|---|---|---|---|", *self._rows(comp, labels), "",
            f"Diagram: [{COMPONENTS}]({COMPONENTS}).", "",
            "## How they talk", "", *(talk or ["- see the arrows in the diagram"]), "",
            "## Where to look for X", "", *(where or ["- (no verified entries)"]), "",
            "## More", "", f"- Architecture decisions: [{DECISIONS}]({DECISIONS})",
            f"- Facts found in the code later: [{learned.FILE}]({learned.FILE})", ""])
        if len(txt) > CONTEXT_MAX_CHARS:
            self.notes.append(f"AI_CONTEXT cut to {CONTEXT_MAX_CHARS} chars")
            txt = txt[:CONTEXT_MAX_CHARS].rsplit("\n", 1)[0] + "\n"
        return txt

    def adrs(self, cands: list[dict]) -> list[dict]:
        out = []
        for i, a in enumerate(cands, 1):
            d = self.ask("write", SYS_ADR, self._adr_prompt(a), 900)
            if not isinstance(d, dict) or not str(d.get("title") or "").strip():
                self.notes.append(f"decision record for {a['key']} not written (bad model answer)")
                continue
            f = {k: plain(d.get(k), 900) for k in ("context", "decision", "consequences")}
            title = plain(d.get("title"), 90).rstrip(".")
            if any(SECRET_RE.search(v) for v in (*f.values(), title)):
                self.notes.append(f"decision record for {a['key']} dropped: secret-looking text")
                continue
            conf = d.get("confidence") if d.get("confidence") in ("low", "medium", "high") else "low"
            num = f"{len(out) + 1:04d}"
            ev = [f"- `{c.split(' ', 1)[0][:7]}` {c.split(' ', 1)[1] if ' ' in c else ''}".rstrip() for c in a["commits"]]
            ev += [f"- `{p}`" for p in a["evidence"][:12]]
            text = "\n".join([f"# {num}. {title}", "", f"- **Status:** {STATUS_INFERRED}",
                              f"- **Date:** {date.today().isoformat()}", f"- **Type:** {a['type']}", f"- **Confidence:** {conf}",
                              "", "## Context", "", f["context"], "", "## Decision", "", f["decision"], "",
                              "## Consequences", "", f["consequences"], "", "## Evidence", "",
                              "Inferred by a model from these commits and files:", "", *ev, "",
                              f"<!-- brieflet key: {a['key']} -->", ""])
            out.append({"num": num, "title": title, "path": f"{ADR_DIR}/{num}-{slug(title)}.md", "text": text})
        return out

    @staticmethod
    def decisions_md(adrs: list[dict]) -> str:
        rows = [f"| [{a['num']}]({a['path']}) | {a['title']} | {STATUS_INFERRED} |" for a in adrs]
        return "\n".join(["# Architecture decisions", "",
                          "One row per decision record in `docs/decisions/`. Status *Inferred* = written by a model "
                          "from the code and commits; a human changes it to *Accepted* (or fixes it).", "",
                          "| # | Decision | Status |", "|---|---|---|", *rows, ""])

    # ---------------------------------------------------------------- run
    def run(self, plan: dict) -> dict:
        comp = plan["comp"]
        self.log(f"labels ({self.llm.small}) …")
        labels = self.labels(comp)
        files = {COMPONENTS: render(comp, labels)}
        self.log(f"AI_CONTEXT ({self.llm.write}) …")
        files[AI_CONTEXT] = self.ai_context(comp, labels)
        self.log(f"{len(plan['adrs'])} decision records ({self.llm.write}) …")
        adrs = self.adrs(plan["adrs"])
        for a in adrs:
            files[a["path"]] = a["text"]
        if adrs:
            files[DECISIONS] = self.decisions_md(adrs)
        if not (self.repo / CLAUDE_MD).exists() or self.out != self.repo:
            files[CLAUDE_MD] = CLAUDE_TXT
        # LEARNED.md: keep what assistants added, drop lines whose files are gone
        old = self.repo / learned.FILE
        kept, dropped = learned.clean(learned.parse_lines(old.read_text(encoding="utf-8")) if old.exists() else [], self.repo)
        files[learned.FILE] = learned.render(kept)
        self.notes += [f"LEARNED.md dropped: {d}" for d in dropped]
        for rel, txt in files.items():
            p = self.out / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(txt, encoding="utf-8")
        return {"files": sorted(files), "notes": self.notes, "calls": self.llm.calls}
