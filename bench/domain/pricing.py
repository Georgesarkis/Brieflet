"""Money rules: what a run costs, and which runs cost money at all. Pure functions, no IO."""
from __future__ import annotations

FREE_RUNNERS = {"fake"}
MODEL_ALIASES = {"sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5", "haiku": "claude-haiku-5-5"}
CACHE_MIX = (0.15, 0.15, 0.70)   # share of input that is new / cache write / cache read in a typical tool loop


def is_paid(model: dict) -> bool:
    """Claude Code on a subscription and the fake runner are $0 extra; everything else is real money."""
    if model["runner"] in FREE_RUNNERS:
        return False
    return not (model["runner"] == "claude_code" and model.get("billing", "subscription") == "subscription")


def price_of(prices: dict, model: dict) -> dict | None:
    table = prices.get("openai" if model["runner"] == "openai" else "anthropic", {}) or {}
    return table.get(MODEL_ALIASES.get(model["model"], model["model"]))


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
