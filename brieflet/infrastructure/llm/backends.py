"""One HTTP call per backend: (model, system, prompt, max_out) → (text, input tokens, output tokens).

Brieflet is local-first: the built-in backend is Ollama, free, on your machine. Other backends are plugins: a
package registers a class under the `brieflet.llm_backends` entry point group (or calls `register()`), with
`complete()`, `default_models = {"small": ..., "write": ...}`, `prices = {model: (usd_in, usd_out) per 1M}` and
`paid = True`. A plugin backend counts as paid unless it says `paid = False`.
"""
from __future__ import annotations

import os
from importlib.metadata import entry_points

from ...application.ports import ModelError

GROUP = "brieflet.llm_backends"


class OllamaBackend:
    paid = False
    default_models = {"small": "qwen3.5:9b", "write": "hf.co/prism-ml/Bonsai-27B-gguf:Q1_0"}
    prices: dict = {}

    def __init__(self, url: str | None = None, num_ctx: int = 12288, timeout_s: int = 300):
        self.url = url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.num_ctx, self.timeout_s = num_ctx, timeout_s

    def complete(self, model: str, system: str, prompt: str, max_out: int) -> tuple[str, int, int]:
        import requests
        body = {"model": model, "stream": False, "think": False, "format": "json",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "options": {"num_ctx": self.num_ctx, "temperature": 0, "num_predict": max_out}}
        try:
            r = requests.post(f"{self.url}/api/chat", json=body, timeout=self.timeout_s)
            r.raise_for_status()
        except requests.RequestException as e:
            raise ModelError(f"ollama: {e}") from e
        d = r.json()
        return d["message"]["content"].strip(), d.get("prompt_eval_count") or 0, d.get("eval_count") or 0


BUILT_IN = {"ollama": OllamaBackend}
_registered: dict[str, type] = {}


def register(name: str, cls: type) -> None:
    """Add a backend at runtime (plugins without packaging, tests)."""
    _registered[name] = cls


def _plugins() -> dict:
    return {ep.name: ep for ep in entry_points(group=GROUP)}


def available() -> list[str]:
    return sorted({*BUILT_IN, *_registered, *_plugins()})


def backend_class(name: str) -> type:
    if name in BUILT_IN:
        return BUILT_IN[name]
    if name in _registered:
        return _registered[name]
    ep = _plugins().get(name)
    if ep is None:
        raise ModelError(f"unknown backend {name}. Installed: {', '.join(available())}")
    return ep.load()
