"""Money rules: what a run costs, and which runs cost money at all. Pure functions, no IO."""
from __future__ import annotations

FREE_RUNNERS = {"fake"}
CACHE_MIX = (0.15, 0.15, 0.70)   # share of input that is new / cache write / cache read in a typical tool loop


def is_paid(model: dict) -> bool:
    """The fake runner and any `billing: subscription` model are $0 extra; everything else is real money."""
    return model.get("runner") not in FREE_RUNNERS and not is_subscription(model)


def is_subscription(model: dict) -> bool:
    """Billed by a flat plan the user already pays (no extra money, but it uses the plan's limit)."""
    return model.get("billing") == "subscription"


def price_of(prices: dict, model: dict) -> dict | None:
    """prices.yaml has one section per runner name: {runner: {model: {input, output, cache_read, cache_write}}}."""
    return (prices.get(model.get("runner")) or {}).get(model.get("model"))


def usage_cost(usage: dict, price: dict | None) -> float | None:
    """USD for measured usage; None without a price."""
    if not price:
        return None
    return (usage.get("input_tokens", 0) * price["input"] + usage.get("output_tokens", 0) * price["output"]
            + usage.get("cache_read", 0) * price.get("cache_read", price["input"])
            + usage.get("cache_write", 0) * price.get("cache_write", price["input"])) / 1e6


def estimate_run(tokens: dict, price: dict | None) -> tuple[float, float] | None:
    """(low, high) USD for one question run. Low = most input read from cache (tool loops re-send the prefix),
    high = no cache hits at all. Budget checks use high."""
    if not price:
        return None
    i, out = tokens["input"], tokens["output"] * price["output"]
    new, write, read = CACHE_MIX
    low = (new * i * price["input"] + write * i * price.get("cache_write", price["input"])
           + read * i * price.get("cache_read", price["input"]) + out) / 1e6
    return low, (i * price["input"] + out) / 1e6
