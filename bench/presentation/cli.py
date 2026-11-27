"""Brieflet benchmark: does a short AI context make a model read fewer tokens and answer faster, without worse answers?

  python -m bench plan   [-c bench.yaml]                      matrix + cost estimate. Never spends.
  python -m bench learn  [-c bench.yaml] [--yes] [--only MODEL]  learning pass for arms with `learn:` (writes LEARNED.md per fold).
  python -m bench run    [-c bench.yaml] --yes [--only MODEL] [--resume]  runs it. Paid runners need --yes AND estimate ≤ max_usd.
  python -m bench judge  [-c bench.yaml] [--yes]               quality 0-3 per answer (needs a `judge:` block).
  python -m bench dashboard [-c bench.yaml]                   one HTML page: results, models, generated docs.
  python -m bench report [-c bench.yaml]                      median table per repo × model × arm.

Money rule: nothing that costs money runs without `--yes`, and `run` re-checks the estimate against max_usd first.
This module is the controller: it parses the command, calls one use case and prints the view.
"""
from __future__ import annotations

import argparse
import sys

from ..application.outcome import Outcome
from ..application.ports import JudgeClient, RunnerFactory
from . import plan_table, report_table

COMMANDS = ["plan", "learn", "run", "judge", "report", "dashboard"]


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m bench")
    ap.add_argument("cmd", choices=COMMANDS)
    ap.add_argument("-c", "--config", default="bench.yaml")
    ap.add_argument("--yes", action="store_true", help="allow paid runs (after reading `plan`)")
    ap.add_argument("--only", help="only this model name from the config")
    ap.add_argument("--resume", action="store_true", help="skip runs that already worked (after a usage limit)")
    return ap


def main(argv=None, runner_for: RunnerFactory | None = None, judge: JudgeClient | None = None) -> int:
    """runner_for / judge: swap in fakes (tests); default = the real runners and judge clients."""
    from ..bootstrap import BenchApp, SetupError
    a = parser().parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up in a nohup log right away
    app = BenchApp(a.config, runner_for, judge)
    if a.cmd == "plan":
        print(plan_table.render(app.plan().execute(a.only)))
        return int(Outcome.OK)
    if a.cmd == "report":
        print("\n".join(report_table.render(app.store.runs(), app.store.verdicts(), app.cfg.arms)))
        return int(Outcome.OK)
    try:
        rc = _command(app, a)
    except SetupError as e:
        print(e)
        rc = Outcome.REFUSED
    app.publish_dashboard()
    return int(rc)


def _command(app, a) -> Outcome:
    if a.cmd == "learn":
        return app.learn().execute(a.yes, a.only)
    if a.cmd == "run":
        plan = app.plan().execute(a.only)
        print(plan_table.render(plan))
        return app.run().execute(plan, a.yes, a.only, a.resume)
    if a.cmd == "judge":
        return app.judge().execute(a.yes)
    return Outcome.OK
