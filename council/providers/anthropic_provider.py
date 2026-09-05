"""Anthropic (Claude) adapter skeleton.

Not required for V0 tests (those all run against MockProvider). Requires the
`anthropic` package (`pip install ai-design-council[anthropic]`) and an
ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel

from council.providers._llm_common import build_json_instruction, estimate_cost_usd, parse_and_validate, timed_call
from council.providers.base import Provider, ProviderError, ProviderResponse

ModelT = TypeVar("ModelT", bound=BaseModel)

# Rough, approximate public pricing (USD per 1K tokens) - update as needed.
_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (0.003, 0.015),
    "claude-haiku-4-5-20251001": (0.0008, 0.004),
}


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ProviderError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in, "
                "or pass api_key= explicitly. (Not needed for --provider mock.)"
            )
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise ProviderError(
                "the 'anthropic' package is not installed. Run: pip install 'ai-design-council[anthropic]'"
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
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        full_user_prompt = f"{user_prompt}\n\n{build_json_instruction(response_model)}"

        def _call():
            return client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": full_user_prompt}],
            )

        response, elapsed = timed_call(_call)
        raw_text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        parsed = parse_and_validate(raw_text, response_model)

        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "input_tokens", None) if usage else None
        tokens_out = getattr(usage, "output_tokens", None) if usage else None
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
