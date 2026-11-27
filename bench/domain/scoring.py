"""Quality score per answer, 0-3, computed from the judge's per-point verdict (same rule for every arm):
  3 = every must point, nothing wrong · 2 = ≥ 2/3 of must points, no major error · 1 = some · 0 = none or a major error
"""
from __future__ import annotations

import json
import re

GOOD = 2   # an answer scoring ≥ GOOD counts as a good answer


def score(n_must: int, verdict: dict) -> int:
    hits = sum(1 for x in (verdict.get("must") or [])[:n_must] if x is True)
    major = any((w or {}).get("severity") == "major" for w in verdict.get("wrong_claims") or [])
    if major or hits == 0:
        return 0
    frac = hits / max(n_must, 1)
    if frac == 1 and not verdict.get("wrong_claims"):
        return 3
    return 2 if frac >= 2 / 3 else 1


def parse_verdict(text: str) -> dict | None:
    """The judge's JSON ({"must": [...], "wrong_claims": [...]}) or None."""
    for cand in (text, (re.search(r"\{.*\}", text or "", re.S) or [None])[0]):
        try:
            d = json.loads(cand)
            if isinstance(d, dict) and isinstance(d.get("must"), list):
                return d
        except (TypeError, ValueError):
            pass
    return None
