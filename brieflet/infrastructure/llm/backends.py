"""One HTTP/SDK call per backend: (model, system, prompt, max_out) → (text, input tokens, output tokens).

SDKs are imported lazily, so the free local path needs only `requests`.
"""
from __future__ import annotations

import os

from ...application.ports import ModelError


class OllamaBackend:
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


class AnthropicBackend:
    def complete(self, model: str, system: str, prompt: str, max_out: int) -> tuple[str, int, int]:
        import anthropic
        try:
            resp = anthropic.Anthropic().messages.create(
                model=model, max_tokens=max(max_out, 1024), system=system + "\nAnswer with the JSON object only.",
                messages=[{"role": "user", "content": prompt}])
        except anthropic.APIStatusError as e:
            raise ModelError(f"anthropic {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ModelError(f"anthropic connection: {e}") from e
        if resp.stop_reason == "refusal":
            raise ModelError("anthropic: refusal")
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text.strip(), resp.usage.input_tokens or 0, resp.usage.output_tokens or 0


class OpenAIBackend:
    def complete(self, model: str, system: str, prompt: str, max_out: int) -> tuple[str, int, int]:
        import openai
        try:
            resp = openai.OpenAI().chat.completions.create(
                model=model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        except openai.APIStatusError as e:
            raise ModelError(f"openai {e.status_code}: {e.message}") from e
        except openai.APIConnectionError as e:
            raise ModelError(f"openai connection: {e}") from e
        return (resp.choices[0].message.content or "").strip(), resp.usage.prompt_tokens or 0, resp.usage.completion_tokens or 0


BACKENDS = {"ollama": OllamaBackend, "anthropic": AnthropicBackend, "openai": OpenAIBackend}
