"""Ollama (local model) adapter skeleton.

Not required for V0 tests (those all run against MockProvider). Talks to a
local Ollama server's HTTP API (default http://localhost:11434) - no API key
needed, but Ollama must be running with the requested model pulled.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, TypeVar

from pydantic import BaseModel

from council.providers._llm_common import build_json_instruction, parse_and_validate, timed_call
from council.providers.base import Provider, ProviderError, ProviderResponse

ModelT = TypeVar("ModelT", bound=BaseModel)


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    def complete(
        self,
        *,
        role: str,
        round_num: int,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
        context: dict[str, Any],
    ) -> ProviderResponse:
        full_user_prompt = f"{user_prompt}\n\n{build_json_instruction(response_model)}"
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": full_user_prompt,
                "system": system_prompt,
                "stream": False,
                "format": "json",
            }
        ).encode()

        def _call():
            req = urllib.request.Request(
                f"{self.base_url}/api/generate", data=payload, headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return json.loads(resp.read())
            except urllib.error.URLError as exc:
                raise ProviderError(
                    f"could not reach Ollama at {self.base_url} (is `ollama serve` running?): {exc}"
                ) from exc

        response, elapsed = timed_call(_call)
        raw_text = response.get("response", "")
        parsed = parse_and_validate(raw_text, response_model)

        # Ollama reports token counts as *_count fields when available.
        tokens_in = response.get("prompt_eval_count")
        tokens_out = response.get("eval_count")

        return ProviderResponse(
            parsed=parsed,
            raw_text=raw_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost_usd=0.0,  # local inference: no per-token API cost
            latency_seconds=elapsed,
            provider_name=self.name,
            metadata={"model": self.model, "role": role, "round": round_num},
        )
