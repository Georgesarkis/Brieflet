"""LanguageModel port: two roles (`small` = box labels, `write` = prose) on one backend, every call counted.

Ollama is local and free (default). A paid plugin backend is estimated BEFORE anything is sent.
"""
from __future__ import annotations

import time

from ...application.ports import WRITE, ModelError
from .backends import backend_class
from .json_reply import parse_json

CHARS_PER_TOKEN = 3.5


class ModelGateway:
    def __init__(self, backend: str = "ollama", small: str | None = None, write: str | None = None, client=None):
        self.backend = backend
        self.client = client or backend_class(backend)()
        defaults = getattr(self.client, "default_models", None) or {}
        self.small = small or defaults.get("small")
        self.write = write or defaults.get("write")
        if not self.small or not self.write:
            raise ModelError(f"{backend}: set --small-model and --write-model")
        self.paid: bool = getattr(self.client, "paid", True)   # unknown = paid, so the money gate applies
        self.prices: dict = getattr(self.client, "prices", None) or {}
        self.calls: list[dict] = []

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
        for role, chars, out in planned:   # prices: USD per 1M tokens (input, output), from the backend
            price = self.prices.get(self.model(role))
            if not price:
                return None
            total += (chars / CHARS_PER_TOKEN * price[0] + out * price[1]) / 1e6
        return total
