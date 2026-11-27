"""Big repos: cut a component list to max boxes. Most important projects stay; the rest become folder group boxes."""
from __future__ import annotations

import re

from ...domain.components import Component, Link

MAX_INFRA = 5
TOOLING = re.compile(r"(^|[-/@_])(tsconfig|eslint|prettier|config|configs|tooling|types)($|[-_/])", re.I)


def collapse(comps: list[Component], links: list[Link], refs: dict[str, list[str]], max_boxes: int):
    """→ (components, links, project_refs) with at most max_boxes components."""
    used = {c.id: 0 for c in comps}
    for l in links:
        used[l.target] = used.get(l.target, 0) + 1
    infra = sorted((c for c in comps if c.path is None), key=lambda c: -used[c.id])[:MAX_INFRA]
    projects = [c for c in comps if c.path is not None]
    ranked = sorted(projects, key=lambda c: (-_score(c, used), c.path or ""))
    slots = max_boxes - len(infra)
    singles, groups = _fit(ranked, slots)
    box_of = {c.id: c.id for c in [*infra, *singles]}
    group_boxes = []
    for key, members in groups.items():
        if len(members) == 1:               # a group of one is just that project
            singles.append(members[0])
            box_of[members[0].id] = members[0].id
            continue
        box = _group_box(key, members)
        group_boxes.append(box)
        box_of.update({m.id: box.id for m in members})
    out_links: dict[tuple[str, str], Link] = {}
    for l in links:
        a, b = box_of.get(l.source), box_of.get(l.target)
        if a and b and a != b and ((a, b) not in out_links or not out_links[(a, b)].label):
            out_links[(a, b)] = Link(a, b, l.label, l.dotted)
    keep = [c for c in comps if c.id in {x.id for x in [*infra, *singles]}]   # original order
    return [*keep, *group_boxes], list(out_links.values()), {k: v for k, v in refs.items() if k in box_of and box_of[k] == k}


def _score(c: Component, used: dict[str, int]) -> int:
    """Things that run first (what a developer asks about), then the libraries most others use. Shared lint/tsconfig
    packages are used by everyone but explain nothing."""
    tooling = TOOLING.search(c.name) is not None
    return (25 if c.kind == "service" else 0) + (5 if c.entry else 0) + min(used[c.id], 20) - (30 if tooling else 0)


def _fit(ranked: list[Component], slots: int):
    """Most single boxes k such that k + the group boxes for the rest fit. Groups by parent folder ("packages/ui/*")
    or by top folder ("packages/*"), whichever keeps more singles (parent wins a tie: more detail)."""
    best = None
    for depth in ("parent", "top"):
        for k in range(slots - 1, -1, -1):
            groups = _groups(ranked[k:], depth)
            if k + len(groups) <= slots:
                if best is None or k > len(best[0]):
                    best = (ranked[:k], groups)
                break
    if best:
        return best
    groups = _groups(ranked, "top")
    big = sorted(groups, key=lambda g: -len(groups[g]))
    kept = {g: groups[g] for g in big[: slots - 1]}
    kept["…"] = [m for g in big[slots - 1:] for m in groups[g]]
    return [], kept


def _groups(rest: list[Component], depth: str) -> dict[str, list[Component]]:
    out: dict[str, list[Component]] = {}
    for c in rest:
        parts = [p for p in (c.path or "").split("/") if p not in ("", ".")]
        key = "/".join(parts[:-1]) if depth == "parent" else (parts[0] if len(parts) > 1 else "")
        out.setdefault(key, []).append(c)
    return out


def _group_box(key: str, members: list[Component]) -> Component:
    name = f"{key}/*" if key not in ("", "…") else ("other parts" if key == "…" else "other top folders")
    kinds = {m.kind for m in members}
    box = Component("grp_" + ("".join(ch if ch.isalnum() else "_" for ch in key).lower() or "root"), name, "group", "box",
                    key if key not in ("", "…") else None, f"{len(members)} " + ("services" if kinds == {"service"} else
                                                                                "packages"))
    box.packages = [m.name for m in members][:8]
    return box
