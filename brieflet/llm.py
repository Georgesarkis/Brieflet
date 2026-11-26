"""One prompt in, JSON out. Backends: ollama (local, free), anthropic, openai (API keys, cost money).

Two roles: `small` (box labels; cheap) and `write` (AI_CONTEXT prose, decision records). Every call is counted so
`brieflet init` can print what it used, and cloud backends are estimated BEFORE anything is sent.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

DEFAULTS = {
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


class LLMError(RuntimeError):
    pass


@dataclass
class LLM:
    backend: str = "ollama"
    small: str | None = None
    write: str | None = None
    ollama_url: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    num_ctx: int = 12288
    timeout_s: int = 300
    calls: list = field(default_factory=list)

    def __post_init__(self):
        d = DEFAULTS[self.backend]
        self.small = self.small or d["small"]
        self.write = self.write or d["write"]
        if not self.small or not self.write:
            raise LLMError(f"{self.backend}: set --small-model and --write-model")

    @property
    def paid(self) -> bool:
        return self.backend != "ollama"

    def model(self, role: str) -> str:
        return self.write if role == "write" else self.small

    def ask_json(self, role: str, system: str, prompt: str, max_out: int):
        """→ (dict | None, raw text). Never raises for a bad answer; raises LLMError when the backend fails."""
        model = self.model(role)
        t0 = time.monotonic()
        if self.backend == "ollama":
            text, tin, tout = self._ollama(model, system, prompt, max_out)
        elif self.backend == "anthropic":
            text, tin, tout = self._anthropic(model, system, prompt, max_out)
        else:
            text, tin, tout = self._openai(model, system, prompt, max_out)
        self.calls.append({"role": role, "model": model, "in": tin, "out": tout, "secs": round(time.monotonic() - t0, 1)})
        return parse_json(text), text

    def _ollama(self, model, system, prompt, max_out):
        import requests
        body = {"model": model, "stream": False, "think": False, "format": "json",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "options": {"num_ctx": self.num_ctx, "temperature": 0, "num_predict": max_out}}
        try:
            r = requests.post(f"{self.ollama_url}/api/chat", json=body, timeout=self.timeout_s)
            r.raise_for_status()
        except requests.RequestException as e:
            raise LLMError(f"ollama: {e}") from e
        d = r.json()
        return d["message"]["content"].strip(), d.get("prompt_eval_count") or 0, d.get("eval_count") or 0

    def _anthropic(self, model, system, prompt, max_out):
        import anthropic
        try:
            resp = anthropic.Anthropic().messages.create(
                model=model, max_tokens=max(max_out, 1024), system=system + "\nAnswer with the JSON object only.",
                messages=[{"role": "user", "content": prompt}])
        except anthropic.APIStatusError as e:
            raise LLMError(f"anthropic {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"anthropic connection: {e}") from e
        if resp.stop_reason == "refusal":
            raise LLMError("anthropic: refusal")
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text.strip(), resp.usage.input_tokens or 0, resp.usage.output_tokens or 0

    def _openai(self, model, system, prompt, max_out):
        import openai
        try:
            resp = openai.OpenAI().chat.completions.create(
                model=model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        except openai.APIStatusError as e:
            raise LLMError(f"openai {e.status_code}: {e.message}") from e
        except openai.APIConnectionError as e:
            raise LLMError(f"openai connection: {e}") from e
        return (resp.choices[0].message.content or "").strip(), resp.usage.prompt_tokens or 0, resp.usage.completion_tokens or 0

    def estimate_usd(self, planned: list[tuple[str, int, int]]) -> float | None:
        """planned = [(role, prompt_chars, max_out_tokens)] → worst-case USD, None if a model has no known price."""
        if not self.paid:
            return 0.0
        tot = 0.0
        for role, chars, out in planned:
            p = PRICES.get(self.model(role))
            if not p:
                return None
            tot += (chars / CHARS_PER_TOKEN * p[0] + out * p[1]) / 1e6
        return tot


def parse_json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text or "", re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
