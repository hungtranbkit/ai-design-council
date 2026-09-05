"""OpenAI adapter skeleton.

Not required for V0 tests (those all run against MockProvider). Requires the
`openai` package (`pip install ai-design-council[openai]`) and an
OPENAI_API_KEY. Kept intentionally small - this is a skeleton to plug in a
real provider, not a fully hardened production client.
"""
from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel

from council.providers._llm_common import build_json_instruction, estimate_cost_usd, parse_and_validate, timed_call
from council.providers.base import Provider, ProviderError, ProviderResponse

ModelT = TypeVar("ModelT", bound=BaseModel)

# Rough, approximate public pricing (USD per 1K tokens) - update as needed.
# Not authoritative; only used to populate an estimated_cost_usd metric.
_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.0004, 0.0016),
    "gpt-4.1": (0.002, 0.008),
}


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL") or None
        if not self.api_key:
            raise ProviderError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in, "
                "or pass api_key= explicitly. (Not needed for --provider mock.)"
            )
        try:
            import openai  # noqa: F401
        except ImportError as exc:
            raise ProviderError(
                "the 'openai' package is not installed. Run: pip install 'ai-design-council[openai]'"
            ) from exc

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
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        full_user_prompt = f"{user_prompt}\n\n{build_json_instruction(response_model)}"

        def _call():
            return client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_user_prompt},
                ],
                temperature=0.4,
            )

        response, elapsed = timed_call(_call)
        raw_text = response.choices[0].message.content or ""
        parsed = parse_and_validate(raw_text, response_model)

        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
        tokens_out = getattr(usage, "completion_tokens", None) if usage else None
        price_in, price_out = _PRICE_PER_1K.get(self.model, (0.0, 0.0))

        return ProviderResponse(
            parsed=parsed,
            raw_text=raw_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost_usd=estimate_cost_usd(tokens_in, tokens_out, price_in, price_out),
            latency_seconds=elapsed,
            provider_name=self.name,
            metadata={"model": self.model, "role": role, "round": round_num},
        )
