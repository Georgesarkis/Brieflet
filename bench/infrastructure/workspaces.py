"""Workspaces: temp copies of a repo at the pinned commit with one arm's docs laid over it.

An arm can also name shell commands: `prepare` runs once in its fresh copy (e.g. build a tool's index; not timed),
`cleanup` runs when the temp area closes (e.g. stop a tool's background daemon). `{dir}` = the copy's path.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from brieflet.domain import learned as L
from brieflet.presentation.views.learned_md import RULE, render

from ..application.config import BenchConfig
from ..application.ports import ResultsStore


class SetupError(Exception):
    """The benchmark can't start: a repo at the wrong commit, a missing overlay or learning file."""


class ArmWorkspaces:
    def __init__(self, cfg: BenchConfig, store: ResultsStore, tmp: Path, log=print):
        self.cfg, self.store, self.tmp, self.log = cfg, store, Path(tmp), log
        self._cleanups: list[tuple[str, Path]] = []

    def arm(self, repo: str, arm: str) -> Path:
        """Repo copy (no .git), our own docs stripped, the arm's overlay folders + CLAUDE.md on top. Made once."""
        dst = self.tmp / f"{repo}-{arm}"
        if dst.exists():
            return dst
        rc = self.cfg.repos[repo]
        src = self.cfg.path(rc["path"])
        self._check_pinned(repo, src, str(rc.get("sha") or ""))
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git"), symlinks=False,
                        ignore_dangling_symlinks=True)   # cal.com: packages/prisma/.env -> missing ../../.env
        for s in rc.get("strip", []):
            p = dst / s
            shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
        a = self.cfg.arm(arm)
        for ov in a.get("overlay", []):
            ov = self.cfg.path(ov, repo)
            if not ov.is_dir():
                raise SetupError(f"arm {arm}: overlay folder missing: {ov} (generate it first)")
            shutil.copytree(ov, dst, dirs_exist_ok=True)
        if a.get("claude_md"):
            (dst / "CLAUDE.md").write_text(a["claude_md"])
        for cmd in a.get("prepare", []):
            self.log(f"prepare {arm}: {cmd}")
            p = _sh(cmd, dst)
            if p.returncode != 0:
                raise SetupError(f"arm {arm}: prepare failed: {cmd}\n{(p.stderr or p.stdout)[-500:]}")
        self._cleanups += [(cmd, dst) for cmd in a.get("cleanup", [])]
        return dst

    def close(self) -> None:
        """Run the arms' cleanup commands (best effort)."""
        for cmd, d in self._cleanups:
            _sh(cmd, d if d.exists() else self.tmp)
        self._cleanups.clear()

    @staticmethod
    def _check_pinned(repo: str, src: Path, want: str) -> None:
        if len(want) != 40:
            return
        head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if head != want:
            raise SetupError(f"{repo}: {src} is at {head[:7] or '?'}, config pins {want[:7]}: git -C {src} checkout {want}")

    def learning(self, repo: str, model: str, arm: str, fold: int) -> Path:
        """Fresh copy for a learning pass: empty LEARNED.md + the CLAUDE.md rule to fill it."""
        wd = self.tmp / f"{repo}-{arm}-{model}-learn{fold + 1}"
        shutil.copytree(self.arm(repo, arm), wd)
        (wd / L.FILE).write_text(render([]), encoding="utf-8")
        _add_rule(wd)
        return wd

    def measured_learn(self, repo: str, model: str, arm: str, qid: str) -> Path:
        """Measured run of a learn arm: base arm + LEARNED.md from the OTHER folds only (never this question's)."""
        fold = self.cfg.fold_of(repo, qid)
        dst = self.tmp / f"{repo}-{arm}-{model}-test{fold + 1}"
        if dst.exists():
            return dst
        shutil.copytree(self.arm(repo, arm), dst)
        facts = []
        for i in range(len(self.cfg.folds(repo))):
            if i == fold:
                continue
            f = self.store.learned_file(repo, model, arm, i)
            if not f.exists():
                raise SetupError(f"arm {arm}: {f} missing. Run `python -m bench learn` first.")
            facts += L.parse_facts(f.read_text(encoding="utf-8"))
        kept, _ = L.prune(facts, lambda p: _exists_in(dst, p))
        (dst / L.FILE).write_text(render(kept), encoding="utf-8")
        _add_rule(dst)
        return dst

    def add_learned(self, workdir: Path, answer: str) -> tuple[int, list[str]]:
        """Facts from the answer's LEARNED: block → workdir/LEARNED.md. → (facts added, dropped reasons)."""
        new = L.facts_from_answer(answer)
        if not new:
            return 0, []
        f = Path(workdir) / L.FILE
        old = L.parse_facts(f.read_text(encoding="utf-8")) if f.exists() else []
        stamp = f"· {date.today().isoformat()}"
        merged, dropped = L.prune(old + [L.LearnedFact(n.fact, n.path, n.rest or stamp) for n in new],
                                  lambda p: _exists_in(workdir, p))
        f.write_text(render(merged), encoding="utf-8")
        return len(merged) - len([e for e in old if e in merged]), dropped

    @staticmethod
    def learned_text(workdir: Path) -> str | None:
        f = Path(workdir) / L.FILE
        return f.read_text(encoding="utf-8") if f.exists() else None


def _sh(cmd: str, d: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd.replace("{dir}", str(d)), shell=True, cwd=d, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=3600)


def _exists_in(root: Path, rel: str) -> bool:
    root = Path(root).resolve()
    p = (root / rel.split(":")[0].split("#")[0]).resolve()
    return (p == root or root in p.parents) and p.exists()


def _add_rule(wd: Path) -> None:
    cm = wd / "CLAUDE.md"
    txt = cm.read_text(encoding="utf-8") if cm.exists() else ""
    if "LEARNED.md" not in txt or "When the docs were not enough" not in txt:
        cm.write_text(txt.rstrip() + "\n" + RULE, encoding="utf-8")


def opener(cfg: BenchConfig, store: ResultsStore, prefix: str):
    """OpenWorkspaces port: `with open_ws() as ws:` → temp area, removed afterwards."""
    @contextmanager
    def open_ws() -> Iterator[ArmWorkspaces]:
        with tempfile.TemporaryDirectory(prefix=prefix) as t:
            ws = ArmWorkspaces(cfg, store, Path(t))
            try:
                yield ws
            finally:
                ws.close()
    return open_ws
