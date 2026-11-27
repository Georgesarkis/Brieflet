"""Use case: quality 0-3 per answer against reference points (questions/<repo>.refs.yaml).

The judge never sees which arm wrote the answer. It only says, per `must` point, whether the answer gets it right,
and lists wrong claims; the score is computed in domain/scoring.py, the same rule for every arm.
"""
from __future__ import annotations

from ..domain.results import row_key
from ..domain.scoring import parse_verdict, score
from .config import BenchConfig
from .outcome import Outcome
from .ports import JudgeClient, Log, Notifier, Progress, ResultsStore

SYSTEM = """You grade an answer to a question about a code repository, against reference points from the real code.
For each MUST point: true if the answer states it correctly (wording may differ; it must be the same fact), else false.
List claims in the answer that contradict the reference or the code as the reference describes it ("wrong_claims"),
each with severity "major" (would send a developer the wrong way) or "minor". Do not reward length or style.
Answer ONLY with JSON: {"must": [true|false, ...], "wrong_claims": [{"claim": "...", "severity": "major|minor"}]}"""
CHARS_PER_TOKEN = 3.5
OUT_TOKENS_PER_VERDICT = 600
FAILS_TO_STOP = 3


def prompt(question: str, refs: dict, answer: str) -> str:
    must = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(refs["must"]))
    nice = "\n".join(f"- {p}" for p in refs.get("nice", [])) or "(none)"
    return (f"QUESTION:\n{question}\n\nMUST POINTS:\n{must}\n\nNICE-TO-HAVE (do not grade, context only):\n{nice}\n\n"
            f"ANSWER TO GRADE:\n{answer[:12000]}")


class JudgeAnswers:
    def __init__(self, cfg: BenchConfig, store: ResultsStore, client: JudgeClient, notifier: Notifier,
                 progress: Progress, log: Log = print):
        self.cfg, self.store, self.client, self.notifier, self.progress, self.log = cfg, store, client, notifier, progress, log

    def execute(self, yes: bool) -> Outcome:
        jc = self.cfg.judge
        done = {k for k, v in self.store.verdicts().items() if v.get("score") is not None}   # failed ones are retried
        todo = [(r, refs) for r in self.store.runs() if not r.get("error") and row_key(r) not in done
                and (refs := self.cfg.refs.get(r["repo"], {}).get(r["q"]))]
        if not todo:
            self.log("nothing to judge")
            return Outcome.OK
        if not self._money_gate(jc, todo, yes):
            return Outcome.REFUSED
        fails = 0
        for i, (r, refs) in enumerate(todo, 1):
            raw, use = self.client.ask(jc, prompt(r["question"], refs, r.get("answer") or ""))
            v = parse_verdict(raw)
            rec = {"key": row_key(r), "q": r["q"], "arm": r["arm"], "model": r["model"], "repo": r["repo"],
                   "judge": jc.get("model"), "verdict": v, "score": score(len(refs["must"]), v) if v else None, **use}
            self.store.add_verdict(rec)
            self.log(f"{i}/{len(todo)} {r['q']} {r['arm']:14} score={rec['score']}")
            self.progress(f"Judging: {i}/{len(todo)} answers")
            fails = fails + 1 if rec["score"] is None else 0
            if fails >= FAILS_TO_STOP:
                msg = "Brieflet judge stopped: 3 failures in a row (usage limit?). Run judge again later, it continues."
                self.log(msg)
                self.notifier.send(msg)
                return Outcome.ERROR_STOP
        self.notifier.send(f"Brieflet judge done: {len(todo)} answers scored. Dashboard updated.")
        return Outcome.OK

    def _money_gate(self, jc: dict, todo: list, yes: bool) -> bool:
        if jc.get("runner", "claude_code") == "claude_code":
            self.log(f"{len(todo)} answers to judge with Claude Code ({jc.get('model', 'opus')}) on your login: $0 extra.")
            return True
        p = self.cfg.prices["anthropic"].get(jc["model"])
        if not p:
            self.log(f"Refused: no price for judge model {jc['model']}")
            return False
        chars = sum(len(SYSTEM) + len(prompt(r["question"], refs, r.get("answer") or "")) for r, refs in todo)
        est = (chars / CHARS_PER_TOKEN * p["input"] + len(todo) * OUT_TOKENS_PER_VERDICT * p["output"]) / 1e6
        self.log(f"{len(todo)} answers to judge with {jc['model']} via API: estimate ${est:.2f}.")
        if not yes:
            self.log("Refused: paid judge needs --yes.")
        elif est > self.cfg.max_usd:
            self.log(f"Refused: estimate > max_usd ${self.cfg.max_usd}.")
        else:
            return True
        return False
