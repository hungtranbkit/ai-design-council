"""OpenAI adapter - calls a real OpenAI model via the Responses API.

Uses the SDK's structured-output helper (`client.responses.parse`,
`text_format=<pydantic model>`) rather than hand-rolled "please reply with
JSON" prompting: OpenAI's strict JSON-schema mode constrains the response to
the schema derived from our own pydantic model, and `response.output_parsed`
is already validated against it - including our custom business-rule
validators (e.g. "a review can't be pure agreement", "no rubber-stamp
Devil's Advocate findings"), since the SDK runs
`response_model.model_validate_json(...)` under the hood. A real model that
violates one of those rules surfaces as a normal pydantic ValidationError,
wrapped below into a ProviderError. See council/providers/anthropic_provider.py
for the same pattern against Claude.

Requires the `openai` package (`pip install ai-design-council[openai]`) and
an OPENAI_API_KEY (see .env.example). Not exercised by the V0 test suite
(those all run against MockProvider) - this needs a real API key to call.
"""
from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from council.providers._llm_common import estimate_cost_usd, timed_call
from council.providers.base import Provider, ProviderError, ProviderResponse

ModelT = TypeVar("ModelT", bound=BaseModel)

DEFAULT_MODEL = "gpt-6-astra"
DEFAULT_MAX_OUTPUT_TOKENS = 8192

# OpenAI API pricing, USD per 1K tokens (input, output). Update alongside
# council/pipeline model changes - these are not fetched live.
_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-6-astra": (0.010, 0.050),
    "gpt-5.6-sol": (0.004, 0.020),
    "gpt-5.4-mini": (0.00075, 0.0045),
}


def _extract_refusal(response: Any) -> str | None:
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for content in item.content:
                if getattr(content, "type", None) == "refusal":
                    return content.refusal
    return None


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ):
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self.max_output_tokens = max_output_tokens
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL") or None
        if not api_key:
            raise ProviderError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in, "
                "or pass api_key= explicitly. (Not needed for --provider mock.)"
            )
        try:
            import openai
        except ImportError as exc:
            raise ProviderError(
                "the 'openai' package is not installed. Run: pip install 'ai-design-council[openai]'"
            ) from exc

        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

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
        openai = self._openai

        def _call():
            return self._client.responses.parse(
                model=self.model,
                instructions=system_prompt,
                input=user_prompt,
                max_output_tokens=self.max_output_tokens,
                text_format=response_model,
            )

        try:
            response, elapsed = timed_call(_call)
        except openai.AuthenticationError as exc:
            raise ProviderError(f"OpenAI authentication failed - check OPENAI_API_KEY: {exc}") from exc
        except openai.NotFoundError as exc:
            raise ProviderError(f"OpenAI model '{self.model}' not found - check OPENAI_MODEL: {exc}") from exc
        except openai.RateLimitError as exc:
            raise ProviderError(f"OpenAI rate limit hit for role={role} round={round_num}: {exc}") from exc
        except openai.APITimeoutError as exc:
            raise ProviderError(f"OpenAI request timed out for role={role} round={round_num}: {exc}") from exc
        except openai.APIStatusError as exc:
            raise ProviderError(f"OpenAI API error ({exc.status_code}) for role={role} round={round_num}: {exc}") from exc
        except openai.APIConnectionError as exc:
            raise ProviderError(f"could not reach the OpenAI API: {exc}") from exc
        except ValidationError as exc:
            raise ProviderError(
                f"OpenAI's structured output for role={role} round={round_num} failed schema validation:\n{exc}"
            ) from exc

        if response.status not in (None, "completed"):
            refusal = _extract_refusal(response)
            detail = refusal or (response.error.message if response.error else None) or response.incomplete_details
            raise ProviderError(
                f"OpenAI response not completed for role={role} round={round_num} "
                f"(status={response.status!r}): {detail}"
            )

        parsed = response.output_parsed
        if parsed is None:
            raise ProviderError(
                f"OpenAI did not return structured output for role={role} round={round_num} "
                f"(status={response.status!r})"
            )

        raw_text = response.output_text
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
