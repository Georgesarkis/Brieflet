"""LanguageModel port: two roles (`small` = box labels, `write` = prose) on one backend, every call counted.

Ollama is local and free (default). Cloud backends cost money and are estimated BEFORE anything is sent.
"""
from __future__ import annotations

import time

from ...application.ports import WRITE, ModelError
from .backends import BACKENDS
from .json_reply import parse_json

DEFAULT_MODELS = {
    "ollama": {"small": "qwen3.5:9b", "write": "hf.co/prism-ml/Bonsai-27B-gguf:Q1_0"},
    "anthropic": {"small": "claude-haiku-5-5", "write": "claude-sonnet-5-5"},
    "openai": {"small": None, "write": None},  # set --small-model / --write-model
}
# USD per 1M tokens (input, output). Estimate only; check current prices before a big run.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
CHARS_PER_TOKEN = 3.5


class ModelGateway:
    def __init__(self, backend: str = "ollama", small: str | None = None, write: str | None = None, client=None):
        if backend not in BACKENDS:
            raise ModelError(f"unknown backend {backend}")
        self.backend = backend
        self.small = small or DEFAULT_MODELS[backend]["small"]
        self.write = write or DEFAULT_MODELS[backend]["write"]
        if not self.small or not self.write:
            raise ModelError(f"{backend}: set --small-model and --write-model")
        self.client = client or BACKENDS[backend]()
        self.calls: list[dict] = []

    @property
    def paid(self) -> bool:
        return self.backend != "ollama"

    def model(self, role: str) -> str:
        return self.write if role == WRITE else self.small

    def ask_json(self, role: str, system: str, prompt: str, max_out: int) -> tuple[dict | None, str]:
        """→ (JSON object | None, raw text). A bad answer returns None; a failing backend raises ModelError."""
        model, t0 = self.model(role), time.monotonic()
        text, tin, tout = self.client.complete(model, system, prompt, max_out)
        self.calls.append({"role": role, "model": model, "in": tin, "out": tout, "secs": round(time.monotonic() - t0, 1)})
        return parse_json(text), text

    def estimate_usd(self, planned: list[tuple[str, int, int]]) -> float | None:
        """planned = [(role, prompt chars, max output tokens)] → worst-case USD; None if a model has no price."""
        if not self.paid:
            return 0.0
        total = 0.0
        for role, chars, out in planned:
            price = PRICES.get(self.model(role))
            if not price:
                return None
            total += (chars / CHARS_PER_TOKEN * price[0] + out * price[1]) / 1e6
        return total
