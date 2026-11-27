"""Runners answer one question inside one arm's working copy and return the same row shape (domain/results.py).

Built in: `fake` (offline, for tests). Real readers are plugins: a package
registers `run(question, workdir, model, price, max_usd_this_run) -> row` under the `brieflet.bench_runners`
entry point group. Compare arms only WITHIN one runner + model: the harnesses differ.
"""
from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points

GROUP = "brieflet.bench_runners"
MODULES = {"fake": "fake"}


def runner_for(name: str):
    """RunnerFactory port: runner name from bench.yaml → its run() function (loaded only when used)."""
    if name in MODULES:
        return import_module(f"{__name__}.{MODULES[name]}").run
    ep = {e.name: e for e in entry_points(group=GROUP)}.get(name)
    if ep is None:
        raise ValueError(f"unknown runner {name}")
    return ep.load()
