"""Provider abstraction.

A Provider turns (role, round, prompts, structured context) into a validated
pydantic model. Real providers (OpenAI/Anthropic/Ollama) call an LLM and parse
its JSON output; MockProvider computes a deterministic simulated response
without any network access, so the whole pipeline is testable offline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class ProviderResponse:
    """Envelope returned by every provider call, real or mock."""

    parsed: BaseModel
    raw_text: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    estimated_cost_usd: float | None = None
    latency_seconds: float = 0.0
    provider_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce a schema-valid response."""


class Provider:
    """Base interface every provider (mock or real) must implement."""

    name: str = "base"

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
        """Produce a response_model-validated ProviderResponse.

        Parameters
        ----------
        role: agent role id (e.g. "architect", "qa_security")
        round_num: 1-5 (which debate round this call belongs to)
        system_prompt: the agent's persona/system instructions (from its role config)
        user_prompt: the rendered task prompt for this call (brief + any prior-round
            context serialized as text - used verbatim by real LLM providers)
        response_model: the pydantic model the output must validate against
        context: structured data available for this call (e.g. prior proposals as
            dicts). Real providers may ignore it (it's already embedded in
            user_prompt as text); MockProvider uses it directly to compute a
            deterministic simulated answer.
        """
        raise NotImplementedError

    @staticmethod
    def _timed(fn):
        start = time.perf_counter()
        result = fn()
        return result, time.perf_counter() - start
