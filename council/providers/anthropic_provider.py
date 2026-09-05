"""Anthropic (Claude) adapter - calls a real Claude model.

Uses the SDK's structured-output helper (`client.messages.parse`,
`output_format=<pydantic model>`) rather than hand-rolled "please reply with
JSON" prompting: the API constrains the response to the schema derived from
our own pydantic model, and `response.parsed_output` is already validated
against it - including our custom business-rule validators (e.g. "a review
can't be pure agreement", "no rubber-stamp Devil's Advocate findings"),
since the SDK runs `TypeAdapter(response_model).validate_json(...)` under the
hood. A real model that violates one of those rules surfaces as a normal
pydantic ValidationError, wrapped below into a ProviderError.

Requires the `anthropic` package (`pip install ai-design-council[anthropic]`)
and an ANTHROPIC_API_KEY (see .env.example). Not exercised by the V0 test
suite (those all run against MockProvider) - this needs a real API key to
call.
"""
from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from council.providers._llm_common import estimate_cost_usd, timed_call
from council.providers.base import Provider, ProviderError, ProviderResponse

ModelT = TypeVar("ModelT", bound=BaseModel)

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_MAX_TOKENS = 8192

# Anthropic first-party API pricing, USD per 1K tokens (input, output).
# Update alongside council/pipeline model changes - these are not fetched live.
_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "claude-opus-5": (0.005, 0.025),
    "claude-sonnet-5": (0.002, 0.010),
    "claude-haiku-4-5": (0.001, 0.005),
    "claude-haiku-4-5-20251001": (0.001, 0.005),
}


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS):
        self.model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in, "
                "or pass api_key= explicitly. (Not needed for --provider mock.)"
            )
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError(
                "the 'anthropic' package is not installed. Run: pip install 'ai-design-council[anthropic]'"
            ) from exc

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

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
        anthropic = self._anthropic

        def _call():
            # `thinking` is intentionally omitted: on claude-opus-5 (the
            # default model) and claude-sonnet-5, omitting it already runs
            # adaptive thinking. Older models (e.g. Haiku) simply run
            # without thinking, which is an acceptable V0 tradeoff for a
            # smaller/cheaper model choice.
            return self._client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                output_format=response_model,
            )

        try:
            response, elapsed = timed_call(_call)
        except anthropic.AuthenticationError as exc:
            raise ProviderError(f"Anthropic authentication failed - check ANTHROPIC_API_KEY: {exc}") from exc
        except anthropic.NotFoundError as exc:
            raise ProviderError(f"Anthropic model '{self.model}' not found - check ANTHROPIC_MODEL: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError(f"Anthropic rate limit hit for role={role} round={round_num}: {exc}") from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderError(f"Anthropic request timed out for role={role} round={round_num}: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Anthropic API error ({exc.status_code}) for role={role} round={round_num}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError(f"could not reach the Anthropic API: {exc}") from exc
        except ValidationError as exc:
            raise ProviderError(
                f"Claude's structured output for role={role} round={round_num} failed schema validation:\n{exc}"
            ) from exc

        if response.stop_reason == "refusal":
            raise ProviderError(
                f"Claude refused the request for role={role} round={round_num} "
                f"(stop_details={response.stop_details!r})"
            )

        parsed = response.parsed_output
        if parsed is None:
            raise ProviderError(
                f"Claude did not return structured output for role={role} round={round_num} "
                f"(stop_reason={response.stop_reason!r})"
            )

        raw_text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
        usage = response.usage
        tokens_in = usage.input_tokens if usage else None
        tokens_out = usage.output_tokens if usage else None
        price_in, price_out = _PRICE_PER_1K.get(self.model, (0.0, 0.0))

        return ProviderResponse(
            parsed=parsed,
            raw_text=raw_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost_usd=estimate_cost_usd(tokens_in, tokens_out, price_in, price_out),
            latency_seconds=elapsed,
            provider_name=self.name,
            metadata={"model": self.model, "role": role, "round": round_num, "request_id": getattr(response, "_request_id", None)},
        )
